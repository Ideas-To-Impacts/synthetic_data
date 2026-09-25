"""
Shared pieces for the Leatherstocking dwelling-fire profiles that cover the
"DFIRE", "LLP", "R-DFIRE" and dec sources.  It is not a profile itself (no
SOURCE), so the engine skips it; each profile module imports what it needs.

Everything here is layout-agnostic: the source-specific REPLACE lists, page
geometry and printed strings stay in the profile modules.
"""

from __future__ import annotations

import copy
import re

from ..engine import addr, amt, date_fv, derived, fv, logo, money  # noqa: F401

ROOT = "Leatherstocking Cooperative Insurance Company/dwelling_fire/"

DISCLAIMER = ("The Deductible reflected applies to all property coverages unless "
              "otherwise stipulated within the policy language.")
PLAN = "CO-OPERATIVE ASSESSMENT PLAN"
PLAN_SENTENCE = "THIS POLICY IS ISSUED ON THE " + PLAN

# carrier letterhead is form furniture: it is printed but never varies
STATIC = [
    r"^\$0\.00$",                   # included coverages / no fees
    r"13326", r"^Phone: 607-547",   # the carrier's own letterhead
]

# printed "Label: value" pairs that are not data: both repeat values already keyed elsewhere
IGNORE_PAIRS = [
    r"^Phone: 607-547-2007 Fax: 607-547-2056",   # carrier letterhead, keyed as carrier.contact.phone / fax
    r"^Policy Number: .* Page \d+ of \d+$",      # page footer, repeats the keyed policy number
]

# page furniture that looks like data: the letterhead phone line, keyed as carrier.contact
FURNITURE = [r"^Phone: 607-547-2007 Fax: 607-547-2056$"]

MODIFIES = "Modifies Coverage(s) at Renewal: "


# -- small helpers ------------------------------------------------------------------------

def usd(n, cents=True):
    body = format(abs(n), ",.2f" if cents else ",.0f")
    return "%s$%s" % ("-" if n < 0 else "", body)


