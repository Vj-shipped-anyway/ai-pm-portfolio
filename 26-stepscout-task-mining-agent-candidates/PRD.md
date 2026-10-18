# PRD · StepScout — Task Mining to Agent Candidates

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for an operations-transformation, data-protection and works-council read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an operations-transformation review in the seat. It is not a record of a PRD landed at a named bank. The step features and classifier rules, the control screen, the build-brief shape, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. RICE scores and rollout durations below are planning estimates (🔴), not measurements. The answer key is the generator's own and I planted the signals the classifier reads, so accuracy shows the method works on this data. No model is used anywhere in this repo. Task mining records what employees do at their desktops: that is a privacy and works-council question this PRD designs for and the prototype does not build.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | StepScout — task mining to agent candidates |
| **Owner** | Operations process owner for the queue (line-1), with the operations transformation lead as co-owner of the candidate list |
| **Stage** | Portfolio prototype; operations-transformation, data-protection and works-council read |
| **Primary user** | The operations lead who has to choose where to put an agent |
| **Secondary users** | The engineer who picks up a build brief; the control and data-classification owners; the data-protection officer; a works-council representative; the process-mining analyst. The workers are the subjects of the data and are never scored |
| **Problem** | Agent pilots are aimed from an interview and from the case system's log. The interview describes one happy path, the log never sees work in a spreadsheet, an email or a second application, and a ranking by volume times time puts judgment-heavy steps at the top. In the synthetic data, 🟢 24.8% of cases follow the documented path, 🟢 44.8% of touch time is outside the case system, and 🟢 6 of the volume-first top 10 are steps an agent can take over. |
| **Solution** | An evidence layer: merge desktop and system events into step occurrences with touch time, classify each step from observable features, screen it for controls and restricted data, rank by modeled hours at stake times readiness, and write a build brief an engineer can pick up. |
| **North-star metric** | Share of agent pilots aimed at a step that a person who knows the work calls agent-ready. Target 🔴 set after the labeled-sample phase. Prototype: 🟢 9 of 10 in the top 10 against the generator's key; the miss is S14. |
| **Measured metrics (synthetic)** | 🟢 13 of 16 steps classified as the key says; precision 92.3% and recall 100.0% for agent-ready steps. 🟢 87.8% of handling time attributed to a named step, against at most 49.6% from the log alone. 🟢 98.8% of status events land on a labeled occurrence of the right step. |
| **Modeled metrics** | 🟡 592 agent-ready hours at stake in StepScout's top 10 against 371 in the volume-first list, per 30 days, assuming an agent removes 70% of a step's touch time. 🟡 Utility (42.3 − 26.5) × 14 = 221 hours per 30 days. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on collector coverage, event volume and labeling effort, and has not been sized. |
| **Risk #1** | A judgment made off the desktop looks like a rule. 🟢 S14 is classified AGENT and the key says HUMAN_JUDGMENT; it ranks #10. Mitigation: the build brief's shadow-mode test, a check of whether similar inputs lead to different choices, and a time-diary sample of off-desktop work. All 🔴 designed, not built. |
| **Risk #2** | Desktop data on employees. Task mining is a privacy and works-council question. Mitigation by design: pseudonymous worker ids, counts of typed characters and never text, views aggregate by step with a minimum group size, no ranking of workers, collection only after the review. 🔴 designed, not built. |
| **Risk #3** | The thresholds fit the planted signals and not a real queue. Mitigation: calibrate on a sample of steps that a person who knows the work has classified by hand, and report the gap. 🔴 designed. |
| **Out of scope** | Which pilots get funded and the intake form (TierGate 11); benefit tracking after a build (ValueLedger 12); what an agent is permitted to do (ScopeKeeper 23); the fallback and the drill (KillSwitch 25); adoption by workers (AdoptionPulse 21); building the agent (AgentKit 27); any scoring of workers. |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is steps or briefs, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. **The privacy and works-council review is a gate, not a backlog item: in a real deployment nothing is collected before it is done.**

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Ranking** by hours at stake times readiness | 16 steps | 2 | 0.8 | 1 | 25.6 | Built in prototype; v0.1 |
| 2 | **Hand-labeled sample and threshold calibration** (a person who knows the work classifies a sample of steps) | 16 steps | 3 | 0.7 | 2 | 16.8 | Sequenced for v0.1 |
| 3 | **Merge** desktop and system events into step occurrences | 16 steps | 3 | 0.9 | 3 | 14.4 | Built in prototype; v0.1 |
| 4 | **Control screen** and register (four-eyes, restricted data, gated steps) | 16 steps | 3 | 0.8 | 3 | 12.8 | Built in prototype; v0.1 |
| 5 | **Classifier** from observable features | 16 steps | 3 | 0.7 | 3 | 11.2 | Built in prototype; v0.1 |
| 6 | **Time-diary sample** for work off the desktop | 16 steps | 2 | 0.6 | 2 | 9.6 | Sequenced for v0.2 |
| 7 | **Pseudonymization and aggregate-only views** with a minimum group size | 16 steps | 3 | 0.7 | 4 | 8.4 | Sequenced for v0.1 |
| 8 | **Build brief writer and validator** | 10 briefs | 3 | 0.8 | 3 | 8.0 | Built in prototype; v0.1 |
| 9 | **Brief hand-off** to the permission review and the agent build | 10 briefs | 2 | 0.7 | 2 | 7.0 | Sequenced for v0.2 |
| 10 | **Hours-saved tracking** after a build, feeding the benefit record | 10 briefs | 3 | 0.6 | 3 | 6.0 | Sequenced for v0.3 |
| 11 | **Step labeler** for a real miner (application and action patterns to step ids) | 16 steps | 3 | 0.5 | 6 | 4.0 | Sequenced for v0.2 |
| 12 | **Decision-consistency check** (similar inputs, different choices) for hidden judgment | 16 steps | 3 | 0.4 | 5 | 3.8 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from StepScout | What they fear |
| --- | --- | --- | --- |
| **Operations lead** | Primary user | A list of steps to put an agent on, with the evidence, so a pilot is not aimed at the wrong step. | Another ranking that rewards waiting; a pilot that fails in shadow mode. |
| **Process owner** (line-1) | Owner | Step-level touch time and rework, in numbers the team recognizes. | A tool that is read as a measure of the people on the queue. |
| **Engineer** | Reader of the brief | A pack with scope, tools, controls, tests and an estimate, so the first line of code is not a guess. | A brief that hides a judgment step or a control. |
| **Control and data-classification owners** | Register owners | The restricted-data and four-eyes flags applied before anything is built. | An agent on a four-eyes step because nobody flagged it. |
| **Data-protection officer** | Approver | Pseudonymous ids, no keystroke content, a stated purpose and aggregate views. | Employee monitoring by another name. |
| **Works-council representative** | Consulted | A say before collection, and a promise that nobody is scored. | Findings used against individual workers. |
| **Workers** | Subjects | To know what is collected and why; the dull steps taken away, not their jobs. | Being measured at the desk. |
| **Risk reviewer** (line-2) | Auditor | A record of why each step was called agent-ready, with the features it came from. | A classification nobody can explain. |

