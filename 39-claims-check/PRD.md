# PRD: Claims Check

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a documentation review. It is not a record of a PRD landed at a named bank. The planted bullets, the rules and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone; the tool has been run on this portfolio's own README and on nothing else.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Claims Check: a command-line check, with a staged GitHub Action, that reads the numbers after each green circle in a README and fails when one is not printed, as a whole number, in the output of the project's scripts |
| **Owner** | The README's author, with the repository owner as co-owner of the capture step and the matching rules |
| **Stage** | Portfolio prototype on synthetic data (40 projects, 284 planted bullets); the Action is staged and unpublished |
| **Primary user** | Anyone who publishes numbers next to code and wants a reader to be able to rerun a script and see the same number; in this portfolio, the owner of a README with green-tagged figures |
| **Secondary users** | The reviewer of a pull request that edits a README; the reader who reruns a script; internal audit |
| **Problem** | A README says "caught 80 of 98" and the number was right when I typed it. The script moves on, the README does not, and CI stays green because nothing compares the two. A grep for the number does not fix it: it passes a 12 that is really a 112, and it reads a wrapped bullet one line at a time. In the planted set, 🟢 no check stops 0 of 98 wrong bullets, and a grep catches 38 of 98 and flags 19 of 186 fine ones (`step_01_no_check.py`, `step_02_grep_for_the_number.py`). |
| **Solution** | (1) Reads the numbers after each green circle in a README, per paragraph or list item. (2) Skips fenced code, code spans, link targets and URLs. (3) Checks each number against the text the scripts printed: as a whole number, with "a of b" matched as a pair. (4) Prints each unsupported number with its line, exits 1 when there is one, and writes GitHub annotations on request. |
| **North-star metric** | Share of green-tagged numbers on the main branch that a script prints as written. Target 🔴 100%. Prototype today: 80 of 98 wrong bullets caught. |
| **Measured metrics (synthetic)** | 🟢 80 of 98 wrong bullets caught, against 38 of 98 for a grep; 8 of 186 fine bullets flagged, against 19 of 186; a person opens 88 of 284 bullets and 80 of 88 are real problems (`step_04_with_claims_check.py`). |
| **Modeled metrics** | 🟡 Utility (80/98 − 38/98) × 30 = 12.9 wrong green bullets a year caught that a grep would pass, assuming 30 wrong green bullets are written each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one other README whose author agrees and report the planted numbers and the real numbers apart. |
| **Risk #2** | The check proves a number was printed, not that it is the right one. 🟢 All 10 coincidence bullets pass and so do 8 single-digit bullets (`step_04_with_claims_check.py`). Mitigation: a check that the number sits beside the metric name, and the one-digit count reported on every run. |
| **Risk #3** | Stale evidence passes, and the pair rule flags a pair printed on two lines. 🟢 8 of 186 fine bullets are flagged (`step_04_with_claims_check.py`). Mitigation: capture evidence in the same CI job, and print "a of b" in the script. |
| **Out of scope** | Running the scripts; judging whether a printed number means what the sentence says; HTML; nested documents; any model call; hosting. A Marketplace listing is a later, separate step. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is green-tagged bullets, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Whole-number matching** (12 is not supported by a line that prints 112) | 284 bullets | 3 | 0.9 | 1 | 766.8 | Built in prototype |
| 2 | **CI output** (exit codes, GitHub annotations, `--fail-on`, escaped strings) | 284 bullets | 2 | 0.9 | 1 | 511.2 | Built in prototype |
| 3 | **Pair matching** ("a of b" must be printed together) | 284 bullets | 2 | 0.8 | 1 | 454.4 | Built in prototype |
| 4 | **Claim extraction** (numbers after a green circle, wrapped bullets joined, code and links skipped) | 284 bullets | 3 | 0.9 | 2 | 383.4 | Built in prototype |
| 5 | **Input validation** (unreadable, empty, binary or unmatched input exits 2) | 284 bullets | 2 | 0.9 | 2 | 255.6 | Built in prototype |
| 6 | **One-digit skip with a count** (`--min-digits`) | 284 bullets | 1 | 0.8 | 1 | 227.2 | Built in prototype |
| 7 | **Evidence freshness check** (captured output newer than the scripts) | 284 bullets | 3 | 0.6 | 3 | 170.4 | Sequenced for v0.2 |
| 8 | **Publish the Action from its own repository** | 284 bullets | 2 | 0.5 | 2 | 142.0 | Sequenced for v0.2 (staged in `action/`, not published) |
| 9 | **Report numbers hidden in code spans after a green circle** | 284 bullets | 2 | 0.5 | 3 | 94.7 | Sequenced for v0.2 |
| 10 | **Run record** (README and evidence hashes, tool version, counts, result) | 284 bullets | 2 | 0.6 | 4 | 85.2 | Sequenced for v0.3 |
| 11 | **Number beside the metric name** (catches a coincidence) | 284 bullets | 3 | 0.4 | 6 | 56.8 | Queued |
| 12 | **HTML README support** | 284 bullets | 1 | 0.4 | 5 | 22.7 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Claims Check | What they fear |
| --- | --- | --- | --- |
| **README author** | Owner | A failure that names the line and says whether the number is wrong or only unmatched. | A check that flags fine bullets and gets switched off. |
| **Pull request reviewer** | Approver | To stop comparing numbers by hand, and to know what the check could not see. | Trusting a green check on a number that passed by coincidence. |
| **Reader of the README** | Consumer | To rerun a script and see the same number. | Finding out the number moved months ago. |
| **Repository owner** | Owns CI | A step with clear exit codes that reads files and runs nothing. | A new step that executes untrusted scripts. |
| **Security / CISO** | Approver | No model call, no key, and strings from the README kept out of logs. | A tool that echoes input into a workflow command. |
| **Internal audit** | Reader | A path from a published figure to the output that printed it. | A figure that was right once and is never rechecked. |

