"""Vary the figures the generic engine leaves alone, on one Progressive layout.

`fideon_synth` replaces everything that identifies someone - names, addresses,
policy numbers, VINs, phones, dates - but keeps every amount as printed,
because rescaling a schedule rounds its parts away from its total. So every
synthetic twin of a document carries the source's exact premiums, limits,
deductibles, ages and vehicle, and ten "variations" differ only in who and
when.

This pass fixes that for the Progressive motorcycle/off-road renewal layout
(`Data/POLICIES-FINAL/Progressive/autop/progressive_autop.pdf`). It does not
scale anything. It draws a NEW, internally consistent policy and derives every
dependent figure from it, so the arithmetic is exact by construction:

    7 coverage premiums           -> 12-month premium T = their sum
    paid-in-full discount D       -> pay-in-full total  T - D
    installment fee F             -> each of 4 installments (T + 4F) / 4,
                                     installment plan total  T + 4F

Limits move between real limit tiers (BI/SUM pairs stay ordered), deductibles
and the accessory limit between real options. NY's statutory no-fault figures
($50,000 PIP, $2,000 work loss, $25/day, $2,000 death) are law, not a choice,
and stay. Every varied value differs from the source's.

Each value is redrawn in place - the old glyphs removed from the text layer,
not painted over, so no extractor can read the source figure underneath - and
the gold JSON is rewritten from the same drawn model, then its page references
re-measured off the saved PDF.

The layout is checked before anything is touched: if any anchor this pass
expects is missing, it reports a problem and leaves the file alone rather than
half-editing a document it does not recognise.
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime
from pathlib import Path

import pymupdf

from fideon_synth import pageref
from fideon_synth.fields import as_number, derived, fv, walk_indexed

# ── the source's values (identical in every twin: the engine keeps them) ─────

COVERAGES = [  # row label, coverage key, source premium text
    ("Bodily Injury Liability", "bi", "$33"),
    ("Property Damage Liability", "pd", "18"),
    ("Mandatory Pedestrian Personal Injury Protection", "pip", "2"),
    ("Supplementary Uninsured/Underinsured Motorist", "sum", "4"),
    ("Medical Payments", "med", "2"),
    ("Comprehensive", "comp", "35"),
    ("Collision", "coll", "47"),
]
SRC = dict(bi=("$250,000", "$500,000"), pd="$100,000", med="$1,000", comp_ded="$500",
           coll_ded="$500", accessory="$3,000", total=141, disc=16, fee=5.00,
           mp=7, cf=3, ho=42, tier="Ultra Preferred D", since="2017",
           vehicle=("2017", "POLARIS", "RANGER 900", "875"), ages=("64", "32"))

BI_TIERS = [("$25,000", "$50,000"), ("$50,000", "$100,000"), ("$100,000", "$300,000"),
            ("$250,000", "$500,000"), ("$500,000", "$1,000,000")]
PD_TIERS = ["$25,000", "$50,000", "$100,000", "$250,000"]
MED_TIERS = ["$500", "$1,000", "$2,500", "$5,000"]
DED_TIERS = ["$250", "$500", "$1,000"]
ACCESSORY_TIERS = ["$1,000", "$3,000", "$5,000"]
FEES = [3.00, 4.00, 5.00, 6.00]
TIERS = ["Ultra Preferred A", "Ultra Preferred B", "Ultra Preferred C", "Ultra Preferred D",
         "Preferred A", "Preferred B", "Standard C"]
VEHICLES = [  # make, model, engine cc - motorcycle / off-road units Progressive writes
    ("POLARIS", "RANGER 900", "875"), ("POLARIS", "GENERAL 1000", "999"),
    ("HONDA", "PIONEER 1000", "999"), ("HONDA", "TALON 1000R", "999"),
    ("CAN-AM", "DEFENDER HD9", "976"), ("YAMAHA", "WOLVERINE X2", "847"),
    ("KAWASAKI", "TERYX KRX", "999"), ("ARCTIC CAT", "PROWLER PRO", "812"),
    ("SUZUKI", "KINGQUAD 750", "722"), ("CFMOTO", "ZFORCE 950", "963"),
]


def _other(rng, options, current):
    """A random option that is not the source's."""
    return rng.choice([o for o in options if o != current])


