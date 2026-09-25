"""
North Country Insurance Company - "Fire Policy Declaration" (policy_2), New
Business, two pages, text-only, Agent Copy. Owner lives out of state (Florida
mailing address); the dwelling itself is not covered (Cov A and Cov D print $0),
Cov B, C, L and M are. Page 2 carries two "Special Interests".

GAPS (printed but no canonical leaf): "Structure: Main Residence"; "Fire Alarm";
"Usage" when not seasonal; "Fire, EC & VMM" is mapped to covered_causes_of_loss;
the Loc #/Bldg # column; "Limits and deductibles stated above are not in
addition to those on specific forms."; the policy-period boilerplate paragraphs;
empty "Loan #:" / "Rank:" labels under Special Interests.
"""

from ..engine import amt, derived, fv, money
from . import _ncic_common as N

SOURCE = "North Country Insurance Company/dwelling_fire/north_country_insurance_company_dfire_policy_2.pdf"

GAPS = ["Structure: Main Residence", "Fire Alarm (smoke alarm / central station)",
        "Usage (Primary / Secondary) when not seasonal",
        "Limits and deductibles stated above are not in addition to those on specific forms.",
        "Policy period / coverage-applies boilerplate paragraphs",
        "Loc #/Bldg # column (Loc 1/Bldg 1)", "Loan # and Rank labels (printed empty)"]

FORMS = [
    ("FL-18 0696-Intentional Acts Exclusion", None, None),
    ("FL-20 0192-Agreement", None, None),
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
    ("NC-FL-315A 1016-Addl Insured (Owner-", "f315", None),
    ("FL-1R 0192-Causes of Loss", None, "Loc 1/Bldg 1"),
    ("NC-FL-315A 1016-Additional Insured", None, "Loc 1/Bldg 1"),
]

STREETS = ["RIVERSIDE DR", "OCEAN BLVD", "PALM AVE", "BAYSHORE DR", "GULF BLVD",
           "HARBOR VIEW RD", "SUNSET LN", "CORAL WAY"]
TRUSTS = ["REVOCABLE LIVING TRUST", "FAMILY TRUST", "LIVING TRUST", "IRREVOCABLE TRUST"]


def draw(v, C):
    d = {"pol": "DF%06d" % v.integer(300, 4999)}
    d.update(N.term(v, C))
    d.update(N.agency(v, C, 2))
    n1, n2 = C.couple(v)
    city, state, zip5 = v.choice(N.FL_TOWNS)
    street = "%d %s%s" % (v.integer(10, 999), v.choice(["NORTH ", "SOUTH ", "EAST ", "WEST ", ""]),
                          v.choice(STREETS))
    if v.maybe(0.6):
        street += " APT %d" % v.integer(100, 420)
    d.update(n1=n1, n2=n2, trust=v.choice(TRUSTS), ins_street=street, ins_city=city, ins_state=state,
             ins_zip=zip5, ins_zip4="%s-%04d" % (zip5, v.integer(1000, 9999)))
    d["ins_line4"] = "%s, %s %s" % (city, state, d["ins_zip4"])
    d["ins_line5"] = "%s, %s %s" % (city, state, zip5)
    N.characteristics(v, C, d)

    d["occ"] = v.choice(["Owner Occupied", "Owner Occupied", "Tenant Occupied", "Unoccupied / Seasonal"])
    d["usage"] = "Seasonal" if d["occ"] == "Unoccupied / Seasonal" else v.choice(["Seasonal", "Seasonal", "Primary"])
    d["descr"] = "%d acres of land with a %s" % (v.integer(2, 40), v.choice(
        ["storage shed", "detached garage", "barn", "workshop", "boat house"]))

    b = v.limit(10000, 60000, 1000)
    c = v.limit(1000, 6000, 500)
    lim_l = v.choice([100000, 300000, 500000])
    med_p, med_a = v.choice([1000, 2000, 5000]), v.choice([10000, 25000, 50000])
    prem = {"B": round(b / 1000.0 * v.rng.uniform(2.0, 3.0)), "C": v.integer(3, 15),
            "L": v.integer(40, 100), "M": v.integer(5, 15)}
    f373, f52a, f315 = -v.integer(1, 3), -v.integer(1, 3), v.integer(3, 12)
    basic = sum(prem.values())
    forms_total = f373 + f52a + f315
    usd = C.usd
    d.update(b=b, c=c, lim_l=lim_l, med_p=med_p, med_a=med_a, prem=prem, f373=f373, f52a=f52a, f315=f315,
             basic=basic, forms_total=forms_total, total=basic + forms_total,
             b_s=usd(b, False), c_s=usd(c, False), l_s="%s Occ" % usd(lim_l, False),
             m_s="%s Per/%s Acc" % (usd(med_p, False), usd(med_a, False)),
             pb_s=usd(prem["B"]), pc_s=usd(prem["C"]), pl_s=usd(prem["L"]), pm_s=usd(prem["M"]),
             basic_s=usd(basic), f373_s="($%d.00)" % -f373, f52a_s="($%d.00)" % -f52a,
             f315_s=usd(f315), forms_s=usd(forms_total), total_s=usd(basic + forms_total))
    d["cov_premiums"] = [("Cov B - Related Private Structures", prem["B"]), ("Cov C - Personal Property", prem["C"]),
                         ("Cov L - Premises Liability", prem["L"]), ("Cov M - Medical Payments", prem["M"])]
    return d


