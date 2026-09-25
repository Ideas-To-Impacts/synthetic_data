"""
Tests for the generic generator (fideon_synth.generic / overlay).

The sources are built here rather than read from Data/, so the tests run on
any checkout: one declarations page with a real text layer, and the same page
as a scan with an invisible OCR layer - the two kinds the corpus holds.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date

import fitz
import pytest

from fideon_synth import CanonicalSchema, Values, generic, overlay
from fideon_synth.fields import as_date

pytestmark = pytest.mark.filterwarnings("ignore")

LINES = [
    (40, 60, 16, "WATERCRAFT DECLARATIONS PAGE"),
    (40, 100, 10, "Policy Number:"),
    (40, 114, 10, "MSB00001028349"),
    (300, 100, 10, "Policy Period: From 08/26/2026 To 08/26/2027"),
    (40, 150, 10, "Insured Name and Mailing Address"),
    (40, 166, 11, "Delphine Calloway"),
    (40, 180, 11, "506 WASHINGTON RD."),
    (40, 194, 11, "Lake Forest, IL 60045"),
    (300, 150, 10, "Your Agent"),
    (300, 166, 10, "Patriotic Insurance Group"),
    (300, 180, 10, "PO Box 329"),
    (300, 194, 10, "Inlet, NY 13360"),
    (40, 240, 10, "FEIN: 87-2200775"),
    (40, 300, 10, "TOTAL ANNUAL PREMIUM: $535.00"),
    (40, 700, 9, "Policy MSB00001028349 - page 1 of 1"),
]
ORIGINALS = ["MSB00001028349", "Delphine Calloway", "506 WASHINGTON RD.",
             "Lake Forest, IL 60045", "Patriotic Insurance Group", "PO Box 329",
             "87-2200775"]


def _digital(path):
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    for x, y, size, text in LINES:
        page.insert_text((x, y), text, fontsize=size, fontname="tiro")
    doc.save(str(path))
    return path


def _scanned(path, tmp_path):
    """The same page as an image under an invisible text layer, the way an
    OCR'd scan arrives."""
    src = fitz.open(str(_digital(tmp_path / "print.pdf")))
    pix = src[0].get_pixmap(dpi=150)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, pixmap=pix)
    for x, y, size, text in LINES:
        page.insert_text((x, y), text, fontsize=size, fontname="tiro", render_mode=3)
    doc.save(str(path))
    return path


def _source(tmp_path, name, scanned=False):
    folder = tmp_path / "data" / "Markel American Insurance Company" / "ocean_marine"
    folder.mkdir(parents=True)
    pdf = folder / name
    return _scanned(pdf, tmp_path) if scanned else _digital(pdf)


@pytest.fixture(scope="module")
def schema():
    return CanonicalSchema.load("ocean_marine")


@pytest.mark.parametrize("scanned", [False, True], ids=["text-layer", "ocr-scan"])
def test_synthesize_replaces_and_labels(tmp_path, schema, scanned):
    source = _source(tmp_path, "boat.pdf", scanned)
    out = tmp_path / "out"
    out.mkdir()
    built = generic.synthesize(source, out / "boat_synth.pdf", out / "boat_synth.json",
                               schema, Values("t"), seed=1)
    assert built.ok, built.problems            # includes: no original survives
    assert fitz.open(str(built.pdf)).page_count == 1
    gold = json.loads(built.gold.read_text("utf-8"))

    number = gold["policy"]["policy_number"]["raw"]
    assert number != "MSB00001028349" and number.startswith("MSB0000")
    assert len(number) == len("MSB00001028349")          # same shape
    assert gold["named_insured"]["primary_name"]["raw"] not in ORIGINALS
    assert gold["named_insured"]["mailing_address"]["state"]["raw"] == "NY"
    assert gold["producer"]["agency_name"]["raw"].endswith("Insurance Group")
    assert gold["named_insured"]["fein"]["raw"] != "87-2200775"
    assert gold["carrier"]["company_name"]["raw"] == "Markel American Insurance Company"

    # every date moves by one offset, so the term is still a year
    eff = as_date(gold["policy"]["effective_date"]["parsed"])      # parsed as MM/DD/YYYY
    exp = as_date(gold["policy"]["expiration_date"]["parsed"])
    assert (exp - eff).days in (365, 366)
    assert eff != date(2026, 8, 26)


