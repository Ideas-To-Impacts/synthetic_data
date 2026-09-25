"""
Factories for the four redacted Leatherstocking two-page declarations that share a layout:

  make_dfire(src)  "DFIRE_redacted" and "R-DFIRE_redacted": Dwelling Fire renewals
  make_llp(src)    "LLP -1_redacted" and "LLP_redacted": Landlords Package renewals

``src`` carries the strings printed in that particular source (amounts, dates,
policy number, ...); the layout, the drawn values and the gold are the same for a
pair.  Not a profile itself (no SOURCE).
"""

from __future__ import annotations

from types import SimpleNamespace

from . import _leatherstocking as L
from ..engine import derived, fv, money

usd = L.usd

DFIRE_FORMS = (
    "FL-18 (6/96) Intentional Act Exclusion, FL-20 (1/92) Agreement, FL-83 (02/02) Amendment of "
    "Policy Conditions, FL-90 (11/06) Clarification Endorsement, FMD-1 (12/94) Important Flood "
    "Insurance Notice, LCI-11 (4/91) Senior Citizen Form, PR (3/01) Notice of Privacy Policy, "
    "LCI-J (9/17) By-Laws, FL-21 05/10 Suit Against Us Amendatory Endorsement, FL-1R (1/92) "
    "Causes of Loss, FL-OLT (1/92) Premises Liability Insurance Coverage Part, ML-59 (6/99) "
    "Lead Exclusion, SM-26 (7/00) Automatic Increase, FL-80 (7/96) Redefinition of Insured")

LLP_FORMS = (
    "FL-20 (1/92) Agreement, FL-18 (6/96) Intentional Act Exclusion, FL-30 (5/92) Amendatory "
    "Endorsement Principal Coverages, FL-80 (7/96) Redefinition of Insured, FL-83 (2/02) "
    "Amendment of Policy Conditions, FL-84A (4/94) New York Amendatory Endorsement, FL-90 "
    "(11/06) Clarification Endorsement, LCI-J (9/17) By-Laws, FMD-1 (12/94) Important Flood "
    "Insurance Notice, PR (3/01) Notice of Privacy Policy, LCIC-TRIA (02/15) Policyholder "
    "Disclosure Notice of Terrorism Insurance Coverage, LCI-11 (4/91) Senior Citizen Form, "
    "FL-21 05/10 Suit Against Us Amendatory Endorsement, FL-1R 9/16 Causes of Loss, FL-345 "
    "(12/17) Equipment Breakdown Enhancement Endorsement, FL-OLT (1/92) Premises Liability "
    "Coverage, ML-216 (6/99) Protective Device Credit, SM-26 (7/00) Automatic Increase")

A_LIMITS = [(500, 10000, 5), (1000, 25000, 8), (2000, 50000, 11)]
L_PREMIUM = {100000: 34, 300000: 58, 500000: 68, 1000000: 82}
OLT_PREMIUM = {100000: 48, 300000: 80, 500000: 96, 1000000: 110}


def _money(src_text, key):
    return (src_text, "{%s}" % key, {"exact": True, "leak": False})


def _party_entries(s):
    """Header, term, agency, insured and plan-sentence entries common to all four sources."""
    return [
        (s["policy"], "{policy_no}", {"size": 9}),
        (s["eff"], "{eff}"),
        (s["exp"], "{exp}"),
        # agency block and the "Mail To" block that repeats it
        ("Rob Bowen Patriotic Insurance Group -", "{agency} -", {"leak": False}),
        ("RBF", "{ag_code}", {"exact": True}),
        ("1992 Harbor", "{ag_street}", {"exact": True, "size": 9}),
        ("Suite 132B", "", {"exact": True}),
        ("Chester Shop Rite Plaza", "{ag_city_line}", {"exact": True}),
        ("Liberty, NY 12754", "", {"exact": True}),
        ("(226) 783-0236", "{ag_work}", {"size": 9}),
        ("(440) 929-3100", "{ag_fax}", {"size": 9}),
        # redaction artefact: restore the plan sentence
        ("MERIDIAN WORKS", L.PLAN_SENTENCE, {"exact": True, "size": 9}),
        ("-OPERATIVE ASSESSMENT PLAN", "", {"exact": True, "leak": False}),
    ]


