# PRD · SwapBrief — Go or No-Go Brief for a Model Migration

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a pre-model-risk-committee read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an AI platform and model risk review in the seat. It is not a record of a PRD landed at a named bank. The deficiency taxonomy, the decision rule, and the rollout plan are mine. The prototype numbers come from simulated evaluation results (a seeded generator, no model called); the production validation is what the next role does.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | SwapBrief — a go or no-go decision brief for moving a production GenAI feature to a new model version |
| **Owner** | AI platform lead (line 1), with the feature product owner as co-owner of the decision |
| **Stage** | Portfolio prototype; pre-model-risk-committee read |
| **Primary user** | AI platform lead who has to move a feature before a vendor's end-of-support date |
| **Secondary users** | Model risk reviewer (approves tolerances and thresholds); feature product owner (accepts or refuses known regressions); finance partner (reads cost per correct answer) |
| **Problem** | A vendor retires the model behind a production GenAI feature. The team migrates because the headline average improved. Slice regressions, cost per correct answer, tail latency, and prompt sensitivity then show up in production, and nobody wrote down what would trigger a rollback. |
| **Solution** | A decision brief built on the evaluation harness's paired results: per-slice paired bootstrap intervals, cost per correct answer, p50 and p95 latency, a prompt-fair comparison, a decision (GO, GO WITH GUARDRAILS, NO-GO), and rollback triggers (metric, threshold, window). |
| **North-star metric** | Share of model migrations that ship with a signed brief and registered triggers. Target: 100%. Current state: 0%, no brief exists. 🔴 Design target. |
| **Prototype metrics (simulated)** | 🟢 False-GO rate 96.9% (headline average) to 8.2% (SwapBrief) over 200 scenarios; 🟢 bad-migration rate 47.0% to 10.5%; 🟢 guardrails on 23.3% of good migrations, 0.0% blocked; 🟡 2.2 bad migrations avoided per year, assuming 6 migrations a year. |
| **Cost** | 🔴 Not estimated. The prototype runs on a laptop. Production cost scales with evaluation-run volume and is a design question in `ARCHITECTURE.md`. |
| **Risk #1** | Teams treat GO WITH GUARDRAILS as GO and never register the triggers. Mitigation: the triggers are part of the decision record, and the release workflow does not close the migration until they are registered. |
| **Risk #2** | Tolerances are loosened until the answer is the one the team wants. Mitigation: proposer and approver are different people, threshold history is append-only, and model risk owns the tolerances. |
| **Risk #3** | A slice with too few items gives false comfort. Mitigation: the INCONCLUSIVE status, listed in every brief with its item count; in the prototype, 5 of 75 true slice regressions sat in such a slice, and more items resolved them. |
| **Out of scope** | Running the evaluation and judging answers (EvalForge, project 04); prompt authoring; vendor negotiation; drift monitoring beyond the triggers (DriftSentinel, project 02); price and cost accounting (InferenceLens, project 07). |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is migrations per year (🟡 6, the assumption in the README) or named reviewers. Effort in PM-weeks. The inputs are my estimates, not measurements. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Decision rule and brief** (GO, GO WITH GUARDRAILS, NO-GO with reasons) | 6 migrations | 3 | 0.9 | 2 | 8.1 | Mechanic in this prototype |
| 2 | **Prompt-fair comparison** (B with the old prompt and with the retuned prompt) | 6 migrations | 3 | 0.8 | 2 | 7.2 | Mechanic in this prototype |
| 3 | **Per-slice paired bootstrap intervals and status ladder** | 6 migrations | 3 | 0.9 | 3 | 5.4 | Mechanic in this prototype |
| 4 | **Rollback trigger generator** (metric, threshold, window, minimum sample) | 6 migrations | 3 | 0.85 | 3 | 5.1 | Mechanic in this prototype |
| 5 | **Cost per correct answer with an interval** (price feed from InferenceLens) | 6 migrations | 2 | 0.8 | 2 | 4.8 | Mechanic in this prototype; price feed sequenced for v0.2 |
| 6 | **Items-needed check per slice** (flag a slice that cannot be resolved before the run) | 6 migrations | 2 | 0.8 | 2 | 4.8 | Sequenced for v0.1 |
| 7 | **p50 and p95 with intervals** | 6 migrations | 2 | 0.7 | 2 | 4.2 | Mechanic in this prototype |
| 8 | **Evidence bundle to the model risk record** | 4 reviewers | 2 | 0.9 | 2 | 3.6 | Sequenced for v0.3 |
| 9 | **EvalForge probe-set import** (slice-tagged, versioned items) | 6 migrations | 3 | 0.75 | 4 | 3.4 | Sequenced for v0.2 |
| 10 | **Snapshot-pin rollback target** (DriftSentinel interlock) | 6 migrations | 2 | 0.7 | 3 | 2.8 | Sequenced for v0.2 |
| 11 | **Standard-slice waiver record** (named owner, expiry date) | 4 owners | 2 | 0.7 | 2 | 2.8 | Sequenced for v0.2 |
| 12 | **Trigger evaluator on a live scoring stream** | 6 migrations | 3 | 0.6 | 6 | 1.8 | Sequenced for v0.3 |
| 13 | **Threshold approval workflow** (proposer and approver differ) | 4 reviewers | 2 | 0.7 | 4 | 1.4 | Sequenced for v0.3 |
| 14 | **Multi-candidate comparison** (A against B and C) | 3 migrations | 2 | 0.6 | 4 | 0.9 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from SwapBrief | What they fear |
| --- | --- | --- | --- |
| **AI platform lead** (line 1) | Owner | A decision they can defend before the end-of-support date, and a rollback target that still exists when a trigger fires. | A tool that blocks every migration, or that becomes their unowned maintenance burden. |
| **Model risk reviewer** (line 2) | Approver of tolerances and thresholds | Evidence they can challenge: intervals, not averages, and a threshold history with names on it. | SwapBrief becoming a parallel attestation surface that competes with the model risk record. |
| **Feature product owner** | Co-owner of the decision | To know which customer questions get worse and what they are accepting in writing. | Being handed a NO-GO with no path, or a GO that later turns out to be a known regression they never saw. |
| **Finance partner** | Consulted | Cost per correct answer on the new model, not a price-per-token headline. | A migration that looks cheaper on the vendor's price sheet and costs more per answer. |
| **Vendor management** | Consulted | The end-of-support date and what a rollback to the old model is worth before that date. | Discovering a rollback target has been withdrawn. |
| **Customer service operations** | Consulted | A trigger before the complaint queue grows. | Finding out from the queue. |
| **Internal audit** (line 3) | Reviewer | An append-only record of the decision, the thresholds, and who approved them. | A decision with no trail. |

