# PRD · KillSwitch — Fallback and Degradation Drills for an AI Decision Service

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for an operational-resilience and model-risk read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an operational-resilience review in the seat. It is not a record of a PRD landed at a named bank. The tier-and-recovery design, the drill scorecard, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. RICE scores and rollout durations below are planning estimates (🔴), not measurements. The fallback rules path is a stub with generator-set quality numbers, and no model is used anywhere in this repo. Thresholds are set on days 1-60 and scored on days 61-90; both are reported.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | KillSwitch — fallback and degradation drills for an AI decision service |
| **Owner** | Service owner for the AI decision service (line-1), with the operational-resilience lead as co-owner of the trigger policy |
| **Stage** | Portfolio prototype; operational-resilience and model-risk read |
| **Primary user** | The service owner, who answers for what happens when the model path degrades |
| **Secondary users** | Operational-resilience lead; on-call engineer; owner of the rules engine; model risk reviewer; customer operations |
| **Problem** | The service has a fallback path (a simple rules engine) and the plan is "we will switch it off manually." Nobody has defined the trigger, drilled the switch, measured how long recovery takes, or asked whether every segment must fall back when one is hurt. In the synthetic data, 🟢 the manual process switches before the event ends for 2 of 12 events and 🟢 4 of 10 drills fail. |
| **Solution** | A control between a degraded signal and a customer decision: four signals per segment and hour scored against the segment's own normal, a warn tier and a trip tier, a per-segment switch to the rules path, hysteresis and a cool-off, a recovery timeline, and a drill scorecard. |
| **North-star metric** | Share of degradation events in which only the affected segments are on the safe path within a defined time. Target 🔴 set in the first calibration phase. Prototype: 🟢 4 of 5 on the held-out days, 9 of 12 overall; the misses are the silent errors. |
| **Measured metrics (synthetic)** | 🟢 Median 2.5 hours to a trip on the held-out days (design floor 2 hours); 🟢 0 of 17 returns re-tripped within 6 hours; 🟢 0 healthy decisions dragged along; 🟢 223 bad decisions per event against 255 for the tuned single threshold on days 61-90. |
| **Modeled metrics** | 🟡 298 bad decisions per event for the manual plan, resting on a notice level of 12 complaints in 3 hours and a 4-hour decision delay. 🟡 Utility (255 − 223) × 4 = 128 bad decisions avoided per quarter, assuming 4 events a quarter. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on metric volume, shadow scoring and the rules engine, and has not been sized. |
| **Risk #1** | The rules path is worse than a mildly degraded model, so a trip makes things worse. Mitigation: a severity-aware trip is on the backlog; until then the rollout keeps the trip advisory for the segment with the widest quality gap (new to bank). |
| **Risk #2** | The fallback fails when it is needed. 🟢 4 of 10 drills failed in the log, 3 of those on a stale rules version. Mitigation: the scorecard blocks an automatic trip for a segment whose last drill failed and pages instead. |
| **Risk #3** | A silent error moves no metric. 🟢 3 of 3 were missed. Mitigation: a golden-set canary or an outcome backtest, designed here and not built; until then this product must not be described as covering silent degradation. |
| **Out of scope** | Detecting drift and agent failures (DriftSentinel 02, AgentWatch 05); the human fallback queue (OversightOps 08); the incident record (IncidentLedger 19); what the rules path is permitted to do (ScopeKeeper 23); the model itself. |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is segments or drill scenarios, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Per-segment scorer and baselines** (four signals, 3-hour window, volume guard) | 4 segments | 3 | 0.9 | 3 | 3.6 | Built in prototype; v0.1 |
| 2 | **Tier state machine** (warn, trip, hysteresis, cool-off) | 4 segments | 3 | 0.9 | 3 | 3.6 | Built in prototype; v0.1 |
| 3 | **Drill scorecard** (worked, fast enough, fresh rules version) | 7 scenarios | 2 | 0.9 | 2 | 6.3 | Built in prototype; v0.1 |
| 4 | **Segment flag and router integration** (the switch itself) | 4 segments | 3 | 0.7 | 6 | 1.4 | Sequenced for v0.1 |
| 5 | **Rules registry** with an owner, a version and a test suite | 4 segments | 3 | 0.8 | 5 | 1.9 | Sequenced for v0.1 |
| 6 | **Recovery timeline and return criteria** | 4 segments | 2 | 0.8 | 2 | 3.2 | Built in prototype; v0.2 |
| 7 | **Complaints and override feeds** into the scorer | 4 segments | 2 | 0.7 | 3 | 1.9 | Sequenced for v0.2 |
| 8 | **Shadow scoring** of the model path while a segment is on the rules path | 4 segments | 3 | 0.6 | 5 | 1.4 | Sequenced for v0.2 |
| 9 | **Manual override** with a two-person rule for the return | 4 segments | 2 | 0.8 | 2 | 3.2 | Sequenced for v0.2 |
| 10 | **Incident hook** (a trip opens an incident with the timeline) | 4 segments | 2 | 0.7 | 2 | 2.8 | Sequenced for v0.3 |
| 11 | **Hour-of-day baselines** | 4 segments | 2 | 0.7 | 3 | 1.9 | Sequenced for v0.3 |
| 12 | **Faster return rule** for loud, short events | 4 segments | 2 | 0.6 | 3 | 1.6 | Queued |
| 13 | **Severity-aware trip** (trip only when the model is expected to be worse than the rules path) | 4 segments | 3 | 0.5 | 5 | 1.2 | Queued |
| 14 | **Golden-set canary** for silent errors | 4 segments | 3 | 0.5 | 6 | 1.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from KillSwitch | What they fear |
| --- | --- | --- | --- |
| **Service owner** (line-1) | Owner | A defined trigger, a switch that works, and a way back, so a bad day is a procedure and not a judgment call at 3 a.m. | A trip on noise that moves good customers to a weaker path; a switch nobody has tried. |
| **Operational-resilience lead** | Co-owner of the policy | Evidence that recovery is drilled and scored, and that tolerances are written down. | A drill log that says "passed" while the rules version is stale. |
| **On-call engineer** | Consumer of warns and trips | One timeline per event: what tripped, when, what came back and why. | A second alert stream that duplicates monitoring; a controller that flaps. |
| **Rules-engine owner** | Dependency | A named owner and a refresh cadence for the fallback, with a test suite to run before it is trusted. | Being the fallback of record with no budget to keep it current. |
| **Model risk reviewer** (line-2) | Auditor | A record of which segment was on which path, why, and who approved the return. | A heuristic presented as a guarantee; a threshold nobody can explain. |
| **Customer operations** | Consulted | To know why a segment's decisions changed on a given day. | Finding out from complaints. |
| **Security / CISO** | Approver | A controller that can move traffic is a privileged system: least privilege, two-person return, full audit. | A single account that can switch the whole service. |
| **Segment product owners** | Consulted | Their segment is not dragged into someone else's incident. | An all-or-nothing switch that costs their customers for another segment's problem. |

