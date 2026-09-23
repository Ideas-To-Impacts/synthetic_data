#!/usr/bin/env python3
"""
Adding your own carrier form - a working skeleton.

    python examples/new_form.py

This is a deliberately small Homeowners declaration: a masthead, a party box,
a three-row schedule, a footer. It is not pretty. It is here to show that a
template is three methods and about a hundred lines, and that everything
else - schema validation, page references, the absent list, scanned twins,
the four checks, the CLI - arrives for free once those three exist.

Copy this file, change the carrier, the line of business and the drawing, and
you have a new form. When it is ready, register it in
``fideon_synth/forms/__init__.py`` so ``--form yourkey`` finds it.

Two things to get right, because they are the ones that bite:

*Do not fill ``page_ref``.* Those are measured off the finished PDF. Filling
them in by hand turns a check that catches layout drift into a check that
agrees with you.

*Use ``derived`` for anything the page does not print.* "Individual" is not
on a page that simply names a person. Marking it ``deterministic`` tells a
harness it is quotable, and every extractor that correctly fails to find it
is scored wrong.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fideon_synth import Corpus, Template, Values
from fideon_synth.draw import BOLD, ITALIC, REGULAR, Column, Table, render
from fideon_synth.fields import date_fv, derived, fmt_money, fv, money, \
    money_from

CARRIER = "Butternut Valley Mutual Insurance Company"
LEFT, RIGHT = 54.0, 558.0


class ButternutHomeowners(Template):
    key = "butternut_homeowners"
    lob = "homeowners"
    description = "Example: a one-page Homeowners declaration"

    # ── 1. the documents to build ───────────────────────────────────────────

    def variants(self, count=None, seed=0):
        vals = Values(seed)
        out = []
        for i in range(count or 3):
            risk = vals.address()
            effective, expiration = vals.term()
            dwelling = vals.limit(120000, 400000)
            rows = [
                ("Coverage A - Dwelling", dwelling,
                 float(vals.rate(dwelling, 1000.0, (3.1, 4.0)))),
                ("Coverage C - Personal Property", int(dwelling * 0.5),
                 float(vals.rate(dwelling * 0.5, 1000.0, (1.4, 2.0)))),
                ("Coverage E - Personal Liability", 300000,
                 float(vals.integer(42, 78))),
            ]
            out.append({
                "key": "ho_%03d_%s" % (i + 1, risk["city"].lower()),
                "policy_number": vals.policy_number("BVM-{7d}-{2d}"),
                "insureds": vals.household(vals.integer(1, 2)),
                "address": risk,
                "effective_date": effective,
                "expiration_date": expiration,
                "deductible": float(vals.choice([500, 1000, 2500])),
                "rows": rows,
            })
        return out

    # ── 2. the page ─────────────────────────────────────────────────────────

    def render(self, variant, path):
        return render(path, lambda sheet: _draw(sheet, variant),
                      left=LEFT, right=RIGHT, author=CARRIER)

    # ── 3. the gold ─────────────────────────────────────────────────────────

    def gold(self, variant, pdf_name, pages):
        total = sum(premium for _, _, premium in variant["rows"])
        insureds = variant["insureds"]
        address = variant["address"]
        return {
            "document": {
                "document_type": fv("DECLARATIONS", "Declarations"),
                "line_of_business_as_stated": fv("Homeowners"),
                "page_count": fv(str(pages), pages,
                                 evidence="Page 1 of %d" % pages),
                "source_file_name": derived(pdf_name),
            },
            "carrier": {"company_name": fv(CARRIER)},
            "named_insured": {
                "primary_name": fv(insureds[0]),
                "entity_type": derived("Individual", insureds[0]),
                "mailing_address": {
                    "line_1": fv(address["line_1"]),
                    "city": fv(address["city"]),
                    "state": fv(address["state"]),
                    "postal_code": fv(address["postal_code"]),
                },
            },
            "policy": {
                "policy_number": fv(variant["policy_number"]),
                "policy_type": fv("Homeowners"),
                "effective_date": date_fv(variant["effective_date"]),
                "expiration_date": date_fv(variant["expiration_date"]),
            },
            "coverages": [
                {"coverage_name": fv(name),
                 "limit": money("${:,}".format(limit)),
                 "premium": money_from(premium)}
                for name, limit, premium in variant["rows"]],
            "premium": {"total_policy_premium": money_from(total)},
            "deductibles": [{
                "deductible_type": derived("All Other Perils", "Deductible"),
                "amount": money_from(variant["deductible"])}],
        }


def _draw(sheet, v):
    sheet.text(LEFT, 726, CARRIER, BOLD, 13)
    sheet.rule(716, 1.0)
    sheet.text(LEFT, 690, "HOMEOWNERS DECLARATIONS", BOLD, 15)
    sheet.right_text(RIGHT, 690, v["policy_number"], REGULAR, 10)

    address = v["address"]
    sheet.column_box(
        668,
        [("Named Insured(s):", list(v["insureds"]) + [
            address["line_1"], "%s, %s %s" % (address["city"],
                                              address["state"],
                                              address["postal_code"])]),
         ("Policy Period:", ["From %s" % v["effective_date"],
                             "To   %s" % v["expiration_date"],
                             "12:01 A.M. Standard Time"])],
        (LEFT + 6, 320.0), dividers=(310.0,))

    table = Table(sheet, [Column(LEFT, 380.0), Column(380.0, 470.0, "right"),
                          Column(470.0, RIGHT, "right")])
    y = table.bar(560, ["SECTION I & II", "LIMIT", "PREMIUM"])
    for i, (name, limit, premium) in enumerate(v["rows"]):
        y = table.row(y, [name, "${:,}".format(limit), fmt_money(premium)],
                      rule_above=i > 0)
    y = table.row(y, ["Total Policy Premium", "",
                      fmt_money(sum(p for _, _, p in v["rows"]))],
                  rule_above=True)
    table.close(y)

    sheet.text(LEFT, y - 30, "Deductible: ", REGULAR, 9)
    sheet.text(LEFT + sheet.measure("Deductible: ", REGULAR, 9), y - 30,
               fmt_money(v["deductible"]), ITALIC, 9)

    sheet.footer(30, left="BVM-HO (01/24)",
                 right="Page %d of %d" % (sheet.page,
                                          sheet.total_pages or sheet.page))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(__file__).resolve().parent / "_new_form_output"
    report = Corpus(ButternutHomeowners(), out).build(count=3)
    print(report.summary())
    raise SystemExit(0 if report.ok else 1)
