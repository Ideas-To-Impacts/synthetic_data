"""
Tests for the generic generator (fideon_synth.generic / overlay).

The sources are built here rather than read from Data/, so the tests run on
any checkout: one declarations page with a real text layer, and the same page
as a scan with an invisible OCR layer - the two kinds the corpus holds.
"""

from __future__ import annotations

import json
import sys
from datetime import date

import fitz
import pytest

from fideon_synth import CanonicalSchema, Values, generic, overlay

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
    eff = date.fromisoformat(gold["policy"]["effective_date"]["parsed"])
    exp = date.fromisoformat(gold["policy"]["expiration_date"]["parsed"])
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
