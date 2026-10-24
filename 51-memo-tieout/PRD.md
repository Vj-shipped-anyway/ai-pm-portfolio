# PRD: Memo Tieout

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a credit-operations review. It is not a record of a PRD landed at a named bank. The marks, the formulas, the rounding rule and the planted memos are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Memo Tieout: a command-line tool that reads a markdown credit memo and a spread exported as CSV and reports each figure in the memo as tied, not tied, unresolved or untied |
| **Owner** | The credit analyst who writes the memo, with the reviewer who signs it off as co-owner of the formula definitions |
| **Stage** | Portfolio prototype on synthetic data |
| **Primary user** | The credit analyst who writes the memo |
| **Secondary users** | The reviewer who signs it off; the spreading team that owns the spread export; second-line credit risk; internal audit; in this portfolio, the owner of a prototype who wants a number in a memo to be rerunnable against the spread |
| **Problem** | A credit memo quotes revenue, EBITDA and a handful of ratios from a spread. The spread is revised after the memo is drafted, a figure is copied from the wrong year, a ratio is worked out on last year's EBITDA, and a coverage ratio is rounded up to look better. Nothing compares the two files, so the reviewer opens both and looks each figure up. In the planted set, 🟢 a process with no check stops 0 of 124 wrong figures before sign-off and 28 of 28 memos carry at least one. |
| **Solution** | Reads the figures in a markdown memo: dollar amounts, percents and multiples, skipping code, links and URLs. Ties each marked figure to one line and one period of the spread, converting units, and recomputes margins and ratios from the spread. Requires the figure to equal the spread value rounded to the decimals the memo shows, with no tolerance. Reports figures with no mark as untied and proposed terms as set aside, prints each problem with its line and column, exits 1 on a problem, and writes GitHub annotations on request. |
| **North-star metric** | Share of figures in memos reaching sign-off that carry a mark and a tie-out result of tied, with no unresolved or untied figure left. Target 🔴 100%. Today in this model: nothing compares the memo and the spread. |
| **Measured metrics (synthetic)** | 🟢 104 of 124 wrong figures caught against 98 of 124 for a value-anywhere script; 12 of 184 fine figures flagged against 107 of 184; a person opens 116 of 308 figures and 104 of the 116 are real problems; 16 of 28 memos still carry a wrong figure, against 28 of 28 (`step_04_with_memo_tieout.py`). |
| **Modeled metrics** | 🟡 Utility (104/124 − 98/124) × 50 = 2.4 more wrong figures a year caught than a value-anywhere script catches, assuming 50 wrong figures reach the check each year. The formulas and the rounding rule are my definitions. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one memo and spread whose owner agrees, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The tool trusts the mark. 🟢 20 of 124 wrong figures still pass: ten `prose_tag_mismatch` figures whose number agrees with its mark under a sentence that names another line, and ten `unparsed_form` figures written in words (`step_04_with_memo_tieout.py`). A mark can also be edited with the number. Mitigation: a check that the words before a mark name the tied line, and a record of the spread hash with each result. |
| **Risk #3** | The formulas are mine, and a bank's spread may define EBITDA and coverage with add-backs. The tool also flags proposed terms that carry no term mark: 🟢 12 of 184 fine figures flagged (`step_04_with_memo_tieout.py`). Mitigation: a reviewed formula file with the credit policy's definitions, and a `term:` mark for proposed terms. |
| **Out of scope** | Whether the spread matches the financial statements; whether the sentence around a figure names the right line; figures written in words; bracketed negatives; ranges; any model call; hosting; a Marketplace listing. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is figures or memos, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Tie a marked figure to a spread line and period** (units converted, rounded half away from zero to the shown decimals, no tolerance) | 308 figures | 3 | 0.9 | 1 | 831.6 | Built in prototype |
| 2 | **Recompute margins and ratios from the spread** (EBITDA, margins, growth, debt to EBITDA, current ratio, coverage, debt to equity) | 308 figures | 3 | 0.8 | 1 | 739.2 | Built in prototype |
| 3 | **Flag figures with no mark; set proposed terms aside** (`term:name`) | 308 figures | 2 | 0.8 | 1 | 492.8 | Built in prototype |
| 4 | **Reviewed formula definitions** (the bank's own EBITDA and coverage, with add-backs) | 308 figures | 3 | 0.6 | 3 | 184.8 | Sequenced for v0.2 |
| 5 | **Accept bracketed negatives and ranges** | 308 figures | 2 | 0.6 | 2 | 184.8 | Sequenced for v0.2 |
| 6 | **Check that the words before a mark name the tied line** (the 10 `prose_tag_mismatch` figures pass today) | 308 figures | 3 | 0.5 | 3 | 154.0 | Sequenced for v0.2 |
| 7 | **Suggest the mark for an untied figure** (the nearest line and period that ties) | 308 figures | 2 | 0.4 | 4 | 61.6 | Sequenced for v0.3 |
| 8 | **Input validation** (empty, truncated, oversize, non-UTF-8, unclosed fence or bad spread row exits 2) | 28 memos | 2 | 0.9 | 1 | 50.4 | Built in prototype |
| 9 | **Figures written in words or with a USD prefix** (the 10 `unparsed_form` figures are never read) | 308 figures | 2 | 0.4 | 5 | 49.3 | Queued |
| 10 | **CI output** (GitHub annotations with line and column, escaped strings) | 28 memos | 1 | 0.8 | 1 | 22.4 | Built in prototype |
| 11 | **Publish a staged GitHub Action** from its own repository | 28 memos | 2 | 0.6 | 2 | 16.8 | Sequenced for v0.2 |
| 12 | **Check record per run** (memo and spread hashes, formulas used, result) | 28 memos | 2 | 0.5 | 4 | 7.0 | Sequenced for v0.3 |

---

## Stakeholder map

| Stakeholder | Role | What they want from Memo Tieout | What they fear |
| --- | --- | --- | --- |
| **Credit analyst** | Owner, writes the memo | A result that names the line and column of every figure that does not tie, and a mark that is quick to write. | Marking every figure by hand for a check that flags terms and years it should have ignored. |
| **Credit reviewer** | Approver | To start from a short list of figures to open, not from two open files. | A pass that hides a wrong figure under a correct-looking mark. |
| **Spreading team** | Provider of the spread | A tool that reads their export as it is, with units declared per row. | A revision to the spread that silently invalidates memos already signed. |
| **Credit risk (second line)** | Reader | A rule they can read, a stated rounding rule and the formulas written out. | Formulas that differ from the credit policy's without anyone having decided so. |
| **Internal audit** | Reader | A path from a result back to the memo and the spread it read. | A result that cannot be reproduced after the spread is revised. |
| **Credit committee** | Consumer of the memo | Confidence that the figures in the memo came from the spread. | Learning of a wrong figure after the decision. |

---

## User stories (top 4)

1. **As a credit analyst**, I want to mark a figure with its spread line and period and have the tool check it, so a copy from the wrong year is caught before the reviewer sees the memo.
2. **As a reviewer**, I want a ratio recomputed from the spread, so a coverage ratio worked out on last year's EBITDA or rounded up does not pass because the number looks plausible.
3. **As a reviewer**, I want an unmarked figure listed as untied, so a number with no source does not slip through as unchecked prose.
4. **As internal audit**, I want each result tied to the memo and spread it read and the formulas it used, so I can reproduce it later.

---

## KPIs

**North star:** share of figures in memos reaching sign-off that carry a mark and a tie-out result of tied, with no unresolved or untied figure left. Target 🔴 100%.

**Inputs (leading):**
- Figures that carry a mark (the prototype set has 🟢 308 planted figures in 28 memos, from `data/README.md`).
- Spread exports with a declared unit on every row (prototype: 20 spreads in `usd_thousands`, 4 in `usd` and 4 in `usd_millions`).
- Formula definitions reviewed against the credit policy (target: every formula; today all are mine).
- Proposed terms marked `term:name` (target: every term).

**Outputs (lagging):** prototype baselines from the planted set.
- Wrong figures caught. 🟢 104 of 124, against 98 of 124 for a value-anywhere script (`step_04_with_memo_tieout.py`, `step_02_value_anywhere.py`).
- Fine figures flagged by mistake. 🟢 12 of 184, against 107 of 184 (`step_04_with_memo_tieout.py`, `step_02_value_anywhere.py`).
- Figures a person has to open. 🟢 116 of 308, and 104 of the 116 are real problems (`step_04_with_memo_tieout.py`).
- Memos that still carry a wrong figure after the check. 🟢 16 of 28, against 28 of 28 with no check (`step_04_with_memo_tieout.py`).
- Known misses. 🟢 20 of 124 wrong figures still pass (`step_04_with_memo_tieout.py`).
- Results overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the tool on one memo and its spread whose owner agrees. Print the result, change nothing, and compare with what the reviewer found by hand. |
| 1: Calibration | 4w | Replace my formulas with the credit policy's definitions. Mark one team's figures as they draft and measure how long a mark takes. |
| 2: Advisory in review | 6w | The result goes to the reviewer with the memo. Exit 1 stays a flag, not a gate on sign-off. |
| 3: Prose and form checks | 6w | Add the check that the words before a mark name the tied line, bracketed negatives and ranges. Re-run the planted set and compare with the pinned numbers. |
| 4: Record and gate | 8w | Write a check record per run with the memo and spread hashes. Test the designed interlocks named in the ARCHITECTURE doc, then decide whether a pass is required at sign-off. |

---

## Open questions

1. **Would analysts write marks as they draft?** I have not asked anyone, so this is hypothetical. Recommendation: try it with one analyst on one memo and measure the time to mark before deciding anything else.
2. **Whose definitions for EBITDA and coverage?** Mine: EBITDA is revenue less cost of goods sold less operating expenses, and debt service coverage is EBITDA over interest plus scheduled principal. Recommendation: move the formulas into a reviewed file with the credit policy's definitions; a line in the spread with the same name already wins over a formula.
3. **What to do about a number that agrees with its mark under the wrong words?** Ten such figures pass every rule. Recommendation: add the sentence-versus-line check and test it on the planted kind before any pilot.
4. **Shown precision or a tolerance?** A 1% tolerance catches 72 of 124 and flags 22 of 184 fine figures, against 88 of 124 and none for the shown precision with the formulas in. Recommendation: keep the shown precision with no tolerance, and mark proposed terms so they are counted and not checked.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One check in the memo workflow.** The tool is stateless: it reads two files and prints a result. Production adds a memo and spread feed, reviewed formula definitions and a check record, all designed and none built.
- **Never silent.** An unreadable, empty, oversize or malformed input exits 2. A memo with no figures, or only terms, says nothing was checked and exits 1; it is not a pass.
- **Strings from input are data.** Text and annotations escape control characters, so hostile text in a memo or a file name cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a change that moves the caught count shows in the diff.

**What is next.** Run it on one memo and spread whose owner agrees; add a check that the words before a mark name the tied line; accept bracketed negatives; publish a staged GitHub Action from its own repository.

**What would have to be true before a pilot.**
- The spread export declares a unit on every row and one period end per period.
- The credit policy's definitions replace my formulas.
- One analyst agrees to mark figures as they draft.
- A reviewer will read the result beside the memo.
- The team agrees that the output is advisory until a pass is shown to match what reviewers find by hand.

---

*This PRD names [39 Claims Check](../39-claims-check/), [77 Spread Extraction Eval](../77-spread-extraction-eval/) and [74 Report Trace](../74-report-trace/) as designed interlocks (🔴 designed, none built). The idea of tying a number to the output that should print it comes from 39; nothing is imported from it.*
