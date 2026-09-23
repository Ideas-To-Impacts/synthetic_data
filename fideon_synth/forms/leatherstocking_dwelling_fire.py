"""
Leatherstocking Cooperative Insurance Company - Dwelling Fire declarations.

The worked example. Read it as the answer to "what does a template look
like?", then copy the shape for your own carrier.

Three parts, in the order you will write them:

  the value sets    plain dicts, hand-written for the first few and generated
                    past that, so a team can start with five careful
                    documents and grow to two hundred
  ``_draw``         the page, built from :mod:`fideon_synth.draw` primitives
  ``gold``          the canonical document, leaves built from
                    :mod:`fideon_synth.fields`

Nothing outside this module reads the variant dict, so its shape is yours to
choose. What the rest of the package needs is the four methods at the bottom.
"""

from __future__ import annotations

from ..draw import (BOLD, BOLD_ITALIC, ITALIC, MONO, REGULAR, SERIF_ITALIC,
                    Column, Sheet, Table, render)
from ..fields import (derived, date_fv, fmt_money, fv, money, money_from,
                      yes_no)
from ..template import Template
from ..values import NY_TOWNS, Values

# ── the carrier ─────────────────────────────────────────────────────────────

CARRIER = {
    "company_name": "Leatherstocking Cooperative Insurance Company",
    "address": {"line_1": "PO Box 630", "line_2": "4313 County Highway 11",
                "city": "Cooperstown", "state": "NY", "postal_code": "13326"},
    "phone": "607-547-2007",
    "fax": "607-547-2056",
    "website": "www.leatherstockinginsurance.com",
    "form_code": "LCIC(4/11)",
    "notice": "THIS POLICY IS ISSUED ON THE CO-OPERATIVE ASSESSMENT PLAN",
}

PREAMBLE = [
    "This replaces all previously issued policy declarations, if any. This "
    "policy applies only to accidents, occurrences or losses which happen "
    "during the policy period shown above.",
    "This policy applies only to those coverages below for which a limit of "
    "liability or premium charge is shown. Our limit of liability for each "
    "coverage shall not be more than the amount stated for such coverage, "
    "subject to all the terms of this policy.",
]

DISCLAIMER = ("The Deductible reflected applies to all property coverages "
              "unless otherwise stipulated within the policy language.")

# ── page geometry, read off the original at 400 dpi ─────────────────────────

RULE_L, RULE_R = 46.0, 568.0
TEXT_L = 52.0
COL_X = (56.0, 231.0, 401.0)
COL_DIV = (224.0, 391.0)
BODY_MIN_Y = 115.0              # page one stops here, above the signature
SIG_TOP, SIG_BOT = 83.0, 43.0
FOOT_Y = 22.0

COLUMNS = [Column(46.0, 435.0), Column(435.0, 500.0, "right"),
           Column(500.0, 568.0, "right")]
HEADINGS = [None, "COVERAGE LIMIT", "PREMIUM"]


def totals(v):
    """Every printed money figure, derived from the schedule rather than
    stored beside it.

    The original form's printed Property Total is two dollars off the sum of
    its own rows. Reproducing that quirk would put a known-wrong number in a
    file whose entire purpose is to be right, and would fail the audit rule
    the schema itself declares. So the arithmetic here ties.
    """
    rows = ([(n, p) for n, _, p in v["section_i"]]
            + [(n, p) for n, _, p, _ in v["section_ii"]]
            + [(n, p) for n, _, p in v["optional"]])
    property_total = round(sum(p for _, p in rows), 2)
    fees = round(sum(a for _, a in v["fees"]), 2)
    return {"rows": rows, "property_total": property_total,
            "coverage_premium": property_total, "fees": fees,
            "total": round(property_total + fees, 2)}


# ── the page ────────────────────────────────────────────────────────────────

