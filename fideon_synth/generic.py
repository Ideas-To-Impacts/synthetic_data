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
from .scan import HIGH_QUALITY_COMPACT, by_key as scan_by_key, scan_pdf

#: a scan larger than this is stored compactly: GitHub's recommended largest file
SHARE_LIMIT = 50 * 1024 * 1024
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
    ("phone", re.compile(r"(?<!\d)(?:\(\d{3}\)\s?|\d{3}[-.‐-–])\d{3}[-.‐-–]\d{4}(?!\d)")),
    ("fein", re.compile(r"(?<![\d-])\d{2}-\d{7}(?![\d-])")),
    ("pobox", re.compile(r"\bP\.?\s?O\.?\s?(?:Box|BX)\s+\d+\b", re.I)),
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
#: an ISO form number, spaced or run together: "CG 20 18 04 13", "CG20180413", "IL00171198"
ISO_FORM = re.compile(r"^[A-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2}$")
#: what follows a form number: its state and edition, "CW (11-23)", "NY (06/21)"
EDITION = re.compile(r"^\s*(?:[A-Z]{2}\s*)?\(\d{2}[-/]\d{2}\)")
ID_LABEL = re.compile(r"\b(number|no|id|code|hin|vin|account|acct|agency|customer|"
                      r"ref|serial|hull|loan|certificate|claim|policy|#)\b", re.I)
NAME_LABEL = re.compile(r"\b(insured|insureds|client|clients|agent|producer|"
                        r"operator|operators|owner|applicant|contact)\b", re.I)
PRODUCER_LABEL = re.compile(r"\b(agent|producer|agency|broker)\b", re.I)
DRIVER_LABEL = re.compile(r"\b(drivers?|operators?)\b", re.I)
CODED_NAME = re.compile(r"(.+?)\s+-\s*#\s*(\d{3,})\s*")       # "BURKHARD EVANS INC - #909255"
CODE_ONLY = re.compile(r"\s*#\s*(\d{3,})\s*")                 # "#913886" on its own line
DASH_CODE = re.compile(r"\s*-\s*#\s*(\d{3,})\s*")             # "- #495001" in its own column
LABELLED_NAME = re.compile(r"\b(insured)\s*:?\s*([A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){1,3})\s*$", re.I)
#: a ZIP+4 after a state that is not one - an address a redaction scrambled
SCRAMBLED_ZIP = re.compile(r",[^,]*?\b([A-Z]{2,5})\s+(\d{5}-\d{4})\s*$")
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
SCANLINE = re.compile(r"\d{4,}(?:\s+\d{3,}){1,9}(?:\s+\d{1,2})?")   # and a check digit
DASHED_ID = re.compile(r"(?<![\w$,./-])\d{2,5}(?:\s?-\s?|\s)(\d{7,})(?:(?:\s?-\s?|\s)\d{1,4})?(?![\w,./-])")
GROUPED_ID = re.compile(r"(?<![\w$,./-])\d{2,5}(?:-\d{2,5}){2,}(?![\w,./-])")
TIMED_DATE = re.compile(r"(?<![\d/])(\d{1,2}/\d{1,2}/\d{4})(?=\d{1,2}:\d{2})")
#: a date broken over two lines: "... through May 23," / "2027. Your ..."
DATE_HEAD = re.compile(r"(?<![A-Za-z])(?:%s)\.? \d{1,2}(?=,?\s*$)" % "|".join(
    MONTHS + [m[:3] for m in MONTHS] + ["Sept"]))