def _money(x, cents=False):
    return f"${x:,.2f}" if cents else f"${x:,.0f}"


def draw_model(rng: random.Random, eff_year: int) -> dict:
    """A new policy whose every dependent figure is computed, never scaled."""
    while True:
        prem = {key: max(1, round(int(as_number(src)) * rng.uniform(0.5, 2.2)))
                for _, key, src in COVERAGES}
        total = sum(prem.values())
        # Widths are held so in-sentence figures fit where the old ones stood:
        # T three digits, D two, each installment two before the point.
        disc = round(total * rng.uniform(0.08, 0.13))
        fee = _other(rng, FEES, SRC["fee"])
        if (100 <= total - disc and total != SRC["total"] and 10 <= disc <= 99
                and disc != SRC["disc"] and (total + 4 * fee) / 4 < 100
                and total + 4 * fee != SRC["total"] + 4 * SRC["fee"]):   # else the installment repeats $40.25
            break
    make, model, cc = _other(rng, VEHICLES, SRC["vehicle"][1:])
    year = str(rng.randint(eff_year - 12, eff_year - 1))
    since = str(rng.choice([y for y in range(eff_year - 15, eff_year) if str(y) != SRC["since"]]))
    ages = (str(rng.choice([a for a in range(21, 81) if str(a) != SRC["ages"][0]])),
            str(rng.choice([a for a in range(16, 81) if str(a) != SRC["ages"][1]])))
    bi = _other(rng, BI_TIERS, SRC["bi"])
    return dict(
        prem=prem, total=total, disc=disc, pif=total - disc, fee=fee,
        inst=(total + 4 * fee) / 4, plan_total=total + 4 * fee,
        bi=bi, sum=bi,                       # NY: SUM may not exceed BI; carriers print it equal
        pd=_other(rng, PD_TIERS, SRC["pd"]), med=_other(rng, MED_TIERS, SRC["med"]),
        comp_ded=_other(rng, DED_TIERS, SRC["comp_ded"]),
        coll_ded=_other(rng, DED_TIERS, SRC["coll_ded"]),
        accessory=_other(rng, ACCESSORY_TIERS, SRC["accessory"]),
        mp=rng.choice([n for n in range(3, 16) if n != SRC["mp"]]),
        cf=rng.choice([n for n in range(1, 10) if n != SRC["cf"]]),
        ho=rng.choice([n for n in range(20, 61) if n != SRC["ho"]]),
        tier=_other(rng, TIERS, SRC["tier"]), since=since, ages=ages,
        genders=(rng.choice(["Male", "Female"]), rng.choice(["Male", "Female"])),
        marital=(rng.choice(["Married", "Single"]), rng.choice(["Married", "Single"])),
        vehicle=(year, make, model, cc),
    )


# ── reading and editing the page ─────────────────────────────────────────────

class Line:
    def __init__(self, line):
        spans = [s for s in line["spans"] if s["text"].strip()]
        self.spans = spans
        self.text = "".join(s["text"] for s in line["spans"]).strip()
        self.bbox = pymupdf.Rect(line["bbox"])
        self.size = spans[0]["size"]
        self.cy = (self.bbox.y0 + self.bbox.y1) / 2


def _lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            if any(s["text"].strip() for s in l["spans"]):
                ln = Line(l)
                if ln.size >= 3:                  # not the 1pt white tracking strip
                    out.append(ln)
    return out


