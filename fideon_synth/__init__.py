"""
fideon-synth - synthetic insurance documents with gold answers.

Build a corpus of declarations pages that look like the ones a pipeline will
actually meet, each with a gold JSON conforming to the canonical
``policy_check`` schema, and each with an image-only scanned twin.

    from fideon_synth import Corpus
    from fideon_synth.forms import LeatherstockingDwellingFire

    report = Corpus(LeatherstockingDwellingFire(), "out/").build(count=20)
    print(report.summary())

or from a shell::

    fideon-synth --list
    fideon-synth --form leatherstocking_dwelling_fire --out ./out --count 20

Four checks run on every document and the build reports failure rather than
writing quietly broken data: the gold validates against the live schema, the
premiums sum to the stated total, every value the gold claims is printed was
found on a page, and the scanned twin really has no text layer.

To add your own carrier form, subclass :class:`Template`, implement three
methods, and register it in ``fideon_synth.forms``. Everything above comes
with it. ``examples/new_form.py`` is a working skeleton.
"""

from .corpus import Built, Corpus, Report
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
