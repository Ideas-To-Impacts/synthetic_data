"""
Leatherstocking Cooperative Insurance Company - "LLP -1_redacted.pdf"

Two-page Landlords Package declaration, renewal transaction: Coverage A, B, D, OLT
premises liability and medical payments, FL-345 equipment breakdown, ML-216 protective
device credit, a mortgagee (escrow billed) and the TRIA disclosure form.  Redacted copy:
the overlays are upsized and the property / mortgagee lines put on one line each.
Shared logic lives in _leatherstocking_src.make_llp.

GAPS (printed but no canonical leaf): the Mail To block (repeats the producer) and the SIGNATURE
box's date (not printed; the signature is keyed).
"""

from . import _leatherstocking as L
from . import _leatherstocking_src as F

SOURCE = L.ROOT + "LLP -1_redacted.pdf"

_P = F.make_llp(dict(
    policy="29-2895-7714", eff="09/06/2022", exp="09/06/2023",
    cov_a="$263,700", prem_a="$870.00", cov_b="$26,400", liab="$1,000,000", prem_l="$110.00",
    mp_person="$500", prem_mp="$5.00", mp_occ="$10,000", eq="$29.00", alarm="-$17.00",
    total="$997.00", ded="$2,500.00", settle="RC", ziplus4=True, loan=False))

draw, REPLACE, gold, audit, GAPS, STATIC = _P.draw, _P.REPLACE, _P.gold, _P.audit, _P.GAPS, _P.STATIC
IGNORE_PAIRS = _P.IGNORE_PAIRS
FURNITURE = _P.FURNITURE
