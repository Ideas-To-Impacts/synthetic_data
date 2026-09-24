"""
Dryden Mutual Insurance Company - "Standard Landlords Package Policy" application
(dryden_mutual_dfire_app.pdf, 14 pages).

An e-signed application packet: pages 1-4 application + premium schedule for
location 1, pages 5-8 the same for location 2, page 9 loss history and the
signatures, page 10 NY Regulation 194 disclosure, page 11 ACORD 35 cancellation
of the prior owner's policy, page 12 ACORD 60 flood rejection, pages 13-14 the
e-signature completion certificate.

The source is a redacted copy: overlay text in other fonts, a producer name
that differs between pages, the Reg 194 applicant printed as "Kenneth &Noelle
Norcross", and certificate lines whose overlay name collides with the printed
e-mail. This profile unifies them so the packet reads as one document.

Page 11 (ACORD 35) is left exactly as printed: its overlay text is NimbusSans whose true glyphs are wider
than the extracted bbox, so the engine's redaction rectangle cannot erase it cleanly (engine limitation).

Yes/No answers are flipped by swapping the two labels next to a fixed "X"
(the mark cannot be moved, but the word beside it can change).

GAPS (printed, no canonical leaf): see GAPS below.
"""

from datetime import date, timedelta

import fitz

from ..engine import addr, amt, derived, date_fv, extra, fv, money

SOURCE = "Dryden Mutual/dwelling_fire/dryden_mutual_dfire_app.pdf"

GAPS = [
    "Location 2's dwelling details (heating, fuel, roof, electrical, market value, years owned, Y/N answers, "
    "water exposure) and its rating criteria beyond locations[]: dwelling_fire.dwelling and "
    "underwriting_questions[] carry location 1 only",
    "Purchase Price / Cost of Improvements: printed as a bare '$' with a blank value (nothing to state)",
    "Insured occupation, second applicant's marital status: blank on the form",
    "Application file number 'File #' is stated only as an alternate identifier (no policy number is printed)",
    "Agency Service Representative name/phone/e-mail vs the agency phone: a single producer contact",
    "ACORD 35 / ACORD 60 / e-signature certificate / Reg 194 prose: captured by text_sections, no other leaf",
]

CARRIER_ADDR = "12 Ellis Drive"

# (form number, title, is_premium_bearing)
FORMS = [
    ("FL-3", "Causes of Loss (Special Perils)", None),
    ("FMD-1", "Flood Disclosure Notice", None),
    ("FL-10", "Auto Increase in Insurance", "fl10"),
    ("FL-18", "Intentional Acts Exclusion", None),
    ("FL-20", "Agreement", None),
    ("FL-30", "Amendatory Endorsement", None),
    ("FL-42", "Building Theft Coverage", "fl42"),
    ("FL-52A", "Trampoline Exclusion", "fl52"),
    ("FL-83", "Amendment of Policy Conditions", None),
    ("FL-84A", "New York Amendatory End.", None),
    ("FL-19", "Amended Limits of Liability", None),
    ("FL-OLT", "Premises Liability Coverage", None),
    ("DMIC-PP", "Privacy Notice", None),
    ("DFL-153P", "Dwelling Package VIP Plus (FL2 and FL3)", "dfl"),
    ("ML-216", "Premises Alarm", "alarm"),
]
DFL_ITEMS = [
    "Coverage C- Personal Property Replacement Cost", "Limited Flood Coverage", "Debris Removal",
    "Trees Plants Shrubs And Lawns", "Generator Expense", "Earth Movement", "Ordinance or Law",
    "Motorized Vehicles", "Replacement of Locks", "Underground Utility Line Coverage",
    "Extension of Coverage- Green Environmental, Safety and Efficiency Improvements",
    "Personal Injury", "Pollution Liability", "Premises Medical Payments",
]

HEATING = ["Hot Water Boiler", "Forced Air Furnace", "Steam Boiler", "Heat Pump"]
FUELS = ["Oil", "Propane", "Natural Gas", "Electric"]
ROOFS = ["Metal/Steel", "Asphalt Shingle", "Slate", "Wood Shingle"]
ELECTRIC = ["Circuit Breakers", "Fuses"]
WATER = ["Lake / River Frontage", "Pond on Premises", "Creek / Stream"]
EXPLAIN = ["fireplace", "wood stove", "pellet stove", "kerosene heater"]
SOLID_FUEL = ("fireplace", "wood stove", "pellet stove")
COL_FORMS = [("FL-3 (Special)", "FL-3", "Special Perils"), ("FL-2 (Broad)", "FL-2", "Broad Perils")]
HYDRANT = ["Greater than 1000 Feet", "Within 1000 Feet"]
MILES = ["5 Miles or Less", "Greater than 5 Miles"]
PROT = ["Protected", "Semi-Protected", "Unprotected"]
SETTLE = [("Replacement Cost", "Replacement Cost Contents"), ("Actual Cash Value", "Actual Cash Value Contents")]
CONSTR = ["Frame", "Masonry", "Masonry Veneer"]
PREV_CARRIERS = ["NYCM", "Allstate", "Travelers", "Erie", "Utica National", "Farmers", "Liberty Mutual"]
MARITAL = ["Married", "Single", "Divorced"]
AGENT_TOWNS = ["Delhi", "Andes", "Rome", "Owego", "Utica", "Malone", "Camden", "Elmira"]
AGENT_STREETS = ["88 Main St", "12 Elm St", "5 Mill St", "7 Front St", "4 Depot St", "9 Park Ave"]
ZIPS = {"Norwich": "13815", "Oxford": "13830", "Delhi": "13753", "Andes": "13731", "Rome": "13440",
        "Camden": "13316", "Hudson": "12534", "Owego": "13827", "Ithaca": "14850", "Utica": "13501",
        "Malone": "12953", "Oneida": "13421", "Walton": "13856", "Sidney": "13838", "Milford": "13807",
        "Fulton": "13069", "Elmira": "14901"}


def _n(x):
    return format(x, ",")


def _c(x):
    return format(x, ",.2f")


def _name(v, C, surname=None):
    for _ in range(40):
        nm = C.person(v, surname)
        if len(nm) <= 19:
            return nm
    return nm


def _yn(v, p=0.5):
    return "Yes" if v.maybe(p) else "No"


