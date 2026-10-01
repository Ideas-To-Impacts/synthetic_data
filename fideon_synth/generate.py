#!/usr/bin/env python3
"""Synthetic variations of one real policy PDF, each with its gold JSON.

    python generator/generate.py                       # 2 variations of the default source
    python generator/generate.py --count 5
    python generator/generate.py --source <pdf> --lob personal_auto

Runs the repo's own generic engine (`fideon_synth.generator.synthesize`): it
reads the source's text layer, replaces every identifying value in place
(names, addresses, policy numbers, VINs, phones; dates shifted together so the
term stays valid), and writes the gold JSON from that same pass. It then
re-reads the saved PDF to prove the gold, and fails if any original value
survives.

Two things this wrapper does that `fideon-synth --source` does not:

- **Names the line of business.** The CLI takes it from the source's folder
  name, and the folder here is `autop`, which is not a schema -- so the CLI
  would silently fall back to `_fallback.json`. Here it is `personal_auto`
  unless `--lob` says otherwise.
- **Uses FideonSLM's canonical schema** (`config/canonical_schema/policy_check/`,
  personal_auto v1.9.0) rather than this repo's older copy (v1.5.0). The newer
  one is a strict superset: every field of the old one plus 117 more.

Output, next to this script:

    generator/PDF/<stem>_synth_001.pdf
    generator/gold_json/<stem>_synth_001.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from fideon_synth.generator import synthesize  # noqa: E402
from fideon_synth.schema import CanonicalSchema  # noqa: E402
from fideon_synth.values import Values  # noqa: E402

sys.path.insert(0, str(HERE))
from vary import vary  # noqa: E402

DEFAULT_SOURCE = REPO / "Data" / "POLICIES-FINAL" / "Progressive" / "autop" / "progressive_autop.pdf"
DEFAULT_SCHEMA_DIR = Path.home() / "Desktop" / "FideonSLM" / "config" / "canonical_schema"


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--lob", default="personal_auto")
    ap.add_argument("--schema-dir", type=Path, default=DEFAULT_SCHEMA_DIR)
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=HERE)
    ap.add_argument("--no-vary", dest="vary", action="store_false",
                    help="skip generator/vary.py (premiums, limits, ages, vehicle stay as the source's)")
    args = ap.parse_args(argv)

    schema = CanonicalSchema.load(args.lob, args.schema_dir)
    pdf_dir, gold_dir = args.out / "PDF", args.out / "gold_json"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)
    print(f"  source: {args.source}")
    print(f"  schema: {schema!r}  ({schema.path})")

    failed = 0
    for index in range(1, args.count + 1):
        name = f"{args.source.stem}_synth_{index:03d}"
        # Same seeding as fideon_synth.generator.generate_folder, so a run here
        # and a run through the CLI give the same document for the same index.
        vals = Values(f"{args.seed}:{args.source.name}:{index}")
        built = synthesize(args.source, pdf_dir / f"{name}.pdf", gold_dir / f"{name}.json",
                           schema, vals, seed=index)
        # The gold carries every canonical leaf, `null` where the page is
        # silent, and `null` fails FieldValue's `type: object`. The README
        # calls that "expected, reported, not a build error", but `built.ok`
        # counts it -- so every document read as FAIL. Count it, don't fail on it.
        silent = [p for p in built.problems if p.startswith("None is not of type 'object'")]
        real = [p for p in built.problems if p not in silent]
        if not real and args.vary:
            # The engine keeps every amount as printed; give this copy its own.
            real = vary(pdf_dir / f"{name}.pdf", gold_dir / f"{name}.json",
                        seed=f"{args.seed}:{args.source.name}:{index}:figures")
        print(f"  {'FAIL' if real else 'ok  '} {name}  {built.pages} pp  {built.fields} fields"
              f"  ({len(silent)} schema fields not stated on the page)")
        for problem in real:
            print(f"       - {problem}")
        failed += bool(real)

    print(f"  -> {pdf_dir}\n  -> {gold_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
