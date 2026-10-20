# PRD · AgentKit — A Reference Agent Build and Delivery Playbook

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a platform-engineering and operational-risk read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to a platform-engineering review in the seat. It is not a record of a PRD landed at a named bank. The kit, the brief handling, the gate-by-gate playbook, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. RICE scores and rollout durations below are planning estimates (🔴), not measurements. The reasoning step is a stub, a deterministic template that stands in for a language model, and no model is used anywhere in this repo. The playbook is a design: nobody has run it on a live program here.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | AgentKit — the reusable pieces behind an agent that takes over a rule-based operations workflow (scoped tools, person gates, an audit trail, a shadow scorecard) and the gate-by-gate playbook that carries it from a build brief to production ownership |
| **Owner** | The AI program lead who answers for agent pilots reaching an owner, with the platform engineering lead as co-owner of the kit |
| **Stage** | Portfolio prototype; platform-engineering and operational-risk read |
| **Primary user** | The engineer who picks up the hand-off pack and has to take it to production |
| **Secondary users** | Program lead; process owner; the people who hold S07 and S09 (analyst, reviewer); security; model risk reviewer; internal audit; the owning team's on-call engineer |
| **Problem** | Agent pilots stall between the idea and production ownership. Each team re-writes tool wrappers, approval logic, logging and test harnesses, ships without a shadow-mode comparison against human outcomes, and hands off without a runbook. In the synthetic data, 🟢 a happy-path script resubmits 515 payments with no approval, fails silently on 52 cases, writes a trace for 18.7% of its decisions and was never compared with the humans (82.9% agreement once measured). |
| **Solution** | A kit read from a build brief: tool registry with scope checked on every call, a step state machine with retries, idempotency keys, two always-person gates and a kill switch, an append-only hash-chained audit log, a shadow harness that scores against recorded human outcomes, a runbook skeleton drafted from the brief, and a playbook with entry criteria, exit criteria and an artifact for each gate. |
| **North-star metric** | Share of agent pilots that reach a named production owner with the full pack: validated brief, scope record, offline tests, shadow scorecard with its known-miss list, rehearsed runbook. Target 🔴 set after the first two real workflows. Prototype: 🟢 one brief taken through the offline and shadow gates; 8 of 9 acceptance criteria pass and the failing one blocks exit. |
| **Measured metrics (synthetic)** | 🟢 242 unit tests pass (`python3 -m unittest discover -s tests`); 🟢 shadow agreement 95.26% on the 548 cases where the kit proposed an outcome; 🟢 0 out-of-scope calls executed, 4 of 4 rogue calls blocked; 🟢 0 resubmissions without a person's approval, 1,164 unapproved attempts blocked; 🟢 audit completeness 1.000 across four runs with the hash chain intact; 🟢 12 malformed records sent back to the human queue with a reason; 14 duplicate deliveries closed once. |
| **Modeled metrics** | 🟡 268.1 hours of recorded human touch time in the 30-day window, from the generator's per-step minutes (the size of the pool, not a saving). 🟡 4.9 minutes per case with the kit's routes against 26.8 manual, assuming a reviewer spends only the S09 minutes and escalated and queued cases keep their manual minutes. 🟡 Utility (21.2% − 2.5%) × 1,800 cases a quarter = 336 fewer wrong or unsafe outcomes taken without a person. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on case volume, the approval service, audit storage and any model behind the drafting step, and has not been sized. |
| **Risk #1** | The agent finishes a case on its own and is wrong. 🟢 15 of 134 cases the kit finished on its own differ from the recorded human outcome (11.2%), against a limit of 1%. AC-06 fails and the brief's exit criteria keep the kit in shadow mode. Mitigation: send name mismatches and closed-account returns that carry an advised account to a person; re-run; the re-run is not held-out evidence. |
| **Risk #2** | A wrong proposal reaches a reviewer who approves it. 🟢 6 wrong proposals reach S09 in the shadow run. A real reviewer's catch rate is 🔴 not measured. Mitigation: show the match score and the screening result on the approval screen; sample approvals weekly in limited rollout. |
| **Risk #3** | The playbook is a document nobody follows. 🔴 It has not been run on a live program. Mitigation: each gate has a checkable exit criterion and an artifact; four gates are backed by kit output; the first real workflow is the test of the playbook, not only of the kit. |
| **Out of scope** | Intake and business case (11 TierGate, 12 ValueLedger); permission review (23 ScopeKeeper); agent observability (05 AgentWatch); the fallback trigger, per-segment switch and drills (25 KillSwitch); the model that may one day draft corrections; the brief generator (26 StepScout). |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is workflows per year the pack would serve, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Brief loader and validator** (exact keys, cross-checks, derived config and acceptance tests) | 6 workflows | 3 | 0.9 | 2 | 8.1 | Built in prototype; v0.1 |
| 2 | **Tool registry with scope checked on every call** | 6 workflows | 3 | 0.9 | 2 | 8.1 | Built in prototype; v0.1 |
| 3 | **Orchestrator** (retries, idempotency keys, two person gates, four-eyes, kill switch, fallback) | 6 workflows | 3 | 0.8 | 4 | 3.6 | Built in prototype; v0.1 |
| 4 | **Append-only audit log with a completeness check** | 6 workflows | 3 | 0.9 | 2 | 8.1 | Built in prototype; v0.1 |
| 5 | **Shadow harness and scorecard** | 6 workflows | 3 | 0.8 | 3 | 4.8 | Built in prototype; v0.1 |
| 6 | **Delivery playbook** (eight gates, standards) | 6 workflows | 3 | 0.6 | 2 | 5.4 | Written as a design; v0.1 |
| 7 | **Runbook skeleton and monitoring signals drawn from the brief** | 6 workflows | 2 | 0.7 | 1 | 8.4 | Built in prototype; v0.2 |
| 8 | **Approval service integration** (S07 and S09 in the bank's own work queue) | 6 workflows | 3 | 0.6 | 6 | 1.8 | Sequenced for v0.2 |
| 9 | **System adapters for a first real workflow** | 1 workflow | 3 | 0.5 | 8 | 0.2 | Sequenced for v0.2 |
| 10 | **Audit sink** (immutable store, chain and completeness jobs) | 6 workflows | 3 | 0.7 | 4 | 3.2 | Sequenced for v0.2 |
| 11 | **Limited-rollout controller** (a share of new cases, weekly sample) | 6 workflows | 2 | 0.6 | 4 | 1.8 | Sequenced for v0.3 |
| 12 | **Hold-out tooling** (a later period kept out of any tuning) | 6 workflows | 2 | 0.7 | 2 | 4.2 | Sequenced for v0.3 |
| 13 | **Model-backed drafting behind the stub's interface, with an evaluation gate** | 3 workflows | 2 | 0.4 | 8 | 0.3 | Queued; needs 04 EvalForge |
| 14 | **Brief generator hook** (read StepScout output directly) | 6 workflows | 2 | 0.6 | 2 | 3.6 | Queued; needs 26 StepScout |

---

## Stakeholder map

| Stakeholder | Role | What they want from AgentKit | What they fear |
| --- | --- | --- | --- |
| **Program lead** | Owner | A pilot that ends in a named owner, with evidence at each gate, not a demo | A pilot that works on the slide and has no runbook |
| **Engineer who picks the pack up** | Primary user | A brief that validates, code that matches it, tests that pass, a runbook skeleton | Inheriting an agent nobody can explain, with logs that do not say why it decided |
| **Process owner** | Consulted | To see how the agent disagrees with their people before it touches a case | A rollout that surprises the team |
| **Reviewer (S09) and analyst (S07)** | Gate holders | A correction pack with the match score and the screening result in front of them | Becoming a rubber stamp; being blamed for the agent's wrong proposal |
| **Security / CISO** | Approver | Least privilege per tool, no self-approval, an audit trail that cannot be edited | A write tool reachable by a bug; one identity that can approve its own work |
| **Model risk reviewer** (line-2) | Auditor | The brief, the thresholds, the shadow results and the known misses written down in one place | A stub described as a model, or a threshold nobody can explain |
| **Internal audit** | Auditor | A trace per case: decisions, tool calls, gates, approvals | A log with holes |
| **Operations on-call** | Operator | A kill switch they have rehearsed and a runbook that says what to do | A switch nobody has tried |
| **Works council / privacy** | Consulted | Aggregate-only views of worker data in shadow comparisons; pseudonymous ids | A shadow scorecard that turns into a ranking of individual workers |

---

## User stories (top 4)

1. **As the engineer who picks up the pack**, I want the brief validated before anything runs and the tool scope, the gates and the acceptance tests derived from it, so I build to the same file the reviewers signed.
2. **As a process owner**, I want the agent replayed on our own historical cases in shadow mode, scored against what our people did, with the misses listed, so I know where it will disagree before it touches a live case.
3. **As a security reviewer**, I want every tool call checked against the brief's scope before it runs and every refused call logged, so a bug or a bad instruction cannot reach a system the brief does not name.
4. **As the owning team's on-call engineer**, I want a kill switch I have rehearsed, a trace per case and a runbook with the steps written down, so a bad day is a procedure.

---

## KPIs

**North star:** share of agent pilots that reach a named production owner with the full pack. Target 🔴 set after the first two real workflows.

**Inputs (leading):**
- Briefs that validate on the first load (target: every brief). Prototype: 🟢 the sample brief validates with 0 problems and 0 warnings; the three briefs StepScout (26) wrote validate too, and BB-002 carries an unsupported-step warning (S14) and is refused at run time.
- Acceptance tests measured per brief (target: all). Prototype: 🟢 9 of 9 measured.
- Controls covered by an automated test: scope, gates, idempotency, kill switch, audit, faults. Prototype: 🟢 all six, 242 tests.
- Shadow cases replayed against the brief's stated count. Prototype: 🟢 600 of 600.

**Outputs (lagging):**
- Out-of-scope calls executed (target 0). Prototype: 🟢 0; 4 of 4 rogue calls blocked.
- Resubmissions without a person's approval (target 0). Prototype: 🟢 0.
- Audit completeness (target 1.0). Prototype: 🟢 1.000.
- Agreement of the agent's proposals with the recorded outcome (limit 0.95). Prototype: 🟢 0.9526 on 548 proposals.
- Cases finished on its own that differ from the recorded outcome (limit 1%). Prototype: 🟢 11.2%. Fails.
- Share of cases routed back to the human queue (limit 5%). Prototype: 🟢 2.0%.
- Runbook items rehearsed by someone other than the builder (target all). Prototype: 🔴 0 of 7; a skeleton was drafted and nobody has run it.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Reference build | Done in this repo | The kit, the sample brief, the synthetic data, the playbook as a design |
| 1 — One real workflow, shadow only | 6w | A real brief for one workflow; adapters to read-only systems; shadow scorecard on the team's own history; a named owner |
| 2 — The same workflow in limited rollout | 8w | A share of new cases with S07 and S09 held by people; a weekly sample against the person's outcome |
| 3 — A second workflow | 8w | Tests whether the kit and the playbook are reusable, which is the claim of the whole product |
| 4 — Template and CI | 6w | Briefs from StepScout, scorecard regenerated in CI, hold-out tooling |

---

## Open questions

1. **What does a failing acceptance test do?** In the sample, AC-06 fails. Recommendation: the gate stays shut, the owner and decision are recorded, and the re-run after a rule change is labeled as not held-out.
2. **How good is a reviewer at S09?** The enforcement run uses a scripted double and tests mechanics only. Recommendation: measure the catch rate on a sample in limited rollout before relying on S09 to absorb the kit's wrong proposals.
3. **Should a name mismatch ever be closed by the agent?** In the synthetic data 9 of 54 auto returns on a mismatch were cases a person had resubmitted. Recommendation: route mismatches to S07 until a real history says otherwise.
4. **Where does the rule table live and who owns it?** The closed-account rule ignores a successor account in the advice. Recommendation: the process owner owns the table and a change to it is a brief change.
5. **How are per-worker comparisons governed?** The shadow scorecard joins to recorded outcomes that carry a worker id. Recommendation: pseudonymous ids, aggregate-only views, a works-council read before any real program. 🔴 designed, not built.
6. **When does a model replace the stub?** Recommendation: only behind the same two methods, with an evaluation gate (04 EvalForge) and the same shadow replay; nothing in this repo is a model.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Brief registry:** versioned briefs with an approver per version; the config and the acceptance tests are derived, never hand-edited.
- **Tool gateway:** one choke point that checks scope, approval and idempotency before a call reaches a system.
- **Orchestrator:** a state machine per case; person gates park the case; the kill switch is checked before every step and every call.
- **Approval service:** S07 and S09 in the bank's own work queue; the kit checks who answered.
- **Audit store:** append-only, hash-chained, with completeness and chain checks on a schedule.
- **Shadow job:** replay and scorecard, regenerated when a skill or a threshold changes.

**Throughput envelope and latency budget.**
- The prototype replays 600 cases in a few seconds on a laptop, with every step and every tool call written to the audit log. Production volume has not been sized.
- Latency added by the scope check and the audit write: 🔴 a design budget, not measured here.

**Failure modes and degradation strategy.**
- A tool times out or answers with a malformed payload: retried up to three attempts, then the case goes back to the human queue with the reason.
- The watch-list screen fails: the case never proceeds unscreened; it goes back to the human queue.
- A record is malformed: back to the human queue with a reason, never guessed.
- A brief names a step the kit has no skill for (a StepScout decoy step): it validates with a warning, and building a kit from it is refused with a named error.
- A pack starts mid-workflow, so a step lacks a result an earlier step would have given it: the case goes to the human queue with the reason `prerequisite_missing`.
- A duplicate delivery: closed once, and a write keyed by the exception cannot repeat.
- The kill switch is engaged: no new step, no tool call; open cases go back to the human queue with their trace.
- The audit log fails a completeness or chain check: alert; the owner decides whether to pause.
