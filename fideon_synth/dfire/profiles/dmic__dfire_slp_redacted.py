"""
Dryden Mutual Insurance Company - "Standard Landlords Package Policy,
Declaration Page" (DFIRE-SLP_redacted.pdf), seven pages: a summary page, then a
coverage page, a forms page and a premium page for each of two locations.

The source is a redacted copy: tiny 6-7 pt overlay strings sit where values were
painted out, some scrambled across lines (the address is split between an overlay
and a bold "28," fragment, labels such as "Policy #:" were replaced by cipher
words, form numbers by "FF-6", stray names float next to "Insured"). This profile
tidies those: overlays are erased or upsized, each location becomes one line,
the letterhead address is put back on one line, the truncated title on the forms
pages, the "New York State Fire Surcharge" label and the "Any such" sentence
fragment are restored.

GAPS (printed but no canonical leaf): "Miles From Fire Dept", "Fire District",
"Renovator Credit", "Type: Standard", "Special Rating Conditions",
"Loss Settlement Contents", "Inland Marine Premium $0.00", the "go paperless"
notice, "Coverage / Form" descriptions of the enhanced
DFL-153P coverage list beyond their names.
"""

import fitz

from ..engine import addr, amt, date_fv, derived, extra, fv, money
from . import _ncic_common as N

SOURCE = "DMIC/dwelling_fire/DFIRE-SLP_redacted.pdf"

GAPS = ["Miles From Fire Dept", "Fire District", "Renovator Credit", "Type: Standard",
        "Special Rating Conditions", "Loss Settlement Contents", "Inland Marine Premium (0.00)",
        "Paperless notice"]

CAUSES = [("FL-3", "Special", "Special Perils"), ("FL-2", "Broad", "Broad Perils")]
DESCS = ["Main House", "Garage With Apartment", "Carriage House", "Rear Cottage", "Guest House",
         "Farmhouse", "Lake House", "Duplex"]
CREDIT = {1000: 0.08, 2500: 0.17, 5000: 0.24}
FORMS = [  # (number, edition, title, premium key)
    (None, "09/00", None, None), ("FMD-1", "08/08", "Flood Disclosure Notice", None),
    ("FL-10", "01/92", "Auto Increase in Insurance", "fl10"), ("FL-18", "06/96", "Intentional Acts Exclusion", "zero"),
    ("FL-20", "01/92", "Agreement", None), ("FL-30", "05/92", "Amendatory Endorsement", None),
    ("FL-42", "05/92", "Building Theft Coverage", "fl42"), ("FL-52A", "12/98", "Trampoline Exclusion", "fl52a"),
    ("FL-83", "02/02", "Amendment of Policy Conditions", None), ("FL-84A", "04/94", "New York Amendatory End.", None),
    ("FL-19", "04/94", "Amended Limits of Liability", None), ("FL-OLT", "01/92", "Premises Liability Coverage", "zero"),
    ("DMIC-PP", None, "Privacy Notice", None),
    ("DFL-153P", "11/23", "Dwelling Package VIP Plus (FL2 and FL3)", "dfl"),
    ("ML-216", "06/99", "Premises Alarm", "ml"),
]
ENHANCED = ["Coverage C- Personal Property Replacement Cost", "Limited Flood Coverage", "Debris Removal",
            "Trees Plants Shrubs And Lawns", "Generator Expense", "Earth Movement", "Ordinance or Law",
            "Motorized Vehicles", "Replacement of Locks", "Underground Utility Line Coverage",
            "Extension of Coverage- Green Environmental, Safety and Efficiency Improvements",
            "Personal Injury", "Pollution Liability", "Premises Medical Payments"]


def _rpad(text, font, size, x0, x1):
    """Leading spaces so a right-aligned source line stays right-aligned when redrawn from x0."""
    w = fitz.get_text_length(text, fontname=font, fontsize=size)
    sp = fitz.get_text_length(" ", fontname=font, fontsize=size)
    return " " * max(0, int((x1 - x0 - w) / sp)) + text


def _fits(text, font, size, limit):
    return fitz.get_text_length(text, fontname=font, fontsize=size) <= limit


