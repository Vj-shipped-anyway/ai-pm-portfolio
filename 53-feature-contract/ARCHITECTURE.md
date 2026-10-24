# Architecture: Feature Contract gate

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/feature_contract.py`, that reads a contract and one delivery of a feature table, checks structure and values, and prints PASS, WARN or FAIL, run here over 90 synthetic deliveries from three feeds. A GitHub Action is staged in `action/` and has not been published or run on GitHub. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![Feature Contract flow](./assets/feature-contract-flow.svg)

---

## 1. Logical architecture

Feature Contract is a function between a feed and a scoring job: a contract and a delivery in, a decision out. It fetches no data, calls no model and repairs no value.

Eight components: five decide the outcome, three support.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `fc-contract` | The rules for one feature table. Rejects an unknown key or a min above max. Changes by review only. | Python 3.9+, standard library. Prototype: `load_contract`, `check_contract_shape` | Yes, by refusing: exit 2 | Stateful, in git |
| `fc-ingest` | Reads CSV or JSON lines. Rejects an empty, ragged or repeated-column file. | Python. Prototype: `read_batch` | Yes, by refusing: exit 2 | No |
| `fc-structure` | A listed column absent is a FAIL; an unlisted one is a WARN or FAIL by policy; an unparsed value counts against the tolerance. | Python. Prototype: `check_batch`, `parse_value` | Yes | No |
| `fc-values` | Null share over the allowance; a value out of range or list, failing the field past the tolerance. | Python. Prototype: `_check_field`, `_exceeds` | Yes | No |
| `fc-verdict` | Takes the highest level among findings and maps it to an exit code at `--fail-on`. | Python. Prototype: `decide`, `DECISION_RANK`, `run_check` | Yes | No |
| `fc-report` | Prints text or GitHub annotations and escapes untrusted strings. | Python. Prototype: `render`, `escape_annotation`, `safe`, `q` | No | No |
| `fc-action` | Runs the command in a CI job, inputs through environment variables. | Composite GitHub Action, staged in `action/`, not published | No | No |
| `fc-ledger` | One record per decision and counts, off the decision path (design). Prototype analog: `src/out/step_04_decisions.csv`. | PostgreSQL, object storage, OpenTelemetry (design) | No | Stateful |

**What decides the outcome.** The contract, the input check, the structure and value rules, and the verdict. The report, Action and ledger carry or record it. A value inside the declared type, range and null rate is a PASS whatever it means.

**Repo structure** (production shape):

```
feature-contract/
├── gate/       # contract, ingest, structure, values, verdict, report
├── action/     # composite Action wrapper
├── contracts/  # one per feature table, changed by pull request
├── ledger/     # decision record writer
├── infra/      # terraform for gcp, aws, azure
└── tests/      # unit, golden (planted set), hostile (injection strings)
```

---

## 2. Physical and deployment architecture

The gate is one short-lived task that runs after a delivery lands and before the scoring job starts. No server stays warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Gate process (ingest, rules, verdict, report) | Cloud Run job, called by the orchestrator | ECS Fargate task or CodeBuild step | Container Apps job or Azure Pipelines step | Stateless, one pass; the scoring task depends on its exit code |
| `fc-contract` | A reviewed file in the pipeline repo | Same | Same | A range change lands in the same history as the pipeline change |
| Delivery store, `fc-ledger` and counts | Cloud Storage, versioned; Cloud SQL for PostgreSQL; OTel to Cloud Monitoring | S3, versioned; RDS for PostgreSQL; CloudWatch | Blob Storage, versioned; Azure Database for PostgreSQL; Azure Monitor | Versioning keeps the exact bytes a decision used; the platform team already runs the rest |

**Failure behavior (the decision that matters most).** The gate must never silently pass. A missing, empty, truncated or mistyped input does not become PASS and is not skipped: it ends the run with exit 2 and a one-line reason, and that exit fails the step even with `--fail-on never`.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Contract unreadable, not an object, an unknown key, a bad type, min above max or a repeated field name | Exit 2, one line on stderr, step fails | P2 if repeated on one feed, else P3 |
| Delivery missing, empty, header only, a ragged row, a repeated column name, a NUL byte, not `.csv` or `.jsonl`, or a JSON line that is not an object | Exit 2 with the reason | P2 if repeated on one feed, else P3 |
| A listed column is absent | Finding `missing_field`: FAIL | P3 |
| A column the contract does not list, or NA text in a number column | WARN by policy; NA text is a type mismatch against the tolerance | P4 |
| Ledger unavailable (design) | The decision and exit code stand; the record queues locally and the gap is listed | P3 |

**Latency.** The prototype is one pass over a 100-row file; I have not timed it. 🔴 Design target: a decision within 120 seconds of the delivery landing, for the largest delivery a feed produces (size not measured). Recovery is a re-run from the same delivery and contract version.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Contract | `contract`, `version` | The rules for one feature table | `data/contract_*.json`: `contract`, `version`, `unexpected_columns`, `max_bad_rate`, `fields`; per field `name`, `type`, `min`, `max`, `allowed`, `max_null_rate`, `unit`, `description` |
| Delivery | `batch_id` | The header as delivered and the rows | `data/batches.jsonl`: `batch_id`, `feed`, `columns`, `rows`. The command reads a `.csv` or `.jsonl` file |
| Decision record, with its findings (`kind`, `field`, `level`, `count`, `rows`, `reason` from `check_batch`) | `decision_id` | Design: feed, contract name and version, decision, findings, tool version, SHA-256 of the delivery, time | Prototype: `src/out/step_04_decisions.csv`: `batch_id`, `feed`, `change_kind`, `field`, `truth`, `decision`, `findings` |

**Retention** is a design choice, not a measurement; confirm it against the bank's own schedule. 🔴 Design default: decision records and findings 7 years, in PostgreSQL archived to object storage with a retention lock; the deliveries a decision used for as long, in versioned storage, so a decision can be reproduced.

**Lineage.** A decision traces back in three hops: the record names the feed, contract version and delivery hash; the versioned store returns those bytes; and the rules are deterministic, so re-running `check_batch` reproduces the findings. In the prototype the trace is a row of `step_04_decisions.csv`, ending in a findings string such as `above_max:cash_ratio`.

**Deliberately not stored.** Row values. The ledger keeps counts and kinds. The one raw value is the `reason` text, which quotes the first value seen, cut to 40 characters by `q`.

---

## 4. Security architecture

**Identity and roles.** The gate runs under the pipeline's workload identity and has no user account of its own.

Four roles: `fc:runner` (the pipeline identity: reads the delivery and contract, writes a decision record), `fc:approver` (second-line reviewer: approves a contract change, never a widening for their own feed), `fc:auditor` (reads decisions and contract history) and `fc:admin` (platform lead).

**Secrets.** None, and no model call, so no vendor key is in its path. The pipeline identity reaches the store and ledger through workload identity, with no static keys. The staged Action passes inputs through environment variables and puts `--` before the file arguments; `tests/test_cli.py` covers a path that starts with a dash.

**Data classification and boundary.** A real feature table holds applicant, account or transaction attributes, so I would classify a delivery as confidential. In the prototype nothing leaves the machine. In the design three things leave the job: the exit code, the annotations and the ledger write. Annotations quote one value per finding; the design adds a per-field switch to suppress it.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a column name, cell or contract name echoed into a log or annotation | A header holding a newline and text that looks like a workflow command | `escape_annotation` rewrites `%`, carriage return and newline; `safe` and `q` escape control characters and cap length. `tests/test_cli.py` covers a hostile column name, value and contract name |
| A range is widened to make a FAIL go away | `max` raised after a feed starts sending percents | Pull request with a different approver; every decision stores the contract version |
| The delivery is edited after the feed wrote it | A bad value overwritten | Versioned storage; the decision stores the hash; a changed hash is an alert |

---

## 5. Operational architecture

**SLIs.** Decisions per level per feed per week (prototype baseline on harmless synthetic deliveries: 🟢 0 of 43 blocked and 5 of 43 warned, `step_04_with_contract.py`); input rejections; findings by kind and field; FAILs overturned after review; time to decision.

**SLOs (all 🔴 design targets, none measured).**
- Decision available within 120 seconds of the delivery landing.
- Every scoring run of an in-scope model preceded by a gate decision.
- Every FAIL read by a named person within one business day (planning estimate).

**Alerts.** P2: repeated input rejections on one feed, or the ledger down over a day. P3: a FAIL on a production feed, also sent to the feed owner, or a changed hash. P4: a daily digest of WARN decisions.

**Runbooks** (one page each, in `docs/runbooks/`):
- `field-failed.md`: read the finding, ask the feed owner, hold the scoring job or release it with a reason.
- `changing-a-range.md`: pull request, feed owner consulted, second approver, planted set re-run.
- `unexpected-column.md`: harmless, add it to the contract, or move the feed to fail. `input-rejected.md`: find why the input could not be read.

**On-call and ownership.** The pipeline owner owns the runner and runbooks. The model owner owns the contract, with the feed owner as reviewer. The second-line reviewer approves range and tolerance changes.

**Change control.** Rules and contracts are versioned in the repo; a change needs a proposer and a different approver. Before merge the planted set is re-run against the pinned numbers in `tests/test_golden.py`, so a change that moves the stopped count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites nothing: I claim no alignment to a standard or a regulation, and I did not read a source to cite. A data contract is a working pattern, and this is a prototype.

- **What the design does.** It states a model's inputs in one reviewed file, checks each delivery against it, and records the decision with the contract version.
- **What it does not claim.** It makes no claim of conformity to any standard, rule or guidance, holds no certification, and I have not read or mapped any source.

---

## 7. What is deliberately not here

- **Changes that stay inside the declared type, range and null rate.** 🟢 Ten of the 47 bad batches pass: null_zero_fill 3, unit_cents 2 and unit_in_range 5 (`step_04_with_contract.py`). A zero-fill becomes a valid-looking 0, and days sent as weeks keep their range.
- **A range wider than the changed scale.** The two unit_cents misses sit on `txn_total_30d_usd`, whose declared maximum holds the values multiplied by 100.
- **Distribution checks.** A shift inside the range is the job of a monitor such as [02 DriftSentinel](../02-driftsentinel-model-drift-monitoring/), designed and not built. I make no claim about how many of the ten it would catch.
- **Row counts, freshness, dates, patterns, cross-field rules and uniqueness.** A clean delivery of one row passes.
- **Drafting a contract.** It is written by hand.
- **Tolerances tuned on real feeds.** The 2.0% and 5.0% are my assumptions.
- **Hosting, fetching data or a published Action.**

---

## Appendix: sample contract

The shape is the prototype's own (`data/contract_credit_triage.json`, trimmed to two fields). The `--demo` output is under "Run one now" in the README.

```json
{
  "contract": "credit_triage_features",
  "version": "1.0.0",
  "unexpected_columns": "warn",
  "max_bad_rate": 0.02,
  "fields": [
    {"name": "dti_ratio", "type": "number", "min": 0, "max": 1.5},
    {"name": "ltv_ratio", "type": "number", "min": 0, "max": 1.5, "max_null_rate": 0.05}
  ]
}
```

```bash
python3 feature_contract.py check contract.json batch.csv --fail-on fail
```

Exit status: 0 below `--fail-on`, 1 at or above it, 2 for bad input.
