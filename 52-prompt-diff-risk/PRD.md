# PRD: prompt-diff-risk (PR check)

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a release-governance review for a customer-facing assistant. It is not a record of a PRD landed at a named bank. The rules, the word lists, the planted pull requests and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and no model was called: the failing probes are planted.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | prompt-diff-risk: a command-line check, with a staged GitHub Action, that compares two revisions of a system prompt, sorts each change into constraints, scope, tone or tools, prints ALLOW, REVIEW or BLOCK, and names the probe slices to run before the change merges |
| **Owner** | The engineer or product owner who maintains the prompt of a customer-facing assistant, with the reviewer who approves changes to it as co-owner of the rules and lists |
| **Stage** | Portfolio prototype on synthetic data; the Action is staged and unpublished |
| **Primary user** | An engineer or product owner who maintains the prompt of a customer-facing assistant |
| **Secondary users** | The reviewer who approves changes to the prompt; the evaluation owner who runs the probe set; second-line risk; internal audit |
| **Problem** | A system prompt is edited in a pull request like any other file. The unit tests on the code around it still pass. The assistant then refuses what it used to answer, drops a rule, or gains a tool, and the first signal is a customer. Running the full probe set on every edit is slow and costly, and reading every diff does not say which probes matter. In the planted set, 🟢 no gate means 0 of 70 pull requests run a probe before merge and 74 planted failing probes reach users unseen. |
| **Solution** | Splits two prompt revisions into statements and aligns them. Classifies each changed statement as constraints, scope, tone, tools or other, with a risk class a reader can act on. Reads tool grants from a catalogue with an explicit read or write access field. Maps each finding to probe slices and prints how many probes to run. Prints ALLOW, REVIEW or BLOCK, exits non-zero at a chosen level, and writes GitHub annotations on request. |
| **North-star metric** | Share of prompt pull requests merged with a recorded decision and, for every REVIEW or BLOCK, the named probe slices run and attached. Target 🔴 100%. Today in this model: no probe runs before merge. |
| **Measured metrics (synthetic)** | 🟢 19 of 22 high-risk pull requests blocked and 21 of 22 flagged; 24 of 30 medium-risk flagged; 2 of 18 harmless blocked and 5 of 18 sent to review; a person reads 52 of 70 instead of 70; the selected slices contain the planted failing probe in 45 of 52 risky pull requests, with 504 probe runs of 3780 (`step_04_with_gate.py`). |
| **Modeled metrics** | 🟡 Utility (3780 − 504) / 70 × 200 = 9,360 probe runs a year not spent against running the full set on every change, assuming 200 prompt pull requests a year. The two overlap thresholds (0.75 and 0.4), the rule-word list, the exception list and the tone list are my assumptions. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of a probe run and of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling, although the set includes cases the rules miss and cases that raise false alarms. The failing probes are simulated. Mitigation: run it on one real prompt repository the owner may share, count the false alarms, and compare the slices it names with the probes that failed after past changes. |
| **Risk #2** | A swapped word in a long sentence passes. 🟢 7 of the 52 risky changes pass, six of them one-word swaps with no rule word, tone word, tool name or number (`step_04_with_gate.py`). Mitigation: keep REVIEW as the floor for prompt files in the pilot, and count what reviewers find in the changes the tool let through. |
| **Risk #3** | Harmless rewordings can be blocked and a loophole in other words passes as a rewrite. 🟢 2 of 18 harmless pull requests are blocked and 2 of 22 high-risk are flagged but not blocked (`step_04_with_gate.py`). Mitigation: the lists are reviewed and extended from real pull requests; a BLOCK is cleared by a person other than the author, with the named probes attached. |
| **Out of scope** | Running the probes; calling any model; judging whether a sentence is true or safe; non-English prompts; prompts in structured formats other than plain text; order and heading effects; hosting. A Marketplace listing is a later, separate step. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is prompt pull requests. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Named probe slices** (by tool access, dimension and topic word, with the probe count) | 70 pull requests | 3 | 0.9 | 1 | 189.0 | Built in prototype |
| 2 | **Constraint strength rules** (rule removed, weakened to a softer word or given an exception: BLOCK; new, stronger or rewritten rule: REVIEW) | 70 pull requests | 3 | 0.8 | 1 | 168.0 | Built in prototype |
| 3 | **Input validation** (empty, headings-only, non-UTF-8, bad JSON or bad probe file exits 2, never a traceback) | 70 pull requests | 2 | 0.9 | 1 | 126.0 | Built in prototype |
| 4 | **Scope, tone and number rules** (a changed statement is REVIEW; unknown is not safe) | 70 pull requests | 2 | 0.7 | 1 | 98.0 | Built in prototype |
| 5 | **Tool grants from a catalogue** (write tool granted or its confirmation dropped: BLOCK; read tool granted or tool dropped: REVIEW) | 70 pull requests | 3 | 0.8 | 2 | 84.0 | Built in prototype |
| 6 | **CI output** (GitHub annotations, `--fail-on`, escaped strings) | 70 pull requests | 2 | 0.8 | 2 | 56.0 | Built in prototype |
| 7 | **Tool grants from the agent's real configuration** (not names in the prompt text) | 70 pull requests | 3 | 0.6 | 4 | 31.5 | Sequenced for v0.2 |
| 8 | **Publish the Action from its own repository** | 70 pull requests | 2 | 0.6 | 3 | 28.0 | Sequenced for v0.2 (staged in `action/`, not published) |
| 9 | **Calibrate the word lists and overlap thresholds on a real repository** | 70 pull requests | 2 | 0.6 | 3 | 28.0 | Sequenced for v0.2 |
| 10 | **Decision record per run** (inputs, hashes, thresholds, findings) | 70 pull requests | 2 | 0.5 | 4 | 17.5 | Sequenced for v0.3 |
| 11 | **Meaning check for one-word swaps** (a routing target or a tone image changed in a long sentence) | 70 pull requests | 3 | 0.3 | 6 | 10.5 | Queued |
| 12 | **Non-English and structured prompts** | 70 pull requests | 2 | 0.4 | 8 | 7.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from prompt-diff-risk | What they fear |
| --- | --- | --- | --- |
| **Prompt owner** | Owner | A check that fails with a reason a person can act on, and names the probes to run instead of all of them. | A check that blocks harmless rewordings and gets switched off. |
| **Prompt reviewer** | Approver of a BLOCK | The finding, the old and new sentence and the slices, in one place. | A BLOCK cleared by the author, so the gate becomes a formality. |
| **Evaluation owner** | Owns the probe set | Slice names that match the probe set, and a count of probes per run. | A tool that redefines the slices or runs the whole set anyway. |
| **Platform / CI owner** | Operator | A step that runs in seconds with no key and no network. | Another dependency in the pipeline, or a Marketplace listing nobody maintains. |
| **Second-line risk** | Reader | A rule they can read, with the word lists written out and the known misses stated. | A check presented as a safety guarantee. |
| **Security / CISO** | Approver | Nothing leaving the boundary, and prompt text kept out of workflow commands. | Prompt text, which can hold anything, forging an annotation. |
| **Internal audit** | Reader | A path from a decision to the two prompt revisions, the lists and the thresholds it used. | Word lists changed silently between two runs. |

