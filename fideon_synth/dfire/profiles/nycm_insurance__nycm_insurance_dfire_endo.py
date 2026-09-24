"""
New York Central Mutual Fire Insurance Company (NYCM) - "nycm_insurance_dfire_endo.pdf"

Five pages: a four-page dwelling-fire Declarations printed for an ENDORSEMENT
transaction (insured / agency / policy information, location summary, location
coverage detail, detailed form list) followed by the FL-1 "Perils Section" form
page. The source has a clean text layer, so spans are rewritten directly.

Transaction captured as printed: type ENDORSEMENT, effective date, the transaction
reason line, the "these changes have resulted in a return/additional premium of"
sentence (summary_of_changes and return_premium / additional_premium).

GAPS: none beyond prose captured by text_sections (see GAPS below).
"""

from . import _nycm_common as N
from ..engine import fv

SOURCE = "NYCM Insurance/dwelling_fire/nycm_insurance_dfire_endo.pdf"

GAPS = list(N.COMMON_GAPS)
IGNORE_PAIRS = list(N.IGNORE_PAIRS)
FURNITURE = list(N.FURNITURE)

PERILS = ("Fire or Lightning, Explosion, Windstorm or Hail, Riot or Civil Commotion, Aircraft, "
          "Vehicles, Sudden and Accidental Damage from Smoke, Vandalism")


def draw(v, C):
    return N.draw(v, C, "endorsement")


B = {"size": 9}          # body text: Calibri 10 pt is redrawn as Helvetica 9 pt (same width)


def _b(**kw):
    o = dict(B)
    o.update(kw)
    return o


REPLACE = [
    # named insured (body spans only; footers below keep their own 7 pt size)
    ("Rafael Ingram", "{ins_name}", _b(exact=True)),
    ("INSURED: Rafael Ingram", "INSURED: {ins_name}", {"exact": True}),
    ("PO BOX 239", "{ins_street}", _b(exact=True)),
    ("INLET NY 13360", "{ins_city_line}", _b(exact=True)),
    # agency address box, then the Agency Information block (L1 and L2 kept adjacent)
    ("PATRIOTIC INSURANCE GROUP", "{ag_l1}", _b(exact=True)),
    ("BROKERAGE INC", "{ag_suf}", _b(exact=True)),
    ("159 ROUTE 28", "{ag_street}", _b(exact=True)),
    ("PO BOX 329", "{ag_pobox}", _b(exact=True)),
    ("INLET NY 13360-0329", "{ag_city_line}", _b(exact=True)),
    ("PATRIOTIC INSURANCE GROUP BROKERAGE", "{ag_info_l1}", _b(exact=True)),
    ("INC", "{ag_info_l2}", _b(exact=True)),
    ("08014", "{ag_code}", _b(exact=True)),
    ("3R", "{ag_terr}", _b(exact=True)),
    ("YES", "{paper_off_pad}", _b(exact=True, page=1, nth=0, leak=False)),
    ("YES", "{direct_mail_pad}", _b(exact=True, page=1, nth=1, leak=False)),
    ("D8/I", "{run_code}", {"exact": True}),
    ("315-357-5901", "{ag_office}", _b()),
    ("315-357-5126", "{ag_fax}", _b()),
    ("beservice@patrioticinsurancegroup.com", "{ag_email_pad}", _b(exact=True)),
    ("https://patrioticinsurancegroup.com", "{ag_web_pad}", _b(exact=True)),
    # transaction
    ("PER  AGENT AMEND BASE FORM", "{reason}", _b(exact=True)),
    ("THESE CHANGES HAVE RESULTED IN A RETURN PREMIUM OF -$33.00.", "{change_line}", _b(exact=True)),
    ("6136287", "{policy_no}", _b(exact=True)),
    ("POLICY: 6136287", "POLICY: {policy_no}", {"exact": True, "page": 5, "size": 9}),
    ("POLICY: 6136287", "POLICY: {policy_no}", {"exact": True}),
    # dates: the source prints the transaction effective date as its print date too
    ("09/06/2024 13:14:33", "{txn_eff} {print_time}", {"exact": True}),
    ("09/06/2024 12:01 AM EST", "{txn_eff} 12:01 AM EST", _b(exact=True)),
    ("10/09/2010", "{inception}", _b(nth=0)),
    ("10/09/2010", "{protected}", _b(nth=1)),
    ("10/09/2023", "{eff}", _b()),
    ("10/09/2024", "{exp}", _b()),
    # insured summary
    ("MARRIED", "{marital}", _b(exact=True)),
    ("MALE", "{gender}", _b(exact=True)),
    # location summary, location detail
    ("431 ROUTE 28", "{pr_street}", _b(exact=True)),
    ("INLET, NY 13360-1610", "{pr_city_line}", _b(exact=True)),
    ("$1,045.00", "{total_s}", {"size": 9, "page": 1, "nth": 0}),
    ("$1,045.00", "{total_s}", {"size": 11, "page": 1, "nth": 1}),
    ("$1,045.00", "{total_s}", {"size": 11, "page": 3}),
    ("$1,045.00", "{total_s}", _b(page=4)),
    ("041", "{pr_county_code}", _b(leak=False)),
    ("HAMILTON", "{pr_county}", _b()),
    ("INLET", "{pr_city}", _b(exact=True, page=3)),
    ("13360-1610", "{pr_zip9}", _b(exact=True, page=3)),
    ("1970", "{year_built}", _b(exact=True, page=3)),
    ("2", "{units}", _b(exact=True, page=3, leak=False)),
    ("FRAME", "{constr}", _b(exact=True)),
    ("VACANT", "{occupied}", _b(exact=True, leak=False)),
    ("PARTIALLY PROTECTED", "{protect}", _b(exact=True)),
    ("NO", "{lead}", _b(exact=True, page=3, nth=0)),
    ("NO", "{seasonal}", _b(exact=True, page=3, nth=1)),
    ("A", "{territory}", _b(exact=True, page=3)),
    ("$500", "{ded_s}", _b()),
    ("311,000", "{cov_a_s}", _b()),
    ("$1,032.00", "{prem_a_s}", _b()),
    ("5,000", "{cov_c_s}", _b(leak=False)),
    ("$13.00", "{prem_c_s}", _b()),
    ("31,100", "{cov_d_s}", _b()),
    ("$32.00", "{savings_s}", _b()),
    # detailed form information (7 pt sub-tables keep their size)
    ("LOCAL FIRE ALARM", "{alarm}", {"exact": True}),
    ("3%", "{pct_s}", {"exact": True}),
    ("5.00%", "{ig_s}", {"exact": True}),
]

STATIC = [
    r"^\$0\.00$",                     # certified terrorism loss premium
    r"13335-1899", r"800-234-6926",   # the carrier's own letterhead
]


def audit(d):
    return N.audit(d)


def gold(d):
    g = N.gold(d)
    g["document"]["coverage_parts_present"] = [fv("PERILS SECTION")]
    g["dwelling_fire"]["property_coverages"]["covered_causes_of_loss"] = fv(PERILS, evidence="Fire or Lightning")
    return g
