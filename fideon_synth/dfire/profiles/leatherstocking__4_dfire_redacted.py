"""
Leatherstocking Cooperative Insurance Company - "4-DFIRE_redacted.pdf"

Four-file-page Dwelling Fire declaration (renewal in the source; the fourth
sheet is blank and the footer reads "Page n of 3").  Special Form (FL-3) with
Coverage A, B, D (each with EC and VMM), L, M, ML-59, FL-VC tenant vandalism,
FL-16 incidental business, ML-216 protective devices, ML-56 related private
structure exclusion, a nonzero fee line and a mortgagee block.

Tidied redaction artefacts: the agency address (real text) gets consecutive
lines and the stray city overlays are erased; the insured and property
overlays are upsized; the property line (real street + overlaid city/county)
becomes one bold line, and so does the mortgagee's property reference; the
scrambled "Location" overlay on the ML-56 detail is replaced.  Several city
overlays are the same string on page 1 ("Ilion, NY 13357"); they are told
apart by position (insured, Mail To, Agency, property).  "RBF" on the agency
line is a producer code, printed here after the agency name.

GAPS (printed but no canonical leaf): the SIGNATURE box's date (not printed); the "Mail To"
block (repeats the producer); the blank fourth sheet.
"""

from ..engine import fv, money
from . import _lcic_common as L

SOURCE = "Leatherstocking Cooperative Insurance Company/dwelling_fire/4-DFIRE_redacted.pdf"

GAPS = ["SIGNATURE / DATE box: no date printed (the signature is keyed)",
        "Mail To block (repeats the producer address)"]

IGNORE_PAIRS = [
    r"^Phone: 607-547-2007 Fax: 607-547-2056$",   # carrier letterhead; keyed as carrier.contact phone/fax
    r"^Policy Number: \S+ Page \d+ of \d+$",       # page footer; policy number is keyed, page counter is furniture
]

FURNITURE = [
    r"^Phone: 607-547-2007 Fax: 607-547-2056$",   # carrier letterhead; already keyed as carrier.contact phone/fax
]

FORMS = L.FORMS_HEAD + [
    ("FL-3B", "9/00", "Causes of Loss"),
    ("FL-VC", "3/19", "Tenant Vandalism Endorsement"),
    ("FL-16", "1/92", "Incidental Business Activity Endorsement"),
    ("FL-OLT", "1/92", "Premises Liability Insurance Coverage Part"),
    ("ML-216", "6/99", "Premises Alarm"),
    ("ML-59", "6/99", "Lead Exclusion"),
    ("ML-56", "7/10", "Related Private Structure Exclusion"),
    ("SM-26", "7/00", "Automatic Increase"),
    ("FL-80", "7/96", "Redefinition of Insured"),
]
SM26 = ("Coverage B - Related Private Structures, Coverage D - Additional Living Expense / "
        "Loss of Rent, Coverage A - Residence")

CELLS = [
    ("$546,900", "a_lim_s"), ("$1,520.00", "a_prem_s"),
    ("$152.00", "eca_prem_s"), ("$197.00", "vmma_prem_s"),
    ("$6,200", "b_lim_s"), ("$17.00", "b_prem_s"),
    ("$2.00", "ecb_prem_s"), ("$2.00", "vmmb_prem_s"),
    ("$6,200", "d_lim_s"), ("$17.00", "d_prem_s"),
    ("$2.00", "ecd_prem_s"), ("$2.00", "vmmd_prem_s"),
    ("$1,000,000", "l_lim_s"), ("$289.00", "l_prem_s"),
    ("$5,000", "mp_lim_s"), ("$41.00", "mp_prem_s"),
    ("$50,000", "mo_lim_s"), ("$0.00", "mo_prem_s"),
    ("-$20.00", "ml59_prem_s"),
    ("$109.00", "vcr_prem_s"), ("$1.00", "vcs_prem_s"),
    ("$875.00", "fl16_prem_s"), ("-$78.00", "ml216_prem_s"),
    ("$3,128.00", "pt_s"),
    ("$0.00", "ml56_prem_s"),
    ("$3,128.00", "pt_s"), ("$19.43", "fees_s"), ("$3,147.43", "total_s"),
]


def draw(v, C):
    d = L.draw_base(v, C, "{2d}-{4d}-{5d}", terr_tail="All Other")
    L.schedule(v, C, d, "d4")
    d.update(L.draw_mortgagee(v, C))
    d.update(biz=v.choice(["Short Term Rentals", "Home Daycare", "Bed and Breakfast",
                           "Hobby Farm", "Home Office"]),
             alarm=v.choice(["Hardwired Smoke Alarm", "Central Station Fire Alarm",
                             "Local Fire Alarm"]),
             bldg=v.choice(["Garage/Shed", "Detached Garage", "Barn", "Storage Shed", "Workshop"]),
             color=v.choice(["White", "Gray", "Brown", "Green", "Tan", "Red"]),
             ml56_loc=v.choice(["Rear of property", "Side yard", "Adjacent to dwelling",
                                "Back lot"]))
    return d


