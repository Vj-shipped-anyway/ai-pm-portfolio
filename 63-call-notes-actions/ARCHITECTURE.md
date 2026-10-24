# Architecture: call-notes-actions

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/call_notes_actions.py`, that reads call-note sentences and proposed CRM actions, each with a cited sentence and quote, applies five plain-rule checks and prints ACCEPT, REVIEW or REJECT, run here over 120 synthetic notes and 440 candidate actions from a stub extractor. It writes to no CRM and holds no queue. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![call-notes-actions flow](./assets/call-notes-actions-flow.svg)

---

## 1. Logical architecture

call-notes-actions is a function between an extractor and a CRM: two files in, a decision per action and an exit code out. It does not extract, split notes into sentences, judge truth or write anywhere.

Eight components: four decide the outcome, four support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `cn-ingest` | Loads the notes and candidates. Rejects an empty, header-only, truncated, mistyped or duplicate-keyed file with a line number. | Python 3.9+, standard library. Prototype: `load_notes`, `load_candidates`, `InputError` in `src/call_notes_actions.py` | Yes, by refusing: exit 2 | No |
| `cn-ground` | Citation and support: the quote is in the cited sentence, the sentence carries the action type and names the subject. | Python. Prototype: `normalize`, `quote_in`, `ACTION_TYPES` | Yes: REJECT | No |
| `cn-agree` | Slots, owner and modality: the date and amount are in the sentence, the speaker matches the owner, no conditional, negated, past or hedged word. | Python. Prototype: `resolve_dates`, `find_amounts`, `owner_markers`, `MODALITY` | Yes: REVIEW | No |
| `cn-verdict` | Runs the parts in a fixed order, returns one decision with reasons, and maps decisions to an exit code at `--fail-on`. | Python. Prototype: `check_candidate`, `check_all`, `run_check` | Yes | No |
| `cn-report` | Prints text or JSON and escapes untrusted strings. | Python. Prototype: `render_text`, `esc` | No | No |
| `cn-adapter` | Splits notes into sentences with stable ids and feeds the extractor's output in the candidate shape (design). | A job beside the CRM note editor (design) | No, it supplies the input | No |
| `cn-queue` | Holds REVIEW actions for the manager and writes only ACCEPT to the CRM (design). | The CRM's task API and a review queue (design) | Yes, a person decides held actions | Stateful |
| `cn-ledger` | One record per decision: rules version, hashes, reasons (design). Prototype analog: `src/out/step_04_decisions.csv`. | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |

**What decides the outcome.** The input check, the five parts and the verdict. The report, the adapter, the queue and the ledger carry or record the decision, except that the queue is where a person settles a held action. The check reads the cited sentence only: it trusts the sentence split, the lists are mine, and ACCEPT means the sentence says it, not that it is true.

**Repo structure** (production shape):

```
call-notes-actions/
├── check/      # ingest.py, ground.py, agree.py, verdict.py, report.py
├── lists/      # trigger, negation, hedge and past word lists, changed by pull request
├── adapter/    # sentence splitter and extractor feed
├── queue/      # held-action queue and CRM writer
├── ledger/     # decision record writer
├── infra/      # terraform for gcp, aws, azure
└── tests/      # unit, golden (planted-set numbers), hostile strings
```

---

## 2. Physical and deployment architecture

The check is one short-lived process behind the extractor. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Check (`cn-ingest` to `cn-report`) | Cloud Run job | ECS Fargate task | Container Apps job | Stateless, one pass per note batch |
| `cn-adapter` | A function beside the note editor | Same | Same | Sentence ids must match what the manager sees |
| Notes and candidate store | Cloud Storage, versioned, restricted | S3, versioned, restricted | Blob Storage, versioned, restricted | Notes hold client detail, so access is narrow |
| `cn-queue` | The CRM's own task queue | Same | Same | Managers already work there |
| `cn-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The check must never silently pass an action. A missing, empty, truncated or malformed file ends the run with exit 2 and a line number. A candidate the check cannot ground is REJECT or REVIEW, never ACCEPT. The queue writes only ACCEPT (design).

