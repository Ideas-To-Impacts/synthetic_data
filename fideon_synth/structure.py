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

from .fields import as_date, as_number, derived, fv, is_field, yes_no

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
VALUE = re.compile(r"^-?\(?\$?\d[\d,]*(?:\.\d+)?\)?\*?$|^(?:incl(?:uded)?|excluded|n/?a)\W*$", re.I)
INCLUDED = re.compile(r"^incl", re.I)
COVERAGE_HEAD = {"name": {"coverage", "coverages", "endorsement", "endorsements"},
                 "limit": {"limit", "limits", "amount"},
                 "deductible": {"deductible", "deductibles"}, "premium": {"premium", "premiums"}}
#: a unit's own description line: "2024 Viaggio by Misty Harbor 20 Lago Series"
UNIT_LINE = re.compile(r"^((?:19|20)\d\d)\s+([A-Za-z].*?)(\s+\(continued\))?$", re.I)
#: a form reference: "BY-403 CW (11-23)", "PL-50776 NY (11-23)"
FORM_REF = re.compile(r"(?<![A-Z0-9-])([A-Z]{1,4}-[A-Z0-9]{2,6})(?:\s*([A-Z]{2}))?\s*\((\d{2}[-/]\d{2})\)")
#: a sub-row that qualifies its group's limit rather than naming a coverage
QUALIFIER = re.compile(r"^(?:amount of insurance|aggregate|each |per |any one)", re.I)
#: a coverage's premium effect in a policy change
PREMIUM_CHANGE = re.compile(r"\b(decreases|increases) the premium by\s*(\S+)", re.I)
SEASON = re.compile(r"not be in ([A-Z][a-z]+(?: [A-Z][a-z]+)*) for the period between "
                    r"([A-Z][a-z]+ \d{1,2})(?:\s*(?:st|nd|rd|th))?\s+and\s+([A-Z][a-z]+ \d{1,2})")
EFFECTIVE_AT = re.compile(r"\b(?:begins on|began on|period is from)\b.*?\bat\s+(?:the later of\s+)?"
                          r"(\d{1,2}:\d{2}\s*[AaPp]\.?\s?[Mm]\.?)(\s+STANDARD TIME)?", re.I)
#: "This policy period ends on <date> at 12:01 a.m.", "... to <date> at 12:01 A.M."
EXPIRES_AT = re.compile(r"(?:\b(?:expires on|ends on|period ends)\b|\bTIME\s+to\b)[^.]*?\bat\s+"
                        r"(\d{1,2}:\d{2}(?:\s*[AaPp]\.?\s?[Mm]\.?)?)", re.I)
LOCATION_HEAD = {"number": {"location", "loc", "#"}, "address": {"address"},
                 "legal": {"legal"}}
FORM_LINE = re.compile(r"^(?:(?P<num>[A-Z]{2,6}[0-9A-Z]{2,6}-\d{4})\s*)?-\s*(?P<title>\S.*)$")
def _form_of(ref):
    """A form number as printed with its state code: "BY-300 NY", "BY-403 CW"."""
    return ref.group(1) + (" " + ref.group(2) if ref.group(2) else "")


FORM_SHAPE = re.compile(r"^([A-Z]{2,6})(\d{3,5})-\d{4}$")
#: fields whose value is a date, an amount or an identifier - never a plain word
NOT_TEXT = re.compile(r"date|premium|amount|limit|fee|deductible|number(?!_of_)|_id$|"
                      r"(?<!postal_)code|phone|fax|email|fein|tax|surcharge|percentage|rate|value|"
                      r"address|(?<!company_)(?<!group_)name|insured|doing_business")
TIME = re.compile(r"\b(\d{1,2}:\d{2}\s*[AP]\.?\s?M\.?)\s+(\S.*\bTime\b.*)$")


# ── the page as words and values ────────────────────────────────────────────

class Seg:
    """One word, or one whole replaced value, with where it is printed."""

    def __init__(self, text, orig, rect, found=None, cell=None, start=0):
        self.text, self.orig, self.rect, self.found = text, orig, rect, found
        self.cell, self.start = cell, start

    @property
    def cx(self):
        return (self.rect.x0 + self.rect.x1) / 2


def _worded(seg):
    """Is this number followed by words in its own cell - "75 Nautical
    Miles" - so part of a phrase rather than a figure in a column?"""
    if seg.cell is None:
        return False
    after = seg.cell.text[seg.start + len(seg.orig):]
    return bool(re.match(r"\s+[A-Za-z]{2,}", after)) and not re.match(r"(?i)^\s*(?:incl|each|per)\b", after)


def say(segs):
    """A FieldValue for the text of ``segs``. A replaced value inside it is
    printed apart from the words around it, so the longest run of words
    that were not replaced is what the page is searched for."""
    raw = " ".join(s.text for s in segs).strip()
    if not any(s.found is not None for s in segs):
        return fv(raw)
    runs, run = [], []
    for s in segs:
        if s.found is None:
            run.append(s.text)
        else:
            runs.append(run)
            run = []
    runs.append(run)
    best = max((" ".join(r) for r in runs), key=len, default="")
    return fv(raw, evidence=best if len(best) >= 3 else raw)


