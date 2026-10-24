# PRD: call-notes-actions grounding check

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an operations and relationship-management review. It is not a record of a PRD landed at a named bank. The rules, the planted notes and the rollout plan are mine, and the extractor is a stub I wrote; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | call-notes-actions: a command-line check that, for every CRM action proposed from a call note, looks up the sentence the action cites and prints ACCEPT, REVIEW or REJECT |
| **Owner** | The person who owns the note-to-CRM step, with a records or compliance reviewer as co-owner of the word lists and the hold policy |
| **Stage** | Portfolio prototype on synthetic data against a stub extractor |
| **Primary user** | The person who owns the note-to-CRM step |
| **Secondary users** | The relationship manager who has to trust the tasks in their queue; the team that runs the extractor; internal audit |
| **Problem** | A relationship manager finishes a call and a model proposes CRM tasks from the notes. The tasks look right. Some are not in the note at all, some cite a sentence that says the opposite (a conditional, a refusal, something already done), and some carry a date or an owner the sentence does not give. Written straight to the CRM, they send a client a chaser for a document already delivered. In the planted set, 🟢 256 of 440 candidates are ungrounded and all 256 are written when nothing checks (`step_01_no_check.py`). |
| **Solution** | Takes the notes (one sentence per row) and the proposed actions, each with a cited sentence id and quote. Checks that the citation is in the note, that the sentence carries this kind of action and names its subject, that the due date and amount are in the sentence, and that the owner matches who is speaking. Holds a sentence that is conditional, negated, past or hedged for a person. Prints ACCEPT, REVIEW or REJECT per action and exits non-zero at a chosen level. |
| **North-star metric** | Ungrounded actions written to the CRM, as a share of ungrounded actions proposed. Target 🔴 set against real notes, since the planted share is not a rate. Prototype: 🟢 38 of 256 (14.8%), against 256 of 256 with no check (`step_04_with_grounding_check.py`). |
| **Measured metrics (synthetic)** | 🟢 Ungrounded actions written 38 of 256 against 256 with no check; grounded actions written without a person 175 of 184; the known misses named (clause swaps 13, soft hedges 17, phrasal negations 8) (`step_04_with_grounding_check.py`). |
| **Modeled metrics** | 🟡 Utility (250/256 − 38/256) × 1000 = 828.1 ungrounded actions a year kept out of the CRM that an exact quote match would let through, assuming 1000 ungrounded actions a year are proposed. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set, the stub extractor's error mix and the rules share an author, so the numbers are a ceiling, not a rate on real notes. Mitigation: run it on a few hundred real notes with the real extractor, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The hold queue is the cost. 🟢 175 of 440 candidates need a person, and 9 of 184 grounded actions are held for nothing (`step_04_with_grounding_check.py`). If managers do not clear the queue, the check turns into a delay. Mitigation: measure minutes per held action in shadow before enforcing, and keep `--fail-on reject` until the queue is acceptable. |
| **Risk #3** | A sentence-level check cannot see which clause a date belongs to, and the word lists are English only. 🟢 38 ungrounded actions pass (`step_04_with_grounding_check.py`). Mitigation: review the lists against held and passed samples, and add clause splitting if the real extractor shows clause swaps. |
| **Out of scope** | Finding actions the extractor never proposed; splitting notes into sentences; reading a note for meaning; any model call; writing to a CRM; recordkeeping and privacy rules for call notes. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is candidate actions unless labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Citation check** (the quote is in the cited sentence after normalizing; otherwise REJECT) | 440 candidates | 3 | 0.9 | 1 | 1188.0 | Built in prototype |
| 2 | **Support check** (a trigger word for the action type and the subject named; otherwise REJECT) | 440 candidates | 3 | 0.8 | 1 | 1056.0 | Built in prototype |
| 3 | **Input validation** (empty, truncated, wrong-type, duplicate or binary input exits 2, never a traceback) | 440 candidates | 2 | 0.9 | 1 | 792.0 | Built in prototype |
| 4 | **Decision output** (text and JSON, reasons per action, `--fail-on` levels, escaped strings) | 440 candidates | 2 | 0.9 | 1 | 792.0 | Built in prototype |
| 5 | **Slot check** (the due date and the amount are in the sentence; otherwise REVIEW) | 440 candidates | 2 | 0.8 | 1 | 704.0 | Built in prototype |
| 6 | **Owner check** (first person for the manager, third person for the client; otherwise REVIEW) | 440 candidates | 2 | 0.7 | 1 | 616.0 | Built in prototype |
| 7 | **Modality check** (conditional, negated, past or hedged words; otherwise REVIEW) | 440 candidates | 3 | 0.7 | 2 | 462.0 | Built in prototype |
| 8 | **Calibration on a real extractor and real notes** | 440 candidates | 3 | 0.6 | 3 | 264.0 | Sequenced for v0.2 |
| 9 | **Decision record** (rules version, note and candidate hashes, reasons) | 440 candidates | 2 | 0.6 | 4 | 132.0 | Sequenced for v0.3 |
| 10 | **Held queue for the manager and a CRM write of ACCEPT only** | 175 held | 3 | 0.8 | 4 | 105.0 | Sequenced for v0.2 |
| 11 | **Word-list review** for soft hedges and phrasal negations (17 and 8 pass today) | 25 candidates | 2 | 0.7 | 1 | 35.0 | Sequenced for v0.2 |
| 12 | **Clause splitting** (a date or document taken from the other clause) | 38 candidates | 3 | 0.5 | 3 | 19.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from the check | What they fear |
| --- | --- | --- | --- |
| **Note-to-CRM owner** | Owner | A step that fails on an action nobody said, with the reason, and passes the rest. | A check so noisy that the team switches it off. |
| **Relationship manager** | User of the queue | Only tasks they said, and a short held queue where each item shows its sentence and its reason. | A queue that grows until it is ignored, or a wrong task sent to a client in their name. |
| **Extractor owner** | Consulted | A count by kind of defect, so they can fix the extractor and not only filter its output. | A check that hides the extractor's errors instead of showing them. |
| **Records and compliance officer** | Approver | A path from every written task to the sentence and the rules that allowed it. | A task in the CRM that cannot be traced to anything the client or manager said. |
| **Head of operations** | Sponsor | Fewer wrong chasers and complaints, at a queue size the managers will clear. | Paying for a check whose cost in minutes nobody measured. |
| **Security / CISO** | Approver | Client note text kept inside the boundary, with no model call in the check. | Note text in logs, or a new tool that holds client data. |
| **Internal audit** | Reader | Word lists and hold policy changed only through review, with the old version kept. | Lists edited quietly so that flags stop firing. |

