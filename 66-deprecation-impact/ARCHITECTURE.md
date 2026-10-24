# Architecture: Deprecation Impact

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/deprecation_impact.py`, that reads a model catalog, an alias table, a feature register and a usage list, resolves every model string, dates each hit against the lead time the feature needs and prints a calendar, a hit list and a check queue, run here over a synthetic register of 60 features. No CI Action is staged. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![Deprecation Impact flow](./assets/deprecation-impact-flow.svg)

---

## 1. Logical architecture

Deprecation Impact is a function over four exports and a date: a catalog, an alias table, a register and a usage list in, a dated list of features out. It does not fetch a notice, call a model or migrate anything.

Eight components: four decide the outcome, four support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `di-ingest` | Loads the four files and the policy. Rejects an empty, truncated, wrong-type or duplicate input, a usage that names no feature, an alias that names no model, and a base-model chain that loops. | Python 3.9+, standard library. Prototype: `load_models`, `load_aliases`, `load_features`, `load_usages`, `load_policy` in `src/deprecation_impact.py` | Yes, by refusing: exit 2 | No |
| `di-resolve` | Maps one model string to hit, clear or check: exact id, alias with its recorded date, family name, or the base of a fine-tune. | Python. Prototype: `resolve`, `retirement` | Yes | No |
| `di-tier` | Days left, the lead time the feature needs, slack, and a tier: PAST, LATE, TIGHT, ROOM or SUNSETS. | Python. Prototype: `lead_days`, `tier_of`, `_dep` | Yes | No |
| `di-cost` | Monthly cost now and on the named successor, from calls, tokens and the price table. | Python. Prototype: `monthly_cost` | No, a view | No |
| `di-verdict` | Takes the worst tier among hits and maps it to an exit code at `--fail-on`. | Python. Prototype: `worst`, `FAIL_TIERS`, `run_report` | Yes | No |
| `di-report` | Prints the calendar, hits and check queue as text or JSON; strips control characters from untrusted strings. | Python. Prototype: `render_text`, `clean` | No | No |
| `di-ledger` | Appends one record per run (design). Prototype analog: `src/out/step_04_dependencies.csv`. | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |
| `di-telemetry` | Counts hits by tier, check entries and rejections, off the decision path (design). | OpenTelemetry | No | No |

**What decides the outcome.** The input check, the resolver, the tier arithmetic and the verdict. The cost view, the report, the ledger and telemetry inform or record. The tool trusts the registry: a dependency no row records is invisible to it.

**Repo structure** (production shape):

```
deprecation-impact/
├── impact/     # ingest, resolve, tier, cost, verdict, report
├── policy/     # lead times and the alias age limit, changed by pull request
├── ledger/     # impact record writer
├── jobs/       # scheduled run and run-on-new-notice definitions
├── infra/      # terraform for gcp, aws, azure; IAM
├── docs/runbooks/
└── tests/      # unit, golden, hostile strings
```

---

## 2. Physical and deployment architecture

The tool is one short-lived process, started on a schedule and when a notice is entered in the catalog. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Impact process (`di-ingest` to `di-report`) | Cloud Run job started by Cloud Scheduler | ECS Fargate scheduled task | Container Apps job on a schedule | Stateless, one pass, no inbound traffic |
| Policy file (lead times, alias age limit) | A file in the repo | Same | Same | A lead-time change lands in the same history as the code |
| Catalog, alias, register and usage exports | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Versioning keeps the exact bytes a record used |
| `di-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |
| `di-telemetry` | OTel Collector to Cloud Monitoring | To CloudWatch | To Azure Monitor | Off the decision path |

**Failure behavior (the decision that matters most).** The tool must never silently clear. Unreadable input does not become an empty hit list: the run ends with exit 2 and a one-line reason. A string that cannot be resolved is a check entry, never clear, and a feature with no usage row is a check entry too.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Any file missing, empty, truncated, with a bad date, number or role, a duplicate id, or a policy key it does not know | Exit 2, one line on stderr naming the file and line | P2 if repeated on one schedule, else P3 |
| A usage names a feature not in the register; an alias or a base model names a model not in the catalog; a base-model chain loops | Exit 2 with the reason | P3 |
| Usage file has a header and no rows | Every feature lands in the check queue as "no model is recorded" | P3 |
| No usage resolves to a model with a notice | Prints that line, so a quiet run is visible | None |
| `--model` names a model with no notice | Exit 2 | P4 |
| An export is older than its expected refresh (design) | The run stops with exit 2 and names the stale export | P2 |
| Ledger or telemetry unavailable (design) | The hit list and exit code stand; the record queues locally | P3 |

