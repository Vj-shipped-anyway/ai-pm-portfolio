# PRD: report-trace

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a regulatory reporting review. It is not a record of a PRD landed at a named bank. The loan table, the report, the adjustment log and the planted problems are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | report-trace: a command-line tool that records, for every cell of a filed report, the rule and the exact source rows behind it, then checks each cell against the source as it stands today and prints the path back |
| **Owner** | The person who owns a recurring report and has to answer "where does this number come from?", with the reviewer who accepts the answer as co-owner of the report spec |
| **Stage** | Portfolio prototype on synthetic data; the capture is a reference implementation run after the fact, not inside a job |
| **Primary user** | The owner of a recurring report |
| **Secondary users** | The reviewer who has to believe the answer; the data engineer who runs the reporting job; the colleague who asks about one number; internal audit |
| **Problem** | A filed report gives one number per cell. When a reviewer, an auditor or a colleague asks which loans make up a cell, the answer is a hunt: a mapping sheet that may be out of date, a query re-run on a table that has moved since filing, and no way to tell a logged adjustment from an unlogged one. In the planted set, 🟢 0 of 71 filed cells point to a source row, and a reviewer reads 3724 rows of the loan table to find the loans behind one cell (`step_01_no_trace.py`). |
| **Solution** | Captures, for every leaf cell, the rule and the source rows behind it with the fields the rule reads, plus the adjustments logged against it. Explains each filed value as rows plus logged adjustments and names any unexplained amount. Compares the lineage with a current copy of the source: changed rows, missing rows, rows that now fit the rule and were never in the cell; fields the rule does not read are ignored. Checks that totals and ratios foot the filed numbers, and lists open loans that sit in no cell. Prints the path from one cell to its rows, and exits non-zero when a cell needs a person. |
| **North-star metric** | Share of cells in recurring reports whose filed value carries a recorded path to source rows, checked against the source before sign-off. Target 🔴 100%. Today in this model: 0 of 71. |
| **Measured metrics (synthetic)** | 🟢 21 of 21 planted problems found with 0 false alarms among 46 cells; the rows named equal the rows planted on 14 of 14 cells with a source change; a reviewer reads 18 rows instead of 611; the known miss is 4 of 4 wrong source rows that trace cleanly (`step_04_with_lineage.py`). |
| **Modeled metrics** | 🟡 Utility (611 − 18) / 14 × 100 = 4,236 rows a year a reviewer does not have to read, assuming 100 cells a year need a source change explained. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of a capture inside a real job, and the size of the lineage file, have not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real recurring report the owner may share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The source has to be frozen or versioned for the comparison to mean anything. A live ledger that moves every day would flag every cell. Mitigation: the pilot report uses a position table that is corrected in place, and the design stores a versioned source snapshot. |
| **Risk #3** | Lineage shows where a number came from, not whether the source was right. 🟢 4 of 4 cells that hold a wrong source row verify as TRACED (`step_04_with_lineage.py`). The lineage file also grows with the rows behind the report. Mitigation: keep sampling source rows against the upstream system, and size the file on the pilot report. |
| **Out of scope** | Any model call; counts, joins and multi-table lineage; rounding tolerance; deciding whether a source row is right; hosting; wiring the capture into a real reporting job. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is cells, loans or filings, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Input validation** (empty, wrong-type, truncated or duplicate input exits 2, never a traceback; strings from input escaped) | 71 cells | 2 | 0.9 | 1 | 127.8 | Built in prototype |
| 2 | **Trace command** (the path from one cell to its rows, with the rule and the differences) | 71 cells | 2 | 0.8 | 1 | 113.6 | Built in prototype |
| 3 | **Verdict per leaf cell** (TRACED, ADJUSTED, UNEXPLAINED, SOURCE_CHANGED, with the rows named) | 48 cells | 3 | 0.9 | 2 | 64.8 | Built in prototype |
| 4 | **Row-level capture at filing** (rule, rows with the fields the rule reads, adjustments, filed value) | 48 cells | 3 | 0.9 | 3 | 43.2 | Built in prototype (reference implementation, run after the fact) |
| 5 | **Footing check on derived cells** (totals and ratios against the filed inputs) | 23 cells | 2 | 0.9 | 1 | 41.4 | Built in prototype |
| 6 | **Immutable lineage store with a hash kept outside the file** | 71 cells | 2 | 0.6 | 4 | 21.3 | Sequenced for v0.2 |
| 7 | **Versioned source adapter** (a frozen copy of the source at filing) | 71 cells | 3 | 0.5 | 5 | 21.3 | Sequenced for v0.2 |
| 8 | **Capture hook inside the reporting job** | 71 cells | 3 | 0.5 | 8 | 13.3 | Sequenced for v0.2 |
| 9 | **Loans in no cell, and adjustments that match no leaf cell** | 7 loans | 2 | 0.9 | 1 | 12.6 | Built in prototype |
| 10 | **Counts, joins and multi-table lineage** | 70 cells | 3 | 0.4 | 8 | 10.5 | Queued |
| 11 | **Rounding tolerance for ratio cells** | 20 cells | 1 | 0.5 | 2 | 5.0 | Queued |
| 12 | **Sampling of source rows against the upstream system** (the wrong-row case) | 4 cells | 3 | 0.3 | 6 | 0.6 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from report-trace | What they fear |
| --- | --- | --- | --- |
| **Report owner** | Owner | A path from any cell to its rows, available on the day someone asks, with the logged adjustments shown apart from the rows. | A tool that flags every cell after a late load and gets ignored. |
| **Reviewer** | Approver of the report spec | A verdict that says what changed and which rows, so a cell is accepted or opened without a hunt. | Accepting a cell that traces cleanly to a wrong row. |
| **Data engineer** | Consulted | A capture that reads the aggregation the job already does, with no second query path. | A capture that slows the filing run or drifts from the job's own logic. |
| **Colleague asking about one number** | Informed | A short answer: the rule, the rows, the adjustments. | A reply that takes days and still says "it should be". |
| **Security / CISO** | Approver | Loan-level fields held in one place with access control, and nothing leaving the boundary. | A lineage file copied into a chat or a ticket. |
| **Internal audit** | Reader | A record that shows the rows, the adjustments and the source version behind a filed value. | A lineage file edited after the fact, or a source that was overwritten. |

