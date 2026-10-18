# PRD · FairLens — Fairness Test Pack for a Credit-Decision Model

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a model-risk and fair-lending read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to a model-risk review in the seat. It is not a record of a PRD landed at a named bank. The six-test taxonomy, the verdict vocabulary, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. RICE scores and rollout durations below are planning estimates (🔴), not measurements. The scorecard in the prototype is a stub, not a trained model, and nothing here is a legal finding.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | FairLens — a fairness test pack for a credit-decision model |
| **Owner** | Model Risk Lead (line-2), with the model owner (line-1) as co-owner of the fixes |
| **Stage** | Portfolio prototype; model-risk and fair-lending read |
| **Primary user** | Model risk or fair-lending reviewer, who is asked whether a credit-decision model is fair and is given an accuracy figure |
| **Secondary users** | Model owner; credit policy (owns the cutoff); compliance counsel; internal audit |
| **Problem** | A credit-decision model ships with a model card that reports overall accuracy and an approval rate. A reviewer cannot tell from that whether one group is approved far less often than another, whether the answer holds across nearby cutoffs, whether one input is a stand-in for group, or whether declined applicants get consistent reasons. In the synthetic data, 🟢 the model card says 87.1% accuracy and 75.7% approved, while approval rates by group are 83.5%, 64.3% and 62.7% (a 20.9-point spread) and accuracy by group (88.9%, 84.2%, 84.2%) looks fine. |
| **Solution** | A repeatable test pack with six tests: group approval gap, adverse impact ratio (AIR) by group with a bootstrap interval, cutoff sweep, proxy ablation, reason-code consistency and small-group stability. Each returns PASS, REVIEW or FAIL with its numbers beside it. |
| **North-star metric** | Share of in-scope credit-model releases and cutoff changes that receive a FairLens run before they go live. Target 🔴 100% of in-scope models. Today in this model: 0%, nothing runs (the accuracy-only view runs 0 of 6 tests). |
| **Measured metrics (synthetic)** | 🟢 4 FAIL, 1 REVIEW, 1 PASS across 6 tests at the policy cutoff of 190; 🟢 lowest AIR 0.750 (Group C, interval 0.698 to 0.808) against the 0.80 screen; 🟢 the screen holds up to cutoff 185; 🟢 lowest AIR 0.750 to 0.871 with the postcode points neutral. |
| **Modeled metrics** | 🟡 Utility 1.00 × 20,000 = 20,000 credit decisions a year under a model with a full test pack, assuming a modeled bank decides 20,000 applications a year with this scorecard. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on decision-log volume and the group-inference step, and has not been sized. |
| **Risk #1** | Group labels. Real credit data does not carry them, and inference errors push AIR toward 1. 🟢 In the prototype, with 14.8% of labels wrong at random, a failing screen (lowest AIR 0.750) passes (0.817). Mitigation: a separate, documented group-inference step with its own validation, and a label-error sensitivity printed beside every verdict. |
| **Risk #2** | The pack is read as a legal finding or a compliance pass. Mitigation: the verdict vocabulary says screen; compliance counsel owns conclusions; every run prints its known limits. AIR is a screening statistic and the 0.80 line comes from employment guidance, not from a credit-law standard. |
| **Risk #3** | The ablation only finds the proxy someone thought to name. 🟢 The reason-code pair check passes (+3.3 points against its control) while 295 declines are caused by the postcode points. Mitigation: ablate every input in turn (backlog item 7) and review the inputs that correlate with group. |
| **Out of scope** | Group inference (named, not built); drift monitoring (DriftSentinel, 02); the generic evaluation harness (EvalForge, 04); obligation mapping (ControlMap, 16); use-case tiering (TierGate, 11); any legal conclusion. |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is credit models in scope (a planning assumption of 10) unless labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE (🔴 estimate) | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Cutoff sweep** (where the lowest AIR crosses the screen, and what passing costs) | 10 | 2 | 0.9 | 1 | 18.0 | Built in prototype; v0.1 |
| 2 | **Small-group stability** (seeded bootstrap interval, REVIEW when it straddles) | 10 | 2 | 0.9 | 1 | 18.0 | Built in prototype; v0.1 |
| 3 | **Label-error sensitivity beside every verdict** | 10 | 2 | 0.8 | 1 | 16.0 | Built as a printed example; v0.2 |
| 4 | **AIR by group with an interval** | 10 | 3 | 0.9 | 2 | 13.5 | Built in prototype; v0.1 |
| 5 | **Proxy ablation** (one named input) | 10 | 3 | 0.8 | 2 | 12.0 | Built in prototype; v0.1 |
| 6 | **Verdict rules as configuration** (thresholds per model tier) | 10 | 2 | 0.8 | 2 | 8.0 | Sequenced for v0.2 |
| 7 | **Ablate every input in turn** (a proxy scan) | 10 | 3 | 0.6 | 3 | 6.0 | Sequenced for v0.3 |
| 8 | **Decision-log reader and run store** | 10 | 3 | 0.9 | 5 | 5.4 | Sequenced for v0.1 |
| 9 | **Reason-code consistency** (matched pairs, naming check) | 10 | 2 | 0.7 | 3 | 4.7 | Built in prototype; v0.2 |
| 10 | **Scheduled rerun when scores drift** (DriftSentinel interlock) | 10 | 2 | 0.7 | 3 | 4.7 | Sequenced for v0.3 |
| 11 | **Reason-method options** (points lost against the maximum, or against the average approved applicant) | 10 | 1 | 0.6 | 2 | 3.0 | Queued |
| 12 | **Evidence bundle exporter** to the model-risk record | 2 reviewers | 2 | 0.9 | 2 | 1.8 | Sequenced for v0.3 |
| 13 | **Intersectional groups** | 10 | 2 | 0.4 | 5 | 1.6 | Queued |
| 14 | **Group inference with its own validation** | 10 | 3 | 0.4 | 8 | 1.5 | Queued; the hardest item and the one the prototype does not have |