def _logo(sheet, x, y):
    """The oval device beside the company name.

    A stand-in, deliberately. Reproducing a carrier's registered mark on a
    synthetic document would make it look like something it is not; this
    occupies the same space and reads as a logo, which is all the layout
    needs.
    """
    c = sheet.canvas
    c.saveState()
    c.setLineWidth(0.9)
    c.ellipse(x, y, x + 17, y + 26)
    c.setLineWidth(0.7)
    p = c.beginPath()
    p.moveTo(x + 8.5, y + 21)
    p.curveTo(x + 5, y + 16, x + 6, y + 11, x + 7, y + 5)
    p.moveTo(x + 8.5, y + 18)
    p.curveTo(x + 12, y + 15, x + 12.5, y + 10, x + 11, y + 5)
    c.drawPath(p)
    c.circle(x + 8.5, y + 21.5, 1.9, stroke=1, fill=1)
    c.restoreState()


def _masthead(sheet, v):
    _logo(sheet, RULE_L, 726)
    sheet.text(RULE_L + 24, 731, CARRIER["company_name"], SERIF_ITALIC, 15.5)

    a = CARRIER["address"]
    y = 745
    for line in ["%s, %s" % (a["line_1"], a["line_2"]),
                 "%s, %s %s" % (a["city"], a["state"], a["postal_code"]),
                 "Phone: %s Fax: %s" % (CARRIER["phone"], CARRIER["fax"]),
                 CARRIER["website"]]:
        sheet.right_text(RULE_R, y, line, REGULAR, 7.6)
        y -= 9.4

    sheet.rule(707, 1.0)
    sheet.text(RULE_L, 694, v["transaction"], BOLD_ITALIC, 8.6)
    width = sheet.measure(v["policy_number"], REGULAR, 8.6)
    sheet.right_text(RULE_R - width, 694, "Policy ID: ", BOLD, 8.6)
    sheet.right_text(RULE_R, 694, v["policy_number"], REGULAR, 8.6)


def _signature_panel(sheet):
    """Fixed furniture on page one.

    Drawn with the masthead rather than after the schedule: when the schedule
    carries over - which is most of the time - anything drawn after it lands
    on page two, and the panel silently disappears from the page that is
    supposed to carry it.
    """
    sheet.box(RULE_L, SIG_BOT, RULE_R, SIG_TOP)
    sheet.vline(391, SIG_BOT, SIG_TOP, 0.9)
    sheet.text(RULE_L + 6, SIG_TOP - 9, "SIGNATURE", BOLD, 5.2)
    sheet.text(397, SIG_TOP - 9, "DATE", BOLD, 5.2)
    sheet.text(RULE_L + 6, SIG_BOT + 12, "✖", BOLD, 12)
    sheet.scrawl(76, SIG_BOT + 14, width=82, height=15)


def _footer(sheet, v):
    total = sheet.total_pages or sheet.page
    sheet.footer(FOOT_Y, left=CARRIER["form_code"],
                 centre=[("Policy Number:", REGULAR),
                         (v["policy_number"], BOLD)],
                 right="Page %d of %d" % (sheet.page, total))


def _party_box(sheet, v, y_top):
    ag, ia = v["agency"], v["insured_address"]
    mail = [ag["name"], ag["name_2"], ag["line_1"],
            "%s, %s %s" % (ag["city"], ag["state"], ag["postal_code"])]
    insured = list(v["insureds"]) + [
        ia["line_1"], "%s, %s %s" % (ia["city"], ia["state"],
                                     ia["postal_code"])]
    agency = mail + ["Work: %s" % ag["work"], "Fax: %s" % ag["fax"]]

    y_bottom = sheet.column_box(
        y_top, [("Mail To:", mail), ("Named Insured(s):", insured),
                ("Agency:", agency)], COL_X, COL_DIV)

    y_term = y_bottom - 14
    sheet.text(COL_X[0], y_term, "Policy Term Effective Date:", BOLD, 8.4)
    sheet.text(COL_X[1], y_term, "Policy Term Expiration Date:", BOLD, 8.4)
    y_value = y_term - 10.2
    for x, printed in ((COL_X[0], v["effective_date"]),
                       (COL_X[1], v["expiration_date"])):
        sheet.run(x, y_value,
                  [("%s, %s " % (printed, v["effective_time"]), REGULAR, 8.4),
                   (v["time_zone"], ITALIC, 8.4)])

    y_end = y_value - 12
    sheet.rule(y_end, 1.0)
    return y_end


