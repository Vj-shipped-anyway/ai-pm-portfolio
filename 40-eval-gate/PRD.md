# PRD: Eval Gate

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a release-governance review. It is not a record of a PRD landed at a named bank. The rules, the planted deploy set and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Eval Gate: a command-line gate, with a staged GitHub Action, that reads a probe file and a results file and prints ALLOW, REVIEW or BLOCK for a model deploy |
| **Owner** | The engineer who owns the deploy pipeline for a model-backed feature, with a second-line reviewer as co-owner of the pin and the thresholds |
| **Stage** | Portfolio prototype on synthetic data; the Action is staged and unpublished |
| **Primary user** | The engineer who owns a deploy pipeline for a model-backed feature |
| **Secondary users** | The reviewer who signs off on moving to a new snapshot; the evaluation owner who runs the probe set; internal audit |
| **Problem** | A team calls a hosted model through a name. The vendor can change the snapshot behind it, and the pass rate on the team's probe set may not move enough to notice, or may move on a few high-severity probes while the average hides it. Nothing in the deploy pipeline compares which snapshot answered with which one the team decided to use. In the planted set, 🟢 a pipeline with no check stops 0 of 64 deploys. |
| **Solution** | Reads a probe file (severity and baseline per probe) and a results file (passes, trials and the snapshot id each response reported). Blocks when any probe was served by an id other than the pin, or when a probe has no result. Blocks or sends to review when the mean pass rate falls under the baseline, and blocks when a high-severity probe collapses. Prints ALLOW, REVIEW or BLOCK, exits non-zero at a chosen level, and writes GitHub annotations on request. |
| **North-star metric** | Share of production deploys of in-scope model-backed features that pass through the gate with a recorded decision and a pin that equals the served id. Target 🔴 100%. Today in this model: nothing checks the served id. |
| **Measured metrics (synthetic)** | 🟢 25 of 25 should-block deploys stopped; 0 of 31 fine deploys blocked and 1 of 31 sent to review; 5 of 8 should-review deploys flagged; the decision matches the planted truth on 59 of 64 (`step_04_with_gate.py`). |
| **Modeled metrics** | 🟡 Utility (25/25 − 13/25) × 10 = 4.8 should-block deploys a year stopped that a 0.90 pass-rate floor would pass, assuming 10 should-block deploys reach the gate each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real harness export and report the planted numbers and the real numbers apart. |
| **Risk #2** | The gate trusts the snapshot id the harness records. A harness that copies the id it asked for turns rule one into a comparison of the pin with the pin. Mitigation: a harness contract test that fails when `served_model` is set from the request; the Action README says the same. |
| **Risk #3** | The thresholds are assumptions and ten trials per probe leave noise on the mean. 🟢 The worst clean run sat 3.3 points under its baseline and 1 of 31 fine runs went to review (`step_03_deficiencies_exposed.py`, `step_04_with_gate.py`). Mitigation: calibrate the lines on clean runs from the real harness; REVIEW does not fail the step unless the team asks. |
| **Out of scope** | Running the probes; judging answers; production monitoring; refreshing baselines; any model call; hosting. A Marketplace listing is a later, separate step. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is deploys or probes, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Snapshot pin check** (any probe served by an id other than the pin: BLOCK) | 64 deploys | 3 | 0.9 | 1 | 172.8 | Built in prototype |
| 2 | **Input validation** (empty, truncated, wrong-type or duplicate input exits 2, never a traceback) | 64 deploys | 2 | 0.9 | 1 | 115.2 | Built in prototype |
| 3 | **Coverage rule** (a probe with no result: BLOCK if high severity, else REVIEW) | 64 deploys | 2 | 0.8 | 1 | 102.4 | Built in prototype |
| 4 | **Pass-rate drop rule** (REVIEW above 3 points, BLOCK above 5) | 64 deploys | 2 | 0.7 | 1 | 89.6 | Built in prototype |
| 5 | **CI output** (text and GitHub annotations, `--fail-on` levels, escaped strings) | 64 deploys | 2 | 0.9 | 2 | 57.6 | Built in prototype |
| 6 | **Publish the Action from its own repository** | 64 deploys | 2 | 0.6 | 2 | 38.4 | Sequenced for v0.2 (staged in `action/`, not published) |
| 7 | **Pin change workflow** (pull request, a different approver, the vendor notice linked) | 64 deploys | 3 | 0.6 | 3 | 38.4 | Sequenced for v0.2 |
| 8 | **High-severity probe collapse rule** (50 points or more under baseline: BLOCK) | 12 probes | 3 | 0.7 | 1 | 25.2 | Built in prototype |
| 9 | **Decision ledger** (pin, thresholds, file hashes, findings) | 64 deploys | 2 | 0.7 | 4 | 22.4 | Sequenced for v0.2 |
| 10 | **Noise-aware drop test** (a bound from trials per probe instead of a fixed point line) | 64 deploys | 2 | 0.4 | 5 | 10.2 | Sequenced for v0.3 |
| 11 | **Per-slice drop rule** (a slice can fall while the mean holds) | 30 probes | 2 | 0.5 | 3 | 10.0 | Sequenced for v0.3 |
| 12 | **Baseline refresh workflow** | 30 probes | 2 | 0.5 | 4 | 7.5 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Eval Gate | What they fear |
| --- | --- | --- | --- |
| **Deploy pipeline owner** | Owner | A step that fails with a reason a person can act on, and a non-zero exit only when something is wrong. | A gate that blocks good releases on noise and gets switched off. |
| **Second-line reviewer** | Approver of pin and threshold changes | A record of which snapshot was meant, which one answered, and who moved the pin. | A pin moved without the vendor's notice read, so rule one becomes a formality. |
| **Feature owner** | Consulted | A decision early, and REVIEW instead of BLOCK when the cause is noise. | A surprise BLOCK late in a release. |
| **Evaluation owner** | Owns the probe set and the harness | The gate reads the harness export as it is, with no change to the harness shape. | A gate that quietly redefines the probe set or the baselines. |
| **Vendor manager** | Informed | Snapshot changes matched to vendor notices and to pin moves. | Learning of a snapshot change from the gate before the vendor's notice. |
| **Security / CISO** | Approver | No vendor key in the gate's path, nothing leaving the boundary, strings from input kept out of logs. | Another tool in the pipeline holding credentials. |
| **Internal audit** | Reader | A path from a decision to the exact inputs, pin and thresholds it used. | Thresholds changed silently between two runs. |

