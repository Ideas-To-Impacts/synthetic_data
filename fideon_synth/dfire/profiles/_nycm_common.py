"""
Shared draws and canonical mapping for the three NYCM Insurance (New York Central
Mutual Fire Insurance Company) dwelling-fire documents.

The three sources are one document family (the same dwelling-fire policy printed
as an endorsement twice and as a revised renewal once), so the value model and
the gold mapping live here. Each profile module owns only its own REPLACE list.
This module has no SOURCE, so the engine's profile loader skips it.
"""

import copy
from datetime import timedelta
from pathlib import Path

import fitz

from .. import engine
from ..engine import addr, amt, date_fv, derived, fv, money
from ...values import SURNAME

NYCM_FIRST_F = ["Juniper", "Adelaide", "Perpetua", "Ottoline", "Marguerite", "Delphine",
                "Rosalind", "Clementine", "Winifred", "Henrietta", "Beatrix", "Seraphina",
                "Georgiana", "Wilhelmina", "Octavia", "Lavinia"]
NYCM_FIRST_M = ["Hollis", "Waldemar", "Cornelius", "Rutherford", "Ignatius", "Barnaby",
                "Thaddeus", "Ambrose", "Leopold", "Silas", "Alastair", "Montague",
                "Peregrine", "Bartholomew"]

# NY county -> FIPS-style three digit code (Hamilton = 041 as printed on the source)
COUNTY_CODE = {
    "Broome": "007", "Chemung": "015", "Chenango": "017", "Clinton": "019",
    "Columbia": "021", "Cortland": "023", "Delaware": "025", "Essex": "031",
    "Franklin": "033", "Fulton": "035", "Greene": "039", "Hamilton": "041",
    "Herkimer": "043", "Jefferson": "045", "Lewis": "049", "Madison": "053",
    "Montgomery": "057", "Oneida": "065", "Oswego": "075", "Otsego": "077",
    "Saratoga": "091", "Schenectady": "093", "Schoharie": "095", "St. Lawrence": "089",
    "Steuben": "101", "Tioga": "107", "Tompkins": "109", "Ulster": "111",
    "Warren": "113",
}

AGENCY_MID = ["INSURANCE GROUP", "INSURANCE SERVICES", "INSURANCE AGENCY",
              "COVERAGE GROUP", "BROKERAGE", "INSURANCE"]
AGENCY_SUF = ["INC", "LLC", "LTD"]

ALARMS = [("LOCAL FIRE ALARM", 3), ("CENTRAL STATION FIRE ALARM", 5),
          ("DIRECT FIRE DEPARTMENT ALARM", 5)]

ENDO_REASONS = [
    ("PER AGENT AMEND BASE FORM", "return"),
    ("PER AGENT ADD ALARM CREDIT", "return"),
    ("PER AGENT DECREASE COVERAGE A LIMIT", "return"),
    ("PER AGENT INCREASE COVERAGE A LIMIT", "additional"),
    ("PER AGENT CORRECT LOCATION DETAILS", "additional"),
]

CARRIER_NAME = "New York Central Mutual Fire Insurance Company"

FORMS = [
    ("FL-1", "11 79", "BASIC FORM"),
    ("FL-20", "11 79", "GENERAL POLICY PROVISIONS"),
    ("FL-84", "07 81", "NEW YORK ENDORSEMENT"),
    ("FL-250", "10 84", "AMENDATORY ENDORSEMENT"),
    ("DP 7570", "02 21", "CERTIFIED TERRORISM LOSS"),
    ("ML-216", "07 78", "PREMISES ALARM OR FIRE PROTECTION SYSTEM"),
    ("NYC 1045", "12 20", "POLICYHOLDER DISCLOSURE NOTICE OF TERRORISM INSURANCE COVERAGE"),
    ("IL N 160", "09 08", "FLOOD/MUDSLIDE EXCLUSION ADVISORY NOTICE TO POLICYHOLDERS - NEW YORK"),
    ("NYC-211", "08 91", "IMPORTANT SENIOR CITIZEN INFORMATION"),
    ("NYCM FL 268", "05 10", "INFLATION GUARD"),
    ("NYC FL 263", "09 14", "AMENDATORY ENDORSEMENT NEW YORK"),
]

# Footer pairs: not data. The policy number and form edition they repeat are already stated as
# policy.policy_number / policy_form_number / policy_form_edition; the rest is copyright and paging.
IGNORE_PAIRS = [
    r"^POLICY: \d+ Page \d+( of \d+)?$",          # running footer: policy number (duplicate) + page count
    r"EDITION: 11 79 Copyright 1979, American Association of Insurance",  # FL-1 form footer boilerplate
]