def draw(v, C):
    d = {}
    d["pol"] = v.policy_number("{3a}{8d}-{2d}")
    d["acct"] = "D%06d" % v.integer(1000, 999999)
    eff, exp = C.term(v)
    d.update(eff=C.fmt(eff), exp=C.fmt(exp), prt=C.fmt(C.before(v, eff, 0, 15)))

    # named insured
    if v.maybe(0.3):
        d["ins_name"], d["ins_first"], d["ins_kind"] = C.business(v), C.business(v), "Business"
        d["ins_first"] = d["ins_name"]
        d["ins_second"] = None
    else:
        a, b = C.couple(v)
        sur = a.split()[1]
        fa, fb = a.split()[0], b.split()[0]
        m1, m2 = v.choice("ABCDEFGHJKLMNPRSTW"), v.choice("ABCDEFGHJKLMNPRSTW")
        d["ins_first"] = "%s %s. %s" % (fa, m1, sur)
        d["ins_second"] = "%s %s. %s" % (fb, m2, sur)
        d["ins_name"] = "%s and %s" % (d["ins_first"], d["ins_second"])
        d["ins_kind"] = "Individual"
    mail = C.address(v)
    d["ins_street"] = C.po_box(v) if v.maybe(0.5) else mail["line_1"]
    d["ins_city"], d["ins_zip"] = mail["city"], "%s-%04d" % (mail["postal_code"], v.integer(1000, 9999))
    d["ins_line"] = "%s, NY %s" % (d["ins_city"], d["ins_zip"])

    # agency block (right aligned in the source)
    while True:
        name = "%s Brokerage" % v.choice(C.AGENCY_HEAD)
        if _fits(name, "hebo", 10, 176):
            break
    while True:
        street = "%d NY-%d" % (v.integer(1, 999), v.choice([7, 10, 12, 23, 28, 30, 80])) if v.maybe(0.5) \
            else "%d %s" % (v.integer(1, 99), v.choice(["Main St", "Mill St", "Elm St", "Front St", "Depot St"]))
        if _fits(street, "hebo", 10, 56):
            break
    while True:
        town = C.town(v)
        line = "%s, NY %s" % (town[0], town[1])
        if _fits(line, "helv", 8, 84):
            break
    d.update(ag_code="%03d" % v.integer(100, 999), ag_name=name, ag_street=street, ag_city=town[0],
             ag_zip=town[1], ag_line=line, ag_phone=C.phone(v, "paren"))
    d["ag_name_1"] = _rpad(name, "hebo", 10, 413.9, 589)
    d["ag_name_2"] = _rpad(name, "hebo", 10, 416.3, 591)
    d["ag_street_p"] = _rpad(street, "hebo", 10, 541.2, 589)

    # the property: one address, two buildings
    pr = C.address(v)
    d["prop_street"], d["prop_city"], d["prop_county"] = pr["line_1"], pr["city"], pr["county"]
    d["prop_zip"] = "%s-%04d" % (pr["postal_code"], v.integer(1000, 9999))
    descs = v.pick(DESCS, 2)

    cause = v.choice(CAUSES)
    ded = v.choice([1000, 2500, 5000])
    d.update(cause_no=cause[0], cause="%s (%s)" % (cause[0], cause[1]), perils=cause[2],
             ded=ded, ded_s="$ {:,}".format(ded), settle=v.choice(["Replacement Cost", "Actual Cash Value"]),
             protect=v.choice(["Protected", "Semi-Protected", "Unprotected"]),
             miles=v.choice(["5 Miles or Less", "Greater than 5 Miles"]),
             hydrant=v.choice(["Greater than 1000 Feet", "1000 Feet or Less"]))

    lim_l = v.choice([1000000, 2000000])
    lim_g = lim_l + v.choice([1000000, 2000000])
    med_p, med_a = v.choice([1000, 2000, 5000]), v.choice([10000, 25000, 50000])
    d.update(l_n=C.num(lim_l), g_n=C.num(lim_g), mp_n=C.num(med_p), ma_n=C.num(med_a),
             lim_l=lim_l, lim_g=lim_g, med_p=med_p, med_a=med_a)
    shared = dict(pc=v.integer(35, 70), pl=v.integer(50, 110), pm=v.integer(20, 45),
                  fl42=v.choice([8, 10, 12, 15]), fl52a=-v.choice([2, 3]))
    d.update(shared)
    d["pc_n"], d["pl_n"], d["pm_n"] = (C.num(shared[k], True) for k in ("pc", "pl", "pm"))
    d["fl42_n"], d["fl52a_n"] = C.num(shared["fl42"], True), C.num(shared["fl52a"], True)

    total = 0
    d["locs"] = []
    for i in (1, 2):
        a = v.limit(100000, 750000, 5000)
        b = C.round_to(a * 0.1, 1000)
        dd = C.round_to(a * v.choice([0.1, 0.1, 0.15]), 1000)
        c = v.choice([10000, 15000, 20000, 25000, 30000])
        base = round(a / 1000.0 * v.rng.uniform(4.0, 4.8))
        fl10 = round(base * 0.02)
        dfl = round(base * 0.10)
        dc = -round(base * CREDIT[ded])
        loc_total = base + shared["pc"] + shared["pl"] + shared["pm"] + fl10 + shared["fl42"] + \
            shared["fl52a"] + dfl - fl10 + dc
        total += loc_total
        loc = dict(i=i, desc=descs[i - 1], fam=v.choice(["1 Family", "1 Family", "2 Family"]),
                   constr=v.choice(["Frame", "Masonry", "Masonry Veneer", "Frame"]),
                   year=str(v.integer(1900, 2018)), zone=str(v.integer(1, 5)),
                   a=a, b=b, c=c, d=dd, base=base, fl10=fl10, dfl=dfl, ml=-fl10, dc=dc, total=loc_total,
                   a_n=C.num(a), b_n=C.num(b), c_n=C.num(c), d_n=C.num(dd),
                   base_n=C.num(base, True), fl10_n=C.num(fl10, True), dfl_n=C.num(dfl, True),
                   ml_n=C.num(-fl10, True), dc_n=C.num(dc, True), total_n=C.num(loc_total, True))
        loc["text"] = "%s, (%s), %s, NY %s" % (d["prop_street"], loc["desc"], d["prop_city"], d["prop_zip"])
        loc["fam_dw"] = "%s Dwelling" % loc["fam"]
        d["locs"].append(loc)
        for k, val in loc.items():
            d["%s%d" % (k, i)] = val
    d["total"], d["total_n"] = total, C.num(total, True)
    d["fire_n"] = "0.00"
    return d


