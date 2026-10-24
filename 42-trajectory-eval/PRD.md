# PRD: Trajectory Eval

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an agent-governance review. It is not a record of a PRD landed at a named bank. The task rubrics, the planted runs and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Trajectory Eval: a suite of 20 bank-operations task rubrics and a scorer that reads the calls in a recorded agent run and prints PASS or FAIL with the reason |
| **Owner** | The AI operations lead or engineer who owns an agent in a rule-based workflow, with the control owner as co-owner of the rubric |
| **Stage** | Portfolio prototype on synthetic data; no Action or service is staged |
| **Primary user** | The AI operations lead or engineer who owns an agent in a rule-based workflow |
| **Secondary users** | The control owner who decides which steps must happen first; the process owner whose workflow the agent runs; the second-line reviewer; internal audit |
| **Problem** | A team that evaluates an operations agent usually checks the final answer. A run can reach the right answer after skipping a check, acting before an approval, calling a tool the task forbids, or looping. The final-answer eval passes those runs, and the reviewer who owns the process never sees them. In the planted set, 🟢 236 of 240 runs are accepted because the agent returned a final answer, and 92 of those 236 are defective (`step_01_self_report.py`). |
| **Solution** | Holds a task as a rubric: graded steps (tools that count, arguments that must match, which earlier steps each must follow), forbidden tools, stop signals, a call budget and the expected final answer. Grades a recorded run against it and prints PASS or FAIL with the reason, a partial-credit score and an exit code. Lets independent steps come in any order and lists equivalent tools, so a valid alternative path is not punished. |
| **North-star metric** | Share of production agent runs in in-scope workflows that are graded on their steps with a recorded result, and where every failing run is read by a named person. Target 🔴 100%. Today in this model: only the final answer is checked. |
| **Measured metrics (synthetic)** | 🟢 90 of 96 defective runs caught, against 12 of 96 for a final-answer check; 78 of the 84 defective runs with a right final answer caught; 6 of 64 hard negatives failed; the 7 sound runs at exactly the call budget all pass (`step_04_trajectory_scorer.py`). |
| **Modeled metrics** | 🟡 Utility (90/96 − 12/96) × 800 = 650 defective runs a year caught beyond what a final-answer check catches, assuming 800 defective runs reach the eval each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The runs and the rubric share an author, so the numbers are a ceiling. I built the runs from a world model of each task and wrote the rubric separately, but I wrote both. Mitigation: run it on a few days of traces from one agent the owner may share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | A rubric is only as complete as its author. 🟢 Six sound runs fail because they use an equivalent tool the rubric does not list (`step_04_trajectory_scorer.py`). Mitigation: run in shadow first, read every sound run that fails, and add the listed alternative by reviewed change. |
| **Risk #3** | The scorer reads tool names, named arguments, observations, order and the call count, not free text. 🟢 Six defective runs pass because sensitive text sits in a free-text argument (`step_04_trajectory_scorer.py`), and no simple check sees it either (`step_03_deficiencies_exposed.py`). Mitigation: say so in the output, and queue a pattern check for free-text arguments. |
| **Out of scope** | Running an agent; reading free text inside arguments or the wording of a final answer; finding unsafe actions nobody listed; prompt-injection or hijacking tests; any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is runs or tasks, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Forbidden-tool rule** (any call to a listed tool fails the run, even one that errors) | 240 runs | 3 | 0.9 | 1 | 648.0 | Built in prototype |
| 2 | **Order rule** (a step that must follow another and ran before it is wrong order) | 240 runs | 3 | 0.8 | 1 | 576.0 | Built in prototype |
| 3 | **Stop-signal rule** (a blocked tool called after a check returned the stop value fails the run) | 240 runs | 3 | 0.7 | 1 | 504.0 | Built in prototype |
| 4 | **Final-answer keys** (the named keys of the expected answer must match) | 240 runs | 2 | 0.9 | 1 | 432.0 | Built in prototype |
| 5 | **Required steps** (successful call, named arguments, equivalent tools, a step used once) | 240 runs | 3 | 0.9 | 2 | 324.0 | Built in prototype |
| 6 | **CI output** (text and GitHub annotations, `--fail-on`, escaped strings) | 240 runs | 2 | 0.9 | 2 | 216.0 | Built in prototype |
| 7 | **Call budget** (more calls than the budget fails the run) | 240 runs | 1 | 0.5 | 1 | 120.0 | Built in prototype |
| 8 | **Trace collector and redaction** (export the calls from the agent runtime, strip sensitive text) | 240 runs | 2 | 0.6 | 6 | 48.0 | Sequenced for v0.2 |
| 9 | **Input validation** (malformed task or run exits 2, never a traceback) | 20 tasks | 2 | 0.9 | 1 | 36.0 | Built in prototype |
| 10 | **Rubric alternatives from failing runs** (propose the unlisted equivalent tools to a reviewer) | 20 tasks | 2 | 0.5 | 3 | 6.7 | Sequenced for v0.2 |
| 11 | **Budget per task from real traces** (replace the two-times-plus-two formula) | 20 tasks | 1 | 0.5 | 2 | 5.0 | Queued |
| 12 | **Pattern check on free-text arguments** (sensitive text in a note field) | 6 runs | 3 | 0.4 | 4 | 1.8 | Sequenced for v0.3 |

---

## Stakeholder map