---

## User stories (top 4)

1. **As an operations lead**, I want every workflow step shown with its measured touch time and its readiness, so I do not pick a pilot because a step waits a long time.
2. **As an engineer**, I want a build brief with the scope, the tools, the controls, the tests and an estimate, so I can start from evidence and know what the agent must not touch.
3. **As a control owner**, I want restricted-data and four-eyes steps flagged before a candidate list leaves the team, so no agent is aimed at a step that must stay with a person.
4. **As a works-council representative**, I want the data to be pseudonymous and the views aggregate by step, so the work is studied and the people are not.

---

## KPIs

**North star:** share of agent pilots aimed at a step that a person who knows the work calls agent-ready. Target 🔴 set after the labeled-sample phase.

**Inputs (leading):**
- Desktop events that carry a step label (target: set in calibration). Prototype: 🟢 2.4% unlabeled.
- Status events that land on a labeled occurrence of the right step (target: set in calibration). Prototype: 🟢 98.8%.
- Steps with a control and data-classification flag in the register (target: every step in scope). Prototype: 16 of 16 by construction.

**Outputs (lagging):**
- Agent-ready steps in the top 10. Prototype baseline: 🟢 6 with the volume-first list, 9 with StepScout.
- Classification accuracy against a labeled sample. Prototype: 🟢 13 of 16 against the generator's key.
- Handling time attributed to a named step. Prototype: 🟢 87.8% against at most 49.6% from the log alone.
- Modeled hours at stake in the top 10. Prototype: 🟡 592 against 371.
- Work that no file records (phone calls). Prototype: 🟢 10.1% of handling time.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Review | 4w | Privacy, data-protection and works-council review. Agree the fields, the retention, the pseudonymization and the aggregate-only rule. Nothing is collected. |
| 1 — Pilot collection | 4w | One queue, pseudonymous events, views aggregate by step. Compare the merged view with the interview and the log. |
| 2 — Labeled sample | 3w | People who know the work classify a sample of steps. Calibrate the thresholds and report where the classifier and the people disagree. |
| 3 — Candidate list and control screen | 4w | The ranked list with the register's flags, reviewed with the control owners. |
| 4 — Briefs and shadow mode | 6w | Briefs to engineering for the top packs; one agent runs in shadow mode against workers. |
| 5 — Close the loop | ongoing | Measured touch time after a build, fed to the benefit record. |

