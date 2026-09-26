"""
Shared pieces for the two Dryden Mutual dwelling-fire profiles (declarations and
policy-change endorsement).  Both are the same two-location Standard Landlords
Package Policy: a summary page, then for each location a coverage page, a forms
page and a premium-computation page.  This module holds the draw, the REPLACE
builder, the gold pieces and the arithmetic that are common to both.

Not a profile itself (no SOURCE), so the engine skips it.
"""

from __future__ import annotations

from datetime import date, timedelta

import fitz

from ..engine import addr, amt, date_fv, derived, extra, fv, money

FONT_B = "hebo"

# --- static printed content -------------------------------------------------------------

FORMS = [  # number, edition, title, key of the premium printed for it (or None)
    ("{comp_no}", "09/00", "{comp_title}", None),
    ("FMD-1", "08/08", "Flood Disclosure Notice", None),
    ("FL-10", "01/92", "Auto Increase in Insurance", "fl10"),
    ("FL-18", "06/96", "Intentional Acts Exclusion", "zero"),
    ("FL-20", "01/92", "Agreement", None),
    ("FL-30", "05/92", "Amendatory Endorsement", None),
    ("FL-42", "05/92", "Building Theft Coverage", "fl42"),
    ("FL-52A", "12/98", "Trampoline Exclusion", "fl52"),
    ("FL-83", "02/02", "Amendment of Policy Conditions", None),
    ("FL-84A", "04/94", "New York Amendatory End.", None),
    ("FL-19", "04/94", "Amended Limits of Liability", None),
    ("FL-OLT", "01/92", "Premises Liability Coverage", "zero"),
    ("DMIC-PP", None, "Privacy Notice", None),
    ("DFL-153P", "11/23", "Dwelling Package VIP Plus (FL2 and FL3)", "dfl"),
    ("ML-216", "06/99", "Premises Alarm", "alarm"),
]

VIP_ITEMS = [
    ("Coverage C- Personal Property Replacement Cost", None),
    ("Limited Flood Coverage", None),
    ("Debris Removal", None),
    ("Trees Plants Shrubs And Lawns", None),
    ("Generator Expense", None),
    ("Earth Movement", None),
    ("Ordinance or Law", None),
    ("Motorized Vehicles", None),
    ("Replacement of Locks", None),
    ("Underground Utility Line Coverage", None),
    ("Extension of Coverage- Green Environmental, Safety and Efficiency Improvements",
     "Extension of Coverage- Green Environmental, Safety and Efficiency"),
    ("Personal Injury", None),
    ("Pollution Liability", None),
    ("Premises Medical Payments", None),
]

CARRIER_ADDR = dict(line_1="12 Ellis Drive", line_2="P.O. Box 635", city="Dryden")

PROT = {  # protection class -> (hydrant, fire-dept distance)
    "Protected": ("1000 Feet or Less", "5 Miles or Less"),
    "Semi-Protected": ("Greater than 1000 Feet", "5 Miles or Less"),
    "Unprotected": ("Greater than 1000 Feet", "Greater than 5 Miles"),
}
DED_CREDIT = {1000: 0.06, 2500: 0.17, 5000: 0.26}
ALARMS = [("Smoke Detectors", 2), ("Smoke Detectors", 3), ("Fire Alarm", 5)]
LIABILITY = [(100000, 300000), (300000, 600000), (500000, 1000000), (1000000, 2000000),
             (2000000, 3000000)]
SECOND_BLDG = ["Garage With Apartment", "Guest Cottage", "Carriage House", "Rental Cottage"]
FIRST_BLDG = ["Main House", "Farmhouse", "Lake House", "Residence"]
COMP = [("FL-3", "(Special)", "Causes of Loss (Special Perils)"),
        ("FL-2", "(Broad)", "Causes of Loss (Broad Perils)")]


def ralign(text, width, size=10.0, font=FONT_B):
    """Leading spaces so ``text`` ends where a span ``width`` pt wide used to end."""
    w = fitz.get_text_length(text, fontname=font, fontsize=size)
    sp = fitz.get_text_length(" ", fontname=font, fontsize=size)
    n = int(round((width - w) / sp))
    return (" " * n if n > 0 else "") + text


def _ra(key, width):
    return lambda d: ralign(d[key], width)


# --- draw -------------------------------------------------------------------------------

