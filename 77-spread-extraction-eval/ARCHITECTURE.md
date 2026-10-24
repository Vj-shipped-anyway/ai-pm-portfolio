# Architecture: spread-extraction-eval

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/spread_eval.py`, that scores an extractor's predictions on financial statements field by field and layout by layout, runs a tie-out check that needs no truth, and gates on drift between layouts, run here over 120 synthetic statements in six layouts and two rule-based stand-in extractors, not a model. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![spread-extraction-eval flow](./assets/spread-extraction-eval-flow.svg)

---

## 1. Logical architecture

spread-extraction-eval is a function between an extraction job and a model-change decision: a labeled set and a predictions file in, a result by layout and a gate verdict out. It does not read a statement, run a model or spread anything.

Eight components: four decide the outcome, four support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `se-ingest` | Loads the documents file, the truth and the predictions. Rejects empty, header-only, wrong-type, non-finite, duplicate or truncated input, a bad period and predictions that match no truth. | Python 3.9+, standard library. Prototype: `load_docs`, `load_truth`, `load_predictions`, `_rows`, `_number`, `_keyed` in `src/spread_eval.py` | Yes, by refusing: exit 2 | No |
| `se-registry` | The labeled set per layout, with one layout held out, and the gate limits. Changes only by a reviewed change. | A versioned dataset and a config file (design). Prototype: `data/statements.csv`, `data/truth.csv`, `DEFAULT_FLOOR`, `DEFAULT_MAX_GAP`, `DEFAULT_MIN_DOCS` | Yes, config | Stateful, in git and object storage |
| `se-score` | A value is right within half a dollar. Accuracy by layout, field and error class; statements right in full. | Python. Prototype: `evaluate`, `classify`, `pct` | Yes | No |
| `se-gate` | Fails a layout under the floor or too far under the best layout; skips a layout with too few statements; maps the verdict to an exit code. | Python. Prototype: `gate`, `run_score` | Yes | No |
| `se-tieout` | Tests ten accounting identities on the predictions alone. Advisory: it is printed and does not change the verdict. | Python. Prototype: `tie_out`, `IDENTITIES` | No | No |
| `se-report` | Prints the layout table, pooled accuracy, error classes and the gate reasons. Escapes untrusted strings. | Python. Prototype: `render`, `clean` | No | No |
| `se-standins` | Two rule-based extractors that produce a predictions file for the demo. In production the team's extraction job writes the file. | Python. Prototype: `fixed_label`, `alias_aware` in `src/_standins.py`, `predict` | No | No |
| `se-ledger` | One record per model change: limits, sample hash, per-layout result, verdict (design). Prototype analog: the files the steps write to `src/out/`. | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |

**What decides the outcome.** The input check, the labeled set and limits, the scorer and the gate. The tie-out check is advisory because it cannot see every wrong value, and the report and the ledger carry the result. The scorer needs only a document id, a layout, and the field, period and value of each row; it never reads the statement text.

**Repo structure** (production shape):

```
spread-eval/
├── eval/       # ingest, score, gate, tieout, report
├── registry/   # labeled-set pointers and gate limits per extraction step
├── ledger/     # gate record writer
├── infra/      # terraform for gcp, aws, azure; IAM and bucket policies
├── docs/runbooks/
└── tests/      # unit, golden (planted-set numbers), hostile (injection strings)
```

---

## 2. Physical and deployment architecture

The gate is one short-lived process in the change path of an extraction model or prompt, run after the extraction job has written its predictions.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Gate process | Cloud Build step or Cloud Run job | CodeBuild step or ECS Fargate task | Azure Pipelines step or Container Apps job | Stateless, one pass, runs where the model change is built |
| `se-registry` | Cloud Storage, versioned, customer-managed keys; limits in the repo | S3, versioned, KMS; limits in the repo | Blob Storage, versioned, customer-managed keys; limits in the repo | Real statements stay inside the boundary and a change to the labeled set is visible |
| `se-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The gate must never silently pass. A missing, empty, truncated or mistyped input does not become PASS: it ends the run with exit 2 and a one-line reason. Predictions that match no truth row are an input error. A layout with too few statements is listed as not gated, and if no layout has enough, the run stops.

