# fideon-synth

Synthetic insurance documents with gold answers.

Builds declarations pages that look like the ones a pipeline actually meets —
each with a gold JSON conforming to the live canonical `policy_check` schema,
and each with an image-only scanned twin.

```bash
pip install -e .

# Generate 5 synthetic samples by default:
fideon-synth

# Generate N samples (e.g. 10):
fideon-synth --count 10

# Or customize input, output, and count explicitly:
fideon-synth --input-dir "Data\original PDFs" --out E:\fideon-synth\output --count 10
```

Output lands in:

```
output/PDF/          high-quality image-only scanned PDFs
output/gold_json/    canonical gold JSON conforming to config/policy_check/
```

## Any source document: `--source`

The generic generator takes any source PDF - or every PDF under a folder -
and makes synthetic twins of it, with no per-carrier code:

```bash
# one sample per PDF for a carrier
fideon-synth --source "Data\original data\Markel American Insurance Company" --schema-dir config\policy_check --out output --count 1

# 3 samples of one document
fideon-synth --source "Data\original data\Progressive\auto\progressive_autob.pdf" --schema-dir config\policy_check --out output --count 3
```

Sources are read as `<Carrier>/<lob>/<file>.pdf`: the folder name picks the
schema (`_fallback` if there is none), the carrier folder is the carrier.

For each document it:

1. reads the layout from the text layer - real text, or a scan's invisible
   OCR layer (one that is flipped or scaled against the page is detected and
   corrected);
2. finds identifying values by shape and position - dates, money, phones,
   emails, FEINs, policy/hull/account numbers, street and city lines, PO
   boxes, and names above an address or under "Insured", "Agent", "Clients";
3. replaces them consistently - one original, one replacement, everywhere it
   is printed; every date by the same offset (terms stay valid); money by one
   factor; identifiers keep their shape. The carrier's own name and address
   stay;
4. whites out the printed value and draws the new one at the size, baseline
   and face (serif or sans) measured from the page, then rescans;
5. matches each value's printed label to the schema's field names and
   aliases for the gold. Values it changed but could not place confidently go
   to `fideon:unmapped` with their label and pages - the gold never guesses.
   A required section it found no label for is listed in `fideon:incomplete`.

A document fails only if an original identifying value survives, or the gold
claims a value that is not on the page. Known limits: a value the OCR misread
is not recognised and stays as printed; table rows are replaced but not
labelled; a scaled total can differ from its scaled parts by a rounding unit.
`FIDEON_KEEP_DIGITAL=1` keeps the pre-scan render for inspection.

---

## The four checks

Every document is checked as it is built, and the build reports failure rather
than writing quietly broken data. `fideon-synth` exits non-zero, so it can sit
in CI without anyone reading the output to find out whether it worked.

| check | what it catches |
|---|---|
| **schema** | the gold validates against the merged canonical schema |
| **arithmetic** | coverage premiums + fees equal the stated total — the rule the schema itself declares |
| **page refs** | every value the gold says is printed was found on a page |
| **scan** | the scanned twin has no extractable text, the same page count, the same page size |

The third is the one that earns its keep. A generator knows what it *meant* to
draw; only a search of the finished PDF knows what it drew. When those disagree
it is almost always the gold asserting something the page does not say — the
one kind of error a benchmark cannot survive, because every extractor is then
marked wrong for reading the document correctly.

It has already caught two: a renewal's prior policy number, and the *kind* of
fee behind a line the form labels only `Fees:`. Neither is printed anywhere.
Both are now in `fideon:absent` where they belong.

---

## Gold files

Leaves are `FieldValue` objects exactly as `_common.json` defines them:

```json
{ "raw": "$425,000", "parsed": 425000.0,
  "confidence": { "score": 1.0, "source": "deterministic" },
  "page_ref": [1], "flagged": false }
```

Four decisions are baked in, and you should know them before using the output:

**`deterministic` vs `structural`.** A value printed on the page is
`deterministic` — it can be quoted. A value the document only *implies* is
`structural`: `entity_type: "Individual"` is nowhere on a page that simply
names two people, and a twelve-month term is the gap between two printed
dates. Marking those `deterministic` would tell a harness they are quotable
when they are not, and every extractor scored against them would look worse
than it is. Use `fv()` for the first and `derived()` for the second.

**Page references are measured, not asserted.** After rendering, each value is
searched for in each page's text. `policy_number` comes back `[1, 2]` because
the footer repeats it. The match is token-bounded on purpose: a bare substring
test finds the state `NY` inside `Company` and the language code `en` inside
`Residence`, and a page reference that is *accidentally* right is worse than a
missing one, because nobody can spot it. A short value that genuinely occurs
twice gets both pages — that is what the pages say.

**Only stated fields are emitted.** The dwelling-fire schema has 364 leaves; a
declaration states about a sixth. Writing the rest as nulls would sextuple the
file and imply the document was checked for each. Instead every unstated leaf
is named once in `fideon:absent`, so a harness can separate "the document is
silent" from "nobody looked", and a hallucinated value has something to be
scored against.