class Editor:
    """Collects edits for one page, then applies them in one redaction pass."""

    def __init__(self, page, problems):
        self.page, self.problems, self.lines, self.edits = page, problems, _lines(page), {}

    def row_y(self, label):
        hits = [l for l in self.lines if l.text == label and l.bbox.x0 < 300]
        if not hits:
            self.problems.append(f"p{self.page.number + 1}: row {label!r} not found")
            return None
        return hits[0].cy

    def cell(self, y, x0, x1, old, new, align="left"):
        """Replace `old` in the line starting in [x0, x1] on row `y`."""
        if y is None:
            return
        hits = [l for l in self.lines if x0 <= l.bbox.x0 <= x1 and abs(l.cy - y) < 4 and old in l.text]
        self._queue(hits, old, new, align, f"cell {old!r} at y={y:.0f}")

    def inline(self, context, old, new, align="left", nth=None):
        """Replace `old` inside every line containing `context` (or the nth one)."""
        hits = [l for l in self.lines if context in l.text and old in l.text]
        if nth is not None:
            hits = sorted(hits, key=lambda l: (l.bbox.y0, l.bbox.x0))[nth:nth + 1]
        self._queue(hits, old, new, align, f"{old!r} in {context!r}")

    def _queue(self, hits, old, new, align, what):
        """Edits are made to whole LINES, never to a run inside one.

        Redrawing only "$100,000" of "$100,000 each accident" leaves the new
        figure as a separate run at the end of the content stream, so the
        text layer reads "each accident ... $250,000" - the line an extractor
        sees is broken, and so is the gold's own page-reference search. The
        whole line is removed and redrawn with the substitution made in it.
        """
        if not hits:
            self.problems.append(f"p{self.page.number + 1}: {what} not found")
            return
        for line in hits:
            entry = self.edits.setdefault(id(line), [line, line.text, align])
            entry[1] = entry[1].replace(old, new)
            if align == "right":
                entry[2] = "right"

    def apply(self):
        if not self.edits:
            return
        for line, _, _ in self.edits.values():
            r = line.bbox
            self.page.add_redact_annot(pymupdf.Rect(r.x0 + 0.3, r.y0 + r.height * 0.35,
                                                    r.x1 - 0.3, r.y1 - r.height * 0.35), fill=False)
        # remove the old glyphs from the text layer; keep rules and images
        self.page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                                   graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
        for line, text, align in self.edits.values():
            span = line.spans[0]
            bold = any(k in span["font"] for k in ("Bold", "Black", "Heavy"))
            font = "hebo" if bold else "helv"
            size = span["size"]
            width = pymupdf.get_text_length(text, fontname=font, fontsize=size)
            # a cell may grow a little into its gutter; a line of prose may not
            room = line.bbox.width + (12 if len(line.text) < 50 and align != "inline" else 0.5)
            if width > room:                      # condense rather than run into the next word
                size *= room / width
                width = room
            x = line.bbox.x1 - width if align == "right" else line.bbox.x0
            self.page.insert_text((x, span["origin"][1]), text, fontname=font,
                                  fontsize=size, color=(0, 0, 0))


# ── the pass ─────────────────────────────────────────────────────────────────