def _location(v, C):
    a = C.address(v)
    x = {"street": a["line_1"], "city": a["city"], "zip": a["postal_code"], "county": a["county"]}
    x["zip9"] = "%s-%04d" % (a["postal_code"], v.integer(1, 9999))
    x["line"] = "%s, %s, NY %s" % (x["street"], x["city"], x["zip9"])
    A = v.limit(150000, 700000, 25000)
    B = C.round_to(A * 0.10, 5000)
    Cc = v.choice([5000, 10000, 15000, 20000, 25000])
    lo, lag, lprem = v.choice([(1000000, 2000000, 55), (2000000, 3000000, 77), (500000, 1000000, 42)])
    mp, ma, mprem = v.choice([(1000, 10000, 18), (2500, 25000, 26), (5000, 50000, 33)])
    ded, pct = v.choice([(1000, 0.08), (2500, 0.17), (5000, 0.25)])
    base = round(A / 1000.0 * v.rng.uniform(4.2, 4.8))
    fl10 = round(0.02 * base)
    x.update(A=A, B=B, C=Cc, D=B, lo=lo, lag=lag, lprem=lprem, mp=mp, ma=ma, mprem=mprem, ded=ded,
             base=base, cprem=round(Cc / 1000.0 * 5.1), fl10=fl10, fl42=v.choice([8, 10, 12]),
             fl52=-v.integer(1, 3), dfl=round(0.10 * base), alarm=-fl10, dedc=-round(base * pct))
    x["total"] = (x["base"] + x["cprem"] + x["lprem"] + x["mprem"] + x["fl10"] + x["fl42"] + x["fl52"]
                  + x["dfl"] + x["alarm"] + x["dedc"])
    x.update(col=v.choice(COL_FORMS), settle=v.choice(SETTLE), families=v.choice(["1 Family", "1 Family", "2 Family"]),
             constr=v.choice(CONSTR), year=v.integer(1890, 2005), zone=v.integer(1, 6),
             fire="%s Fire Department" % a["city"], hydrant=v.choice(HYDRANT), miles=v.choice(MILES),
             prot=v.choice(PROT), heating=v.choice(HEATING), fuel=v.choice(FUELS),
             sysyear=v.integer(1998, 2025), electric=v.choice(ELECTRIC), roofyear=v.integer(1992, 2025),
             roof=v.choice(ROOFS), owned=v.integer(1, 9), water=v.choice(WATER),
             renov="Yes" if v.maybe(0.2) else "No",
             market=v.limit(A + 50000, min(A + 400000, 990000), 5000))
    x["risk"] = "%s Dwelling" % x["families"]
    for k in ("A", "B", "C", "D", "lo", "lag", "mp", "ma", "market"):
        x[k + "_s"] = _n(x[k])
    for k in ("base", "cprem", "lprem", "mprem", "fl10", "fl42", "fl52", "dfl", "alarm", "dedc", "total"):
        x[k + "_s"] = _c(x[k])
    return x


def _yesno(v, d):
    """Answers for the Yes/No questions. The X boxes are fixed, so the answer is changed by
    swapping the two words: the label beside the X'd box carries the answer."""
    a = {}
    a[2] = ["Yes" if v.maybe(0.2) else "No", "Yes", _yn(v, 0.3), _yn(v, 0.8)]
    a[6] = list(a[2])
    a[9] = ["Yes" if v.maybe(0.2) else "No"]
    for i, page in ((1, 3), (2, 7)):
        x = d["L"][i - 1]
        roof_yes = x["roofyear"] >= 2006
        rented = "Yes" if v.maybe(0.8) else "No"
        college = ("Yes" if v.maybe(0.2) else "No") if rented == "Yes" else "No"
        a[page] = ["Yes" if v.maybe(0.2) else "No", "Yes" if i == 1 else "No", "Yes" if roof_yes else "No",
                   rented, college, "Yes" if v.maybe(0.15) else "No", _yn(v, 0.4), "Yes" if v.maybe(0.1) else "No",
                   _yn(v, 0.3), _yn(v, 0.2)]
        d["l%d_rented" % i], d["l%d_seasonal" % i] = rented, a[page][5]
    d["yn"] = a
    for page, answers in a.items():
        sides = SIDES[page]
        for k, ans in enumerate(answers):
            opp = "No" if ans == "Yes" else "Yes"
            left, right = (opp, ans) if sides[k] == "R" else (ans, opp)
            d["yl_%d_%d" % (page, k)], d["yr_%d_%d" % (page, k)] = left, right


# which box carries the fixed X for each question: L = the Yes box, R = the No box
SIDES = {2: "RLRL", 6: "RLRL", 9: "R",
         3: "RLLLRRRRRR", 7: "RRLLRRRRRR"}


