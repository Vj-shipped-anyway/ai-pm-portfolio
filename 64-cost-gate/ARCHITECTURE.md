# Architecture: Cost Gate

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/cost_gate.py`, that reads an eval results CSV and a budget file, works out cost per correct answer for the whole run and each slice with an interval, and prints PASS, WARN or FAIL, run here over 40 synthetic change requests of 236 items each. A GitHub Action is staged in `action/` and has not been published or run on GitHub. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![Cost Gate flow](./assets/cost-gate-flow.svg)

---

## 1. Logical architecture

Cost Gate is a function between an eval harness and a merge: two files in, a decision out. It does not run the eval, judge an answer, call a model or read an invoice.

Eight components: five decide the outcome, three support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `cg-ingest` | Loads the budget and the results. Rejects a malformed input with the line number. | Python 3.9+, standard library. Prototype: `parse_budget`, `parse_rows`, `read_results` in `src/cost_gate.py` | Yes, by refusing: exit 2 | No |
| `cg-budget` | Prices, `min_items` and ceilings, changed only by a reviewed change (design). | A reviewed file in the feature repo (design). Prototype: `data/budget.json` | Yes, config | Stateful, in git |
| `cg-cost` | Cost per correct answer for a set of items, and a delta-method interval. | Python. Prototype: `cost_per_correct` | Yes | No |
| `cg-judge` | One status per scope (FAIL, WARN, PASS, THIN, NO_BUDGET, NO_ROWS) and the overall decision. | Python. Prototype: `judge`, `evaluate` | Yes | No |
| `cg-verdict` | Maps the decision to an exit code at `--fail-on`. | Python. Prototype: `DECISION_RANK`, `FAIL_ON_RANK`, the exit logic in `run_check` | Yes | No |
| `cg-report` | Prints text or GitHub annotations and escapes untrusted strings. | Python. Prototype: `render`, `clean`, `escape_annotation` | No | No |
| `cg-action` | Runs the command in a CI job, inputs through environment variables. | Composite GitHub Action, staged in `action/action.yml`, not published | No | No |
| `cg-ledger` | One record per decision, with the input hashes (design). Prototype analog: `src/out/step_04_decisions.csv`. | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |

**What decides the outcome.** The input check, the budget, the cost and interval, the judge and the verdict. The report, the Action wrapper and the ledger carry or record the decision. The gate counts token cost only, reads `correct` as the harness wrote it, and uses the prices it is given.

**Repo structure** (production shape):

```
cost-gate/
├── gate/       # ingest.py, cost.py, judge.py, verdict.py, report.py
├── action/     # composite Action wrapper
├── budgets/    # prices and ceilings per feature, changed by pull request
├── ledger/     # decision record writer
├── infra/      # terraform for gcp, aws, azure
└── tests/      # unit, golden (planted-set numbers), hostile strings
```

---

## 2. Physical and deployment architecture

The gate is one short-lived process in the pipeline that already runs the eval.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Gate process (`cg-ingest` to `cg-report`) | Cloud Build step or Cloud Run job | CodeBuild step or ECS Fargate task | Azure Pipelines step or Container Apps job | Stateless, one pass, runs where the eval runs |
| `cg-budget` | A file in the feature repo | Same | Same | Changes land in the same history as the change it gates |
| Results store | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Versioning keeps the exact bytes a decision used |
| `cg-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The gate must never silently pass. A missing, empty, truncated or mistyped input ends the run with exit 2 and a line number, and that exit fails the CI step even with `--fail-on never`. A scope the gate cannot judge is named, not dropped.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Results or budget missing, empty, truncated, binary or mistyped; a model with no price; an item id that repeats | Exit 2, one line on stderr naming the line, CI step fails | P2 if repeated on one feature, else P3 |
| A slice is in the results and not in the budget, or in the budget and not in the results | WARN, named (`NO_BUDGET`, `NO_ROWS`), so a renamed slice cannot switch its own check off | P3 |
| A slice has fewer than `min_items` items (the whole run: WARN, nothing can be judged) | THIN: printed, not judged alone, still counted in the whole run | P4 in a weekly digest |
| The budget sets no slice ceilings | The report says only the whole run was checked | P4 |
| Price table older than its age limit (design) | WARN | P3 |
| Ledger unavailable (design) | The decision and exit code stand; the record queues locally | P3 |

