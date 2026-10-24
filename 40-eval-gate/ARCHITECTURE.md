# Architecture: Eval Gate

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/eval_gate.py`, that reads a probe file and a results file, compares the snapshot id each response reported with a pin, applies four rules and prints ALLOW, REVIEW or BLOCK, run here over 64 synthetic candidate deploys. A GitHub Action is staged in `action/` and has not been published or run on GitHub. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![Eval Gate flow](./assets/eval-gate-flow.svg)

---

## 1. Logical architecture

Eval Gate is a function between a test harness and a deploy: two files and a pin in, a decision out. It does not run a probe, call a model or judge an answer.

Eight components: four decide the outcome, four support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `eg-ingest` | Loads both files. Rejects an empty, header-only, truncated, wrong-type or duplicate input with a one-line message. | Python 3.9+, standard library. Prototype: `load_probes`, `load_results` in `src/eval_gate.py` | Yes, by refusing: exit 2 | No |
| `eg-pins` | The pinned snapshot id per deploy target and the three thresholds. Moves only by a reviewed change that links the vendor's notice. | A reviewed config file in the deploy repo (design). Prototype: `--pin`, the threshold flags, `data/run_pins.csv` | Yes, config | Stateful, in git |
| `eg-rules` | The four rules, each returning a finding with a level: `snapshot_changed`, `unscored_probes`, `overall_drop`, `probe_collapse`. | Python. Prototype: `evaluate` | Yes | No |
| `eg-verdict` | Takes the highest level among findings and maps it to an exit code at `--fail-on`. | Python. Prototype: `DECISION_RANK`, `run_check` | Yes | No |
| `eg-report` | Prints text or GitHub annotations. Escapes untrusted strings before a log or a workflow command. | Python. Prototype: `render`, `escape_annotation`, `safe` | No | No |
| `eg-action` | Runs the command in a CI job, inputs through environment variables. | Composite GitHub Action, staged in `action/action.yml`, not published | No | No |
| `eg-ledger` | Appends one record per decision (design). Prototype analog: `src/out/step_04_decisions.csv`. | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |
| `eg-telemetry` | Counts decisions, rejections and run time, off the decision path (design). | OpenTelemetry to the platform's monitoring | No | No |

**What decides the outcome.** The input check, the pin and thresholds, the rules and the verdict. The report, the Action wrapper, the ledger and telemetry carry or record the decision. The gate reads `passes` as the harness wrote it and trusts `served_model`.

**Repo structure** (production shape):

```
eval-gate/
├── gate/       # ingest.py, rules.py, verdict.py, report.py
├── action/     # composite Action wrapper
├── pins/       # pin and threshold config per target, changed by pull request
├── ledger/     # decision record writer
├── infra/      # terraform for gcp, aws, azure; IAM and bucket policies
├── docs/runbooks/
└── tests/      # unit, golden (planted-set numbers), hostile (injection strings)
```

---

## 2. Physical and deployment architecture

The gate is one short-lived process in the pipeline that already deploys the feature. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Gate process (`eg-ingest`, `eg-rules`, `eg-verdict`, `eg-report`) | Cloud Build step or Cloud Run job | CodeBuild step or ECS Fargate task | Azure Pipelines step or Container Apps job | Stateless, one pass, runs where the deploy runs |
| `eg-pins` | A file in the deploy repo | Same | Same | The pin change lands in the same history as the deploy |
| Probe and results store | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | The harness writes, the gate reads, versioning keeps the exact bytes a decision used |
| `eg-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |
| `eg-telemetry` | OTel Collector to Cloud Monitoring | To CloudWatch | To Azure Monitor | Off the decision path |

**Failure behavior (the decision that matters most).** The gate must never silently pass. A missing, empty, truncated or mistyped input does not become ALLOW and is not skipped: it ends the run with exit 2 and a one-line reason, and that exit fails the CI step even with `--fail-on never`. A probe with no result is a finding, not a shrug.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Results file missing, empty, header only or truncated; a bad count; `served_model` empty | Exit 2, one line on stderr naming the line, CI step fails | P2 if repeated on one target, else P3 |
| Pin empty; several runs in one file with no run id; no result row matches any probe | Exit 2 with the reason | P3 |
| Some result rows name probes not in the probe file | Rows ignored, with a note | P4 |
| A probe has no result | Finding `unscored_probes`: BLOCK if any is high severity, else REVIEW | P3 on BLOCK |
| Ledger or telemetry unavailable (design) | The decision and exit code stand; the record queues locally and the gap is listed | P3 |

