# Architecture: Tag Chargeback

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/tag_chargeback.py`, that reads one month of a billing export, a cost-center registry, an account map and a tag policy, allocates each line by rule and reports what nobody owns, run over a synthetic bill of 1,284 lines. There is no model call, no billing feed and no real cloud account. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![Tag Chargeback flow](./assets/tag-chargeback-flow.svg)

---

## 1. Logical architecture

Tag Chargeback is a monthly batch function: four files in, a chargeback by cost center and a list of unallocated spend out. It does not fetch a bill, change a tag or choose a shared-cost basis.

Eight components: five decide the outcome, three support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `tc-ingest` | Loads the four files. Rejects a bad column, date, amount, tag JSON or duplicate `line_id`, a bill that spans months, and a bill with no positive net spend. | Python 3.9+, standard library. Prototype: `load_bill`, `load_policy`, `load_cost_centers`, `load_accounts`, `_parse_usd`, `_parse_tags` in `src/tag_chargeback.py` | Yes, by refusing: exit 2 | No |
| `tc-policy` | Required tags, aliases, shared services, the registry, the account map and the limit. Changes by reviewed change. | Reviewed files (design). Prototype: `data/policy.json`, `cost_centers.csv`, `accounts.csv`, `alloc_spec` | Yes, config | Stateful, in git |
| `tc-rules` | Rules 0 to 5, first match wins: zero cost, tag, shared split, inherit, account default, unallocated with a reason. | Python. Prototype: `allocate`, `resolve_direct`, `split_amount` | Yes | No |
| `tc-compliance` | Counts lines that carry every required tag, strict and after repair. Does not change the allocation. | Python. Prototype: `line_compliance`, `compliance_summary` | No | No |
| `tc-summary` | Totals by cost center and by reason, checks allocated plus unallocated equals the bill, and sets the exit code against the limit. | Python. Prototype: `summarize`, `run_report` | Yes, as the exit code | No |
| `tc-report` | Prints text or GitHub annotations and writes the chargeback and line CSVs, escaping bill text. | Python. Prototype: `render_text`, `render_github`, `write_chargeback`, `write_lines`, `clean`, `escape_annotation` | No | No |
| `tc-ledger` | One record per billing month (design). | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |
| `tc-telemetry` | Counts runs, rejections and the unallocated share, off the decision path (design). | OpenTelemetry to the platform's monitoring | No | No |

**What decides the outcome.** The input check, the policy, the rules, the summary and the exit code. The report, ledger and telemetry carry or record it. The rules read a tag as written, with case and spaces repaired, and cannot tell that a valid tag names the wrong team.

**Repo structure** (production shape):

```
tag-chargeback/
├── chargeback/ # ingest.py, rules.py, compliance.py, summary.py, report.py
├── policy/     # tag policy, registry, account map, changed by pull request
├── job/        # monthly batch wrapper (design)
├── ledger/     # run record writer
├── infra/      # terraform for gcp, aws, azure
└── tests/      # unit, golden, hostile strings
```

---

## 2. Physical and deployment architecture

One monthly batch job, started when the provider's billing export lands in object storage. It reads files and never calls the provider.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Job (`tc-ingest` to `tc-report`) | Cloud Run job on a schedule | ECS Fargate scheduled task | Container Apps job | Stateless, once a month, no server to keep warm |
| Billing export and outputs | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | The exact bytes a month used can be returned |
| `tc-policy` | Files in the repo | Same | Same | A policy change lands in the same history as the code |
| `tc-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |
| `tc-telemetry` | OTel Collector to Cloud Monitoring | To CloudWatch | To Azure Monitor | Off the decision path |

