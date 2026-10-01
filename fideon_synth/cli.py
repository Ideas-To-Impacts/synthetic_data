#!/usr/bin/env python3
"""
Command line for fideon-synth.

    fideon-synth --list
    fideon-synth --out ./out --count 1
    fideon-synth --source "Data\\original data\\Markel American Insurance Company" --out ./out --count 1

The generic engine: a source PDF, or a folder whose PDFs are all used. The
line of business is read straight off each source's own folder name, never
assumed - one call covers every line of business there is a canonical schema
for. With no --source, every source under --input-dir runs.

Exits non-zero if any document fails a check, so it can sit in a build
without anyone having to read the output to find out whether it worked.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .schema import available, resolve_dir


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    parser = argparse.ArgumentParser(
        prog="fideon-synth", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=r"E:\fideon-synth\output",
                        help="output directory (default: E:\\fideon-synth\\output)")
    parser.add_argument("--input-dir", default=r"Data\original data",
                        help="original source documents directory (default: Data\\original data)")
    parser.add_argument("--count", type=int, default=5,
                        help="how many documents to generate per source PDF (default: 5)")
    parser.add_argument("--seed", type=int, default=0,
                        help="seed for generated documents (default 0)")
    parser.add_argument("--schema-dir", default=r"E:\fideon-synth\config\policy_check",
                        help="canonical_schema root (default: E:\\fideon-synth\\config\\policy_check)")
    parser.add_argument("--pdf-subdir", default="PDF",
                        help="subdirectory name for PDFs (default: PDF)")
    parser.add_argument("--gold-subdir", default="gold_json",
                        help="subdirectory name for gold JSON (default: gold_json)")
    parser.add_argument("--list", action="store_true",
                        help="show the canonical schemas available")
    parser.add_argument("--source", default=None,
                        help="a source PDF, or a folder whose PDFs are all used; "
                             "--count is then samples per PDF. Default: every "
                             "source under --input-dir.")
    args = parser.parse_args(argv)

    if args.list:
        return _catalogue(args.schema_dir)

    if argv is None:                     # from a terminal: a closed session must not end it
        from . import tmux
        tmux.ensure([sys.executable, "-m", "fideon_synth.cli"] + sys.argv[1:], "fideon-synth")

    return _generic(args, source=args.source or args.input_dir)


def _generic(args, source):
    from .generator import generate_folder

    source = Path(source)
    if not source.exists():
        print("  Source not found: %s" % source)
        return 2
    print("  Source: %s" % source)
    print("  Target output: %s" % args.out)
    print("  %d sample(s) per PDF" % args.count)
    print()
    report = generate_folder(source, args.out, schema_dir=args.schema_dir,
                             count=args.count, seed=args.seed,
                             pdf_subdir=args.pdf_subdir, gold_subdir=args.gold_subdir,
                             progress=_line)
    print()
    n = len(report.documents)
    bad = [d for d in report.documents if not d.ok]
    print("  %d synthetic PDFs, %d with problems" % (n, len(bad)))
    print("  -> PDFs: %s" % (Path(args.out) / args.pdf_subdir))
    print("  -> Gold JSON: %s" % (Path(args.out) / args.gold_subdir))
    return 1 if bad else 0


def _line(built):
    print("  %s %-28s %d pp  %3d fields  %s"
          % ("ok " if built.ok else "FAIL", built.key, built.pages,
             built.fields, built.profile))
    for problem in built.problems:
        print("       - %s" % problem)


def _catalogue(schema_dir):
    print("\n  canonical schemas")
    try:
        root = resolve_dir(schema_dir)
        names = available(schema_dir)
        print("    %s" % root)
        for i in range(0, len(names), 4):
            print("      " + "  ".join("%-22s" % n for n in names[i:i + 4]))
    except FileNotFoundError as exc:
        print("    %s" % str(exc).splitlines()[0])
        print("    set FIDEON_CANONICAL_SCHEMA to the canonical_schema folder")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