def test_same_value_gets_same_replacement_everywhere(tmp_path, schema):
    # the policy number in the footer carries no label; it must still change,
    # and to the same new number as the labelled one
    source = _source(tmp_path, "boat.pdf")
    out = tmp_path / "out"
    out.mkdir()
    digital = out / "_temp_b.pdf"
    import os
    os.environ["FIDEON_KEEP_DIGITAL"] = "1"
    try:
        built = generic.synthesize(source, out / "b.pdf", out / "b.json", schema, Values("t"))
    finally:
        del os.environ["FIDEON_KEEP_DIGITAL"]
    text = " ".join(fitz.open(str(digital))[0].get_text().split())
    new = json.loads(built.gold.read_text("utf-8"))["policy"]["policy_number"]["raw"]
    assert text.count(new) == 2 and "MSB00001028349" not in text


SCHEDULE = LINES[:9] + [
    (40, 230, 10, "Unit Description: 1914 FAY & BOWEN FANTAIL LAUNCH"),
    (380, 230, 10, "HIN: 327939"),
    (40, 250, 10, "TERM: 12 Months"),
    (60, 300, 10, "COVERAGE"), (260, 300, 10, "LIMIT"),
    (360, 300, 10, "DEDUCTIBLE"), (470, 300, 10, "PREMIUM"),
    (40, 314, 10, "Watercraft Liability"), (260, 314, 10, "$300,000"),
    (365, 314, 10, "$0"), (470, 314, 10, "$71"),
    (40, 328, 10, "Medical Payments"), (260, 328, 10, "$10,000"),
    (365, 328, 10, "$0"), (470, 328, 10, "$18"),
    (40, 342, 10, "Oil Pollution Liability"), (260, 342, 10, "$1,076,000"),
    (470, 342, 10, "incl."),
    (40, 420, 10, "Forms and Endorsements"),
    (40, 434, 9, "MAM5001-0407 - The Markel Boat Policy"),
    (40, 446, 9, "MAMS047-0407 - New York Amendatory Endorsement"),
    (40, 520, 10, "Location #"), (150, 520, 10, "Address"),
    (40, 534, 10, "1"), (150, 534, 10, "12 Cove Way"),
    (150, 546, 10, "Long Lake, NY 12847"),
]


def test_schedules_lists_and_plain_labels_reach_the_gold(tmp_path, schema, monkeypatch):
    # what no single label names: a unit, its coverage table, the forms list,
    # a location schedule and text that is never replaced
    monkeypatch.setattr(sys.modules[__name__], "LINES", SCHEDULE)
    source = _source(tmp_path, "boat.pdf")
    out = tmp_path / "out"
    out.mkdir()
    built = generic.synthesize(source, out / "b.pdf", out / "b.json", schema, Values("t"))
    assert built.ok, built.problems              # every value is on the page it claims
    gold = json.loads(built.gold.read_text("utf-8"))
    raw = lambda node: node["raw"]

    assert gold["document"]["document_type"]["parsed"] == "Declaration"
    assert gold["policy"]["policy_term_months"]["parsed"] == 12

    unit, = gold["watercraft"]["watercraft"]
    assert raw(unit["unit_description"]) == "1914 FAY & BOWEN FANTAIL LAUNCH"
    assert unit["year"]["parsed"] == 1914
    hin = raw(unit["hull_identification_number"])
    assert hin != "327939" and len(hin) == 6

    names = [raw(c["coverage_name"]) for c in unit["coverages"]]
    assert names == ["Watercraft Liability", "Medical Payments", "Oil Pollution Liability"]
    liability = unit["coverages"][0]
    assert raw(liability["limit_amount"]) == \
        raw(gold["watercraft"]["liability_coverages"]["bodily_injury_and_property_damage_limit"])
    assert unit["coverages"][2]["is_included"]["parsed"] == "Yes"
    assert gold["watercraft"]["liability_coverages"]["fuel_spill_liability_included"]["parsed"] == "Yes"

    forms = [raw(f["form_number"]) for f in gold["forms_and_endorsements"]]
    assert forms == ["MAM5001-0407", "MAM5047-0407"]          # the OCR's S read back as 5
    assert raw(gold["policy"]["policy_form_name"]) == "The Markel Boat Policy"

    location, = gold["locations"]
    assert raw(location["location_number"]) == "1"
    assert raw(location["address"]["line_1"]) != "12 Cove Way"

    # a value placed in a schedule is not listed again as unmapped
    assert not [u for u in gold["fideon:unmapped"] if u["kind"] == "money"]


