#!/usr/bin/env python3
"""
Reviewed gold for a source document, written from its printed pages.

    python scripts/gold_review.py show   "<source pdf>" [--pages 1-5]
    python scripts/gold_review.py finish "<source pdf>" <facts.json> [--base <base gold json>]

``show`` prints each page's text in reading order, and says which pages are
scans (read those from the page image).

``finish`` turns a facts file - the document's values as printed, laid out
like the line's canonical schema, with plain strings for leaves - into gold:

    {"policy": {"policy_number": "CYC237253-10", "effective_date": "07/23/2025"},
     "motorcycle": {"units": [{"year": "2009", "make": "HARLEY-DAVIDSON", ...}]}}

A leaf may also be {"raw": ..., "parsed": ..., "source": "structural"} for a
value the page does not print word for word (an X mark read as "Yes", a
count). Amounts parse to numbers and dates to MM/DD/YYYY; each value gets the
pages that print it. The gold must use only the schema's own paths and
satisfy it; the policy wording (text_sections) comes from the base gold.

Written to Data/original gold/<carrier>/<lob>/<name>.json, with a row in
Data/original gold/_review_log.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fitz  # noqa: E402
fitz.TOOLS.mupdf_display_errors(False)
from fideon_synth import generic  # noqa: E402
from fideon_synth.schema import CanonicalSchema  # noqa: E402

DATA = ROOT / "Data" / "original data"
GOLD = ROOT / "Data" / "original gold"
MONEY = re.compile(r"^\(?-?\$\s?[\d,]+(?:\.\d{1,2})?\)?$")
DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%b. %d, %Y")


def norm(text):
    return re.sub(r"[^a-z0-9$.,/&-]+", " ", str(text).lower()).strip()


def page_texts(pdf):
    doc = fitz.open(str(pdf))
    out = [(norm(p.get_text()), len(p.get_text().strip()) < 30) for p in doc]
    doc.close()
    return out


def show(pdf, pages=None):
    doc = fitz.open(str(pdf))
    first, last = 1, len(doc)
    if pages:
        a, _, b = pages.partition("-")
        first, last = int(a), int(b or a)
    print("%s: %d pages" % (pdf, len(doc)))
    for i in range(first - 1, min(last, len(doc))):
        page = doc[i]
        text = page.get_text("text", sort=True).strip()
        scanned = len(text) < 30 or generic.overlay.invisible_text(page)
        print("\n===== page %d%s =====" % (i + 1, "  (SCAN - read the image)" if scanned else ""))
        print(re.sub(r"\n{3,}", "\n\n", text))
    doc.close()


def parse(raw):
    s = str(raw).strip()
    if MONEY.match(s):
        v = float(re.sub(r"[^\d.]", "", s))
        return -v if s.startswith(("(", "-")) else v
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%m/%d/%Y")
        except ValueError:
            pass
    return s


def wrap(value, texts, stats):
    """A facts leaf as a FieldValue, with the pages that print it."""
    if isinstance(value, dict) and "raw" in value:
        raw, parsed = value["raw"], value.get("parsed", parse(value["raw"]))
        source = value.get("source", "deterministic")
    else:
        raw, parsed, source = value, parse(value), "deterministic"
    raw = str(raw)
    key = norm(raw)
    tight = key.replace(" ", "")
    # "$ 19" in the text layer is the printed "$19"
    pages = [i + 1 for i, (t, _) in enumerate(texts) if key and (key in t or tight in t.replace(" ", ""))]
    if not pages and source != "structural":
        stats["from_image"].append(raw)         # read off a scan or a table's image
    return {"raw": raw, "parsed": parsed, "confidence": {"score": 1.0, "source": source},
            "page_ref": pages, "flagged": False}


def build(node, texts, stats, key=None):
    if isinstance(node, dict) and "raw" not in node:
        return {k: build(v, texts, stats, k) for k, v in node.items() if v not in (None, "", [], {})}
    if isinstance(node, list):
        return [build(v, texts, stats, key) for v in node]
    if key in ("label", "section") and isinstance(node, str):
        return node                             # additional_fields[] names its value in plain text
    return wrap(node, texts, stats)


def leaves(d, p=""):
    if isinstance(d, dict):
        if "raw" in d and "confidence" in d:
            yield p, d
            return
        for k, v in d.items():
            if not k.startswith("fideon:") and k != "text_sections":
                yield from leaves(v, p + "." + k if p else k)
    elif isinstance(d, list):
        for v in d:
            yield from leaves(v, p + "[]")


def finish(pdf, facts_file, base_file=None):
    pdf = Path(pdf).resolve()
    rel = pdf.relative_to(DATA)
    lob = generic._lob_for(pdf, str(ROOT / "config" / "policy_check"))
    schema = CanonicalSchema.load(lob, str(ROOT / "config" / "policy_check"))
    texts = page_texts(pdf)
    stats = {"from_image": []}
    facts = json.loads(Path(facts_file).read_text("utf-8"))
    gold = build(facts, texts, stats)
    gold.setdefault("document", {})
    gold["document"].setdefault("source_file_name", wrap({"raw": pdf.name, "source": "structural"}, texts, stats))
    gold["document"].setdefault("page_count", wrap({"raw": str(len(texts)), "parsed": len(texts),
                                                    "source": "structural"}, texts, stats))
    if base_file and Path(base_file).exists():
        base = json.loads(Path(base_file).read_text("utf-8"))
        if base.get("text_sections"):
            gold["text_sections"] = base["text_sections"]
    gold["fideon:provenance"] = {"source": rel.as_posix(), "schema": "%s v%s" % (lob, schema.version),
                                 "synthetic": False,
                                 "gold": "reviewed and completed by Claude against the printed pages",
                                 "reviewed": datetime.now().strftime("%Y-%m-%d")}

    unknown = sorted({p for p, _ in leaves(gold) if p not in schema.leaves})
    errors = [e for e in schema.validate(gold) if "is a required property at (root)" not in e]
    fields = sum(1 for _ in leaves(gold))
    print("%s  [%s]  %d fields" % (rel.as_posix(), lob, fields))
    print("  paths not in the schema: %s" % (unknown or "none"))
    print("  schema errors: %s" % (errors or "none"))
    print("  read from the page image (not in the text layer): %d" % len(stats["from_image"]))
    for raw in stats["from_image"][:40]:
        print("      %r" % raw)
    if unknown or errors:
        print("  NOT written: fix the facts first")
        return 1
    out = GOLD / rel.with_suffix(".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(gold, indent=2, ensure_ascii=False), encoding="utf-8")
    log = GOLD / "_review_log.csv"
    rows = []
    if log.exists():
        rows = [r for r in csv.DictReader(open(log, encoding="utf-8")) if r["source"] != rel.as_posix()]
    rows.append({"source": rel.as_posix(), "lob": lob, "pages": len(texts),
                 "scanned_pages": sum(1 for _, s in texts if s), "fields": fields,
                 "from_image": len(stats["from_image"]), "schema_ok": "yes",
                 "reviewed": datetime.now().strftime("%Y-%m-%d %H:%M")})
    with open(log, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[-1]))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["lob"], r["source"])))
    print("  written: %s" % out.relative_to(ROOT))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show")
    s.add_argument("pdf")
    s.add_argument("--pages")
    f = sub.add_parser("finish")
    f.add_argument("pdf")
    f.add_argument("facts")
    f.add_argument("--base")
    args = parser.parse_args(argv)
    if args.cmd == "show":
        show(Path(args.pdf), args.pages)
        return 0
    return finish(args.pdf, args.facts, args.base)


if __name__ == "__main__":
    sys.exit(main())
