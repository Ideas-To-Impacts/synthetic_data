"""
Shared pieces for the Leatherstocking numbered dwelling-fire declarations
(2-DFIRE, 3-DFIRE, 4-DFIRE, 5- DFIRE, 6- DFIRE).  NOT a profile: it has no
SOURCE, so the engine's profile loader skips it.

The five sources are close cousins of ``1- DFIRE_redacted``: the same masthead,
"Mail To / Named Insured / Agency" block, term box, property schedule, rating
information and forms paragraph.  What differs is the schedule of coverages
(rows), the optional items, a mortgagee block on the 4-page ones, and where
the redaction overlays sit.  The profiles list their own source strings; this
module supplies the seeded draws, the amount-replacement helper and the gold
builder that maps the whole declaration onto the canonical schema.
"""

from __future__ import annotations

from ...fields import yes_no
from ..engine import addr, date_fv, derived, fv, logo, money
from ._leatherstocking import property_fields

DISCLAIMER = ("The Deductible reflected applies to all property coverages unless "
              "otherwise stipulated within the policy language.")

# forms paragraph, shared head (identical in all five sources)
FORMS_HEAD = [
    ("FL-18", "6/96", "Intentional Act Exclusion"),
    ("FL-20", "1/92", "Agreement"),
    ("FL-83", "02/02", "Amendment of Policy Conditions"),
    ("FL-90", "11/06", "Clarification Endorsement"),
    ("FMD-1", "12/94", "Important Flood Insurance Notice"),
    ("LCI-11", "4/91", "Senior Citizen Form"),
    ("PR", "3/01", "Notice of Privacy Policy"),
    ("LCI-J", "9/17", "By-Laws"),
    ("FL-21", "05/10", "Suit Against Us Amendatory Endorsement"),
]
FORMS_BASIC = FORMS_HEAD + [
    ("FL-1", "2/92", "Causes of Loss"),
    ("FL-OLT", "1/92", "Premises Liability Insurance Coverage Part"),
    ("ML-59", "6/99", "Lead Exclusion"),
    ("SM-26", "7/00", "Automatic Increase"),
    ("FL-80", "7/96", "Redefinition of Insured"),
]

NAMES = {
    "a": "Coverage A - Residence",
    "b": "Coverage B - Related Private Structures",
    "c": "Coverage C - Personal Property",
    "d": "Coverage D - Additional Living Expense / Loss of Rent",
    "l": "Coverage L - Premises Liability",
    "mp": "Coverage M - Medical Payments - Per Person",
    "mo": "Coverage M - Medical Payments - Per Occurrence",
    "eca": "EC - Residence",
    "vmma": "VMM - Residence",
    "ecb": "EC - Related Private Structures",
    "vmmb": "VMM - Related Private Structures",
    "ecc": "EC - Personal Property",
    "vmmc": "VMM - Personal Property",
    "ecd": "EC - Additional Living Expense / Loss of Rent",
    "vmmd": "VMM - Additional Living Expense / Loss of Rent",
    "ml59": "ML-59 - Lead Exclusion",
    "haz": "Hazardous Conditions - Occupancy",
    "vcr": "FL-VC Tenant Vandalism Endorsement - Residence",
    "vcs": "FL-VC Tenant Vandalism Endorsement - Related Private Structures",
    "fl16": "FL-16 - Incidental Business Activities",
    "ml216": "ML-216 - Protective Devices",
    "ml56": "ML-56 - Related Private Structure Exclusion",
    "mlwd": "ML-WD - Water Backup-Sewers and Drains",
}
BASE = ("a", "b", "c", "d", "l", "mp", "mo")          # coverages proper
LIMIT_BASIS = {"l": "Each Occurrence", "mp": "Per Person", "mo": "Per Occurrence"}
# the schedule section each row is printed under; every other row is an Optional Item
SECTION = dict([(k, "Section I") for k in ("a", "eca", "vmma", "b", "ecb", "vmmb", "c", "ecc",
                                           "vmmc", "d", "ecd", "vmmd")]
               + [(k, "Section II") for k in ("l", "mp", "mo", "ml59")])
