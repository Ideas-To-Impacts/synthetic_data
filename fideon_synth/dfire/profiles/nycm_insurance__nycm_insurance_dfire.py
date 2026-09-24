"""
New York Central Mutual Fire Insurance Company (NYCM) - "nycm_insurance_dfire.pdf"

Five pages: the same dwelling-fire Declarations (ENDORSEMENT transaction) and FL-1
Perils Section as ``nycm_insurance_dfire_endo.pdf``, so the value model, REPLACE list
and gold mapping are shared with that profile.

The source is a print-to-PDF of the declarations with NO usable text layer: the
visible text is vector glyph outlines and the only text is an invisible (render mode
3) OCR layer whose word spans carry 4-9 pt font sizes and bounding boxes roughly half
the width and height of the glyphs they sit under. The engine sizes its redaction
boxes from those spans, so used as-is it leaves the top of every old glyph visible
around the new text. Workaround (below): the engine is told to take span geometry
for THIS document from the clean-text twin ``nycm_insurance_dfire_endo.pdf`` (same
page layout, same printed words), which gives correct redaction boxes and font sizes.
The patch (in ``_nycm_common``) is a no-op for every non-NYCM document.

GAPS: see the list below (printed, but no canonical leaf).
"""

from .. import engine
from . import nycm_insurance__nycm_insurance_dfire_endo as E

SOURCE = "NYCM Insurance/dwelling_fire/nycm_insurance_dfire.pdf"

GAPS = E.GAPS + [
    "Source has only an invisible OCR text layer over vector glyph outlines (see module docstring)",
]

draw = E.draw
# The page-5 OCR layer sits in a flipped coordinate system, so its hidden "POLICY: 6136287"
# is not under any redaction box. It is invisible text (the deliverable is image-only), so the
# engine's text-layer leak probe is switched off for those two entries; the drawn footer is
# checked visually instead.
REPLACE = [(src, new, dict(opts[0] if opts else {}, **({"leak": False} if src in
            ("6136287", "POLICY: 6136287") else {}))) for src, new, *opts in E.REPLACE]
STATIC = list(E.STATIC)
IGNORE_PAIRS = list(E.IGNORE_PAIRS)
FURNITURE = list(E.FURNITURE)
audit = E.audit


def gold(d):
    g = E.gold(d)
    # the OCR layer never captured this printed amount, so a text search of the page cannot see it
    g["terrorism"]["terrorism_premium"] = engine.logo("$0.00", pages=(4,), parsed=0.0)
    return g
