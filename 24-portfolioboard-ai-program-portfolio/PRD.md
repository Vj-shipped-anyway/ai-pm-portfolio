# PRD · PortfolioBoard — An AI Program Portfolio Run on Gate Evidence, Capacity and Dependencies

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a portfolio-governance read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an AI program office review in the seat. It is not a record of a PRD landed at a named bank. The status rules, the pull rule, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. RICE scores and rollout durations below are planning estimates (🔴), not measurements.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | PortfolioBoard — an AI program portfolio run on gate evidence, capacity and dependencies |
| **Owner** | Head of the AI program office (line-1), with the model risk review lead as co-owner of the gate evidence |
| **Stage** | Portfolio prototype; portfolio-governance read |
| **Primary user** | Head of the AI program office, who owns the monthly portfolio report and the pause and fund calls |
| **Secondary users** | Program owners who attest evidence; sponsors who fund; model risk review and security review leads who run the scarce queues; the finance partner who reads the benefit line |
| **Problem** | A modeled bank runs 30 AI programs. Each owner picks a red, amber or green status once a month. The report cannot show which green programs fail their gate criteria, where reviewer demand exceeds supply, which programs wait on a slipped upstream program, how much work is in flight per stage, or how much promised benefit is at risk. In the synthetic data, 🟢 4 of 19 green reports fail a gate criterion, 🟢 6 sit behind a red or slipped upstream program, and 🟢 6 of 16 team-quarters have demand above supply. |
| **Solution** | A status layer over the evidence: an evidence status per program with its reason, a capacity grid for four teams over four quarters, dependency propagation, a pull rule that suggests what to pause when a stage is over its work-in-progress limit, and a benefit-at-risk rollup labeled modeled. |
| **North-star metric** | Share of in-scope AI programs whose monthly status is computed from gate evidence instead of picked by the owner. Target 🔴 100% of in-scope programs. Today in this model: 0%, nothing runs. |
| **Measured metrics (synthetic)** | 🟢 23 of 30 statuses change once evidence is applied; 🟢 the board shows the true status for 27 of 30 programs against 7 of 30 for the report (by construction apart from 3 planted false attestations); 🟢 model risk review is over in 4 of 4 quarters; 🟢 10 of 30 programs carry stale evidence. |
| **Modeled metrics** | 🟡 $20.25M of $60.35M owner-estimated benefit on red-by-evidence programs (owner estimates, never measured). 🟡 Utility about 23.3 owners and sponsors who see a true status for their program, assuming one sponsor per 3 programs and that the board is read and acted on. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on the number of source systems and has not been sized. |
| **Risk #1** | Attestation becomes a form to fill, so "met" is cheap and the board inherits the optimism it was built to remove. Mitigation: a sample audit of "met" flags against the documents, with the result feeding the status. In the prototype, 🟢 3 planted false attestations are invisible to the board. |
| **Risk #2** | The rules mark most programs amber and the board stops being read. In the prototype, 🟢 14 of 30 programs are amber. Mitigation: owner-set freshness rules, a reason on every status, and the count of ambers cleared per cycle as a first-class metric. |
| **Risk #3** | A pause suggestion is read as a decision, or is gamed by inflating the benefit estimate it ranks on. Mitigation: suggestions with a named approver; ValueLedger's measured benefit replaces the estimate when it exists. |
| **Out of scope** | Measuring benefit (ValueLedger, 12); intake and tiering (TierGate, 11); collecting control evidence (ControlMap, 16); incident handling (IncidentLedger, 19); the adoption funnel (AdoptionPulse, 21); the resourcing system itself. |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is programs, teams, stages, criteria or roles, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Evidence feed and store** (attestations with the evidence date, per program and criterion) | 30 programs | 3 | 0.8 | 5 | 14.4 | Sequenced for v0.1 |
| 2 | **Evidence status rules** (red, amber, green with a reason on every row) | 30 programs | 3 | 0.9 | 2 | 40.5 | Built in prototype; v0.1 |
| 3 | **Dependency register and propagation** (blocked-by, direct and through a chain) | 30 programs | 3 | 0.8 | 2 | 36.0 | Built in prototype; v0.1 |
| 4 | **Capacity grid** (demand against supply, four teams by quarter) | 4 teams | 3 | 0.8 | 3 | 3.2 | Built in prototype; v0.1 |
| 5 | **Work-in-progress limits and pull rule** (pause suggestions, review supply by value per FTE) | 5 stages | 2 | 0.7 | 2 | 3.5 | Built in prototype; v0.2 |
| 6 | **Benefit-at-risk rollup** (owner estimates, labeled modeled) | 30 programs | 2 | 0.9 | 1 | 54.0 | Built in prototype; v0.2 |
| 7 | **Freshness rules owned by each attester** (days per criterion) | 17 criteria | 2 | 0.8 | 2 | 13.6 | Sequenced for v0.2 |
| 8 | **Sample audit of "met" flags** (counter the known limit) | 30 programs | 3 | 0.6 | 4 | 13.5 | Sequenced for v0.2 |
| 9 | **Board console** for the head of the AI program office | 6 roles | 3 | 0.8 | 4 | 3.6 | Sequenced for v0.3 |
| 10 | **Owner challenge flow** (dispute a status, attach evidence) | 25 owners | 2 | 0.6 | 3 | 10.0 | Sequenced for v0.3 |
| 11 | **TierGate interlock** (risk tier and intake registration from intake) | 30 programs | 2 | 0.7 | 3 | 14.0 | Queued |
| 12 | **ControlMap interlock** (control evidence from the control crosswalk) | 17 criteria | 2 | 0.6 | 4 | 5.1 | Queued |
| 13 | **ValueLedger interlock** (measured benefit replaces the estimate) | 30 programs | 3 | 0.5 | 5 | 9.0 | Queued |
| 14 | **IncidentLedger and AdoptionPulse interlocks** (incidents and adoption feed status) | 30 programs | 1 | 0.4 | 4 | 3.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from PortfolioBoard | What they fear |
| --- | --- | --- | --- |
| **Head of the AI program office** (line-1) | Owner | A monthly view they can defend: which programs are really on track, where the queue is, what to pause. | A board nobody trusts, or one that turns every program amber. |
| **Program owners** | Attesters | A clear list of what is missing and why a status is what it is, and a way to challenge it. | A second reporting burden that they cannot influence; a red they did not see coming. |
| **Sponsors** | Funders | One page that says where the money is at risk, with the reason. | Finding out at the next gate. |
| **Model risk review lead** (line-2) | Co-owner of gate evidence | Demand they can plan against, and a stop to "ready" programs that are not. | Becoming the reason a portfolio is red; a board that treats their queue as a scheduling problem alone. |
| **Security review lead** | Attester | The same: planned demand, and gate requests that are complete. | Late, incomplete requests. |
| **Finance partner** | Reader of the benefit line | A benefit figure labeled for what it is. | An owner estimate presented as a measured saving. |
| **Internal audit** | Consulted | A record of which evidence a status was based on and when. | A status that cannot be reproduced. |

