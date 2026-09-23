"""
Tests for fideon-synth.

The build itself runs four checks on every document, so these do not repeat
them. What they cover is the machinery underneath - the places where a bug
would make those four checks pass while being wrong.
"""

from __future__ import annotations

import json

import pytest

from fideon_synth import CanonicalSchema, Corpus, Values, fields, scan
from fideon_synth.fields import (NO_EVIDENCE, as_number, derived, fmt_money,
                                 fv, money_from, walk, yes_no)
from fideon_synth.forms import by_key, catalogue
from fideon_synth.forms.leatherstocking_dwelling_fire import (
    LeatherstockingDwellingFire, parse_forms, totals)
from fideon_synth.pageref import on_page

pytestmark = pytest.mark.filterwarnings("ignore")


# ── field values ────────────────────────────────────────────────────────────

def test_printed_and_derived_carry_different_sources():
    assert fv("Frame")["confidence"]["source"] == "deterministic"
    assert derived("Individual", "Hollis Brackenridge")["confidence"][
        "source"] == "structural"


def test_yes_no_never_emits_a_json_boolean():
    # the schema's `parsed` admits string, number or null - a boolean here
    # validates on some drafts and not others, which is worse than failing
    assert yes_no(True, "New Policy")["parsed"] == "Yes"
    assert yes_no(False, "New Policy")["parsed"] == "No"


@pytest.mark.parametrize("raw,expected", [
    ("$425,000", 425000.0), ("$742.00", 742.0), ("-$5.00", -5.0),
    ("($12.50)", -12.5), ("***", None), ("", None), ("Included", None),
    ("N/A", None), (None, None), ("not money", None),
])
def test_as_number_reads_printed_amounts(raw, expected):
    assert as_number(raw) == expected


def test_no_limit_notation_is_not_zero():
    """*** means "no separate limit applies", not nothing.

    Zero would sum into a total and be wrong by exactly the amount nobody
    notices.
    """
    assert as_number("***") is None


def test_money_prints_the_sign_outside():
    assert fmt_money(-5.0) == "-$5.00"
    assert fmt_money(1167.0) == "$1,167.00"
    assert money_from(-5.0)["parsed"] == -5.0


def test_walk_collapses_list_indices():
    doc = {"coverages": [{"limit": fv("$1")}, {"limit": fv("$2")}]}
    assert {p for p, _ in walk(doc)} == {"coverages[].limit"}


# ── page references ─────────────────────────────────────────────────────────

def test_page_match_is_token_bounded():
    """A bare substring test finds "NY" inside "Company" and "en" inside
    "Residence". Both resolve to a page and neither means anything."""
    assert not on_page("ny", "leatherstocking cooperative insurance company")
    assert not on_page("en", "coverage a - residence")
    assert on_page("ny", "cooperstown, ny 13326")


def test_amounts_and_dates_still_match():
    text = "coverage a - residence $425,000 $1,584.00 03/18/2026"
    assert on_page("$425,000", text)
    assert on_page("$1,584.00", text)
    assert on_page("03/18/2026", text)


# ── schema ──────────────────────────────────────────────────────────────────

def test_schema_merges_common_into_the_line_file():
    schema = CanonicalSchema.load("dwelling_fire")
    assert "dwelling_fire" in schema.merged["properties"]   # line-specific
    assert "carrier" in schema.merged["properties"]         # from _common
    assert schema.mandatory == ["carrier", "named_insured", "policy"]


def test_absent_list_names_what_is_not_stated():
    schema = CanonicalSchema.load("dwelling_fire")
    absent = schema.absent_from({"policy.policy_number"})
    assert "policy.policy_number" not in absent
    assert "policy.cancellation_reason" in absent


def test_missing_line_of_business_says_what_is_available():
    with pytest.raises(FileNotFoundError, match="Available:"):
        CanonicalSchema.load("not_a_real_lob")


# ── the worked example ──────────────────────────────────────────────────────

def test_hand_written_schedules_all_tie():
    for variant in LeatherstockingDwellingFire().variants():
        t = totals(variant)
        assert abs(sum(p for _, p in t["rows"]) - t["property_total"]) < 0.01
        assert abs(t["property_total"] + t["fees"] - t["total"]) < 0.01


def test_forms_paragraph_round_trips():
    text = ("FL-52A (12/98) Trampoline Exclusion, FL-21 05/10 Suit Against "
            "Us Amendatory Endorsement, ML-WD (1.1) Water Damage-Sewers and "
            "Drains, LCIC-DX (06/23) Exclusion of Canine Related Injuries "
            "or Damages")
    parsed = parse_forms(text)
    assert [f["form_number"]["raw"] for f in parsed] == [
        "FL-52A", "FL-21", "ML-WD", "LCIC-DX"]
    assert parsed[1]["edition_date"]["raw"] == "05/10"     # no parentheses
    assert parsed[3]["form_title"]["raw"].endswith("Injuries or Damages")


