# 🚦 Cost Gate: an inference budget in CI

**I wanted to know whether a pull request that changes a prompt or a model can be stopped when it pushes the cost of a right answer over a budget, and what a spend check on cost per call misses. This is a command-line gate and a staged GitHub Action: it reads an eval results CSV and a budget file, works out the cost per correct answer for the whole run and for each slice with a confidence interval, and prints PASS, WARN or FAIL.** It takes the cost-per-correct-answer measure from [13 SwapBrief](../13-swapbrief-model-migration/) and the tokens-times-price accounting from [07 InferenceLens](../07-inferencelens-inference-finops/), and moves the check from a migration brief and a dashboard into the pull request. I copied no code from either; from 13 I reused the two synthetic price points.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 64-cost-gate/src && python3 cost_gate.py --demo
```

It prints:

```text
run: 236 items, 5 slices
scope              items  correct  $/correct  95% interval         ceiling  status
overall              236      201    0.00655  0.00600 to 0.00711   0.00670  PASS
balance_inquiry       64       62    0.00313  0.00277 to 0.00349   0.00382  PASS
card_services         48       42    0.00823  0.00703 to 0.00943   0.00610  FAIL
dispute_status        56       45    0.00829  0.00712 to 0.00946   0.01034  PASS
fee_questions         56       44    0.00670  0.00553 to 0.00787   0.00768  PASS
wire_exceptions       12        8    0.01375  0.00805 to 0.01946   0.02081  THIN
  FAIL card_services: the interval's lower end 0.00703 is above the ceiling 0.00610
  THIN wire_exceptions: 12 items is below min_items 30; not judged alone, still counted in the overall
decision: FAIL
```

The whole run is inside its ceiling and one slice is not. Standard library only, Python 3.9 or newer. To check your own run: `python3 cost_gate.py check results.csv budget.json`. It exits 1 on FAIL, so a CI step fails; `--fail-on warn` also fails on WARN, and `--format github` prints annotations. Bad input exits 2 with one line on stderr.

How to read a status. Cost per correct answer is the money spent on every call, right or wrong, divided by the number of right answers.

| Status | Meaning |
|---|---|
| FAIL | The lower end of the 95% interval is above the ceiling: over budget, with confidence |
| WARN | The estimate is above the ceiling but the interval still reaches it: a person decides |
| PASS | The estimate is at or under the ceiling |
| THIN | A slice with fewer than `min_items` items: printed, not judged alone, still counted in the whole run |

A slice that is in the results but not in the budget, or in the budget but not in the results, is WARN and is named, so a renamed slice cannot switch its own check off.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 40 change requests, each with an eval run of 236 items; the script is named in brackets). The truth for each change request comes from the parameters that generated its run, not from the gate:

- 🟢 No cost check in CI: 0 of 40 change requests stopped, 21 of 40 are over budget, 15 of those 21 on the whole run and 6 of 21 only inside one slice (`step_01`)
- 🟢 Failing on cost per call (more than 10% over the baseline run) stops 12 of 40: it catches 8 of 21 over-budget change requests, passes 13 of 21, and fails 4 of 19 within-budget ones; 6 of the 21 over-budget change requests cost less per call than the baseline (`step_02`)
- 🟢 The measured cost per correct answer with no interval fails 18 of 21 over-budget change requests and wrongly fails 2 of 19 within-budget ones; an interval on the whole run alone fails 9 of 21 and cannot see the 6 of 21 that are over only inside a slice (`step_03`)
- 🟢 On every fourth item (59 items) the interval gate fails 5 of 21 over-budget change requests against 13 on the full set, and no slice has enough items to be judged alone (`step_03`)
- 🟢 Interval, whole run and slices together: FAIL on 13 of 21 over-budget change requests, WARN on 5, PASS on 3; of 19 within budget, 0 stopped, 2 warned, 17 passed; a person reads 20 of 40 (`step_04`)
- 🟢 The 4 of 4 planted slice regressions fail on a slice ceiling although the whole-run status was PASS on all 4 (`step_04`)

## What it still gets wrong

- 🟢 3 of 21 over-budget change requests still PASS (`step_04` prints each one). CR-010 and CR-024 regress inside `wire_exceptions`, a slice of 12 items, which is below `min_items` and so is never judged alone. CR-029 has a true cost per correct answer of 1.018 times its whole-run ceiling, which is inside the noise of 236 items. The tool is built to miss these, and I left them in on purpose.
- 🟢 With the default `--fail-on fail`, the 5 WARN and 3 PASS over-budget change requests still merge unless a person acts. `--fail-on warn` stops 18 of 21 over-budget and 2 of 19 within-budget change requests (`step_04`). That is a trade between missed overspend and noisy builds. I would set `warn` where one missed overspend costs more than the reviews of the within-budget change requests it also holds up.
- **The data and the rules share an author.** I wrote the generator and the gate, and I did not retune the effect sizes after running the gate, but the planted changes are still ones I thought of. Treat the numbers as a ceiling for this gate on this kind of data, not a rate on a real eval set, which I have not tested.
- **The interval counts only which items were sampled.** It is a normal approximation for a ratio (the delta method). It does not include grader noise: if `correct` comes from a model judge, that judge's error is not in the interval. It is unreliable with few right answers, which is the reason for `min_items`. Up to six scopes are judged per run, and I made no correction for that.
- **Only token cost is counted.** No latency, caching discount, batch price or per-request fee. Prices live in the budget file, so when a vendor changes a price the file has to change too, or the gate measures a stale one.
- **It does not judge quality.** A cheaper model that answers worse can still be inside the cost-per-correct ceiling. Pair it with an accuracy check; this one only knows what `correct` says.
- An eval set is not production traffic. A ceiling set on one is a guard on a change, not a forecast of the invoice.

## Use it in CI

[`action/`](./action/README.md) holds a staged GitHub Action and the steps to publish it from its own repository, which a Marketplace listing requires. It has not been published and has not run on GitHub. What is tested is the command it wraps (`tests/test_cli.py`, 50 tests in all across the folder).

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What happens to the budget when nothing checks it? | `step_01_no_gate.py` |
| 2 | What does failing on cost per call get wrong? | `step_02_cost_per_call.py` |
| 3 | Where does each part of the gate fail alone? | `step_03_deficiencies_exposed.py` |
| 4 | What do an interval, a whole-run ceiling and slice ceilings catch together? | `step_04_with_cost_gate.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

