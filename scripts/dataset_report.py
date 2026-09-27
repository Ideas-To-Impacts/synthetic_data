#!/usr/bin/env python3
"""
What a dataset build made, and what its own checks flagged.

    python scripts/dataset_report.py --out "Data/synthetic data"
    python scripts/dataset_report.py --out "Data/synthetic data" --quarantine

Reads <out>/manifest.csv (written by build_dataset.py) and prints the
documents per split and line of business, then every document whose checks
raised something, grouped by the kind of problem:

    leak          an original value is still in the PDF, the gold or the text
    not on page   the gold states a value the page does not print
    schema        the gold does not satisfy the schema
    crash         the generator stopped on the document
    other         anything else

--quarantine moves the flagged PDFs and gold files to <out>/Flagged/<split>/
so the training splits hold only documents that passed every check; the
manifest keeps their rows, with the split column saying "Flagged/<split>".
Moving them back is the same files moved the other way.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

KINDS = (("leak", re.compile(r"still in the generated PDF|is in the gold|survived into")),
         ("not on page", re.compile(r"not on any page")),
         ("crash", re.compile(r"^\w+Error:|worker died")),
         ("schema", re.compile(r" at [\w/.\[\]()]+$| is not | is a required")))


def kind(problem):
    for name, rx in KINDS:
        if rx.search(problem):
            return name
    return "other"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--out", default="Data/synthetic data")
    parser.add_argument("--quarantine", action="store_true",
                        help="move flagged documents out of the splits, to <out>/Flagged/")
    args = parser.parse_args(argv)
    out = Path(args.out)
    manifest = out / "manifest.csv"
    if not manifest.exists():
        sys.exit("no manifest at %s" % manifest)
    rows = list(csv.DictReader(open(manifest, encoding="utf-8")))
    # a document made again after an interrupted run keeps its last row
    last = {}
    for r in rows:
        last[r["pdf"]] = r
    # a document whose files were deleted is gone - unless it never had any
    # (a crash), which is still worth seeing
    rows = [r for r in last.values() if (out / r["pdf"]).exists() or r["ok"] != "True"
            and not (out / r["gold"]).exists() and "Error" in r["problems"]]

    splits = Counter(r["split"] for r in rows)
    print("%d documents: %s" % (len(rows), ", ".join("%s %d" % kv for kv in sorted(splits.items()))))
    kinds = Counter((r.get("kind") or "synthetic", r["split"]) for r in rows)
    if any(k == "original" for k, _ in kinds):
        for which in ("synthetic", "original"):
            print("  %-10s %s" % (which, ", ".join("%s %d" % (s, kinds[(which, s)])
                                                  for s in sorted(splits) if kinds[(which, s)])))
    by_lob = defaultdict(Counter)
    for r in rows:
        by_lob[r["lob"]][r["split"]] += 1
    names = sorted(splits)
    print("%-22s %s" % ("line", " ".join("%8s" % s[:8] for s in names)))
    for lob, c in sorted(by_lob.items()):
        print("%-22s %s" % (lob, " ".join("%8d" % c[s] for s in names)))

    bad = [r for r in rows if r["ok"] != "True"]
    print("\n%d flagged (%.1f%%)" % (len(bad), 100.0 * len(bad) / max(len(rows), 1)))
    groups = defaultdict(list)
    for r in bad:
        problems = [p.strip() for p in r["problems"].split(" | ") if p.strip()] or ["(no detail)"]
        for k in sorted({kind(p) for p in problems}):
            groups[k].append((r, [p for p in problems if kind(p) == k]))
    for k in ("leak", "crash", "not on page", "schema", "other"):
        if groups.get(k):
            print("\n== %s: %d document(s)" % (k, len(groups[k])))
            for r, ps in groups[k]:
                print("  %s" % r["pdf"])
                for p in ps[:3]:
                    print("      %s" % p[:220])

    if args.quarantine and bad:
        moved = 0
        for r in bad:
            if r["split"].startswith("Flagged"):
                continue
            for key in ("pdf", "gold"):
                src = out / r[key]
                if src.exists():
                    dst = out / "Flagged" / r[key]
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dst))
            for key in ("pdf", "gold"):
                r[key] = str(Path("Flagged") / r[key])
            r["split"] = "Flagged/" + r["split"]
            moved += 1
        with open(manifest, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print("\nmoved %d flagged document(s) to %s" % (moved, out / "Flagged"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
