"""
Shared draws for dwelling-fire profiles.

Everything is invented; places are public geography. A profile calls these with
its seeded ``Values`` so a document is reproducible from (seed, source, index).
"""

from __future__ import annotations

from datetime import date, timedelta

from ..values import GIVEN, STREET_NAME, SURNAME

# (city, ZIP, county) - main-post-office ZIPs only
TOWNS = [
    ("Cooperstown", "13326", "Otsego"), ("Oneonta", "13820", "Otsego"),
    ("Milford", "13807", "Otsego"), ("Richfield Springs", "13439", "Otsego"),
    ("Norwich", "13815", "Chenango"), ("Oxford", "13830", "Chenango"),
    ("Sherburne", "13460", "Chenango"), ("Sidney", "13838", "Delaware"),
    ("Walton", "13856", "Delaware"), ("Delhi", "13753", "Delaware"),
    ("Margaretville", "12455", "Delaware"), ("Andes", "13731", "Delaware"),
    ("Cobleskill", "12043", "Schoharie"), ("Herkimer", "13350", "Herkimer"),
    ("Little Falls", "13365", "Herkimer"), ("Ilion", "13357", "Herkimer"),
    ("Old Forge", "13420", "Herkimer"), ("Eagle Bay", "13331", "Herkimer"),
    ("Utica", "13501", "Oneida"), ("Rome", "13440", "Oneida"),
    ("Boonville", "13309", "Oneida"), ("Camden", "13316", "Oneida"),
    ("Oneida", "13421", "Madison"), ("Cazenovia", "13035", "Madison"),
    ("Hamilton", "13346", "Madison"), ("Canastota", "13032", "Madison"),
    ("Morrisville", "13408", "Madison"), ("Fulton", "13069", "Oswego"),
    ("Oswego", "13126", "Oswego"), ("Ithaca", "14850", "Tompkins"),
    ("Cortland", "13045", "Cortland"), ("Binghamton", "13901", "Broome"),
    ("Endicott", "13760", "Broome"), ("Owego", "13827", "Tioga"),
    ("Elmira", "14901", "Chemung"), ("Corning", "14830", "Steuben"),
    ("Watertown", "13601", "Jefferson"), ("Lowville", "13367", "Lewis"),
    ("Potsdam", "13676", "St. Lawrence"), ("Malone", "12953", "Franklin"),
    ("Lake Placid", "12946", "Essex"), ("Plattsburgh", "12901", "Clinton"),
    ("Glens Falls", "12801", "Warren"), ("Saratoga Springs", "12866", "Saratoga"),
    ("Gloversville", "12078", "Fulton"), ("Johnstown", "12095", "Fulton"),
    ("Amsterdam", "12010", "Montgomery"), ("Schenectady", "12305", "Schenectady"),
    ("Kingston", "12401", "Ulster"), ("Catskill", "12414", "Greene"),
    ("Hudson", "12534", "Columbia"), ("Speculator", "12164", "Hamilton"),
]

STREETS = STREET_NAME + [
    "Main St", "Church St", "Mill St", "River Rd", "Lake Rd", "Maple Ave",
    "Union St", "Depot St", "Academy St", "Center St", "Elm St", "Front St",
    "Orchard St", "Walnut St", "Prospect Ave", "Chestnut St", "Pleasant St",
    "Railroad Ave", "Water St", "Spring St",
]

LENDER_HEAD = [
    "Otsego", "Chenango Valley", "Catskill Hudson", "Adirondack Trust",
    "Mohawk Community", "Leatherstocking", "Susquehanna", "Tri-County",
    "Northern Lakes", "Empire State", "Hudson Headwaters", "Unadilla Valley",
    "Finger Lakes", "Southern Tier", "Champlain", "Black River", "Cayuga",
    "Genesee", "Oneida Lake", "St. Lawrence",
]
LENDER_TAIL = [
    "Savings Bank", "Federal Credit Union", "Bank, N.A.", "Community Bank",
    "Mortgage Corp.", "Home Loans LLC", "Trust Company", "Financial Services",
]

BUSINESS_HEAD = [
    "Winterberry", "Ironwood", "Northfield", "Stonecrop", "Larkspur",
    "Cedarhollow", "Brightwater", "Thornfield", "Millbrook", "Fernbank",
    "Copperkettle", "Blue Heron", "Silverbirch", "Redfern", "Lakeshore",
    "Meadowbrook", "Oakmont", "Pinecrest", "Riverbend", "Stonegate",
]
BUSINESS_TAIL = ["Realty LLC", "Properties LLC", "Holdings LLC", "Rentals LLC",
                 "Management Inc.", "Family Trust", "Investments LLC"]