---

## Open questions

1. **Consent and scope.** Who approves collection, for which fields, and for how long? Recommendation: the works-council consultation and the data-protection review come first, and the pilot runs on one queue.
2. **How fine is a step?** A label that is too coarse hides a judgment inside a rule. Recommendation: label at the level a worker would name a step, and split any step whose runs disagree.
3. **How do hidden judgments get found?** In the synthetic data S14 is invisible. Recommendation: a decision-consistency check and a time-diary sample, and a review of the top 10 with a person who knows the work.
4. **What share of touch time does an agent really remove?** The 70% is an assumption. Recommendation: measure it in shadow mode on the first brief and replace it.
5. **Who owns the control register?** Recommendation: the data-classification and control owners, with an approver and a version.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Collector and labeler:** a desktop collector that writes pseudonymous events (application, action, time, a count of typed characters), and a labeler that maps patterns to step ids.
- **Merge and classifier:** a batch job that builds step occurrences, joins the case-system log and writes step features and classes.
- **Register:** the control and data-classification flags, owned outside the team, versioned and approved.
- **Ranker and brief writer:** ranking by hours at stake times readiness, and briefs validated against build-brief/v1.
- **Storage:** Postgres for steps, features, classes, rankings and briefs; object storage for evidence bundles.

**Throughput envelope.**
- The prototype merges 53,584 desktop events and 19,050 status events with a plain Python loop in seconds. Production volume has not been sized.
- Collector latency and label coverage on a real miner: 🔴 not built, not timed.

**Failure modes and degradation strategy.**
- Collector down: the step features keep their last values and the list is marked stale.
- Labeler cannot assign an event: the event counts toward handling time and no step; the unlabeled share is a tracked number (🟢 2.4% here).
- Case-system log late: the merge runs on desktop events alone and flags the steps that lose their anchor.
- Register missing a flag: the step is held out of the candidate list until the control owner answers.

**Migration path from current state.**
- If there is an interview-based pilot list: keep it as the nomination step. StepScout checks each nominee against touch time, features and the register.
- If there is a process-mining pass over the case log: keep it for variants and cycle time. StepScout adds the steps and the time the log cannot see.

**Org dependencies.**
- Someone must own the register, with a version and an approver. Without that the control screen is a stale document.
- The data-protection and works-council review must be done before any desktop event is collected.
- An engineer must be willing to start from a brief and to report where the brief was wrong.

---

*This PRD interlocks with Projects 11 (TierGate) and 12 (ValueLedger) for intake and the business case, 23 (ScopeKeeper) for agent permissions, 25 (KillSwitch) for the fallback, 21 (AdoptionPulse) for adoption, and 27 (AgentKit), which takes a brief of this shape as its input. All interlocks are 🔴 designed, none built.*
