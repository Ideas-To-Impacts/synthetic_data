#!/usr/bin/env python3
"""
The shortest useful thing you can do with fideon-synth.

    python examples/quickstart.py

Builds five declarations with gold answers and scanned twins, then shows what
a gold leaf looks like and what the build checked.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fideon_synth import Corpus
from fideon_synth.fields import walk
from fideon_synth.forms import LeatherstockingDwellingFire

import json


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(__file__).resolve().parent / "_quickstart_output"

    report = Corpus(LeatherstockingDwellingFire(), out).build()
    print(report.summary())
    if not report.ok:
        return 1

    first = report.documents[0]
    gold = json.loads(first.gold.read_text("utf-8"))

    print("\n  one leaf, as the schema defines it")
    print("   ", json.dumps(gold["policy"]["policy_number"], indent=None))

    printed = [f for _, f in walk(gold)
               if f["confidence"]["source"] == "deterministic"]
    implied = [f for _, f in walk(gold)
               if f["confidence"]["source"] == "structural"]
    print("\n  %d values are printed on the page and quotable" % len(printed))
    print("  %d are implied by it and marked structural" % len(implied))
    print("  %d schema leaves this document does not state"
          % len(gold["fideon:absent"]))

    print("\n  digital  %s" % first.pdf)
    print("  scanned  %s  (%s)" % (first.scanned, first.profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