---

## User stories (top 4)

1. **As the note-to-CRM owner**, I want the step to reject an action that cites a quote that is not in the note, so a task the manager never said does not reach the CRM.
2. **As a relationship manager**, I want each held action to show the sentence and the reason, such as a conditional or a due date that is not in the sentence, so I can decide in seconds.
3. **As the extractor owner**, I want the decisions broken down by kind of defect, so I know which errors the check stops and which pass.
4. **As internal audit**, I want each written task tied to the sentence, the decision and the rules version, so I can reproduce it later.

---

## KPIs

**North star:** ungrounded actions written to the CRM, as a share of ungrounded actions proposed. Target 🔴 set against real notes. Prototype: 🟢 38 of 256 (14.8%), against 256 of 256 with no check.

**Inputs (leading):**
- Notes split into sentences with a stable sentence id (the prototype set has 🟢 120 notes and 705 sentences, from `data/README.md`; target: every note).
- Candidates that carry a cited sentence id and quote (target: every candidate).
- Candidates that carry `owner`, `due`, `subject` and `amount` where they apply, since an empty slot is not checked (target: every candidate).
- Word lists reviewed against held and passed samples (target: every quarter, planning estimate).

**Outputs (lagging):** prototype baselines from the planted set.
- Ungrounded actions written. 🟢 38 of 256 with the check, against 256 with none (`step_04_with_grounding_check.py`, `step_01_no_check.py`).
- Ungrounded actions held for a person, and rejected outright. 🟢 166 held and 52 rejected (`step_04_with_grounding_check.py`).
- Grounded actions written without a person. 🟢 175 of 184, with 9 held and none rejected (`step_04_with_grounding_check.py`).
- Candidates a person reads. 🟢 175 of 440, against reading every candidate (`step_04_with_grounding_check.py`).
- Share of held candidates that were ungrounded. 🟢 94.9% (`step_04_with_grounding_check.py`).
- Known miss. 🟢 38 ungrounded actions pass, and 74 of 258 planted actions never come out of the extractor correctly (`step_04_with_grounding_check.py`).
- Minutes per held action: not measured; I did not time anyone.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the check on notes and candidates from the real extractor with `--fail-on never`. Print the decisions, write nothing, and compare with what managers did. |
| 1: Calibration | 4w | Read the passes and the holds. Review the word lists. Measure minutes per held action. Fix the sentence split where it breaks citations. |
| 2: Reject enforced | 4w | Fail the step on REJECT. Write ACCEPT to the CRM. REVIEW waits in a queue a person clears. |
| 3: Hold policy set | 6w | Choose whether held actions wait or write with a flag, from the measured minutes. Name an owner for the word lists. |
| 4: Record and clause rule | 8w | Write a decision record per candidate. Add clause splitting if the real extractor shows clause swaps, and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should a held action wait for a person or be written with a flag?** In the prototype, REVIEW means a person decides; that is my policy, not a measurement. Recommendation: write only ACCEPT, and let REVIEW wait, until shadow data shows the minutes per held action and the queue size.
2. **Who owns the word lists?** The trigger, hedge and negation lists are mine and English only. Recommendation: a named product owner and a relationship manager review them each quarter against a sample of held and passed actions, with every change recorded.
3. **Does clause splitting pay for itself?** It would catch clause swaps, at the price of more held actions. Recommendation: build it only if the real extractor produces them, and measure the change in the queue first.
4. **What counts as a sentence?** The check reads the sentences it is given. Recommendation: use the note editor's own split, record its version, and treat a bad split as a finding.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process behind the extractor.** The check is stateless: it reads two files and returns a decision per action. Production adds a sentence splitter, a held queue with a CRM write and a decision record, all designed and none built.
- **Never silent.** A missing, empty, malformed or truncated file exits 2. A candidate that names no note is a REJECT, not a skip, and an empty candidate list says so.
- **Strings from input are data.** Output escapes control characters and cuts length, so a hostile quote cannot forge a log line.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a change to a word list that moves the written count shows in the diff.

**What is next.** Run it on a few hundred real notes the owner can share, with the extractor that will be used; add clause splitting and see what it costs in held actions; measure how long a person takes per held action.

**What would have to be true before a pilot.**
- The extractor cites one sentence per action, and the notes are split into sentences with a stable id.
- A named person owns the word lists and the hold policy.
- A few hundred real notes can be shared, so the lists and the queue size are set against real notes and not mine.
- Managers agree to clear a held queue, and the minutes per action are measured.
- The team agrees which level fails the step.

---

*This PRD names [08 OversightOps](../08-oversightops-hitl-workflow/), [04 EvalForge](../04-evalforge-llm-eval-platform/) and [01 HalluGuard](../01-halluguard-bank-chatbot-safety/) as designed interlocks (🔴 designed, none built). This folder shares no code with them and reads none of their files.*
