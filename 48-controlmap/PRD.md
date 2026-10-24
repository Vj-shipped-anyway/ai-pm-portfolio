# PRD: controlmap

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a model risk or AI governance review. It is not a record of a PRD landed at a named bank. The dictionary, the planted library and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | controlmap: a command-line tool that reads an obligations file, a controls file and a theme dictionary, and prints COVERED, STALE, PARTIAL, UNCOVERED or UNMAPPED for each obligation, with the reason |
| **Owner** | The model risk or AI governance analyst who prepares the crosswalk, with the second-line reviewer as co-owner of the dictionary and the evidence-age rule |
| **Stage** | Portfolio prototype on synthetic data; nothing is hosted |
| **Primary user** | The model risk or AI governance analyst who prepares the answer |
| **Secondary users** | The second-line reviewer who has to defend the dictionary behind it; the control owners who are asked for evidence; internal audit |
| **Problem** | A bank has to show, for each AI-related obligation, which control meets it and whether the evidence is current. The answer lives in a register column someone typed, or in a sheet that links rows by shared words. Neither knows a control's scope or evidence date, and neither says when it cannot decide. In the planted set, 🟢 reading the typed column as covered or uncovered gives the right status for 22 of 56 obligations (`step_01_register_as_it_stands.py`). |
| **Solution** | Reads an obligations CSV, a controls CSV and a theme dictionary CSV. Matches controls to obligations on dictionary phrases, ignoring retired controls and phrases that are denied ("this is not model monitoring"). Labels each match full, partial or out of scope, and checks evidence age against a multiple of the control's test cycle. Prints one status per obligation with the reason, lists controls that serve nothing and dictionary phrases that matched nothing, and groups stale evidence into one request per control. Exits 1 at a chosen level, 2 on bad input. |
| **North-star metric** | Share of in-scope AI obligations with a status computed from the current register and control library, and a named owner for every status that is not COVERED. Target 🔴 100%. Today in this model: the typed column gives the right status for 🟢 22 of 56 (`step_01_register_as_it_stands.py`). |
| **Measured metrics (synthetic)** | 🟢 Right status per obligation: 42 of 56, against 19 of 56 for a keyword sheet; pair precision 93.0% and recall 75.4%; 13 of 15 orphan controls listed; 14 of 56 statuses wrong, of which 4 are UNMAPPED and said out loud (`step_04_controlmap.py`). |
| **Modeled metrics** | 🟡 Utility (42/56 − 22/56) × 120 = 42.9 obligations with the right status that the typed column would get wrong, assuming 120 obligations in a real register. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The data and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real register and library, have a reviewer label a sample of pairs, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The dictionary is the weak point. 🟢 5 obligations are wrong because controls are worded outside it, and 2 controls that use a dictionary phrase in another sense are linked (`step_04_controlmap.py`). Mitigation: the dictionary has an owner and a change history, and the UNMAPPED, orphan and dead-phrase lists are read before the statuses. |
| **Risk #3** | The 1.5-cycle freshness rule and the as-of date are my assumptions, and fresh evidence does not show that a control works. Mitigation: set the rule per control family with the reviewer, record the as-of date with every run, and say in the output what fresh means. |
| **Out of scope** | Reading obligation text to choose a theme; testing whether a control works; any model call; a regulation text or framework mapping; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is obligations, links or pairs, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Input validation** (empty, truncated, wrong-type, duplicate, a bad date or evidence dated after the as-of date exits 2, never a traceback) | 56 obligations | 2 | 0.9 | 1 | 100.8 | Built in prototype |
| 2 | **Scope check** (full when the control runs in every class the obligation applies to, partial when in some) | 56 obligations | 2 | 0.8 | 1 | 89.6 | Built in prototype |
| 3 | **Dictionary match on active controls** (retired controls skipped and noted) | 56 obligations | 3 | 0.8 | 2 | 67.2 | Built in prototype |
| 4 | **Evidence freshness** (newest evidence against a multiple of the test cycle, giving STALE) | 56 obligations | 3 | 0.7 | 2 | 58.8 | Built in prototype |
| 5 | **Reviewer-labeled sample of pairs** (precision and recall on a real library) | 175 pairs | 2 | 0.6 | 4 | 52.5 | Sequenced for v0.2 |
| 6 | **Text and CSV output with escaping** (control characters made visible, formula-leading cells defused) | 56 obligations | 1 | 0.9 | 1 | 50.4 | Built in prototype |
| 7 | **Orphan, dead-phrase and evidence-request lists** (one ask per control) | 56 obligations | 2 | 0.8 | 2 | 44.8 | Built in prototype |
| 8 | **Reviewed dictionary** (an owner, a change history and a second approver) | 56 obligations | 3 | 0.6 | 3 | 33.6 | Sequenced for v0.2 |
| 9 | **Negation rule** (a denied phrase within three words does not count) | 20 links | 2 | 0.7 | 1 | 28.0 | Built in prototype |
| 10 | **Crosswalk ledger** (files hash, as-of date, grace, statuses per run) | 56 obligations | 2 | 0.7 | 3 | 26.1 | Sequenced for v0.2 |
| 11 | **UNMAPPED status** (a theme with no dictionary row is said out loud, not read as a gap) | 4 obligations | 3 | 0.9 | 1 | 10.8 | Built in prototype |
| 12 | **Wrong-sense check** (flag a control linked to many unrelated themes) | 4 obligations | 2 | 0.3 | 5 | 0.5 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from controlmap | What they fear |
| --- | --- | --- | --- |
| **Model risk / AI governance analyst** | Owner | A status per obligation with the control and the reason, and lists that say what to fix first. | A confident wrong answer, and a dictionary nobody maintains. |
| **Second-line reviewer** | Approver of the dictionary and the evidence rule | A tool that says UNMAPPED instead of guessing, and a record of who changed which phrase. | A phrase used in another sense, linked and never seen. |
| **Control owner (first line)** | Consulted | One evidence request per control, not one per obligation. | Being asked for evidence on a control the tool linked by mistake. |
| **Compliance / obligation owner** | Consulted | Obligations tied to a theme and a status that someone owns. | An obligation shown as covered because a control shares a word with it. |
| **Security / CISO** | Approver | Nothing leaving the boundary, no credentials in the tool, strings from the files kept out of logs and spreadsheets. | A control library, a map of where the weak spots are, ending up somewhere wide. |
| **Internal audit** | Reader | A status that reproduces from the same files, as-of date and evidence rule. | A rule or phrase changed silently between two runs. |