def draw(v, C):
    d = {}
    # people
    n1 = _name(v, C)
    n2 = _name(v, C)
    d.update(n1=n1, n2=n2, full="%s & %s" % (n1, n2), ins_email=C.email(n1, "example.com"),
             ins_phone=C.phone(v, "paren"), dob1=C.fmt(date(1950 + v.integer(0, 30), v.integer(1, 12), v.integer(1, 28))),
             dob2=C.fmt(date(1950 + v.integer(0, 30), v.integer(1, 12), v.integer(1, 28))),
             marital=v.choice(MARITAL))
    mail = C.address(v)
    d.update(mail_street=C.po_box(v), mail_city=mail["city"], mail_zip9="%s-%04d" % (mail["postal_code"], v.integer(1, 9999)))
    d["mail_line"] = "%s, NY %s" % (d["mail_city"], d["mail_zip9"])

    # agency: kept short because the source block is right aligned in a narrow slot
    head = v.choice(C.AGENCY_HEAD)
    agency = "%s %s" % (head, v.choice(["Insurance Group", "Agency Inc", "Insurance Agency"]))
    town = v.choice(AGENT_TOWNS)
    rep = _name(v, C)
    d.update(agency=agency, ag_head=head, ag_street=v.choice(AGENT_STREETS), ag_city=town, ag_zip=ZIPS[town],
             ag_line="%s, NY %s" % (town, ZIPS[town]), ag_pobox="PO Box %d" % v.integer(100, 900),
             ag_phone=C.phone(v, "paren"), agcode=str(v.integer(100, 899)),
             rep=rep, domain=head.lower().replace(" ", "") + ".com",
             prod_code="%05d" % v.integer(1000, 99999), cust_id="%08d" % v.integer(1, 99999999),
             cust_id2="%08d" % v.integer(1, 99999999))
    d["ag_phone_ns"] = d["ag_phone"].replace(") ", ")")
    d["rep_email"] = "%s%s@%s" % (rep.split()[0][0].lower(), rep.split()[1].lower(), d["domain"])
    d["svc_email"] = "beservice@%s" % d["domain"]
    d["bill"] = v.choice(["Insured Direct", "Agency Direct"])
    d["plan"] = v.choice(["Annual", "Annual", "Monthly"])
    d["billing_line"] = "%s %s New Business" % (d["bill"], d["plan"])
    d["file_no"] = "L%06d" % v.integer(100000, 999999)

    # dates: form printed, applicant signs +2, agent signs +3 (also the effective date)
    fp, _ = C.term(v, earliest=date(2023, 1, 1), latest=date(2026, 9, 1))
    eff = fp + timedelta(days=3)
    exp = C.add_months(eff, 12)
    old_eff = eff - timedelta(days=v.integer(60, 330))
    d.update(fp=C.fmt(fp), fp1=C.fmt(fp + timedelta(days=1)), s1=C.fmt(fp + timedelta(days=2)),
             eff=C.fmt(eff), exp=C.fmt(exp), eff2=C.fmt(eff, "short2"), fd=C.fmt(fp - timedelta(days=v.integer(3, 14))),
             old_eff=C.fmt(old_eff), old_exp=C.fmt(C.add_months(old_eff, 12)),
             fp_long=C.fmt(fp, "long"))
    d["fp_iso"] = fp
    d["s1_ts"] = "%s 08:04AM US/Eastern" % d["s1"]
    d["s2_ts"] = "%s 09:05AM US/Eastern" % d["eff"]

    # prior policy / other policies / prior owner
    d.update(prior_owner="%s %s %s" % (v.choice(C.GIVEN), v.choice("ABCDEFGHJKLMNPRSTW"), v.choice(C.SURNAME)),
             old_pol=str(v.integer(1000000, 9999999)),
             other_pols="HPP%08d & RFP%09d" % (v.integer(1, 99999999), v.integer(1, 999999999)),
             doc_uuid="%08x-%04x-4%03x-b%03x-%012x" % (v.rng.getrandbits(32), v.rng.getrandbits(16),
                                                      v.rng.getrandbits(12), v.rng.getrandbits(12),
                                                      v.rng.getrandbits(48)),
             ip1="%d.%d.%d.%d" % (v.integer(11, 99), v.integer(11, 250), v.integer(2, 250), v.integer(11, 250)),
             ip2="%d.%d.%d.%d" % (v.integer(11, 99), v.integer(11, 250), v.integer(2, 250), v.integer(11, 250)))
    d["explain"] = v.choice(EXPLAIN)
    d["prev_carrier"] = v.choice(PREV_CARRIERS)
    d["cond"] = v.choice(["Good", "Good", "Average", "Excellent"])

    L = [_location(v, C), _location(v, C)]
    for i, loc in enumerate(L, 1):
        for k, val in loc.items():
            d["l%d_%s" % (i, k)] = val
        d["l%d_col_full" % i], d["l%d_col_no" % i], d["l%d_col_desc" % i] = loc["col"]
        d["l%d_settle_b" % i], d["l%d_settle_c" % i] = loc["settle"]
        d["l%d_ded_s" % i] = "$ " + _n(loc["ded"])
        loc["col_full"], loc["col_no"], loc["col_desc"] = loc["col"]
        loc["ded_s"] = d["l%d_ded_s" % i]
    d["L"] = L
    d["total_all"] = L[0]["total"] + L[1]["total"]
    d["total_all_s"] = _c(d["total_all"])
    _yesno(v, d)
    return d


# -- REPLACE ---------------------------------------------------------------------------

NB = lambda s: s.replace(" ", "\xa0")


def _num(page, src, tmpl, nth=None):
    o = {"page": page, "exact": True, "leak": False}
    if nth is not None:
        o["nth"] = nth
    return (src, tmpl, o)


REPLACE = []
R = REPLACE.append

# -- names ------------------------------------------------------------------------------
R((NB("Marguerite Ellery & Noelle Norcross"), "{full}"))
R((NB("Marguerite Ellery"), "{n1}"))
R((NB("Noelle Norcross"), "{n2}"))
R(("&Noelle Norcross", "", {"exact": True, "page": 10}))
R(("Kenneth", "{full}", {"page": 10, "size": 12}))
# ACORD 35: signature overlay collides with the time stamp; shrink it
R(("Marguerite Ellery", "{n1}", {"page": 11, "size": 11}))
R(("Marguerite Ellery", "{n1}"))
R(("Noelle Delaney", "{rep}", {"page": 13, "exact": True}))  # placeholder, replaced below on 13/14
REPLACE.pop()
# certificate lines: overlay name + printed e-mail collide, so the name and e-mail are drawn together
R(("Noelle Delaney", "{rep} ({rep_email})", {"page": 13, "exact": True}))
R(("(glevi@stablerock.com)", "", {"page": 13, "exact": True}))
for k, t in enumerate(["{rep} ({rep_email}).", "{rep} ({rep_email}).", "{rep} ({rep_email}) has agreed to terms of",
                       "{rep} ({rep_email}).", "{rep} ({rep_email})."]):
    R(("Noelle Delaney", t, {"page": 14, "exact": True, "nth": k}))
R(("(glevi@stablerock.com).", "", {"page": 14, "exact": True}))
R(("(glevi@stablerock.com) has agreed to terms of", "", {"page": 14, "exact": True}))
R(("Noelle Delaney", "{rep}"))
# insured e-mail: the p13 line 'has agreed to terms of' is printed on top of the e-mail; move the words
R(("has agreed to terms of", "", {"page": 13, "exact": True}))
for k in range(6):
    R(("marguerite.ellery@example.com", "{ins_email}" + (" has agreed to terms of" if k == 4 else ""),
       {"page": 13, "nth": k}))
R(("marguerite.ellery@example.com", "{ins_email}"))
R(("glevi@stablerock.com", "{rep_email}"))
R(("beservice@stablerock.com", "{svc_email}"))

# -- carrier letterhead: static. agency block ------------------------------------------------
R(("Patriotic Insurance Group Brokerage", "{agency}", {"page": 1}))
R(("Patriotic Insurance Group Brokerage", "{agency}", {"page": 5}))
R(("Patriotic Insurance Group", "{agency}", {"page": 10}))
R(("Stable Rock Insurance Agency LLC", "{agency}", {"page": 12}))
R(("Stable Rock", "{ag_head}", {"page": 10}))
R(("159 NY-28", "{ag_street}", {"exact": True, "page": 1}))
R(("159 NY-28", "{ag_street}", {"exact": True, "page": 5}))
R(("Inlet, NY 13360", "{ag_line}", {"exact": True, "page": 1}))
R(("Inlet, NY 13360", "{ag_line}", {"exact": True, "page": 5}))
R(("159 Route 28, PO Box 329", "{ag_street}, {ag_pobox}"))
R(("Inlet, New York 13360", "{ag_city}, New York {ag_zip}"))
R(("# 760", "# {agcode}", {"exact": True, "leak": False}))
R(("(845) 610-5700", "{ag_phone}"))
R(("(315) 357-5901", "{ag_phone}"))
R(("Insured Direct Annual New Business", "{billing_line}", {"exact": True}))
R(("00006168", "{cust_id2}", {"exact": True}))