| Failure | Behavior | Alert |
| --- | --- | --- |
| A file is missing, empty, header only, not UTF-8, has a missing column, a row with too few columns, a non-numeric or non-finite value, a duplicate row or a bad period | Exit 2, one line on stderr | P2 if repeated on one step, else P3 |
| The truth names a document not in the documents file, or no prediction row matches a truth row | Exit 2 with the reason | P3 |
| A threshold outside its range | Exit 2 | P3 |
| No layout has the minimum number of statements | Exit 2: nothing can be gated | P3 |
| A layout has too few statements | Listed as "not gated, too few documents"; the other layouts are gated | P4 |
| A truth value has no prediction | Counted as `missing`, not as correct | P4 |
| Ledger unavailable (design) | The verdict and exit code stand; the record queues locally | P3 |

**Latency.** The prototype is one pass over 5,280 values; I have not timed it. 🔴 Design target: a gate result within 10 minutes of a predictions file landing (planning estimate).

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Statement | `doc_id` | The layout, and for `predict` the text | `data/statements.csv`: `doc_id`, `layout`, `split`, `company`, `text`. The scorer reads `doc_id` and `layout`; `predict` also reads `text` |
| True value | `doc_id`, `field`, `period` | The labeled value in whole dollars | `data/truth.csv`: `doc_id`, `field`, `period`, `value`. 22 fields, current and prior |
| Prediction | `doc_id`, `field`, `period` | The extractor's value, empty for no prediction | A file in the same shape as truth |
| Gate result | layout | Statements, values, correct, error classes, statements right in full | Prototype: `src/out/step_04_summary.json`, `src/out/step_04_results.json` |
| Gate record | `record_id` | Design: model or prompt version, labeled-set hash, limits, per-layout accuracy, verdict, time | None in the prototype |

**Retention** is a design choice, not a measurement: 🔴 7 years by default for gate records and the labeled-set version a record used. Statement text is kept only as long as the labeled set needs it; confirm both against the bank's own schedule.

**Lineage.** A verdict traces back in three hops: the record names the model version, the limits and the labeled-set hash; the versioned store returns the sample; and the scorer is deterministic (no clock, locale or random draw), so re-running `score` on the same files reproduces the table and the reasons.

**Deliberately not stored.** Statement text and company names in the gate record or the logs. The result holds layout names, counts, accuracy and error classes.

---

## 4. Security architecture

**Identity and roles.** The gate runs under the platform's workload identity and has no user account of its own.

| Role | Can | Maps to |
| --- | --- | --- |
| `se:runner` | Read the documents, truth and predictions; write a gate record | The CI service identity |
| `se:labeller` | Write truth values, never for a model change they own | Credit analyst or data steward |
| `se:approver` | Approve a change to the limits or the labeled set, never their own | Model-risk reviewer |

**Secrets.** None. The scorer never calls a model; the job identity reaches the stores through workload identity with no static keys.

**Data classification and what leaves the boundary.** Real statements are confidential customer financials. The scorer's path carries no text, only ids, layouts and values. In the prototype everything is synthetic and nothing leaves the machine. In the design three things leave the job: the exit code, the layout table and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a layout name or id echoed into output | A layout named with a newline and `::error::` text | `clean` writes `%`, carriage return, newline and other control characters as escapes and cuts long text. `tests/test_cli.py` covers a hostile layout |
| Limits changed after the result | A floor lowered so a model passes | Limits live in the reviewed registry; the record stores them; a different approver signs a change |
| The labeled set is edited or leaks into training | Truth values copied into a prompt | Labeler and model owner are different roles; the set is versioned with a hash; the held-out layout stays out of any tuning |
| Customer financials in a log or ticket | A statement pasted into an issue | The README asks for layout and error class, not statements; outputs hold none |

