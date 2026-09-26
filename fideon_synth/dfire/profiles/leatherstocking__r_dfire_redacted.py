"""
Leatherstocking Cooperative Insurance Company - "R-DFIRE_redacted.pdf"

Two-page Dwelling Fire renewal declaration (the prior term of the same policy as
DFIRE_redacted), with a mortgagee block and Coverage M.  It prints no separate prior
policy number: the Policy ID carries over, so only the Renewal transaction is stated.
Shared logic lives in _leatherstocking_src.make_dfire.

GAPS (printed but no canonical leaf): the Mail To block (repeats the producer) and the SIGNATURE
box's date (not printed; the signature is keyed).
"""

from . import _leatherstocking as L
from . import _leatherstocking_src as F

SOURCE = L.ROOT + "R-DFIRE_redacted.pdf"

_P = F.make_dfire(dict(
    policy="34-7817-53119", eff="10/07/2022", exp="10/07/2023",
    cov_a="$138,700", prem_a="$512.00", liab="$1,000,000", prem_l="$82.00",
    mp_person="$1,000", prem_mp="$8.00", mp_occ="$25,000", lead="-$6.00", haz="$128.00",
    total="$724.00", ded="$500.00", settle="RC",
    modifies=("Coverage B - Related Private Structures, Coverage D - Additional Living Expense / "
              "Loss of Rent, Coverage A - Residence")))

draw, REPLACE, gold, audit, GAPS, STATIC = _P.draw, _P.REPLACE, _P.gold, _P.audit, _P.GAPS, _P.STATIC
IGNORE_PAIRS = _P.IGNORE_PAIRS
FURNITURE = _P.FURNITURE
