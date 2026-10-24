# Architecture: Claims Check

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/claims_check.py`, that reads the numbers after each green circle in a README and checks each one against the text a project's scripts printed, as a whole number, with "a of b" matched as a pair. It runs here over 40 synthetic projects with 284 planted bullets. A GitHub Action is staged in `action/`, unpublished and not run on GitHub. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![Claims Check flow](./assets/claims-check-flow.svg)

---

## 1. Logical architecture

Claims Check is a function between a documentation change and a merge: a README and the files holding what the scripts printed in, a pass or a fail out. It does not run the scripts, judge what a number means or call a model.

Eight components: four decide the outcome, four read, report or record.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `cc-ingest` | Reads the README and the evidence files; refuses an unreadable, empty, binary or oversize file, and a pattern that matches no file | Python 3.9+, standard library. Prototype: `read_text`, `expand_evidence` | Yes, by refusing: exit 2 | No |
| `cc-extract` | Finds the numbers after each green circle, per paragraph, list item or table row; joins wrapped bullets; skips code blocks, code spans, link targets and URLs | Python. Prototype: `blocks`, `extract_claims` | Yes: decides what is a claim | No |
| `cc-evidence` | Indexes everything the scripts printed: each whole number, and each "a of b" or "a/b" pair on one line | Python. Prototype: `index_evidence`, `norm` | Yes | No |
| `cc-check` | Marks each claim supported, unsupported or skipped, with a reason; picks PASS, FAIL or NOTHING CHECKED | Python. Prototype: `check_claims`, `tally`, `run_check` | Yes | No |
| `cc-report` | Prints text or annotations; escapes paths and text from the input | Python. Prototype: `render_text`, `render_github`, `clean`, `escape_data`, `escape_property` | No | No |
| `cc-capture` | Reruns the scripts in CI and stores their output with a time (design). Prototype analog: the step outputs read by `tests/test_golden.py` | CI job step (design) | No, but the check trusts it | Stateful |
| `cc-action` | Runs the check in a CI job, inputs through environment variables | Composite GitHub Action, staged in `action/action.yml` | No | No |
| `cc-ledger` | One record per run (design). Prototype analog: `src/out/step_04_results.csv` | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |

**What decides the outcome.** The input check, the extractor, the evidence index and the matcher. A claim is supported only when its whole number, or its pair, is printed. The report, the capture step and the ledger carry or record the result. The check proves a number was printed, not that it is the right one.

**Repo structure** (production shape):

```
claims-check/
├── check/      # ingest, extract, evidence, match, report
├── action/     # composite Action wrapper
├── capture/    # CI step that reruns scripts and stores their output
├── ledger/     # run record writer
├── infra/      # terraform for gcp, aws, azure
├── docs/runbooks/
└── tests/      # unit, golden (planted-set numbers), self-check on the README
```

---

## 2. Physical and deployment architecture

The check is one short-lived process in the pipeline that already builds the project. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Check process | Cloud Build step or Cloud Run job | CodeBuild step or ECS Fargate task | Azure Pipelines step or Container Apps job | Stateless, one pass, runs where the scripts run |
| Captured evidence | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Versioning keeps the exact text a result used |
| `cc-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The check must never report PASS on something it did not read. An unreadable input ends the run with exit 2. A run that found nothing to check says so in words and does not print PASS.

| Failure | Behavior | Alert |
| --- | --- | --- |
| README or evidence file missing, empty, binary, not UTF-8, containing NUL bytes, or over the size limit | Exit 2, one line on stderr | P3 |
| An evidence pattern matches no file, or none is given | Exit 2 with the pattern named | P3 |
| No number follows a green circle, or every such number is too short | `NOTHING CHECKED`, exit 0; the Action prints a warning | P4 digest |
| A claim is not printed as a whole number, or a pair is not printed together | `not supported` with the line and the reason; exit 1 at `--fail-on unsupported` | P3 on a protected branch |
| Evidence is stale: the scripts were not rerun | The check cannot see this. The design adds an age check on the captured files | P3 |
| Ledger unavailable (design) | The result and exit code stand; the record queues locally | P3 |

**Latency.** The prototype is one pass over two text files; I have not timed it. 🔴 Design target: a result within 30 seconds of the evidence landing.

---

## 3. Data architecture

| Entity | Key | Real columns in the prototype |
| --- | --- | --- |
| README | path | Markdown text; the claims are the numbers after each green circle |
| Evidence | file | Plain text the scripts printed; the check indexes whole numbers and pairs |
| Claim | line, text | In memory: `line`, `kind` (number or ratio), `text`, `key`; then `status` (supported, unsupported, skipped) and `why` |
| Run record | `run_id` | Design: README path and hash, evidence file hashes, tool version, counts, result. Prototype: `step_04_results.csv` with `project_id`, `line_start`, `kind`, `expected`, `claims_check`, `grep` |
| Planted truth | `project_id`, `line_start` | `projects.json` (`project_id`, `readme`, `evidence`) and `truth.csv` (`project_id`, `line_start`, `line_end`, `kind`, `expected`); exists only because the data is synthetic |

