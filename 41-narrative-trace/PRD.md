# PRD: narrative-trace

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a financial-crime operations review. It is not a record of a PRD landed at a named bank. The rules, the planted narrative set and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | narrative-trace: a command-line check that reads a case narrative and a transactions file, traces every sentence to the transaction it cites, and prints each as traced, unchecked or not traced |
| **Owner** | The financial-crime operations lead who owns the narrative review step, with the engineer who builds the tooling around it as co-owner of the rules |
| **Stage** | Portfolio prototype on synthetic data; no Action or service is staged |
| **Primary user** | The financial-crime operations lead who owns the narrative review step |
| **Secondary users** | The engineer who builds the tooling around the review step; the reviewer who reads the narrative before it is filed; the case analyst who wrote it; internal audit |
| **Problem** | A case narrative states amounts, dates, counterparties and counts. A reviewer confirms each one by opening the transaction behind it. When a sentence cites no record, cites a record that does not exist, or states a figure the record does not show, the reviewer finds out only by reading all of it. In the planted set, 🟢 a process with no trace stops 0 of 140 planted defects before a reviewer reads them (`step_01_no_trace.py`). |
| **Solution** | Splits a narrative into sentences, keeping abbreviations such as "Inc." and a citation placed after the period intact. Resolves each `[txn: ID]` against a transactions file, and against one case when asked. Compares the amount, date, counterparty, direction, channel and count in the sentence with the cited records. Prints each sentence as traced, unchecked (cites a record, states nothing comparable) or not traced, and exits non-zero at a chosen level, with GitHub annotations on request. |
| **North-star metric** | Share of narratives sent to review with every sentence either traced or listed for the reviewer to read, and a recorded run. Target 🔴 100%. Today in this model: nothing checks a citation before the reviewer. |
| **Measured metrics (synthetic)** | 🟢 120 of 140 planted defects flagged; 10 of 268 fine sentences flagged; 158 of 408 sentences left for a person to read instead of 408; the known passes are 12 laundered and 8 mixed-record (`step_04_with_trace.py`). |
| **Modeled metrics** | 🟡 Utility (120/140 − 44/140) × 1,000 = 543 defective sentences a year flagged beyond what a missing-bracket pattern flags, assuming 1,000 defective sentences reach review each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The data and the rules share an author, so the numbers are a ceiling, and the sentences are template-built and more regular than an analyst's prose. Mitigation: run it on one real narrative set an institution may share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The tool cannot tell an unsupported claim from a fine connecting sentence when neither states a comparable fact. 🟢 Both come back unchecked: 12 planted defects and 16 fine sentences (`step_04_with_trace.py`). Mitigation: list unchecked sentences for the reviewer rather than pass them, and let the team choose `--fail-on unchecked` after seeing what a missed sentence costs. |
| **Risk #3** | A reviewer who sees "traced" reads the sentence less closely. 🟢 20 of 140 defects pass by default (`step_04_with_trace.py`). Mitigation: the output says traced means the stated facts match the cited records, not that the narrative is complete, and the known passes are named in the README. |
| **Out of scope** | Judging whether a narrative is complete, persuasive or ready to file; reading implied meaning; any model call; filing; hosting; a staged Action. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is sentences or narratives, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Citation resolve** (no citation, an ID not in the file, an ID from another case: not traced) | 408 sentences | 3 | 0.9 | 1 | 1101.6 | Built in prototype |
| 2 | **Rounding and sums** (read an amount to the precision written; accept the sum of cited records) | 408 sentences | 2 | 0.7 | 1 | 571.2 | Built in prototype |
| 3 | **Fact compare** (amount, date, counterparty, direction, channel, count against the cited records) | 408 sentences | 3 | 0.8 | 2 | 489.6 | Built in prototype |
| 4 | **Sentence splitter** (abbreviations, initials, decimals, citation after the period, blank line) | 408 sentences | 2 | 0.9 | 2 | 367.2 | Built in prototype |
| 5 | **Input validation** (empty, truncated, wrong-type or duplicate input exits 2, never a traceback) | 40 narratives | 2 | 0.9 | 1 | 72.0 | Built in prototype |
| 6 | **Relative-date and amount-in-words reader** ("the next day", "nine thousand") | 408 sentences | 1 | 0.4 | 3 | 54.4 | Sequenced for v0.2 |
| 7 | **CI output** (text and GitHub annotations, `--fail-on` levels, escaped strings) | 40 narratives | 2 | 0.9 | 2 | 36.0 | Built in prototype |
| 8 | **Reviewer worklist** (the sentences left to read, as a task in the review queue) | 40 narratives | 3 | 0.6 | 3 | 24.0 | Sequenced for v0.2 |
| 9 | **Run record** (narrative hash, export hash, tool version, verdicts) | 40 narratives | 2 | 0.7 | 4 | 14.0 | Sequenced for v0.3 |
| 10 | **Bind-figures-to-record check** (each amount and date to the record it sits beside) | 8 sentences | 2 | 0.4 | 5 | 1.3 | Queued |
| 11 | **Support for a laundered claim** (a sentence that cites a record and says what no field confirms) | 12 sentences | 2 | 0.2 | 8 | 0.6 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from narrative-trace | What they fear |
| --- | --- | --- | --- |
| **Financial-crime operations lead** | Owner | Fewer sentences for a reviewer to open by hand, and a non-zero exit only when something is wrong. | A check that flags fine sentences until analysts stop citing in the expected form, or ignore it. |
| **Case analyst** | Writes the narrative | A message that names the sentence and the field that disagrees, so the fix takes a minute. | A tool that rewrites or scores their prose, or that blocks a filing on a style point. |
| **Narrative reviewer** | Reads before filing | A short list of what to read first, and a plain statement of what "traced" does and does not mean. | Treating a traced narrative as a correct one. |
| **BSA / AML officer** | Approver of the rule set | A control that tests on every narrative that each statement traces to a record, and a record of what ran. | A control described as more than it is, or rules changed without a record. |
| **Case-system engineer** | Builds the hook | Plain CSV in, plain text out, and exit codes that mean the same thing every time. | A new service with write access to the case system. |
| **Security / privacy officer** | Approver | Narrative text and transactions stay inside the boundary, with no vendor key and no copy kept longer than needed. | Another tool holding a copy of the most restricted case text. |
| **Internal audit** | Reader | A path from a verdict to the exact narrative text, export and tool version it used. | Rules changed silently between two runs. |

