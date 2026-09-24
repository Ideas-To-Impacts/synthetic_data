"""
Leatherstocking Cooperative Insurance Company - "DFIRE_redacted.pdf"

Two-page Dwelling Fire declaration, renewal transaction, with a mortgagee block and
Coverage M (per person / per occurrence).  Redacted copy: the named-insured, agency
and property overlays are tiny; this profile upsizes them, restores the agency block
(name / code / street / city), the property line, the plan sentence and the mortgagee
lines.  Shared logic lives in _leatherstocking_src.make_dfire (same layout as R-DFIRE).

GAPS (printed but no canonical leaf): the "Property: 1 of 1" counter, the Mail To block (repeats the
producer) and the SIGNATURE / DATE box.
"""

from . import _leatherstocking as L
from . import _leatherstocking_src as F

SOURCE = L.ROOT + "DFIRE_redacted.pdf"

_P = F.make_dfire(dict(
    policy="34-7817-53119", eff="10/07/2023", exp="10/07/2024",
    cov_a="$149,700", prem_a="$551.00", liab="$1,000,000", prem_l="$82.00",
    mp_person="$1,000", prem_mp="$8.00", mp_occ="$25,000", lead="-$6.00", haz="$138.00",
    total="$773.00", ded="$500.00", settle="RC",
    modifies=("Coverage D - Additional Living Expense / Loss of Rent, Coverage A - Residence, "
              "Coverage B - Related Private Structures")))

draw, REPLACE, gold, audit, GAPS, STATIC = _P.draw, _P.REPLACE, _P.gold, _P.audit, _P.GAPS, _P.STATIC
IGNORE_PAIRS = _P.IGNORE_PAIRS
FURNITURE = _P.FURNITURE
