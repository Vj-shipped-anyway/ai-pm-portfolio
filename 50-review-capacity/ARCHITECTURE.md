# Architecture: Review Capacity

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/review_capacity.py`, that reads one row of assumptions per queue (or fits them from a case log), models the share of late cases, raises the reviewers at the desk until the wait target and the utilization cap hold, converts seats to a roster and compares it with a headcount, run here over 13 synthetic queues and 7049 replayed cases. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![review-capacity flow](./assets/review-capacity-flow.svg)

---

## 1. Logical architecture

Review Capacity is a function between a review tool's case log and a headcount request: assumptions in, seats and a roster out. It schedules no shift and judges no review.

Eight components: four decide the outcome, four support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `rc-ingest` | Loads a queues file or a case log and rejects bad input with a one-line message. The design adds a scheduled export from the review tool. | Python 3.9+, standard library. Prototype: `read_rows`, `load_queues`, `load_log`, `number`, `queue_id`, `parse_days` | Yes, by refusing: exit 2 | No |
| `rc-fit` | Measures arrival rate, opening batch, handling time and the spread of gaps and handling from logged days. | Python. Prototype: `fit_queue`, `run_fit` | Yes, it sets the inputs | No |
| `rc-policy` | The wait target, share, utilization cap and shrinkage per queue, with a reason. Moves only by a reviewed change. | Reviewed config in a repo (design). Prototype: columns in the queues file, `DEFAULT_TARGETS` | Yes, config | Stateful, in git |
| `rc-sizer` | Models the late share (live tail plus opening-batch drain) and raises seats until both limits hold. | Python. Prototype: `erlang_c`, `offered_load`, `late_share`, `required_seats` | Yes | No |
| `rc-roster` | Converts seats to a roster, compares with the headcount held and sets the exit code. | Python. Prototype: `roster`, and the status and exit code in `render_size`, `run_size` | Yes | No |
| `rc-backtest` | Replays the latest days against the recommended seats and reports the late share. Design only; the prototype's `replay` serves the step scripts and the golden test. | Python job (design) | No | No |
| `rc-report` | Prints the table or GitHub annotations and escapes untrusted strings. | Python. Prototype: `render_size`, `safe`, `escape_annotation` | No | No |
| `rc-ledger` | One record per sizing: inputs, targets, seats, roster, tool version. Design only. | PostgreSQL plus object storage (design) | No | Stateful |

**What decides the outcome.** The input check, the targets, the fit, the late-share model and the roster comparison. The report, back-test and ledger carry or check the result. The tool reads times as logged and does not judge a review.

**Repo structure** (production shape):

```
review-capacity/
├── sizing/     # ingest.py, fit.py, sizer.py, roster.py, report.py
├── policy/     # targets and shrinkage per queue, changed by pull request
├── backtest/   # replay job
├── ledger/     # sizing record writer
├── infra/      # terraform for gcp, aws, azure
├── docs/runbooks/
└── tests/      # unit, golden, hostile strings
```

---

## 2. Physical and deployment architecture

One short-lived job runs when a headcount review opens or a queue owner asks. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Sizing job (`rc-ingest` to `rc-report`) | Cloud Run job | ECS Fargate task | Container Apps job | Stateless, one pass, short-lived |
| `rc-backtest` | Cloud Scheduler to a Cloud Run job | EventBridge Scheduler to Fargate | Container Apps job on a schedule | Runs after the latest days land |
| Case-log store | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Versioning keeps the bytes a sizing used |
| `rc-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The tool must never silently pass. A missing, empty, truncated or mistyped input does not become "covered": it ends the run with exit 2 and a one-line reason. A queues file with no `current_headcount` prints that nothing was compared and does not call the queue covered.

| Failure | Behavior | Alert |
| --- | --- | --- |
| File missing, unreadable, empty, header only, a missing column, a truncated row or extra fields | Exit 2, one line naming the file and row | P3 |
| A value that is not a number or is out of range; a `queue_id` that fails the pattern or repeats; a queue with no arrivals and no batch; a non-integer headcount | Exit 2 naming the row and column | P3 |
| Inputs that would need more than 500 reviewers | Exit 2: check the inputs | P3 |
| `fit` on a window with no cases, fewer than 2 cases, or an unreadable `--days` | Exit 2 naming the queue | P3 |
| `fit` with too few live arrivals to measure gaps | Runs, sets `arrival_cv` to 1 and prints a note | P4 |
| No `current_headcount` given | Runs, says no headcount was compared | None |
| Ledger or back-test unavailable (design) | The table and exit code stand; the gap is listed | P3 |

**Latency.** I have not timed the prototype. 🔴 Design target: a sizing within 10 minutes of a case-log export landing. Recovery is a re-run from the same versioned log and targets.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Case | `queue_id`, `day`, `arrival_min` | One reviewed case: when it arrived and how long it took | `data/cases.csv`: `queue_id`, `day`, `arrival_min`, `handle_min`, `channel` (`live` or `batch`) |
| Queue assumptions | `queue_id` | Load, spread, targets and headcount | `data/queues.csv`: `hours_open`, `target_wait_min`, `target_share`, `max_utilization`, `shrinkage`. The tool's own file adds `arrivals_per_hour`, `opening_batch`, `handling_minutes`, `handling_cv`, `arrival_cv`, `current_headcount` |
| Sizing result | `queue_id`, run | Load, seats, utilization, mean-only seats, roster, held, status | Prototype: `size` output, `src/out/step_04_queues.csv` |
| Planted truth | `queue_id` | Planted kind and the true number of reviewers | `data/queue_truth.csv`: `true_seats`, late share and utilization at that number. Exists only because the data is synthetic |

