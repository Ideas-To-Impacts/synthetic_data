"""
Structure on the page that the value-by-value labeller cannot see.

:func:`generic.build_gold` names one replaced value at a time by the label
printed beside it. That misses whatever is laid out rather than labelled:

* **tables** - a coverage schedule (Coverage / Limit / Deductible / Premium)
  and a location schedule (Location # / Address), split into columns by the
  position of the header words, so a row the OCR ran into one cell still
  splits;
* **lists** - forms and endorsements under their heading;
* **units** - a watercraft, or whatever the line's own schema lists with its
  own coverages: description, year, make, hull ID, mooring place and its
  coverage table. A new unit starts when one of its fields repeats or a unit
  heading ("Coverage and Rating Information") is printed again;
* **plain labelled text** - "TERM: 12 Months", "Payment Plan: Annual" - which
  identifies nobody, so it is never replaced and the labeller never saw it;
* a few fixed shapes: the document title, the carrier's town under its name,
  the effective time, a transaction type printed after its date, the print
  date in a page's header or footer band, and where a signature was signed.

Labels are matched to the schema through its field names and
``fideon:aliases``, so teaching it a new carrier's wording is a schema edit.
Every value is read off the generated document (a replaced value's new text,
the rest as printed) and checked against the rendered pages by
:func:`pageref.attach` like any other.
"""

from __future__ import annotations

import copy
import re
from datetime import date

from .fields import as_number, derived, fv, is_field, yes_no

STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY", "district of columbia": "DC",
}
TRANSACTION_WORDS = {"new", "new business", "renewal", "rewrite", "endorsement", "change",
                     "policy change", "cancellation", "reinstatement", "reissue", "audit"}
TITLE = re.compile(r"\b(declarations? page|declarations?|policy history|policy change|binder|"
                   r"quote|proposal)\b", re.I)
DOC_TYPE = {"declaration": "Declaration", "policy history": "Policy History",
            "policy change": "Policy Change", "binder": "Binder", "quote": "Quote",
            "proposal": "Quote"}
#: a table cell that is a value rather than part of a row's name
VALUE = re.compile(r"^\(?\$?\d[\d,]*(?:\.\d+)?\)?$|^(?:incl\.?|included|excluded|n/?a)$", re.I)
COVERAGE_HEAD = {"name": {"coverage", "coverages"}, "limit": {"limit", "limits"},
                 "deductible": {"deductible", "deductibles"}, "premium": {"premium", "premiums"}}
LOCATION_HEAD = {"number": {"location", "loc", "#"}, "address": {"address"},
                 "legal": {"legal"}}
FORM_LINE = re.compile(r"^(?:(?P<num>[A-Z]{2,6}[0-9A-Z]{2,6}-\d{4})\s*)?-\s*(?P<title>\S.*)$")
FORM_SHAPE = re.compile(r"^([A-Z]{2,6})(\d{3,5})-\d{4}$")
#: fields whose value is a date, an amount or an identifier - never a plain word
NOT_TEXT = re.compile(r"date|premium|amount|limit|fee|deductible|number|_id$|code|phone|fax|"
                      r"email|fein|tax|surcharge|percentage|rate|value|address")
TIME = re.compile(r"\b(\d{1,2}:\d{2}\s*[AP]\.?\s?M\.?)\s+(\S.*\bTime\b.*)$")


# ── the page as words and values ────────────────────────────────────────────

class Seg:
    """One word, or one whole replaced value, with where it is printed."""

    def __init__(self, text, orig, rect, found=None):
        self.text, self.orig, self.rect, self.found = text, orig, rect, found

    @property
    def cx(self):
        return (self.rect.x0 + self.rect.x1) / 2


