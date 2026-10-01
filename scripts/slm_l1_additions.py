#!/usr/bin/env python3
"""
Additions carried over from the SLM L1 copy of the policy_check schemas.

``E:\\SML\\SLM L1\\config\\canonical_schema\\policy_check`` - the pipeline these
gold files feed, and a fallback location in ``fideon_synth/schema.py`` - grew
its own extensions while this repo grew others. This module applies the SLM L1
ones that this repo lacked to every file in ``config/policy_check``, so a
regenerated base schema comes back with them:

    python scripts/slm_l1_additions.py            apply, in place
    python scripts/slm_l1_additions.py --check    exit 1 if applying would change a file

It is idempotent and only adds - a key a file already has is left as it is:

1. ``additional_fields``  printed label/value pairs no field holds, in the
                          shape homeowners already declares (the generator
                          writes it for every line);
2. ``full``               on every address: the address as printed, unsplit;
3. ``FIELDS``             policy, named insured, document and signature fields
                          the SLM L1 corpus review found printed across lines;
4. ``coverages``          one generic coverage list (``CoverageSection``) and
                          the ``math`` audit rule that sums its premiums;
5. ``text_sections``      described, and excluded from the VLM FSM;
6. ``fideon:verification`` recomputed from ``Data/original data`` - how many
                          source documents and carriers this line has here;
7. ``fideon:source.field_count`` recounted.

homeowners.json's own ``text_sections``, ``coverages`` and ``field_count``
were authored separately (a one-time review of 69 reference documents,
already applied) - this module still leaves those alone (OWNED_ELSEWHERE,
below), since this script only adds what a file is missing, never
overwrites what another process already got right.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "config" / "policy_check"
DOCS = ROOT / "Data" / "original data"
REF = "#/$defs/FieldValue"
NOTE = ("Fields carried over from SLM L1 2026-09-27 by scripts/slm_l1_additions.py: additional_fields, "
        "address full, policy tier/rating state/quote/original inception/cancellation method/renewal offer/"
        "term as printed, named insured contact name/occupation/marital status, document endorsement "
        "number/delivery preference/e-signature certificate, signature presence, coverages and the math "
        "audit rule; re-run it after any regeneration.")

CORPUS = ("Printed across the POLICIES-FINAL corpus (277 documents, ~40 carriers) and absent from the "
          "supplied schemas. Printed on %d of the 22 lines. ")

# ── 3. fields: block -> [(name, why, printed labels, insert after, skip if the block has)] ──
FIELDS = {
    "policy": [
        ("policy_tier", CORPUS % 8 + "NYCM prints `Tier: 9`. A rating tier moves the premium and had no "
         "slot, so it travelled in `additional_fields` flagged as unverified.",
         ["Policy Tier", "Tier"], None, ("rating_tier",)),
        ("rating_state", CORPUS % 9 + "The state whose rates apply -- not always where the policy was "
         "issued (`carrier.state_of_issue`), nor where the risk sits.", ["Rating State"], None, ()),
        ("quote_number", CORPUS % 4 + "The quote this policy was issued from. NYCM prints "
         "`QUOTE #: Q31829763` on every page.", ["QUOTE #"], None, ()),
        ("original_inception_date", CORPUS % 13 + "The date the policy FIRST incepted, which a renewal "
         "states beside its own term -- North Country prints `Inception Date`. Distinct from "
         "`effective_date` and from `anniversary_date`.", ["Original Inception Date", "Inception Date"],
         "anniversary_date", ("first_inception_date",)),
        ("cancellation_method", CORPUS % 8 + "HOW a policy was cancelled -- flat, pro-rata, short rate. "
         "`cancellation_date` and `cancellation_reason` exist; the method is what decides the refund.",
         [], "cancellation_reason", ()),
        ("renewal_offer", CORPUS % 12 + "Whether the carrier is offering renewal, and on what terms. "
         "A compliance fact on any non-renewal.", [], None, ()),
        ("policy_term_as_printed", "The policy term EXACTLY as the page states it, whichever form that "
         "takes. Carriers print two: a duration (`Policy Term: 12 Months`) and a date range (`Policy "
         "Term: 02/29/2024 to 02/28/2025`). `policy_term_months` counts months, so a carrier printing "
         "the range had its date pair written into a numeric field. Keeping both means "
         "`policy_term_months` stays a number and the printed form survives as the audit trail.",
         [], "policy_term_months", ()),
    ],
    "named_insured": [
        ("contact_name", CORPUS % 12 + "`named_insured.contact` models phone, fax, email and website "
         "and carries no name, so the PERSON to contact had nowhere to go.", [], "contact", ()),
        ("occupation", CORPUS % 4 + "A personal-lines rating factor.", ["Occupation"], None, ()),
        ("marital_status", CORPUS % 5 + "A personal-lines rating factor.", ["Marital Status"], None, ()),
    ],
    "document": [
        ("endorsement_number", CORPUS % 11 + "Which endorsement THIS document is. "
         "`forms_and_endorsements[]` lists the forms attached to the policy; this names the change "
         "the page represents.", [], None, ()),
        ("delivery_preference", CORPUS % 4 + "Paper or electronic. A notice sent the way the "
         "policyholder did not choose is a compliance failure.", [], None, ("delivery_method",)),
        ("esignature_certificate", CORPUS % 5 + "The e-signature certificate -- the evidence the "
         "document was signed. Same shape as homeowners.", None, None, ()),
    ],
    "signature": [
        ("has_signature", "Whether the declarations page carries a signature at all. The `signature` "
         "block models the signature's CONTENTS -- representative name, title, dates -- and has no "
         "key for its presence. An unsigned declarations page is a compliance question, so `false` "
         "is a finding rather than an absence.", [], None, ()),
    ],
}

FULL_WHY = ("The address as the document PRINTS it, unparsed. The split parts need a reader to guess "
            "where the street ends and the city begins; this keeps the block whole.")

ADDITIONAL_FIELDS = {
    "type": "array",
    "description": "Printed label/value pairs that have no dedicated field above, kept as key and value: "
                   "the label as the document prints it, the section heading it sits under, and the "
                   "value as a FieldValue (raw, parsed, page_ref).",
    "items": {"type": "object",
              "properties": {"section": {"type": ["string", "null"]},
                             "label": {"type": "string"},
                             "value": {"$ref": REF}},
              "required": ["label", "value"]}}

TEXT_SECTIONS = {
    "type": "object",
    "additionalProperties": {"$ref": "#/$defs/TextSection"},
    "fideon:fsm_exclude": True,
    "description": "Raw text blocks for SLM/LLM-based policy comparison \u2014 populated by the text "
                   "extraction path, not the VLM FSM. These are what the Comparison API reads."}

COVERAGES = {
    "type": "array",
    "items": {"$ref": "#/$defs/CoverageSection"},
    "fideon:aliases": ["Coverage", "Coverages", "Coverage Part", "Schedule of Coverages",
                       "Limits of Insurance"]}

COVERAGE_SECTION = {
    "type": "object",
    "properties": {k: {"$ref": REF} for k in (
        "coverage_type", "coverage_name", "covered_auto_symbols", "limit", "aggregate_limit",
        "deductible", "retention", "sublimit", "premium")}}
COVERAGE_SECTION["properties"]["endorsement_refs"] = {"type": "array", "items": {"$ref": REF}}

MATH = ["sum(coverages[*].premium) \u2248 premium.total_policy_premium \u00b1 0.01"]

# bopgl/boppr already named their form-level coverage row CoverageSection
OLD_ROW = "BusinessLiabilityCoverageRow"

# homeowners.json's text_sections/coverages/field_count were authored by a
# separate one-time review, already applied - left alone here
OWNED_ELSEWHERE = {"homeowners.json"}

FREE_TEXT = ("text_sections", "additional_fields", "printed_lines")


def _clean(node):
    """A copy without homeowners' generated description/value_type annotations."""
    if isinstance(node, dict):
        return {k: _clean(v) for k, v in node.items() if k not in ("description", "fideon:value_type")}
    if isinstance(node, list):
        return [_clean(v) for v in node]
    return node


