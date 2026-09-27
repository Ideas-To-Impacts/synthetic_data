#!/usr/bin/env python3
"""
Build a train / validation / test set of synthetic documents.

Every source PDF of the chosen lines of business gets ``--per-source``
synthetic twins (a scanned PDF and its gold JSON each), and all the twins of
one source go to the same split - a layout the model is tested on is one it
never trained on. Within each line the sources are dealt out carrier by
carrier, so every split sees every carrier it can, and a line with three
sources or more has at least one in each split.

The shares follow how many documents of the type the build makes (see BANDS):
under 200, 70/18/12 (pilot); 200 to 999, 75/15/10 (growing); 1,000 and up,
80/10/10 (target state) - 192 personal-line sources x 10 is 1,920, so 80/10/10.

    python scripts/build_dataset.py --out "Data/synthetic data"
    python scripts/build_dataset.py --out "Data/synthetic data" --per-source 10 --workers 10

OCR is the slow part. Its readings are cached (<out>/.ocr_cache, shared by all
workers), and every source's first variant is made before any second, so the
unedited pages of a source are read once for all its variants. Set
FIDEON_OCR_GPU=cuda to run the OCR on an NVIDIA card (onnxruntime-gpu).

Output, under --out:

    Train|Test|Val/pdfs/<lob>__<source>__synth_NNN.pdf
    Train|Test|Val/gold json/<lob>__<source>__synth_NNN.json
    splits.json      which source went to which split
    manifest.csv     one row per document: split, lob, carrier, source, sample,
                     files, pages, fields, ok, problems

It resumes: a document whose PDF and gold JSON both exist is not made again,
so an interrupted run is continued by running the same command.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PERSONAL = ["personal_auto", "homeowners", "dwelling_fire", "flood", "personal_umbrella",
            "motorcycle", "recreational_vehicle", "ocean_marine", "classic_auto"]
SPLITS = ("Train", "Val", "Test")
#: the share of each split by how many documents of one document type the set
#: holds - the fine-tuning corpus build's bands (its constants.py:128, from
#: finetuning-architecture-v1.md:578). Below 200 a tenth is under 20
#: documents, too few to measure on, so validation and test get more and the
#: numbers are directional; from 1,000 a tenth is 100 documents or more,
#: enough on its own, and training gets the rest.
BANDS = ((200, "pilot", {"Train": 0.70, "Val": 0.18, "Test": 0.12}),
         (1000, "growing", {"Train": 0.75, "Val": 0.15, "Test": 0.10}),
         (None, "target state", {"Train": 0.80, "Val": 0.10, "Test": 0.10}))
FIELDS = ["split", "lob", "carrier", "source", "sample", "pdf", "gold", "pages", "fields",
          "ok", "seconds", "problems"]


def band(documents):
    """(stage, {split: share}) for a document type with this many documents."""
    for below, stage, shares in BANDS:
        if below is None or documents < below:
            return stage, shares


def sources(data, lobs):
    """{lob: [source pdf]} for every readable PDF of the chosen lines."""
    import fitz
    fitz.TOOLS.mupdf_display_errors(False)
    out = defaultdict(list)
    for pdf in sorted(Path(data).rglob("*.pdf")):
        if pdf.parent.name not in lobs:
            continue
        try:
            fitz.open(str(pdf)).close()
        except Exception:
            continue
        out[pdf.parent.name].append(pdf)
    return out


def split_sources(pdfs, shares):
    """{split: [pdf]}: the sources shared out as ``shares`` says, carriers
    dealt out evenly."""
    n = len(pdfs)
    want = {name: round(n * shares[name]) for name in SPLITS}
    want["Train"] = n - want["Test"] - want["Val"]
    if n >= 3:                                   # every split gets a source
        for name in ("Val", "Test"):
            if want[name] == 0:
                want[name], want["Train"] = 1, want["Train"] - 1
    by_carrier = defaultdict(list)
    for pdf in pdfs:
        by_carrier[pdf.parent.parent.name].append(pdf)
    # one of each carrier in turn, so no carrier lands in one split alone
    order, queues = [], [list(v) for _, v in sorted(by_carrier.items())]
    while any(queues):
        for q in queues:
            if q:
                order.append(q.pop(0))
    out = {name: [] for name in SPLITS}
    for i, pdf in enumerate(order):
        # the split furthest behind its share of the sources dealt so far
        name = max((s for s in SPLITS if len(out[s]) < want[s]),
                   key=lambda s: want[s] * (i + 1) / n - len(out[s]))
        out[name].append(pdf)
    return out


def make(task):
    split, lob, pdf, k, out = task
    from fideon_synth import generic
    from fideon_synth.schema import CanonicalSchema
    from fideon_synth.values import Values
    name = "%s__%s__synth_%03d" % (lob, pdf.stem, k)
    pdf_out = Path(out) / split / "pdfs" / (name + ".pdf")
    gold_out = Path(out) / split / "gold json" / (name + ".json")
    row = {"split": split, "lob": lob, "carrier": pdf.parent.parent.name,
           "source": str(pdf.relative_to(ROOT / "Data" / "original data")), "sample": k,
           "pdf": str(pdf_out.relative_to(out)), "gold": str(gold_out.relative_to(out))}
    if pdf_out.exists() and gold_out.exists():
        return None                               # made on an earlier run
    t = time.time()
    try:
        schema = CanonicalSchema.load(generic._lob_for(pdf, str(ROOT / "config" / "policy_check")),
                                      str(ROOT / "config" / "policy_check"))
        built = generic.synthesize(pdf, pdf_out, gold_out, schema,
                                   Values("%d:%s" % (k, row["source"])), seed=k)
        row.update(pages=built.pages, fields=built.fields, ok=built.ok,
                   problems=" | ".join(built.problems))
    except Exception as exc:                      # one bad source must not stop the run
        row.update(pages=0, fields=0, ok=False, problems="%s: %s" % (type(exc).__name__, exc))
    row["seconds"] = round(time.time() - t, 1)
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "Data" / "synthetic data"))
    parser.add_argument("--data", default=str(ROOT / "Data" / "original data"))
    parser.add_argument("--lob", action="append", default=None,
                        help="line of business; repeatable (default: the 9 personal lines)")
    parser.add_argument("--per-source", type=int, default=10)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--ocr-cache", default=None,
                        help="where OCR readings are kept for all workers (default: <out>/.ocr_cache)")
    args = parser.parse_args(argv)
    out = Path(args.out)
    lobs = args.lob or PERSONAL
    # set before the workers start, so every one of them shares it
    os.environ.setdefault("FIDEON_OCR_CACHE", args.ocr_cache or str(out / ".ocr_cache"))

    found = sources(args.data, lobs)
    # the personal lines are one document type (the policy_check schemas):
    # its band is set by all the documents this build makes of it
    documents = sum(len(v) for v in found.values()) * args.per_source
    stage, shares = band(documents)
    plan_file = out / "splits.json"
    plan = json.loads(plan_file.read_text("utf-8")) if plan_file.exists() else None
    made = any((out / s / "pdfs").glob("*__synth_*.pdf") for s in SPLITS)
    if plan is not None and plan.get("shares") != shares:
        if made:
            sys.exit("%s was split %s; this build would be split %s (%d documents, %s). Finish "
                     "it with the same --per-source and sources, or empty %s to start over."
                     % (plan_file, plan.get("shares"), shares, documents, stage, out))
        plan = None                               # nothing made yet: split again
    if plan is None:
        plan = {"documents": documents, "stage": stage, "shares": shares,
                "lines": {lob: {s: [str(p.relative_to(ROOT / "Data" / "original data")) for p in v]
                                for s, v in split_sources(found[lob], shares).items()}
                          for lob in lobs if found[lob]}}
        out.mkdir(parents=True, exist_ok=True)
        plan_file.write_text(json.dumps(plan, indent=1), "utf-8")
    for split in SPLITS:
        (out / split / "pdfs").mkdir(parents=True, exist_ok=True)
        (out / split / "gold json").mkdir(parents=True, exist_ok=True)

    print("%d documents of one type: %s, Train / Val / Test %s" % (
        documents, stage, " / ".join("%.0f" % (100 * shares[s]) for s in SPLITS)))
    print("%-22s %6s %6s %6s   sources (documents = x%d)" % ("line", "train", "val", "test", args.per_source))
    tasks = []
    for lob, splits in plan["lines"].items():
        print("%-22s %6d %6d %6d" % (lob, *(len(splits[s]) for s in SPLITS)))
        for split in SPLITS:
            for rel in splits[split]:
                for k in range(1, args.per_source + 1):
                    tasks.append((split, lob, ROOT / "Data" / "original data" / rel, k, out))
    # every source's first variant before any second: the OCR of a source's
    # unedited pages is then cached for its other variants; and the longest
    # sources first within each round, so no worker is left with one at the end
    import fitz
    pages = {}
    for t in tasks:
        if t[2] not in pages:
            with fitz.open(str(t[2])) as d:
                pages[t[2]] = len(d)
    tasks.sort(key=lambda t: (t[3], -pages[t[2]]))
    print("%d documents to make, %d pages" % (len(tasks), sum(pages[t[2]] for t in tasks)))

    manifest = out / "manifest.csv"
    new = not manifest.exists()
    done = failed = 0
    start = time.time()
    with open(manifest, "a", newline="", encoding="utf-8") as fh, Pool(args.workers) as pool:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        for row in pool.imap_unordered(make, tasks):
            if row is None:
                continue
            writer.writerow(row)
            fh.flush()
            done += 1
            failed += not row["ok"]
            if done % 10 == 0 or not row["ok"]:
                print("%5d made, %d with problems, %.0f min | %s %s" % (
                    done, failed, (time.time() - start) / 60,
                    "ok  " if row["ok"] else "PROBLEM", row["pdf"]), flush=True)
    print("DONE: %d made this run, %d with problems" % (done, failed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