def draw_core(v, C, endo):
    d = {}
    # named insured
    r = v.rng.random()
    if r < 0.22:
        d.update(ins_name=C.business(v), ins_kind="Business")
    elif r < 0.42:
        d.update(ins_name=C.person(v), ins_kind="Individual")
    else:
        a, b = C.person(v), C.person(v)
        d.update(ins_name="%s & %s" % (a, b), ins_kind="Individual")
    ins = C.address(v)
    box = v.integer(12, 990)
    if v.maybe(0.6):
        d.update(ins_l1="PO Box %d" % box, ins_zip="%s-%04d" % (ins["postal_code"], box))
    else:
        d.update(ins_l1=ins["line_1"], ins_zip=ins["postal_code"])
    d.update(ins_city=ins["city"])
    d["ins_city_line"] = "%s, NY %s" % (ins["city"], d["ins_zip"])

    # agency (short strings: the block is right-aligned and cannot grow leftwards)
    for _ in range(40):
        name = C.agency(v)
        if len(name) <= 30:
            break
    small = [t for t in C.TOWNS if len(t[0]) <= 6]
    city, zip5, _county = v.choice(small)
    abox = v.integer(100, 899) if endo else v.integer(10, 99)
    d.update(ag_name=name, ag_code="%d" % v.integer(100, 899), ag_phone=C.phone(v, "paren"),
             ag_l1="PO Box %d" % abox, ag_city=city,
             ag_zip=("%s-%04d" % (zip5, abox)) if endo else zip5)
    d["ag_city_line"] = "%s, NY %s" % (city, d["ag_zip"])

    # policy identity and dates
    tail = "-01"
    renewal = v.maybe(0.3)
    if renewal:
        tail = "-%02d" % v.integer(2, 6)
    d.update(policy_no=v.policy_number("LPP{8d}") + tail, file_no="L%06d" % v.integer(100000, 999999),
             is_renewal="Yes" if renewal else "No", trans="Renewal" if renewal else "New Business")
    eff, exp = C.term(v, 12, earliest=date(2024, 1, 1), latest=date(2026, 12, 31))
    d.update(eff=C.fmt(eff), exp=C.fmt(exp))
    if endo:
        chg = eff + timedelta(days=v.integer(25, 300))
        d.update(chg=C.fmt(chg), vc=C.fmt(chg + timedelta(days=v.integer(3, 10))))
    else:
        d.update(vc=C.fmt(eff + timedelta(days=v.integer(1, 6))))

    # billing
    bill = v.choice([("Insured Direct", "Insured"), ("Agency Bill", "Agency")])
    freq = v.choice(["Annual", "Annual", "Semi-Annual", "Quarterly"])
    d.update(bill_plan=bill[0], bill_to=bill[1], bill_freq=freq,
             bill_line="%s %s %s" % (bill[0], freq, d["trans"]))

    # risk: both buildings share one street address
    pr = C.address(v)
    zip9 = "%s-%04d" % (pr["postal_code"], v.integer(1, 9999))
    d.update(pr_street=pr["line_1"], pr_city=pr["city"], pr_zip=zip9, pr_county=pr["county"])
    descs = (v.choice(FIRST_BLDG), v.choice(SECOND_BLDG))
    for i in (1, 2):
        d["l%d_desc" % i] = descs[i - 1]
        d["l%d_line" % i] = "%s, (%s), %s, NY %s" % (pr["line_1"], descs[i - 1], pr["city"], zip9)
        fam = v.choice([1, 1, 2])
        d["l%d_fam" % i] = "%d Family" % fam
        d["l%d_fam_n" % i] = fam
        d["l%d_risk" % i] = "%d Family Dwelling" % fam
        d["l%d_constr" % i] = v.choice(["Frame", "Frame", "Masonry", "Masonry Veneer"])
        d["l%d_year" % i] = str(v.integer(1890, 2016))
    d["zone"] = str(v.integer(1, 6))

    prot = v.choice(["Protected", "Semi-Protected"] if endo else list(PROT))
    special = v.choice(["None", "None", "Seasonal Occupancy"])
    comp = v.choice(COMP)
    d.update(rating_type=v.choice(["Standard", "Standard", "Preferred"]),
             renovator=v.choice(["No", "No", "Yes"]), comp_no=comp[0], comp_label=comp[1], comp_title=comp[2],
             comp_line="%s %s" % (comp[0], comp[1]), special=special,
             settle=v.choice(["Replacement Cost", "Replacement Cost", "Actual Cash Value"]))
    pct_q = v.choice([1.0, 1.5, 2.0])
    dev = v.choice(ALARMS)
    d.update(prot=prot, hydrant=PROT[prot][0], miles=PROT[prot][1], fl10_pct="%.1f" % pct_q,
             fl10_txt="%.1f%% per Quarter" % pct_q, dev="%s %d%%" % dev, dev_pct=dev[1])
    d["ded"] = v.choice([1000, 2500, 2500, 5000])
    d["ded_s"] = "$ %s" % C.num(d["ded"])

    # limits and premium arithmetic
    occ, agg = v.choice(LIABILITY)
    medp = v.choice([1000, 2500, 5000])
    meda = v.choice([25000, 50000, 100000])
    d.update(occ=occ, agg=agg, medp=medp, meda=meda, occ_s=C.num(occ), agg_s=C.num(agg),
             medp_s=C.num(medp), meda_s=C.num(meda))
    c = v.choice([10000, 15000, 20000, 25000])
    d.update(c=c, c_s=C.num(c))
    d["c_prem"] = round(c / 1000.0 * v.rng.uniform(4.6, 5.4))
    d["l_prem"] = round(occ / 100000.0 * 3 + 60 + v.integer(0, 14))
    d["m_prem"] = v.integer(24, 44)
    d["fl42"] = v.choice([8, 10, 12])
    d["fl52"] = -v.choice([2, 3])
    fb, fd = v.choice([0.05, 0.10, 0.10, 0.15]), v.choice([0.10, 0.10, 0.20])
    rate = v.rng.uniform(3.3, 5.2)
    total = 0
    for i in (1, 2):
        a = v.limit(150000, 600000, 25000) if i == 1 else v.limit(100000, 400000, 25000)
        b = C.round_to(a * fb, 1000)
        dd = C.round_to(a * fd, 1000)
        base = round(a / 1000.0 * rate * v.rng.uniform(0.97, 1.03))
        fl10 = round(base * 0.02 * pct_q)
        dfl = round(base * 0.10)
        alarm = -round(base * dev[1] / 100.0)
        dcr = -round(base * DED_CREDIT[d["ded"]])
        loc_total = (base + d["c_prem"] + d["l_prem"] + d["m_prem"] + fl10 + d["fl42"]
                     + d["fl52"] + dfl + alarm + dcr)
        d.update({"l%d_a" % i: a, "l%d_b" % i: b, "l%d_d" % i: dd, "l%d_base" % i: base,
                  "l%d_fl10" % i: fl10, "l%d_dfl" % i: dfl, "l%d_alarm" % i: alarm,
                  "l%d_dcr" % i: dcr, "l%d_total" % i: loc_total})
        total += loc_total
    d["total"] = total
    for k in ("c_prem", "l_prem", "m_prem", "fl42", "fl52"):
        d[k + "_s"] = C.num(d[k], True)
    for i in (1, 2):
        for k in ("a", "b", "d"):
            d["l%d_%s_s" % (i, k)] = C.num(d["l%d_%s" % (i, k)])
        for k in ("base", "fl10", "dfl", "alarm", "dcr", "total"):
            d["l%d_%s_s" % (i, k)] = C.num(d["l%d_%s" % (i, k)], True)
        # mortgagee
        if v.maybe(0.4):
            ml = C.address(v)
            m = dict(name=C.lender(v), street=ml["line_1"], city=ml["city"], zip=ml["postal_code"],
                     loan=C.loan_number(v))
            m["line"] = "%s, %s, %s, NY %s  Loan # %s" % (m["name"], m["street"], m["city"], m["zip"], m["loan"])
            d["l%d_mort" % i] = m
            d["l%d_mort_line" % i] = m["line"]
        else:
            d["l%d_mort" % i] = None
            d["l%d_mort_line" % i] = "None Listed"
    d["total_s"] = C.num(total, True)
    return d