| Stakeholder | Role | What they want from Trajectory Eval | What they fear |
| --- | --- | --- | --- |
| **AI operations lead** | Owner | A grade for every run that names the step and the reason, and a non-zero exit only when something is wrong. | A suite that fails sound runs until the team stops reading it. |
| **Agent engineer** | Builds and tunes the agent | A failing run with the call, the step and the expected argument, so the fix is clear. | A rubric that punishes a valid alternative path and locks the agent to one route. |
| **Control owner** | Decides which steps come first | Order and forbidden-tool rules written once and applied to every run. | A rubric that drifts from the control it is meant to enforce. |
| **Process owner** | Owns the workflow | To know when an agent acted before an approval or skipped a check. | Learning of it from an incident. |
| **Second-line reviewer** | Approver of rubric changes | A record of which rubric version graded which run, and who changed it. | Rubrics loosened to turn failures green. |
| **Security / CISO** | Approver | Traces that hold sensitive text kept inside the boundary, with no vendor key in the grader's path. | A new store of raw agent traces. |
| **Internal audit** | Reader | A path from a grade to the exact run, rubric and tool version it used. | A rubric changed between two grading runs without a record. |

---

## User stories (top 4)

1. **As the AI operations lead**, I want a run that called a forbidden tool, acted before its approval or ignored a stop signal to fail even when the final answer is right, so the process is graded as well as the result.
2. **As an agent engineer**, I want each failing run to name the step, the call and the reason, so I can fix the agent without reading the whole trace.
3. **As a control owner**, I want independent steps and listed equivalent tools to pass in any order, so a valid path is not punished and the rubric only encodes what the control requires.
4. **As internal audit**, I want each grade tied to the run, the rubric version and the tool version, so I can reproduce it later.

---

## KPIs

**North star:** share of production agent runs in in-scope workflows that are graded on their steps with a recorded result, and where every failing run is read by a named person. Target 🔴 100%.

**Inputs (leading):**
- Tasks with a rubric reviewed by the control owner (the prototype has 🟢 20 tasks, from `data/README.md`).
- Traces that carry each call's named arguments and its observation (target: every agent).
- Tasks with a stop signal where the workflow has one.
- Rubric alternatives reviewed against real traces (target: before enforcement).

**Outputs (lagging):** prototype baselines from the planted set.
- Defective runs caught. 🟢 90 of 96 with the scorer, against 12 of 96 with a final-answer check (`step_04_trajectory_scorer.py`, `step_02_final_answer_check.py`).
- Defective runs with a right final answer caught. 🟢 78 of 84, mean score 0.82 (`step_04_trajectory_scorer.py`).
- Sound runs failed. 🟢 6 of 144; hard negatives failed 6 of 64 (`step_04_trajectory_scorer.py`).
- Known miss. 🟢 6 of 96 defective runs pass, all note_leak (`step_04_trajectory_scorer.py`).
- Runs accepted on the final answer alone. 🟢 236 of 240 (`step_01_self_report.py`).
- Failing runs overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Grade one agent's recorded runs with `--fail-on never`. Print the grades, fail nothing, and compare with what the process owner would have said. |
| 1: Calibration | 4w | Read every sound run that fails. Add reviewed equivalent tools, and set the call budget per task from clean real traces. |
| 2: Safety rules enforced | 4w | Fail the step on forbidden tools and ignored stop signals. Order and steps stay advisory. |
| 3: Order and steps enforced | 6w | Fail the step on wrong order, missing steps and wrong arguments. Add the trace collector with redaction. |
| 4: History and pattern check | 8w | Write a grade record per run. Add the free-text pattern check and test the interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Who writes the rubric?** Recommendation: the control owner writes order, forbidden tools and stop signals; the agent engineer lists the equivalent tools; both are reviewed together, and every change goes through a second approver.
2. **How are unlisted equivalent tools handled?** Six of 144 sound runs fail on one in the planted set. Recommendation: shadow first, then add each reviewed alternative, never a blanket allow.
3. **Is the call budget formula right?** It is two times the reference steps plus two, an assumption I fixed before generating a run. Recommendation: set it per task from clean real traces and keep the planted loops as the test.
4. **Should the score ever replace the all-conditions rule?** Recommendation: no. A run passes only when every condition holds; the score is a reading aid.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, no state.** The scorer reads a rubric file and a run file and returns a grade per run. Production adds a trace collector with redaction, a reviewed rubric repo and a grade history, all designed and none built.
- **Never silent.** A run that names a task not in the file, a malformed rubric or a trace that does not parse exits 2 and fails the step, even with `--fail-on never`. A task with no runs is named, not skipped.
- **Strings from input are data.** Run ids are shown with control characters as visible escapes and annotations are escaped, so a hostile id cannot forge a workflow command.
- **Changes to a rubric are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the caught count shows in the diff.

**What is next.** Run it on a few days of traces from one agent the owner may share; add a way to propose rubric alternatives from the tools that fail most often; add a check for sensitive patterns in free-text arguments.

**What would have to be true before a pilot.**
- The trace export carries each call's named arguments and observation.
- The control owner has written the order, forbidden-tool and stop-signal rules for the pilot workflow.
- A named person owns the rubric and will review each added alternative.
- A few days of real traces can be shared, so the budget and the alternatives are set against real runs and not mine.
- The team agrees which failure classes fail the step.

---

*This PRD names [04 EvalForge](../04-evalforge-llm-eval-platform/), [27 AgentKit](../27-agentkit-reference-agent-and-playbook/), [05 AgentWatch](../05-agentwatch-agent-observability/) and [23 ScopeKeeper](../23-scopekeeper-agent-permission-review/) as designed interlocks (🔴 designed, none built). It reads no file from any of them.*
