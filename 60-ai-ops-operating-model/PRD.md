# PRD: AI ops operating model review skill

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an AI program office review. It is not a record of a PRD landed at a named bank. The checklist, the planted programs and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and the skill has not been run by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | A staged Agent Skill and the command it wraps: the skill collects an artifact reference, a producer and a date for every item a program's tier owes at each of eight stages, and the command prints the stage the evidence reaches and CONFIRMED, OVERCLAIM or UNDERCLAIM against the stage the owner claims |
| **Owner** | The lead of the AI program office, with the second-line reviewer as co-owner of the checklist, the tiers and the cycles |
| **Stage** | Portfolio prototype on synthetic data; the skill is staged and has not been installed in any agent |
| **Primary user** | The lead of an AI program office |
| **Secondary users** | The reviewer who has to say whether a claimed stage holds; the program owner who files the evidence; internal audit |
| **Problem** | A program owner says an AI use case in bank operations is "in rollout" or "handed off". The status deck repeats it. Nobody checks that the proof for each earlier stage exists, is current and was produced by someone other than the builder, so the program office learns the real stage from an incident or an audit. In the planted set, 🟢 the owners' reported stage equals the true stage for 16 of 60 programs and 36 of 60 report a stage above it (`step_01_self_reported_status.py`). |
| **Solution** | A skill walks the eight stages of OPERATING_MODEL.md and records nothing when it gets no reference. A command compares the register with the checklist: tier-aware owed list, placeholder test, future-date test, freshness (1.5 times the cycle) and independence from the builder. It prints the stage reached and the decision, with a first-90-days count, and exits 1 on an overclaim. It names what a person must open: one artifact per stage marked OK, and the sentence to confirm in it. |
| **North-star metric** | Share of AI programs whose reported stage in the status deck equals the stage their evidence reaches, with the audit sample opened for every OK stage. Target 🔴 100%. Today in this model: 🟢 16 of 60 (`step_01_self_reported_status.py`). |
| **Measured metrics (synthetic)** | 🟢 Stage reached equals the planted truth for 45 of 60 programs; 30 of the 36 claims above the truth are flagged and none of the other 24; 19 of 24 lapsed, 9 of 9 blank-reference, 5 of 5 builder-produced and 2 of 2 future-dated items are rejected (`step_04_evidence_review.py`). |
| **Modeled metrics** | 🟡 Utility (45/60 − 19/60) × 40 = 17.3 programs a year read at the right stage that a flat checklist reads wrong, assuming 40 programs under review each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted data and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real register and report the planted numbers and the real numbers apart. |
| **Risk #2** | The command reads the register, not the artifacts. 🟢 It rejects 0 of 19 hollow artifacts, and 6 of the 36 overclaims still pass (`step_04_evidence_review.py`). Mitigation: the audit sample, where a second person opens one artifact per stage marked OK; it is designed and not measured. |
| **Risk #3** | Tiers, cycles and the first-90-days mapping are assumptions, and a cycle that ran late looks stale. 🟢 8 items planted as fine were rejected as stale, and one program landed below its true stage (`step_03_deficiencies_exposed.py`). Mitigation: set cycle days with the item owners, and run in advisory mode first. |
| **Out of scope** | Reading the artifacts; computing the tier (project 11 does that); approving a program; mapping to a rule clause by clause; any model call; a skill marketplace listing. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is programs, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Stage reached and decision** (CONFIRMED, OVERCLAIM or UNDERCLAIM against the claim; exit 1 on an overclaim) | 60 programs | 3 | 0.9 | 1 | 162.0 | Built in prototype |
| 2 | **Freshness test** (older than 1.5 times the item's cycle is STALE) | 60 programs | 3 | 0.8 | 1 | 144.0 | Built in prototype |
| 3 | **Tier-aware owed list** (a tier-1 program is not asked for what only tier 3 owes) | 60 programs | 3 | 0.9 | 1.5 | 108.0 | Built in prototype |
| 4 | **Placeholder and future-date tests** (empty, TBD, n/a and a date after the review date are not evidence) | 60 programs | 2 | 0.9 | 1 | 108.0 | Built in prototype |
| 5 | **Input validation** (empty, truncated, wrong-type input, unknown program or item, a second row for one item: exit 2) | 60 programs | 2 | 0.9 | 1 | 108.0 | Built in prototype |
| 6 | **Independence from the builder** (the builder cannot produce an independent item) | 60 programs | 2 | 0.8 | 1 | 96.0 | Built in prototype |
| 7 | **First-90-days count** (`--window` 30, 60 or 90) | 60 programs | 2 | 0.7 | 1 | 84.0 | Built in prototype |
| 8 | **CI output** (GitHub annotations, `--fail-on`, escaped strings) | 60 programs | 1 | 0.8 | 1 | 48.0 | Built in prototype |
| 9 | **Staged Agent Skill** (eight stages, the questions, no reference means no row) | 60 programs | 3 | 0.5 | 2 | 45.0 | Built in prototype (staged, not installed or run) |
| 10 | **Same reference cited for two items** | 60 programs | 2 | 0.5 | 2 | 30.0 | Sequenced for v0.2 |
| 11 | **Audit sample with a second reader** (one artifact per OK stage, one sentence confirmed) | 36 overclaims | 3 | 0.5 | 3 | 18.0 | Sequenced for v0.2 (designed in the skill, not measured) |
| 12 | **Register with history** (every artifact, not only the latest row) | 60 programs | 2 | 0.5 | 4 | 15.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from the review | What they fear |
| --- | --- | --- | --- |
| **AI program office lead** | Owner | A stage they can state with the evidence behind it, and a list of what is missing for each claim. | Reporting a stage to the board that an incident then disproves. |
| **Program owner** | Files the evidence | To be asked only for what the program's tier owes, and told which item is open. | A flat list that asks a small program for the proof a large one owes. |
| **Second-line reviewer** | Reads the audit sample | A named artifact per stage to open and one sentence to confirm in it. | Treating a complete-looking row as proof when the artifact is hollow. |
| **Platform / build lead** | Builder | A clear rule on which items someone else must produce. | Being the producer of their own validation and not knowing it is not enough. |
| **Internal audit** | Reader | A path from a stage decision to the register rows, the review date and the checklist version. | A register edited after a review to match the claim. |
| **Security / CISO** | Approver | No credential in the review, nothing leaving the boundary, strings from the register kept out of logs and annotations. | A register entry that carries a hostile string into a workflow log. |

---

## User stories (top 4)

1. **As the program office lead**, I want the stage in the deck to be the stage the evidence reaches, so I do not learn the real stage from an incident.
2. **As a program owner**, I want to be asked only for what my tier owes, so a small program is not asked for the proof of a large one.
3. **As a reviewer**, I want an item with no reference to be missing and a placeholder to be rejected, so a spoken status is never counted as evidence.
4. **As internal audit**, I want each decision to name the review date and the items behind it, so I can reproduce it later.

---

## KPIs

**North star:** share of AI programs whose reported stage in the status deck equals the stage their evidence reaches, with the audit sample opened for every OK stage. Target 🔴 100%.

**Inputs (leading):**
- Evidence rows filed per owed item (prototype: 🟢 677 evidence rows on file for 60 programs and 23 checklist items, `step_01_self_reported_status.py`).
- Items with a real reference, a date and a producer (target: every owed item).
- Cycle days agreed with the item owner (target: every item).
- Audit samples opened by a second person (target: one per OK stage).

**Outputs (lagging):** prototype baselines from the planted set.
- Stage matches the planted truth. 🟢 45 of 60, against 16 of 60 for owners' reports and 19 of 60 for a flat checklist (`step_04_evidence_review.py`, `step_01_self_reported_status.py`, `step_02_presence_checklist.py`).
- Overclaims flagged. 🟢 30 of 36, with 0 of 24 other claims flagged (`step_04_evidence_review.py`).
- Programs with every first-90-days item evidenced. 🟢 18 of 60 by the review, 14 of 60 by the planted truth (`step_04_evidence_review.py`).
- Known miss. 🟢 0 of 19 hollow artifacts rejected; 6 of 36 overclaims pass (`step_04_evidence_review.py`).
- Items overturned by an audit sample: not measured; the planted set has no second reader.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the command with `--fail-on never` on one real register. Compare its stage with the one in the deck. Fail nothing. |
| 1: Calibration | 4w | Set tiers, cycle days and independence flags with the item owners. Count items rejected as stale that were fine. |
| 2: Evidence filed through the skill | 6w | Owners file references, producers and dates through the staged skill. No reference, no row. |
| 3: Audit sample | 6w | A second person opens one artifact per OK stage and confirms one sentence. Count the OK stages that fail. |
| 4: Register and decision record | 8w | Keep the register with history, and record each review with the checklist version and the review date. |

---

## Open questions

1. **Is the stage in the deck the owner's claim or the register's finding?** I set it to the register. Recommendation: show both side by side in the deck for a quarter, and use the register's stage for gates only after the audit sample has been run.
2. **How is a late cycle told from a lapsed one?** The 1.5 times factor rejects some fine items and passes some lapsed ones. Recommendation: set cycle days with the item owners, and record a reason when an owner says a cycle ran late.
3. **What should the audit sample cover?** One artifact per stage marked OK is the minimum. Recommendation: open more at tier 3 and above, and start with the items the planted set shows as hollow.
4. **Who produces independent items?** The rule only compares the producer with the builder. Recommendation: name the independent function per item in the checklist, so "someone else" is a role and not a person who happened to sign.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One review per program, stateless.** The command reads three CSV files and a review date and prints a decision. Production adds a register with history and an audit queue, both designed and none built.
- **Never silent.** A malformed file, an unknown program or item, or a second row for one item exits 2. An owed item with no row is MISSING, and an empty register marks every owed item MISSING.
- **The clock is never read.** The review date is an input, so the same files give the same decision on any day.
- **Strings from the register are data.** Output text and annotations escape control characters, so a hostile reference cannot forge a workflow command.

**What is next.** Run the command on one real register the owner may share; test the audit sample on artifacts, with a second reader; add a check that the same reference is not cited for two items.

**What would have to be true before a pilot.**
- A register in which each row has an artifact reference a second person can open.
- Tiers computed by a process the program office trusts, not copied from the sponsor.
- Cycle days and independence flags agreed with the item owners.
- A second reader who will open the audit sample.
- The status deck shows the register's stage beside the owner's.

---

*This PRD names [11 TierGate](../11-tiergate-ai-usecase-intake/), [24 PortfolioBoard](../24-portfolioboard-ai-program-portfolio/), [27 AgentKit](../27-agentkit-reference-agent-and-playbook/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The tier comes from 11 as an input; nothing here reads its files.*