def _pages(src, new, pages, **opts):
    return [(src, new, dict({"exact": True, "page": p}, **opts)) for p in pages]


E = {"exact": True}
K = {"exact": True, "leak": False}
LOC_SRC = [
    dict(pages=(2, 3, 4), n=1, a="500,000", b="50,000", c="10,000", d="50,000", year="1959", total="2,209.00",
         base="2,194.00", dfl="219.00", fl10="44.00", ml="-44.00", dc="-373.00", desc="(Main House)",
         street_erase="28, (Main House),"),
    dict(pages=(5, 6, 7), n=2, a="300,000", b="30,000", c="10,000", d="30,000", year="1950", total="1,423.00",
         base="1,348.00", dfl="135.00", fl10="27.00", ml="-27.00", dc="-229.00", desc="(Garage With Apartment)",
         street_erase="28, (Garage With Apartment),"),
]

REPLACE = [
    # ---- letterhead (carrier is static; the address is put back on one line) ----------------
    ("4289 Franklin", "4289 Franklin . P.O. Box 708 . Dryden, New York 13053",
     {"exact": True, "size": 10, "font": "helv"}),
    (".", "", K), ("P.O. Box 708", "", K), ("Dryden, New York 13053", "", K),
    ("A New York", "A New York Mutual Company", E),
    ("Clearwater Enterprises", "", K),
    # ---- policy identity ------------------------------------------------------------------
    ("Gjfc #: D034526", "Acct #: {acct}", {"exact": True, "size": 7.5, "font": "helv"}),
    ("Qygcki #: WFZ89764606-34", "Policy #: {pol}", {"exact": True, "size": 7.5, "font": "helv"}),
    ("06/01/2026", "{eff}"), ("06/01/2027", "{exp}"), ("06/03/2026", "{prt}"),
    # ---- named insured -------------------------------------------------------------------
    ("Kenneth G. Hinckley and Jane S. Hinckley", "{ins_name}", E),
    ("PO Box 5644", "{ins_street}", {"exact": True, "size": 9}),
    ("Oneonta, NY 13820-7331", "{ins_line}", {"exact": True, "size": 9}),
    ("STONEPATH WORKS", "", K), ("Herkimer", "", K), ("Medina", "", K),
    ("Roger Radcliffe", "", K), ("Diane Yarrow", "", K), ("Sylvia Stanhope", "", K), ("Kingston", "", K),
    ("Insured", "Insured Locations", {"exact": True, "page": 1, "nth": 1}),
    ("Insured", "Insured Location", {"exact": True, "page": 2}),
    ("Insured", "Insured Location", {"exact": True, "page": 5}),
    # ---- agency ---------------------------------------------------------------------------
    ("# 760", "# {ag_code}", E),
    ("Patriotic Insurance Group Brokerage", "{ag_name_1}", {"exact": True, "page": 1}),
    ("Patriotic Insurance Group Brokerage", "{ag_name_2}", {"exact": True, "page": 2}),
    ("Patriotic Insurance Group Brokerage", "{ag_name_2}", {"exact": True, "page": 5}),
    ("159 NY-28", "{ag_street_p}", E),
    ("Ilion, NY 13357", "{ag_line}", {"exact": True, "size": 8}),
    ("(226) 783-0236", "{ag_phone}", {"exact": True, "size": 8}),
    # ---- location lines (page 1 rows, then the "Location:" line of pages 2-7) -------------
    ("8035 Millbrook", "{text1}", {"exact": True, "page": 1, "nth": 0, "size": 10, "font": "hebo"}),
    ("8035 Millbrook", "{text2}", {"exact": True, "page": 1, "nth": 1, "size": 10, "font": "hebo"}),
    ("28, (Main House),", "", K), ("28, (Garage With Apartment),", "", K),
    ("Liberty, NY 12754-1256", "", K),
    ("Liberty", "", K), ("Cortland", "Any such", {"exact": True, "size": 10, "font": "helv"}),
    ("Warwick", "New York State Fire Surcharge:", {"exact": True, "size": 10}),
    ("$e", "$", E),
    # ---- coverage page numbers shared by both locations -----------------------------------
    ("$2,000,000", "${l_n}", E), ("2,000,000", "{l_n}", E),
    ("$3,000,000", "${g_n}", E), ("3,000,000", "{g_n}", E),
    ("5,000", "{mp_n}", E),
    ("51.00", "{pc_n}", E), ("77.00", "{pl_n}", E), ("33.00", "{pm_n}", E),
    ("10.00", "{fl42_n}", E), ("-2.00", "{fl52a_n}", E),
    ("$ 2,500", "{ded_s}", E),
    ("FL-3 (Special)", "{cause}", E),
    ("Causes of Loss (Special Perils)", "Causes of Loss ({perils})", E),
    ("Hamilton", "{prop_county}", E), ("Raquette Lake", "{prop_city}", E),
    ("Semi-Protected", "{protect}", E), ("5 Miles or Less", "{miles}", E),
    ("Greater than 1000 Feet", "{hydrant}", E), ("Replacement Cost", "{settle}", E),
    ("3,632.00", "{total_n}", E),
    # forms-page title: the overlay hid the words in front of the location number
    ("MERIDIAN FABRICATION", "Policy Forms and Endorsements for Location # 1",
     {"exact": True, "page": 3, "size": 12, "font": "hebo"}),
    ("1", "", {"exact": True, "page": 3, "leak": False}),
    ("MERIDIAN FABRICATION", "Policy Forms and Endorsements for Location # 2",
     {"exact": True, "page": 6, "size": 12, "font": "hebo"}),
    ("2", "", {"exact": True, "page": 6, "leak": False}),
    ("0", "", K),
    ("Smoke Detectors 2%", "Smoke Detectors 2%", K), ("1.0% per Quarter", "1.0% per Quarter", K),
]
for _p in (3, 6):
    REPLACE.append(("FF-6", "{cause_no}", {"exact": True, "page": _p, "nth": 0, "size": 10, "font": "helv"}))
    REPLACE.append(("FF-6", "FL-30", {"exact": True, "page": _p, "nth": 1, "size": 10, "font": "helv"}))

