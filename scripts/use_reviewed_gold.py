#!/usr/bin/env python3
"""
Give each source document in the dataset its reviewed gold.

build_dataset.py --originals puts every source itself in the set
(<lob>__<source>__original), scanned, with the gold the generator reads off
it. Where Data/original gold holds a reviewed gold for that source - written
from the printed pages - that gold replaces the generator's. The scan has the
source's own pages, so the reviewed page references hold as they are.

    python scripts/use_reviewed_gold.py                      # Data/synthetic data
    python scripts/use_reviewed_gold.py --out "<dataset>" --dry-run

A reviewed gold is used only when it satisfies its schema and every page it
names exists in the document; otherwise the generator's gold stays and the
reason is printed. manifest.csv follows: the row's fields, ok and problems
describe the gold now in the set. Run it again as more sources are reviewed.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fitz  # noqa: E402
fitz.TOOLS.mupdf_display_errors(False)
from fideon_synth.fields import walk  # noqa: E402
from fideon_synth.schema import CanonicalSchema  # noqa: E402

REVIEWED = ROOT / "Data" / "original gold"
SCHEMAS = str(ROOT / "config" / "policy_check")


def reviewed_for(source):
    """The reviewed gold of a source ("Carrier/lob/name.pdf"), or None."""
    path = REVIEWED / Path(source).with_suffix(".json")
    return path if path.exists() else None


def check(gold, pdf):
    """Why this gold cannot go with this PDF, or None."""
    lob = gold.get("fideon:provenance", {}).get("schema", "").split()[0]
    errors = CanonicalSchema.load(lob, SCHEMAS).validate(gold)
    if errors:
        return "%d schema error(s), first: %s" % (len(errors), errors[0])
    with fitz.open(str(pdf)) as doc:
        pages = len(doc)
    beyond = sorted({p for _, f in walk(gold) for p in f["page_ref"] if p > pages})
    if beyond:
        return "names page(s) %s of a %d-page document" % (beyond, pages)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "Data" / "synthetic data"))
    parser.add_argument("--dry-run", action="store_true", help="report only; change nothing")
    args = parser.parse_args(argv)
    out = Path(args.out)
    manifest = out / "manifest.csv"
    with open(manifest, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, list(reader)

    used = same = kept = refused = 0
    for row in rows:
        if row.get("kind") != "original":
            continue
        source = reviewed_for(row["source"])
        if source is None:
            kept += 1                                   # not reviewed yet
            continue
        pdf, gold_path = out / row["pdf"], out / row["gold"]
        if not pdf.exists():
            continue                                    # not built (or set aside)
        gold = json.loads(source.read_text("utf-8"))
        problem = check(gold, pdf)
        if problem:
            refused += 1
            print("  kept the generator's gold for %s: %s" % (row["source"], problem))
            continue
        text = json.dumps(gold, indent=2, ensure_ascii=False)
        if gold_path.exists() and gold_path.read_text("utf-8") == text:
            same += 1
            continue
        used += 1
        if not args.dry_run:
            gold_path.parent.mkdir(parents=True, exist_ok=True)
            gold_path.write_text(text, encoding="utf-8")
            row.update(fields=sum(1 for _ in walk(gold)), ok=True, problems="")

    if not args.dry_run and used:
        with open(manifest, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    print("%s reviewed gold: %d newly in the set, %d already there, %d refused; "
          "%d source(s) not reviewed yet keep the generator's gold"
          % ("would use" if args.dry_run else "used", used, same, refused, kept))
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
