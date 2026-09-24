"""
Shared pieces for the two North Country Insurance Company "Fire Policy
Declaration" profiles (policy_1 and policy_2). Not a profile itself (no SOURCE).
"""

import re

from .. import engine
from ..engine import addr, amt, date_fv, derived, extra, fv, money

# --- workaround for a MuPDF redaction-filter bug ---------------------------------------
# The North Country sources set "9.2 TL" and show every line with the ' operator. MuPDF's
# redaction filter rewrites those as "TD ... T*", and because TD changes the leading, the
# T* that follows lands on the wrong baseline: every surviving line of the page jumps.
# Before the engine redacts one of these pages, ' is replaced by the equivalent
# "0 -TL Td (text) Tj" (same glyph positions, no leading involved). Pages of other
# sources are left untouched.
_QUOTE_OP = re.compile(rb"(\((?:\\.|[^\\)])*\))'")
_TL = re.compile(rb"([\d.]+)\s+TL")
_BOTH = re.compile(rb"([\d.]+)\s+TL|(\((?:\\.|[^\\)])*\))'")


def _fix_quote_ops(page):
    doc = page.parent
    if "north_country_insurance_company_dfire_policy" not in (doc.name or "").replace("\\", "/"):
        return
    xrefs = page.get_contents()
    if len(xrefs) != 1:
        return
    data = doc.xref_stream(xrefs[0])
    if b"'" not in data or not _TL.search(data):
        return
    leading = [b"0"]

    def sub(m):
        if m.group(1) is not None:          # "<n> TL" - remember it
            leading[0] = m.group(1)
            return m.group(0)
        return b"0 -" + leading[0] + b" Td " + m.group(2) + b" Tj"

    new = _BOTH.sub(sub, data)
    doc.update_stream(xrefs[0], new)


if not getattr(engine, "_ncic_patched", False):
    _orig_apply = engine._apply

    def _apply_fixed(page, edits, page_spans, problems):
        if edits:
            _fix_quote_ops(page)
        return _orig_apply(page, edits, page_spans, problems)

    engine._apply = _apply_fixed
    engine._ncic_patched = True

# FIPS county numbers; the declaration prints them as "00043-Herkimer"
FIPS = {"Herkimer": "043", "Oneida": "065", "Lewis": "049", "Jefferson": "045",
        "St. Lawrence": "089", "Franklin": "033", "Essex": "031", "Clinton": "019",
        "Hamilton": "041", "Fulton": "035", "Warren": "113", "Oswego": "075",
        "Otsego": "077", "Madison": "053"}

FL_TOWNS = [("NEW SMYRNA BEACH", "FL", "32168"), ("NAPLES", "FL", "34102"),
            ("SARASOTA", "FL", "34236"), ("FORT MYERS", "FL", "33901"),
            ("VENICE", "FL", "34285"), ("PUNTA GORDA", "FL", "33950"),
            ("VERO BEACH", "FL", "32960"), ("OCALA", "FL", "34470"),
            ("BRADENTON", "FL", "34205"), ("MYRTLE BEACH", "SC", "29577"),
            ("HILTON HEAD ISLAND", "SC", "29926"), ("SCOTTSDALE", "AZ", "85251")]

DISCLAIMER_LIMITS = "Limits and deductibles stated above are not in addition to those on specific forms."


def keep_entries(source, replace, skip_fonts=()):
    """Identity entries for every static span of the source.

    The redaction step deletes any glyph that overlaps an edited box, and these
    declarations pack their rows 10 pt apart, so an edit also wipes the label
    above or below it. Redrawing each static span (same text, same place) puts
    them back. Spans that look variable are NOT kept: they must be handled
    (replaced or declared STATIC) on purpose.
    """
    import fitz
    from pathlib import Path
    from ...generator import _base14
    root = Path(__file__).resolve().parents[3] / "Data" / "original data"
    doc = fitz.open(str(root / source))
    seen, out, skipped = set(), [], set()
    for page in doc:
        spans = [s for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])
                 for s in l["spans"] if s["text"].strip()]
        for span in spans:
            raw, text = span["text"], span["text"].strip()
            if not text or span["font"] in skip_fonts:
                continue
            if raw[:1].isspace() or any(ord(ch) > 127 for ch in text):
                skipped.add(text)
                continue
            if text in seen or engine._VARIABLE.search(text) or "{" in text or "}" in text:
                continue
            # justified text (word spacing) cannot be redrawn as plain text
            natural = fitz.get_text_length(text, fontname=_base14(span["font"]), fontsize=span["size"])
            if abs(natural - (span["bbox"][2] - span["bbox"][0])) > 4 + 0.03 * natural:
                skipped.add(text)
                continue
            # a neighbour holding a no-break space or a non-Latin-1 character would be redrawn
            # by the engine and come out garbled
            bad = False
            for o in spans:
                if o is span or abs(o["origin"][1] - span["origin"][1]) > 2:
                    continue
                touching = abs(o["bbox"][0] - span["bbox"][2]) < 3 or abs(span["bbox"][0] - o["bbox"][2]) < 3
                if touching and any(ord(ch) > 127 for ch in o["text"]):
                    bad = True
            if bad:
                skipped.add(text)
                continue
            seen.add(text)
            out.append((text, (lambda d, t=text: t), {"exact": True, "leak": False}))
    doc.close()
    return [e for e in out if e[0] not in skipped]


