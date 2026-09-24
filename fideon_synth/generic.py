"""
Generic synthetic generator: any source PDF in, a synthetic twin and gold out.

No per-carrier or per-document code. For each source PDF:

1. **Read** the page layout from whatever text layer it has (see :mod:`overlay`).
2. **Find** the values that identify the policy, by their shape and position:
   dates, money, phone numbers, emails, FEINs, policy/hull/account numbers,
   street and city lines, PO boxes, and the names printed above an address or
   under a label such as "Insured", "Agent" or "Clients".
3. **Replace** them consistently: one original always gets one replacement,
   every date moves by the same offset (so terms and date order survive),
   money scales by one factor, identifiers keep their shape.
4. **Draw** the replacements in place and rescan the result.
5. **Label** what it can for the gold: a value's printed label ("Policy
   Number:") is matched to the canonical schema's field names and aliases.
   Only confident matches go into the schema fields; everything else that was
   changed is listed under ``fideon:unmapped`` with its label and pages, so
   the gold never asserts a field it only guessed.

The line of business is the source's folder name (``.../<Carrier>/<lob>/x.pdf``)
and picks the schema; the carrier is the folder above it.

Known limits, reported rather than hidden: a value the OCR misread is not
recognised and stays as printed; table cells (coverage rows) are replaced but
not labelled; money totals can differ by a rounding unit from their scaled
parts.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import fitz

from . import overlay, pageref, structure
from .corpus import Built, Report
from .fields import NO_EVIDENCE, as_number, derived, fv, strip_evidence
from .scan import by_key as scan_by_key, scan_pdf
from .schema import CanonicalSchema, available
from .values import GIVEN, STREET_NAME, SURNAME, Values

# ── corpora ─────────────────────────────────────────────────────────────────

NAME_PREFIX = [
    "Harrowgate", "Beacon Crest", "Empire Ridge", "Mohawk Valley", "Adirondack",
    "Pioneer", "Winterberry", "Ironwood", "Northfield", "Stonecrop", "Larkspur",
    "Cedarhollow", "Brightwater", "Thornfield", "Millbrook", "Fernbank",
    "Blue Heron", "Silverbirch", "Lakeshore", "Meadowbrook", "Oakmont",
    "Pinecrest", "Riverbend", "Summit Ridge", "Timberline", "Willowbrook",
]
COMPANY_WORDS = {"llc", "inc", "inc.", "corp", "corp.", "corporation", "company",
                 "co", "co.", "group", "agency", "insurance", "lp", "llp", "ltd",
                 "trust", "partners", "services", "associates", "brokers",
                 "brokerage", "holdings", "ventures", "properties", "realty",
                 "marine", "agents", "risk", "underwriters"}
#: (city, ZIP) - real towns, main post-office ZIPs.
TOWNS = [
    ("Cooperstown", "13326"), ("Oneonta", "13820"), ("Norwich", "13815"),
    ("Delhi", "13753"), ("Cobleskill", "12043"), ("Herkimer", "13350"),
    ("Little Falls", "13365"), ("Utica", "13501"), ("Rome", "13440"),
    ("Cazenovia", "13035"), ("Hamilton", "13346"), ("Oswego", "13126"),
    ("Ithaca", "14850"), ("Cortland", "13045"), ("Binghamton", "13901"),
    ("Owego", "13827"), ("Elmira", "14901"), ("Corning", "14830"),
    ("Watertown", "13601"), ("Potsdam", "13676"), ("Saranac Lake", "12983"),
    ("Lake Placid", "12946"), ("Glens Falls", "12801"), ("Kingston", "12401"),
    ("Old Forge", "13420"), ("Skaneateles", "13152"), ("Geneva", "14456"),
    ("Canandaigua", "14424"), ("Hammondsport", "14840"), ("Clayton", "13624"),
]
STATES = set("""AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN
MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC""".split())

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# ── value shapes ────────────────────────────────────────────────────────────

_B = r"(?<![A-Za-z0-9])"
#: street-type words: part of a street line, never of a city name
_SUFFIX = (r"(?i:St|Street|Rd|Road|Ave|Avenue|Way|Ln|Lane|Dr|Drive|Pl|Place|Ct|Court|Blvd|"
           r"Hwy|Highway|Route|Rte|Pkwy|Ter|Terrace|Cir|Circle|Trl|Trail|Suite|Ste|Floor|Fl)")
_E = r"(?![A-Za-z0-9])"
PATTERNS = [   # (kind, regex) - earlier kinds win overlaps
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[A-Za-z]{2,})+")),
    ("phone", re.compile(r"(?<!\d)(?:\(\d{3}\)\s?|\d{3}[-.])\d{3}[-.]\d{4}(?!\d)")),
    ("fein", re.compile(r"(?<![\d-])\d{2}-\d{7}(?![\d-])")),
    ("pobox", re.compile(r"\bP\.?\s?O\.?\s?Box\s+\d+\b", re.I)),
    ("cityline", re.compile(
        r"(?<![A-Za-z])((?:(?!%s\b)[A-Z][A-Za-z.']+\s){0,2}(?!%s\b)[A-Z][A-Za-z.']+),?\s+([A-Z]{2})\s+(\d{5})(?:-\d{4})?(?!\d)"
        % (_SUFFIX, _SUFFIX))),
    ("street", re.compile(
        r"(?<![\w/$.,-])\d{1,6}\s+(?!\d)(?:[A-Za-z0-9.']+\s){0,3}(?:St|Street|Rd|Road|Ave|Avenue|Way|"
        r"Ln|Lane|Dr|Drive|Pl|Place|Ct|Court|Blvd|Hwy|Highway|Route|Rte|Pkwy|Ter|Terrace|"
        r"Cir|Circle|Trl|Trail|Pt|Point|Cove|Loop|Run|Pike|Path|Row|Sq)\b\.?", re.I)),
    ("date", re.compile(r"(?<![\d/])\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})(?![\d/])")),
    ("date", re.compile(r"(?<![\d-])\d{4}-\d{2}-\d{2}(?![\d-])")),
    ("date", re.compile(r"\b(?:%s)\.? \d{1,2}, \d{4}\b" % "|".join(MONTHS + [m[:3] for m in MONTHS] + ["Sept"]))),
    ("money", re.compile(r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?(?![\d,])")),
    ("id", re.compile(_B + r"(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9][A-Z0-9-]{5,}" + _E)),
    ("digits", re.compile(r"(?<![\w$,./-])\d{5,}(?:\s-\s\d{3,})?(?![\w,./-])")),
]
FORM_NUMBER = re.compile(r"^[A-Z]{2,6}\d{2,5}-\d{4}$")     # forms keep their numbers
ID_LABEL = re.compile(r"\b(number|no|id|code|hin|vin|account|acct|agency|customer|"
                      r"ref|serial|hull|loan|certificate|claim|policy|#)\b", re.I)
NAME_LABEL = re.compile(r"\b(insured|insureds|client|clients|agent|producer|"
                        r"operator|operators|owner|applicant|contact)\b", re.I)
PRODUCER_LABEL = re.compile(r"\b(agent|producer|agency|broker)\b", re.I)
INSURED_LABEL = re.compile(r"\b(insured|insureds|client|clients|applicant|owner)\b", re.I)
NOT_A_NAME = re.compile(r"\b(page|policy|coverage|date|premium|limit|number|total|"
                        r"address|description|declarations|location|endorsement|"
                        r"information|type|plan|form|effective|expiration|period)\b", re.I)
PII = {"email", "phone", "fein", "pobox", "cityline", "street", "id", "digits",
       "person", "company"}


# ── the schema, as label phrases ────────────────────────────────────────────

#: Label phrasings common across carriers, beyond the schema's own aliases.
SYNONYMS = {
    "policy number": "policy.policy_number", "policy no": "policy.policy_number",
    "policy": "policy.policy_number",
    "prior policy number": "policy.prior_policy_number",
    "agency number": "producer.producer_code", "agency id": "producer.producer_code",
    "agency code": "producer.producer_code", "agent code": "producer.producer_code",
    "agent number": "producer.producer_code", "producer code": "producer.producer_code",
    "effective date": "policy.effective_date", "policy period from": "policy.effective_date",
    "policy period": "policy.effective_date", "from": "policy.effective_date",
    "effective": "policy.effective_date",
    "expiration date": "policy.expiration_date", "to": "policy.expiration_date",
    "expiration": "policy.expiration_date", "expires": "policy.expiration_date",
    "transaction effective date": "document.transaction_effective_date",
    "issue date": "document.issue_date", "date issued": "document.issue_date",
    "print date": "document.print_date", "date printed": "document.print_date",
    "inception date": "policy.policyholder_since_date",
    "total annual premium": "premium.total_policy_premium",
    "total premium": "premium.total_policy_premium",
    "total policy premium": "premium.total_policy_premium",
    "term amount": "premium.total_policy_premium",
    "annual premium": "premium.total_policy_premium",
    "minimum earned premium": "premium.minimum_premium",
    "minimum premium": "premium.minimum_premium",
    "fein": "named_insured.fein", "fein number": "named_insured.fein",
    "federal id": "named_insured.fein", "federal employer id": "named_insured.fein",
    "signed on": "signature.signature_date", "signature date": "signature.signature_date",
    "email": "named_insured.contact.email", "email address": "named_insured.contact.email",
    "phone": "named_insured.contact.phone", "cell phone": "named_insured.contact.phone",
    "home phone": "named_insured.contact.phone", "telephone": "named_insured.contact.phone",
}
KIND_FITS = {
    "date": re.compile(r"date"),
    "money": re.compile(r"premium|amount|limit|fee|deductible|value|surcharge|tax"),
    "id": re.compile(r"number|code|_id|fein"), "digits": re.compile(r"number|code|_id|fein"),
    "fein": re.compile(r"fein"), "phone": re.compile(r"phone|fax"),
    "email": re.compile(r"email"),
}


def _norm_label(text):
    text = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    words = [w for w in text.split() if w not in ("your", "the", "of")]
    return " ".join(words)


def label_index(schema):
    """Label phrase -> schema path, from field names, aliases and SYNONYMS.
    Only non-list fields: a list entry needs a row to hang on."""
    index = {}

    def visit(node, path):
        if "[]" in path:
            return
        for alias in node.get("fideon:aliases", []) or []:
            index.setdefault(_norm_label(alias), path)
        if "$ref" in node:
            name = node["$ref"].split("/")[-1]
            if name == "FieldValue":
                index.setdefault(_norm_label(path.rsplit(".", 1)[-1].replace("_", " ")), path)
            else:
                visit(schema.merged["$defs"][name], path)
            return
        if node.get("type") == "array":
            visit(node.get("items") or {}, path + "[]")
        for key, sub in (node.get("properties") or {}).items():
            visit(sub, f"{path}.{key}" if path else key)

    # these first, so their phrasings win; then every other section except the
    # per-document-type blocks, which only a document of that type fills
    first = ("policy", "premium", "document", "producer", "named_insured", "signature")
    for key in first + tuple(k for k in schema.merged["properties"]
                             if k not in first and k != "document_type_detail"):
        if key in schema.merged["properties"]:
            visit(schema.merged["properties"][key], key)
    index.update(SYNONYMS)
    return {k: v for k, v in index.items() if k and v in schema.leaves}


def match_label(label, kind, index):
    """The schema path a label names, or None. Whole-label matches first;
    then the longest multi-word phrase contained in the label."""
    if not label:
        return None
    fits = KIND_FITS.get(kind)
    ok = (lambda p: fits.search(p.rsplit(".", 1)[-1])) if fits else (lambda p: True)
    if label in index and ok(index[label]):
        return index[label]
    padded = " %s " % label
    best = None
    for phrase, path in index.items():
        if " " in phrase and " %s " % phrase in padded and ok(path):
            if best is None or len(phrase) > len(best[0]):
                best = (phrase, path)
    return best[1] if best else None


# ── detection ───────────────────────────────────────────────────────────────

class Found:
    """One printed value to replace."""

    def __init__(self, kind, cell, start, end):
        self.kind, self.cell, self.start, self.end = kind, cell, start, end
        self.text = cell.text[start:end]
        self.label = ""
        self.after = 0            # where the previous value in this cell ended
        self.role = None          # "insured" / "producer" for name-address blocks
        self.new = None
        self.key = None           # the whole value, when this is one piece of it
        self.blank = False        # a later piece of a value split across cells

    @property
    def rect(self):
        return self.cell.span_rect(self.start, self.end)


def _detect(cell_list):
    found = []
    for cell in cell_list:
        if re.search(r"https?:|www\.|://", cell.text):
            continue
        taken = []
        for kind, rx in PATTERNS:
            for m in rx.finditer(cell.text):
                s, e = m.span()
                if any(s < te and ts < e for ts, te in taken):
                    continue
                text = m.group(0)
                if kind == "id" and (FORM_NUMBER.match(text) or len(re.sub(r"\D", "", text)) < 3):
                    continue
                if kind == "cityline" and m.group(2) not in STATES:
                    continue
                found.append(Found(kind, cell, s, e))
                taken.append((s, e))
    return found


def _above(cell, cell_list, max_gap=1.9, x_tol=14):
    """The cell printed directly above ``cell`` in the same column."""
    r = cell.rect
    best = None
    for other in cell_list:
        o = other.rect
        if other is cell or o.y1 > r.y0 + 0.5 * r.height or r.y0 - o.y1 > max_gap * r.height:
            continue
        if abs(o.x0 - r.x0) <= x_tol or (o.x0 <= r.x0 and o.x1 >= r.x0 + 4):
            if best is None or o.y1 > best.rect.y1:
                best = other
    return best


def _below(cell, cell_list, max_gap=1.8, x_tol=14):
    r = cell.rect
    best = None
    for other in cell_list:
        o = other.rect
        if other is cell or o.y0 < r.y1 - 0.5 * r.height or o.y0 - r.y1 > max_gap * r.height:
            continue
        if abs(o.x0 - r.x0) <= x_tol:
            if best is None or o.y0 < best.rect.y0:
                best = other
    return best


def _left(cell, cell_list):
    r = cell.rect
    best = None
    for other in cell_list:
        if other.row == cell.row and other.rect.x1 <= r.x0 + 1:
            if best is None or other.rect.x1 > best.rect.x1:
                best = other
    return best


def _looks_like_name(text):
    words = text.split()
    if not 2 <= len(words) <= 5 or ":" in text or NOT_A_NAME.search(text):
        return False
    if re.search(r"\b(for|to|the|in|on|by|with|if|is|are|be|this|that|your|our|from|at)\b",
                 text, re.I):
        return False                      # a heading or a sentence, not a name
    if ";" in text or any(w[0].islower() for w in words if w.lower() not in ("and", "of", "&", "de", "van", "von")):
        return False                      # names are capitalised; policy wording is not
    if "," in text and not re.fullmatch(r"[A-Za-z'-]+, [A-Za-z.' -]+", text):
        return False                      # "Smith, John" is a name; a list is not
    letters = sum(c.isalpha() for c in text)
    return letters >= 0.8 * len(text.replace(" ", "")) and not re.search(r"\d", text)


def _label_for(f, cell_list):
    """The text that labels a value: text before it in its own cell, else the
    cell to its left, else the cell above it."""
    prefix = f.cell.text[f.after:f.start].strip()
    if prefix and re.search(r"[A-Za-z]", prefix):
        return prefix
    left = _left(f.cell, cell_list)
    if left is not None and re.search(r"[A-Za-z]{2}", left.text) and not re.search(r"\d", left.text):
        return left.text
    up = _label_above(f.rect, cell_list)
    return up or ""


def _label_above(r, cell_list, max_gap=2.2):
    """The label printed over a value: the nearest cell above it, by vertical
    gap and then horizontal distance - a value in a box is often indented from
    its label. When that cell holds several "Label:" headings run together,
    only the heading nearest the value is its label."""
    best, best_key = None, None
    for other in cell_list:
        o = other.rect
        if o.y1 > r.y0 + 0.5 * r.height or r.y0 - o.y1 > max_gap * r.height:
            continue
        if not re.search(r"[A-Za-z]{2}", other.text):
            continue
        dx = max(0.0, o.x0 - r.x1, r.x0 - o.x1)
        if dx > 3 * r.height:
            continue
        key = (round((r.y0 - o.y1) / max(r.height, 1)), dx)
        if best_key is None or key < best_key:
            best, best_key = other, key
    if best is None:
        return None
    segments = [(m.start(), m.end()) for m in re.finditer(r"[^:]+:?", best.text)
                if m.group(0).strip()]
    if len(segments) < 2:
        return best.text
    def distance(seg):
        s = best.span_rect(*seg)
        return 1e9 if s is None else max(0.0, s.x0 - r.x1, r.x0 - s.x1) + abs(s.x0 - r.x0) * 0.01
    start, end = min(segments, key=distance)
    return best.text[start:end].strip()


def find_values(cell_list):
    """Everything on a page worth replacing, labelled where a label exists."""
    found = _detect(cell_list)
    for f in found:
        before = [g.end for g in found if g.cell is f.cell and g.end <= f.start]
        f.after = max(before, default=0)
        f.label = _label_for(f, cell_list)
    # a bare run of digits is only an identifier when a label says so, and
    # a form number keeps its number however it is shaped
    found = [f for f in found if (f.kind != "digits" or ID_LABEL.search(f.label))
             and (f.kind != "id" or len(re.sub(r"\D", "", f.text)) >= 5 or ID_LABEL.search(f.label))
             and not (f.kind in ("id", "digits") and re.search(r"\bforms?\b", f.label, re.I))]

    # names: the line above an address, or the line a name label introduces
    names = {}
    for f in found:
        if f.kind in ("street", "pobox") and f.start == 0:
            up = _above(f.cell, cell_list)
            if up is not None and _looks_like_name(up.text):
                names[id(up)] = (up, None)
    for cell in cell_list:
        if NAME_LABEL.search(cell.text) and len(cell.text) < 45:
            for cand in (_below(cell, cell_list, max_gap=3.2), ):
                if cand is not None and _looks_like_name(cand.text):
                    names[id(cand)] = (cand, cell.text)
    for cell, label in names.values():
        if any(f.cell is cell for f in found):
            continue
        kind = "company" if set(w.lower().strip(",") for w in cell.text.split()) & COMPANY_WORDS \
            else "person"
        f = Found(kind, cell, 0, len(cell.text))
        f.label = label or ""
        found.append(f)

    # who a name-and-address block belongs to
    for f in found:
        if f.kind not in ("person", "company"):
            continue
        context = f.label
        up = f.cell
        for _ in range(3):
            if context:
                break
            up = _above(up, cell_list, max_gap=3.5, x_tol=60)
            if up is None:
                break
            if NAME_LABEL.search(up.text) or PRODUCER_LABEL.search(up.text):
                context = up.text
        if PRODUCER_LABEL.search(context or ""):
            f.role = "producer"
        elif INSURED_LABEL.search(context or ""):
            f.role = "insured"
        elif f.kind == "company" and re.search(r"insurance|agency|brokers?", f.text, re.I):
            f.role = "producer"
    return found


# ── replacements ────────────────────────────────────────────────────────────

def _case_like(new, old):
    if old.isupper():
        return new.upper()
    if old.islower():
        return new.lower()
    return new


def _reshape_digits(text, vals):
    """Same shape, new digits; a group's leading zeros are kept, the way
    carrier numbering pads them."""
    def group(m):
        g = m.group(0)
        zeros = len(g) - len(g.lstrip("0"))
        zeros = min(zeros, len(g) - 1)
        rest = len(g) - zeros
        body = str(vals.integer(1, 9)) + "".join(str(vals.integer(0, 9)) for _ in range(rest - 1))
        return "0" * zeros + body
    for _ in range(10):
        new = re.sub(r"\d+", group, text)
        if new != text:
            return new
    return new


class Faker:
    """Consistent replacements for one document."""

    def __init__(self, vals: Values, originals=()):
        self.v = vals
        self.days = vals.choice([-1, 1]) * vals.integer(45, 540)
        self.factor = vals.rng.uniform(0.82, 1.28)
        self.memo: Dict[tuple, str] = {}
        # a replacement must not be another original value of this document -
        # the insured's town handed to the agent is still the insured's town
        self.used = {_key(o) for o in originals}

    def __call__(self, f: Found) -> str:
        if f.blank:
            return ""
        key = (f.kind, f.key or _key(f.text))
        if key not in self.memo:
            self.memo[key] = getattr(self, "_" + f.kind)(f.text)
        return _case_like(self.memo[key], f.text)

    def _unique(self, make, old):
        for _ in range(50):
            new = make()
            if _key(new) != _key(old) and _key(new) not in self.used:
                self.used.add(_key(new))
                return new
        return new

    # identity
    def _person(self, old):
        words = old.split()
        def make():
            parts = [self.v.choice(GIVEN), self.v.choice(SURNAME)]
            if len(words) >= 3 and len(words[1].strip(".")) == 1:
                parts.insert(1, self.v.choice("ABCDEFGHJKLMNPRSTW") + ".")
            return " ".join(parts)
        return self._unique(make, old)

    def _company(self, old):
        words = old.split()
        tail = []
        while words and words[-1].lower().strip(",") in COMPANY_WORDS:
            tail.insert(0, words.pop())
        tail = tail or ["LLC"]
        make = lambda: " ".join([self.v.choice(NAME_PREFIX)] + tail)
        return self._unique(make, old)

    def _street(self, old):
        m = re.match(r"(\d+)", old)
        digits = len(m.group(1)) if m else 3
        make = lambda: "%d %s" % (self.v.integer(10 ** (digits - 1), 10 ** digits - 1),
                                  self.v.choice(STREET_NAME))
        return self._unique(make, old)

    def _pobox(self, old):
        m = re.match(r"(.*?)(\d+)$", old)
        return m.group(1) + str(self.v.integer(12, 990))

    def _cityline(self, old):
        comma = "," in old
        def make():
            city, zip_ = self.v.choice(TOWNS)
            return "%s%s NY %s" % (city, "," if comma else "", zip_)
        return self._unique(make, old)

    # contact
    def _phone(self, old):
        area = self.v.choice(["315", "518", "607", "716", "845"])
        line = "01%02d" % self.v.integer(0, 99)
        if old.startswith("("):
            return "(%s) 555-%s" % (area, line)
        sep = "." if "." in old else "-"
        return sep.join([area, "555", line])

    def _email(self, old):
        return "%s.%s@example.com" % (self.v.choice(GIVEN).lower(), self.v.choice(SURNAME).lower())

    def _fein(self, old):
        return "%02d-%07d" % (self.v.choice([20, 22, 26, 45, 46, 81, 82, 83, 84, 85, 86, 87]),
                              self.v.integer(0, 9999999))

    # identifiers
    def _id(self, old):
        return self._unique(lambda: _reshape_digits(old, self.v), old)

    _digits = _id

    # dates and money
    def _date(self, old):
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%b. %d, %Y"):
            try:
                d = datetime.strptime(old, fmt).date()
                break
            except ValueError:
                continue
        else:
            return old
        n = d + timedelta(days=self.days)
        if "/" in old:
            mo, dy, yr = old.split("/")
            parts = [("%02d" if len(mo) == 2 else "%d") % n.month,
                     ("%02d" if len(dy) == 2 else "%d") % n.day,
                     str(n.year) if len(yr) == 4 else "%02d" % (n.year % 100)]
            return "/".join(parts)
        if "-" in old:
            return n.isoformat()
        return "%s %d, %d" % (n.strftime("%B" if old.split()[0] in MONTHS else "%b"), n.day, n.year)

    def _money(self, old):
        amount = as_number(old)
        if not amount:
            return old
        cents = "." in old
        value = amount * self.factor
        if not cents and amount >= 10000 and amount % 1000 == 0:
            value = round(value / 1000) * 1000
        text = "{:,.2f}".format(value) if cents else "{:,}".format(int(round(value)))
        return ("$ " if old.startswith("$ ") else "$") + text


# ── gold ────────────────────────────────────────────────────────────────────

def _set(doc, path, value):
    keys = path.split(".")
    for k in keys[:-1]:
        doc = doc.setdefault(k, {})
    doc.setdefault(keys[-1], value)


def _field(kind, raw):
    if kind == "date":
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
            try:
                return fv(raw, datetime.strptime(raw, fmt).strftime("%Y-%m-%d"))
            except ValueError:
                pass
    if kind == "money":
        return fv(raw, as_number(raw))
    return fv(raw)


def build_gold(found, index, carrier, lob_title, pdf_name, pages, page_text):
    gold = {"document": {"source_file_name": derived(pdf_name),
                         "page_count": derived(str(pages), NO_EVIDENCE, pages)}}
    on_page = pageref.on_page(pageref._norm(carrier), page_text)
    gold["carrier"] = {"company_name": fv(carrier) if on_page else derived(carrier)}
    unmapped, placed = [], set()

    # name-and-address blocks
    by_cell = {}
    for f in found:
        by_cell.setdefault(id(f.cell), []).append(f)
    for f in found:
        if f.kind not in ("person", "company") or f.role is None:
            continue
        base = "named_insured" if f.role == "insured" else "producer"
        name_path = base + (".primary_name" if base == "named_insured" else ".agency_name")
        if name_path in placed:
            # a second name under its own label: "CLIENTS" is a contact
            path = match_label(_norm_label(f.label), f.kind, index)
            if path and path not in placed:
                _set(gold, path, fv(f.new))
                placed.add(path)
                continue
            unmapped.append({"kind": f.kind, "label": f.label.strip(), "value": f.new,
                             "page": f.cell.page + 1})
            continue
        placed.add(name_path)
        _set(gold, name_path, fv(f.new))
        if base == "named_insured":
            gold["named_insured"]["entity_type"] = derived(
                "Individual" if f.kind == "person" else "Organization", f.new)
        addr = base + (".mailing_address" if base == "named_insured" else ".address")
        cell = f.cell
        for _ in range(3):
            cell = _below(cell, [x.cell for x in found])
            if cell is None:
                break
            for g in by_cell.get(id(cell), []):
                if g.kind in ("street", "pobox"):
                    _set(gold, addr + ".line_1", fv(g.new)); g.label = g.label or "(address)"
                    placed.add(id(g))
                elif g.kind == "cityline":
                    m = PATTERNS[4][1].search(g.new)
                    if m:
                        _set(gold, addr + ".city", fv(m.group(1)))
                        _set(gold, addr + ".state", fv(m.group(2)))
                        _set(gold, addr + ".postal_code", fv(m.group(3)))
                        placed.add(id(g))

    for f in found:
        if f.blank or id(f) in placed or f.kind in ("person", "company") and f.role:
            continue
        label = _norm_label(f.label)
        path = match_label(label, f.kind, index)
        if f.kind in ("phone", "email") and PRODUCER_LABEL.search(f.label):
            path = "producer.contact." + f.kind
        if path and path not in placed:
            _set(gold, path, _field(f.kind, f.new))
            placed.add(path)
        elif path and _get(gold, path) is not None and _get(gold, path)["raw"] == f.new:
            continue                                  # same value printed again
        else:
            unmapped.append({"kind": f.kind, "label": f.label.strip(), "value": f.new,
                             "page": f.cell.page + 1})
    if lob_title:
        gold["document"].setdefault("line_of_business_as_stated", derived(lob_title))
    return gold, unmapped


def _get(doc, path):
    for k in path.split("."):
        if not isinstance(doc, dict) or k not in doc:
            return None
        doc = doc[k]
    return doc


# ── pipeline ────────────────────────────────────────────────────────────────

def _lob_for(source_pdf, schema_dir):
    names = set(available(schema_dir))
    for part in (source_pdf.parent.name, source_pdf.parent.parent.name):
        if part in names:
            return part
    return "_fallback"


def _sweep(pages, marks=()):
    """Replace an identifying value everywhere it is printed, not only where
    its shape or label gave it away. A policy number found beside "Policy
    Number:" on page 1 is the same policy number in a page-4 footer that
    carries no label, and left there it leaks the original.

    Matching is across a whole row, ignoring case and spacing: the same name
    is often printed in capitals elsewhere, or set in two table columns. A
    match that spans cells is redrawn in the first and blanked in the rest."""
    kinds = {}
    for *_, found in pages:
        for f in found:
            if f.kind in PII and len(f.text) >= 4 and not f.blank:
                kinds.setdefault(_key(f.text), f.kind)
    if not kinds:
        return
    # a name can be run into the word before it ("Prepared forMartin
    # Lindqvist"); a lowercase-to-capital join is a boundary for names only
    glued = r"(?:(?<![A-Za-z0-9])|(?-i:(?<=[a-z])(?=[A-Z]))%s)" % "".join(
        "|(?<=%s)" % re.escape(m) for m in sorted(marks))
    pattern = re.compile("|".join(
        (glued if kinds[k] in ("person", "company") else r"(?<![A-Za-z0-9])")
        + r"\s+".join(map(re.escape, k.split())) + r"(?![A-Za-z0-9])"
        for k in sorted(kinds, key=len, reverse=True)), re.I)
    for page, ink, matrix, visible, cell_list, found in pages:
        taken = {}
        for f in found:
            taken.setdefault(id(f.cell), []).append((f.start, f.end))
        rows = {}
        for cell in cell_list:
            rows.setdefault(cell.row, []).append(cell)
        for row in rows.values():
            row.sort(key=lambda c: c.rect.x0)
            text, where = "", []
            for cell in row:
                if text:
                    text += " "
                    where.append(None)
                for i in range(len(cell.text)):
                    where.append((cell, i))
                text += cell.text
            for m in pattern.finditer(text):
                pieces = {}
                for k in range(*m.span()):
                    if where[k] is not None:
                        cell, i = where[k]
                        s, e = pieces.get(id(cell), (cell, i, i))[1:]
                        pieces[id(cell)] = (cell, min(s, i), max(e, i + 1))
                if any(any(s < te and ts < e for ts, te in taken.get(id(c), []))
                       for c, s, e in pieces.values()):
                    continue
                full = _key(m.group(0))
                for n, (cell, s, e) in enumerate(pieces.values()):
                    f = Found(kinds[full], cell, s, e)
                    f.key, f.blank = full, n > 0
                    f.label = _label_for(f, cell_list)
                    found.append(f)
                    taken.setdefault(id(cell), []).append((s, e))
        # and a value wrapped onto the next line of a narrow column
        for cell in cell_list:
            head = _key(cell.text)
            if not head or taken.get(id(cell)):
                continue
            for full, kind in kinds.items():
                if not full.startswith(head + " "):
                    continue
                below = _below(cell, cell_list)
                if below is None or taken.get(id(below)) or _key(below.text) != full[len(head) + 1:]:
                    continue
                for n, c in enumerate((cell, below)):
                    f = Found(kind, c, 0, len(c.text))
                    f.key, f.blank = full, n > 0
                    f.label = _label_for(f, cell_list)
                    found.append(f)
                    taken.setdefault(id(c), []).append((0, len(c.text)))
                break


def _key(text):
    return " ".join(text.lower().split())


def _carrier_marks(carrier):
    """The distinctive words of a carrier's name: "utica" in "Utica First
    Insurance Company", never "insurance" or "mutual"."""
    generic = {"insurance", "company", "mutual", "group", "assurance", "casualty",
               "underwriters", "surplus", "cooperative", "national", "american",
               "general", "services", "insurers", "indemnity", "specialty", "fire",
               "property", "preferred", "corp", "corporation", "inc", "llc", "first"}
    return {w for w in re.findall(r"[a-z]{4,}", carrier.lower()) if w not in generic}


