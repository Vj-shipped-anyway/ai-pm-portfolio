# PRD: runbook-dryrun

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an operational-resilience review. It is not a record of a PRD landed at a named bank. The policy values, the drill cases and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | runbook-dryrun: a command-line tool that reads an incident runbook in a small YAML subset, walks it against a state snapshot without running anything, and holds at each approval gate until a valid record is on file. It prints READY, WAITING or BLOCKED |
| **Owner** | The owner of an AI-operations runbook (model rollback, fallback routing, tool switch-off), with the approver role as co-owner of the gates |
| **Stage** | Portfolio prototype on synthetic data; nothing is executed by the tool |
| **Primary user** | The owner of an AI-operations runbook |
| **Secondary users** | The person on call who follows it; the person asked to approve one of its steps; the second-line reviewer; internal audit |
| **Problem** | An incident runbook is usually a page. Its first real test is the incident, when the person following it finds an unfilled parameter, a precondition that is not true, or an approval that covers a different target. A dry-run flag that prints the commands does not help with any of those. In the planted set, 🟢 53 of 94 cases go wrong only while someone follows the runbook, and a printed dry run notices 0 of 16 invalid approvals (`step_01_prose_runbook.py`, `step_02_echo_dry_run.py`). |
| **Solution** | Reads a runbook in a small YAML subset: steps with an effect, a risk, a command, preconditions, declared state changes, an optional approval gate and a rollback. Lints the runbook alone, walks the steps against a copy of a state snapshot applying the declared changes, and holds at each gate until a record exists from a different person, in the right role, for the digest of the exact rendered command, inside its time limit. Prints READY, WAITING or BLOCKED and exits non-zero at a chosen level, with GitHub annotations on request. Nothing is executed. |
| **North-star metric** | Share of high-risk write steps in in-scope runbooks that have a dry-run verdict and a digest-bound approval on file before they run. Target 🔴 100%. Today in this model: nothing checks. |
| **Measured metrics (synthetic)** | 🟢 46 of 53 blocked cases caught; 8 of 8 waiting cases held at the gate; the missing rollback warned in 4 of 4; 14 of 17 hard negatives pass; the verdict matches the planted truth in 84 of 94 (`step_04_with_dryrun.py`). |
| **Modeled metrics** | 🟡 Utility (46/53 − 5/53) × 12 = 9.3 defective runbook runs a year caught before anyone follows them that a printed dry run would miss, assuming 12 such runs reach the tool each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real runbook the owner can share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The tool trusts what a step declares about its effect and what the snapshot says about the world. 🟢 7 of 53 blocked cases pass as READY: mislabeled_effect 4 and world_drift 3 (`step_04_with_dryrun.py`). Mitigation: a reviewer signs the effect and risk of each write at runbook review, and a snapshot carries its age with a limit. |
| **Risk #3** | A strict type check blocks a clean case whose snapshot holds a number as text. 🟢 3 of 41 clean or waiting cases are blocked wrongly (`step_04_with_dryrun.py`). Mitigation: fix the collector to emit numbers; keep the tool strict, so it never guesses. |
| **Out of scope** | Running commands; branches, loops and parallel steps; full YAML; a directory lookup for roles; reading a command to infer its effect; any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is cases or runs, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Lint of the runbook alone** (duplicate id, undefined parameter, undeclared state key, ungated high-risk write, missing rollback as a warning) | 94 cases | 2 | 0.9 | 1 | 169.2 | Built in prototype |
| 2 | **Approval gate bound to the exact command** (different person, role, digest, time limit) | 94 cases | 3 | 0.9 | 2 | 126.9 | Built in prototype |
| 3 | **State walk against a snapshot copy** (preconditions, declared changes, stop at the first failure) | 94 cases | 3 | 0.8 | 2 | 112.8 | Built in prototype |
| 4 | **Strict YAML subset and input validation** (anchors, tabs, oversize and malformed files exit 2, never a traceback) | 94 cases | 2 | 0.9 | 2 | 84.6 | Built in prototype |
| 5 | **CI output** (text and GitHub annotations, `--fail-on` levels, escaped strings) | 94 cases | 2 | 0.9 | 2 | 84.6 | Built in prototype |
| 6 | **Snapshot age limit** (the snapshot carries its read time and a stale one blocks) | 94 cases | 3 | 0.6 | 2 | 84.6 | Sequenced for v0.2 |
| 7 | **Directory-backed roles** (a gate names a group, not a role string) | 94 cases | 3 | 0.5 | 3 | 47.0 | Sequenced for v0.2 |
| 8 | **Read-only snapshot collector** that emits typed values | 94 cases | 3 | 0.6 | 4 | 42.3 | Sequenced for v0.2 |
| 9 | **Dry-run record** (runbook version, snapshot hash, verdict, findings) | 94 cases | 2 | 0.7 | 4 | 32.9 | Sequenced for v0.2 |
| 10 | **Approval capture** in the incident tool, writing the digest it was shown | 94 cases | 3 | 0.5 | 5 | 28.2 | Queued |
| 11 | **Branches and parallel steps** | 94 cases | 2 | 0.3 | 8 | 7.1 | Queued |
| 12 | **Effect attestation** (a second person signs the declared effect of each write) | 7 cases | 3 | 0.4 | 3 | 2.8 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from runbook-dryrun | What they fear |
| --- | --- | --- | --- |
| **Runbook owner** | Owner | Defects found before the incident, with a finding that names the step and the rule. | A tool that blocks every runbook until it is rewritten, so nobody runs it. |
| **On-call responder** | Requester | A runbook that has already been walked, and a clear statement of what is waiting on whom. | A BLOCKED verdict in the middle of an incident for a reason that is not theirs to fix. |
| **Incident commander** | Approver | To sign the exact command that will run, once, for this target. | Signing a step whose command changed after they approved it. |
| **Platform / SRE lead** | Owner of the state snapshot | Typed values in the snapshot and a limit on its age. | A dry run read as proof that production is in the state the snapshot shows. |
| **Second-line operational risk reviewer** | Approver of gate and policy changes | A record of which runbook version, snapshot and approvals a verdict used. | A role string accepted without a directory behind it. |
| **Security / CISO** | Approver | Nothing executed by the tool, no credentials in its path, strings from input kept out of logs. | A dry-run tool that quietly gains the right to run commands. |
| **Internal audit** | Reader | A path from a verdict to the exact runbook, snapshot and approval records. | A gate whose time limit or role was changed silently between two runs. |