def _rating_block(sheet, y, title, pairs, page_break):
    needed = 12 + 9.6 * len(pairs)
    if y - needed < BODY_MIN_Y:
        y = page_break()
    sheet.swatch(TEXT_L, y - 5.5)
    x = TEXT_L + 10
    end = sheet.text(x, y - 6, title + ": ", BOLD, 8.2)
    sheet.text(end, y - 6, "Property 1", BOLD_ITALIC, 8.2)
    y -= 17

    for label, value in pairs:
        lead = "%s: " % label
        sheet.text(x + 6, y, lead, REGULAR, 7.8)
        vx = x + 6 + sheet.measure(lead, REGULAR, 7.8)
        for i, line in enumerate(sheet.wrap(value, RULE_R - vx, ITALIC, 7.8)):
            sheet.text(vx if i == 0 else x + 6, y, line, ITALIC, 7.8)
            y -= 9.6
    return y - 3


def _draw(sheet, v):
    t = totals(v)
    _masthead(sheet, v)
    _signature_panel(sheet)

    def page_break():
        _footer(sheet, v)
        return sheet.new_page(730.0)

    end = sheet.text(RULE_L, 645, "DECLARATION,", BOLD, 16.5)
    sheet.text(end + sheet.measure(" ", BOLD, 16.5), 645, "Dwelling Fire",
               ITALIC, 16.5)

    y = _party_box(sheet, v, 630) - 30
    sheet.text(TEXT_L, y, CARRIER["notice"], REGULAR, 8)
    y -= 24
    for para in PREAMBLE:
        y = sheet.paragraph(TEXT_L, y, para, RULE_R - TEXT_L, REGULAR, 8) - 12

    p = v["property"]
    y -= 20
    sheet.text(TEXT_L - 2, y,
               "Property %d - %s - %s %s %s - %s County"
               % (p["number"], p["line_1"], p["city"], p["state"],
                  p["postal_code"], p["county"]), BOLD, 8.6)
    tail = ": %d of %d" % (p["number"], p["of"])
    sheet.right_text(RULE_R - sheet.measure(tail, REGULAR, 8.6), y,
                     "Property", BOLD, 8.6)
    sheet.right_text(RULE_R, y, tail, REGULAR, 8.6)
    y -= 6

    table = Table(sheet, COLUMNS)
    sections = [
        ("Section I", [(n, l, pr, None) for n, l, pr in v["section_i"]]),
        ("Section II", list(v["section_ii"])),
        ("Optional Items", [(n, l, pr, None) for n, l, pr in v["optional"]]),
    ]
    for label, rows in sections:
        if y - table.bar_height - table.row_height < BODY_MIN_Y:
            y = page_break()
        y = table.bar(y, [label] + HEADINGS[1:])
        for i, (name, limit, premium, note) in enumerate(rows):
            if y - table.row_height < BODY_MIN_Y:
                y = page_break()
                y = table.bar(y, [label] + HEADINGS[1:])   # repeats on carry
                i = 0
            y = table.row(y, [name, limit, fmt_money(premium)], note=note,
                          rule_above=i > 0)

    if y - table.row_height < BODY_MIN_Y:
        y = page_break()
        y = table.bar(y, ["Optional Items"] + HEADINGS[1:])
    y = table.row(y, ["Property Total", "***",
                      fmt_money(t["property_total"])], rule_above=True)
    table.close(y)

    if y - 60 < BODY_MIN_Y:
        y = page_break()
    y -= 30
    for label, amount in (("Coverage Premium:", t["coverage_premium"]),
                          ("Fees:", t["fees"]), ("Total:", t["total"])):
        sheet.right_text(452.0, y, label, REGULAR, 8.6)
        sheet.right_text(RULE_R - 8, y, fmt_money(amount), BOLD, 8.6)
        y -= 14

    y -= 8
    if y - 40 < BODY_MIN_Y:
        y = page_break()
    sheet.text(TEXT_L + 6, y, "RATING INFORMATION:", BOLD, 8.4)
    sheet.rule(y - 6, 0.7)
    y -= 20
    for title, pairs in v["rating"]:
        y = _rating_block(sheet, y, title, pairs, page_break)

    lines = sheet.wrap(v["forms"], RULE_R - TEXT_L, MONO, 8.2)
    if y - (26 + 9.8 * len(lines)) < BODY_MIN_Y:
        y = page_break()
    y -= 10
    sheet.text(TEXT_L, y,
               "Policy Subject to the Following Forms and Endorsements:",
               "Times-Bold", 8.6)
    y -= 12
    for line in lines:
        sheet.text(TEXT_L, y, line, MONO, 8.2)
        y -= 9.8

    _footer(sheet, v)