def round_to(n, step):
    return int((n + step / 2.0) // step * step)


def code_of(name):
    """Agency code as the block prints it (a short mnemonic of the agency name)."""
    words = re.sub(r"[^A-Za-z ]", " ", name).split()
    return "".join(w[0] for w in words[:3]).upper()


def city_line(city, zip_code):
    return "%s, NY %s" % (city, zip_code)


# -- draws --------------------------------------------------------------------------------

def draw_parties(v, C):
    """Agency, two named insureds with their mailing address, and the insured property."""
    d = {}
    ag = C.address(v)
    agency = C.agency(v)
    work, fax = v.phone_pair()
    d.update(agency=agency, ag_code=code_of(agency), ag_street=ag["line_1"], ag_city=ag["city"],
             ag_zip=ag["postal_code"], ag_city_line=city_line(ag["city"], ag["postal_code"]),
             ag_work=work, ag_fax=fax)

    if v.maybe(0.25):
        d.update(ins1=C.business(v), ins2=C.person(v), ins1_kind="Business")
    elif v.maybe(0.6):
        a, b = C.couple(v)
        d.update(ins1=a, ins2=b, ins1_kind="Individual")
    else:
        a = C.person(v)
        b = C.person(v)
        while b == a:
            b = C.person(v)
        d.update(ins1=a, ins2=b, ins1_kind="Individual")
    ins = C.address(v)
    d.update(ins_street=C.po_box(v) if v.maybe(0.15) else ins["line_1"], ins_city=ins["city"],
             ins_zip=ins["postal_code"], ins_city_line=city_line(ins["city"], ins["postal_code"]))

    pr = C.address(v)
    d.update(prop_street=pr["line_1"], prop_city=pr["city"], prop_zip=pr["postal_code"],
             prop_county=pr["county"], prop_city_line=city_line(pr["city"], pr["postal_code"]),
             prop_line="Property 1 - %s - %s, NY %s - %s County" % (
                 pr["line_1"], pr["city"], pr["postal_code"], pr["county"]),
             prop_line2="Property 1 - %s; %s, NY %s" % (pr["line_1"], pr["city"], pr["postal_code"]))
    return d


def draw_term(v, C, d):
    eff, exp = C.term(v)
    d.update(eff=C.fmt(eff), exp=C.fmt(exp), eff_year=eff.year)


def draw_mortgagee_lines(v, C, d, ziplus4=False):
    """Mortgagee identity shared by the sources that print one."""
    m = C.address(v)
    zip_code = m["postal_code"]
    if ziplus4:
        zip_code = "%s-%04d" % (zip_code, v.integer(1000, 9999))
    street = C.po_box(v) if v.maybe(0.5) else m["line_1"]
    d.update(m_street=street, m_city=m["city"], m_zip=zip_code,
             m_city_line=city_line(m["city"], zip_code))


# -- gold ---------------------------------------------------------------------------------

_FORM_START = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)?\s*(?:\(|\d{1,2}/\d{2})")
_FORM_PARTS = re.compile(
    r"^(?P<num>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)?)\s*"
    r"(?:\((?P<ed1>[^)]+)\)|(?P<ed2>\d{1,2}/\d{2}))\s*(?P<title>.*)$")


def parse_forms(text):
    """Split the printed forms paragraph back into forms_and_endorsements entries."""
    entries = []
    for frag in (f.strip() for f in text.split(",")):
        if not frag:
            continue
        if entries and not _FORM_START.match(frag):
            entries[-1] += ", " + frag
        else:
            entries.append(frag)
    out = []
    for entry in entries:
        m = _FORM_PARTS.match(entry)
        item = {"form_number": fv(m.group("num")), "edition_date": fv(m.group("ed1") or m.group("ed2"))}
        title = m.group("title").strip()
        if title:
            item["form_title"] = fv(title)
        out.append(item)
    return out


def mortgagee(m):
    """Mortgagee object (the same shape serves dwelling_fire.mortgagees and interested_parties)."""
    a = {"line_1": fv(m["street"]), "city": fv(m["city"]), "state": fv("NY"),
         "postal_code": fv(m["zip"])}
    out = {"party_type": derived("Mortgagee", "1st Mortgagee"),
           "rank": fv("1st", 1, evidence="1st Mortgagee"),
           "name": fv(m["name"]), "address": a,
           "applies_to": fv("Property 1 - %s" % m["applies_street"])}
    if m.get("clause"):
        out["clause_type"] = fv(m["clause"])
    if m.get("desc"):
        out["description_of_interest"] = fv(m["desc"])
    if m.get("loan"):
        out["loan_number"] = fv(m["loan"], m["loan"].lstrip("#"))
    return out


def build_gold(d, S):
    """The canonical gold shared by every source; S holds what differs per source.

    S keys: lob, transaction, rows (Section I / II schedule rows), optional (Optional
    Items schedule rows), notes (endorsement blocks with no schedule row), form_name,
    forms_text, dwelling (dict of extra dwelling leaves), location (extra location
    leaves), deductibles (list), mortgagee (dict or None), extra (dict merged last).
    A row is a dict: name, limit, premium, leaf=(group, key)|None, basis, form.
    """
    eff, exp = d["eff"], d["exp"]
    total = usd(d["total"])
    prop = addr(d["prop_street"], d["prop_city"], "NY", d["prop_zip"])
    prop["county"] = fv("%s County" % d["prop_county"], d["prop_county"])

    rows, optional = S["rows"], S["optional"]
    parts = ["Section I", "Section II", "Optional Items"]

    coverages, prop_cov, liab_cov = [], {}, {}
    for r in rows:
        c = {"coverage_name": fv(r["name"]), "limit_amount": money(r["limit"]),
             "premium": money(r["premium"])}
        if r.get("basis"):
            c["limit_basis"] = fv(r["basis"])
        if r.get("form"):
            c["form_reference"] = fv(r["form"])
        coverages.append(c)
        if r.get("leaf"):
            group, key = r["leaf"]
            (prop_cov if group == "property" else liab_cov)[key] = money(r["limit"])
    prop_cov["loss_settlement_basis"] = fv(d["settle"])
    prop_cov["covered_causes_of_loss"] = fv(S["form_name"])
    prop_cov.update(S.get("property_extra", {}))
    liab_cov.update(S.get("liability_extra", {}))

    credits = []
    for r in rows + optional:
        if r["premium"].startswith("-"):
            credit = {"description": fv(r["name"]), "amount": money(r["premium"]),
                      "is_applied": derived("Yes", r["name"])}
            if r.get("form"):
                credit["form_reference"] = fv(r["form"])
            credits.append(credit)

    opt_cov = []
    for r in optional:
        o = {"coverage_name": fv(r["name"]), "limit_amount": money(r["limit"]),
             "premium": money(r["premium"]), "is_included": derived("Yes", r["name"])}
        if r.get("form"):
            o["form_reference"] = fv(r["form"])
        opt_cov.append(o)
    for n in S.get("notes", []):
        o = {"coverage_name": fv(n["name"]), "is_included": derived("Yes", n["name"])}
        if n.get("form"):
            o["form_reference"] = fv(n["form"])
        if n.get("notes"):
            o["notes"] = fv(n["notes"])
        opt_cov.append(o)

    dwelling = {
        "described_location": dict(prop),
        "occupancy_type": fv("1-2 Family"),
        "protection_class": fv(d["protect"]),
        "territory_code": fv(d["territory"]),
    }
    if d.get("constr"):
        dwelling["construction_type"] = fv(d["constr"])
    dwelling.update(S.get("dwelling", {}))

    location = {
        "location_number": fv("1", 1, evidence="Property 1"),
        "address": dict(prop),
        "occupancy_description": fv("1-2 Family"),
        "protection_class": fv(d["protect"]),
        "territory_code": fv(d["territory"]),
        "coverages": coverages,
    }
    if d.get("constr"):
        location["construction_type"] = fv(d["constr"])
    location.update(S.get("location", {}))

    named = {
        "primary_name": fv(d["ins1"]),
        "entity_type": derived(d["ins1_kind"]),
        "mailing_address": addr(d["ins_street"], d["ins_city"], "NY", d["ins_zip"]),
        "additional_named_insureds": [{"name": fv(d["ins2"]), "entity_type": derived("Individual")}],
    }

    gold = {
        "document": {
            "document_type": fv("DECLARATION", "Declaration"),
            "document_title_as_stated": fv("DECLARATION, %s" % S["lob"]),
            "line_of_business_as_stated": fv(S["lob"]),
            "transaction_type": fv(S["transaction"]),
            "transaction_effective_date": date_fv(eff),
            "coverage_parts_present": [fv(p) for p in parts],
            "applicable_coverages": [fv(r["name"]) for r in rows + optional],
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
            "producer_code": fv(d["ag_code"]),
            "address": addr(d["ag_street"], d["ag_city"], "NY", d["ag_zip"]),
            "contact": {"phone": fv(d["ag_work"]), "fax": fv(d["ag_fax"])},
        },
        "policy": {
            "policy_number": fv(d["policy_no"]),
            "alternate_policy_identifiers": [{"identifier_type": fv("Policy ID"),
                                              "identifier_value": fv(d["policy_no"])}],
            "policy_form_number": fv("LCIC(4/11)"),
            "policy_form_edition": fv("4/11"),
            "policy_form_name": fv(S["form_name"]),
            "policy_type": fv(S["lob"]),
            "plan_type": fv(PLAN),
            "is_assessable": derived("Yes", "ASSESSMENT PLAN"),
            "effective_date": date_fv(eff),
            "expiration_date": date_fv(exp),
            "effective_time": fv("12:01 AM", evidence="12:01"),
            "expiration_time": fv("12:01 AM", evidence="12:01"),
            "time_zone": fv("Standard Time"),
            "policy_term_months": derived("12", eff, 12),
            "is_renewal": derived("Yes" if S["transaction"] == "Renewal" else "No", S["transaction"]),
        },
        "named_insured": named,
        "locations": [location],
        "premium": {
            "total_policy_premium": money(total),
            "basic_premium": money(total),
            "premium_by_coverage_part": [{"coverage_part": fv("Property 1"), "premium": money(total)}],
            "taxes_and_fees": [{"description": fv("Fees"), "amount": money("$0.00")}],
        },
        "forms_and_endorsements": parse_forms(S["forms_text"]),
        "deductibles": S["deductibles"],
        "dwelling_fire": {
            "dwelling": dwelling,
            "property_coverages": prop_cov,
            "liability_coverages": liab_cov,
            "deductibles": {"all_other_perils_deductible": money(usd(d["deductible"]))},
            "optional_endorsement_coverages": opt_cov,
        },
    }
    if credits:
        gold["premium"]["discounts_and_credits"] = credits
    if S.get("mortgagee"):
        m = mortgagee(S["mortgagee"])
        gold["dwelling_fire"]["mortgagees"] = [m]
        gold["interested_parties"] = [copy.deepcopy(m)]
    gold.update(S.get("extra", {}))
    return gold


def deductible_entry(d, applies_raw, evidence=None, notes=None, derived_applies=False):
    entry = {
        "applies_to": derived(applies_raw, evidence) if derived_applies else fv(applies_raw, evidence=evidence),
        "deductible_type": derived("All Other Perils", "Deductible"),
        "amount": money(usd(d["deductible"])),
    }
    if notes:
        entry["notes"] = fv(notes)
    return entry


def row(name, limit, prem, leaf=None, basis=None, form=None):
    """One schedule row: ``limit`` is printed text, ``prem`` a whole-dollar number."""
    return {"name": name, "limit": limit, "premium": usd(prem), "prem": prem,
            "leaf": leaf, "basis": basis, "form": form}


def audit_rows(d, rows, optional):
    """Premium schedule arithmetic: every row (Section I, II and Optional) sums to the total."""
    total = sum(r["prem"] for r in rows + optional)
    problems = []
    if d["cov_a"] <= 0 or total != d["total"]:
        problems.append("premium schedule sums to %s, not the printed total %s" % (total, d["total"]))
    return problems