for _loc in LOC_SRC:
    _i, _pg = _loc["n"], _loc["pages"]
    REPLACE += _pages("Location:", "Location: {text%d}" % _i, _pg, leak=False)
    REPLACE += _pages("8035 Millbrook", "", _pg, leak=False)
    REPLACE += _pages("1 Family Dwelling", "{fam_dw%d}" % _i, _pg)
    REPLACE += _pages("1 Family", "{fam%d}" % _i, [_pg[0]])
    REPLACE += [(_loc["a"], "{a_n%d}" % _i, E), (_loc["year"], "{year%d}" % _i, E)]
    REPLACE += _pages("10,000", "{c_n%d}" % _i, [_pg[0], _pg[2]])
    REPLACE += _pages("Frame", "{constr%d}" % _i, [_pg[0]])
    REPLACE += [("2,209.00" if _i == 1 else "1,423.00", "{total_n%d}" % _i, E)]
    REPLACE += [(_loc[k], "{%s_n%d}" % (k, _i), E) for k in ("base", "dfl", "fl10", "ml", "dc")]
    REPLACE += [("1", "{zone%d}" % _i, {"exact": True, "page": _pg[0], "nth": 2 if _i == 1 else 0})]
    if _i == 1:
        REPLACE += [("50,000", "{b_n1}", {"exact": True, "page": 2, "nth": 0}),
                    ("50,000", "{d_n1}", {"exact": True, "page": 2, "nth": 1}),
                    ("50,000", "{ma_n}", {"exact": True, "page": 2, "nth": 2}),
                    ("50,000", "{ma_n}", {"exact": True, "page": 4})]
    else:
        REPLACE += [("30,000", "{b_n2}", {"exact": True, "page": 5, "nth": 0}),
                    ("30,000", "{d_n2}", {"exact": True, "page": 5, "nth": 1}),
                    ("50,000", "{ma_n}", {"exact": True, "page": 5}),
                    ("50,000", "{ma_n}", {"exact": True, "page": 7})]

