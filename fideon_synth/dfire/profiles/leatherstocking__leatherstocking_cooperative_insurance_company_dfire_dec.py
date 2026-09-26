"""
Leatherstocking Cooperative Insurance Company - "leatherstocking_cooperative_insurance_company_dfire_dec.pdf"

Unredacted two-page Dwelling Fire declaration, new policy: all text is real, so no
overlay tidying is needed.  Section I carries Coverage A and Coverage C each with EC and
VMM, Section II Coverage L, ML-59 and FL-52A, Optional Items ML-WD and Hazardous
Conditions, plus the LCIC-DX canine exclusion block.  The source prints a Property Total
two dollars above its own Coverage Premium / Total; the synthetic schedule ties.  No
mortgagee, terrorism, billing, loss history or state notice is printed.

GAPS (printed but no canonical leaf): the Mail To block (repeats the producer) and the SIGNATURE
box's date (not printed; the signature is keyed).
"""

from . import _leatherstocking as L
from ..engine import fv

SOURCE = L.ROOT + "leatherstocking_cooperative_insurance_company_dfire_dec.pdf"

GAPS = ["Mail To block (repeats the producer name and address)",
        "SIGNATURE / DATE box: no printed name or date (the signature image is keyed)"]

STATIC = list(L.STATIC)
IGNORE_PAIRS = list(L.IGNORE_PAIRS)
FURNITURE = list(L.FURNITURE)

FORMS = (
    "FL-52A (12/98) Trampoline Exclusion, FL-18 (6/96) Intentional Act Exclusion, FL-20 (1/92) "
    "Agreement, FL-83 (02/02) Amendment of Policy Conditions, FL-90 (11/06) Clarification "
    "Endorsement, FMD-1 (12/94) Important Flood Insurance Notice, LCI-11 (4/91) Senior Citizen "
    "Form, PR (3/01) Notice of Privacy Policy, LCI-J (9/17) By-Laws, FL-21 05/10 Suit Against Us "
    "Amendatory Endorsement, FL-1R (1/92) Causes of Loss, ML-WD (1.1) Water Damage-Sewers and "
    "Drains, FL-OLT (1/92) Premises Liability Insurance Coverage Part, ML-59 (6/99) Lead "
    "Exclusion, SM-26 (7/00) Automatic Increase, FL-80 (7/96) Redefinition of Insured, LCIC-DX "
    "(06/23) Exclusion of Canine Related Injuries or Damages")
MODIFIES = ("Coverage A - Residence, Coverage B - Related Private Structures, Coverage D - "
            "Additional Living Expense / Loss of Rent")
L_PREM = {100000: 32, 300000: 54, 500000: 66, 1000000: 80}
usd = L.usd


def draw(v, C):
    d = L.draw_parties(v, C)
    L.draw_term(v, C, d)
    d["policy_no"] = v.policy_number("10-{year}-{5d}", year=d["eff_year"])
    d.update(settle=v.choice(["ACV", "RC", "RC"]),
             constr=v.choice(["Frame", "Masonry", "Masonry Veneer"]),
             protect=v.choice(["Protected", "Semi-Protected", "Unprotected"]),
             classif=v.choice(["Dwelling - 1 Family", "Dwelling - 2 Family"]),
             territory="%02d - All Others" % v.integer(1, 30),
             condition=v.choice(["Unoccupancy", "Vacancy", "Seasonal Occupancy"]),
             deductible=v.choice([500, 1000, 1000, 2500]))
    cov_a = v.limit(90000, 480000, 500)
    cov_c = v.choice([5000, 10000, 15000, 20000, 25000])
    liab = v.choice([100000, 300000, 500000, 1000000])
    p = dict(
        prem_a=round(cov_a / 1000.0 * v.rng.uniform(3.6, 3.8)),
        ec_a=round(cov_a / 1000.0 * v.rng.uniform(0.48, 0.54)),
        vmm_a=round(cov_a / 1000.0 * v.rng.uniform(0.055, 0.065)),
        prem_c=max(1, round(cov_c / 1000.0 * v.rng.uniform(3.1, 3.3))),
        ec_c=max(1, round(cov_c / 1000.0 * 0.2)), vmm_c=max(1, round(cov_c / 1000.0 * 0.2)),
        prem_l=L_PREM[liab], ml59=-v.integer(4, 8), fl52=-v.integer(1, 3),
        mlwd=v.integer(20, 30), haz=round(cov_a / 1000.0 * v.rng.uniform(0.93, 0.95)))
    total = sum(p.values())
    d.update(p, cov_a=cov_a, cov_c=cov_c, liab=liab, total=total,
             cov_a_s=usd(cov_a, False), cov_c_s=usd(cov_c, False), liab_s=usd(liab, False),
             total_s=usd(total), ded_s=usd(d["deductible"]))
    for k in p:
        d[k + "_s"] = usd(p[k])
    return d


def _m(src, key, **opts):
    o = {"exact": True, "leak": False}
    o.update(opts)
    return (src, "{%s}" % key, o)