def _insert(props, name, node, after=None, before=None):
    """``props`` with ``name`` placed after ``after`` (or before ``before``), else last."""
    items = list(props.items())
    at = len(items)
    keys = [k for k, _ in items]
    if after in keys:
        at = keys.index(after) + 1
    elif before in keys:
        at = keys.index(before)
    items.insert(at, (name, node))
    props.clear()
    props.update(items)


def _aliases_in(schema):
    out = set()

    def w(n):
        if isinstance(n, dict):
            for a in n.get("fideon:aliases", []) or []:
                out.add(a.lower())
            for v in n.values():
                w(v)
        elif isinstance(n, list):
            for v in n:
                w(v)
    w(schema)
    return out


def _addresses(node):
    """Every address object: one with a street line and a city or postal code."""
    if isinstance(node, dict):
        props = node.get("properties")
        if node.get("type") == "object" and isinstance(props, dict) and "line_1" in props \
                and ("city" in props or "postal_code" in props):
            yield props
        for v in node.values():
            yield from _addresses(v)
    elif isinstance(node, list):
        for v in node:
            yield from _addresses(v)


def _count(schema):
    defs = schema.get("$defs", {})
    n = 0

    def v(x):
        nonlocal n
        if "$ref" in x:
            name = x["$ref"].split("/")[-1]
            if name == "FieldValue":
                n += 1
            else:
                v(defs[name])
            return
        if x.get("type") == "object":
            for s in (x.get("properties") or {}).values():
                v(s)
        elif x.get("type") == "array":
            v(x.get("items") or {})
    for k, s in schema["properties"].items():
        if k not in FREE_TEXT:
            v(s)
    return n


def _documents(lob):
    """(source PDFs, carriers) for a line of business in Data/original data."""
    if not DOCS.is_dir():
        return 0, 0
    pdfs = [p for p in DOCS.glob("*/%s/**/*" % lob) if p.suffix.lower() == ".pdf"] if lob else \
        [p for p in DOCS.rglob("*") if p.suffix.lower() == ".pdf"]
    return len(pdfs), len({p.relative_to(DOCS).parts[0] for p in pdfs})


