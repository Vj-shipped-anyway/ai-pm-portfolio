# 📑 spread-extraction-eval (synthetic statements): where extraction drifts across layouts

**I wanted to know what happens when the financial statements a credit analyst spreads arrive in a layout the extractor was not written for, and whether the usual single accuracy number would tell me. This is a seeded generator of 120 statements in six layouts, a field-level scorer and a drift gate that names the layout that slipped.** It scores two rule-based stand-ins, not a model. The point is the harness: the same documents, the same scoring, one gate. Swap in a model's output file and keep the rest.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 77-spread-extraction-eval/src && python3 spread_eval.py --demo
```

It prints:

```text
extractor: fixed_label (a rule-based stand-in, not a model)
documents 120, truth values 5280, no prediction 1848, extra prediction rows 0
layout              docs  values  correct   accuracy  documents all right
plain_two_column      20     880      880     100.0%             20 of 20
side_by_side          20     880      640      72.7%              0 of 20
note_column           20     880      602      68.4%              0 of 20
relabelled            20     880      160      18.2%              0 of 20
thousands_parens      20     880        0       0.0%              0 of 20
wrapped_footnotes     20     880        0       0.0%              0 of 20
all layouts pooled    120    5280     2282      43.2%
wrong values by class: missing 1848, scale 2, wrong_period 136, compound 870, other 142
tie-out, no truth needed: flags 85 of 120 documents; 15 of 100 documents with a wrong value pass every identity
gate (floor 95.0%, max gap 3.0 points, at least 10 documents per layout): FAIL
  thousands_parens: 0.0% is below the floor of 95.0% and 100.0 points below plain_two_column
  wrapped_footnotes: 0.0% is below the floor of 95.0% and 100.0 points below plain_two_column
  relabelled: 18.2% is below the floor of 95.0% and 81.8 points below plain_two_column
  note_column: 68.4% is below the floor of 95.0% and 31.6 points below plain_two_column
  side_by_side: 72.7% is below the floor of 95.0% and 27.3 points below plain_two_column
```

Standard library only, Python 3.9 or newer. To score your own extractor: `python3 spread_eval.py score --docs statements.csv --truth truth.csv --predictions mine.csv`. It exits 1 when the gate fails and 2 for malformed input. `python3 spread_eval.py predict --extractor alias_aware --docs statements.csv` prints a predictions file in the format `score` reads.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 120 statements, 6 layouts, 5,280 field values; the script is named in brackets):

- 🟢 A pilot on the layout the extractor was written against finds 880 of 880 values right, and 100 of 120 statements (83.3%) sit in layouts the pilot never touched (`step_01`)
- 🟢 One pooled number: `fixed_label` 43.2% (2282 of 5280 values), `alias_aware` 94.7% (5002 of 5280), a gain of 51.5 points (`step_02`)
- 🟢 Behind the 94.7%: best layout 100.0%, worst 68.4% (`note_column`), a spread of 31.6 points, and 100 of 120 statements (83.3%) with every field right (`step_03`)
- 🟢 A random audit of 10 statements holds no `note_column` statement in 146 of 1000 draws (`step_03`)
- 🟢 The gate passes `alias_aware` on the 5 development layouts and fails it on all 6. In `note_column`, 7 of 22 fields fall below 100.0%; the wrong values are 136 `wrong_period` and 142 `other` (`step_04`)
- 🟢 `fixed_label` fails the gate on 4 of the 5 development layouts: 0.0% on `thousands_parens` and `wrapped_footnotes`, 18.2% on `relabelled`, 72.7% on `side_by_side` (`step_04`)
- 🟢 Hard negatives: 24 development statements carry a negative value (a loss or a deficit); `alias_aware` reads all 24 with every field right and the tie-out check raises 0 false alarms (`step_04`)
- 🟡 Modeled, with the share of incoming statements assumed: if `note_column` were 5% of traffic the same extractor would pool at 98.4%, at 30% 90.5%, at 60% 81.0% (`step_03` prints them)
- 🟡 The gate limits (floor 95.0%, gap 3.0 points, at least 10 statements per layout) are my assumptions. Set your own on the command line.
- 🔴 Hypothetical: a real model would show a spread like this. I have not run one.

## What it still gets wrong

- 🟢 The tie-out check passes 15 of the 100 statements `fixed_label` reads wrong, all in `thousands_parens` (`step_03` and `step_04` print it). That extractor ignores the "in thousands" header and swaps the two columns, and both mistakes keep every accounting identity true. Only a labeled sample sees it. I left this in on purpose.
- **The data and the rules share an author.** I wrote the generator and both extractors. `alias_aware` reaches 100.0% on five layouts because I fixed it against the error classes `fixed_label` printed on them. `note_column` was held out in the sense that no rule was written for it; I still designed it knowing what the rules look like. Treat every number as a ceiling for these rules, not a rate on real statements.
- **The stand-ins are rules, not a model.** A model drifts for other reasons: it can invent a figure, it can differ between runs, it can read a scanned page worse than a clean one. Nothing here measures any model. What carries over is the scoring and the gate.
- 20 statements per layout is thin. The 880 values in a layout come from 20 documents and are not independent, so the gate also prints how many statements are right in full.
- A value is right when it is within half a dollar of the truth. A wrong tax line counts the same as a wrong revenue line; there is no materiality weighting. The tie-out check uses the same half-dollar tolerance, so statements that "may not sum due to rounding" would raise false alarms.
- **Left out to fit the build:** scanned or noisy input, multi-page statements, a cash-flow statement, consolidated against parent accounts, multiple currencies, labels in other languages, restated prior-year figures, confidence intervals on the accuracies, and a hosted app. The generator has 22 fields in 2 statements and 6 layouts, which is the part that fit.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does a pilot on one layout tell you? | `step_01_pilot_only.py` |
| 2 | What does one pooled accuracy say? | `step_02_pooled_accuracy.py` |
| 3 | What does the pooled number hide, and what does the tie-out check miss? | `step_03_deficiencies_exposed.py` |
| 4 | What do layout-level scoring and a gate catch? | `step_04_layout_scorer.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. `src/_standins.py` holds the two stand-in extractors and is the only place their rules live. [`PRD.md`](./PRD.md) holds the scope.

## Aligned to

Nothing. No published standard or regulation is cited and none is claimed. The one idea borrowed is ordinary model evaluation practice: score by slice, because a pooled number depends on the mix of inputs. This is a prototype on synthetic data.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Company names are invented. Nothing comes from any employer, customer or real filing. The statements are plain text, which is what an extractor would see after text recognition; no image is involved. A prototype on synthetic data, not a production case study.

## Fork it

Replace `data/statements.csv` and `data/truth.csv` with your own labeled statements, keeping the columns (`doc_id`, `layout`, and `text` for `predict`; `doc_id`, `field`, `period`, `value` for truth). Write your extractor's output as a predictions file in the same shape as truth and run `score`. Group by whatever `layout` means to you: a template, a vendor, a country. Read the [data notes](./data/README.md) before you change the field list; the tie-out check expects the 22 field names.