# -- policy identity and term -------------------------------------------------------------
R(("L653169", "{file_no}", {"exact": True}))
# The ACORD 35 (page 11) overlays are NimbusSans text whose real glyphs are ~26% wider than the
# extracted bbox, so the engine's redaction rectangle leaves the tail of the old text visible.
# Page 11 is therefore left as printed (STATIC); every other page is rewritten.
NO11 = [p for p in range(1, 15) if p != 11]
for src, tmpl in (("05/29/2026", "{fp}"), ("05/30/2026", "{fp1}"), ("05/31/2026", "{s1}"),
                  ("06/01/2026", "{eff}"), ("06/01/2027", "{exp}"), ("06/01/26", "{eff2}"),
                  ("May 29, 2026", "{fp_long}")):
    for pg in NO11:
        R((src, tmpl, {"leak": False, "page": pg, "optional": True}))

# -- mailing address ----------------------------------------------------------------------
R(("PO Box 236", "{mail_street}", {"exact": True}))
R(("Blue Mountain Lake, NY 12812-0236", "{mail_line}", {"exact": True}))

# -- per location: 1 = pages 1-4, 2 = pages 5-8 --------------------------------------------------
LOC_SRC = "221 State Route 28, Raquette Lake, NY 13436-1903"
for i, (p1, p2, p3, p4) in ((1, (1, 2, 3, 4)), (2, (5, 6, 7, 8))):
    t = "l%d_" % i
    for p in (p1, p2, p3, p4):
        R((LOC_SRC, "{%sline}" % t, {"page": p}))
    for p in (p1, p2, p3, p4):
        R(("1 Family Dwelling", "{%srisk}" % t, {"page": p}))
    # page 1 / 5: coverage and rating summary
    if i == 1:
        R(_num(p1, "500,000", "{l1_A_s}"))
        R(_num(p1, "50,000", "{l1_B_s}", 0))
        R(_num(p1, "10,000", "{l1_C_s}"))
        R(_num(p1, "50,000", "{l1_D_s}", 1))
        R(_num(p1, "50,000", "{l1_ma_s}", 2))
        R(_num(p1, "5,000", "{l1_mp_s}"))
        R(_num(p1, "1", "{l1_zone}", 1))
        R(("1959", "{l1_year}", {"page": p1, "exact": True, "leak": False}))
        R(_num(p1, "2,209.00", "{l1_total_s}"))
        R(("$3,632.00", "${total_all_s}", {"page": p1, "leak": False}))
    else:
        R(_num(p1, "300,000", "{l2_A_s}"))
        R(_num(p1, "30,000", "{l2_B_s}", 0))
        R(_num(p1, "10,000", "{l2_C_s}"))
        R(_num(p1, "30,000", "{l2_D_s}", 1))
        R(_num(p1, "50,000", "{l2_ma_s}"))
        R(_num(p1, "5,000", "{l2_mp_s}"))
        R(_num(p1, "1", "{l2_zone}"))
        R(("1950", "{l2_year}", {"page": p1, "exact": True, "leak": False}))
        R(_num(p1, "1,423.00", "{l2_total_s}"))
        R(("$3,632.00", "${total_all_s}", {"page": p1, "leak": False}))
    R(_num(p1, "2,000,000", "{%slo_s}" % t))
    R(_num(p1, "3,000,000", "{%slag_s}" % t))
    R(("FL-3 (Special)", "{%scol_full}" % t, {"page": p1, "exact": True}))
    R(("$ 2,500", "{%sded_s}" % t, {"page": p1, "exact": True, "leak": False}))
    R(("Replacement Cost", "{%ssettle_b}" % t, {"page": p1, "exact": True}))
    R(("Replacement Cost Contents", "{%ssettle_c}" % t, {"page": p1}))
    R(("1 Family", "{%sfamilies}" % t, {"page": p1, "exact": True}))
    R(("Frame", "{%sconstr}" % t, {"page": p1, "exact": True}))
    R(("No", "{%srenov}" % t, {"page": p1, "exact": True, "leak": False}))
    R(("Raquette Lake Fire Department", "{%sfire}" % t, {"page": p1, "exact": True}))
    R(("Greater than 1000 Feet", "{%shydrant}" % t, {"page": p1, "exact": True}))
    R(("Hamilton", "{%scounty}" % t, {"page": p1, "exact": True}))
    R(("Semi-Protected", "{%sprot}" % t, {"page": p1, "exact": True}))
    R(("5 Miles or Less", "{%smiles}" % t, {"page": p1, "exact": True}))
    # premium schedule (page 4 / 8)
    base_src = {1: ("500,000", "2,194.00", "10,000", "51.00", "44.00", "-44.00", "219.00", "-373.00", "2,209.00",
                    "50,000"),
                2: ("300,000", "1,348.00", "10,000", "51.00", "27.00", "-27.00", "135.00", "-229.00", "1,423.00",
                    "50,000")}[i]
    (s_a, s_base, s_c, s_cp, s_fl10, s_alarm, s_dfl, s_dedc, s_total, s_acc) = base_src
    R(_num(p4, s_a, "{%sA_s}" % t))
    R(_num(p4, s_base, "{%sbase_s}" % t))
    R(_num(p4, s_c, "{%sC_s}" % t))
    R(_num(p4, s_cp, "{%scprem_s}" % t))
    R(_num(p4, "2,000,000", "{%slo_s}" % t))
    R(_num(p4, "3,000,000", "{%slag_s}" % t))
    R(_num(p4, "77.00", "{%slprem_s}" % t))
    R(_num(p4, "5,000", "{%smp_s}" % t))
    R(_num(p4, s_acc, "{%sma_s}" % t))
    R(_num(p4, "33.00", "{%smprem_s}" % t))
    R(_num(p4, s_fl10, "{%sfl10_s}" % t))
    R(_num(p4, "10.00", "{%sfl42_s}" % t))
    R(_num(p4, "-2.00", "{%sfl52_s}" % t))
    R(_num(p4, s_dfl, "{%sdfl_s}" % t))
    R(_num(p4, s_alarm, "{%salarm_s}" % t))
    R(_num(p4, s_dedc, "{%sdedc_s}" % t))
    R(_num(p4, s_total, "{%stotal_s}" % t))
    R(("FL-3", "{%scol_no}" % t, {"page": p4, "exact": True}))
    R(("Causes of Loss (Special Perils)", "Causes of Loss ({%scol_desc})" % t, {"page": p4, "exact": True}))

    # questions page (2/6 and 3/7)
    for src, tmpl in (("Marguerite Ellery", None),):
        pass
    R(("(808)\xa0555\xad1831", "{ins_phone}", {"page": p2, "exact": True}))
    R(("NYCM", "{prev_carrier}", {"page": p2, "exact": True, "leak": False}))
    R(("Good", "{cond}", {"page": p2, "exact": True, "leak": False}))
    R(("HPP00120326 & RFP000080503", "{other_pols}", {"page": p2, "exact": True}))
    R(("11/05/1969", "{dob1}", {"page": p3, "exact": True, "leak": False}))
    R(("08/03/1971", "{dob2}", {"page": p3, "exact": True, "leak": False}))
    R(("Married", "{marital}", {"page": p3, "exact": True}))
    R(("Hot Water Boiler", "{%sheating}" % t, {"page": p3, "exact": True}))
    R(("Metal/Steel", "{%sroof}" % t, {"page": p3, "exact": True}))
    R(("Circuit Breakers", "{%selectric}" % t, {"page": p3, "exact": True}))
    R(("$ 800,000", "$ {%smarket_s}" % t, {"page": p3, "exact": True, "leak": False}))
    R(("1", "{%sowned}" % t, {"page": p3, "exact": True, "leak": False}))
    if i == 1:
        R(("Oil", "{l1_fuel}", {"page": p3, "exact": True}))
        R(("2009", "{l1_sysyear}", {"page": p3, "exact": True, "leak": False}))
        R(("2025", "{l1_roofyear}", {"page": p3, "exact": True, "leak": False}))
        R(("fireplace", "{explain}", {"page": p3, "exact": True}))
        R(("Lake / River Frontage", "{l1_water}", {"page": p3, "exact": True}))
    else:
        R(("Propane", "{l2_fuel}", {"page": p3, "exact": True}))
        R(("2025", "{l2_sysyear}", {"page": p3, "exact": True, "leak": False}))
        R(("2012", "{l2_roofyear}", {"page": p3, "exact": True, "leak": False}))
        R(("Lake / River Frontage", "{l2_water}", {"page": p3, "exact": True}))

