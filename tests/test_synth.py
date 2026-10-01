"""
Tests for fideon-synth's reusable infrastructure - field values, page
references, schema loading, seeded value generation, scanner profiles.

The engine itself (any source PDF in, synthetic digital twin + gold out) is
covered in test_generic.py. The declarative per-carrier Corpus/Template
system these tests used to also cover (fideon_synth.forms,
fideon_synth.dfire) was removed: the generic engine already handles every
line of business, dwelling_fire included, with no per-carrier code.
"""

from __future__ import annotations

import pytest

from fideon_synth import CanonicalSchema, Values, scan
from fideon_synth.fields import (as_number, derived, fmt_money, fv,
                                 money_from, walk, yes_no)
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


def test_schema_is_cached_by_file_and_mtime():
    # repeat loads of the same schema file return the same object - and the
    # label index built from it - rather than re-reading and re-walking it
    from fideon_synth import generator
    a = CanonicalSchema.load("dwelling_fire")
    b = CanonicalSchema.load("dwelling_fire")
    assert a is b
    assert generator.label_index(a) is generator.label_index(b)


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
# scan.py's degradation profiles are no longer used by the generic engine
# (the output stays digital), but remain for anything that still wants a
# scanned-look render - kept correct, independent of the engine.

def test_every_profile_has_a_distinct_key():
    keys = [p.key for p in scan.PROFILES]
    assert len(keys) == len(set(keys))


def test_unknown_profile_lists_the_real_ones():
    with pytest.raises(KeyError, match="office_flatbed"):
        scan.by_key("nope")