def property_town(v, C):
    while True:
        t = C.town(v)
        if t[2] in FIPS:
            return t


def county_text(county):
    return "00%s-%s" % (FIPS[county], county)


def paren_phone(v, C):
    return C.phone(v, "paren").replace(") ", ")")


def agency(v, C, kind):
    """Agency block: number, name, street, city line, phone, e-mail."""
    town = C.town(v)
    name = C.agency(v).upper()
    if kind == 1 and v.maybe(0.5):
        name += ","
    words = re.sub(r"[^a-z ]", "", name.lower()).split()
    domain = "".join(words[:2]) + v.choice(["insurance", "agency", "ins"]) + ".com"
    street = "PO BOX %d" % v.integer(12, 990) if v.maybe(0.5) else C.street(v).upper()
    return {"ag_code": "%03d" % v.integer(100, 999), "ag_name": name,
            "ag_street": street, "ag_city": town[0].upper(), "ag_zip": town[1],
            "ag_line": "%s, NY %s" % (town[0].upper(), town[1]),
            "ag_phone": paren_phone(v, C),
            "ag_email": "%s@%s" % (v.choice(["agency", "service", "info", "policies"]), domain)}


def term(v, C):
    months = v.choice([12, 36, 36])
    eff, exp = C.term(v, months)
    proc = C.before(v, eff, 0, 7)
    return {"months": months, "eff_d": eff, "eff": C.fmt(eff), "exp": C.fmt(exp),
            "proc": C.fmt(proc), "proc_d": proc}


def characteristics(v, C, d):
    town = property_town(v, C)
    d.update(prop_street=C.street(v), prop_city=town[0], prop_zip=town[1], prop_county=town[2])
    d["prop_line"] = "%s %s, NY %s" % (d["prop_street"], town[0], town[1])
    d.update(county_line=county_text(town[2]), county_code="00%s" % FIPS[town[2]],
             zone="Zone %d, Sub-Zone %d" % (v.integer(1, 3), v.integer(1, 9)),
             protect=v.choice(["Protected", "Semi-Protected", "Unprotected"]),
             constr=v.choice(["Frame", "Masonry", "Masonry Veneer", "Frame"]),
             year=str(v.integer(1900, 2018)), families=v.choice(["1 Family", "1 Family", "2 Family"]),
             burglar=v.choice(["None", "None", "Central Station", "Local Alarm"]),
             fire_alarm=v.choice(["Smoke Alarm/Detector", "Smoke Alarm/Detector", "None", "Central Station"]),
             sprink=v.choice(["None", "None", "Full"]),
             settle=v.choice(["Replacement Cost", "Actual Cash Value"]))
    ded = v.choice([500, 1000, 1000, 2500])
    d["structure"] = v.choice(["Main Residence", "Main Residence", "Cottage", "Guest House"])
    d.update(ded=ded, ded_p1="$%d" % ded, ded_p2="${:,}".format(ded))
    return d


def parse_form(text):
    m = re.match(r"^(\S+) (\d{4})-(.*)$", text)
    return m.group(1), m.group(2), m.group(3)