# Coincidental repeats between drawn values and other source strings ("50,000" appears in
# several places) make the leak probe meaningless for anything but names, dates and ids.
_LEAKY = {"Kenneth G. Hinckley and Jane S. Hinckley", "Patriotic Insurance Group Brokerage", "PO Box 5644",
          "Oneonta, NY 13820-7331", "06/01/2026", "06/01/2027", "06/03/2026", "Gjfc #: D034526",
          "Qygcki #: WFZ89764606-34", "159 NY-28", "Ilion, NY 13357", "(226) 783-0236", "# 760"}
REPLACE = [(e[0], e[1], (e[2] if len(e) > 2 else {}) if e[0] in _LEAKY else dict(e[2] if len(e) > 2 else {}, leak=False))
           for e in REPLACE]

REPLACE += N.keep_entries(SOURCE, REPLACE, skip_fonts=("Helvetica",))

# footer code "VC <date>" repeats the keyed print_date on every page
FURNITURE = [r"^VC \d\d/\d\d/\d{4}$"]

STATIC = [r"^Smoke Detectors 2%$", r"^1\.0% per Quarter$"]


def audit(d):
    out = []
    for loc in d["locs"]:
        parts = (loc["base"] + d["pc"] + d["pl"] + d["pm"] + loc["fl10"] + d["fl42"] + d["fl52a"] +
                 loc["dfl"] + loc["ml"] + loc["dc"])
        if parts != loc["total"]:
            out.append("location %d premium lines do not sum" % loc["i"])
    if sum(l["total"] for l in d["locs"]) != d["total"]:
        out.append("locations do not sum to the annual premium")
    return out


def _mn(text):
    return money(text)


