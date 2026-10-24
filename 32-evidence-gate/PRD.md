# PRD: Evidence Gate

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a release-governance review. It is not a record of a PRD landed at a named bank. The rules, the planted pull request set and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Evidence Gate: a command-line gate, with a staged GitHub Action, that reads the AI change record in a pull request description and prints ALLOW, REVIEW or BLOCK |
| **Owner** | The governance lead who owns the tier-to-evidence table, with the engineer who owns the repository's CI as co-owner of the check |
| **Stage** | Portfolio prototype on synthetic data; the Action is staged and unpublished |
| **Primary user** | An engineer who ships changes to an AI use case |
| **Secondary users** | The reviewer who approves those changes; the governance lead who owns the tier table; the owner of the use-case registry |
| **Problem** | A team says a use case has the evidence its risk tier requires. The pull request that changes the use case has a template with a checklist, and nothing reads it. Boxes get ticked, lines get deleted, a link points at a file that was never added, a date is a year ahead. The reviewer finds out by opening every link, or does not. In the planted set, 🟢 a process with no check stops 0 of 107 pull requests and 129 of 642 owed evidence items are missing, stale or unusable. |
| **Solution** | Reads the record in the description (use case, declared tier, one line per evidence item; comments and code fences are ignored). Takes the tier from the registry when the use case is listed and looks up the evidence that tier owes, cumulatively. Checks that each owed item is listed, ticked, references a file that is in the repository and carries a valid date within its freshness limit. Prints ALLOW, REVIEW or BLOCK, exits non-zero at a chosen level, and writes GitHub annotations on request. |
| **North-star metric** | Share of merged changes to in-scope AI use cases that pass the gate with a recorded decision and evidence the tier requires. Target 🔴 100%. Today in this model: nothing reads the checklist. |
| **Measured metrics (synthetic)** | 🟢 49 of 59 should-block pull requests blocked, against 8 of 59 for a rule that every box is ticked; 6 of 6 wrong-tier labels sent to review; 3 of 42 fine pull requests blocked, all with evidence written as a table (`step_04_with_gate.py`, `step_02_checklist_rule.py`). |
| **Modeled metrics** | 🟡 Utility (49/59 − 8/59) × 40 = 27.8 should-block pull requests a year stopped that a tick check would pass, assuming 40 should-block pull requests reach the gate each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real repository and report the planted numbers and the real numbers apart. |
| **Risk #2** | The gate trusts a typed date and a file that exists. 🟢 7 of 59 should-block pull requests pass: a reference to a real file that holds another use case's evidence, and a registry one tier too low that the author copies (`step_04_with_gate.py`). Mitigation: the README names both misses; add a content check for the one or two evidence types that can be machine-read, and an owner and refresh date for the registry. |
| **Risk #3** | A registry that is not kept current sets the wrong bar. Mitigation: an owner and a refresh date for the registry, and REVIEW on any tier the gate cannot confirm. |
| **Out of scope** | Reading the evidence itself; proving a date or a signature; mapping evidence items to a framework's identifiers; a full markdown parser; any model call; hosting. A Marketplace listing is a later, separate step. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is pull requests, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Listed-and-ticked check** (an owed item that is missing or unticked: BLOCK) | 107 PRs | 2 | 0.9 | 1 | 192.6 | Built in prototype |
| 2 | **Input validation** (empty, truncated, wrong-type or duplicate input exits 2, never a traceback) | 107 PRs | 2 | 0.9 | 1 | 192.6 | Built in prototype |
| 3 | **Tier bar from the registry** (the registry sets the bar; a differing label is a REVIEW) | 107 PRs | 3 | 0.8 | 2 | 128.4 | Built in prototype |
| 4 | **Reference-in-repository check** (a ref must be a path in the file listing; a web link is a REVIEW) | 107 PRs | 3 | 0.8 | 2 | 128.4 | Built in prototype |
| 5 | **CI output** (text and GitHub annotations, `--fail-on` levels, escaped strings) | 107 PRs | 2 | 0.9 | 2 | 96.3 | Built in prototype |
| 6 | **Parser tolerance** (CRLF, `[X]`, bold labels; comments and code fences not read) | 107 PRs | 2 | 0.8 | 2 | 85.6 | Built in prototype |
| 7 | **Freshness check** (a real date, not in the future, within the inclusive limit) | 107 PRs | 2 | 0.7 | 2 | 74.9 | Built in prototype |
| 8 | **Publish the Action from its own repository** | 107 PRs | 2 | 0.6 | 2 | 64.2 | Sequenced for v0.2 (staged in `action/`, not published) |
| 9 | **Decision ledger** (use case, tier, findings, file hashes, tool version) | 107 PRs | 2 | 0.7 | 4 | 37.4 | Sequenced for v0.2 |
| 10 | **Registry feed from intake** (the inventory export, with a refresh date) | 59 PRs | 2 | 0.5 | 4 | 14.8 | Sequenced for v0.3 |
| 11 | **Content check for machine-readable evidence** (one or two evidence types) | 59 PRs | 3 | 0.4 | 5 | 14.2 | Sequenced for v0.3 |
| 12 | **Read evidence written as a table** (3 fine pull requests are blocked today) | 42 PRs | 1 | 0.5 | 3 | 7.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Evidence Gate | What they fear |
| --- | --- | --- | --- |
| **Engineer who ships the change** | Primary user | A failure that names the item and the reason, so the fix is one edit to the description or the repository. | A block on a good change because the evidence was written in a format the parser does not read. |
| **Reviewer** | Approver of the change | Not having to open every link; a short list of the few changes that need a person. | A gate that passes a ticked box pointing at the wrong file, so the reviewer trusts it too far. |
| **Governance lead** | Owner of the tier table | The tier table enforced where work cannot skip it, and freshness limits that follow policy. | Limits set from the prototype's assumptions and treated as policy. |
| **Registry owner** | Keeper of the use-case inventory | A registry that sets the bar, with a clear signal when a use case is missing or one tier too low. | Being blamed for a miss that comes from a stale registry. |
| **CI platform owner** | Co-owner of the check | One step that fails with a reason and does not slow the pipeline. | Another required check that engineers learn to route around. |
| **Security / CISO** | Approver | No key in the gate's path, nothing leaving the boundary, strings from the description kept out of workflow commands. | A description field that can forge a workflow command. |
| **Internal audit** | Reader | A path from a merge to the exact description, tier table and registry it was checked against. | Limits changed silently between two merges. |