# optional/endorsement rows: (form reference, coverage code) as printed in the name
OPT_META = {
    "eca": (None, "EC"), "ecb": (None, "EC"), "ecc": (None, "EC"), "ecd": (None, "EC"),
    "vmma": (None, "VMM"), "vmmb": (None, "VMM"), "vmmc": (None, "VMM"), "vmmd": (None, "VMM"),
    "ml59": ("ML-59", None), "vcr": ("FL-VC", None), "vcs": ("FL-VC", None),
    "fl16": ("FL-16", None), "ml216": ("ML-216", None), "ml56": ("ML-56", None),
    "mlwd": ("ML-WD", None),
}

KIND_ROWS = {
    "basic": ["a", "l", "ml59", "haz"],
    "med": ["a", "l", "mp", "mo", "ml59", "haz"],
    "d4": ["a", "eca", "vmma", "b", "ecb", "vmmb", "d", "ecd", "vmmd", "l", "mp", "mo",
           "ml59", "vcr", "vcs", "fl16", "ml216", "ml56"],
    "d6": ["a", "eca", "vmma", "b", "ecb", "vmmb", "c", "ecc", "vmmc", "d", "ecd", "vmmd",
           "l", "mp", "mo", "ml59", "mlwd"],
}

SERVICERS = [("San Antonio", "TX", "78269"), ("Dallas", "TX", "75265"),
             ("Phoenix", "AZ", "85072"), ("Des Moines", "IA", "50306"),
             ("Buffalo", "NY", "14240"), ("Syracuse", "NY", "13220")]


# -- draws ------------------------------------------------------------------------------

def draw_base(v, C, pn_pattern, terr_tail="All Others"):
    """Everything on the declaration that is not the coverage schedule."""
    d = {}
    name = C.agency(v)
    for _ in range(60):                     # keep "<agency> - CODE" inside its column
        if len(name) <= 27:
            break
        name = C.agency(v)
    ag = C.address(v)
    d.update(agency=name, ag_code="".join(w[0] for w in name.split()[:3]).upper(),
             ag_street=ag["line_1"], ag_city=ag["city"], ag_zip=ag["postal_code"],
             ag_city_line="%s, NY %s" % (ag["city"], ag["postal_code"]),
             ag_work=C.phone(v, "paren"), ag_fax=C.phone(v, "paren"))

    if v.maybe(0.3):
        d["ins_name"], d["ins_kind"] = C.business(v), "Business"
    else:
        a, b = C.couple(v)
        d["ins_name"] = ("%s & %s" % (a.split()[0], b)) if v.maybe(0.6) else a
        d["ins_kind"] = "Individual"
    ins = C.address(v)
    d.update(ins_street=C.po_box(v) if v.maybe(0.15) else ins["line_1"], ins_city=ins["city"],
             ins_zip=ins["postal_code"], ins_city_line="%s, NY %s" % (ins["city"], ins["postal_code"]))

    pr = C.address(v)
    d.update(prop_street=pr["line_1"], prop_city=pr["city"], prop_zip=pr["postal_code"],
             prop_county=pr["county"])
    d["prop_line"] = "Property 1 - %s - %s, NY %s - %s County" % (
        pr["line_1"], pr["city"], pr["postal_code"], pr["county"])

    d["policy_no"] = v.policy_number(pn_pattern)
    eff, exp = C.term(v)
    d.update(eff=C.fmt(eff), exp=C.fmt(exp), txn=v.choice(["New Policy", "Renewal"]))

    fam = v.integer(1, 4)
    ded = v.choice([500, 1000, 1000, 2500, 5000])
    d.update(settle=v.choice(["ACV", "RC"]),
             constr=v.choice(["Frame", "Frame", "Masonry", "Masonry Veneer"]),
             protect=v.choice(["Protected", "Semi-Protected", "Unprotected"]),
             occupancy="1-2 Family" if fam <= 2 else "3-4 Family",
             classif="Dwelling - %d Family" % fam,
             territory="%02d - %s" % (v.integer(1, 30), terr_tail),
             condition=v.choice(["Unoccupancy", "Vacancy", "Seasonal Occupancy"]),
             deductible=ded, ded_s=C.usd(ded), zero_s="$0.00")
    return d


def draw_mortgagee(v, C):
    lender = C.lender(v)
    if v.maybe(0.5):
        city, state, zip5 = v.choice(SERVICERS)
        postal = "%s-%04d" % (zip5, v.integer(0, 9999))
    else:
        city, postal, _county = C.town(v)
        state = "NY"
    return dict(ml_name=lender, ml_street=C.po_box(v), ml_city=city, ml_state=state,
                ml_zip=postal, ml_city_line="%s, %s %s" % (city, state, postal))


