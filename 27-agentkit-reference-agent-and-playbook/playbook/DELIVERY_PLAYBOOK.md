# Delivery playbook: from a build brief to production ownership

> 🔴 **Design.** Nobody has run this playbook on a live program in this repo. It is the gate-by-gate path I would try, written so that the engineer who picks the pack up can follow it without me. The kit in `src/agentkit/` is what makes four of the gates checkable on synthetic data; the rest is process, and process is only a design until a team has run it. Where a number appears, it comes from a script in this folder (`step_01` to `step_04`) and the playbook says which.

**Reader.** The engineer (a platform engineer, or a forward-deployed engineer) who is handed a build brief and has to take an agent from that file to something a named team owns. The program lead reads the gate table and the exit criteria.

**What the brief is.** A `build-brief/v1` file: the candidate workflow and its steps, scope, tools with read or write access and allowed actions, human gates, four-eyes rules, a kill switch, an audit rule, acceptance tests, a test plan, rollout stages, hand-off items and a modeled estimate. The shape comes from project 26 StepScout. The sample in `briefs/wire_repair_agent_brief.json` is hand-written; it is not StepScout output.

**What sits outside this playbook.** Intake and the business case are projects 11 TierGate and 12 ValueLedger. Permission review is 23 ScopeKeeper. Agent observability in production is 05 AgentWatch. The full trigger, the per-segment switch and the drills for a fallback are 25 KillSwitch. This playbook says where each plugs in and does not repeat them.

---

## The gates at a glance

| Gate | Name | Owner (role) | Exit artifact | Kit support |
| --- | --- | --- | --- | --- |
| G0 | Intake check | Program lead with the business owner | Intake record, business case reference, validated brief | `load_brief`, `check_brief` |
| G1 | Scope and permissions | Security reviewer with the engineer | Permissions record, tool inventory | Tool scope from the brief; `tests/test_scope.py` |
| G2 | Build | Engineer | Reviewed code, unit test report | Skills, registry, orchestrator, audit log |
| G3 | Offline tests | Engineer, business owner signs the golden cases | Offline test report | `python3 -m unittest discover -s tests`; step 4 enforcement run |
| G4 | Shadow mode | Engineer and the process owner | Shadow scorecard and the known-miss list | `shadow.replay`, `shadow.score`; step 4 |
| G5 | Limited rollout | Process owner, on-call engineer | Weekly rollout report | Same orchestrator in live mode with person gates |
| G6 | Hand-off and runbook | Owning team lead | Signed hand-off record, completed runbook | `handoff.build_runbook`, `monitoring_signals` |
| G7 | Post-launch review | Program lead | Review record and the next brief version | Acceptance tests re-run on live data |

A gate does not open because the calendar says so. It opens when its exit criteria are met and the artifact exists.

---

## G0. Intake check

**Purpose.** Decide whether this workflow is a candidate at all, and write down which steps an agent may do.

**Entry criteria**
- A named workflow, a named business owner, and access to historical cases with the human outcome recorded.
- A claim of benefit that someone has to own (the business case, 12 ValueLedger).

**Work**
- Classify every step: AGENT (rule-based, data-complete), AGENT_HITL (an agent drafts or acts, a person approves), HUMAN_JUDGMENT, HUMAN_CONTROL. The brief's `candidate.steps` lists only steps the agent touches, and any person-held step in the list must carry a gate.
- Confirm the approver roles exist as real roles with real people.
- Decide what the recorded human outcome means. It is the yardstick for G4. If past workers disagreed with each other, G4 has a ceiling nobody should miss.

**Exit criteria**
- The intake record is approved under the intake process (11 TierGate).
- The brief passes `check_brief` with no problems. A brief that tries to drop the S07 or S09 gate, that contains S10 without a four-eyes entry for S09, or that lists a write-like action under a read tool, fails here. S09 may sit outside the pack, with a named person, if the brief says so in a four-eyes entry.
- A warning about an unsupported step (a well-formed step id the kit has no skill for) is a stop for G2: the brief validates but nobody runs that pack until the step has a skill or leaves the pack. The kit enforces this: it refuses to derive a runnable config from such a brief.
- The estimate in the brief is tagged modeled and names its assumption.

**Artifact.** Intake record, business case reference, the validated brief (version 1).

**Watch for.** Task data about individual workers. The recorded outcome in this repo carries a pseudonymous worker id the kit never reads. A real program that compares agent and worker outcomes is making a privacy and works-council decision. The prototype only designs for that (🔴 designed, not built): pseudonymous ids, no keystroke content, aggregate-only views.

---

## G1. Scope and permissions

**Purpose.** Make the brief's tool list true at the system level, not only in the kit.

