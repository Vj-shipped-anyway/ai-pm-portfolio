# Architecture: dispute-clock

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/dispute_clock.py`, that reads a policy file of clocks, a holiday file and a dispute file, steps each due date in business or calendar days from the clock's anchor event, and prints each clock as on time, late, breached, running or not started, run here over 150 synthetic disputes and 524 clocks. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![dispute-clock flow](./assets/dispute-clock-flow.svg)

---

## 1. Logical architecture

dispute-clock is a function between a case system and a queue owner: three files and an as-of date in, a status per clock out. It sends no notice and changes no case.

Eight components: four decide the outcome, four support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `dc-extract` | Pulls the columns the policy names from the case system. Design only. | Scheduled export job. Prototype analog: `data/disputes.csv` | No | No |
| `dc-ingest` | Loads the three files and rejects bad input with a one-line message. | Python 3.9+, standard library. Prototype: `read_rows`, `load_policy`, `load_holidays`, `load_disputes`, `parse_date` | Yes, by refusing: exit 2 | No |
| `dc-policy` | The five clocks and the holiday calendar, each window with a named source. | Reviewed config in a repo. Prototype: `data/policy.csv`, `data/holidays.csv` | Yes, config | Stateful, in git |
| `dc-calendar` | Steps a due date and counts days, in business or calendar days. | Python. Prototype: `is_business_day`, `add_days`, `count_days` | Yes | No |
| `dc-clocks` | Picks the clocks that apply, finds the earliest satisfying event, sets the status. | Python. Prototype: `applies`, `sent_date`, `status_of`, `evaluate_clock`, `evaluate_all` | Yes | No |
| `dc-report` | Prints the lists or GitHub annotations, escaping untrusted strings. | Python. Prototype: `render_text`, `render_github`, `due_soon`, `clean`, `escape_data`, `escape_property` | No | No |
| `dc-ledger` | One record per clock per as-of date. Design only. Prototype analog: `src/out/step_04_clocks.csv`. | PostgreSQL plus object storage (design) | No | Stateful |
| `dc-telemetry` | Counts statuses and rejections, off the report path. Design only. | OpenTelemetry | No | No |

**What decides the outcome.** The input check, the policy and calendar, the day stepping and the status rule. The report, extract, ledger and telemetry carry or record the result. Dates are taken as recorded.

**Repo structure** (production shape):

```
dispute-clock/
├── clock/      # ingest.py, calendar.py, clocks.py, report.py
├── policy/     # clocks.csv and holidays.csv, changed by pull request
├── extract/    # case-system export job and column allow-list
├── ledger/     # clock record writer
├── infra/      # terraform for gcp, aws, azure
├── docs/runbooks/
└── tests/      # unit, golden, hostile strings
```

---

## 2. Physical and deployment architecture

One short-lived job runs after the extract lands. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `dc-extract` and the clock job | Cloud Scheduler to a Cloud Run job | EventBridge Scheduler to an ECS Fargate task | Container Apps job on a schedule | Stateless, one pass, runs where the case system's network path already exists |
| Extract store | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Versioning keeps the bytes a status used |
| `dc-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |
| `dc-telemetry` | Cloud Monitoring | CloudWatch | Azure Monitor | Off the report path |

**Failure behavior (the decision that matters most).** The tool must never silently pass. A missing, empty, truncated or mistyped input does not become "nothing missed": it ends the run with exit 2 and a one-line reason, even with `--fail-on never`. A clock whose anchor date is empty shows as not started, which is a status and not a failure.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Dispute file missing, empty, a column missing or a short row | Exit 2, one line on stderr naming the line | P2 if repeated, else P3 |
| A date not in YYYY-MM-DD, not a real date, or outside 1900 to 2200; a bad `window_class` or `credit_eligible`; an empty or repeated `dispute_id` | Exit 2 naming the line and column | P3 |
| Policy empty, a repeated `clock_id`, a bad `applies_to` or `day_type`, a window not a whole number from 1 to 3650 | Exit 2 with the reason | P3 |
| An event date after the as-of date, or no clock applies to any dispute | Exit 2: the extract is newer than the as-of date, a date was mistyped, or `applies_to` matches nothing | P3 |
| Holiday file empty, or a due date reaches a year with no holiday in it | Runs, with a note that says so and gives the count | P3 |
| Ledger or telemetry unavailable (design) | The report and exit code stand; the record queues locally and the gap is listed | P3 |

**Latency.** I have not timed the prototype. 🔴 Design target: a clock report within 5 minutes of the case-system extract landing. Recovery is a re-run from the same versioned inputs and as-of date.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Dispute | `dispute_id` | Type, window class, credit eligibility and the date of each step | `data/disputes.csv`: `dispute_id`, `dispute_type`, `window_class`, `credit_eligible`, `first_contact_on`, `logged_on`, `acknowledged_on`, `provisional_credit_on`, `concluded_on`, `final_notice_on`, `info_requested_on`, `info_received_on`. The tool reads the first four plus the date columns the policy names |
| Clock policy | `clock_id` | Who it applies to, window, day type, anchor event, satisfying events | `data/policy.csv`: `clock_id`, `clock_name`, `applies_to`, `window_days`, `day_type`, `anchor_event`, `satisfied_by`, `basis`, `note` |
| Holiday | `date` | A weekday on which the modeled bank is closed | `data/holidays.csv`: `date`, `name` |
| Clock result | `dispute_id`, `clock_id`, as-of date | Start, due date, date done, status, days over or left | Prototype: `src/out/step_04_clocks.csv` |
| Planted truth | `dispute_id`, `clock_id` | The planted status, due date and hard-case tags | `data/truth.csv`: `planted_status`, `planted_due`, `hard_case`. Exists only because the data is synthetic |