def audit_core(d):
    out = []
    t = 0
    for i in (1, 2):
        s = (d["l%d_base" % i] + d["c_prem"] + d["l_prem"] + d["m_prem"] + d["l%d_fl10" % i] + d["fl42"]
             + d["fl52"] + d["l%d_dfl" % i] + d["l%d_alarm" % i] + d["l%d_dcr" % i])
        if s != d["l%d_total" % i]:
            out.append("location %d premium components do not sum" % i)
        t += d["l%d_total" % i]
    if t != d["total"]:
        out.append("policy total is not the sum of the locations")
    return out


# --- REPLACE ----------------------------------------------------------------------------

def loc_entries(S, i, cov, frm, prm, first):
    """Entries for location ``i`` (source strings in ``S``) on its three pages."""
    p = "l%d_" % i
    src = S[i]
    ex = {"exact": True}
    e = []
    # coverage page
    nth_b = 0 if src["b"] == src["d"] == S["meda"] else None
    e.append((src["a"], "{%sa_s}" % p, dict(ex, page=cov)))
    same_b_d = src["b"] == src["d"]
    if src["b"] == S["meda"]:      # B, D and each-accident share text on this page
        e.append((src["b"], "{%sb_s}" % p, dict(ex, page=cov, nth=0)))
        e.append((src["d"], "{%sd_s}" % p, dict(ex, page=cov, nth=1)))
        e.append((S["meda"], "{meda_s}", dict(ex, page=cov, nth=2)))
    else:
        e.append((src["b"], "{%sb_s}" % p, dict(ex, page=cov, nth=0 if same_b_d else None)))
        e.append((src["d"], "{%sd_s}" % p, dict(ex, page=cov, nth=1 if same_b_d else None)))
        e.append((S["meda"], "{meda_s}", dict(ex, page=cov)))
    e.append((src["year"], "{%syear}" % p, dict(ex, page=cov)))
    e.append(("Frame" if first else "Frame", "{%sconstr}" % p, dict(ex, page=cov)))
    e.append(("1 Family", "{%sfam}" % p, dict(ex, page=cov)))
    e.append(("1", "{zone}", dict(ex, page=cov, nth=2 if first else 0)))
    e.append(("None Listed", "{%smort_line}" % p, dict(ex, page=cov)))
    # forms page
    # premium page
    e.append((S["meda"], "{meda_s}", dict(ex, page=prm)))
    e.append((src["a"], "{%sa_s}" % p, dict(ex, page=prm)))
    e.append((src["base"], "{%sbase_s}" % p, dict(ex, page=prm)))
    e.append((src["fl10"], "{%sfl10_s}" % p, dict(ex, page=prm)))
    e.append((src["dfl"], "{%sdfl_s}" % p, dict(ex, page=prm)))
    e.append((src["alarm"], "{%salarm_s}" % p, dict(ex, page=prm)))
    e.append((src["dcr"], "{%sdcr_s}" % p, dict(ex, page=prm)))
    for pg in (cov, frm, prm):
        e.append(("1 Family Dwelling", "{%srisk}" % p, dict(ex, page=pg)))
    return e