def _drop_carrier(found, cell_list, carrier):
    """The carrier's own name and address are public and stay as printed -
    the gold names the carrier, and an insurer is not a policyholder."""
    marks = _carrier_marks(carrier)
    if not marks:
        return found
    for f in found:                         # "UticaCEDARLINE FABRICATION"
        if f.kind in ("person", "company"):
            for mark in marks:
                if f.text.lower().startswith(mark) and f.text[len(mark):len(mark) + 1].isalpha():
                    f.start += len(mark)
                    f.text = f.cell.text[f.start:f.end]
                    break
    drop = set()
    for f in found:
        if f.kind == "company" and marks & set(re.findall(r"[a-z]{4,}", f.text.lower())):
            drop.add(id(f))
            cell = f.cell
            for _ in range(3):              # and the address printed under it
                cell = _below(cell, cell_list)
                if cell is None:
                    break
                for g in found:
                    if g.cell is cell and g.kind in ("street", "pobox", "cityline"):
                        drop.add(id(g))
    return [f for f in found if id(f) not in drop]


def _alignment(f, cell_list):
    """``right`` when the value sits in a right-aligned column - the cells
    above and below it end where it ends but start elsewhere."""
    r = f.rect
    lefts = rights = 0
    for c in cell_list:
        if c is f.cell or abs(c.row - f.cell.row) > 3:
            continue
        o = c.rect
        if abs(o.x0 - r.x0) < 1.5:
            lefts += 1
        elif abs(o.x1 - r.x1) < 1.5:
            rights += 1
    return "right" if rights > lefts else "left"


