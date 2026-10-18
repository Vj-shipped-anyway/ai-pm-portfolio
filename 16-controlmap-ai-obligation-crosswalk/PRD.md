# PRD · ControlMap — AI Obligation to Control Crosswalk

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a second-line governance read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an AI governance review in the seat. It is not a record of a PRD landed at a named bank. The theme taxonomy, the status vocabulary, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Obligation statements are paraphrases written for this exercise, not the text of any rule.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | ControlMap — a crosswalk from AI-related obligations to the controls that meet them and to evidence that is still current |
| **Owner** | Head of AI governance (line-1 program), with the second-line model risk reviewer as co-owner of the dictionary |
| **Stage** | Portfolio prototype; second-line governance read |
| **Primary user** | Head of AI governance, who has to answer an exam question such as "which control meets this obligation, and what is the latest evidence" |
| **Secondary users** | Second-line reviewer; control owners; AI product owners; internal audit |
| **Problem** | A modeled bank answers obligations from four frameworks (EU AI Act, model risk guidance, NIST AI RMF, ECOA / Regulation B). Today a spreadsheet maps obligations to controls by shared keywords. It marks obligations "covered" that are not, misses controls that use different words, hides stale evidence and never shows controls that serve no obligation. In the synthetic data, 🟢 the sheet gives the right status to 23 of 48 obligations and marks 42 covered while 40 have any meeting control. |
| **Solution** | A theme dictionary that finds the controls that meet an obligation, a scope check (full or partial), an evidence-freshness check, four statuses (COVERED, STALE, PARTIAL, UNCOVERED) with a reason on every row, an orphan-control list and one consolidated evidence request per theme. |
| **North-star metric** | Share of in-scope obligations that carry a status, a named control and an evidence date no older than the limit, reviewed by a person before the exam-prep cutoff. Target 🔴 100% of in-scope obligations. Today in this model: 0%, the sheet holds no evidence date. |
| **Measured metrics (synthetic)** | 🟢 46 of 48 obligations given the right status (95.8%) against 23 of 48 for the sheet; 🟢 pair precision 97.4% and recall 96.2%; 🟢 10 of 11 orphan controls listed; 🟢 20 evidence requests instead of 48. |
| **Modeled metrics** | 🟡 Utility (46/48 − 23/48) × 288 = 138 obligation entries given the right status, assuming 6 business lines each track their own copy of the list. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on the evidence systems it reads and has not been sized. |
| **Risk #1** | The dictionary is the product, and it was written by the author of the data. 🟢 39 of 50 control-to-theme links rest on a single phrase, and with the first phrase per theme only, pair recall falls to 25.6%. Mitigation: a proposer and a different approver for every phrase, and a sampling step that measures precision and recall against a reviewer's judgment. |
| **Risk #2** | Fresh evidence is read as proof that a control works. It shows only that something was collected recently. Mitigation: the status names what it checked (wording, scope, evidence date) and what it did not (design and operating effectiveness); a COVERED row is not an assurance opinion. |
| **Risk #3** | A phrase match cannot read negation. 🟢 4 wrong links come from 1 control whose description names a dictionary phrase only to say it is not that thing. Mitigation: a reviewer confirms each new link once; links are stored with the phrase that produced them. |
| **Out of scope** | Intake and tiering of use cases (TierGate, 11); decision-level audit (LineageLog, 09); testing whether a control works; writing or interpreting the rules themselves. |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is obligations, controls, themes or roles, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Obligation and control import** (CSV first; framework, theme, applies_to, scope, test cycle) | 48 obligations | 3 | 0.9 | 3 | 43.2 | Built in prototype; v0.1 |
| 2 | **Theme dictionary** (editable table, phrases per theme, versioned) | 48 obligations | 3 | 0.8 | 3 | 38.4 | Built in prototype; v0.1 |
| 3 | **Scope check** (full or partial against the obligation's classes) | 48 obligations | 3 | 0.9 | 2 | 64.8 | Built in prototype; v0.1 |
| 4 | **Evidence-freshness check** (latest item against 1.5 × the test cycle) | 60 controls | 3 | 0.8 | 4 | 36.0 | Built in prototype; v0.1 |
| 5 | **Status view with reasons** (COVERED, STALE, PARTIAL, UNCOVERED) | 48 obligations | 3 | 0.9 | 3 | 43.2 | Built in prototype; v0.1 |
| 6 | **Orphan-control list** | 60 controls | 2 | 0.8 | 1 | 96.0 | Built in prototype; v0.1 |
| 7 | **Dictionary change workflow** (proposer and a different approver) | 20 themes | 2 | 0.6 | 3 | 8.0 | Sequenced for v0.2 |
| 8 | **Calibration sampling** (a reviewer judges a sample of pairs; precision and recall tracked) | 48 obligations | 3 | 0.6 | 4 | 21.6 | Sequenced for v0.2 |
| 9 | **Consolidated evidence requests** (one per theme, to the control owners) | 20 themes | 2 | 0.7 | 3 | 9.3 | Built in prototype as a list; v0.2 for delivery |
| 10 | **Control-owner attestation field** ("does this control run as described?") | 60 controls | 3 | 0.5 | 4 | 22.5 | Sequenced for v0.2 |
| 11 | **TierGate feed for applies_to** (tier sets the classes an obligation applies to) | 48 obligations | 2 | 0.6 | 3 | 19.2 | Sequenced for v0.3 |
| 12 | **Evidence feeds from LineageLog and EvalForge** (system-generated evidence dates) | 10 controls | 2 | 0.5 | 5 | 2.0 | Sequenced for v0.3 |
| 13 | **Exam pack export** (one note per obligation: status, control, evidence) | 2 reviewers | 2 | 0.9 | 2 | 1.8 | Built in prototype as a Markdown download; v0.3 |
| 14 | **Joint coverage** (two partial controls that together span the scope) | 8 obligations | 2 | 0.5 | 5 | 1.6 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from ControlMap | What they fear |
| --- | --- | --- | --- |
| **Head of AI governance** (line-1) | Owner | One answer per obligation: the control, its scope and the date of its latest evidence, with the gaps named before an examiner finds them. | A crosswalk that says COVERED and is wrong in the room. |
| **Second-line reviewer** (line-2) | Co-owner of the dictionary | A record of why each control was linked, a way to correct the dictionary, and no claim that fresh evidence means the control works. | A parallel register that competes with the model inventory; a status read as an assurance opinion. |
| **Control owners** | Consumers of the evidence requests | One request per theme, with the obligations it serves, instead of the same ask from four lists. | Being asked for evidence on a control that is out of scope for the obligation. |
| **AI product owners** | Consulted | To see which obligations apply to their use case and which controls they inherit. | A crosswalk that adds work without telling them what to do. |
| **Internal audit** (line-3) | Reader | Traceability from a status to the pairs, the phrase and the evidence item. | A tool that edits the record it reports on. |
| **Security / CISO** | Approver | Read-only access to evidence metadata; no evidence content copied into another store. | Evidence documents duplicated into yet another system. |
| **Compliance (fair lending)** | Consulted | The adverse-action obligations mapped with scope and evidence dates. | Obligations with specific timing rules treated like generic ones. |

---

## User stories (top 4)

1. **As the head of AI governance**, I want every AI-related obligation to carry a status, a named control and an evidence date, so I can prepare for an exam without rebuilding a spreadsheet.
2. **As a second-line reviewer**, I want to see which phrase linked a control to an obligation, and correct the dictionary, so the crosswalk is a record I can defend and not a black box.
3. **As a control owner**, I want one evidence request per theme with the obligations it serves, so I answer once for record-keeping instead of once per framework.
4. **As internal audit**, I want the controls that serve no obligation listed, and the obligations with no control named as gaps, so the register is complete in both directions.

---

## KPIs

**North star:** share of in-scope obligations with a status, a named control and an evidence date within the limit, reviewed by a person before the exam-prep cutoff. Target 🔴 100%.

**Inputs (leading):**
- Obligations with a theme and applies_to assigned (target: every in-scope obligation).
- Controls with a scope and a test cycle recorded (target: every active control).
- Evidence items with a collection date (target: every control with a test cycle).
- Dictionary phrases with a proposer and a different approver (target: every phrase).

**Outputs (lagging):**
- Obligations given the right status. Prototype baseline: 🟢 23 of 48 with the sheet, 46 of 48 with ControlMap.
- Wrong links per 100 links. Prototype: 🟢 4 of 154 links wrong with ControlMap; 69 of 130 with the sheet.
- Stale obligations found. Prototype: 🟢 7 of 7.
- Orphan controls listed. Prototype: 🟢 10 of 11, with 2 wrongly listed because their wording is outside the dictionary.
- Evidence requests per cycle. Prototype: 🟢 20 against 48.
- Statuses a reviewer overturns after the fact (the known-limit class). Prototype: 🟢 2 obligations, from 6 missed pairs.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Shadow | 4w | Import the obligation register and the control library. Run the dictionary with no output to owners; compare the links with a reviewer's sample. |
| 1 — Calibration | 4w | Reviewers judge a sample of pairs. Track precision and recall per theme. Fix the dictionary where it misses. |
| 2 — Advisory statuses | 6w | Statuses visible to the head of AI governance and the second line. Evidence dates read from the systems that hold them. Owners attest. |
| 3 — Exam-ready | 6w | One note per obligation, orphan list and gap list reviewed each cycle. Consolidated evidence requests go to control owners. |
| 4 — Interlocks | 8w | TierGate feeds applies_to; LineageLog and EvalForge supply system-generated evidence; FairLens supplies adverse-action evidence; IncidentLedger links incidents to controls. |

---

## Open questions

1. **What is the unit of truth: a theme or a sentence?** The prototype judges at the theme level: a control that serves a theme meets every obligation filed under it. Recommendation: keep the theme as the unit for the status, and let a reviewer mark a pair as "not for this sentence" without changing the theme.
2. **Who owns the dictionary?** Recommendation: the second-line reviewer approves, the line-1 program proposes, and every change is a different person from the proposer.
3. **Do two partial controls ever add up to a full one?** The prototype judges one control at a time, and the generator avoids the case. Recommendation: treat joint coverage as a reviewer decision recorded on the obligation, not a rule (backlog item 14).
4. **Who tests that a control works?** ControlMap dates the evidence; it does not test design or operating effectiveness. Recommendation: keep that with the control owner's attestation and the second line's own testing, and show the difference on the status.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Registry:** obligations, controls and evidence metadata imported from the systems that hold them, with their identifiers kept.
- **Dictionary and matcher:** a versioned table of phrases per theme; a matcher that stores the phrase that produced each link.
- **Scope and freshness:** deterministic checks on scope and on evidence dates, re-run when either changes.
- **Storage:** Postgres for obligations, controls, links, statuses and the dictionary; object storage with retention for exam notes.

**Throughput envelope and latency budget.**
- The work is obligations times controls. The prototype checks 2,880 candidate pairs with a plain Python loop. Production volumes have not been sized.
- Refresh: 🔴 design target is a status that is never older than the latest evidence date in the source systems. Not built, not timed.

**Failure modes and degradation strategy.**
- Evidence source unavailable: the status keeps its last evidence date and shows the age of that read; it does not turn COVERED to STALE on a missing feed.
- Theme missing from the dictionary: the obligation shows UNCOVERED with the reason "no phrase group", not a silent gap.
- Obligation with no theme or no applies_to: the status is blocked and the row goes to a reviewer.
- Dictionary change: statuses are recomputed and the rows that changed are listed for review before they are published.

**Migration path from current state.**
- If the crosswalk is a spreadsheet today: keep the identifiers, import both sheets, and run ControlMap beside it in shadow. The differences are the first review list.
- If controls have no recorded scope or test cycle: record them first. The scope check and the freshness check cannot run without them.

**Org dependencies.**
- A second-line reviewer must own the dictionary approval. Without that the dictionary drifts.
- Control owners must record scope and test cycle, and evidence systems must expose collection dates.
- The head of AI governance must accept a status that names a gap, including a theme with no control.

---

*This PRD interlocks with [Project 11 (TierGate)](../11-tiergate-ai-usecase-intake/), [Project 09 (LineageLog)](../09-lineagelog-ai-decision-audit/) and [Project 04 (EvalForge)](../04-evalforge-llm-eval-platform/); FairLens (17) and IncidentLedger (19) are named as designed interlocks (🔴 designed, none built).*
