# Architecture: Memo Tieout

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/memo_tieout.py`, that reads a markdown credit memo and a spread CSV, ties each marked figure to a spread line or a recomputed ratio at the decimals the memo shows, and reports each figure as tied, not tied, unresolved or untied, run here over 28 synthetic memos and 308 planted figures. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![Memo Tieout flow](./assets/memo-tieout-flow.svg)

---

## 1. Logical architecture

Memo Tieout is a function between a spreading system and a memo review: a memo and a spread in, a result per figure out. It edits no memo and judges no credit.

Seven components: four decide the outcome, three support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `mt-ingest` | Reads the memo and the spread and rejects bad input with a one-line message. The design adds a feed from the document store and the spreading system. | Python 3.9+, standard library. Prototype: `read_text`, `read_spread`, `build_spread` | Yes, by refusing: exit 2 | No |
| `mt-parse` | Finds figures (a dollar sign, a percent sign or a trailing x) and marks, skipping code, link targets and URLs. | Python. Prototype: `parse_figures`, `scan_memo` | Yes, it defines what a figure is | No |
| `mt-formulas` | Resolves a mark to a spread line or a recomputed margin or ratio, at one period. Formulas move only by a reviewed change. | Python. Prototype: `METRICS`, `evaluate` | Yes, config | Stateful in git (design) |
| `mt-tie` | Compares the figure with the value rounded half away from zero to the shown decimals, with no tolerance, and names other lines that do tie. | Python. Prototype: `ties`, `find_ties`, `_resolve`, `check_memo` | Yes | No |
| `mt-report` | Tallies the statuses and prints text or GitHub annotations, escaping untrusted strings. | Python. Prototype: `tally`, `render_text`, `render_github`, `clean`, `escape_data`, `escape_property` | No | No |
| `mt-extract` | Pulls the memo and its spread for one sign-off. Design only. | A job in the memo workflow (design). Prototype analog: the two file arguments | No | No |
| `mt-ledger` | One record per run. Design only. Prototype analog: `src/out/step_04_results.csv`. | PostgreSQL plus object storage (design) | No | Stateful |

**What decides the outcome.** What counts as a figure, what a mark resolves to, the formulas and the rounding rule. The report, extract and ledger carry or record the result. The tool trusts the mark: a number edited together with its mark passes.

**Repo structure** (production shape):

```
memo-tieout/
├── tieout/     # ingest.py, parse.py, formulas.py, tie.py, report.py
├── formulas/   # reviewed definitions, changed by pull request
├── extract/    # memo and spread feed
├── ledger/     # check record writer
├── infra/      # terraform for gcp, aws, azure
├── docs/runbooks/
└── tests/      # unit, golden, hostile strings
```

---

## 2. Physical and deployment architecture

The tool is one short-lived job in the memo workflow, run when a draft is submitted for review. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Tie-out job (`mt-ingest` to `mt-report`) | Cloud Run job | ECS Fargate task | Container Apps job | Stateless, one pass, short-lived |
| Memo and spread store | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Versioning keeps the exact bytes a result used |
| `mt-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |
| Telemetry | Cloud Monitoring | CloudWatch | Azure Monitor | Off the result path |

**Failure behavior (the decision that matters most).** The tool must never silently pass. An unreadable, empty or malformed input does not become PASS: it ends the run with exit 2 and a one-line reason. A memo with no figures, or only terms, prints that nothing was checked, shows NOTHING CHECKED and exits 1.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Memo or spread unreadable, over 5 MB, not UTF-8, holding NUL bytes or empty | Exit 2, one line naming the file | P3 |
| Spread with a missing column, a short row, a bad line name, period or `period_end`, a unit other than `usd`, `usd_thousands` or `usd_millions`, a value that is not a plain number, a repeated line and period, or no rows | Exit 2 naming the row | P3 |
| A code fence in the memo that never closes | Exit 2: the rest of the memo would be skipped without a word | P3 |
| A mark naming a line, formula or period the spread lacks; a formula with a missing value, no prior period or a zero divisor; a figure of the wrong form | The figure is unresolved, with the reason; FAIL, exit 1 | None |
| A figure with no mark | Reported untied; FAIL, exit 1 | None |
| No figure to check | NOTHING CHECKED, exit 1 | P4 |
| Ledger unavailable (design) | The result and exit code stand; the record queues locally and the gap is listed | P3 |

**Latency.** I have not timed the prototype. 🔴 Design target: a tie-out result within 60 seconds of a memo and its spread landing. Recovery is a re-run from the same versioned files.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Memo | `memo_id` | Markdown text with marked figures | `data/memos.json`: `memo_id`, `borrower`, `memo` |
| Spread row | `memo_id`, `line`, `period` | One value, in a declared unit | `data/spreads.csv`: `memo_id`, `period`, `period_end`, `line`, `value`, `unit`. The tool's own input drops `memo_id` |
| Figure result | `memo_id`, `line`, `col` | Status, tag and the reason | Prototype: `src/out/step_04_results.csv` (`status`, `why`) |
| Planted truth | `memo_id`, `line`, `col` | The planted kind and whether the figure should be flagged | `data/truth.csv`: `kind`, `expected`, `text`. Exists only because the data is synthetic |