**Failure behavior (the decision that matters most).** The tool must never silently pass. A missing, empty, truncated or mistyped input does not become a chargeback: the run ends with exit 2 and a one-line reason. A line that cannot be placed becomes unallocated with a reason, not a quiet default.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Bill missing, empty, header only, truncated, bad date, bad amount, bad tag JSON, duplicate `line_id` | Exit 2 with the row and the reason | P3 |
| Bill spans more than one month, or net spend is not positive | Exit 2: run one billing month at a time | P3 |
| Policy, registry or account map malformed; output path unwritable | Exit 2 with the reason | P3 |
| An account on the bill is not in the account map | Named in the report; its lines are placed by tag or left unallocated | P3 to the finance lead |
| Nothing matches any rule | Said out loud in the report, never an empty success | P3 |
| Partial billing feed (design) | The job compares the row count and total with the provider's invoice and refuses to publish on a mismatch | P2 |
| Ledger or telemetry down (design) | The chargeback and exit code stand; the record queues locally | P3 |

**Latency.** The prototype handles 1,284 lines; I have not timed it at any scale. 🔴 Design target: a monthly allocation of a 100-million-line export within 30 minutes. A job that misses it would need a streaming pass and a partitioned sort for the inherit rule, which I have not designed in detail.

Recovery is a re-run from the same versioned bill, policy and registry.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Billing line | `line_id` | A day, an account, a service, a resource, a cost and the tags as typed | `data/billing_export.csv`: `line_id`, `usage_date`, `account_id`, `service`, `resource_id`, `usage_type`, `cost_usd`, `tags_json` |
| Cost center | `cost_center` | Name, business line, owner team, whether it is active | `data/cost_centers.csv`: `cost_center`, `name`, `business_line`, `owner_team`, `active` |
| Account | `account_id` | A name, a default cost center, whether it is shared | `data/accounts.csv`: `account_id`, `account_name`, `default_cost_center`, `shared` |
| Policy | version | Required tags, aliases, shared services, the unallocated limit | `data/policy.json` |
| Allocation | `line_id` | The cost center, the rule that placed it and the reason if unallocated | Prototype: `--lines-csv` output and `src/out/step_04_chargeback.csv` |
| Planted truth | `line_id` | The true owner, the defect planted, whether the line is compliant | `data/billing_truth.csv`: `true_cost_center`, `defect_kind`, `compliant`. Synthetic data only |

**Retention** is a design choice; confirm each value against the bank's own schedule. 🔴 Design defaults: billing exports, allocations and run records 7 years, in versioned object storage with a retention lock; policy versions as long as the months that used them.

**Lineage.** A charge traces back in three hops: the allocation line names the rule, the reason and the cost center; the run record names the bill hash, the policy and registry versions and the tool version; and the rules are deterministic (first match wins, money in integer millionths, sorted output), so a re-run reproduces the month. In the prototype the trace is a row of the `--lines-csv` file.

**Deliberately not stored.** Usage content, application data and anything beyond what the export carries. Tag values are kept as written, because that is the evidence.

---

## 4. Security architecture

**Identity and roles.** The job runs under the finance project's workload identity and has no user account of its own.

| Role | Can | Maps to |
| --- | --- | --- |
| `tc:runner` | Read the export and policy, write allocations and a run record | The job identity |
| `tc:finance` | Read results, dispute a charge | Cloud finance |
| `tc:approver` | Approve a policy change, never their own | Controller |
| `tc:auditor` | Read allocations, records and policy history | Internal audit |
| `tc:admin` | Manage roles, buckets and the ledger | Platform engineering lead |

**Secrets.** The tool holds none and calls no cloud API. The job reads the export bucket through workload identity, read-only.

**Data classification and what leaves the boundary.** The export names accounts, resources and what each team spends: internal, and confidential once joined to cost-center owners. Tag values are typed by people, so they are untrusted text. In the prototype nothing leaves the machine and every row is synthetic. In the design three things leave the job: the chargeback, the unallocated list and a run record.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile resource id or tag value echoed into a log or annotation | A resource id holding a newline and text that looks like a workflow command | `clean` writes control characters as visible escapes; `escape_annotation` rewrites `%`, carriage return and newline. `tests/test_cli.py` covers a hostile resource id in an annotation and in text, and a hostile value in an error |
| A team tags its resource with another team's cost center | A valid tag that moves cost to a neighbor | The tool charges it as tagged. Design: only the platform pipeline may write the cost-center tag, and an application-owner list cross-checks it. Neither is built |
| A policy edited to shift who pays | A shared-cost basis or alias changed | Reviewed policy with a different approver; every run record stores the policy version |
| The bill or registry edited after the month closes | A closed cost center reopened | Versioned storage; the record stores both hashes; a changed hash for a closed month is an alert |

