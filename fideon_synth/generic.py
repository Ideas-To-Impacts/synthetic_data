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
   identifiers keep their shape. Amounts stay as printed: they identify
   no one, and a scaled total can never equal the sum of its rounded
   scaled parts, so scaling would break the arithmetic the gold asserts.
4. **Draw** the replacements in place and rescan the result.
5. **Label** what it can for the gold: a value's printed label ("Policy
   Number:") is matched to the canonical schema's field names and aliases.
   Only confident matches go into the schema fields; everything else that was
   changed is listed under ``fideon:unmapped`` with its label and pages, so
   the gold never asserts a field it only guessed. What is laid out rather
   than labelled - coverage and location tables, the forms list, a unit's
   details, plain text such as "TERM: 12 Months" - is read by
   :mod:`structure`.

The line of business is the source's folder name (``.../<Carrier>/<lob>/x.pdf``)
and picks the schema; the carrier is the folder above it.

Known limits, reported rather than hidden: a value the OCR misread is not
recognised and stays as printed.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import fitz

from . import overlay, pageref, prose, recover, structure
from .corpus import Built, Report
from .fields import DATE_FORMAT, NO_EVIDENCE, as_number, derived, fv, strip_evidence
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
                 "marine", "agents", "risk", "underwriters", "ins"}
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
_SUFFIX = (r"(?i:St|Street|Rd|Road|Ave|Av|Avenue|Way|Ln|Lane|Dr|Drive|Pl|Place|Ct|Court|Blvd|"
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
    # a ZIP printed apart from its town: "Garaging ZIP Code: 12543-1157",
    # or a state and ZIP on a line of their own, under a town ("NY 13331-1714")
    ("zip", re.compile(r"(?<![\w$.,/-])\d{5}-\d{4}(?![\w-])")),
    ("zip", re.compile(r"(?<=\b[A-Z]{2} )\d{5}(?![\w-])")),
    ("street", re.compile(
        r"(?<![\w/$.,-])\d{1,6}\s+(?:(?:(?-i:%s|US|SR|CR)|State\s+Route|County\s+Road|Route|Rte|Hwy)"
        r"[- ]\d{1,4}\b(?![-/])|"
        r"(?!\d)(?:[A-Za-z0-9.']+\s){0,3}(?:St|Street|Rd|Road|Ave|Av|Avenue|Way|"
        r"Ln|Lane|Dr|Drive|Pl|Place|Ct|Court|Blvd|Hwy|Highway|Route|Rte|Pkwy|Ter|Terrace|"
        r"Cir|Circle|Trl|Trail|Pt|Point|Cove|Loop|Run|Pike|Path|Row|Sq)\b(?![-/]\d)\.?)"
        r"(?:\s+(?:UNIT|APT|SUITE|STE|#)\s*[\w-]+)?" % "|".join(sorted(STATES)), re.I)),
    ("date", re.compile(r"(?<![\d/])\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})(?![\d/])")),
    ("date", re.compile(r"(?<![\d-])\d{4}-\d{2}-\d{2}(?![\d-])")),
    ("date", re.compile(r"(?<![\d-])\d{1,2}-\d{1,2}-\d{4}(?![\d-])")),
    ("date", re.compile(r"\b(?:%s)\.? \d{1,2}, \d{4}\b" % "|".join(MONTHS + [m[:3] for m in MONTHS] + ["Sept"]))),
    ("money", re.compile(r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?(?!\d|,\d)")),
    ("id", re.compile(_B + r"(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9][A-Z0-9-]{5,}" + _E)),
    # a short code in two groups - "PRODUCER CODE: 28-0071" - kept only
    # when a label says it is an identifier, like any bare run of digits
    ("digits", re.compile(r"(?<![\w$,./-])\d{2,4}-\d{3,6}(?![\w,./-])")),
    # a run of digits; a dash printed against it after a label is not part
    # of it ("PACKAGE POLICY NUMBER -803986891")
    ("digits", re.compile(r"(?:(?<![\w$,./-])|(?<=\s-))\d{5,}(?:\s-\s\d{3,}|(?:\s\d{1,4}){1,2}(?=\s*$))?"
                          r"(?![\w,./-])")),
]
FORM_NUMBER = re.compile(r"^[A-Z]{2,6}\d{2,5}-\d{4}$")     # forms keep their numbers
#: what follows a form number: its state and edition, "CW (11-23)", "NY (06/21)"
EDITION = re.compile(r"^\s*(?:[A-Z]{2}\s*)?\(\d{2}[-/]\d{2}\)")
ID_LABEL = re.compile(r"\b(number|no|id|code|hin|vin|account|acct|agency|customer|"
                      r"ref|serial|hull|loan|certificate|claim|policy|#)\b", re.I)
NAME_LABEL = re.compile(r"\b(insured|insureds|client|clients|agent|producer|"
                        r"operator|operators|owner|applicant|contact)\b", re.I)
PRODUCER_LABEL = re.compile(r"\b(agent|producer|agency|broker)\b", re.I)
INSURED_LABEL = re.compile(r"\b(insured|insureds|client|clients|applicant|owner)\b", re.I)
NOT_A_NAME = re.compile(r"\b(page|policy|coverage|date|premium|limit|number|total|"
                        r"address|description|declarations|location|endorsement|"
                        r"information|type|plan|form|effective|expiration|period|amount|"
                        r"paid|loss|losses|claim|violation|operator|vehicle|owner|original|"
                        r"discount|discounts|free|renewal|online|payment|summary|"
                        r"watercraft)\b", re.I)
#: a line that names an insurer rather than a policyholder or an agency
INSURER_NAME = re.compile(r"\b(?:insurance|indemnity|assurance|casualty)\s+(?:company|co\.?|"
                          r"corporation|corp\.?)(?:\s|$)|\bunderwriters\b", re.I)
PII = {"email", "phone", "fein", "pobox", "cityline", "street", "id", "digits",
       "person", "company", "scanline", "zip", "place", "county", "gluedcity"}
#: a town, state and ZIP read off a scan as one word: "EAGLEBAYNY133310252"
GLUED_CITY = re.compile(r"([A-Z]{4,})([A-Z]{2})(\d{5}(?:\d{4})?)")
#: a label naming a person printed beside it: "Name:", "Driver Name", "NAMED INSURED:"
NAME_BESIDE = re.compile(r"^(?:(?:driver|insured|named insured|co-insured|operator|applicant|"
                         r"owner|registrant)\s+)?names?(?:\s*\(s\))?\s*:?$|"
                         r"^(?:named\s*)?insureds?(?:\s*\(s\))?\s*:?$", re.I)
#: a table column of names: "DRIVER NAME", "Name(s)", "Drivers"
NAME_COLUMN = re.compile(r"^(?:driver|operator|insured)?\s*names?(?:\s*\(s\))?$|"
                         r"^(?:drivers?|operators?)(?:\s*\(s\))?$", re.I)
#: what a driver or household row prints beside a name: "32 Male Single",
#: "Gender: Male" - nothing but age, gender and marital status ("combined
#: single limit" is not one)
DEMOGRAPHIC = re.compile(r"(?i)\b(?:male|female|married|single|divorced|widowed|separated)\b")
DEMOGRAPHIC_WORDS = {"male", "female", "married", "single", "divorced", "widowed", "separated",
                     "age", "gender", "sex", "marital", "status", "m", "f"}


def _demographic(text):
    words = re.findall(r"[A-Za-z]+|\d+", text)
    return bool(words) and len(words) <= 6 and bool(DEMOGRAPHIC.search(text)) \
        and all(w.isdigit() and len(w) <= 3 or w.lower() in DEMOGRAPHIC_WORDS for w in words)
#: a town or county printed as its own labelled value: "City  EAGLE BAY"
PLACE_LABEL = re.compile(r"(?i)^(?:city|town|county(?:\s+name)?)\s*:?$")
COUNTIES = ["Otsego", "Chenango", "Delaware", "Schoharie", "Madison", "Oneida", "Tompkins",
            "Cortland", "Broome", "Tioga", "Chemung", "Steuben", "Jefferson", "Essex",
            "Warren", "Ulster", "Ontario", "Yates", "Lewis", "Hamilton", "Fulton"]
#: a machine-read line - a payment coupon's scan line, a MICR line: only
#: groups of digits, many of them. It encodes the policy number, the amount
#: and the due date, so it is replaced whole
SCANLINE = re.compile(r"\d{4,}(?:\s+\d{3,}){1,9}")
#: a date broken over two lines: "... through May 23," / "2027. Your ..."
DATE_HEAD = re.compile(r"(?<![A-Za-z])(?:%s)\.? \d{1,2}(?=,?\s*$)" % "|".join(
    MONTHS + [m[:3] for m in MONTHS] + ["Sept"]))


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
    "coverage begins on": "policy.effective_date", "coverage began on": "policy.effective_date",
    "policy expires on": "policy.expiration_date", "expires on": "policy.expiration_date",
    "policy period ends on": "policy.expiration_date",
    "policy service": "producer.contact.phone",
    "pay initial installment": "billing.amount_due",
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
    # an amount can be a no-fault benefit too: "Maximum Monthly Work Loss: $2,000",
    # "Death Benefit: $2,000", "Other Necessary Expenses per Day: $25"
    "money": re.compile(r"premium|amount|limit|fee|deductible|value|surcharge|tax|discounts|savings|cost|"
                        r"work_loss|benefit|expenses|available"),
    "id": re.compile(r"number|code|_id|fein"), "digits": re.compile(r"number|code|_id|fein"),
    "fein": re.compile(r"fein"), "phone": re.compile(r"phone|fax"),
    "email": re.compile(r"email"),
    # a name or an address only ever fills a name or an address: "MARITAL STATUS
    # HAS BEEN CHANGED ... FOR Juno Keswick" names no marital status
    "person": re.compile(r"name|insured|driver|designee|representative|signator|operator"),
    "company": re.compile(r"name|agency|company|carrier|insurer|lienholder|payee|party|designee"),
    "street": re.compile(r"line_|address|street"), "pobox": re.compile(r"line_|address"),
    "cityline": re.compile(r"city|address"), "place": re.compile(r"city|town|address"),
    "county": re.compile(r"county"), "zip": re.compile(r"postal|zip"),
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
        # a section's heading ("Insurer" over the carrier block) is not a
        # field: it must not take the phrase from the field that has it
        if path in schema.leaves:
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
    # a schema that keeps the first inception apart from the current term
    # takes "Inception Date" there, not to the policyholder's tenure
    if "policy.original_inception_date" in schema.leaves:
        index["inception date"] = "policy.original_inception_date"
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
        self.no_zip = False       # a known town printed here without its ZIP
        self.whole = None         # the whole value, when this is one line of it
        self.part = None          # 0 = its first line, 1 = the line it ends on
        self.name_part = None     # 0/1 = the first/last name alone of the person in ``key``
        self.city_only = False    # the town alone of the city line in ``key``

    @property
    def rect(self):
        return self.cell.span_rect(self.start, self.end)


def _date_of(text):
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y", "%b. %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _wrapped_dates(cell_list, found):
    """A date whose year was set on the next line of a paragraph."""
    out = []
    for cell in cell_list:
        m = DATE_HEAD.search(cell.text)
        if m is None or any(f.cell is cell and f.start < m.end() and m.start() < f.end
                            for f in found):
            continue
        below = _below(cell, cell_list)
        if below is None or any(f.cell is below and f.start < 4 for f in found):
            continue
        year = re.match(r"\d{4}(?![\d/,])", below.text)
        whole = m.group(0).replace(".", "") + ", " + (year.group(0) if year else "")
        if year is None or _date_of(whole) is None:
            continue
        for n, (c, s, e) in enumerate(((cell, m.start(), m.end()), (below, 0, 4))):
            f = Found("date", c, s, e)
            f.whole, f.key, f.part = whole, _key(whole), n
            out.append(f)
    return out


def _detect(cell_list):
    found = []
    for cell in cell_list:
        if re.search(r"https?:|www\.|://", cell.text):
            continue
        if SCANLINE.fullmatch(cell.text.strip()) and len(re.sub(r"\D", "", cell.text)) >= 20:
            s = len(cell.text) - len(cell.text.lstrip())
            found.append(Found("scanline", cell, s, s + len(cell.text.strip())))
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
                if kind == "id" and GLUED_CITY.fullmatch(text) and GLUED_CITY.fullmatch(text).group(2) in STATES:
                    kind = "gluedcity"            # "EAGLEBAYNY133310252": a town line read without spaces
                if kind in ("id", "digits") and EDITION.match(cell.text[e:]):
                    continue                      # a form number and its edition
                if kind == "cityline" and m.group(2) not in STATES:
                    continue
                if kind == "zip" and "-" not in text and cell.text[max(0, s - 3):s - 1] not in STATES:
                    continue                      # five digits after two capitals that are no state
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
    if NAME_LABEL.search(text) or re.search(r"\bnamed\b|\(s\)", text, re.I):
        return False                      # a label: "NAMED INSURED(S)", "Your Agent"
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
    if f.after and prefix.lower() in ("-", "\u2013", "to", "through", "thru"):
        return "to"                               # the end of "from A - B"
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
    found += _wrapped_dates(cell_list, found)
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
            first = True                          # a surname alone heads an ID card's block
            while up is not None and id(up) not in names and (
                    _looks_like_name(up.text) or first and _one_word_name(up.text)):
                names[id(up)] = (up, None)
                up = _above(up, cell_list)        # a second insured stacked above
                first = False
    for cell in cell_list:
        if NAME_LABEL.search(cell.text) and len(cell.text) < 45 and len(cell.text.split()) <= 5 \
                and not re.search(r"\d", cell.text):
            cand = _below(cell, cell_list, max_gap=3.2)
            while cand is not None and _looks_like_name(cand.text) and id(cand) not in names:
                names[id(cand)] = (cand, cell.text)
                cand = _below(cand, cell_list)    # a second name stacked under the first
        # "Name:  Juno Prentice", "Named Insured  VANTAGE CONTRACTING"
        left = _left(cell, cell_list)
        if left is not None and NAME_BESIDE.match(_plain(left.text)) and _looks_like_name(cell.text):
            names.setdefault(id(cell), (cell, left.text))
        # a column of names under its heading: "DRIVER NAME" over "MEGHAN", "PETER"
        if NAME_COLUMN.match(_plain(cell.text)):
            cand = _below(cell, cell_list, max_gap=3.2)
            while cand is not None and id(cand) not in names and (
                    _looks_like_name(cand.text) or _one_word_name(cand.text)):
                names[id(cand)] = (cand, cell.text)
                cand = _below(cand, cell_list, max_gap=2.5)
    # a driver or household row: a name with gender or marital status beside it
    for cell in cell_list:
        if id(cell) in names or not _looks_like_name(cell.text):
            continue
        r = cell.rect
        for other in cell_list:
            o = other.rect
            if other is cell or o.x0 < r.x1 or abs((o.y0 + o.y1) - (r.y0 + r.y1)) > 3.2 * r.height:
                continue
            if _demographic(other.text):
                names[id(cell)] = (cell, "")
                break
    for cell, label in names.values():
        if any(f.cell is cell for f in found):
            continue
        for s, e in _name_spans(cell.text):
            words = set(w.lower().strip(",") for w in cell.text[s:e].split())
            f = Found("company" if words & COMPANY_WORDS else "person", cell, s, e)
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
        elif f.kind == "company" and re.search(r"insurance|agency|brokers?|\bins\b", f.text, re.I):
            f.role = "producer"
    # a mailing block with no label over it - an envelope window - holds the
    # policyholder: people, above an address, when no label named anyone else
    streets = [f.cell for f in found if f.kind in ("street", "pobox")]
    block = [f for f in found if f.kind == "person" and any(
        s.rect.y0 > f.rect.y0 and s.rect.y0 - f.rect.y1 < 4 * f.rect.height
        and abs(s.rect.x0 - f.rect.x0) < 14 for s in streets)]
    if block and not any(f.role for f in block):
        for f in block:
            f.role = "insured"
    extra = _address_block(found, cell_list)
    for g in extra:
        g.label = _label_for(g, cell_list)
    found += extra
    # a town or county printed as a labelled value: "City  EAGLE BAY"
    for cell in cell_list:
        left = _left(cell, cell_list)
        text = cell.text.strip()
        if left is None or not PLACE_LABEL.match(left.text.strip()) \
                or any(f.cell is cell for f in found) \
                or not re.fullmatch(r"[A-Za-z][A-Za-z.' -]{1,40}", text):
            continue
        s = len(cell.text) - len(cell.text.lstrip())
        f = Found("county" if "county" in left.text.lower() else "place", cell, s, s + len(text))
        f.label = left.text
        found.append(f)
    return found


def _plain(text):
    """A heading as words: underlined print ("D__R_I_V_E_R__N_A_M_E_") read plain."""
    text = text.strip()
    if re.fullmatch(r"(?:[A-Za-z]_+)+[A-Za-z]?_*", text.replace(" ", "")):
        text = text.replace("_", "")
    return " ".join(text.split())


def _one_word_name(text):
    """A single capitalised word that can only be a name: a surname heading
    an ID card's address, a first name in a column of driver names."""
    text = text.strip()
    return bool(re.fullmatch(r"[A-Z][A-Za-z'-]{2,}", text)) and not NOT_A_NAME.search(text) \
        and not NAME_LABEL.search(text) and text.lower() not in COMPANY_WORDS \
        and text.upper() not in STATES and text.lower() not in (
            "none", "yes", "no", "named", "name", "names", "driver", "drivers", "married",
            "single", "male", "female", "divorced", "widowed", "separated", "principal",
            "occasional", "excluded", "included", "incl", "rated", "status", "file", "insured")


def _name_spans(text):
    """Where the names in a cell are: two people printed together ("Juno
    Prentice & Hazel Vance") are two names, each replaced on its own."""
    s = len(text) - len(text.lstrip())
    e = len(text.rstrip())
    parts = list(re.finditer(r"\s+(?:&|and)\s+", text[s:e]))
    if len(parts) == 1:
        a, b = text[s:s + parts[0].start()], text[s + parts[0].end():e]
        if len(a.split()) >= 2 and len(b.split()) >= 2 and not (
                set(w.lower().strip(",") for w in (a + " " + b).split()) & COMPANY_WORDS):
            return [(s, s + parts[0].start()), (s + parts[0].end(), e)]
    return [(s, e)]


#: a street line whose type word is missing or unknown: "9599 STATION"
BARE_STREET = re.compile(r"[1-9]\d{0,5}\s+[A-Za-z][A-Za-z .'#-]*")   # not "05 SAAB 9-3 ARC"
#: a town line in an address block: one to three capitalised words
TOWN_LINE = re.compile(r"[A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){0,2}")


def _address_block(found, cell_list):
    """The lines of a name-and-address block its shapes do not give away: a
    street with no street-type word, the town set on a line of its own, the
    second line of a name. They are read as address only once a line of the
    block is known to be one - a street, a PO box, a town-and-ZIP."""
    out = []
    held = {id(f.cell) for f in found}
    kinds = ("street", "pobox", "cityline", "zip", "place")
    for f in [g for g in found if g.kind in ("person", "company")]:
        cell, address, pending = f.cell, False, []
        # the end of the name set in the next column: "NORTHVALE BUILDERS  CISA"
        r = f.cell.rect
        right = min((c for c in cell_list if c.row == f.cell.row and c.rect.x0 > r.x1
                     and c.rect.x0 - r.x1 < 8 * r.height), key=lambda c: c.rect.x0, default=None)
        if right is not None and id(right) not in held and _one_word_name(right.text) \
                and right.text.strip().isupper() == f.text.isupper():
            s = len(right.text) - len(right.text.lstrip())
            pending.append(Found("place", right, s, s + len(right.text.strip())))
        for _ in range(6):
            cell = _below(cell, cell_list, max_gap=2.6)   # a block set with open leading
            if cell is None:
                break
            text = cell.text.strip()
            mine = [g for g in found + out if g.cell is cell]
            if mine:
                if any(g.kind in kinds for g in mine):
                    address = True
                    out += pending
                    pending = []
                continue
            # a line whose ZIP or town is set in the next column is an address line
            beside = any(g.cell.row == cell.row and g.kind in kinds for g in found)
            if ":" in text or NAME_LABEL.search(text) or PRODUCER_LABEL.search(text) \
                    or len(text.split()) > 4:
                break
            if len(re.sub(r"[^A-Za-z0-9]", "", text)) <= 3:
                continue                          # a stray fragment of the print
            s = len(cell.text) - len(cell.text.lstrip())
            if BARE_STREET.fullmatch(text) and id(cell) not in held:
                out += pending + [Found("street", cell, s, s + len(text))]
                pending, address = [], True
            elif TOWN_LINE.fullmatch(text) and not NOT_A_NAME.search(text) \
                    and text.upper() not in STATES and id(cell) not in held:
                g = Found("place", cell, s, s + len(text))
                if address or beside:
                    out += pending + [g]
                    pending, address = [], True
                else:
                    pending.append(g)
            else:
                break
    seen, unique = set(), []
    for g in out:
        if id(g.cell) not in seen:
            seen.add(id(g.cell))
            unique.append(g)
    return unique


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
        self.memo: Dict[tuple, str] = {}
        # a replacement must not be another original value of this document -
        # the insured's town handed to the agent is still the insured's town
        self.used = {_key(o) for o in originals}

    def __call__(self, f: Found) -> str:
        if f.blank:
            return ""
        if f.name_part is not None:          # "MEGHAN" in a driver column: the new first name
            key = ("person", f.key)
            if key not in self.memo:
                self.memo[key] = self._person(f.key)
            words = self.memo[key].split()
            return _case_like(words[0] if f.name_part == 0 else words[-1], f.text)
        if f.city_only:                      # "EAGLE BAY" alone: the new town, no state or ZIP
            key = ("cityline", f.key)
            if key not in self.memo:
                self.memo[key] = self._cityline(f.key)
            m = PATTERNS[4][1].search(self.memo[key])
            return _case_like(m.group(1) if m else self.memo[key], f.text)
        if f.kind in ("id", "digits") and not f.key:
            key = ("ident", re.sub(r"\s", "", f.text).lower())
            if key not in self.memo:
                self.memo[key] = self._id(f.text)
            chars = iter(re.sub(r"\s", "", self.memo[key]))
            return "".join(c if c.isspace() else next(chars) for c in f.text)
        key = (f.kind, f.key or _key(f.text))
        if key not in self.memo:
            self.memo[key] = getattr(self, "_" + f.kind)(f.whole or f.text)
        new = self.memo[key]
        if f.part is not None:               # one line of a wrapped date
            head, _, year = new.rpartition(" ")
            return head.rstrip(",") if f.part == 0 else year
        if f.no_zip:
            new = re.sub(r"\s+\d{5}(?:-\d{4})?$", "", new)
        if f.kind == "date" and f.key and _key(f.text) != f.key:
            return new                       # a garbled copy: print the date cleanly
        return _case_like(new, f.text)

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
        if len(words) == 1:                  # a first name alone, or a surname alone
            given = {g.lower() for g in GIVEN}
            pool = GIVEN if old.strip().lower() in given else SURNAME
            return self._unique(lambda: self.v.choice(pool), old)
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

    def _gluedcity(self, old):
        m = GLUED_CITY.fullmatch(old)
        def make():
            city, zip_ = self.v.choice(TOWNS)
            plus = "".join(str(self.v.integer(0, 9)) for _ in range(len(m.group(3)) - 5))
            return re.sub(r"\W", "", city).upper() + "NY" + zip_ + plus
        return self._unique(make, old)

    def _zip(self, old):
        return self._unique(lambda: _reshape_digits(old, self.v), old)

    def _place(self, old):
        return self._unique(lambda: self.v.choice(TOWNS)[0], old)

    def _county(self, old):
        return self._unique(lambda: self.v.choice(COUNTIES), old)

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
    def _scanline(self, old):
        """New digits in the same groups, with the replaced identifiers the
        line encodes spliced back in where the originals stood."""
        new = _reshape_digits(old, self.v)
        flat_old, flat_new = re.sub(r"\s", "", old), list(re.sub(r"\s", "", new))
        for (kind, key), value in self.memo.items():
            digits = re.sub(r"\D", "", key)
            if kind in ("id", "digits", "ident") and len(digits) >= 6 and digits in flat_old:
                repl = re.sub(r"\D", "", value)
                if len(repl) == len(digits):
                    at = flat_old.index(digits)
                    flat_new[at:at + len(digits)] = repl
        out, k = [], 0
        for c in new:
            if c.isdigit():
                out.append(flat_new[k])
                k += 1
            else:
                out.append(c)
        return "".join(out)

    def _date(self, old):
        d = _date_of(old)
        if d is None:
            return old
        n = d + timedelta(days=self.days)
        sep = "/" if "/" in old else "-" if re.fullmatch(r"\d{1,2}-\d{1,2}-\d{4}", old) else None
        if sep:
            mo, dy, yr = old.split(sep)
            parts = [("%02d" if len(mo) == 2 else "%d") % n.month,
                     ("%02d" if len(dy) == 2 else "%d") % n.day,
                     str(n.year) if len(yr) == 4 else "%02d" % (n.year % 100)]
            return sep.join(parts)
        if "-" in old:
            return n.isoformat()
        return "%s %d, %d" % (n.strftime("%B" if old.split()[0] in MONTHS else "%b"), n.day, n.year)

    def _money(self, old):
        # kept: a premium schedule's total is the sum of rows printed
        # without a "$", and any scaling rounds the parts apart from it
        return old


# ── gold ────────────────────────────────────────────────────────────────────

def _set(doc, path, value):
    keys = path.split(".")
    for k in keys[:-1]:
        doc = doc.setdefault(k, {})
    doc.setdefault(keys[-1], value)


def _field(kind, raw):
    if kind == "date":
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"):
            try:
                return fv(raw, datetime.strptime(raw, fmt).strftime(DATE_FORMAT))
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
    # the first name printed in a block is its primary one: a policy's
    # second insured sits under the first
    ordered = sorted((f for f in found if f.kind in ("person", "company") and f.role),
                     key=lambda f: (f.cell.page, f.rect.y0, f.rect.x0))
    for f in ordered:
        base = "named_insured" if f.role == "insured" else "producer"
        name_path = base + (".primary_name" if base == "named_insured" else ".agency_name")
        if name_path in placed:
            # a second name under its own label: "CLIENTS" is a contact
            path = match_label(_norm_label(f.label), f.kind, index)
            if path and path not in placed:
                _set(gold, path, fv(f.new))
                placed.add(path)
                continue
            # a second policyholder printed in the same mailing block, or
            # under a label that names policyholders ("CLIENTS")
            if base == "named_insured" and (not f.label or INSURED_LABEL.search(f.label)):
                extra = gold["named_insured"].setdefault("additional_named_insureds", [])
                if f.new != gold["named_insured"]["primary_name"]["raw"] and \
                        not any(e["name"]["raw"] == f.new for e in extra):
                    extra.append({"name": fv(f.new), "entity_type": derived(
                        "Individual" if f.kind == "person" else "Organization", f.new)})
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
        for _ in range(5):
            cell = _below(cell, [x.cell for x in found])
            if cell is None:
                break
            for g in by_cell.get(id(cell), []):
                if g.kind in ("email", "phone") and not g.blank:
                    # printed under the mailing address: this party's contact
                    _set(gold, base + ".contact." + g.kind, fv(g.new))
                    placed.add(id(g))
                elif g.kind in ("street", "pobox"):
                    _set(gold, addr + ".line_1", fv(g.new)); g.label = g.label or "(address)"
                    placed.add(id(g))
                elif g.kind == "cityline":
                    m = PATTERNS[4][1].search(g.new)
                    if m:
                        _set(gold, addr + ".city", fv(m.group(1)))
                        _set(gold, addr + ".state", fv(m.group(2)))
                        _set(gold, addr + ".postal_code", fv(m.group(3)))
                        placed.add(id(g))
                elif g.kind == "place" and not g.city_only:
                    _set(gold, addr + ".city", fv(g.new))
                    placed.add(id(g))
                elif g.kind == "zip":
                    _set(gold, addr + ".postal_code", fv(g.new))
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
        elif path and _get(gold, path) is not None and (
                _get(gold, path)["raw"] == f.new
                or _get(gold, path).get("parsed") == _field(f.kind, f.new).get("parsed")):
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
    # and run into the word after it ("Elena VaseyMarried Male Driver")
    glued_end = r"(?:(?![A-Za-z0-9])|(?-i:(?<=[a-z])(?=[A-Z])))"
    pattern = re.compile("|".join(
        (glued if kinds[k] in ("person", "company") else r"(?<![A-Za-z0-9])")
        + r"\s+".join(map(re.escape, k.split()))
        + (glued_end if kinds[k] in ("person", "company") else r"(?![A-Za-z0-9])")
        for k in sorted(kinds, key=len, reverse=True)), re.I)
    # a first or last name printed alone in a cell ("MEGHAN" in a driver
    # column) is that person's: it takes the same new first or last name
    parts = {}
    for k, kind in kinds.items():
        words = k.split()
        if kind == "person" and len(words) >= 2 and "&" not in words:
            for n, w in ((0, words[0]), (1, words[-1])):
                if len(w) >= 3 and w.isalpha() and w.upper() not in STATES:
                    parts.setdefault(w, (k, n))
    cities = {}
    garbled, towns = [], []
    for *_, found in pages:
        for f in found:
            if f.kind == "date" and not f.blank:
                m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", f.text)
                if m:
                    garbled.append((_key(f.text), re.compile(
                        r"(?<![\d/])\d{1,2}[/1lI|]?0?%s[/1lI|]%s(?![\d/])" % (m.group(2), m.group(3)))))
            if f.kind == "cityline" and not f.blank:
                m = PATTERNS[4][1].fullmatch(f.text)
                if m:
                    towns.append((_key(f.text), re.compile(
                        r"(?<![A-Za-z])%s,\s*%s(?!\s*\d)(?![A-Za-z])" % (re.escape(m.group(1)), m.group(2)))))
                    cities.setdefault(_key(m.group(1)), _key(f.text))
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
        # a known date the OCR read with its slashes as 1s: "112912026" is
        # 7/29/2026 printed in a stamp - the day and year must match exactly
        for cell in cell_list:
            spans = taken.setdefault(id(cell), [])
            for key, rx in garbled:
                for m in rx.finditer(cell.text):
                    s, e = m.span()
                    if any(s < te and ts < e for ts, te in spans):
                        continue
                    f = Found("date", cell, s, e)
                    f.key = key
                    f.label = _label_for(f, cell_list)
                    found.append(f)
                    spans.append((s, e))
            # a known town printed without its ZIP: "Signed ... at Inlet, NY"
            for key, rx in towns:
                for m in rx.finditer(cell.text):
                    s, e = m.span()
                    if any(s < te and ts < e for ts, te in spans):
                        continue
                    f = Found("cityline", cell, s, e)
                    f.key, f.no_zip = key, True
                    f.label = _label_for(f, cell_list)
                    found.append(f)
                    spans.append((s, e))
            # a known first/last name, or a known town, as the whole cell:
            # "MEGHAN" under DRIVER NAME, "EAGLE BAY" beside "City"
            alone = _key(cell.text)
            if spans or not alone or re.search(r"\d", alone):
                continue
            s = len(cell.text) - len(cell.text.lstrip())
            if alone in parts:
                f = Found("person", cell, s, s + len(cell.text.strip()))
                f.key, f.name_part = parts[alone]
            elif alone in cities:
                f = Found("cityline", cell, s, s + len(cell.text.strip()))
                f.key, f.city_only = cities[alone], True
            else:
                continue
            f.label = _label_for(f, cell_list)
            found.append(f)
            spans.append((f.start, f.end))
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
    drop, heads = set(), []
    for f in found:
        # "TRAVELERS" alone over the carrier's own PO box reads like a name
        if f.kind in ("company", "person") and marks & set(re.findall(r"[a-z]{4,}", f.text.lower())):
            drop.add(id(f))
            heads.append(f.cell)
    # the carrier's name printed as plain text heads its address too: the
    # remittance block under "PROGRESSIVE", or "One Tower Square, Hartford"
    # two lines under "TRAVCO INSURANCE COMPANY"
    for cell in cell_list:
        words = cell.text.split()
        if 0 < len(words) <= 6 and not any(g.cell is cell for g in found) and (
                marks & set(re.findall(r"[a-z]{4,}", cell.text.lower()))
                or INSURER_NAME.search(cell.text)):
            heads.append(cell)
    for head in heads:
        cell = head
        for _ in range(3):                  # and the address printed under it
            cell = _below(cell, cell_list)
            if cell is None or NAME_LABEL.search(cell.text) or _looks_like_name(cell.text) \
                    and not (marks & set(re.findall(r"[a-z]{4,}", cell.text.lower()))):
                break                       # another party's block begins
            for g in found:
                if g.cell is cell and g.kind in ("street", "pobox", "cityline", "zip", "place"):
                    drop.add(id(g))
    return [f for f in found if id(f) not in drop]


def _layer_line(layer, r):
    """The text layer's characters printed across a line's box, in order -
    with some slack, as a layer can sit a little off its print."""
    band = fitz.Rect(r.x0 - 0.5 * r.height, r.y0, r.x1 + 3 * r.height, r.y1)
    row = [ch for ch in layer
           if band.contains(fitz.Point((ch.box.x0 + ch.box.x1) / 2, (ch.box.y0 + ch.box.y1) / 2))]
    return "".join(ch.c for ch in sorted(row, key=lambda ch: ch.box.x0))


def _layer_span(layer, r):
    """``(x0, x1, n)`` of the text layer's characters set across a line's
    box - ``n`` its letters and digits - or None when the layer has nothing there."""
    band = fitz.Rect(r.x0 - 0.5 * r.height, r.y0, r.x1 + 0.5 * r.height, r.y1)
    inside = [ch for ch in layer
              if band.contains(fitz.Point((ch.box.x0 + ch.box.x1) / 2, (ch.box.y0 + ch.box.y1) / 2))]
    if not inside:
        return None
    return (min(ch.box.x0 for ch in inside), max(ch.box.x1 for ch in inside),
            sum(ch.c.isalnum() for ch in inside))


def _layer_word(layer, r):
    """The text layer's whole word(s) printed over ``r``, and their box: the
    characters on its line that overlap it, grown to the word's ends."""
    row = sorted((ch for ch in layer if ch.box.y0 < r.y1 and ch.box.y1 > r.y0
                  and abs((ch.box.y0 + ch.box.y1) / 2 - (r.y0 + r.y1) / 2) < 0.5 * r.height),
                 key=lambda ch: ch.box.x0)
    hit = [k for k, ch in enumerate(row) if ch.box.x1 > r.x0 - 1 and ch.box.x0 < r.x1 + 1]
    if not hit:
        return "", r
    a, b = hit[0], hit[-1]
    gap = lambda k: row[k + 1].box.x0 - row[k].box.x1
    while a > 0 and gap(a - 1) < 0.35 * row[a].box.height:
        a -= 1
    while b < len(row) - 1 and gap(b) < 0.35 * row[b].box.height:
        b += 1
    box = fitz.Rect(row[a].box)
    for ch in row[a:b + 1]:
        box |= ch.box
    return "".join(ch.c for ch in row[a:b + 1]), box


def _signature_ink(pages):
    """The printed label of a signature line with handwriting beside or over
    it - dark ink where no text is - or None. A scan draws the signature
    into the page image, so it is found in the ink, not the text layer."""
    import numpy as np
    for page, ink, matrix, visible, cell_list, found in pages:
        for cell in cell_list:
            if not re.match(r"(?i)^(signed\b|signature\b|authorized (?:representative )?signature)",
                            cell.text.strip()):
                continue
            r = cell.rect
            h = max(r.height, 6)
            band = fitz.Rect(r.x0, r.y0 - 3.5 * h, page.rect.width - 20, r.y1 + 0.5 * h)
            z = ink.zoom
            y0, y1 = int(max(0, band.y0 * z)), int(min(ink.mask.shape[0], band.y1 * z))
            x0, x1 = int(max(0, band.x0 * z)), int(min(ink.mask.shape[1], band.x1 * z))
            region = ink.mask[y0:y1, x0:x1].copy()
            if not region.size:
                continue
            region[region.mean(1) > 0.5, :] = False      # rules across the band
            region[:, region.mean(0) > 0.5] = False
            for other in cell_list:                      # printed text is not a hand
                q = other.rect
                if q is None or not q.intersects(band):
                    continue
                pad = 0.3 * q.height
                a, b = int(max(0, (q.x0 - pad) * z)) - x0, int((q.x1 + pad) * z) - x0
                c, d = int(max(0, (q.y0 - pad) * z)) - y0, int((q.y1 + pad) * z) - y0
                region[max(0, c):max(0, d), max(0, a):max(0, b)] = False
            if region.mean() > 0.004 and np.count_nonzero(region.any(0)) > 20 * z:
                label = re.match(r"(?i)^(signed(?: on)?|(?:authorized (?:representative )?)?signature)",
                                 cell.text.strip())
                return label.group(1)            # the label, not the replaced date after it
    return None


def _walk_fields(doc):
    from .fields import walk
    return walk({k: v for k, v in doc.items() if not k.startswith("fideon")})


def _drop_path(doc, path):
    """Remove the field at an indexed path ("a.b[2].c"); True if it was there."""
    keys = re.findall(r"[^.\[\]]+|\[\d+\]", path)
    node = doc
    for k in keys[:-1]:
        node = node[int(k[1:-1])] if k.startswith("[") else node.get(k)
        if node is None:
            return False
    last = keys[-1]
    if last.startswith("[") or not isinstance(node, dict) or last not in node:
        return False
    del node[last]
    return True


def _alignment(f, cell_list):
    """``right`` when the value sits in a right-aligned column - the cells
    above and below it end where it ends but start elsewhere."""
    if f.cell.text[f.end:].strip(" ,;.-–"):
        return "left"                     # words follow it: it is set in a sentence
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


def _turn_of(page):
    """The quarter turn that sets a page's print upright - 90 when most of
    its text runs up the sheet, -90 when down - or 0."""
    across = up = down = 0
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            n = sum(len(span["chars"]) for span in line["spans"])
            dx, dy = line["dir"]
            if abs(dx) >= 0.7:
                across += n
            elif dy <= -0.7:
                up += n
            elif dy >= 0.7:
                down += n
    if up + down < 20 or up + down < 1.5 * across:
        return 0
    return 90 if up >= down else -90


def _ocr_yield(lines):
    return sum(len(re.sub(r"\W", "", text)) for text, _, conf in lines if conf >= 0.8)


def _scan_turn(page, upright_lines):
    """The quarter turn a scanned page needs, read from its image: a sideways
    card's OCR layer is reversed text the engine reads twice over, and the
    engine reads a quarter turn of it better still."""
    layer = len(re.sub(r"\W", "", page.get_text()))
    base = _ocr_yield(upright_lines)
    if not layer or base < 1.6 * layer:
        return 0
    best, turn = base, 0
    for t in (90, -90):
        got = _ocr_yield(recover.read_page(page, turn=t))
        if got >= 1.25 * base and got > best:
            best, turn = got, t
    return turn


def _upright(doc, dpi=300, read=None):
    """Pages printed sideways - an envelope sheet, ID cards set up the page -
    are read as a scan of themselves turned upright: the generator reads,
    replaces and draws in lines across the page. Returns ``{index: turn}``
    for the finished scan to be turned back. ``read`` collects the upright
    OCR of scanned pages, for the page to be read only once."""
    turned = {}
    for i in range(len(doc)):
        page = doc[i]
        turn = _turn_of(page)
        if not turn and read is not None and recover.is_scanned(page, overlay.invisible_text(page)):
            read[i] = recover.read_page(page)
            turn = _scan_turn(page, read[i])
            if turn:
                del read[i]
        if not turn:
            continue
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72).prerotate(turn))
        page = doc.new_page(pno=i, width=pix.width * 72 / dpi, height=pix.height * 72 / dpi)
        page.insert_image(page.rect, pixmap=pix)
        doc.delete_page(i + 1)
        turned[i] = turn
    return turned