---

## User stories (top 4)

1. **As an AI platform lead**, I want one brief per migration that says GO, GO WITH GUARDRAILS, or NO-GO and why, so I can take a defensible decision to the release board before the vendor's end-of-support date.
2. **As a model risk reviewer**, I want every slice reported as an interval with a tolerance and a status, and every threshold stored with its proposer and approver, so I can challenge the evidence and not the average.
3. **As a feature product owner**, I want to see which slices regress, by how much, and under which prompt, so I can accept a bounded regression in writing or refuse it.
4. **As a finance partner**, I want cost per correct answer with an interval beside the price per token, so I can tell a cheaper token from a cheaper answer.

---

## KPIs

**North star:** share of model migrations that ship with a signed brief and registered triggers. Target: 100%. 🔴 Design target.

**Inputs (leading):**
- Slices with enough items to be resolved: share of slices not marked INCONCLUSIVE (prototype, base evaluation of 720 items: 1 of 8 slices inconclusive on the committed set).
- Briefs with every trigger registered and approved before release (target 100%, 🔴).
- Time from vendor notice to a signed decision (🔴 no target set; measure it first).

**Outputs (lagging):**
- Bad-migration rate (prototype: 🟢 10.5% for SwapBrief against 47.0% for the headline rule, on simulated scenarios; in production, measured as migrations that needed an unplanned rollback or a post-launch waiver).
- False-GO rate (prototype: 🟢 8.2% against 96.9%).
- Guardrails given to migrations that were fine (prototype: 🟢 23.3%; the cost of caution, tracked so it does not grow).
- Unplanned rollbacks, and rollbacks a trigger fired that the owner judged unnecessary.