LEADERS = LINES[:9] + [
    (48, 220, 11, "Drivers and household residents"),
    (108, 236, 10, "Delphine Calloway"),
    (108, 248, 10, "Age: 55"), (294, 248, 10, "Gender: Male"),
    (108, 260, 10, "Marital status: Married"),
    (48, 290, 11, "Outline of coverage"),
    (108, 304, 10, "2024 Viaggio by Misty Harbor 20 Lago Series"),
    (108, 316, 10, "Total Horsepower: 20"),
    (108, 328, 10, "Outboard #1"), (179, 328, 10, "Year: 2024"), (252, 328, 10, "Make: Mercury"),
    (108, 340, 10, "Trailer information"), (180, 340, 10, "Year: 2024"),
    (252, 340, 10, "Make: Venture"),
    (350, 356, 10, "Limits"), (480, 356, 10, "Deductible"), (540, 356, 10, "Premium"),
    (107, 370, 10, "Liability To Others"), (550, 370, 10, "$27"),
    (114, 382, 10, "Bodily Injury and Property Damage Liability"),
    (350, 382, 9, "$300,000 combined single limit each accident"),
    (117, 394, 10, "Includes Fuel Spill Liability"),
    (108, 408, 10, "Medical Payments ....................................................."),
    (350, 408, 10, "$5,000 each person ................................"),
    (559, 408, 10, "2"),
    (108, 422, 10, "Included with Comprehensive and Collision:"),
    (112, 434, 10, "Wreckage Removal"),
    (108, 448, 10, "Total 12 month policy premium"), (543, 448, 10, "$264"),
    (108, 460, 10, "Discount if paid in full"), (552, 460, 10, "-22"),
    (48, 490, 11, "Premium discounts"),
    (108, 504, 10, "Policy"),
    (108, 516, 10, "MSB00001028349"), (294, 516, 10, "Claim Free Renewal and Home Owner"),
]


def test_leadered_schedule_drivers_units_and_discounts(tmp_path, schema, monkeypatch):
    # a coverage summary laid out with dot leaders and no "Coverage" heading:
    # a limit on the line under its row, a note, an included list, totals and
    # discounts, and the drivers, the unit, its motor and trailer around it
    monkeypatch.setattr(sys.modules[__name__], "LINES", LEADERS)
    source = _source(tmp_path, "boat.pdf")
    out = tmp_path / "out"
    out.mkdir()
    built = generic.synthesize(source, out / "b.pdf", out / "b.json", schema, Values("t"))
    assert built.ok, built.problems
    gold = json.loads(built.gold.read_text("utf-8"))
    raw = lambda node: node["raw"]
    block = gold["watercraft"]

    driver, = block["operators"]
    assert raw(driver["name"]) == raw(gold["named_insured"]["primary_name"])
    assert driver["age"]["parsed"] == 55 and raw(driver["gender"]) == "Male"

    unit, = block["watercraft"]
    assert raw(unit["unit_description"]).endswith("20 Lago Series") and unit["year"]["parsed"] == 2024
    assert raw(unit["total_horsepower"]) == "20"
    assert raw(unit["motors"][0]["make"]) == "Mercury" and raw(unit["motors"][0]["motor_number"]) == "1"
    assert raw(unit["trailer"]["make"]) == "Venture"

    names = [raw(c["coverage_name"]) for c in unit["coverages"]]
    assert names == ["Liability To Others", "Medical Payments", "Wreckage Removal"]
    liability, medical, wreck = unit["coverages"]
    assert raw(liability["limit_amount"]) == \
        raw(block["liability_coverages"]["bodily_injury_and_property_damage_limit"])
    assert raw(liability["limit_basis"]) == "combined single limit each accident"
    assert raw(liability["coverage_description"]) == "Bodily Injury and Property Damage Liability"
    assert block["liability_coverages"]["fuel_spill_liability_included"]["parsed"] == "Yes"
    assert raw(medical["premium"]) == "2" and raw(medical["limit_basis"]) == "each person"
    assert wreck["is_included"]["parsed"] == "Yes"

    assert "total_policy_premium" in gold["premium"]
    discounts = {raw(d["description"]): d for d in gold["premium"]["discounts_and_credits"]}
    assert discounts["Discount if paid in full"]["amount"]["parsed"] == -22
    assert {"Claim Free Renewal", "Home Owner"} <= set(discounts)


