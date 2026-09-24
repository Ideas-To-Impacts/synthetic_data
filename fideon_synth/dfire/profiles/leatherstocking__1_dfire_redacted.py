"""
Leatherstocking Cooperative Insurance Company - "1- DFIRE_redacted.pdf"

REFERENCE PROFILE. Two-page Dwelling Fire declaration, new policy. The source
is a redacted copy: values were painted over as tiny 6 pt overlays and the
agency block is scrambled, so this profile also tidies those artefacts (upsizes
overlays, puts the agency address on consecutive lines, restores the
"CO-OPERATIVE" plan line).

GAPS (printed but no canonical leaf): "Zone: All Other" rating zone.
"""

from ..engine import addr, amt, derived, date_fv, fv, logo, money

SOURCE = "Leatherstocking Cooperative Insurance Company/dwelling_fire/1- DFIRE_redacted.pdf"

FORMS = [
    ("FL-18", "6/96", "Intentional Act Exclusion"),
    ("FL-20", "1/92", "Agreement"),
    ("FL-83", "02/02", "Amendment of Policy Conditions"),
    ("FL-90", "11/06", "Clarification Endorsement"),
    ("FMD-1", "12/94", "Important Flood Insurance Notice"),
    ("LCI-11", "4/91", "Senior Citizen Form"),
    ("PR", "3/01", "Notice of Privacy Policy"),
    ("LCI-J", "9/17", "By-Laws"),
    ("FL-21", "05/10", "Suit Against Us Amendatory Endorsement"),
    ("FL-1", "2/92", "Causes of Loss"),
    ("FL-OLT", "1/92", "Premises Liability Insurance Coverage Part"),
    ("ML-59", "6/99", "Lead Exclusion"),
    ("SM-26", "7/00", "Automatic Increase"),
    ("FL-80", "7/96", "Redefinition of Insured"),
]
DISCLAIMER = ("The Deductible reflected applies to all property coverages unless "
              "otherwise stipulated within the policy language.")


def draw(v, C):
    d = {}
    # agency (the "Mail To" block repeats it)
    ag = C.address(v)
    d.update(agency=C.agency(v), ag_street=ag["line_1"], ag_city=ag["city"], ag_zip=ag["postal_code"],
             ag_city_line="%s, NY %s" % (ag["city"], ag["postal_code"]),
             ag_work=C.phone(v, "paren"), ag_fax=C.phone(v, "paren"))

    # named insured
    if v.maybe(0.3):
        d["ins_name"] = C.business(v).upper()
        d["ins_kind"] = "Business"
    else:
        a, b = C.couple(v)
        d["ins_name"] = ("%s & %s" % (a.split()[0], b)) if v.maybe(0.6) else a
        d["ins_kind"] = "Individual"
    ins = C.address(v)
    d.update(ins_street=C.po_box(v) if v.maybe(0.15) else ins["line_1"], ins_city=ins["city"],
             ins_zip=ins["postal_code"], ins_city_line="%s, NY %s" % (ins["city"], ins["postal_code"]))

    # insured property
    pr = C.address(v)
    d.update(prop_street=pr["line_1"], prop_city=pr["city"], prop_zip=pr["postal_code"], prop_county=pr["county"])
    d["prop_line"] = "Property 1 - %s - %s, NY %s - %s County" % (
        pr["line_1"], pr["city"], pr["postal_code"], pr["county"])

    d["policy_no"] = v.policy_number("{2d}-{4d}-{3d}")
    eff, exp = C.term(v)
    d.update(eff=C.fmt(eff), exp=C.fmt(exp))

    # rating information
    d.update(settle=v.choice(["ACV", "RC"]),
             constr=v.choice(["Frame", "Masonry", "Masonry Veneer"]),
             protect=v.choice(["Protected", "Semi-Protected", "Unprotected"]),
             form_name=v.choice(["Basic Form (FL-1)", "Broad Form (FL-2)"]),
             classif=v.choice(["Dwelling - 1 Family", "Dwelling - 2 Family"]),
             territory="%02d - All Others" % v.integer(1, 30),
             condition=v.choice(["Unoccupancy", "Vacancy", "Seasonal Occupancy"]),
             deductible=v.choice([500, 1000, 1000, 2500]))

    # money - rated off the limits so the page reads like a real one
    cov_a = v.limit(90000, 480000, 1000)
    prem_a = round(cov_a / 1000.0 * v.rng.uniform(3.6, 4.8))
    lim_l = v.choice([100000, 300000, 500000, 1000000])
    prem_l = v.integer(48, 96)
    lead = -v.integer(4, 8)
    haz = v.integer(150, 420)
    total = prem_a + prem_l + lead + haz
    d.update(cov_a=cov_a, prem_a=prem_a, lim_l=lim_l, prem_l=prem_l, lead=lead, haz=haz, total=total,
             cov_a_s=C.usd(cov_a, False), prem_a_s=C.usd(prem_a), lim_l_s=C.usd(lim_l, False),
             prem_l_s=C.usd(prem_l), lead_s=C.usd(lead), haz_s=C.usd(haz), total_s=C.usd(total),
             ded_s=C.usd(d["deductible"]))
    return d