def _turn_back(pdf, turned):
    """Set the finished scan's upright pages back as the source printed them."""
    if not turned:
        return
    doc = fitz.open(str(pdf))
    for i, turn in turned.items():
        doc[i].set_rotation(turn % 360)
    doc.saveIncr()
    doc.close()


def _second_look(page, found):
    """Read a scanned page again once its replacements are drawn, and cover
    any original identifying value still legible where the print shows it.

    A scan's text layer can be set apart from its print - narrower, or out of
    order - and a value found in the layer is then covered where the layer
    puts it, not where it is printed. The OCR engine sees the print."""
    olds = {}
    for f in found:
        if f.kind in PII and f.new and f.new != f.text and not f.blank and f.part is None                 and f.name_part is None and not f.city_only:
            key = re.sub(r"[^a-z0-9]", "", f.text.lower())
            if len(key) >= 6 and re.search(r"\d", key):     # an identifier, a ZIP, a street number
                olds.setdefault(key, f)
    if not olds:
        return []
    reps, ink = [], None
    for text, rect, conf in recover.read_page(page):
        mine, where = recover._key(text)
        chars = recover._chars_of(text, rect)
        for key, f in olds.items():
            i = mine.find(key)
            if i < 0:
                continue
            a, b = where[i], where[i + len(key) - 1] + 1
            span = fitz.Rect(chars[a][1])
            for _, box in chars[a:b]:
                span |= box
            # the engine's line box is spread by glyph widths, not measured:
            # start the cover where the printed word begins, a little left at most
            ink = ink or overlay.Ink(page)
            h = span.height
            start = ink.word_start(span.y0 + 0.2 * h, span.y1 - 0.2 * h, span.x0 + 1, gap=0.3 * h)
            span.x0 = max(min(start, span.x0), span.x0 - 0.25 * span.width)
            reps.append(overlay.Replacement(
                page=page.number, old=text[a:b], new=f.new, visible_rect=span, ocr_rect=span,
                font="helv", face_known=False, glued=a > 0 and not text[a - 1].isspace(),
                color=0, align="left", room=None))
    if reps:
        overlay.apply(page, reps, ink or overlay.Ink(page), fitz.Identity)
    return reps