---

## Stakeholder map

| Stakeholder | Role | What they want from FairLens | What they fear |
| --- | --- | --- | --- |
| **Model Risk Lead** (line-2) | Owner | The same tests on every release, with a verdict and numbers they can put in a validation report. | A tool that turns a screening statistic into a conclusion, or a record that competes with the model inventory. |
| **Model owner** (line-1) | Co-owner of the fixes | To know which test failed, by how much, and what the cutoff change costs, before the review meeting. | Thresholds that move between releases; a REVIEW with no way to clear it. |
| **Credit policy** | Owns the cutoff | The approval-rate and risk cost of moving the cutoff, side by side. | A tool that picks the cutoff for them. |
| **Compliance / fair-lending counsel** | Reads the result | Clear limits, no legal language in the output, and the evidence behind each verdict. | A dashboard figure quoted as a finding. |
| **Internal audit** | Consumer of the record | Runs, seeds, thresholds and verdicts kept for each model version. | Results that cannot be reproduced. |
| **Security / CISO** | Approver | No applicant-level data copied beyond what a run needs; least-privilege reads. | Another store holding protected-class inferences. |
| **Data science / validators** | Consulted | A pack that does not duplicate their own validation, and a clear place to add tests. | A fixed list that blocks better tests. |

---

## User stories (top 4)

1. **As a model risk reviewer**, I want the same six tests run on every model release and every cutoff change, each with a verdict and its numbers, so I can tell what moved without rebuilding a spreadsheet.
2. **As a model owner**, I want to see which test failed and by how much, with what passing would cost in approval rate and in the default rate of the approved book, so I can fix the right thing before the review.
3. **As credit policy**, I want the cutoff sweep beside the verdicts, so the choice between approval volume and the screen is mine and is made with both numbers in view.
4. **As compliance counsel**, I want every run to print what it cannot see (the group labels, the single ablation, the reason method), so I can use the pack as a screen and keep the conclusions where they belong.

---

## KPIs

**North star:** share of in-scope credit-model releases and cutoff changes with a FairLens run before going live. Target 🔴 100%.

**Inputs (leading):**
- Models with a decision log and a documented source for group labels (target: every in-scope model).
- Runs per release and per cutoff change (target: one per event, plus a scheduled rerun).
- Label-source coverage: share of decisions with a group label or an inferred one that has been validated (target: set by counsel).
- Run time (🔴 design target: finishes inside a release pipeline step; not built, not timed).

