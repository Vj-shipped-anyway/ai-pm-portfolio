# Architecture: swapbrief

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/swapbrief.py`, that reads a results file and a prices file for a baseline and a candidate model, pairs the items, computes seeded paired bootstrap intervals, applies fixed thresholds and prints GO, GO WITH GUARDRAILS or NO-GO with rollback triggers, run here over a committed set of 600 paired items and 80 simulated migrations. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![swapbrief flow](./assets/swapbrief-flow.svg)

---

## 1. Logical architecture

swapbrief is a function between an evaluation harness and a launch decision: two files and two system names in, a brief out. It does not run the evaluation, grade an answer or call a model.

Eight components: five decide the outcome (one as config), three report or record it.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `sb-ingest` | Reads both files, matches systems by exact text, pairs items, refuses bad input. | Python 3.9+, standard library. Prototype: `read_results`, `read_prices`, `build_pairs`, `_read_rows` in `src/swapbrief.py` | Yes, by refusing: exit 2 | No |
| `sb-stats` | Seeded paired bootstrap intervals for accuracy, cost, p50, p95 and each slice. | Python. Prototype: `_bootstrap`, `_interval`, `percentile` | Yes | No |
| `sb-rules` | Intervals into statuses: slice (REGRESSED to IMPROVED) and ratio (BLOCK, WATCH, OK). | Python. Prototype: `slice_status`, `ratio_status`, `headline_rule` | Yes | No |
| `sb-verdict` | Collects block and guard reasons, picks the decision, sets the exit code. | Python. Prototype: `analyze`, `exit_code` | Yes | No |
| `sb-triggers` | Writes the rollback triggers: metric, threshold, window, action. | Python. Prototype: `triggers`, `WINDOWS` | No | No |
| `sb-report` | Prints text or JSON. Escapes names from the files. | Python. Prototype: `render_text`, `clean`, `--format json` | No | No |
| `sb-policy` | Thresholds, windows and critical slices per feature, by review (design). Prototype: `POLICY`, `--tolerance-pp`, `--critical` | Reviewed config in the platform repo | Yes, config | Stateful, in git |
| `sb-ledger` | One record per brief (design). Prototype analog: `src/out/step_04_brief.json` | PostgreSQL and object storage (design) | No | Stateful |

**What decides the outcome.** The input check, the interval, the thresholds and the verdict. The triggers, the report and the ledger carry or record the decision. The tool does not judge answers: `correct` is the grade the harness wrote, and the brief is only as good as that grade and the sample behind it.

**Repo structure** (production shape):

```
swapbrief/
├── brief/      # ingest, stats, rules, verdict, triggers, report
├── policy/     # thresholds, windows, critical slices per feature, by pull request
├── ledger/     # brief record writer
├── docs/runbooks/
└── tests/      # unit, golden (simulated-set numbers), hostile (injection strings)
```

---

## 2. Physical and deployment architecture

One short-lived process, run when an evaluation export lands for a migration. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Brief process | Cloud Build step or Cloud Run job | CodeBuild step or ECS Fargate task | Azure Pipelines step or Container Apps job | Stateless, one pass, runs next to the harness |
| Export store | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Keeps the bytes a brief used |
| `sb-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | Already run by the platform team |

**Failure behavior (the decision that matters most).** The tool must never silently pass. A file it cannot use does not become GO: it exits 2 with a one-line reason. A sample too thin to rule a loss out does not become GO either; it becomes a guardrail.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Results or prices file empty, header only, a column missing, a wrong field count or a wrong-type value | Exit 2, one line on stderr naming the line | P2 if repeated, else P3 |
| An item missing for one system, a duplicate row, a slice that differs between systems, a system name that matches no row, or an unknown `--critical` slice | Exit 2 with the reason | P3 |
| Fewer than 30 paired items, a system with fewer than 5 correct answers, both prices zero for one system | Exit 2: the ratios are not defined | P3 |
| A critical slice too small to rule a loss out | Status INCONCLUSIVE; decision GO WITH GUARDRAILS and a trigger for that slice | P4 digest |
| A file cut exactly between two items | Looks complete; known limit. In the design a harness manifest with row count and hash is checked | P3 |
| Ledger unavailable (design) | The brief and exit code stand; the record queues locally and the gap is listed | P3 |

**Latency.** The prototype is untimed. 🔴 Design target: a brief within 5 minutes of an evaluation export landing.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Result row | `item_id`, `system` | Grade, tokens and latency for one item under one system | `data/results.csv`: `item_id`, `slice`, `system`, `correct`, `input_tokens`, `output_tokens`, `latency_ms` |
| Price | `system` | Price per 1,000 input and output tokens | `data/prices.csv`: `system`, `input_usd_per_1k`, `output_usd_per_1k` |
| Slice | `slice` | Critical flag, size, description | `data/slices.csv`: `slice`, `critical`, `n_items`, `description`. The tool takes critical slices from `--critical` |
| Brief | brief id (design) | Decision, reasons, intervals, slice statuses, triggers, limits, seed | Prototype: `src/out/step_04_brief.json` |
| Planted truth | `scenario` | The true effects of a simulated migration and its labels | `data/scenario_truth.csv`, `data/committed_truth.csv`, `data/committed_world.json`. Exist only because the data is synthetic |

**Retention** is a design choice, not a measurement; confirm it against the bank's own record-retention schedule. 🔴 Design default: briefs, limits and seed for 7 years in PostgreSQL archived with a retention lock; the exports a brief used for as long as the brief, in versioned storage.