def synthesize(source_pdf, out_pdf, out_gold, schema, vals, seed=0):
    """One synthetic document and its gold from one source PDF."""
    source_pdf = Path(source_pdf)
    built = Built(key=Path(out_pdf).stem, pdf=Path(out_pdf), gold=Path(out_gold),
                  pages=0, fields=0)
    digital = built.pdf.with_name("_temp_" + built.pdf.name)
    try:
        doc = fitz.open(str(source_pdf))
        built.pages = len(doc)
        read = {}
        turned = _upright(doc, read=read)
        found_all, plans, pages = [], [], []
        recovered, scanned = {}, set()
        for page in doc:
            ink = overlay.Ink(page)
            invisible = overlay.invisible_text(page)
            visible = not invisible
            matrix = fitz.Identity if visible else overlay.calibrate(page, ink)
            extra = drop = None
            stretched = []
            if recover.is_scanned(page, invisible):
                scanned.add(page.number)
                # read the scan again: what its OCR layer left out or garbled
                layer = overlay.layer_chars(page, matrix)
                runs, drop = recover.reconcile(
                    read.pop(page.number, None) or recover.read_page(page),
                    lambda r, layer=layer: _layer_line(layer, r),
                    lambda r, layer=layer: _layer_word(layer, r),
                    lambda r, layer=layer: _layer_span(layer, r), stretched)
                if runs:
                    recovered[page.number] = runs
                    extra = recover.as_chars(runs, matrix)
                    visible = False                # draw as on a scan
            cell_list = overlay.cells(page, matrix, ink, extra=extra, drop=drop, stretch=stretched)
            found = _drop_carrier(find_values(cell_list), cell_list, source_pdf.parent.parent.name)
            pages.append((page, ink, matrix, visible, cell_list, found))
        _sweep(pages, _carrier_marks(source_pdf.parent.parent.name))
        faker = Faker(vals, [f.text for *_, found in pages for f in found if f.kind in PII])
        for *_, found in pages:          # a scan line encodes the others
            for f in found:
                if f.kind != "scanline":
                    f.new = faker(f)
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
                # the words printed after it in its own line: the new value
                # must end a space before them, not run over them
                room = (nxt.rect.x0 - 3) if nxt is not None else page.rect.width - 18
                after = end
                while after < len(f.cell.text) and f.cell.chars[after] is None:
                    after += 1
                if after < len(f.cell.text) and f.cell.chars[end - 1] is not None:
                    gap = f.cell.chars[after].box.x0 - f.cell.chars[end - 1].box.x1
                    room = f.cell.chars[after].box.x0 - max(1.5, 0.8 * gap)
                reps.append(overlay.Replacement(
                    page=page.number, old=f.text + tail, new=f.new + tail,
                    visible_rect=f.cell.span_rect(f.start, end),
                    ocr_rect=f.cell.span_rect(f.start, end, ocr=True),
                    font=overlay.base14(first.font, visible), face_known=visible,
                    glued=f.start > 0 and f.cell.text[f.start - 1] not in " ",
                    color=first.color if visible else 0,
                    align=_alignment(f, cell_list), room=room))
            found_all += found
            plans.append((page, reps, ink, matrix))
        signed = _signature_ink(pages)
        carrier = source_pdf.parent.parent.name
        index = label_index(schema)
        reader = structure.Reader([(p.number, p.rect.height, cell_list, found)
                                   for p, _, _, _, cell_list, found in pages],
                                  schema, index, carrier)
        laid_out = reader.read()
        every = [f for *_, found in pages for f in found]
        for page, reps, ink, matrix in plans:
            overlay.apply(page, reps, ink, matrix)
            if page.number in scanned:
                reps += _second_look(page, every)
            if page.number in recovered:
                recover.write_back(page, recovered[page.number],
                                   [r.visible_rect for r in reps])
        doc.save(str(digital), garbage=3, deflate=True)
        doc.close()

        texts = pageref.page_texts(digital)
        whole = " ".join(texts)
        rest = whole
        for new in sorted({pageref._norm(f.new) for f in found_all if f.new}, key=len, reverse=True):
            rest = rest.replace(new, " ")
        # a value split across cells is checked whole: its first piece alone
        # ("CEDARLINE") can be a word of some other name on the page
        leaks = sorted({f.key or f.text for f in found_all
                        if (f.kind in PII or f.kind == "date") and f.new != f.text
                        and not f.blank
                        and pageref.on_page(pageref._norm(f.key or f.text), rest)})
        # a policy number is also encoded inside a coupon's scan line
        runs = re.sub(r"(?<=\d)\s(?=\d)", "", rest)
        leaks += sorted({f.text for f in found_all if f.kind in ("id", "digits")
                         and f.new != f.text and len(re.sub(r"\D", "", f.text)) >= 7
                         and re.sub(r"\D", "", f.text) in runs} - set(leaks))
        built.problems += ["source value %r is still in the generated PDF" % t for t in leaks]

        title = schema.merged.get("title", "")
        gold, unmapped = build_gold([f for f in found_all if id(f) not in reader.consumed
                                     and f.part is None and f.kind != "scanline"],
                                    index, carrier, title, built.pdf.name, built.pages, whole)
        structure.finish(structure.merge(gold, laid_out), schema)
        if signed and "signature.signature_present" in schema.leaves:
            gold.setdefault("signature", {}).setdefault(
                "signature_present", derived("Yes", signed))
        unmapped = [u for u in unmapped if not reader.repeated(u)]
        held = {str(fld["raw"]).lower() for _, fld in _walk_fields(gold)}
        unmapped = [u for u in unmapped if str(u["value"]).lower() not in held]
        resolved, misses = pageref.attach(gold, digital)
        # text copied off a page - never a replaced value - can be garbled by
        # an OCR layer, or printed in pieces the text layer keeps apart
        # ("(Vantage 1)" with "Vantage" stored elsewhere). It is set aside,
        # listed, rather than asserted. A replaced value is never set aside:
        # its absence from the page is a real failure
        # only values that were changed: an amount is kept as printed, and a
        # line of garbled text holding "$300,000" is still garbled text
        new_values = {f.new for f in found_all if f.new and f.new != f.text}
        unverified = [(p, raw) for p, raw in misses if raw not in new_values
                      and not any(v in str(raw) for v in new_values if len(v) > 3)
                      and _drop_path(gold, p)]
        misses = [m for m in misses if m not in unverified]
        if unverified:
            gold["fideon:unverified"] = [{"path": p, "value": raw} for p, raw in unverified]
        built.problems += ["gold says %s = %r is printed, but it is not on any page"
                           % (p, raw) for p, raw in misses]
        for item in unmapped:
            item["page_ref"] = [i + 1 for i, t in enumerate(texts)
                                if pageref.on_page(pageref._norm(item["value"]), t)]

        if "text_sections" in schema.merged["properties"]:
            # the printed paragraphs no field holds, in the replaced wording
            gold["text_sections"] = prose.text_sections(digital, {f.new for f in found_all if f.new})
            blob = " ".join(s["raw_text"] for s in gold["text_sections"].values()).lower()
            built.problems += ["source value %r survived into text_sections" % t
                               for t in sorted({f.key or f.text for f in found_all
                                                if f.kind in PII and f.new != f.text and not f.blank
                                                and pageref.on_page(pageref._norm(f.key or f.text), blob)})]

        stats = scan_pdf(digital, built.pdf, scan_by_key("high_quality"), seed=seed)
        _turn_back(built.pdf, turned)
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
            "text_recovered_by_ocr": sum(len(r) for r in recovered.values()),
            "date_shift_days": faker.days,
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
