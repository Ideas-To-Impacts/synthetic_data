"""
Common Synthetic Data Generator.

A single unified generator that:
1. Takes the original source PDF documents in `test_documents/`
2. Generates synthetic variations (modifying policy numbers, dates, insured names, addresses, premiums)
3. Outputs the synthetic PDFs to `output/PDF/`
4. Generates matching gold JSON files adhering to `config/policy_check/` in `output/gold_json/`
5. Is fully configurable via `--count`
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from . import pageref
from .corpus import Built, Report
from .fields import as_number, date_fv, derived, fmt_money, fv, money_from
from .scan import PROFILES, scan_pdf
from .schema import CanonicalSchema
from .values import Values


COMPANY_NAMES = [
    "Harrowgate Realty LLC",
    "Beacon Crest Properties LLC",
    "Empire Ridge Logistics Inc.",
    "Hudson River Hospitality LLC",
    "Mohawk Valley Builders Co.",
    "Adirondack Timber & Mill LLC",
    "Catskill Peak Hospitality LLC",
    "Pioneer Transport Services LLC",
]

AGENCIES = [
    ("CHENANGO BROKERS, LLC", "PO BOX 460", "HANCOCK", "NY", "13783"),
    ("KEYSTONE RISK PARTNERS LLC", "100 EAST MARKET ST", "ELMIRA", "NY", "14901"),
    ("DELAWARE AGENCY SERVICES", "45 MAIN STREET", "DELHI", "NY", "13753"),
    ("GENESEE BROKERAGE INC", "78 COURT STREET", "BINGHAMTON", "NY", "13901"),
]


class SyntheticGenerator:
    """Unified generator creating synthetic documents and matching gold JSON from source documents."""

    def __init__(
        self,
        input_dir: str | Path = r"E:\fideon-synth\test_documents",
        out_dir: str | Path = r"E:\fideon-synth\output",
        schema_dir: str | Path = r"E:\fideon-synth\config\policy_check",
        pdf_subdir: str = "PDF",
        gold_subdir: str = "gold_json",
    ):
        self.input_dir = Path(input_dir)
        self.out_dir = Path(out_dir)
        self.schema_dir = Path(schema_dir)
        self.pdf_dir = self.out_dir / pdf_subdir
        self.gold_dir = self.out_dir / gold_subdir

        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.gold_dir.mkdir(parents=True, exist_ok=True)

        self.schema = CanonicalSchema.load("wc", schema_dir=self.schema_dir)

    def generate(self, count: int = 5, seed: int = 0, progress=None) -> Report:
        """Generate `count` synthetic variations."""
        report = Report(template="test_documents_source", schema="%s v%s" % (self.schema.lob, self.schema.version))
        vals = Values(seed)

        # Source reference documents
        source_dec = self.input_dir / "amtrust_wc_dec.pdf"
        if not source_dec.exists():
            raise FileNotFoundError("Source document not found: %s" % source_dec)

        for i in range(1, count + 1):
            built = self._generate_one(source_dec, i, vals)
            report.documents.append(built)
            if progress:
                progress(built)

        return report

    def _generate_one(self, source_path: Path, index: int, vals: Values) -> Built:
        built = Built(
            key="wc_sample_%03d" % index,
            pdf=self.pdf_dir / ("sample_%03d.pdf" % index),
            gold=self.gold_dir / ("sample_%03d.json" % index),
            pages=0,
            fields=0,
        )

        try:
            # 1. Generate synthetic parameters
            policy_num = "TWC%07d" % vals.integer(4500000, 4999999)
            prior_num = "TWC%07d" % (int(policy_num[3:]) - vals.integer(50000, 150000))
            insured_name = vals.choice(COMPANY_NAMES)
            agency_name, ag_l1, ag_city, ag_st, ag_zip = vals.choice(AGENCIES)

            # Dates
            eff_year = vals.integer(2024, 2026)
            eff_date = "8/14/%d" % eff_year
            exp_date = "8/14/%d" % (eff_year + 1)
            issue_date = "7/%d/%d" % (vals.integer(1, 28), eff_year)

            # Rates & Remuneration
            remun = vals.integer(60, 150) * 1000
            rate = round(vals.rng.uniform(3.20, 4.20), 2)
            manual_premium = round(remun * rate / 100.0)
            exp_mod = round(vals.rng.uniform(0.90, 1.10), 2)
            mod_premium = round(manual_premium * exp_mod)
            terr_premium = max(10, round(manual_premium * 0.01))
            nat_dis_prem = max(2, round(manual_premium * 0.001))
            expense_const = 200
            total_est_annual = round(mod_premium + terr_premium + nat_dis_prem + expense_const)
            state_assess = round(total_est_annual * 0.092)
            total_cost = round(total_est_annual + state_assess)

            # 2. Mutate PDF from source
            doc = fitz.open(str(source_path))
            built.pages = len(doc)

            # Target key text replacements across pages
            replacements = {
                "TWC4467573": policy_num,
                "TWC4308391": prior_num,
                "Harrowgate Realty LLC": insured_name,
                "8/14/2024": eff_date,
                "8/14/2025": exp_date,
                "7/2/2024": issue_date,
                "CHENANGO BROKERS, LLC": agency_name,
            }

            for page in doc:
                for target, repl in replacements.items():
                    rects = page.search_for(target)
                    for r in rects:
                        # Redact and replace with clean font
                        page.add_redact_annot(r, fill=(1, 1, 1))
                        page.apply_redactions()
                        page.insert_text(
                            r.bl - (0, 1.5),
                            repl,
                            fontsize=8.5,
                            fontname="helv",
                        )

            temp_digital = self.pdf_dir / ("_temp_%s" % built.pdf.name)
            doc.save(str(temp_digital))
            doc.close()

            # 3. Create canonical Gold JSON adhering to policy_check/wc.json
            gold_data = self._build_gold(
                built.pdf.name,
                built.pages,
                policy_num,
                prior_num,
                insured_name,
                agency_name,
                eff_date,
                exp_date,
                issue_date,
                remun,
                rate,
                manual_premium,
                exp_mod,
                mod_premium,
                terr_premium,
                nat_dis_prem,
                expense_const,
                total_est_annual,
                state_assess,
                total_cost,
            )

            # Measure page references from digital text before rasterization
            resolved, misses = pageref.attach(gold_data, temp_digital)

            # 4. Turn into scanned-only image PDF (no text layer)
            profile = PROFILES[index % len(PROFILES)]
            scan_stats = scan_pdf(temp_digital, built.pdf, profile, seed=index)
            built.profile = scan_stats["profile"]

            # Remove temporary digital file
            if temp_digital.exists():
                temp_digital.unlink()

            gold_data["fideon:absent"] = self.schema.absent_from(
                pageref.stated_paths(gold_data)
            )
            gold_data["fideon:provenance"] = {
                "generator": "fideon-synth",
                "source": "test_documents",
                "schema": "%s v%s" % (self.schema.lob, self.schema.version),
                "render": "scanned_only",
                "scanner_profile": scan_stats["profile"],
                "synthetic": True,
                "note": "Scanned synthetic document generated from reference source test_documents.",
            }

            # 5. Validate against canonical schema
            schema_problems = self.schema.validate(gold_data)
            if schema_problems:
                built.problems.extend(schema_problems)

            # 6. Write Gold JSON (matching exactly: sample_001.pdf -> sample_001.json)
            with open(built.gold, "w", encoding="utf-8") as f:
                json.dump(gold_data, f, indent=2)

            built.fields = len(pageref.stated_paths(gold_data))

        except Exception as e:
            built.problems.append(str(e))

        return built

    def _build_gold(
        self,
        pdf_name: str,
        pages: int,
        policy_num: str,
        prior_num: str,
        insured_name: str,
        agency_name: str,
        eff_date: str,
        exp_date: str,
        issue_date: str,
        remun: int,
        rate: float,
        manual_premium: int,
        exp_mod: float,
        mod_premium: int,
        terr_premium: int,
        nat_dis_prem: int,
        expense_const: int,
        total_est_annual: int,
        state_assess: int,
        total_cost: int,
    ) -> dict:
        return {
            "document": {
                "document_type": fv("POLICY INFORMATION PAGE", "Information Page"),
                "document_title_as_stated": fv("WORKERS COMPENSATION AND EMPLOYERS LIABILITY INSURANCE POLICY"),
                "line_of_business_as_stated": fv("WORKERS COMPENSATION"),
                "page_count": fv(str(pages), pages, evidence=str(pages)),
                "source_file_name": derived(pdf_name),
                "issue_date": date_fv(issue_date),
            },
            "carrier": {
                "company_name": fv("Technology Insurance Company, Inc."),
                "address": {
                    "line_1": fv("59 Maiden Lane, 43rd Floor"),
                    "city": fv("New York"),
                    "state": fv("NY"),
                    "postal_code": fv("10038"),
                },
            },
            "named_insured": {
                "primary_name": fv(insured_name),
                "entity_type": derived("Limited Liability Company" if "LLC" in insured_name else "Corporation", insured_name),
                "mailing_address": {
                    "line_1": fv("Old Forge, NY 13420"),
                    "city": fv("Old Forge"),
                    "state": fv("NY"),
                    "postal_code": fv("13420"),
                },
            },
            "producer": {
                "agency_name": fv(agency_name),
                "address": {
                    "line_1": fv("PO BOX 460"),
                    "city": fv("HANCOCK"),
                    "state": fv("NY"),
                    "postal_code": fv("13783"),
                },
            },
            "policy": {
                "policy_number": fv(policy_num),
                "prior_policy_number": fv(prior_num),
                "effective_date": date_fv(eff_date),
                "expiration_date": date_fv(exp_date),
                "policy_type": fv("Workers Compensation"),
            },
            "premium": {
                "total_policy_premium": money_from(total_cost),
                "estimated_annual_premium": money_from(total_est_annual),
                "deposit_premium": money_from(total_cost),
                "minimum_premium": money_from(600),
                "surcharges": [
                    {
                        "description": fv("New York State Assessment"),
                        "amount": money_from(state_assess),
                    }
                ],
            },
            "workers_compensation": {
                "item_1_insured": {
                    "named_insured": fv(insured_name),
                    "legal_entity_type": derived("Limited Liability Company" if "LLC" in insured_name else "Corporation", insured_name),
                    "ncci_code": fv("39071"),
                },
                "item_2_policy_period": {
                    "effective_date": date_fv(eff_date),
                    "expiration_date": date_fv(exp_date),
                    "state_of_issue": fv("New York", "NY"),
                },
                "item_3_coverage": {
                    "part_one_states": [fv("New York", "NY")],
                    "part_two_employers_liability_bodily_injury_by_accident_each_accident": money_from(100000),
                    "part_two_employers_liability_bodily_injury_by_disease_policy_limit": money_from(500000),
                    "part_two_employers_liability_bodily_injury_by_disease_each_employee": money_from(100000),
                    "part_three_other_states_insurance": [fv("All states except ND, OH, WA, WY and State(s) Designated in Item 3.A")],
                },
                "item_4_premium_basis": [
                    {
                        "state": fv("New York", "NY"),
                        "class_code": fv("9052"),
                        "classification_description": fv("Hotel NOC: All Other Employees & Drivers"),
                        "number_of_employees": fv("2", 2),
                        "estimated_annual_remuneration": money_from(remun),
                        "rate_per_100_of_remuneration": fv("%.2f" % rate, rate),
                        "estimated_annual_premium": money_from(manual_premium),
                    }
                ],
                "premium_adjustments": {
                    "experience_modification_factor": fv(str(exp_mod), exp_mod),
                    "expense_constant": money_from(expense_const),
                    "terrorism_premium": money_from(terr_premium),
                    "catastrophe_premium": money_from(nat_dis_prem),
                    "total_estimated_annual_premium": money_from(total_est_annual),
                    "deposit_premium": money_from(total_cost),
                    "minimum_premium": money_from(600),
                },
            },
            "signature": {
                "title": fv("Authorized Representative"),
                "signature_date": date_fv(issue_date),
            },
        }