---

## 5. Operational architecture

**SLIs.** Gate runs per week; input rejections; pooled accuracy and worst-layout accuracy per extraction step; layouts failing; statements right in full; labeled-set age; time to a gate result. Prototype baseline: 🟢 best layout 100.0%, worst 68.4%, a spread of 31.6 points (`step_03_deficiencies_exposed.py`).

**SLOs (all 🔴 design targets, none measured).**
- A gate result within 10 minutes of a predictions file landing.
- Every model or prompt change in an in-scope step has a gate record.
- Every failing layout is read by the extraction owner before release (planning estimate).
- 99.9 percent of gate records written to the ledger.

**Alerts.** P2: repeated input rejections, or the ledger down for more than a day. P3: a model released with no gate record, or a failing layout on a step in production. P4: a labeled set older than the review cycle.

**Runbooks** (one page each, in `docs/runbooks/`):
- `layout-failed.md`: read the error classes, fix a rule or a prompt, re-score, route the layout to manual spreading meanwhile.
- `adding-a-layout.md`: label a sample, hold one layout out, write the limits first.
- `changing-the-limits.md`: propose, re-run the planted set, compare with the golden numbers, approve.
- `input-rejected.md`: read the one-line reason, fix the file.

**On-call and ownership.** The extraction owner owns the step, the predictions contract and the runbooks. The data steward owns the labeled set. The model-risk reviewer approves limits. Nobody is paged for a layout that is not gated.

**Change control.** Limits, the tolerance and the identities are versioned. A change needs a proposer and a different approver. Before merge the planted set is re-run and compared with `tests/test_golden.py`, so a change that moves an accuracy shows in the diff.

---

## 6. Alignment and posture

The README's "Aligned to" section cites nothing: no published standard or regulation is cited and none is claimed. The one idea borrowed is ordinary model evaluation practice, to score by slice, because a pooled number depends on the mix of inputs.

- **What the design does.** It scores an extractor by layout, names the layout that slipped and records the verdict before a model change is released.
- **What it does not claim.** It makes no claim of conformity to any standard or regulation, holds no certification, and I have not read or mapped any source.

---

## 7. What is deliberately not here

- **A real model.** The extractors are rules. A model can invent a figure, differ between runs and read a scanned page worse; nothing here measures that.
- **A wrong value the tie-out check cannot see.** 🟢 It passes 15 of the 100 statements `fixed_label` reads wrong, because ignoring the "in thousands" header and swapping the columns keep every identity true (`step_03_deficiencies_exposed.py`).
- **Scanned or noisy input,** multi-page statements, a cash-flow statement, consolidated accounts, other currencies, other languages and restated prior-year figures.
- **Materiality.** A wrong tax line counts the same as a wrong revenue line.
- **Intervals.** The 880 values in a layout come from 20 statements and are not independent; the gate prints statements right in full beside field accuracy.
- **Gate limits from any source.** The floor, the gap and the minimum are my assumptions.
- **Rates on real statements.** The data and the rules share an author, and one stand-in was fixed against the errors of the other, so the numbers are a ceiling.

---

## Appendix: sample contract

The call is the prototype's own. Its output for the bundled `--demo` run is under "Run one now" in the README.

```bash
python3 spread_eval.py score --docs statements.csv --truth truth.csv --predictions mine.csv --floor 95 --max-gap 3 --min-docs 10
```

`statements.csv` needs `doc_id` and `layout`; `truth.csv` and the predictions file need `doc_id`, `field`, `period` (current or prior) and `value`, with an empty value meaning no prediction. A gate reason line reads `thousands_parens: 0.0% is below the floor of 95.0% and 100.0 points below plain_two_column`. Exit status: 0 when the gate passes, 1 when it fails, 2 for bad input.