**Retention** is a design choice, not a measurement; confirm it against the bank's own schedule. 🔴 Design default: clock records 7 years, in PostgreSQL and archived with a retention lock; the files a record used are kept as long, so it can be reproduced.

**Lineage.** A status traces back in three hops: the record names the dispute, clock, as-of date, policy row and holiday file version, with the extract hash; the versioned store returns those bytes; and the rules are deterministic, so re-running `evaluate_clock` reproduces the due date and status. In the prototype the trace is a row of `step_04_clocks.csv`.

**Deliberately not stored.** Customer names, account and card numbers, narratives and amounts. The extract is an allow-list of the columns above.

---

## 4. Security architecture

**Identity and roles.** The job runs under the platform's workload identity and has no user account of its own.

| Role | Can | Maps to |
| --- | --- | --- |
| `dc:runner` | Read the extract, policy and holiday file; write a clock record | The job's service identity |
| `dc:approver` | Approve a window, holiday or day-type change, never their own | Counsel or compliance |
| `dc:auditor` | Read records and the policy history | Internal audit |
| `dc:admin` | Manage roles, buckets, ledger | Platform engineering lead |

**Secrets.** The tool holds none and calls no model. The job uses workload identity, with no static keys.

**Data classification and what leaves the boundary.** Dispute ids, types and dates are internal, and confidential once tied to a customer. In the prototype nothing leaves the machine. In the design the report, the exit code and the ledger write leave the job.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in an input field echoed into a log or annotation | A `dispute_id` or `clock_name` holding a newline and text that looks like a workflow command | `escape_data` and `escape_property` rewrite `%`, carriage return, newline, colon and comma; `clean` turns control characters into a question mark. `tests/test_cli.py` covers a hostile dispute id, hostile policy text and new lines |
| A window is lengthened or a closure added to make a miss go away | A 7-day window set to 9, or a weekday added to the holiday file | Pull request with a different approver; every record stores the policy row and calendar version |
| A date is edited after the fact | `acknowledged_on` backfilled after a complaint | Versioned extracts; the record stores the extract hash; a changed hash is an alert |
| Customer data rides along in the extract | A free-text narrative column added to the export | The extract reads an allow-list; the tool reads only the columns the policy names |

---

## 5. Operational architecture

**SLIs.** Clocks per status per clock id per day; disputes with at least one missed clock (prototype baseline: 🟢 107 of 150, `step_04_business_day_clocks.py`); running clocks due soon; input rejections; due dates in years the holiday file does not cover; extract age; policy age; time to report.

**SLOs (all 🔴 design targets, none measured).**
- A clock report within 5 minutes of the extract landing.
- Every missed clock appears in the next business day's report.
- Every extract produces a report or a rejection, never nothing.
- 99.9 percent of reports written to the ledger.

**Alerts.** P2: repeated rejections on one queue, or the ledger down over a day. P3: a changed hash for a finished as-of date, an empty holiday file, or due dates in a year with no holiday. P4: a daily digest of clocks due soon.

**Runbooks** (one page each, in `docs/runbooks/`):
- `missed-clock.md`: confirm the dates, tell the analyst, record the outcome.
- `input-rejected.md`: find the line named, ask for a re-run of the extract.
- `changing-a-window.md`: propose, re-run the planted set, compare with the golden numbers, approve with a source.
- `updating-the-holiday-file.md`: add next year's closures each January.

**Ownership.** The operations lead owns the report and runbooks, the case-system owner the extract, counsel or compliance the windows and calendar. Nobody is paged for a missed clock; the report is the alert.

**Change control.** Policy and holiday files are versioned. A change needs a proposer and a different approver, and the policy row names its source. Before merge, the planted set is re-run against `tests/test_golden.py`, so a change that moves the missed count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites nothing: the title says Reg E style because the process has that shape, but I did not read Regulation E for this project, and none of the windows is taken from it.

- **What the design does.** It keeps each window in a policy file with a `basis` column, today an assumption of a modeled bank, so counsel's reading can replace it with a recorded source, and it stores the policy row with every result.
- **What it does not claim.** Any alignment with, or conformity to, a rule or standard. The day counts are mine, and I have not read or mapped any source.

---

## 7. What is deliberately not here

- **Pauses.** 🟢 Four clocks on paused investigations are called missed when the plan says they were not (`step_04_business_day_clocks.py`). The tool does not read `info_requested_on` or `info_received_on`.
- **A check on the recorded window class.** 🟢 DSP-0092 was recorded as extended, so the tool gave it 60 days, but the longer window never applied (`step_04_business_day_clocks.py`).
- **Times of day.** A clock is counted in whole days, so a notice sent after close of business counts for that day.
- **Rollover and restarts.** A calendar due date on a day off stays there, and new facts mid-investigation restart nothing.
- **Proof that the customer was told.** `acknowledged_on` is the date someone entered, taken as recorded.
- **A statement of any rule.** The windows and holiday list are assumptions; a missing closure would make the tool and the truth wrong alike.
- **Hosting or sending notices.**

---

## Appendix: sample contract

```bash
python3 dispute_clock.py check disputes.csv --as-of 2026-09-30 --policy policy.csv --holidays holidays.csv --fail-on missed
```

Exit status: 0 when nothing was missed or with `--fail-on never`, 1 when a clock was missed, 2 for unreadable input. The `--demo` output is in the README.