for page, sides in SIDES.items():
    for k in range(len(sides)):
        R(("Yes", "{yl_%d_%d}" % (page, k), {"page": page, "exact": True, "nth": k, "leak": False}))
        R(("No", "{yr_%d_%d}" % (page, k), {"page": page, "exact": True, "nth": k, "leak": False}))
# page 12: insured property
R(("221 State Route 28", "{l1_street}", {"page": 12}))
R(("Raquette Lake, NY 13436", "{l1_city}, NY {l1_zip}", {"page": 12}))
R(("518d5b0f-d56f-4579-b89e-29f4d853f9ce", "{doc_uuid}", {"leak": False}))
R(("50.108.208.163", "{ip1}", {"leak": False}))
R(("38.77.7.105", "{ip2}", {"leak": False}))

R((NB("Noelle Delaney"), "{rep}"))
# categorical values may legitimately recur (the other location, another page): no leak probe
_CAT = {"Metal/Steel", "Semi-Protected", "Circuit Breakers", "Replacement Cost", "Replacement Cost Contents",
        "Frame", "Greater than 1000 Feet", "5 Miles or Less", "Hot Water Boiler", "has agreed to terms of",
        "1 Family", "Oil", "Propane", "Married", "Lake / River Frontage", "fireplace", "FL-3 (Special)", "FL-3",
        "Hamilton", "1 Family Dwelling", "Causes of Loss (Special Perils)", "Stable Rock Insurance Agency LLC", "Stable Rock", "159 NY-28", "Inlet, NY 13360",
        "221 State Route 28", "Raquette Lake, NY 13436"}   # the last six also survive on the static page 11
REPLACE[:] = [(s, t, dict(o, leak=False) if s in _CAT else o) for s, t, o in
              [(e[0], e[1], e[2] if len(e) > 2 else {}) for e in REPLACE]]

STATIC = [
    r"^13053$", r"Dryden, New York 13053",           # carrier letterhead
    r"^14834$", r"13335",                            # prior carrier NAIC / ZIP on the ACORD 35 (carrier data)
    r"Smoke Detectors 2%", r"1\.0% per Quarter",     # rating credit and auto-increase rate
    # ACORD 35 (page 11) left as printed, see the note at NO11
    r"^\(315\)357-5901$", r"^08014$", r"^00004315$", r"^4803762$", r"^05/18/2026$", r"^06/01/2026$",
    r"^04/09/202[67]$", r"^05/31/2026 08:04AM US/Eastern$", r"Printed by GAL on May 29, 2026",
    r"^Inlet, NY 13360$", r"^Raquette Lake, NY 13436-1903$",
]


def audit(d):
    out = []
    for i, x in enumerate(d["L"], 1):
        if x["total"] != (x["base"] + x["cprem"] + x["lprem"] + x["mprem"] + x["fl10"] + x["fl42"] + x["fl52"]
                          + x["dfl"] + x["alarm"] + x["dedc"]):
            out.append("location %d schedule does not sum" % i)
    if d["total_all"] != d["L"][0]["total"] + d["L"][1]["total"]:
        out.append("total quoted premium does not sum")
    return out


def gold(d):
    return _gold(d)


def _loc_gold(d, i):
    x = d["L"][i - 1]
    mo = money
    cov = [
        {"coverage_name": fv("Coverage A – Residence"), "limit_amount": mo(x["A_s"]), "premium": mo(x["base_s"])},
        {"coverage_name": fv("Coverage B – Other Structures"), "limit_amount": mo(x["B_s"])},
        {"coverage_name": fv("Coverage C – Personal Property"), "limit_amount": mo(x["C_s"]),
         "premium": mo(x["cprem_s"])},
        {"coverage_name": fv("Coverage D – Addl.Living Exp. and Loss of Rent"), "limit_amount": mo(x["D_s"])},
        {"coverage_name": fv("Premises Liability"), "limit_amount": mo(x["lo_s"]), "limit_basis": fv("Each Occurrence"),
         "aggregate_limit_amount": mo(x["lag_s"]), "premium": mo(x["lprem_s"])},
        {"coverage_name": fv("Medical Payments"), "limit_amount": mo(x["mp_s"]), "limit_basis": fv("Each Person"),
         "sublimit_amount": mo(x["ma_s"]), "sublimit_basis": fv("Each Accident"),
         "premium": mo(x["mprem_s"])},
    ]
    return {
        "location_number": fv(str(i), i, evidence="Location Number:"),
        "address": addr(x["street"], x["city"], "NY", x["zip9"], x["county"]),
        "occupancy_description": fv(x["risk"]),
        "construction_type": fv(x["constr"]),
        "protection_class": fv(x["prot"]),
        "territory_code": fv(str(x["zone"]), evidence="Rating Zone:"),
        "year_built": fv(str(x["year"])),
        "alarm_type": fv("Smoke Detectors 2%"),
        "coverages": cov,
    }