**Retention** is a design choice, not a measurement; confirm it against the bank's own schedule. 🔴 Design default: check records 7 years, in PostgreSQL and archived with a retention lock; the memo and spread a record used are kept as long, so the result can be reproduced.

**Lineage.** A result traces back in three hops: the record names the memo, the spread, the formula file version and the file hashes; the versioned store returns those bytes; and the rules are deterministic (decimal arithmetic, no clock, locale or random draw), so re-running `check_memo` reproduces the statuses. In the prototype the trace is a row of `step_04_results.csv`.

**Deliberately not stored.** The memo text itself in the ledger, borrower names and narrative. The record keeps the position, the figure text, the tag, the status and the hashes.

---

## 4. Security architecture

**Identity and roles.** The job runs under the platform's workload identity and has no user account of its own.

| Role | Can | Maps to |
| --- | --- | --- |
| `mt:runner` | Read the memo, spread and formulas; write a check record | The job's service identity |
| `mt:reviewer` | Read results for memos they review | Credit reviewer |
| `mt:approver` | Approve a formula change, never their own | Credit risk or policy owner |
| `mt:auditor` | Read records and formula history | Internal audit |

**Secrets.** The tool holds none and calls no model; the job uses workload identity.

**Data classification and what leaves the boundary.** A memo and a spread carry a borrower's financial information and are confidential. A result quotes figures and values, so it is as sensitive as the memo and gets the same access. In the prototype nothing leaves the machine. In the design the result, the exit code and the ledger write leave the job.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a memo or file name echoed into a log or annotation | A link label or file name holding a newline and text that looks like a workflow command | `clean` turns control characters into spaces; `escape_data` and `escape_property` rewrite `%`, carriage return, newline, colon and comma. `tests/test_cli.py` covers hostile memo text, a hostile file name and control characters in text output |
| The number and its mark are edited together | A figure and its tag changed after review | The record stores the spread and memo hashes; a changed hash for a reviewed memo is an alert |
| A spread figure is marked `term:` to skip the check | `[$47.3 million](term:revenue)` | The result prints the count of terms set aside; the design compares terms with the term sheet |
| Oversize or binary input | A multi-gigabyte file, NUL bytes | The tool reads at most 5 MB and rejects NUL bytes and invalid UTF-8 |

---

## 5. Operational architecture

**SLIs.** Figures per status per memo; memos with a flagged figure; share of figures with a mark; unresolved marks; terms set aside per memo; input rejections; time to a result. Prototype baseline: 🟢 16 of 28 memos still carry a wrong figure after the check (`step_04_with_memo_tieout.py`).

**SLOs (all 🔴 design targets, none measured).**
- A result within 60 seconds of the memo and spread landing.
- Every memo that reaches sign-off has a check record.
- Every FAIL is read by a named person before sign-off.
- 99.9 percent of runs written to the ledger.

**Alerts.** P3: repeated rejections for one team, or a changed hash for a reviewed memo. P4: a weekly digest of unresolved marks and memos with nothing checked.

**Runbooks** (one page each, in `docs/runbooks/`):
- `figure-does-not-tie.md`: check the mark, the period and the spread revision, then fix the memo or the mark.
- `unresolved-mark.md`: find the missing line or period and ask the spreading team.
- `changing-a-formula.md`: propose, re-run the planted set, compare with the golden numbers, approve.
- `input-rejected.md`: find the row or line named and ask for a corrected export.

**Ownership.** The analyst owns the memo and its marks, the spreading team the export, credit risk the formulas, and the platform team the job. Nobody is paged for a FAIL; the reviewer is the reader.

**Change control.** Formulas are versioned. A change needs a proposer and a different approver. Before merge, the planted set is re-run against `tests/test_golden.py`, so a change that moves the caught count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites nothing: I claim no alignment with a standard, framework or regulation, and the marks, the formulas and the rounding rule are my own.

- **What the design does.** It writes the rounding rule and each formula out, keeps formulas in a reviewed file, and stores the formula version and file hashes with every result.
- **What it does not claim.** Any alignment with, or conformity to, a standard or a rule, and any statement about how a bank defines EBITDA or coverage. I have not read or mapped any source.

---

## 7. What is deliberately not here

- **A sentence that names the wrong line.** 🟢 Ten `prose_tag_mismatch` figures pass every rule (`step_04_with_memo_tieout.py`): the number agrees with its mark under words that name another line.
- **Figures written in words.** 🟢 Ten `unparsed_form` figures are never read (`step_04_with_memo_tieout.py`): words, or a USD prefix.
- **Bracketed negatives and ranges.** A loss in brackets is read as positive and `$4-$5 million` as two figures.
- **A check that the spread matches the financial statements.** The tool ties a memo to a spread, not a spread to its source.
- **Your definitions.** The formulas are mine, and a bank's spread may add back items. A line in the spread with the same name wins.
- **Trust in the mark.** A number edited together with its mark passes.
- **Hosting, a published Action or a model call.**

---

## Appendix: sample contract

```bash
python3 memo_tieout.py check memo.md --spread spread.csv --format text
```

A mark is `[$47.3 million](spread:revenue/FY2024)` for a figure, or `[$5.0 million](term:facility_amount)` for a proposed term. The spread has the columns `period, period_end, line, value, unit`. The result is PASS, FAIL or NOTHING CHECKED. Exit status: 0 when every figure ties, 1 when one does not or nothing could be checked, 2 for bad input.