| Failure | Behavior | Alert |
| --- | --- | --- |
| Notes or candidates file missing, empty, header only, unreadable, truncated or missing a column | Exit 2, one line on stderr | P3 |
| A date is not real, a sentence id is not a whole number, or a note, sentence or candidate id repeats | Exit 2 with the line | P3 |
| A candidate names a note that is not in the file | REJECT `note_not_found`. If none match, the report says nothing could be grounded | P4 |
| Unknown action type, or a citation not in the note | REJECT with the reason | P4 |
| No candidates | The report says "no candidates: nothing was checked" and counts notes with no proposed action | P3 if a note had commitments (design) |
| Queue or CRM write fails (design) | Nothing is written. The action stays held and retries | P3 |
| Ledger unavailable (design) | The decision and exit code stand; the record queues locally | P3 |

**Latency.** The prototype is one pass over two small files; I have not timed it. 🔴 Design target: a decision for every candidate of a note within 5 seconds of the extractor output landing.

Recovery is a re-run from the same versioned notes and candidates.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Note sentence | `note_id`, `sent_id` | One sentence and the call date | `data/notes.csv`: `note_id`, `client_id`, `call_date`, `sent_id`, `text`. The check reads `note_id`, `call_date`, `sent_id`, `text` |
| Candidate action | `cand_id` | An action, its slots and the sentence it cites | `data/candidates.csv`: `cand_id`, `note_id`, `action_type`, `owner`, `due`, `subject`, `amount`, `cite_sent_id`, `cite_quote`. Owner, due, subject and amount are optional |
| Decision | `cand_id` | ACCEPT, REVIEW or REJECT and the reasons | Prototype: `src/out/step_04_decisions.csv` |
| Decision record | `decision_id` | Design: rules version, hashes of the note and candidate files, decision, reasons, time | Not built |
| Planted truth | `cand_id` | The planted cause and whether the candidate is valid. Exists only because the data is synthetic | `data/candidate_truth.csv`: `defect`, `valid`, `truth_action_id`; `data/truth_actions.csv`; `data/sentence_roles.csv` |

🔴 Design default retention: decision records are kept 7 years in PostgreSQL, archived to object storage with a retention lock; the notes follow the CRM's own retention and are not copied. Confirm both against the bank's own record-retention schedule.

**Lineage.** A decision traces back in three hops: the record names the candidate, the rules version and the file hashes; `cite_sent_id` and `note_id` return the sentence from the versioned store; and the rules are deterministic, so re-running `check_candidate` reproduces the decision and its reasons.

**Deliberately not stored.** Note text and client names in the ledger, which keeps ids and hashes only. The check does not read `client_id`.

---

## 4. Security architecture

**Identity and roles.** The job runs under workload identity and has no user account of its own. `cn:runner` reads notes and candidates and writes decisions; `cn:owner` proposes list changes; `cn:approver` approves list and policy changes, never their own; `cn:auditor` reads records; `cn:admin` manages roles and buckets.

**Secrets.** The check holds none and makes no model call. The extractor is a separate system with its own keys. The queue writes to the CRM through a scoped service identity (design).

**Data classification and what leaves the boundary.** Call notes are client-confidential and may carry financial detail. In the prototype nothing leaves the machine, and the data is synthetic. In the design three things leave the job: the exit code, ACCEPT writes to the CRM, and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a quote or id echoed into a log | A `cite_quote` holding a newline and text that looks like another log line | `esc` rewrites `%`, carriage return, newline and other control characters, and cuts length. `tests/test_cli.py` covers a hostile string and an escaped path in an error |
| A sentence in the note phrased as a commitment grounds an action | A note line that reads like a task, whoever wrote it | The check cannot tell. Only seven action types exist; each written task carries its cited sentence for the manager to see |
| Word lists edited so that flags stop firing | A hedge word removed | Lists live in the repo under review with a different approver; the golden test shows a changed count |
| An action is attached to the wrong note | A candidate with another client's `note_id` | The cited sentence must exist in that note, else REJECT; ids are checked as keys |
| The extractor changes and the mix of errors shifts | A new model version | Shadow decisions are compared with the planted-set numbers before a new extractor is allowed behind the check |