def build_replace(S, kind):
    """S: source-string table for the document; kind: 'dec' or 'endo'."""
    ex = {"exact": True}
    R = []
    pg = S["pages"]
    # identity
    R += [
        (S["ins_name"], "{ins_name}"),
        (S["ins_l1"], "{ins_l1}", ex),
        (S["ins_city_line"], "{ins_city_line}", ex),
        (S["policy_no"], "{policy_no}"),
        (S["file_no"], "{file_no}"),
        (S["eff"], "{eff}"),
        (S["exp"], "{exp}"),
        (S["vc"], "{vc}"),
    ]
    n_identity = len(R)
    # agency block (right aligned in the source, so pad on the left)
    W = S["agency_w"]
    for page, w in W["name"].items():
        R.append((S["ag_name"], _ra("ag_name", w), dict(ex, page=page)))
    R.append((S["ag_code"], "%s{ag_code}" % S["ag_code_prefix"], ex))
    if kind == "endo":
        R.append(("# 760", "# {ag_code}", ex))
    for page, w in W["l1"].items():
        R.append((S["ag_l1"], _ra("ag_l1", w), dict(ex, page=page)))
    for page, w in W["city"].items():
        R.append((S["ag_city_line"], _ra("ag_city_line", w), dict(ex, page=page)))
    R.append((S["ag_phone"], "{ag_phone}"))
    for page, w in W["bill"].items():
        R.append(("Insured Direct Annual New Business", _ra("bill_line", w), dict(ex, page=page)))
    # "From " is redrawn whole beside the date; drop its trailing space so it keeps its size
    for page in S["from_pages"]:
        R.append(("From ", "From", {"raw": True, "page": page, "nth": 0}))
    # locations
    R += loc_entries(S, 1, *pg["loc1"], first=True)
    R += loc_entries(S, 2, *pg["loc2"], first=False)
    R.append((S[1]["line"], "{l1_line}"))
    R.append((S[2]["line"], "{l2_line}"))
    # summary page(s)
    sp = pg["summary"]
    R.append(("1 Family Dwelling", "{l1_risk}", dict(ex, page=sp, nth=0)))
    R.append(("1 Family Dwelling", "{l2_risk}", dict(ex, page=sp, nth=1)))
    R.append((S[1]["total"], "{l1_total_s}", ex))
    R.append((S[2]["total"], "{l2_total_s}", ex))
    R.append((S["total"], "{total_s}", ex))
    # shared values
    R += [
        ("10,000", "{c_s}", ex), ("5,000", "{medp_s}", ex),
        ("2,000,000", "{occ_s}"), ("3,000,000", "{agg_s}"),
        (S["c_prem"], "{c_prem_s}", ex), ("77.00", "{l_prem_s}", ex), ("33.00", "{m_prem_s}", ex),
        ("10.00", "{fl42_s}", ex), ("-2.00", "{fl52_s}", ex),
        ("$e", "$", ex),
        ("$ 2,500", "{ded_s}", ex),
        ("FL-3 (Special)", "{comp_line}", ex),
        ("FL-3", "{comp_no}", ex),
        ("Causes of Loss (Special Perils)", "{comp_title}", ex),
        ("Replacement Cost", "{settle}", ex),
        ("Hamilton", "{pr_county}", ex),
        ("Semi-Protected" if kind == "dec" else "Protected", "{prot}", ex),
        ("5 Miles or Less", "{miles}", ex),
        ("Raquette Lake", "{pr_city}", ex),
        (S["hydrant"], "{hydrant}", ex),
        ("Smoke Detectors 2%", "{dev}", ex),
        ("None", "{special}", ex),
        ("Standard", "{rating_type}", ex),
        ("No", "{renovator}", ex),
        ("1.0% per Quarter", "{fl10_txt}", ex),
    ]
    # location and shared values are drawn from small domains, so a new value can equal
    # the old text by chance; that is not a leak.
    return R[:n_identity] + [(e[0], e[1], dict(e[2] if len(e) > 2 else {}, leak=False))
                             for e in R[n_identity:]]