RENEWAL = LINES[:9] + [
    (48, 230, 10, "Your current policy period ends May 23, 2026 at 12:01 a.m. The renewal is"),
    (48, 242, 10, "for the period May 23, 2026 through May 23,"),
    (48, 254, 10, "2027. Your 12-month policy premium is $264.00."),
    (48, 290, 11, "Your Payment Schedule"),
    (55, 306, 8, "Date"), (128, 306, 8, "Amount**"), (174, 306, 8, "Date"), (247, 306, 8, "Amount**"),
    (55, 318, 7.5, "May 23, 2026"), (133, 318, 7.5, "$71.00"),
    (174, 318, 7.5, "Jul 23, 2026"), (252, 318, 7.5, "$71.00"),
    (55, 330, 7.5, "Jun 23, 2026"), (133, 330, 7.5, "$71.00"),
    (174, 330, 7.5, "Aug 23, 2026"), (252, 330, 7.5, "$71.00"),
    # the rule under each row is a line of dots, set a little lower
    (55, 321, 8, "." * 40), (174, 321, 8, "." * 40),
    (55, 333, 8, "." * 40), (174, 333, 8, "." * 40),
    (46, 350, 7, "**An installment fee of $5.00 per installment is included."),
    # a coupon's scan line: the policy number and the amount inside it
    (87, 600, 10, "030800001028349131055 0007100 0026900 5000693"),
]


def test_wrapped_dates_ruled_schedules_and_scan_lines_leave_nothing(tmp_path, schema, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "LINES", RENEWAL)
    monkeypatch.setenv("FIDEON_KEEP_DIGITAL", "1")
    source = _source(tmp_path, "renewal.pdf")
    out = tmp_path / "out"
    out.mkdir()
    built = generic.synthesize(source, out / "r.pdf", out / "r.json", schema, Values("t"))
    assert built.ok, built.problems
    text = " ".join(p.get_text() for p in fitz.open(str(out / "_temp_r.pdf")))
    for original in ("May 23", "Jun 23", "Jul 23", "Aug 23", "00001028349"):
        assert original not in text
    gold = json.loads(built.gold.read_text("utf-8"))
    policy = re.sub(r"\D", "", gold["policy"]["policy_number"]["raw"])
    assert policy in re.sub(r"\s", "", text)          # the scan line carries the new number

    # amounts are kept, so the schedule still adds up to what it says
    assert "$264.00" in text and text.count("$71.00") == 4
    plan = gold["billing"]["installments"]
    dues = [as_date(row["due_date"]["parsed"]) for row in plan]
    assert len(dues) == 4 and dues == sorted(dues)
    assert [row["installment_number"]["parsed"] for row in plan] == [1, 2, 3, 4]