# Page furniture: the bare policy number left in the hidden OCR text of dfire page 5 repeats
# policy.policy_number. (The footer timestamps are keyed as document.print_date.)
FURNITURE = [r"^\d{7}$"]

# printed on every source but with no canonical leaf (module GAPS of each profile extends this)
COMMON_GAPS = [
    "no printed item currently lacks a canonical leaf (empty labels such as '# Units between Fire Walls', "
    "'Feet to Hydrant', 'Miles to Fire Department', 'Special Rating' print no value and are left to "
    "text_sections)",
]


def rpad(text, left, right, size=9.0, font="helv"):
    """Leading spaces so ``text`` ends near ``right`` when drawn from ``left``.

    The engine left-aligns non-numeric text at the source span's origin; the source
    prints several of these fields flush right.
    """
    width = fitz.get_text_length(text, fontname=font, fontsize=size)
    gap = (right - left) - width
    if gap <= 0:
        return text
    spaces = int(gap // fitz.get_text_length(" ", fontname=font, fontsize=size))
    return " " * spaces + text


def _zip9(v, zip5):
    return "%s-%04d" % (zip5, v.integer(1, 9999))


def _street(v, C):
    return C.street(v).upper()


def draw(v, C, kind):
    """kind: 'endorsement' or 'renewal'."""
    d = {"kind": kind}

    # insured
    female = v.maybe(0.5)
    first = v.choice(NYCM_FIRST_F if female else NYCM_FIRST_M)
    d["ins_name"] = "%s %s" % (first, v.choice(SURNAME))
    d["gender"] = "FEMALE" if female else "MALE"
    d["marital"] = v.choice(["MARRIED", "MARRIED", "SINGLE", "WIDOWED", "DIVORCED"])

    # location town, mailing address, agency
    p_city, p_zip, p_county = C.town(v)
    if v.maybe(0.7):
        m_city, m_zip = p_city, p_zip
    else:
        m_city, m_zip, _ = C.town(v)
    d.update(pr_street=_street(v, C), pr_city=p_city.upper(), pr_zip=p_zip,
             pr_zip9=_zip9(v, p_zip), pr_county=p_county.upper(),
             pr_county_code=COUNTY_CODE[p_county])
    d["pr_city_line"] = "%s, NY %s" % (d["pr_city"], d["pr_zip9"])
    d.update(ins_street=("PO BOX %d" % v.integer(12, 990)) if v.maybe(0.6) else _street(v, C),
             ins_city=m_city.upper(), ins_zip=m_zip)
    d["ins_city_line"] = "%s NY %s" % (d["ins_city"], m_zip)

    a_city, a_zip, _ = (p_city, p_zip, None) if v.maybe(0.5) else C.town(v)
    head = v.choice(C.AGENCY_HEAD).upper()
    mid = v.choice(AGENCY_MID)
    suf = v.choice(AGENCY_SUF)
    if fitz.get_text_length("%s %s" % (head, mid), fontname="helv", fontsize=9) > 168:
        mid = "INSURANCE"       # keep the first line clear of the 'Office' column
    d.update(ag_l1="%s %s" % (head, mid), ag_suf=suf, ag_head=head, ag_tail="%s %s" % (mid, suf))
    d["ag_name"] = "%s %s %s" % (head, mid, suf)
    d["ag_info_l1"] = rpad(d["ag_l1"], 135, 310)
    d["ag_info_l2"] = rpad(suf, 298, 310)
    slug = (head + mid.split()[0]).lower().replace(" ", "")
    mailbox = v.choice(["service", "info", "policy", "office"])
    if fitz.get_text_length("https://%s.com" % slug, fontname="helv", fontsize=9) > 140:
        slug = head.lower().replace(" ", "")
    d["ag_web"] = "https://%s.com" % slug
    d["ag_email"] = "%s@%s.com" % (mailbox, slug)
    d["ag_web_pad"] = rpad(d["ag_web"], 433, 577)
    d["ag_email_pad"] = rpad(d["ag_email"], 417, 577)
    d.update(ag_street=_street(v, C), ag_pobox="PO BOX %d" % v.integer(12, 990),
             ag_city=a_city.upper(), ag_zip9=_zip9(v, a_zip))
    d["ag_city_line"] = "%s NY %s" % (d["ag_city"], d["ag_zip9"])
    d.update(ag_office=C.phone(v), ag_fax=C.phone(v),
             ag_code="%05d" % v.integer(1000, 99999),
             ag_terr="%d%s" % (v.integer(1, 9), v.choice("ABCDEFGHJKLMNPRSTUVWXYZ")))
    d["paper_off"] = v.choice(["YES", "YES", "NO"])
    d["direct_mail"] = v.choice(["YES", "YES", "NO"])
    d["paper_off_pad"] = rpad(d["paper_off"], 298, 310)
    d["direct_mail_pad"] = rpad(d["direct_mail"], 298, 310)
    d["run_code"] = "D8/" + v.choice("ABCDEFGHJKLMNP")
    d["policy_no"] = v.policy_number("{7d}")
    if d["policy_no"].startswith("0"):
        d["policy_no"] = "6" + d["policy_no"][1:]

    # terms
    eff, exp = C.term(v, earliest=C.date(2023, 1, 1), latest=C.date(2025, 12, 31))
    inception = C.add_months(eff, -12 * v.integer(2, 24))
    d["inception"] = C.fmt(inception)
    d["protected"] = C.fmt(inception) if v.maybe(0.6) else C.fmt(C.add_months(inception, 12 * v.integer(1, 3)))
    d.update(eff=C.fmt(eff), exp=C.fmt(exp))
    if kind == "renewal":
        d["txn_eff"], d["txn_exp"] = d["eff"], d["exp"]
        pr_date = eff - timedelta(days=v.integer(20, 45))
        d["txn_label"] = v.choice(["REVISED RENEWAL", "REVISED RENEWAL", "RENEWAL"])
        d["txn_label_pad"] = rpad(d["txn_label"], 506, 578, size=8)
    else:
        txn = eff + timedelta(days=v.integer(30, 300))
        if txn >= exp:
            txn = exp - timedelta(days=30)
        d["txn_eff"], d["txn_exp"] = C.fmt(txn), d["exp"]
        pr_date = txn
        d["txn_label"] = "ENDORSEMENT"
    d["print_date"] = C.fmt(pr_date)
    d["print_time"] = "%02d:%02d:%02d" % (v.integer(7, 18), v.integer(0, 59), v.integer(0, 59))

    # dwelling
    d.update(year_built=str(v.integer(1890, 2018)), units=str(v.integer(1, 4)),
             constr=v.choice(["FRAME", "FRAME", "MASONRY", "MASONRY VENEER"]),
             occupied=v.choice(["VACANT", "OWNER", "TENANT"]),
             protect=v.choice(["PARTIALLY PROTECTED", "PROTECTED", "UNPROTECTED"]),
             lead=v.choice(["NO", "NO", "YES"]), seasonal=v.choice(["NO", "NO", "YES"]),
             territory=v.choice("ABCDEF"))
    d["fire_district"] = d["pr_city"]

    # money, rated off the limits
    cov_a = v.limit(90000, 480000, 1000)
    cov_c = v.choice([5000, 5000, 10000, 15000, 20000])
    cov_d = int(round(cov_a / 10.0 / 100.0)) * 100
    prem_a = int(round(cov_a / 1000.0 * v.rng.uniform(2.9, 4.6)))
    prem_c = int(round(cov_c / 1000.0 * 2.6))
    total = prem_a + prem_c
    alarm, pct = v.choice(ALARMS)
    savings = int(round(total * pct / 100.0))
    ded = v.choice([250, 500, 500, 1000, 2500])
    ig = v.choice([3, 4, 5, 6])
    d.update(cov_a=cov_a, cov_c=cov_c, cov_d=cov_d, prem_a=prem_a, prem_c=prem_c, total=total,
             alarm=alarm, alarm_pct=pct, savings=savings, ded=ded, ig=ig)
    d.update(cov_a_s=C.num(cov_a), cov_c_s=C.num(cov_c), cov_d_s=C.num(cov_d),
             prem_a_s=C.usd(prem_a), prem_c_s=C.usd(prem_c), total_s=C.usd(total),
             savings_s=C.usd(savings), ded_s=C.usd(ded, False), pct_s="%d%%" % pct,
             ig_s="%d.00%%" % ig)

    if kind == "endorsement":
        reason, direction = v.choice(ENDO_REASONS)
        change = v.integer(9, 140)
        if direction == "return":
            d["change_s"] = C.usd(-change)
            d["change_line"] = "THESE CHANGES HAVE RESULTED IN A RETURN PREMIUM OF %s." % d["change_s"]
        else:
            d["change_s"] = C.usd(change)
            d["change_line"] = "THESE CHANGES HAVE RESULTED IN AN ADDITIONAL PREMIUM OF %s." % d["change_s"]
        d.update(reason=reason, direction=direction, change=change)
    return d


def audit(d):
    out = []
    if d["prem_a"] + d["prem_c"] != d["total"]:
        out.append("coverage premiums do not sum to the total premium")
    if d["cov_a"] <= 0:
        out.append("coverage A limit must be positive")
    return out


def gold(d):
    kind = d["kind"]
    renewal = kind == "renewal"
    prop = addr(d["pr_street"], d["pr_city"], "NY", d["pr_zip9"])
    prop["county"] = fv(d["pr_county"])
    prop["county_code"] = fv(d["pr_county_code"])
    loc_addr = dict(prop)

    document = {
        "document_type": fv("DECLARATIONS", "Declaration"),
        "document_title_as_stated": fv("DECLARATIONS - *INSURED COPY*"),
        "line_of_business_as_stated": fv("DWELLING FIRE"),
        "copy_type": fv("INSURED COPY"),
        "form_run_code": fv(d["run_code"]),
        "transaction_type": fv(d["txn_label"]),
        "transaction_effective_date": date_fv(d["txn_eff"]),
        "print_date": date_fv("%s %s" % (d["print_date"], d["print_time"]), "%m/%d/%Y %H:%M:%S"),
        "applicable_coverages": [
            fv("Coverage A RESIDENCE FIRE"),
            fv("Coverage C PERSONAL PROPERTY FIRE"),
            fv("Coverage D ADDL LIVING EXP AND LOSS OF RENT FIRE INCL"),
        ],
    }
    premium = {
        "total_policy_premium": amt(d["total"]),
        "basic_premium": amt(d["total"]),
        "premium_by_coverage_part": [{"coverage_part": fv("PRIMARY BUILDING"), "premium": amt(d["total"])}],
        "discounts_and_credits": [{
            "description": fv("ALARM SYSTEM"),
            "form_reference": fv("ML-216"),
            "edition_date": fv("07 78"),
            "amount": amt(d["savings"]),
            "percentage": fv(d["pct_s"], float(d["alarm_pct"])),
            "is_applied": derived("Yes", "ALARM SYSTEM"),
        }],
    }
    if not renewal:
        premium_key = "return_premium" if d["direction"] == "return" else "additional_premium"
        premium[premium_key] = money(d["change_s"])
        premium["change_in_annual_premium"] = money(d["change_s"])
        premium["premium_adjustment_type"] = fv("RETURN PREMIUM" if d["direction"] == "return"
                                                else "ADDITIONAL PREMIUM")
        document["transaction_reason"] = fv(d["reason"])
        document["summary_of_changes"] = fv(d["change_line"])

    forms = []
    for number, edition, title in FORMS:
        row = {"form_number": fv(number), "edition_date": fv(edition), "form_title": fv(title),
               "premium": money(d["total_s"]) if number == "FL-1" else money("INCL.")}
        # the sub-table printed under the form's row
        if number == "ML-216":
            row["form_details"] = [{"description": fv(d["alarm"]),
                                    "percentage": fv(d["pct_s"], float(d["alarm_pct"]))}]
        elif number == "NYCM FL 268":
            row["form_details"] = [{"percentage": fv(d["ig_s"], float(d["ig"]))}]
        forms.append(row)

    dwelling = {
        "described_location": dict(prop),
        "occupancy_type": fv(d["occupied"]),
        "tenant_occupied": derived("Yes" if d["occupied"] == "TENANT" else "No", d["occupied"]),
        "construction_type": fv(d["constr"]),
        "protection_class": fv(d["protect"]),
        "territory_code": fv(d["territory"]),
        "year_built": fv(d["year_built"]),
        "number_of_units": fv(d["units"]),
        "seasonal_or_vacant": fv(d["seasonal"]),
        "protected_since_date": date_fv(d["protected"]),
        "lead_abatement": fv(d["lead"]),
        "fire_district": fv(d["fire_district"]),
        "structure_description": fv("PRIMARY BUILDING"),
        "fire_alarm_type": fv(d["alarm"]),
    }

    inflation = {
        "coverage_name": fv("INFLATION GUARD"),
        "form_reference": fv("NYCM FL 268"),
        "limit_amount": fv(d["ig_s"], float(d["ig"])),
        "limit_basis": fv("PERCENTAGE"),
        "is_included": derived("Yes", "INFLATION GUARD"),
    }

    g = {
        "document": document,
        "carrier": {
            "company_name": fv(CARRIER_NAME),
            "address": {"line_1": fv("1899 Central Plaza East"), "city": fv("Edmeston"),
                        "state": fv("NY"), "postal_code": fv("13335-1899")},
            "contact": {"phone": fv("800-234-6926"), "website": fv("www.nycm.com")},
            "state_of_issue": derived("NY", "Edmeston NY 13335-1899"),
        },
        "producer": {
            "agency_name": fv(d["ag_name"]),
            "producer_code": fv(d["ag_code"]),
            "territory_code": fv(d["ag_terr"]),
            "paper_off": fv(d["paper_off"], evidence="Paper Off"),
            "direct_mail": fv(d["direct_mail"], evidence="Direct Mail"),
            "address": addr(d["ag_street"], d["ag_city"], "NY", d["ag_zip9"], line_2=d["ag_pobox"]),
            "contact": {"phone": fv(d["ag_office"]), "fax": fv(d["ag_fax"]),
                        "email": fv(d["ag_email"]), "website": fv(d["ag_web"])},
        },
        "policy": {
            "policy_number": fv(d["policy_no"]),
            "policy_type": fv("DWELLING FIRE"),
            "policy_form_number": fv("FL-1"),
            "policy_form_name": fv("FL-1 - BASIC FORM"),
            "policy_form_edition": fv("11 79"),
            "policyholder_since_date": date_fv(d["inception"]),
            "effective_date": date_fv(d["eff"]),
            "expiration_date": date_fv(d["exp"]),
            "effective_time": fv("12:01 AM"),
            "expiration_time": fv("12:01 AM"),
            "time_zone": fv("EST"),
            "policy_term_months": fv("12 MONTHS", 12),
        },
        "named_insured": {
            "primary_name": fv(d["ins_name"]),
            "entity_type": derived("Individual", d["ins_name"]),
            "insured_type": fv("PRIMARY INSURED"),
            "marital_status": fv(d["marital"]),
            "gender": fv(d["gender"]),
            "mailing_address": addr(d["ins_street"], d["ins_city"], "NY", d["ins_zip"]),
        },
        "locations": [{
            "location_number": fv("1", 1, evidence="Location 1 of 1"),
            "address": loc_addr,
            "building_description": fv("PRIMARY BUILDING"),
            "construction_type": fv(d["constr"]),
            "year_built": fv(d["year_built"]),
            "occupancy_description": fv(d["occupied"]),
            "protection_class": fv(d["protect"]),
            "territory_code": fv(d["territory"]),
            "alarm_type": fv(d["alarm"]),
            "location_premium": amt(d["total"]),
            "coverages": [
                {"coverage_name": fv("Coverage A RESIDENCE FIRE"), "limit_amount": money(d["cov_a_s"]),
                 "premium": amt(d["prem_a"])},
                {"coverage_name": fv("Coverage C PERSONAL PROPERTY FIRE"), "limit_amount": money(d["cov_c_s"]),
                 "premium": amt(d["prem_c"])},
                {"coverage_name": fv("Coverage D ADDL LIVING EXP AND LOSS OF RENT FIRE INCL"),
                 "limit_amount": money(d["cov_d_s"]), "premium": money("INCL."),
                 "is_included": derived("Yes", "Coverage D ADDL LIVING EXP AND LOSS OF RENT FIRE INCL")},
            ],
        }],
        "premium": premium,
        "terrorism": {
            "terrorism_premium": money("$0.00"),
            "disclosure_form_number": fv("NYC 1045"),
            "tria_coverage_elected": derived("Yes", "CERTIFIED TERRORISM LOSS"),
        },
        "forms_and_endorsements": forms,
        "deductibles": [{
            "deductible_type": derived("All Other Perils", "Deductible"),
            "amount": money(d["ded_s"]),
        }],
        "state_notices": [
            {"form_reference": fv("NYC 1045"),
             "notice_title": fv("POLICYHOLDER DISCLOSURE NOTICE OF TERRORISM INSURANCE COVERAGE"),
             "state": derived("NY", "NEW YORK")},
            {"form_reference": fv("IL N 160"),
             "notice_title": fv("FLOOD/MUDSLIDE EXCLUSION ADVISORY NOTICE TO POLICYHOLDERS - NEW YORK"),
             "state": derived("NY", "NEW YORK")},
            {"form_reference": fv("NYC-211"), "notice_title": fv("IMPORTANT SENIOR CITIZEN INFORMATION"),
             "state": derived("NY", "NEW YORK")},
        ],
        "dwelling_fire": {
            "dwelling": dwelling,
            "property_coverages": {
                "coverage_a_dwelling_limit": money(d["cov_a_s"]),
                "coverage_c_personal_property_limit": money(d["cov_c_s"]),
                "coverage_e_additional_living_expense_limit": money(d["cov_d_s"]),
                "inflation_guard_percentage": fv(d["ig_s"], float(d["ig"])),
            },
            "deductibles": {"all_other_perils_deductible": money(d["ded_s"])},
            "optional_endorsement_coverages": [inflation],
        },
    }
    # "Coverage Information for Location 1 of 1": the one location's own page
    g["dwelling_fire"]["dwellings"] = [{
        "location_number": fv("1", 1, evidence="Location 1 of 1"),
        "described_location": dict(prop),
        "property_description": fv("PRIMARY BUILDING"),
        "coverages": copy.deepcopy(g["locations"][0]["coverages"]),
        "surcharges_none_reported": fv("*** NO SURCHARGES EXIST FOR THIS LOCATION ***"),
        "total_premium": amt(d["total"]),
    }]
    if renewal:
        g["policy"]["is_renewal"] = derived("Yes", d["txn_label"])
        g["billing"] = {"billing_note": fv("BILL WILL FOLLOW")}
    return g


# -- engine workarounds, active only while an NYCM document is being built ------------------
#
# 1. Background sampling: the engine paints each redaction box with the lightest of four pixels
#    2 px outside its corners. NYCM tables are ruled every 13 pt, so all four corners land on a
#    rule and the box is painted grey (or black). We sample eight points 3 px out, so a white
#    one is always found.
# 2. nycm_insurance_dfire.pdf has no usable text layer (vector glyph outlines under an invisible
#    OCR layer whose spans are half the size of the glyphs). For that document the span geometry
#    is taken from the clean-text twin nycm_insurance_dfire_endo.pdf (same layout, same words),
#    widened 1.2 pt on the right because the outlined glyphs sit about 1 pt beyond the twin's.

TWIN_FOR = {"nycm_insurance_dfire.pdf": "nycm_insurance_dfire_endo.pdf"}
_STATE = {"on": False}
_TWINS = {}


def _install():
    if getattr(engine._spans, "_nycm", False):
        return
    orig_spans, orig_bg = engine._spans, engine._background

    def spans(page):
        name = (getattr(page.parent, "name", "") or "").replace("\\", "/")
        _STATE["on"] = "/NYCM Insurance/" in name
        twin_name = TWIN_FOR.get(name.rsplit("/", 1)[-1]) if _STATE["on"] else None
        if not twin_name:
            return orig_spans(page)
        path = str(Path(name).with_name(twin_name))
        twin = _TWINS.get(path)
        if twin is None:
            twin = _TWINS[path] = fitz.open(path)
        out = []
        for sp in orig_spans(twin[page.number]):
            sp = dict(sp)
            b = sp["bbox"]
            sp["bbox"] = (b[0], b[1], b[2] + 1.2, b[3])
            out.append(sp)
        return out

    def background(pix, rect):
        if not _STATE["on"]:
            return orig_bg(pix, rect)
        mx, my = (rect.x0 + rect.x1) / 2.0, (rect.y0 + rect.y1) / 2.0
        points = [(rect.x0 - 3, rect.y0 - 3), (rect.x1 + 3, rect.y0 - 3),
                  (rect.x0 - 3, rect.y1 + 3), (rect.x1 + 3, rect.y1 + 3),
                  (rect.x0 - 3, my), (rect.x1 + 3, my), (mx, rect.y0 - 3), (mx, rect.y1 + 3)]
        best, colour = -1, (255, 255, 255)
        for px, py in points:
            x = min(max(int(px), 0), pix.width - 1)
            y = min(max(int(py), 0), pix.height - 1)
            r, g, b = pix.pixel(x, y)[:3]
            if r + g + b > best:
                best, colour = r + g + b, (r, g, b)
        return tuple(c / 255.0 for c in colour)

    spans._nycm = True
    engine._spans = spans
    engine._background = background


_install()
