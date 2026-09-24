"""
Leatherstocking Cooperative Insurance Company - "2-DFIRE_redacted.pdf"

Two-page Dwelling Fire declaration (same layout as 1- DFIRE): Coverage A,
Coverage L, ML-59 and Hazardous Conditions - Occupancy, ACV/RC rating block.
Redaction artefacts are tidied as in the reference (overlays upsized, agency
and address lines put on consecutive lines, "CO-OPERATIVE" plan line restored).
The agency's trailing "RBF" line is a producer code, printed here after the
agency name.

GAPS (printed but no canonical leaf): the
"Property: 1 of 1" counter; the blank SIGNATURE / DATE box; the "Mail To"
block (repeats the producer).
"""

from . import _lcic_common as L

SOURCE = "Leatherstocking Cooperative Insurance Company/dwelling_fire/2-DFIRE_redacted.pdf"

GAPS = ["Property: 1 of 1 (property counter)",
        "SIGNATURE / DATE box (blank)", "Mail To block (repeats the producer address)"]

IGNORE_PAIRS = [
    r"^Phone: 607-547-2007 Fax: 607-547-2056$",   # carrier letterhead; keyed as carrier.contact phone/fax
    r"^Policy Number: \S+ Page \d+ of \d+$",       # page footer; policy number is keyed, page counter is furniture
]

FURNITURE = [
    r"^Phone: 607-547-2007 Fax: 607-547-2056$",   # carrier letterhead; already keyed as carrier.contact phone/fax
]

FORMS = L.FORMS_BASIC
SM26 = ("Coverage A - Residence, Coverage D - Additional Living Expense / Loss of Rent, "
        "Coverage B - Related Private Structures")

CELLS = [
    ("$530,000", "a_lim_s"), ("$2,236.00", "a_prem_s"),
    ("$1,000,000", "l_lim_s"), ("$82.00", "l_prem_s"),
    ("-$6.00", "ml59_prem_s"),
    ("$559.00", "haz_prem_s"),
    ("$2,871.00", "pt_s"), ("$2,871.00", "pt_s"), ("$2,871.00", "total_s"),
    ("$0.00", "fees_s"),
]


def draw(v, C):
    d = L.draw_base(v, C, "{2d}-{4d}-{5d}")
    return L.schedule(v, C, d, "basic")


REPLACE = [
    # policy identity, transaction and term
    ("65-9884-63313", "{policy_no}", {"size": 9}),
    ("New Policy", "{txn}", {"exact": True}),
    ("12/09/2022", "{eff}"),
    ("12/09/2023", "{exp}"),
    # agency block and the "Mail To" block that repeats it
    ("Rob Bowen Patriotic Insurance Group -", "{agency} - {ag_code}"),
    ("RBF", "{ag_street}", {"exact": True}),
    ("1992 Harbor", "{ag_city_line}", {"exact": True, "size": 9}),
    ("Suite 132B", "", {"exact": True}),
    ("Chester Shop Rite Plaza", "", {"exact": True}),
    ("Liberty, NY 12754", "", {"exact": True}),
    ("(226) 783-0236", "{ag_work}", {"size": 9}),
    ("(440) 929-3100", "{ag_fax}", {"size": 9}),
    # named insured
    ("GRANITE ROW INDUSTRIES", "{ins_name}", {"size": 9}),
    ("226 Meridian", "{ins_street}", {"exact": True, "size": 9}),
    ("Canton, NY 13617", "{ins_city_line}", {"exact": True, "size": 9, "leak": False}),
    # redaction artefacts: restore the plan line
    ("MERIDIAN WORKS", "", {"exact": True}),
    ("-OPERATIVE ASSESSMENT PLAN", "CO-OPERATIVE ASSESSMENT PLAN", {"exact": True}),
    # property line: one bold line, the overlays and separators erased
    ("Property 1 -", "{prop_line}", {"exact": True, "page": 1}),
    ("8769 Chestnut Boulevard", "", {"exact": True}),
    ("-", "", {"exact": True, "page": 1}),
    ("Beacon, NY 12508", "", {"exact": True, "leak": False}),
    ("- Orange County", "", {"exact": True}),
    # rating information (page 2)
    ("$1,000.00", "{ded_s}", {"leak": False}),
    ("ACV", "{settle}", {"exact": True}),
    ("Automatic Increase, ACV", "Automatic Increase, {settle}"),
    ("Frame", "{constr}", {"exact": True}),
    ("Semi-Protected", "{protect}", {"exact": True}),
    ("1-2 Family", "{occupancy}", {"exact": True}),
    ("Dwelling - 1 Family", "{classif}", {"exact": True}),
    ("19 - All Others", "{territory}", {"exact": True}),
    ("Unoccupancy", "{condition}", {"exact": True}),
] + L.amount_entries(CELLS)

STATIC = [
    r"^\$0\.00$",                     # zero premiums are form furniture
    r"13326", r"^Phone: 607-547",     # the carrier's own letterhead
]


def audit(d):
    return L.audit(d)


def gold(d):
    return L.build_gold(d, forms=FORMS, form_name="Basic Form (FL-1)", sm26=SM26,
                        has_condition=True)
