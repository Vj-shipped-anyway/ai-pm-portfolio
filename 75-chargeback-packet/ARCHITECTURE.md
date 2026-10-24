# Architecture: chargeback packet check

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/chargeback_packet.py`, that takes a dispute case and its packet, looks up the evidence list for the reason code, runs the response clock, checks that the documents agree with the case and prints READY, FIX or LATE, run here over 100 synthetic dispute cases. Nothing below is claimed as deployed or load-tested. No CI wrapper or export adapter is built. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![chargeback-packet flow](./assets/chargeback-packet-flow.svg)

---

## 1. Logical architecture

The check is a function in the send step: a case file, an evidence list and a check date in, a decision out. It does not open a document, predict an outcome or file a response.

Eight components: six decide the outcome, two support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `cp-ingest` | Loads the case file and the evidence list. Rejects empty, wrong-type, truncated input, an unknown reason code or a bad date with a one-line message. | Python 3.9+, standard library. Prototype: `load_rules`, `validate_rules`, `validate_case`, `parse_date` in `src/chargeback_packet.py` | Yes, by refusing: exit 2 | No |
| `cp-rules` | The evidence list: reason codes, windows, slots with either-or `accept` lists, the page limit, two document-type lists. Changes only by a reviewed change. | A reviewed JSON file (design). Prototype: `data/rules.json` | Yes, config | Stateful, in git |
| `cp-completeness` | Reports each required item with no accepted document, naming the alternatives; notes a document type on no list. | Python. Prototype: the `completeness` branch of `check_case` | Yes | No |
| `cp-clock` | Due date from the receipt date plus the window, days left against the check date (draft) or the sent date (sent packet), last day counting. | Python. Prototype: the `clock` branch of `check_case` | Yes | No |
| `cp-consistency` | Reference, date, amount and page-count checks on the documents. | Python. Prototype: the `consistency` branch of `check_case` | Yes | No |
| `cp-verdict` | LATE if the window has closed, else FIX if any problem, else READY; exit 1 when any packet is not READY. | Python. Prototype: the `state` line of `check_case`, `run_check` | Yes | No |
| `cp-report` | Prints findings, days left and the summary line. Escapes and cuts untrusted strings. | Python. Prototype: `render`, `clock_phrase`, `safe` | No | No |
| `cp-ledger` | One record per decision, and counts off the decision path (design). Prototype analog: the files step 4 writes to `src/out/`. | PostgreSQL plus object storage with a retention lock, OpenTelemetry (design) | No | Stateful |

**What decides the outcome.** The input check, the evidence list, the three checks and the verdict. The report and the ledger carry or record the decision. The checker reads labels, dates, references, amounts and page counts, so a document with the right label and the wrong content passes.

**Repo structure** (production shape):

```
chargeback-packet/
├── check/      # ingest, completeness, clock, consistency, verdict, report
├── rules/      # one reviewed evidence list per acquirer, changed by pull request
├── intake/     # export adapter for open disputes
├── ledger/     # decision record writer
├── infra/      # terraform for gcp, aws, azure
└── tests/      # unit, golden (planted-set numbers), hostile (injection strings), clock boundaries
```

---

## 2. Physical and deployment architecture

The check is one short-lived process in the step before a packet is sent, plus a scheduled pass over open drafts. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Check process | Cloud Run job, scheduled | ECS Fargate scheduled task | Container Apps job | Stateless, one pass, runs on a timer over open drafts and on demand before a send |
| `cp-rules` | A file in the rules repo | Same | Same | A list change lands in the same history as a code change |
| Case export | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Versioning keeps the exact bytes a decision used |
| `cp-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The check must never silently pass. A missing, empty, truncated or mistyped input does not become READY: it ends the run with exit 2 and a one-line reason. An empty case list says nothing was checked. A document type on no list is a note, not a pass.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Case or rules file missing, empty, truncated, or the wrong type; deeply nested JSON | Exit 2, one line on stderr | P2 if repeated, else P3 |
| Unknown reason code, a date that is not a calendar date, a received date before the purchase, a sent date before the receipt | Exit 2 naming the case and the field | P3 |
| A bad `--as-of` date | Exit 2 | P3 |
| An empty list of cases | Exit 2: "nothing was checked" | P3 |
| A document type on no list for the reason code | A note: the type counts for nothing; a required item still shows as missing | P4 |
| Ledger unavailable (design) | The decision and exit code stand; the record queues locally | P3 |

**Latency.** The prototype is one pass over small files; I have not timed it. 🔴 Design target: a decision on every open dispute within 15 minutes of a case being created or changed (planning estimate).

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Evidence list | reason code | Name, window in days, slots (`id`, `label`, `accept`, `required`) | `data/rules.json`: `reason_codes`, `max_pages`, `after_purchase_types`, `amount_types` |
| Case | `case_id` | The dispute and its packet | `data/cases.json`: `case_id`, `reason_code`, `order_id`, `txn_date`, `received_date`, `amount_cents`, `submitted_date`, `docs` |
| Document | `doc_id` | Metadata only | `doc_id`, `doc_type`, `ref_id`, `doc_date`, `pages`, and `amount_cents` on order records and billing histories |
| Decision record | `decision_id` | Design: list version and hash, case hash, check date, state, findings, days left, tool version, time | Prototype: `src/out/step_04_decisions.csv`, `src/out/step_04_summary.json` |
| Planted truth | `case_id` | The fault planted into a good packet | `data/case_truth.csv`: `planted_kind`, `truth_class`, `visible_in_metadata`. Only because the data is synthetic |

