"""
Engine for dwelling-fire synthetic documents.

A *profile* (``profiles/<source stem>.py``) describes one source PDF:

    SOURCE  = r"Carrier Folder\\dwelling_fire\\name.pdf"     # under Data/original data
    draw(v, C)   -> dict of drawn values (v: seeded Values, C: dfire.corpora)
    REPLACE      = [ (printed_text, "{template}", {options}), ... ]
    gold(d)      -> gold dict shaped like the canonical dwelling_fire schema
    STATIC       = [regex, ...]   printed numbers/dates that are form furniture
    audit(d)     -> optional list of arithmetic problems

The engine draws values, rewrites the printed text in the real source PDF, has
the profile build the gold, and then checks it:

  schema     the gold validates against the live canonical schema
  page refs  every value the gold says is printed is found on a page
  leak       none of the source's replaced text survives in the new PDF
  unmapped   every date / amount / phone / ZIP / long number printed in the
             source is either replaced (and so in the gold) or declared STATIC
  audit      the profile's own arithmetic, plus effective <= expiration
  scan       the scanned twin has no text layer

Only the scanned PDF and the gold are kept, named ``<source stem>_001`` ...
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import re
import shutil
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF

from .. import pageref
from ..corpus import Built, Report
from ..fields import as_date, date_fv, derived, fmt_money, fv, money, money_from, walk_indexed
from ..generator import _base14, _bounded, _color
from ..scan import by_key as scan_by_key, scan_pdf
from ..schema import CanonicalSchema
from ..values import Values
from . import corpora as C

LOB = "dwelling_fire"


# -- helpers a profile's gold() may use -------------------------------------------------

def amt(n, cents=True, evidence=None):
    """A money FieldValue printed as $1,438.00 (or $1,438 with cents=False)."""
    return money(C.usd(n, cents), evidence)


def addr(line_1=None, city=None, state=None, postal_code=None, county=None,
         line_2=None, country=None):
    """An address object of FieldValues; only the parts given are emitted."""
    parts = {"line_1": line_1, "line_2": line_2, "city": city, "state": state,
             "postal_code": postal_code, "county": county, "country": country}
    return {k: fv(v) for k, v in parts.items() if v not in (None, "")}


def logo(raw, pages=(1,), parsed=None):
    """A value printed only inside an image (a logo), so its text cannot be searched.

    It is stated on ``pages`` by inspection; ``derived`` because a text search of
    the page cannot confirm it, and marked so the page reference is still kept.
    """
    field = derived(raw) if parsed is None else derived(raw, parsed=parsed)
    field["_fixed_pages"] = list(pages)
    return field


def extra(label, value, section=None, evidence=None):
    """One additional_fields entry: a printed label and its value as a FieldValue."""
    field = value if isinstance(value, dict) else fv(value, evidence=evidence)
    return {"section": section, "label": label, "value": field}


# -- profiles ----------------------------------------------------------------------------

@dataclass
class Entry:
    src: str
    new: object
    page: Optional[int] = None
    nth: Optional[int] = None
    raw: bool = False
    optional: bool = False
    leak: bool = True
    exact: bool = False           # the whole (stripped) span must equal src
    size: Optional[float] = None  # redraw at this font size (redaction overlays are tiny)
    font: Optional[str] = None    # base-14 name: helv hebo heit tiro tibo cour

    def resolve(self, d):
        if callable(self.new):
            return str(self.new(d))
        return str(self.new).format(**d)


class Profile:
    def __init__(self, module):
        self.module = module
        self.source = Path(module.SOURCE.replace("\\", "/"))
        self.key = self.source.stem
        self.carrier = self.source.parts[0]
        self.entries = []
        for item in module.REPLACE:
            src, new = item[0], item[1]
            opts = item[2] if len(item) > 2 else {}
            self.entries.append(Entry(src, new, **opts))
        self.static = [re.compile(s) for s in getattr(module, "STATIC", [])]
        self.ignore_pairs = [re.compile(s) for s in getattr(module, "IGNORE_PAIRS", [])]
        self.furniture = [re.compile(s) for s in getattr(module, "FURNITURE", [])]

    def __repr__(self):
        return "<Profile %s/%s>" % (self.carrier, self.key)


def load_profiles(only=None):
    from . import profiles as pkg
    found = []
    for info in pkgutil.iter_modules(pkg.__path__):
        try:
            module = importlib.import_module("%s.%s" % (pkg.__name__, info.name))
            if hasattr(module, "SOURCE"):
                found.append(Profile(module))
        except Exception as exc:  # one broken profile must not stop the others
            warnings.warn("profile %s failed to load: %s: %s" % (info.name, type(exc).__name__, exc))
    if only:
        needles = [o.lower() for o in only]
        found = [p for p in found
                 if any(n in ("%s/%s" % (p.carrier, p.key)).lower() for n in needles)]
    return sorted(found, key=lambda p: (p.carrier, p.key))


# -- PDF editing ------------------------------------------------------------------------

_NUMERIC = re.compile(r"^[\s\-]*\$?\s*[\d,]+(?:\.\d+)?%?$")

_VARIABLE = re.compile(
    r"\$\s?-?[\d,]+(?:\.\d\d)?"                # money
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"            # date
    r"|\b\d{3}[-.)\s]\s?\d{3}[-.]\d{4}\b"      # phone
    r"|\b[\w.+-]+@[\w-]+\.[\w.]+\b"            # email
    r"|\b\d{5}(?:-\d{4})?\b"                   # ZIP / long id
    r"|\b\d+(?:\.\d+)?%"                       # percentage
    r"|\b\d{6,}\b"                             # long number
    r"|\b[A-Z]{1,4}[- ]?\d{5,}\b"              # policy-number-ish
)


def _spans(page):
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["text"].strip():
                    out.append(span)
    return out


def _plan(doc, entries, values):
    """Match every entry against the source; returns edits and unmatched entries."""
    page_spans = {p.number: _spans(p) for p in doc}
    hits = {}          # (page, span index) -> [(start, end, entry index)]
    matched = [0] * len(entries)
    unmatched = []

    for ei, entry in enumerate(entries):
        if entry.exact:
            pattern = re.compile(r"^\s*(%s)\s*$" % re.escape(entry.src))
        else:
            pattern = re.compile(re.escape(entry.src) if entry.raw else _bounded(entry.src))
        found = []
        for pn, spans in page_spans.items():
            if entry.page and pn + 1 != entry.page:
                continue
            for si, span in enumerate(spans):
                for m in pattern.finditer(span["text"]):
                    grp = 1 if entry.exact else 0
                    found.append((pn, round(span["bbox"][1], 1), round(span["bbox"][0], 1),
                                  si, m.start(grp), m.end(grp)))
        found.sort()
        if entry.nth is not None:
            found = [found[entry.nth]] if len(found) > entry.nth else []
        if not found and not entry.optional:
            unmatched.append(entry.src)
        matched[ei] = len(found)
        for pn, _, _, si, s, e in found:
            hits.setdefault((pn, si), []).append((s, e, ei))

    edits = []
    for (pn, si), spans_hits in hits.items():
        span = page_spans[pn][si]
        text = span["text"]
        taken, chosen = [], []
        for s, e, ei in sorted(spans_hits, key=lambda h: -(h[1] - h[0])):
            if all(e <= ts or s >= te for ts, te in taken):
                taken.append((s, e))
                chosen.append((s, e, ei))
        new, pos = [], 0
        for s, e, ei in sorted(chosen):
            new.append(text[pos:s])
            new.append(entries[ei].resolve(values))
            pos = e
        new.append(text[pos:])
        first = entries[sorted(chosen)[0][2]]
        edits.append({"page": pn, "span": span, "new": "".join(new),
                      "entries": [ei for _, _, ei in chosen],
                      "size": first.size, "font": first.font})
    return edits, unmatched, page_spans


def _background(pix, rect):
    """Lightest of four pixels just outside the rect: paper, not a rule line."""
    best, colour = -1, (255, 255, 255)
    for px, py in ((rect.x0 - 2, rect.y0 - 2), (rect.x1 + 2, rect.y0 - 2),
                   (rect.x0 - 2, rect.y1 + 2), (rect.x1 + 2, rect.y1 + 2)):
        x = min(max(int(px), 0), pix.width - 1)
        y = min(max(int(py), 0), pix.height - 1)
        r, g, b = pix.pixel(x, y)[:3]
        if r + g + b > best:
            best, colour = r + g + b, (r, g, b)
    return tuple(c / 255.0 for c in colour)


def _apply(page, edits, page_spans, problems):
    if not edits:
        return
    pix = page.get_pixmap(dpi=72, colorspace=fitz.csRGB)
    width = page.rect.width

    # Redaction also clips text that touches the box, so any untouched neighbour
    # abutting an edited span is redrawn whole rather than left half-deleted.
    edited = {id(e["span"]) for e in edits}
    extra = []
    for edit in edits:
        sp = edit["span"]
        band = fitz.Rect(sp["bbox"][0] - 1.5, sp["origin"][1] - sp["size"] * 0.76,
                         sp["bbox"][2] + 1.5, sp["origin"][1] + sp["size"] * 0.22)
        for other in page_spans[edit["page"]]:
            if id(other) in edited:
                continue
            tight = fitz.Rect(other["bbox"][0], other["origin"][1] - other["size"] * 0.76,
                              other["bbox"][2], other["origin"][1] + other["size"] * 0.22)
            if tight.intersects(band):
                edited.add(id(other))
                extra.append({"page": edit["page"], "span": other, "new": other["text"],
                              "size": None, "font": None})
    edits = edits + extra

    for edit in edits:
        span = edit["span"]
        size, (ox, oy) = span["size"], span["origin"]
        x0, _, x1, _ = span["bbox"]
        rect = fitz.Rect(x0 + 0.3, oy - size * 0.76, x1 - 0.6, oy + size * 0.22)
        page.add_redact_annot(rect, fill=_background(pix, rect))
    try:
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                              graphics=fitz.PDF_REDACT_LINE_ART_NONE)
    except (AttributeError, TypeError):
        page.apply_redactions()

    erased = {id(e["span"]) for e in edits if not e["new"].strip()}
    for edit in edits:
        span, new = edit["span"], edit["new"]
        new = new.encode("latin-1", "replace").decode("latin-1")
        if not new.strip():
            continue
        font = edit.get("font") or _base14(span["font"])
        size, (ox, oy) = edit.get("size") or span["size"], span["origin"]
        x0, _, x1, _ = span["bbox"]
        right = bool(_NUMERIC.match(span["text"].strip())) and bool(_NUMERIC.match(new.strip()))
        text_w = fitz.get_text_length(new, fontname=font, fontsize=size)

        # room to the neighbours on the same baseline
        right_limit, left_limit = width - 14, 8.0
        for other in page_spans[edit["page"]]:
            if other is span or id(other) in erased or abs(other["origin"][1] - oy) > size * 0.6:
                continue
            if other["bbox"][0] >= x1 - 0.5:
                right_limit = min(right_limit, other["bbox"][0] - 2)
            elif other["bbox"][2] <= x0 + 0.5:
                left_limit = max(left_limit, other["bbox"][2] + 2)
        room = (x1 - left_limit) if right else (right_limit - ox)
        if text_w > room:
            scale = room / text_w
            if scale < 0.72:
                problems.append("page %d: %r does not fit beside its neighbours (needs %.0f pt, has %.0f)"
                                % (edit["page"] + 1, new, text_w, room))
            size *= max(scale, 0.72)
            text_w = fitz.get_text_length(new, fontname=font, fontsize=size)
        x = (x1 - text_w) if right else ox
        page.insert_text((x, oy), new, fontsize=size, fontname=font, color=_color(span["color"]))



# -- printed text -----------------------------------------------------------------------

_FORM_NO = re.compile(r"(?<![A-Za-z0-9])[A-Z]{1,6}[- ]?\d{1,4}[A-Z]?\s?\(\d{1,2}/\d{2,4}\)")


def _lines(page):
    """Visual lines of a page: [(top, height, x0, text, has_column_gap)] in reading order."""
    words = [w for w in page.get_text("words") if str(w[4]).strip()]
    words.sort(key=lambda w: ((w[1] + w[3]) / 2.0, w[0]))
    rows, current = [], []
    for w in words:
        centre, height = (w[1] + w[3]) / 2.0, max(w[3] - w[1], 4.0)
        if current and abs(centre - current[-1][0]) > 0.55 * height:
            rows.append(current)
            current = []
        current.append((centre, height, w))
    if current:
        rows.append(current)
    out = []
    for row in rows:
        row.sort(key=lambda r: r[2][0])
        parts, gap = [row[0][2][4]], False
        for (_, height, prev), (_, _, cur) in zip(row, row[1:]):
            wide = cur[0] - prev[2] > 0.9 * height
            gap = gap or wide
            parts.append(("  " if wide else " ") + cur[4])
        out.append((row[0][0], row[0][1], row[0][2][0], "".join(parts), gap))
    return out


def text_sections(pdf_path):
    """Everything the PDF prints, as gold text sections.

    Each run of prose lines (no column gaps, six or more words) becomes its own
    section, titled by the short line above it when there is one. Labels, values
    and table cells are NOT dumped here: they must be keyed fields in the gold.
    """
    doc = fitz.open(str(pdf_path))
    sections = {}
    for page in doc:
        n = page.number + 1
        lines = _lines(page)
        prose = [len(t.split()) >= 6 and not gap and sum(c.isalpha() for c in t) > 0.6 * len(t)
                 for _, _, _, t, gap in lines]
        k, i = 0, 0
        while i < len(lines):
            if not prose[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(lines) and prose[j + 1] and lines[j + 1][0] - lines[j][0] <= 1.8 * lines[j][1]:
                j += 1
            k += 1
            title = None
            if i > 0 and not prose[i - 1] and len(lines[i - 1][3]) <= 90                     and lines[i][0] - lines[i - 1][0] <= 2.2 * lines[i - 1][1]:
                title = lines[i - 1][3].strip()
            text = " ".join(lines[x][3] for x in range(i, j + 1))
            form = _FORM_NO.search(text)
            sections["page%d_s%d" % (n, k)] = {
                "section_id": "page%d_s%d" % (n, k), "section_title": title, "section_type": "prose",
                "raw_text": re.sub(r"\s+", " ", text).strip(), "page_range": [n],
                "form_number": form.group(0) if form else None}
            i = j + 1
    doc.close()
    return sections



def _cells(line):
    return [c for c in re.split(r"\s{2,}", line) if c.strip()]


def printed_pairs(pdf_path):
    """('page', label, value) for every printed "Label: value" pair.

    Lines are cut into cells at runs of two or more spaces; a cell with a colon
    starts a pair whose value is the rest of the cell plus the following cells
    until the next cell that has a colon. Long values (prose) are not pairs.
    """
    doc = fitz.open(str(pdf_path))
    out = []
    for page in doc:
        for _, _, _, text, _ in _lines(page):
            cells = _cells(text)
            i = 0
            while i < len(cells):
                m = re.match(r"^([A-Za-z#][^:]{0,45}?):\s*(.*)$", cells[i])
                if not m or not re.search(r"[A-Za-z]", m.group(1)) or len(m.group(1).split()) > 6                         or re.search(r"\d{2}|/", m.group(1)):
                    i += 1
                    continue
                label, parts, j = m.group(1).strip(), [m.group(2)], i + 1
                while j < len(cells) and not re.match(r"^[A-Za-z#][^:]{0,45}?:(\s|$)", cells[j]):
                    parts.append(cells[j])
                    j += 1
                value = " ".join(p for p in parts if p).strip()
                if value and len(value.split()) < 12:
                    out.append((page.number + 1, label, value))
                i = j
    doc.close()
    return out


def _norm_text(text):
    return re.sub(r"\W+", " ", str(text)).strip().lower()


def _unstructured(pairs, gold, ignore):
    """Printed pairs whose value is not carried by any keyed field of the gold."""
    blob = " | ".join(_norm_text(f["raw"]) for _, f in walk_indexed(gold))
    tokens = set(blob.replace("|", " ").split())
    left = []
    for page, label, value in pairs:
        norm = _norm_text(value)
        if not norm or norm in blob:
            continue
        parts = norm.split()
        if len(parts) >= 3 and all(t in tokens for t in parts):
            continue  # a composite value (an address, a period) held as separate keyed parts
        if any(r.search("%s: %s" % (label, value)) for r in ignore):
            continue
        left.append("page %d: %s: %s" % (page, label, value[:70]))
    return left



def _clean_label(label):
    label = re.sub(r"\s+", " ", label).strip(" :-–")
    return label


def label_map(pdf_path):
    """Printed labels by normalised value: {norm(value): label}, from 'Label: value'
    pairs and from the first cell of table rows ('Coverage A - Residence  $340,000')."""
    doc = fitz.open(str(pdf_path))
    seen = {}
    for page in doc:
        for _, _, _, text, _ in _lines(page):
            cells = _cells(text)
            if len(cells) >= 2 and ":" not in cells[0] and re.search(r"[A-Za-z]{3}", cells[0])                     and not re.search(r"\d{3}", cells[0]) and len(cells[0].split()) <= 8:
                for cell in cells[1:]:
                    seen.setdefault(_norm_text(cell), _clean_label(cells[0]))
    doc.close()
    for _, label, value in printed_pairs(pdf_path):
        seen[_norm_text(value)] = _clean_label(label)
    return seen


def add_printed_labels(gold, pdf_path):
    """Record on each keyed value the label the document printed beside it.

    Exact matches only, and only for values distinctive enough to identify: a
    bare "No" or "1" sits beside many labels and would be attributed to the
    wrong one.
    """
    labels = label_map(pdf_path)
    values = {_norm_text(f["raw"]) for _, f in walk_indexed(gold)}
    for _, field in walk_indexed(gold):
        norm = _norm_text(field["raw"])
        if len(norm) < 3 or norm in _GENERIC:
            continue
        label = labels.get(norm)
        # a row's first cell is only a label if it carries no keyed value (a name, an address)
        if label and len(label) <= 60:
            nl = _norm_text(label)
            if not any(len(v) >= 8 and v != nl and v in nl for v in values):
                field["printed_label"] = label


_GENERIC = {"yes", "no", "none", "n a", "na", "standard", "primary", "other"}


def tidy_text(gold):
    """Replace the control character some source fonts use for an en dash."""
    def fix(value):
        return value.replace("", "–") if isinstance(value, str) else value

    for _, field in walk_indexed(gold):
        for key in ("raw", "parsed", "printed_label"):
            if key in field:
                field[key] = fix(field[key])
    for section in gold.get("text_sections", {}).values():
        section["raw_text"] = fix(section["raw_text"])
        section["section_title"] = fix(section["section_title"])



def _gold_blob(gold):
    """All the text the gold carries, normalised: keyed values, labels, additional fields, prose."""
    parts = []
    for _, field in walk_indexed(gold):
        parts.append(_norm_text(field["raw"]))
        if field.get("printed_label"):
            parts.append(_norm_text(field["printed_label"]))
    for item in gold.get("additional_fields", []):
        parts += [_norm_text(item.get("label", "")), _norm_text(item.get("section") or "")]
    for sec in gold.get("text_sections", {}).values():
        parts += [_norm_text(sec["raw_text"]), _norm_text(sec.get("section_title") or "")]
    return " | ".join(p for p in parts if p)


def printed_lines(pdf_path, gold, furniture):
    """Lines the gold does not already carry, and the data-like cells among them.

    A cell is carried when its normalised text sits inside the gold's text, or
    (three or more words) every word does - an address kept as separate parts.
    Everything else is recorded as a printed line so nothing on the page is
    missing from the gold. A leftover cell that looks like data is returned as a
    problem: data has to be keyed, not parked here.
    """
    blob = _gold_blob(gold)
    tokens = set(blob.replace("|", " ").split())
    doc = fitz.open(str(pdf_path))
    out, data = [], []
    for page in doc:
        height = page.rect.height
        for top, _, _, text, _ in _lines(page):
            left = []
            for cell in _cells(text):
                norm = _norm_text(cell)
                if not norm or norm in blob:
                    continue
                parts = norm.split()
                if len(parts) >= 3 and all(t in tokens for t in parts):
                    continue
                pair = re.match(r"^[^:]{1,45}:\s*(\S.*)$", cell)
                if pair and _norm_text(pair.group(1)) in blob:
                    continue  # "Label: value" whose value is keyed; the label is furniture
                left.append(cell.strip())
            if not left:
                continue
            for cell in left:
                if _VARIABLE.search(cell) and not any(f.search(cell) for f in furniture):
                    data.append("page %d: %s" % (page.number + 1, cell[:80]))
            words = " ".join(left)
            if top > 0.92 * height:
                kind = "footer"
            elif top < 0.06 * height:
                kind = "header"
            elif not re.search(r"\d", words) and len(words.split()) <= 8:
                kind = "heading" if len(left) == 1 else "caption"
            else:
                kind = "row"
            out.append({"page": page.number + 1, "kind": kind, "cells": left})
    doc.close()
    return out, data


# -- checks -----------------------------------------------------------------------------

def _unmapped(page_spans, edits, profile):
    """Variable-looking printed values the profile neither replaces nor declares static."""
    covered = {(e["page"], id(e["span"])) for e in edits}
    left = []
    for pn, spans in page_spans.items():
        for span in spans:
            text = span["text"].strip()
            if (pn, id(span)) in covered or not _VARIABLE.search(text):
                continue
            if re.fullmatch(r"(?i)page\s+\d+\s+of\s+\d+", text):
                continue
            if any(p.search(text) for p in profile.static):
                continue
            left.append("page %d: %r" % (pn + 1, text[:90]))
    return left


def _coverage(schema, gold):
    stated = pageref.stated_paths(gold)
    sections = {}
    for leaf in schema.leaves:
        sec = leaf.split(".")[0].replace("[]", "")
        have, total = sections.get(sec, (0, 0))
        sections[sec] = (have + (leaf in stated), total + 1)
    return len(stated), sections


def _date_problems(gold):
    try:
        eff = gold["policy"]["effective_date"]["parsed"]
        exp = gold["policy"]["expiration_date"]["parsed"]
        if as_date(eff) and as_date(exp) and as_date(eff) > as_date(exp):
            return ["policy.effective_date %s is after expiration_date %s" % (eff, exp)]
    except KeyError:
        pass
    return []


# -- generation -------------------------------------------------------------------------

class DwellingFireGenerator:
    def __init__(self, input_dir=r"Data\original data", out_dir="output",
                 schema_dir="config/policy_check", pdf_subdir="PDF",
                 gold_subdir="gold_json", scan=True):
        self.scan = scan
        self.input_dir = Path(input_dir)
        self.out_dir = Path(out_dir)
        self.pdf_root = self.out_dir / pdf_subdir
        self.gold_root = self.out_dir / gold_subdir
        self.schema = CanonicalSchema.load(LOB, schema_dir=schema_dir)

    def generate(self, count=2, seed=0, only=None, progress=None):
        report = Report(template="dwelling_fire_sources",
                        schema="%s v%s" % (self.schema.lob, self.schema.version))
        for profile in load_profiles(only):
            vals = Values("%s:%s:%s" % (seed, profile.carrier, profile.key))
            for index in range(1, count + 1):
                built = self._one(profile, index, vals)
                report.documents.append(built)
                if progress:
                    progress(built)
        return report

    def _one(self, profile, index, vals):
        name = "%s_%03d" % (profile.key, index)
        sub = Path(profile.carrier) / LOB
        pdf_path = self.pdf_root / sub / (name + ".pdf")
        gold_path = self.gold_root / sub / (name + ".json")
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        gold_path.parent.mkdir(parents=True, exist_ok=True)
        built = Built(key="%s/%s" % (profile.carrier, name), pdf=pdf_path,
                      gold=gold_path, pages=0, fields=0)
        temp = pdf_path.with_name("_temp_" + pdf_path.name)

        try:
            source = self.input_dir / profile.source
            if not source.exists():
                raise FileNotFoundError("source not found: %s" % source)

            d = profile.module.draw(vals, C)

            doc = fitz.open(str(source))
            built.pages = len(doc)
            edits, unmatched, page_spans = _plan(doc, profile.entries, d)
            for src in unmatched:
                built.problems.append("replace text not found in source: %r" % src)

            problems = []
            for page in doc:
                _apply(page, [e for e in edits if e["page"] == page.number], page_spans, problems)
            built.problems.extend(problems)
            doc.save(str(temp))
            doc.close()

            gold = profile.module.gold(d)
            self._defaults(gold, pdf_path.name, built.pages, profile)
            gold["text_sections"] = text_sections(temp)
            blob = " ".join(sec["raw_text"] for sec in gold["text_sections"].values()).lower()
            for entry in profile.entries:
                probe = re.sub(r"\s+", " ", entry.src).strip().lower()
                if entry.leak and (len(probe) >= 5 or any(c.isdigit() for c in probe))                         and probe in blob and probe not in entry.resolve(d).lower():
                    built.problems.append("source text %r survived into text_sections" % entry.src)

            # leak: replaced source text must not survive into the new PDF
            out_text = " ".join(pageref.page_texts(temp))
            for entry in profile.entries:
                probe = re.sub(r"\s+", " ", entry.src).strip().lower()
                if entry.leak and (len(probe) >= 5 or any(c.isdigit() for c in probe)) \
                        and probe in out_text and probe not in entry.resolve(d).lower():
                    built.problems.append("source text %r survived into the generated PDF" % entry.src)

            for left in _unmapped(page_spans, edits, profile):
                built.problems.append("printed value not mapped or declared STATIC - %s" % left)

            resolved, misses = pageref.attach(gold, temp)
            for line in _unstructured(printed_pairs(temp), gold, profile.ignore_pairs):
                built.problems.append("printed label/value not in a keyed field (map it, add it to additional_fields, or IGNORE_PAIRS) - %s" % line)
            for _, field in walk_indexed(gold):
                fixed = field.pop("_fixed_pages", None)
                if fixed is not None:
                    field["page_ref"] = fixed
            add_printed_labels(gold, temp)
            tidy_text(gold)
            gold["printed_lines"], leftover_data = printed_lines(temp, gold, profile.furniture)
            for cell in leftover_data:
                built.problems.append("printed data not in a keyed field (map it, add it to additional_fields, or FURNITURE if it is page furniture) - %s" % cell)
            for path, raw in misses:
                built.problems.append("gold says %s = %r is printed, but it is not on any page" % (path, raw))

            if self.scan:
                scan_stats = scan_pdf(temp, pdf_path, scan_by_key("high_quality"), seed=index)
                if scan_stats["words"]:
                    built.problems.append("scan has %d extractable words" % scan_stats["words"])
            else:  # quick check while writing a profile: keep the digital PDF, skip the slow scan
                shutil.copyfile(temp, pdf_path)
                scan_stats = {"profile": "not scanned (--no-scan)"}
            built.profile = scan_stats["profile"]

            total, sections = _coverage(self.schema, gold)
            gold["fideon:absent"] = self.schema.absent_from(pageref.stated_paths(gold))
            gold["fideon:provenance"] = {
                "generator": "fideon-synth",
                "source": "%s/%s" % (profile.carrier, profile.source.name),
                "schema": "%s v%s" % (self.schema.lob, self.schema.version),
                "render": "scanned_only",
                "scanner_profile": scan_stats["profile"],
                "synthetic": True,
                "note": "Scanned synthetic document generated from a reference source document.",
            }

            built.problems.extend(self.schema.validate(gold))
            built.problems.extend(_date_problems(gold))
            audit = getattr(profile.module, "audit", None)
            if audit:
                built.problems.extend(audit(d))

            gold_path.write_text(json.dumps(gold, indent=2, ensure_ascii=False), encoding="utf-8")
            built.fields = total
            built.coverage = sections
        except Exception as exc:  # a broken profile is a build failure, not a crash
            built.problems.append("%s: %s" % (type(exc).__name__, exc))
        finally:
            if temp.exists():
                temp.unlink()
        return built

    @staticmethod
    def _defaults(gold, pdf_name, pages, profile):
        document = gold.setdefault("document", {})
        document.setdefault("source_file_name", derived(pdf_name))
        document.setdefault("source_carrier_folder", derived(profile.carrier))
        document.setdefault("page_count", derived(str(pages), parsed=pages))
