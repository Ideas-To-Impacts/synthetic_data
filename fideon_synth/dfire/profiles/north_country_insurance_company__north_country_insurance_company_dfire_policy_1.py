"""
North Country Insurance Company - "Fire Policy Declaration" (policy_1), New
Business, two pages, text-only, Agent Copy. Dwelling with Cov A-D, L and M.

GAPS (printed but no canonical leaf): "Structure: Main Residence"; "Fire Alarm";
"Usage" when not seasonal; the "Loc #/Bldg #" column as a standalone value;
"Limits and deductibles stated above are not in addition to those on specific
forms." wording; the two policy-period boilerplate paragraphs; "Process Date"
is filed as document.issue_date.
"""

from ..engine import amt, derived, fv, money
from . import _ncic_common as N

SOURCE = "North Country Insurance Company/dwelling_fire/north_country_insurance_company_dfire_policy_1.pdf"

GAPS = ["Structure: Main Residence", "Fire Alarm (smoke alarm / central station)",
        "Usage (Primary / Secondary) when not seasonal",
        "Limits and deductibles stated above are not in addition to those on specific forms.",
        "Policy period / coverage-applies boilerplate paragraphs",
        "Loc #/Bldg # column (Loc 1/Bldg 1)"]

# (printed text, premium key, applies_to)   premium key None -> "Included"
FORMS = [
    ("FL-18 0696-Intentional Acts Exclusion", None, None),
    ("FL-20 0192-Agreement", None, None),
    ("FL-345 1200-Mechanical, Electrical, or", "f345", None),
    ("FL-373A 0523-Canine Related Injuries or", "f373", None),
    ("FL-52A 1298-Trampoline Exclusion", "f52a", None),
    ("FL-59 0697-Lead Exclusion", None, None),
    ("FL-84A 0494-New York Amendatory", None, None),
    ("FL-87 0192-Excl.-", None, None),
    ("FL-99 0598-Calendar Date Exclusion", None, None),
    ("FL-OLT 0192-Seasonal or Tenant Occupied", None, None),
    ("FMD-1 0808-Important Flood Insurance", None, None),
    ("ML-430 0191-Renewal Endorsement", None, None),
    ("NC-FL-90 1106-Clarification End", None, None),
    ("NY-STAT-1 1108-NY Statutory", None, None),
    ("FL-3B 0192-Causes of Loss", None, "Loc 1/Bldg 1"),
]


def draw(v, C):
    d = {"pol": "DF%06d" % v.integer(300, 4999)}
    d.update(N.term(v, C))
    d.update(N.agency(v, C, 1))
    ins = C.address(v)
    d.update(ins_name=C.person(v),
             ins_street=C.po_box(v).upper() if v.maybe(0.5) else ins["line_1"].upper(),
             ins_city=ins["city"].upper(), ins_zip=ins["postal_code"])
    d["ins_line"] = "%s, NY %s" % (d["ins_city"], d["ins_zip"])
    N.characteristics(v, C, d)

    seasonal = v.maybe(0.6)
    d["seasonal"] = seasonal
    d["occ"] = "Unoccupied / Seasonal" if seasonal else v.choice(["Owner Occupied", "Tenant Occupied"])
    d["usage"] = "Seasonal" if seasonal else v.choice(["Primary", "Secondary", "Secondary"])
    d["descr"] = v.choice(["Year Round Home", "Seasonal Camp", "Lake Cottage", "Hunting Camp", "Rental Home"])

    a = v.limit(100000, 480000, 1000)
    b = C.round_to(a * v.choice([0.05, 0.1, 0.1]), 100)
    c = v.choice([5000, 10000, 15000, 20000, 25000])
    dd = C.round_to(a * v.choice([0.1, 0.1, 0.2]), 100)
    lim_l = v.choice([100000, 300000, 500000])
    med_p, med_a = v.choice([1000, 2000, 5000]), v.choice([10000, 25000, 50000])
    prem = {"A": round(a / 1000.0 * v.rng.uniform(3.6, 4.5)), "B": round(b / 1000.0 * v.rng.uniform(1.8, 2.4)),
            "C": round(c / 1000.0 * v.rng.uniform(2.8, 3.6)), "D": round(dd / 1000.0 * v.rng.uniform(3.5, 4.5)),
            "L": v.integer(60, 120), "M": v.integer(20, 50)}
    f345, f373, f52a = v.integer(10, 40), -v.integer(1, 3), -v.integer(1, 3)
    basic = sum(prem.values())
    forms_total = f345 + f373 + f52a
    d.update(a=a, b=b, c=c, dd=dd, lim_l=lim_l, med_p=med_p, med_a=med_a, prem=prem,
             f345=f345, f373=f373, f52a=f52a, basic=basic, forms_total=forms_total, total=basic + forms_total)
    usd = C.usd
    d.update(a_s=usd(a, False), b_s=usd(b, False), c_s=usd(c, False), d_s=usd(dd, False),
             l_s="%s Occ" % usd(lim_l, False),
             m_s="%s Per/%s Acc" % (usd(med_p, False), usd(med_a, False)),
             pa_s=usd(prem["A"]), pb_s=usd(prem["B"]), pc_s=usd(prem["C"]), pd_s=usd(prem["D"]),
             pl_s=usd(prem["L"]), pm_s=usd(prem["M"]), basic_s=usd(basic),
             f345_s=usd(f345), f373_s="($%d.00)" % -f373, f52a_s="($%d.00)" % -f52a,
             forms_s=usd(forms_total), total_s=usd(d["total"]))
    d["sur_lbl"] = "Unoccupied/Seasonal Surcharge" if seasonal else ""
    d["sur_loc"] = "Loc 1/Bldg 1" if seasonal else ""
    d["sur_inc"] = "Included" if seasonal else ""
    d["cov_premiums"] = [("Cov A - Dwelling", prem["A"]), ("Cov B - Related Private Structures", prem["B"]),
                         ("Cov C - Personal Property", prem["C"]),
                         ("Cov D - Addl Living Exp/Loss of Rents", prem["D"]),
                         ("Cov L - Premises Liability", prem["L"]), ("Cov M - Medical Payments", prem["M"])]
    return d


