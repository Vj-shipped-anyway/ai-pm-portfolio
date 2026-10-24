# PRD: Inventory Check

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a model risk governance review. It is not a record of a PRD landed at a named bank. The field list, the cadences and the rollout plan are mine, because the guidance I read prescribes none; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and the skill is staged and has not run in an agent harness.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Inventory Check: a command-line tool, with a staged agent skill, that reads an inventory of generative and agentic AI systems and, if available, a model-gateway usage export, and prints PASS, REVIEW or FAIL with the finding behind each |
| **Owner** | The person who owns the inventory of AI systems, with the model risk reviewer as co-owner of the field list and the cadences |
| **Stage** | Portfolio prototype on synthetic data; the skill is staged and not installed |
| **Primary user** | The person who owns the inventory of AI systems |
| **Secondary users** | The model risk reviewer who relies on the inventory; the business and technical owner of each system; the team that runs the model gateway; internal audit |
| **Problem** | The current federal model risk guidance, SR 26-2, calls a model inventory common industry practice and places generative and agentic AI outside its scope. A bank's own governance has to carry those systems, and the inventory is where that starts. Inventories for them are kept by hand: a record can be blank, stale, or missing entirely, and a system can run for months with no record. Nobody tests the file. In the planted set, 🟢 57 of 100 records are defective and 0 of 100 are flagged for a reviewer (`step_01_no_test.py`). |
| **Solution** | Completeness: required fields, legal values, the fields an agent needs (tools, permission scope, human approval), and the evidence a production system owes at its risk tier. Staleness: review and evaluation dates against a cadence per tier, and the recorded model id against the model recent traffic used. Coverage: traffic from systems with no record or no system id, retired systems still running, production systems with no traffic. Prints the decision with the finding behind each, exits non-zero at a chosen level, and prints GitHub annotations on request. A staged agent skill wraps the command. |
| **North-star metric** | Share of in-scope AI systems whose record passes the tests on the latest run, with the run recorded and every FAIL finding read by a named person. Target 🔴 100%. Today in this model: no test runs on the inventory. |
| **Measured metrics (synthetic)** | 🟢 51 of 57 defective records flagged; 2 of 43 clean records flagged; a person opens 53 of 100 records instead of all 100; the usage export names 4 of the 7 shadow systems (`step_04_with_checks.py`). |
| **Modeled metrics** | 🟡 Utility (51/57 − 8/57) × 114 = 86 defective records found that a blank-cell check would miss, assuming 114 defective records in the inventory. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling, and a real inventory has messier fields. Mitigation: run it on one real inventory the owner may share and report the planted numbers and the real numbers apart. |
| **Risk #2** | The usage tests depend on a gateway that logs the system id and the model id on every call. 🟢 Three of the 7 shadow systems stay unnamed: one sends no system id and two send theirs under a listed system's id (`step_03_deficiencies_exposed.py`). Mitigation: a gateway contract that rejects a call with no system id, and the note the tool prints when no usage row matches. |
| **Risk #3** | The cadences are assumptions, and a PASS means the record passed these rules, not that the inventory is right. 🟢 Six of 57 defective records pass, and 2 of 43 clean records are flagged (`step_04_with_checks.py`). Mitigation: set the cadences with the model risk team, and say in the output what a PASS does not cover. |
| **Out of scope** | Judging whether a system is safe or well governed; reading a purpose statement for meaning; checking that an owner is still employed; any model call; hosting; a mapping to any rule clause. The field list and every number is an assumption, because SR 26-2 prescribes none. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is records or usage rows, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Input validation** (empty, truncated, wrong-type or deeply nested input exits 2, never a traceback) | 100 records | 2 | 0.9 | 1 | 180.0 | Built in prototype |
| 2 | **Completeness** (required fields, legal values, placeholder words) | 100 records | 3 | 0.9 | 2 | 135.0 | Built in prototype |
| 3 | **Agent fields and evidence by tier** (tools, permission scope, human approval; evaluation, independent review, fallback) | 100 records | 3 | 0.8 | 2 | 120.0 | Built in prototype |
| 4 | **Staleness** (review and evaluation dates against a cadence per tier) | 100 records | 3 | 0.7 | 2 | 105.0 | Built in prototype |
| 5 | **CI output** (text and GitHub annotations, `--fail-on` levels, escaped strings) | 100 records | 2 | 0.9 | 2 | 90.0 | Built in prototype |
| 6 | **Coverage** (an unlisted system, a retired system still running, a production system with no traffic) | 105 usage rows | 3 | 0.7 | 3 | 73.5 | Built in prototype |
| 7 | **Model-id change** (the recorded model id against what recent traffic ran on) | 105 usage rows | 2 | 0.6 | 2 | 63.0 | Built in prototype |
| 8 | **Staged agent skill** (tells an agent how to run the command and read the exit status) | 100 records | 1 | 0.6 | 2 | 30.0 | Staged in `skill/`, not installed |
| 9 | **Owner-still-employed check** against a staff list | 100 records | 2 | 0.4 | 3 | 26.7 | Sequenced for v0.2 |
| 10 | **Scheduled feeds** for the inventory export and the gateway usage export | 105 usage rows | 2 | 0.6 | 5 | 25.2 | Sequenced for v0.2 |
| 11 | **Findings history and sign-off** (who read which finding, and when) | 100 records | 2 | 0.6 | 6 | 20.0 | Sequenced for v0.3 |
| 12 | **Bulk-refresh detector** (a review date refreshed on many records at once) | 3 records | 3 | 0.4 | 3 | 1.2 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Inventory Check | What they fear |
| --- | --- | --- | --- |
| **Inventory owner** | Owner | A list of gaps by system and by test, and a non-zero exit only when something is wrong. | A check that flags clean records until owners stop reading it. |
| **Model risk reviewer** | Relies on the inventory; co-owns cadences | To know which records are incomplete, overdue or contradicted by traffic before a review. | A PASS read as a statement that the inventory is right. |
| **Business owner of a system** | Named on a record | A finding that says what to fix and by when, without a meeting. | A finding raised on a quarterly process that is quiet by design. |
| **Technical owner of a system** | Named on a record | The model id and the tools on the record to match what runs. | An agent recorded as generative to skip the agent fields. |
| **Gateway / platform team** | Runs the usage export | A plain CSV contract, and a system id and a model id on every call. | A tool that depends on fields the gateway cannot guarantee. |
| **Security / CISO** | Approver | Nothing leaving the boundary, no vendor key in the path, strings from input kept out of logs. | Another tool holding a copy of the inventory and the traffic. |
| **Internal audit** | Reader | A path from a finding to the inventory, usage export, as-of date and cadences it used. | Cadences changed between two runs with no record. |