# --- gold pieces ------------------------------------------------------------------------

def _mort_party(d, i):
    m = d["l%d_mort" % i]
    if not m:
        return None
    return {"name": fv(m["name"]),
            "address": addr(m["street"], m["city"], "NY", m["zip"]),
            "loan_number": fv(m["loan"]),
            "party_type": derived("Mortgagee", "Mortgagee Information"),
            "applies_to": derived("Location %d" % i, "Mortgagee Information")}


def forms_gold(d, i):
    out = []
    for no, ed, title, pk in FORMS:
        no_s, title_s = no.format(**d), title.format(**d)
        f = {"form_number": fv(no_s), "form_title": fv(title_s),
             "applies_to": derived("Location %d" % i, "Supplemental Policy Declarations for Location #")}
        if ed:
            f["edition_date"] = fv(ed)
        if pk == "zero":
            f["premium"] = money("0.00")
        elif pk:
            f["premium"] = money(d["l%d_%s_s" % (i, pk)] if pk in ("fl10", "dfl", "alarm")
                                 else d[pk + "_s"])
        # the line printed under the form's row
        if pk == "fl10":
            f["percentage"] = fv(d["fl10_txt"])
        elif pk == "alarm":
            f["percentage"] = fv("%d%%" % d["dev_pct"], evidence=d["dev"])
        elif pk == "dfl":
            f["included_coverages"] = [fv(name, evidence=ev) for name, ev in VIP_ITEMS]
        out.append(f)
    return out