---

## User stories (top 4)

1. **As the head of the AI program office**, I want each program's status computed from its gate evidence, with the reason, so I can defend the monthly view without arguing about colors.
2. **As a model risk review lead**, I want planned demand against supply by quarter, with the programs behind each peak, so I can say which reviews fit and which should wait.
3. **As a program owner**, I want to see exactly which criteria make my program amber or red and which upstream program blocks it, so I can fix the right thing and challenge a status with evidence.
4. **As a sponsor**, I want the benefit at risk shown next to the programs it sits on, labeled as an owner estimate, so I do not fund a number as if it were measured.

---

## KPIs

**North star:** share of in-scope AI programs whose monthly status is computed from gate evidence. Target 🔴 100%.

**Inputs (leading):**
- Programs with a complete set of attestations for their stage (target: every in-scope program).
- Share of criteria within their freshness rule. Prototype: 🟢 14 criteria across 10 programs are past it.
- Evidence feed lag, from attestation to board (🔴 design target: inside one nightly run, not measured).
- Sample audit failure rate on "met" flags (target: trending down). Prototype: 🟢 3 planted false attestations in 30 programs; the board shows none of them as red.

**Outputs (lagging):**
- Statuses that differ from the owner's color. Prototype baseline: 🟢 23 of 30.
- Green reports contradicted by evidence. Prototype: 🟢 16 of 19, of which 4 are red.
- Quarters in which model risk review demand exceeds supply. Prototype: 🟢 4 of 4 as planned, 2 after the pauses (🟡 assuming they hold).
- Stages above their work-in-progress limit. Prototype: 🟢 2 of 5.
- Weeks waiting at the review gates after build and pilot. Prototype: 🟢 12.7, against 3.1 at the gates after idea and discovery.
- Benefit at risk, labeled modeled. Prototype: 🟡 $20.25M of $60.35M.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Shadow | 4w | Compute statuses from whatever evidence exists for a handful of programs. Show nothing to owners; compare against what the review teams say. |
| 1 — Evidence feed | 6w | Wire the gate-evidence feed from the review systems. Agree the freshness rules with each attester. |
| 2 — Advisory board | 6w | Publish the board beside the monthly report. Owners can challenge. Count how often the color and the status differ. |
| 3 — Capacity and pull rule | 6w | Add the capacity grid and pause suggestions to the monthly review. A named approver accepts or declines each. |
| 4 — Audit sample and interlocks | 8w | Start the sample audit of "met" flags. Connect TierGate, ControlMap and ValueLedger as they exist. |

