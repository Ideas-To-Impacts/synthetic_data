"""
FieldValue: the leaf shape every canonical gold file is made of.

``_common.json`` defines it and every line-specific schema inherits it, so
this module is the one place that knows what a leaf looks like:

    {"raw": "$425,000", "parsed": 425000.0,
     "confidence": {"score": 1.0, "source": "deterministic"},
     "page_ref": [1], "flagged": false}

The distinction that matters here is ``deterministic`` versus ``structural``.
A value printed on the page is deterministic - it can be quoted. A value the
document only implies is structural: ``entity_type: "Individual"`` is nowhere
on a page that simply names two people, and a twelve-month term is the gap
between two printed dates. Marking those deterministic would tell a harness
they are quotable when they are not, and every extractor scored against them
would look worse than it is.

Use :func:`fv` for the first kind and :func:`derived` for the second.
"""

from __future__ import annotations

from datetime import datetime

#: Marker for a value that has no supporting text anywhere on the page - file
#: metadata, essentially. Distinct from "look for the raw value", which is
#: what ``evidence=None`` means.
NO_EVIDENCE = object()

_SENTINEL = "__same__"
_REQUIRED = {"raw", "parsed", "page_ref", "flagged"}


def fv(raw, parsed=_SENTINEL, evidence=None, score=1.0):
    """A FieldValue for something the document prints.

    ``evidence`` is the text to search for when resolving the page reference.
    Give it only when the value is stored in a different shape than it is
    printed - a page count stored as ``"2"`` but printed as ``"Page 1 of 2"``.
    """
    if parsed is _SENTINEL:
        parsed = raw
    return {
        "raw": raw,
        "parsed": parsed,
        "confidence": {"score": score, "source": "deterministic"},
        "page_ref": [],
        "flagged": False,
        "_evidence": raw if evidence is None else evidence,
    }


def derived(raw, evidence=NO_EVIDENCE, parsed=_SENTINEL, score=1.0):
    """A FieldValue for something the document implies but never prints.

    Pass the printed text it was read from as ``evidence`` so the page
    reference still points somewhere real. Pass nothing when there is no
    supporting text at all, as for a source filename.
    """
    f = fv(raw, parsed, evidence, score)
    f["confidence"]["source"] = "structural"
    return f


def is_field(node) -> bool:
    """Is this dict a FieldValue rather than a nesting level?"""
    return isinstance(node, dict) and _REQUIRED <= set(node)


def walk(doc, path=""):
    """Yield ``(dotted_path, field)`` for every FieldValue in a gold document.

    List indices collapse to ``[]`` so paths line up with schema leaf paths:
    ``coverages[].premium``, not ``coverages[3].premium``.
    """
    if is_field(doc):
        yield path, doc
    elif isinstance(doc, dict):
        for key, val in doc.items():
            yield from walk(val, f"{path}.{key}" if path else key)
    elif isinstance(doc, list):
        for val in doc:
            yield from walk(val, path + "[]")


def walk_indexed(doc, path=""):
    """Like :func:`walk`, but keeping list indices - for error messages."""
    if is_field(doc):
        yield path, doc
    elif isinstance(doc, dict):
        for key, val in doc.items():
            yield from walk_indexed(val, f"{path}.{key}" if path else key)
    elif isinstance(doc, list):
        for i, val in enumerate(doc):
            yield from walk_indexed(val, "%s[%d]" % (path, i))


# ── typed helpers ───────────────────────────────────────────────────────────

def as_number(raw):
    """A printed money or limit string as a number.

    Carrier notations for "no separate limit applies" - ``***``, a bare dash,
    an empty cell - are not numbers and come back ``None`` rather than zero.
    A zero would sum into a total and be wrong by exactly the amount nobody
    notices.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if text in ("***", "", "-", "N/A", "Incl.", "Included"):
        return None
    cleaned = text.replace("$", "").replace(",", "").strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    if cleaned.startswith("-"):
        negative = True
        cleaned = cleaned[1:]
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -value if negative else value


def fmt_money(value):
    """Print a number the way a declarations page does: ``-$5.00``, not
    ``$-5.00``. The sign goes outside."""
    return "%s$%s" % ("-" if value < 0 else "", format(abs(value), ",.2f"))


def money(raw, evidence=None):
    """A FieldValue whose ``parsed`` is the number behind the printed text."""
    return fv(raw, as_number(raw), evidence)


def money_from(value, evidence=None):
    """A money FieldValue built from a number rather than a printed string."""
    return money(fmt_money(value), evidence)


def date_fv(printed, fmt="%m/%d/%Y", evidence=None):
    """A date FieldValue: ``raw`` as printed, ``parsed`` as ISO."""
    iso = datetime.strptime(printed, fmt).strftime("%Y-%m-%d")
    return fv(printed, iso, evidence)


def yes_no(flag, evidence):
    """A boolean, as the schema can carry one.

    ``parsed`` admits string, number or null - never a JSON boolean - so this
    is "Yes"/"No". It is always :func:`derived`: a page prints "New Policy",
    never "No".
    """
    return derived("Yes" if flag else "No", evidence)


def strip_evidence(doc):
    """Remove the private ``_evidence`` keys before a document is written."""
    for _, field in walk(doc):
        field.pop("_evidence", None)
    return doc
