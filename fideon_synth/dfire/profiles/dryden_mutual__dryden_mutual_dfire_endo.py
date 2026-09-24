"""
Dryden Mutual Insurance Company - Standard Landlords Package Policy, Policy Change
Endorsement ("Amended Declarations Page as of <date>").

Eight pages: p1 the change page (transaction, premium adjustment, prior / change /
revised annual premium), p2 the location summary, then per location a coverage page,
a forms page and a premium computation (p3-5 = Location 1, p6-8 = Location 2), all
"as of" the change date.  The change is a protection-class amendment that lowers
the premium, so the revised class is Protected or Semi-Protected and the premium
drops by 5-16 %; the pro-rata adjustment is the change times the days left in the
term (or the whole change when the adjustment type is Flat).

GAPS: none; every printed item has a canonical leaf (prose is captured in text_sections).
"""

from datetime import datetime

from ..engine import date_fv, fv, money
from . import _dryden_common as X

SOURCE = "Dryden Mutual/dwelling_fire/dryden_mutual_dfire_endo.pdf"

GAPS = []

S = {
    "pages": {"summary": 2, "loc1": (3, 4, 5), "loc2": (6, 7, 8)},
    "ins_name": "Marguerite Ellery & Noelle Norcross",
    "ins_l1": "PO Box 236",
    "ins_city_line": "Blue Mountain Lake, NY 12812-0236",
    "policy_no": "LPP00185357-01",
    "file_no": "L653169",
    "eff": "06/01/2026", "exp": "06/01/2027", "vc": "08/03/2026",
    "ag_name": "Stable Rock Insurance Agency LLC",
    "ag_code": "#760", "ag_code_prefix": "#",
    "ag_l1": "PO Box 329", "ag_city_line": "Inlet, NY 13360-0329", "ag_phone": "(845) 610-5700",
    "agency_w": {"name": {1: 169, 2: 168, 3: 168, 6: 168},
                 "l1": {1: 56, 2: 56}, "city": {1: 96, 2: 96},
                 "bill": {1: 175, 2: 174}},
    "from_pages": {1, 3, 6},
    "meda": "50,000", "c_prem": "47.00", "hydrant": "1000 Feet or Less",
    "total": "3,278.00",
    1: {"a": "500,000", "b": "50,000", "d": "50,000", "year": "1959", "base": "1,963.00",
        "fl10": "39.00", "dfl": "196.00", "alarm": "-39.00", "dcr": "-334.00",
        "total": "1,990.00",
        "line": "221 State Route 28, (Main House), Raquette Lake, NY 13436-1903"},
    2: {"a": "300,000", "b": "30,000", "d": "30,000", "year": "1950", "base": "1,207.00",
        "fl10": "24.00", "dfl": "121.00", "alarm": "-24.00", "dcr": "-205.00",
        "total": "1,288.00",
        "line": "221 State Route 28, (Garage With Apartment), Raquette Lake, NY 13436-1903"},
}

CHANGE = "Amended Protection Class Location #1 and Location #2"

REPLACE = X.build_replace(S, "endo") + [
    ("07/27/2026", "{chg}", {"leak": True}),
    ("2", "{term_seq}", {"exact": True, "page": 1, "leak": False}),
    ("$3,632.00", "{prior_usd}", {"exact": True}),
    ("-$354.00", "{chg_usd}", {"exact": True}),
    ("$3,278.00", "{rev_usd}", {"exact": True}),
    ("-$299.70", "{adj_usd}", {"exact": True}),
    ("Pro-Rate", "{adj_type}", {"exact": True, "leak": False}),
]

STATIC = [r"13053", r"^\$0\.00$"]


def draw(v, C):
    d = X.draw_core(v, C, endo=True)
    total = d["total"]
    prior = total + round(total * v.rng.uniform(0.05, 0.16))
    chg = total - prior
    exp = datetime.strptime(d["exp"], "%m/%d/%Y")
    when = datetime.strptime(d["chg"], "%m/%d/%Y")
    kind = v.choice(["Pro-Rate", "Pro-Rate", "Flat"])
    adj = round(chg * (exp - when).days / 365.0, 1) if kind == "Pro-Rate" else float(chg)
    d.update(prior=prior, chg_amt=chg, term_seq=str(v.integer(2, 6)), adj_type=kind,
             prior_usd=C.usd(prior), chg_usd=C.usd(chg), rev_usd=C.usd(total), adj_usd=C.usd(adj),
             title="Amended Declarations Page as of %s" % d["chg"])
    return d


def audit(d):
    out = X.audit_core(d)
    if d["prior"] + d["chg_amt"] != d["total"]:
        out.append("prior + change != revised annual premium")
    return out


def gold(d):
    g = X.common_gold(d)
    g["document"] = X.doc_common(
        d, ("Policy Change Endorsement", "Endorsement"), d["title"],
        {"transaction_type": fv("Policy Change Endorsement"),
         "transaction_effective_date": date_fv(d["chg"]),
         "transaction_reason": fv("Amended Protection Class"),
         "summary_of_changes": fv(CHANGE)})
    g["premium"].update(X.summary_premium(d, d["rev_usd"]))
    g["premium"].update({
        "return_premium": money(d["adj_usd"]),
        "fire_fee": fv("N/A"),
        "prior_annual_premium": money(d["prior_usd"]),
        "change_in_annual_premium": money(d["chg_usd"]),
        "prior_fire_fee": money("$0.00"),
        "fire_fee_change": fv("N/A"),
        "revised_fire_fee": money("$0.00"),
        "premium_adjustment_type": fv(d["adj_type"]),
    })
    g["policy"]["term_sequence"] = fv(d["term_seq"], evidence=d["term_seq"])
    return g