**Scanned gold says where its page refs came from.** A scan has no text to
search, so its references are carried from the digital twin, whose layout is
identical by construction. `fideon:provenance.page_refs_measured_on` names the
file they were measured on rather than leaving a reader to assume they were
read off the image.

---

## Scanner profiles

Each document is also rasterised, degraded and re-embedded as an image, with
**no text layer at all**. What varies is *how*. A corpus where every page came
through one profile measures one thing; these are five different bad days:

| profile | what it does |
|---|---|
| `office_flatbed` | 300 dpi, square on the glass, light grain — the easy case |
| `fax_bitonal` | 200 dpi thresholded to pure black and white, speckled |
| `phone_photo` | uneven light, a soft edge shadow, visible skew, colour cast |
| `photocopy` | blotchy, vertical toner streaks, dust, darker |
| `old_flatbed` | 180 dpi, clearly skewed, heavy JPEG artefacts, warm paper |

They are handed out one per document, so a corpus covers the range instead of
sampling one point of it repeatedly. Degradation is seeded from the document
key and page number: a scanned page that changed between runs would make a
regression impossible to see.

Degraded, not destroyed — RapidOCR at 300 dpi recovers 89–97% of the values
the gold asserts. Restrict the set with `--profile fax_bitonal` (repeatable),
or build your own:

```python
from fideon_synth import Profile
Profile(key="duplex_bleed", label="duplex, show-through",
        dpi=220, jpeg_quality=70, gradient=0.1, noise=(8, 14))
```

---

## Adding your own carrier form

Three methods. Everything above — schema validation, page references, the
absent list, scanned twins, the checks, the CLI — arrives with them.

```python
from fideon_synth import Template, Values
from fideon_synth.draw import Column, Table, render
from fideon_synth.fields import fv, derived, money_from, date_fv

class ButternutHomeowners(Template):
    key = "butternut_homeowners"
    lob = "homeowners"                       # names the canonical schema file

    def variants(self, count=None, seed=0):  # plain dicts, your shape
        ...
    def render(self, variant, path):         # draw it, return the page count
        return render(path, lambda sheet: _draw(sheet, variant))
    def gold(self, variant, pdf_name, pages):
        ...                                  # leave page_ref empty
```

Register it in `fideon_synth/forms/__init__.py` and `--form yourkey` finds it.

`examples/new_form.py` is a complete working one — a different carrier on a
different line of business, ~100 lines, passing all four checks. Run it.

Two things to get right, because they are the ones that bite:

- **Do not fill `page_ref`.** They are measured off the finished PDF. Filling
  them by hand turns a check that catches layout drift into a check that
  agrees with you.
- **Use `derived()` for anything the page does not print**, with the printed
  text it was read from as evidence.

### What the toolkit gives you

`fideon_synth.draw` wraps a bare canvas rather than a flowable engine. A
declarations page is not a document that flows — it is a printed form with
fixed rules, a party box with vertical dividers, black section bars, dashed
row separators, a signature panel pinned to the bottom of page one. Platypus
wants to reflow all of that, and the point of a synthetic corpus is that the
page looks like the page an extractor will actually meet.

| | |
|---|---|
| `Sheet` | `text` `right_text` `run` `wrap` `paragraph` `rule` `dashed` `vline` `box` `swatch` `column_box` `footer` `scrawl` |
| `Table` | `bar` (black section bar) `row` (bordered, dashed separator, italic qualifier) `close` |
| `render` | draws twice, so a footer can say "Page 1 of 2" truthfully |

`fideon_synth.values` is seeded: `person` `household` `company` `agency`
`address` `phone_pair` `policy_number("10-{year}-{5d}")` `term` `limit` `rate`.
Same seed, same corpus — across processes, not just within a run.

Hand-write the first few documents and generate the rest. `variants(count=N)`
in the worked example returns the five hand-written ones then composes the
rest; careful beyond about a dozen stops being careful and starts being
repetitive.

---

## Requirements

`reportlab`, `PyMuPDF`, `Pillow`, `numpy`, `jsonschema`. The `ocr` extra pulls
`rapidocr-onnxruntime`, needed only to measure how readable the scans are.

The canonical schemas are read live rather than copied — gold built against a
copy drifts the moment the real one changes, and nothing tells you, because
the copy still validates against the wrong thing. Found in this order:

1. the `schema_dir` argument / `--schema-dir`
2. the `FIDEON_CANONICAL_SCHEMA` environment variable
3. known install locations (see `schema.py`)

```bash
set FIDEON_CANONICAL_SCHEMA=E:\SML\SLM L1\config\canonical_schema
```

```bash
python -m pytest        # 37 tests
```

---

Nothing this package produces is a real policy. Every name, address,
identifier and amount is invented, the place names are public geography, and
the carrier mark on the worked example is drawn rather than copied.