---

## User stories (top 4)

1. **As the report owner**, I want each filed cell to carry the rule and the exact rows behind it, so I can answer "where does this number come from?" without re-deriving it.
2. **As a reviewer**, I want a cell to be called ADJUSTED when its value is rows plus a logged adjustment, and UNEXPLAINED when an amount has neither, so I can tell a documented top-side entry from a hole.
3. **As a reviewer**, I want a changed or missing row, or a late arrival that fits the rule, to be named by its loan id, so I read the cause and not the table.
4. **As internal audit**, I want totals and ratios checked against the filed inputs, and loans that sit in no cell listed, so a footing error or a silently skipped loan does not go unseen.

---

## KPIs

**North star:** share of cells in recurring reports whose filed value carries a recorded path to source rows, checked against the source before sign-off. Target 🔴 100%.

**Inputs (leading):**
- Cells with a recorded rule and rows (prototype: 🟢 48 leaf cells and 23 derived cells in the report, `data/README.md`).
- Source tables that are frozen or versioned at filing (target: every report).
- Adjustments logged against a named cell with a reason (prototype: 🟢 4 logged adjustments, `data/README.md`).
- Open loans in no cell (prototype: 🟢 7, from a blank days-past-due, `data/README.md`).

**Outputs (lagging):** prototype baselines from the planted set.
- Planted problems found. 🟢 21 of 21 (`step_04_with_lineage.py`).
- False alarms among cells that are fine or only explained by the log. 🟢 0 of 46 (`step_04_with_lineage.py`).
- Cells with a source change where the rows named equal the rows planted. 🟢 14 of 14 (`step_04_with_lineage.py`).
- Rows a reviewer reads for those cells. 🟢 18 named against 611 with the mapping sheet (`step_04_with_lineage.py`).
- Known miss. 🟢 4 of 4 wrong source rows trace cleanly (`step_04_with_lineage.py`).
- Cells a reviewer opened and found harmless: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run `build` and `verify` after the fact on one recurring report with a frozen source. Print verdicts, fail nothing, and compare with what the owner already knew. |
| 1: Calibration | 4w | Check the cell rules against the job's own aggregation. Decide which late loads are harmless. Size the lineage file on the real report. |
| 2: Capture at filing | 6w | Add the capture hook to the job so the lineage file is written when the report is filed, and stored with a hash. |
| 3: Verify before sign-off | 6w | Run `verify` before sign-off and fail the step on UNEXPLAINED, SOURCE_CHANGED and DOES_NOT_FOOT. |
| 4: Counts, joins and sampling | 10w | Add count cells and joins. Sample source rows against the upstream system. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should a late loan that fits the rule flag the cell?** In the prototype a row booked after the as-of date is ignored, and a row booked before it but loaded after filing flags SOURCE_CHANGED. Recommendation: keep both, because the second changes what the report would say today.
2. **Where does the capture run?** The prototype runs it after the fact on a snapshot. Recommendation: put it in the job, reading the same aggregation, so the rows are the ones the report used.
3. **Who may log an adjustment?** An adjustment is the only thing that turns UNEXPLAINED into ADJUSTED. Recommendation: an append-only log with an author and a time, reviewed by someone other than the author.
4. **What is the source of truth?** The tool needs a position table corrected in place with later loans appended. Recommendation: if the source is a live ledger, freeze a copy at filing and capture against it.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Capture at filing, verify later.** `build` is the only step that needs the source as it stood at filing; `verify` and `trace` read the lineage file and a current copy. Production adds a capture hook, an immutable store and a decision record, all designed and none built.
- **Never silent.** A missing, empty, truncated or malformed input exits 2. A source that shares no row with the lineage says so on stderr. Loans in no cell and adjustments that match no cell are listed, not skipped.
- **Strings from input are data.** Loan ids, cell ids and adjustment reasons are escaped in text and in annotations, so a hostile string cannot forge a workflow command or an output line.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the found count shows in the diff.

**What is next.** Run it on one real recurring report whose owner can share it; add counts and a join case; test the capture inside a real job and measure its cost.

**What would have to be true before a pilot.**
- The source is a position table that is frozen or versioned at filing.
- The cell rules in the spec match the aggregation the job really runs.
- Adjustments are logged against a named cell, with a reason and an author.
- A named person owns the report spec and will read a SOURCE_CHANGED verdict.
- Loan-level fields can be held in one controlled place.

---

*This PRD names [09 LineageLog](../09-lineagelog-ai-decision-audit/), [51 Memo Tieout](../51-memo-tieout/) and [34 Audit Chain](../34-audit-chain/) as designed interlocks (🔴 designed, none built).*