**Entry criteria**
- G0 exit.

**Work**
- For each tool in the brief, create a credential with the least privilege that does the listed actions. A tool the brief calls `read` gets a read-only credential, so that a bug in the kit cannot write.
- Name every action the kit must not be able to reach. In the sample brief those are editing the original payment, cancelling a payment, reading or changing the whole watch list, and approving a correction.
- Run the permissions review (23 ScopeKeeper) on the tool list.

**Exit criteria**
- The permissions record maps every brief tool to a credential and an owner.
- A written test that each out-of-scope action fails at the system, with the failure recorded.
- `out_of_scope` in the brief matches what the system refuses.

**Artifact.** Permissions record and tool inventory.

**What the kit gives you.** The registry checks every call against the brief's tools before it runs, and refuses a tool that declares more access than the brief allows (`tests/test_scope.py`). That is a second line. It is not a replacement for system-level least privilege: step 3 shows what a script does when the only limit is the script's own good manners.

---

## G2. Build

**Purpose.** Turn the brief into running code that the owning team can read.

**Entry criteria**
- G1 exit; a repository; a code review rota that includes someone who did not write the code.

**Work**
- Replace the simulated environment with adapters to the real systems. The registry, the skills and the orchestrator stay; the adapters change.
- Keep rule steps as rules. Where a drafting step will use a model, put it behind the same two methods the reasoning stub implements (`draft_correction`, `draft_case_note`), and evaluate it before it is allowed near G4 (04 EvalForge). Nothing in this repo is a model.
- Wire S07 and S09 to a real approval service. The kit checks who answered (a person, the gate's role, a different person from the S07 judge, the right correction digest). It does not produce an answer.
- Send the audit log to storage the engineer cannot edit.

**Exit criteria**
- Two reviewers have approved changes to `skills/`, `tools.py` and `orchestrator.py`.
- Every skill has a unit test; every write has an idempotency key and a test that a replay does not repeat it.
- A written list of what is still a stub.

**Artifact.** Reviewed code, unit test report, stub list.

---

## G3. Offline tests

**Purpose.** Show that the controls hold before any real case is touched.

**Entry criteria**
- G2 exit; the brief's `test_plan` (golden cases, fault injections, shadow case count).

**Work**
- Golden cases: the brief says how many. Each has an expected route and outcome, and the business owner signs them.
- Control tests: scope enforcement, gate enforcement (S10 cannot run without an S09 approval), idempotency, kill switch, audit completeness, brief validation (including the briefs StepScout wrote, kept as a snapshot).
- Fault injection: tool timeout, malformed tool output, duplicate delivery, an out-of-scope call, a lost answer after a write, the kill switch engaged mid-case.

**Exit criteria**
- The suite passes from a clean checkout: `python3 -m unittest discover -s tests`.
- The enforcement run reports zero unapproved resubmissions and zero out-of-scope calls that reached a system (`step_04`).
- The golden cases are signed.

**Artifact.** Offline test report.

---

## G4. Shadow mode

**Purpose.** Learn how the agent disagrees with people before it does anything to a real case.

**Entry criteria**
- G3 exit; at least the brief's `shadow_mode_cases` historical cases with the recorded outcome; a period of data the build did not see, if a threshold was tuned.

**Work**
- Replay the cases read-only. Every write is a dry run and both person gates park the case. The recorded human outcome is never an input; it is used afterwards, to score.
- Evaluate every acceptance test in the brief. Report agreement by class, how many cases went auto, to a person and back to the human queue, and the confusion matrix.
- Write the known-miss list: where the agent's proposal looked right by the rules and differed from the person, and anything it finished on its own that was wrong.

**Exit criteria**
- Every acceptance test is measured, and every failing one has a named owner and a decision: fix, accept with a control, or stop.
- The audit trace for the replay is complete and its hash chain verifies.
- The miss list is attached to the scorecard, not kept in a separate file.

**Artifact.** Shadow scorecard and the known-miss list.

**What this repo's first run does.** On the synthetic data, 8 of the 9 acceptance tests in the sample brief pass and AC-06 fails: the kit finished 134 cases on its own and 15 of them differ from the recorded human outcome, against a limit of 1%. Under the brief's own exit criteria that is a gate that stays shut (`step_04`). The playbook's answer is not to move the limit. It is to change the rule (send name mismatches and closed-account returns that carry an advised account to a person), re-run, and say the second run is no longer held-out evidence because the rule was designed from the first.

**Watch for.** Agreement is a ceiling set by the people. A recorded outcome is not ground truth. And a high agreement rate hides the cases where the agent chose not to propose; report those too.

---

## G5. Limited rollout

**Purpose.** Put real cases through it with a person at both gates.

**Entry criteria**
- G4 exit; the kill switch drilled by someone who did not build it; an on-call engineer named; the runbook items drafted.

**Work**
- Route a small share of new cases (the brief says 10 percent) through the kit in live mode. S07 and S09 stay with people on every case. The kit resubmits only after an approval from a person who is not the preparer, for that exact correction.
- Each week, sample cases and compare the agent's proposal with what the person did.
- Track the queue-return rate, the retries and fallbacks, the scope blocks and the gate queue depth.

**Exit criteria**
- The criteria written in the brief's `rollout.exit_criteria` hold for the stated period (the sample brief says four weeks of a weekly sample).
- No scope violation, no resubmission without an approval, no duplicate write.
- Every case in the human queue has a reason kind and an owner.

**Artifact.** Weekly rollout report and the change log.

**Not evaluable in this repo.** Everything in this gate needs live data. The step 4 printout marks those exit criteria "not evaluable here".

---

## G6. Hand-off and runbook

**Purpose.** Move ownership from the builder to the team that will carry the pager.

**Entry criteria**
- G5 exit; a named owner role (the brief's `handoff.owner_role`); the runbook items in the brief drafted.

**Work**
- Finish the runbook. The kit drafts a skeleton from the brief (`handoff.build_runbook`) with what the brief already knows and TO WRITE where an operator's steps belong. Nobody has run the skeleton.
- Wire the monitors the brief names (gate queue depth, tool error rate, queue-return rate, scope blocks, kill switch state, agreement on a weekly sample) into the platform's observability (05 AgentWatch).
- Rehearse: someone from the owning team engages and releases the kill switch (RB-01), works a case that came back to the human queue (RB-03), and rolls back to the human-only process (RB-07).
- Move the brief, the config and the kit version under the owning team's change control.

**Exit criteria**
- The owning team lead signs the hand-off record.
- A person other than the builder completed RB-01 and RB-07 in a rehearsal, with the audit trace to show it.
- Access recertification is scheduled.

**Artifact.** Signed hand-off record and the completed runbook.

---

## G7. Post-launch review

**Purpose.** Decide what to do with what production taught.

**Entry criteria**
- 30 days of live operation (a design value, set when the brief is written).

**Work**
- Re-run the acceptance tests on live data. Compare with G4.
- Read the human queue by reason kind, the scope-change requests, and every case where a person overrode a gate decision.
- Review benefit against the business case (12 ValueLedger).
- Decide: widen the scope (a new brief version), fix, hold, or retire.

**Exit criteria**
- A review record with a decision and an owner for each finding.
- The next brief version, with the changed thresholds and their approver.

**Artifact.** Review record and the next brief version.

---

## Engineering standards for the engineer who picks the pack up

### Code review
- Two reviewers for anything under `skills/`, `tools.py` and `orchestrator.py`.
- A change that adds a tool or an action changes the brief first, with its approver, and the code second.
- A change near S07, S09 or S10 needs a test that fails without it.
- Every new decision writes an audit event. Every new write has an idempotency key.
- A stub stays labeled as a stub, in code, in the docs and in the app, until a model replaces it and has been evaluated.

### Test and evaluation gates
- Merge is blocked unless the unit, scope, gate, idempotency, kill switch, audit and fault-injection tests pass.
- A change to a skill, a matching threshold or the reason-code table re-runs the shadow replay, and the acceptance results are diffed against the last run.
- Thresholds and limits are brief changes. They are not edited in code to make a test pass.
- If anything was tuned on a set of cases, the evidence for it comes from a later set of cases.

### Rollback
- The kill switch stops new work and sends open cases back to the human queue. It is not a rollback: it does not undo a write.
- Rollback is a decision to return the workflow to the human-only process (RB-07). Rehearse it before G5 closes.
- Pin the brief version, the config and the kit version together, so that a rollback restores a known set.
- Idempotency keys survive a rollback, so a case replayed after one does not resubmit twice.

### Logging
- One event per decision, tool call, gate, approval and route, with a case id. Sampling decisions is not allowed.
- The log is append-only and hash-chained. Run the chain check and the completeness check on a schedule and alert on failure.
- In production, mask account numbers and names in the log and keep the full values in the system of record. The prototype logs synthetic values and says so.
- Retention and access follow the owning team's record-keeping rules. The design defaults are in `ARCHITECTURE.md`.

### Definition of done for the pack
- The brief validates. The tests pass. The shadow scorecard and its miss list exist. The runbook has been rehearsed by someone other than the builder. The owning team has signed. The post-launch review is on the calendar.
