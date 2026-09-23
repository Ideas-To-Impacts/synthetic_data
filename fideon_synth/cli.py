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
    parser.add_argument("--form", help="template key; see --list")
    parser.add_argument("--out", help="output directory")
    parser.add_argument("--count", type=int, default=None,
                        help="how many documents; default is the "
                             "hand-written set")
    parser.add_argument("--seed", type=int, default=0,
                        help="seed for generated documents (default 0)")
    parser.add_argument("--schema-dir", default=None,
                        help="canonical_schema root; also read from "
                             "FIDEON_CANONICAL_SCHEMA")
    parser.add_argument("--no-scanned", action="store_true",
                        help="skip the image-only scanned twins")
    parser.add_argument("--profile", action="append", default=None,
                        help="restrict to named scanner profiles; repeatable")
    parser.add_argument("--list", action="store_true",
                        help="show templates, schemas and scanner profiles")
    args = parser.parse_args(argv)

    if args.list:
        return _catalogue(args.schema_dir)
    if not args.form or not args.out:
        parser.error("--form and --out are required (or use --list)")

    template = by_key(args.form)
    profiles = ([scan_by_key(p) for p in args.profile]
                if args.profile else None)
    corpus = Corpus(template, args.out, schema_dir=args.schema_dir,
                    scanned=not args.no_scanned, profiles=profiles)

    print("  %s -> %s v%s" % (template.key, corpus.schema.lob,
                              corpus.schema.version))
    print()
    report = corpus.build(count=args.count, seed=args.seed,
                          progress=_line)
    print()
    if not report.ok:
        print("  %d problem(s):" % len(report.problems))
        for problem in report.problems:
            print("    - %s" % problem)
        return 1

    n = len(report.documents)
    print("  %d digital + %d scanned, %d gold files, every check passes"
          % (n, 0 if args.no_scanned else n, n if args.no_scanned else n * 2))
    for directory in ([corpus.pdf_dir, corpus.gold_dir]
                      + ([] if args.no_scanned
                         else [corpus.scan_dir, corpus.scan_gold_dir])):
        print("  -> %s" % directory)
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