def verification(stem, schema):
    if stem == "_fallback":
        return {"source_documents": 0, "source_carriers": 0, "verified_against_documents": False,
                "note": "used when no line of business matches, so no document is filed under it"}
    docs, carriers = _documents(None if stem == "_common" else stem)
    reviewed = "gap_analysis_extensions" in schema.get("fideon:source", {})
    if stem == "_common":
        note = "the shared core, read on every line's documents; see each line's file"
    elif not docs:
        note = "no source document in Data/original data is filed under this line, so every field " \
               "here is modelled and none is confirmed against a real page"
    elif reviewed:
        note = "fields reviewed against these documents; see fideon:source.gap_analysis_extensions"
    else:
        note = "source documents exist here, but no field-by-field review of them is recorded"
    return {"source_documents": docs, "source_carriers": carriers,
            "verified_against_documents": bool(docs) and reviewed, "note": note}


def extend(schema, stem, esig):
    props = schema["properties"]
    owned = stem + ".json" in OWNED_ELSEWHERE
    taken = _aliases_in(schema)

    # 1. additional_fields
    if "additional_fields" not in props:
        props["additional_fields"] = json.loads(json.dumps(ADDITIONAL_FIELDS))

    # 2. full on every address
    for addr in _addresses(props):
        if "full" not in addr:
            addr["full"] = {"$ref": REF, "fideon:repo_addition": FULL_WHY}

    # 3. fields
    for block, fields in FIELDS.items():
        box = props.get(block, {}).get("properties")
        if box is None:
            continue
        for name, why, labels, after, twins in fields:
            if name in box or any(t in box for t in twins):
                continue
            if labels is None:          # e-signature certificate: homeowners' section
                node = json.loads(json.dumps(esig))
            else:
                node = {"$ref": REF}
                free = [a for a in labels if a.lower() not in taken]
                if free:
                    node["fideon:aliases"] = free
                    taken.update(a.lower() for a in free)
            node["fideon:repo_addition"] = why
            _insert(box, name, node, after=after)

    # 4. coverages, CoverageSection and the math rule
    defs = schema.setdefault("$defs", {})
    old = defs.get("CoverageSection")
    if old is not None and "coverage_name" not in old.get("properties", {}):
        text = json.dumps(schema).replace('"#/$defs/CoverageSection"', '"#/$defs/%s"' % OLD_ROW)
        schema.clear()
        schema.update(json.loads(text))
        props, defs = schema["properties"], schema["$defs"]
        items = list(defs.items())
        defs.clear()
        defs.update((OLD_ROW if k == "CoverageSection" else k, v) for k, v in items)
    if "CoverageSection" not in defs:
        defs["CoverageSection"] = json.loads(json.dumps(COVERAGE_SECTION))
    if "coverages" not in props:
        _insert(props, "coverages", json.loads(json.dumps(COVERAGES)), before="text_sections")
    rules = schema.setdefault("fideon:audit_rules", {})
    if "math" not in rules:
        rules["math"] = list(MATH)

    # 5. text_sections
    if "text_sections" in props and "description" not in props["text_sections"]:
        props["text_sections"] = json.loads(json.dumps(TEXT_SECTIONS))

    # 6. verification, beside fideon:source
    ver = verification(stem, schema)
    if schema.get("fideon:verification") != ver:
        items = [(k, v) for k, v in schema.items() if k != "fideon:verification"]
        at = next((i + 1 for i, (k, _) in enumerate(items) if k == "fideon:source"), len(items))
        items.insert(at, ("fideon:verification", ver))
        schema.clear()
        schema.update(items)

    # 7. note and field count
    if NOTE not in schema.get("fideon:note", ""):
        schema["fideon:note"] = (schema.get("fideon:note", "") + " " + NOTE).strip()
    if not owned:
        schema.setdefault("fideon:source", {})["field_count"] = _count(schema)
    return schema


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report only; exit 1 if a file would change")
    parser.add_argument("--schema-dir", default=str(SCHEMA_DIR), help="default: %(default)s")
    args = parser.parse_args(argv)
    folder = Path(args.schema_dir)
    esig = _clean(json.loads((folder / "homeowners.json").read_text("utf-8"))
                  ["properties"]["document"]["properties"]["esignature_certificate"])
    esig.pop("fideon:repo_addition", None)
    changed = 0
    for path in sorted(folder.glob("*.json")):
        raw = path.read_bytes().decode("utf-8")
        newline = "\r\n" if "\r\n" in raw else "\n"
        # keep the file's own style: some carry "§" as is, others escaped
        out = json.dumps(extend(json.loads(raw), path.stem, esig), indent=2,
                         ensure_ascii=raw.isascii()).replace("\n", newline) + newline
        if out == raw:
            continue
        changed += 1
        if args.check:
            print("%s: would change" % path.name)
        else:
            path.write_bytes(out.encode("utf-8"))
            print("%s: extended" % path.name)
    if not changed:
        print("%s: up to date" % folder)
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    sys.exit(main())