def test_printed_prose_reaches_the_gold_as_text_sections(tmp_path, schema):
    # a bold heading over a paragraph whose last line is one word, and a
    # sentence carrying a replaced date: the gold holds the words as printed
    folder = tmp_path / "data" / "Markel American Insurance Company" / "ocean_marine"
    folder.mkdir(parents=True)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    for x, y, size, text in LINES:
        page.insert_text((x, y), text, fontsize=size, fontname="tiro")
    page.insert_text((48, 400), "Deductibles", fontsize=11, fontname="hebo")
    page.insert_text((60, 416), "All physical damage losses, regardless of loss settlement option and",
                     fontsize=10, fontname="helv")
    page.insert_text((60, 428), "whether partial or total, are subject to the applicable",
                     fontsize=10, fontname="helv")
    page.insert_text((60, 440), "deductible.", fontsize=10, fontname="helv")
    page.insert_text((60, 470), "Your coverage begins on 08/26/2026 at 12:01 a.m. at the address shown.",
                     fontsize=10, fontname="helv")
    for x, y, text in ((60, 520, "- Pay a bill"), (260, 520, "- Update your policy"),
                       (60, 534, "- Report a claim"), (260, 534, "- Check recalls")):
        page.insert_text((x, y), text, fontsize=10, fontname="helv")
    page.insert_text((60, 580), "Watercraft and Equipment Value Total Agreed Amount: $19,000",
                     fontsize=10, fontname="helv")
    doc.save(str(folder / "prose.pdf"))
    out = tmp_path / "out"
    out.mkdir()
    built = generic.synthesize(folder / "prose.pdf", out / "p.pdf", out / "p.json", schema, Values("t"))
    assert built.ok, built.problems
    sections = list(json.loads(built.gold.read_text("utf-8"))["text_sections"].values())
    deductibles, = [s for s in sections if s["section_title"] == "Deductibles"]
    assert deductibles["raw_text"].endswith("subject to the applicable deductible.")
    assert deductibles["page_range"] == [1]
    begins, = [s for s in sections if s["raw_text"].startswith("Your coverage begins on")]
    assert "08/26/2026" not in begins["raw_text"]         # the replaced date, not the original
    # a list set in two columns is one section; a "Label: value" row is no prose
    listed, = [s for s in sections if s["section_type"] == "other"]
    assert listed["raw_text"] == "Pay a bill; Update your policy; Report a claim; Check recalls"
    assert not any(s["raw_text"].startswith("Watercraft and Equipment Value") for s in sections)


def test_facts_a_page_states_in_sentences_and_footers(tmp_path, schema):
    folder = tmp_path / "data" / "Progressive" / "ocean_marine"
    folder.mkdir(parents=True)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    for x, y, size, text in LINES[:9] + [
            (48, 250, 10, "This renewal offer is for the policy period 08/26/2026 through 08/26/2027."),
            (48, 266, 10, "Your current policy period ends 08/26/2026 at 12:01 a.m."),
            (48, 282, 10, "Changes: The Automatic Card Payments (ACP) discount has been removed from your"),
            (48, 294, 10, "policy."),
            (48, 310, 10, "Manage your policy at progressiveagent.com or call us."),
            (48, 760, 8, "Form A016 (07/19)")]:
        page.insert_text((x, y), text, fontsize=size, fontname="helv")
    doc.save(str(folder / "facts.pdf"))
    out = tmp_path / "out"
    out.mkdir()
    built = generic.synthesize(folder / "facts.pdf", out / "f.pdf", out / "f.json", schema, Values("t"))
    assert built.ok, built.problems
    gold = json.loads(built.gold.read_text("utf-8"))
    offer = gold["document_type_detail"]["renewal_offer"]
    start, end = offer["renewal_effective_date"]["parsed"], offer["renewal_expiration_date"]["parsed"]
    assert as_date(start) < as_date(end) and start != "08/26/2026"    # replaced, and in order
    assert offer["expiring_policy_expiration_date"]["parsed"] == start
    change, = gold["document_type_detail"]["policy_change"]["changes"]
    assert change["change_description"]["raw"].endswith("has been removed from your policy.")
    assert gold["carrier"]["contact"]["website"]["raw"] == "progressiveagent.com"
    assert "A016" in [f["form_number"]["raw"] for f in gold["forms_and_endorsements"]]


def _image_only(path, tmp_path, layer_lines=()):
    """The page as a picture, with an invisible OCR layer holding only
    ``layer_lines`` - none for a pure image scan."""
    src = fitz.open(str(_digital(tmp_path / "print.pdf")))
    pix = src[0].get_pixmap(dpi=200)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, pixmap=pix)
    for x, y, size, text in layer_lines:
        page.insert_text((x, y), text, fontsize=size, fontname="tiro", render_mode=3)
    doc.save(str(path))
    return path