---

## User stories (top 4)

1. **As the operations lead**, I want a narrative that cites a record that does not exist, or one from another case, to fail before a reviewer opens it, so the reviewer's time goes to sentences that need judgment.
2. **As a case analyst**, I want each finding to say what the sentence states and what the cited record shows, so I can fix a wrong figure or a wrong ID without a meeting.
3. **As a narrative reviewer**, I want the sentences that cite a real record and state nothing comparable listed apart from the ones that traced, so I know where my reading is the only check.
4. **As internal audit**, I want each verdict tied to the narrative text, the transactions export and the tool version it used, so I can reproduce it later.

---

## KPIs

**North star:** share of narratives sent to review with every sentence either traced or listed for the reviewer to read, and a recorded run. Target 🔴 100%.

**Inputs (leading):**
- Sentences that cite in the `[txn: ID]` form (the prototype narratives use that form throughout, apart from the planted uncited sentences; real analysts will vary).
- Transactions exports that carry `case_id`, so a citation can be held to its own case (prototype: 🟢 478 records in 40 cases, from `data/README.md`).
- Counterparty names that appear in the export, so a name in a sentence can be checked.
- Narratives per week that reach the review step with the check run.

**Outputs (lagging):** prototype baselines from the planted set.
- Planted defects flagged. 🟢 120 of 140 with the trace, against 0 of 140 stopped with no trace (`step_04_with_trace.py`, `step_01_no_trace.py`).
- Fine sentences flagged. 🟢 10 of 268, all of them sentences about an opening date (`step_04_with_trace.py`).
- Sentences a person has to read. 🟢 158 of 408 (`step_04_with_trace.py`).
- Splitter agreement with the planted boundaries. 🟢 408 of 408 (`step_04_with_trace.py`).
- Known miss. 🟢 20 of 140 defects pass by default: 12 laundered and 8 mixed-record (`step_04_with_trace.py`).
- With `--fail-on unchecked`. 🟢 132 of 140 defects flagged and 26 of 268 fine sentences (`step_04_with_trace.py`).
- Reviewer time saved against a hand check: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the check on one team's narratives with `--fail-on never`. Print the findings, fail nothing, and compare with what the reviewers found by hand. |
| 1: Calibration | 4w | Read the false alarms and the misses against real prose. Add the wording the splitter and the readers do not know. Settle the citation form the analysts will use. |
| 2: Citation rules enforced | 4w | Fail the step on uncited, dangling and other-case sentences. Facts stay advisory. |
| 3: Fact rules enforced | 6w | Fail the step on a stated fact that no cited record supports. Unchecked sentences go to the reviewer's worklist. |
| 4: Record and worklist | 8w | Write a run record per narrative. Send the sentences left to read to the review queue. Test the interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should an unchecked sentence fail the step?** In the prototype it is listed and the exit is 0 unless asked. Recommendation: list-only for the pilot, then choose from the real cost of a missed sentence; the planted set moves from 120 to 132 of 140 and from 10 to 26 of 268 fine sentences.
2. **What should happen to a date that is not a transaction date?** The tool reads it as a claim about the cited records, so an opening date is flagged: 10 of 10 such sentences in the planted set. Recommendation: keep the flag in the pilot and add a reviewed phrase list only after real prose shows how often it occurs.
3. **Where does the citation come from?** Analysts type `[txn: ID]` by hand in the prototype's world. Recommendation: have the case tool insert it from a picker over the case's own records, so a typo cannot create a dangling ID.
4. **Should the case always be passed?** Without `--case`, a citation of another case's record is not caught. Recommendation: always pass the case in production, and treat a missing `case_id` column as a configuration error.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, no state.** The check reads a narrative and an export and returns a verdict per sentence. Production adds a read-only ledger extract, a case-tool trigger, a run record and a worklist, all designed and none built.
- **Never silent.** An empty, unreadable or malformed file exits 2 and fails the step, even with `--fail-on never`. A narrative that cites nothing is reported sentence by sentence, with a note, not passed.
- **Strings from input are data.** Annotations and text output escape control characters, so a hostile citation or counterparty name cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the flagged count shows in the diff.

**What is next.** Run it against a narrative set an institution is allowed to share; add a relative-date reader; measure the reviewer time saved against a hand check.

**What would have to be true before a pilot.**
- A named owner decides which level fails the step and which sentences go to the reviewer's worklist.
- The transactions export carries `case_id` and the counterparty names as the ledger spells them.
- Analysts cite in one agreed form, or the case tool inserts the citation.
- One real narrative set can be shared, so the splitter and the readers are tested on real prose and not on my templates.
- Security has agreed that narrative text and transactions stay inside the boundary.

---

*This PRD names [39 Claims Check](../39-claims-check/), [08 OversightOps](../08-oversightops-hitl-workflow/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). It reads no file from any of them.*
