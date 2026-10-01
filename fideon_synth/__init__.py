"""
fideon-synth - synthetic insurance documents with gold answers.

The generic engine: any source PDF in, a synthetic digital twin and its gold
JSON out, conforming to the canonical ``policy_check`` schema for whatever
line of business the source's own folder names - no per-carrier or
per-document code.

    from fideon_synth import synthesize, generate_folder, CanonicalSchema, Values

    schema = CanonicalSchema.load("dwelling_fire")
    built = synthesize(source_pdf, out_pdf, out_gold, schema, Values(1), seed=1)

or every PDF under a folder at once::

    report = generate_folder("Data/original data", "out/", count=5)

or from a shell::

    fideon-synth --list
    fideon-synth --source "Data\\original data\\Markel American Insurance Company" --out ./out --count 1
"""

from .corpus import Built, Corpus, Report
from .generator import synthesize, generate_folder
from .draw import Column, Sheet, Table, render
from .fields import (NO_EVIDENCE, as_number, date_fv, derived, fmt_money, fv,
                     is_field, money, money_from, walk, yes_no)
from .scan import PROFILES, Profile, by_key as scan_profile, scan_pdf
from .schema import CanonicalSchema, available
from .template import Template
from .values import Values

__version__ = "1.0.0"

__all__ = [
    # building a corpus
    "Corpus", "Report", "Built", "Template",
    # the generic engine: any source PDF in, synthetic digital PDF + gold out
    "synthesize", "generate_folder",
    # the schema
    "CanonicalSchema", "available",
    # gold leaves
    "fv", "derived", "money", "money_from", "date_fv", "yes_no",
    "as_number", "fmt_money", "is_field", "walk", "NO_EVIDENCE",
    # drawing a form
    "Sheet", "Table", "Column", "render",
    # scanning
    "scan_pdf", "Profile", "PROFILES", "scan_profile",
    # synthetic values
    "Values",
]