def _ocr_source(tmp_path, layer_lines=()):
    pytest.importorskip("rapidocr_onnxruntime")
    folder = tmp_path / "data" / "Markel American Insurance Company" / "ocean_marine"
    folder.mkdir(parents=True)
    return _image_only(folder / "boat.pdf", tmp_path, layer_lines)


def test_an_image_only_scan_is_read_by_ocr(tmp_path, schema):
    # no text layer at all: without reading the image nothing would be
    # replaced, and the original insured would ship in the synthetic copy
    source = _ocr_source(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    built = generic.synthesize(source, out / "b.pdf", out / "b.json", schema, Values("t"))
    assert built.ok, built.problems
    gold = json.loads(built.gold.read_text("utf-8"))
    assert gold["fideon:provenance"]["text_recovered_by_ocr"] > 5
    number = gold["policy"]["policy_number"]["raw"]
    assert number.startswith("MSB0000") and number != "MSB00001028349"
    assert gold["named_insured"]["primary_name"]["raw"] not in ORIGINALS


def test_a_line_the_scan_layer_left_out_is_recovered(tmp_path, schema):
    # the scanner's OCR kept every line but the FEIN; it is printed, so it
    # is replaced and reaches the gold all the same
    kept = [line for line in LINES if "FEIN" not in line[3]]
    source = _ocr_source(tmp_path, kept)
    out = tmp_path / "out"
    out.mkdir()
    built = generic.synthesize(source, out / "b.pdf", out / "b.json", schema, Values("t"))
    assert built.ok, built.problems
    gold = json.loads(built.gold.read_text("utf-8"))
    fein = gold["named_insured"]["fein"]["raw"]
    assert re.fullmatch(r"\d{2}-\d{7}", fein) and fein != "87-2200775"


def test_calibrate_recovers_a_flipped_text_layer(tmp_path):
    # a printed web page can carry its OCR layer flipped and scaled against
    # the drawing; every position depends on putting it back
    src = fitz.open(str(_digital(tmp_path / "print.pdf")))
    pix = src[0].get_pixmap(dpi=150)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, pixmap=pix)
    inverse = ~fitz.Matrix(1.3, 0, 0, -1.3, 0, 790)
    for x, y, size, text in LINES:
        p = fitz.Point(x, y) * inverse
        page.insert_text(p, text, fontsize=size / 1.3, fontname="tiro", render_mode=3,
                         morph=(p, fitz.Matrix(1, 0, 0, -1, 0, 0)))
    matrix = overlay.calibrate(page, overlay.Ink(page))
    assert matrix.a == pytest.approx(1.3, abs=0.03)
    assert matrix.d == pytest.approx(-1.3, abs=0.03)


def test_value_shapes():
    found = {kind for kind, rx in generic.PATTERNS for s in [
        "customer209@example.com", "(315) 555-0142", "87-2200775", "PO Box 329",
        "Lake Forest, IL 60045", "506 WASHINGTON RD.", "08/26/2026", "Dec 23, 2025",
        "$1,076,000", "MSB00001028349"] if rx.fullmatch(s)}
    assert found >= {"email", "phone", "fein", "pobox", "cityline", "street",
                     "date", "money", "id"}
    # a form keeps its number; a street word is not part of a city
    assert generic.FORM_NUMBER.match("MAM5001-0407")
    assert generic.PATTERNS[4][1].search("175 Atlantic Ave Boston, MA 02111").group(1) == "Boston"


def test_headings_are_not_names():
    assert generic._looks_like_name("Delphine Calloway")
    assert generic._looks_like_name("Patriotic Insurance Group")
    assert not generic._looks_like_name("VEHICLE FOR PRODUCTION")
    assert not generic._looks_like_name("Watercraft & Equipment, Agreed Value")
    assert not generic._looks_like_name("NAMED INSURED(S)")      # a label, not a person
    assert not generic._looks_like_name("Your Agent")


