# Architecture: Credit Policy Needle

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/credit_policy_needle.py`, with an `audit` that lists the clauses of a manual that read as exceptions and a `score` that compares an assistant's answers with exact expected answers, flags failing cells and prints PASS or FAIL, run here over 3 synthetic manuals, 210 questions and four stub readers. No CI Action is staged. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![Credit Policy Needle flow](./assets/credit-policy-needle-flow.svg)

---

## 1. Logical architecture

Credit Policy Needle is a function over three files: a manual, a probe file and an answers file in, a list of exception clauses and a PASS or FAIL out. It does not ask an assistant a question or judge free text.

Eight components: three decide the outcome, five support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `cp-ingest` | Loads the manual, probes and answers. Rejects a missing, empty, non-UTF-8, header-only or mismatched file, a repeated id, and an answers file that matches no probe. | Python 3.9+, standard library. Prototype: `read_text`, `read_rows`, `load_probes`, `load_answers` in `src/credit_policy_needle.py` | Yes, by refusing: exit 2 | No |
| `cp-audit` | Lists numbered clauses and register entries with an exception cue and a limit or clause reference; says which do not name their rule. | Python. Prototype: `audit_text` | No, it lists and exits 0 | No |
| `cp-score` | Exact match on normalized answers; counts per cell, form, depth and slice. A probe with no answer scores as a fail. | Python. Prototype: `normalize`, `score_probes` | Yes | No |
| `cp-gate` | Flags cells under 90% and returns PASS or FAIL against the floors; maps FAIL to an exit code. | Python. Prototype: `gate`, `CELL_FLOOR`, `GATE_OVERALL`, `GATE_SLICE` | Yes | No |
| `cp-report` | Prints text or annotations; strips or escapes untrusted strings. | Python. Prototype: `render_audit`, `render_score`, `clean`, `gh_data`, `annotation` | No | No |
| `cp-harness` | Asks the assistant under test each probe and writes the answers file (design). Prototype analog: the four stub readers and `run_reader` in `src/common.py`. | A small client per assistant API (design) | No | No |
| `cp-ledger` | Appends one sweep record per release (design). Prototype analog: `src/out/step_04_cells.csv`. | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |
| `cp-telemetry` | Counts sweeps, failing cells and rejections, off the decision path (design). | OpenTelemetry | No | No |

**What decides the outcome.** The input check, the exact-match score and the gate. The audit tells a policy owner where exceptions sit and which would escape a search; the report, harness, ledger and telemetry carry or record the result. The gate sees only the answers it is given.

**Repo structure** (production shape):

```
credit-policy-needle/
├── needle/     # ingest, audit, score, gate, report
├── probes/     # question sets per manual, signed off by the policy owner
├── harness/    # one adapter per assistant under test
├── ledger/     # sweep record writer
├── infra/      # terraform for gcp, aws, azure; IAM
├── docs/runbooks/
└── tests/      # unit, golden, hostile strings
```

---

## 2. Physical and deployment architecture

The tool is one short-lived process in the release pipeline of the assistant, run on each release candidate. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Gate process (`cp-ingest` to `cp-report`) | Cloud Build step or Cloud Run job | CodeBuild step or ECS Fargate task | Azure Pipelines step or Container Apps job | Stateless, one pass, runs where the release runs |
| Manual, probe and answers files | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Versioning keeps the exact bytes a record used |
| `cp-harness` | Cloud Run job | ECS Fargate task | Container Apps job | Needs network to the assistant, so it runs apart from the gate |
| `cp-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |
| `cp-telemetry` | OTel Collector to Cloud Monitoring | To CloudWatch | To Azure Monitor | Off the decision path |

