"""
Leatherstocking Cooperative Insurance Company - "6- DFIRE_redacted.pdf"

Four-file-page Dwelling Fire declaration (renewal in the source; the fourth
sheet is blank and the footer reads "Page n of 3").  Special Form (FL-3) with
Coverage A, B, C, D (each with EC and VMM), L, M, ML-59, ML-WD water backup,
a fee line and a mortgagee block, RC loss settlement.

Tidied redaction artefacts: the agency address (real text) gets consecutive
lines and the stray city overlays are erased; insured and property overlays
are upsized; the property line (real street + overlaid city/county) becomes
one bold line, and so does the mortgagee's property reference.  The
"Ilion, NY 13357" overlay repeats on page 1 (Mail To, Agency, property); the
copies are told apart by position.  "RBF" on the agency line is a producer
code, printed here after the agency name.

GAPS (printed but no canonical leaf): the SIGNATURE box's date (not printed); the "Mail To"
block (repeats the producer); the blank fourth sheet.
"""

from . import _lcic_common as L

SOURCE = "Leatherstocking Cooperative Insurance Company/dwelling_fire/6- DFIRE_redacted.pdf"

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
    ("ML-WD", "1.1", "Water Damage-Sewers and Drains"),
    ("FL-OLT", "1/92", "Premises Liability Insurance Coverage Part"),
    ("ML-59", "6/99", "Lead Exclusion"),
    ("SM-26", "7/00", "Automatic Increase"),
    ("FL-80", "7/96", "Redefinition of Insured"),
]
SM26 = ("Coverage A - Residence, Coverage B - Related Private Structures, Coverage D - "
        "Additional Living Expense / Loss of Rent")

CELLS = [
    ("$455,500", "a_lim_s"), ("$857.00", "a_prem_s"),
    ("$257.00", "eca_prem_s"), ("$282.00", "vmma_prem_s"),
    ("$45,600", "b_lim_s"), ("$79.00", "b_prem_s"),
    ("$28.00", "ecb_prem_s"), ("$28.00", "vmmb_prem_s"),
    ("$5,000", "c_lim_s"), ("$10.00", "c_prem_s"),
    ("$1.00", "ecc_prem_s"), ("$4.00", "vmmc_prem_s"),
    ("$45,600", "d_lim_s"), ("$79.00", "d_prem_s"),
    ("$28.00", "ecd_prem_s"), ("$28.00", "vmmd_prem_s"),
    ("$1,000,000", "l_lim_s"), ("$125.00", "l_prem_s"),
    ("$5,000", "mp_lim_s"), ("$34.00", "mp_prem_s"),
    ("$25,000", "mo_lim_s"), ("$0.00", "mo_prem_s"),
    ("-$9.00", "ml59_prem_s"), ("$25.00", "mlwd_prem_s"),
    ("$1,856.00", "pt_s"), ("$1,856.00", "pt_s"),
    ("$0.00", "fees_s"), ("$1,856.00", "total_s"),
]


def draw(v, C):
    d = L.draw_base(v, C, "{2d}-{4d}-{4d}")
    L.schedule(v, C, d, "d6")
    d.update(L.draw_mortgagee(v, C))
    return d


REPLACE = [
    # policy identity, transaction and term
    ("29-5166-0657", "{policy_no}", {"size": 9}),
    ("Renewal", "{txn}", {"exact": True, "leak": False}),
    ("01/31/2025", "{eff}"),
    ("01/31/2026", "{exp}"),
    # agency block and the "Mail To" block that repeats it (real text; its city overlays erased)
    ("Patriotic Insurance Group Brokerage", "{agency} - {ag_code}"),
    ("Inc- RBF", "{ag_street}", {"exact": True}),
    ("159 NY - 28", "{ag_city_line}", {"exact": True}),
    ("Ilion, NY 13357", "", {"exact": True, "page": 1, "nth": 0, "leak": False}),
    ("Ilion, NY 13357", "", {"exact": True, "page": 1, "nth": 1, "leak": False}),
    ("(226) 783-0236", "{ag_work}", {"size": 9}),
    ("(440) 929-3100", "{ag_fax}", {"size": 9}),
    # named insured
    ("VANTAGE CONTRACTING", "{ins_name}", {"size": 9}),
    ("375 Meridian", "{ins_street}", {"exact": True, "size": 9}),
    ("Beacon, NY 12508", "{ins_city_line}", {"exact": True, "size": 9, "leak": False}),
    # redaction artefacts: restore the plan line
    ("MERIDIAN WORKS", "", {"exact": True}),
    ("-OPERATIVE ASSESSMENT PLAN", "CO-OPERATIVE ASSESSMENT PLAN", {"exact": True}),
    # property line: one bold line (street is real text), overlays erased
    ("Property 1 - 670 Route 32 -", "{prop_line}", {"exact": True, "page": 1}),
    ("Ilion, NY 13357", "", {"exact": True, "page": 1, "nth": 2, "leak": False}),
    ("- Ulster County", "", {"exact": True}),
    # rating information (page 2/3)
    ("$1,000.00", "{ded_s}", {"leak": False}),
    ("RC", "{settle}", {"exact": True}),
    ("Automatic Increase, RC", "Automatic Increase, {settle}"),
    ("Frame", "{constr}", {"exact": True}),
    ("Protected", "{protect}", {"exact": True}),
    ("1-2 Family", "{occupancy}", {"exact": True}),
    ("Dwelling - 2 Family", "{classif}", {"exact": True}),
    ("19 - All Others", "{territory}", {"exact": True}),
    # mortgagee block (page 3)
    ("TEG Federal Credit Union", "{ml_name}", {"exact": True}),
    ("PO Box 4090", "{ml_street}", {"exact": True, "size": 9}),
    ("Cortland, NY 13045", "{ml_city_line}", {"exact": True, "size": 9, "leak": False}),
    ("Property 1 - 670 Route 32;", "Property 1 - {prop_street}; {prop_city}, NY {prop_zip}",
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
    return L.build_gold(
        d, forms=FORMS, form_name="Special Form (FL-3)", sm26=SM26,
        ded_rows=("a", "b", "c", "d"), settle_rows=("a", "b", "d"), printed_pages=3,
        mortgagee_clause="ISAOA/ATIMA")
