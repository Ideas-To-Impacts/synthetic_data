"""
The five hand-written Leatherstocking declarations.

Kept apart from the template so the two kinds of variant are obviously
different things. These five were written by hand for realism - a coherent
household, a real agency two towns over, a schedule an underwriter would
recognise. Past the fifth, ``_generated`` in the template composes them, and
that is the right trade: careful beyond about a dozen documents stops being
careful and starts being repetitive.

Each is a plain dict. Nothing outside the template reads it.

  1  new business, owner-occupied, Basic Form, no fees
  2  renewal of a tenant-occupied rental: Coverage B and D, medical payments
  3  seasonal dwelling: separate wind/hail deductible, a fee, longest schedule
  4  the small one: masonry, ACV, $500 deductible, shortest schedule
  5  an LLC on the insured line, mailing to a PO box away from the risk

Coverage rows are ``(name, limit, premium)``; Section II rows carry a fourth
element, the italic qualifier the form prints in the description cell. A
``limit`` of "***" is the carrier's notation for "no separate limit applies" -
printed literally, and not a number.
"""

from __future__ import annotations

from .leatherstocking_dwelling_fire import DISCLAIMER

HAND_WRITTEN = [
    # -- 1 -------------------------------------------------------------------
    # New business, owner-occupied, the plainest of the five: Basic Form, no
    # fees, two named insureds on one dwelling.
    {
        "key": "df_001_piseco_new",
        "transaction": "New Policy",
        "is_renewal": False,
        "policy_number": "10-2026-14207",
        "effective_date": "03/18/2026",
        "expiration_date": "03/18/2027",
        "effective_time": "12:01AM",
        "time_zone": "Standard Time",
        "agency": {
            "name": "Northfield Ridge Agency Inc -",
            "name_2": "TRL",
            "line_1": "88 Main St",
            "city": "Speculator", "state": "NY", "postal_code": "12164",
            "work": "(518) 548-3120", "fax": "(518) 548-3125",
            "producer_code": "TRL",
        },
        "insureds": ["Hollis Brackenridge", "Juniper Brackenridge"],
        "entity_type": "Individual",
        "insured_address": {
            "line_1": "44 Tannery Flats",
            "city": "Piseco", "state": "NY", "postal_code": "12139",
        },
        "property": {
            "number": 1, "of": 1,
            "line_1": "86 Tannery Flats",
            "city": "Piseco", "state": "NY", "postal_code": "12139",
            "county": "Hamilton",
        },
        "section_i": [
            ("Coverage A - Residence", "$198,000", 742.00),
            ("EC - Residence", "***", 104.00),
            ("VMM - Residence", "***", 12.00),
            ("Coverage C - Personal Property", "$8,000", 24.00),
            ("EC - Personal Property", "***", 2.00),
            ("VMM - Personal Property", "***", 1.00),
        ],
        "section_ii": [
            ("Coverage L - Premises Liability", "$300,000", 58.00,
             "(Each Occurrence)"),
            ("ML-59 - Lead Exclusion", "***", -5.00, None),
        ],
        "optional": [
            ("ML-WD - Water Backup-Sewers and Drains", "***", 25.00),
            ("SM-26 - Automatic Increase, RC", "***", 18.00),
            ("Hazardous Conditions - Occupancy", "***", 186.00),
        ],
        "fees": [],
        "rating": [
            ("Coverage A - Residence", [
                ("Deductible", "$1,000.00"),
                ("Loss Settlement", "RC"),
                ("Construction", "Frame"),
                ("Protection", "Semi-Protected"),
                ("Zone", "All Other"),
                ("Form", "Basic Form (FL-1)"),
                ("Occupancy", "1-2 Family"),
                ("Disclaimer", DISCLAIMER),
            ]),
            ("Coverage C - Personal Property", [
                ("Deductible", "$1,000.00"),
                ("Construction", "Frame"),
                ("Protection", "Semi-Protected"),
                ("Zone", "All Other"),
                ("Occupancy", "1-2 Family"),
                ("Form", "Basic Form (FL-1)"),
            ]),
            ("Coverage L - Premises Liability", [
                ("Classification", "Dwelling - 1 Family"),
                ("Territory Code", "19 - All Others"),
            ]),
            ("Hazardous Conditions - Occupancy", [
                ("Condition", "Unoccupancy"),
            ]),
            ("SM-26 Automatic Increase, RC", [
                ("Modifies Coverage(s) at Renewal",
                 "Coverage A - Residence, Coverage B - Related Private "
                 "Structures, Coverage D - Additional Living Expense / "
                 "Loss of Rent"),
            ]),
        ],
        "forms":
            "FL-18 (6/96) Intentional Act Exclusion, FL-20 (1/92) Agreement, "
            "FL-83 (02/02) Amendment of Policy Conditions, FL-90 (11/06) "
            "Clarification Endorsement, FMD-1 (12/94) Important Flood "
            "Insurance Notice, PR (3/01) Notice of Privacy Policy, LCI-J "
            "(9/17) By-Laws, FL-21 05/10 Suit Against Us Amendatory "
            "Endorsement, FL-1R (1/92) Causes of Loss, ML-WD (1.1) Water "
            "Damage-Sewers and Drains, FL-OLT (1/92) Premises Liability "
            "Insurance Coverage Part, ML-59 (6/99) Lead Exclusion, SM-26 "
            "(7/00) Automatic Increase, FL-80 (7/96) Redefinition of Insured",
        "dwelling": {
            "occupancy_type": "1-2 Family",
            "tenant_occupied": False,
            "construction_type": "Frame",
            "protection_class": "Semi-Protected",
            "territory_code": "19 - All Others",
            "loss_settlement_basis": "RC",
            "covered_causes_of_loss": "Basic Form (FL-1)",
            "seasonal_or_vacant": None,
            "hazardous_conditions_occupancy": "Unoccupancy",
            "classification_description": "Dwelling - 1 Family",
            "aop_deductible": 1000.00,
        },
    },

    # -- 2 -------------------------------------------------------------------
    # Renewal of a tenant-occupied rental: Coverage B and D replace C, medical
    # payments appears, Broad Form, a single named insured.
    {
        "key": "df_002_milford_renewal",
        "transaction": "Renewal Policy",
        "is_renewal": True,
        "policy_number": "10-2026-15881",
        "effective_date": "07/01/2026",
        "expiration_date": "07/01/2027",
        "effective_time": "12:01AM",
        "time_zone": "Standard Time",
        "agency": {
            "name": "Cooperstown Valley Insurance Services -",
            "name_2": "JLM",
            "line_1": "7 Chestnut St",
            "city": "Cooperstown", "state": "NY", "postal_code": "13326",
            "work": "(607) 293-4180", "fax": "(607) 293-4188",
            "producer_code": "JLM",
        },
        "insureds": ["Waldemar Pettigrew"],
        "entity_type": "Individual",
        "insured_address": {
            "line_1": "12 Susquehanna Terrace",
            "city": "Milford", "state": "NY", "postal_code": "13807",
        },
        "property": {
            "number": 1, "of": 1,
            "line_1": "231 Fish Creek Rd",
            "city": "Milford", "state": "NY", "postal_code": "13807",
            "county": "Otsego",
        },
        "section_i": [
            ("Coverage A - Residence", "$312,000", 1046.00),
            ("EC - Residence", "***", 151.00),
            ("VMM - Residence", "***", 17.00),
            ("Coverage B - Related Private Structures", "$31,200", 38.00),
            ("Coverage D - Additional Living Expense / Loss of Rent",
             "$24,960", 29.00),
        ],
        "section_ii": [
            ("Coverage L - Premises Liability", "$500,000", 71.00,
             "(Each Occurrence)"),
            ("Coverage M - Medical Payments", "$2,000", 9.00, "(Each Person)"),
            ("FL-52A Trampoline Exclusion", "***", -2.00, None),
        ],
        "optional": [
            ("ML-WD - Water Backup-Sewers and Drains", "***", 25.00),
            ("ML-54 - Theft Coverage", "***", 64.00),
        ],
        "fees": [],
        "rating": [
            ("Coverage A - Residence", [
                ("Deductible", "$1,000.00"),
                ("Loss Settlement", "RC"),
                ("Construction", "Frame"),
                ("Protection", "Protected"),
                ("Zone", "All Other"),
                ("Form", "Broad Form (FL-2)"),
                ("Occupancy", "Tenant Occupied"),
                ("Disclaimer", DISCLAIMER),
            ]),
            ("Coverage B - Related Private Structures", [
                ("Deductible", "$1,000.00"),
                ("Construction", "Frame"),
                ("Protection", "Protected"),
                ("Form", "Broad Form (FL-2)"),
            ]),
            ("Coverage L - Premises Liability", [
                ("Classification", "Dwelling - 1 Family Tenant Occupied"),
                ("Territory Code", "07 - Otsego"),
            ]),
            ("ML-54 Theft Coverage", [
                ("Limit", "Coverage C limit applies"),
                ("Deductible", "$1,000.00"),
            ]),
        ],
        "forms":
            "FL-52A (12/98) Trampoline Exclusion, FL-18 (6/96) Intentional "
            "Act Exclusion, FL-20 (1/92) Agreement, FL-83 (02/02) Amendment "
            "of Policy Conditions, FL-90 (11/06) Clarification Endorsement, "
            "FMD-1 (12/94) Important Flood Insurance Notice, PR (3/01) "
            "Notice of Privacy Policy, LCI-J (9/17) By-Laws, FL-21 05/10 "
            "Suit Against Us Amendatory Endorsement, FL-2R (1/92) Causes of "
            "Loss, ML-WD (1.1) Water Damage-Sewers and Drains, ML-54 (6/99) "
            "Theft Coverage, FL-OLT (1/92) Premises Liability Insurance "
            "Coverage Part, FL-80 (7/96) Redefinition of Insured",
        "dwelling": {
            "occupancy_type": "Tenant Occupied",
            "tenant_occupied": True,
            "construction_type": "Frame",
            "protection_class": "Protected",
            "territory_code": "07 - Otsego",
            "loss_settlement_basis": "RC",
            "covered_causes_of_loss": "Broad Form (FL-2)",
            "seasonal_or_vacant": None,
            "hazardous_conditions_occupancy": None,
            "classification_description": "Dwelling - 1 Family Tenant Occupied",
            "aop_deductible": 1000.00,
        },
    },

    # -- 3 -------------------------------------------------------------------
    # Seasonal dwelling: the only one carrying a separate wind/hail deductible
    # and a policy fee, and the largest schedule.
    {
        "key": "df_003_andes_seasonal",
        "transaction": "New Policy",
        "is_renewal": False,
        "policy_number": "10-2027-10346",
        "effective_date": "01/12/2027",
        "expiration_date": "01/12/2028",
        "effective_time": "12:01AM",
        "time_zone": "Standard Time",
        "agency": {
            "name": "Catskill Headwaters Agency LLC -",
            "name_2": "PDQ",
            "line_1": "214 Delaware Ave",
            "city": "Delhi", "state": "NY", "postal_code": "13753",
            "work": "(607) 746-9022", "fax": "(607) 746-9027",
            "producer_code": "PDQ",
        },
        "insureds": ["Cornelius Vantassel", "Adelaide Vantassel",
                     "Rutherford Vantassel"],
        "entity_type": "Individual",
        "insured_address": {
            "line_1": "9 Bramble Hollow Rd",
            "city": "Andes", "state": "NY", "postal_code": "13731",
        },
        "property": {
            "number": 1, "of": 1,
            "line_1": "1408 Palmer Hill Rd",
            "city": "Andes", "state": "NY", "postal_code": "13731",
            "county": "Delaware",
        },
        "section_i": [
            ("Coverage A - Residence", "$425,000", 1584.00),
            ("EC - Residence", "***", 214.00),
            ("VMM - Residence", "***", 23.00),
            ("Coverage B - Related Private Structures", "$42,500", 52.00),
            ("Coverage C - Personal Property", "$21,250", 61.00),
            ("EC - Personal Property", "***", 8.00),
        ],
        "section_ii": [
            ("Coverage L - Premises Liability", "$500,000", 66.00,
             "(Each Occurrence)"),
            ("ML-59 - Lead Exclusion", "***", -5.00, None),
            ("FL-52A Trampoline Exclusion", "***", -2.00, None),
        ],
        "optional": [
            ("ML-WD - Water Backup-Sewers and Drains", "***", 25.00),
            ("SM-26 - Automatic Increase, RC", "***", 27.00),
            ("Hazardous Conditions - Occupancy", "***", 318.00),
            ("Seasonal Dwelling Surcharge", "***", 95.00),
        ],
        "fees": [("Policy Fee", 25.00)],
        "rating": [
            ("Coverage A - Residence", [
                ("Deductible", "$2,500.00"),
                ("Wind/Hail Deductible", "$5,000.00"),
                ("Loss Settlement", "RC"),
                ("Construction", "Frame"),
                ("Protection", "Unprotected"),
                ("Zone", "All Other"),
                ("Form", "Basic Form (FL-1)"),
                ("Occupancy", "Seasonal"),
                ("Disclaimer", DISCLAIMER),
            ]),
            ("Coverage C - Personal Property", [
                ("Deductible", "$2,500.00"),
                ("Construction", "Frame"),
                ("Protection", "Unprotected"),
                ("Zone", "All Other"),
                ("Occupancy", "Seasonal"),
                ("Form", "Basic Form (FL-1)"),
            ]),
            ("Coverage L - Premises Liability", [
                ("Classification", "Dwelling - 1 Family Seasonal"),
                ("Territory Code", "22 - Delaware"),
            ]),
            ("Hazardous Conditions - Occupancy", [
                ("Condition", "Seasonal Unoccupancy"),
            ]),
            ("SM-26 Automatic Increase, RC", [
                ("Modifies Coverage(s) at Renewal",
                 "Coverage A - Residence, Coverage B - Related Private "
                 "Structures"),
            ]),
        ],
        "forms":
            "FL-52A (12/98) Trampoline Exclusion, FL-18 (6/96) Intentional "
            "Act Exclusion, FL-20 (1/92) Agreement, FL-83 (02/02) Amendment "
            "of Policy Conditions, FL-90 (11/06) Clarification Endorsement, "
            "FMD-1 (12/94) Important Flood Insurance Notice, LCI-11 (4/91) "
            "Senior Citizen Form, PR (3/01) Notice of Privacy Policy, LCI-J "
            "(9/17) By-Laws, FL-21 05/10 Suit Against Us Amendatory "
            "Endorsement, FL-1R (1/92) Causes of Loss, ML-WD (1.1) Water "
            "Damage-Sewers and Drains, FL-OLT (1/92) Premises Liability "
            "Insurance Coverage Part, ML-59 (6/99) Lead Exclusion, SM-26 "
            "(7/00) Automatic Increase, FL-80 (7/96) Redefinition of "
            "Insured, LCIC-WH (03/19) Windstorm or Hail Deductible",
        "dwelling": {
            "occupancy_type": "Seasonal",
            "tenant_occupied": False,
            "construction_type": "Frame",
            "protection_class": "Unprotected",
            "territory_code": "22 - Delaware",
            "loss_settlement_basis": "RC",
            "covered_causes_of_loss": "Basic Form (FL-1)",
            "seasonal_or_vacant": "Seasonal",
            "hazardous_conditions_occupancy": "Seasonal Unoccupancy",
            "classification_description": "Dwelling - 1 Family Seasonal",
            "aop_deductible": 2500.00,
            "wind_hail_deductible": 5000.00,
        },
    },

    # -- 4 -------------------------------------------------------------------
    # The small one: masonry, actual cash value, a $500 deductible, no
    # surcharge. Shortest schedule, so it puts the page break somewhere else.
    {
        "key": "df_004_oxford_renewal",
        "transaction": "Renewal Policy",
        "is_renewal": True,
        "policy_number": "10-2026-16920",
        "effective_date": "09/29/2026",
        "expiration_date": "09/29/2027",
        "effective_time": "12:01AM",
        "time_zone": "Standard Time",
        "agency": {
            "name": "Chenango Valley Coverage Group -",
            "name_2": "RBF",
            "line_1": "41 South Broad St",
            "city": "Norwich", "state": "NY", "postal_code": "13815",
            "work": "(607) 335-2410", "fax": "(607) 335-2415",
            "producer_code": "RBF",
        },
        "insureds": ["Perpetua Danforth", "Ignatius Danforth"],
        "entity_type": "Individual",
        "insured_address": {
            "line_1": "57 Hillcrest Terrace",
            "city": "Oxford", "state": "NY", "postal_code": "13830",
        },
        "property": {
            "number": 1, "of": 1,
            "line_1": "57 Hillcrest Terrace",
            "city": "Oxford", "state": "NY", "postal_code": "13830",
            "county": "Chenango",
        },
        "section_i": [
            ("Coverage A - Residence", "$145,000", 498.00),
            ("EC - Residence", "***", 76.00),
            ("VMM - Residence", "***", 9.00),
            ("Coverage C - Personal Property", "$14,500", 41.00),
            ("EC - Personal Property", "***", 6.00),
            ("VMM - Personal Property", "***", 1.00),
        ],
        "section_ii": [
            ("Coverage L - Premises Liability", "$100,000", 44.00,
             "(Each Occurrence)"),
            ("Coverage M - Medical Payments", "$1,000", 7.00, "(Each Person)"),
        ],
        "optional": [
            ("ML-WD - Water Backup-Sewers and Drains", "***", 25.00),
            ("ML-121 - Personal Injury", "***", 16.00),
        ],
        "fees": [],
        "rating": [
            ("Coverage A - Residence", [
                ("Deductible", "$500.00"),
                ("Loss Settlement", "ACV"),
                ("Construction", "Masonry"),
                ("Protection", "Protected"),
                ("Zone", "All Other"),
                ("Form", "Basic Form (FL-1)"),
                ("Occupancy", "1-2 Family"),
                ("Disclaimer", DISCLAIMER),
            ]),
            ("Coverage C - Personal Property", [
                ("Deductible", "$500.00"),
                ("Construction", "Masonry"),
                ("Protection", "Protected"),
                ("Zone", "All Other"),
                ("Occupancy", "1-2 Family"),
                ("Form", "Basic Form (FL-1)"),
            ]),
            ("Coverage L - Premises Liability", [
                ("Classification", "Dwelling - 2 Family"),
                ("Territory Code", "14 - Chenango"),
            ]),
            ("ML-121 Personal Injury", [
                ("Limit", "Coverage L limit applies"),
            ]),
        ],
        "forms":
            "FL-18 (6/96) Intentional Act Exclusion, FL-20 (1/92) Agreement, "
            "FL-83 (02/02) Amendment of Policy Conditions, FL-90 (11/06) "
            "Clarification Endorsement, FMD-1 (12/94) Important Flood "
            "Insurance Notice, PR (3/01) Notice of Privacy Policy, LCI-J "
            "(9/17) By-Laws, FL-21 05/10 Suit Against Us Amendatory "
            "Endorsement, FL-1R (1/92) Causes of Loss, ML-WD (1.1) Water "
            "Damage-Sewers and Drains, ML-121 (6/99) Personal Injury, "
            "FL-OLT (1/92) Premises Liability Insurance Coverage Part, "
            "FL-80 (7/96) Redefinition of Insured",
        "dwelling": {
            "occupancy_type": "1-2 Family",
            "tenant_occupied": False,
            "construction_type": "Masonry",
            "protection_class": "Protected",
            "territory_code": "14 - Chenango",
            "loss_settlement_basis": "ACV",
            "covered_causes_of_loss": "Basic Form (FL-1)",
            "seasonal_or_vacant": None,
            "hazardous_conditions_occupancy": None,
            "classification_description": "Dwelling - 2 Family",
            "aop_deductible": 500.00,
        },
    },

    # -- 5 -------------------------------------------------------------------
    # An LLC on the named insured line with a member listed under it. The only
    # variant whose insured is not a natural person, and the only one whose
    # mailing address is a PO box away from the risk.
    {
        "key": "df_005_eaglebay_llc",
        "transaction": "New Policy",
        "is_renewal": False,
        "policy_number": "10-2027-11475",
        "effective_date": "05/22/2027",
        "expiration_date": "05/22/2028",
        "effective_time": "12:01AM",
        "time_zone": "Standard Time",
        "agency": {
            "name": "Adirondack Gateway Insurance Agency -",
            "name_2": "KTS",
            "line_1": "3020 State Route 28",
            "city": "Old Forge", "state": "NY", "postal_code": "13420",
            "work": "(315) 369-6140", "fax": "(315) 369-6145",
            "producer_code": "KTS",
        },
        "insureds": ["Winterberry Holdings LLC", "Ottoline Marchbanks"],
        "entity_type": "Limited Liability Company",
        "insured_address": {
            "line_1": "PO Box 218",
            "city": "Old Forge", "state": "NY", "postal_code": "13420",
        },
        "property": {
            "number": 1, "of": 1,
            "line_1": "22 Birchbark Ln",
            "city": "Eagle Bay", "state": "NY", "postal_code": "13331",
            "county": "Herkimer",
        },
        "section_i": [
            ("Coverage A - Residence", "$268,000", 914.00),
            ("EC - Residence", "***", 132.00),
            ("VMM - Residence", "***", 15.00),
            ("Coverage B - Related Private Structures", "$26,800", 33.00),
            ("Coverage D - Additional Living Expense / Loss of Rent",
             "$21,440", 26.00),
        ],
        "section_ii": [
            ("Coverage L - Premises Liability", "$500,000", 66.00,
             "(Each Occurrence)"),
            ("ML-59 - Lead Exclusion", "***", -5.00, None),
        ],
        "optional": [
            ("ML-WD - Water Backup-Sewers and Drains", "***", 25.00),
            ("ML-54 - Theft Coverage", "***", 58.00),
            ("Hazardous Conditions - Occupancy", "***", 241.00),
        ],
        "fees": [("Policy Fee", 15.00)],
        "rating": [
            ("Coverage A - Residence", [
                ("Deductible", "$1,000.00"),
                ("Loss Settlement", "RC"),
                ("Construction", "Frame"),
                ("Protection", "Semi-Protected"),
                ("Zone", "All Other"),
                ("Form", "Broad Form (FL-2)"),
                ("Occupancy", "Tenant Occupied"),
                ("Disclaimer", DISCLAIMER),
            ]),
            ("Coverage B - Related Private Structures", [
                ("Deductible", "$1,000.00"),
                ("Construction", "Frame"),
                ("Protection", "Semi-Protected"),
                ("Form", "Broad Form (FL-2)"),
            ]),
            ("Coverage L - Premises Liability", [
                ("Classification", "Dwelling - 1 Family Tenant Occupied"),
                ("Territory Code", "11 - Herkimer"),
            ]),
            ("Hazardous Conditions - Occupancy", [
                ("Condition", "Unoccupancy"),
            ]),
            ("ML-54 Theft Coverage", [
                ("Limit", "Coverage C limit applies"),
                ("Deductible", "$1,000.00"),
            ]),
        ],
        "forms":
            "FL-18 (6/96) Intentional Act Exclusion, FL-20 (1/92) Agreement, "
            "FL-83 (02/02) Amendment of Policy Conditions, FL-90 (11/06) "
            "Clarification Endorsement, FMD-1 (12/94) Important Flood "
            "Insurance Notice, PR (3/01) Notice of Privacy Policy, LCI-J "
            "(9/17) By-Laws, FL-21 05/10 Suit Against Us Amendatory "
            "Endorsement, FL-2R (1/92) Causes of Loss, ML-WD (1.1) Water "
            "Damage-Sewers and Drains, ML-54 (6/99) Theft Coverage, FL-OLT "
            "(1/92) Premises Liability Insurance Coverage Part, ML-59 (6/99) "
            "Lead Exclusion, FL-80 (7/96) Redefinition of Insured, LCIC-DX "
            "(06/23) Exclusion of Canine Related Injuries or Damages",
        "dwelling": {
            "occupancy_type": "Tenant Occupied",
            "tenant_occupied": True,
            "construction_type": "Frame",
            "protection_class": "Semi-Protected",
            "territory_code": "11 - Herkimer",
            "loss_settlement_basis": "RC",
            "covered_causes_of_loss": "Broad Form (FL-2)",
            "seasonal_or_vacant": None,
            "hazardous_conditions_occupancy": "Unoccupancy",
            "classification_description": "Dwelling - 1 Family Tenant Occupied",
            "aop_deductible": 1000.00,
        },
    },
]