**Failure behavior (the decision that matters most).** The gate must never silently pass. A missing, empty or mismatched file does not become PASS: it ends the run with exit 2 and a one-line reason. An answers file for the wrong release, one that matches none of the probe ids, is an error. A probe with no answer is a fail.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Manual, probes or answers missing, empty, not UTF-8, header only, or short of required columns | Exit 2, one line on stderr naming the file | P2 if repeated on one pipeline, else P3 |
| A line with a different field count; a non-integer length or depth; an empty id, form or expected answer; a repeated `probe_id` | Exit 2 with the line | P3 |
| Answers file matches none of the probe ids | Exit 2: check that it is the right file | P3 |
| Some probes have no answer; some answers match no probe | The missing ones score as fails; the extras are counted and not scored | P3 |
| Assistant unreachable in the harness (design) | The harness stops with a non-zero exit and writes no answers file, so the gate cannot run on stale answers | P2 |
| Ledger or telemetry unavailable (design) | The result and exit code stand; the record queues locally | P3 |

**Latency.** The prototype scores 210 questions against stub readers in one pass; I have not timed it, and I have not run it against a real assistant. 🔴 Design target: a sweep result within 30 minutes of a release candidate being tagged. Recovery is a re-run from the same versioned files.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Manual | `manual_id` | The document the assistant is given | `data/manuals/*.txt`; `data/manuals.csv` holds length and counts |
| Probe | `probe_id` | One question, its exact answer, form, length and depth | `data/probes.csv`: `probe_id`, `manual_id`, `length_pages`, `doc_chars`, `form`, `depth_pct`, `variant`, `question`, `expected_answer`, `answer_kind`, `trap_answer`, and clause and offset columns. The gate reads `probe_id`, `form`, `length_pages`, `depth_pct`, `expected_answer` |
| Answer | `probe_id` | What the assistant said | `probe_id`, `answer` |
| Cell result | form, length, depth, reader | Passed out of total | `src/out/step_04_cells.csv`: `reader`, `form`, `length_pages`, `depth_pct`, `passed`, `total` |
| Sweep record | `record_id` | Design: assistant release, floors, SHA-256 of the three files, tool version, cells, result, time | Design only |
| Planted truth | `manual_id`, `block_id` | Whether a block is an exception, and which clause it cites | `data/exceptions_truth.csv`: `kind`, `is_exception`, `cites`. The audit never reads it |

**Retention** is a design choice, not a measurement; confirm it against the bank's own record-retention schedule. Sweep records and the files they used: 🔴 7 years (design default), in PostgreSQL archived to versioned object storage with a retention lock.

**Lineage.** A result traces back in three hops: the record names the release, the floors and the hash of the three files; the versioned store returns those bytes; and the score is deterministic (exact match on normalized text, sorted output, no clock or random draw), so re-running `score_probes` reproduces the cells. In the prototype the trace is a row of `step_04_cells.csv`, ending in a form, length and depth.

**Deliberately not stored.** Free-text assistant output beyond the answer, customer data and live policy text in the tool's logs. The gate needs the probe id, the form, the depth and a short answer.

---

## 4. Security architecture

**Identity and roles.** The gate runs under the CI platform's workload identity and has no user account of its own.

| Role | Can | Maps to |
| --- | --- | --- |
| `cp:runner` | Read the three files; write a sweep record | The pipeline's service identity |
| `cp:author` | Propose probes and expected answers | Policy owner |
| `cp:approver` | Approve a floor change or a probe change, never for their own release | Model risk reviewer |
| `cp:auditor` | Read records and change history | Internal audit |

**Secrets.** The gate holds none and calls no model. The harness holds the assistant's credential for the test environment, in the platform's secret store with no static keys in the repo, and writes only the answers file.

**Classification and what leaves the boundary.** A real credit policy and its thresholds are confidential, and a probe set derived from it is too. In the prototype nothing leaves the machine and every limit is invented. In the design three things leave the job: the exit code, the annotations and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a file echoed into a log or annotation | A `form` name or a clause holding a newline and text that looks like a workflow command | `clean` replaces control characters; `gh_data` and `gh_prop` escape `%`, carriage return, newline, colon and comma. `tests/test_cli.py` covers a hostile form name, `tests/test_audit.py` a hostile clause |
| Floors or expected answers are edited so FAIL becomes PASS | A floor lowered, an expected answer changed to the trap answer | Pull request with a different approver; the record stores both hashes and the floors it used |
| The assistant has seen the probes | Answers memorized from a leaked question set | Keep probes out of the assistant's context and training data; rotate a held-out set (design) |
| Policy text copied into a test artifact | A real clause in a repo or a log | Probes carry questions and answers, not the manual; logs show clause ids only |
| A stale answers file is gated | Last release's answers scored for this one | The record binds the answers hash to the release tag; the harness writes no file on failure |