---

## User stories (top 4)

1. **As the prompt owner**, I want the pull request to fail when a rule is removed, weakened or given an exception, so a change to a constraint is read by a person before it ships.
2. **As a reviewer**, I want a write tool granted, or its confirmation condition dropped, to be a BLOCK, so an agent does not gain the power to act without anyone deciding it should.
3. **As an evaluation owner**, I want each finding mapped to the probe slices to run, so a change costs a few slices and not the full set.
4. **As internal audit**, I want each decision tied to the two prompt revisions, the lists and the thresholds it used, so I can reproduce it later.

---

## KPIs

**North star:** share of prompt pull requests merged with a recorded decision and, for every REVIEW or BLOCK, the named probe slices run and attached. Target 🔴 100%.

**Inputs (leading):**
- Probes with a slice (the prototype set has 🟢 54 probes in 9 slices, 6 in each, from `data/README.md`).
- Tools in the catalogue with an explicit read or write access field (prototype: 8 tools, 4 read and 4 write).
- Prompt repositories running the check in advisory mode before it is enforced (target: the pilot repository).
- BLOCKs cleared by a person other than the author, with probe results attached (target: every BLOCK).

**Outputs (lagging):** prototype baselines from the planted set.
- High-risk pull requests blocked. 🟢 19 of 22, and 21 of 22 flagged (`step_04_with_gate.py`).
- Medium-risk pull requests flagged. 🟢 24 of 30 (`step_04_with_gate.py`).
- Harmless pull requests blocked or sent to review. 🟢 2 of 18 blocked, 5 of 18 sent to review (`step_04_with_gate.py`).
- Pull requests a person has to read. 🟢 52 of 70, against 70 of 70 for reading every change (`step_04_with_gate.py`, `step_02_basic_approach.py`).
- Probe runs. 🟢 504 of 3780, which is 13.3% of the full-set cost (`step_04_with_gate.py`).
- Planted failing probe inside the selected slices. 🟢 45 of 52 risky pull requests (`step_04_with_gate.py`).
- Known misses. 🟢 7 of 52 risky pull requests pass (`step_04_with_gate.py`).
- BLOCKs overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the check on one prompt repository with `--fail-on never`. Print the decision, fail nothing, and compare with what the reviewers did. |
| 1: Calibration | 4w | Count the false alarms and the changes the check let through. Set the rule-word, exception and tone lists, and the two overlap thresholds, with the team that owns the prompt. |
| 2: Review enforced | 4w | Fail the step on BLOCK. REVIEW stays advisory and names the slices. A BLOCK is cleared by a different person with the named probes run. |
| 3: Action published and tools wired | 6w | Publish the Action from its own repository. Read tool grants from the agent's configuration and not from names in the prompt text. |
| 4: Record and results gate | 8w | Write a decision record per run. Test the designed interlock with the probe results gate named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should a loophole in words off the exception list BLOCK?** Today a rule given an exception with "unless" or "except" is a BLOCK, and the same loophole in other words is a rewrite. Recommendation: keep the list reviewed, extend it from real pull requests, and treat a rewrite of a rule sentence as REVIEW at minimum.
2. **Who clears a BLOCK?** The tool does not know whether anyone signed off. Recommendation: a person other than the author, with the named probe results attached, recorded in the pull request.
3. **What to do about a one-word swap in a long sentence?** Six such edits pass, a routing target or a tone image. Recommendation: in the pilot, keep REVIEW as the floor for prompt files and count what reviewers find, until a meaning check is tested on a real repository.
4. **Where do tool grants come from?** The tool reads names in the prompt text. Recommendation: read the catalogue from the agent's configuration, which is the source an agent starts with.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One step in the pipeline.** The check is stateless: it reads two prompt files and optional catalogue and probe files, and prints a decision. Production adds reviewed lists, a decision record and a probe results gate, all designed and none built.
- **Never silent.** An empty prompt, a prompt of only headings or comments, a missing file or a malformed catalogue or probe file exits 2, never a traceback. A file with no changes says so.
- **Strings from input are data.** Annotations and text output escape control characters, so hostile prompt text cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the blocked count shows in the diff.

**What is next.** Run it on one real prompt repository the owner is allowed to share and count the false alarms; compare the slices it names with the probes that actually failed after past prompt changes; publish the Action from its own repository.

**What would have to be true before a pilot.**
- The probe set carries a slice on every probe, and the slice names match the ones the tool maps to.
- The tool catalogue has an explicit read or write access field for every tool.
- A named person owns the word lists and will extend them from real pull requests.
- One real repository can be shared, so the false alarms and the misses are counted on real edits.
- The team agrees which level fails the step and who clears a BLOCK.

---

*This PRD names [04 EvalForge](../04-evalforge-llm-eval-platform/), [13 SwapBrief](../13-swapbrief-model-migration/), [28 Tool Schema Drift](../28-tool-schema-drift/) and [40 Eval Gate](../40-eval-gate/) as designed interlocks (🔴 designed, none built). The probe-set shape, the slice table and the gate layout come from the first three; nothing is imported from them.*
