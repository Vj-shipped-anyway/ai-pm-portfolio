# PRD · AdoptionPulse — AI Enablement Funnel

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for an AI-enablement program read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an AI enablement program review in the seat. It is not a record of a PRD landed at a named bank. The stage definitions, the leak logic, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. RICE scores and rollout durations below are planning estimates (🔴), not measurements.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | AdoptionPulse — AI adoption measured by stage, unit and week |
| **Owner** | AI enablement program lead (line-1), with unit heads as co-owners of the response |
| **Stage** | Portfolio prototype; program-read of a four-stage funnel |
| **Primary user** | The AI enablement program lead, who is asked whether the rollout is working |
| **Secondary users** | Unit heads; champions; HR and privacy reviewer; security; the finance partner who reads cost per active user |
| **Problem** | A bank licenses an AI assistant to hundreds of staff and reports adoption as licenses issued and people who logged in. That number stays high. It cannot say who uses the tool every week, which unit lags, whether training changed anything or whether champions matter. In the synthetic data, 🟢 704 of 800 licensed users (88.0%) count as adopted while 🟢 221 of 800 (27.6%) are habitual. |
| **Solution** | A staging layer on weekly AI usage: licensed, activated, habitual, proficient from plain rules in a policy file; the funnel by org unit with the leak between stages; training-to-usage and champion reads; a retention curve; and a ranked list of units to act on with a rule-based action. |
| **North-star metric** | Habitual users as a share of licensed users, by unit. In this model: 🟢 27.6% across the estate, from 4.0% to 66.7% by unit. No target is set here; targets are set per unit after the shadow phase. |
| **Measured metrics (synthetic)** | 🟢 762 of 800 users (95.2%) staged as the generator decided, against 407 of 800 (50.9%) for the login flag at its best; 🟢 337 of 558 activated users (60.4%) never became habitual; 🟢 51.6% of activated users active in week 4 and 36.4% in week 12. |
| **Modeled metrics** | 🟡 Utility about 355 users correctly staged, assuming the modeled bank's 800 licensed staff are all in scope and the accuracy measured here holds on real usage data. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on the usage feed volume and has not been sized. |
| **Risk #1** | Usage data about people gets used to rate people. Mitigation: unit-level reports only, a minimum group size, no individual ranking, access logged, and an HR and privacy review before the first report leaves the program team. |
| **Risk #2** | The stage thresholds look objective and are assumptions. Mitigation: the policy file is versioned and approved; thresholds are calibrated against a manager sample review in phase 1; every report prints the policy version. |
| **Risk #3** | "Proficient" is read as "good at the work". It is a proxy. 🟢 13 of 80 users staged proficient (16.2%) produce poor work in the generator, and the counts cannot show it. Mitigation: a manager sample review with a rubric agreed with the unit head, and the word "proficient" never shown without its definition. |
| **Out of scope** | Benefit realization against a holdout (ValueLedger, 12); which use cases to enable (TierGate, 11); enablement as a program portfolio (PortfolioBoard, 24); inference cost (InferenceLens, 07); judging the quality of anyone's work. |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is org units, or roles where labeled. Effort in PM-weeks. RICE is rounded to a whole number. All scores are 🔴 planning estimates. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Usage ingest and pseudonymous user key** | 20 units | 3 | 90% | 4 | 14 | Sequenced for v0.1 |
| 2 | **Stage rules from the policy file** (licensed, activated, habitual, proficient) | 20 units | 3 | 90% | 2 | 27 | Built in prototype; v0.1 |
| 3 | **Unit funnel and leak** (conversion furthest below the estate rate) | 20 units | 3 | 80% | 3 | 16 | Built in prototype; v0.1 |
| 4 | **Minimum group size and unit-level access** | 20 units | 3 | 80% | 3 | 16 | Sequenced for v0.1 |
| 5 | **Retention curve by week** | 20 units | 2 | 90% | 1 | 36 | Built in prototype; v0.1 |
| 6 | **Ranked list with a rule-based action** | 20 units | 2 | 70% | 2 | 14 | Built in prototype; v0.2 |
| 7 | **Training-to-usage read** | 20 units | 2 | 70% | 2 | 14 | Built in prototype; v0.2 |
| 8 | **Champion coverage read** | 20 units | 2 | 60% | 2 | 12 | Built in prototype; v0.2 |
| 9 | **Weekly stage job and report delivery** | 20 units | 3 | 70% | 5 | 8 | Sequenced for v0.2 |
| 10 | **Threshold calibration against real usage** | 20 units | 3 | 60% | 4 | 9 | Sequenced for v0.2 |
| 11 | **Manager sample review for the quality gap** | 20 units | 3 | 50% | 4 | 8 | Sequenced for v0.3 |
| 12 | **Policy versioning and approval** | 3 roles | 2 | 90% | 2 | 3 | Sequenced for v0.3 |
| 13 | **Staggered rollout design with ValueLedger** (a causal read of training and champions) | 20 units | 3 | 50% | 5 | 6 | Queued |
| 14 | **Opt-in individual coaching view** | 20 units | 1 | 40% | 5 | 2 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from AdoptionPulse | What they fear |
| --- | --- | --- | --- |
| **AI enablement program lead** (line-1) | Owner | An honest answer to "is it working", by unit, with the place each team loses people. | A report that reads well and means little; a login number that leaves them defending a rollout they cannot see. |
| **Unit heads** | Co-owners of the response | Their unit's funnel against the estate and one next step they can take without building a report. | Being ranked in public; actions that add work with no support. |
| **Champions** | Consulted | To see where in their unit people start and stop. | Being judged by their unit's numbers when the unit is hard. |
| **HR and privacy reviewer** | Approver | Reports that cannot single out a person; access they can audit. | Usage data used in performance conversations. |
| **Security / CISO** | Approver | Pseudonymous keys, least-privilege reads from the usage log, no prompt text stored. | A second copy of staff activity. |
| **Data platform owner** | Consulted | A weekly job that fits the platform's scheduling and lineage. | A bespoke pipeline nobody else can run. |
| **Finance partner** | Consulted | Habitual users by unit as the denominator for cost per active user. | A denominator that moves each time the thresholds change. |
| **Staff** | Subjects | To know what is measured and why; a way to ask. | Being ranked by how often they use a tool. |