REPLACE = [
    # agency block and the "Mail To" block that repeats it
    ("Rob Bowen Patriotic Insurance Group -", "{agency}"),
    ("RBF", "{ag_street}", {"exact": True}),
    ("1992 Harbor", "{ag_city_line}", {"exact": True, "size": 9}),
    ("Suite 132B", "", {"exact": True}),
    ("Chester Shop Rite Plaza", "", {"exact": True}),
    ("Liberty, NY 12754", "", {"exact": True}),
    ("(226) 783-0236", "{ag_work}", {"size": 9}),
    ("(440) 929-3100", "{ag_fax}", {"size": 9}),
    # named insured
    ("GRANITE ROW INDUSTRIES", "{ins_name}", {"size": 9}),
    ("226 Meridian", "{ins_street}", {"size": 9}),
    ("Canton, NY 13617", "{ins_city_line}", {"size": 9}),
    # policy identity and term
    ("95-8892-256", "{policy_no}", {"size": 9}),
    ("01/25/2023", "{eff}"),
    ("01/25/2024", "{exp}"),
    # redaction artefacts: restore the plan line
    ("MERIDIAN WORKS", "", {"exact": True}),
    ("-OPERATIVE ASSESSMENT PLAN", "CO-OPERATIVE ASSESSMENT PLAN", {"exact": True}),
    # property line: one bold line, the overlays and separators erased
    ("Property 1 -", "{prop_line}", {"exact": True, "page": 1}),
    ("4703 Maple Drive", "", {"exact": True}),
    ("-", "", {"exact": True, "page": 1}),
    ("Warwick, NY 10990", "", {"exact": True}),
    ("- Orange County", "", {"exact": True}),
    # schedule
    ("$340,000", "{cov_a_s}"),
    ("$1,438.00", "{prem_a_s}"),
    ("$1,000,000", "{lim_l_s}"),
    ("$82.00", "{prem_l_s}"),
    ("-$6.00", "{lead_s}"),
    ("$360.00", "{haz_s}"),
    ("$1,874.00", "{total_s}"),
    # rating information (page 2)
    ("$1,000.00", "{ded_s}", {"page": 2}),
    ("ACV", "{settle}", {"exact": True, "page": 2}),
    ("Automatic Increase, ACV", "Automatic Increase, {settle}", {"page": 2}),
    ("Frame", "{constr}", {"exact": True}),
    ("Semi-Protected", "{protect}", {"exact": True}),
    ("Basic Form (FL-1)", "{form_name}", {"exact": True}),
    ("Dwelling - 1 Family", "{classif}", {"exact": True}),
    ("19 - All Others", "{territory}", {"exact": True}),
    ("Unoccupancy", "{condition}", {"exact": True}),
]

STATIC = [
    r"^\$0\.00$",                     # Fees: unchanged
    r"13326", r"^Phone: 607-547",     # the carrier's own letterhead
]


FURNITURE = [
    r"^Phone: 607-547-2007 Fax: 607-547-2056$",   # carrier letterhead, keyed as carrier.contact.phone / fax
]

IGNORE_PAIRS = [
    r"^Phone: 607-547-2007 Fax: 607-547-2056",   # carrier letterhead, keyed as carrier.contact.phone / fax
    r"^Policy Number: .* Page \d+ of \d+$",      # page footer, repeats the keyed policy number
]


def audit(d):
    if d["cov_a"] <= 0 or d["prem_a"] + d["prem_l"] + d["lead"] + d["haz"] != d["total"]:
        return ["premium schedule does not sum to the total"]
    return []