def test_amounts_dates_and_one_identifier_printed_two_ways():
    money = next(rx for kind, rx in generic.PATTERNS if kind == "money")
    assert money.match("$22.00, plus you").group(0) == "$22.00"
    assert money.match("$1,076,000").group(0) == "$1,076,000"
    assert any(rx.fullmatch("08-04-2026") for kind, rx in generic.PATTERNS if kind == "date")

    faker = generic.Faker(Values(4))
    shift = faker._date("08-04-2026")
    assert re.fullmatch(r"\d{2}-\d{2}-\d{4}", shift) and shift != "08-04-2026"
    # "884806529 908 9" and "type in your policy number 8848065299089"
    cell = overlay.Cell("884806529 908 9 8848065299089", [None] * 29, 0, 0)
    spaced = faker(generic.Found("digits", cell, 0, 15))
    joined = faker(generic.Found("digits", cell, 16, 29))
    assert spaced.count(" ") == 2 and spaced.replace(" ", "") == joined != "8848065299089"


def test_rules_that_hold_for_any_document(schema):
    from fideon_synth import structure, prose
    # an operator the page calls "Named insured" is one
    gold = {"named_insured": {"primary_name": generic.fv("Clementine Crowthorne")},
            "watercraft": {"operators": [
                {"name": generic.fv("Clementine Crowthorne"), "relationship_to_insured": generic.fv("Named insured")},
                {"name": generic.fv("Marguerite Everly"), "relationship_to_insured": generic.fv("Named insured")},
                {"name": generic.fv("Tom Everly"), "relationship_to_insured": generic.fv("Son")}]}}
    structure.finish(gold, schema)
    assert [e["name"]["raw"] for e in gold["named_insured"]["additional_named_insureds"]] == ["Marguerite Everly"]
    # where a period ends, and its time - "A.M." may have wrapped to the next line
    assert structure.EXPIRES_AT.search("This policy period ends on 02/25/2027 at 12:01 a.m.").group(1) == "12:01 a.m."
    assert structure.EXPIRES_AT.search("STANDARD TIME to May 6, 2027 at 12:01").group(1) == "12:01"
    # an ISO form number is a form's, never an identifier to replace
    assert generic.ISO_FORM.match("CG20180413") and generic.ISO_FORM.match("CG 20 18 04 13")
    assert not generic.ISO_FORM.match("MSB00001028349")
    # words OCR ran together come apart only into words the document prints
    vocab = generic._vocabulary("combined single limit each accident Liability To Others "
                                "Liability to progressive agent")
    assert generic._unglue("combinedsinglelimiteachaccident", vocab) == "combined single limit each accident"
    assert generic._unglue("LiabilityTo Others", vocab) == "Liability To Others"
    assert generic._unglue("progressiveagent.com", vocab) == "progressiveagent.com"   # an address
    assert generic._unglue("Progressiveagent", vocab) == "Progressiveagent"           # maybe a name
    # a policy-wide value the units print differently is dropped
    gold = {"watercraft": {"physical_damage_coverages": {"personal_effects_limit": generic.fv("$3,000"),
                                                         "on_water_towing_limit": generic.fv("$1,000")},
                           "watercraft": [{"personal_effects_limit": generic.fv("$3,000")},
                                          {"personal_effects_limit": generic.fv("$5,000")}]}}
    structure.finish(gold, schema)
    assert list(gold["watercraft"]["physical_damage_coverages"]) == ["on_water_towing_limit"]
    # a form number keeps its state code
    assert structure._form_of(structure.FORM_REF.search("BY-300 NY (11-23)")) == "BY-300 NY"
    # rows of labels and address lines are not prose; a short sentence is
    line = lambda text: prose.Line(0, 10, 0, text, False, False, [(0, text)])
    assert not line("Outboard #1 Year: 2026 Make: Yamaha Horsepower: 150").prose()
    assert not line("One Tower Square, Hartford, CT 06183").prose()
    assert line("Enclosed are your policy documents.").prose()


