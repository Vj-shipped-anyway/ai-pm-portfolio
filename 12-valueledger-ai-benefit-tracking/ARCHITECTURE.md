# Architecture — ValueLedger

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO, your data platform lead, and your finance business partner on day one.

> **Status.** This is the design for the production shape. The repo implements the measurement mechanic as a prototype (a seeded synthetic panel with an answer key, four standard-library step scripts, a Streamlit app, and a static demo). Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. GCP is shown as primary; AWS and Azure equivalents are called out inline.

![ValueLedger flow](./assets/valueledger-flow.svg)

---

## 1. Logical architecture

ValueLedger is a measurement layer. It does not replace the copilots, the work system, the finance ledger, or the eval harness. It reads from them, estimates a copilot's effect against a comparison group, and writes a benefit statement for review. Nothing in it sits in a user's request path.

Nine components. One is interactive, five are batch jobs, and three are support pieces (a cohort registry API, the panel store, and telemetry) that no one's work waits on.

| Component | Responsibility | Language / framework | In request path? | Stateful? |
| --- | --- | --- | --- | --- |
| `vl-ingest` | Pulls copilot usage logs and work and time records, joins them on person and week, and joins the two copilot logs on a shared task ID. Rejects files that fail schema checks. | Python 3.11 batch jobs | No, batch | Stateful (checkpoints) |
| `vl-cohorts` | Append-only registry of who was treated or held out, when, and by what assignment rule. A cohort must be on file before its first statement. | Python 3.11, FastAPI, Pydantic v2 | No | Stateful (Postgres) |
| `vl-panel` | The person-by-week fact table: tasks, minutes per task, usage events per copilot, rework minutes. | ClickHouse | No | Stateful |
| `vl-estimator` | Difference-in-differences against the holdout, the pre-period gap slope and placebo launch, rework netting, the weekly effect curve and decay fit, and overlap deduplication. | Python 3.11 (the prototype uses only the standard library) | No, batch | No (reads the panel, writes estimates) |
| `vl-bootstrap` | Team-level resampling within each arm, seeded, with the seed stored beside the interval. | Python 3.11 | No, batch | No |
| `vl-ledger` | Joins estimates to budget lines, applies the cash lever and the addressable-spend ceiling, and writes hard and soft lines. | Python 3.11, Postgres | No, batch | Stateful (Postgres) |
| `vl-guardrail` | Reads the eval pass rate (04 EvalForge) and the rework share, and sets a hold on a cost center whose rework exceeds a threshold. The prototype's threshold is 40% of gross time saved, a design choice. | Python 3.11 | No, batch | No |
| `vl-console` | Statement review and sign-off: the three columns (claimed, pre/post, ledger), the interval, the known limit, the hard-versus-soft split, held lines. | React + Next.js + Tailwind | Interactive, not in any request path | No |
| `vl-telemetry` | OpenTelemetry spans from every job, exported off the job path. | OTel Collector to Datadog | No | No |

**What is interactive, and what is not.** Only the console is interactive, and no one's work waits on it. Everything else runs on a schedule per cohort and per quarter. A statement is a versioned artifact, not a live number.

**Repo structure** (production shape; a monorepo):

```
valueledger/
├── apps/
│   ├── ingest/         # adapters, schema checks, task key join
│   ├── cohorts/        # registry API
│   ├── estimator/      # DiD, checks, decay, dedupe
│   ├── bootstrap/      # seeded team-level resampling
│   ├── ledger/         # budget join, cash lever, ceiling
│   ├── guardrail/      # hold rules
│   └── console/        # review and sign-off UI
├── infra/
│   ├── terraform/      # multi-cloud IaC (gcp, aws, azure)
│   └── policies/       # IAM templates, network policies
├── docs/
│   ├── ARCHITECTURE.md
│   ├── runbooks/
│   └── api/            # OpenAPI spec
└── tests/
    ├── unit/
    ├── synthetic/      # a seeded generator with a known answer key, like this repo's data/
    └── integration/
```

