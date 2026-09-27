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
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
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
FIELDS = ["split", "lob", "carrier", "source", "sample", "kind", "pdf", "gold", "pages", "fields",
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
    # in one order on every machine: Windows sorts paths without regard to case,
    # Linux with it, and the split must not depend on where it is made
    for pdf in sorted(Path(data).rglob("*.pdf"), key=lambda p: p.as_posix()):
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


def doc_name(lob, pdf, k, shared):
    """<lob>__<source>__synth_NNN - and the carrier as well where two carriers'
    sources of the line share a file name (HOME_redacted.pdf from Chubb, Madison
    Mutual and MILLENNIAL): their documents must never write the same files."""
    tail = "original" if k == 0 else "synth_%03d" % k       # sample 0: the source itself
    if (lob, pdf.stem) in shared:
        carrier = re.sub(r"[^A-Za-z0-9]+", "_", pdf.parent.parent.name).strip("_")
        return "%s__%s__%s__%s" % (lob, pdf.stem, carrier, tail)
    return "%s__%s__%s" % (lob, pdf.stem, tail)


def make(task):
    split, lob, pdf, k, out, name = task
    from fideon_synth import generic
    from fideon_synth.schema import CanonicalSchema
    from fideon_synth.values import Values
    pdf_out = Path(out) / split / "pdfs" / (name + ".pdf")
    gold_out = Path(out) / split / "gold json" / (name + ".json")
    row = {"split": split, "lob": lob, "carrier": pdf.parent.parent.name,
           "source": pdf.relative_to(ROOT / "Data" / "original data").as_posix(), "sample": k,
           "kind": "original" if k == 0 else "synthetic",
           "pdf": str(pdf_out.relative_to(out)), "gold": str(gold_out.relative_to(out))}
    if pdf_out.exists() and gold_out.exists() or \
            (Path(out) / "Flagged" / split / "pdfs" / (name + ".pdf")).exists():
        return None                               # made on an earlier run (or set aside, flagged)
    t = time.time()
    try:
        schema = CanonicalSchema.load(generic._lob_for(pdf, str(ROOT / "config" / "policy_check")),
                                      str(ROOT / "config" / "policy_check"))
        built = generic.synthesize(pdf, pdf_out, gold_out, schema,
                                   Values("%d:%s" % (k, row["source"])), seed=k, keep=k == 0)
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
    parser.add_argument("--originals", action="store_true",
                        help="also each source itself, scanned, with its own gold (<lob>__<source>__original), "
                             "in the same split as its synthetic twins")
    parser.add_argument("--originals-only", action="store_true",
                        help="make only the originals (the split and its band stay those of the full build "
                             "with --per-source synthetic twins), e.g. where the twins were made elsewhere")
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--ocr-cache", default=None,
                        help="where OCR readings are kept for all workers (default: <out>/.ocr_cache)")
    args = parser.parse_args(argv)
    args.originals = args.originals or args.originals_only
    if argv is None:                     # from a terminal: a closed session must not end it
        from fideon_synth import tmux
        tmux.ensure([sys.executable, str(Path(__file__).resolve())] + sys.argv[1:],
                    "build-dataset")
    out = Path(args.out)
    lobs = args.lob or PERSONAL
    # set before the workers start, so every one of them shares it
    os.environ.setdefault("FIDEON_OCR_CACHE", args.ocr_cache or str(out / ".ocr_cache"))
    # the workers are the parallelism: each keeps to one thread, or 30 of them
    # with a thread per core in every library run a machine out of threads
    for var in ("FIDEON_OCR_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(var, "1")

    found = sources(args.data, lobs)
    # the personal lines are one document type (the policy_check schemas):
    # its band is set by all the documents this build makes of it
    documents = sum(len(v) for v in found.values()) * (args.per_source + args.originals)
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
    # a file name two carriers' sources of one line share
    stems = defaultdict(set)
    for lob, splits in plan["lines"].items():
        for rel in (r for s in SPLITS for r in splits[s]):
            stems[(lob, Path(rel).stem)].add(rel)
    shared = {key for key, rels in stems.items() if len(rels) > 1}
    for lob, splits in plan["lines"].items():
        print("%-22s %6d %6d %6d" % (lob, *(len(splits[s]) for s in SPLITS)))
        for split in SPLITS:
            for rel in splits[split]:
                pdf = ROOT / "Data" / "original data" / rel
                # sample 0 is the source itself, in the split of its twins
                for k in range(0 if args.originals else 1,
                               1 if args.originals_only else args.per_source + 1):
                    tasks.append((split, lob, pdf, k, out, doc_name(lob, pdf, k, shared)))
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
    if not new:
        # a manifest from before the "kind" column: every row in it is synthetic
        with open(manifest, encoding="utf-8") as fh:
            old = list(csv.DictReader(fh))
        if old and "kind" not in old[0]:
            with open(manifest, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
                w.writeheader()
                for r in old:
                    r.setdefault("kind", "synthetic")
                    w.writerow(r)
    done = failed = 0
    start = time.time()
    tries = defaultdict(int)          # task -> how many times a worker died with it in flight
    with open(manifest, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            writer.writeheader()

        def record(row):
            nonlocal done, failed
            writer.writerow(row)
            fh.flush()
            done += 1
            failed += not row["ok"]
            if done % 10 == 0 or not row["ok"]:
                print("%5d made, %d with problems, %.0f min | %s %s" % (
                    done, failed, (time.time() - start) / 60,
                    "ok  " if row["ok"] else "PROBLEM", row["pdf"]), flush=True)

        pending = list(tasks)
        while pending:
            # a worker that dies (out of memory, a crash in a library) breaks
            # the pool: start fresh workers for what is left, instead of
            # waiting for ever on the document it held
            with ProcessPoolExecutor(args.workers) as pool:
                futures = {pool.submit(make, t): t for t in pending}
                broken = []
                for fut in as_completed(futures):
                    try:
                        row = fut.result()
                    except BrokenProcessPool:
                        broken.append(futures[fut])
                        continue
                    if row is not None:
                        record(row)
            if not broken:
                break
            print("  a worker died - starting the workers again for %d documents" % len(broken), flush=True)
            pending = []
            for t in broken:
                if made_already(t):
                    continue
                tries[t[:4]] += 1
                if tries[t[:4]] >= 3:                     # it takes a worker down every time
                    row = describe(t)
                    row.update(pages=0, fields=0, ok=False, seconds=0,
                               problems="a worker died making this document three times")
                    record(row)
                else:
                    pending.append(t)
    print("DONE: %d made this run, %d with problems" % (done, failed))
    return 0


def describe(task):
    """The manifest row of a task, before it is made."""
    split, lob, pdf, k, out, name = task
    return {"split": split, "lob": lob, "carrier": pdf.parent.parent.name,
            "kind": "original" if k == 0 else "synthetic",
            "source": pdf.relative_to(ROOT / "Data" / "original data").as_posix(), "sample": k,
            "pdf": str(Path(split) / "pdfs" / (name + ".pdf")),
            "gold": str(Path(split) / "gold json" / (name + ".json"))}


def made_already(task):
    row, out = describe(task), task[4]
    return (Path(out) / row["pdf"]).exists() and (Path(out) / row["gold"]).exists() \
        or (Path(out) / "Flagged" / row["pdf"]).exists()


if __name__ == "__main__":
    sys.exit(main())