E = {"exact": True}
K = {"exact": True, "leak": False}
DATE = "02/27/2026"
REPLACE = [
    ("DF000616", "{pol}"),
    # inception / process / effective, on both pages, in reading order
    (DATE, "{eff}", {"exact": True, "nth": 0}), (DATE, "{proc}", {"exact": True, "nth": 1}),
    (DATE, "{eff}", {"exact": True, "nth": 2}), (DATE, "{eff}", {"exact": True, "nth": 3}),
    (DATE, "{proc}", {"exact": True, "nth": 4}), (DATE, "{eff}", {"exact": True, "nth": 5}),
    ("02/27/2029", "{exp}"),
    # agency
    ("848", "{ag_code}", E),
    ("PATRIOTIC INSURANCE GROUP", "{ag_name}", E),
    ("PO BOX 329", "{ag_street}", E),
    ("INLET, NY 13360", "{ag_line}", E),
    ("(315)357-5901", "{ag_phone}", E),
    ("agency@patrioticinsurancegroup.com", "{ag_email}", E),
    # named insured and the special interests that repeat it
    ("Marguerite Granger", "{n1}", E),
    ("Marguerite Vance", "{n2}", E),
    ("REVOCABLE LIVING TRUST", "{trust}", E),
    ("101 NORTH RIVERSIDE DR APT 203", "{ins_street}", E),
    ("NEW SMYRNA BEACH, FL 32168-3216", "{ins_line4}", E),
    ("NEW SMYRNA BEACH, FL 32168", "{ins_line5}", E),
    # location
    ("287 Pine Street Thendara, NY 13472", "{prop_line}", E),
    # coverages
    ("$0", "$0", K),
    ("$29,000", "{b_s}", E),
    ("$72.00", "{pb_s}", E),
    ("$2,000", "{c_s}", E),
    ("$6.00", "{pc_s}", E),
    ("$500,000 Occ", "{l_s}", E),
    ("$66.00", "{pl_s}", E),
    ("$1,000 Per/$50,000 Acc", "{m_s}", E),
    ("$9.00", "{pm_s}", E),
    ("$1000", "{ded_p1}", E),
    ("$153.00", "{basic_s}", E),
    ("($1.00)", "{f373_s}", K),
    ("($2.00)", "{f52a_s}", K),
    ("$7.00", "{f315_s}", E),
    ("$4.00", "{forms_s}", E),
    ("$157.00", "{total_s}", E),
    # page 2
    ("6 acres of land with a storage shed", "{descr}", E),
    ("Protected", "{protect}", E),
    ("Zone 1, Sub-Zone 4", "{zone}", E),
    ("Frame", "{constr}", E),
    ("Main Residence", "{structure}", E),
    ("00043-Herkimer", "{county_line}", E),
    ("2002", "{year}", E),
    ("Owner Occupied", "{occ}", E),
    ("$1,000", "{ded_p2}", {"exact": True, "page": 2, "leak": False}),
    ("Seasonal", "{usage}", E),
    ("1 Family", "{families}", E),
    ("None", "{burglar}", {"exact": True, "page": 2, "nth": 0}),
    ("Smoke Alarm/Detector", "{fire_alarm}", E),
    ("None", "{sprink}", {"exact": True, "page": 2, "nth": 1}),
    ("Actual Cash Value", "{settle}", E),
]

