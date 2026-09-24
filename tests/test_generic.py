"""
Tests for the generic generator (fideon_synth.generic / overlay).

The sources are built here rather than read from Data/, so the tests run on
any checkout: one declarations page with a real text layer, and the same page
as a scan with an invisible OCR layer - the two kinds the corpus holds.
"""

from __future__ import annotations

import json
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