**Retention** is a design choice, not a measurement: 🔴 7 years by default for decision records and the list version a decision used, in PostgreSQL archived to object storage with a retention lock. Confirm it against the bank's own schedule.

**Lineage.** A decision traces back in three hops: the record names the case, the list version and the check date; the versioned export returns the case bytes; and the rules are deterministic, so re-running `check_case` with the same check date reproduces the findings. In the prototype the trace is a row of `step_04_decisions.csv`.

**Deliberately not stored.** The documents themselves, customer names and card numbers. The check needs a label, a reference, a date, a page count and, on two document types, an amount.

---

## 4. Security architecture

**Identity and roles.** The check runs under the platform's workload identity and has no user account of its own.

| Role | Can | Maps to |
| --- | --- | --- |
| `cp:runner` | Read the case export and the list; write a decision record | The scheduler's service identity |
| `cp:approver` | Approve a list change, never their own | Merchant-services reviewer |
| `cp:auditor` | Read decisions, findings and list history | Internal audit |

**Secrets.** None. The check never calls a model or a card network; the job identity reaches the export and the ledger through workload identity with no static keys.

**Data classification and what leaves the boundary.** Case ids, order ids, amounts and dates are confidential. Document files never reach the check. In the prototype nothing leaves the machine. In the design three things leave the job: the exit code, the finding lines and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a case id, document id or type echoed into output | A `doc_type` holding a newline and text that looks like a decision line | `safe` writes control characters as escapes and cuts long text. `tests/test_cli.py` covers a hostile string in a log line and a hostile reason code in an error |
| The list is edited so a gap goes away | A required slot flipped to optional | Pull request with a different approver; the record stores the list version; a golden test shows a changed FIX count |
| The check date is moved to make a late packet look on time | `--as-of` set to an earlier day | The scheduled run sets the date itself; a sent packet is judged on its own sent date; the record stores the date |
| A wrong file carries the right label | A document from another case, or an unreadable scan | The checker cannot see this. The design keeps a person opening such packets and adds a hash or page-count check later |

---

## 5. Operational architecture

**SLIs.** Decisions per state per week; input rejections; drafts with 3 or fewer days left; time from case change to decision; share of sent packets with a recorded decision; packets a person opens. Prototype baseline: 🟢 0 of 43 ready packets flagged (`step_04_with_check.py`).

**SLOs (all 🔴 design targets, none measured).**
- A decision on every open dispute within 15 minutes of a change.
- Every sent packet carries a decision record.
- Every FIX with 3 or fewer days left is read by a named person the same business day (planning estimate).
- 99.9 percent of decisions written to the ledger.

**Alerts.** P2: repeated input rejections, or the scheduled pass not run for a day. P3: a FIX with 3 or fewer days left, a LATE on an open draft, or the ledger down for more than a day. P4: a daily digest of notes.

**Runbooks** (one page each, in `docs/runbooks/`):
- `fix-with-few-days.md`: find the missing or wrong item, get it, re-run.
- `late-packet.md`: confirm the window, tell the manager, record the decision to send or not.
- `changing-the-list.md`: propose, re-run the planted set, compare with the golden numbers, approve.
- `input-rejected.md`: read the one-line reason, fix the export.

**On-call and ownership.** The merchant-services manager owns the evidence list and the runbooks. The packet owner clears findings. The platform team owns the job and the stores. The reviewer approves list changes.

**Change control.** The list and the rules are versioned. A change needs a proposer and a different approver. Before merge the planted set is re-run and compared with `tests/test_golden.py`, so a change that moves a count shows in the diff. Rollout is shadow, calibration, then hold on FIX, as the PRD lays out.

---

## 6. Alignment and posture

Nothing is cited. The README's "Aligned to" section says it plainly: I did not read any card network's rules, reason-code list or published deadlines for this build, so the codes RC-01 to RC-06 and everything attached to them are my own.

- **What the design does.** It applies a reviewed evidence list and a clock to each packet before it is sent, and records the decision. That is an engineering control, not a claim about any scheme.
- **What it does not claim.** It makes no claim of conformity to any scheme, holds no certification, and I have not read or mapped any network's rules.

---

## 7. What is deliberately not here

- **Reading the documents.** 🟢 9 of 9 wrong-file packets pass as READY (`step_04_with_check.py`): a document from another case, or an unreadable scan, with the right label, reference, date and page count.
- **Real lists and deadlines.** The reason codes, lists, windows and the page limit are invented. Load the one your acquirer publishes before relying on any output.
- **Weekends, holidays and time zones.** The window is counted in calendar days; there is no extension rule.
- **More than one reason code per case,** second presentment, pre-arbitration, or the strength of a document. A weak document and a strong one are both READY.
- **File size or format.** It checks page counts only.
- **Predicting a win, filing the response, or any model call.** READY means the checker found nothing wrong that it can see.
- **Rates on a real queue.** The recipe for a good packet and the rules share an author, so the numbers are a ceiling. Hosting is not built.

---

## Appendix: sample contract

The call is the prototype's own. Its output for the bundled `--demo` run is under "Run one now" in the README.

```bash
python3 chargeback_packet.py check cases.json --rules my_rules.json --as-of 2026-03-31
```

`cases.json` holds one case or a list. A case carries `case_id`, `reason_code`, `order_id`, `txn_date`, `received_date`, `amount_cents`, `submitted_date` (empty while a draft) and `docs`, each with `doc_id`, `doc_type`, `ref_id`, `doc_date`, `pages` and, on order records and billing histories, `amount_cents`. A finding line reads `[missing_evidence      ] delivery proof: need one of delivery_tracking, digital_access_log`. Exit status: 0 when every packet is READY, 1 when any is FIX or LATE, 2 for bad input.