**Retention** is a design choice, not a measurement; confirm it against the bank's own schedule. 🔴 Design default: sizing records 7 years, in PostgreSQL and archived with a retention lock; the log and targets a record used are kept as long, so it can be reproduced.

**Lineage.** A roster traces back in three hops: the record names the queue, targets, tool version and the hash of the log or queues file; the versioned store returns those bytes; and the arithmetic is deterministic (no sampling, clock or random draw), so re-running `required_seats` reproduces the seats. In the prototype the trace is a row of `step_04_queues.csv`.

**Deliberately not stored.** Case content, customer data, reviewer names and reviewer decisions. The tool needs only the queue, the day, an arrival minute, a handling time and a channel.

---

## 4. Security architecture

**Identity and roles.** The job runs under the platform's workload identity and has no user account of its own.

| Role | Can | Maps to |
| --- | --- | --- |
| `rc:runner` | Read the log and targets; write a sizing record | The job's service identity |
| `rc:approver` | Approve a target, cap or shrinkage change, never their own | Headcount approver or second line |
| `rc:auditor` | Read records and the target history | Internal audit |
| `rc:admin` | Manage roles, buckets and the ledger | Platform engineering lead |

**Secrets.** The tool holds none and calls no model; the job uses workload identity.

**Data classification and what leaves the boundary.** Arrival minutes, handling times and queue ids are internal. In the prototype nothing leaves the machine. In the design the table, the exit code and the ledger write leave the job.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in an input field echoed into a log or annotation | A `queue_id` or path holding a newline and text that looks like a workflow command | `queue_id` must match a pattern of letters, digits, spaces, underscores, dots and hyphens; `safe` escapes `%`, carriage return and newline and caps the length; `escape_annotation` does the same for annotations. `tests/test_cli.py` covers a hostile queue id and a hostile string in an annotation |
| A target is loosened to make a queue look covered | `target_wait_min` raised, `max_utilization` set to 0.99 | Pull request with a different approver; every record stores the targets it used |
| The log is edited | Slow cases deleted before `fit` | Versioned storage; the record stores the log hash |
| Sizing inputs are read as a finding on review quality | The utilization cap quoted as evidence | The README and the table state that the cap is a policy choice |

---

## 5. Operational architecture

**SLIs.** Sizings per queue per quarter; input rejections; seats against the back-test (late share on the latest days against the allowed share); queues short against the headcount held; log age; time to a sizing. Prototype baseline: 🟢 12 of 13 queues meet both limits on the replay (`step_04_with_review_capacity.py`).

**SLOs (all 🔴 design targets, none measured).**
- A sizing within 10 minutes of the log landing.
- Every headcount request carries a sizing record that names its targets.
- Every back-test result is read by a named person within one business day (planning estimate).
- 99.9 percent of sizings written to the ledger.

**Alerts.** P3: repeated rejections on one queue, or a back-test late share above the allowed share on a sized queue. P4: a weekly digest of queues short against the headcount held.

**Runbooks** (one page each, in `docs/runbooks/`):
- `queue-short.md`: read the assumptions, check the log window, decide to hire or relax a target in writing.
- `backtest-late.md`: compare fitted and latest days, refit on a longer window, resize.
- `changing-a-target.md`: propose, re-run the planted set, compare with the golden numbers, approve with a reason.
- `input-rejected.md`: find the row named and ask for a corrected export.

**Ownership.** The queue owner owns the sizing and runbooks, the approver the targets, the workforce planner shrinkage, the platform team the job. Nobody is paged for a short queue; the headcount review is the alert.

**Change control.** Targets and shrinkage are versioned. A change needs a proposer and a different approver, with a reason. Before merge, the planted set is re-run against `tests/test_golden.py`, so a change that moves the sizing shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites nothing: I did not build this against a published standard or a regulator's text.

- **What the design does.** It keeps every target in a reviewed config with a reason and stores the targets used with each sizing, so the number can be reproduced and challenged.
- **What it does not claim.** Any alignment with, or conformity to, a standard or a rule, and any statement about how many reviewers a regulation requires. I have not read or mapped any source.

---

## 7. What is deliberately not here

- **Priority classes, skill routing, abandonment and time-of-day staffing** beyond the opening batch. The replay is first come first served with identical reviewers.
- **Review quality.** Nothing measures whether a reviewer who runs near the cap reviews worse, so the cap is a policy choice.
- **Bursty arrivals.** 🟢 One bursty queue is still one reviewer short, 5 where 6 were needed (`step_04_with_review_capacity.py`). The gap statistic does not see busy and quiet spells well.
- **Change after the history.** 🟢 A queue whose volume rose gets 4 reviewers where 5 were needed (`step_04_with_review_capacity.py`).
- **A proven variability term.** I wrote it from the standard form and have not checked it against the original papers; 13 queues cannot settle it.
- **Shift scheduling and cost.**

---

## Appendix: sample contract

```bash
python3 review_capacity.py size queues.csv --fail-on short --format text
python3 review_capacity.py fit caselog.csv --days 1-10 > queues.csv
```

`size` prints one row per queue with `load`, `seats`, `util`, `mean-only`, `roster`, `have` and a status of ok or SHORT by N. Exit status: 0 when every queue with a headcount is covered, 1 when one is short, 2 for bad input.