def segments(cell, found):
    """The cell in reading order: a replaced value is one segment carrying its
    new text; the rest splits on spaces."""
    out, pos = [], 0

    def words(s, e):
        for m in re.finditer(r"\S+", cell.text[s:e]):
            r = cell.span_rect(s + m.start(), s + m.end())
            if r is not None:
                out.append(Seg(m.group(0), m.group(0), r, None, cell, s + m.start()))

    for f in sorted(found, key=lambda f: f.start):
        if f.start < pos:
            continue
        words(pos, f.start)
        if not f.blank and f.rect is not None:
            out.append(Seg(f.new if f.new is not None else f.text, f.text, f.rect, f, cell, f.start))
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
            for key, sub in (node["items"].get("properties") or {}).items():
                if "$ref" in sub and sub["$ref"].endswith("/FieldValue"):
                    self.unit_index.setdefault(self.norm(key.replace("_", " ")), []).append(key)
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
        self.conflicts = set()           # policy-wide paths the units disagree on
        self.units, self.locations, self.deductibles = [], [], []
        self.cur = -1                     # the unit being read; a unit can be returned to
        self.operators, self.discounts, self.skip = [], [], set()
        self.none_losses = self.none_violations = None
        block = schema.merged.get("fideon:source", {}).get("line_specific_block")
        blocknode = schema.merged["properties"].get(block) if block else None
        self.ops_at = None
        for key, sub in ((blocknode or {}).get("properties") or {}).items():
            if key == "operators" and sub.get("type") == "array":
                self.ops_at = ("%s.%s" % (block, key), sub)
        self.op_index = {}
        if self.ops_at:
            _aliases(self.ops_at[1]["items"], "", self.op_index, self.norm, defs)
            for key in (self.ops_at[1]["items"].get("properties") or {}):
                self.op_index.setdefault(self.norm(key.replace("_", " ")), []).append(key)
        self.heads = {}
        for name, path in (("operators", self.ops_at[0] if self.ops_at else None),
                           ("discounts", "premium.discounts_and_credits"),
                           ("installments", "billing.installments"),
                           ("payment_options", "billing.payment_options"),
                           ("navigation", "%s.navigation_and_use.navigational_territory" % block),
                           ("losses", "loss_history")):
            node = self._node(path) if path else None
            for a in (node or {}).get("fideon:aliases", []) or []:
                self.heads[self.norm(a)] = name
        # a unit's sub-parts: motors (a list) and trailer (an object)
        self.sub_index = {}
        if self.units_at:
            item = self.units_at[1]["items"]["properties"]
            for part in ("motors", "trailer"):
                node = item.get(part)
                if not node:
                    continue
                body = node.get("items", node)
                for a in (node.get("fideon:aliases") or []):
                    self.sub_index.setdefault("@" + self.norm(a), part)
                for key, sub in (body.get("properties") or {}).items():
                    for a in [key.replace("_", " ")] + (sub.get("fideon:aliases") or []):
                        self.sub_index.setdefault((part, self.norm(a)), key)
        self.coverage_names, self.location_values, self.form_numbers = [], set(), set()

    # ── entry point ─────────────────────────────────────────────────────────

    def read(self):
        self._title()
        self._carrier_address()
        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            head = self.heads.get(self.norm(line.text.rstrip(":"))) if len(line.cells) == 1 else None
            if i in self.skip:
                i += 1
            elif self.units_at and self._is_coverage_head(line):
                i = self._coverage_table(i)
            elif self._is_location_head(line):
                i = self._location_table(i)
            elif self._is_forms_head(line):
                i = self._forms(i)
            elif head == "operators":
                i = self._operators(i)
            elif head == "discounts":
                i = self._discounts(i)
            elif head == "installments":
                i = self._installments(i)
            elif head == "payment_options":
                i = self._payment_options(i)
            elif head == "navigation":
                i = self._navigation(i)
            elif head == "losses":
                i = self._losses(i)
            elif self.norm(line.text) in ("reason for change",) or \
                    self.norm(line.text.rstrip(":")) == "reason for change":
                i = self._changes(i)
            elif self.units_at and self._unit_line(i):
                i += 1
            elif self.units_at and self._sub_part(line, i):
                i += 1
            else:
                if self.units_at and self.norm(line.text) in self.unit_marks \
                        and self.units and self._current() and self._next_is_unit_line(i) is False:
                    self._start_unit()
                for cell in line.cells:
                    self._labelled(cell)
                i += 1
        self._footer_form_number()
        self._print_date()
        self._whole_document()
        self._printed_facts()
        for path in self.conflicts:           # set from the first unit, then contradicted
            keys = path.split(".")
            node = _get(self.gold, ".".join(keys[:-1])) if len(keys) > 1 else self.gold
            if isinstance(node, dict):
                node.pop(keys[-1], None)

        if self.operators:
            if self.none_violations is not None:
                for op in self.operators:
                    op.setdefault("no_violations_reported", yes_no(True, self.none_violations))
            _put(self.gold, self.ops_at[0], self.operators)
        if self.none_losses is not None and "loss_history_none_reported" in self.schema.leaves:
            _put(self.gold, "loss_history_none_reported", yes_no(True, self.none_losses))
        if self.discounts:
            _put(self.gold, "premium.discounts_and_credits",
                 self.discounts + (_get(self.gold, "premium.discounts_and_credits") or []))
        for n, _, cells, found in self.pages:
            for f in found:
                if f.kind == "money" and not f.blank and self.units and \
                        self.norm(f.label) in ("unit premium", "total premium for this unit"):
                    self._current().setdefault("premium", fv(f.new, as_number(f.new)))
        for u in self.units:
            self._make_model(u)
        units = [u for u in self.units if u]
        if units:
            _put(self.gold, self.units_at[0], units)
        if self.locations:
            self.gold["locations"] = self.locations
        if self.deductibles:
            self.gold["deductibles"] = self.deductibles
        return self.gold

    def repeated(self, item):
        """Is this unmapped value a location address printed again as a block?"""
        return item["kind"] in ("street", "pobox", "cityline") and \
            " ".join(str(item["value"]).lower().split()) in self.location_values

    def _use(self, f):
        if f is not None:
            self.consumed.add(id(f))

    def _node(self, path):
        """The schema node at a dotted path, or None."""
        node = {"properties": self.schema.merged["properties"]}
        defs = self.schema.merged["$defs"]
        for key in path.split("."):
            while "$ref" in node and not node["$ref"].endswith("/FieldValue"):
                node = defs[node["$ref"].split("/")[-1]]
            if node.get("type") == "array":
                node = node.get("items") or {}
            node = (node.get("properties") or {}).get(key)
            if node is None:
                return None
        return node

    def _current(self):
        if not self.units:
            self.units.append({})
            self.cur = 0
        return self.units[self.cur]

    def _start_unit(self, unit=None):
        self.units.append(unit if unit is not None else {})
        self.cur = len(self.units) - 1
        return self.units[self.cur]

    # ── fixed shapes ────────────────────────────────────────────────────────

    def _title(self):
        """The document's own title. A declarations, policy change or policy
        history title anywhere wins; "quote", "binder", "proposal" are
        taken only on the first page - a discount called "Early Quote" is
        not a title."""
        first = min(self.cells) if self.cells else None
        for strong in (True, False):
            for line in self.lines:
                if not strong and line.page != first:
                    break
                for cell in line.cells:
                    m = TITLE.search(cell.text)
                    if not m or len(cell.text.split()) > 8 or self.found_in.get(id(cell)):
                        continue
                    kind = m.group(1).lower()
                    if strong != (kind not in ("quote", "proposal", "binder")):
                        continue
                    words = cell.text.split()
                    while words and words[0].lower() in self.marks:
                        words.pop(0)              # the carrier's logo run into it
                    if not all(w[0].isupper() or not w[0].isalpha() for w in words) \
                            or cell.text.rstrip()[-1:] in ".,;:":
                        continue                  # a sentence that mentions it
                    _put(self.gold, "document.document_title_as_stated", fv(" ".join(words)))
                    kind = "declaration" if kind.startswith("declaration") else kind
                    _put(self.gold, "document.document_type", fv(m.group(1), DOC_TYPE[kind]))
                    return

    def _carrier_address(self):
        """"GLEN ALLEN, VIRGINIA" printed under the carrier's name, or "One
        Tower Square, Hartford, CT 06183" under the insurer's."""
        from .generic import INSURER_NAME
        for i, line in enumerate(self.lines):
            if not any(INSURER_NAME.search(c.text) and len(c.text.split()) <= 6
                       for c in line.cells):
                continue
            for later in self.lines[i + 1:i + 4]:
                for c in later.cells:
                    m = re.match(r"^(.+?),\s*([A-Z][A-Za-z .']+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$",
                                 c.text.strip())
                    if m and not self.found_in.get(id(c)):
                        _put(self.gold, "carrier.address.line_1", fv(m.group(1)))
                        _put(self.gold, "carrier.address.city", fv(m.group(2)))
                        _put(self.gold, "carrier.address.state", fv(m.group(3)))
                        _put(self.gold, "carrier.address.postal_code", fv(m.group(4)))
                        break
                else:
                    continue
                break
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

    def _has(self, path):
        return path in self.schema.leaves

    def _printed_facts(self):
        """Facts a page states in its own words rather than beside a label:
        the forms named in page footers, the web addresses, the renewal
        offer's dates, a change "removed from your policy", where the period
        runs, a print code, a coupon's scan line, the time a page was printed."""
        self._footer_forms()
        self._websites()
        self._renewal_dates()
        self._change_sentences()
        for line in self.lines:
            for cell in line.cells:
                m = re.search(r"(?i)\bat the (residence premises|address of the named insured)\b",
                              cell.text)
                if m and self._has("policy.policy_period_location_basis"):
                    _put(self.gold, "policy.policy_period_location_basis", fv(m.group(0)))
        for _, height, cells, found in self.pages:
            for f in found:
                if f.kind == "scanline" and not f.blank and self._has("billing.payment_coupon_scan_line"):
                    _put(self.gold, "billing.payment_coupon_scan_line", fv(f.new))
                # "9/18/26, 2:39 PM": the time printed with the print date
                if f.kind == "date" and not f.blank and self._has("document.print_time") and \
                        (_get(self.gold, "document.print_date") or {}).get("raw") == f.new:
                    m = re.match(r"\s*,?\s*(\d{1,2}:\d{2}\s?[AP]M)\b", f.cell.text[f.end:], re.I)
                    if m:
                        _put(self.gold, "document.print_time", fv(m.group(1)))
        # a print code repeated in the footer of several pages: "577/0DQD25"
        seen = {}
        for n, height, cells, _ in self.pages:
            for c in cells:
                text = c.text.strip()
                if c.rect is not None and c.rect.y0 > 0.85 * height and \
                        re.fullmatch(r"[0-9A-Z]{2,5}/[0-9A-Z]{4,10}", text) and \
                        re.search(r"[A-Z]", text) and re.search(r"\d", text):
                    seen.setdefault(text, set()).add(n)
        codes = [t for t, pages in seen.items() if len(pages) >= 2]
        if codes and self._has("document.print_code"):
            _put(self.gold, "document.print_code", fv(codes[0]))

    def _footer_forms(self):
        """"Form 6489 NY (06/21)", "PL-50776 NY (11-23)": a form printed on
        its own at a page's foot, and the policy contract a sentence names,
        join the forms list - once each."""
        if not self._has("forms_and_endorsements[].form_number"):
            return
        forms = self.gold.setdefault("forms_and_endorsements", [])
        have = {re.sub(r"\W", "", f["form_number"]["raw"]).lower() for f in forms if "form_number" in f}
        shape = re.compile(r"^(?:Form\s+)?((?:[A-Z]{1,6}-?)?\d{3,5}[A-Z]?(?: [A-Z]{2})?)\s?\((\d{2}[-/]\d{2})\)$")
        for n, height, cells, _ in self.pages:
            for c in cells:
                m = shape.match(c.text.strip())
                if not m or c.rect is None:
                    continue
                # "Form A016 (07/19)" names a form wherever a page ends its
                # text; a bare "PL-50776 NY (11-23)" only in the footer band
                if not c.text.strip().lower().startswith("form ") and c.rect.y0 < 0.8 * height:
                    continue
                key = re.sub(r"\W", "", m.group(1)).lower()
                if key in have:
                    continue
                have.add(key)
                forms.append({"form_number": fv(m.group(1)), "edition_date": fv(m.group(2))})
        contract = _get(self.gold, "policy.policy_form_number")
        if contract is not None:
            key = re.sub(r"\W", "", contract["raw"]).lower()
            if key not in have:
                item = {"form_number": copy.deepcopy(contract), "form_type": derived("Policy", contract["raw"])}
                edition = _get(self.gold, "policy.policy_form_edition")
                if edition is not None:
                    item["edition_date"] = copy.deepcopy(edition)
                forms.insert(0, item)
        if not forms:
            del self.gold["forms_and_endorsements"]

    def _websites(self):
        """A web address: the carrier's own site, or the page's own address
        when a printout carries it ("https://attachment-viewer...")."""
        site = re.compile(r"(?i)(?<![\w@./])((?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*"
                          r"\.(?:com|net|org|app|us|gov)(?:/[\w./%-]*)?)")
        for line in self.lines:
            for cell in line.cells:
                for m in site.finditer(cell.text):
                    url = m.group(1).rstrip("./")
                    if url.lower().startswith("http") and "/" in url.split("//", 1)[1]:
                        if self._has("document.source_url"):
                            _put(self.gold, "document.source_url", fv(url))
                    elif any(mark in url.lower() for mark in self.marks) and \
                            self._has("carrier.contact.website"):
                        _put(self.gold, "carrier.contact.website", fv(url))

    def _renewal_dates(self):
        """"This renewal offer is for the policy period A through B", "Your
        current policy period ends C", "Renewal Payment ... Due By: D"."""
        ro = "document_type_detail.renewal_offer."
        if not self._has(ro + "renewal_effective_date"):
            return
        dates = []                                 # (page, y, x, new, prefix) in reading order
        for line in self.lines:
            text = ""
            for cell in line.cells:
                for f in sorted(self.found_in.get(id(cell), []), key=lambda g: g.start):
                    if f.kind != "date" or f.blank:
                        continue
                    new = f.new
                    if f.part == 0:                # a date wrapped onto the next line
                        tail = next((g for fs in self.found_in.values() for g in fs
                                     if g.part == 1 and g.key == f.key), None)
                        new = f.new + ", " + tail.new if tail is not None else None
                    elif f.part == 1:
                        continue
                    if new:
                        dates.append((line, new, text + cell.text[:f.start]))
                text += cell.text + " "
        offer = False
        for k, (line, new, before) in enumerate(dates):
            b = before.lower()
            if re.search(r"renewal offer is for the policy period\s*$", b):
                _put(self.gold, ro + "renewal_effective_date", self.field("date", new))
                offer = True
                nxt = dates[k + 1] if k + 1 < len(dates) else None
                if nxt is not None and re.search(r"\b(?:through|to|-)\s*$", nxt[2].lower()):
                    _put(self.gold, ro + "renewal_expiration_date", self.field("date", nxt[1]))
            elif re.search(r"current policy (?:period ends|will expire on|expires on)\s*$", b) and \
                    self._has(ro + "expiring_policy_expiration_date"):
                _put(self.gold, ro + "expiring_policy_expiration_date", self.field("date", new))
            elif re.search(r"due by:?\s*$", b) and "renewal payment" in b:
                _put(self.gold, ro + "payment_due_date", self.field("date", new))
        issued = _get(self.gold, "document.issue_date")
        if offer and issued is not None:
            _put(self.gold, ro + "offer_issue_date", copy.deepcopy(issued))

    def _change_sentences(self):
        """"The Automatic Card Payments (ACP) discount has been removed from
        your policy." - a change the document states as a sentence."""
        path = "document_type_detail.policy_change.changes[].change_description"
        if not self._has(path):
            return
        for k, line in enumerate(self.lines):
            text = re.sub(r"^\s*Changes?:\s*", "", line.text)
            if not re.search(r"(?i)\bhas been (?:removed from|added to)(?: your)?$|"
                             r"\bhas been (?:removed from|added to) your policy\.", text):
                continue
            nxt = self.lines[k + 1] if k + 1 < len(self.lines) else None
            if not text.rstrip().endswith(".") and nxt is not None and nxt.page == line.page:
                text = text.rstrip() + " " + nxt.text.strip()
            m = re.search(r"([A-Z][^.]*?\bhas been (?:removed from|added to) your policy\.)", text)
            if m:
                changes = self.gold.setdefault("document_type_detail", {}) \
                    .setdefault("policy_change", {}).setdefault("changes", [])
                if not any(c.get("change_description", {}).get("raw") == m.group(1) for c in changes):
                    changes.append({"change_description": fv(m.group(1))})

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
        """The form a document is printed on: the form number in its page
        footers - the one most pages carry, not an insert's own ("PL-50957"
        on a two-page summary before four pages of "PL-50776 NY")."""
        seen = {}                                   # value -> pages, in page order
        for n, height, cells, _ in self.pages:
            for c in cells:
                text = c.text.strip()
                if c.rect is None or c.rect.y0 <= 0.9 * height or text in self.form_numbers:
                    continue
                if re.fullmatch(r"[A-Z]{2,6}[0-9A-Z]{2,6}-\d{4}", text):
                    value = fv(self._fix_form(text), evidence=text)
                elif FORM_REF.fullmatch(text) or re.fullmatch(
                        r"Form\s+([0-9A-Z-]+(?:\s[A-Z]{2})?)\s*\((\d{2}/\d{2})\)", text):
                    value = fv(text)                # "PL-50776 NY (11-23)", "Form 6489 NY (06/21)"
                else:
                    continue
                seen.setdefault(value["raw"], [value, set()])[1].add(n)
        if seen:
            value, _ = max(seen.values(), key=lambda v: len(v[1]))   # first of the most printed
            _put(self.gold, "document.form_number", value)

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
        if self.units and top in self._current():
            have = self._current()[top]
            if isinstance(value, dict) and isinstance(have, dict) and not is_field(have) \
                    and not set(value) & set(have):
                return self._current()
            self._start_unit()
        return self._current()

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
                if self._repeated_on_row(cell, label):
                    continue
                value = self._address(f) if rels[0].endswith("address") else \
                    (self.field(f.kind, f.new) if f.kind in ("date", "money") else fv(f.new))
                if f.kind in ("id", "digits") and self._held_by_unit(rels[0], value):
                    self._use(f)                   # a VIN printed again, in a discount table
                    continue
                if value:
                    self._unit_set(rels[0], value)
                    self._use(f)
                continue
            if f.kind == "date" and "transaction" in label and "effective" in label:
                _put(self.gold, "document.transaction_effective_date", self.field("date", f.new))
            if f.kind == "date" and "transaction" in label:
                after = cell.text[f.end:].split()
                word = after[0] if after else ""
                if not word:
                    nxt = self._right_of(cell)
                    word = nxt.text.strip() if nxt is not None else ""
                if word.lower() in TRANSACTION_WORDS:
                    _put(self.gold, "document.transaction_type", fv(word, word.title()))
            if f.kind == "date" and scalar == "signature.signature_date":
                after = " ".join(sg.text for sg in segments(cell, self.found_in.get(id(cell), []))
                                 if sg.start >= f.end)
                m = re.match(r"\s*at\s+([A-Z][A-Za-z.' -]*?,\s*[A-Z]{2})\b", after)
                if m:
                    _put(self.gold, "signature.signature_location", fv(m.group(1)))

        m = TIME.search(cell.text)
        if m and not found:
            _put(self.gold, "policy.effective_time", fv(m.group(1)))
            _put(self.gold, "policy.expiration_time", fv(m.group(1)))
            _put(self.gold, "policy.time_zone", fv(m.group(2).strip()))
        m = EXPIRES_AT.search(cell.text)
        if m and found:
            when = m.group(1)
            if not re.search(r"[AaPp]\.?\s?[Mm]", when) and not cell.text[m.end():].strip():
                # "... at 12:01" | "A.M. STANDARD TIME ...": the time wraps
                row = next((k for k, l in enumerate(self.lines) if cell in l.cells), None)
                nxt = self.lines[row + 1] if row is not None and row + 1 < len(self.lines) else None
                ampm = re.match(r"\s*([AaPp]\.?\s?[Mm]\.?)", nxt.text) if nxt is not None else None
                when = when + " " + ampm.group(1) if ampm else None
            if when:
                _put(self.gold, "policy.expiration_time", fv(when))
        m = EFFECTIVE_AT.search(cell.text)
        if m and found:
            _put(self.gold, "policy.effective_time", fv(m.group(1)))
            if m.group(2):
                _put(self.gold, "policy.time_zone", fv(m.group(2).strip()))
        for f in found:                            # "Premium change: $4.00"
            if f.kind == "money" and self.norm(f.label) == "premium change":
                self._premium_change(f, "increases")
        m = PREMIUM_CHANGE.search(cell.text)
        if m:
            f = next((g for g in found if g.kind == "money"), None)
            if f is not None:
                self._premium_change(f, m.group(1).lower())
        m = re.search(r"(?i)\bsubsidiary(?: or affiliate)? of (.+?)\.?$", cell.text)
        if m and not found:
            _put(self.gold, "carrier.group_name", fv(m.group(1).strip()))
        m = re.search(r"(?i)\bpolicy contract is form ([0-9A-Z-]+(?: [A-Z]{2})?) \((\d{2}/\d{2})\)",
                      cell.text)
        if m:
            _put(self.gold, "policy.policy_form_number", fv(m.group(1)))
            _put(self.gold, "policy.policy_form_edition", fv(m.group(2)))
        m = re.search(r"(?i)\bpayable to ([A-Z][\w .&'-]+?(?: Co| Company| Inc| LLC| Corp)\.?)(?=\s|$)",
                      cell.text)
        if m:
            _put(self.gold, "billing.payable_to", fv(m.group(1).rstrip(".")))
            self._remittance(cell)
        m = re.search(r"(?i)\binstallment fee of\s*(\S+)", cell.text)
        if m:
            f = next((g for g in found if g.kind == "money"), None)
            if f is not None:
                self._use(f)
                self.fee = fv(f.new, as_number(f.new))

        # plain text beside its label: "TERM: 12 Months", or "Year:" | "1999"
        if self.found_in.get(id(cell)):
            return
        whole = self.index.get(self.norm(cell.text))
        if whole == "document.copy_type":          # "Insured Copy" names itself
            _put(self.gold, whole, fv(cell.text.strip()))
            return
        m = re.match(r"^\s*([A-Za-z][A-Za-z /&#().'-]{1,40}?)\s*:\s*(\S.*)$", cell.text)
        vcell = cell
        if m and ":" not in m.group(2):
            label, value = m.group(1), m.group(2).strip()
        elif cell.text.count(":") == 1 and cell.text.rstrip().endswith(":"):
            nxt = self._right_of(cell) or self._below_of(cell)
            if nxt is None or ":" in nxt.text or self.found_in.get(id(nxt)) or \
                    not self._value_like(nxt.text):
                return
            label, value, vcell = cell.text.rstrip()[:-1], nxt.text.strip(), nxt
        elif whole and not NOT_TEXT.search(whole.rsplit(".", 1)[-1]) \
                and not cell.text.strip()[:1].islower():   # "occupation." wrapped out of a sentence
            nxt = self._right_of(cell)             # "Your Insurer  |  TRAVCO INSURANCE COMPANY"
            if nxt is None or ":" in nxt.text or self.found_in.get(id(nxt)) or \
                    not self._value_like(nxt.text):
                return
            label, value, vcell = cell.text, nxt.text.strip(), nxt
        else:
            return
        value = self._continued(vcell, value)
        if not value or len(value.split()) > 15:
            return
        label = self.norm(label)
        rels = [r for r in self.unit_index.get(label, []) if not NOT_TEXT.search(r.rsplit(".", 1)[-1])]
        if rels and self._repeated_on_row(cell, label):
            return
        if rels:
            self._unit_set(rels[0], self._plain(rels[0], value))
            season = re.match(r"(?i)(summer|winter|spring|fall|autumn)\b", label)
            if season and rels[0].startswith("moorage") and self.units_at:
                self._current().setdefault("moorage_season", derived(season.group(1).title(),
                                                                     season.group(1)))
            if rels[0] == "unit_description":
                year = re.match(r"(1[89]|20)\d\d\b", value)
                if year:
                    self._current().setdefault("year", derived(year.group(0), year.group(0),
                                                               int(year.group(0))))
            return
        path = self.index.get(label)
        if path and not NOT_TEXT.search(path.rsplit(".", 1)[-1]):
            _put(self.gold, path, self._plain(path, value))
            return
        # a label of a unit's motor or trailer with no context: "Engine Type"
        for part in ("motors", "trailer"):
            key = self.sub_index.get((part, label))
            if key and self.units_at and key not in ("year", "make", "model"):
                self._sub_set(part, key, self._plain(key, value), new=False)
                return

    def _is_label(self, text):
        """Printed text that is itself a label: in a grid of labels over their
        values, the cell beside "Buyout Indicator" is "Channel Of Process"."""
        n = self.norm(text.strip().rstrip(":"))
        return bool(n) and (n in self.index or n in self.unit_index or n in self.op_index
                            or n in self.heads)

    def _value_like(self, text):
        return bool(re.search(r"[A-Za-z0-9]", text)) and not self._is_label(text)

    def _held_by_unit(self, rel, value):
        """An identifier some unit already has: the same unit, printed again."""
        return "." not in rel and is_field(value) and \
            any(is_field(u.get(rel)) and u[rel]["raw"] == value["raw"] for u in self.units)

    def _repeated_on_row(self, cell, label):
        """The same label printed again along the row - one column per unit,
        which this reader cannot tell apart, so it does not guess."""
        return sum(1 for o in self.cells[cell.page] if o.row == cell.row and ":" in o.text
                   and self.norm(o.text.split(":", 1)[0]) == label) >= 2

    def _below_of(self, cell):
        """The cell printed directly under ``cell``, left edges aligned."""
        r = cell.rect
        best = None
        for o in self.cells[cell.page]:
            q = o.rect
            if o is cell or q is None or q.y0 < r.y1 - 0.3 * r.height or q.y0 - r.y1 > 1.6 * r.height:
                continue
            if abs(q.x0 - r.x0) > 6:
                continue
            if best is None or q.y0 < best.rect.y0:
                best = o
        return best

    def _continued(self, cell, value):
        """A value that runs onto the next line at the same indent."""
        for _ in range(3):
            nxt = self._below_of(cell)
            if nxt is None or ":" in nxt.text or self.found_in.get(id(nxt)) or \
                    value.rstrip().endswith("."):
                break
            if len(nxt.text.split()) > 12 or not nxt.text[:1].islower():
                break
            value, cell = value + " " + nxt.text.strip(), nxt
        return value

    def _premium_change(self, f, direction):
        self._use(f)
        amount = fv(f.new, as_number(f.new))
        key = "premium.return_premium" if direction == "decreases" else "premium.additional_premium"
        _put(self.gold, key, amount)
        signed = copy.deepcopy(amount)
        if direction == "decreases" and signed["parsed"] is not None:
            signed["parsed"] = -signed["parsed"]
        detail = "document_type_detail.policy_change"
        if detail + ".net_change_amount" in self.schema.leaves:
            _put(self.gold, detail + ".net_change_amount", signed)
            _put(self.gold, detail + ".additional_or_return_premium",
                 derived("Return" if direction == "decreases" else "Additional", f.new))

    def _remittance(self, cell):
        """The coupon's address, printed under the carrier's name after the
        payee sentence: "PROGRESSIVE / PO BOX 7247-0308 / PHILADELPHIA PA ..."."""
        lines = [l for l in self.lines if l.page == cell.page and l.y > cell.rect.y1]
        for k, line in enumerate(lines[:8]):
            for c in line.cells:
                pob = re.match(r"(?i)^(P\.?\s?O\.?\s?Box\s+[\w-]+)$", c.text.strip())
                if pob and not self.found_in.get(id(c)):
                    _put(self.gold, "billing.remittance_address.line_1", fv(pob.group(1)))
                    for later in lines[k + 1:k + 3]:
                        for d in later.cells:
                            city = re.match(r"^([A-Z][A-Za-z .']+?),?\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$",
                                            d.text.strip())
                            if city and not self.found_in.get(id(d)):
                                _put(self.gold, "billing.remittance_address.city", fv(city.group(1)))
                                _put(self.gold, "billing.remittance_address.state", fv(city.group(2)))
                                _put(self.gold, "billing.remittance_address.postal_code",
                                     fv(city.group(3)))
                                return
                    return

    # ── a unit's own lines ──────────────────────────────────────────────────

    def _make_model(self, unit):
        """"1914 FAY & BOWEN FANTAIL LAUNCH": the builder is the first word,
        with any "&" partner; "2024 Viaggio by Misty Harbor 20 Lago Series":
        the builder is named after "by". Which words are the make is a
        reading, not a label, so it is marked derived with a lower score."""
        desc = unit.get("unit_description")
        if desc is None or "make" in unit:
            return
        m = re.match(r"^(?:19|20)\d\d\s+(.+)$", desc["raw"])
        if not m:
            return
        rest = m.group(1).strip()
        by = re.match(r"^(.+?)\s+by\s+([A-Z][A-Za-z.&' -]+?)(?:\s+(\d.*))?$", rest)
        if by:
            make, model = by.group(2).strip(), (by.group(1) + " " + (by.group(3) or "")).strip()
        else:
            words = rest.split()
            # a model number ends the make: "Correct Craft/Nautique 200 Sport
            # Nautique", "Sea Ray 240 Sundancer"
            num = next((k for k, w in enumerate(words[:4]) if k and re.match(r"\d", w)), None)
            if num is not None:
                k = num
            else:
                k = 1
                while k + 1 < len(words) and words[k] in ("&", "and", "-"):
                    k += 2                       # "FAY & BOWEN"
            make, model = " ".join(words[:k]), " ".join(words[k:])
        if make:
            unit["make"] = derived(make, desc["raw"], score=0.7)
        if model:
            unit.setdefault("model", derived(model, desc["raw"], score=0.7))

    def _next_is_unit_line(self, i):
        nxt = self.lines[i + 1] if i + 1 < len(self.lines) else None
        return nxt is not None and bool(UNIT_LINE.match(nxt.text.strip()))

    def _unit_line(self, i):
        """"2024 Viaggio by Misty Harbor 20 Lago Series" under a unit heading,
        or over the unit's own fields; "... (continued)" returns to a unit."""
        line = self.lines[i]
        if len(line.cells) != 1 or self.found_in.get(id(line.cells[0])) or ":" in line.text:
            return False
        m = UNIT_LINE.match(line.text.strip())
        if not m:
            return False
        before = self.lines[i - 1] if i else None
        after = self.lines[i + 1] if i + 1 < len(self.lines) else None
        under_head = before is not None and self.norm(before.text.rstrip(":")) in self.unit_marks
        over_fields = after is not None and any(
            self.norm(re.split(r":", c.text)[0]) in self.unit_index for c in after.cells)
        desc = (m.group(1) + " " + m.group(2)).strip()
        known = self._unit_named(desc)
        if not (under_head or over_fields or m.group(3) or known is not None):
            return False
        if known is not None:
            self.cur = self.units.index(known)
            return True
        unit = self._current() if self.units and not self._current().get("unit_description") \
            and not self._current().get("coverages") else self._start_unit()
        unit["unit_description"] = fv(desc)
        unit.setdefault("year", fv(m.group(1), int(m.group(1))))
        return True

    def _sub_set(self, part, key, value, new):
        unit = self._current()
        if part == "motors":
            motors = unit.setdefault("motors", [])
            if new or not motors:
                motors.append({})
            motors[-1].setdefault(key, value)
        else:
            unit.setdefault("trailer", {}).setdefault(key, value)

    def _sub_part(self, line, i):
        """A motor's or trailer's line: "Outboard #1 | Year: 2024 | Make:
        Mercury", "Trailer information Year: 2024 | Make: Venture", or
        "Trailer Details:" over "2025 VENTURE"."""
        first = line.cells[0].text.strip()
        part = None
        for phrase_len in (3, 2, 1):
            words = first.split()
            lead = self.norm(" ".join(words[:phrase_len]))
            if ("@" + lead) in self.sub_index:
                part = self.sub_index["@" + lead]
                rest = " ".join(words[phrase_len:])
                break
        if part is None:
            return False
        if part == "motors" and ":" in first and "#" not in first:
            return False                           # "Engine Type: Inboard" is a field
        if part == "motors":
            self._sub_set("motors", "motor_type", fv(first.split()[0]), new=True)
            number = re.search(r"#\s*(\d+)", first)
            if number:
                self._sub_set("motors", "motor_number", fv(number.group(1)), new=False)
            rest = re.sub(r"^#?\s*\d+\b\s*", "", rest)
        pieces = ([rest] if rest else []) + [c.text for c in line.cells[1:]]
        got = False
        for piece in pieces:
            m = re.match(r"^\s*([A-Za-z][A-Za-z /#.'-]{0,30}?)\s*:\s*(\S.*)$", piece)
            if not m:
                continue
            key = self.sub_index.get((part, self.norm(m.group(1))))
            if key:
                self._sub_set(part, key, self._plain(key, m.group(2).strip()), new=False)
                got = True
        if part == "trailer" and not got and first.rstrip().endswith(":") and i + 1 < len(self.lines):
            m = UNIT_LINE.match(self.lines[i + 1].text.strip())
            if m:                                   # "Trailer Details:" / "2025 VENTURE"
                self._sub_set("trailer", "year", fv(m.group(1), int(m.group(1))), new=False)
                self._sub_set("trailer", "make", fv(m.group(2).strip()), new=False)
                self.skip.add(i + 1)
                got = True
        return got or part == "motors"

    # ── sections ────────────────────────────────────────────────────────────

    def _is_head(self, line):
        """Does this line open a section some reader here knows?"""
        if len(line.cells) != 1:
            return False
        n = self.norm(line.text.rstrip(":"))
        return n in self.heads or self._is_forms_head(line) or n in self.unit_marks \
            or n == "reason for change"

    def _section(self, i, gap=3.2):
        """The lines of the section headed by line ``i``: until a wide gap, a
        page change, or a line printed left of the section's own text."""
        head = self.lines[i]
        out, prev, j, left = [], head.y, i + 1, None
        while j < len(self.lines) and self.lines[j].page == head.page:
            line = self.lines[j]
            if line.y - prev > gap * max(line.height, head.height) or \
                    line.y > 0.92 * self.heights.get(line.page, 1e9) or self._is_head(line):
                break
            x0 = line.cells[0].rect.x0
            if left is None:
                left = x0
            elif x0 < left - 8:
                break
            out.append(line)
            prev, j = line.y, j + 1
        return out, j

    def _looks_named(self, cell):
        from .generic import _looks_like_name
        f = [g for g in self.found_in.get(id(cell), []) if not g.blank]
        if f and f[0].kind == "person" and f[0].start == 0:
            return f[0].new
        return None if f or not _looks_like_name(cell.text) else cell.text.strip()

    def _operators(self, i):
        lines, j = self._section(i)
        current = None
        for line in lines:
            if len(line.cells) == 1:
                name = self._looks_named(line.cells[0])
                if name and not self._is_label(name):
                    current = {"name": fv(name)}
                    self.operators.append(current)
                    continue
            if current is None:
                continue
            for cell in line.cells:
                m = re.match(r"^\s*([A-Za-z][A-Za-z /#().'-]{0,40}?)\s*:\s*(\S.*)$", cell.text)
                if not m:
                    continue
                keys = self.op_index.get(self.norm(m.group(1)))
                if keys:
                    value = m.group(2).strip()
                    current.setdefault(keys[0], fv(value, int(value)) if keys[0] == "age"
                                       and value.isdigit() else fv(value))
        return j

    def _discounts(self, i):
        """"Policy | 876380454 | Home Owner, Multi-Policy and Paid in Full",
        "Vehicle | 2025 Starcraft | Original Owner", or a row of names under
        "The following discounts reduced your premium:"."""
        lines, j = self._section(i)
        scope, skip = None, set()
        for k, line in enumerate(lines):
            if k in skip:
                continue
            texts = [c.text.strip() for c in line.cells]
            if len(texts) == 1 and self.norm(texts[0]) in ("policy", "vehicle", "watercraft", "boat"):
                scope = texts[0]
                continue
            if len(texts) == 1 and texts[0].endswith(":"):
                continue
            applies = line.cells[0]
            f = [g for g in self.found_in.get(id(applies), []) if not g.blank]
            if len(texts) >= 2 and scope and re.search(r"[A-Za-z]", texts[-1]) and \
                    (f or UNIT_LINE.match(applies.text.strip())):
                target = f[0].new if f else applies.text.strip()
                nxt = lines[k + 1] if k + 1 < len(lines) else None
                if not f and nxt is not None and len(nxt.cells) == 1 and ":" not in nxt.text \
                        and abs(nxt.cells[0].rect.x0 - applies.rect.x0) < 3 \
                        and self.norm(nxt.text) not in ("policy", "vehicle", "watercraft", "boat") \
                        and nxt.y - line.y < 1.8 * line.height:
                    target += " " + nxt.text.strip()          # the name wraps onto the next line
                    skip.add(k + 1)
                for name in re.split(r",\s*|\s+and\s+", texts[-1]):
                    if name.strip():
                        self.discounts.append({"description": fv(name.strip()),
                                               "applies_to": fv(target),
                                               "is_applied": yes_no(True, name.strip())})
                continue
            if len(texts) >= 2 and all(len(x.split()) <= 4 and not re.search(r"\d", x)
                                       for x in texts):
                for name in texts:
                    self.discounts.append({"description": fv(name),
                                           "is_applied": yes_no(True, name)})
                continue
            if scope is None and len(texts) == 1 and len(texts[0].split()) <= 4 \
                    and not re.search(r"\d", texts[0]):
                self.discounts.append({"description": fv(texts[0]),
                                       "is_applied": yes_no(True, texts[0])})
        return j

    def _installments(self, i):
        lines, j = self._section(i, gap=4)
        rows = []
        for line in lines:
            pending = None                         # a date cell, its amount to its right
            for cell in line.cells:
                found = [g for g in self.found_in.get(id(cell), []) if not g.blank]
                money = [g for g in found if g.kind == "money"]
                dates = [g for g in found if g.kind == "date"] or \
                    ([pending] if pending is not None else [])
                pending = None
                if re.search(r"(?i)installment fee of", cell.text):
                    if money:                      # "**An installment fee of $5.00 ..."
                        self._use(money[0])
                        self.fee = fv(money[0].new, as_number(money[0].new))
                    continue
                if not money:
                    if dates and cell.text.strip() == dates[0].text.strip():
                        pending = dates[0]
                    continue
                row = {"installment_number": derived(str(len(rows) + 1), parsed=len(rows) + 1),
                       "amount": fv(money[0].new, as_number(money[0].new))}
                self._use(money[0])
                if dates:
                    row["due_date"] = self.field("date", dates[0].new)
                    self._use(dates[0])
                rows.append(row)
        # a schedule set in two columns reads across: Jan, Mar, Feb, Apr
        if rows and all(as_date(r.get("due_date", {}).get("parsed")) for r in rows):
            rows.sort(key=lambda r: as_date(r["due_date"]["parsed"]))
            for n, r in enumerate(rows, 1):
                r["installment_number"] = derived(str(n), parsed=n)
        if rows:
            self.gold.setdefault("billing", {})["installments"] = rows
        return j

    def _payment_options(self, i):
        """"PAY IN FULL | PAY IN INSTALLMENTS" over "$242.00 Total Cost |
        $284.00 Total Cost" and "Includes savings of $22.00": each figure
        belongs to the plan printed over its column."""
        lines, j = self._section(i, gap=3.2)
        plans = []
        for line in lines:
            texts = [c.text.strip() for c in line.cells]
            if not plans and len(texts) >= 2 and all(re.match(r"(?i)pay\b", x) for x in texts):
                plans = [{"x": c.rect.x0, "item": {"plan_name": fv(c.text.strip())}}
                         for c in line.cells]
                continue
            if not plans:
                continue
            for cell in line.cells:
                money = [g for g in self.found_in.get(id(cell), []) if g.kind == "money" and not g.blank]
                if not money:
                    continue
                plan = min(plans, key=lambda p: abs(p["x"] - cell.rect.x0))["item"]
                key = "savings" if re.search(r"(?i)saving", cell.text) else \
                    "total_cost" if re.search(r"(?i)total cost", cell.text) else None
                if key:
                    plan.setdefault(key, fv(money[0].new, as_number(money[0].new)))
                    self._use(money[0])
        if plans:
            _put(self.gold, "billing.payment_options", [p["item"] for p in plans])
        return j

    def _navigation(self, i):
        lines, j = self._section(i, gap=2.6)
        text = " ".join(l.text for l in lines if len(l.text.split()) > 2)
        for sentence in re.split(r"(?<=\.)\s+", text):
            if re.search(r"(?i)\bwaters\b|nautical miles|offshore", sentence) and \
                    not re.match(r"(?i)it is hereby", sentence):
                _put(self.gold, self.units_at[0].split(".")[0] + ".navigation_and_use.navigational_territory",
                     fv(sentence.strip()))
                break
        m = SEASON.search(text)
        block = self.units_at[0].split(".")[0] if self.units_at else None
        if m and block and "%s.navigation_and_use.seasonal_restrictions[].area" % block in self.schema.leaves:
            _put(self.gold, block + ".navigation_and_use.seasonal_restrictions",
                 [{"area": fv(m.group(1)),
                   "start": fv(m.group(2), evidence="between " + m.group(2)),
                   "end": fv(m.group(3), evidence="and " + m.group(3))}])
        return j

    def _losses(self, i):
        lines, j = self._section(i, gap=4)
        topic = None
        for line in lines:
            low = line.text.lower()
            if "violation" in low and len(low.split()) > 3:
                topic = "violations"
            elif "loss" in low and len(low.split()) > 3:
                topic = "losses"
            elif self.norm(line.text) == "none" and topic:
                if topic == "violations":
                    self.none_violations = line.text.strip()
                else:
                    self.none_losses = line.text.strip()
        return j

    def _changes(self, i):
        """"Reason For Change:" over a list in one or two columns, entries
        sharing their first word ("Removed ...") and wrapping at the same
        indent."""
        lines, j = self._section(i, gap=2.6)
        verb, entries, open_in, end = None, [], {}, j
        for k, line in enumerate(lines):
            took = False
            for cell in line.cells:
                text = cell.text.strip()
                words = text.split()
                col = round(cell.rect.x0 / 20)
                if verb is None:
                    verb = words[0]
                if words and words[0] == verb:
                    entries.append(text)
                    open_in[col] = len(entries) - 1
                    took = True
                elif col in open_in and len(words) <= 6 and not text.endswith("."):
                    entries[open_in[col]] += " " + text   # wrapped at the same indent
                    took = True
            if not took:
                end = i + 1 + k                        # the paragraph after the list
                break
        j = min(j, end)
        # interleave the columns back into reading order
        if entries:
            _put(self.gold, "document.transaction_reason", fv("; ".join(entries),
                                                              evidence=entries[0]))
            detail = "document_type_detail.policy_change.changes[].change_description"
            if detail in self.schema.leaves:
                _put(self.gold, "document_type_detail.policy_change.changes",
                     [{"change_description": fv(e)} for e in entries])
        return j

    def _whole_document(self):
        """What a sentence says anywhere: the renewal title of a coverage
        summary, the phone numbers placed by what is printed around them."""
        first = min(self.cells) if self.cells else None
        joined = " ".join(l.text for l in self.lines if l.page == first)
        # a right-hand column can be read between the two lines of the title:
        # "This is your Renewal" | "1- 845-555-0166" | "Declarations Page"
        m = re.search(r"\bThis is your ((?:revised )?(Renewal|New Business|Policy Change)?)\s*"
                      r"(?:[^.]{0,40}?\s)?(Declarations Page)", joined, re.I)
        if m and _get(self.gold, "document.document_title_as_stated") is None:
            title = (m.group(1) + " " + m.group(3)).strip()
            _put(self.gold, "document.document_title_as_stated", fv(title, evidence=m.group(3)))
            _put(self.gold, "document.document_type", fv(m.group(3), "Declaration"))
            if m.group(2):
                _put(self.gold, "document.transaction_type", fv(m.group(2), m.group(2).title()))
            if m.group(2) and m.group(2).lower() == "renewal" and "policy.is_renewal" in self.schema.leaves:
                # "This is your Renewal Declarations Page" says so; it prints no Yes
                _put(self.gold, "policy.is_renewal", derived("Yes", m.group(2)))
        dtype = (_get(self.gold, "document.document_type") or {}).get("parsed")
        if dtype == "Policy Change":
            _put(self.gold, "document.transaction_type",
                 derived("Policy Change", (_get(self.gold, "document.document_type") or {}).get("raw")))
        if getattr(self, "fee", None) and _get(self.gold, "billing.installments"):
            for row in self.gold["billing"]["installments"]:
                row.setdefault("installment_fee", copy.deepcopy(self.fee))
        self._phones()
        # "use product code BY2", and "This is not a bill. You will be billed
        # separately ..." - wherever they are printed, in a section or not
        for line in self.lines:
            for cell in line.cells:
                m = re.search(r"(?i)\bproduct code ([A-Z0-9]{2,8})\b", cell.text)
                if m and "policy.product_code" in self.schema.leaves:
                    _put(self.gold, "policy.product_code", fv(m.group(1)))
                m = re.match(r"\s*(This is not a bill\.(?:\s+[^.]{0,80}\.)?)", cell.text, re.I)
                if m and "billing.billing_note" in self.schema.leaves:
                    _put(self.gold, "billing.billing_note", fv(m.group(1)))
        from .generic import INSURER_NAME
        for n, _, cells, found in self.pages:
            for f in found:
                if f.kind == "date" and not f.blank and id(f) not in self.consumed \
                        and INSURER_NAME.search(f.label or "") and len(f.label.split()) <= 6:
                    _put(self.gold, "document.issue_date", self.field("date", f.new))
                    self._use(f)
                if f.kind == "money" and not f.blank and id(f) not in self.consumed and \
                        re.search(r"(?i)policy premium excluding\b.*\bis\s*$", f.cell.text[:f.start]):
                    leaf = "document_type_detail.renewal_offer.renewal_premium"
                    if leaf in self.schema.leaves:
                        _put(self.gold, leaf, fv(f.new, as_number(f.new)))
                        self._use(f)

    def _phones(self):
        """A phone number with no label of its own, placed by the words
        printed with it: "To report a claim." under it, "Your Agency" over it,
        "(F)" before it."""
        for n, _, cells, found in self.pages:
            lines = [l for l in self.lines if l.page == n]
            for f in found:
                if f.kind != "phone" or f.blank or id(f) in self.consumed:
                    continue
                if self.match(self.norm(f.label), "phone", self.index):
                    continue
                fax = re.search(r"\(f\)|\bfax\b", f.cell.text[max(0, f.start - 8):f.start], re.I)
                k = next((k for k, l in enumerate(lines) if f.cell in l.cells), None)
                if k is None:
                    continue
                r = f.cell.rect
                near = " ".join(c.text for l in lines[k + 1:k + 3] for c in l.cells
                                if c.rect.x1 > r.x0 - 20 and c.rect.x0 < r.x1 + 150)
                above = " ".join(l.text for l in lines[max(0, k - 7):k])
                if re.search(r"(?i)report a claim|claim service", near):
                    path = "claim_reporting.claims_phone"
                elif re.search(r"(?i)\bagent\b|\bagency\b", near) or re.search(r"(?i)your agency", above):
                    path = "producer.contact." + ("fax" if fax else "phone")
                else:
                    continue
                if _get(self.gold, path) is None:
                    _put(self.gold, path, fv(f.new))
                    self._use(f)

    # ── coverage tables ─────────────────────────────────────────────────────

    def _is_coverage_head(self, line):
        cols = _columns(line, COVERAGE_HEAD)
        if len(line.segs) > 10 or "premium" not in cols or \
                not ("limit" in cols or "deductible" in cols):
            return False
        # a heading with no "Coverage" word leaves the name column to its left
        return "name" in cols or min(s.rect.x0 for s in line.segs) > 150

    def _coverage_table(self, i):
        """A coverage schedule. Beyond one row per coverage it reads rows whose
        name wraps onto a second line, a group heading with its sub-rows
        ("Commercial Towing ..." / "Services while afloat"), sub-lines that
        qualify a limit ("Amount of insurance for any one event", "Aggregate
        ..."), a row whose limit is printed on the next, indented line, notes
        ("Includes Fuel Spill Liability"), a list of coverages included with
        others, total and discount rows, and an endorsement schedule."""
        head = self.lines[i]
        cols = _columns(head, COVERAGE_HEAD)
        forms = "name" in cols and re.match(r"(?i)endorsement", cols["name"].orig)
        centers = {k: s.cx for k, s in cols.items() if k != "name"}
        value_left = min(s.rect.x0 for k, s in cols.items() if k != "name") - 25
        unit = self._current()
        self.ded_type = None
        above = self.lines[i - 1] if i and self.lines[i - 1].page == head.page else None
        if above is not None and "deductible" in cols and \
                head.y - above.y < 1.8 * max(head.height, above.height):
            d = cols["deductible"]
            for s in above.segs:
                if s.found is None and s.rect.x1 > d.rect.x0 - 4 and s.rect.x0 < d.rect.x1 + 4 \
                        and re.fullmatch(r"[A-Za-z]{3,}", s.text):
                    self.ded_type = fv(s.text, s.text.title())
        prev, j = head.y, i + 1
        name_x, last, pending, included = None, None, None, None
        included_clean = True
        last_x = last_line = None
        while j < len(self.lines) and self.lines[j].page == head.page:
            line = self.lines[j]
            if line.y - prev > 4 * max(line.height, head.height) or self._is_coverage_head(line) \
                    or self._is_head(line):
                break
            if self.units_at and UNIT_LINE.match(line.text.strip()) and len(line.cells) == 1 \
                    and not self.found_in.get(id(line.cells[0])):
                break                              # the next unit's own line
            first = line.cells[0]
            x0 = first.rect.x0
            left = [s for s in line.segs if s.rect.x1 <= value_left]
            right = [s for s in line.segs if s.rect.x1 > value_left]
            # a long name runs on past where the value columns begin: "Total
            # 12 month policy premium if paid | in full" - words set a space
            # after it are still the name
            while left and right and right[0].found is None and not VALUE.match(right[0].text) \
                    and right[0].rect.x0 - left[-1].rect.x1 < 0.8 * line.height:
                left.append(right.pop(0))
            name = " ".join(s.text for s in left).strip()
            values = [s for s in right if s.found is not None and s.found.kind == "money"
                      or s.found is None and VALUE.match(s.text) and not _worded(s)]
            extra_segs = [s for s in right if s not in values]
            extra = " ".join(s.text for s in extra_segs).strip()
            said_name, said_extra = say(left), say(extra_segs)
            if any(s.found is not None and s.found.kind not in ("money",) and not s.found.blank
                   for s in line.segs):
                break
            if name_x is None and name:
                name_x = x0
            if name_x is not None and x0 < name_x - 8 and not values:
                break                              # an outdented heading: the next section
            if ":" in name and values and name.rstrip().endswith(":"):
                for cell in line.cells:            # "Diminishing Deductible: $0"
                    self._labelled(cell)
                prev, j = line.y, j + 1
                continue
            prev, j = line.y, j + 1

            # ── a line with nothing in the value columns ──
            if not values:
                ref = FORM_REF.search(line.text)
                if ref and last is not None:       # "See Endorsement BY-403 CW (11-23)"
                    last.setdefault("form_number", fv(_form_of(ref)))
                    last.setdefault("edition_date", fv(ref.group(3)))
                    continue
                if not name and extra and last is not None:
                    basis = last.get("limit_basis")   # "each occurrence" under a limit
                    if basis is not None:
                        basis["raw"] = basis["parsed"] = basis["raw"] + " " + extra
                        basis["_evidence"] = extra
                    continue
                if re.match(r"(?i)includes? ", name) and last is not None:
                    self._targets(unit, name.split(None, 1)[1], yes=True)
                    last.setdefault("notes", fv(name))
                    continue
                if name.endswith((":", ".")) and re.match(r"(?i)included\s*with\b", name):
                    included = name.rstrip(":.").strip()
                    # a heading a scan's layer garbled ("includedwith Comprehensaivnde
                    # Collision.") says the rows are included, not in its own words
                    included_clean = name.endswith(":")
                    continue
                if included and name_x is not None and x0 > name_x + 2:
                    item = {"coverage_name": fv(name),
                            "is_included": yes_no(True, included if included_clean else name)}
                    if included_clean:
                        item["notes"] = fv(included)
                    unit.setdefault("coverages", []).append(item)
                    self._targets(unit, name, yes=True)
                    continue
                included = None
                if pending and x0 > pending["x"] + 3:
                    pending.setdefault("desc", said_name)  # "50% of incurred cost"
                    continue
                nxt = self.lines[j] if j < len(self.lines) else None
                heads_group = nxt is not None and nxt.page == line.page and \
                    nxt.cells[0].rect.x0 > x0 + 3      # rows indented under it: a group
                leads_on = re.search(r"(?:[,\-/&]|\b(?:and|of|or|for|the))$", name, re.I)
                if last is not None and last_x is not None and abs(x0 - last_x) < 3 \
                        and line.y - last_line < 1.6 * line.height and not pending \
                        and not heads_group and not leads_on:
                    key = "form_title" if forms else "coverage_name"
                    old_name = last[key]["raw"]
                    last[key] = fv(old_name + " " + name)   # wrapped after its values
                    for d in self.deductibles:
                        if d["applies_to"]["raw"] == old_name:
                            d["applies_to"] = fv(last[key]["raw"])
                    continue
                if pending and not pending.get("item") and abs(x0 - pending["x"]) < 3 \
                        and not pending.get("desc"):
                    pending["name"] += " " + name     # a name wrapped onto a second line
                    continue
                pending = {"name": name, "x": x0}
                continue

            included = None
            vals = {}
            for s in values:
                vals.setdefault(min(centers, key=lambda k: abs(centers[k] - s.cx)), s)

            # ── rows that are totals, discounts or a unit's premium ──
            if name and not forms:
                n = self.norm(name)
                for_unit = re.match(r"(?i)total premium for (.+)$", name)
                if n == "total" or for_unit:
                    target = self._unit_named(for_unit.group(1)) if for_unit else unit
                    if target is not None and "premium" in vals:
                        target.setdefault("premium", self._amount(vals["premium"]))
                    if n == "total":
                        break
                    continue
                if re.match(r"(?i)discount", name):
                    s = vals.get("premium") or values[-1]
                    self.discounts.append({"description": fv(name), "amount": self._signed(s),
                                           "is_applied": yes_no(True, name)})
                    continue
                scalar = self.match(n, "money", self.index)
                if scalar and scalar.split(".")[0] in ("premium", "billing"):
                    s = vals.get("premium") or values[-1]
                    _put(self.gold, scalar, self._amount(s))
                    continue

            # ── a sub-row under a group heading ──
            if pending and name and x0 > pending["x"] + 3:
                if QUALIFIER.match(name) and "limit" in vals:
                    group = self._group_item(unit, pending, forms)
                    key = "aggregate_limit_amount" if re.match(r"(?i)aggregate", name) else "limit_amount"
                    group.setdefault(key, self._amount(vals["limit"]))
                    if key == "limit_amount":
                        group.setdefault("limit_basis", fv(name))
                    last = group
                    continue
                item = self._coverage(unit, name, vals, extra, forms, said_name, said_extra)
                item.setdefault("coverage_description", fv(pending["name"]))
                pending["used"] = True             # a group heading, spent on its rows
                last = item
                continue
            # a name printed on the line over its row's values - one that
            # reads on: "Coverage M - Owners, Landlords, and Tenants (OLT),"
            if pending and name and not pending.get("item") and not pending.get("desc") \
                    and not pending.get("used") and abs(x0 - pending["x"]) < 3 \
                    and re.search(r"(?:[,\-/&]|\b(?:and|of|or|for|the))$", pending["name"], re.I):
                whole = pending["name"] + " " + name
                pending = None
                last = self._coverage(unit, whole, vals, extra, forms, fv(whole), said_extra)
                last_x, last_line = x0, line.y
                continue
            held, pending = pending, None

            # ── a limit printed under its row: "Bodily Injury ... $300,000 ..." ──
            if last is not None and name and name_x is not None and x0 > name_x + 3 \
                    and "limit" in vals and "limit_amount" not in last:
                last["limit_amount"] = self._amount(vals["limit"])
                if extra:
                    last.setdefault("limit_basis", said_extra)
                last.setdefault("coverage_description", said_name)
                self._targets(unit, name, limit=last["limit_amount"])
                continue
            # ── "Purchase Price $35,000" / "Agreed Value $52,000" under a row ──
            # ── a premium or "included" set a hair below its row's name ──
            if not name and values and "limit" not in vals \
                    and ("premium" in vals or "deductible" in vals) \
                    and (last is not None or held):
                if held and not held.get("used") and not held.get("item") \
                        and not held.get("desc"):
                    # the name over it was no group heading: "Roadside Assistance"
                    last = self._coverage(unit, held["name"], {}, "", forms,
                                          fv(held["name"]), None)
                    last_x, last_line = held["x"], line.y
                for col, field in (("deductible", "deductible_amount"), ("premium", "premium")):
                    s = vals.get(col)
                    if s is None:
                        continue
                    if INCLUDED.match(s.text):
                        last.setdefault("is_included", yes_no(True, s.text.rstrip(".*")))
                    else:
                        last.setdefault(field, self._amount(s))
                continue
            if not name and last is not None and values:
                s = values[0]
                label = self.norm(extra)
                rels = [r for r in self.unit_index.get(label, []) if r.endswith(("price", "value"))]
                amount = self._amount(s)
                if rels:
                    unit.setdefault(rels[0], copy.deepcopy(amount))
                last.setdefault("limit_amount", amount)
                continue
            if not name:
                continue
            last = self._coverage(unit, name, vals, extra, forms, said_name, said_extra)
            last_x, last_line = x0, line.y
        return j

    def _group_item(self, unit, pending, forms):
        if pending.get("item") is None:
            item = {("form_title" if forms else "coverage_name"): fv(pending["name"])}
            if pending.get("desc"):
                item["coverage_description"] = pending["desc"]
            (self.gold.setdefault("forms_and_endorsements", []) if forms
             else unit.setdefault("coverages", [])).append(item)
            pending["item"] = item
            self._targets(unit, pending["name"])
        return pending["item"]

    def _signed(self, seg):
        self._use(seg.found)
        return fv(seg.text, as_number(seg.text))

    def _unit_named(self, text):
        want = self.norm(text)
        for u in self.units:
            d = u.get("unit_description")
            if d is not None and self.norm(d["raw"]).startswith(want):
                return u
        return None

    def _targets(self, unit, name, yes=False, limit=None, ded=None, text=None):
        """Fill the block's named fields a coverage row feeds: "Watercraft
        Liability" -> the liability limit, "Includes Fuel Spill Liability" ->
        fuel spill included, "Coastal Navigation 75 Nautical Miles" -> the
        navigational territory, "Trailer Deductible" -> the trailer's."""
        n = self.norm(name)
        targets = self.cov_targets.get(n) or             self.cov_targets.get(re.sub(r"\s+coverage$", "", n), [])
        for where, path in targets:
            leaf = path.rsplit(".", 1)[-1]
            if leaf.endswith("_included"):
                value = yes_no(True, name)
            elif yes:
                continue
            elif "deductible" in leaf and ded is not None:
                value = copy.deepcopy(ded)
            elif limit is not None and "deductible" not in leaf:
                value = copy.deepcopy(limit)
            elif text and not re.search(r"limit|amount|deductible|premium|value", leaf):
                value = fv(text)
            else:
                continue
            if where == "scalar":
                # a policy-wide field fed from each unit's row holds only when
                # the units agree: $3,000 on one boat and $5,000 on the next
                # says nothing about the policy as a whole
                have = _get(self.gold, path)
                if path in self.conflicts:
                    continue
                if have is not None and str(have.get("raw")) != str(value.get("raw")):
                    self.conflicts.add(path)
                    continue
            _put(self.gold if where == "scalar" else unit, path, value)

    def _amount(self, seg):
        self._use(seg.found)
        return fv(seg.text, as_number(seg.text))

    def _coverage(self, unit, printed, vals, extra="", forms=False, said=None, said_extra=None):
        name = re.sub(r"&l\b", "&I", printed)          # the OCR reads P&I as P&l
        name = re.sub(r"[\u00ae\ufffd]+$", "", name).strip()   # "Sign & Glide®"
        if name.startswith("("):                       # and can lose the P&I entirely
            name = next((n for n in self.coverage_names if n.endswith(" " + name)), name)
        key = "form_title" if forms else "coverage_name"
        item = {key: fv(name, evidence=(said or {}).get("_evidence", printed))}
        if vals.get("deductible") is not None and getattr(self, "ded_type", None) is not None \
                and not INCLUDED.match(vals["deductible"].text):
            item["deductible_type"] = copy.deepcopy(self.ded_type)
        for col, field in (("limit", "limit_amount"), ("deductible", "deductible_amount"),
                           ("premium", "premium")):
            s = vals.get(col)
            if s is None:
                continue
            if INCLUDED.match(s.text):
                item["is_included"] = yes_no(True, s.text.rstrip(".*"))
            elif re.match(r"(?i)excl", s.text):
                item["is_excluded"] = yes_no(True, s.text)
            else:
                item[field] = self._amount(s)
        # words in the limit column beside a figure qualify it; alone they
        # say how the coverage is valued or how far it reaches - words, not a
        # speck a scan's layer made letters of ("EE")
        if extra and len(re.sub(r"[^A-Za-z]", "", extra)) < 4 and not re.search(r"\d", extra):
            extra = ""
        figure = re.fullmatch(r"\$?\d{1,3}(?:,\d{3})*(?:\.\d\d)?", extra.strip()) if extra else None
        if figure and "limit_amount" not in item:
            # "1,000" in the limit area of a table's continued rows, whose
            # columns were not found again on the next page
            item["limit_amount"] = fv(figure.group(0), as_number(figure.group(0)))
            extra = ""
        if extra:
            said_extra = said_extra or fv(extra)
            if "limit_amount" in item:
                item["limit_basis"] = said_extra
                # "Agreed Value $52,000": the limit is also the unit's own value
                rels = [r for r in self.unit_index.get(self.norm(extra), [])
                        if r.endswith(("price", "value"))]
                if rels and unit is not None:
                    unit.setdefault(rels[0], copy.deepcopy(item["limit_amount"]))
            elif re.search(r"\d", extra):
                item["coverage_description"] = copy.deepcopy(said_extra)
            else:
                item["valuation_basis"] = copy.deepcopy(said_extra)
        if forms:
            unit_desc = unit.get("unit_description")
            if unit_desc is not None:
                item["applies_to"] = copy.deepcopy(unit_desc)
            item["form_type"] = derived("Endorsement", name)
            self.gold.setdefault("forms_and_endorsements", []).append(item)
            return item
        unit.setdefault("coverages", []).append(item)
        self.coverage_names.append(name)

        limit = item.get("limit_amount")
        self._targets(unit, name, limit=limit, ded=item.get("deductible_amount"),
                      text=extra if limit is None and re.search(r"\d", extra or "") else None)
        if "agreed value" in name.lower():
            unit.setdefault("total_loss_settlement_basis", derived("Agreed Value", "Agreed Value"))
        if extra and re.search(r"(?i)replacement|purchase price|agreed value|actual cash", extra):
            unit.setdefault("total_loss_settlement_basis", fv(extra))

        ded = item.get("deductible_amount")
        if ded is not None and (ded["parsed"] or 0) > 0 and \
                not any(d["amount"]["raw"] == ded["raw"] and d["applies_to"]["raw"] == name
                        for d in self.deductibles):
            self.deductibles.append({"amount": copy.deepcopy(ded),
                                     "applies_to": fv(name, evidence=printed)})
        return item

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

    def _is_forms_head(self, line):
        n = self.norm(line.text.rstrip(":"))
        return n in self.forms_heads or (len(line.cells) == 1 and len(n.split()) <= 10
                                         and re.search(r"\bforms (?:and )?endorsements\b", n))

    def _forms(self, i):
        head = self.lines[i]
        prev, j = head.y, i + 1
        forms = self.gold.setdefault("forms_and_endorsements", [])
        while j < len(self.lines) and self.lines[j].page == head.page:
            line = self.lines[j]
            if line.y - prev > 3 * max(line.height, head.height):
                break
            ref = FORM_REF.fullmatch(line.cells[-1].text.strip()) if len(line.cells) >= 2 else None
            if ref:                                # "Boat Policy  |  BY-100 CW (11-23)"
                title = " ".join(c.text for c in line.cells[:-1]).strip()
                num = _form_of(ref)
                item = {"form_number": fv(num), "edition_date": fv(ref.group(3)),
                        "form_title": fv(title), "is_included": yes_no(True, head.text)}
                if re.search(r"\bpolicy$", title, re.I):
                    item["form_type"] = derived("Policy", title)
                    _put(self.gold, "policy.policy_form_name", fv(title))
                    _put(self.gold, "policy.policy_form_number", fv(num))
                    _put(self.gold, "policy.policy_form_edition", fv(ref.group(3)))
                elif re.search(r"\bendorsement\b", title, re.I):
                    item["form_type"] = derived("Endorsement", title)
                self.form_numbers.add(line.cells[-1].text.strip())
                forms.append(item)
                prev, j = line.y, j + 1
                continue
            m = FORM_LINE.match(line.text.strip())
            if not m:
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
        a, b = as_date(eff["parsed"]), as_date(exp["parsed"])
        if a and b:
            months = (b.year - a.year) * 12 + b.month - a.month - (b.day < a.day - 1)
            if months > 0:
                policy["policy_term_months"] = derived(str(months), parsed=months)

    # a policy-wide field whose units print it differently says nothing for
    # the policy: "Personal Property $3,000" on one boat's tile, $5,000 on the next
    at = unit_list(schema)
    units = (_get(gold, at[0]) or []) if at else []
    block = gold.get(at[0].split(".")[0]) if at else None
    if isinstance(block, dict) and len(units) >= 2:
        for part in [block] + [v for v in block.values() if isinstance(v, dict) and not is_field(v)]:
            for key in [k for k, v in part.items() if is_field(v)]:
                seen = {str(u[key]["raw"]) for u in units if isinstance(u, dict) and is_field(u.get(key))}
                if len(seen) >= 2:
                    del part[key]

    # a driver or operator the page calls "Named insured" is one, though only
    # the first of them heads the mailing block
    insured = gold.get("named_insured")
    if isinstance(insured, dict) and "named_insured.additional_named_insureds[].name" in schema.leaves:
        known = {str((insured.get("primary_name") or {}).get("raw", "")).lower()}
        known |= {str(e["name"]["raw"]).lower() for e in insured.get("additional_named_insureds", [])}
        for section in gold.values():
            for people in (section.values() if isinstance(section, dict) else []):
                if not (isinstance(people, list) and people and isinstance(people[0], dict)):
                    continue
                for person in people:
                    rel, name = person.get("relationship_to_insured"), person.get("name")
                    if is_field(rel) and is_field(name) and re.fullmatch(
                            r"(?i)named insured", str(rel["raw"]).strip()) \
                            and str(name["raw"]).lower() not in known:
                        insured.setdefault("additional_named_insureds", []).append(
                            {"name": copy.deepcopy(name),
                             "entity_type": derived("Individual", name["raw"])})
                        known.add(str(name["raw"]).lower())

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