def base_gold(d, forms, loc_cov, deductible_rows, kind):
    """The parts of the gold both declarations share. ``forms`` is
    [(printed text, premium FieldValue, applies_to or None)]."""
    eff, exp, proc = d["eff"], d["exp"], d["proc"]
    prop = addr(d["prop_street"], d["prop_city"], "NY", d["prop_zip"], county=d["prop_county"])
    prop["county_code"] = fv(d["county_code"], evidence=d["county_line"])
    prop["county"] = fv(d["prop_county"], evidence=d["county_line"])

    gold = {
        "document": {
            "document_type": derived("Declaration", "Fire Policy Declaration"),
            "document_title_as_stated": fv("Fire Policy Declaration"),
            "line_of_business_as_stated": fv("Fire Policy", evidence="Fire Policy Declaration"),
            "transaction_type": fv("New Business"),
            "transaction_effective_date": date_fv(eff),
            "issue_date": date_fv(proc),
            "copy_type": fv("Agent Copy"),
            "page_count": fv("2", 2, evidence="Page 1 of 2"),
        },
        "carrier": {
            "company_name": fv("North Country Insurance Company"),
            "address": addr("21170 NYS Route 232", "Watertown", "NY", "13601", line_2="PO Box 6540"),
            "state_of_issue": derived("NY", "Watertown, NY 13601"),
        },
        "producer": {
            "agency_name": fv(d["ag_name"]),
            "producer_code": fv(d["ag_code"]),
            "address": addr(d["ag_street"], d["ag_city"], "NY", d["ag_zip"]),
            "contact": {"phone": fv(d["ag_phone"]), "email": fv(d["ag_email"])},
        },
        "policy": {
            "policy_number": fv(d["pol"]),
            "plan_type": fv("CO-OPERATIVE PLAN"),
            "is_assessable": derived("No", "NON-ASSESSABLE"),
            "policy_form_number": fv("NCIC"),
            "policy_form_edition": fv("07/14"),
            "policy_type": derived("Dwelling Fire", "Fire Policy Declaration"),
            "effective_date": date_fv(eff),
            "expiration_date": fv(exp + " 12:01 A.M.", date_fv(exp)["parsed"], evidence=exp + " 12:01 A.M."),
            "expiration_time": fv("12:01 A.M."),
            "policyholder_since_date": date_fv(eff),
            "policy_term_months": derived(str(d["months"]), eff, d["months"]),
            "is_renewal": derived("No", "New Business"),
        },
        "locations": [{
            "location_number": fv("1", 1, evidence="Location 1:"),
            "address": prop,
            "building_number": fv("1", 1, evidence="Loc 1/Bldg 1"),
            "building_description": fv(d["descr"]),
            "occupancy_description": fv(d["occ"]),
            "construction_type": fv(d["constr"]),
            "protection_class": fv(d["protect"]),
            "territory_code": fv(d["zone"]),
            "year_built": fv(d["year"]),
            "alarm_type": fv(d["burglar"]),
            "sprinklered": fv(d["sprink"]),
            "coverages": loc_cov,
        }],
        "premium": {
            "basic_premium": amt(d["basic"]),
            "forms_and_endorsements_premium": amt(d["forms_total"]),
            "total_policy_premium": amt(d["total"]),
            "premium_by_coverage_part": [
                {"coverage_part": fv(name), "premium": amt(p)} for name, p in d["cov_premiums"]],
        },
        "forms_and_endorsements": [],
        "additional_fields": [
            extra("County", d["county_line"], section="Property Characteristics"),
            extra("# of Families", d["families"], section="Property Characteristics"),
        ],
        "deductibles": deductible_rows,
        "dwelling_fire": {
            "dwelling": {
                "described_location": dict(prop),
                "occupancy_type": fv(d["occ"]),
                "tenant_occupied": derived("Yes" if d["occ"] == "Tenant Occupied" else "No", d["occ"]),
                "construction_type": fv(d["constr"]),
                "protection_class": fv(d["protect"]),
                "territory_code": fv(d["zone"]),
                "year_built": fv(d["year"]),
                "structure_description": fv(d["structure"]),
                "fire_alarm_type": fv(d["fire_alarm"]),
                "usage": fv(d["usage"]),
                "number_of_units": fv(d["families"][0], int(d["families"][0]), evidence=d["families"]),
            },
            "property_coverages": {"loss_settlement_basis": fv(d["settle"])},
            "liability_coverages": {},
            "deductibles": {"all_other_perils_deductible": money(d["ded_p2"])},
        },
    }
    if d["usage"] == "Seasonal" or "Seasonal" in d["occ"]:
        gold["dwelling_fire"]["dwelling"]["seasonal_or_vacant"] = \
            fv(d["occ"]) if "Seasonal" in d["occ"] else fv("Seasonal")
    for text, prem, applies in forms:
        num, ed, title = parse_form(text)
        row = {"form_number": fv(num), "edition_date": fv(ed), "form_title": fv(title, evidence=title),
               "premium": prem}
        if prem["raw"] == "Included":
            row["is_included"] = derived("Yes", "Included")
        if applies:
            row["applies_to"] = fv(applies)
        gold["forms_and_endorsements"].append(row)
    return gold


def cov_rows(items):
    """items: [(name, limit FieldValue|None, deductible FieldValue|None, premium amount, extras)]"""
    rows = []
    for name, limit, ded, prem, extra in items:
        row = {"coverage_name": fv(name)}
        if prem is not None:
            row["premium"] = amt(prem)
        if limit is not None:
            row["limit_amount"] = limit
        if ded is not None:
            row["deductible_amount"] = ded
        if name[:3] == "Cov" and name[4] in "ABCD":
            row["applies_to"] = fv("Loc 1/Bldg 1")
        row.update(extra)
        rows.append(row)
    return rows