The `synthetic/` folder is the design's regression test: if an estimator change moves the error against the generator's answer key, the change does not merge.

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Batch jobs (`vl-ingest`, `vl-estimator`, `vl-bootstrap`, `vl-ledger`, `vl-guardrail`) | Cloud Run jobs, scheduled | ECS Fargate scheduled tasks | Container Apps jobs | Short-lived, idempotent, re-runnable for a past quarter |
| `vl-cohorts` API | Cloud Run | ECS Fargate | Container Apps | Small stateless service over Postgres |
| Postgres | Cloud SQL | RDS | Azure Database for PostgreSQL | Cohorts, estimates, ledger lines, sign-offs; the bank's ops team already runs it |
| Panel store | ClickHouse on GKE | ClickHouse on EKS | ClickHouse on AKS | Append-only person-by-week facts, queried by date range |
| `vl-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI |

**Failure behavior (the decision that matters most).** The statement fails closed. If an input export is missing, a schema check fails, or the pre-trend check cannot run, no new statement is published and the last signed statement stays current. A late or partial export never produces a quietly different number. This trades freshness for trust, the right default for a number that finance signs.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Work-system export missing or fails schema check | Statement not published; last signed statement stays current | P2 |
| Copilot usage log and task key do not join (match rate below a design floor) | Overlap deduplication blocked; statement marked incomplete | P2 |
| Pre-trend gap slope or placebo outside tolerance | Statement prints a range and a "not credible as a point estimate" flag | P3 |
| Cohort not on file before first statement | Statement refused | P2 |
| Use case with no registered ID or not approved | Its benefit is not booked | P3 |
| Cost center held by the guardrail | Stays soft; cannot book hard cash until a named reviewer releases it | P3 |
| Bootstrap job fails | Point estimate withheld; the statement needs its interval | P3 |
| Telemetry sink down | Buffer locally, drop with a counter once the buffer fills | P4 |

### Network topology

```
Source systems (copilot usage exports, work system, finance ledger, TierGate, InferenceLens, EvalForge)
   │   read-only, scheduled pulls over private endpoints
   ▼
[vl-ingest, batch jobs]  ──► schema checks ──► [Panel store]   (private endpoint, no ingress from outside)
   │
   ├──► [vl-cohorts API] ──► [PostgreSQL: cohorts, estimates, ledger, sign-offs]   (private endpoints)
   ├──► [vl-estimator] ──► [vl-bootstrap] ──► [vl-ledger] ──► [vl-guardrail]
   └──► async: [OTel Collector] ──► Datadog

Interactive:
   Finance, program lead, product owners, CRO ──► [bank SSO] ──► [vl-console]
        egress only to the bank's GRC tool for the signed statement
        [Network Firewall / VPC Service Controls] for data-exfiltration prevention
```

### Region & DR

- The region follows the work system's footprint. ValueLedger does not get a different recovery objective than the system of record it reads from.
- Region-specific instances where data residency applies. Each has its own database and key ring; there is no cross-region replication of work records.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | Cohort registry, estimates with intervals, ledger lines, statements, sign-offs, audit log | Relational integrity for the audit trail; append-only tables for the registry |
| **ClickHouse** | The person-by-week panel | High-volume, append-only, queried by date range and team |
| **Object storage with Object Lock (WORM)** | Signed statements and the input snapshots they were computed from | Write-once-read-many, so a signed statement cannot be edited |

### PostgreSQL schema (the consequential tables)

```sql
-- Who was treated or held out, and by what rule. Append-only.
CREATE TABLE cohort_assignments (
    cohort_id       TEXT NOT NULL,
    team_id         TEXT NOT NULL,
    arm             TEXT NOT NULL,          -- treated / holdout
    effective_week  DATE NOT NULL,
    rule            TEXT NOT NULL,          -- e.g. "top teams by enthusiasm score, not randomized"
    recorded_by     TEXT NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (cohort_id, team_id, recorded_at)
);

-- One row per estimate. The interval and the seed travel with the point value.
CREATE TABLE estimates (
    estimate_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cohort_id       TEXT NOT NULL,
    use_case_id     TEXT NOT NULL,          -- joined to the TierGate register
    window_start    DATE NOT NULL,
    window_end      DATE NOT NULL,
    method          TEXT NOT NULL,          -- claim / prepost / ledger
    net_hours       NUMERIC(12,1) NOT NULL,
    ci_low          NUMERIC(12,1),
    ci_high         NUMERIC(12,1),
    bootstrap_seed  INT,
    bootstrap_reps  INT,
    pretrend_slope  NUMERIC(8,4),
    placebo_effect  NUMERIC(8,4),
    pretrend_ok     BOOLEAN,
    code_version    TEXT NOT NULL
);