Q3 = ["Does this property have a local caretaker other than the insured?",
      "Any Other Secondary Heating Source?",
      "Has the roof been updated in the last 20 years?",
      "Is this property currently rented?",
      "Are any tenants’ college students?",
      "Is this a seasonal rental property?",
      "Are there other structures on premises considered to be related private structures?",
      "Any Business conducted on premises (in dwelling or outbuilding)?",
      "Are there any dogs owned by the residents of the property?",
      "Are there any other animals besides dogs?"]


def _questions(d):
    """Underwriting questions (location 1's page 3 answers; page 9 loss history)."""
    a2, a3, a9 = d["yn"][2], d["yn"][3], d["yn"][9]
    q = []

    def add(text, answer, evidence=None, details=None, printed=False):
        row = {"question": fv(text, evidence=evidence),
               "answer": fv(answer) if printed else derived(answer, evidence or text)}
        if details:
            row["details"] = fv(details)
        q.append(row)

    add("Has any company cancelled, non-renewed or refused insurance (including non-payment of premium) "
        "for this applicant?", a2[0], "Has any company cancelled, non-renewed or refused insurance "
        "(including non-payment of premium)")
    add("Does Insured have other policies with Dryden Mutual?", a2[1], details=d["other_pols"])
    add("Was prior approval given from underwriting for this risk?", a2[2])
    add("Has this property been visually inspected by agency staff?", a2[3])
    add("Overall condition of the risk:", d["cond"], printed=True)
    for k, text in enumerate(Q3):
        if k == 1:
            add(text, a3[k], details=d["explain"])
        elif k == 2:
            add(text, a3[k], details=str(d["L"][0]["roofyear"]))
        else:
            add(text, a3[k])
        if k == 6:
            add("Any Water Exposures?", d["L"][0]["water"], printed=True)
    add("Any previous property or liability losses, whether or not paid by insurance during the last 5 years, "
        "on any owned or previously owned risk in which you have or had an insured interest?", a9[0],
        "Any previous property or liability losses, whether or not paid by insurance during the last 5 years, "
        "on any owned or")
    return q


IGNORE_PAIRS = [
    r"^Secondary Phone: Mobile Home Business Other$",       # unchecked phone-type options, no number printed
    r"^Check any exposures that apply: .*Diving Board$",     # unchecked exposure options (every box is empty)
    r"^(Signature of Applicant|Date): .*_{3,}",              # blank signature / date rule lines
    r"^SUB CODE: POLICY TYPE$",                              # ACORD 35 label with no value (adjacent caption)
]


def _additional(d):
    """Printed 'Label: value' pairs with no dedicated leaf: location 2's rating criteria and answers
    (dwelling_fire.dwelling holds location 1 only) and the ACORD 35 / certificate header fields."""
    x = d["L"][1]
    out = []

    def add(section, label, value, evidence=None):
        out.append(extra(label, value, section=section, evidence=evidence))

    sec = "Location 2 - Rating Criteria"
    add(sec, "Risk Description", x["risk"])
    add(sec, "Type", "Standard", "Type:")
    add(sec, "Cause of Loss Form", x["col_full"])
    add(sec, "Deductible", x["ded_s"])
    add(sec, "Families", x["families"])
    add(sec, "Loss Settlement Building", x["settle"][0])
    add(sec, "Loss Settlement Contents", x["settle"][1])
    add(sec, "Construction", x["constr"])
    add(sec, "Year of Construction", str(x["year"]))
    add(sec, "Rating Zone", str(x["zone"]), "Rating Zone:")
    add(sec, "County", x["county"])
    add(sec, "Fire District", x["fire"])
    add(sec, "Fire Protection", x["prot"])
    add(sec, "Feet From Hydrant", x["hydrant"])
    add(sec, "Miles From Fire Dept", x["miles"])
    add(sec, "Protective Devices", "Smoke Detectors 2%")
    add(sec, "Special Rating Conditions", "None")
    add(sec, "Renovator Credit", x["renov"], "Renovator Credit:")
    sec = "Location 2 - Building Utilities"
    add(sec, "Primary Heating Type", x["heating"])
    add(sec, "Fuel Type", x["fuel"])
    add(sec, "Year Primary System Updated", str(x["sysyear"]))
    add(sec, "Electrical Service", x["electric"])
    add(sec, "Year Roof Updated", str(x["roofyear"]))
    add(sec, "Roof Type", x["roof"])
    sec = "Location 2 - Property Questions"
    add(sec, "How many years has the applicant owned this risk?", str(x["owned"]),
        "How many years has the applicant owned this risk?")
    add(sec, "Market Value", "$ " + x["market_s"])
    add(sec, "Any Water Exposures?", x["water"])
    a7 = d["yn"][7]
    for text, ans in zip(Q3, a7):
        add("Location 2 - Property and Liability Questions", text, derived(ans, text))
    add("Regulation 194 Disclosure", "Name of Companies", fv("Dryden %s" % d["ag_head"], evidence="Dryden"))
    for i, loc in enumerate(d["L"], 1):
        add("Location %d - Coverages" % i, "Aggregate Limit", loc["lag_s"])
    sec = "ACORD 35 Cancellation Request"
    add(sec, "DATE (MM/DD/YYYY)", "05/18/2026")
    add(sec, "PHONE (A/C, No, Ext)", "(315)357-5901")
    for line in ("Stable Rock Insurance Agency LLC", "159 NY-28", "Inlet, NY 13360"):
        add(sec, "PRODUCER", line)
    for line in ("New York Central Mutual Fire Insurance Company", "1899 Central Plaza E", "Edmeston, NY 13335"):
        add(sec, "COMPANY NAME AND ADDRESS", line)
    for label in ("INSURED NAME AND ADDRESS", "NAME AND ADDRESS"):
        for line in ("Carol B Mitchell", "221 State Route 28", "Raquette Lake, NY 13436-1903"):
            add(sec, label, line)
    add(sec, "POLICY TYPE", "Homeowners: Personal")
    add(sec, "POLICY NUMBER", "4803762")
    add(sec, "CANCELLATION DATE", "06/01/2026")
    add(sec, "TIME", "12:01")
    add(sec, "EFFECTIVE DATE", "04/09/2026")
    add(sec, "EXPIRATION DATE", "04/09/2027")
    add(sec, "OTHER (Identify)", "Insured deceased")
    add(sec, "SIGNATURE OF NAMED INSURED", fv("05/31/2026 08:04AM US/Eastern", evidence="08:04AM US/Eastern"))
    add("ACORD 60 Flood Selection / Rejection", "DATE (MM/DD/YYYY)", d["fp"])
    add("ACORD 60 Flood Selection / Rejection", "EFFECTIVE DATE", d["eff2"])
    hist = "E-Signature Certificate - Document History"
    for stamp, label in ((d["fp"] + " 03:31PM", "Sender downloaded document."),
                         (d["fp"] + " 03:36PM", "Sender downloaded document."),
                         (d["fp"] + " 03:37PM", "Document sent by"),
                         (d["fp"] + " 03:37PM", "Email sent to"),
                         (d["fp1"] + " 12:31PM", "Email sent to"),
                         (d["s1"] + " 08:00AM", "Document viewed by"),
                         (d["s1"] + " 08:04AM", "Signed by"),
                         (d["s1"] + " 08:04AM", "Email sent to"),
                         (d["eff"] + " 09:04AM", "Document viewed by"),
                         (d["eff"] + " 09:05AM", "Signed by"),
                         (d["eff"] + " 09:05AM", "Document copy sent to")):
        add(hist, label, stamp)
    sec = "ACORD 35 Cancellation Request"
    add(sec, "CODE", "08014")
    add(sec, "NAIC CODE", "14834")
    add(sec, "AGENCY CUSTOMER ID", "00004315")
    add("ACORD 60 Flood Selection / Rejection", "AGENCY CUSTOMER ID", d["cust_id2"])
    sec = "E-Signature Certificate"
    add(sec, "Document Reference", d["doc_uuid"])
    add(sec, "Document Title", "Landlord Application/Cancellation Form")
    add(sec, "Document Region", "Northern Virginia")
    add(sec, "Sender Name", "No Name")
    add(sec, "Sender Email", d["svc_email"])
    add(sec, "Total Document Pages", "12")
    add(sec, "Secondary Security", "Not Required")
    return out