def location_gold(d, i):
    p = "l%d_" % i
    address = addr(d["pr_street"], d["pr_city"], "NY", d["pr_zip"])
    address["county"] = fv(d["pr_county"])
    covs = [
        {"coverage_code": fv("Coverage A"), "coverage_name": fv("Coverage A - Residence", evidence="Residence"),
         "limit_amount": money(d[p + "a_s"]),
         "premium": money(d[p + "base_s"]), "notes": fv("Base Premium before Deductible")},
        {"coverage_code": fv("Coverage B"),
         "coverage_name": fv("Coverage B - Other Structures", evidence="Other Structures"),
         "limit_amount": money(d[p + "b_s"])},
        {"coverage_code": fv("Coverage C"),
         "coverage_name": fv("Coverage C - Personal Property", evidence="Personal Property"),
         "limit_amount": money(d["c_s"]), "premium": money(d["c_prem_s"])},
        {"coverage_code": fv("Coverage D"),
         "coverage_name": fv("Coverage D - Addl.Living Exp. and Loss of Rent",
                             evidence="Addl.Living Exp. and Loss of Rent"),
         "limit_amount": money(d[p + "d_s"])},
        {"coverage_code": fv("Coverage L"), "coverage_name": fv("Premises Liability"),
         "limit_amount": money(d["occ_s"]), "aggregate_limit_amount": money(d["agg_s"]),
         "limit_basis": fv("Each Occurrence"), "premium": money(d["l_prem_s"])},
        {"coverage_code": fv("Coverage M"), "coverage_name": fv("Medical Payments"),
         "limit_amount": money(d["medp_s"]), "limit_basis": fv("Each Person"),
         "premium": money(d["m_prem_s"])},
        {"coverage_name": fv("Medical Payments", evidence="Each Accident"),
         "limit_amount": money(d["meda_s"]), "limit_basis": fv("Each Accident")},
    ]
    return {
        "location_number": fv(str(i), i, evidence="Location Number:"),
        "address": address,
        "building_description": fv(d[p + "desc"]),
        "occupancy_description": fv(d[p + "risk"]),
        "construction_type": fv(d[p + "constr"]),
        "protection_class": fv(d["prot"]),
        "territory_code": fv(d["zone"]),
        "year_built": fv(d[p + "year"]),
        "alarm_type": fv(d["dev"]),
        "coverages": covs,
    }


PROPERTY_CODES = ("Coverage A", "Coverage B", "Coverage C", "Coverage D")


def dwellings_gold(d):
    """dwelling_fire.dwellings[]: each location as its own pages print it - the
    coverage page (limits under Property Coverages / Liability Coverages, rating
    criteria, mortgagee), the premium computation and the location's total."""
    out = []
    for i in (1, 2):
        p = "l%d_" % i
        loc = location_gold(d, i)
        covs = []
        for c in loc["coverages"]:
            section = "Property Coverages" if c.get("coverage_code", {}).get("raw") in PROPERTY_CODES \
                else "Liability Coverages"
            covs.append(dict({"coverage_section": fv(section)}, **c))
        entry = {
            "location_number": fv(str(i), i, evidence="Location Number:"),
            "described_location": loc["address"],
            "property_description": fv(d[p + "desc"]),
            "occupancy_type": fv(d[p + "risk"]),
            "number_of_units": fv(d[p + "fam"], d[p + "fam_n"]),
            "construction_type": fv(d[p + "constr"]),
            "year_built": fv(d[p + "year"]),
            "protection_class": fv(d["prot"]),
            "rating_type": fv(d["rating_type"]),
            "rating_zone": fv(d["zone"], evidence="Rating Zone:"),
            "renovator_credit": fv(d["renovator"]),
            "fire_district": fv(d["pr_city"]),
            "feet_to_hydrant": fv(d["hydrant"]),
            "miles_to_fire_department": fv(d["miles"]),
            "fire_alarm_type": fv(d["dev"]),
            "special_rating_conditions": fv(d["special"]),
            "covered_causes_of_loss": fv(d["comp_line"]),
            "loss_settlement_basis": fv(d["settle"]),
            "loss_settlement_contents": fv("Replacement Cost Contents"),
            "all_other_perils_deductible": money(d["ded_s"]),
            "deductible_credit_amount": money(d[p + "dcr_s"]),
            "total_premium": money(d[p + "total_s"]),
            "fire_surcharge": money("0.00", evidence="New York State Fire Surcharge"),
            "coverages": covs,
        }
        if not d[p + "mort"]:
            entry["mortgagees_none_listed"] = fv("None Listed")
        out.append(entry)
    return out