AGENCY_HEAD = [
    "Northfield Ridge", "Cooperstown Valley", "Catskill Headwaters",
    "Chenango Valley", "Adirondack Gateway", "Butternut Creek", "Oneida Lake",
    "Unadilla River", "Sherburne Hill", "Otsego Lake", "Finger Lakes",
    "Southern Tier", "Mohawk River", "Susquehanna", "Delaware County",
]
AGENCY_TAIL = ["Agency Inc", "Insurance Services", "Agency LLC",
               "Coverage Group", "Insurance Agency", "Associates Inc"]

AREA_CODES = ["315", "518", "607", "845", "716", "585"]


def town(v):
    return v.choice(TOWNS)


def street(v):
    number = v.choice([v.integer(3, 299), v.integer(300, 2999)])
    style = v.integer(0, 2)
    if style == 0:
        return "%d %s" % (number, v.choice(STREETS))
    if style == 1:
        return "%d State Route %d" % (number, v.choice([7, 10, 12, 28, 30, 80, 205, 206, 23, 8]))
    return "%d County Route %d" % (number, v.integer(2, 48))


def address(v):
    """{'line_1', 'city', 'state', 'postal_code', 'county'} in a real NY town."""
    city, postal, county = town(v)
    return {"line_1": street(v), "city": city, "state": "NY",
            "postal_code": postal, "county": county}


def po_box(v):
    return "PO Box %d" % v.integer(12, 990)


def person(v, surname=None):
    return "%s %s" % (v.choice(GIVEN), surname or v.choice(SURNAME))


def couple(v):
    """Two full names sharing a surname."""
    surname = v.choice(SURNAME)
    a, b = v.pick(GIVEN, 2)
    return "%s %s" % (a, surname), "%s %s" % (b, surname)


def business(v):
    return "%s %s" % (v.choice(BUSINESS_HEAD), v.choice(BUSINESS_TAIL))


def lender(v):
    return "%s %s" % (v.choice(LENDER_HEAD), v.choice(LENDER_TAIL))


def agency(v):
    return "%s %s" % (v.choice(AGENCY_HEAD), v.choice(AGENCY_TAIL))


def loan_number(v, digits=10):
    return "".join(str(v.integer(0, 9)) for _ in range(digits))


def phone(v, style="dash"):
    """607-547-2007 ('dash'), (607) 547-2007 ('paren') or 607.547.2007 ('dot')."""
    a = v.choice(AREA_CODES)
    b = "%d%02d" % (v.integer(2, 9), v.integer(0, 99))
    c = "%04d" % v.integer(0, 9999)
    return {"dash": "%s-%s-%s", "paren": "(%s) %s-%s", "dot": "%s.%s.%s"}[style] % (a, b, c)


def email(name, domain):
    return "%s@%s" % (name.lower().replace(" ", "."), domain)


# -- dates ---------------------------------------------------------------------

def add_months(d, months):
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    day = d.day
    while True:
        try:
            return date(y, m, day)
        except ValueError:
            day -= 1


def term(v, months=12, earliest=date(2023, 1, 1), latest=date(2026, 12, 31)):
    """(effective, expiration) dates on the same anniversary."""
    start = earliest + timedelta(days=v.integer(0, (latest - earliest).days))
    return start, add_months(start, months)


def before(v, d, low=10, high=60):
    return d - timedelta(days=v.integer(low, high))


def fmt(d, style="mdy"):
    """mdy 01/25/2023 | md 1/25/2023 | long January 25, 2023 | short2 01/25/23 | iso 2023-01-25"""
    if style == "mdy":
        return d.strftime("%m/%d/%Y")
    if style == "md":
        return "%d/%d/%d" % (d.month, d.day, d.year)
    if style == "long":
        return "%s %d, %d" % (d.strftime("%B"), d.day, d.year)
    if style == "short2":
        return d.strftime("%m/%d/%y")
    if style == "iso":
        return d.isoformat()
    raise ValueError(style)


# -- money ---------------------------------------------------------------------

def usd(n, cents=True):
    """$1,438.00 (or $1,438); negatives print as -$6.00."""
    body = format(abs(n), ",.2f" if cents else ",.0f")
    return "%s$%s" % ("-" if n < 0 else "", body)


def num(n, cents=False):
    return format(n, ",.2f" if cents else ",.0f")


def round_to(n, step):
    return int(round(n / float(step))) * step
