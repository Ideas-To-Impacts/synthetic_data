"""
Dryden Mutual Insurance Company - Standard Landlords Package Policy, Declaration Page.

Seven pages: summary (p1), then per location a coverage declaration, a supplemental
forms page and an annual premium computation (p2-4 = Location 1, p5-7 = Location 2).
The source is already clean (no redaction artefacts).  The agency block is right
aligned, so replacement text is padded on the left to keep that edge.

dwelling_fire.* describes Location 1; both locations are stated under locations[].

GAPS: none; every printed item has a canonical leaf (prose is captured in text_sections).
"""

from ..engine import derived, fv, money
from . import _dryden_common as X

SOURCE = "Dryden Mutual/dwelling_fire/dryden_mutual_dfire_dec.pdf"

GAPS = []

S = {
    "pages": {"summary": 1, "loc1": (2, 3, 4), "loc2": (5, 6, 7)},
    "ins_name": "Marguerite Ellery & Noelle Norcross",
    "ins_l1": "PO Box 236",
    "ins_city_line": "Blue Mountain Lake, NY 12812-0236",
    "policy_no": "LPP00185357-01",
    "file_no": "L653169",
    "eff": "06/01/2026", "exp": "06/01/2027", "vc": "06/03/2026",
    "ag_name": "Patriotic Insurance Group Brokerage",
    "ag_code": "# 760", "ag_code_prefix": "# ",
    "ag_l1": "159 NY-28", "ag_city_line": "Inlet, NY 13360", "ag_phone": "(845) 610-5700",
    "agency_w": {"name": {1: 175, 2: 175, 5: 175}, "l1": {1: 48}, "city": {1: 71},
                 "bill": {1: 174}},
    "from_pages": {1, 2, 5},
    "meda": "50,000", "c_prem": "51.00", "hydrant": "Greater than 1000 Feet",
    "total": "3,632.00",
    1: {"a": "500,000", "b": "50,000", "d": "50,000", "year": "1959", "base": "2,194.00",
        "fl10": "44.00", "dfl": "219.00", "alarm": "-44.00", "dcr": "-373.00",
        "total": "2,209.00",
        "line": "221 State Route 28, (Main House), Raquette Lake, NY 13436-1903"},
    2: {"a": "300,000", "b": "30,000", "d": "30,000", "year": "1950", "base": "1,348.00",
        "fl10": "27.00", "dfl": "135.00", "alarm": "-27.00", "dcr": "-229.00",
        "total": "1,423.00",
        "line": "221 State Route 28, (Garage With Apartment), Raquette Lake, NY 13436-1903"},
}

REPLACE = X.build_replace(S, "dec")

STATIC = [r"13053"]


def draw(v, C):
    return X.draw_core(v, C, endo=False)


def audit(d):
    return X.audit_core(d)


def gold(d):
    g = X.common_gold(d)
    g["document"] = X.doc_common(
        d, ("Declaration Page", "Declaration"), "Declaration Page",
        {"transaction_type": fv(d["trans"]),
         "transaction_effective_date": _date(d["eff"])})
    prem = X.summary_premium(d, d["total_s"])
    g["premium"].update(prem)
    return g


def _date(s):
    from ..engine import date_fv
    return date_fv(s)
