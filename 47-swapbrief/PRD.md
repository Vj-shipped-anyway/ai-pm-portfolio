# PRD: SwapBrief CLI, a go or no-go brief for a model migration

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a model-change review. It is not a record of a PRD landed at a named bank. The thresholds, the simulated migrations and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and no model was called.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | swapbrief: a command-line tool that reads graded results and a price table for a current and a candidate model and prints GO, GO WITH GUARDRAILS or NO-GO, with the reasons and the rollback triggers |
| **Owner** | The AI platform lead who owns the migration, with the model risk reviewer as co-owner of the limits and the critical-slice list |
| **Stage** | Portfolio prototype on synthetic data; nothing is hosted |
| **Primary user** | The AI platform lead who owns the migration |
| **Secondary users** | The model risk reviewer who has to accept the evidence; the finance partner who asks what a correct answer costs; the feature owner; internal audit |
| **Problem** | A vendor retires the model behind a production GenAI feature. The team runs its evaluation set on the successor and sees the average rise. The average does not show what a correct answer now costs, whether the slow tail got worse while the median improved, or which slice fell. Nobody writes down what would send traffic back, so the first signal is a complaint. In the simulated set, 🟢 45 of 80 migrations carry a real problem, and the headline average gives GO to 41 of 45 of them with 0 rollback triggers written (`step_01_headline_average.py`). |
| **Solution** | Reads two files: paired per-item results for the current and the candidate system, and a price table. The contract is documented in the README and refuses anything it cannot use, with exit status 2. Reports the accuracy change, cost per correct answer, p50 and p95 latency, and a status per slice, each with a paired bootstrap interval. Prints GO, GO WITH GUARDRAILS or NO-GO with the reasons, exits non-zero at a chosen level, and prints rollback triggers: metric, threshold, window. |
| **North-star metric** | Share of in-scope model migrations that carry a written brief, with a decision and rollback triggers, before launch. Target 🔴 100%. Today in this model: the basic approach writes 🟢 0 rollback triggers (`step_01_headline_average.py`). |
| **Measured metrics (synthetic)** | 🟢 False GO falls from 41 of 45 (headline average) and 36 of 45 (average plus vendor sheet) to 2 of 45; 0 of 26 cost problems lack a cost flag and 1 of 11 p95 problems lacks a p95 flag; 0 of 35 good migrations are stopped (`step_04_with_swapbrief.py`). |
| **Modeled metrics** | 🟡 Utility (36/45 − 2/45) × 3 = 2.3 migrations a year with a real problem stopped or guarded that the basic rule would pass, assuming 3 migrations a year with a real problem. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted problems and the thresholds share an author, so the rates are a ceiling. Mitigation: run it on one real evaluation export and report the simulated numbers and the real numbers apart. |
| **Risk #2** | The thresholds are assumptions taken from project 13, not from any rule. Mitigation: the limits live in a reviewed per-feature config, and a change is a pull request with a different approver. |
| **Risk #3** | Caution has a price. 🟢 19 of 35 good migrations (54.3%) get GO WITH GUARDRAILS, mostly because a critical slice is too thin to rule a loss out (`step_04_with_swapbrief.py`). Mitigation: grow the critical slice rather than loosen the limit, and read the guardrail as a written trigger, not a stop. |
| **Out of scope** | Judging answers; comparing prompts (run it once per system); wiring triggers to a monitor; price changes over time; any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is migrations in the simulated set. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Two-file contract validation** (empty, truncated, wrong-type, unpaired, duplicate or too-small input exits 2, never a traceback) | 80 migrations | 2 | 0.9 | 1 | 144.0 | Built in prototype |
| 2 | **Cost per correct answer with an interval** (watch and block at the interval's lower bound) | 80 migrations | 3 | 0.9 | 2 | 108.0 | Built in prototype |
| 3 | **Rollback triggers** (metric, threshold, window, action, written before launch) | 80 migrations | 3 | 0.8 | 2 | 96.0 | Built in prototype |
| 4 | **p95 latency with an interval** (the slow tail beside the median) | 80 migrations | 3 | 0.6 | 2 | 72.0 | Built in prototype |
| 5 | **Fail-on levels and JSON output** (`--fail-on nogo`, `guardrails`, `never`) | 80 migrations | 1 | 0.8 | 1 | 64.0 | Built in prototype |
| 6 | **Per-slice status with a critical-slice rule** (REGRESSED, WATCH, INCONCLUSIVE, OK, IMPROVED) | 80 migrations | 3 | 0.7 | 3 | 56.0 | Built in prototype |
| 7 | **Reviewed per-feature limits** (thresholds, windows and critical slices, approved by a second person) | 80 migrations | 2 | 0.6 | 2 | 48.0 | Sequenced for v0.2 |
| 8 | **Margin option for the headline rule** (require a gain, not just "not lower") | 80 migrations | 1 | 0.5 | 1 | 40.0 | Sequenced for v0.2 |
| 9 | **Harness manifest check** (row count and hash, so a file cut between two items is caught) | 80 migrations | 2 | 0.5 | 2 | 40.0 | Sequenced for v0.2 |
| 10 | **Brief ledger** (limits, file hashes, seed, decision, reasons) | 80 migrations | 2 | 0.7 | 3 | 37.3 | Sequenced for v0.2 |
| 11 | **Publish as a CI step** | 80 migrations | 2 | 0.6 | 3 | 32.0 | Sequenced for v0.2 |
| 12 | **Price changes over time and prompt comparison** | 80 migrations | 1 | 0.3 | 4 | 6.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from swapbrief | What they fear |
| --- | --- | --- | --- |
| **AI platform lead** | Owner | One brief that says go or no-go with the reasons and the triggers, and a clean exit when the data is bad. | A tool that blocks a good move on noise and gets bypassed. |
| **Model risk reviewer** | Approver of limits | Each reason tied to a rule and an interval, and a record of who set the limits. | Evidence that looks complete and rests on a thin slice. |
| **Finance partner** | Consulted | Cost per correct answer, not list price per token, so the bill matches the answer. | A cheaper token that buys a dearer answer. |
| **Feature owner** | Consulted | Early notice of a slice that fell, in terms of their cases. | A migration decided on an average that hides their slice. |
| **Vendor manager** | Informed | The retirement date matched to the move and its triggers. | A forced move with no written fallback. |
| **Security / CISO** | Approver | Nothing leaving the boundary, no vendor key in the tool, strings from the files kept out of logs. | Another tool holding credentials or echoing hostile input. |
| **Internal audit** | Reader | A brief that re-runs from the same files, limits and seed. | A limit changed between two briefs with no record. |

---

## User stories (top 4)

1. **As the AI platform lead**, I want cost per correct answer and the p95 tail next to the accuracy change, so a higher average does not hide a dearer and slower model.
2. **As a model risk reviewer**, I want each reason in the decision to name a rule and an interval, so I can accept or challenge it without rebuilding the analysis.
3. **As the finance partner**, I want cost per correct answer with an interval, so the budget reflects what the feature now pays for an answer.
4. **As the feature owner**, I want rollback triggers with a metric, a threshold and a window written before launch, so a bad week has a pre-agreed response.

---

## KPIs

**North star:** share of in-scope model migrations that carry a written brief, with a decision and rollback triggers, before launch. Target 🔴 100%.

**Inputs (leading):**
- Paired items in the evaluation export (prototype: 🟢 600 paired items in 6 slices, `step_04_with_swapbrief.py`).
- Size of the smallest critical slice (prototype: `account_closure` has 🟢 40 items on purpose, as if those cases were slow to grade, `step_04_with_swapbrief.py`).
- Evaluation exports that carry tokens and latency for both systems (target: every export).
- Migrations whose limits were set by a named reviewer (target: every one).

**Outputs (lagging):** prototype baselines from the simulated set.
- False GO. 🟢 2 of 45, against 41 of 45 for the headline average and 36 of 45 for the average plus vendor sheet (`step_04_with_swapbrief.py`).
- Cost problems with no cost flag. 🟢 0 of 26 (`step_04_with_swapbrief.py`).
- p95 problems with no p95 flag. 🟢 1 of 11 (`step_04_with_swapbrief.py`).
- Good migrations stopped. 🟢 0 of 35; given guardrails 19 of 35 (`step_04_with_swapbrief.py`).
- Known miss. 🟢 4 of 26 true slice regressions pass unflagged (`step_04_with_swapbrief.py`).
- Rollbacks triggered after launch: not measured; the simulation has no launch.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Back-test | 4w | Run the brief on one past migration whose outcome is known, with `--fail-on never`. Compare with what the team decided and what happened. |
| 1: Calibration | 4w | Set the cost, p95 and slice limits for the feature with the finance partner and the model risk reviewer. Name the critical slices. Check the evaluation export has tokens and latency for both systems. |
| 2: Advisory in the launch review | 4w | Attach the brief to the launch decision. NO-GO is read by a person; nothing fails automatically. |
| 3: Enforced as a CI step | 6w | Fail the migration step at NO-GO. Limit changes go through a pull request with a different approver. |
| 4: Ledger and trigger wiring | 8w | Write a brief record per run and wire the rollback triggers to a monitor. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should the headline rule require a margin?** Today it is "accuracy not lower". Recommendation: keep it as the first row only, and let cost, p95 and slices decide, since the average alone gives GO to 🟢 41 of 45 migrations with a real problem (`step_01_headline_average.py`). Add a margin option in v0.2 for teams that want one.
2. **Where should the limits come from?** They are copied from project 13 and taken from no rule. Recommendation: set them per feature with the finance partner and the model risk reviewer, and record who signed.
3. **Is GO WITH GUARDRAILS an acceptable default for a thin critical slice?** Over half of good migrations land there. Recommendation: accept it at pilot, treat the guardrail as a written trigger, and fix the cause by adding items to the critical slice.
4. **Who wires the rollback triggers to a monitor?** The prototype prints text for the launch plan. Recommendation: the platform lead owns the triggers, and wiring them to a monitor is a v0.3 item once one team has used the text.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, run per migration.** The tool is stateless: it reads two files and returns a brief. Production adds reviewed limits per feature, a brief ledger and a CI step, all designed and none built.
- **Never silent.** An empty, unpaired, truncated or too-small input exits 2. A critical slice too thin to rule a loss out is INCONCLUSIVE and costs a guardrail, not a GO.
- **Same files, same brief.** The bootstrap is seeded, so a rerun with the same files and seed reproduces the intervals.
- **Strings from input are data.** Names are escaped before they reach a log or a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the simulated-set numbers.

**What is next.** Run it on one real evaluation export its owner can share; add a margin option for the headline rule; publish it as a CI step.

**What would have to be true before a pilot.**
- The harness writes `correct`, tokens and latency for both systems on the same items.
- A named reviewer owns the limits and the critical-slice list.
- The critical slices are large enough to rule a loss out, or the team accepts guardrails as the outcome.
- One real export can be shared, so the limits are set against real data and not mine.
- The team agrees which level fails the migration step.

---

*This PRD names [13 SwapBrief](../13-swapbrief-model-migration/), [66 Deprecation Impact](../66-deprecation-impact/) and [40 Eval Gate](../40-eval-gate/) as designed interlocks (🔴 designed, none built). The thresholds are copied from 13 as constants, not read from its files.*
