# PRD: agent-breaker

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an agent-governance review. It is not a record of a PRD landed at a named bank. The faults, the call stream and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | agent-breaker: a standard-library module and command that trips when an agent fails, holds its calls for a person, tests the way back with probes, and writes a hash-chained log that a second run can reproduce |
| **Owner** | The engineer or operations owner of an agent that calls tools in a regulated workflow, with the second-line reader as co-owner of the thresholds and the log |
| **Stage** | Portfolio prototype on synthetic data; a back-test on recorded history, not a live service |
| **Primary user** | The engineer or operations owner of an agent that calls tools in a regulated workflow |
| **Secondary users** | The people who work the human queue; the second-line reader who asks how the agent was stopped; the on-call operator who engages the switch; internal audit |
| **Problem** | An agent that starts failing keeps taking cases. A person sees it late, flips a switch that nothing flips back, and afterwards nobody can show what happened or why the agent was allowed back. In the planted set, 🟢 312 of 7523 calls are harmful and with no stop every one is served (`step_01_no_breaker.py`). |
| **Solution** | Keeps one breaker per agent (a field in the data) with four states: CLOSED, OPEN, HALF_OPEN and FORCED_OPEN. Trips on a critical failure kind, on N failures in a row, or on a failure rate over a time window that holds enough calls, and warns at a fraction of the trip level. Holds the agent's calls for a person, doubles the hold after a failed probe, closes only after several good probes. An operator switch releases into probes, never straight to closed. Writes a hash-chained log and verifies it by replay. |
| **North-star metric** | Share of agent calls in in-scope workflows that pass through a breaker with a verifiable log, and where every trip is read by a named person. Target 🔴 100%. Today in this model: a person on a schedule and a switch. |
| **Measured metrics (synthetic)** | 🟢 12 of 14 must-trip faults tripped, against 9 of 14 for a failures-in-a-row breaker; 142 of 312 harmful calls served, against 168; 267 harmless calls held, against 140; the log verifies and the tamper tests are caught, 3 of 4 from the log alone and 4 of 4 with the head hash (`step_04_with_breaker.py`, `step_02_consecutive_count.py`). |
| **Modeled metrics** | 🟡 Utility (12/14 − 9/14) × 28 = 6 must-trip faults a year stopped that the common breaker would miss, assuming 28 must-trip faults reach the fleet each year. The person-on-a-schedule model in step 1 is also an assumption. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces, and of the people who work the queue, has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling. Every threshold is an assumption and the trip rate was not fitted. Mitigation: back-test on one real tool-call log and report the planted numbers and the real numbers apart. |
| **Risk #2** | Holding calls has a price. 🟢 The breaker sends 267 harmless calls to the human queue against 140 for the common one, 1.57 held per harmful call avoided against 0.97 (`step_04_with_breaker.py`). Mitigation: size the queue from the real fault rate, cap the hold, and review the rate line after the pilot. |
| **Risk #3** | The breaker reads outcomes, not whether an outcome was right. 🟢 33 of the 312 harmful calls were reported ok by the agent, and 0 of 2 silent-error faults tripped (`step_04_with_breaker.py`). Mitigation: say so in the output, and queue a second signal. |
| **Out of scope** | Reading whether an outcome was right; fitting thresholds; a live service, timeouts and cross-process state; signing the log; any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is planted faults or agents, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Failures-in-a-row trip with a human-queue hold** (N failures trip the breaker; calls go to a person) | 25 faults | 3 | 0.9 | 1 | 67.5 | Built in prototype |
| 2 | **Critical-failure trip** (one failure of a critical kind, such as a scope violation, trips at once) | 25 faults | 3 | 0.8 | 1 | 60.0 | Built in prototype |
| 3 | **Probe recovery with backoff** (several good probes close it; a failed probe doubles the hold, capped) | 25 faults | 2 | 0.8 | 2 | 20.0 | Built in prototype |
| 4 | **Failure-rate trip with a warn** (rate over a window that holds enough calls; warn switches nothing) | 25 faults | 2 | 0.6 | 2 | 15.0 | Built in prototype |
| 5 | **Operator switch** (engage and release; a release goes to probes, never to closed) | 5 agents | 3 | 0.8 | 1 | 12.0 | Built in prototype |
| 6 | **Input validation and exit codes** (empty, truncated or wrong-type input exits 2; a trip or a bad log exits 1) | 5 agents | 2 | 0.9 | 1 | 9.0 | Built in prototype |
| 7 | **Fit the trip rate on held-out days** (replace my unfitted 0.5) | 25 faults | 2 | 0.5 | 3 | 8.3 | Sequenced for v0.2 |
| 8 | **Anchor the head hash outside the file by default** (a cut tail is found without a stored hash) | 5 agents | 3 | 0.8 | 2 | 6.0 | Sequenced for v0.2 |
| 9 | **Hash-chained log with replay verify** (every call, transition, warn and control) | 5 agents | 3 | 0.9 | 3 | 4.5 | Built in prototype |
| 10 | **Live loop wrapper** (time out a call that never returns; cross-process state) | 5 agents | 3 | 0.5 | 5 | 1.5 | Sequenced for v0.3 |
| 11 | **Low-volume agent rule** (score the rate from fewer calls for a quiet agent) | 2 faults | 2 | 0.4 | 2 | 0.8 | Sequenced for v0.3 |
| 12 | **Second signal for silent errors** (see a wrong answer reported as ok) | 2 faults | 3 | 0.3 | 8 | 0.2 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from agent-breaker | What they fear |
| --- | --- | --- | --- |
| **Agent owner** | Owner | An agent that stops itself on a clear failure, and a way back that does not need a meeting. | A breaker that trips on noise until the team turns it off. |
| **Human-queue lead** | Receives held calls | A hold that is bounded, a reason on each held call, and a sense of the volume before it arrives. | A flood of harmless calls held after a short blip. |
| **Operations lead** | Accountable for the workflow | Harm stopped sooner, and the price of the stop stated in held calls. | Paying for a breaker that holds more than it saves. |
| **Second-line reader** | Reviews how an agent was stopped | A log that shows which rule fired on which evidence, and that a second run can reproduce. | A story told after the fact that the log cannot support. |
| **On-call operator** | Engages and releases the switch | A switch that engages at once and releases into probes, with a reason recorded. | A release that sends the agent straight back to work. |
| **Security / CISO** | Approver | No vendor key in the path, nothing leaving the boundary, strings from input kept out of logs. | A control that can be switched off silently or a log that can be rewritten. |
| **Internal audit** | Reader | A path from a trip to the calls, the policy and the tool version it used. | Thresholds changed between two runs with no record. |