**Outputs (lagging):**
- Tests returning REVIEW or FAIL per run. Prototype baseline: 🟢 5 of 6 on the synthetic set at the policy cutoff.
- Time from a FAIL to the next PASS on the same model.
- Reviewer disagreement rate: REVIEW verdicts a person later clears.
- Releases that went live with an open FAIL (target 🔴 zero without a named, recorded exception).

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Shadow | 4w | Run the pack on one model's historical decisions; compare each verdict with what the validators concluded by hand. |
| 1 — Group-inference validation | 6w | Choose and validate the source of group labels or the inference step. No verdicts shown until the label error is measured. |
| 2 — Advisory runs on release | 6w | Verdicts posted with each release as a non-blocking check. Label-error sensitivity printed beside every verdict. |
| 3 — Blocking for tier-1 credit models | 6w | An open FAIL holds a release or a cutoff change; REVIEW needs a named approver. |
| 4 — Estate and interlocks | 8w | Remaining models; ControlMap evidence link; EvalForge as the runner; DriftSentinel reruns; TierGate tiering. |

---

## Open questions

1. **Where do the group labels come from?** Real credit data does not carry them. Recommendation: treat inference as its own product with its own validation, and print the label-error sensitivity beside every verdict until it is measured on real data.
2. **Who owns the thresholds?** The prototype's 0.80 screen, 15-point approval spread and the rest are assumptions of a modeled bank. Recommendation: model risk owns them, per model tier, as configuration under change control.
3. **Which reason method, and how many reasons are listed?** 🟢 The naming check passes when 4 reasons are listed (18 of 295 proxy-caused declines omit the postcode reason) and would fail when 2 are listed (only 59 of 295 name it). Recommendation: test the bank's own method, and record the number listed in the run.
4. **Does a REVIEW hold a release?** Recommendation: advisory first, blocking only for tier-1 models and only for FAIL; REVIEW needs a named approver but does not hold.
5. **What is the minimum group size?** The prototype's smallest group has 450 applicants and its interval straddles the screen. Recommendation: set a minimum per model from the first calibration phase; below it, the verdict is REVIEW by rule.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Reader:** a scheduled job reading scored decisions, outcomes and group labels from the model's scoring log through a read-only view.
- **Test runner:** stateless workers running the six tests; the bootstrap is seeded and the seed is stored with the result.
- **Group inference:** a separate adapter with its own validation, not folded into the tests.
- **Storage:** Postgres for runs, results and verdicts; a columnar store for per-decision results; object storage with retention for evidence bundles.

**Throughput envelope and latency budget.**
- Work per run is decisions × bootstrap resamples × cutoffs. The prototype runs 6,000 decisions with 1,000 resamples in plain Python. Production volumes have not been sized.
- Run latency: 🔴 design target is a run inside one pipeline step. Not built, not timed.

**Failure modes and degradation strategy.**
- Group labels missing or stale: the run says REVIEW with "labels unavailable"; it never returns PASS.
- Fewer decisions in a group than the minimum: REVIEW by rule.
- A model that is not a points scorecard: the reader takes a score per decision; reason codes are skipped and T5 reports "not applicable", not PASS.
- Runner unavailable: the release check fails per its mode (advisory fails open with a logged bypass; blocking fails closed for tier-1 models).

**Migration path from current state.**
- If the validators already keep an AIR spreadsheet: keep it. The pack is what reruns it on every release and cutoff change, with the sweep and the interval the spreadsheet usually lacks.
- If there is no decision log with outcomes: start the reader first. Every test needs scored decisions and a performance outcome.

**Org dependencies.**
- Counsel must agree on how a group label may be sourced or inferred. Without that the pack can only run on synthetic or consented data.
- The model owner must keep the scoring log and the outcome window in a form the reader can use.
- The model-risk team must accept the run record as part of its validation file. Without that interlock the audit story is incomplete.

---

*This PRD interlocks with 16 ControlMap, [Project 04 (EvalForge)](../04-evalforge-llm-eval-platform/), [Project 02 (DriftSentinel)](../02-driftsentinel-model-drift-monitoring/) and [Project 11 (TierGate)](../11-tiergate-ai-usecase-intake/). All four interlocks are 🔴 designed, none built.*