---

## User stories (top 4)

1. **As a README author**, I want the build to fail when a number after a green circle is not printed by a script, so a stale figure does not sit next to a green tag.
2. **As a pull request reviewer**, I want each failure to name the line and, where one exists, the longer printed figure that contains the number, so I can see a typo or a rounded figure at once.
3. **As a README author**, I want "a of b" matched as a pair, so two printed numbers that never appear together do not pass.
4. **As internal audit**, I want each result tied to the hashes of the README and the evidence it used, so I can reproduce it.

---

## KPIs

**North star:** share of green-tagged numbers on the main branch that a script prints as written. Target 🔴 100%. Prototype baseline: 80 of 98 wrong bullets caught.

**Inputs (leading):**
- Green bullets under the check (prototype: 🟢 284 across 40 projects, `step_01_no_check.py`).
- Numbers a reviewer would otherwise compare by hand (prototype: 🟢 301, `step_01_no_check.py`).
- Evidence captured in the same CI job as the check (target: every repository).
- Numbers skipped for having one digit (prototype: 🟢 16, `step_04_with_claims_check.py`).

**Outputs (lagging):** prototype baselines from the planted set.
- Wrong bullets caught. 🟢 80 of 98, against 38 of 98 for a grep and 0 of 98 for no check (`step_04_with_claims_check.py`, `step_02_grep_for_the_number.py`, `step_01_no_check.py`).
- Fine bullets flagged by mistake. 🟢 8 of 186, against 19 of 186 for a grep (`step_04_with_claims_check.py`).
- Bullets a person opens. 🟢 88 of 284, and 80 of 88 are real problems (`step_04_with_claims_check.py`).
- Flags outside every planted bullet. 🟢 0 (`step_04_with_claims_check.py`).
- Known passes. 🟢 coincidence 10 and single_digit 8 (`step_04_with_claims_check.py`).
- Flags overturned by an author: not measured; the planted set has no author.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 2w | Run the check on one real README with `--fail-on never`. Print the result, fail nothing, and compare with what a reviewer found by hand. |
| 1: Calibration | 2w | Read every flag. Fix READMEs that round or wrap numbers. Print "a of b" in scripts that print the two numbers on separate lines. |
| 2: FAIL enforced | 4w | Fail the step on an unsupported number on one repository. NOTHING CHECKED stays a warning. |
| 3: Action published and wider use | 4w | Publish the Action from its own repository. Add the evidence capture step to each repository that uses it. |
| 4: Freshness, hidden claims and run record | 8w | Add the evidence age check, report numbers hidden in code spans and write a run record. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should NOTHING CHECKED fail the step?** In the prototype it exits 0 and says so in words. Recommendation: warn in shadow, then fail on any repository that publishes green figures, because a README that lost its tags passes silently otherwise.
2. **Should one-digit numbers be checked?** 🟢 Checking them catches all 8 wrong single-digit bullets and flags 16 of 186 fine ones (`step_03_deficiencies_exposed.py`). Recommendation: keep two digits as the default, count the skipped ones on every run, and allow a per-README override.
3. **Where does the evidence come from?** Recommendation: the same CI job reruns the scripts and passes their output to the check, so a stale file cannot pass.
4. **What should happen to a pair printed on two lines?** Recommendation: print "a of b" in the script; `--no-pairs` stays as an escape hatch, not a default.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the pipeline.** The check is stateless: it reads a README and evidence files and returns a result. Production adds an evidence capture step, a run record and a published Action, all designed and none built.
- **Never silent on input.** An unreadable file or an evidence pattern that matches nothing exits 2. A README with no green number says `NOTHING CHECKED` and does not print PASS.
- **Strings from input are data.** Annotations and text output escape control characters, so a hostile path cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, and another runs the tool on its own README.

**What is next.** Run it against one other README whose author agrees; add a check that the evidence files are newer than the scripts; publish the Action from its own repository.

**What would have to be true before a pilot.**
- The scripts that print the numbers are rerun in the same job as the check.
- The README's green tags mean what the portfolio's convention says they mean.
- One other README can be shared, so the rules are tried on text I did not write.
- The team agrees whether NOTHING CHECKED fails the step.

---

*This PRD names [51 memo-tieout](../51-memo-tieout/), [56 aigf-checks](../56-aigf-checks/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The code here imports nothing from them.*