**Retention** is a design choice, not a measurement; confirm it against the organization's record-retention schedule. 🔴 Design default: run records 3 years; the README and evidence a run used, the same period, in versioned storage.

**Lineage.** A result traces back in three hops: the record names the README and evidence hashes; the versioned store returns those bytes; and the matcher is deterministic, so re-running `check_claims` reproduces each line of the report. Each unsupported line names the line number, the number as written and, where one exists, a longer printed figure that contains it.

**Deliberately not stored.** Anything beyond the README text and the printed evidence. The check keeps no model output because it makes no model call.

---

## 4. Security architecture

**Identity and roles.** The check runs under the CI platform's workload identity with no user account. `cc:runner` reads the README and evidence and writes a run record. `cc:approver` approves a change to the minimum digit count or the pair rule, never their own. `cc:auditor` reads results and config history. `cc:admin` manages roles, buckets and the ledger.

**Secrets.** None. The tool reads text files and calls no model.

**Data classification and what leaves the boundary.** A README and script output may describe internal results; treat them as internal. In the prototype everything is synthetic and nothing leaves the machine. In the design three things leave the job: the exit code, annotations on the pull request and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a README path, an evidence pattern or claim text echoed into a log or annotation | A path holding a newline and text that looks like a workflow command | `escape_data` and `escape_property` follow GitHub's documented escapes; `clean` turns control characters into spaces. `tests/test_cli.py` covers a forged command and one-line error text |
| An unsupported number hidden in a code span | The writer wraps the number in backticks so it is not a claim | The design counts inert numbers after a green circle and lists them; the prototype skips them by rule |
| Evidence edited to contain the number | A committed text file with the figure in it | Evidence comes from the capture step in the same job, not from the repository; the record stores its hash |
| A wrong number that equals another printed number | The row count or the seed | The check cannot see this: 🟢 all 10 coincidence bullets pass (`step_04_with_claims_check.py`) |
| A very large or binary file | A multi-megabyte upload as evidence | Files over the size limit, non-UTF-8 files and files with NUL bytes are refused |

---

## 5. Operational architecture

**SLIs.** Results per week by outcome; unsupported claims per README; skipped one-digit numbers per README (prototype: 🟢 16 skipped, `step_04_with_claims_check.py`); NOTHING CHECKED runs; evidence age; fine bullets flagged (prototype baseline: 🟢 8 of 186, the pair rule's price, `step_04_with_claims_check.py`); time to result.

**SLOs (all 🔴 design targets, none measured).**
- A result within 30 seconds of the evidence landing.
- Every README with green figures passes through the check before merge and leaves a run record.
- Every FAIL read by the README's author within one business day (planning estimate).
- Evidence no older than the last change to a script.

**Alerts.** P2: repeated input rejections on one repository, or the ledger down for more than a day. P3: a FAIL on a protected branch, or evidence older than the last script change. P4: a daily digest of NOTHING CHECKED runs.

**Runbooks** (in `docs/runbooks/`): `unsupported-number.md` (rerun the script, copy the number as printed, or remove the tag); `nothing-checked.md` (why no claim was found, and whether the tags are missing); `stale-evidence.md` (rerun the capture step and compare); `changing-the-rule.md` (propose, re-run the planted set, compare with the golden numbers, approve).

**On-call and ownership.** The README's author owns each result; the repository owner owns the capture step and runbooks; a second-line reviewer approves rule changes. Nobody is paged for a FAIL.

**Change control.** The matching rules and the digit minimum are versioned in the repo. A change needs a proposer, a different approver and a re-run of the planted set against the pinned numbers in `tests/test_golden.py`, so a change that moves a count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites nothing: it claims no alignment with a standard, framework or regulation. The credibility tags (green measured, yellow modeled, red hypothetical) are a convention of this portfolio, and this tool is what enforces the green ones.

- **What the design does.** It enforces one convention: a number tagged as measured is printed, as written, by a script.
- **What it does not claim.** It makes no claim of conformity to any standard, holds no certification, and I have not read or mapped any source for it.

---

## 7. What is deliberately not here

- **A check that a number is the right one.** 🟢 A wrong number that equals another printed number passes: all 10 such bullets pass (`step_04_with_claims_check.py`). The tool checks that a number was printed, not what it was printed next to.
- **Wrong one-digit numbers.** 🟢 8 single-digit bullets pass because numbers of one digit are skipped (`step_04_with_claims_check.py`). Checking them flags every stray small numeral.
- **Pairs printed on separate lines.** 🟢 The pair rule flags 8 of 186 fine bullets (`step_04_with_claims_check.py`). Print "a of b" in the script, or pass `--no-pairs`.
- **Fresh evidence.** The tool reads files; it does not run anything, so evidence from last month passes.
- **HTML and nested documents.** Markdown paragraphs, lists and tables are read.
- **Judging meaning, a model call, hosting, a published Action.**

---

## Appendix: sample contract

The call is the prototype's own; the `--demo` output is in the README.

```bash
python3 claims_check.py check README.md --evidence out/*.txt --fail-on unsupported --format github
```

Exit status: 0 when nothing is unsupported, 1 when at least one claim is, 2 for bad input.