E = {"exact": True}
REPLACE = [
    # header, both pages
    ("DF000629", "{pol}"),
    ("08/04/2026", "{eff}"),
    ("08/04/2029", "{exp}"),
    ("08/03/2026", "{proc}"),
    # agency
    ("848", "{ag_code}", E),
    ("STABLE ROCK INSURANCE AGENCY,", "{ag_name}", E),
    ("PO BOX 329", "{ag_street}", E),
    ("INLET, NY 13360", "{ag_line}", E),
    ("(315)357-5901", "{ag_phone}", E),
    ("agency@patrioticinsurancegroup.com", "{ag_email}", E),
    # named insured
    ("Rosalind Marsh", "{ins_name}", E),
    ("PO BOX 274", "{ins_street}", E),
    ("THENDARA, NY 13472", "{ins_line}", E),
    # location
    ("177 Park Ave Old Forge, NY 13420", "{prop_line}", E),
    # coverages
    ("$361,000", "{a_s}", E),
    ("$1,456.00", "{pa_s}", E),
    ("$36,100", "{b_s}", {"exact": True, "nth": 0}),
    ("$36,100", "{d_s}", {"exact": True, "nth": 1}),
    ("$72.00", "{pb_s}", E),
    ("$5,000", "{c_s}", {"exact": True, "leak": False}),
    ("$17.00", "{pc_s}", {"exact": True, "nth": 0}),
    ("$144.00", "{pd_s}", E),
    ("$500,000 Occ", "{l_s}", E),
    ("$98.00", "{pl_s}", E),
    ("$5,000 Per/$10,000 Acc", "{m_s}", E),
    ("$34.00", "{pm_s}", E),
    ("$1000", "{ded_p1}", E),
    ("$1,821.00", "{basic_s}", E),
    ("$20.00", "{f345_s}", E),
    ("($1.00)", "{f373_s}", {"exact": True, "leak": False}),
    ("($2.00)", "{f52a_s}", {"exact": True, "leak": False}),
    ("$17.00", "{forms_s}", {"exact": True, "nth": 1}),
    # page 2
    ("Unoccupied/Seasonal Surcharge", "{sur_lbl}", {"exact": True, "leak": False}),
    ("Loc 1/Bldg 1", "{sur_loc}", {"exact": True, "page": 2, "nth": 0, "leak": False}),
    ("Included", "{sur_inc}", {"exact": True, "page": 2, "nth": 0, "leak": False}),
    ("$1,838.00", "{total_s}", E),
    ("Year Round Home", "{descr}", E),
    ("Protected", "{protect}", E),
    ("Zone 1, Sub-Zone 4", "{zone}", E),
    ("Frame", "{constr}", E),
    ("Main Residence", "{structure}", E),
    ("00043-Herkimer", "{county_line}", E),
    ("1959", "{year}", E),
    ("Unoccupied / Seasonal", "{occ}", E),
    ("$1,000", "{ded_p2}", {"exact": True, "page": 2, "leak": False}),
    ("Secondary", "{usage}", E),
    ("1 Family", "{families}", E),
    ("None", "{burglar}", {"exact": True, "page": 2, "nth": 0}),
    ("Smoke Alarm/Detector", "{fire_alarm}", E),
    ("None", "{sprink}", {"exact": True, "page": 2, "nth": 1}),
    ("Replacement Cost", "{settle}", E),
]