def schedule(v, C, d, kind):
    """Draw the coverage schedule so every premium and total ties by construction."""
    keys = KIND_ROWS[kind]
    lim, prem = {}, {}

    a = v.limit(90000, 600000, 100)
    lim["a"], prem["a"] = a, round(a / 1000.0 * v.rng.uniform(1.8, 4.8))
    prem["eca"] = round(prem["a"] * v.rng.uniform(0.10, 0.30))
    prem["vmma"] = round(prem["a"] * v.rng.uniform(0.12, 0.33))

    b = C.round_to(a * v.choice([0.05, 0.1]), 100)          # B and D rate identically
    lim["b"] = lim["d"] = b
    prem["b"] = prem["d"] = round(b / 1000.0 * v.rng.uniform(1.6, 3.0))
    prem["ecb"] = prem["vmmb"] = prem["ecd"] = prem["vmmd"] = max(1, round(prem["b"] * v.rng.uniform(0.1, 0.4)))

    c = v.choice([5000, 10000, 15000, 25000])
    lim["c"], prem["c"] = c, round(c / 1000.0 * v.rng.uniform(1.5, 2.5))
    prem["ecc"], prem["vmmc"] = max(1, round(prem["c"] * 0.1)), max(1, round(prem["c"] * 0.4))

    l_lim = v.choice([100000, 300000, 500000, 1000000, 1000000])
    span = {100000: (38, 70), 300000: (60, 110), 500000: (80, 150), 1000000: (80, 300)}[l_lim]
    lim["l"], prem["l"] = l_lim, v.integer(*span)
    lim["mp"], prem["mp"] = v.choice([1000, 2000, 5000, 5000]), v.integer(24, 44)
    lim["mo"], prem["mo"] = v.choice([25000, 50000]), 0

    prem["ml59"] = -v.integer(4, 20)
    prem["haz"] = v.integer(120, 600)
    prem["vcr"], prem["vcs"] = v.integer(60, 180), v.integer(1, 6)
    prem["fl16"] = v.integer(300, 1100)
    prem["ml216"] = -v.integer(30, 120)
    prem["ml56"] = 0
    prem["mlwd"] = v.integer(15, 60)

    for k in keys:
        d[k + "_lim"], d[k + "_prem"] = lim.get(k), prem[k]
        d[k + "_lim_s"] = C.usd(lim[k], False) if k in lim and k in BASE else "***"
        d[k + "_prem_s"] = C.usd(prem[k])
    pt = sum(prem[k] for k in keys)
    fees = round(pt * v.rng.uniform(0.004, 0.009), 2) if v.maybe(0.5) else 0.0
    total = round(pt + fees, 2)
    d.update(pt=pt, pt_s=C.usd(pt), fees=fees, fees_s=C.usd(fees), total=total, total_s=C.usd(total),
             rows=keys)
    return d


# -- replacement helpers ----------------------------------------------------------------

def amount_entries(cells):
    """REPLACE entries for the schedule's money cells.

    ``cells`` lists (printed source text, key of the drawn printed string) in
    reading order (page, then top to bottom).  A source string that repeats is
    told apart by its position; if every repeat maps to one key a single entry
    replaces them all.  Whole-span matches only, so "$5,000" never lands inside
    "Deductible: $5,000.00".
    """
    groups = {}
    for src, key in cells:
        groups.setdefault(src, []).append(key)
    out = []
    for src, keys in groups.items():
        if len(set(keys)) == 1:
            out.append((src, "{%s}" % keys[0], {"exact": True, "leak": False}))
        else:
            for n, key in enumerate(keys):
                out.append((src, "{%s}" % key, {"exact": True, "nth": n, "leak": False}))
    return out


def audit(d):
    bad = []
    if sum(d[k + "_prem"] for k in d["rows"]) != d["pt"]:
        bad.append("premium schedule does not sum to the property total")
    if round(d["pt"] + d["fees"], 2) != d["total"]:
        bad.append("coverage premium + fees does not equal the total")
    if d["a_lim"] <= 0:
        bad.append("Coverage A limit must be positive")
    return bad