#: a month name that ends its line, the day and year set on the next
MONTH_TAIL = re.compile(r"(?<![A-Za-z])(?:%s)\.?(?=\s*$)" % "|".join(
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
    # a name belongs in a name field, not in whatever field's label happens to
    # sit above it ("RATING STATE: NY" over a policyholder); an address only
    # ever fills an address ("MARITAL STATUS HAS BEEN CHANGED ... FOR Juno Keswick")
    "person": re.compile(r"name|insured|representative|designee|agent|holder|contact|driver|operator|signator"),
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
    index = {k: v for k, v in index.items() if k and v in schema.leaves}
    # a text layer that drops the spaces between words ("PolicyEffectiveDate")
    # still names the same field
    for k, v in list(index.items()):
        if " " in k and len(k) >= 10:
            index.setdefault(k.replace(" ", ""), v)
    return index


def match_label(label, kind, index):
    """The schema path a label names, or None. Whole-label matches first;
    then the longest multi-word phrase contained in the label."""
    if not label:
        return None
    fits = KIND_FITS.get(kind)
    ok = (lambda p: fits.search(p.rsplit(".", 1)[-1])) if fits else (lambda p: True)
    for whole in (label, label.replace(" ", "")):   # "Named StormPercentage Deductible"
        if whole in index and ok(index[whole]):
            return index[whole]
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
        self.split = None         # "month": the first line holds the month alone
        self.aside = False        # a name replaced but not the policy's insured or agent

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
    # and one whose month ends a line with the day and year on the next:
    # "...policy period August 26, 2026 through August" / "26, 2027."
    for cell in cell_list:
        m = MONTH_TAIL.search(cell.text)
        if m is None or any(f.cell is cell and f.start < m.end() and m.start() < f.end
                            for f in found + out):
            continue
        below = _below(cell, cell_list)
        if below is None or any(f.cell is below and f.start < 8 for f in found + out):
            continue
        rest = re.match(r"\d{1,2},\s*\d{4}(?![\d/,])", below.text)
        if rest is None:
            continue
        whole = m.group(0).replace(".", "") + " " + re.sub(r",\s*", ", ", rest.group(0))
        if _date_of(whole) is None:
            continue
        for n, (c, s, e) in enumerate(((cell, m.start(), m.end()), (below, 0, rest.end()))):
            f = Found("date", c, s, e)
            f.whole, f.key, f.part, f.split = whole, _key(whole), n, "month"
            out.append(f)
    return out


#: a street with no street-type word: "9581 Millbrook", "2646 SUMMIT"
BARE_STREET = re.compile(r"\d{1,6}\s+[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z0-9][A-Za-z0-9.'#-]*){0,4}")
#: a name label with the first name run into it: "Named InsuredWINSLOW"
GLUED_LABEL = re.compile(r"((?:named\s+)?insureds?(?:\(s\))?:?)\s*([A-Z][A-Za-z'-]+)$", re.I)


def _one_word_name(text):
    """A single capitalised word that can be a name in an address block."""
    t = text.strip()
    return bool(re.fullmatch(r"[A-Z][A-Za-z'-]{2,}", t)) and not NOT_A_NAME.search(t)         and not NAME_LABEL.search(t) and t.lower() not in COMPANY_WORDS


def _bare_streets(cell_list, found):
    """A street known by where it stands, not by its words: a line that opens
    with a house number, set over a "City, ST ZIP" line in its column."""
    out = []
    for f in found:
        if f.kind != "cityline" or f.start != 0:
            continue
        up = _above(f.cell, cell_list)
        if up is None or any(g.cell is up for g in found + out) or ":" in up.text:
            continue
        text = up.text.strip()
        if BARE_STREET.fullmatch(text) and abs(up.rect.x0 - f.cell.rect.x0) < 6                 and not NOT_A_NAME.search(text):
            s = len(up.text) - len(up.text.lstrip())
            out.append(Found("street", up, s, s + len(text)))
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
                if kind == "id" and (FORM_NUMBER.match(text) or ISO_FORM.match(text)
                                     or len(re.sub(r"\D", "", text)) < 3):
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
        # an all-digit number set in groups - "255-0072123586-16", "255 -
        # 0072123586": its long core is the identifier, the same wherever it
        # is printed; a product code before it and a sequence after it stay
        for m in DASHED_ID.finditer(cell.text):
            s, e = m.span(1)
            if not any(s < te and ts < e for ts, te in taken):
                found.append(Found("id", cell, s, e))
                taken.append((s, e))
        # an all-digit number in three or more short groups, "103-194-455":
        # an identifier where a label says so (see find_values)
        for m in GROUPED_ID.finditer(cell.text):
            s, e = m.span()
            if len(re.sub(r"\D", "", m.group(0))) >= 8 and _date_of(m.group(0)) is None \
                    and not any(s < te and ts < e for ts, te in taken):
                found.append(Found("digits", cell, s, e))
                taken.append((s, e))
        # a scrambled address keeps its ZIP+4: "WPSWNSWWCV, GHZT 29346-8107"
        m = SCRAMBLED_ZIP.search(cell.text)
        if m and m.group(1) not in STATES:
            s, e = m.span(2)
            if not any(s < te and ts < e for ts, te in taken):
                found.append(Found("id", cell, s, e))
                taken.append((s, e))
        # a date with the time run into it: "09/19/202412:01A.M."
        for m in TIMED_DATE.finditer(cell.text):
            s, e = m.span(1)
            if _date_of(m.group(1)) and not any(s < te and ts < e for ts, te in taken):
                found.append(Found("date", cell, s, e))
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
    found += _bare_streets(cell_list, found)
    for f in found:
        before = [g.end for g in found if g.cell is f.cell and g.end <= f.start]
        f.after = max(before, default=0)
        f.label = _label_for(f, cell_list)
    # a bare run of digits is only an identifier when a label says so, and
    # a form number keeps its number however it is shaped
    # (nine digits or more is an identifier whatever labels it - a policy or
    # licence number: "AUTO - SPECIAL: 933712824", "NY / 110916892")
    found = [f for f in found if (f.kind != "digits" or ID_LABEL.search(f.label)
                                  or len(re.sub(r"\D", "", f.text)) >= 9)
             and (f.kind != "id" or len(re.sub(r"\D", "", f.text)) >= 5 or ID_LABEL.search(f.label))
             and not (f.kind in ("id", "digits") and re.search(r"\bforms?\b", f.label, re.I))]

    # names: the line above an address, or the line a name label introduces
    names = {}
    for f in found:
        if f.kind in ("street", "pobox") and f.start == 0:
            # the names stacked over an address; a one-word line ("MEDINA")
            # counts only in a block a name label heads, where it can be
            # nothing else
            chain, up = [], _above(f.cell, cell_list)
            while up is not None and id(up) not in names and                     (_looks_like_name(up.text) or _one_word_name(up.text)):
                chain.append(up)
                up = _above(up, cell_list)        # a second insured stacked above
            # an agency's block counts as well: "Agency Address" over "IRONVALE"
            headed = up is not None and (NAME_LABEL.search(up.text) or PRODUCER_LABEL.search(up.text)
                                         or GLUED_LABEL.match(up.text))
            for k, cell in enumerate(chain):
                # a surname alone right over the street, in upper and lower case,
                # heads an ID card's block ("Vance" over "122 PROSPECT AVE")
                lone = k == 0 and _lone_name(cell.text) and not cell.text.strip().isupper()
                if not headed and not _looks_like_name(cell.text) and not lone:
                    break
                names[id(cell)] = (cell, None)
            glued = GLUED_LABEL.match(up.text) if headed and chain else None
            if glued and _one_word_name(glued.group(2)) and not any(g.cell is up for g in found):
                g = Found("person", up, glued.start(2), glued.end(2))   # "Named InsuredWINSLOW"
                g.label = glued.group(1)
                found.append(g)
    for cell in cell_list:
        if NAME_LABEL.search(cell.text) and len(cell.text) < 45 and len(cell.text.split()) <= 5 \
                and not re.search(r"\d", cell.text):
            # the name under its label, or beside it: "Named Insured(s):  Redhaven Properties LLC"
            # - beside it only after a colon: "Named Insured  |  Primary Residence"
            # without one is two column headings, not a label and its value
            right = min((c for c in cell_list if c.row == cell.row and c.rect.x0 > cell.rect.x1),
                        key=lambda c: c.rect.x0, default=None) if cell.text.rstrip().endswith(":") else None
            for cand in (_below(cell, cell_list, max_gap=3.2), right):
                if cand is not None and _looks_like_name(cand.text):
                    names[id(cand)] = (cand, cell.text)
            cand = _below(cell, cell_list, max_gap=3.2)
            for _ in range(4):                    # a second name stacked under the first
                cand = _below(cand, cell_list) if cand is not None else None
                if cand is None or not _looks_like_name(cand.text):
                    break
                names.setdefault(id(cand), (cand, cell.text))
        # "Name:  Juno Prentice", "Named Insured  VANTAGE CONTRACTING"
        left = _left(cell, cell_list)
        if left is not None and NAME_BESIDE.match(_plain(left.text)) and _looks_like_name(cell.text):
            names.setdefault(id(cell), (cell, left.text))
        # a column of names under its heading: "DRIVER NAME" over "MEGHAN", "PETER"
        if NAME_COLUMN.match(_plain(cell.text)):
            cand = _below(cell, cell_list, max_gap=3.2)
            while cand is not None and id(cand) not in names and (
                    _looks_like_name(cand.text) or _lone_name(cand.text)):
                names[id(cand)] = (cand, cell.text)
                cand = _below(cand, cell_list, max_gap=2.5)
    # a list of drivers is one name per line under its label ("Listed
    # Drivers:"): every name in it, not only the first
    for cell in cell_list:
        if DRIVER_LABEL.search(cell.text) and len(cell.text) < 45 and len(cell.text.split()) <= 5 \
                and not re.search(r"\d", cell.text):
            cand = _below(cell, cell_list, max_gap=3.2)
            while cand is not None and _looks_like_name(cand.text) and id(cand) not in names:
                names[id(cand)] = (cand, cell.text)
                cand = _below(cand, cell_list)
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
        words = {w.lower().strip(",.") for w in cell.text.split()}
        if words <= COMPANY_WORDS:
            continue                          # "AGENCY LLC": no name in it
        # two people printed together ("Juno Prentice & Hazel Vance") are two names
        for s, e in _name_spans(cell.text):
            part = {w.lower().strip(",.") for w in cell.text[s:e].split()}
            f = Found("company" if part & COMPANY_WORDS else "person", cell, s, e)
            f.label = label or ""
            found.append(f)
    # an agency printed with its agency code: "BURKHARD EVANS INC - #909255",
    # the code wrapped under it ("... BROKERAGE INC -" / "#913886"), or set in
    # the next column ("GRANITE ROW  |  - #495001")
    for cell in cell_list:
        pieces = []
        m = CODED_NAME.fullmatch(cell.text)
        if m and _looks_like_name(m.group(1)):
            pieces = [(cell, *m.span(1)), (cell, *m.span(2))]
        m = re.fullmatch(r"(.+?)\s+-\s*", cell.text)
        below = _below(cell, cell_list) if m else None
        if m and below is not None and CODE_ONLY.fullmatch(below.text) and _looks_like_name(m.group(1)):
            pieces = [(cell, *m.span(1)), (below, *CODE_ONLY.fullmatch(below.text).span(1))]
        m = DASH_CODE.fullmatch(cell.text)
        left = _left(cell, cell_list) if m else None
        if m and left is not None and _looks_like_name(left.text):
            pieces = [(left, 0, len(left.text)), (cell, *m.span(1))]
        elif m and left is not None:
            # the name at the end of a cell run into the column before it:
            # "Policy Discounts GRANITE ROW"
            t = re.search(r"(?:^|\s)([A-Z][A-Z&.'-]*(?:\s+[A-Z][A-Z&.'-]*){1,4})\s*$", left.text)
            if t and t.start(1) > 0 and not left.text[:t.start(1)].strip().isupper() \
                    and _looks_like_name(t.group(1)):
                pieces = [(left, *t.span(1)), (cell, *m.span(1))]
        def free(c, s, e):
            return not any(g.cell is c and g.start < e and s < g.end for g in found)
        if not pieces or not free(*pieces[0]):
            continue
        name = Found("company", *pieces[0])      # a name with an agency code is an agency
        name.label = ""
        # the wholesaler under "Contracted Agency:" is not the policy's agent
        up = _above(pieces[0][0], cell_list, max_gap=3.5, x_tol=60)
        if up is not None and re.search(r"\bcontracted\b", up.text, re.I):
            name.aside, name.label = True, up.text.strip()
        found.append(name)
        if free(*pieces[1]):
            code = Found("digits", *pieces[1])
            code.label = pieces[0][0].text[pieces[0][1]:pieces[0][2]]
            found.append(code)
    # a label and the name it introduces in one cell: "INSURED JANET DANFORTH"
    for cell in cell_list:
        m = LABELLED_NAME.search(cell.text)
        if m and _looks_like_name(m.group(2)) and not any(
                g.cell is cell and g.start < m.end(2) and m.start(2) < g.end for g in found):
            f = Found("person", cell, *m.span(2))
            f.label, f.aside = m.group(1), True    # replaced; the mailing block names the insured
            found.append(f)

    # who a name-and-address block belongs to
    for f in found:
        if f.kind not in ("person", "company") or f.aside:
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
    block = [f for f in found if f.kind == "person" and not f.aside and any(
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


def _lone_name(text):
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
UNTYPED_STREET = re.compile(r"[1-9]\d{0,5}\s+[A-Za-z][A-Za-z .'#-]*")   # not "05 SAAB 9-3 ARC"
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
        if right is not None and id(right) not in held and _lone_name(right.text) \
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
            if UNTYPED_STREET.fullmatch(text) and id(cell) not in held:
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
        # never about a whole year: a one-year term's start would land on its
        # own end, and the synthetic dates would repeat the original ones
        self.days = vals.choice([-1, 1]) * vals.integer(45, 540)
        while abs(abs(self.days) % 365.25 - 182.6) > 175:
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
        if f.kind in ("id", "digits"):
            # one identifier, one replacement, wherever and however it is
            # printed: "103-194-455" and the ID card's "103194455" alike
            base = f.key or f.text
            ident = re.sub(r"\D", "", base) if re.fullmatch(r"[\d\s-]+", base) \
                else re.sub(r"\s", "", base).lower()
            key = ("ident", ident)
            if key not in self.memo:
                self.memo[key] = self._id(f.text)
            chars = iter(re.sub(r"[^A-Za-z0-9]", "", self.memo[key]))
            return "".join(next(chars, c) if c.isalnum() else c for c in f.text)
        key = (f.kind, f.key or _key(f.text))
        if key not in self.memo:
            self.memo[key] = getattr(self, "_" + f.kind)(f.whole or f.text)
        new = self.memo[key]
        if f.part is not None and f.split == "month":   # "August" / "26, 2027"
            month, _, rest = new.partition(" ")
            return month if f.part == 0 else rest
        if f.part is not None:               # one line of a wrapped date
            head, _, year = new.rpartition(" ")
            return head.rstrip(",") if f.part == 0 else year
        if f.no_zip:
            new = re.sub(r"\s+\d{5}(?:-\d{4})?$", "", new)
        if f.kind == "date" and f.key and _key(f.text) != f.key:
            return new                       # a garbled copy: print the date cleanly
        return _case_like(new, f.text)

    def avoid(self, dates):
        """Choose the shift again until no original date lands on another:
        with April 9 and August 9 both printed, a 122-day shift would make
        the new April date the original August one."""
        dates = {d for d in (_date_of(t) for t in dates) if d is not None}
        for _ in range(60):
            if not dates or not {d + timedelta(days=self.days) for d in dates} & dates:
                return
            self.days = self.v.choice([-1, 1]) * self.v.integer(45, 540)

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
            if len(words) == 1:               # "MEDINA": one word for one word
                return self.v.choice(SURNAME)
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
        sep = "." if "." in old else "-"      # a typographic dash is drawn as a plain one
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


def build_gold(found, index, carrier, lob_title, pdf_name, pages, page_text, cells=None):
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
        # down the lines of the name's own page - a cell at the same place on
        # another page is no part of this block - stepping past a short label
        # set in the block ("Residence Premises") and a name's own second line
        # ("BROKERAGE INC"), and stopping at a sentence
        pool = (cells or {}).get(f.cell.page) or [x.cell for x in found if x.cell.page == f.cell.page]
        for _ in range(8):
            cell = _below(cell, pool, max_gap=3.0 if cell is f.cell else 1.8)
            if cell is None or (len(cell.text.split()) > 6 and id(cell) not in by_cell):
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
    # a long number is found again with a label or prefix run into it:
    # "Policy Number085121419", "ER78202066"
    long_digits = {k for k, kind in kinds.items() if kind in ("id", "digits")
                   and re.fullmatch(r"\d{7,}", k.replace(" ", ""))}
    if not kinds:
        return
    # a name can be run into the word before it ("Prepared forMartin
    # Lindqvist"); a lowercase-to-capital join is a boundary for names only
    glued = r"(?:(?<![A-Za-z0-9])|(?-i:(?<=[a-z])(?=[A-Z]))%s)" % "".join(
        "|(?<=%s)" % re.escape(m) for m in sorted(marks))
    # a name or address set in a text layer with no spaces or with commas for
    # them - "BURKHARDEVANSINC", "ROBERT,A,QUEEN" - is the same value
    # and a name run into the word after it ("Elena VaseyMarried Male Driver")
    glued_end = r"(?:(?![A-Za-z0-9])|(?-i:(?<=[a-z])(?=[A-Z])))"
    loose = {"person", "company", "pobox", "street", "cityline"}
    canon = {re.sub(r"[\s,-]", "", k): k for k in sorted(kinds, key=len)}

    def words(k):
        if k in long_digits:              # "23101304" printed "23 10 13 04" too
            return r"\s?".join(re.escape(c) for c in k.replace(" ", ""))
        # an all-digit identifier printed with or without its dashes:
        # "103-194-455" on the declarations is "103194455" on the ID card
        groups = re.split(r"[\s-]+", k)
        if kinds[k] in ("id", "digits") and len(groups) >= 2 and all(g.isdigit() for g in groups) \
                and len("".join(groups)) >= 8:
            return r"\s*-?\s*".join(groups)     # "37-3001-144", "37 - 3001 - 144", "37 3001 144"
        sep = r"[\s,]*" if kinds[k] in loose and len(k.split()) >= 2 and len(k) >= 8 else r"\s+"
        return sep.join(map(re.escape, k.split()))
    pattern = re.compile("|".join(
        (glued if kinds[k] in ("person", "company") else r"(?<!\d)" if k in long_digits
         else r"(?<![A-Za-z0-9])")
        + words(k) + (r"(?!\d)" if k in long_digits
                     else glued_end if kinds[k] in ("person", "company")
                     else r"(?![A-Za-z0-9])")
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
                if full not in kinds:                  # matched without its spaces, dashes or with commas
                    full = canon.get(re.sub(r"[\s,-]", "", full))
                    if full is None:
                        continue
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
                rest = full[len(head) + 1:]
                below = _below(cell, cell_list)
                if below is None or _key(below.text) != rest:
                    # a right-aligned block wraps flush right: "Patriotic
                    # Insurance Group" over "Brokerage"
                    r = cell.rect
                    below = next((c for c in cell_list if c is not cell and _key(c.text) == rest
                                  and abs(c.rect.x1 - r.x1) < 6 and 0 <= c.rect.y0 - r.y1 < 1.8 * r.height),
                                 None)
                if below is None or taken.get(id(below)) or _key(below.text) != rest:
                    continue
                for n, c in enumerate((cell, below)):
                    f = Found(kind, c, 0, len(c.text))
                    f.key, f.blank = full, n > 0
                    f.label = _label_for(f, cell_list)
                    found.append(f)
                    taken.setdefault(id(c), []).append((0, len(c.text)))
                break
        # and the front of a known name, cut off mid-word where the rest of
        # the line was blacked out: "PATRIOTIC INSU" of "PATRIOTIC INSURANCE
        # GROUP BROKERAGE INC"
        for cell in cell_list:
            head = _key(cell.text)
            if len(head) < 10 or " " not in head or taken.get(id(cell)):
                continue
            full = next((k for k, kind in kinds.items() if kind in ("person", "company")
                         and k.startswith(head) and k != head), None)
            if full is not None:
                f = Found(kinds[full], cell, 0, len(cell.text))
                f.key = full
                f.label = _label_for(f, cell_list)
                found.append(f)
                taken.setdefault(id(cell), []).append((0, len(cell.text)))


def _vertical(page, swapped):
    """Replaced values in text set vertically - a date stamped up the page
    margin. The layout reads rows of horizontal text, so such a line is
    rewritten here as a whole: removed, and drawn again in its own direction
    with every replaced value in it swapped."""
    lines = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            dx, dy = line["dir"]
            if abs(dx) > 0.2 or not line["spans"]:
                continue                                  # horizontal: done already
            text = "".join(c["c"] for s in line["spans"] for c in s["chars"])
            new = text
            for old, rep in swapped:
                new = new.replace(old, rep)
            if new != text:
                lines.append((fitz.Rect(line["bbox"]), line["spans"][0], dy, new))
    if not lines:
        return
    for rect, *_ in lines:
        page.add_redact_annot(rect, fill=False)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
    for rect, span, dy, new in lines:
        page.draw_rect(rect, color=None, fill=(1, 1, 1), overlay=True)
        c = span.get("color", 0)
        page.insert_text(fitz.Point(span["origin"]), new, fontname="helv", fontsize=span["size"],
                         rotate=90 if dy < 0 else 270,
                         color=((c >> 16 & 255) / 255, (c >> 8 & 255) / 255, (c & 255) / 255))


def _mop_up(page, swaps):
    """The last pass: an original value still in the page's text - a copy
    the layout never read whole, in text overprinted by another line, or a
    scan's layer split into pieces - is removed, covered in the paper colour
    and drawn anew, found by the value itself rather than by layout."""
    hits = []
    for old, new in swaps:
        for r in page.search_for(old):
            if r.width > 1 and r.height > 1:
                hits.append((r, new))
    if not hits:
        return
    shade = page.get_pixmap(dpi=overlay.BG_DPI, colorspace=fitz.csRGB, annots=False)
    fills = [overlay._paper(shade, r) for r, _ in hits]
    for r, _ in hits:
        page.add_redact_annot(r, fill=False)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
    for (r, new), fill in zip(hits, fills):
        page.draw_rect(r + (-0.5, -0.5, 0.5, 0.5), color=None, fill=fill, overlay=True)
        size = max(4.0, r.height * 0.8)
        width = fitz.get_text_length(new, fontname="helv", fontsize=size) or 1.0
        origin = fitz.Point(r.x0, r.y1 - 0.2 * r.height)
        page.insert_text(origin, new, fontname="helv", fontsize=size,
                         morph=(origin, fitz.Matrix(min(1.0, r.width / width), 1)))


def _moves_on_edit(source_pdf, n):
    """Does removing one word from page ``n`` move the page's other words?

    Some producers write content that MuPDF cannot rewrite faithfully: a
    redaction there relocates the text instead of deleting it, so an old
    value would survive, somewhere else. Tried on a throwaway copy."""
    doc = fitz.open(str(source_pdf))
    try:
        page = doc[n]
        words = page.get_text("words")
        target = next((w for w in words if re.search(r"\d", w[4])), words[0] if words else None)
        if target is None:
            return False
        page.add_redact_annot(fitz.Rect(target[:4]), fill=False)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
        before = {(w[4], round(w[0]), round(w[1])) for w in words if w is not target}
        after = {(w[4], round(w[0]), round(w[1])) for w in page.get_text("words")}
        return len(before - after) > max(2, 0.02 * len(before))
    except Exception:
        return False
    finally:
        doc.close()


def _flatten(doc, n):
    """Replace page ``n`` with its image under an invisible layer of its
    words, each set at its own place and printed width - a page the
    generator can then edit as it edits a scan."""
    page = doc[n]
    words = page.get_text("words")
    # each word at its span's own size and baseline: a producer's word boxes
    # can be taller than its line pitch, and sizes drawn from them overlap
    spans = [(fitz.Rect(s["bbox"]), s["size"], s["origin"][1])
             for b in page.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]]
    pix = page.get_pixmap(dpi=300)
    tmp = fitz.open()
    new = tmp.new_page(width=page.rect.width, height=page.rect.height)
    new.insert_image(new.rect, pixmap=pix)
    for x0, y0, x1, y1, text, *_ in words:
        mid = fitz.Point((x0 + x1) / 2, (y0 + y1) / 2)
        span = next((s for s in spans if s[0].contains(mid)), None)
        size = span[1] if span else max(4.0, (y1 - y0) * 0.8)
        width = fitz.get_text_length(text, fontname="helv", fontsize=size) or 1.0
        origin = fitz.Point(x0, span[2] if span else y1 - 0.22 * (y1 - y0))
        new.insert_text(origin, text, fontname="helv", fontsize=size, render_mode=3,
                        morph=(origin, fitz.Matrix((x1 - x0) / width, 1)))
    doc.delete_page(n)
    doc.insert_pdf(tmp, start_at=n)
    tmp.close()


def _not_values(pages):
    """Drop what was taken for identifying values but identifies no one.

    * a "name" whose words the document prints in lower case in its running
      text: "Residence Premises" (on "the residence premises"), a defined
      term such as "Shareholder Derivative Demand Investigation Costs";
    * an identifier repeated in the footer of several pages with no number
      label beside it: the document's form code ("LPL 39500-NY-1116")."""
    lower, footer = set(), {}
    for page, ink, matrix, visible, cell_list, found in pages:
        height = page.rect.height
        for c in cell_list:
            lower |= set(re.findall(r"(?<![A-Za-z])[a-z]{4,}(?![A-Za-z])", c.text))
        for f in found:
            if f.kind in ("id", "digits") and f.rect is not None and f.rect.y0 > 0.9 * height:
                footer.setdefault(_key(f.text), set()).add(page.number)
    for *_, found in pages:
        keep = []
        for f in found:
            words = [w for w in re.findall(r"[A-Za-z]{4,}", f.text) if w.lower() not in COMPANY_WORDS]
            if f.kind in ("person", "company") and words and \
                    sum(w.lower() in lower for w in words) * 2 >= len(words) + 1:
                continue
            if f.kind in ("id", "digits") and len(footer.get(_key(f.text), ())) >= 2 \
                    and not ID_LABEL.search(f.label or ""):
                continue
            keep.append(f)
        found[:] = keep


def _key(text):
    return " ".join(text.lower().split())


def _carrier_marks(carrier):
    """The distinctive words of a carrier's name: "utica" in "Utica First
    Insurance Company", never "insurance" or "mutual"."""
    generic = {"insurance", "company", "mutual", "group", "assurance", "casualty",
               "underwriters", "surplus", "cooperative", "national", "american",
               "general", "services", "insurers", "indemnity", "specialty", "fire",
               "property", "preferred", "corp", "corporation", "inc", "llc", "first"}
    marks = {w for w in re.findall(r"[a-z]{4,}", carrier.lower()) if w not in generic}
    # and a carrier known by its initials: "CNA", "NCIC", "DMIC"
    return marks | {w.lower() for w in re.findall(r"\b[A-Z]{3,5}\b", carrier)}


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
        words = set(re.findall(r"[a-z]{3,}", f.text.lower()))
        first = (re.findall(r"[a-z]{3,}", f.text.lower()) or [""])[0]
        if f.kind == "company" and marks & words or f.kind == "person" and words and words <= marks \
                or f.kind in ("person", "company") and first in marks:   # "CNA Granite Row"
            drop.add(id(f))
            heads.append(f.cell)
    # the carrier's name printed as plain text heads its address too: the
    # remittance block under "PROGRESSIVE", or "One Tower Square, Hartford"
    # two lines under "TRAVCO INSURANCE COMPANY"
    for cell in cell_list:
        words = cell.text.split()
        if 0 < len(words) <= 6 and not any(g.cell is cell for g in found) and (
                marks & set(re.findall(r"[a-z]{3,}", cell.text.lower()))
                or INSURER_NAME.search(cell.text)):
            heads.append(cell)
    for head in heads:
        cell = head
        for _ in range(3):                  # and the address printed under it
            cell = _below(cell, cell_list)
            if cell is None or NAME_LABEL.search(cell.text) or _looks_like_name(cell.text) \
                    and not (marks & set(re.findall(r"[a-z]{3,}", cell.text.lower()))):
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


def _vocabulary(text):
    """How often each word is printed in the document."""
    counts = {}
    for w in re.findall(r"[a-z]+", text.lower()):
        counts[w] = counts.get(w, 0) + 1
    return counts


def _unglue(text, vocab, titled=False):
    """Words a scan's OCR ran together, set apart again: "combinedsingle-
    limiteachaccident", "LiabilityTo", "LossReplacement/PurchasePrice".
    A run is split only into words the document prints elsewhere on their
    own - each at least as often as the run itself. Web addresses,
    e-mails and anything with a digit are left as printed. A capitalised
    run ("Pleaserefer") is split only in prose (``titled``): in a field it
    may be a name - "Timberline" is not "Timber line"."""
    def split(run):
        low = run.lower()
        if len(low) < 8:
            return run
        if not titled and run[0].isupper() and not re.search(r"[a-z][A-Z]", run):
            return run
        best = {0: []}
        for i in range(1, len(low) + 1):
            for j in range(max(0, i - 20), i):
                word = low[j:i]
                if word == low:
                    continue                      # the run is not its own part
                if j in best and (vocab.get(word, 0) >= 1 and (len(word) >= 3 or word in
                                  ("a", "an", "by", "to", "of", "in", "on", "or", "at", "is", "be", "if", "as"))):
                    cand = best[j] + [(j, i)]
                    if i not in best or len(cand) < len(best[i]):
                        best[i] = cand
        parts = best.get(len(low))
        if not parts or len(parts) < 2:
            return run
        # the run printed as a word ("liabilityto" in a scan's layer and again
        # in its OCR re-read) yields only to parts printed at least as often;
        # "MyTravelers" stays whole where "my" is rare
        if min(vocab.get(low[a:b], 0) for a, b in parts) < vocab.get(low, 0):
            return run
        return " ".join(run[a:b] for a, b in parts)

    out = []
    for token in re.split(r"(\s+)", text):
        if not token.strip() or re.search(r"\d|@|www|https?:|\.(?:com|net|org|app|gov)(?![a-z])",
                                          token, re.I):
            out.append(token)
            continue
        # "policy.Please": a sentence run into the next
        token = re.sub(r"(?<=[a-z]{2})\.(?=[A-Z][a-z])", ". ", token)
        out.append(re.sub(r"[A-Za-z]+", lambda m: split(m.group(0)), token))
    return "".join(out)


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
    if f.start > 0 and not f.cell.text[f.start - 1].isspace():
        return "left"                     # set against what precedes it: "1-800-876-5581"
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
        # a page whose content cannot be edited in place - removing one word
        # moves the others - is replaced by its image and a text layer
        flattened = set()
        for n in range(len(doc)):
            if _moves_on_edit(source_pdf, n):
                _flatten(doc, n)
                flattened.add(n)
        read = {}
        turned = _upright(doc, read=read)
        found_all, plans, pages = [], [], []
        recovered, scanned = {}, set()
        for page in doc:
            ink = overlay.Ink(page)
            invisible = overlay.invisible_text(page)
            visible = not invisible
            # a flattened page's layer was written in place: nothing to fit
            matrix = fitz.Identity if visible or page.number in flattened                 else overlay.calibrate(page, ink)
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
        _not_values(pages)
        _sweep(pages, _carrier_marks(source_pdf.parent.parent.name))
        faker = Faker(vals, [f.text for *_, found in pages for f in found if f.kind in PII])
        faker.avoid([f.whole or f.text for *_, found in pages for f in found if f.kind == "date"])
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
                # (a scan's layer sits a few points off its print: there the
                # next word's box would cut the cover short of the old ink)
                if visible and after < len(f.cell.text) and f.cell.chars[end - 1] is not None:
                    gap = f.cell.chars[after].box.x0 - f.cell.chars[end - 1].box.x1
                    room = f.cell.chars[after].box.x0 - max(1.5, 0.8 * gap)
                reps.append(overlay.Replacement(
                    page=page.number, old=f.text + tail, new=f.new + tail,
                    visible_rect=f.cell.span_rect(f.start, end),
                    ocr_rect=f.cell.span_rect(f.start, end, ocr=True),
                    font=overlay.base14(first.font, visible), face_known=visible,
                    glued=f.start > 0 and f.cell.text[f.start - 1] not in " ",
                    color=first.color if visible else 0,
                    align=_alignment(f, cell_list), room=room,
                    follows=bool(f.cell.text[end:].strip(" ,;.-–"))))
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
        personal = {f.text for f in found_all if f.kind in PII or f.kind == "date"}
        swapped = sorted({f.text: f.new for f in found_all
                          if f.new and f.new != f.text and not f.blank and f.part is None}.items(),
                         key=lambda kv: -len(kv[0]))
        for page, reps, ink, matrix in plans:
            overlay.apply(page, reps, ink, matrix)
            if page.number in scanned:
                reps += _second_look(page, every)
            if page.number in recovered:
                recover.write_back(page, recovered[page.number],
                                   [r.visible_rect for r in reps], swapped)
            _vertical(page, swapped)
            _mop_up(page, [(o, n) for o, n in swapped if len(o) >= 5 and o in personal])
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
                                    index, carrier, title, built.pdf.name, built.pages, whole,
                                    {cl[0].page: cl for *_, cl, _ in pages if cl})   # the document is closed by now
        structure.finish(structure.merge(gold, laid_out), schema)
        vocab = _vocabulary(whole)
        for _, fld in _walk_fields(gold):
            if isinstance(fld.get("raw"), str) and fld["confidence"]["source"] == "deterministic":
                fixed = _unglue(fld["raw"], vocab)
                if fixed != fld["raw"]:
                    if fld.get("parsed") == fld["raw"]:
                        fld["parsed"] = fixed
                    fld["raw"] = fixed
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
        # a label is copied off the source page, and can itself be a value
        # that was replaced - the insured's street over its city line
        swaps = sorted({(f.key or f.text): f.new for f in found_all
                        if f.new and f.new != f.text and not f.blank and f.part is None
                        and (f.kind in PII or f.kind == "date")}.items(),
                       key=lambda kv: -len(kv[0]))
        for item in unmapped:
            for old, new in swaps:
                item["label"] = re.sub(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])"
                                       % r"\s+".join(map(re.escape, old.split())),
                                       lambda m, new=new: new, item["label"], flags=re.I)
            item["page_ref"] = [i + 1 for i, t in enumerate(texts)
                                if pageref.on_page(pageref._norm(item["value"]), t)]

        if "text_sections" in schema.merged["properties"]:
            # the printed paragraphs no field holds, in the replaced wording
            gold["text_sections"] = prose.text_sections(digital, {f.new for f in found_all if f.new})
            for sec in gold["text_sections"].values():
                sec["raw_text"] = _unglue(sec["raw_text"], vocab, titled=True)
            blob = " ".join(s["raw_text"] for s in gold["text_sections"].values()).lower()
            built.problems += ["source value %r survived into text_sections" % t
                               for t in sorted({f.key or f.text for f in found_all
                                                if f.kind in PII and f.new != f.text and not f.blank
                                                and pageref.on_page(pageref._norm(f.key or f.text), blob)})]

        stats = scan_pdf(digital, built.pdf, scan_by_key("high_quality"), seed=seed)
        if built.pdf.stat().st_size > SHARE_LIMIT:
            # too large to share: the same scan, stored compactly
            stats = scan_pdf(digital, built.pdf, HIGH_QUALITY_COMPACT, seed=seed)
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
        # and nothing the gold carries may be an original value either
        written = json.dumps(gold, indent=2, ensure_ascii=False)
        flat = pageref._norm(written)
        built.problems += ["source value %r is in the gold" % old for old, _ in swaps
                           if len(old) >= 4 and pageref.on_page(pageref._norm(old), flat)]
        built.gold.write_text(written, encoding="utf-8")
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