---

## 5. Operational architecture

**SLIs.** Sweeps per release; pass by form and depth; cells flagged; input rejections; share of exceptions with a paired question; time from release candidate to result (prototype baseline on the stub readers: 🟢 the gate fails 3 of 3 faulty readers and passes the control, `step_04_with_gate.py`).

**SLOs (all 🔴 design targets, none measured).**
- A sweep result within 30 minutes of a release candidate being tagged.
- Every release of an in-scope assistant has a sweep record.
- Every FAIL read by a named owner within one business day (planning estimate).
- 99.9 percent of sweeps written to the ledger.

**Alerts.** P2: repeated input rejections, an unreachable assistant, or the ledger down for more than a day. P3: a FAIL on a release candidate, which also goes to the assistant owner. P4: a weekly digest of cells that passed with less than 5 points to spare (planning estimate).

**Runbooks** (one page each, in `docs/runbooks/`):
- `sweep-failed.md`: read the failing cells, tell truncation from retrieval from a skipped exception, fix or hold the release.
- `input-rejected.md`: read the reason, fix the file, re-run.
- `new-exception-form.md`: add a form and its paired questions, re-run the control.
- `changing-a-floor.md`: propose, re-run the planted set, compare with the golden numbers, approve.

**On-call and ownership.** The assistant owner owns the pipeline step and runbooks. The policy owner owns the question set. The model risk reviewer approves floor and probe changes.

**Change control.** Rules, floors and probes are versioned. A change needs a proposer and a different approver. Before merge, the planted set is re-run and compared with the numbers pinned in `tests/test_golden.py`, so a change that moves a pass count shows in the diff. Rollout is shadow, calibration, advisory, then enforcement, as the PRD lays out.

---

## 6. Alignment and posture

The README's "Aligned to" section cites nothing: it claims no alignment to a regulation or a standard. It credits the needle-in-a-haystack idea of planting a fact at a known depth, and the approach of [14 PolicyNeedle](../14-policyneedle-long-context-fidelity/), which this folder reuses without importing its code or data. This design restates that and adds nothing.

- **What the design does.** It tests whether an assistant finds the exception that changes the answer, and records the result so it can be reproduced.
- **What it does not claim.** It makes no claim of conformity to any guidance, holds no certification, and I have not read or mapped any source to it.

---

## 7. What is deliberately not here

- **A real assistant.** No model is called; the readers are stubs with faults I planted, and the retrieval stub is blunter than a real retriever.
- **Restated limits.** 🟢 The audit misses 15 of 15 restated limits, which carry no exception wording (`step_04_with_gate.py`).
- **Look-alikes.** 🟢 The audit lists 12 of 36 look-alikes by mistake: pointers that use exception words (`step_04_with_gate.py`).
- **A reader that never opens an exception.** 🟢 It passes 90 of 90 questions where the exception does not apply (`step_03_deficiencies_exposed.py`); only the paired question fails it.
- **Other kinds of exception.** Exceptions here only loosen a limit, carry one numeric condition and nest one level. Not covered: tightening, stacking, amendments, tables and non-numeric conditions.
- **Free-text answers.** Matching is exact on a normalized answer, so a correct answer wrapped in a sentence scores as wrong.
- **Other clause numbering.** The audit reads English cue words and clause numbers in the form 7.12 with register entries R-3.
- **A measured rate on real data.** The data, the readers and the checks share an author, so the results are a ceiling, not a rate on a real policy.

---

## Appendix: sample contract

The call is the prototype's own; its `--demo` output is under "Run one now" in the README.

```bash
python3 credit_policy_needle.py score probes.csv answers.csv --fail-on fail
```

A probe row and its answer, with the columns the gate reads:

```text
probe_id,form,length_pages,depth_pct,expected_answer
P050-PLN-000-1,plain,50,0,640 points

probe_id,answer
P050-PLN-000-1,640 points
```

Exit status: 0 on PASS or with `--fail-on never`, 1 on FAIL, 2 for bad input.