def _loc_gold(d, loc, prop):
    n = loc["i"]
    cov = [
        {"coverage_code": fv("Coverage A"), "coverage_name": fv("Residence"), "limit_amount": _mn(loc["a_n"]),
         "premium": _mn(loc["base_n"])},
        {"coverage_code": fv("Coverage B"), "coverage_name": fv("Other Structures"),
         "limit_amount": _mn(loc["b_n"])},
        {"coverage_code": fv("Coverage C"), "coverage_name": fv("Personal Property"),
         "limit_amount": _mn(loc["c_n"]), "premium": _mn(d["pc_n"])},
        {"coverage_code": fv("Coverage D"), "coverage_name": fv("Addl.Living Exp. and Loss of Rent"),
         "limit_amount": _mn(loc["d_n"])},
        {"coverage_code": fv("Coverage L"), "coverage_name": fv("Premises Liability"),
         "limit_amount": _mn(d["l_n"]), "limit_basis": fv("Each Occurrence"),
         "aggregate_limit_amount": _mn(d["g_n"]), "premium": _mn(d["pl_n"])},
        {"coverage_code": fv("Coverage M"), "coverage_name": fv("Medical Payments"),
         "limit_amount": _mn(d["mp_n"]), "limit_basis": fv("Each Person"),
         "sublimit_amount": _mn(d["ma_n"]), "sublimit_basis": fv("Each Accident"), "premium": _mn(d["pm_n"])},
    ]
    return {
        "location_number": fv(str(n), n, evidence="Location Number:"),
        "address": dict(prop),
        "building_description": fv("(%s)" % loc["desc"]),
        "occupancy_description": fv(loc["fam_dw"].replace(" Dwelling", " Dwelling")),
        "construction_type": fv(loc["constr"]),
        "protection_class": fv(d["protect"]),
        "territory_code": fv(loc["zone"], evidence="Rating Zone:"),
        "year_built": fv(loc["year"]),
        "alarm_type": fv("Smoke Detectors 2%"),
        "coverages": cov,
    }


def _dwelling_gold(d, loc, prop):
    """dwelling_fire.dwellings[] entry: the location as its own coverage page (limits,
    rating criteria, mortgagee) and premium computation print it."""
    return {
        "location_number": fv(str(loc["i"]), loc["i"], evidence="Location Number:"),
        "described_location": dict(prop),
        "property_description": fv(loc["desc"]),
        "occupancy_type": fv(loc["fam_dw"]),
        "number_of_units": fv(loc["fam"][0], int(loc["fam"][0]), evidence=loc["fam"]),
        "construction_type": fv(loc["constr"]),
        "year_built": fv(loc["year"]),
        "protection_class": fv(d["protect"]),
        "rating_type": fv("Standard"),
        "rating_zone": fv(loc["zone"], evidence="Rating Zone:"),
        "renovator_credit": fv("No"),
        "fire_district": fv(d["prop_city"]),
        "feet_to_hydrant": fv(d["hydrant"]),
        "miles_to_fire_department": fv(d["miles"]),
        "fire_alarm_type": fv("Smoke Detectors 2%"),
        "special_rating_conditions": fv("None"),
        "covered_causes_of_loss": fv(d["cause"]),
        "loss_settlement_basis": fv(d["settle"]),
        "loss_settlement_contents": fv("Replacement Cost Contents"),
        "all_other_perils_deductible": _mn(d["ded_s"]),
        "deductible_credit_amount": _mn(loc["dc_n"]),
        "total_premium": _mn(loc["total_n"]),
        "fire_surcharge": money(d["fire_n"], evidence="New York State Fire Surcharge"),
        "mortgagees_none_listed": fv("None Listed"),
        "coverages": _loc_gold(d, loc, prop)["coverages"],
    }


def _forms(d, loc):
    out = []
    prem = {"fl10": loc["fl10_n"], "zero": "0.00", "fl42": d["fl42_n"], "fl52a": d["fl52a_n"],
            "dfl": loc["dfl_n"], "ml": loc["ml_n"]}
    for num, ed, title, key in FORMS:
        num = num or d["cause_no"]
        title = title or "Causes of Loss (%s)" % d["perils"]
        row = {"form_number": fv(num), "form_title": fv(title), "applies_to": fv("Location %d" % loc["i"]) \
               if False else derived("Location %d" % loc["i"], "Location Number:")}
        if ed:
            row["edition_date"] = fv(ed)
        if key:
            row["premium"] = _mn(prem[key])
        # the line printed under the form's row
        if key == "fl10":
            row["percentage"] = fv("1.0% per Quarter")
        elif key == "ml":
            row["percentage"] = fv("2%", evidence="Smoke Detectors 2%")
        elif key == "dfl":
            # the long "Extension of Coverage" entry wraps onto a second printed line
            row["included_coverages"] = [
                fv(t, evidence="Extension of Coverage- Green Environmental, Safety and Efficiency"
                   if t.startswith("Extension") else None) for t in ENHANCED]
        out.append(row)
    return out


