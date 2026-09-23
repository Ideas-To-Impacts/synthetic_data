"""
Build a corpus and check it.

    from fideon_synth import Corpus
    from fideon_synth.forms import LeatherstockingDwellingFire

    report = Corpus(LeatherstockingDwellingFire(), "out/").build(count=20)
    report.ok            # False if anything failed
    print(report.summary())

Four checks run on every document, and the build reports failure rather than
writing quietly broken data:

  schema      the gold validates against the merged canonical schema
  arithmetic  the coverage premiums plus fees come to the stated total -
              the rule the schema itself declares
  page refs   every value the gold says is printed was found on a page
  scan        the scanned twin has no extractable text, the same page count
              and the same page geometry

The third is the one that earns its keep. A generator knows what it meant to
draw; only a search of the finished PDF knows what it drew. When those
disagree it is almost always the gold asserting something the page does not
say, which is the one kind of error a benchmark cannot survive - every
extractor is marked wrong for reading the document correctly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import pageref
from .fields import strip_evidence
from .scan import PROFILES, scan_pdf
from .schema import CanonicalSchema


@dataclass
class Built:
    key: str
    pdf: Path
    gold: Path
    pages: int
    fields: int
    scanned: Path = None
    scanned_gold: Path = None
    profile: str = ""
    problems: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.problems


@dataclass
class Report:
    template: str
    schema: str
    documents: list = field(default_factory=list)

    @property
    def ok(self):
        return all(d.ok for d in self.documents)

    @property
    def problems(self):
        return [p for d in self.documents for p in d.problems]

    def summary(self):
        lines = ["  %s -> %s" % (self.template, self.schema), ""]
        for d in self.documents:
            lines.append("  %s %-28s %d pp  %3d fields  %s"
                         % ("ok " if d.ok else "FAIL", d.key, d.pages,
                            d.fields, d.profile))
            for problem in d.problems:
                lines.append("       - %s" % problem)
        lines.append("")
        if self.ok:
            lines.append("  %d documents, every check passes"
                         % len(self.documents))
        else:
            lines.append("  %d of %d documents have problems"
                         % (sum(1 for d in self.documents if not d.ok),
                            len(self.documents)))
        return "\n".join(lines)


class Corpus:
    """One template, rendered to a directory, checked as it goes."""

    def __init__(self, template, out_dir, schema_dir=None, scanned=True,
                 profiles=None, indent=2):
        self.template = template
        self.out = Path(out_dir)
        self.scanned = scanned
        self.profiles = list(profiles) if profiles else list(PROFILES)
        self.indent = indent
        self.schema = CanonicalSchema.load(template.lob, schema_dir,
                                           template.doc_type)

        self.pdf_dir = self.out / "pdf"
        self.gold_dir = self.out / "gold"
        self.scan_dir = self.out / "scanned"
        self.scan_gold_dir = self.out / "gold_scanned"
        dirs = [self.pdf_dir, self.gold_dir]
        if scanned:
            dirs += [self.scan_dir, self.scan_gold_dir]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    # ── build ───────────────────────────────────────────────────────────────

    def build(self, count=None, seed=0, progress=None):
        report = Report(self.template.key,
                        "%s v%s" % (self.schema.lob, self.schema.version))
        variants = self.template.variants(count=count, seed=seed)

        for index, variant in enumerate(variants):
            built = self._one(variant, index)
            report.documents.append(built)
            if progress:
                progress(built)
        return report

    def _one(self, variant, index):
        name = self.template.name_for(variant) or "document_%03d" % (index + 1)
        pdf_path = self.pdf_dir / ("%s.pdf" % name)
        gold_path = self.gold_dir / ("%s.json" % name)

        pages = self.template.render(variant, pdf_path)
        doc = self.template.gold(variant, pdf_path.name, pages)

        resolved, misses = pageref.attach(doc, pdf_path)
        doc["fideon:absent"] = self.schema.absent_from(
            pageref.stated_paths(doc))
        doc["fideon:provenance"] = dict({
            "generator": "fideon-synth",
            "template": self.template.key,
            "schema": "%s v%s" % (self.schema.lob, self.schema.version),
            "render": "digital",
            "synthetic": True,
            "note": "Not a real policy. Every name, address, identifier and "
                    "amount is invented.",
        }, **self.template.provenance(variant))

        problems = list(self.schema.validate(doc))
        problems += self.template.audit(doc)
        problems += ["%s claims to be printed but is not on any page: %r"
                     % (path, raw) for path, raw in misses[:5]]
        if len(misses) > 5:
            problems.append("... and %d more unresolved page references"
                            % (len(misses) - 5))

        self._write(gold_path, doc)
        built = Built(key=name, pdf=pdf_path, gold=gold_path, pages=pages,
                      fields=resolved + len(misses), problems=problems)

        if self.scanned:
            self._scan(built, variant, doc, index)
        return built

    def _scan(self, built, variant, doc, index):
        profile = self.profiles[index % len(self.profiles)]
        scan_path = self.scan_dir / ("%s_scanned.pdf" % built.key)
        stats = scan_pdf(built.pdf, scan_path, profile, built.key)

        gold = json.loads(json.dumps(doc))
        for key in ("raw", "parsed"):
            gold["document"]["source_file_name"][key] = scan_path.name
        gold["fideon:provenance"].update({"render": "scanned",
                                          "scan_profile": profile.label})
        pageref.carry_over(gold, built.pdf.name)
        scan_gold = self.scan_gold_dir / ("%s_scanned.json" % built.key)
        self._write(scan_gold, gold, strip=False)

        built.scanned = scan_path
        built.scanned_gold = scan_gold
        built.profile = profile.label
        if stats["words"]:
            built.problems.append(
                "scan has %d extractable words - it is not image-only"
                % stats["words"])
        if stats["pages"] != built.pages:
            built.problems.append("scan has %d pages, digital has %d"
                                  % (stats["pages"], built.pages))
        if not _same_geometry(built.pdf, scan_path):
            built.problems.append("scan changed the page size")

    def _write(self, path, doc, strip=True):
        if strip:
            strip_evidence(doc)
        path.write_text(json.dumps(doc, indent=self.indent,
                                   ensure_ascii=False), encoding="utf-8")


def _same_geometry(a_path, b_path):
    """A scan that came back a different size breaks every coordinate a
    downstream reader derives from the page."""
    import fitz
    fitz.TOOLS.mupdf_display_errors(False)
    a, b = fitz.open(str(a_path)), fitz.open(str(b_path))
    same = a.page_count == b.page_count and all(
        abs(pa.rect.width - pb.rect.width) < 0.5
        and abs(pa.rect.height - pb.rect.height) < 0.5
        for pa, pb in zip(a, b))
    a.close()
    b.close()
    return same