---

## User stories (top 4)

1. **As an AI enablement program lead**, I want every licensed user staged each week from AI usage, so I know which units lose people and at which stage.
2. **As a unit head**, I want my unit's funnel next to the estate's and one rule-based next step, so I can act without building a report.
3. **As a champion**, I want to see how many people in my unit started and stopped, as a group figure, so I know where to spend my time.
4. **As an HR and privacy reviewer**, I want reports limited to groups above a minimum size with no individual ranking, so usage data cannot be used to rate a person.

---

## KPIs

**North star:** habitual users as a share of licensed users, by unit. Prototype baseline: 🟢 27.6% across the estate. Target: 🔴 set per unit after the shadow phase.

**Inputs (leading):**
- Licensed users with all weeks of usage present (target: every licensed user).
- Units with a named champion and an active roster.
- Stage policy approved and versioned (target: one approved version in force).
- Unit heads who open the weekly report.

**Outputs (lagging):**
- Habitual rate by unit. Prototype: 🟢 4.0% to 66.7%.
- Activated-to-habitual conversion. Prototype: 🟢 39.6% across the estate.
- Active share of activated users in week 12. Prototype: 🟢 36.4%.
- Trained users who never used the tool. Prototype: 🟢 132 of 428 (30.8%).
- Staged-proficient users whose work is rated poor in the sample review. Prototype: 🟢 13 of 80 in the generator, planted and invisible to telemetry by design.
- Gap between the best and worst unit. Prototype: 🟢 62.7 points on the habitual rate, against 30.0 points on the login view.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Shadow | 4w | Ingest usage and stage every user for a few units. Show nothing to unit heads; compare the stages against a manager sample. |
| 1 — Calibrate | 4w | Check thresholds against what staged users actually do. Sample review of staged-proficient users. Agree the policy and the minimum group size with HR and privacy. |
| 2 — Program lead report | 6w | A weekly unit-level report to the program lead. Policy version printed on every report. |
| 3 — Unit heads and champions | 6w | Unit funnels and rule-based actions shared with unit heads, above the minimum group size. |
| 4 — Interlocks | 8w | Habitual users by unit to ValueLedger and InferenceLens; stage counts to PortfolioBoard. |

---

## Open questions

1. **Unit level or individual level?** Recommendation: unit level with a minimum group size. Individual views only if a person opts in, and never in a performance process.
2. **Who owns the usage feed?** The stager needs sessions, prompts, accepted outputs and advanced-feature counts per user per week. Recommendation: the platform team owns capture; prompt text is never stored.
3. **Is four of the last six weeks the right line?** Recommendation: treat it as a starting value, calibrate in phase 1 against what staged users produce, and keep the policy versioned.
4. **How do we read the effect of training and champions?** On real data a with-and-without comparison is confounded. Recommendation: stagger the next wave of training and champion assignment and hold units out, jointly with ValueLedger. 🟢 In the generator the champion read missed its planted size (23.1 measured, 13.9 planted) even with nothing confounded but 20 unit draws.
5. **What is a rubric for the quality gap?** Recommendation: a manager sample review, with a rubric agreed with each unit head.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Ingest:** a scheduled pull of the assistant's usage log, keyed by a pseudonymous user key, joined to the staff directory inside the data platform.
- **Stager:** a weekly job that applies the policy file's rules and writes one stage row per user per week.
- **Report:** unit-level aggregates with a minimum group size, a ranked list and a rule-based action per unit.
- **Storage:** Postgres for usage, stages, policy versions and reports, partitioned by week; object storage with retention for report snapshots.

**Throughput envelope and latency budget.**
- The prototype stages 800 users across 12 weeks (9,600 user-weeks) with a plain Python loop. Production volumes have not been sized.
- Freshness: 🔴 design target is a report ready at the start of each week. Not built, not timed.

**Failure modes and degradation strategy.**
- Usage feed late or partial: the report shows the last complete week and says so; no stage is computed from an incomplete week.
- A unit below the minimum group size: rolled up into a parent unit, never shown alone.
- Policy changed: the report prints both versions for one week so a step change is not read as a behavior change.
- Directory join fails for a user: the user is staged but counted in an "unassigned" bucket that is not shown below the minimum size.

**Migration path from current state.**
- If the program reports logins today: keep them. They measure reach, and reach is the first stage of the funnel. AdoptionPulse starts where the login count stops.
- If there is no usage feed: ask for one before anything else. The stager needs weekly counts per person.

**Org dependencies.**
- HR and privacy must approve what is measured and who sees it. Without that the first report does not ship.
- The platform team must expose per-user weekly counts without prompt text.
- Unit heads must agree to read the report and act on it. Without that the ranked list is a page nobody opens.

---

*This PRD interlocks with [Project 12 (ValueLedger)](../12-valueledger-ai-benefit-tracking/), [Project 11 (TierGate)](../11-tiergate-ai-usecase-intake/) and [Project 07 (InferenceLens)](../07-inferencelens-inference-finops/), and with Project 24 (PortfolioBoard), which is not yet in this repo. All four interlocks are 🔴 designed, none built.*