---

## User stories (top 4)

1. **As a runbook owner**, I want a high-risk write with no approval gate to fail the check, so the first reader of the runbook is a lint rule and not the person on call.
2. **As the person on call**, I want the dry run to stop at the first precondition the snapshot says is false, so I learn it before I have changed anything.
3. **As an incident commander**, I want my approval bound to the exact rendered command, so a rollback approved for scorer-v8 cannot carry over to scorer-v7.
4. **As internal audit**, I want each verdict tied to the runbook, snapshot and approval records it read, so I can reproduce it later.

---

## KPIs

**North star:** share of high-risk write steps in in-scope runbooks that have a dry-run verdict and a digest-bound approval on file before they run. Target 🔴 100%.

**Inputs (leading):**
- Runbooks in the YAML subset with an effect and a risk on every step (the prototype set has 🟢 94 drill cases, `data/README.md`).
- Medium and high writes that name a rollback or say `rollback: none` (target: every one).
- Snapshots with typed values and a recorded age (target: every snapshot).
- Gates whose role resolves in a directory (target: every gate; the prototype takes role names as written).

**Outputs (lagging):** prototype baselines from the planted set.
- Blocked cases caught. 🟢 46 of 53 with the tool, against 5 of 53 problems shown by a printed dry run (`step_04_with_dryrun.py`, `step_02_echo_dry_run.py`).
- Waiting cases held at the gate. 🟢 8 of 8 (`step_04_with_dryrun.py`).
- Clean or waiting cases blocked wrongly. 🟢 3 of 41 (`step_04_with_dryrun.py`).
- Verdict matches the planted truth. 🟢 84 of 94 (`step_04_with_dryrun.py`).
- Known miss. 🟢 7 of 53 pass: mislabeled_effect 4 and world_drift 3 (`step_04_with_dryrun.py`).
- Minutes saved in a real incident: not measured; the planted set has no incident.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Dry-run one runbook with `--fail-on never`. Print the verdict, hold nothing, and compare with what the runbook owner already knew. |
| 1: Calibration | 4w | Fix the findings with the runbook owner. Agree the effect and risk of each write, the approval time limit, and what a snapshot must carry. |
| 2: Lint and state enforced | 4w | Fail the pipeline step on BLOCKED from lint and the state walk. Runbook changes go through a pull request with a different approver. |
| 3: Gates enforced | 6w | Require a digest-bound approval for every high-risk write. Move role names to a directory group. |
| 4: Record and capture | 8w | Write a dry-run record per run and capture approvals in the incident tool. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Who vouches for the effect and risk a step declares?** The tool applies them as written, and 4 of the 7 misses are a write labeled a read. Recommendation: the reviewer signs the declared effect of each write at runbook review, and the effect attestation moves up the backlog if the pilot finds a mislabeled step.
2. **How long should an approval last?** The prototype uses 30 minutes unless a gate sets another limit; that is my policy value. Recommendation: set it per gate against how long the real change takes to start, and keep the limit inclusive, as the prototype does.
3. **How fresh must the snapshot be?** A snapshot that moved after it was read passes today. Recommendation: add an age limit on the snapshot (backlog item 6), and treat a dry run as proof of the runbook, not of production.
4. **Should a number held as text stop the run?** It does today, and 3 of 41 clean or waiting cases are blocked for it. Recommendation: keep the tool strict and fix the collector to emit typed values, so the tool never guesses.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, nothing executed.** The tool reads a runbook, a snapshot and approval records and returns a verdict. Production adds a reviewed runbook repo, a snapshot collector, approval capture and a dry-run record, all designed and none built.
- **Never silent.** A missing, empty, truncated or mistyped input exits 2 and fails the step, even with `--fail-on never`. A gate with no record is WAITING, not READY.
- **Strings from input are data.** Text and annotations escape control characters, so a hostile parameter or approver name cannot forge a line or a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the caught count shows in the diff.

**What is next.** Run it against one real runbook whose owner can share it; add a snapshot age limit; let a gate name a directory group instead of a role string.

**What would have to be true before a pilot.**
- A named owner agrees the effect, risk and rollback of every write in the runbook.
- The snapshot comes from a read-only collector that emits typed values.
- Approvers sign the digest the dry run prints, in a tool that records it.
- The roles named in the gates map to a directory the reviewer trusts.
- The team agrees which verdict fails the step, and that a dry run is not proof of production state.

---

*This PRD names [19 IncidentLedger](../19-incidentledger-ai-incident-response/), [27 AgentKit](../27-agentkit-reference-agent-and-playbook/), [25 KillSwitch](../25-killswitch-ai-fallback-drills/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The approval digest idea comes from 27 and is re-implemented here; no code or file is imported from it.*