# the column-heading row of the coverage table is layout, not a label/value pair
IGNORE_PAIRS = [r"^Policy Coverages: Loc #/Bldg # Limit Deductible Premium$"]

STATIC = [r"^Watertown, NY 13601$", r"^NCIC 07/14$", r"^21170 NYS Route 232$"]

# a drawn amount can coincide with another source amount ("$17.00"), which makes the leak probe meaningless
REPLACE = [(e[0], e[1], dict(e[2] if len(e) > 2 else {}, leak=False) if e[0][:1] in "$(" else (e[2] if len(e) > 2 else {}))
           for e in REPLACE]

REPLACE += N.keep_entries(SOURCE, REPLACE)


def audit(d):
    if sum(d["prem"].values()) != d["basic"] or d["basic"] + d["forms_total"] != d["total"]:
        return ["premiums do not sum"]
    return []


def _party_addr(d, zip_text):
    return {"line_1": fv(d["ins_street"]), "city": fv(d["ins_city"]), "state": fv(d["ins_state"]),
            "postal_code": fv(zip_text)}


def gold(d):
    ded = lambda: money(d["ded_p1"])
    loc_cov = N.cov_rows([
        ("Cov A - Dwelling", money("$0"), None, None, {}),
        ("Cov B - Related Private Structures", amt(d["b"], False), ded(), d["prem"]["B"], {}),
        ("Cov C - Personal Property", amt(d["c"], False), ded(), d["prem"]["C"], {}),
        ("Cov D - Addl Living Exp/Loss of Rents", money("$0"), None, None, {}),
        ("Cov L - Premises Liability", amt(d["lim_l"], False, evidence=d["l_s"]), None, d["prem"]["L"],
         {"limit_basis": fv("Occ")}),
        ("Cov M - Medical Payments", amt(d["med_p"], False, evidence=d["m_s"]), None, d["prem"]["M"],
         {"aggregate_limit_amount": amt(d["med_a"], False, evidence=d["m_s"]),
          "limit_basis": fv(d["m_s"])}),
    ])
    deds = [{"applies_to": fv(n), "deductible_type": derived("All Other Perils", "Deductible"),
             "amount": money(d["ded_p1"])}
            for n in ("Cov B - Related Private Structures", "Cov C - Personal Property")]
    prem_of = {"f373": money(d["f373_s"]), "f52a": money(d["f52a_s"]), "f315": amt(d["f315"])}
    forms = [(t, prem_of[k] if k else money("Included"), ap) for t, k, ap in FORMS]
    g = N.base_gold(d, forms, loc_cov, deds, 2)
    g["named_insured"] = {
        "primary_name": fv(d["n1"]),
        "entity_type": derived("Individual", d["n1"]),
        "additional_named_insureds": [{"name": fv(d["n2"]), "entity_type": derived("Individual", d["n2"])}],
        "mailing_address": _party_addr(d, d["ins_zip4"]),
    }
    g["interested_parties"] = [
        {"name": fv("%s %s %s" % (d["n1"], d["n2"], d["trust"]), evidence=d["trust"]),
         "description_of_interest": fv("Deeded owner"), "applies_to": fv("Policy"),
         "is_payor": fv("No"), "address": _party_addr(d, d["ins_zip"])},
        {"name": fv("%s %s" % (d["n1"], d["n2"]), evidence=d["n1"]),
         "description_of_interest": fv("Addl Insured (Fiduciaries)"), "applies_to": fv("Loc 1/Bldg 1"),
         "is_payor": fv("No"), "address": _party_addr(d, d["ins_zip4"])},
    ]
    df = g["dwelling_fire"]
    df["property_coverages"].update({
        "coverage_a_dwelling_limit": money("$0"),
        "coverage_b_other_structures_limit": amt(d["b"], False),
        "coverage_c_personal_property_limit": amt(d["c"], False),
        "coverage_e_additional_living_expense_limit": money("$0"),
        "covered_causes_of_loss": fv("Fire, EC & VMM")})
    df["liability_coverages"].update({
        "coverage_l_premises_liability_limit": amt(d["lim_l"], False, evidence=d["l_s"]),
        "coverage_m_medical_payments_per_person_limit": amt(d["med_p"], False, evidence=d["m_s"]),
        "coverage_m_medical_payments_per_occurrence_limit": amt(d["med_a"], False, evidence=d["m_s"])})
    return g