-- Hard versus soft, per cost center. Unique per use case, cost center and period.
CREATE TABLE ledger_lines (
    line_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    estimate_id       UUID NOT NULL REFERENCES estimates(estimate_id),
    cost_center_id    TEXT NOT NULL,
    net_hours         NUMERIC(12,1) NOT NULL,
    value_usd         NUMERIC(14,2) NOT NULL,
    cash_lever        TEXT,
    line_ceiling_usd  NUMERIC(14,2),
    hard_usd          NUMERIC(14,2) NOT NULL,
    soft_usd          NUMERIC(14,2) NOT NULL,
    rework_share      NUMERIC(5,3),
    held              BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (estimate_id, cost_center_id)
);

CREATE TABLE statements (
    statement_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cohort_id       TEXT NOT NULL,
    version         INT NOT NULL,
    status          TEXT NOT NULL,          -- draft / in_review / signed / superseded
    known_limit     TEXT NOT NULL,          -- printed on every statement
    content_sha256  TEXT NOT NULL,
    UNIQUE (cohort_id, version)
);

CREATE TABLE signoffs (
    statement_id    UUID NOT NULL REFERENCES statements(statement_id),
    column_signed   TEXT NOT NULL,          -- hard / soft
    signed_by       TEXT NOT NULL,          -- finance business partner
    signed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    amount_usd      NUMERIC(14,2) NOT NULL,
    PRIMARY KEY (statement_id, column_signed)
);