def gold(d):
    eff, exp = d["eff"], d["exp"]
    prop = addr(d["prop_street"], d["prop_city"], "NY", d["prop_zip"])
    prop["county"] = fv("%s County" % d["prop_county"], d["prop_county"])

    coverages = ["Coverage A - Residence", "Coverage L - Premises Liability",
                 "ML-59 - Lead Exclusion", "Hazardous Conditions - Occupancy"]

    return {
        "document": {
            "document_type": fv("DECLARATION", "Declaration"),
            "document_title_as_stated": fv("DECLARATION, Dwelling Fire"),
            "line_of_business_as_stated": fv("Dwelling Fire"),
            "transaction_type": fv("New Policy"),
            "transaction_effective_date": date_fv(eff),
            "coverage_parts_present": [fv("Section I"), fv("Section II"), fv("Optional Items")],
            "applicable_coverages": [fv(c) for c in coverages],
        },
        "carrier": {
            "company_name": logo("Leatherstocking Cooperative Insurance Company"),
            "address": {"line_1": fv("PO Box 630, 4313 County Highway 11"), "city": fv("Cooperstown"),
                        "state": fv("NY"), "postal_code": fv("13326")},
            "contact": {"phone": fv("607-547-2007"), "fax": fv("607-547-2056"),
                        "website": fv("www.leatherstockinginsurance.com")},
            "state_of_issue": derived("NY", "Cooperstown, NY 13326"),
        },
        "producer": {
            "agency_name": fv(d["agency"]),
            "address": addr(d["ag_street"], d["ag_city"], "NY", d["ag_zip"]),
            "contact": {"phone": fv(d["ag_work"]), "fax": fv(d["ag_fax"])},
        },
        "policy": {
            "policy_number": fv(d["policy_no"]),
            "alternate_policy_identifiers": [{"identifier_type": fv("Policy ID"),
                                              "identifier_value": fv(d["policy_no"])}],
            "policy_form_number": fv("LCIC(4/11)"),
            "policy_form_name": fv(d["form_name"]),
            "policy_type": fv("Dwelling Fire", evidence="Dwelling Fire"),
            "plan_type": fv("CO-OPERATIVE ASSESSMENT PLAN"),
            "effective_date": date_fv(eff),
            "expiration_date": date_fv(exp),
            "effective_time": fv("12:01 AM", evidence="12:01"),
            "expiration_time": fv("12:01 AM", evidence="12:01"),
            "time_zone": fv("Standard Time"),
            "policy_term_months": derived("12", eff, 12),
            "is_renewal": derived("No", "New Policy"),
        },
        "named_insured": {
            "primary_name": fv(d["ins_name"]),
            "entity_type": derived(d["ins_kind"]),
            "mailing_address": addr(d["ins_street"], d["ins_city"], "NY", d["ins_zip"]),
        },
        "locations": [{
            "location_number": fv("1", 1, evidence="Property 1"),
            "address": dict(prop),
            "occupancy_description": fv("1-2 Family"),
            "construction_type": fv(d["constr"]),
            "protection_class": fv(d["protect"]),
            "territory_code": fv(d["territory"]),
            "coverages": [
                {"coverage_name": fv("Coverage A - Residence"), "limit_amount": amt(d["cov_a"], False),
                 "premium": amt(d["prem_a"]), "deductible_amount": amt(d["deductible"]),
                 "valuation_basis": fv(d["settle"])},
                {"coverage_name": fv("Coverage L - Premises Liability"),
                 "limit_amount": amt(d["lim_l"], False), "premium": amt(d["prem_l"]),
                 "limit_basis": fv("Each Occurrence")},
            ],
        }],
        "premium": {
            "total_policy_premium": amt(d["total"]),
            "basic_premium": amt(d["total"]),
            "premium_by_coverage_part": [{"coverage_part": fv("Property 1"), "premium": amt(d["total"])}],
            "taxes_and_fees": [{"description": fv("Fees"), "amount": amt(0)}],
        },
        "forms_and_endorsements": [
            {"form_number": fv(n), "edition_date": fv(e), "form_title": fv(t)} for n, e, t in FORMS],
        "deductibles": [{
            "applies_to": fv("all property coverages", evidence="all property coverages"),
            "deductible_type": derived("All Other Perils", "Deductible"),
            "amount": amt(d["deductible"]),
            "notes": fv(DISCLAIMER),
        }],
        "dwelling_fire": {
            "dwelling": {
                "described_location": dict(prop),
                "occupancy_type": fv("1-2 Family"),
                "occupancy_classification_code": fv(d["classif"]),
                "construction_type": fv(d["constr"]),
                "protection_class": fv(d["protect"]),
                "territory_code": fv(d["territory"]),
                "hazardous_conditions_occupancy": fv(d["condition"]),
            },
            "property_coverages": {
                "coverage_a_dwelling_limit": amt(d["cov_a"], False),
                "loss_settlement_basis": fv(d["settle"]),
            },
            "liability_coverages": {
                "coverage_l_premises_liability_limit": amt(d["lim_l"], False),
            },
            "deductibles": {"all_other_perils_deductible": amt(d["deductible"])},
            "optional_endorsement_coverages": [
                {"coverage_name": fv("ML-59 - Lead Exclusion"), "form_reference": fv("ML-59"),
                 "limit_amount": money("***"), "premium": amt(d["lead"]),
                 "is_included": derived("Yes", "ML-59 - Lead Exclusion")},
                {"coverage_name": fv("Hazardous Conditions - Occupancy"), "limit_amount": money("***"),
                 "premium": amt(d["haz"]), "is_included": derived("Yes", "Hazardous Conditions - Occupancy")},
                {"coverage_name": fv("SM-26 Automatic Increase, %s" % d["settle"]),
                 "form_reference": fv("SM-26"),
                 "notes": fv("Modifies Coverage(s) at Renewal: Coverage A - Residence, Coverage D - Additional "
                             "Living Expense / Loss of Rent, Coverage B - Related Private Structures")},
            ],
        },
    }