def dwelling_fire_gold(d):
    """dwelling_fire.* describes Location 1 (the main dwelling); both are under locations[]
    and dwellings[]."""
    address = addr(d["pr_street"], d["pr_city"], "NY", d["pr_zip"])
    address["county"] = fv(d["pr_county"])
    loc1 = derived("Location 1", "Supplemental Policy Declarations for Location #")
    opt = [
        {"coverage_name": fv("Auto Increase in Insurance"), "form_reference": fv("FL-10"),
         "notes": fv(d["fl10_txt"]), "premium": money(d["l1_fl10_s"]),
         "applies_to": dict(loc1), "is_included": derived("Yes", "Auto Increase in Insurance")},
        {"coverage_name": fv("Building Theft Coverage"), "form_reference": fv("FL-42"),
         "premium": money(d["fl42_s"]), "applies_to": dict(loc1),
         "is_included": derived("Yes", "Building Theft Coverage")},
        {"coverage_name": fv("Dwelling Package VIP Plus (FL2 and FL3)"), "form_reference": fv("DFL-153P"),
         "premium": money(d["l1_dfl_s"]), "applies_to": dict(loc1),
         "coverage_description": fv("See Attached Form for Complete Enhanced Coverage Description and Limits"),
         "is_included": derived("Yes", "Dwelling Package VIP Plus (FL2 and FL3)")},
        {"coverage_name": fv("Premises Alarm"), "form_reference": fv("ML-216"),
         "premium": money(d["l1_alarm_s"]), "applies_to": dict(loc1), "notes": fv(d["dev"]),
         "is_included": derived("Yes", "Premises Alarm")},
    ]
    for name, ev in VIP_ITEMS:
        opt.append({"coverage_name": fv(name, evidence=ev), "form_reference": fv("DFL-153P"),
                    "applies_to": dict(loc1),
                    "is_included": derived("Yes", ev or name)})
    mort = [m for m in (_mort_party(d, 1), _mort_party(d, 2)) if m]
    out = {
        "dwelling": {
            "described_location": address,
            "occupancy_type": fv(d["l1_risk"]),
            "number_of_units": fv(d["l1_fam"], d["l1_fam_n"]),
            "construction_type": fv(d["l1_constr"]),
            "protection_class": fv(d["prot"]),
            "rating_zone": fv(d["zone"], evidence="Rating Zone:"),
            "year_built": fv(d["l1_year"]),
            "feet_to_hydrant": fv(d["hydrant"]),
            "special_rating_conditions": fv(d["special"]),
            "rating_type": fv(d["rating_type"]),
            "renovator_credit": fv(d["renovator"]),
            "fire_district": fv(d["pr_city"]),
            "miles_to_fire_department": fv(d["miles"]),
            "fire_alarm_type": fv(d["dev"]),
        },
        "property_coverages": {
            "coverage_a_dwelling_limit": money(d["l1_a_s"]),
            "coverage_b_other_structures_limit": money(d["l1_b_s"]),
            "coverage_c_personal_property_limit": money(d["c_s"]),
            "coverage_e_additional_living_expense_limit": money(d["l1_d_s"]),
            "covered_causes_of_loss": fv(d["comp_line"]),
            "loss_settlement_basis": fv(d["settle"]),
            "loss_settlement_contents": fv("Replacement Cost Contents"),
            "inflation_guard_percentage": fv("%s%%" % d["fl10_pct"], evidence=d["fl10_txt"]),
            "inflation_guard_period": fv("per Quarter"),
        },
        "liability_coverages": {
            "coverage_l_premises_liability_limit": money(d["occ_s"]),
            "premises_liability_aggregate_limit": money(d["agg_s"]),
            "coverage_m_medical_payments_per_person_limit": money(d["medp_s"]),
            "coverage_m_medical_payments_per_occurrence_limit": money(d["meda_s"]),
        },
        "deductibles": {"all_other_perils_deductible": money(d["ded_s"])},
        "optional_endorsement_coverages": opt,
        "dwellings": dwellings_gold(d),
    }
    if mort:
        out["mortgagees"] = mort
    return out