# -- gold -------------------------------------------------------------------------------

def _parts(d):
    prop = addr(d["prop_street"], d["prop_city"], "NY", d["prop_zip"])
    prop["county"] = fv("%s County" % d["prop_county"], d["prop_county"])
    return prop


def _mortgagee(d, clause):
    def party():
        return {
            "party_type": derived("Mortgagee", "MORTGAGEE(S):"),
            "rank": derived("1", "1st Mortgagee", 1),
            "name": fv(d["ml_name"]),
            "address": addr(d["ml_street"], d["ml_city"], d["ml_state"], d["ml_zip"]),
            "clause_type": fv(clause),
            "applies_to": fv("Property 1 - %s" % d["prop_street"]),
            "description_of_interest": fv("1st Mortgagee"),
        }
    return party


def build_gold(d, *, forms, form_name, sm26, has_classif=True, has_condition=False,
               ded_rows=("a",), settle_rows=("a",), printed_pages=None, mortgagee_clause=None,
               location_extra=None, optional_extra=None, dwelling_extra=None):
    """The gold for one generated declaration; every leaf here is printed on its pages."""
    eff, exp, rows = d["eff"], d["exp"], d["rows"]
    prop = _parts(d)
    renewal = d["txn"] == "Renewal"

    document = {
        "document_type": fv("DECLARATION", "Declaration"),
        "document_title_as_stated": fv("DECLARATION, Dwelling Fire"),
        "line_of_business_as_stated": fv("Dwelling Fire"),
        "transaction_type": fv(d["txn"]),
        "transaction_effective_date": date_fv(eff),
        "coverage_parts_present": [fv("Section I"), fv("Section II"), fv("Optional Items")],
        "applicable_coverages": [fv(NAMES[k]) for k in rows],
    }
    if printed_pages:
        document["page_count"] = fv(str(printed_pages), printed_pages,
                                    evidence="Page 1 of %d" % printed_pages)

    # coverage schedule rows: coverages proper -> locations[].coverages[]
    coverages = []
    for k in rows:
        if k not in BASE:
            continue
        cov = {"coverage_name": fv(NAMES[k]), "limit_amount": money(d[k + "_lim_s"]),
               "premium": money(d[k + "_prem_s"])}
        if k in LIMIT_BASIS:
            cov["limit_basis"] = fv(LIMIT_BASIS[k])
        if k in ded_rows:
            cov["deductible_amount"] = money(d["ded_s"])
        if k in settle_rows:
            cov["valuation_basis"] = fv(d["settle"])
        coverages.append(cov)

    location = {
        "location_number": fv("1", 1, evidence="Property 1"),
        "address": dict(prop),
        "occupancy_description": fv(d["occupancy"]),
        "construction_type": fv(d["constr"]),
        "protection_class": fv(d["protect"]),
        "territory_code": fv(d["territory"]),
        "location_type": derived("Dwelling", "Property 1"),
        "coverages": coverages,
    }
    location.update(location_extra or {})

    # optional / endorsement rows + the SM-26 automatic increase note
    optional = []
    for k in rows:
        if k in BASE:
            continue
        item = {"coverage_name": fv(NAMES[k]), "limit_amount": money("***"),
                "premium": money(d[k + "_prem_s"]), "is_included": derived("Yes", NAMES[k])}
        form_ref, code = OPT_META.get(k, (None, None))
        if form_ref:
            item["form_reference"] = fv(form_ref)
        if code:
            item["coverage_code"] = fv(code)
        item.update((optional_extra or {}).get(k, {}))
        optional.append(item)
    optional.append({
        "coverage_name": fv("SM-26 Automatic Increase, %s" % d["settle"]),
        "form_reference": fv("SM-26"),
        "notes": fv("Modifies Coverage(s) at Renewal: %s" % sm26),
    })

    dwelling = {
        "described_location": dict(prop),
        "occupancy_type": fv(d["occupancy"]),
        "construction_type": fv(d["constr"]),
        "protection_class": fv(d["protect"]),
        "territory_code": fv(d["territory"]),
        "rating_zone": fv("All Other"),
    }
    dwelling.update(dwelling_extra or {})
    if has_classif:
        dwelling["occupancy_classification_code"] = fv(d["classif"])
    if has_condition:
        dwelling["hazardous_conditions_occupancy"] = fv(d["condition"])
        if d["condition"] != "Unoccupancy":
            dwelling["seasonal_or_vacant"] = fv(d["condition"])

    property_cov = {"loss_settlement_basis": fv(d["settle"]),
                    "covered_causes_of_loss": fv(form_name)}
    limit_leaf = {"a": ["coverage_a_dwelling_limit"], "b": ["coverage_b_other_structures_limit"],
                  "c": ["coverage_c_personal_property_limit"],
                  "d": ["coverage_e_additional_living_expense_limit",
                        "coverage_d_fair_rental_value_limit"]}
    liability = {}
    for k in rows:
        for leaf in limit_leaf.get(k, []):
            property_cov[leaf] = money(d[k + "_lim_s"])
    if "l" in rows:
        liability["coverage_l_premises_liability_limit"] = money(d["l_lim_s"])
    if "mp" in rows:
        liability["coverage_m_medical_payments_per_person_limit"] = money(d["mp_lim_s"])
    if "mo" in rows:
        liability["coverage_m_medical_payments_per_occurrence_limit"] = money(d["mo_lim_s"])

    gold = {
        "document": document,
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
            "producer_code": fv(d["ag_code"]),
            "address": addr(d["ag_street"], d["ag_city"], "NY", d["ag_zip"]),
            "contact": {"phone": fv(d["ag_work"]), "fax": fv(d["ag_fax"])},
        },
        "policy": {
            "policy_number": fv(d["policy_no"]),
            "alternate_policy_identifiers": [{"identifier_type": fv("Policy ID"),
                                              "identifier_value": fv(d["policy_no"])}],
            "policy_form_number": fv("LCIC(4/11)"),
            "policy_form_edition": derived("4/11", "LCIC(4/11)"),
            "policy_form_name": fv(form_name),
            "policy_type": fv("Dwelling Fire", evidence="Dwelling Fire"),
            "plan_type": fv("CO-OPERATIVE ASSESSMENT PLAN"),
            "effective_date": date_fv(eff),
            "expiration_date": date_fv(exp),
            "effective_time": fv("12:01 AM", evidence="12:01"),
            "expiration_time": fv("12:01 AM", evidence="12:01"),
            "time_zone": fv("Standard Time"),
            "policy_term_months": derived("12", eff, 12),
            "is_renewal": yes_no(renewal, d["txn"]),
        },
        "named_insured": {
            "primary_name": fv(d["ins_name"]),
            "entity_type": derived(d["ins_kind"], d["ins_name"]),
            "mailing_address": addr(d["ins_street"], d["ins_city"], "NY", d["ins_zip"]),
        },
        "locations": [location],
        "premium": {
            "total_policy_premium": money(d["total_s"]),
            "basic_premium": money(d["pt_s"]),
            "premium_by_coverage_part": [{"coverage_part": fv("Property 1"),
                                          "premium": money(d["pt_s"])}],
            "taxes_and_fees": [{"description": fv("Fees"), "amount": money(d["fees_s"])}],
        },
        "forms_and_endorsements": [
            {"form_number": fv(n), "edition_date": fv(e), "form_title": fv(t)} for n, e, t in forms],
        "deductibles": [{
            "applies_to": fv("all property coverages", evidence="all property coverages"),
            "deductible_type": derived("All Other Perils", "Deductible"),
            "amount": money(d["ded_s"]),
            "notes": fv(DISCLAIMER),
        }],
        "dwelling_fire": {
            "dwelling": dwelling,
            "property_coverages": property_cov,
            "liability_coverages": liability,
            "deductibles": {"all_other_perils_deductible": money(d["ded_s"])},
            "optional_endorsement_coverages": optional,
        },
    }
    if mortgagee_clause:
        party = _mortgagee(d, mortgagee_clause)
        gold["dwelling_fire"]["mortgagees"] = [party()]
        gold["interested_parties"] = [party()]

    entry = dict(zip([k for k in rows if k in BASE], coverages))
    entry.update(zip([k for k in rows if k not in BASE], optional))
    schedule = [(SECTION.get(k, "Optional Items"), entry[k]) for k in rows]
    property_fields(gold, prop, schedule, d["pt_s"], d["fees_s"], d["settle"], sm26)
    return gold