**Latency.** The prototype is one pass over two small files; I have not timed it. 🔴 Design target: a decision within 60 seconds of the results file landing.

Recovery is a re-run from the same versioned inputs and pin. The designed interlocks (none built) are in the README.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Probe | `probe_id` | Severity and baseline pass rate on the pinned snapshot | `data/probes.csv`: `probe_id`, `slice`, `severity`, `situation`, `expected_behavior`, `baseline_rate`. The gate reads only `probe_id`, `severity`, `baseline_rate` |
| Result row | `run_id`, `probe_id` | Passes out of trials, and the snapshot id the response reported | `data/runs.csv`: `run_id`, `probe_id`, `passes`, `trials`, `served_model`. The single-run shape has no `run_id` |
| Pin | deploy target | The snapshot id this deploy is meant to use | `data/run_pins.csv`: `run_id`, `pin` |
| Decision record, with its findings (`kind`, `level`, `probe`, `message` from `evaluate`) | `decision_id` | Design: run, target, pin, served ids, probes scored, pass rate, baseline, decision, thresholds used, SHA-256 of both files, tool version, time | Prototype: `src/out/step_04_decisions.csv` |
| Planted truth | `run_id` | The event planted and the decision it deserves | `data/run_truth.csv`: `run_id`, `planted_kind`, `truth_decision`. Exists only because the data is synthetic |

**Retention** is a design choice, not a measurement; confirm each value against the bank's own record-retention schedule.

| Data | Retention (🔴 design default) | Storage |
| --- | --- | --- |
| Decision records and findings | 7 years | PostgreSQL, archived to object storage with a retention lock |
| Probe and results files a decision used | Same as the decision, so it can be reproduced | Versioned object storage |

**Lineage.** A decision traces back in three hops: the record names the run, pin, thresholds and the hash of both files; the versioned store returns those bytes; and the rules are deterministic (no clock, locale or random draw), so re-running `evaluate` reproduces the findings. In the prototype the trace is a row of `step_04_decisions.csv`, ending in a findings string such as `probe_collapse:P005`.

**Deliberately not stored.** Prompts, responses, judge output and customer text. The gate needs only counts and the reported id, and ignores `situation` and `expected_behavior`.

---

## 4. Security architecture

**Identity and roles.** The gate runs under the CI platform's workload identity and has no user account of its own.

| Role | Can | Maps to |
| --- | --- | --- |
| `eg:runner` | Read both files and the pins config; write a decision record | The CI service identity for the target |
| `eg:approver` | Approve a pin change (vendor notice linked) or a threshold change, never for their own deploy | Second-line or model-risk reviewer |
| `eg:auditor` | Read decisions, findings and config history | Internal audit |
| `eg:admin` | Manage roles, buckets and the ledger | Platform engineering lead |

**Secrets.** The gate holds none and never calls a model, so no vendor key is in its path. The CI identity reaches the store and the ledger through workload identity, with no static keys. The Action passes inputs through environment variables and an argument array, with `--` before the file arguments; `tests/test_cli.py` checks that no `${{ }}` expression sits inside the shell script.

**Data classification and what leaves the boundary.** Pass counts, trial counts, severity labels and snapshot ids are internal. If a real probe file carries scenario text with customer-like detail, treat it as confidential; the gate does not need it. In the prototype nothing leaves the machine. In the design three things leave the job: the exit code, the annotations and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in an input field echoed into a log or annotation | A `served_model` holding a newline and text that looks like a workflow command | `escape_annotation` rewrites `%`, carriage return and newline; `safe` writes control characters as escapes in text output. `tests/test_cli.py` covers a hostile snapshot id in an annotation, and a hostile pin and id in text |
| The pin or a threshold is changed to make a BLOCK go away | A pin moved with no vendor notice; `--block-drop` raised | Changes go through pull request with a different approver; every decision stores the pin and thresholds it used |
| The results file or the baseline is edited | Pass counts raised or `baseline_rate` lowered after the harness wrote them | Versioned storage; the decision stores both hashes; a changed hash for a finished run is an alert |
| The harness copies the id it asked for | `served_model` always equals the request | The gate cannot see this. The design asks for a harness contract test that fails when `served_model` is set from the request |