def common_gold(d):
    """Sections the two documents print identically (given their drawn values)."""
    ins = {"primary_name": fv(d["ins_name"]), "entity_type": derived(d["ins_kind"]),
           "mailing_address": addr(d["ins_l1"], d["ins_city"], "NY", d["ins_zip"])}
    ded = {"applies_to": derived("Coverage A", "Coverage A - Deductible"),
           "deductible_type": derived("All Other Perils", "Deductible:"),
           "amount": money(d["ded_s"])}
    parties = [m for m in (_mort_party(d, 1), _mort_party(d, 2)) if m]
    forms = forms_gold(d, 1) + forms_gold(d, 2)
    out = {
        "carrier": {
            "company_name": fv("Dryden Mutual Insurance Company"),
            "address": {"line_1": fv(CARRIER_ADDR["line_1"]), "line_2": fv(CARRIER_ADDR["line_2"]),
                        "city": fv(CARRIER_ADDR["city"]), "state": fv("New York", "NY"),
                        "postal_code": fv("13053")},
            "contact": {"website": fv("www.drydenmutual.com")},
            "company_structure": fv("A New York State Advance Premium Co-Operative Fire Insurance Corporation"),
            "state_of_issue": derived("NY", "Dryden, New York 13053"),
        },
        "producer": {
            "agency_name": fv(d["ag_name"]),
            "producer_code": fv(d["ag_code"]),
            "address": addr(d["ag_l1"], d["ag_city"], "NY", d["ag_zip"]),
            "contact": {"phone": fv(d["ag_phone"])},
        },
        "policy": {
            "policy_number": fv(d["policy_no"]),
            "file_number": fv(d["file_no"]),
            "alternate_policy_identifiers": [{"identifier_type": fv("File #"),
                                              "identifier_value": fv(d["file_no"])}],
            "policy_form_name": fv("Standard Landlords Package Policy"),
            "policy_type": fv("Landlords Package Policy"),
            "plan_type": fv("Co-Operative Plan"),
            "is_assessable": derived("No", "Non- Assessable"),
            "effective_date": date_fv(d["eff"]),
            "expiration_date": date_fv(d["exp"]),
            "effective_time": fv("12:01am"),
            "expiration_time": fv("12:01am"),
            "time_zone": fv("Standard Time"),
            "policy_term_months": derived("12", d["eff"], 12),
            "is_renewal": derived(d["is_renewal"], "Renewal" if d["is_renewal"] == "Yes" else "New Business"),
        },
        "named_insured": ins,
        "locations": [location_gold(d, 1), location_gold(d, 2)],
        "forms_and_endorsements": forms,
        "deductibles": [ded],
        "state_notices": [
            {"notice_title": fv("Flood Disclosure Notice"), "form_reference": fv("FMD-1")},
            {"notice_title": fv("Privacy Notice"), "form_reference": fv("DMIC-PP")},
        ],
        "billing": {
            "billing_plan": fv(d["bill_plan"]),
            "bill_to_party": derived(d["bill_to"], d["bill_plan"]),
            "payment_frequency": fv(d["bill_freq"]),
            "billing_note": fv("Your billing invoice will be mailed separately."),
        },
        "premium": {
            "fire_fee": fv("0.00", 0.0, evidence="New York State Fire Surcharge"),
            "discounts_and_credits": [
                {"description": fv("Credit or Surcharge for Coverage A - Deductible"),
                 "amount": money(d["l%d_dcr_s" % i]),
                 "applies_to": derived("Location %d" % i, "Annual Premium Computation for Location #")}
                for i in (1, 2)],
        },
        "dwelling_fire": dwelling_fire_gold(d),
        "_document_dates": None,
    }
    del out["_document_dates"]
    if parties:
        out["interested_parties"] = parties
        # the printed "Loan #" label rides with the composite mortgagee line
        out["additional_fields"] = [
            extra("Loan #", d["l%d_mort" % i]["loan"], section="Mortgagee Information")
            for i in (1, 2) if d["l%d_mort" % i]]
    return out


def doc_common(d, doc_type, title, extra=None):
    doc = {
        "document_type": fv(doc_type[0], doc_type[1]) if isinstance(doc_type, tuple) else fv(doc_type),
        "document_title_as_stated": fv(title),
        "line_of_business_as_stated": fv("Standard Landlords Package Policy"),
        "coverage_parts_present": [fv("Property Coverages"), fv("Liability Coverages")],
        "applicable_coverages": [
            fv("Coverage A - Residence", evidence="Residence"),
            fv("Coverage B - Other Structures", evidence="Other Structures"),
            fv("Coverage C - Personal Property", evidence="Personal Property"),
            fv("Coverage D - Addl.Living Exp. and Loss of Rent",
               evidence="Addl.Living Exp. and Loss of Rent"),
            fv("Premises Liability"), fv("Medical Payments")],
        "print_date": date_fv(d["vc"]),
        "form_run_code": fv("VC %s" % d["vc"]),
        "copy_type": fv("Agent Copy"),
    }
    if extra:
        doc.update(extra)
    return doc


def summary_premium(d, total_raw):
    return {
        "total_policy_premium": money(total_raw),
        "premium_by_coverage_part": [
            {"coverage_part": derived("Location 1", "Loc. #"), "premium": money(d["l1_total_s"])},
            {"coverage_part": derived("Location 2", "Loc. #"), "premium": money(d["l2_total_s"])},
        ],
        "inland_marine_premium": money("0.00"),
    }