REPLACE = [
    ("10-2026-16132", "{policy_no}"),
    ("05/06/2026", "{eff}"), ("05/06/2027", "{exp}"),
    # agency block and the "Mail To" block that repeats it
    ("Stable Rock Insurance Agency LLC -", "{agency} -", {"leak": False}),
    ("RBF", "{ag_code}", {"exact": True}),
    ("159 NY - 28", "{ag_street}", {"exact": True}),
    ("Inlet, NY 13360", "{ag_city_line}", {"exact": True}),
    ("(845) 610-5700", "{ag_work}"), ("(845) 610-5705", "{ag_fax}"),
    # named insureds
    ("Marguerite Calloway", "{ins1}", {"exact": True}),
    ("Delphine Underhill", "{ins2}", {"exact": True}),
    ("291 Poplar Point", "{ins_street}", {"exact": True}),
    ("Raquette Lake, NY 13436", "{ins_city_line}", {"exact": True}),
    # property line (one span)
    ("175 Durant Rd", "{prop_street}"),
    ("Blue Mountain Lake NY 12812", "{prop_city} NY {prop_zip}"),
    ("Hamilton County", "{prop_county} County"),
    # Section I
    _m("$234,500", "cov_a_s"), _m("$868.00", "prem_a_s"),
    _m("$120.00", "ec_a_s"), _m("$14.00", "vmm_a_s"),
    _m("$5,000", "cov_c_s"), _m("$16.00", "prem_c_s"),
    _m("$1.00", "ec_c_s", nth=0), _m("$1.00", "vmm_c_s", nth=1),
    # Section II
    _m("$500,000", "liab_s"), _m("$66.00", "prem_l_s"),
    _m("-$5.00", "ml59_s"), _m("-$2.00", "fl52_s"),
    # Optional Items and totals
    _m("$25.00", "mlwd_s"), _m("$221.00", "haz_s"),
    _m("$1,327.00", "total_s"), _m("$1,325.00", "total_s"),
    # rating information (page 2)
    ("$1,000.00", "{ded_s}", {"page": 2, "leak": False}),
    ("RC", "{settle}", {"exact": True, "page": 2, "leak": False}),
    ("Automatic Increase, RC", "Automatic Increase, {settle}", {"page": 2, "leak": False}),
    ("Frame", "{constr}", {"exact": True}),
    ("Semi-Protected", "{protect}", {"exact": True}),
    ("Dwelling - 1 Family", "{classif}", {"exact": True}),
    ("19 - All Others", "{territory}", {"exact": True}),
    ("Unoccupancy", "{condition}", {"exact": True}),
]


def _rows(d):
    rows = [
        L.row("Coverage A - Residence", d["cov_a_s"], d["prem_a"],
              leaf=("property", "coverage_a_dwelling_limit")),
        L.row("EC - Residence", "***", d["ec_a"]),
        L.row("VMM - Residence", "***", d["vmm_a"]),
        L.row("Coverage C - Personal Property", d["cov_c_s"], d["prem_c"],
              leaf=("property", "coverage_c_personal_property_limit")),
        L.row("EC - Personal Property", "***", d["ec_c"]),
        L.row("VMM - Personal Property", "***", d["vmm_c"]),
        L.row("Coverage L - Premises Liability", d["liab_s"], d["prem_l"],
              leaf=("liability", "coverage_l_premises_liability_limit"), basis="Each Occurrence"),
        L.row("ML-59 - Lead Exclusion", "***", d["ml59"], form="ML-59"),
        L.row("FL-52A Trampoline Exclusion", "***", d["fl52"], form="FL-52A"),
    ]
    opt = [L.row("ML-WD - Water Backup-Sewers and Drains", "***", d["mlwd"], form="ML-WD"),
           L.row("Hazardous Conditions - Occupancy", "***", d["haz"])]
    return rows, opt


def audit(d):
    rows, opt = _rows(d)
    return L.audit_rows(d, rows, opt)


def gold(d):
    rows, opt = _rows(d)
    S = {
        "lob": "Dwelling Fire", "transaction": "New Policy", "rows": rows, "optional": opt,
        "form_name": "Basic Form (FL-1)", "forms_text": FORMS,
        "notes": [
            {"name": "SM-26 Automatic Increase, %s" % d["settle"], "form": "SM-26",
             "notes": L.MODIFIES + MODIFIES},
            {"name": "LCIC-DX Exclusion of Canine Related Injuries or Damages", "form": "LCIC-DX"},
        ],
        "dwelling": {"occupancy_classification_code": fv(d["classif"]),
                     "hazardous_conditions_occupancy": fv(d["condition"]),
                     "rating_zone": fv("All Other")},
        "deductibles": [
            L.deductible_entry(d, "all property coverages", evidence="all property coverages",
                               notes=L.DISCLAIMER),
            L.deductible_entry(d, "Coverage C - Personal Property",
                               evidence="Coverage C - Personal Property", derived_applies=True),
        ],
    }
    return L.build_gold(d, S)