---

## User stories (top 4)

1. **As a service owner**, I want each customer segment tripped on its own signals, so a regression in a small segment is handled without moving every other segment to a weaker path.
2. **As an operational-resilience lead**, I want every fallback scenario drilled on a fresh rules version and scored on three criteria, so "we have a fallback" is a statement I can show evidence for.
3. **As an on-call engineer**, I want a trip to come with a timeline and a return rule, so I am not deciding at 3 a.m. whether it is safe to switch back.
4. **As a model risk reviewer**, I want the thresholds, the fit period and the held-out results written down, so the ongoing-monitoring story is documented per event and not only at attestation time. SR 26-2 and the NIST AI RMF 'Manage' function are the design basis here, as analogy, not a claim of coverage.

---

## KPIs

**North star:** share of degradation events in which only the affected segments are on the safe path within a defined time. Target 🔴 set after the shadow phase.

**Inputs (leading):**
- Scenarios whose last drill passed all three scorecard criteria and is recent (target: every in-scope scenario). Prototype: 🟢 0 of 7.
- Rules-version age at the time of each drill (target: under the policy limit of 30 days). Prototype: 🟢 4 of 10 drills ran on a stale version.
- Segments with a scored baseline and a volume guard (target: every in-scope segment).

**Outputs (lagging):**
- Bad decisions per degradation event. Prototype baseline on days 61-90: 🟢 255 with the tuned single threshold, 223 with KillSwitch.
- Trip delay, hours from the start of an event to the first hour on the rules path. Prototype: 🟢 median 2.5 on days 61-90.
- False trips per quarter (budget 🟡 2 in 60 days, an assumption). Prototype: 🟢 1 on days 1-60 and 1 on days 61-90.
- Returns that re-tripped within 6 hours. Prototype: 🟢 0 of 17.
- Hours on the rules path after an event ends (the price of a careful return). Prototype: 🟢 median 14.
- Bad decisions in events nothing detected (the known-limit class). Prototype: 🟢 340 across 3 silent errors.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Shadow | 4w | Scorer and baselines on every segment; no warns shown, no flag. Compare scores with the incident history and with the complaints that did arrive. |
| 1 — Advisory | 4w | Warns go to the on-call person and the service owner. No automatic switch. Count the warns that were not real. |
| 2 — Trip for one segment | 6w | Automatic trip for one segment whose rules path passed its last drill and whose quality gap is small. Two-person return. |
| 3 — All segments and a drill cadence | 6w | Per-segment trip everywhere the scorecard is green; scheduled drills with the scorecard on the operational-resilience dashboard. |
| 4 — Interlocks | 8w | Drift and agent signals in, human queue and incident record out, silent-error canary. |