REPLACE = [
    # policy identity, transaction and term
    ("06-6676-86084", "{policy_no}", {"size": 9}),
    ("Renewal", "{txn}", {"exact": True, "leak": False}),
    ("07/27/2024", "{eff}"),
    ("07/27/2025", "{exp}"),
    # agency block and the "Mail To" block that repeats it (real text; its city overlays erased)
    ("Patriotic Insurance Group Brokerage", "{agency} - {ag_code}"),
    ("Inc- RBF", "{ag_street}", {"exact": True}),
    ("159 NY - 28", "{ag_city_line}", {"exact": True}),
    ("Ilion, NY 13357", "", {"exact": True, "page": 1, "nth": 1, "leak": False}),
    ("Ilion, NY 13357", "", {"exact": True, "page": 1, "nth": 2, "leak": False}),
    ("(226) 783-0236", "{ag_work}", {"size": 9}),
    ("(440) 929-3100", "{ag_fax}", {"size": 9}),
    # named insured ("Ilion" overlays on page 1 in reading order: insured, Mail To, Agency, property)
    ("Ashcroft Logistics", "{ins_name}", {"size": 9}),
    ("5688 Maple", "{ins_street}", {"exact": True, "size": 9}),
    ("Ilion, NY 13357", "{ins_city_line}",
     {"exact": True, "page": 1, "nth": 0, "size": 9, "leak": False}),
    # redaction artefacts: restore the plan line
    ("MERIDIAN WORKS", "", {"exact": True}),
    ("-OPERATIVE ASSESSMENT PLAN", "CO-OPERATIVE ASSESSMENT PLAN", {"exact": True}),
    # property line: one bold line (street is real text), overlays erased
    ("Property 1 - 28 Parkway -", "{prop_line}", {"exact": True, "page": 1}),
    ("Ilion, NY 13357", "", {"exact": True, "page": 1, "nth": 3, "leak": False}),
    ("- Orange County", "", {"exact": True}),
    # rating information (page 2) and the endorsement details
    ("$5,000.00", "{ded_s}", {"leak": False}),
    ("ACV", "{settle}", {"exact": True}),
    ("Automatic Increase, ACV", "Automatic Increase, {settle}"),
    ("Frame", "{constr}", {"exact": True}),
    ("Protected", "{protect}", {"exact": True}),
    ("3-4 Family", "{occupancy}", {"exact": True}),
    ("Short Term Rentals", "{biz}", {"exact": True}),
    ("19 - All Other", "{territory}", {"exact": True}),
    ("Hardwired Smoke Alarm", "{alarm}", {"exact": True}),
    ("Garage/Shed", "{bldg}", {"exact": True}),
    ("White", "{color}", {"exact": True}),
    ("Location", "Location: {ml56_loc}", {"exact": True}),
    ("ye Uaoiqsis: Bjwn zp Joqfwtyt", "", {"exact": True}),
    # mortgagee block (page 3)
    ("Anchor Loans LP", "{ml_name}", {"exact": True}),
    ("PO Box 8186", "{ml_street}", {"exact": True, "size": 9}),
    ("San Antonio, TX 78269-0087", "{ml_city_line}", {"exact": True, "leak": False}),
    ("Property 1 - 28 Parkway;", "Property 1 - {prop_street}; {prop_city}, NY {prop_zip}",
     {"exact": True}),
    ("Ilion, NY 13357", "", {"exact": True, "page": 3, "leak": False}),
] + L.amount_entries(CELLS)

STATIC = [
    r"^\$0\.00$",                     # zero premiums are form furniture
    r"13326", r"^Phone: 607-547",     # the carrier's own letterhead
]


def audit(d):
    return L.audit(d)


def gold(d):
    g = L.build_gold(
        d, forms=FORMS, form_name="Special Form (FL-3)", sm26=SM26, has_classif=False,
        ded_rows=("a", "b", "d"), settle_rows=("a", "b", "d"), printed_pages=3,
        mortgagee_clause="ISAOA/ ATIMA",
        dwelling_extra={"structure_description": fv(d["bldg"]), "fire_alarm_type": fv(d["alarm"])},
        location_extra={"alarm_type": fv(d["alarm"]), "business_description": fv(d["biz"])},
        optional_extra={
            "fl16": {"deductible_amount": money(d["ded_s"]), "business_type": fv(d["biz"])},
            "ml56": {"structure_type": fv(d["bldg"]), "structure_dimensions": fv("No answer provided"),
                     "structure_color": fv(d["color"]), "structure_location": fv(d["ml56_loc"])},
        })
    return g