---

## 5. Operational architecture

**SLIs.** Decisions per level per target per week (prototype baseline on fine synthetic runs: 🟢 1 of 31 sent to review, `step_04_with_gate.py`); input rejections; probes scored over probes in the file; probes served by an id other than the pin; pin age; BLOCKs overturned after review; time to decision.

**SLOs (all 🔴 design targets, none measured).**
- Decision available within 60 seconds of the results file landing.
- Every production deploy of an in-scope feature passes through the gate and leaves a decision record.
- Every BLOCK read by a named person within one business day (planning estimate).
- 99.9 percent of decisions written to the ledger.

**Alerts.** P2: repeated input rejections on one target, or the ledger down for more than a day (low-urgency page to the pipeline owner). P3: a BLOCK on `snapshot_changed` for a production target, which also goes to vendor management, or a changed hash for a finished run (chat). P4: a daily digest of REVIEW decisions (email).

**Runbooks** (one page each, in `docs/runbooks/`):
- `snapshot-changed.md`: read the vendor's notice, re-run the harness, move the pin or hold.
- `moving-the-pin.md`: the pull request, the notice, the second approver, a re-run on the new id.
- `unscored-probes.md`: find why the harness produced no result for a probe, and re-run.
- `changing-a-threshold.md`: propose, re-run the planted set, compare with the golden numbers, approve.

**On-call and ownership.** The pipeline owner owns the runner, the Action wrapper and the runbooks. The evaluation owner owns the probe set, baselines and harness contract. The second-line reviewer approves pin and threshold changes. Nobody is paged for a REVIEW.

**Change control for rules and thresholds.** Rules and thresholds are versioned in the repo. A change needs a proposer and a different approver. Before merge, the planted set is re-run and compared with the pinned numbers in `tests/test_golden.py`, so a change that moves the stopped count shows in the diff. Every decision stores the tool version and thresholds it used. Rollout is shadow, then calibration, then enforcement, as the PRD lays out.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites one source, restated with the same wording about what was read: the [NIST AI RMF Playbook](https://airc.nist.gov/AI_RMF_Knowledge_Base/Playbook/Measure), MEASURE 2.4, which I read on 2026-10-23 (the page shows no publication date). It covers monitoring AI systems once they are in production and suggests comparing production metrics with pre-deployment test results.

- **What the design does.** It runs a related comparison earlier, on the candidate deploy: probe results against baselines measured on the pinned snapshot, with the decision recorded.
- **What it does not claim.** It does no production monitoring. It is not compliant with the playbook or any other standard, holds no certification, and I have not read or mapped any other source.

---

## 7. What is deliberately not here

- **Judging answers.** The gate reads `passes` as given. Judge noise and the choice of probes are outside it.
- **Production monitoring and baseline refresh.** The gate looks at a candidate deploy once. Baselines come in through the probe file and are not recomputed.
- **Subtle drift behind an unchanged id.** 🟢 Three subtle drifts pass (`step_04_with_gate.py`). The mean moved about two points, which ten trials per probe cannot tell from noise.
- **A way to know the harness is honest.** The gate trusts `served_model`. A harness that copies the requested id defeats rule one, and the exact-string match raises a false BLOCK on a vendor that reports one model under two spellings.
- **A per-slice drop rule.** A slice of probes can fall while the mean holds. It is next in the backlog, not built.
- **Thresholds tuned on real traffic.** The 3 and 5 point lines and the 0.90 floor are assumptions from project 04; the 50-point line is mine.
- **Running the probes, hosting, or a published Action.** A Marketplace listing is a later, separate step.

---

## Appendix: sample contract

The call is the prototype's own. Its output for the bundled `--demo` run (`data/example_results.csv`) is under "Run one now" in the README.

```bash
python3 eval_gate.py check probes.csv results.csv --pin vendor-balanced-4-20260214 --fail-on block
```

Exit status: 0 below `--fail-on`, 1 at or above it, 2 for bad input.