**Lineage.** A decision traces back in three hops: the record names the file hashes, limits, seed and resample count; the versioned store returns those bytes; and the bootstrap is seeded, so re-running `analyze` reproduces the intervals and the decision. In the prototype the trace is `step_04_brief.json` plus the committed files.

**Deliberately not stored.** Prompts, answers, grader rationales and customer text. The tool needs a grade, token counts, a latency and a slice label per item.

---

## 4. Security architecture

**Identity and roles.** The tool runs under the CI platform's workload identity and has no user account of its own. `sb:runner` reads the export and the policy file and writes a brief record. `sb:approver` approves a limit or critical-slice change, never for their own migration. `sb:auditor` reads briefs and config history. `sb:admin` manages roles, buckets and the ledger.

**Secrets.** The tool holds none and calls no model, so no vendor key is in its path. Store and ledger access is by workload identity, with no static keys.

**Data classification and what leaves the boundary.** Item ids, slice names, grades, token counts and latencies are internal. Case text, if a real export carried it, is confidential and not needed. In the prototype nothing leaves the machine. In the design three things leave the job: the exit code, the brief and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a slice or system name echoed into a log or a workflow command | A slice name holding a newline and text that looks like a command | `clean` rewrites `%`, and every control character. `tests/test_cli.py` covers hostile names |
| A limit is loosened to turn a NO-GO into a GO | `cost_block` moved from 1.25 to 2.0 | Limits live in `sb-policy`, change by pull request with a different approver, and the brief stores the limits it used |
| The seed is varied until an interval is favorable | Re-running with new seeds | The default seed is fixed and the brief stores the seed and resample count |
| The export is edited | `correct` flipped on the candidate's rows | Versioned storage and a stored hash; a changed hash for a finished brief is an alert |
| The grade is not honest | A harness that grades the candidate more kindly | The tool cannot see this. The design asks the evaluation owner for a harness contract test |

---

## 5. Operational architecture

**SLIs.** Briefs per decision per feature; input rejections; paired items per brief; size of the smallest critical slice; briefs with INCONCLUSIVE critical slices (prototype baseline on good migrations: 🟢 19 of 35 get guardrails, `step_04_with_swapbrief.py`); time to a brief.

**SLOs (all 🔴 design targets, none measured).**
- A brief within 5 minutes of an export landing.
- Every in-scope migration decided with a brief and a ledger record.
- Every NO-GO read by a named person within one business day (planning estimate).
- 99.9 percent of briefs written to the ledger.

**Alerts.** P2: repeated input rejections on one feature, or the ledger down for more than a day. P3: a NO-GO on a production migration, or a changed hash for a finished brief. P4: a weekly digest of GO WITH GUARDRAILS and INCONCLUSIVE critical slices.

**Runbooks** (one page each, in `docs/runbooks/`):
- `no-go-brief.md`: read the reasons, then fix the cause, run a bigger sample or escalate.
- `thin-critical-slice.md`: add items to the slice, or accept the guardrail with its trigger in writing.
- `export-rejected.md`: read the reason, fix the export, re-run.
- `changing-a-limit.md`: propose, re-run the simulated set, compare, approve.

**On-call and ownership.** The platform lead owns the runner, the export contract and the runbooks. The evaluation owner owns the harness and the grades. The model risk reviewer approves limits. Nobody is paged for a guardrail.

**Change control for rules and thresholds.** Rules and limits are versioned in the repo. A change needs a proposer and a different approver. Before merge, the simulated set is re-run and compared with the numbers pinned in `tests/test_golden.py`, so a change that moves the false-GO count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites one source, restated with the same wording about what was read: the FSB's [Sound Practices for Responsible Adoption of Artificial Intelligence](https://www.fsb.org/uploads/P151026-1.pdf) (final report, 15 October 2026; I read it on 24 October 2026). Sound Practice 9 on performance management asks institutions to assess AI performance over time and lists recent changes to the model or system among the factors that set how often and how hard to assess; it also describes results that can indicate contingency plans should be triggered. Sound Practice 12 covers third-party AI providers and business continuity. The report does not mention cost per correct answer or p95 latency; those are my additions.

- **What the design does.** It treats a model migration as such a change: it compares the two versions on paired items and writes the contingency trigger down before launch.
- **What it does not claim.** It makes no claim of conformity to the report, monitors nothing after launch, and I have not read or mapped any other source.

---

## 7. What is deliberately not here

- **Judging answers.** `correct` is the harness's grade. The tool does not check it, compare prompts or confirm that latency is measured the same way for both systems.
- **Monitoring after launch.** The triggers are text for the launch plan. Wiring them to a monitor is not built.
- **Every slice regression.** 🟢 4 of 26 true slice regressions pass unflagged (`step_04_with_swapbrief.py`), and a file cut between two items looks complete.
- **A real evaluation export.** Nothing was tested on one. The data and the rules share an author, so the rates are a ceiling for worlds I defined.
- **Limits from a rule.** The thresholds are assumptions copied from project 13; only `--tolerance-pp` is on the command line.
- **A margin for the headline rule.** The rule is "accuracy not lower"; a team that requires a margin would behave differently, and I did not test that.
- **Price changes over time, hosting, or a model call.**

---

## Appendix: sample contract

```bash
python3 swapbrief.py brief results.csv prices.csv --baseline current-model --candidate successor-model \
    --critical card_disputes,wire_exceptions --fail-on nogo --format json
```

The JSON carries `decision`, `block_reasons`, `guard_reasons`, `accuracy`, `cost`, `latency`, `slices`, `triggers` and the `policy` used. Each trigger holds `metric`, `threshold`, `window` and `action`. Exit status: 0 below `--fail-on`, 1 at or above it, 2 for bad input.
