# Architecture: aigf-checks

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/aigf_checks.py`, that reads a risk catalogue, a check registry, a crosswalk and the captured output of each check, and reports the rows that no longer hold, run here over 73 synthetic rows. It runs no check. Nothing below is claimed as deployed or load-tested. The contribution it supports is drafted and not opened. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![aigf-checks flow](./assets/aigf-checks-flow.svg)

---

## 1. Logical architecture

aigf-checks is a function between a crosswalk and its readers: four files in, findings and a status per risk out. It compares text. It does not run a check, read a check's code or judge what a risk requires.

Eight components: five decide the outcome, three support or supply.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `ag-ingest` | Reads the four files. Rejects an empty, truncated, mistyped, duplicate-id or no-row file with a one-line message. | Python 3.9+, standard library. Prototype: `read_rows`, `load_risks`, `load_checks`, `load_crosswalk`, `load_outputs` | Yes, by refusing: exit 2 | No |
| `ag-resolve` | The risk and the check of each row exist; no second row repeats the same risk, check and claim label. | Python. Prototype: `analyze` | Yes | No |
| `ag-compare` | Finds the labelled `label: value` line in the check's output and compares the value after setting aside case, spacing and thousands separators. | Python. Prototype: `printed_lines`, `norm_label`, `norm_value` | Yes | No |
| `ag-aspects` | A row marked full needs every aspect of the risk; a partial row needs one. The note is read for overclaiming words. | Python. Prototype: `analyze`, `OVERCLAIM` | Yes | No |
| `ag-status` | One status per risk: CHECKED, PARTIAL, UNVERIFIED or GAP. | Python. Prototype: the end of `analyze` | Yes | No |
| `ag-report` | Prints text or GitHub annotations, sets the exit code, escapes file text. Also the sign-off lint. | Python. Prototype: `render`, `one_line`, `escape_annotation`, `run_check`, `commit_problems` | No | No |
| `ag-capture` | Runs each check and saves its output beside the crosswalk in the same CI job (design). The prototype takes `outputs.json` as given. | A CI job step (design) | No, but it sets how fresh a pass is | Stateful, per run |
| `ag-ledger` | One status record per run, off the decision path (design). Prototype analog: `src/out/step_04_risks.csv`. | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |

**What decides the outcome.** The input check, the id and duplicate checks, the label-bound comparison, the aspects and the status. The report, the capture and the ledger carry or record it. The tool trusts the aspects a check declares and the capture it is given.

**Repo structure** (production shape):

```
aigf-checks/
├── tool/       # ingest, resolve, compare, aspects, status, report
├── crosswalk/  # risks, checks, rows; changed by pull request
├── ci/         # capture step and gate step
├── ledger/     # status record writer
├── infra/      # terraform for gcp, aws, azure
└── tests/      # unit, golden (planted set), hostile (injection strings)
```

---

## 2. Physical and deployment architecture

The tool is one short-lived step in the CI job that runs the checks. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Capture and gate steps | Cloud Build steps | CodeBuild steps | Azure Pipelines steps | The capture and the comparison share one job, so the output is as fresh as the run |
| `crosswalk/` files | A reviewed repo | Same | Same | A row change lands in the same history as the check change |
| Captured outputs | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Versioning keeps the exact bytes a status used |
| `ag-ledger` and counts | Cloud SQL for PostgreSQL; OTel to Cloud Monitoring | RDS for PostgreSQL; CloudWatch | Azure Database for PostgreSQL; Azure Monitor | The platform team already runs them; off the decision path |

**Failure behavior (the decision that matters most).** The tool must never silently pass. A missing, empty, truncated or mistyped input does not become "no findings": it ends the run with exit 2 and a one-line reason. A row whose check has no captured output is a finding, `no_output`, not a skip.

| Failure | Behavior | Alert |
| --- | --- | --- |
| A file missing, empty, binary, with a missing column, a truncated row, a duplicate id, a bad `covers` value or no rows | Exit 2, one line on stderr | P2 if repeated on one crosswalk, else P3 |
| `outputs.json` is not an object of check id to text | Exit 2 | P3 |
| A row names a check with no captured output | Finding `no_output`; the claim is not compared | P3 |
| No claim in the crosswalk could be compared with a printed line | A line saying no number was verified | P3 |
| The capture is older than the checks it covers (design) | The gate step fails before the tool runs | P3 |
| Ledger unavailable (design) | The findings and exit code stand; the record queues locally and the gap is listed | P3 |

**Latency.** The prototype is one pass over a small crosswalk; I have not timed it. 🔴 Design target: a verdict on the whole crosswalk within 2 minutes of the checks finishing. Recovery is a re-run from the same files.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Risk | `risk_id` | A framework risk and the aspects a check must exercise | `data/risks.csv`: `risk_id`, `title`, `summary`, `aspects` (separated by `;`) |
| Check | `check_id` | A runnable check and the aspects its registry entry says it exercises | `data/checks.csv`: `check_id`, `project`, `command`, `exercises` |
| Crosswalk row | `row_id` | One claim: this check covers this risk, and this line shows it | `data/crosswalk.csv`: `row_id`, `risk_id`, `check_id`, `covers`, `claim_label`, `claim_value`, `note` |
| Captured output | `check_id` | The text the check printed | `data/check_outputs.json` |
| Finding and status record | `record_id` | Design: crosswalk version, capture hashes, findings, a status per risk, tool version, time | Prototype: `src/out/step_04_rows.csv` and `step_04_risks.csv`; findings carry `row_id`, `kind`, `detail` |
| Planted truth | `row_id`, `risk_id` | The planted kind and the status each risk should get | `data/row_truth.csv`, `data/risk_truth.csv`, `data/check_truth.csv`. Synthetic data only |

**Retention** is a design choice, not a measurement; confirm it against the bank's own schedule. 🔴 Design default: status records and the captures they read 7 years, in versioned storage with a retention lock.

**Lineage.** A status traces back in three hops: the record names the crosswalk version and the capture hashes; the store returns those bytes; and the rules are deterministic, so re-running `analyze` reproduces the findings. In the prototype the trace is a row of `step_04_rows.csv`.

**Deliberately not stored.** Any check's code, or its data beyond the printed lines the crosswalk cites.

---

## 4. Security architecture

**Identity and roles.** The tool runs under the CI platform's workload identity with no user account of its own. Four roles: `ag:runner` (reads the files, writes a record), `ag:approver` (approves a crosswalk change, never their own), `ag:auditor` (reads records and history) and `ag:admin` (platform lead).

**Secrets.** None, and no model call. The tool executes nothing named in a registry: the `command` column is text. The capture step runs the checks under its own scoped identity, outside this tool.

**Data classification and boundary.** The risks, rows and printed lines are internal and, in a public contribution, would be published. In the prototype nothing leaves the machine. In the design three things leave the job: the exit code, the annotations and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a note, label or value reaches a log or an annotation | A note holding a newline and text that looks like a workflow command | `one_line` cuts file text to one printable line; `escape_annotation` rewrites `%`, carriage return and newline. `tests/test_cli.py` covers hostile values, and a hostile commit message that is not echoed |
| A capture is edited to match the claim | A printed number changed by hand | The capture is written by the CI job, its hash is stored with the status, and a changed hash is an alert |
| A check declares an aspect it does not exercise | A registry entry that lists `approval_step` | A reviewer reads the aspects against the output at review time. The tool cannot see this |

---

## 5. Operational architecture

**SLIs.** Runs per week; input rejections; findings by kind; risks by status (prototype baseline on harmless synthetic rows: 🟢 0 of 28 flagged, `step_04_with_checks.py`); rows with no captured output; capture age at the run; findings overturned after review; time to verdict.

**SLOs (all 🔴 design targets, none measured).**
- A verdict on the whole crosswalk within 2 minutes of the checks finishing.
- Every row compared with a capture from the run that is being gated.
- Every finding read by a named person within five business days (planning estimate).

**Alerts.** P2: repeated input rejections, or the ledger down for more than a day. P3: a `no_output` or `stale_value` finding on a gated crosswalk, a stale capture, or a changed capture hash. P4: a weekly digest of risks that moved status.

**Runbooks** (one page each, in `docs/runbooks/`):
- `stale-value.md`: read the check's output, then fix the claim or the check, and re-capture.
- `no-output.md`: find why the check produced no capture, and re-run the capture step.
- `changing-aspects.md`: pull request, a reviewer reads the aspects against the output, golden numbers re-run.
- `input-rejected.md`: find why a file could not be read, and re-run.

**On-call and ownership.** The contributor owns the crosswalk rows. The check owners own the labels their output prints. The platform owner owns the CI job.

**Change control.** Rules and the word list are versioned in the repo; a change needs a proposer and a different approver. Before merge the planted set is re-run against `tests/test_golden.py`, so a change that moves the found count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites one source, restated with the same wording about what was read: the [FINOS AI Governance Framework](https://air-governance-framework.finos.org/) risk entries named in the README, as read on 2026-10-24, and its contribution guide. The status words come from [16 ControlMap](../16-controlmap-ai-obligation-crosswalk/), changed to fit a risk and a check.

- **What the design does.** It keeps a claim that a check covers a risk tied to what the check prints, and it lints a commit message against the sign-off and subject-length rules in the contribution guide.
- **What it does not claim.** It makes no claim of conformity to the framework, is not endorsed by FINOS, holds no certification, and I have not read or mapped any other source. The mappings in the README are my reading; no maintainer has read them.

---

## 7. What is deliberately not here

- **Paraphrased overclaims.** 🟢 3 notes overclaim in words the rule does not list and pass (`step_04_with_checks.py`).
- **A false declaration.** 🟢 4 rows pass because the registry declares an aspect the check does not exercise; one leaves R-18 shown as CHECKED where the planted truth is PARTIAL (`step_04_with_checks.py`).
- **Meaning.** It compares text. A check that keeps its label and starts measuring something else passes, and if a check prints one label twice the tool reads the first line.
- **Running a check.** It compares a claim with a capture the contributor supplies, so a stale capture gives a stale pass.
- **Deciding the aspects.** For a real framework entry a person reads the risk text and decides what a check must exercise.
- **Commit style beyond form.** The sign-off lint does not check that the address is the author's, or the mood of the subject.
- **Opening the issue or the pull request.** Both are drafted and wait for the author.

---

## Appendix: sample contract

The shape is the prototype's own. Its output for the bundled `--demo` run is under "Run one now" in the README.

```bash
python3 aigf_checks.py check risks.csv checks.csv crosswalk.csv outputs.json --fail-on any --format github
```

A crosswalk row from the example: `ROW-2,R-02,C-01,full,retrieved cases caught,17 of 20,` with an empty note, read against `outputs.json`, a JSON object of check id to the text the check printed. Exit status: 0 when nothing is found, 1 when a row has a finding, 2 for bad input.