def gold(d):
    prop = addr(d["prop_street"], d["prop_city"], "NY", d["prop_zip"], county=d["prop_county"])
    l1 = d["locs"][0]
    locs = [_loc_gold(d, loc, prop) for loc in d["locs"]]
    forms = _forms(d, d["locs"][0]) + _forms(d, d["locs"][1])

    named = {"primary_name": fv(d["ins_first"]), "entity_type": derived(d["ins_kind"], d["ins_first"]),
             "mailing_address": {"line_1": fv(d["ins_street"]), "city": fv(d["ins_city"]), "state": fv("NY"),
                                 "postal_code": fv(d["ins_zip"])}}
    if d["ins_second"]:
        named["additional_named_insureds"] = [{"name": fv(d["ins_second"]),
                                                "entity_type": derived("Individual", d["ins_second"])}]

    optional = [
        {"coverage_name": fv("Auto Increase in Insurance"), "form_reference": fv("FL-10"),
         "notes": fv("1.0% per Quarter"), "premium": _mn(l1["fl10_n"])},
        {"coverage_name": fv("Premises Alarm"), "form_reference": fv("ML-216"),
         "notes": fv("Smoke Detectors 2%"), "premium": _mn(l1["ml_n"])},
        {"coverage_name": fv("Dwelling Package VIP Plus (FL2 and FL3)"), "form_reference": fv("DFL-153P"),
         "notes": fv("See Attached Form for Complete Enhanced Coverage Description and Limits"),
         "premium": _mn(l1["dfl_n"])},
    ] + [{"coverage_name": fv(t), "form_reference": fv("DFL-153P"), "is_included": derived("Yes", t)}
         for t in ENHANCED[:11]] + [
        {"coverage_name": fv("Personal Injury"), "form_reference": fv("DFL-153P"), "is_included": derived("Yes", "Personal Injury")},
        {"coverage_name": fv("Pollution Liability"), "form_reference": fv("DFL-153P"), "is_included": derived("Yes", "Pollution Liability")},
        {"coverage_name": fv("Premises Medical Payments"), "form_reference": fv("DFL-153P"), "is_included": derived("Yes", "Premises Medical Payments")},
    ]
    # the long "Extension of Coverage" entry wraps onto a second printed line; state the first line only
    optional[3 + 10]["coverage_name"] = fv("Extension of Coverage- Green Environmental, Safety and Efficiency")

    return {
        "document": {
            "document_type": fv("Declaration", evidence="Declaration Page"),
            "document_title_as_stated": fv("Declaration Page"),
            "line_of_business_as_stated": fv("Standard Landlords Package Policy"),
            "transaction_effective_date": date_fv(d["eff"]),
            "print_date": date_fv(d["prt"]),
            "copy_type": fv("Agent Copy"),
            "applicable_coverages": [fv(t) for t in ("Residence", "Other Structures", "Personal Property",
                                                      "Premises Liability", "Medical Payments")],
        },
        "carrier": {
            "company_name": fv("Dryden Mutual Insurance Company"),
            "company_structure": fv("A New York Mutual Company"),
            "address": addr("4289 Franklin", "Dryden", "New York", "13053", line_2="P.O. Box 708"),
            "contact": {"website": fv("www.drydenmutual.com")},
            "state_of_issue": derived("NY", "Dryden, New York 13053"),
        },
        "producer": {
            "agency_name": fv(d["ag_name"]),
            "producer_code": fv(d["ag_code"]),
            "address": addr(d["ag_street"], d["ag_city"], "NY", d["ag_zip"]),
            "contact": {"phone": fv(d["ag_phone"])},
        },
        "policy": {
            "policy_number": fv(d["pol"]),
            "account_id": fv(d["acct"]),
            "policy_form_name": fv("Standard Landlords Package Policy"),
            "plan_type": fv("Co-Operative Plan"),
            "is_assessable": derived("No", "Non- Assessable Policy"),
            "effective_date": date_fv(d["eff"]),
            "expiration_date": date_fv(d["exp"]),
            "effective_time": fv("12:01am"),
            "expiration_time": fv("12:01am"),
            "time_zone": fv("Standard Time"),
            "policy_term_months": derived("12", d["eff"], 12),
        },
        "named_insured": named,
        "locations": locs,
        "billing": {"bill_to_party": fv("Insured"),
                    "billing_note": fv("Your billing invoice will be mailed separately.")},
        "additional_fields": [
            extra("Limit", "%s Each Occurrence" % d["l_n"], section="Annual Premium Computation",
                  evidence=d["l_n"]),
        ],
        "premium": {
            "total_policy_premium": _mn(d["total_n"]),
            "fire_fee": _mn(d["fire_n"]),
            "inland_marine_premium": _mn("0.00"),
            "premium_by_coverage_part": [
                {"coverage_part": derived("Location %d" % loc["i"], "Loc. #"), "premium": _mn(loc["total_n"])}
                for loc in d["locs"]],
            "discounts_and_credits": [
                {"description": fv("Credit or Surcharge for Coverage A - Deductible"),
                 "applies_to": derived("Location %d" % loc["i"], "Location Number:"),
                 "amount": _mn(loc["dc_n"]), "is_applied": derived("Yes", "Credit or Surcharge for Coverage A - Deductible")}
                for loc in d["locs"]],
        },
        "forms_and_endorsements": forms,
        "deductibles": [{"applies_to": derived("Coverage A", "Credit or Surcharge for Coverage A - Deductible"),
                         "deductible_type": derived("All Other Perils", "Deductible:"),
                         "amount": _mn(d["ded_s"])}],
        "state_notices": [{"notice_title": fv("Flood Disclosure Notice"), "form_reference": fv("FMD-1")},
                          {"notice_title": fv("Privacy Notice"), "form_reference": fv("DMIC-PP")}],
        "dwelling_fire": {
            "dwelling": {
                "described_location": dict(prop),
                "occupancy_type": fv(l1["fam_dw"]),
                "number_of_units": fv(l1["fam"][0], int(l1["fam"][0]), evidence=l1["fam"]),
                "construction_type": fv(l1["constr"]),
                "protection_class": fv(d["protect"]),
                "territory_code": fv(l1["zone"], evidence="Rating Zone:"),
                "year_built": fv(l1["year"]),
                "distance_to_hydrant": fv(d["hydrant"]),
                "feet_to_hydrant": fv(d["hydrant"]),
                "rating_type": fv("Standard"),
                "rating_zone": fv(l1["zone"], evidence="Rating Zone:"),
                "fire_district": fv(d["prop_city"]),
                "miles_to_fire_department": fv(d["miles"]),
                "renovator_credit": fv("No"),
                "special_rating_conditions": fv("None"),
            },
            "property_coverages": {
                "coverage_a_dwelling_limit": _mn(l1["a_n"]),
                "coverage_b_other_structures_limit": _mn(l1["b_n"]),
                "coverage_c_personal_property_limit": _mn(l1["c_n"]),
                "coverage_e_additional_living_expense_limit": _mn(l1["d_n"]),
                "covered_causes_of_loss": fv(d["cause"]),
                "loss_settlement_basis": fv(d["settle"]),
                "loss_settlement_contents": fv("Replacement Cost Contents"),
                "inflation_guard_percentage": fv("1.0%", evidence="1.0% per Quarter"),
                "inflation_guard_period": fv("per Quarter"),
            },
            "liability_coverages": {
                "coverage_l_premises_liability_limit": _mn(d["l_n"]),
                "premises_liability_aggregate_limit": _mn(d["g_n"]),
                "coverage_m_medical_payments_per_person_limit": _mn(d["mp_n"]),
                "coverage_m_medical_payments_per_occurrence_limit": _mn(d["ma_n"]),
            },
            "deductibles": {"all_other_perils_deductible": _mn(d["ded_s"])},
            "optional_endorsement_coverages": optional,
            "dwellings": [_dwelling_gold(d, loc, prop) for loc in d["locs"]],
        },
    }