def test_a_date_shift_never_lands_one_original_date_on_another():
    faker = generic.Faker(Values(5))
    faker.days = 122                                   # April 9 -> August 9
    faker.avoid(["April 9, 2026", "August 9, 2026"])
    assert faker.days != 122


def test_copies_the_layout_hides_are_replaced_too(tmp_path, schema):
    # a policy number printed spaced in a header, a date stamped up the margin,
    # an agency name wrapped onto "AGENCY LLC", and a heading the document
    # also uses in lower case - which is no one's name
    folder = tmp_path / "data" / "Markel American Insurance Company" / "ocean_marine"
    folder.mkdir(parents=True)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    for x, y, size, text in LINES + [
            (40, 330, 10, "Account Number: 7382910455"), (400, 40, 9, "73 82 91 04 55"),
            (300, 260, 10, "Stable Rock Insurance"), (300, 272, 10, "AGENCY LLC"),
            (300, 284, 10, "12 Mill Rd"), (300, 296, 10, "Utica, NY 13501"),
            (40, 360, 10, "Residence Premises"),
            (40, 380, 10, "Coverage applies on the residence premises only.")]:
        page.insert_text((x, y), text, fontsize=size, fontname="helv")
    page.insert_text((590, 300), "08/26/2026", fontsize=7, fontname="helv", rotate=90)
    doc.save(str(folder / "hidden.pdf"))
    out = tmp_path / "out"
    out.mkdir()
    built = generic.synthesize(folder / "hidden.pdf", out / "h.pdf", out / "h.json", schema, Values("t"))
    assert built.ok, built.problems
    gold = built.gold.read_text("utf-8")
    assert "Residence Premises" not in json.loads(gold)["named_insured"]["primary_name"]["raw"]


def test_a_model_number_ends_the_make():
    from fideon_synth import structure
    unit = {"unit_description": generic.fv("2015 Correct Craft/Nautique 200 Sport Nautique")}
    structure.Reader._make_model(None, unit)
    assert unit["make"]["raw"] == "Correct Craft/Nautique" and unit["model"]["raw"] == "200 Sport Nautique"
    unit = {"unit_description": generic.fv("1914 FAY & BOWEN FANTAIL LAUNCH")}
    structure.Reader._make_model(None, unit)
    assert unit["make"]["raw"] == "FAY & BOWEN"


def test_labels_match_schema_fields(schema):
    index = generic.label_index(schema)
    def match(label, kind):
        return generic.match_label(generic._norm_label(label), kind, index)
    assert match("Policy Number:", "id") == "policy.policy_number"
    assert match("Effective Date/Transaction:", "date") == "policy.effective_date"
    assert match("TRANSACTION EFFECTIVE DATE:", "date") == "document.transaction_effective_date"
    assert match("TOTAL ANNUAL PREMIUM:", "money") == "premium.total_policy_premium"
    # a label that names a field of the wrong kind is not a match
    assert match("Policy Number:", "money") is None


def test_parsed_dates_must_be_month_day_year(schema):
    # the schema declares the form; a date parsed any other way is reported
    from fideon_synth.fields import fv
    good = {"policy": {"effective_date": fv("May 6, 2026", "05/06/2026")},
            "forms_and_endorsements": [{"edition_date": fv("04/07")}]}   # no day: exempt
    bad = {"policy": {"effective_date": fv("May 6, 2026", "2026-05-06")}}
    assert schema.format_errors(good) == []
    assert schema.format_errors(bad) == [
        "parsed date '2026-05-06' is not MM/DD/YYYY at policy.effective_date"]


def test_faker_keeps_formats_and_is_consistent():
    faker = generic.Faker(Values(3))
    cell = overlay.Cell("08/26/2026 8/1/26 2026-08-26", [None] * 28, 0, 0)
    a = faker(generic.Found("date", cell, 0, 10))
    b = faker(generic.Found("date", cell, 11, 17))
    c = faker(generic.Found("date", cell, 18, 28))
    assert len(a) == 10 and a.count("/") == 2
    assert len(b.split("/")[2]) == 2
    assert c[4] == "-" and c == date.fromisoformat(c).isoformat()
    again = faker(generic.Found("date", cell, 0, 10))
    assert again == a