---

## 5. Operational architecture

**SLIs.** Unallocated share of net spend per month (prototype baseline: 🟢 5.2%, `step_04_with_tool.py`); allocated plus unallocated equals the bill; tag compliance strict and repaired; dollars by rule; run rejections; run time; charges disputed after close.

**SLOs (all 🔴 design targets, none measured).**
- A monthly allocation of a 100-million-line export within 30 minutes.
- The chargeback published within two business days of month end (planning estimate).
- Every month reconciles to the bill to the cent, or it is not published.

**Alerts.** P2: a partial feed, or a reconciliation mismatch. P3: a rejected input, an account missing from the map, or the unallocated share above the limit. P4: a monthly digest of the largest unallocated resources.

**Runbooks** (one page each, in `docs/runbooks/`):
- `bill-rejected.md`: read the row and reason, ask the owner of the export, re-run.
- `unallocated-over-limit.md`: rank by dollars, send the list to the platform lead, decide whether to publish.
- `changing-the-policy.md`: propose, re-run the planted bill, compare with the golden numbers, approve.
- `closing-a-month.md`: lock the inputs, hash them, write the record.

**On-call and ownership.** The cloud finance lead owns the job and the runbooks. The platform lead owns the tags and the fix list. The controller approves the rule order and the shared-cost basis. Nobody is paged for an unallocated share.

**Change control.** The policy and the rules are versioned. A change needs a different approver, and the planted bill is re-run against the pinned numbers in `tests/test_golden.py` before merge, so a rule change that moves a dollar shows in the diff. Rollout is shadow, then calibration, then publishing, as the PRD lays out.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites nothing published: I did not read a standard or a regulation for this project, so I claim no alignment.

- **What the design does.** It states the rule order, keeps a record of which rule placed each charge, and reconciles to the bill.
- **What it does not claim.** It makes no claim of conformity to any standard or regulation, holds no certification, and I have not read or mapped any source for it.

---

## 7. What is deliberately not here

- **A valid tag for the wrong cost center.** 🟢 24 lines ($20,618.63) are charged as tagged, and 20 of 24 pass the compliance check (`step_03_deficiencies_exposed.py`). Only a person who knows the application can catch it.
- **An untagged resource of one team inside another team's account.** 🟢 36 lines ($16,460.42) go to the wrong team through the account default (`step_04_with_tool.py`).
- **Keys and values the policy does not list.** 🟢 24 lines use an unlisted key: $13,014.07 is recovered by the account default and $590.88 is left. 16 lines ($1,731.48) with the hyphen dropped are all left (`step_04_with_tool.py`).
- **Coverage without error.** 🟢 Wrong spend rises from 3.7% to 4.8% as coverage rises (`step_02_exact_tag_report.py`, `step_04_with_tool.py`).
- **Bills across months, commitment amortization, tags on resources billed under another id, cost-center hierarchies.** Matching ignores case and spaces and nothing else.
- **A real mix of defects.** The mix is my guess and the data and the rules share an author, so the numbers are a ceiling.
- **Fetching a bill, forecasting, hosting, or any standard or regulation.** The shared-cost basis is mine, not a chosen one.

---

## Appendix: sample contract

The bundled `--demo` run (a 14-line bill) is under "Run one now" in the README.

```bash
python3 tag_chargeback.py report bill.csv --policy policy.json --cost-centers cost_centers.csv \
  --accounts accounts.csv --max-unallocated-pct 10 --chargeback-csv chargeback.csv --lines-csv lines.csv
```

A bill line: `L00001,2026-03-08,410000000001,Kubernetes,res-1a3edfc6,Cluster hours,207.89,"{""CostCenter"":""CC-1001"",""app"":""ledger-03"",""env"":""prod""}"`. The report prints compliance, allocation by rule, unallocated by reason, the largest unallocated resources, the chargeback and a `result:` line. Exit: 0 at or below the limit, 1 above it, 2 for malformed input.