---

## Rollout

All durations are design targets, 🔴 not executed.

| Phase | Duration | Scope |
| --- | --- | --- |
| 0 — Backtest | 4w | Replay the brief on past migrations from the model inventory's change records; no live decisions. |
| 1 — Shadow | 6w | Write the brief for each live migration beside the existing decision; compare the two and record the differences. |
| 2 — Gate | 6w | A signed brief is required for release; the model risk reviewer approves tolerances and thresholds. |
| 3 — Triggers live | 8w | Trigger evaluator on the live scoring stream for one feature; a rollback drill before the end-of-support date. |
| 4 — Evidence | 4w | The brief and its approvals attach to the model risk record; EvalForge and InferenceLens feeds replace manual exports. |

---

## Open questions

1. **Who owns the tolerances?** A critical slice blocks and a standard slice ships with a trigger; who sets the tolerance numbers, and how often are they re-approved? Recommendation: model risk owns them, re-approved at each migration.
2. **Is a standard-slice regression ever acceptable?** The prototype ships it with a trigger and an owner. Recommendation: allow it only with a named owner and an expiry date, recorded as a waiver.
3. **How many items does a slice need?** The prototype marks a slice INCONCLUSIVE when its interval is wider than ±10 points and still reaches past the tolerance. Recommendation: run an items-needed check before the evaluation, not after.
4. **What is the right window for a production trigger?** The prototype uses 7 days for slices, 24 hours for cost, and 1 hour (3 in a row) for p95. Recommendation: set windows from each feature's traffic, not from a global default.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Analysis service:** stateless; takes paired results and a policy version, returns intervals, statuses, a decision, and proposed triggers. Seeds are fixed so the same input gives the same brief.
- **Trigger registry:** Postgres, append-only; a change is a new row with a proposer and an approver.
- **Trigger evaluator:** a scheduled job reading hourly aggregates of scored responses from a column store; it fires, pages, and asks the router to return traffic to the pinned model A.
- **Interlocks:** probe sets from EvalForge, price and cost per feature from InferenceLens, snapshot pins from DriftSentinel.

**Throughput envelope.** One analysis per migration, on the order of 720 to several thousand items; the prototype's 200-scenario test takes about 20 seconds on a laptop. Trigger evaluation is the only recurring load: one aggregate query per trigger per window. 🔴 Design figures, not load-tested.

**Failure modes and degradation strategy.**
- Trigger evaluator down: page the owner and mark the migration "triggers unevaluated". Do not change routing on evaluator failure.
- Pinned model A no longer deployable: a fired trigger pages with the fallback plan instead of rolling back.
- Evaluation export missing a condition: the brief refuses to decide and says which condition is missing.

**Migration path from current state.**
- If the team decides on a spreadsheet or a dashboard average: start with Phase 0, replaying past migrations.
- If an evaluation harness already exports per-item results: SwapBrief is the layer on top; do not replace the harness.

**Org dependencies.**
- Model risk must accept the brief as part of the model change record, or the decision has no authority.
- The platform's router needs an API a trigger can call; start that conversation on day one.
- Product owners must be willing to sign a bounded regression, or every standard-slice regression becomes a NO-GO by default.

---

*This PRD interlocks with [Project 02 (DriftSentinel)](../02-driftsentinel-model-drift-monitoring/), [Project 04 (EvalForge)](../04-evalforge-llm-eval-platform/), and [Project 07 (InferenceLens)](../07-inferencelens-inference-finops/). Acknowledgement: [Hamel Husain's eval-first thesis](https://hamel.dev/blog/posts/evals/): the evaluation set comes before the decision code.*
