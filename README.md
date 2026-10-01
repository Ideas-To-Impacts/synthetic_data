# fideon-synth

Synthetic insurance documents with gold answers.

Builds synthetic digital twins of real declarations pages — each with a gold
JSON conforming to the live canonical `policy_check` schema, built from the
same single pass that drew the PDF, never re-derived from a rendered file.

```bash
pip install -e .

# Generate 5 synthetic samples by default:
fideon-synth

# Generate N samples (e.g. 10):
fideon-synth --count 10

# Or customize input, output, and count explicitly:
fideon-synth --input-dir "Data\original data" --out E:\fideon-synth\output --count 10
```

Output lands in:

```
output/PDF/          synthetic digital PDFs - a real text layer, selectable
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

On Linux (RunPod) a run started from a terminal always moves itself into a
detached tmux session, so it keeps going when the SSH connection or the laptop
closes - `fideon-synth` and `scripts/build_dataset.py` both do this. It prints
the session name; `tmux attach -t <name>` watches it (Ctrl+B, D to leave
again), and everything it prints is also in `logs/<name>-<time>.log`. Install
tmux once with `apt-get install -y tmux`; set `FIDEON_NO_TMUX=1` to run in the
foreground on purpose. Windows runs in the foreground as before.

Sources are read as `<Carrier>/<lob>/<file>.pdf`: the folder name picks the
schema (`_fallback` if there is none), the carrier folder is the carrier.
The schemas are looked up in a folder named `policy_check` (the document
type), so `config/policy_check` must keep that name.

For each document it:

1. reads the layout from whatever text layer the source already has - real
   text, or an existing OCR layer a prior scan left on it (one that is
   flipped or scaled against the page is detected and corrected). No fresh
   OCR pass is run on it;
2. finds identifying values by shape and position - dates, money, phones,
   emails, FEINs, policy/hull/account numbers, street and city lines, PO
   boxes, and names above an address or under "Insured", "Agent", "Clients";
3. replaces them consistently - one original, one replacement, everywhere it
   is printed; every date by the same offset (terms stay valid), including a
   date wrapped over two lines; identifiers keep their shape, and a coupon's
   scan line is replaced with the new policy number inside it. Amounts stay
   as printed - a scaled total never equals the sum of its rounded scaled
   parts. The carrier's own name and address stay;
4. covers the printed value in the paper colour around it (grey on a grey
   panel) and draws the new one at the size, baseline and face (serif or
   sans) measured from the page - bounded by where the next word's ink
   begins, and condensed when it is longer than the old one, so it never
   runs into the words after it. The output stays this digital render - no
   scan-degradation pass. Form numbers, ISO forms ("CG 20 18 04 13")
   included, keep their numbers;
5. matches each value's printed label to the schema's field names and
   aliases for the gold. The gold always has the schema's full shape - every
   canonical field present, `null` where the document does not state it.
   Values it changed but could not place confidently are never dropped: they
   go into the schema's own `additional_fields[]` list, with their label and
   page - the gold never guesses, and never invents a non-canonical key to
   hold them either.

Printed paragraphs no field holds - a deductible condition, a navigation
restriction, a renewal notice, a disclaimer - go to the gold's
`text_sections`, one per paragraph, titled by the heading over it, in the
replaced wording; a bulleted list is one section of its items, read from the
same text layer as everything else. Words run together in that layer
("combinedsinglelimiteachaccident") are set apart again - only into words the
same document prints on its own; names, web addresses and figures are left
as printed.

Facts a page states in its own words rather than beside a label are read too:
forms named in page footers, web addresses, renewal-offer dates ("This renewal
offer is for the policy period A through B"), a change "removed from your
policy", where and when a period ends, a print code, a coupon's scan line. A
policy-wide value the units print differently is left out rather than taken
from one of them.

A document fails if an original identifying value or date survives anywhere -
in the PDF, even inside a longer run of digits, or in the gold itself,
labels included - or if the gold claims a value that is not on the page.
Known limit: a source page with an image and no text layer at all (no OCR
ever run on it, nested in an otherwise-digital document) contributes nothing
- flagged per page in the build log, not silently missing.

---

## What's checked

Every document is checked as it is built, and the build reports failure rather
than writing quietly broken data. `fideon-synth` exits non-zero, so it can sit
in CI without anyone reading the output to find out whether it worked.

| check | what it catches |
|---|---|
| **schema** | the gold validates against the merged canonical schema (an absent field's `null` failing `FieldValue`'s own `type: object` is expected, reported, not a build error) |
| **arithmetic** | coverage premiums + fees equal the stated total — the rule the schema itself declares |
| **page refs** | every value the gold says is printed was found on a page, re-read off the actually-saved PDF - never just asserted from what the generator meant to draw |

The last is the one that earns its keep. A generator knows what it *meant* to
draw; only a search of the finished PDF knows what it drew. When those disagree
it is almost always the gold asserting something the page does not say — the
one kind of error a benchmark cannot survive, because every extractor is then
marked wrong for reading the document correctly. A value it can't verify is
dropped from the gold, not asserted on faith, and logged to the build manifest.

---

## Gold files

Leaves are `FieldValue` objects exactly as `_common.json` defines them:

```json
{ "raw": "$425,000", "parsed": 425000.0,
  "confidence": { "score": 1.0, "source": "deterministic" },
  "page_ref": [1], "flagged": false }
```

Three decisions are baked in, and you should know them before using the output:

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

**Every canonical field is present, `null` where the document is silent.** The
gold is always the schema's full shape — every leaf the dwelling-fire schema
declares (364 of them), say, not just the ~60 a given declaration states. A
harness can tell "the document is silent" from "nobody looked" by looking at
one field, not a separate side-list; a hallucinated value still has something
real to be scored against. Anything detected and changed that couldn't be
matched to a field with confidence isn't dropped either — it goes into the
schema's own `additional_fields[]` array, never a non-canonical key.

---

## Scanner profiles

Not used by the generic engine above, which outputs a digital PDF directly.
These remain for `fideon_synth.scan` - a page rasterised, degraded and
re-embedded as an image, with **no text layer at all** - should a
scanned-look render ever be wanted again, standalone or through the older
declarative `Corpus`/`Template` path (see below). What varies is *how*:

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
regression impossible to see. Build your own:

```python
from fideon_synth import Profile
Profile(key="duplex_bleed", label="duplex, show-through",
        dpi=220, jpeg_quality=70, gradient=0.1, noise=(8, 14))
```

---

## A new carrier, a new line of business

Nothing to write. The generic engine (`--source`, above) takes any real
source PDF and reads the line of business straight off its own folder name
(`.../<Carrier>/<lob>/x.pdf`) against whatever schema that name has under
`config/policy_check/` — no per-carrier or per-document code, and no
registration step. Point it at the new source folder and it works the same
way every other carrier and line of business already does.

A hand-built, declarative form (drawn from scratch, not generated from a real
source PDF) is still possible via `fideon_synth.Template`/`fideon_synth.Corpus`
(see `corpus.py`, `template.py`) for the rare case that's worth writing by
hand - but that path has no CLI flag or catalogue of its own any more; call
`Corpus(YourTemplate(), out_dir).build()` directly.

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

`reportlab`, `PyMuPDF`, `Pillow`, `numpy`, `jsonschema`.

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
python -m pytest        # 56 tests
```

---

Nothing this package produces is a real policy. Every name, address,
identifier and amount is invented, the place names are public geography, and
the carrier mark on the worked example is drawn rather than copied.