# =============================================================================================
#  DFIRE / R-DFIRE
# =============================================================================================

def make_dfire(s):
    def draw(v, C):
        d = L.draw_parties(v, C)
        L.draw_term(v, C, d)
        d["policy_no"] = v.policy_number("{2d}-{4d}-{5d}")
        d.update(settle=v.choice(["ACV", "RC", "RC"]),
                 constr=v.choice(["Frame", "Masonry", "Masonry Veneer"]),
                 protect=v.choice(["Protected", "Semi-Protected", "Unprotected"]),
                 classif=v.choice(["Dwelling - 1 Family", "Dwelling - 2 Family"]),
                 territory="%02d - All Others" % v.integer(1, 30),
                 condition=v.choice(["Unoccupancy", "Vacancy", "Seasonal Occupancy"]),
                 deductible=v.choice([500, 1000, 1000, 2500]))
        cov_a = v.limit(90000, 480000, 100)
        prem_a = round(cov_a / 1000.0 * v.rng.uniform(3.25, 3.75))
        liab = v.choice([100000, 300000, 500000, 1000000])
        mp_person, mp_occ, prem_mp = v.choice(A_LIMITS)
        lead = -v.integer(4, 8)
        haz = round(cov_a / 1000.0 * v.rng.uniform(0.9, 0.96))
        total = prem_a + L_PREMIUM[liab] + prem_mp + lead + haz
        d.update(cov_a=cov_a, prem_a=prem_a, liab=liab, prem_l=L_PREMIUM[liab], mp_person=mp_person,
                 mp_occ=mp_occ, prem_mp=prem_mp, lead=lead, haz=haz, total=total,
                 cov_a_s=usd(cov_a, False), prem_a_s=usd(prem_a), liab_s=usd(liab, False),
                 prem_l_s=usd(L_PREMIUM[liab]), mp_person_s=usd(mp_person, False),
                 prem_mp_s=usd(prem_mp), mp_occ_s=usd(mp_occ, False), lead_s=usd(lead),
                 haz_s=usd(haz), total_s=usd(total), ded_s=usd(d["deductible"]))

        # mortgagee: two individuals, or a lender (the block has five lines either way)
        L.draw_mortgagee_lines(v, C, d)
        street, cl = d["m_street"], d["m_city_line"]
        if v.maybe(0.5):
            name = "%s and %s" % (C.person(v), C.person(v))
            d.update(m_name=name, m_desc="joint tenants", m1=name + ",", m2="joint tenants",
                     m3="ISAOA, ATMIA", m4=street, m5=cl)
        else:
            name = C.lender(v)
            d.update(m_name=name, m_desc=None, m1=name, m2="ISAOA, ATMIA", m3=street, m4=cl, m5="")
        return d

    replace = _party_entries(s) + [
        # named insured (two names, street, city)
        ("Marcus Ellery", "{ins1}", {"exact": True, "size": 9}),
        ("Joseph Krol", "{ins2}", {"exact": True}),
        ("226 Meridian", "{ins_street}", {"exact": True, "size": 9}),
        ("Canton, NY 13617", "{ins_city_line}", {"exact": True, "size": 9}),
        # property line, page 1 and the mortgagee's reference on page 2: one bold line each
        ("Property 1 - 2W Forest Road -", "{prop_line}", {"exact": True, "page": 1}),
        ("Medina, NY 14103", "", {"exact": True}),
        ("- Sullivan County", "", {"exact": True}),
        ("Property 1 - 2W Forest Road;", "{prop_line2}", {"exact": True, "page": 2}),
        # schedule
        _money(s["cov_a"], "cov_a_s"), _money(s["prem_a"], "prem_a_s"),
        _money(s["liab"], "liab_s"), _money(s["prem_l"], "prem_l_s"),
        _money(s["mp_person"], "mp_person_s"), _money(s["prem_mp"], "prem_mp_s"),
        _money(s["mp_occ"], "mp_occ_s"), _money(s["lead"], "lead_s"),
        _money(s["haz"], "haz_s"), _money(s["total"], "total_s"),
        # rating information (page 2)
        (s["ded"], "{ded_s}", {"page": 2, "leak": False}),
        (s["settle"], "{settle}", {"exact": True, "page": 2, "leak": False}),
        ("Automatic Increase, %s" % s["settle"], "Automatic Increase, {settle}",
         {"page": 2, "leak": False}),
        ("Frame", "{constr}", {"exact": True}),
        ("Semi-Protected", "{protect}", {"exact": True}),
        ("Dwelling - 1 Family", "{classif}", {"exact": True}),
        ("19 - All Others", "{territory}", {"exact": True}),
        ("Unoccupancy", "{condition}", {"exact": True}),
        # mortgagee block
        ("Marcel Witschard and Helga Dreiner,", "{m1}", {"exact": True, "leak": False}),
        ("joint tenants", "{m2}", {"exact": True, "leak": False}),
        ("ISAOA, ATMIA", "{m3}", {"exact": True, "leak": False}),
        ("8825 Lincoln Lane", "{m4}", {"exact": True, "size": 9, "leak": False}),
        ("Cortland, NY 13045", "{m5}", {"exact": True, "size": 9, "leak": False}),
    ]

    def rows(d):
        r = [L.row("Coverage A - Residence", d["cov_a_s"], d["prem_a"],
                   leaf=("property", "coverage_a_dwelling_limit")),
             L.row("Coverage L - Premises Liability", d["liab_s"], d["prem_l"],
                   leaf=("liability", "coverage_l_premises_liability_limit"), basis="Each Occurrence"),
             L.row("Coverage M - Medical Payments - Per Person", d["mp_person_s"], d["prem_mp"],
                   leaf=("liability", "coverage_m_medical_payments_per_person_limit"),
                   basis="Per Person"),
             L.row("Coverage M - Medical Payments - Per Occurrence", d["mp_occ_s"], 0,
                   leaf=("liability", "coverage_m_medical_payments_per_occurrence_limit"),
                   basis="Per Occurrence"),
             L.row("ML-59 - Lead Exclusion", "***", d["lead"], form="ML-59")]
        o = [L.row("Hazardous Conditions - Occupancy", "***", d["haz"])]
        return r, o

    def audit(d):
        r, o = rows(d)
        return L.audit_rows(d, r, o)

    def gold(d):
        r, o = rows(d)
        S = {
            "lob": "Dwelling Fire", "transaction": "Renewal", "rows": r, "optional": o,
            "form_name": "Basic Form (FL-1)", "forms_text": DFIRE_FORMS,
            "notes": [{"name": "SM-26 Automatic Increase, %s" % d["settle"], "form": "SM-26",
                       "notes": L.MODIFIES + s["modifies"]}],
            "dwelling": {"occupancy_classification_code": fv(d["classif"]),
                         "hazardous_conditions_occupancy": fv(d["condition"]),
                         "rating_zone": fv("All Other")},
            "deductibles": [L.deductible_entry(d, "all property coverages",
                                               evidence="all property coverages",
                                               notes=L.DISCLAIMER)],
            "mortgagee": {"name": d["m_name"], "street": d["m_street"], "city": d["m_city"],
                          "zip": d["m_zip"], "applies_street": d["prop_street"],
                          "clause": "ISAOA, ATMIA", "desc": d["m_desc"]},
        }
        return L.build_gold(d, S)

    gaps = ["Property: 1 of 1 (property counter)",
            "Mail To block (repeats the producer name and address)",
            "SIGNATURE / DATE box (signature image only; no printed name or date)"]
    return SimpleNamespace(draw=draw, REPLACE=replace, gold=gold, audit=audit, GAPS=gaps,
                           STATIC=list(L.STATIC), IGNORE_PAIRS=list(L.IGNORE_PAIRS),
                           FURNITURE=list(L.FURNITURE))


