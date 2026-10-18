# Sample Data — SwapBrief walkthrough

Seven CSVs that drive Steps 1 through 4 of the walkthrough. **Everything here is simulated.** A seeded generator, [`_generate.py`](./_generate.py) (standard library only), writes all of it. No model was called, no API was used, and none of it measures any real model, vendor, bank, or customer. The generator is a stub that stands in for real evaluation runs, with the true effects written down so a decision rule can be scored against them.

---

## How to regenerate

```bash
cd data
python3 _generate.py
```

Running it twice on the same machine produces byte-identical files. The committed seed is `270`. The same module draws the 200 simulated scenarios used in `src/step_04_with_swapbrief.py` (`scenario_spec`, `scenario_truth`), so the committed set and the scenarios come from one world model.

---

## `eval_items.csv` — 720 evaluation items

| Field | Description |
| --- | --- |
| `item_id` | `Q0001` to `Q0720`. |
| `slice` | One of 8 slices (see `slices.csv`). |
| `probe_id` | A synthetic id such as `PS1-FEE-001`. In production the items would be an export of EvalForge probe sets (project 04); no row here corresponds to a row in project 04. |
| `probe_set` | `probeset-v1`. |
| `should_refuse` | 1 if refusing is the correct behavior for the item. All `jailbreak_resistance` items, and 33 of the 90 `refusal_edge` items (the generator draws each item at 45%). |

---

## `eval_results.csv` — 2160 rows: every item scored under 3 systems

| Field | Description |
| --- | --- |
| `item_id`, `slice` | As above. |
| `system` | `A` (current model, its own prompt), `B_old_prompt` (model B with A's old prompt: the in-place swap), `B_new_prompt` (model B with a prompt retuned for B: the prompt-fair condition). |
| `correct` | 0 or 1. |
| `input_tokens`, `output_tokens` | Tokens for the call. Model B counts about 4% more input tokens for the same text; the retuned prompt adds about 300 input tokens; B writes longer answers. |
| `latency_ms` | Time to the full answer. Model B has a faster median and a heavier slow tail. |
| `refusal` | 1 if the system refused. When a system is wrong on an item it should answer, it sometimes over-refuses; the rate is higher for `B_old_prompt`. |

Items are paired: the same `item_id` is scored under all three systems, and a shared per-item difficulty makes the three outcomes correlated, as they are when one evaluation set is run against two model versions.

---

## `ground_truth_effects.csv` — the injected truth

The true accuracy of model A in each slice and the true change for each B condition. **The decision rules never read this file**, and no script does: the scoring in step 4 takes the same values from `_generate.py`, and this file records them.

| slice | severity | items | A true accuracy | true change, B with A's old prompt | true change, B retuned prompt | truth label |
| --- | --- | --- | --- | --- | --- | --- |
| fee_questions | critical | 120 | 0.88 | +0.05 | +0.06 | improves |
| eligibility | critical | 110 | 0.82 | +0.06 | +0.07 | improves |
| multi_hop | standard | 100 | 0.60 | +0.10 | +0.12 | improves |
| citation | standard | 90 | 0.70 | +0.07 | +0.09 | improves |
| numeric_units | standard | 100 | 0.80 | -0.11 | -0.10 | regresses |
| long_answers | standard | 40 | 0.72 | -0.10 | -0.10 | regresses |
| refusal_edge | critical | 90 | 0.84 | -0.14 | +0.01 | regresses_old_prompt_only |
| jailbreak_resistance | critical | 70 | 0.80 | +0.03 | +0.05 | improves |

Most slices improve. Two regress under both prompts (`numeric_units`, `long_answers`). One, `refusal_edge`, regresses only under A's old prompt. The committed draw is a sample of these effects, so what the scripts measure differs from them: the sample shows `long_answers` at -2.5 pp against a true change of -10.0 pp.

---

## `slices.csv` — severity, tolerance, size

| slice | severity | tolerance (pp) | items | what it covers |
| --- | --- | --- | --- | --- |
| fee_questions | critical | 5 | 120 | Fee and charge questions answered from the fee schedule |
| eligibility | critical | 5 | 110 | Product eligibility rules (age, balance, residency) |
| multi_hop | standard | 8 | 100 | Questions that need two or more policy documents |
| citation | standard | 8 | 90 | Answers that must cite the right policy section |
| numeric_units | standard | 8 | 100 | Rates, percentages and currency units stated correctly |
| long_answers | standard | 8 | 40 | Answers over 300 words (slow to grade, so few items) |
| refusal_edge | critical | 5 | 90 | Requests that sit on the edge of what the feature should refuse |
| jailbreak_resistance | critical | 5 | 70 | Attempts to talk the feature out of its rules |

*Critical* slices block a migration when a regression is confirmed beyond the tolerance; *standard* slices ship with a trigger and a named owner. One slice is deliberately small (`long_answers` has 40 items, as if answers over 300 words were slow to grade) so the known limit shows up: a slice with too few items stays inconclusive.

---

## `prices.csv`, `models.csv`, `policy.csv`

- **`prices.csv`** — synthetic unit prices per 1,000 tokens. Model B's list price is 20% lower per token than model A's. These are parameters, not vendor prices.
- **`models.csv`** — the three systems, the model each runs, and snapshot pins with synthetic notice and end-of-support dates. In the design these come from DriftSentinel (project 02).
- **`policy.csv`** — the written-down policy: the inconclusive half-width (0.10), the cost and p95 watch (1.05, 1.10) and block (1.25, 1.50) ratios, the bootstrap confidence (0.95), the aggregate test level (0.05), and the trigger windows. The step scripts read it; change a value and the rule changes.

---

## How the simulated results are drawn

For each item the generator draws a shared difficulty and, for each system, an independent component, and calls the item correct if the combined latent value falls below the system's true accuracy for that slice. Token counts are lognormal around per-slice means. Latency is a time to first token plus output tokens times a per-token time, with a chance of a slow call; model B's median is faster and its slow-call rate is higher. All parameters are constants at the top of `_generate.py`.

## How the committed seed was chosen

One 720-item draw is a sample. I scanned seeds 1 to 300 and committed seed 270 because its draw shows the whole walkthrough at once:

- the retuned prompt's overall gain is between +2.5 and +5.0 points with McNemar p below 0.05, so the aggregate test says GO;
- A's old prompt gains between −0.5 and +1.5 points, so the in-place swap does not look worse on average;
- A's overall accuracy is within 1.2 points of its true value;
- SwapBrief reads the draw as GO WITH GUARDRAILS for the retuned prompt and NO-GO for the old prompt, with `numeric_units` REGRESSED, `long_answers` INCONCLUSIVE, `refusal_edge` REGRESSED under the old prompt, and cost and p95 on WATCH.

Other seeds tell other parts of the story. The 200-scenario test in step 4 does not depend on this choice: its worlds come from `scenario_spec(i)` for i = 1 to 200.

---

*All rows are synthetic. Nothing in this folder is a measurement of any real system.*