def segments(cell, found):
    """The cell in reading order: a replaced value is one segment carrying its
    new text; the rest splits on spaces."""
    out, pos = [], 0

    def words(s, e):
        for m in re.finditer(r"\S+", cell.text[s:e]):
            r = cell.span_rect(s + m.start(), s + m.end())
            if r is not None:
                out.append(Seg(m.group(0), m.group(0), r))

    for f in sorted(found, key=lambda f: f.start):
        if f.start < pos:
            continue
        words(pos, f.start)
        if not f.blank and f.rect is not None:
            out.append(Seg(f.new if f.new is not None else f.text, f.text, f.rect, f))
        pos = f.end
    words(pos, len(cell.text))
    return out


class Line:
    """The cells printed on one baseline."""

    def __init__(self, page, cells, found_in):
        self.page = page
        self.cells = sorted(cells, key=lambda c: c.rect.x0)
        self.segs = [s for c in self.cells for s in segments(c, found_in.get(id(c), []))]
        self.y = max(c.rect.y1 for c in cells)
        heights = sorted(c.rect.height for c in cells)
        self.height = heights[len(heights) // 2]
        self.text = " ".join(c.text for c in self.cells)


def _columns(line, head):
    cols = {}
    for s in line.segs:
        word = re.sub(r"[^a-z#]", "", s.orig.lower())
        for key, names in head.items():
            if word in names and key not in cols:
                cols[key] = s
    return cols


def _put(doc, path, value):
    keys = path.split(".")
    for k in keys[:-1]:
        doc = doc.setdefault(k, {})
    doc.setdefault(keys[-1], value)


def _get(doc, path):
    for k in path.split("."):
        if not isinstance(doc, dict) or k not in doc:
            return None
        doc = doc[k]
    return doc


def merge(dst, src):
    """Add ``src`` to ``dst`` without overwriting anything ``dst`` states."""
    for k, v in src.items():
        if k not in dst:
            dst[k] = v
        elif isinstance(dst[k], dict) and isinstance(v, dict) and not is_field(dst[k]):
            merge(dst[k], v)
    return dst


# ── the schema, as label phrases ────────────────────────────────────────────

def _aliases(node, path, out, norm, defs):
    """Explicit aliases of every field and object under ``node``, not
    descending into lists: a list entry needs a row to hang on."""
    for alias in node.get("fideon:aliases", []) or []:
        out.setdefault(norm(alias), []).append(path)
    if "$ref" in node:
        name = node["$ref"].split("/")[-1]
        if name != "FieldValue":
            _aliases(defs[name], path, out, norm, defs)
        return
    for key, sub in (node.get("properties") or {}).items():
        if sub.get("type") != "array":
            _aliases(sub, f"{path}.{key}" if path else key, out, norm, defs)


def unit_list(schema):
    """(path, item node) of the list the line's own block keeps its units in -
    the first list whose entries carry their own coverages - or None."""
    block = schema.merged.get("fideon:source", {}).get("line_specific_block")
    node = schema.merged["properties"].get(block) if block else None
    if not node:
        return None
    for key, sub in (node.get("properties") or {}).items():
        items = sub.get("items") or {}
        if sub.get("type") == "array" and \
                (items.get("properties") or {}).get("coverages", {}).get("type") == "array":
            return "%s.%s" % (block, key), sub
    return None


# ── reading ─────────────────────────────────────────────────────────────────

class Reader:
    """Everything this module reads from one document.

    ``pages`` is ``[(page_number, page_height, cells, found)]`` after the
    replacements are chosen. :meth:`read` returns a gold fragment; the found
    values it used are in :attr:`consumed`, so the labeller does not list
    them again as unmapped."""

    def __init__(self, pages, schema, index, carrier):
        from .generic import PATTERNS, _carrier_marks, _field, _norm_label, match_label
        self.norm, self.match, self.field = _norm_label, match_label, _field
        self.cityline = PATTERNS[4][1]
        self.marks = _carrier_marks(carrier)
        self.schema, self.index = schema, index
        self.pages = pages
        self.cells = {n: cells for n, _, cells, _ in pages}
        self.found_in = {}
        for *_, found in pages:
            for f in found:
                self.found_in.setdefault(id(f.cell), []).append(f)
        self.lines = []
        for n, height, cells, found in pages:
            rows = {}
            for c in cells:
                if c.rect is not None:
                    rows.setdefault(c.row, []).append(c)
            self.lines += [Line(n, rows[r], self.found_in) for r in sorted(rows)]
        self.heights = {n: h for n, h, *_ in pages}

        defs = schema.merged["$defs"]
        self.units_at = unit_list(schema)
        self.unit_index, self.unit_marks, self.cov_targets = {}, set(), {}
        if self.units_at:
            path, node = self.units_at
            _aliases(node["items"], "", self.unit_index, self.norm, defs)
            for alias in (node.get("fideon:aliases") or []) + \
                    (node["items"]["properties"]["coverages"].get("fideon:aliases") or []):
                self.unit_marks.add(self.norm(alias))
            block = path.split(".")[0]
            scalars = {}
            _aliases(schema.merged["properties"][block], block, scalars, self.norm, defs)
            for phrase, paths in scalars.items():
                self.cov_targets.setdefault(phrase, []).extend(("scalar", p) for p in paths)
            for phrase, rels in self.unit_index.items():
                self.cov_targets.setdefault(phrase, []).extend(("unit", r) for r in rels)
        forms = schema.merged["properties"].get("forms_and_endorsements", {})
        self.forms_heads = {self.norm(a) for a in forms.get("fideon:aliases", []) or []}
        self.forms_heads.add("forms and endorsements")

        self.form_digits = {}
        for cells in self.cells.values():
            for c in cells:
                for word in c.text.split():
                    m = FORM_SHAPE.match(word)
                    if m:
                        self.form_digits.setdefault(m.group(1), len(m.group(2)))

        self.gold, self.consumed = {}, set()
        self.units, self.locations, self.deductibles = [], [], []
        self.coverage_names, self.location_values, self.form_numbers = [], set(), set()

    # ── entry point ─────────────────────────────────────────────────────────

    def read(self):
        self._title()
        self._carrier_address()
        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            if self.units_at and self._is_coverage_head(line):
                i = self._coverage_table(i)
            elif self._is_location_head(line):
                i = self._location_table(i)
            elif self.norm(line.text) in self.forms_heads:
                i = self._forms(i)
            else:
                if self.units_at and self.norm(line.text) in self.unit_marks \
                        and self.units and self.units[-1]:
                    self.units.append({})
                for cell in line.cells:
                    self._labelled(cell)
                i += 1
        self._footer_form_number()
        self._print_date()

        units = [u for u in self.units if u]
        if units:
            _put(self.gold, self.units_at[0], units)
        if self.locations:
            self.gold["locations"] = self.locations
        if self.deductibles:
            self.gold["deductibles"] = self.deductibles
        for *_, found in self.pages:            # a location printed again as a block
            for f in found:
                if f.kind in ("street", "pobox", "cityline") and f.new \
                        and " ".join(f.new.lower().split()) in self.location_values:
                    self.consumed.add(id(f))
        return self.gold

    def _use(self, f):
        if f is not None:
            self.consumed.add(id(f))

    # ── fixed shapes ────────────────────────────────────────────────────────

    def _title(self):
        first = min(self.cells) if self.cells else None
        for line in self.lines:
            if line.page != first:
                break
            for cell in line.cells:
                m = TITLE.search(cell.text)
                if not m or len(cell.text.split()) > 8 or self.found_in.get(id(cell)):
                    continue
                words = cell.text.split()
                while words and words[0].lower() in self.marks:
                    words.pop(0)                  # the carrier's logo run into it
                _put(self.gold, "document.document_title_as_stated", fv(" ".join(words)))
                kind = m.group(1).lower()
                kind = "declaration" if kind.startswith("declaration") else kind
                _put(self.gold, "document.document_type", fv(m.group(1), DOC_TYPE[kind]))
                return

    def _carrier_address(self):
        """"GLEN ALLEN, VIRGINIA" printed under the carrier's name."""
        if not self.marks:
            return
        for i, line in enumerate(self.lines[:-1]):
            if not all(m in line.text.lower() for m in self.marks):
                continue
            for cell in self.lines[i + 1].cells:
                m = re.fullmatch(r"([A-Z][A-Za-z .'-]+),\s*([A-Za-z .]+)", cell.text.strip())
                state = m and (STATE_NAMES.get(m.group(2).strip().lower())
                               or (m.group(2).strip() if m.group(2).strip().upper()
                                   in STATE_NAMES.values() else None))
                if state:
                    _put(self.gold, "carrier.address.city", fv(m.group(1).strip()))
                    _put(self.gold, "carrier.address.state", fv(m.group(2).strip(), state))
                    return
            return

    def _print_date(self):
        """A date in a page's header or footer band that no label claims is
        when the page was printed."""
        taken = None
        for n, height, _, found in self.pages:
            for f in found:
                if f.kind != "date" or f.blank or id(f) in self.consumed or f.rect is None:
                    continue
                if not (f.rect.y1 < 0.06 * height or f.rect.y0 > 0.9 * height):
                    continue
                if self.match(self.norm(f.label), "date", self.index):
                    continue
                if taken is None:
                    taken = f.new
                    _put(self.gold, "document.print_date", self.field("date", f.new))
                if f.new == taken:
                    self._use(f)

    def _fix_form(self, num):
        """The OCR reads a form number's 5 as S: MAMS047 for MAM5047, and
        sometimes keeps both, MAMS5055. The form numbers it read cleanly say
        how many digits the prefix takes."""
        m = re.match(r"^([A-Z]+?)S(\d+)-(\d{4})$", num)
        if not m or m.group(1) not in self.form_digits:
            return num
        want, digits = self.form_digits[m.group(1)], m.group(2)
        if len(digits) + 1 == want:
            return "%s5%s-%s" % (m.group(1), digits, m.group(3))
        if len(digits) == want:
            return "%s%s-%s" % (m.group(1), digits, m.group(3))
        return num

    def _footer_form_number(self):
        for n, height, cells, _ in self.pages:
            for c in cells:
                text = c.text.strip()
                if c.rect is not None and c.rect.y0 > 0.9 * height \
                        and re.fullmatch(r"[A-Z]{2,6}[0-9A-Z]{2,6}-\d{4}", text) \
                        and text not in self.form_numbers:
                    _put(self.gold, "document.form_number", fv(self._fix_form(text), evidence=text))
                    return

    # ── labelled values ─────────────────────────────────────────────────────

    def _right_of(self, cell):
        r = cell.rect
        cy, best = (r.y0 + r.y1) / 2, None
        for o in self.cells[cell.page]:
            q = o.rect
            if o is cell or q is None or q.x0 < r.x1 or q.x0 - r.x1 > 150:
                continue
            if abs((q.y0 + q.y1) / 2 - cy) > 0.7 * r.height:
                continue
            if best is None or q.x0 < best.rect.x0:
                best = o
        return best

    def _unit(self, top, value=None):
        """The unit a field belongs to: the current one, or a new one when the
        current one already has it - unless the value fills in the rest of an
        address the unit already started."""
        if self.units and top in self.units[-1]:
            have = self.units[-1][top]
            if isinstance(value, dict) and isinstance(have, dict) and not is_field(have) \
                    and not set(value) & set(have):
                return self.units[-1]
            self.units.append({})
        if not self.units:
            self.units.append({})
        return self.units[-1]

    def _unit_set(self, rel, value):
        keys = rel.split(".")
        node = self._unit(keys[0], value if len(keys) == 1 else None)
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        if isinstance(value, dict) and not is_field(value):
            merge(node.setdefault(keys[-1], {}), value)
        else:
            node.setdefault(keys[-1], value)

    def _address(self, f):
        if f.kind == "cityline":
            m = self.cityline.search(f.new)
            if not m:
                return None
            return {"city": fv(m.group(1)), "state": fv(m.group(2)), "postal_code": fv(m.group(3))}
        return {"line_1": fv(f.new)}

    def _plain(self, path, value):
        leaf = path.rsplit(".", 1)[-1]
        number = re.match(r"\d+", value)
        if number and (leaf.endswith("_months") or leaf == "year"):
            return fv(value, int(number.group(0)))
        return fv(value)

    def _unit_fits(self, kind, rel):
        leaf = rel.rsplit(".", 1)[-1]
        if kind in ("cityline", "street", "pobox"):
            return leaf.endswith("address")
        if kind in ("id", "digits"):
            return re.search(r"number|identification|code|_id|serial|vin", leaf)
        if kind == "money":
            return re.search(r"premium|value|amount|price|limit", leaf)
        if kind == "date":
            return "date" in leaf
        return False

    def _labelled(self, cell):
        found = [f for f in self.found_in.get(id(cell), []) if not f.blank]
        for f in found:
            if id(f) in self.consumed:
                continue
            label = self.norm(f.label)
            scalar = self.match(label, f.kind, self.index)
            rels = [r for r in self.unit_index.get(label, []) if self._unit_fits(f.kind, r)]
            if not scalar and rels:
                value = self._address(f) if rels[0].endswith("address") else \
                    (self.field(f.kind, f.new) if f.kind in ("date", "money") else fv(f.new))
                if value:
                    self._unit_set(rels[0], value)
                    self._use(f)
                continue
            if f.kind == "date" and "transaction" in label:
                after = cell.text[f.end:].split()
                word = after[0] if after else ""
                if not word:
                    nxt = self._right_of(cell)
                    word = nxt.text.strip() if nxt is not None else ""
                if word.lower() in TRANSACTION_WORDS:
                    _put(self.gold, "document.transaction_type", fv(word, word.title()))
            if f.kind == "date" and scalar == "signature.signature_date":
                m = re.match(r"\s*at\s+([A-Z][A-Za-z.' -]*?,\s*[A-Z]{2})\b", cell.text[f.end:])
                if m:
                    _put(self.gold, "signature.signature_location", fv(m.group(1)))

        m = TIME.search(cell.text)
        if m and not found:
            _put(self.gold, "policy.effective_time", fv(m.group(1)))
            _put(self.gold, "policy.expiration_time", fv(m.group(1)))
            _put(self.gold, "policy.time_zone", fv(m.group(2).strip()))

        # plain text beside its label: "TERM: 12 Months", or "Year:" | "1999"
        if found:
            return
        m = re.match(r"^\s*([A-Za-z][A-Za-z /&#().'-]{1,40}?)\s*:\s*(\S.*)$", cell.text)
        if m and ":" not in m.group(2):
            label, value = m.group(1), m.group(2).strip()
        elif cell.text.count(":") == 1 and cell.text.rstrip().endswith(":"):
            nxt = self._right_of(cell)
            if nxt is None or ":" in nxt.text or self.found_in.get(id(nxt)):
                return
            label, value = cell.text.rstrip()[:-1], nxt.text.strip()
        else:
            return
        if not value or len(value.split()) > 15:
            return
        label = self.norm(label)
        rels = [r for r in self.unit_index.get(label, []) if not NOT_TEXT.search(r.rsplit(".", 1)[-1])]
        if rels:
            self._unit_set(rels[0], self._plain(rels[0], value))
            if rels[0] == "unit_description":
                year = re.match(r"(1[89]|20)\d\d\b", value)
                if year:
                    self.units[-1].setdefault("year", derived(year.group(0), year.group(0),
                                                              int(year.group(0))))
            return
        path = self.index.get(label)
        if path and not NOT_TEXT.search(path.rsplit(".", 1)[-1]):
            _put(self.gold, path, self._plain(path, value))

    # ── coverage tables ─────────────────────────────────────────────────────

    def _is_coverage_head(self, line):
        cols = _columns(line, COVERAGE_HEAD)
        return len(line.segs) <= 8 and "name" in cols and "premium" in cols \
            and ("limit" in cols or "deductible" in cols)

    def _coverage_table(self, i):
        head = self.lines[i]
        cols = _columns(head, COVERAGE_HEAD)
        centers = {k: s.cx for k, s in cols.items() if k != "name"}
        if not self.units:
            self.units.append({})
        unit = self.units[-1]
        prev, j = head.y, i + 1
        while j < len(self.lines) and self.lines[j].page == head.page:
            line = self.lines[j]
            if line.y - prev > 4 * max(line.height, head.height) or self._is_coverage_head(line):
                break
            if ":" in line.text:                  # a note under a row: "Diminishing Deductible: $0"
                for cell in line.cells:
                    self._labelled(cell)
                prev, j = line.y, j + 1
                continue
            name = [s for s in line.segs if s.found is None and not VALUE.match(s.text)]
            values = [s for s in line.segs if s not in name]
            if not name or not values:
                break
            vals = {}
            for s in values:
                vals.setdefault(min(centers, key=lambda k: abs(centers[k] - s.cx)), s)
            j += 1
            text = " ".join(s.text for s in name)
            if self.norm(text) == "total":
                if "premium" in vals:
                    unit.setdefault("premium", self._amount(vals["premium"]))
                break
            self._coverage(unit, text, vals)
            prev = line.y
        return j

    def _amount(self, seg):
        self._use(seg.found)
        return fv(seg.text, as_number(seg.text))

    def _coverage(self, unit, printed, vals):
        name = re.sub(r"&l\b", "&I", printed)          # the OCR reads P&I as P&l
        if name.startswith("("):                       # and can lose the P&I entirely
            name = next((n for n in self.coverage_names if n.endswith(" " + name)), name)
        item = {"coverage_name": fv(name, evidence=printed)}
        for key, field in (("limit", "limit_amount"), ("deductible", "deductible_amount"),
                           ("premium", "premium")):
            s = vals.get(key)
            if s is None:
                continue
            if re.match(r"(?i)incl", s.text):
                item["is_included"] = yes_no(True, s.text)
            elif re.match(r"(?i)excl", s.text):
                item["is_excluded"] = yes_no(True, s.text)
            else:
                item[field] = self._amount(s)
        unit.setdefault("coverages", []).append(item)
        self.coverage_names.append(name)

        limit = item.get("limit_amount")
        for where, path in self.cov_targets.get(self.norm(name), []):
            leaf = path.rsplit(".", 1)[-1]
            if leaf.endswith("_included"):
                value = yes_no(True, printed)
            elif limit is not None:
                value = copy.deepcopy(limit)
            else:
                continue
            _put(self.gold if where == "scalar" else unit, path, value)
        if "agreed value" in name.lower():
            unit.setdefault("total_loss_settlement_basis", derived("Agreed Value", "Agreed Value"))

        ded = item.get("deductible_amount")
        if ded is not None and (ded["parsed"] or 0) > 0 and \
                not any(d["amount"]["raw"] == ded["raw"] and d["applies_to"]["raw"] == name
                        for d in self.deductibles):
            self.deductibles.append({"amount": copy.deepcopy(ded),
                                     "applies_to": fv(name, evidence=printed)})

    # ── location tables ─────────────────────────────────────────────────────

    def _is_location_head(self, line):
        cols = _columns(line, LOCATION_HEAD)
        return len(line.segs) <= 8 and "number" in cols and "address" in cols

    def _location_table(self, i):
        head = self.lines[i]
        cols = _columns(head, LOCATION_HEAD)
        addr_left = cols["address"].rect.x0 - 10
        prev, j, rows = head.y, i + 1, []
        while j < len(self.lines) and self.lines[j].page == head.page:
            line = self.lines[j]
            kinds = [s.found.kind for s in line.segs if s.found is not None]
            if line.y - prev > 3 * max(line.height, head.height) or \
                    not set(kinds) & {"street", "pobox", "cityline"}:
                break
            if not rows or set(kinds) & {"street", "pobox"}:
                rows.append({})
            row, legal = rows[-1], []
            for s in line.segs:
                f = s.found
                if f is not None and f.kind in ("street", "pobox", "cityline"):
                    address = self._address(f)
                    if address:
                        merge(row.setdefault("address", {}), address)
                        self.location_values.add(" ".join(f.new.lower().split()))
                        self._use(f)
                elif s.rect.x1 < addr_left and re.fullmatch(r"\d{1,4}", s.text):
                    row.setdefault("location_number", fv(s.text))
                elif "legal" in cols and s.rect.x0 >= cols["legal"].rect.x0 - 10:
                    legal.append(s.text)
            if legal:
                row.setdefault("legal_description", fv(" ".join(legal)))
            prev, j = line.y, j + 1
        self.locations += rows
        return j

    # ── forms ───────────────────────────────────────────────────────────────

    def _forms(self, i):
        head = self.lines[i]
        prev, j = head.y, i + 1
        forms = self.gold.setdefault("forms_and_endorsements", [])
        while j < len(self.lines) and self.lines[j].page == head.page:
            line = self.lines[j]
            m = FORM_LINE.match(line.text.strip())
            if line.y - prev > 3 * max(line.height, head.height) or not m:
                break
            item = {}
            num = m.group("num")
            if num:
                self.form_numbers.add(num)
                item["form_number"] = fv(self._fix_form(num), evidence=num)
            title = m.group("title").strip()
            item["form_title"] = fv(title)
            if re.search(r"\bendorsement$", title, re.I):
                item["form_type"] = derived("Endorsement", title)
            elif re.search(r"\bpolicy$", title, re.I):
                item["form_type"] = derived("Policy", title)
                _put(self.gold, "policy.policy_form_name", fv(title))
                if num:
                    _put(self.gold, "policy.policy_form_number",
                         fv(self._fix_form(num), evidence=num))
            forms.append(item)
            prev, j = line.y, j + 1
        return j


# ── after the labeller ──────────────────────────────────────────────────────

def finish(gold, schema):
    """What follows from the whole gold rather than from one place on a page:
    a term length from the policy dates, and a policy-history page restated
    in the schema's policy-history block."""
    policy = gold.get("policy", {})
    eff, exp = policy.get("effective_date"), policy.get("expiration_date")
    if "policy_term_months" not in policy and eff and exp:
        try:
            a, b = date.fromisoformat(eff["parsed"]), date.fromisoformat(exp["parsed"])
        except (TypeError, ValueError):
            a = b = None
        if a and b:
            months = (b.year - a.year) * 12 + b.month - a.month - (b.day < a.day - 1)
            if months > 0:
                policy["policy_term_months"] = derived(str(months), parsed=months)

    if (_get(gold, "document.document_type") or {}).get("parsed") != "Policy History":
        return gold
    if "document_type_detail.policy_history.inception_date" not in schema.leaves:
        return gold
    copy_of = lambda p: copy.deepcopy(_get(gold, p)) if is_field(_get(gold, p)) else None
    history = {}
    for key, src in (("inception_date", "policy.policyholder_since_date"),
                     ("term_length", "policy.policy_term_months"),
                     ("term_amount", "premium.total_policy_premium")):
        if copy_of(src):
            history[key] = copy_of(src)
    transaction = {}
    for key, src in (("transaction_date", "document.transaction_date"),
                     ("transaction_effective_date", "document.transaction_effective_date"),
                     ("effective_date", "policy.effective_date"),
                     ("expiration_date", "policy.expiration_date"),
                     ("term_amount", "premium.total_policy_premium")):
        if copy_of(src):
            transaction[key] = copy_of(src)
    if transaction:
        history["transactions"] = [transaction]
    unit_path = (unit_list(schema) or ("",))[0]
    rows = []
    for unit in (_get(gold, unit_path) or []) if unit_path else []:
        for cov in unit.get("coverages", []):
            row = {}
            for key, src in (("coverage_name", "coverage_name"), ("limit", "limit_amount"),
                             ("deductible", "deductible_amount"), ("premium", "premium")):
                if src in cov:
                    row[key] = copy.deepcopy(cov[src])
            rows.append(row)
    if rows:
        history["coverage_premium_rows"] = rows
    if history:
        merge(gold.setdefault("document_type_detail", {}).setdefault("policy_history", {}), history)
    return gold