**Latency.** The prototype is one pass over small files; I have not timed it. 🔴 Design target: a refreshed hit list within 10 minutes of a notice being entered in the catalog. Recovery is a re-run from the same versioned exports and policy.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Model | `model_id` | Family, notice and retirement dates, successor, prices, base model for a fine-tune | `data/models.csv`: `model_id`, `family`, `vendor`, `notice_date`, `retire_date`, `successor`, `input_usd_per_1m`, `output_usd_per_1m`, `successor_input_token_factor`, `base_model_id` |
| Alias | `alias` | The snapshot it was recorded as pointing to, and when | `data/aliases.csv`: `alias`, `model_id`, `recorded_on` |
| Feature | `feature_id` | Owner, criticality, evaluation-set flag, sunset date | `data/features.csv`: `feature_id`, `feature_name`, `owner_team`, `business_line`, `criticality`, `has_eval_set`, `sunset_date` |
| Usage | `usage_id` | The model string a feature names in a role, with calls and tokens | `data/usages.csv`: `usage_id`, `feature_id`, `role`, `model_ref`, `config_path`, `monthly_calls`, `avg_input_tokens`, `avg_output_tokens` |
| Dependency result | `feature_id`, `role` | Verdict, tier, days left, lead time, slack, note, costs | Prototype: `src/out/step_04_dependencies.csv` and the JSON output |
| Impact record | `record_id` | Design: as-of date, policy, SHA-256 of the four exports, tool version, hits, check queue | Design only |
| Planted truth | `feature_id`, `role` | The kind planted and whether the dependency is affected | `data/truth_dependencies.csv`, `data/truth_aliases.csv`. The tool never opens them |

**Retention** is a design choice, not a measurement; confirm it against the bank's own record-retention schedule. Impact records and the exports they used: 🔴 7 years (design default), in PostgreSQL archived to versioned object storage with a retention lock.

**Lineage.** A tier traces back in three hops: the record names the as-of date, the policy and the hash of the four exports; the versioned store returns those bytes; and the rules are deterministic (the date is an argument, no clock or random draw, results sorted), so re-running `analyze` reproduces the hit. In the prototype the trace is a row naming the feature, role, model string, resolved model and `note`, such as "built on" a base or "alias recorded".

**Deliberately not stored.** Prompts, responses, source code and vendor credentials. The tool needs the model string, the role, calls and token counts; `config_path` is kept only as a pointer for the owner.

---

## 4. Security architecture

**Identity and roles.** The tool runs under the platform's workload identity and has no user account of its own.

| Role | Can | Maps to |
| --- | --- | --- |
| `di:runner` | Read the exports and the policy; write an impact record | The scheduled job's identity |
| `di:approver` | Approve a lead-time or alias-age change | Platform lead with a feature owner as second approver |
| `di:auditor` | Read records, hits and policy history | Internal audit |
| `di:admin` | Manage roles, buckets and the ledger | Platform engineering lead |

**Secrets.** None. The tool never calls a model or a vendor, so no vendor key is in its path. The job reaches exports and ledger through workload identity, with no static keys.

**Classification and what leaves the boundary.** Feature names, owner teams, call volumes and model strings reveal which products depend on which vendor; treat them as confidential. In the prototype nothing leaves the machine. In the design three things leave the job: the exit code, the report and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in an input field echoed into a log or report | A `feature_name` or `model_ref` holding a newline and text that looks like a CI command or a hit line | `clean` writes control characters as escapes. `tests/test_cli.py` covers a hostile feature name, a hostile error message, and that JSON structure is unchanged |
| A usage row is edited so a dependency disappears | A `model_ref` changed to an unknown string after the fact | An unknown string is a check entry, not clear; versioned exports; the record stores the hashes |
| A lead time or the alias age limit is changed to hide a tier | LATE becomes ROOM after a lead time is cut | Pull request with a different approver; every record stores its policy |
| A stale alias entry hides a retirement | An alias recorded long ago still points at the old snapshot | The age limit sends it to the check queue; the design refreshes the table on each run. The tool cannot see a recent wrong entry |
| A dependency is not in the registry | A fallback used in code and in no row | The tool cannot see this. The design fills the registry from service configuration |

