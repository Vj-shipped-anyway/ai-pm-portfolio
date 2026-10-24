# PRD: Tool Schema Drift gate

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a change-control review for an agent's tool catalogue. It is not a record of a PRD landed at a named bank. The rules, the planted pull-request set and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Tool Schema Drift: a command-line gate, with a staged GitHub Action, that reads two revisions of a tool schema and optional recorded calls and prints ALLOW, REVIEW or BLOCK for a schema pull request |
| **Owner** | The engineer who owns the tool catalogue behind an agent, with a second-line reviewer as co-owner of which level fails the step |
| **Stage** | Portfolio prototype on synthetic data; the Action is staged and unpublished |
| **Primary user** | The engineer who owns a tool catalogue behind an agent |
| **Secondary users** | The reviewer who approves changes to the catalogue; the owner of the agent whose calls depend on the tool; the security reviewer; internal audit |
| **Problem** | Agents call tools through a schema they were given. When a team changes that schema in a pull request, the unit tests on the code behind the tool still pass. The agent then meets rejected calls, or calls that still validate and now mean something else. In the planted set, 🟢 a pipeline with no schema gate stops 0 of 67 pull requests and 25 of 67 break at least one recorded call. |
| **Solution** | Compares two schema files and classifies each change as breaking, behavior-risk or non-breaking, with a reason a reader can act on. Checks numbers and units in every description that changed. Replays recorded calls against the new schema. Prints ALLOW, REVIEW or BLOCK, exits non-zero at a chosen level, and writes GitHub annotations on request. |
| **North-star metric** | Share of schema pull requests on in-scope tool catalogues that pass through the gate with a recorded decision. Target 🔴 100%. Today in this model: no pull request is checked. |
| **Measured metrics (synthetic)** | 🟢 25 of 25 breaking pull requests blocked; 0 of 27 harmless ones blocked; 9 of 15 behavior-risk ones sent to review; a person reads 34 of 67 instead of 67; the decision matches the planted truth on 61 of 67 (`step_04_with_gate.py`). |
| **Modeled metrics** | 🟡 Utility (67 − 34) / 67 × 200 = 98.5 pull requests a year a person does not have to read, assuming 200 pull requests a year touch a tool schema. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling, although the set includes cases the rules miss. Mitigation: run it on one real tool catalogue the owner may share and report the planted numbers and the real numbers apart. |
| **Risk #2** | Replay depends on the recorded calls. 🟢 With only 3 recorded calls per tool it blocks 23 of 25 breaking pull requests (`step_03_deficiencies_exposed.py`). Mitigation: the structural check stands alone and blocks 25 of 25; a log-coverage check on the calls file is in the backlog. |
| **Risk #3** | The unit check misses a scale change that keeps the unit word. 🟢 6 of 15 behavior-risk changes pass, three of them scale changes (`step_04_with_gate.py`). Mitigation: run the unit rule in advisory mode first, and add an explicit unit field to numeric parameters so the check reads a field and not prose. |
| **Out of scope** | Reading descriptions for malicious instructions; semantic-version policy; nested or composed schemas; any model call; hosting. A Marketplace listing is a later, separate step. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is pull requests, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Structural classifier** (rename, removed or required field, type change, enum value, bound) | 67 PRs | 3 | 0.9 | 1 | 180.9 | Built in prototype |
| 2 | **Input validation** (empty, wrong-type or truncated schema exits 2, never a traceback) | 67 PRs | 2 | 0.9 | 1 | 120.6 | Built in prototype |
| 3 | **Replay of recorded calls** (any failing call forces BLOCK) | 67 PRs | 3 | 0.8 | 2 | 80.4 | Built in prototype |
| 4 | **Number and unit check on changed descriptions, and default changes** (REVIEW) | 67 PRs | 2 | 0.5 | 1 | 67.0 | Built in prototype |
| 5 | **CI output** (text and GitHub annotations, `--fail-on` levels, escaped strings) | 67 PRs | 2 | 0.9 | 2 | 60.3 | Built in prototype |
| 6 | **Publish the Action from its own repository** | 67 PRs | 2 | 0.6 | 2 | 40.2 | Sequenced for v0.2 (staged in `action/`, not published) |
| 7 | **Recorded-call capture from production** (`tsd-calllog`) | 67 PRs | 3 | 0.5 | 4 | 25.1 | Sequenced for v0.2 |
| 8 | **Decision ledger** (schemas, calls file hash, findings) | 67 PRs | 2 | 0.6 | 4 | 20.1 | Sequenced for v0.2 |
| 9 | **Semantic-version policy check** | 67 PRs | 1 | 0.4 | 2 | 13.4 | Queued |
| 10 | **Scan of descriptions for malicious instructions** | 67 PRs | 3 | 0.3 | 5 | 12.1 | Queued |
| 11 | **Pattern, format, oneOf, anyOf and nested objects** | 67 PRs | 2 | 0.4 | 5 | 10.7 | Sequenced for v0.3 |
| 12 | **Explicit unit field and scale check** (the three scale changes the unit word hides) | 15 PRs | 2 | 0.4 | 3 | 4.0 | Sequenced for v0.3 |

---

## Stakeholder map

