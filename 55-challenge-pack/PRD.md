# PRD: challenge-pack

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a model-risk governance review. It is not a record of a PRD landed at a named bank. The tier table, the evidence windows and the independence rule are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | challenge-pack: a command-line tool, with a staged Agent Skill, that turns a risk tier into a second-line test plan, adds vendor and scope overlays, reconciles the evidence on file and writes a challenge memo per use case |
| **Owner** | The model-risk or AI-governance reviewer who runs second-line challenge, with the head of that function as co-owner of the tier table and the windows |
| **Stage** | Portfolio prototype on synthetic data; the Skill is staged and not loaded into an agent runtime |
| **Primary user** | A model-risk or AI-governance reviewer who challenges use cases |
| **Secondary users** | The first-line owner who has to supply the evidence; the head of the function; internal audit |
| **Problem** | A second-line challenger gets a risk tier and has to decide what to test and what evidence to ask for. In practice the request list is copied from the last review, the tier on the form is taken as written, and the evidence that comes back is checked by eye. Vendor products and use cases outside the model definition get no extra questions, and stale or mis-versioned evidence passes. In the planted set, 🟢 one generic checklist finds 0 of 437 planted evidence defects (`step_01_generic_checklist.py`). |
| **Solution** | Looks the tier up in a tier-to-test-plan table (13 core items, four depths) and raises the tier when a rubric recomputed from the form says so. Adds a vendor overlay and a scope overlay for use cases outside the guidance's model definition. Reconciles each plan item against the evidence row: missing, wrong version, prepared inside the developer's unit (only where an outside preparer is required), stale on the latest of the evidence date and the reaffirmation date. Writes a challenge memo per use case from a template and a summary CSV. Exits 1 when any use case has a gap. A staged Agent Skill wraps the command. |
| **North-star metric** | Share of in-scope use cases whose challenge request list is generated from the recomputed tier and reconciled against dated evidence. Target 🔴 100%. Today in this model: the list is copied and the evidence is read by eye. |
| **Measured metrics (synthetic)** | 🟢 1403 of 1486 owed items asked for (94.4%); 360 of 437 planted defects found (82.4%); 0 of 152 reaffirmed items, 0 of 34 edge-of-window items and 0 of 632 first-line items flagged; known misses named (`step_04_with_the_pack.py`). |
| **Modeled metrics** | 🟡 Utility (360/437 − 87/437) × 40 = 25.0 evidence defects a year found that a presence-only check would miss, assuming 40 evidence defects reach the challenger each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The data and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real evidence export the owner can share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The tier table, the windows and the independence rule are my assumptions, not the guidance's. Mitigation: a second reviewer tries to break the table before it is used to scope a review, and the head of the function owns every change to it. |
| **Risk #3** | The checks read dates, versions and units, never content, and the form is the only source of the tier. 🟢 30 of 32 hollow items pass every check, and 16 of 150 use cases keep a tier below the truth after the recompute (`step_04_with_the_pack.py`). Mitigation: a person challenges the content and signs the memo; a tiering check against a data catalog and a vendor registry is queued. |
| **Out of scope** | Reading the evidence itself; deciding whether a use case may go live; a validation of any model; the tier recompute beyond the rubric (see [11](../11-tiergate-ai-usecase-intake/)); control crosswalks (see [16](../16-controlmap-ai-obligation-crosswalk/)); any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is use cases or items, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Tier recompute** (higher of the declared tier and the rubric on the form) | 150 use cases | 3 | 0.8 | 1 | 360.0 | Built in prototype |
| 2 | **Independence rule** (an item that needs an outside preparer fails when the developer's unit prepared it) | 150 use cases | 2 | 0.8 | 1 | 240.0 | Built in prototype |
| 3 | **Dated, versioned reconciliation** (missing, wrong version, stale on the latest date) | 150 use cases | 3 | 0.9 | 2 | 202.5 | Built in prototype |
| 4 | **Tier-to-test-plan table** (13 core items, four depths, evidence windows) | 150 use cases | 3 | 0.8 | 2 | 180.0 | Built in prototype |
| 5 | **Input validation** (malformed files exit 2, ids cannot name a file, dates checked) | 150 use cases | 2 | 0.9 | 2 | 135.0 | Built in prototype |
| 6 | **Challenge memo and summary CSV** (sponsor text escaped, formulas neutralized) | 150 use cases | 2 | 0.9 | 2 | 135.0 | Built in prototype |
| 7 | **Load the Agent Skill in a runtime and test it** (staged in `skill/`) | 150 use cases | 1 | 0.5 | 1 | 75.0 | Sequenced for v0.2 |
| 8 | **Vendor and scope overlays** (V01, V02, G01) | 91 use cases | 2 | 0.8 | 2 | 72.8 | Built in prototype |
| 9 | **Reaffirmation names who reaffirmed** | 145 items | 2 | 0.5 | 2 | 72.5 | Sequenced for v0.2 |
| 10 | **Tiering check against a data catalog and a vendor registry** | 150 use cases | 3 | 0.6 | 4 | 67.5 | Sequenced for v0.3 |
| 11 | **Pack record** (tier used, plan, gaps, file hashes, tool version) | 150 use cases | 2 | 0.7 | 4 | 52.5 | Sequenced for v0.3 |
| 12 | **Sampled content check for hollow evidence** | 32 items | 3 | 0.3 | 5 | 5.8 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from challenge-pack | What they fear |
| --- | --- | --- | --- |
| **Second-line reviewer** | Owner | A request list they can defend, and a gap list that names the item, the problem and the date. | A tool that lists gaps on items the use case does not owe and costs them credibility with the first line. |
| **Head of model risk or AI governance** | Co-owner of the table | One tier table applied the same way to every use case. | A table that is read as the bank's policy when it is a working assumption. |
| **First-line use case owner** | Supplier of evidence | To know up front what is owed and what counts as current. | A new demand for evidence that is not in the guidance and arrives after the review has started. |
| **Developer / vendor manager** | Informed | Vendor products asked about at the right depth, with the form's vendor field respected. | A vendor field left blank and the use case treated as in-house. |
| **Chief risk officer** | Approver of the tier table | A defensible reason a use case sits at a tier, with the rubric visible. | A tier raised by a tool with no one accountable for the change. |
| **Security / CISO** | Approver | Sponsor-written text kept out of memos as markup and out of logs as commands. | A tool that turns a title in an export into a link, a formula or a workflow command. |
| **Internal audit** | Reader | A path from a memo to the tier used, the table version, the as-of date and the evidence rows. | A pack whose result depends on the clock or the order of the files. |

---

## User stories (top 4)

1. **As a second-line reviewer**, I want the request list to come from the recomputed tier and not the sponsor's, so a use case declared low does not get a shallow review by default.
2. **As a second-line reviewer**, I want every evidence item reconciled for version, date and independence, so a reaffirmed item is accepted and a stale one is named with its date.
3. **As a first-line owner**, I want a memo that lists exactly what is missing or out of date, so I can supply it once.
4. **As internal audit**, I want the same files and the same as-of date to give the same memo every time, so I can reproduce a challenge later.

---

## KPIs

**North star:** share of in-scope use cases whose challenge request list is generated from the recomputed tier and reconciled against dated evidence. Target 🔴 100%.

**Inputs (leading):**
- Use cases with a complete form, including the vendor field and the data class (the prototype set has 🟢 150 use cases, `data/README.md`).
- Evidence rows with a version, a preparing unit and a date (target: every filed item).
- Tier-table changes with a named approver and a reason (target: every change).
- Reaffirmations that name who reaffirmed (target: every reaffirmation; the prototype does not ask).

**Outputs (lagging):** prototype baselines from the planted set.
- Owed items asked for. 🟢 1403 of 1486 with the pack, against 876 for a generic list and 1080 for the tier table alone (`step_04_with_the_pack.py`, `step_01_generic_checklist.py`, `step_02_tier_table.py`).
- Planted defects found. 🟢 360 of 437 (`step_04_with_the_pack.py`).
- Use cases below the true tier after the recompute. 🟢 16 of 150, against 42 declared alone (`step_04_with_the_pack.py`).
- Gaps raised on owed items that are fine. 🟢 0; on items not owed, 6 (`step_04_with_the_pack.py`).
- Known misses. 🟢 77 of 437 defects not found; 30 of 32 hollow items pass (`step_04_with_the_pack.py`).
- Gaps overturned after the first line replies: not measured; the planted set has no first line.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the pack on one real use-case export and one evidence export. Print the memos, send none, and compare with the request list the reviewer would have written. |
| 1: Calibration | 4w | Walk the tier table, the windows and the independence list with the head of the function. Fix the form fields that are left blank. |
| 2: Memos to the first line | 6w | Send the generated request list for new reviews. A reviewer completes and signs each memo. |
| 3: Reconciliation enforced | 6w | Treat a gap as a finding in the review. Table changes go through a pull request with a different approver. |
| 4: Record and tier check | 8w | Write a pack record per run and add the tiering check against a data catalog and a vendor registry. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Who owns the tier table?** It is my assumption in the prototype and the guidance sets no tiers, test lists or windows. Recommendation: the head of the function owns it, with the chief risk officer approving changes, and the table version is stored with every pack.
2. **Does a reaffirmation count as fresh evidence?** In the prototype it does if its date is inside the window and the version matches. Recommendation: keep that rule for the pilot and add a field for who reaffirmed; 🟢 129 of 145 reaffirmed items are false alarms under a date-only rule (`step_03_deficiencies_exposed.py`).
3. **What should happen when the sponsor declares a tier above the recomputed one?** The prototype keeps the higher tier and says so, which raised 6 gaps on items not owed. Recommendation: keep the higher tier, and show the sponsor why the list is longer.
4. **Where should the tier be checked?** The form is the only source here. Recommendation: pair the pack with a tiering check against a data catalog and a vendor registry before relying on the recompute alone.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, no state.** The command reads two exports and an as-of date and writes memos and a summary. Production adds feeds from a registry and an evidence store, a pack record and a loaded Skill, all designed and none built.
- **Never silent.** A missing, empty, truncated or mistyped input exits 2. An evidence file with no rows reports every item missing, and files that do not belong together are named.
- **Strings from input are data.** Memos escape Markdown, annotations escape control characters, and the summary neutralizes formulas, so a sponsor-written title cannot add markup or a command.
- **The date is an argument.** The same files and date give the same bytes, and a golden test pins the planted-set numbers.

**What is next.** Run it against one real evidence export whose owner can share it; add a field for who reaffirmed; ask a second reviewer to try to break the tier table.

**What would have to be true before a pilot.**
- The head of the function owns the tier table and has read the windows.
- The form carries the vendor field and the data class, and the first line knows they decide the plan.
- One real export can be shared, so the numbers are set against real evidence and not mine.
- A reviewer reads every memo before it goes to the first line.
- The team agrees that the pack lists gaps and decides nothing.

---

*This PRD names [11 TierGate](../11-tiergate-ai-usecase-intake/), [16 ControlMap](../16-controlmap-ai-obligation-crosswalk/), [35 TierGate](../35-tiergate/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The tier rubric comes from 11 and is re-implemented here; no code or file is imported from it.*