---

## User stories (top 4)

1. **As an engineer who ships a change to an AI use case**, I want the pull request to fail when a required evidence item is missing, unticked, unreferenced or out of date, so I find the gap before the reviewer does.
2. **As a reviewer**, I want the registry tier, and not the author's label, to set the evidence a change owes, and a differing label sent to me, so a change cannot lower its own bar.
3. **As the governance lead**, I want each finding to name the item and the rule it broke, so the tier table is enforced in the same words I wrote it in.
4. **As internal audit**, I want each decision tied to the description, the tier table, the registry and the as-of date it used, so I can reproduce it later.

---

## KPIs

**North star:** share of merged changes to in-scope AI use cases that pass the gate with a recorded decision and evidence the tier requires. Target 🔴 100%.

**Inputs (leading):**
- Use cases in the registry with a tier and an owner (the prototype registry holds 🟢 33 registered use cases of 40, from `data/README.md`).
- Evidence items in the tier table with a freshness limit (the prototype table has 🟢 11 evidence items, from `data/README.md`).
- Pull requests whose description carries a change record in the template's line format (target: every change to an in-scope use case).
- Repositories that supply a current file listing to the gate (target: every repository).

**Outputs (lagging):** prototype baselines from the planted set.
- Should-block pull requests stopped. 🟢 49 of 59 with the gate, against 8 of 59 for a rule that every box is ticked and 0 of 107 with no check (`step_04_with_gate.py`, `step_02_checklist_rule.py`, `step_01_no_gate.py`).
- Fine pull requests blocked. 🟢 3 of 42; sent to review 7 of 42 (`step_04_with_gate.py`).
- Wrong-tier labels sent to review. 🟢 6 of 6 (`step_04_with_gate.py`).
- Decision matches the planted truth. 🟢 87 of 107 (`step_04_with_gate.py`).
- Pull requests a reviewer is asked to look at. 🟢 16 of 107, with the author fixing the 52 that are blocked (`step_04_with_gate.py`).
- Known misses. 🟢 7 of 59 should-block pass and 3 of 59 reach review only (`step_03_deficiencies_exposed.py`).
- Blocks overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the gate on one repository with `--fail-on never`. Print the decision, fail nothing, and compare with what the reviewer did. |
| 1: Calibration | 4w | Read the findings with the governance lead. Replace my freshness limits with the policy's. Check the registry against the inventory and name an owner. |
| 2: Missing and unticked enforced | 4w | Fail the step on missing, unticked and unreferenced items. REVIEW stays advisory. |
| 3: Files and dates enforced | 6w | Fail the step on a reference not in the file listing and on stale or future dates. Publish the Action from its own repository. |
| 4: Ledger and registry feed | 8w | Write a decision record per merge. Feed the registry from intake and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should a ticked box with a file that exists but holds another use case's evidence be caught?** The gate misses it today. A rule that the path must contain the use case id would catch it, and I left it out because it infers structure from a naming convention. Recommendation: do not add the rule; add an explicit field for the use case id in the evidence line, and check that.
2. **Where should the freshness limits come from?** They are my assumptions, in `data/tier_evidence.csv`. Recommendation: the governance lead replaces them with the policy's limits in phase 1, and the inclusive-limit convention is confirmed or reversed in writing.
3. **Who keeps the registry current?** A registry one tier too low is one of the two misses the gate cannot catch. Recommendation: name an owner, require a refresh date on each row, and let the gate send any use case it cannot find to review.
4. **Should evidence written as a table be read?** Today it is blocked, which is a false alarm in the planted set. Recommendation: keep the line format as the contract for v0.1, and add table reading only if the pilot shows authors prefer it.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the pipeline.** The gate is stateless: it reads a description, a tier table, a registry and a file listing, and returns a decision. Production adds a registry feed, a decision ledger and telemetry, all designed and none built.
- **Never silent.** A missing, empty or malformed input exits 2 and fails the step, even with `--fail-on never`. An owed item that is not in the record is a finding. A check whose input is not supplied says so in a note.
- **Strings from the description are data.** Annotations and text output escape control characters, so a hostile string cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the blocked count shows in the diff.

**What is next.** Run it on one real repository whose owner will share the pull request descriptions; add a content check for the one or two evidence types that can be machine-read; publish the Action from its own repository.

**What would have to be true before a pilot.**
- A named person owns the registry and refreshes it on a schedule.
- The tier-to-evidence table and its freshness limits are the governance lead's, not mine.
- The repository's template uses the line format, or the parser is extended to the format it uses.
- One real repository can share its descriptions, so the false-alarm rate is measured on real text.
- The team agrees which level fails the step.

---

*This PRD names [11 TierGate](../11-tiergate-ai-usecase-intake/), [24 PortfolioBoard](../24-portfolioboard-ai-program-portfolio/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The tier table and the idea of a freshness limit are copied from the first two, not read from their files.*
