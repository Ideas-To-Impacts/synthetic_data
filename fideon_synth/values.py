"""
Seeded value generators.

Hand-writing five documents is fine. Hand-writing two hundred is not, and the
two hundredth would be worse than the first - by then you are reusing street
names without noticing and the corpus quietly stops testing what you think it
tests.

Everything here is seeded, so a corpus of any size is reproducible: the same
seed gives the same documents, and a document that changes between runs means
the generator changed, not the data.

    v = Values(seed=7)
    v.person()                      # 'Marguerite Calloway'
    v.policy_number("10-{year}-{5d}", year=2026)
    v.address(state="NY")

The name pools are invented rather than drawn from a census list. A synthetic
corpus should not be able to accidentally name a real household at a real
address, and pairing common surnames with real streets in real towns is
exactly how that happens.
"""

from __future__ import annotations

import hashlib
import random
import re
from datetime import date, timedelta

GIVEN = [
    "Hollis", "Juniper", "Waldemar", "Cornelius", "Adelaide", "Rutherford",
    "Perpetua", "Ignatius", "Ottoline", "Marguerite", "Delphine", "Barnaby",
    "Rosalind", "Thaddeus", "Clementine", "Ambrose", "Winifred", "Leopold",
    "Henrietta", "Silas", "Beatrix", "Alastair", "Seraphina", "Montague",
    "Georgiana", "Peregrine", "Wilhelmina", "Octavia", "Bartholomew", "Lavinia",
]

SURNAME = [
    "Brackenridge", "Pettigrew", "Vantassel", "Danforth", "Marchbanks",
    "Calloway", "Underhill", "Fernsby", "Hollingsworth", "Ashworth",
    "Quillfeather", "Blackwood", "Thistlewood", "Ravensdale", "Copperfield",
    "Harrowgate", "Winterbourne", "Stonebridge", "Fairweather", "Mortlake",
    "Ellingham", "Crowthorne", "Barrowclough", "Pemberton", "Larkspur",
]

COMPANY_HEAD = [
    "Winterberry", "Ironwood", "Northfield", "Stonecrop", "Larkspur",
    "Cedarhollow", "Brightwater", "Thornfield", "Millbrook", "Fernbank",
]
COMPANY_TAIL = ["Holdings LLC", "Properties LLC", "Family Trust",
                "Realty LLC", "Group LLC", "Partners LP"]

AGENCY_HEAD = [
    "Northfield Ridge", "Cooperstown Valley", "Catskill Headwaters",
    "Chenango Valley", "Adirondack Gateway", "Butternut Creek",
    "Oneida Lake", "Unadilla River", "Sherburne Hill", "Otsego Lake",
]
AGENCY_TAIL = ["Agency Inc", "Insurance Services", "Agency LLC",
               "Coverage Group", "Insurance Agency", "Associates Inc"]

STREET_NAME = [
    "Tannery Flats", "Susquehanna Terrace", "Bramble Hollow Rd",
    "Hillcrest Terrace", "Birchbark Ln", "Palmer Hill Rd", "Fish Creek Rd",
    "Poplar Point", "Durant Rd", "Quarry Ridge Rd", "Elderberry Ln",
    "Cobbler Hill Rd", "Stonefence Rd", "Mill Pond Way", "Hemlock Ridge Rd",
    "Cranberry Bog Rd", "Sawkill Rd", "Beaver Meadow Rd", "Windfall Rd",
    "Alder Brook Ln",
]

#: Real towns paired with their real county and ZIP. Places are public
#: geography; the people and addresses placed in them are not real.
NY_TOWNS = [
    ("Piseco", "12139", "Hamilton"), ("Speculator", "12164", "Hamilton"),
    ("Milford", "13807", "Otsego"), ("Cooperstown", "13326", "Otsego"),
    ("Andes", "13731", "Delaware"), ("Delhi", "13753", "Delaware"),
    ("Oxford", "13830", "Chenango"), ("Norwich", "13815", "Chenango"),
    ("Old Forge", "13420", "Herkimer"), ("Eagle Bay", "13331", "Herkimer"),
    ("Morrisville", "13408", "Madison"), ("Hamilton", "13346", "Madison"),
    ("Boonville", "13309", "Oneida"), ("Camden", "13316", "Oneida"),
    ("Sherburne", "13460", "Chenango"), ("Richfield Springs", "13439",
                                         "Otsego"),
]

AREA_CODES = ["315", "518", "607", "845"]