def synthesize(source_pdf, out_pdf, out_gold, schema, vals, seed=0):
    """One synthetic document and its gold from one source PDF."""
    source_pdf = Path(source_pdf)
    built = Built(key=Path(out_pdf).stem, pdf=Path(out_pdf), gold=Path(out_gold),
                  pages=0, fields=0)
    digital = built.pdf.with_name("_temp_" + built.pdf.name)
    try:
        doc = fitz.open(str(source_pdf))
        built.pages = len(doc)
        found_all, plans, pages = [], [], []
        for page in doc:
            ink = overlay.Ink(page)
            visible = not overlay.invisible_text(page)
            matrix = fitz.Identity if visible else overlay.calibrate(page, ink)
            cell_list = overlay.cells(page, matrix, ink)
            found = _drop_carrier(find_values(cell_list), cell_list, source_pdf.parent.parent.name)
            pages.append((page, ink, matrix, visible, cell_list, found))
        _sweep(pages, _carrier_marks(source_pdf.parent.parent.name))
        faker = Faker(vals, [f.text for *_, found in pages for f in found if f.kind in PII])
        for page, ink, matrix, visible, cell_list, found in pages:
            reps = []
            for f in found:
                f.new = faker(f)
                if f.new == f.text:
                    continue
                first = next(ch for ch in f.cell.chars[f.start:f.end] if ch is not None)
                nxt = next((c for c in cell_list if c.row == f.cell.row
                            and c.rect.x0 > f.rect.x1 + 0.5), None)
                # punctuation printed against the value - a comma, or the dash
                # of a range like "Dec 23, 2025-Dec 23, 2026" - is covered with
                # it, so it is redrawn with it
                end = f.end + (f.end < len(f.cell.text) and f.cell.text[f.end] in ",;-\u2013")
                tail = f.cell.text[f.end:end]
                reps.append(overlay.Replacement(
                    page=page.number, old=f.text + tail, new=f.new + tail,
                    visible_rect=f.cell.span_rect(f.start, end),
                    ocr_rect=f.cell.span_rect(f.start, end, ocr=True),
                    font=overlay.base14(first.font, visible), face_known=visible,
                    glued=f.start > 0 and f.cell.text[f.start - 1] not in " ",
                    color=first.color if visible else 0,
                    align=_alignment(f, cell_list),
                    room=(nxt.rect.x0 - 3) if nxt is not None else page.rect.width - 18))
            found_all += found
            plans.append((page, reps, ink, matrix))
        carrier = source_pdf.parent.parent.name
        index = label_index(schema)
        reader = structure.Reader([(p.number, p.rect.height, cell_list, found)
                                   for p, _, _, _, cell_list, found in pages],
                                  schema, index, carrier)
        laid_out = reader.read()
        for page, reps, ink, matrix in plans:
            overlay.apply(page, reps, ink, matrix)
        doc.save(str(digital), garbage=3, deflate=True)
        doc.close()

        texts = pageref.page_texts(digital)
        whole = " ".join(texts)
        rest = whole
        for new in sorted({pageref._norm(f.new) for f in found_all if f.new}, key=len, reverse=True):
            rest = rest.replace(new, " ")
        # a value split across cells is checked whole: its first piece alone
        # ("CEDARLINE") can be a word of some other name on the page
        leaks = sorted({f.key or f.text for f in found_all if f.kind in PII and f.new != f.text
                        and not f.blank
                        and pageref.on_page(pageref._norm(f.key or f.text), rest)})
        built.problems += ["source value %r is still in the generated PDF" % t for t in leaks]

        title = schema.merged.get("title", "")
        gold, unmapped = build_gold([f for f in found_all if id(f) not in reader.consumed],
                                    index, carrier, title, built.pdf.name, built.pages, whole)
        structure.finish(structure.merge(gold, laid_out), schema)
        resolved, misses = pageref.attach(gold, digital)
        built.problems += ["gold says %s = %r is printed, but it is not on any page"
                           % (p, raw) for p, raw in misses]
        for item in unmapped:
            item["page_ref"] = [i + 1 for i, t in enumerate(texts)
                                if pageref.on_page(pageref._norm(item["value"]), t)]

        stats = scan_pdf(digital, built.pdf, scan_by_key("high_quality"), seed=seed)
        built.profile = stats["profile"]
        strip_evidence(gold)
        gold["fideon:absent"] = schema.absent_from(pageref.stated_paths(gold))
        gold["fideon:unmapped"] = unmapped
        gold["fideon:provenance"] = {
            "generator": "fideon-synth generic",
            "source": "%s/%s/%s" % (carrier, source_pdf.parent.name, source_pdf.name),
            "schema": "%s v%s" % (schema.lob, schema.version),
            "render": "scanned_only",
            "scanner_profile": stats["profile"],
            "values_replaced": sum(1 for f in found_all if f.new != f.text),
            "date_shift_days": faker.days,
            "money_factor": round(faker.factor, 4),
            "synthetic": True,
            "note": "Identifying values replaced with invented ones. Fields under "
                    "fideon:unmapped were changed but could not be matched to a "
                    "schema field with confidence.",
        }
        # a required section the document never labels clearly (no named
        # insured found, say) is a gap in the gold, not a broken document
        errors = schema.validate(gold)
        missing = [e for e in errors if e.endswith("is a required property at (root)")]
        built.problems += [e for e in errors if e not in missing]
        if missing:
            gold["fideon:incomplete"] = [e.split("'")[1] if "'" in e else e for e in missing]
        built.gold.write_text(json.dumps(gold, indent=2, ensure_ascii=False), encoding="utf-8")
        built.fields = resolved + len(misses)
    except Exception as exc:  # one bad source must not stop a folder run
        built.problems.append("%s: %s" % (type(exc).__name__, exc))
    finally:
        # FIDEON_KEEP_DIGITAL=1 keeps the text-layer render next to the scan,
        # to see exactly what was replaced where
        if digital.exists() and not os.environ.get("FIDEON_KEEP_DIGITAL"):
            digital.unlink()
    return built


def generate_folder(folder, out_dir, schema_dir=None, count=1, seed=0,
                    pdf_subdir="PDF", gold_subdir="gold_json", progress=None):
    """``count`` synthetic documents for every PDF under ``folder``."""
    folder, out = Path(folder), Path(out_dir)
    pdf_dir, gold_dir = out / pdf_subdir, out / gold_subdir
    pdf_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)
    report = Report(template="generic", schema=str(folder))
    schemas = {}
    sources = [folder] if folder.is_file() else sorted(folder.rglob("*.pdf"))
    for source_pdf in sources:
        lob = _lob_for(source_pdf, schema_dir)
        if lob not in schemas:
            schemas[lob] = CanonicalSchema.load(lob, schema_dir)
        for index in range(1, count + 1):
            name = "%s_synth_%03d" % (source_pdf.stem, index)
            vals = Values("%s:%s:%d" % (seed, source_pdf.name, index))
            built = synthesize(source_pdf, pdf_dir / (name + ".pdf"),
                               gold_dir / (name + ".json"), schemas[lob], vals, seed=index)
            report.documents.append(built)
            if progress:
                progress(built)
    return report