| Stakeholder | Role | What they want from Tool Schema Drift | What they fear |
| --- | --- | --- | --- |
| **Tool catalogue owner** | Owner | A check that fails a pull request with a reason a person can act on, and a pass on a harmless reword. | A gate that flags every change, as a text diff does, and gets switched off. |
| **Second-line reviewer** | Approver of the policy | A record of which change was allowed, which was held and why, so a REVIEW is a decision and not a shrug. | A behavior-risk change that merges unread because the gate said ALLOW. |
| **Agent owner** | Consulted | To hear before merge that a parameter, a bound or a unit moved under the agent. | Learning of it from failed calls in production. |
| **Platform / pipeline engineer** | Runs the CI | One command, standard library only, with clear exit codes. | Another service in the pipeline to run and patch. |
| **Security / CISO** | Approver | Tool descriptions treated as inputs that need review, nothing leaving the boundary, strings from input kept out of logs. | A changed description carrying instructions the gate never reads. |
| **Internal audit** | Reader | A path from a decision to the exact schemas and calls it used. | A policy level changed silently between two runs. |

---

## User stories (top 4)

1. **As the tool catalogue owner**, I want the pipeline to fail when a pull request removes or renames a parameter or tightens a bound, so the agent does not meet rejected calls after merge.
2. **As a reviewer**, I want each finding to name the parameter and say what changed, so I can decide to merge or hold without a meeting.
3. **As an agent owner**, I want a changed default or a moved unit in a description to reach a person even though the structure still validates, so a call that passes does not quietly mean something else.
4. **As internal audit**, I want each decision tied to the old schema, the new schema and the calls file it used, so I can reproduce it later.

---

## KPIs

**North star:** share of schema pull requests on in-scope tool catalogues that pass through the gate with a recorded decision. Target 🔴 100%.

**Inputs (leading):**
- Tools with a schema in version control and a pull-request check attached (the prototype set has 🟢 10 tools, from `data/README.md`).
- Recorded calls per tool (prototype: 🟢 40 per tool, 400 in all; target: calls that cover every parameter of every tool).
- Units in the unit table that the catalogue actually uses (target: every unit that appears in a description).
- Pull requests that carry the calls file with the schema change (target: every one).

**Outputs (lagging):** prototype baselines from the planted set.
- Breaking pull requests blocked. 🟢 25 of 25 with the gate, against 0 of 67 stopped with no check (`step_04_with_gate.py`, `step_01_no_gate.py`).
- Harmless pull requests blocked. 🟢 0 of 27; sent to review 0 of 27 (`step_04_with_gate.py`).
- Behavior-risk pull requests sent to review. 🟢 9 of 15 (`step_04_with_gate.py`).
- Pull requests a person has to read. 🟢 34 of 67 against 67 for a text diff (`step_04_with_gate.py`, `step_02_textual_diff.py`).
- Decision matches the planted truth. 🟢 61 of 67 (`step_04_with_gate.py`).
- Known miss. 🟢 6 of 15 behavior-risk changes pass (`step_04_with_gate.py`).
- ALLOW decisions later found to have broken a call in production: not measured; the planted set has no production.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the check on one tool catalogue with `--fail-on never`. Print the decision, fail nothing, and compare with what the reviewer did. |
| 1: Calibration | 4w | Read the REVIEW decisions. Add the units the catalogue uses to the unit table, and decide whether a changed default should reach a person. |
| 2: Breaking enforced | 4w | Fail the step on BLOCK from the structural check and from replay. REVIEW stays advisory. |
| 3: Review enforced and Action published | 6w | Fail the step on REVIEW for the catalogues that asked for it. Publish the Action from its own repository. |
| 4: Call capture and ledger | 8w | Capture recorded calls from production, write a decision record per pull request, and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should one failing recorded call be enough to BLOCK?** In the prototype it is; that is my policy. Recommendation: keep it, because a recorded call is a call the agent already made, and revisit once a real log shows how many of them are test traffic.
2. **Should a changed default go to REVIEW or be allowed?** The prototype sends it to review because calls that omit the field now get a new value and still validate. Recommendation: keep REVIEW, and drop it to advisory if a pilot shows reviewers clearing it every time.
3. **How many recorded calls are enough?** 🟢 With 3 per tool, replay blocks 23 of 25 breaking pull requests (`step_03_deficiencies_exposed.py`). Recommendation: ask for a log that covers every parameter of every tool before replay is allowed to be the only blocker.
4. **Who owns the unit table?** It is English only and short. Recommendation: the catalogue owner, by pull request, with the reviewer as approver.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the pipeline.** The check is stateless: it reads two schemas and an optional calls file and returns a decision. Production adds a recorded-call capture and a decision ledger, both designed and none built.
- **Never silent.** A missing, empty or malformed schema exits 2 and fails the step, even with `--fail-on never`. A calls file with no rows for the tool says so and replays nothing.
- **Strings from input are data.** Annotations escape `%`, carriage return and newline, so a hostile parameter name cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the blocked count shows in the diff.

**What is next.** Run it on one real tool catalogue the owner is allowed to share; add a version-policy check; publish the Action from its own repository.

**What would have to be true before a pilot.**
- The tool schemas live in version control and a pull request is the only way they change.
- The agent's calls are recorded in a form the check can read, with the tool name and the arguments.
- A named person owns the unit table and the level that fails the step.
- One real catalogue can be shared, so the rules are measured on real changes and not mine.
- The team agrees whether REVIEW fails the step or only warns.

---

*This PRD names [15 SchemaWatch](../15-schemawatch-tool-schema-drift/), [05 AgentWatch](../05-agentwatch-agent-observability/), [06 PromptShield](../06-promptshield-prompt-injection-defense/) and [61 MCP Scope Lint](../61-mcp-scope-lint/) as designed interlocks (🔴 designed, none built). The classifier is a copy of 15's with bound checks added, not an import of its files.*