---

## Open questions

1. **Who attests, and in what system?** Today the evidence sits in several places. Recommendation: the review teams attest in their own systems and the feed reads them; owners attest only what no review team owns.
2. **What is the freshness rule per criterion?** The prototype assumes days per criterion (an assumption of the modeled bank, not policy). Recommendation: each attester sets and signs its own.
3. **Does a pause suggestion bind?** Recommendation: advisory for two cycles, then a named approver decides within the cycle and the decision is recorded.
4. **How is a false attestation found?** The board cannot see one (🟢 3 planted; the board shows none of them as red). Recommendation: a sample audit against the documents, with the failure rate published beside the board.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Ingest:** a puller or webhook per source system, writing attestations as immutable events with their evidence date.
- **Status, grid, dependencies, pull rule:** stateless workers on a schedule and on each new attestation.
- **Storage:** Postgres for programs, criteria, attestations, statuses and decisions; object storage with retention for the monthly board snapshot.
- **Console:** read-only for sponsors, with a challenge flow for owners, behind the bank's single sign-on.

**Throughput envelope and latency budget.**
- The prototype computes 30 programs, 286 attestations and 90 stage visits with plain Python loops. Production volumes have not been sized.
- Board run latency: 🔴 design target is one nightly run plus a run on each new attestation. Not built, not timed.

**Failure modes and degradation strategy.**
- A source system is unreachable: the last attestation stands, its age keeps growing, and past the freshness rule the criterion turns stale.
- A criterion has no attestation: it counts as not met, and the status names the missing criterion.
- The dependency register is stale: blocked-by is wrong in the same direction as the register; the register's last-updated date is shown on the board.
- Demand or supply is missing for a team: the grid shows the cell as unknown, never as zero.

**Migration path from current state.**
- If the program office keeps a gate-checklist spreadsheet today: keep it as the first evidence source. The feed reads it until the review systems can be read directly.
- If there is no stage history: start recording stage entry and the review request date first. The wait at the gate and the time in stage need both.

**Org dependencies.**
- Review teams must attest in a system the feed can read. Without that the board is only as good as owner attestations.
- Owners must accept that a status can be computed and challenged, rather than picked.
- The model-risk team must accept the monthly snapshot as part of its record. Without that interlock the audit story is incomplete.

---

*This PRD interlocks with [Project 11 (TierGate)](../11-tiergate-ai-usecase-intake/) and [Project 12 (ValueLedger)](../12-valueledger-ai-benefit-tracking/), and with 16 ControlMap, 19 IncidentLedger and 21 AdoptionPulse (🔴 designed, none built).*