---

## User stories (top 4)

1. **As the owner of an agent**, I want a scope violation to trip the breaker at once and 5 failures in a row to trip it within minutes, so a failing agent stops taking cases before a person has read a dashboard.
2. **As the human-queue lead**, I want each held call to say why the breaker is open and when it will probe, so I can plan the work and tell the owner what is waiting.
3. **As an on-call operator**, I want to engage the switch and release it into probes with my name and reason recorded, so the agent never goes straight back to work.
4. **As the second-line reader**, I want a log I can replay through a fresh breaker, so I can check that the trips, the holds and the closes are what the rules say they should be.

---

## KPIs

**North star:** share of agent calls in in-scope workflows that pass through a breaker with a verifiable log, and where every trip is read by a named person. Target 🔴 100%.

**Inputs (leading):**
- Agents with an events export that carries outcome and failure kind (the prototype has 🟢 5 agents and 7523 calls, from `data/README.md`).
- Failure kinds that must trip at once, agreed with the owner (prototype: one, a scope violation).
- Thresholds with a named owner and a recorded source (prototype: every value an assumption except two fractions).
- Head hashes stored outside the log file (target: every run).

**Outputs (lagging):** prototype baselines from the planted set.
- Must-trip faults tripped. 🟢 12 of 14, against 9 of 14 for a failures-in-a-row breaker (`step_04_with_breaker.py`, `step_02_consecutive_count.py`).
- Median minutes from fault start to trip. 🟢 13, against 18 for the common breaker (`step_04_with_breaker.py`).
- Harmful calls served. 🟢 142 of 312, against 168 for the common breaker and 312 with no stop (`step_04_with_breaker.py`).
- Harmless calls held. 🟢 267, against 140 (`step_04_with_breaker.py`).
- Must-not-trip faults tripped. 🟢 2 of 7: a run of 5 or 6 failures looks like an outage to a count (`step_04_with_breaker.py`).
- Log checks. 🟢 7599 events, chain intact, replay agrees, 0 calls reached the agent while open; 3 of 4 tamper tests caught from the log alone (`step_04_with_breaker.py`).
- Trips overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Back-test | 4w | Replay one agent's recorded tool-call history through the breaker with `--fail-on never`. Print the trips, hold nothing, and compare with what the owner remembers. |
| 1: Calibration | 4w | Fit the trip rate and the hold on held-out days from the real log. Agree the failure kinds that trip at once. |
| 2: Shadow in the loop | 6w | Run the breaker beside the live loop and route nothing. Record what it would have held and read each trip with the owner. |
| 3: Enforced with the queue | 6w | Route held calls to the human queue for one agent. The operator switch is live; releases go to probes. |
| 4: Anchored log and more agents | 8w | Store the head hash outside the file, add the live-loop wrapper and test the interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Where should the trip rate be?** I set 0.5 before looking at the stream. At 0.3 the same run serves 123 harmful calls and holds 202 harmless ones, better on both counts, but moving it now would be tuning to my own data. Recommendation: run 0.5 and 0.3 side by side in the back-test on a real log and fit on held-out days.
2. **How many held calls can the queue absorb?** The breaker holds 267 harmless calls over three days against 140 for the common one. Recommendation: size the queue and the hold cap from the real fault rate, and start with the 30 minute hold.
3. **Should a long run of failures trip?** 2 of 7 must-not-trip faults tripped, the two that fail 5 or 6 times in a row, and a count cannot tell them from an outage. Recommendation: accept it in the pilot and add the failure cause to the evidence so a reviewer can tell.
4. **Who may engage and release the switch?** Recommendation: any on-call operator may engage; a release needs the agent owner and a second person, and always goes to probes.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One breaker per agent, one log.** The module routes a call and records the outcome. Production adds a live-loop wrapper, a human-queue connector, shared state and log storage, all designed and none built.
- **Never silent.** An empty, truncated or wrong-type input exits 2 and is never read as "no failures". A log that does not verify exits 1.
- **Strings from input are data.** Agent names, case ids, failure kinds and operator reasons stay on one line each in the JSON log and are escaped on the terminal, so a hostile value cannot forge a line.
- **Changes to a threshold are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the tripped count shows in the diff.

**What is next.** Back-test on one real tool-call log the owner is allowed to share; add a second signal that can see a wrong answer reported as ok; anchor the head hash outside the file by default.

**What would have to be true before a pilot.**
- The export records each call's outcome and a failure kind for the failures that must trip at once.
- A named person owns the thresholds and the switch, and a team will work the human queue.
- One real history can be shared, so the rate line and the hold are set against real traffic and not mine.
- The head hash of each log is stored somewhere the log's writer cannot edit.
- The team agrees what happens to a held call: who reads it, how soon, and what the agent is told.

---

*This PRD names [25 KillSwitch](../25-killswitch-ai-fallback-drills/), [27 AgentKit](../27-agentkit-reference-agent-and-playbook/), [08 OversightOps](../08-oversightops-hitl-workflow/) and [05 AgentWatch](../05-agentwatch-agent-observability/) as designed interlocks (🔴 designed, none built). It copies two fractions from 25 and reads no file from any of them.*