The [FinOps Foundation framework](https://www.finops.org/framework/), which I read on 2026-10-24 (the pages show no revision date). Its Unit Economics capability pairs spend with a measure of value and gives cost per token as a resource-efficiency unit metric and cost per case resolved as a business unit metric. Cost per correct answer is my reading of a unit metric between the two, measured on an eval rather than on live traffic. Its Budgeting capability expects spend limits, a comparison of actual spend with the limit, and a defined response when spend nears a budget line, such as an alert, an approval gate or a throttle. This gate is the approval gate, applied to a pull request before the spend exists. The page also lists suggested variance limits of 20%, 15% and 12% by maturity level; those describe the gap between budget and actual spend, and I did not derive my ceilings from them.

This is a prototype, aligned to that framework's vocabulary and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, bank or real eval. Prices are synthetic parameters, not vendor prices. 🟡 Modeled, with the assumption named: the overall ceiling is 15% above the baseline's expected cost per correct answer and each slice ceiling is 25% above its own baseline; `min_items` is 30; the 10% line in step 2 is the size of alert I would expect a team to set; correctness is a coin flip per item with a fixed accuracy per slice; token counts are a slice mean times a factor with a long tail on one item in twenty. All are in [`data/README.md`](./data/README.md). A prototype on synthetic data, not a production case study.

## Fork it

Export your eval harness results to `item_id, slice, model, correct, input_tokens, output_tokens` (tokens as billed, retries included). Write a budget file in the shape of [`data/budget.json`](./data/budget.json) with your own prices and ceilings; a baseline run on your main branch is the place to start. Extra columns in the CSV are ignored. Read the [PRD](./PRD.md) for the scope I held to.