**Latency.** The prototype is one pass over 236 rows; I have not timed it. 🔴 Design target: a decision within 60 seconds of the eval results file landing.

Recovery is a re-run from the same versioned inputs. The designed interlocks (none built) are in the README.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Eval item | `item_id` | One scored call and its billed tokens | `data/eval_runs.csv`: `cr_id`, `item_id`, `slice`, `model`, `correct`, `input_tokens`, `output_tokens`. The command reads `item_id`, `slice`, `model`, `correct`, `input_tokens`, `output_tokens`; extra columns are ignored |
| Budget | feature | Prices per model, `min_items`, an overall ceiling and a ceiling per slice | `data/budget.json`: `prices_usd_per_1k_tokens`, `min_items`, `overall`, `slices`, each ceiling as `max_cost_per_correct_usd` |
| Scope result | decision and scope | Items, correct, cost per correct answer, interval, ceiling, status | Prototype: the table `render` prints; `src/out/step_04_decisions.csv` |
| Decision record | `decision_id` | Design: feature, input hashes, tool version, statuses, time | Not built |
| Planted truth | `cr_id` | The planted change and whether it is over budget. Exists only because the data is synthetic | `data/cr_truth.csv`: `truth_class`, `true_worst_ratio`, `true_scopes_over` |

🔴 Design default retention, a choice and not a measurement (confirm it against the bank's own schedule): decision records are kept 7 years in PostgreSQL, archived with a retention lock; the results and budget files a decision used are kept as long, in versioned object storage.

**Lineage.** A decision traces back in three hops: the record names the feature, the budget and results hashes and the tool version; the versioned store returns those bytes; and the gate is deterministic (no random number, no clock), so re-running `evaluate` reproduces every status.

**Deliberately not stored.** Prompts, answers and judge output. The gate needs only the slice name, the model name, the correct flag and the billed token counts.

---

## 4. Security architecture

**Identity and roles.** The gate runs under the CI platform's workload identity and has no user account of its own. `cg:runner` reads the results and budget and writes a decision record; `cg:approver` (finance partner or FinOps lead) approves a ceiling or price change, never for their own change; `cg:auditor` reads decisions and config history; `cg:admin` manages roles and buckets.

**Secrets.** The gate holds none and makes no model call, so no vendor key is in its path. The Action passes inputs through environment variables, with `--` before the file arguments; `tests/test_cli.py` covers a path that starts with a dash.

**Data classification and what leaves the boundary.** Slice names, token counts and prices are internal; a real eval set may carry scenario text, which the gate does not need. In the prototype nothing leaves the machine. In the design three things leave the job: the exit code, the annotations and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a slice or model name echoed into a log or annotation | A slice name holding a newline and text that looks like a workflow command | `escape_annotation` rewrites `%`, carriage return and newline; `clean` shows control characters as escapes. `tests/test_cli.py` covers a hostile slice name in text and in an annotation, and a hostile model name in an error |
| A ceiling is raised or a price lowered to make a FAIL go away | `max_cost_per_correct_usd` edited in the same pull request as the change | Budget changes need a different approver; every decision stores the budget hash |
| The results file is edited, or the harness under-reports tokens | A `correct` flag flipped, or retries left out of the billed count | Versioned storage and a stored hash; a changed hash is an alert. The gate cannot see under-reporting, so the design asks for a harness test against the invoice |
| A slice is renamed so its check stops | `card_services` becomes `cards` | `NO_BUDGET` and `NO_ROWS` raise a named WARN for both names |

---

## 5. Operational architecture

**SLIs.** Decisions per status per feature per week; THIN and unmatched slices; price age; budget changes per quarter; input rejections; FAILs overturned after review; time to a decision (prototype baseline on the planted set: 🟢 20 of 40 change requests a person reads and 0 of 19 within-budget ones stopped, `step_04_with_cost_gate.py`).

**SLOs (all 🔴 design targets, none measured).**
- A decision within 60 seconds of the eval results file landing.
- Every production change to an in-scope feature passes through the gate and leaves a decision record.
- Every FAIL read by a named person within one business day (planning estimate).
- 99.9 percent of decisions written to the ledger.

**Alerts.** P2: repeated input rejections on one feature, or the ledger down for a day. P3: a FAIL on a production feature (also to the finance partner), an unmatched slice, a stale price table, or a changed hash. P4: a weekly digest of WARN decisions and THIN slices.

**Runbooks** (one page each, in `docs/runbooks/`):
- `fail-on-a-slice.md`: read the slice, its interval and ceiling; fix the change or move the ceiling.
- `changing-a-ceiling.md`: the pull request, the baseline run, the second approver, a re-run.
- `updating-prices.md`: read the vendor's price page, change the table, re-run the planted set.
- `thin-slice.md`: grow the slice to `min_items` or read it by hand.

**Ownership.** The feature engineer owns the gate step and the runbooks. The finance partner owns the ceilings. The FinOps lead owns the price table.

**Change control.** Rules, prices and ceilings are versioned; a change needs a proposer and a different approver. Before merge, the planted set is re-run against the numbers pinned in `tests/test_golden.py`, so a change that moves the stopped count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites one source, restated with the same wording about what was read: the [FinOps Foundation framework](https://www.finops.org/framework/), which I read on 2026-10-24 (the pages show no revision date). Its Unit Economics capability pairs spend with a measure of value; cost per correct answer is my reading of a unit metric between its two examples, measured on an eval rather than live traffic. Its Budgeting capability expects spend limits, a comparison of actual spend with the limit, and a defined response when spend nears a budget line, such as an alert, an approval gate or a throttle. The page also lists suggested variance limits of 20%, 15% and 12% by maturity level; those describe the gap between budget and actual spend, and I did not derive my ceilings from them.

- **What the design does.** It acts as the approval gate on a pull request, before the spend exists, and keeps a record of the budget and prices it used.
- **What it does not claim.** It does not forecast the invoice. It is not compliant with the framework or any other standard, holds no certification, and I have not read or mapped any other source.

---

## 7. What is deliberately not here

- **Over-budget changes that still pass.** 🟢 3 of 21 PASS (`step_04_with_cost_gate.py`): CR-010 and CR-024 regress inside a 12-item slice, below `min_items`, and CR-029 sits at 1.018 times its ceiling, inside the noise of 236 items.
- **A stricter default.** With `--fail-on fail`, 🟢 5 WARN and 3 PASS over-budget change requests still merge unless a person acts (`step_04_with_cost_gate.py`).
- **Grader noise and multiple comparisons.** The interval counts only which items were sampled; if `correct` comes from a judge, its error is outside it. Up to six scopes are judged per run with no correction.
- **Costs other than tokens, and quality.** No latency, caching discount, batch price or per-request fee. A cheaper model that answers worse can sit inside the ceiling; pair the gate with an accuracy check.
- **Production traffic and a published Action.** An eval set is not live traffic, so a ceiling guards a change and does not forecast spend. A Marketplace listing is a later, separate step.

---

## Appendix: sample contract

The call is the prototype's own. Its output for the bundled `--demo` run is under "Run one now" in the README.

```bash
python3 cost_gate.py check results.csv budget.json --fail-on fail --format github
```

Results need `item_id, slice, model, correct, input_tokens, output_tokens` (one run per file). The budget needs `prices_usd_per_1k_tokens`, `overall` and, optionally, `min_items` and `slices`. Exit status: 0 below `--fail-on`, 1 at or above it, 2 for bad input.
