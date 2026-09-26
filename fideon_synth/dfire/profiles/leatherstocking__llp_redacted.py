"""
Leatherstocking Cooperative Insurance Company - "LLP_redacted.pdf"

Two-page Landlords Package declaration, renewal transaction (the following term of
"LLP -1"): as LLP -1 but the mortgagee prints a loan number and "ISAOA ATIMA" on the
lender line.  Redacted copy: overlays upsized, property / mortgagee lines tidied.
Shared logic lives in _leatherstocking_src.make_llp.

GAPS (printed but no canonical leaf): the Mail To block (repeats the producer) and the SIGNATURE
box's date (not printed; the signature is keyed).
"""

from . import _leatherstocking as L
from . import _leatherstocking_src as F

SOURCE = L.ROOT + "LLP_redacted.pdf"

_P = F.make_llp(dict(
    policy="29-2895-7714", eff="09/06/2023", exp="09/06/2024",
    cov_a="$284,500", prem_a="$933.00", cov_b="$28,500", liab="$1,000,000", prem_l="$110.00",
    mp_person="$500", prem_mp="$5.00", mp_occ="$10,000", eq="$31.00", alarm="-$19.00",
    total="$1,060.00", ded="$2,500.00", settle="RC", ziplus4=False, loan=True))

draw, REPLACE, gold, audit, GAPS, STATIC = _P.draw, _P.REPLACE, _P.gold, _P.audit, _P.GAPS, _P.STATIC
IGNORE_PAIRS = _P.IGNORE_PAIRS
FURNITURE = _P.FURNITURE