---

## User stories (top 4)

1. **As the model risk analyst**, I want each obligation to show a status, the control and the reason, so I can answer a request without rebuilding a spreadsheet.
2. **As a second-line reviewer**, I want the tool to say UNMAPPED when the dictionary has no phrase for a theme, so I write the row instead of reading a gap that is not one.
3. **As a control owner**, I want one evidence request that lists every obligation my control backs, so I collect once.
4. **As internal audit**, I want a status to reproduce from the files, the as-of date and the grace rule, so I can test the answer later.

---

## KPIs

**North star:** share of in-scope AI obligations with a status computed from the current register and control library, and a named owner for every status that is not COVERED. Target 🔴 100%.

**Inputs (leading):**
- Obligations with a theme and a use-case class list (prototype: 🟢 56 obligations, from `step_01_register_as_it_stands.py`).
- Dictionary phrases that match no active control (prototype: 🟢 5 of 31 phrases, `step_04_controlmap.py`).
- Obligations whose theme has no dictionary row (prototype: 🟢 4 UNMAPPED, `step_04_controlmap.py`).
- Controls with a test cycle and a last-evidence date (prototype: 🟢 55 controls, 51 active and 4 retired, `step_01_register_as_it_stands.py`).
- Dictionary changes approved by a different person (target: every one).

**Outputs (lagging):** prototype baselines from the planted set.
- Right status. 🟢 42 of 56 with the tool, against 22 of 56 for the typed column and 19 of 56 for the keyword sheet (`step_04_controlmap.py`).
- Pairs. 🟢 Precision 93.0% and recall 75.4% (`step_04_controlmap.py`).
- Hard negatives linked. 🟢 0 of the controls that only deny a phrase, the lookalikes, the orphans and the retired controls (`step_04_controlmap.py`).
- Known miss. 🟢 14 of 56 statuses wrong, 10 of them silent (`step_04_controlmap.py`).
- Statuses overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the tool on one register and control library, advisory only. Compare each status with the typed column and with what the analyst already believes. |
| 1: Calibration | 4w | Write the dictionary rows for UNMAPPED themes. A reviewer labels a sample of pairs and reads every control linked to many themes. Set the evidence-age rule per control family. |
| 2: Gaps enforced | 4w | UNCOVERED and UNMAPPED fail the monthly run and need an owner. |
| 3: Evidence requests sent | 6w | STALE and PARTIAL join the enforced set, and each control owner gets one consolidated request. |
| 4: Ledger and export feed | 8w | Write a crosswalk record per run, and read the register and the library from their systems of record instead of files. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Who owns the dictionary?** It decides what a control is read to serve. Recommendation: a second-line analyst owns it, every change is a pull request with a different approver, and the UNMAPPED list is the work queue.
2. **Is 1.5 test cycles the right freshness rule?** It is my assumption. Recommendation: start there, then set it per control family with the reviewer, and record the value with every run.
3. **Should the tool read the obligation statement to choose a theme?** Today the theme is an input and someone assigns it; the keyword sheet reads statements and links 🟢 132 of 195 pairs that are not true pairs (`step_02_keyword_sheet.py`). Recommendation: keep the theme an input until a reviewer-labeled sample shows a reader that beats it.
4. **How is a phrase used in another sense caught?** The tool cannot see it. 🟢 In step 3 one such control is linked to 5 obligations (`step_03_deficiencies_exposed.py`). Recommendation: the reviewer reads any control linked to many unrelated themes, and a flag for that is queued.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, run on a schedule or after an export.** The tool is stateless: it reads three files and an as-of date and returns statuses and lists. Production adds a reviewed dictionary, an export feed and a crosswalk ledger, all designed and none built.
- **Never silent.** A missing, empty or malformed file exits 2. A theme with no dictionary row is UNMAPPED, not UNCOVERED. A control that serves nothing is listed.
- **Strings from input are data.** Control characters are made visible and spreadsheet formula characters are defused, so a hostile cell cannot forge a line or run in a spreadsheet.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the right-status count shows in the diff.

**What is next.** Run it on one real register and library its owner is allowed to share; have a reviewer label a sample of pairs; write the theme rows for whatever comes back UNMAPPED.

**What would have to be true before a pilot.**
- A named analyst owns the dictionary and a different person approves changes.
- Every obligation carries a theme and a use-case class list.
- Every control carries a scope, a test cycle and a last-evidence date.
- One real register and library can be shared, so the rules are tested on real wording and not mine.
- The team agrees which statuses fail the monthly run, and what fresh evidence means for each control family.

---

*This PRD names [16 ControlMap](../16-controlmap-ai-obligation-crosswalk/), [56 AIGF Checks](../56-aigf-checks/) and [44 Inventory Check](../44-inventory-check/) as designed interlocks (🔴 designed, none built). Ideas from 16 are reimplemented here; no file from those projects is read.*