---

## User stories (top 4)

1. **As the inventory owner**, I want a system that calls a model and has no record to fail the check, so a system cannot run for months unlisted.
2. **As a model risk reviewer**, I want records that are overdue for review or evaluation, or whose model id traffic contradicts, listed before a review, so I start with the gaps and not the full file.
3. **As the owner of an agentic system**, I want the check to tell me which of the tools, permission scope or human approval fields is missing, so I can fix the record in one pass.
4. **As internal audit**, I want each finding tied to the as-of date, the inventory, the usage export and the cadences, so I can reproduce it later.

---

## KPIs

**North star:** share of in-scope AI systems whose record passes the tests on the latest run, with the run recorded and every FAIL finding read by a named person. Target 🔴 100%.

**Inputs (leading):**
- Systems that call a model with a record in the inventory (the prototype has 🟢 100 records and 105 usage rows, from `data/README.md`).
- Gateway calls that carry a system id and a model id (target: every call).
- Records with a named business and technical owner and a review date inside the cadence.
- Cadences and windows with a named approver (prototype: every value an assumption).

**Outputs (lagging):** prototype baselines from the planted set.
- Defective records flagged. 🟢 51 of 57 with the tests, against 8 of 57 for a blank-cell check (`step_04_with_checks.py`, `step_02_blank_cells.py`).
- Clean records flagged. 🟢 2 of 43, both quarterly processes; 25 of 27 look-alike clean records left alone (`step_04_with_checks.py`).
- Records a person has to open. 🟢 53 of 100 (`step_04_with_checks.py`).
- Shadow systems named from the usage export. 🟢 4 of 7 (`step_04_with_checks.py`).
- Known misses. 🟢 6 of 57 defective records pass: 3 novel placeholders and 3 bulk-refreshed review dates (`step_04_with_checks.py`).
- Findings overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the check on one real inventory and gateway export with `--fail-on never`. Print the findings, fail nothing, and compare with what the owner already knew. |
| 1: Calibration | 4w | Read the false alarms and the misses against real records. Set the cadences with the model risk team, extend the placeholder list and agree the field list. |
| 2: Coverage enforced | 4w | Fail the step on an unlisted system and on a record that is incomplete. Staleness stays advisory. |
| 3: Staleness enforced and scheduled | 6w | Fail on overdue review and evaluation. Schedule the inventory and usage exports. Install the skill in one agent harness and test it. |
| 4: History and sign-off | 8w | Record each run and who read each finding. Add the owner-still-employed check and test the interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should a system with no inventory record fail?** In the prototype it does; that is my policy, not a measurement of harm. Recommendation: keep FAIL, and let the owner mark a system as sanctioned and pending a record for a bounded time, recorded with an approver.
2. **Where do the cadences come from?** Tier 1 to 4 gaps of 365, 270, 180 and 90 days are my assumptions; SR 26-2 prescribes none. Recommendation: start there, then set them with the model risk team against the bank's own tiers.
3. **What does a REVIEW finding oblige?** Recommendation: an owner reply within an agreed time, decided with the model risk team before enforcement, not after.
4. **How are quarterly processes treated?** Two clean quarterly processes look idle and are flagged, and the record cannot say otherwise. Recommendation: add an expected-quiet field with an approver, rather than loosening the 90 day window for everyone.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, no state.** The tool reads an inventory, an optional usage export and an as-of date, and returns findings and a decision. Production adds scheduled exports, a findings history and telemetry, all designed and none built.
- **Never silent.** A missing, empty, malformed or deeply nested input exits 2. A run without a usage file says which tests did not run, and a usage file that matches no record says so.
- **Strings from input are data.** Annotations and text output escape control characters, so a hostile system id cannot forge a workflow command or a report line.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the flagged count shows in the diff.

**What is next.** Run it on one real inventory the owner is allowed to share; add a check for owners no longer in the staff list; decide with the model risk team what a REVIEW finding obliges.

**What would have to be true before a pilot.**
- The inventory can be exported as a JSON list with one object per system and the field names the tool reads.
- The gateway logs a system id and a model id on every call, and the inventory uses the same ids.
- A named person owns the field list and the cadences, and the model risk team has agreed them.
- One real inventory and export can be shared, so the rules are tested on real records and not on mine.
- The team agrees which decision level fails the step.

---

*This PRD names [11 TierGate](../11-tiergate-ai-usecase-intake/), [16 ControlMap](../16-controlmap-ai-obligation-crosswalk/) and [22 ShadowScan](../22-shadowscan-unsanctioned-ai-discovery/) as designed interlocks (🔴 designed, none built). The tier scale and the stale-evidence idea are copied from 11 and 16, not read from their files.*