---

## 5. Operational architecture

**SLIs.** Hits per tier per notice; check entries open and their age; input rejections; usage rows with a `config_path`; share of features with a recorded model in every role (prototype baseline: 🟢 29 of 42 affected dependencies found and dated, `step_04_with_map.py`); time from notice to hit list.

**SLOs (all 🔴 design targets, none measured).**
- A refreshed hit list within 10 minutes of a notice being entered in the catalog.
- Every check entry opened by a named owner within one business day (planning estimate).
- Every LATE or PAST hit has a ticket with an owner within one business day (planning estimate).
- 99.9 percent of runs written to the ledger.

**Alerts.** P2: repeated input rejections, a stale export, or the ledger down for more than a day. P3: a new PAST or LATE hit, which also goes to the feature owner. P4: a weekly digest of check entries older than a week.

**Runbooks** (one page each, in `docs/runbooks/`):
- `new-notice.md`: enter the notice, run the tool, read the hits and the check queue.
- `check-entry.md`: find what the string really calls, pin it or correct the registry, re-run.
- `input-rejected.md`: read the reason, fix the export, re-run.
- `changing-a-lead-time.md`: propose, re-run the planted set, compare with the golden numbers, approve.

**On-call and ownership.** The platform owner owns the schedule, the policy and the runbooks. Each feature owner owns their usage rows and the move. The vendor manager owns the notice dates in the catalog.

**Change control.** The resolver and the policy are versioned. A change needs a proposer and a different approver. Before merge, the planted set is re-run and compared with the numbers pinned in `tests/test_golden.py`, so a change that moves a tier count shows in the diff. Rollout is shadow, calibration, then enforcement, as the PRD lays out.

---

## 6. Alignment and posture

The README's "Aligned to" section cites nothing published: it claims no alignment with a standard, regulation or vendor policy, and the vendors, model names, notice dates and prices are made up. This design restates that and adds nothing.

- **What the design does.** It records which feature depends on which model, with a date and a tier, so a retirement can be planned. That is an engineering practice of mine, not a requirement I am citing.
- **What it does not claim.** It is not compliant with any standard, holds no certification, and I have not read or mapped any source to it.

---

## 7. What is deliberately not here

- **Dependencies no registry row records.** 🟢 7 of 42 affected dependencies pass with no flag: 4 unrecorded fallbacks and 3 behind a recent wrong alias entry (`step_04_with_map.py`).
- **Reading code or configuration to find model strings.** A model chosen at run time from a list kept elsewhere is invisible unless the usage file says what it chooses from.
- **Embedding models and re-indexing.** Only three roles exist: primary, fallback and judge.
- **Fetching vendor notices.** Filling the catalog from a vendor page is not built and not tested.
- **Real lead times and prices.** Lead times are my assumptions and decide the tiers; prices are made up, and output tokens are held fixed.
- **Fine-tune successors.** A fine-tune has no priced successor because it must be retrained.
- **Migrating or testing the successor.** A hit is a date and a tier, not a plan.
- **A measured rate on real data.** The data and the rules share an author, so 29 of 42 is a ceiling, not a rate on a real register.

---

## Appendix: sample contract

The call is the prototype's own; its `--demo` output is under "Run one now" in the README.

```bash
python3 deprecation_impact.py report --features features.csv --usages usages.csv --models models.csv --aliases aliases.csv --as-of 2026-09-01 --fail-on late
```

One usage row, with the columns the resolver reads:

```text
usage_id,feature_id,role,model_ref,config_path,monthly_calls,avg_input_tokens,avg_output_tokens
U-0001,FT-001,primary,va-fast-lite@2025-06,svc/reconciliation-explainer-retail/config.yaml:primary_model,60000,1650,330
```

Exit status: 0 when the worst tier is below `--fail-on`, 1 when it is at or above it, 2 for bad input.