---

## Open questions

1. **Trip authority.** Who may let the controller move a segment without a person? Recommendation: only where the rules path passed its last drill and the policy marks the segment as eligible; otherwise warn and page.
2. **When is the rules path worse than the model?** In the synthetic data a mild drift in the affluent segment barely pays for a trip: 🟢 210 bad decisions with KillSwitch against 212 if nothing is done, after 85 hours on the rules path. Recommendation: a severity-aware trip, measured against the next incident history.
3. **How careful should the way back be?** The clear rule keeps a segment on the rules path a median 14 hours after an event ends, and on the 3 loud events the single threshold also caught it served fewer bad decisions (678 against 1,219). Recommendation: keep the careful return for drift and regression, test a faster one for outages and tool failures.
4. **What does the rules path do with a case it cannot decide?** Recommendation: route it to the human queue (OversightOps 08), designed and not built.
5. **Silent errors.** Nothing here sees them. Recommendation: a golden-set canary scored hourly, and an outcome backtest, measured against the next incident history.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Collector and scorer:** a streaming job reading per-segment metrics and the complaints feed; baselines per segment, computed from a healthy period a person approves.
- **Controller:** a small service that owns the per-segment state machine and publishes the desired path to a flag service, with every transition written with its reason.
- **Router:** the decision service reads the per-segment flag from a local cache and holds its last known state if the flag service is unreachable.
- **Rules registry and drill service:** versioned rules with an owner and a test suite; a drill scheduler and the scorecard.
- **Storage:** Postgres for state, transitions, policy versions and drill results; object storage for evidence bundles.

**Throughput envelope and latency budget.**
- The prototype scores 8,640 hourly rows with a plain Python loop in seconds. Production metric volume has not been sized.
- Trip latency: 🔴 the design is a flag change honored by every decision node within one cache refresh. Not built, not timed. In the prototype the floor is 2 hours because metrics are hourly.

**Failure modes and degradation strategy.**
- Signal feed down: segments hold their current state, no automatic return, page the on-call person.
- Flag service unreachable: decision nodes hold the last known path for each segment.
- Rules version stale or last drill failed: no automatic trip for that segment; warn and page.
- Controller down: segments hold; a person can still move a segment by hand.
- Window too thin to score a rate: the rate signals are skipped and latency and drift still count.

**Migration path from current state.**
- If there is a runbook that says "switch it off": keep it as the manual override. KillSwitch is what runs before anyone opens it.
- If there is an alert on the overall error rate: keep it as one more signal. It is a useful tripwire and, in this data, it is the right tool for loud, short events.

**Org dependencies.**
- Someone must own the rules engine, with a refresh cadence. Without that the fallback is a stale document.
- The decision service must honor a per-segment flag. Without that the controller can only advise.
- The model-risk team must accept the transition log as part of its record.

---

*This PRD interlocks with [Project 02 (DriftSentinel)](../02-driftsentinel-model-drift-monitoring/), [Project 05 (AgentWatch)](../05-agentwatch-agent-observability/), [Project 08 (OversightOps)](../08-oversightops-hitl-workflow/) and [Project 15 (SchemaWatch)](../15-schemawatch-tool-schema-drift/), plus [Project 19 (IncidentLedger)](../19-incidentledger-ai-incident-response/) and [Project 23 (ScopeKeeper)](../23-scopekeeper-agent-permission-review/). All interlocks are 🔴 designed, none built.*