def _gold(d):
    L1 = d["L"][0]
    mo = money
    named = d["full"]

    forms = [{"form_number": fv("GL"), "edition_date": date_fv(d["fp"]),
              "form_title": fv("Standard Landlords Package Policy")},
             {"form_number": fv("ACORD 35"), "edition_date": fv("2017/05"),
              "form_title": fv("CANCELLATION REQUEST / POLICY RELEASE")},
             {"form_number": fv("ACORD 60"), "edition_date": fv("2010/04"),
              "form_title": fv("FLOOD INSURANCE SELECTION / REJECTION")}]
    credits = []
    for i, x in enumerate(d["L"], 1):
        where = derived("Location %d" % i, "Location #")
        for fn, title, key in FORMS:
            f = {"form_number": fv(x["col_no"] if fn == "FL-3" else fn),
                 "form_title": fv("Causes of Loss (%s)" % x["col_desc"] if fn == "FL-3" else title),
                 "applies_to": dict(where)}
            if key:
                f["premium"] = mo(x[key + "_s"])
            else:
                f["is_included"] = derived("Yes", "Incl")
            forms.append(f)
        credits.append({"description": fv("Premises Alarm"), "amount": mo(x["alarm_s"]),
                        "form_reference": fv("ML-216"), "applies_to": dict(where),
                        "is_applied": derived("Yes", "Smoke Detectors 2%")})
        credits.append({"description": fv("Credit or Surcharge for Coverage A - Deductible"),
                        "amount": mo(x["dedc_s"]), "applies_to": dict(where),
                        "is_applied": derived("Yes", "Deductible")})

    dwelling = {
        "described_location": addr(L1["street"], L1["city"], "NY", L1["zip9"], L1["county"]),
        "occupancy_type": fv(L1["families"]),
        "number_of_units": fv(L1["families"][0], evidence=L1["families"]),
        "tenant_occupied": derived(d["l1_rented"], "Is this property currently rented?"),
        "seasonal_or_vacant": derived(d["l1_seasonal"], "Is this a seasonal rental property?"),
        "construction_type": fv(L1["constr"]),
        "year_built": fv(str(L1["year"])),
        "roof_type": fv(L1["roof"]),
        "heating_type": fv(L1["heating"]),
        "protection_class": fv(L1["prot"]),
        "territory_code": fv(str(L1["zone"]), evidence="Rating Zone:"),
        "distance_to_hydrant": fv(L1["hydrant"]),
        "solid_fuel_burning_device_present": derived("Yes" if d["explain"] in SOLID_FUEL else "No", d["explain"]),
        "rating_type": fv("Standard", evidence="Type:"),
        "rating_zone": fv(str(L1["zone"]), evidence="Rating Zone:"),
        "renovator_credit": fv(L1["renov"], evidence="Renovator Credit:"),
        "fire_district": fv(L1["fire"]),
        "miles_to_fire_department": fv(L1["miles"]),
        "feet_to_hydrant": fv(L1["hydrant"]),
        "special_rating_conditions": fv("None"),
        "structure_description": fv(L1["risk"]),
        "fire_alarm_type": fv("Smoke Detectors 2%"),
        "electrical_service": fv(L1["electric"]),
        "fuel_type": fv(L1["fuel"]),
        "secondary_heating": fv(d["explain"]),
        "year_roof_updated": fv(str(L1["roofyear"])),
        "year_primary_system_updated": fv(str(L1["sysyear"])),
        "market_value": mo("$ " + L1["market_s"]),
        "years_owned": fv(str(L1["owned"])),
    }
    optional = [{"coverage_name": fv(item), "form_reference": derived("DFL-153P", "DFL-153P"),
                 "is_included": derived("Yes", item)} for item in DFL_ITEMS]
    optional += [
        {"coverage_name": fv("Auto Increase in Insurance"), "form_reference": fv("FL-10"),
         "limit_basis": fv("1.0% per Quarter"), "is_included": derived("Yes", "Auto Increase in Insurance")},
        {"coverage_name": fv("Building Theft Coverage"), "form_reference": fv("FL-42"),
         "is_included": derived("Yes", "Building Theft Coverage")},
        {"coverage_name": fv("Trampoline Exclusion"), "form_reference": fv("FL-52A"),
         "is_excluded": derived("Yes", "Trampoline Exclusion")},
        {"coverage_name": fv("Premises Alarm"), "form_reference": fv("ML-216"),
         "is_included": derived("Yes", "Premises Alarm")},
    ]

    return {
        "document": {
            "document_type": fv("Application"),
            "document_title_as_stated": fv("Standard Landlords Package Policy"),
            "line_of_business_as_stated": fv("Standard Landlords Package Policy"),
            "transaction_type": fv("New Business"),
            "transaction_effective_date": date_fv(d["eff"]),
            "print_date": date_fv(d["fp_long"], "%B %d, %Y"),
            "coverage_parts_present": [fv("Property Coverages"), fv("Liability Coverages")],
            "applicable_coverages": [fv("Coverage A – Residence"), fv("Coverage B – Other Structures"),
                                     fv("Coverage C – Personal Property"),
                                     fv("Coverage D – Addl.Living Exp. and Loss of Rent"),
                                     fv("Premises Liability"), fv("Medical Payments")],
        },
        "carrier": {
            "company_name": fv("Dryden Mutual Insurance Company"),
            "company_structure": fv("A New York State Advance Premium Co-Operative Fire Insurance Corporation"),
            "address": {"line_1": fv(CARRIER_ADDR), "line_2": fv("P.O. Box 635"), "city": fv("Dryden"),
                        "state": fv("NY", evidence="New York"), "postal_code": fv("13053")},
            "state_of_issue": derived("NY", "Dryden, New York 13053"),
        },
        "producer": {
            "agency_name": fv(d["agency"]),
            "producer_code": fv(d["agcode"], evidence="# %s" % d["agcode"]),
            "producer_contact_name": fv(d["rep"]),
            "address": addr(d["ag_street"], d["ag_city"], "NY", d["ag_zip"]),
            "contact": {"phone": fv(d["ag_phone"]), "email": fv(d["rep_email"])},
        },
        "policy": {
            "alternate_policy_identifiers": [
                {"identifier_type": fv("File #", evidence="File #:"), "identifier_value": fv(d["file_no"])},
                {"identifier_type": derived("Other Dryden Mutual policy", "Please provide Policy Number(s):"),
                 "identifier_value": fv(d["other_pols"].split(" & ")[0])},
                {"identifier_type": derived("Other Dryden Mutual policy", "Please provide Policy Number(s):"),
                 "identifier_value": fv(d["other_pols"].split(" & ")[1])},
            ],
            "prior_policy_number": fv("4803762"),
            "previous_carrier_name": fv(d["prev_carrier"]),
            "previous_policy_expiration_date": date_fv(d["eff"]),
            "total_number_of_risks": fv("2", evidence="Total Number of Risks:"),
            "policy_type": fv("Standard Landlords Package Policy"),
            "plan_type": fv("Advance Premium Co-Operative"),
            "effective_date": date_fv(d["eff"]),
            "expiration_date": date_fv(d["exp"]),
            "effective_time": fv("12:01am"),
            "time_zone": fv("Standard Time"),
            "policy_term_months": derived("12", d["eff"], 12),
            "is_renewal": derived("No", "New Business"),
        },
        "named_insured": {
            "primary_name": fv(named),
            "entity_type": derived("Individual", "Named Insured and Mailing Address"),
            "mailing_address": addr(d["mail_street"], d["mail_city"], "NY", d["mail_zip9"]),
            "contact": {"phone": fv(d["ins_phone"]), "email": fv(d["ins_email"])},
            "date_of_birth": fv(d["dob1"]),
            "marital_status": fv(d["marital"]),
            "additional_named_insureds": [{"name": fv(d["n2"]), "entity_type": derived("Individual", d["n2"]),
                                           "date_of_birth": fv(d["dob2"])}],
        },
        "underwriting_questions": _questions(d),
        "additional_fields": _additional(d),
        "locations": [_loc_gold(d, 1), _loc_gold(d, 2)],
        "premium": {
            "total_policy_premium": mo("$" + d["total_all_s"]),
            "premium_by_coverage_part": [
                {"coverage_part": derived("Location %d" % i, "Total Annual Premium for Location #"),
                 "premium": mo(x["total_s"])} for i, x in enumerate(d["L"], 1)],
            "taxes_and_fees": [{"description": fv("New York State Fire Surcharge"), "amount": mo("0.00")}],
            "discounts_and_credits": credits,
        },
        "billing": {
            "bill_to_party": fv(d["bill"]),
            "payment_plan": fv(d["plan"]),
            "payment_frequency": derived(d["plan"], d["plan"]),
        },
        "forms_and_endorsements": forms,
        "deductibles": [
            {"applies_to": fv("Coverage A - Deductible"), "deductible_type": derived("All Other Perils", "Deductible:"),
             "amount": mo(x["ded_s"])} for x in d["L"]],
        "state_notices": [
            {"notice_title": fv("DISCLOSURE PURSUANT TO NEW YORK INSURANCE DEPARTMENT REGULATION 194",
                                evidence="REGULATION 194"),
             "state": derived("NY", "New York"), "form_reference": fv("REGULATION 194")},
            {"notice_title": fv("INSURANCE FRAUD WARNING NOTICE"), "state": derived("NY", "New York")},
            {"notice_title": fv("FAIR CREDIT REPORTING ACT NOTICE")},
        ],
        "signature": {
            "authorized_representative_name": fv(d["n1"]),
            "signature_date": date_fv(d["s1_ts"], "%m/%d/%Y %I:%M%p US/Eastern"),
            "countersignature_date": date_fv(d["s2_ts"], "%m/%d/%Y %I:%M%p US/Eastern"),
        },
        "dwelling_fire": {
            "dwelling": dwelling,
            "property_coverages": {
                "coverage_a_dwelling_limit": mo(L1["A_s"]),
                "coverage_b_other_structures_limit": mo(L1["B_s"]),
                "coverage_c_personal_property_limit": mo(L1["C_s"]),
                "coverage_e_additional_living_expense_limit": mo(L1["D_s"]),
                "loss_settlement_basis": fv(L1["settle"][0]),
                "loss_settlement_contents": fv(L1["settle"][1]),
                "covered_causes_of_loss": fv(L1["col"][0]),
            },
            "liability_coverages": {
                "liability_coverage_form": fv("Premises Liability Coverage"),
                "coverage_l_premises_liability_limit": mo(L1["lo_s"]),
                "coverage_m_medical_payments_per_person_limit": mo(L1["mp_s"]),
                "coverage_m_medical_payments_per_occurrence_limit": mo(L1["ma_s"]),
            },
            "deductibles": {"all_other_perils_deductible": mo(L1["ded_s"])},
            "optional_endorsement_coverages": optional,
        },
    }