def test_a_title_containing_a_comma_is_not_split_in_two():
    """"Exclusion of Canine Related Injuries or Damages" survives; so does a
    title that genuinely contains a comma."""
    parsed = parse_forms("SM-26 (7/00) Automatic Increase, RC, "
                         "FL-80 (7/96) Redefinition of Insured")
    assert len(parsed) == 2
    assert parsed[0]["form_title"]["raw"] == "Automatic Increase, RC"


# ── generated values ────────────────────────────────────────────────────────

def test_same_seed_gives_the_same_values_across_processes():
    """str.__hash__ is salted per process, so a generator seeded with it
    makes "reproducible" mean "within this run"."""
    assert Values("abc")._stable("abc") == Values("abc")._stable("abc")
    a = [Values(4).person() for _ in range(5)]
    b = [Values(4).person() for _ in range(5)]
    assert a == b


def test_policy_number_patterns():
    v = Values(1)
    assert v.policy_number("10-{year}-{5d}", year=2026).startswith("10-2026-")
    assert len(v.policy_number("10-{year}-{5d}", year=2026)) == len(
        "10-2026-00000")
    with pytest.raises(ValueError, match="Unknown token"):
        v.policy_number("{nonsense}")


def test_term_uses_anniversary_dating_not_365_days():
    """A policy written on 29 February expires on 28 February. Adding a fixed
    number of days produces a date no carrier system would print."""
    import datetime as dt
    for seed in range(40):
        start, end = Values(seed).term()
        s = dt.datetime.strptime(start, "%m/%d/%Y")
        e = dt.datetime.strptime(end, "%m/%d/%Y")
        assert (e.year - s.year) * 12 + (e.month - s.month) == 12
        assert e.day in (s.day, s.day - 1, s.day - 2)


def test_household_shares_a_surname():
    names = Values(9).household(3)
    assert len({n.split()[-1] for n in names}) == 1


# ── scanner profiles ────────────────────────────────────────────────────────

def test_every_profile_has_a_distinct_key():
    keys = [p.key for p in scan.PROFILES]
    assert len(keys) == len(set(keys))


def test_unknown_profile_lists_the_real_ones():
    with pytest.raises(KeyError, match="office_flatbed"):
        scan.by_key("nope")


# ── end to end ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("corpus")
    corpus = Corpus(LeatherstockingDwellingFire(), out)
    return corpus, corpus.build(count=2)


def test_a_small_corpus_passes_every_check(built):
    _, report = built
    assert report.ok, report.summary()
    assert len(report.documents) == 2


def test_gold_has_no_private_keys_left(built):
    corpus, report = built
    doc = json.loads(report.documents[0].gold.read_text("utf-8"))
    assert all("_evidence" not in field for _, field in walk(doc))


def test_page_refs_point_at_real_pages(built):
    corpus, report = built
    doc = json.loads(report.documents[0].gold.read_text("utf-8"))
    pages = report.documents[0].pages
    printed = [f for _, f in walk(doc)
               if f["confidence"]["source"] == "deterministic"]
    assert printed, "nothing was marked as printed"
    for field in printed:
        assert field["page_ref"], field["raw"]
        assert max(field["page_ref"]) <= pages

    # the footer repeats the policy number, so it is on every page
    assert doc["policy"]["policy_number"]["page_ref"] == list(
        range(1, pages + 1))


def test_scanned_twin_has_no_text_layer(built):
    import fitz
    fitz.TOOLS.mupdf_display_errors(False)
    _, report = built
    for document in report.documents:
        pdf = fitz.open(str(document.scanned))
        assert sum(len(p.get_text("words")) for p in pdf) == 0
        pdf.close()


def test_scanned_gold_says_where_its_page_refs_came_from(built):
    _, report = built
    gold = json.loads(report.documents[0].scanned_gold.read_text("utf-8"))
    provenance = gold["fideon:provenance"]
    assert provenance["render"] == "scanned"
    assert provenance["page_refs_measured_on"].endswith(".pdf")
    assert provenance["scan_profile"]


def test_gold_does_not_assert_what_the_page_never_prints(built):
    """Two fields that were wrong before the page-ref check caught them: a
    renewal's prior policy number, and the kind of fee behind a line the
    form labels only "Fees"."""
    _, report = built
    doc = json.loads(report.documents[0].gold.read_text("utf-8"))
    assert "prior_policy_number" not in doc["policy"]
    assert "policy_fee" not in doc["premium"]


def test_the_audit_rule_actually_fails_when_it_should():
    """A check that cannot fail is not a check."""
    template = LeatherstockingDwellingFire()
    doc = {"coverages": [{"premium": fv("$100.00")}],
           "premium": {"total_policy_premium": fv("$250.00")}}
    assert template.audit(doc)
    doc["premium"]["total_policy_premium"] = fv("$100.00")
    assert not template.audit(doc)


def test_registry_round_trips():
    assert by_key("leatherstocking_dwelling_fire").lob == "dwelling_fire"
    assert catalogue()
    with pytest.raises(KeyError, match="leatherstocking"):
        by_key("nope")