---

## User stories (top 4)

1. **As the deploy pipeline owner**, I want the pipeline to fail when a probe was answered by a snapshot other than the pin, so a vendor-side change does not ship because the average held.
2. **As a reviewer who signs off on a new snapshot**, I want each finding to say what it saw and what to read next, so I can decide to move the pin or hold without a meeting.
3. **As an evaluation owner**, I want a high-severity probe that collapsed to block the deploy even when the mean barely moved, so a few important failures are not averaged away.
4. **As internal audit**, I want each decision tied to the pin, the thresholds and the input files it used, so I can reproduce it later.

---

## KPIs

**North star:** share of production deploys of in-scope model-backed features that pass through the gate with a recorded decision and a pin that equals the served id. Target 🔴 100%.

**Inputs (leading):**
- Probes with a severity and a baseline recorded (the prototype set has 🟢 30 probes: 12 high, 8 medium and 10 low severity, from `data/README.md`).
- Harnesses that write `served_model` from the response and not from the request (target: every harness).
- Trials per probe (prototype: 🟢 10 trials per probe; baselines from 60 earlier trials per probe).
- Pins with a named approver and a linked vendor notice (target: every pin).

**Outputs (lagging):** prototype baselines from the planted set.
- Should-block deploys stopped. 🟢 25 of 25 with the gate, against 0 of 64 deploys stopped with no check (`step_04_with_gate.py`, `step_01_no_gate.py`).
- Fine deploys blocked. 🟢 0 of 31; 1 of 31 sent to review (`step_04_with_gate.py`).
- Should-review deploys flagged. 🟢 5 of 8 (`step_04_with_gate.py`).
- Decision matches the planted truth. 🟢 59 of 64 (`step_04_with_gate.py`).
- Known miss. 🟢 3 subtle drifts pass (`step_04_with_gate.py`).
- BLOCKs overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the gate on one harness with `--fail-on never`. Print the decision, fail nothing, and compare with what the team did. |
| 1: Calibration | 4w | Read the clean runs. Set the 3 and 5 point lines and the collapse line against the harness's own noise. Fix the harness where it copies the requested id. |
| 2: Pin and coverage enforced | 4w | Fail the step on `snapshot_changed` and `unscored_probes`. Pin changes go through a pull request with a different approver. |
| 3: Drop and collapse enforced | 6w | Fail the step on BLOCK from all four rules. REVIEW stays advisory. Publish the Action from its own repository. |
| 4: Ledger and per-slice rule | 8w | Write a decision record per run. Add the per-slice drop rule and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should an unannounced id change block when the scores do not move?** In the prototype it does; that is my policy, not a measurement of harm. Recommendation: keep BLOCK until a person has read the vendor's notice, and revisit after the pilot shows how often an id rotates with no change in behavior.
2. **Where should the thresholds come from?** The 3 and 5 point lines and the 0.90 floor are taken from project 04 as assumptions. Recommendation: start there, then set them against the clean runs of the real harness; the worst clean run in the planted set sat 3.3 points under baseline.
3. **What counts as the same snapshot id?** The match is an exact string, so a vendor that reports one model under two spellings would raise a false BLOCK. Recommendation: keep the exact match and add a reviewed alias list to the pin config, so two spellings are a recorded decision.
4. **Who may move the pin?** Recommendation: a person other than the author of the deploy, with the vendor's notice linked, recorded in the pin config history.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the pipeline.** The gate is stateless: it reads two files and a pin and returns a decision. Production adds a reviewed pin config, a decision ledger and telemetry, all designed and none built.
- **Never silent.** A missing, empty or malformed input exits 2 and fails the step, even with `--fail-on never`. A probe with no result is a finding.
- **Strings from input are data.** Annotations and text output escape control characters, so a hostile snapshot id cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the stopped count shows in the diff.

**What is next.** Run it against one real harness whose owner can share the output; add a per-slice drop rule; publish the Action from its own repository.

**What would have to be true before a pilot.**
- The harness writes `served_model` from the response itself.
- The probe set carries a severity and a baseline measured on the pinned snapshot.
- A named person owns the pin and will read the vendor's notice before moving it.
- One real export can be shared, so the thresholds are set against real noise and not mine.
- The team agrees which level fails the step.

---

*This PRD names [04 EvalForge](../04-evalforge-llm-eval-platform/), [13 SwapBrief](../13-swapbrief-model-migration/), [05 AgentWatch](../05-agentwatch-agent-observability/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The 3 and 5 point lines are copied from 04 as constants, not read from its files.*