# ── gold ────────────────────────────────────────────────────────────────────

import re

_FORM_START = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)?\s*(?:\(|\d{2}/\d{2})")
_FORM_PARTS = re.compile(
    r"^(?P<num>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)?)\s*"
    r"(?:\((?P<ed1>[^)]+)\)|(?P<ed2>\d{2}/\d{2}))\s*(?P<title>.*)$")


def parse_forms(text):
    """Split the printed forms paragraph back into entries.

    Commas separate entries and also appear inside titles, so a fragment that
    does not open with something shaped like a form number is glued back onto
    the one before it.
    """
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
        if not m:
            out.append({"form_number": fv(entry)})
            continue
        out.append({
            "form_number": fv(m.group("num")),
            "edition_date": fv(m.group("ed1") or m.group("ed2")),
            "form_title": fv(m.group("title").strip() or None),
            "is_included": yes_no(True, m.group("num")),
        })
    return out


PROPERTY_LIMIT = {
    "Coverage A - Residence": "coverage_a_dwelling_limit",
    "Coverage B - Related Private Structures":
        "coverage_b_other_structures_limit",
    "Coverage C - Personal Property": "coverage_c_personal_property_limit",
    "Coverage D - Additional Living Expense / Loss of Rent":
        "coverage_e_additional_living_expense_limit",
}
LIABILITY_LIMIT = {
    "Coverage L - Premises Liability": "coverage_l_premises_liability_limit",
    "Coverage M - Medical Payments":
        "coverage_m_medical_payments_per_person_limit",
}


def _coverage(name, limit, premium, part, note=None):
    cov = {"coverage_type": fv(part), "coverage_name": fv(name),
           "limit": money(limit), "premium": money_from(premium)}
    if note:
        cov["sublimit"] = fv(note)
    return cov


def build_gold(v, pdf_name, pages):
    t = totals(v)
    p, ag, ia, dw = (v["property"], v["agency"], v["insured_address"],
                     v["dwelling"])

    location = {"line_1": fv(p["line_1"]), "city": fv(p["city"]),
                "state": fv(p["state"]), "postal_code": fv(p["postal_code"]),
                "county": fv("%s County" % p["county"], p["county"])}

    doc = {
        "document": {
            "document_type": fv("DECLARATION", "Declaration"),
            "document_title_as_stated": fv("DECLARATION, Dwelling Fire"),
            "line_of_business_as_stated": fv("Dwelling Fire"),
            "coverage_parts_present": [fv("Section I"), fv("Section II"),
                                       fv("Optional Items")],
            "applicable_coverages": (
                [fv(n) for n, _, _ in v["section_i"]]
                + [fv(n) for n, _, _, _ in v["section_ii"]]),
            "transaction_type": fv(v["transaction"]),
            "transaction_effective_date": date_fv(v["effective_date"]),
            "page_count": fv(str(pages), pages,
                             evidence="Page 1 of %d" % pages),
            "source_file_name": derived(pdf_name),
            "source_carrier_folder": fv("Leatherstocking"),
        },
        "carrier": {
            "company_name": fv(CARRIER["company_name"]),
            "address": {k: fv(val) for k, val
                        in CARRIER["address"].items()},
            "contact": {"phone": fv(CARRIER["phone"]),
                        "fax": fv(CARRIER["fax"]),
                        "website": fv(CARRIER["website"])},
            "state_of_issue": derived("NY", "Cooperstown, NY 13326"),
        },
        "producer": {
            "agency_name": fv("%s %s" % (ag["name"], ag["name_2"])),
            "producer_code": fv(ag["name_2"]),
            "address": {"line_1": fv(ag["line_1"]), "city": fv(ag["city"]),
                        "state": fv(ag["state"]),
                        "postal_code": fv(ag["postal_code"])},
            "contact": {"phone": fv("Work: %s" % ag["work"], ag["work"]),
                        "fax": fv("Fax: %s" % ag["fax"], ag["fax"])},
        },
        "policy": {
            "policy_number": fv(v["policy_number"]),
            "policy_form_number": fv(CARRIER["form_code"]),
            "policy_type": fv("Dwelling Fire"),
            "effective_date": date_fv(v["effective_date"]),
            "expiration_date": date_fv(v["expiration_date"]),
            "effective_time": fv(v["effective_time"]),
            "time_zone": fv(v["time_zone"]),
            "policy_term_months": derived("12", v["effective_date"], 12),
            "is_renewal": yes_no(v["is_renewal"], v["transaction"]),
        },
        "named_insured": {
            "primary_name": fv(v["insureds"][0]),
            "entity_type": derived(v["entity_type"], v["insureds"][0]),
            "mailing_address": {
                "line_1": fv(ia["line_1"]), "city": fv(ia["city"]),
                "state": fv(ia["state"]),
                "postal_code": fv(ia["postal_code"])},
        },
        "locations": [{
            "location_number": fv(str(p["number"]), p["number"]),
            "address": dict(location),
            "occupancy_description": fv(dw["occupancy_type"]),
            "construction_type": fv(dw["construction_type"]),
            "protection_class": fv(dw["protection_class"]),
            "territory_code": fv(dw["territory_code"]),
            "location_type": derived("Dwelling", "Property %d" % p["number"]),
        }],
        "premium": {
            "total_policy_premium": money_from(t["total"]),
            "premium_by_coverage_part": [{
                "coverage_part": fv("Property %d" % p["number"]),
                "premium": money_from(t["property_total"])}],
        },
        "forms_and_endorsements": parse_forms(v["forms"]),
        "coverages": (
            [_coverage(n, l, pr, "Section I") for n, l, pr in v["section_i"]]
            + [_coverage(n, l, pr, "Section II", note)
               for n, l, pr, note in v["section_ii"]]
            + [_coverage(n, l, pr, "Optional Items")
               for n, l, pr in v["optional"]]),
        "deductibles": [{
            "applies_to": fv("All property coverages"),
            "deductible_type": derived("All Other Perils", "Deductible"),
            "amount": money_from(dw["aop_deductible"]),
            "notes": fv(DISCLAIMER),
        }],
    }

    extra = v["insureds"][1:]
    if extra:
        doc["named_insured"]["additional_named_insureds"] = [
            {"name": fv(n), "entity_type": derived("Individual", n)}
            for n in extra]

    # The page prints a line labelled "Fees" and nothing about what kind.
    # Naming the kind would be reading something that is not there.
    if v["fees"]:
        doc["premium"]["taxes_and_fees"] = [{
            "description": fv("Fees"),
            "amount": money_from(sum(a for _, a in v["fees"]))}]

    if dw.get("wind_hail_deductible"):
        doc["deductibles"].append({
            "applies_to": derived("Windstorm or Hail",
                                  "Wind/Hail Deductible"),
            "deductible_type": derived("Wind/Hail", "Wind/Hail Deductible"),
            "amount": money_from(dw["wind_hail_deductible"])})

    dwelling = {
        "described_location": dict(location),
        "occupancy_type": fv(dw["occupancy_type"]),
        "tenant_occupied": yes_no(dw["tenant_occupied"],
                                  dw["occupancy_type"]),
        "construction_type": fv(dw["construction_type"]),
        "protection_class": fv(dw["protection_class"]),
        "territory_code": fv(dw["territory_code"]),
    }
    if dw.get("seasonal_or_vacant"):
        dwelling["seasonal_or_vacant"] = fv(dw["seasonal_or_vacant"])
    if dw.get("hazardous_conditions_occupancy"):
        dwelling["hazardous_conditions_occupancy"] = fv(
            dw["hazardous_conditions_occupancy"])

    property_cov = {"loss_settlement_basis": fv(dw["loss_settlement_basis"]),
                    "covered_causes_of_loss": fv(dw["covered_causes_of_loss"])}
    for name, limit, _ in v["section_i"]:
        if name in PROPERTY_LIMIT:
            property_cov[PROPERTY_LIMIT[name]] = money(limit)
    liability_cov = {}
    for name, limit, _, _ in v["section_ii"]:
        if name in LIABILITY_LIMIT:
            liability_cov[LIABILITY_LIMIT[name]] = money(limit)

    df_deductibles = {
        "all_other_perils_deductible": money_from(dw["aop_deductible"])}
    if dw.get("wind_hail_deductible"):
        df_deductibles["wind_hail_deductible"] = money_from(
            dw["wind_hail_deductible"])

    doc["dwelling_fire"] = {
        "dwelling": dwelling,
        "property_coverages": property_cov,
        "liability_coverages": liability_cov,
        "deductibles": df_deductibles,
        "optional_endorsement_coverages": [
            {"coverage_name": fv(n), "limit_amount": money(l),
             "premium": money_from(pr), "is_included": yes_no(True, n)}
            for n, l, pr in v["optional"]],
        "rating_characteristics": {
            "classification_description": fv(dw["classification_description"]),
            "territorial_zone": fv(dw["territory_code"]),
        },
    }

    doc["text_sections"] = {
        "assessment_plan_notice": {
            "section_id": "assessment_plan_notice",
            "raw_text": CARRIER["notice"], "page_range": [1],
            "form_number": None},
        "declarations_preamble": {
            "section_id": "declarations_preamble",
            "raw_text": " ".join(PREAMBLE), "page_range": [1],
            "form_number": None},
        "forms_and_endorsements": {
            "section_id": "forms_and_endorsements",
            "raw_text": ("Policy Subject to the Following Forms and "
                         "Endorsements: " + v["forms"]),
            "page_range": [pages], "form_number": None},
    }
    return doc


# ── generated variants ──────────────────────────────────────────────────────

FORM_POOL = [
    "FL-18 (6/96) Intentional Act Exclusion",
    "FL-20 (1/92) Agreement",
    "FL-83 (02/02) Amendment of Policy Conditions",
    "FL-90 (11/06) Clarification Endorsement",
    "FMD-1 (12/94) Important Flood Insurance Notice",
    "PR (3/01) Notice of Privacy Policy",
    "LCI-J (9/17) By-Laws",
    "FL-21 05/10 Suit Against Us Amendatory Endorsement",
    "FL-OLT (1/92) Premises Liability Insurance Coverage Part",
    "FL-80 (7/96) Redefinition of Insured",
]
OPTIONAL_FORMS = [
    "LCI-11 (4/91) Senior Citizen Form",
    "LCIC-DX (06/23) Exclusion of Canine Related Injuries or Damages",
    "ML-121 (6/99) Personal Injury",
    "SM-26 (7/00) Automatic Increase",
]
CONSTRUCTION = ["Frame", "Masonry", "Frame", "Masonry Veneer"]
PROTECTION = ["Protected", "Semi-Protected", "Unprotected"]
OCCUPANCY = [("1-2 Family", False, None), ("Tenant Occupied", True, None),
             ("Seasonal", False, "Seasonal"), ("1-2 Family", False, None)]


def _generated(vals, index):
    """One plausible declaration, composed rather than hand-written.

    The premiums are rated off the limits they sit beside rather than drawn
    at random - a page of unrelated numbers does not survive anyone reading
    it - and the schedule is summed by :func:`totals`, so the arithmetic ties
    by construction rather than by care.
    """
    town = vals.choice(NY_TOWNS)
    risk = vals.address(town)
    renewal = vals.maybe(0.45)
    llc = vals.maybe(0.15)
    insureds = ([vals.company(), vals.person()] if llc
                else vals.household(vals.integer(1, 3)))
    mailing = vals.address(town, po_box=llc)

    agency_name = vals.agency()
    work, fax = vals.phone_pair()
    agency_town = vals.choice(NY_TOWNS)
    code = vals.initials(3)
    # the agency's street must not be the risk's: one page carrying
    # "2020 Beaver Meadow Rd" and "220 Beaver Meadow Rd" reads as a bug even
    # when it is only a coincidence
    for _ in range(8):
        agency_line = vals.address(agency_town)["line_1"]
        if agency_line.split(" ", 1)[-1] != risk["line_1"].split(" ", 1)[-1]:
            break

    effective, expiration = vals.term()
    occupancy, tenant, seasonal = vals.choice(OCCUPANCY)
    construction = vals.choice(CONSTRUCTION)
    protection = vals.choice(PROTECTION)
    basic = vals.maybe(0.6)
    form_name = "Basic Form (FL-1)" if basic else "Broad Form (FL-2)"
    settlement = "RC" if vals.maybe(0.75) else "ACV"
    deductible = vals.choice([500, 1000, 1000, 2500])

    dwelling_limit = vals.limit(95000, 480000, 1000)
    section_i = [("Coverage A - Residence", "${:,}".format(dwelling_limit),
                  float(vals.rate(dwelling_limit, 1000.0, (3.0, 4.2))))]
    section_i.append(("EC - Residence", "***",
                      float(vals.rate(dwelling_limit, 1000.0, (0.45, 0.62)))))
    section_i.append(("VMM - Residence", "***",
                      float(max(vals.rate(dwelling_limit, 1000.0,
                                          (0.04, 0.07)), 1))))
    if tenant:
        other = int(dwelling_limit * 0.1)
        rent = int(dwelling_limit * 0.08)
        section_i.append(("Coverage B - Related Private Structures",
                          "${:,}".format(other),
                          float(vals.rate(other, 1000.0, (1.0, 1.5)))))
        section_i.append(("Coverage D - Additional Living Expense / "
                          "Loss of Rent", "${:,}".format(rent),
                          float(vals.rate(rent, 1000.0, (1.0, 1.4)))))
    else:
        contents = vals.limit(5000, int(dwelling_limit * 0.5) or 5000, 500)
        section_i.append(("Coverage C - Personal Property",
                          "${:,}".format(contents),
                          float(max(vals.rate(contents, 1000.0,
                                              (2.6, 3.4)), 1))))
        section_i.append(("EC - Personal Property", "***",
                          float(max(vals.rate(contents, 1000.0,
                                              (0.2, 0.5)), 1))))
        if vals.maybe(0.7):
            section_i.append(("VMM - Personal Property", "***", 1.0))

    liability = vals.choice([100000, 300000, 500000, 500000])
    section_ii = [("Coverage L - Premises Liability",
                   "${:,}".format(liability),
                   float(vals.integer(38, 82)), "(Each Occurrence)")]
    if vals.maybe(0.4):
        medical = vals.choice([1000, 2000, 5000])
        section_ii.append(("Coverage M - Medical Payments",
                           "${:,}".format(medical),
                           float(vals.integer(6, 14)), "(Each Person)"))
    if vals.maybe(0.5):
        section_ii.append(("ML-59 - Lead Exclusion", "***", -5.0, None))
    if vals.maybe(0.35):
        section_ii.append(("FL-52A Trampoline Exclusion", "***", -2.0, None))

    optional = [("ML-WD - Water Backup-Sewers and Drains", "***", 25.0)]
    if vals.maybe(0.4):
        optional.append(("SM-26 - Automatic Increase, RC", "***",
                         float(vals.integer(14, 34))))
    if vals.maybe(0.35):
        optional.append(("ML-54 - Theft Coverage", "***",
                         float(vals.integer(40, 80))))
    hazard = vals.maybe(0.45)
    if hazard:
        optional.append(("Hazardous Conditions - Occupancy", "***",
                         float(vals.integer(120, 340))))
    if seasonal and vals.maybe(0.6):
        optional.append(("Seasonal Dwelling Surcharge", "***",
                         float(vals.integer(60, 120))))

    fees = [("Policy Fee", float(vals.choice([15, 25])))] \
        if vals.maybe(0.3) else []
    wind_hail = vals.choice([2500, 5000]) if seasonal else None

    rating = [("Coverage A - Residence",
               [("Deductible", "$%s" % format(float(deductible), ",.2f"))]
               + ([("Wind/Hail Deductible",
                    "$%s" % format(float(wind_hail), ",.2f"))]
                  if wind_hail else [])
               + [("Loss Settlement", settlement),
                  ("Construction", construction),
                  ("Protection", protection),
                  ("Zone", "All Other"),
                  ("Form", form_name),
                  ("Occupancy", occupancy),
                  ("Disclaimer", DISCLAIMER)])]
    second = ("Coverage B - Related Private Structures" if tenant
              else "Coverage C - Personal Property")
    rating.append((second, [
        ("Deductible", "$%s" % format(float(deductible), ",.2f")),
        ("Construction", construction), ("Protection", protection),
        ("Zone", "All Other"), ("Occupancy", occupancy),
        ("Form", form_name)]))
    classification = "Dwelling - %s" % (
        "1 Family Tenant Occupied" if tenant
        else "1 Family Seasonal" if seasonal else "1 Family")
    territory = "%02d - %s" % (vals.integer(5, 24), risk["county"])
    rating.append(("Coverage L - Premises Liability",
                   [("Classification", classification),
                    ("Territory Code", territory)]))
    if hazard:
        rating.append(("Hazardous Conditions - Occupancy",
                       [("Condition", "Seasonal Unoccupancy" if seasonal
                         else "Unoccupancy")]))

    forms = FORM_POOL + ["FL-%sR (1/92) Causes of Loss" % ("1" if basic
                                                           else "2"),
                         "ML-WD (1.1) Water Damage-Sewers and Drains"]
    forms += vals.pick(OPTIONAL_FORMS, vals.integer(1, 3))

    year = int(effective[-4:])
    return {
        "key": "df_%03d_%s" % (index, risk["city"].lower().replace(" ", "")),
        "transaction": "Renewal Policy" if renewal else "New Policy",
        "is_renewal": renewal,
        "policy_number": vals.policy_number("10-{year}-{5d}", year=year),
        "effective_date": effective, "expiration_date": expiration,
        "effective_time": "12:01AM", "time_zone": "Standard Time",
        "agency": {"name": agency_name + " -", "name_2": code,
                   "line_1": agency_line,
                   "city": agency_town[0], "state": "NY",
                   "postal_code": agency_town[1],
                   "work": work, "fax": fax},
        "insureds": insureds,
        "entity_type": ("Limited Liability Company" if llc else "Individual"),
        "insured_address": mailing,
        "property": dict(risk, number=1, of=1),
        "section_i": section_i,
        "section_ii": section_ii,
        "optional": optional,
        "fees": fees,
        "rating": rating,
        "forms": ", ".join(forms),
        "dwelling": {
            "occupancy_type": occupancy,
            "tenant_occupied": tenant,
            "construction_type": construction,
            "protection_class": protection,
            "territory_code": territory,
            "loss_settlement_basis": settlement,
            "covered_causes_of_loss": form_name,
            "seasonal_or_vacant": seasonal,
            "hazardous_conditions_occupancy": (
                ("Seasonal Unoccupancy" if seasonal else "Unoccupancy")
                if hazard else None),
            "classification_description": classification,
            "aop_deductible": float(deductible),
            "wind_hail_deductible": float(wind_hail) if wind_hail else None,
        },
    }


# ── the template ────────────────────────────────────────────────────────────

class LeatherstockingDwellingFire(Template):
    """Two-page Dwelling Fire declarations on the LCIC(4/11) form."""

    key = "leatherstocking_dwelling_fire"
    lob = "dwelling_fire"
    description = "Leatherstocking Co-operative - Dwelling Fire declarations"

    def variants(self, count=None, seed=0):
        from .leatherstocking_handwritten import HAND_WRITTEN
        if count is None:
            return list(HAND_WRITTEN)
        out = list(HAND_WRITTEN[:count])
        vals = Values(seed)
        while len(out) < count:
            out.append(_generated(vals, len(out) + 1))
        return out

    def render(self, variant, path):
        return render(path, lambda sheet: _draw(sheet, variant),
                      left=RULE_L, right=RULE_R,
                      title="Declaration, Dwelling Fire - %s"
                            % variant["policy_number"],
                      author=CARRIER["company_name"],
                      subject="Synthetic benchmark document - not a policy")

    def gold(self, variant, pdf_name, pages):
        return build_gold(variant, pdf_name, pages)
