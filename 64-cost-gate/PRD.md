# PRD: Cost Gate

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a release-governance and FinOps review. It is not a record of a PRD landed at a named bank. The rules, the planted change requests and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and the Action is staged and has not run on GitHub.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Cost Gate: a command-line gate, with a staged GitHub Action, that reads an eval results CSV and a budget file and prints PASS, WARN or FAIL on the cost of a correct answer |
| **Owner** | The engineer who owns an AI feature's prompt and model, with the finance partner who owns the budget as co-owner of the ceilings |
| **Stage** | Portfolio prototype on synthetic data; the Action is staged and unpublished |
| **Primary user** | The engineer who owns an AI feature's prompt and model |
| **Secondary users** | The reviewer who approves changes to it; the finance partner who reads the budget file; the evaluation owner who runs the eval set; internal audit |
| **Problem** | A pull request changes a prompt, a retrieval depth or a model. The eval gate, if there is one, reports accuracy. Nothing reports what a right answer now costs, so an overspend shows up on the next invoice. A check on cost per call does not fix that: it passes a cheaper model that is right less often, and it fails a longer prompt that is right more often. In the planted set, 🟢 a pipeline with no cost check stops 0 of 40 change requests and 21 of 40 are over budget (`step_01_no_gate.py`). |
| **Solution** | Reads one eval run (a CSV with item, slice, model, correct, input and output tokens) and a budget file (prices, `min_items`, an overall ceiling, a ceiling per slice). Computes cost per correct answer for the whole run and for each slice, with a 95% interval. Prints FAIL when the interval's lower end is over the ceiling, WARN when only the estimate is, PASS otherwise, and names any slice it did not judge. Exits non-zero at a chosen level, with GitHub annotations on request. |
| **North-star metric** | Share of production changes to in-scope AI features that pass through the gate with a recorded decision against a budget file with a named owner. Target 🔴 100%. Today in this model: nothing checks cost per correct answer. |
| **Measured metrics (synthetic)** | 🟢 13 of 21 over-budget change requests stopped; 0 of 19 within-budget ones stopped; 4 of 4 slice regressions found that the whole-run check passes; the known misses named (3 of 21 over-budget change requests still pass) (`step_04_with_cost_gate.py`). |
| **Modeled metrics** | 🟡 Utility (13/21 − 8/21) × 12 = 2.9 more over-budget change requests a year stopped than a cost-per-call check would stop, assuming 12 over-budget change requests reach the gate each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the gate share an author, so the numbers are a ceiling, not a rate on a real eval set. Mitigation: run it on one real eval export, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The budget file goes stale when prices change, and the gate measures the prices it is given. Mitigation: a price age check, and prices changed only through a reviewed change with the vendor's price page linked. |
| **Risk #3** | The interval counts only which items were sampled, and a small eval set leaves every slice unjudged. 🟢 Every fourth item (59 items) leaves 0 of 5 slices judged alone and the gate fails 5 of 21 over-budget change requests against 13 on the full set (`step_03_deficiencies_exposed.py`). Mitigation: size the eval set so that each slice reaches `min_items`, and read THIN slices by hand. |
| **Out of scope** | Accuracy gates; latency; caching, batch and per-request pricing; production traffic; forecasting the invoice; any model call; hosting. A Marketplace listing is a later, separate step. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is change requests. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Cost per correct answer** for the whole run and each slice, from tokens and prices | 40 CRs | 3 | 0.9 | 1 | 108.0 | Built in prototype |
| 2 | **Slice ceilings** (a slice can be over while the whole run is inside) | 40 CRs | 3 | 0.8 | 1 | 96.0 | Built in prototype |
| 3 | **Input validation** (empty, truncated, wrong-type, binary or two-run input exits 2, never a traceback) | 40 CRs | 2 | 0.9 | 1 | 72.0 | Built in prototype |
| 4 | **Thin and unmatched slices** (under `min_items` is THIN; a slice in only one of results and budget is WARN) | 40 CRs | 2 | 0.8 | 1 | 64.0 | Built in prototype |
| 5 | **Interval and status rules** (FAIL, WARN, PASS from the delta-method interval) | 40 CRs | 3 | 0.8 | 2 | 48.0 | Built in prototype |
| 6 | **Price age check** (WARN when the price table is older than a set age) | 40 CRs | 2 | 0.6 | 1 | 48.0 | Sequenced for v0.2 |
| 7 | **CI output** (text and GitHub annotations, `--fail-on` levels, escaped strings) | 40 CRs | 2 | 0.9 | 2 | 36.0 | Built in prototype |
| 8 | **Publish the Action from its own repository** | 40 CRs | 2 | 0.6 | 2 | 24.0 | Sequenced for v0.2 (staged in `action/`, not published) |
| 9 | **Budget change review** (pull request, finance approver, price page linked) | 40 CRs | 3 | 0.6 | 3 | 24.0 | Sequenced for v0.2 |
| 10 | **Decision record** (budget hash, results hash, thresholds, statuses) | 40 CRs | 2 | 0.6 | 4 | 12.0 | Sequenced for v0.3 |
| 11 | **Grader noise in the interval** (when `correct` comes from a judge) | 40 CRs | 2 | 0.4 | 5 | 6.4 | Sequenced for v0.3 |
| 12 | **Correction for six scopes judged per run** | 40 CRs | 1 | 0.5 | 4 | 5.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Cost Gate | What they fear |
| --- | --- | --- | --- |
| **Feature engineer** | Owner | A step that fails with a reason a person can act on, and passes a longer prompt that is right more often. | A gate that blocks good changes on noise and gets switched off. |
| **Change reviewer** | Approver | The scope that is over, its interval and its ceiling, next to the accuracy result. | Approving a change on accuracy alone and learning the cost from the invoice. |
| **Finance partner** | Owner of the budget file | A ceiling with a named owner, set from a baseline run, and changed only through review. | Ceilings raised quietly until the check means nothing. |
| **Evaluation owner** | Owns the eval set | The gate reads the harness export as it is. | A gate that redefines the eval set or the slices. |
| **FinOps or platform lead** | Consulted | Prices that match the vendor's and the invoice. | A stale price table that makes every number wrong. |
| **Security / CISO** | Approver | No vendor key in the gate's path and nothing leaving the boundary. | Another tool in the pipeline holding credentials. |
| **Internal audit** | Reader | A path from a decision to the budget, prices and results it used. | A ceiling changed silently between two runs. |