---

## 5. Operational architecture

**SLIs.** Decisions per kind per day; reasons per decision; input rejections; share of notes with no proposed action; held-queue size and age; minutes per held action; overturned decisions (prototype baseline: 🟢 38 of 256 ungrounded actions written, 175 of 440 candidates needing a person, `step_04_with_grounding_check.py`).

**SLOs (all 🔴 design targets, none measured).**
- A decision for every candidate of a note within 5 seconds of the extractor output landing.
- Every written task carries a decision record.
- Every held action cleared within two business days (planning estimate).
- 99.9 percent of decisions written to the ledger.

**Alerts.** P3: repeated input rejections, a held queue past its age limit, or the ledger down for more than a day. P4: a daily digest of REJECT reasons and notes with no proposed action. Nobody is paged for a REVIEW.

**Runbooks** (one page each, in `docs/runbooks/`):
- `held-queue-growing.md`: read the reasons, find the extractor change or the word that is firing, decide.
- `bad-sentence-split.md`: a citation fails because the split changed; fix the adapter, re-run.
- `changing-a-word-list.md`: propose, re-run the planted set, compare with the golden numbers, approve.
- `new-extractor-version.md`: run it in shadow, compare the mix of errors, then move the check behind it.

**Ownership.** The note-to-CRM owner owns the check and the runbooks. The extractor owner owns the candidate shape. A relationship manager and a product owner review the word lists each quarter. Records and compliance approve the hold policy. Lists and policy are versioned; a change needs a proposer and a different approver, and `tests/test_golden.py` pins the planted-set numbers.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites nothing: I did not read a standard or a regulation for this project, so I claim no alignment. Call notes in a regulated bank carry recordkeeping and privacy duties that I have not touched.

- **What the design does.** It checks that each proposed action points at a sentence, and keeps a record of the decision. That is a product control, not a mapping to any rule.
- **What it does not claim.** It makes no claim of conformity to any standard or regulation, holds no certification, and I have not read or mapped any source.

---

## 7. What is deliberately not here

- **Ungrounded actions that still pass.** 🟢 38 of 256 pass (`step_04_with_grounding_check.py`): clause swaps 13, soft hedges 17 and phrasal negations 8. The rules read a sentence, not a clause, and the last two are word lists of mine.
- **Grounded actions held for nothing.** 🟢 9 of 184: an amount written in words, and a negation about something else in the same sentence.
- **Actions the extractor never proposes.** 🟢 74 of 258 planted actions never come out correctly. The check removes bad actions and cannot add a missing one.
- **Truth.** ACCEPT means the sentence says it. A wrong note produces a grounded wrong action.
- **A sentence splitter, dates beyond the simple forms, other languages.** "Next Friday" reads as "Friday"; "end of the month" is not read; amounts need a dollar sign or a suffix; the lists are English only.
- **Writing to a CRM, a held queue, or a real extractor.** The stub gives each candidate one defect; a real extractor combines them.
- **Recordkeeping and privacy rules for call notes.** Not read, not mapped.

---

## Appendix: sample contract

The call is the prototype's own. Its output for the bundled `--demo` run is under "Run one now" in the README.

```bash
python3 call_notes_actions.py check notes.csv candidates.csv --fail-on reject --format text
```

Notes need `note_id, call_date, sent_id, text` (one sentence per row). Candidates need `cand_id, note_id, action_type, cite_sent_id, cite_quote`, and may add `owner, due, subject, amount`. Exit status: 0 below `--fail-on`, 1 at or above it, 2 for bad input.