# the column-heading row of the coverage table is layout, not a label/value pair
IGNORE_PAIRS = [r"^Policy Coverages: Loc #/Bldg # Limit Deductible Premium$"]

STATIC = [r"^Watertown, NY 13601$", r"^NCIC 07/14$", r"^21170 NYS Route 232$"]

# a drawn amount can coincide with another source amount ("$17.00"), which makes the leak probe meaningless
REPLACE = [(e[0], e[1], dict(e[2] if len(e) > 2 else {}, leak=False) if e[0][:1] in "$(" else (e[2] if len(e) > 2 else {}))
           for e in REPLACE]

REPLACE += N.keep_entries(SOURCE, REPLACE)


def audit(d):
    p = d["prem"]
    out = []
    if sum(p.values()) != d["basic"] or d["basic"] + d["forms_total"] != d["total"]:
        out.append("premiums do not sum")
    return out


def gold(d):
    ded = money(d["ded_p1"])
    loc_cov = N.cov_rows([
        ("Cov A - Dwelling", amt(d["a"], False), ded, d["prem"]["A"], {}),
        ("Cov B - Related Private Structures", amt(d["b"], False), money(d["ded_p1"]), d["prem"]["B"], {}),
        ("Cov C - Personal Property", amt(d["c"], False), money(d["ded_p1"]), d["prem"]["C"], {}),
        ("Cov D - Addl Living Exp/Loss of Rents", amt(d["dd"], False), money(d["ded_p1"]), d["prem"]["D"], {}),
        ("Cov L - Premises Liability", amt(d["lim_l"], False, evidence=d["l_s"]), None, d["prem"]["L"],
         {"limit_basis": fv("Occ")}),
        ("Cov M - Medical Payments", amt(d["med_p"], False, evidence=d["m_s"]), None, d["prem"]["M"],
         {"aggregate_limit_amount": amt(d["med_a"], False, evidence=d["m_s"]),
          "limit_basis": fv(d["m_s"])}),
    ])
    deds = [{"applies_to": fv(n), "deductible_type": derived("All Other Perils", "Deductible"),
             "amount": money(d["ded_p1"])}
            for n in ("Cov A - Dwelling", "Cov B - Related Private Structures",
                      "Cov C - Personal Property", "Cov D - Addl Living Exp/Loss of Rents")]
    prem_of = {"f345": amt(d["f345"]), "f373": money(d["f373_s"]), "f52a": money(d["f52a_s"])}
    forms = [(t, prem_of[k] if k else money("Included"), ap) for t, k, ap in FORMS]
    g = N.base_gold(d, forms, loc_cov, deds, 1)
    g["named_insured"] = {
        "primary_name": fv(d["ins_name"]),
        "entity_type": derived("Individual", d["ins_name"]),
        "mailing_address": {"line_1": fv(d["ins_street"]), "city": fv(d["ins_city"]),
                            "state": fv("NY"), "postal_code": fv(d["ins_zip"])},
    }
    if d["seasonal"]:
        g["premium"]["surcharges"] = [{"description": fv("Unoccupied/Seasonal Surcharge"),
                                       "applies_to": fv("Loc 1/Bldg 1"),
                                       "amount": money("Included"),
                                       "is_included": derived("Yes", "Included")}]
    g["premium"]["discounts_and_credits"] = [{"description": fv("Deductible Credit"),
                                              "applies_to": fv("Loc 1/Bldg 1"),
                                              "amount": money("Included"),
                                              "is_applied": derived("Yes", "Included")}]
    df = g["dwelling_fire"]
    df["property_coverages"].update({
        "coverage_a_dwelling_limit": amt(d["a"], False),
        "coverage_b_other_structures_limit": amt(d["b"], False),
        "coverage_c_personal_property_limit": amt(d["c"], False),
        "coverage_e_additional_living_expense_limit": amt(d["dd"], False)})
    df["liability_coverages"].update({
        "coverage_l_premises_liability_limit": amt(d["lim_l"], False, evidence=d["l_s"]),
        "coverage_m_medical_payments_per_person_limit": amt(d["med_p"], False, evidence=d["m_s"]),
        "coverage_m_medical_payments_per_occurrence_limit": amt(d["med_a"], False, evidence=d["m_s"])})
    return g
