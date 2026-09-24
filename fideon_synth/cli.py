#!/usr/bin/env python3
"""
Command line for fideon-synth.

    fideon-synth --list
    fideon-synth --form leatherstocking_dwelling_fire --out ./out
    fideon-synth --form leatherstocking_dwelling_fire --out ./out --count 50
    fideon-synth --form ... --out ./out --no-scanned --seed 7

Exits non-zero if any document fails a check, so it can sit in a build
without anyone having to read the output to find out whether it worked.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .corpus import Corpus
from .forms import by_key, catalogue
from .scan import PROFILES
from .scan import by_key as scan_by_key
from .schema import available, resolve_dir


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    parser = argparse.ArgumentParser(
        prog="fideon-synth", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--form", default="amtrust_wc",
                        help="template key (default: amtrust_wc; see --list)")
    parser.add_argument("--out", default=r"E:\fideon-synth\output",
                        help="output directory (default: E:\\fideon-synth\\output)")
    parser.add_argument("--input-dir", default=r"Data\original PDFs",
                        help="original source documents directory (default: Data\\original PDFs)")
    parser.add_argument("--count", type=int, default=5,
                        help="how many documents to generate (default: 5)")
    parser.add_argument("--seed", type=int, default=0,
                        help="seed for generated documents (default 0)")
    parser.add_argument("--schema-dir", default=r"E:\fideon-synth\config\policy_check",
                        help="canonical_schema root (default: E:\\fideon-synth\\config\\policy_check)")
    parser.add_argument("--no-scanned", action="store_true",
                        help="skip the image-only scanned twins")
    parser.add_argument("--pdf-subdir", default="PDF",
                        help="subdirectory name for PDFs (default: PDF)")
    parser.add_argument("--gold-subdir", default="gold_json",
                        help="subdirectory name for gold JSON (default: gold_json)")
    parser.add_argument("--profile", action="append", default=None,
                        help="restrict to named scanner profiles; repeatable")
    parser.add_argument("--list", action="store_true",
                        help="show templates, schemas and scanner profiles")
    args = parser.parse_args(argv)

    if args.list:
        return _catalogue(args.schema_dir)

    from .generator import SyntheticGenerator

    print("  Using reference source: %s" % args.input_dir)
    print("  Target output: %s" % args.out)
    print("  Canonical schema: %s (wc v1.4.0)" % args.schema_dir)
    print("  Generating %d samples..." % args.count)
    print()

    generator = SyntheticGenerator(
        input_dir=args.input_dir,
        out_dir=args.out,
        schema_dir=args.schema_dir,
        pdf_subdir=args.pdf_subdir,
        gold_subdir=args.gold_subdir,
    )

    report = generator.generate(count=args.count, seed=args.seed, progress=_line)
    print()
    if not report.ok:
        print("  %d problem(s):" % len(report.problems))
        for problem in report.problems:
            print("    - %s" % problem)
        return 1

    n = len(report.documents)
    print("  %d synthetic PDFs and %d gold JSON files generated, every check passes" % (n, n))
    print("  -> PDFs: %s" % generator.pdf_dir)
    print("  -> Gold JSON: %s" % generator.gold_dir)
    return 0


def _line(built):
    print("  %s %-28s %d pp  %3d fields  %s"
          % ("ok " if built.ok else "FAIL", built.key, built.pages,
             built.fields, built.profile))
    for problem in built.problems:
        print("       - %s" % problem)


def _catalogue(schema_dir):
    print("\n  form templates")
    for key, lob, description in catalogue():
        print("    %-32s %-16s %s" % (key, lob, description))

    print("\n  scanner profiles")
    for profile in PROFILES:
        print("    %-32s %d dpi, jpeg %d   %s"
              % (profile.key, profile.dpi, profile.jpeg_quality,
                 profile.label))

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