def vary(pdf_path: Path, gold_path: Path, seed: str) -> list[str]:
    """Redraw the varied figures into `pdf_path` and rewrite `gold_path`.

    Returns problems; an empty list means the file was varied and verified.
    """
    problems: list[str] = []
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    eff = gold["policy"]["effective_date"]["raw"]
    eff_year = datetime.strptime(eff, "%b %d, %Y").year
    m = draw_model(random.Random(seed), eff_year)

    doc = pymupdf.open(pdf_path)
    if doc.page_count != 5:
        return [f"expected the 5-page Progressive layout, got {doc.page_count} pages"]
    p1, p2, p3, p4 = (Editor(doc[i], problems) for i in range(4))

    # page 1 - drivers
    driver_rows = sorted([l for l in p1.lines if 290 <= l.bbox.x0 <= 300 and l.text.isdigit()
                          and 490 < l.cy < 545], key=lambda l: l.cy)
    names = []
    if len(driver_rows) != 2:
        problems.append(f"p1: expected 2 driver rows, found {len(driver_rows)}")
    else:
        for i, row in enumerate(driver_rows):
            p1.cell(row.cy, 290, 300, SRC["ages"][i], m["ages"][i])
            old_g = next((l.text for l in p1.lines if 400 <= l.bbox.x0 <= 410 and abs(l.cy - row.cy) < 4), None)
            old_s = next((l.text for l in p1.lines if 476 <= l.bbox.x0 <= 486 and abs(l.cy - row.cy) < 4), None)
            if old_g != m["genders"][i]:
                p1.cell(row.cy, 400, 410, old_g or "?", m["genders"][i])
            if old_s != m["marital"][i]:
                p1.cell(row.cy, 476, 486, old_s or "?", m["marital"][i])
            names.append(next((l.text for l in p1.lines if l.bbox.x0 < 115 and abs(l.cy - row.cy) < 4), None))

    # page 2 - outline of coverage, premium totals, discounts, tier
    year, make, model, cc = m["vehicle"]
    sy, smake, smodel, scc = SRC["vehicle"]
    # "Engine displacement" follows on the same line, so the unit must fit in place
    p2.inline(f"{sy} {smake} {smodel}", f"{sy} {smake} {smodel}", f"{year} {make} {model}", "inline")
    p2.inline("Engine displacement", scc, cc, "inline")
    p2.inline(f"{sy} {smake}", f"{sy} {smake}", f"{year} {make}", nth=1)   # discount block, line 1
    p2.cell(p2.row_y(smodel) if any(l.text == smodel for l in p2.lines) else None,
            100, 115, smodel, model)
    for label, key, src in COVERAGES:
        y = p2.row_y(label)
        new = m["prem"][key]
        p2.cell(y, 520, 560, src, f"${new}" if src.startswith("$") else str(new), "right")
    y_bi, y_sum = p2.row_y("Bodily Injury Liability"), p2.row_y("Supplementary Uninsured/Underinsured Motorist")
    for y, pair in ((y_bi, m["bi"]), (y_sum, m["sum"])):
        p2.cell(y, 290, 300, f"{SRC['bi'][0]} each person/{SRC['bi'][1]} each accident",
                f"{pair[0]} each person/{pair[1]} each accident")
    p2.cell(p2.row_y("Property Damage Liability"), 290, 300, SRC["pd"], m["pd"])
    p2.cell(p2.row_y("Medical Payments"), 290, 300, SRC["med"], m["med"])
    p2.cell(p2.row_y("Comprehensive"), 470, 485, SRC["comp_ded"], m["comp_ded"])
    p2.cell(p2.row_y("Collision"), 470, 485, SRC["coll_ded"], m["coll_ded"])
    p2.cell(p2.row_y("Accessory Coverage"), 290, 300, SRC["accessory"], m["accessory"])
    p2.inline("we provide up to", SRC["accessory"].replace(",", ""), m["accessory"].replace(",", ""), "inline")
    y_total = p2.row_y("Total")
    p2.cell(y_total, 520, 560, f"${SRC['total']}", f"${m['total']}", "right")
    p2.cell(p2.row_y("Discount if paid in full"), 520, 560, f"-{SRC['disc']}", f"-{m['disc']}", "right")
    p2.cell(p2.row_y("Total 12 month policy premium if paid in full"), 520, 560,
            f"${SRC['total'] - SRC['disc']}", f"${m['pif']}", "right")
    y_mp = p2.row_y("Multi-Policy")
    p2.cell(y_mp, 280, 300, f"${SRC['mp']}", f"${m['mp']}", "right")
    p2.cell(y_mp, 530, 560, f"${SRC['cf']}", f"${m['cf']}", "right")
    p2.cell(p2.row_y("Home Owner"), 280, 300, f"${SRC['ho']}", f"${m['ho']}", "right")
    p2.inline("assigned to the", f"{SRC['tier']} tier.", f"{m['tier']} tier.")

    # page 3 - renewal letter and coupon
    T, D, F = m["total"], m["disc"], m["fee"]
    p3.inline("customer since", SRC["since"], m["since"], "inline")
    p3.inline("policy premium excluding", _money(SRC["total"], True), _money(T, True), "inline")
    p3.inline("Total Cost", _money(SRC["total"] + 4 * SRC["fee"], True), _money(m["plan_total"], True), "inline")
    p3.inline("Total Cost", _money(SRC["total"] - SRC["disc"], True), _money(m["pif"], True), "inline")
    p3.inline("Includes savings of", _money(SRC["disc"], True), _money(D, True), "inline")
    p3.inline("Pay in Full:", _money(SRC["total"] - SRC["disc"], True), _money(m["pif"], True), "inline")
    src_inst = _money((SRC["total"] + 4 * SRC["fee"]) / 4, True)
    p3.inline("Pay initial installment", src_inst, _money(m["inst"], True), "inline")

    # page 4 - payment schedule
    for line in [l for l in p4.lines if l.text == src_inst]:
        p4.cell(line.cy, line.bbox.x0 - 1, line.bbox.x0 + 1, src_inst, _money(m["inst"], True))
    p4.inline("installment fee of", _money(SRC["fee"], True), _money(F, True), "inline")

    if problems:                                   # do not half-edit an unrecognised layout
        return problems
    for ed in (p1, p2, p3, p4):
        ed.apply()
    tmp = pdf_path.with_suffix(".tmp.pdf")
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    os.replace(tmp, pdf_path)

    # Re-measure page references for the fields written here only. The
    # engine's own fields keep theirs: some were never printed (a source
    # filename) and carry no evidence once the engine has resolved them, so
    # re-measuring them would report a miss for every one.
    before = {id(f) for _, f in walk_indexed(gold)}
    _rewrite_gold(gold, m, names)
    written = [f for _, f in walk_indexed(gold) if id(f) not in before]
    _, misses = pageref.attach({"written": written}, pdf_path)
    problems += [f"gold value not on any page: {p} = {r!r}" for p, r in misses]
    problems += _verify(pdf_path, gold, m)
    gold_path.write_text(json.dumps(gold, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return problems


# ── gold ─────────────────────────────────────────────────────────────────────

def _m(raw):
    return fv(raw, as_number(raw))


def _rewrite_gold(gold: dict, m: dict, names: list) -> None:
    year, make, model, cc = m["vehicle"]
    unit = f"{year} {make} {model}"
    T = m["total"]
    limits = {"bi": f"{m['bi'][0]} each person/{m['bi'][1]} each accident", "pd": f"{m['pd']} each accident",
              "pip": "$50,000 each person", "sum": f"{m['sum'][0]} each person/{m['sum'][1]} each accident",
              "med": f"{m['med']} each person", "comp": "Actual Cash Value", "coll": "Actual Cash Value"}
    deds = {"pip": "$0", "comp": m["comp_ded"], "coll": m["coll_ded"]}
    groups = {"bi": "Liability To Others"}

    coverages, unit_covs = [], []
    for i, (label, key, src) in enumerate(COVERAGES):
        prem = f"${m['prem'][key]}" if src.startswith("$") else str(m["prem"][key])
        cs = {"coverage_name": fv(label), "limit": fv(limits[key]), "premium": _m(prem)}
        uc = {"coverage_name": fv(label), "applies_to": fv(unit), "limit_amount": fv(limits[key]),
              "premium": _m(prem)}
        if key in groups:
            cs["coverage_type"] = fv(groups[key])
        if key in deds:
            cs["deductible"] = _m(deds[key])
            uc["deductible_amount"] = _m(deds[key])
        if key in ("comp", "coll"):
            uc["valuation_basis"] = fv("Actual Cash Value")
        coverages.append(cs)
        unit_covs.append(uc)
    acc = {"coverage_name": fv("Accessory Coverage"), "limit": _m(m["accessory"]),
           "premium": derived("included", "included")}
    coverages.append(acc)
    unit_covs.append({"coverage_name": fv("Accessory Coverage"), "applies_to": fv(unit),
                      "limit_amount": _m(m["accessory"]), "is_included": derived("true", "included")})
    gold["coverages"] = coverages

    old_vehicle = (gold["auto"].get("vehicles") or [{}])[0]
    zip_af = next((a for a in gold.get("additional_fields", [])
                   if a.get("name", "").startswith("Garaging Zip")), None)
    vehicle = {"year": fv(year), "make": fv(make), "model": fv(model),
               "engine_displacement": fv(f"{cc} cc's", cc), "coverages": unit_covs}
    if old_vehicle.get("vin"):
        vehicle["vin"] = old_vehicle["vin"]
    if zip_af:
        vehicle["garaging_address"] = {"postal_code": zip_af["value"]}
    gold["auto"]["vehicles"] = [vehicle]           # the engine's 2nd "vehicle" was a deductible

    gold["auto"]["drivers"] = [
        {"name": fv(names[i]), "age": fv(m["ages"][i], int(m["ages"][i])),
         "gender": fv(m["genders"][i]), "marital_status": fv(m["marital"][i]),
         **({"relationship_to_insured": fv("Named insured"),
             "is_named_insured": derived("true", "Named insured")} if i == 0 else {})}
        for i in range(2)]

    lc = gold["auto"].setdefault("liability_coverages", {})
    lc.update({
        "bodily_injury_per_person_limit": _m(m["bi"][0]),
        "bodily_injury_per_accident_limit": _m(m["bi"][1]),
        "bodily_injury_split_limits": fv(limits["bi"]),
        "property_damage_limit": _m(m["pd"]),
        "medical_payments_limit": _m(m["med"]),
        "supplementary_uninsured_underinsured_limit": fv(limits["sum"]),
        "supplementary_uninsured_underinsured_per_person_limit": _m(m["sum"][0]),
        "supplementary_uninsured_underinsured_per_accident_limit": _m(m["sum"][1]),
    })
    pdc = gold["auto"].setdefault("physical_damage_coverages", {})
    pdc.update({"comprehensive_deductible": _m(m["comp_ded"]),
                "collision_deductible": _m(m["coll_ded"]),
                "custom_equipment_limit": _m(m["accessory"]),
                "valuation_basis": fv("Actual Cash Value"),
                "comprehensive_premium": _m(str(m["prem"]["comp"])),
                "collision_premium": _m(str(m["prem"]["coll"]))})

    pr = gold["premium"]
    pr["total_policy_premium"] = _m(f"${T}")
    pr["paid_in_full_total_premium"] = _m(_money(m["pif"], True))
    pr["discounts_and_credits"] = [  # the engine filled this with the table's column headings
        {"description": fv(d), "amount": _m(f"${a}"), "applies_to": fv(f"{year} {make}"),
         "is_applied": derived("true", d)}
        for d, a in (("Multi-Policy", m["mp"]), ("Claim Free Renewal", m["cf"]), ("Home Owner", m["ho"]))]

    bl = gold["billing"]
    inst = _money(m["inst"], True)
    bl["amount_due"] = _m(inst)
    for item in bl.get("installments") or []:
        item["amount"] = _m(inst)
        item["installment_fee"] = _m(_money(m["fee"], True))
    bl["installment_fee"] = _m(_money(m["fee"], True))
    bl["installment_plan_total_cost"] = _m(_money(m["plan_total"], True))
    bl["pay_in_full_savings_amount"] = _m(_money(m["disc"], True))

    gold["policy"]["policy_tier"] = fv(m["tier"])
    gold["policy"]["policyholder_since_date"] = fv(m["since"])
    ro = gold.get("document_type_detail", {}).get("renewal_offer")
    if isinstance(ro, dict):
        ro["renewal_premium"] = _m(_money(T, True))

    # paragraphs the gold quotes: same substitutions as the page
    subs = [(f"{SRC['tier']} tier", f"{m['tier']} tier"), ("since 2017", f"since {m['since']}"),
            ("$3000", m["accessory"].replace(",", "")), ("$141.00", _money(T, True)),
            ("$161.00", _money(m["plan_total"], True)), ("$125.00", _money(m["pif"], True)),
            ("$16.00", _money(m["disc"], True)), ("$40.25", inst), ("fee of $5.00", f"fee of {_money(m['fee'], True)}"),
            ("2017 POLARIS RANGER 900", unit), ("875 cc's", f"{cc} cc's")]
    for sec in (gold.get("text_sections") or {}).values():
        if isinstance(sec, dict) and isinstance(sec.get("raw_text"), str):
            for old, new in subs:
                sec["raw_text"] = sec["raw_text"].replace(old, new)

    # values now held by a proper field, or that held the source's figures
    mapped = {"$500,000", "$0", "$141", "$125", "$7", "$3", "$42"}
    gold["additional_fields"] = [
        a for a in gold.get("additional_fields", [])
        if not (a.get("name", "").startswith("Garaging Zip")
                or a["value"].get("raw") in mapped
                or a["value"].get("raw") == names[1])]


def _verify(pdf_path: Path, gold: dict, m: dict) -> list[str]:
    """The arithmetic, and that no source figure is still on the page."""
    out = []
    covs = [c["premium"]["parsed"] for c in gold["coverages"] if isinstance(c["premium"]["parsed"], (int, float))]
    if abs(sum(covs) - gold["premium"]["total_policy_premium"]["parsed"]) > 0.01:
        out.append(f"coverage premiums sum to {sum(covs)}, total says {m['total']}")
    if abs(m["plan_total"] - 4 * m["inst"]) > 0.001:
        out.append("installments do not sum to the plan total")
    text = "\n".join(p.get_text() for p in pymupdf.open(pdf_path))
    for gone in ("$141.00", "$161.00", "$125.00", "$40.25", "$16.00", "RANGER 900", "Ultra Preferred D",
                 "$250,000 each person", "875 cc"):
        if gone in text:
            out.append(f"source figure still printed: {gone!r}")
    return out