class Values:
    """Seeded generators. Two instances with the same seed agree exactly."""

    def __init__(self, seed=0):
        self.seed = seed
        self.rng = random.Random(self._stable(seed))

    @staticmethod
    def _stable(seed):
        """A seed that survives a Python restart.

        ``hash()`` of a string is salted per process, so seeding with it makes
        "reproducible" mean "within this run" - which is the opposite of the
        point.
        """
        digest = hashlib.sha256(str(seed).encode()).digest()
        return int.from_bytes(digest[:8], "big")

    # ── people and organisations ────────────────────────────────────────────

    def person(self, surname=None):
        return "%s %s" % (self.rng.choice(GIVEN),
                          surname or self.rng.choice(SURNAME))

    def household(self, count=2):
        """Several people sharing a surname, as a policy's insureds do."""
        surname = self.rng.choice(SURNAME)
        return [self.person(surname) for _ in range(count)]

    def company(self):
        return "%s %s" % (self.rng.choice(COMPANY_HEAD),
                          self.rng.choice(COMPANY_TAIL))

    def agency(self):
        return "%s %s" % (self.rng.choice(AGENCY_HEAD),
                          self.rng.choice(AGENCY_TAIL))

    def initials(self, n=3):
        return "".join(self.rng.choice("ABCDEFGHJKLMNPRSTVW") for _ in range(n))

    # ── places ──────────────────────────────────────────────────────────────

    def address(self, town=None, po_box=False):
        """A street address in a real town, with its real county and ZIP."""
        city, postal, county = town or self.rng.choice(NY_TOWNS)
        if po_box:
            line_1 = "PO Box %d" % self.rng.randint(12, 980)
        else:
            line_1 = "%d %s" % (self.rng.choice(
                [self.rng.randint(3, 299), self.rng.randint(300, 2400)]),
                self.rng.choice(STREET_NAME))
        return {"line_1": line_1, "city": city, "state": "NY",
                "postal_code": postal, "county": county}

    def phone(self):
        """A NANP-valid number: no leading 0 or 1 in the exchange."""
        return "(%s) %d%02d-%04d" % (self.rng.choice(AREA_CODES),
                                     self.rng.randint(2, 9),
                                     self.rng.randint(0, 99),
                                     self.rng.randint(0, 9999))

    def phone_pair(self):
        """A work number and a fax five apart, as an agency block prints."""
        work = self.phone()
        head, tail = work.rsplit("-", 1)
        return work, "%s-%04d" % (head, (int(tail) + 5) % 10000)

    # ── identifiers ─────────────────────────────────────────────────────────

    def policy_number(self, pattern, **fixed):
        """Fill a carrier's own policy-number shape.

        ``{5d}`` is five digits, ``{3a}`` three uppercase letters, and any
        named field is substituted from ``fixed``:

            v.policy_number("10-{year}-{5d}", year=2026)   # 10-2026-14207
            v.policy_number("{2a}-{7d}-{2d}")              # NH-6645203-01
        """
        def fill(match):
            token = match.group(1)
            if token in fixed:
                return str(fixed[token])
            shape = re.fullmatch(r"(\d+)([da])", token)
            if not shape:
                raise ValueError("Unknown token {%s} in %r" % (token, pattern))
            width, kind = int(shape.group(1)), shape.group(2)
            if kind == "d":
                return "".join(str(self.rng.randint(0, 9))
                               for _ in range(width))
            return "".join(self.rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ")
                           for _ in range(width))
        return re.sub(r"\{([^}]+)\}", fill, pattern)

    # ── time ────────────────────────────────────────────────────────────────

    def term(self, earliest=date(2026, 1, 1), latest=date(2027, 12, 31),
             months=12):
        """An effective date and its expiry, as printed.

        Anniversary dating, not 365 days: a policy written on 29 February
        expires on 28 February, and a generator that adds a fixed number of
        days produces a date no carrier system would ever print.
        """
        span = (latest - earliest).days
        start = earliest + timedelta(days=self.rng.randint(0, max(span, 1)))
        year = start.year + (start.month - 1 + months) // 12
        month = (start.month - 1 + months) % 12 + 1
        day = start.day
        while True:
            try:
                end = date(year, month, day)
                break
            except ValueError:
                day -= 1
        return start.strftime("%m/%d/%Y"), end.strftime("%m/%d/%Y")

    # ── money ───────────────────────────────────────────────────────────────

    def limit(self, low, high, step=1000):
        """A round limit, the way an underwriter writes one."""
        return self.rng.randrange(low // step, high // step + 1) * step

    def rate(self, base, per=1000.0, jitter=(0.85, 1.15)):
        """A premium derived from an exposure, rounded to the dollar.

        Premiums that are random are obviously random. Premiums derived from
        the limit they sit beside survive someone reading the page.
        """
        return round(base / per * self.rng.uniform(*jitter))

    def choice(self, options):
        return self.rng.choice(options)

    def pick(self, options, count):
        return self.rng.sample(list(options), count)

    def maybe(self, probability=0.5):
        return self.rng.random() < probability

    def integer(self, low, high):
        return self.rng.randint(low, high)
