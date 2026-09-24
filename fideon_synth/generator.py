"""
Common Synthetic Data Generator.

A single unified generator that:
1. Takes the original source PDF documents in `Data/original PDFs/`
2. Generates synthetic variations - insured (name, entity type, address, FEIN),
   producer, policy numbers, dates, class of business, payroll, rates and every
   premium figure that follows from them
3. Outputs the synthetic PDFs to `output/PDF/`
4. Generates matching gold JSON files adhering to `config/policy_check/` in `output/gold_json/`
5. Is fully configurable via `--count`

Variation comes from the corpora below rather than from a short fixed list, so
a corpus of a few hundred documents still has few repeated insureds, agencies
or addresses. Every corpus is drawn from a seeded `Values`, so the same seed
gives the same documents.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from . import pageref
from .corpus import Built, Report
from .fields import as_number, date_fv, derived, fmt_money, fv, money, money_from
from .scan import by_key as scan_by_key, scan_pdf
from .schema import CanonicalSchema
from .values import GIVEN, NY_TOWNS, STREET_NAME, SURNAME, Values


# ── corpora ─────────────────────────────────────────────────────────────────
# Invented names throughout: nothing here should be able to name a real
# business. Places are public geography.

COMPANY_PREFIX = [
    "Harrowgate", "Beacon Crest", "Empire Ridge", "Hudson River", "Mohawk Valley",
    "Adirondack", "Catskill Peak", "Pioneer", "Winterberry", "Ironwood",
    "Northfield", "Stonecrop", "Larkspur", "Cedarhollow", "Brightwater",
    "Thornfield", "Millbrook", "Fernbank", "Copperkettle", "Blue Heron",
    "Silverbirch", "Redfern", "Highland Park", "Lakeshore", "Meadowbrook",
    "Oakmont", "Pinecrest", "Riverbend", "Stonegate", "Summit Ridge",
    "Sycamore", "Timberline", "Whitcomb", "Willowbrook", "Yellow Birch",
    "Alder Creek", "Amber Hill", "Ashgrove", "Bellwether", "Birchwood",
    "Bramblewood", "Clearwater", "Cobblestone", "Crescent", "Dogwood",
    "Eastbrook", "Elmhurst", "Foxglove", "Glenmore", "Greystone",
    "Hawthorne", "Juniper Bend", "Kingfisher", "Laurel Run", "Maplecrest",
    "Nutmeg", "Old Mill", "Painted Post", "Quarry Hill", "Rockland",
    "Sawmill", "Tamarack", "Upland", "Valley Forge", "Westbrook",
]

# noun, entity kinds it is used with
COMPANY_NOUN = [
    "Realty", "Properties", "Hospitality", "Logistics", "Builders", "Timber & Mill",
    "Transport Services", "Lodging", "Contracting", "Excavating", "Landscaping",
    "Plumbing & Heating", "Electric", "Roofing", "Carpentry", "Paving",
    "Property Management", "Restaurant Group", "Inn & Suites", "Motor Lodge",
    "Auto Repair", "Hardware", "Marketing", "Consulting", "Medical Billing",
    "Design Studio", "Painting", "Masonry", "Trucking", "Storage",
    "Facility Services", "Janitorial", "Catering", "Outfitters", "Farm Supply",
    "Nursery & Garden", "Stone Works", "Cabinetry", "Sign & Print", "Home Services",
]

CORP_SUFFIX = ["Inc.", "Corp.", "Incorporated"]

AGENCY_HEAD = [
    "CHENANGO", "KEYSTONE", "DELAWARE", "GENESEE", "SUSQUEHANNA", "OTSEGO",
    "UNADILLA", "CATSKILL", "ADIRONDACK", "MOHAWK", "OSWEGO", "SENECA",
    "CAYUGA", "TIOGA", "SCHOHARIE", "HERKIMER", "SARATOGA", "CHAMPLAIN",
    "FINGER LAKES", "SOUTHERN TIER", "NORTH COUNTRY", "LEATHERSTOCKING",
    "BUTTERNUT", "SHERBURNE", "HAMILTON", "MADISON", "ONEIDA", "WYOMING",
    "CORTLAND", "BROOME",
]
AGENCY_TAIL = [
    "BROKERS, LLC", "RISK PARTNERS LLC", "AGENCY SERVICES", "BROKERAGE INC",
    "INSURANCE AGENCY", "INSURANCE GROUP, INC.", "COVERAGE ASSOCIATES", "AGENCY, LLC",
]

AGENCY_STREET = [
    "MAIN STREET", "COURT STREET", "EAST MARKET ST", "CHURCH STREET", "RAILROAD AVE",
    "WEST STATE ST", "ACADEMY STREET", "PARK PLACE", "FRONT STREET", "BRIDGE STREET",
]

STREET_EXTRA = [
    "Main St", "Church St", "Mill St", "River Rd", "Lake Rd", "Maple Ave",
    "Union St", "Depot St", "Academy St", "Center St", "Elm St", "Front St",
]

# (city, ZIP) - larger than values.NY_TOWNS; main-post-office ZIPs only.
NY_CITIES = [
    ("Cooperstown", "13326"), ("Oneonta", "13820"), ("Norwich", "13815"),
    ("Sidney", "13838"), ("Walton", "13856"), ("Delhi", "13753"),
    ("Margaretville", "12455"), ("Cobleskill", "12043"), ("Herkimer", "13350"),
    ("Little Falls", "13365"), ("Ilion", "13357"), ("Utica", "13501"),
    ("Rome", "13440"), ("Oneida", "13421"), ("Cazenovia", "13035"),
    ("Hamilton", "13346"), ("Canastota", "13032"), ("Fulton", "13069"),
    ("Oswego", "13126"), ("Ithaca", "14850"), ("Cortland", "13045"),
    ("Binghamton", "13901"), ("Endicott", "13760"), ("Owego", "13827"),
    ("Elmira", "14901"), ("Corning", "14830"), ("Watertown", "13601"),
    ("Lowville", "13367"), ("Potsdam", "13676"), ("Malone", "12953"),
    ("Saranac Lake", "12983"), ("Lake Placid", "12946"), ("Plattsburgh", "12901"),
    ("Glens Falls", "12801"), ("Saratoga Springs", "12866"), ("Gloversville", "12078"),
    ("Johnstown", "12095"), ("Amsterdam", "12010"), ("Schenectady", "12305"),
    ("Kingston", "12401"), ("Catskill", "12414"), ("Hudson", "12534"),
    ("Old Forge", "13420"), ("Speculator", "12164"), ("Milford", "13807"),
    ("Andes", "13731"), ("Oxford", "13830"), ("Boonville", "13309"),
    ("Camden", "13316"), ("Morrisville", "13408"), ("Sherburne", "13460"),
    ("Richfield Springs", "13439"), ("Eagle Bay", "13331"),
]

# (class code, description as the form prints it, employees, $/employee, rate range)
# Descriptions stay within the width of the classification column.
CLASSES = [
    ("9052", "Hotel NOC: All Other Employees & Drivers", (1, 10), (24, 52), (3.20, 4.20)),
    ("9058", "Hotel: Restaurant Employees", (2, 12), (22, 44), (2.10, 3.30)),
    ("9015", "Building Operation by Owner NOC", (1, 6), (26, 55), (3.00, 5.20)),
    ("8810", "Clerical Office Employees NOC", (2, 14), (32, 62), (0.18, 0.46)),
    ("8742", "Salespersons - Outside", (1, 8), (34, 70), (0.30, 0.85)),
    ("8017", "Store: Retail NOC", (2, 10), (24, 46), (1.40, 2.90)),
    ("9083", "Restaurant NOC", (3, 14), (20, 38), (2.00, 3.80)),
    ("8380", "Automobile Service or Repair Center", (2, 9), (32, 58), (3.10, 5.60)),
    ("5183", "Plumbing NOC & Drivers", (2, 8), (40, 74), (4.60, 7.90)),
    ("5190", "Electrical Wiring Within Buildings", (2, 8), (42, 78), (3.60, 6.20)),
    ("5645", "Carpentry - Detached 1 or 2 Family", (2, 7), (38, 66), (9.20, 14.10)),
    ("5474", "Painting or Decorating NOC", (1, 6), (34, 60), (6.10, 9.80)),
    ("0042", "Landscape Gardening & Drivers", (2, 9), (28, 50), (5.20, 8.90)),
    ("7380", "Drivers, Chauffeurs NOC", (1, 8), (30, 56), (4.10, 7.80)),
    ("8832", "Physician & Clerical", (2, 10), (48, 90), (0.40, 0.95)),
    ("9403", "Garbage or Ash Collection", (2, 8), (34, 60), (8.40, 12.60)),
    ("2802", "Carpentry - Shop Only & Drivers", (2, 8), (32, 56), (4.30, 7.20)),
    ("8039", "Store: Wholesale NOC", (2, 8), (30, 56), (2.30, 4.20)),
]

ENTITIES = [("Limited Liability Company", "LLC"), ("Corporation", "Corporation"),
            ("Partnership", "Partnership"), ("Individual", "Individual")]
ENTITY_WEIGHTS = [45, 25, 15, 15]

MAX_NAME_LEN = 42

# Text in the source dec pages that must not survive into any generated PDF.
SOURCE_LEAKS = [
    "Harrowgate", "TWC4467573", "TWC4308391", "Old Forge", "2898 New York",
    "CHENANGO", "HANCOCK", "854261826", "Hotel NOC", "July 2, 2024",
]

# Page indexes (0-based) in amtrust_wc_dec.pdf and a phrase proving each is the
# page we think it is, so a different source file fails loudly.
INFO_PAGE = (5, "Countersigned by")
PREMIUM_PAGE = (8, "SCHEDULE OF PREMIUMS")


# ── PDF editing ─────────────────────────────────────────────────────────────

def _base14(font_name: str) -> str:
    name = font_name.split("+")[-1].lower()
    bold = "bold" in name
    italic = "italic" in name or "oblique" in name
    if "times" in name:
        return "tibo" if bold else ("tiit" if italic else "tiro")
    return "hebo" if bold else ("heit" if italic else "helv")


def _color(value: int) -> Tuple[float, float, float]:
    return ((value >> 16 & 255) / 255.0, (value >> 8 & 255) / 255.0, (value & 255) / 255.0)


def _bounded(pattern: str) -> str:
    return r"(?<![A-Za-z0-9,])%s(?![A-Za-z0-9])" % re.escape(pattern)


def _compile(mapping: Dict[str, str]):
    if not mapping:
        return None
    keys = sorted(mapping, key=len, reverse=True)
    return re.compile("|".join(_bounded(k) for k in keys))


def _rewrite_page(page, substr: Dict[str, str], exact: Dict[str, str],
                  prefix: Optional[Dict[str, str]] = None) -> List[dict]:
    """Rewrite every span that carries a target, in the span's own font.

    Whole spans are redrawn rather than the matched substring, so a date of a
    different width inside a sentence cannot collide with the words after it.
    Returns the spans that were rewritten, with their new text.
    """
    pattern = _compile(substr)
    edits = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = span["text"]
                new = text
                stripped = text.strip()
                if stripped in exact:
                    new = exact[stripped]
                elif prefix and any(stripped.startswith(k) for k in prefix):
                    new = next(v for k, v in prefix.items() if stripped.startswith(k))
                elif pattern:
                    new = pattern.sub(lambda m: substr[m.group(0)], text)
                if new != text:
                    edits.append({"span": span, "new": new})
    return edits


def _apply(page, edits: List[dict]) -> None:
    for edit in edits:
        if edit.get("draw_only"):
            continue
        span = edit["span"]
        size = span["size"]
        ox, oy = span["origin"]
        x0, _, x1, _ = span["bbox"]
        rect = fitz.Rect(x0 - 0.5, oy - size * 0.76, x1 + 0.5, oy + size * 0.22)
        page.add_redact_annot(rect, fill=(1, 1, 1))
    if edits:
        try:
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        except (AttributeError, TypeError):
            page.apply_redactions()

    for edit in edits:
        span, new = edit["span"], edit["new"]
        if not new.strip():
            continue
        font = _base14(span["font"])
        size = span["size"]
        ox, oy = span["origin"]
        x1 = span["bbox"][2]
        width = fitz.get_text_length(new, fontname=font, fontsize=size)
        x = x1 - width if (x1 >= 500 and len(span["text"]) <= 30) else ox
        page.insert_text((x, oy), new, fontsize=size, fontname=font,
                         color=_color(span["color"]))


def _long_date(d: date) -> str:
    return "%s %d, %d" % (d.strftime("%B"), d.day, d.year)


def _short_date(d: date) -> str:
    return "%d/%d/%d" % (d.month, d.day, d.year)


def _plus_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29 Feb
        return d.replace(year=d.year + 1, day=28)


def _money(n: int) -> str:
    return format(n, ",")


# ── generator ───────────────────────────────────────────────────────────────

class SyntheticGenerator:
    """Unified generator creating synthetic documents and matching gold JSON from source documents."""

    def __init__(
        self,
        input_dir: str | Path = r"Data\original PDFs",
        out_dir: str | Path = r"E:\fideon-synth\output",
        schema_dir: str | Path = r"E:\fideon-synth\config\policy_check",
        pdf_subdir: str = "PDF",
        gold_subdir: str = "gold_json",
    ):
        self.input_dir = Path(input_dir)
        self.out_dir = Path(out_dir)
        self.schema_dir = Path(schema_dir)
        self.pdf_dir = self.out_dir / pdf_subdir
        self.gold_dir = self.out_dir / gold_subdir

        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.gold_dir.mkdir(parents=True, exist_ok=True)

        self.schema = CanonicalSchema.load("wc", schema_dir=self.schema_dir)

    def generate(self, count: int = 5, seed: int = 0, progress=None) -> Report:
        """Generate `count` synthetic variations."""
        report = Report(template="original_documents_source", schema="%s v%s" % (self.schema.lob, self.schema.version))
        vals = Values(seed)
        seen = set()

        source_dec = self.input_dir / "AmTrust" / "wc" / "amtrust_wc_dec.pdf"
        if not source_dec.exists():
            raise FileNotFoundError("Source document not found: %s" % source_dec)

        for i in range(1, count + 1):
            built = self._generate_one(source_dec, i, vals, seen)
            report.documents.append(built)
            if progress:
                progress(built)

        return report

    # ── corpora draws ───────────────────────────────────────────────────────

    def _street(self, vals: Values) -> str:
        number = vals.choice([vals.integer(3, 299), vals.integer(300, 2999)])
        style = vals.integer(0, 3)
        if style == 0:
            return "%d %s" % (number, vals.choice(STREET_NAME))
        if style == 1:
            return "%d %s" % (number, vals.choice(STREET_EXTRA))
        if style == 2:
            return "%d State Route %d" % (number, vals.choice([7, 10, 12, 28, 30, 80, 205, 206, 23, 8]))
        return "%d County Route %d" % (number, vals.integer(2, 48))

    def _insured(self, vals: Values, seen: set) -> dict:
        for _ in range(200):
            kind = vals.rng.choices(ENTITIES, weights=ENTITY_WEIGHTS)[0]
            entity, box = kind
            prefix, noun = vals.choice(COMPANY_PREFIX), vals.choice(COMPANY_NOUN)
            if box == "LLC":
                name = "%s %s LLC" % (prefix, noun)
            elif box == "Corporation":
                name = "%s %s %s" % (prefix, noun, vals.choice(CORP_SUFFIX))
            elif box == "Partnership":
                a, b = vals.pick(SURNAME, 2)
                name = "%s & %s %s" % (a, b, noun)
            else:
                name = "%s %s" % (vals.choice(GIVEN), vals.choice(SURNAME))
            if "Harrowgate" in name:
                continue  # the source document's own insured
            if len(name) <= MAX_NAME_LEN and name not in seen:
                seen.add(name)
                city, postal = vals.choice(NY_CITIES)
                return {"name": name, "entity": entity, "box": box,
                        "street": self._street(vals), "city": city, "postal": postal,
                        "fein": "%02d%07d" % (vals.choice(list(range(20, 28)) + list(range(45, 49)) + list(range(81, 88))),
                                              vals.integer(0, 9999999))}
        raise RuntimeError("could not draw a unique insured")

    def _producer(self, vals: Values) -> dict:
        city, postal = vals.choice(NY_CITIES)
        name = "%s %s" % (vals.choice(AGENCY_HEAD), vals.choice(AGENCY_TAIL))
        if vals.maybe(0.55):
            street = "PO BOX %d" % vals.integer(12, 990)
        else:
            street = "%d %s" % (vals.integer(2, 320), vals.choice(AGENCY_STREET))
        return {"name": name, "street": street, "city": city.upper(), "postal": postal}

    def _finance(self, vals: Values) -> dict:
        while True:
            code, desc, (elo, ehi), (plo, phi), (rlo, rhi) = vals.choice(CLASSES)
            emps = vals.integer(elo, ehi)
            remun = int(round(emps * vals.integer(plo, phi) * 1000 / 100.0)) * 100
            rate = round(vals.rng.uniform(rlo, rhi), 2)
            manual = round(remun * rate / 100.0)
            mod_pct = vals.integer(82, 128)
            mod_premium = round(manual * mod_pct / 100.0)
            terrorism = max(1, round(remun / 100.0 * 0.035))
            catastrophe = max(1, round(remun / 100.0 * 0.004))
            expense = 200
            total_est = mod_premium + terrorism + catastrophe + expense
            if total_est >= 700:
                break
        assessment = round((total_est - expense) * 0.092)
        return {"code": code, "desc": desc, "emps": emps, "remun": remun, "rate": rate,
                "manual": manual, "mod_pct": mod_pct, "mod_premium": mod_premium,
                "terrorism": terrorism, "catastrophe": catastrophe, "expense": expense,
                "total_est": total_est, "assessment": assessment,
                "total_cost": total_est + assessment, "minimum": 600}

    # ── one document ────────────────────────────────────────────────────────

    def _generate_one(self, source_path: Path, index: int, vals: Values, seen: set) -> Built:
        built = Built(
            key="wc_sample_%03d" % index,
            pdf=self.pdf_dir / ("sample_%03d.pdf" % index),
            gold=self.gold_dir / ("sample_%03d.json" % index),
            pages=0,
            fields=0,
        )
        temp_digital = self.pdf_dir / ("_temp_%s" % built.pdf.name)

        try:
            # 1. Draw one consistent set of values for this document
            policy_num = "TWC%07d" % vals.integer(1000000, 8999999)
            prior_num = "TWC%07d" % (int(policy_num[3:]) - vals.integer(50000, 950000))
            insured = self._insured(vals, seen)
            producer = self._producer(vals)
            fin = self._finance(vals)

            eff = date(2024, 1, 1) + timedelta(days=vals.integer(0, 1090))
            exp = _plus_year(eff)
            issue = eff - timedelta(days=vals.integer(14, 60))
            eff_date, exp_date, issue_date = _short_date(eff), _short_date(exp), _short_date(issue)

            # 2. Mutate PDF from source
            doc = fitz.open(str(source_path))
            built.pages = len(doc)
            for idx, phrase in (INFO_PAGE, PREMIUM_PAGE):
                if phrase not in doc[idx].get_text():
                    raise ValueError("source page %d is not the expected page (missing %r)" % (idx + 1, phrase))

            substr = {
                "TWC4467573": policy_num,
                "TWC4308391": prior_num,
                "Harrowgate Realty LLC": insured["name"],
                "2898 New York  Rt 28": insured["street"],
                "Old Forge, NY 13420": "%s, NY %s" % (insured["city"], insured["postal"]),
                "854261826": insured["fein"],
                "8/14/2024": eff_date,
                "8/14/2025": exp_date,
                "7/2/2024": issue_date,
                "July 2, 2024": _long_date(issue),
                "CHENANGO BROKERS, LLC": producer["name"],
                "PO BOX 460": producer["street"],
                "HANCOCK, NY 13783": "%s, NY %s" % (producer["city"], producer["postal"]),
                "2,773": _money(fin["total_est"]),
                "3,010": _money(fin["total_cost"]),
                "2,624": _money(fin["manual"]),
                "2,545": _money(fin["mod_premium"]),
                "72,100": _money(fin["remun"]),
            }

            for page in doc:
                exact, prefix = {}, None
                page_substr = dict(substr)
                if page.number == INFO_PAGE[0]:
                    exact = {"237": _money(fin["assessment"])}
                elif page.number == PREMIUM_PAGE[0]:
                    exact = {
                        "237": _money(fin["assessment"]),
                        "3.64": "%.2f" % fin["rate"],
                        "9052": fin["code"],
                        "2": str(fin["emps"]),
                        "25": _money(fin["terrorism"]),
                        "3": _money(fin["catastrophe"]),
                    }
                    prefix = {"Hotel NOC": fin["desc"]}
                    page_substr["97%"] = "%d%%" % fin["mod_pct"]

                edits = _rewrite_page(page, page_substr, exact, prefix)

                if page.number == INFO_PAGE[0]:
                    edits += self._move_entity_mark(page, insured["box"])
                _apply(page, edits)

            doc.save(str(temp_digital))
            doc.close()

            leaks = [w for w, t in ((w, " ".join(pageref.page_texts(temp_digital))) for w in SOURCE_LEAKS)
                     if w.lower() in t]
            for leak in leaks:
                built.problems.append("source text %r survived into the generated PDF" % leak)

            # 3. Create canonical Gold JSON adhering to policy_check/wc.json
            gold_data = self._build_gold(
                built.pdf.name, built.pages, policy_num, prior_num, insured, producer,
                eff_date, exp_date, issue_date, fin,
            )

            # Measure page references from digital text before rasterization
            resolved, misses = pageref.attach(gold_data, temp_digital)
            for path, raw in misses:
                built.problems.append("gold says %s = %r is printed, but it is not on any page" % (path, raw))

            # 4. Keep only the scanned PDF in the documented PDF output folder.
            profile = scan_by_key("high_quality")
            scan_stats = scan_pdf(temp_digital, built.pdf, profile, seed=index)
            built.profile = scan_stats["profile"]

            gold_data["fideon:absent"] = self.schema.absent_from(
                pageref.stated_paths(gold_data)
            )
            gold_data["fideon:provenance"] = {
                "generator": "fideon-synth",
                "source": "reference_documents",
                "schema": "%s v%s" % (self.schema.lob, self.schema.version),
                "render": "scanned_only",
                "scanner_profile": scan_stats["profile"],
                "synthetic": True,
                "note": "Scanned synthetic document generated from reference source documents.",
            }

            # 5. Validate against canonical schema
            schema_problems = self.schema.validate(gold_data)
            if schema_problems:
                built.problems.extend(schema_problems)

            # 6. Write Gold JSON (matching exactly: sample_001.pdf -> sample_001.json)
            with open(built.gold, "w", encoding="utf-8") as f:
                json.dump(gold_data, f, indent=2)

            built.fields = len(pageref.stated_paths(gold_data))

        except Exception as e:
            built.problems.append(str(e))
        finally:
            if temp_digital.exists():
                temp_digital.unlink()

        return built

    @staticmethod
    def _move_entity_mark(page, box: str) -> List[dict]:
        """Move the printed "X" to the chosen entity-type box on the info page."""
        labels, mark = {}, None
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    t = span["text"].strip()
                    if t in ("Individual", "Partnership", "Corporation", "LLC"):
                        labels[t] = span
                    elif t == "X":
                        mark = span
        if mark is None or box not in labels:
            raise ValueError("entity-type checkboxes not found on the information page")
        target = labels[box]
        x = target["bbox"][0] - (labels["LLC"]["bbox"][0] - mark["bbox"][0])
        moved = dict(mark)
        moved["origin"] = (x, target["origin"][1])
        moved["bbox"] = (x, mark["bbox"][1], x + mark["bbox"][2] - mark["bbox"][0], mark["bbox"][3])
        return [{"span": mark, "new": ""}, {"span": moved, "new": "X", "draw_only": True}]

    def _build_gold(self, pdf_name, pages, policy_num, prior_num, insured, producer,
                    eff_date, exp_date, issue_date, fin) -> dict:
        def amount(value):
            return money(fmt_money(value), evidence=_money(value))

        entity = insured["entity"]
        name = insured["name"]
        address = {
            "line_1": fv(insured["street"]),
            "city": fv(insured["city"]),
            "state": fv("NY"),
            "postal_code": fv(insured["postal"]),
        }
        return {
            "document": {
                "document_type": fv("POLICY INFORMATION PAGE", "Information Page"),
                "document_title_as_stated": fv("WORKERS COMPENSATION AND EMPLOYERS LIABILITY INSURANCE POLICY"),
                "line_of_business_as_stated": fv("WORKERS COMPENSATION"),
                "page_count": fv(str(pages), pages, evidence=str(pages)),
                "source_file_name": derived(pdf_name),
                "issue_date": date_fv(issue_date),
            },
            "carrier": {
                "company_name": fv("Technology Insurance Company, Inc."),
                "address": {
                    "line_1": fv("59 Maiden Lane, 43rd Floor"),
                    "city": fv("New York"),
                    "state": fv("NY"),
                    "postal_code": fv("10038"),
                },
            },
            "named_insured": {
                "primary_name": fv(name),
                "entity_type": derived(entity),
                "fein": fv(insured["fein"]),
                "mailing_address": address,
            },
            "producer": {
                "agency_name": fv(producer["name"]),
                "address": {
                    "line_1": fv(producer["street"]),
                    "city": fv(producer["city"]),
                    "state": fv("NY"),
                    "postal_code": fv(producer["postal"]),
                },
            },
            "policy": {
                "policy_number": fv(policy_num),
                "prior_policy_number": fv(prior_num),
                "effective_date": date_fv(eff_date),
                "expiration_date": date_fv(exp_date),
                "policy_type": fv("Workers Compensation"),
            },
            "premium": {
                "total_policy_premium": amount(fin["total_cost"]),
                "estimated_annual_premium": amount(fin["total_est"]),
                "deposit_premium": amount(fin["total_cost"]),
                "minimum_premium": amount(fin["minimum"]),
                "surcharges": [
                    {
                        "description": fv("New York State Assessment"),
                        "amount": amount(fin["assessment"]),
                    }
                ],
            },
            "workers_compensation": {
                "item_1_insured": {
                    "named_insured": fv(name),
                    "legal_entity_type": derived(entity),
                    "fein": fv(insured["fein"]),
                    "ncci_code": fv("39071"),
                },
                "item_2_policy_period": {
                    "effective_date": date_fv(eff_date),
                    "expiration_date": date_fv(exp_date),
                    "state_of_issue": fv("New York", "NY"),
                },
                "item_3_coverage": {
                    "part_one_states": [fv("New York", "NY")],
                    "part_two_employers_liability_bodily_injury_by_accident_each_accident": money_from(100000, evidence="$100,000"),
                    "part_two_employers_liability_bodily_injury_by_disease_policy_limit": money_from(500000, evidence="$500,000"),
                    "part_two_employers_liability_bodily_injury_by_disease_each_employee": money_from(100000, evidence="$100,000"),
                    "part_three_other_states_insurance": [fv("All states except ND, OH, WA, WY and State(s) Designated in Item 3.A")],
                },
                "item_4_premium_basis": [
                    {
                        "state": fv("New York", "NY"),
                        "class_code": fv(fin["code"]),
                        "classification_description": fv(fin["desc"]),
                        "number_of_employees": fv(str(fin["emps"]), fin["emps"]),
                        "estimated_annual_remuneration": amount(fin["remun"]),
                        "rate_per_100_of_remuneration": fv("%.2f" % fin["rate"], fin["rate"]),
                        "estimated_annual_premium": amount(fin["manual"]),
                    }
                ],
                "premium_adjustments": {
                    "experience_modification_factor": fv("%d%%" % fin["mod_pct"], round(fin["mod_pct"] / 100.0, 2)),
                    "expense_constant": amount(fin["expense"]),
                    "terrorism_premium": amount(fin["terrorism"]),
                    "catastrophe_premium": amount(fin["catastrophe"]),
                    "total_estimated_annual_premium": amount(fin["total_est"]),
                    "deposit_premium": amount(fin["total_cost"]),
                    "minimum_premium": amount(fin["minimum"]),
                },
            },
            "signature": {
                "title": fv("Authorized Representative"),
                "signature_date": date_fv(issue_date),
            },
        }