# =============================================================================================
#  LLP -1 / LLP
# =============================================================================================

def make_llp(s):
    def draw(v, C):
        d = L.draw_parties(v, C)
        L.draw_term(v, C, d)
        d["policy_no"] = v.policy_number("{2d}-{4d}-{4d}")
        d.update(settle=v.choice(["ACV", "RC", "RC"]), constr=None,
                 protect=v.choice(["Protected", "Semi-Protected", "Unprotected"]),
                 deductible=v.choice([1000, 2500, 2500, 5000]))
        d["territory"] = "%s (Zone %d, Sub-Zone %d)" % (d["prop_county"], v.integer(1, 3), v.integer(1, 9))
        cov_a = v.limit(120000, 520000, 100)
        cov_b = L.round_to(cov_a * 0.1, 100)
        prem_a = round(cov_a / 1000.0 * v.rng.uniform(3.2, 3.4))
        liab = v.choice([100000, 300000, 500000, 1000000])
        mp_person, mp_occ, prem_mp = v.choice(A_LIMITS)
        eq = round(cov_a / 1000.0 * v.rng.uniform(0.105, 0.115))
        alarm = -round(prem_a * v.rng.uniform(0.019, 0.021))
        total = prem_a + OLT_PREMIUM[liab] + prem_mp + eq + alarm
        d.update(cov_a=cov_a, cov_b=cov_b, prem_a=prem_a, liab=liab, prem_l=OLT_PREMIUM[liab],
                 mp_person=mp_person, mp_occ=mp_occ, prem_mp=prem_mp, eq=eq, alarm=alarm, total=total,
                 cov_a_s=usd(cov_a, False), cov_b_s=usd(cov_b, False), prem_a_s=usd(prem_a),
                 liab_s=usd(liab, False), prem_l_s=usd(OLT_PREMIUM[liab]),
                 mp_person_s=usd(mp_person, False), prem_mp_s=usd(prem_mp),
                 mp_occ_s=usd(mp_occ, False), eq_s=usd(eq), alarm_s=usd(alarm),
                 total_s=usd(total), ded_s=usd(d["deductible"]))

        L.draw_mortgagee_lines(v, C, d, ziplus4=s["ziplus4"])
        name = C.lender(v)
        d.update(m_name=name, m1=name + " ISAOA ATIMA" if s["loan"] else name)
        if s["loan"]:
            d["loan"] = "#%s" % C.loan_number(v)
        return d

    replace = _party_entries(s) + [
        ("Laura Stanhope", "{ins1}", {"exact": True, "size": 9}),
        ("Fredric Provencial", "{ins2}", {"exact": True}),
        ("3331 Route 207", "{ins_street}", {"exact": True}),
        # the same city overlay is printed for the insured (1st), the property (2nd) and the
        # mortgagee's property reference (3rd); told apart by position
        ("Ilion, NY 13357", "{ins_city_line}", {"exact": True, "nth": 0, "size": 9, "leak": False}),
        ("Ilion, NY 13357", "", {"exact": True, "nth": 1, "leak": False}),
        ("Ilion, NY 13357", "", {"exact": True, "nth": 2, "leak": False}),
        ("4391 Meridian", "", {"exact": True}),
        ("Property 1 -", "{prop_line}", {"exact": True, "page": 1}),
        ("-", "", {"exact": True, "page": 1}),
        ("- Orange County", "", {"exact": True}),
        ("Property 1 -", "{prop_line2}", {"exact": True, "page": 2}),
        (";", "", {"exact": True, "page": 2}),
        # schedule
        _money(s["cov_a"], "cov_a_s"), _money(s["prem_a"], "prem_a_s"),
        _money(s["cov_b"], "cov_b_s"),
        _money(s["liab"], "liab_s"), _money(s["prem_l"], "prem_l_s"),
        _money(s["mp_person"], "mp_person_s"), _money(s["prem_mp"], "prem_mp_s"),
        _money(s["mp_occ"], "mp_occ_s"), _money(s["eq"], "eq_s"), _money(s["alarm"], "alarm_s"),
        _money(s["total"], "total_s"),
        # rating information (page 2)
        (s["ded"], "{ded_s}", {"page": 2, "leak": False}),
        ("Orange (Zone 1, Sub-Zone 6)", "{territory}", {"exact": True}),
        ("Semi-Protected", "{protect}", {"exact": True}),
        (s["settle"], "{settle}", {"exact": True, "page": 2, "leak": False}),
        ("Automatic Increase, %s" % s["settle"], "Automatic Increase, {settle}",
         {"page": 2, "leak": False}),
    ]
    if s["loan"]:
        replace += [
            ("RIDGEWAY", "{m1}", {"exact": True, "size": 9, "leak": False}),
            ("ISAOA ATIMA", "", {"exact": True, "leak": False}),
            ("PO box 7502", "{m_street}", {"exact": True, "size": 9}),
            ("Ilion, MI 13357", "{m_city_line}", {"exact": True, "size": 9}),
            ("#0641403449", "{loan}", {"exact": True}),
        ]
    else:
        replace += [
            ("Nationstar Mortgage, LLC", "{m_name}", {"exact": True}),
            ("PO Box 6377", "{m_street}", {"exact": True, "size": 9}),
            ("Canton, OH 13617-5654", "{m_city_line}", {"exact": True, "size": 9}),
        ]

    def rows(d):
        r = [L.row("Coverage A - Residence", d["cov_a_s"], d["prem_a"],
                   leaf=("property", "coverage_a_dwelling_limit")),
             L.row("Coverage B - Related Private Structures", d["cov_b_s"], 0,
                   leaf=("property", "coverage_b_other_structures_limit")),
             L.row("Coverage D - Additional Living Expense and Loss of Rent", d["cov_b_s"], 0,
                   leaf=("property", "coverage_e_additional_living_expense_limit")),
             L.row("Coverage L - OLT - Premises Liability", d["liab_s"], d["prem_l"],
                   leaf=("liability", "coverage_l_premises_liability_limit")),
             L.row("Coverage M - OLT - Premises Med Pay - Per Person", d["mp_person_s"], d["prem_mp"],
                   leaf=("liability", "coverage_m_medical_payments_per_person_limit"),
                   basis="Per Person"),
             L.row("Coverage M - OLT - Premises Med Pay - Per Occurrence", d["mp_occ_s"], 0,
                   leaf=("liability", "coverage_m_medical_payments_per_occurrence_limit"),
                   basis="Per Occurrence")]
        o = [L.row("FL-345 Equipment Breakdown", "***", d["eq"], form="FL-345"),
             L.row("ML-216 Premises Alarm or Fire Protection System", "***", d["alarm"], form="ML-216")]
        return r, o

    def audit(d):
        r, o = rows(d)
        return L.audit_rows(d, r, o)

    def gold(d):
        r, o = rows(d)
        m = {"name": d["m_name"], "street": d["m_street"], "city": d["m_city"], "zip": d["m_zip"],
             "applies_street": d["prop_street"], "clause": "ISAOA ATIMA" if s["loan"] else "ISAOA",
             "desc": "ESCROW BILLED"}
        if s["loan"]:
            m["loan"] = d["loan"]
        S = {
            "lob": "Landlords Package", "transaction": "Renewal", "rows": r, "optional": o,
            "form_name": "FL-1 Basic Form", "forms_text": LLP_FORMS,
            "notes": [{"name": "SM-26 Automatic Increase, %s" % d["settle"], "form": "SM-26",
                       "notes": L.MODIFIES + "Coverage A - Residence"}],
            "dwelling": {"year_built": fv("Since January 1960"),
                         "tenant_occupied": derived("Yes", "Landlords Package"),
                         "fire_alarm_type": fv("Fire Alarm and/or Smoke Detectors")},
            "property_extra": {"vandalism_basis": fv("With Vandalism")},
            "liability_extra": {"liability_coverage_form": fv("FL-OLT Premises Liability")},
            "location": {"year_built": fv("Since January 1960"),
                         "alarm_type": fv("Fire Alarm and/or Smoke Detectors")},
            "deductibles": [L.deductible_entry(d, "Coverage A - Residence",
                                               evidence="Coverage A - Residence", derived_applies=True)],
            "mortgagee": m,
            "extra": {"terrorism": {"disclosure_form_number": fv("LCIC-TRIA")}},
        }
        return L.build_gold(d, S)

    gaps = ["Property: 1 of 1 (property counter)",
            "Mail To block (repeats the producer name and address)",
            "SIGNATURE / DATE box (signature image only; no printed name or date)"]
    return SimpleNamespace(draw=draw, REPLACE=replace, gold=gold, audit=audit, GAPS=gaps,
                           STATIC=list(L.STATIC), IGNORE_PAIRS=list(L.IGNORE_PAIRS),
                           FURNITURE=list(L.FURNITURE))
