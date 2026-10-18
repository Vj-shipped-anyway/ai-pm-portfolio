# Architecture — SwapBrief

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO, your platform engineering lead, and your model risk reviewer on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (a seeded generator that stands in for evaluation runs, four step scripts, a Streamlit app, and a static demo). Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. GCP is shown as primary; AWS and Azure equivalents are called out inline.

![SwapBrief flow](./assets/swapbrief-flow.svg)

---

## 1. Logical architecture

SwapBrief is a decision layer. It does not run evaluations, judge answers, or serve customer traffic. It reads paired per-item results for a migration case (model A, model B with A's old prompt, model B with a retuned prompt), a price table, and token and latency telemetry. It writes one decision per case and a set of rollback triggers.

Nine components. None is in a customer's request path; one external component, the platform's router, acts on a fired trigger.

| Component | Responsibility | Language / framework | In request path? | Stateful? |
| --- | --- | --- | --- | --- |
| `sb-ingest` | Pulls the paired results for a migration case from the evaluation harness export. Refuses to proceed if a condition is missing, items are unpaired, or slice tags are absent. | Python 3.11, FastAPI, Pydantic v2 | No | No |
| `sb-stats` | Paired bootstrap (stratified by slice), McNemar's exact test, ratio intervals for cost per correct answer and for p50 and p95. Fixed seeds, so the same input gives the same brief. | Python, NumPy | No | No |
| `sb-decider` | Applies the status ladder and the decision rule from a policy version. Emits GO, GO WITH GUARDRAILS, or NO-GO with reasons. | Python | No | No |
| `sb-trigger-registry` | Stores proposed and approved triggers (metric, threshold, window, minimum sample, action) as versioned rows. | Python; Postgres | No | Yes |
| `sb-trigger-evaluator` | On a schedule, reads hourly aggregates of scored responses and compares them with the registered thresholds. Fires, pages, and asks the router to return traffic to the pinned model A. | Python on a scheduler (Airflow / Cloud Composer / MWAA) | No (acts through the router) | Yes (window state) |
| `sb-pin-adapter` | Reads the snapshot pin and end-of-support date for model A and B from DriftSentinel (project 02); checks the rollback target is still deployable. | Python | No | No |
| `sb-cost-adapter` | Reads unit prices and per-feature token counts from InferenceLens (project 07). | Python | No | No |
| `sb-console` | Reviewer console: the brief, the slice table, the threshold history, the approval step. Embeds in the model inventory. | React + Next.js + Tailwind | No | No |
| `sb-telemetry` | OpenTelemetry spans and trigger-state metrics, exported off the analysis path. | OTel Collector to Datadog, Langfuse | No | No |

**What is in a customer's request path, and what is not.** Nothing in SwapBrief. The analysis runs once per migration case; the evaluator runs on a schedule. The only component that touches live traffic is the platform's router, and only when a trigger asks it to move traffic back to the pinned model.

**Repo structure** (production shape; monorepo):

```
swapbrief/
├── apps/
│   ├── ingest/          # pull and validate paired results
│   ├── stats/           # bootstrap, McNemar, ratio intervals
│   ├── decider/         # status ladder and decision rule
│   ├── trigger-registry/
│   ├── trigger-evaluator/
│   ├── adapters/        # pin (DriftSentinel), cost (InferenceLens), probes (EvalForge)
│   └── console/         # review UI
├── policy/              # slices, tolerances, watch and block levels, windows (versioned)
├── infra/
│   ├── terraform/       # multi-cloud IaC (gcp, aws, azure)
│   └── policies/        # OPA bundles, IAM templates
├── docs/
│   ├── ARCHITECTURE.md
│   ├── runbooks/
│   └── api/             # OpenAPI spec
└── tests/
    ├── unit/            # stats against known-answer fixtures
    ├── scenarios/       # seeded worlds with injected truth (the repo's 200-scenario test, productionised)
    └── integration/
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `sb-ingest`, `sb-stats`, `sb-decider` | Cloud Run (one job per case) | ECS Fargate | Container Apps | Bursty, short, stateless: one run per migration case |
| `sb-trigger-evaluator` | Cloud Composer | MWAA | Data Factory or Airflow on AKS | Existing scheduler skill set in most bank ops teams |
| `sb-trigger-registry` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | Relational integrity for the approval trail |
| `sb-pin-adapter`, `sb-cost-adapter` | Cloud Functions gen 2 | Lambda | Functions | Small scheduled readers |
| `sb-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI |

**Failure behavior (the decision that matters most).** The trigger evaluator fails loud, not closed. If it cannot read the scoring aggregates, it pages the owner and marks the migration "triggers unevaluated"; it does not change routing on its own failure. A fired trigger rolls back only if the pinned model A is still deployable; otherwise it pages with the fallback plan. Both are configurable per feature, and any change needs a named owner and a line-2 sign-off.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Evaluation export missing a condition | Refuse to decide; say which condition is missing | P3 to the platform lead |
| Slice has fewer items than the minimum | Mark the slice INCONCLUSIVE; list it in the brief | None (it is in the brief) |
| Trigger evaluator cannot read aggregates | Keep routing as is; mark "triggers unevaluated" | P2 |
| Trigger fires and pinned model A is deployable | Ask the router to return traffic; open an incident | P1 |
| Trigger fires and pinned model A is gone | Page with the fallback plan; no automatic action | P1 |
| Pin adapter cannot reach DriftSentinel | Use the last cached pin; flag the brief | P3 |

**Latency.** No customer-facing latency is added. A design budget for the analysis is minutes per case, not seconds; the prototype's committed-set analysis (two prompts, 2000 resamples each) runs in a few seconds on a laptop. The trigger evaluation windows are set by policy: 7 days rolling for slice accuracy, 24 hours for cost per correct answer, 1 hour with 3 windows in a row for p95. 🔴 Design values, not load-tested.

### Network topology

```
Evaluation harness (EvalForge)        DriftSentinel (pins)        InferenceLens (price, cost)
        │ paired results                   │ snapshot pin, end of support     │ unit price, tokens
        ▼ mTLS via service mesh            ▼                                  ▼
[sb-ingest] ◄──── only caller allowed: the harness identity ───────────────────┘
   │
   ├──► [sb-stats] ──► [sb-decider] ──► [sb-trigger-registry] ──► [PostgreSQL]   (private endpoints)
   └──► [sb-console]  ◄── bank SSO ── reviewers, product owners

Out of band, on a schedule:
   [sb-trigger-evaluator] ──► [column store: hourly scored-response aggregates]
        │ fired
        ▼
   [platform router API] ──► traffic returns to pinned model A
        egress only through a proxy with an allow-list; no public ingress
```

### Region & DR

- Primary and DR regions follow the footprint of the feature being migrated. SwapBrief does not get a different recovery objective from the system whose migration it governs.
- Region-specific instances where data residency applies. Each has its own database and key ring; no cross-region replication of evaluation items that contain customer text.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | Migration cases, runs, slice results, decisions, triggers, trigger events, policy versions, audit log | Relational integrity for the approval trail; the bank's ops team already runs it |
| **ClickHouse** | Hourly aggregates of scored responses per feature, slice, and model | High-volume, append-only, queried by window |
| **Object storage with Object Lock (WORM)** | Archived briefs and the evaluation exports they were computed from | Write-once-read-many for the record-keeping policy |

### PostgreSQL schema (the consequential tables)

```sql
-- One row per model migration being decided
CREATE TABLE migration_cases (
    case_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id      TEXT NOT NULL,
    model_a         TEXT NOT NULL,          -- e.g. model-a@2026-03
    model_b         TEXT NOT NULL,          -- e.g. model-b@2026-08
    end_of_support  DATE NOT NULL,          -- model A, from the pin adapter
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          TEXT NOT NULL           -- OPEN / DECIDED / LIVE / ROLLED_BACK / CLOSED
);

-- The per-slice result of one analysis, for one B condition
CREATE TABLE slice_results (
    case_id         UUID NOT NULL REFERENCES migration_cases,
    condition       TEXT NOT NULL,          -- B_old_prompt / B_new_prompt
    slice           TEXT NOT NULL,
    severity        TEXT NOT NULL,          -- critical / standard
    n_items         INT NOT NULL,
    acc_a           NUMERIC(5,4) NOT NULL,
    acc_b           NUMERIC(5,4) NOT NULL,
    ci_lo           NUMERIC(5,4) NOT NULL,
    ci_hi           NUMERIC(5,4) NOT NULL,
    tolerance       NUMERIC(5,4) NOT NULL,
    status          TEXT NOT NULL,          -- REGRESSED / WATCH / INCONCLUSIVE / OK / IMPROVED
    PRIMARY KEY (case_id, condition, slice)
);

CREATE TABLE decisions (
    decision_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL REFERENCES migration_cases,
    condition       TEXT NOT NULL,
    decision        TEXT NOT NULL,          -- GO / GO_WITH_GUARDRAILS / NO_GO
    reasons         JSONB NOT NULL,
    policy_version  TEXT NOT NULL,
    bootstrap_seed  BIGINT NOT NULL,        -- same input and seed reproduce the brief
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signed_by       TEXT                    -- feature product owner
);

CREATE TABLE triggers (
    trigger_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL REFERENCES migration_cases,
    metric          TEXT NOT NULL,          -- accuracy[slice] / cost_per_correct / p95_latency
    comparison      TEXT NOT NULL,          -- < or >
    threshold       NUMERIC NOT NULL,
    window_spec     TEXT NOT NULL,          -- '7 days rolling' / '24 hours' / '1 hour x 3'
    min_sample      INT,
    action          TEXT NOT NULL,          -- roll back to the pinned model A
    proposed_by     TEXT NOT NULL,
    approved_by     TEXT,                   -- a different person from proposed_by
    effective_from  TIMESTAMPTZ,
    CHECK (approved_by IS NULL OR approved_by <> proposed_by)
);

CREATE TABLE trigger_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_id      UUID NOT NULL REFERENCES triggers,
    evaluated_at    TIMESTAMPTZ NOT NULL,
    observed_value  NUMERIC NOT NULL,
    n_scored        INT NOT NULL,
    fired           BOOLEAN NOT NULL,
    action_taken    TEXT                    -- ROLLED_BACK / PAGED / NONE
);

-- Audit log (immutable, append-only, partitioned by month)
CREATE TABLE audit_log (
    audit_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id        TEXT NOT NULL,
    actor_type      TEXT NOT NULL,          -- user / service_account
    action          TEXT NOT NULL,
    resource_type   TEXT NOT NULL,
    resource_id     TEXT NOT NULL,
    request_id      TEXT NOT NULL,
    payload         JSONB,
    result          TEXT NOT NULL
) PARTITION BY RANGE (occurred_at);
```

**Raw customer text.** The design stores slice tags, scores, token counts, latencies, and hashed item ids, not the question or answer text. Where a reviewer needs the text to understand a regression, it is fetched from the evaluation harness by item id under that system's access rules. SwapBrief does not become a second copy of the evaluation corpus.

### ClickHouse schema (the time-series tables)

```sql
CREATE TABLE scored_hourly (
    feature_id      LowCardinality(String),
    model_id        LowCardinality(String),
    slice           LowCardinality(String),
    hour            DateTime('UTC'),
    n_scored        UInt32,
    n_correct       UInt32,
    input_tokens    UInt64,
    output_tokens   UInt64,
    cost_usd        Float64,
    lat_p50_ms      Float32,
    lat_p95_ms      Float32
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/scored_hourly', '{replica}')
PARTITION BY toYYYYMM(hour)
ORDER BY (feature_id, slice, hour)
TTL hour + INTERVAL 730 DAY DELETE;     -- 2-year hot retention, a design default
```

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-retention schedule before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Decisions, slice results, triggers, trigger events | Life of the feature plus 7 years | Postgres hot for 90 days, then archive to Object Lock | Internal |
| Threshold and policy history | Life of the feature plus 7 years | Postgres, append-only | Internal |
| Evaluation exports behind a brief | Same as the brief | Object Lock | Confidential (may contain item text) |
| Hourly scored aggregates | 2 years hot | ClickHouse | Internal |
| Audit log | 7 years | Postgres partitioned, archive to Object Lock | Confidential |
| Customer conversation text | Not stored by SwapBrief | The evaluation harness's store | Governed by that system |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with customer-managed keys (CMEK / CMK) in Cloud KMS, AWS KMS, or Azure Key Vault, one key ring per region.
- **In transit.** TLS 1.3 north-south. mTLS east-west through the service mesh.
- **Field-level.** Item ids are hashed before any SwapBrief write; no item text is stored.
- **Database-level.** Transparent data encryption on PostgreSQL, encrypted disks on ClickHouse.

### Secrets management

- **Primary store.** HashiCorp Vault or the cloud secret manager. No long-lived static credentials.
- **Application secrets** (database passwords, adapter credentials): fetched at boot through workload identity, rotated on the bank's schedule.
- **Service-account keys.** None. Workload Identity on GCP, IAM Roles for Service Accounts on AWS, Managed Identity on Azure.

### Identity provider & user management

- **IdP.** Whatever the bank already runs (Okta, Microsoft Entra ID, Ping). SAML 2.0 and OIDC. SwapBrief does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Sessions.** OIDC ID token plus signed session cookie (HttpOnly, Secure, SameSite=Strict).
- **Service-to-service identity.** SPIFFE IDs; each component has its own workload identity.

### RBAC matrix

Authorization is enforced at the API with OPA, and every decision is written to `audit_log`.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `sb:viewer` | Read briefs and trigger state | Audit, finance partner, executives |
| `sb:platform-lead` | Viewer + open a case, run an analysis, propose triggers | Line-1 AI platform lead |
| `sb:product-owner` | Viewer + sign a decision, record a standard-slice waiver | Line-1 feature product owner |
| `sb:validator` | Viewer + approve tolerances, thresholds and policy versions | Line-2 model risk |
| `sb:admin` | Config, integrations, role management | Platform engineering lead |

A trigger needs a proposer and a different approver; the `CHECK` constraint on `triggers` enforces it.

### Network controls

- **Perimeter.** VPC Service Controls (GCP), PrivateLink plus Network Firewall (AWS), or Private Endpoints (Azure). Egress only through a proxy with an allow-list.
- **Lateral.** Network policies on the service mesh; the ingest service accepts calls only from the evaluation harness identity.
- **Ingress.** No public ingress. The console sits behind the bank's SSO.
- **Zero-trust.** Every inter-service call is authenticated.

### Threat model

| Threat | Mitigation |
| --- | --- |
| Evaluation results edited to hide a regression | The export is hashed and archived under Object Lock; the brief stores the hash; `sb-ingest` refuses an export whose hash does not match the harness's record |
| Tolerances or thresholds quietly loosened | Append-only policy and trigger history with proposer and approver; a weekly report of threshold changes beside rollback counts |
| Test contamination: evaluation items leak into prompt tuning | Items are versioned and read-only to prompt authors; the brief records the probe-set version used; held-out items are not exposed to the tuning loop |
| A slice relabeled to dilute a regression | Slice tags come from the harness's versioned probe set; a tag change between runs is flagged in the brief |
| A trigger disabled after launch | Disabling is a new row needing an approver; the evaluator pages when a registered trigger has no evaluation in its window |
| Small slice gives false comfort | INCONCLUSIVE status and the item count are printed in every brief; critical inconclusive slices get a trigger |
| Pinned model A removed before a rollback is needed | The pin adapter checks deployability; the brief states the last date a rollback is possible |

---

## 4a. APIs consumed and exposed

SwapBrief is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Evaluation harness (EvalForge, project 04) | REST, mTLS service identity | Export of paired per-item results and the probe-set version | Refuse to decide; no stale result is used |
| Snapshot pin service (DriftSentinel, project 02) | REST, mTLS | Pin and end-of-support date for model A and B | Last cached pin; brief flagged |
| Price and cost service (InferenceLens, project 07) | REST, mTLS | Unit prices and per-feature token counts | Last cached prices; brief flagged |
| Platform router | REST, service principal | Return traffic to the pinned model A | Page the owner; no automatic retry loop |
| Bank IdP (Okta / Entra / Ping) | SAML 2.0 + OIDC | Console login, role lookup | Existing sessions continue |
| Model risk record (GRC tool) | Vendor REST, service principal | File the brief, approvals and threshold history | Local audit trail continues; sync resumes later |
| PagerDuty / chat | REST / webhook | Alert routing | Email fallback |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/cases/{id}/analyze` | OpenAPI 3.1 over HTTPS, mTLS service identity | The evaluation harness, the platform lead's tooling |
| `GET /v1/cases/{id}/brief` | OIDC bearer, role-checked by OPA | `sb-console`, the model risk record |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Incident management, release workflow |

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** The surface is one analysis call and a read of the brief.
- **Deterministic by construction.** The analysis takes a policy version and a seed; the same input returns the same brief, so a reviewer can re-run it.
- **The response carries the reason, not just the verdict.** Every slice returns its interval, tolerance, and status, and the decision lists the reasons that drove it.
- **Idempotency key on `analyze`.** A retried call must not create a second decision.
- **Webhooks are signed, not just authenticated.**
- **No item text in URLs or logs.** Item ids are hashes.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry to Datadog | The SOC's existing pane |
| Analysis runs (inputs hash, seed, policy version, runtime) | Langfuse, self-hosted | Reproduce a single brief |
| Trigger state and window values | ClickHouse + Datadog dashboards | See how close each trigger is to its line |
| Audit log | Postgres, archived to Object Lock | Record-keeping |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **Briefs with every trigger registered and approved before release** | The point of the product. A decision without triggers is the problem restated. |
| **Triggers evaluated on schedule** | A trigger that is not evaluated is not a trigger. |
| **Share of slices INCONCLUSIVE** | Tells you whether the evaluation sets are big enough. In the prototype, 1 of 8 slices on the committed set. |
| **Guardrails given to migrations that were fine** | The cost of caution. In the prototype, 23.3% of good simulated migrations. Too high and teams stop reading the brief. |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P1 | A rollback trigger fires | PagerDuty |
| P2 | Trigger evaluator cannot evaluate a registered trigger | PagerDuty (low urgency) + chat |
| P3 | Evaluation export incomplete; pin adapter stale | Chat |
| P4 | Weekly digest of threshold changes and open waivers | Email |

### Rollout

Backtest first: replay the brief on past migrations from the model inventory's change records. Then shadow: write the brief beside the existing decision. Then gate: a signed brief is required for release. Then triggers live on one feature, with a rollback drill before the end-of-support date, as outlined in the PRD.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **ClickHouse.** Weekly backup to object storage; replicated engine for HA inside a region.
- **Object stores.** Object Lock and versioning for archived briefs and exports.
- **DR drill cadence.** Quarterly failover to the secondary region, validated against the recovery objective of the feature SwapBrief governs.

### Runbooks (one page each, in `docs/runbooks/`)

- `vendor-deprecation-notice.md` — open a case, pin model A, set the end-of-support date
- `slice-inconclusive.md` — a slice has too few items; add items or accept a trigger
- `trigger-fired.md` — verify, roll back, open the incident, record the event
- `trigger-unevaluated.md` — the evaluator cannot read aggregates
- `waiver-expiry.md` — a standard-slice waiver reached its expiry date

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against.

| Framework | How the design relates |
| --- | --- |
| **SR 11-7 / model risk management** | A model change needs documented validation and ongoing monitoring. The brief is the change evidence; the triggers are the monitoring; the threshold history is the challenge record. |
| **NIST AI RMF** | The Measure function maps to intervals, cost, and latency; the Manage function maps to the decision rule and the triggers. |
| **EU AI Act** | Logging and post-deployment monitoring expectations for higher-risk systems: the audit log, the trigger events, and the retained exports are the design's answer. The standard the work would have to meet, not a claim of conformity. |
| **OWASP LLM Top 10** | The jailbreak-resistance slice is critical because prompt injection and jailbreaks are a named risk class. |
| **SOC 2 Type II, GDPR, data localization** | Regional instances, hashed identifiers, append-only audit. |

---

## 7. What's deliberately not here

- **An evaluation harness.** SwapBrief reads results; EvalForge (project 04) produces them.
- **A judge model.** It does not score answers. The `correct` column comes from the harness.
- **A claim that thresholds are right for your bank.** The tolerances in the prototype are policy parameters I chose. The model risk reviewer owns the real ones.
- **Automatic loosening of tolerances.** Tolerances change by one person's proposal and a different person's approval.
- **Prompt authoring or tuning.** The brief compares the prompts it is given.
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each is already owned by another system.

---

## Appendix — sample API contract

```python
# GET /v1/cases/9d3c.../brief
# Auth: OIDC bearer; role: sb:viewer or higher
# Response 200 (abridged; values from the committed simulated set)
{
    "case_id": "9d3c...",
    "model_a": "model-a@2026-03",
    "model_b": "model-b@2026-08",
    "decisions": [
        {"condition": "B_new_prompt", "decision": "GO WITH GUARDRAILS"},
        {"condition": "B_old_prompt", "decision": "NO-GO"}
    ],
    "slices": [
        {"slice": "numeric_units", "severity": "standard", "n_items": 100,
         "change": "-11.0 pp", "interval": "-22.0 to -1.0 pp", "status": "REGRESSED"},
        {"slice": "long_answers", "severity": "standard", "n_items": 40,
         "change": "-2.5 pp", "interval": "-20.0 to +15.0 pp", "status": "INCONCLUSIVE"}
    ],
    "cost_per_correct": {"change": "+8.8%", "interval": "+4.4% to +13.1%"},
    "p95_latency": {"change": "+25.9%", "interval": "+6.2% to +43.6%"},
    "triggers": 8,
    "policy_version": "policy-2026-10",
    "bootstrap_seed": 20261019
}
```

The values are the prototype's step 4 output for the committed simulated set; the case id, policy version, and endpoint are illustrative.

OpenAPI spec lives at `docs/api/openapi.yaml` and is the source of truth for the client and the console.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/13-swapbrief-model-migration/demo.html).
