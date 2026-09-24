"""
New York Central Mutual Fire Insurance Company (NYCM) - "nycm_insurance_dfire_renewal.pdf"

Four pages: dwelling-fire Declarations for a REVISED RENEWAL transaction (insured /
agency / policy information and the renewal premium with "BILL WILL FOLLOW",
a blank page, location coverage detail, detailed form list). Clean text layer, so
spans are rewritten directly. Renewal transaction, term and premium are captured as
printed.

The page does not print a prior policy number (the renewal keeps the policy number),
so policy.prior_policy_number / renewal_of_policy_number are left absent.

GAPS: none beyond prose captured by text_sections (see GAPS below).
"""

from . import _nycm_common as N

SOURCE = "NYCM Insurance/dwelling_fire/nycm_insurance_dfire_renewal.pdf"

GAPS = list(N.COMMON_GAPS)
IGNORE_PAIRS = list(N.IGNORE_PAIRS)
FURNITURE = list(N.FURNITURE)


def draw(v, C):
    return N.draw(v, C, "renewal")


def _b(**kw):
    o = {"size": 9}          # Calibri 10 pt is redrawn as Helvetica 9 pt (same width)
    o.update(kw)
    return o


REPLACE = [
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
    ("D8/J", "{run_code}", {"exact": True}),
    ("315-357-5901", "{ag_office}", _b()),
    ("315-357-5126", "{ag_fax}", _b()),
    ("beservice@patrioticinsurancegroup.com", "{ag_email_pad}", _b(exact=True)),
    ("https://patrioticinsurancegroup.com", "{ag_web_pad}", _b(exact=True)),
    # policy / transaction
    ("6136287", "{policy_no}", _b(exact=True)),
    ("POLICY: 6136287", "POLICY: {policy_no}", {"exact": True}),
    ("REVISED RENEWAL", "{txn_label_pad}", _b(exact=True, size=8)),
    ("09/06/2024 13:16:16", "{print_date} {print_time}", {"exact": True}),
    ("10/09/2010", "{inception}", _b(nth=0)),
    ("10/09/2010", "{protected}", _b(nth=1)),
    ("10/09/2024", "{eff}", _b()),          # transaction effective and policy effective date
    ("10/09/2025", "{exp}", _b()),          # transaction expiration and policy expiration date
    # insured summary
    ("MARRIED", "{marital}", _b(exact=True)),
    ("MALE", "{gender}", _b(exact=True)),
    # location summary, location detail
    ("431 ROUTE 28", "{pr_street}", _b(exact=True)),
    ("INLET, NY 13360-1610", "{pr_city_line}", _b(exact=True)),
    ("$1,095.00", "{total_s}", {"size": 9, "page": 1, "nth": 0}),
    ("$1,095.00", "{total_s}", {"size": 11, "page": 1, "nth": 1}),
    ("$1,095.00", "{total_s}", {"size": 11, "page": 3}),
    ("$1,095.00", "{total_s}", _b(page=4)),
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
    ("327,000", "{cov_a_s}", _b()),
    ("$1,082.00", "{prem_a_s}", _b()),
    ("5,000", "{cov_c_s}", _b(leak=False)),
    ("$13.00", "{prem_c_s}", _b()),
    ("32,700", "{cov_d_s}", _b()),
    ("$33.00", "{savings_s}", _b()),
    # detailed form information (7 pt sub-tables keep their size)
    ("LOCAL FIRE ALARM", "{alarm}", {"exact": True}),
    ("3%", "{pct_s}", {"exact": True}),
    ("3.00%", "{ig_s}", {"exact": True}),
]

STATIC = [
    r"^\$0\.00$",                     # certified terrorism loss premium
    r"13335-1899", r"800-234-6926",   # the carrier's own letterhead
]


def audit(d):
    return N.audit(d)


def gold(d):
    return N.gold(d)