---

## User stories (top 4)

1. **As the feature engineer**, I want the pipeline to fail when a change pushes the cost of a right answer over its ceiling with confidence, so the overspend does not appear on the next invoice.
2. **As a reviewer**, I want each finding to name the scope, its interval and its ceiling, so I can approve or hold without a meeting.
3. **As the finance partner**, I want a slice ceiling to catch a regression that the whole-run average hides, so one important slice cannot overspend behind a good average.
4. **As internal audit**, I want each decision tied to the budget, prices and results file it used, so I can reproduce it later.

---

## KPIs

**North star:** share of production changes to in-scope AI features that pass through the gate with a recorded decision against a budget file with a named owner. Target 🔴 100%.

**Inputs (leading):**
- Eval items per run (the prototype set has 🟢 236 items per run over 5 slices, from `step_01_no_gate.py` and `data/README.md`).
- Slices that reach `min_items` (prototype: 🟢 0 of 5 judged alone on every fourth item, `step_03_deficiencies_exposed.py`; target: every slice on the full set).
- Budget files with a named owner and a price table younger than a set age (target: every budget).
- Harnesses that write tokens as billed, retries included (target: every harness).

**Outputs (lagging):** prototype baselines from the planted set.
- Over-budget change requests stopped. 🟢 13 of 21 with the gate, against 0 of 40 stopped with no check and 8 of 21 with cost per call (`step_04_with_cost_gate.py`, `step_01_no_gate.py`, `step_02_cost_per_call.py`).
- Within-budget change requests stopped. 🟢 0 of 19; 2 warned and 17 passed (`step_04_with_cost_gate.py`).
- Change requests a person reads. 🟢 20 of 40 (`step_04_with_cost_gate.py`).
- Slice regressions failed on a slice ceiling. 🟢 4 of 4, with the whole-run status PASS on all 4 (`step_04_with_cost_gate.py`).
- Known miss. 🟢 3 of 21 over-budget change requests still PASS (`step_04_with_cost_gate.py`).
- FAILs overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the gate on one feature's eval export with `--fail-on never`. Print the decision, fail nothing, and compare with what the team did. |
| 1: Calibration | 4w | Run a baseline on the main branch and set the overall and slice ceilings from it with the finance partner. Check that the harness writes tokens as billed. |
| 2: FAIL enforced | 4w | Fail the step on FAIL. WARN stays advisory. Budget changes go through a pull request with a second approver. |
| 3: WARN decided | 6w | Choose `--fail-on warn` where one missed overspend costs more than the reviews it adds. Add the price age check. Publish the Action from its own repository. |
| 4: Record and noise | 8w | Write a decision record per run. Add the grader-noise term to the interval and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should a WARN stop the merge?** With the default only FAIL does. `--fail-on warn` also holds 2 of 19 within-budget change requests in the planted set. Recommendation: keep `fail` as the default and choose `warn` per feature, where a missed overspend costs more than the extra reviews.
2. **Where should the ceilings come from?** The overall ceiling is 15% above the baseline and each slice 25% above its own baseline, as assumptions. Recommendation: set them from the feature's own baseline run with the finance partner, and record who approved them.
3. **What about a slice that is too small to judge?** It is printed as THIN and not judged alone. Recommendation: grow the eval set until each slice reaches `min_items`, and read THIN slices by hand until then.
4. **Who keeps the prices current?** The gate measures the prices in the budget file. Recommendation: the FinOps lead owns the price table, with an age limit that raises a WARN.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the pipeline.** The gate is stateless: it reads two files and returns a decision. Production adds a reviewed budget file, a price age check and a decision record, all designed and none built.
- **Never silent.** A missing, empty, malformed or truncated input exits 2 and fails the step, even with `--fail-on never`. A slice that is in only one of the results and the budget is a WARN and is named.
- **Strings from input are data.** Annotations and text output escape control characters, so a hostile slice name cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the stopped count shows in the diff.

**What is next.** Run it against one real eval export whose owner can share it; add a price age check; publish the Action from its own repository.

**What would have to be true before a pilot.**
- The harness writes input and output tokens as billed, retries included.
- The budget file carries current prices and ceilings set from a baseline run, with a named owner.
- Each slice that matters reaches `min_items` in the eval set.
- One real export can be shared, so the ceilings are set against real costs and not mine.
- The team agrees which level fails the step.

---

*This PRD names [13 SwapBrief](../13-swapbrief-model-migration/), [07 InferenceLens](../07-inferencelens-inference-finops/), [40 Eval Gate](../40-eval-gate/) and [04 EvalForge](../04-evalforge-llm-eval-platform/) as designed interlocks (🔴 designed, none built). From 13 I reused the two synthetic price points; no code is shared.*