-- Audit log (immutable, append-only, partitioned by month)
CREATE TABLE audit_log (
    audit_id        UUID NOT NULL DEFAULT gen_random_uuid(),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id        TEXT NOT NULL,
    actor_type      TEXT NOT NULL,          -- user / service_account
    action          TEXT NOT NULL,
    resource_type   TEXT NOT NULL,
    resource_id     TEXT NOT NULL,
    payload         JSONB,
    result          TEXT NOT NULL,          -- success / failure / forbidden
    PRIMARY KEY (audit_id, occurred_at)
) PARTITION BY RANGE (occurred_at);
```

**Individual rows.** The panel stores a hashed person key and the team. The console never shows an individual row. A cell with fewer than a set number of people is suppressed (the minimum cell size is a design choice to be set with HR and legal).

### ClickHouse schema (the time-series tables)

```sql
CREATE TABLE panel_person_week (
    person_hash       FixedString(32),
    team_id           LowCardinality(String),
    cost_center_id    LowCardinality(String),
    arm               LowCardinality(String),
    week_start        Date,
    tasks_completed   UInt16,
    task_minutes      Float32,      -- tasks x minutes per task, excludes rework
    events_a          UInt16,
    events_b          UInt16,
    events_both       UInt16,
    rework_minutes    Float32
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/panel_person_week', '{replica}')
PARTITION BY toYYYYMM(week_start)
ORDER BY (team_id, week_start)
TTL week_start + INTERVAL 1095 DAY DELETE;  -- design default; confirm with the retention schedule
```

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-retention schedule before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Person-by-week panel (hashed person key) | 3 years | ClickHouse | Confidential, no direct identifiers |
| Cohort registry and assignment rules | Life of the use case plus 7 years | Postgres, append-only | Internal |
| Estimates and ledger lines | 7 years | Postgres, archive to Object Lock | Internal |
| Signed statements and input snapshots | 7 years | Object Lock | Confidential |
| Audit log | 7 years | Postgres partitioned, archive to Object Lock | Confidential |
| Raw copilot usage exports and work-system exports | Deleted after the panel is built and checked | Object storage, short TTL | Confidential |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with customer-managed keys in Cloud KMS, AWS KMS, or Azure Key Vault, one key ring per region. Keys never cross a region boundary.
- **In transit.** TLS 1.3 north-south. mTLS east-west between services.
- **Field-level.** The person key is hashed with a keyed hash before any ValueLedger write; the key is held outside the panel store.
- **Database-level.** Transparent data encryption on Postgres, encrypted disks on ClickHouse.

### Secrets management

- **Primary store.** HashiCorp Vault or the cloud secret manager. No long-lived static credentials.
- **Application secrets** (source-system credentials): fetched at boot through workload identity, rotated on the bank's schedule.
- **Service-account keys.** None. Workload Identity on GCP, IAM Roles for Service Accounts on AWS, Managed Identity on Azure.

### Identity provider & user management

- **IdP.** Whatever the bank already runs. SAML 2.0 and OIDC. ValueLedger does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Sessions.** OIDC ID token plus signed session cookie (HttpOnly, Secure, SameSite=Strict), with expiry set by bank policy.
- **Service-to-service identity.** Each job has its own workload identity.

### RBAC matrix

Authorization is enforced at the API with OPA, and every decision is written to `audit_log`.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `vl:viewer` | Read signed statements | Executives, audit |
| `vl:program-lead` | Viewer, plus register cohorts and request a statement run | AI program lead |
| `vl:owner` | Viewer, plus read the overlap split for their own copilot | Copilot product owner |
| `vl:finance-signer` | Viewer, plus sign the hard column | Finance business partner |
| `vl:reviewer` | Viewer, plus release a held cost center | CRO delegate, line-2 risk |
| `vl:admin` | Config, integrations, role management | Platform engineering lead |

The person who registers a cohort cannot sign the statement computed from it. Registering and signing are different roles, and both are recorded.

### Network controls

- **Perimeter.** VPC Service Controls (GCP), PrivateLink plus Network Firewall (AWS), or Private Endpoints (Azure). Egress only through a proxy with an allow-list.
- **Lateral.** Network policies between jobs; the panel store accepts calls only from the ingest and estimator identities.
- **Ingress.** The console sits behind the bank's SSO. There is no public ingress.
- **Zero-trust.** Every inter-service call is authenticated.

### Threat model

| Threat | Mitigation |
| --- | --- |
| The cohort is chosen after the results are seen | Append-only `cohort_assignments` with timestamps; each statement records the registry version it used; a cohort not on file before the first statement is refused |
| The holdout is contaminated (holdout teams adopt the tool informally) | Usage-log check on holdout teams: any copilot event flags the statement; a spillover check is queued in the backlog |
| Window or slice shopping | The window and slices are fixed per statement template; a re-run is a new statement version with a reason recorded |
| Vendor-supplied usage logs are untrusted input | Schema validation, counts reconciled to seat counts, no free-text fields, and a match-rate floor on the task key join |
| The same benefit is booked twice | One ledger line per estimate and cost center; `UNIQUE (estimate_id, cost_center_id)`; overlap counted once |
| Work data is used to rank people | Team-level aggregation, hashed person key, a minimum cell size, no individual rows in the console |
| A statement is edited after sign-off | Signed statements are immutable, hashed, and archived to Object Lock |
| Hours are booked as cash where no cash lever exists | The ledger rule caps hard benefit at the addressable spend on the line and gives zero hard benefit where the flag is no; finance signs the hard column, not the hours |
| A number is repeated without its limit | The known limit is a required field on every statement and printed with the number |

---

## 4a. APIs consumed and exposed

ValueLedger is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Copilot usage exports | Export file or REST, key from Vault | Usage events per person per task, with a task ID | Statement not published; last signed statement stays current |
| Work system | Batch export or REST, service principal | Tasks completed, minutes per task, correction records | Same |
| Finance ledger | Read-only export | Cost-center lines, loaded cost per hour, cash levers, addressable spend | Ledger lines not refreshed; statement marked stale |
| 11 TierGate | REST, mTLS | Use-case ID and approval status | A use case without an approved ID is not booked |
| 07 InferenceLens | REST, mTLS | Cost per feature per period | Cost column shows "not available"; return is not computed |
| 04 EvalForge | REST, mTLS | Pass rate per use case | Guardrail falls back to the rework share alone |
| Bank IdP | SAML 2.0 and OIDC | Console login, role lookup | Existing sessions continue |
| Datadog | HTTPS, key from Vault | Metrics and traces | Local buffer |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/cohorts` | OpenAPI 3.1 over HTTPS, OIDC bearer, role-checked by OPA | Program lead tooling |
| `GET /v1/statements/{id}` | Same | Console, the bank's GRC tool |
| `POST /v1/statements/{id}/signoff` | Same, `vl:finance-signer` only | Console |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | GRC tool, finance planning system |

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** The surface is a handful of resources. OpenAPI generates the console SDK from one spec.
- **The response carries the interval and the known limit, not just the number.** A statement without them is invalid.
- **Idempotent statement runs.** A run is keyed by cohort, window, and code version; a retry does not create a second statement.
- **Signed means immutable.** Corrections are a new version that supersedes the old one.
- **No person identifiers in URLs or responses.** Team-level only.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Job logs and traces | OpenTelemetry to Datadog | The platform team's existing pane |
| Estimate history and interval width | Postgres, charted in the console | Shows whether numbers are getting more or less certain over time |
| Audit log | Postgres, archived to Object Lock | Record-keeping |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **Input completeness** per run | A statement built on a partial export is worse than no statement |
| **Pre-trend check pass rate** | The share of statements where the comparison group reads as fair |
| **Statements with an interval and a known limit** | Target 100% (design target); anything less is a claim again |
| **Statement revisions after finance review** | A trend, not a target: fewer revisions means the rule matches how finance reads it |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P2 | Input missing or failing schema checks; cohort not on file | PagerDuty (low urgency) + Slack |
| P3 | Pre-trend outside tolerance; a use case without an approved ID; a held cost center | Slack |
| P4 | Weekly digest of statements in review | Email |

### Rollout

Shadow first: run ValueLedger beside the existing business case for one use case, publish nothing, and let finance compare. Then sign the hard column on that use case. Then add the guardrail and cost reads. Then onboard the rest of the fleet, one use case at a time, with each new launch staggered by team so the comparison group is designed in. The durations are in the PRD and are design targets.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **ClickHouse.** Weekly backup to object storage; replicated engine for HA inside a region. The panel can be rebuilt from the source exports inside their retention window.
- **Object stores.** Object Lock and versioning for signed statements and input snapshots.
- **DR drill cadence.** Design target: quarterly failover to the secondary region, validated against the work system's own recovery objective.

### Runbooks (one page each, in `docs/runbooks/`)

- `input-missing.md` — an export is late or fails its schema check
- `pretrend-failed.md` — the gap slope or the placebo is outside tolerance
- `holdout-contaminated.md` — holdout teams show copilot usage
- `statement-superseded.md` — correct a signed statement with a new version
- `guardrail-release.md` — release a held cost center

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against.

| Framework | How the design relates |
| --- | --- |
| **SR 11-7 / model risk management** | The design treats the estimators as a model in their own right, by analogy: they take inputs and produce a number that informs an investment decision, so the design gives them an inventory entry, validation, and ongoing monitoring. The synthetic regression suite and the stored seed, cohort rule, and interval would be the validation record. This is not a claim that the guidance governs the prototype. |
| **NIST AI RMF** | The Measure function maps to the holdout, the checks, and the interval; the Manage function maps to the guardrail hold and the sign-off. |
| **FinOps Foundation framework** | The cost side of return follows cost-accountability practice: a benefit statement carries its cost beside it. |
| **Employee data and privacy law** | Work-record use is governed by local law and, in some jurisdictions, by works-council agreements. The design aggregates at team level and hashes identifiers; a legal read is a precondition for any real data. |
| **Internal control over budgets** | A signed hard benefit that changes a budget becomes part of the planning record. Control owners decide what evidence they need; the signed statement and its input snapshot are designed to be that evidence. |

---

## 7. What's deliberately not here

- **A new copilot or an eval harness.** ValueLedger measures the benefit of tools the bank already runs, and reads quality from the harness it already has.
- **A claim that it sees selection on unobserved traits.** It does not. The prototype injects one such bias on purpose and prints it. The fix is a randomized or staggered rollout, which is a decision, not a feature.
- **Individual-level scoring.** Team-level aggregation only.
- **Booking into the budget without a signature.** A person signs the hard column.
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each one is already owned by another system or another person.

---

## Appendix — sample API contract

```python
# GET /v1/statements/{statement_id}
# Auth: OIDC bearer, role vl:viewer or above
# Response 200 (illustrative values from the synthetic run in this repo)
{
    "statement_id": "c1a7f0de-...",
    "cohort_id": "COHORT-SYNTH-01",
    "version": 1,
    "status": "in_review",
    "window": {"weeks": "13 to 26", "treated_people": 160, "holdout_people": 160},
    "claimed_hours": 5166,
    "prepost_hours": 4311,
    "ledger": {
        "net_hours": 2152,
        "ci_95": [1784, 2559],
        "bootstrap": {"reps": 1000, "seed": 7712, "unit": "team"},
        "pretrend": {"gap_slope_min_per_task_per_week": -0.050, "placebo_min_per_task": 0.25, "ok": true},
        "rework_hours": 723,
        "hard_usd": 34231,
        "soft_usd": 119358,
        "held_cost_centers": ["CC-104"]
    },
    "known_limit": "Selection on traits the data cannot see is not covered by the interval."
}
```

The values in the example are taken from `step_04_with_valueledger.py` on the synthetic data. A real statement has no answer key. The OpenAPI spec would live at `docs/api/openapi.yaml` and be the source of truth for the console client.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/12-valueledger-ai-benefit-tracking/demo.html).
