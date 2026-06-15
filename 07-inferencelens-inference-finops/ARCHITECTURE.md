# Architecture — InferenceLens

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network topology, operational runbooks. What you would hand to your CISO and your AI Platform engineering lead on day one.

This doc is cloud-agnostic where the design allows it and explicit where it does not. Primary stack shown on AWS because most BFSI GenAI portfolios run on Bedrock for in-VPC inference and AWS for the data plane; GCP and Azure equivalents are called out inline.

---

## 1. Logical architecture

InferenceLens is a **composition + detection layer**, not a logging or billing vendor. It reads OpenTelemetry span attributes, reconciles them against vendor billing APIs, and runs five derived views (per-feature attribution, runaway detection, substitution recommender, dead-feature flagger, ROI ranking). Six components, each independently deployable.

| Component | Responsibility | Language / framework | Stateful? |
| --- | --- | --- | --- |
| `inferencelens-api` | REST + gRPC API. Auth, RBAC, CFO-pack export, per-feature read. | Python 3.11 + FastAPI + Pydantic v2 | No |
| `inferencelens-aggregator` | OpenTelemetry collector tail; computes cost per call from span tokens × pricing snapshot; writes to ClickHouse. | Python + Cloud Functions / Lambda + Pydantic | No (commits offsets) |
| `inferencelens-recommender` | Stateless substitution recommender. Reads EvalForge probe-set pass rates per (feature_family, candidate_model); emits recommendations. | Python + FastAPI | No |
| `inferencelens-detector` | Runaway + dead-feature detector. Reads ClickHouse aggregates; SPC threshold check; PagerDuty integration. | Python + Cloud Functions / Lambda | No |
| `inferencelens-ui` | FinOps / CFO workbench. Per-feature drill-down, runaway alerts, CFO-pack export. | React 19 + Next.js 15 + TypeScript + Tailwind | No |
| `inferencelens-scheduler` | Daily ETL: vendor billing-API reconciler, revenue-attribution join, retention cleanup. | Airflow 2.9 / MWAA / Cloud Composer | Stateful (DAG runs) |

All six are stateless except the scheduler. State lives in the data layer. Stateless components scale horizontally; the scheduler is single-leader with a cold standby.

**Repo structure** (monorepo via Bazel or pnpm workspaces):

```
inferencelens/
├── apps/
│   ├── api/             # FastAPI service
│   ├── aggregator/      # OpenTelemetry tail composer
│   ├── recommender/     # Substitution recommender
│   ├── detector/        # Runaway + dead-feature detector
│   ├── ui/              # Next.js app
│   └── scheduler/       # Airflow DAGs
├── packages/
│   ├── domain/          # Shared domain models (proto + codegen TS/Python)
│   ├── otel-sdk/        # bank-genai-otel — canonical span shape wrapper
│   ├── auth/            # Shared OIDC/SAML libs
│   └── pricing/         # Pricing snapshot + tokenization helpers
├── infra/
│   ├── terraform/       # Multi-cloud IaC (aws, gcp, azure)
│   ├── kubernetes/      # Helm charts + Kustomize overlays
│   └── policies/        # OPA bundles, IAM templates, network policies
├── docs/
│   ├── ARCHITECTURE.md
│   ├── runbooks/
│   └── api/             # OpenAPI spec
└── tests/
    ├── unit/
    ├── integration/     # uses fake OTel + fake billing APIs
    └── load/            # k6 / locust against the aggregator
```

---

## 2. Physical / deployment architecture

### Runtime

**Primary on AWS (matches most BFSI GenAI deployments via Bedrock):**

| Component | Runtime | Why |
| --- | --- | --- |
| `api` | ECS Fargate (or Cloud Run / Container Apps on GCP/Azure) | Stateless HTTP, autoscale 0-N, request-based billing |
| `aggregator` | Lambda + EventBridge (or Cloud Functions / Functions on GCP/Azure) | Event-driven OTel-tail consumer, autoscaling, no idle cost |
| `recommender` | ECS Fargate | Slightly longer-running than Lambda's idle profile; eval-suite reads cache locally |
| `detector` | Lambda + scheduled trigger (every 15 min) | Runs the 3x-baseline check; PagerDuty integration |
| `ui` | CloudFront + S3 (or Cloud Run / Container Apps) | Static + SSR Next.js, embedded inside the FinOps team's existing dashboards |
| `scheduler` | MWAA (managed Airflow) | Daily vendor billing-API reconciler, revenue-attribution join |

**GCP equivalent:** Cloud Run for `api`/`ui`; Cloud Functions for `aggregator`/`detector`; Cloud Composer for `scheduler`.

**Azure equivalent:** Container Apps for `api`/`ui`; Azure Functions + Event Grid for `aggregator`/`detector`; Data Factory or Airflow on AKS for `scheduler`.

### Network topology

```
Internet
   │
   ▼
[AWS WAF / Cloud Armor / Azure Front Door WAF]
   │   (rate-limit, geo-block, OWASP rule set)
   ▼
[ALB with OIDC / Identity-Aware Proxy / App Gateway]
   │   (SSO check, MFA enforced)
   ▼
[ECS Fargate — api, ui]   ← public subnet, no direct DB access
   │
   ▼ (Service Mesh: mTLS via AWS App Mesh / Istio / Cloud Service Mesh)
   │
[Private subnet — aggregator, recommender, detector, scheduler]
   │
   ├──► [ClickHouse — Aiven / Altinity managed]        (PrivateLink)
   ├──► [PostgreSQL — Aurora / Cloud SQL / Azure DB]   (private endpoint)
   ├──► [Snowflake] (read-only for revenue join)       (PrivateLink)
   ├──► [Redis — ElastiCache / Memorystore]            (private endpoint)
   └──► [S3 / GCS / Blob Storage]                      (private endpoint)

Egress to vendor APIs (Anthropic, Azure OpenAI, Bedrock billing):
   [Secure Web Proxy / Squid] — allow-list of vendor URLs only
   [Network Firewall / VPC Service Controls] — data exfiltration prevention
```

### Region & DR

- **Primary:** US-East (us-east-1 AWS / us-east1 GCP / East US Azure)
- **DR:** US-West (us-west-2 / us-west1 / West US 2). Active-passive. RTO 4h, RPO 1h for the ClickHouse cost-event table.
- **EU instance:** Frankfurt (eu-central-1 / europe-west3 / Germany West Central). Required for EU AI Act and GDPR data-residency for EU customer-segment spend rollups.
- **India instance:** Mumbai (ap-south-1 / asia-south1 / Central India). Required for RBI data localization on Indian retail-arm spend.
- Each regional instance has its own ClickHouse cluster, its own KMS key ring, its own ALB. **Cross-region replication only for the executive view's read replica** — primary cost-event tables stay sovereign.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **ClickHouse** (Aiven / Altinity managed) | `cost_events` table — one row per inference call (or aggregated bucket); per-feature daily rollup materialized view. | 10-50x cheaper than Postgres for time-series at this volume. The right substrate for per-feature cost at fleet scale (~500M calls/yr peak). Same engine [LineageLog](../09-lineagelog-ai-decision-audit/) uses for composer telemetry. |
| **PostgreSQL 15** (Aurora / Cloud SQL) | `feature_catalog` table — the source of truth for `(feature_id, model_used, status, owner_team, business_line, revenue_attribution_path)`. Plus the recommender's decision log. | Relational integrity, joins, mature transactions, well-understood by BFSI ops. The feature catalog is the join key for everything. |
| **Snowflake / Databricks** (read-only) | Revenue-attribution table per feature (joined nightly). Plus the bank's historical cost-allocation snapshots for cross-check. | Already exists at every Tier-1 BFSI shop. We don't introduce a third lake. |
| **Redis** (ElastiCache / Memorystore) | Session cache (UI), idempotency keys (aggregator), rate-limit counters, pricing-snapshot cache. | TTL-based eviction. Multi-AZ for high availability. |
| **S3 / GCS / Blob Storage** | Vendor billing-API raw exports, archived CFO packs, weekly fleet-rollup snapshots. | Cheap durable storage; cross-region replication for DR. |
| **EventBridge / Pub/Sub / Event Hubs** | OTel-collector fan-in topic; vendor billing-API ingest topic. | Native to the cloud; ordered delivery within a partition; replay-able. |

### The cost-event table (ClickHouse)

The consequential schema. Every per-feature attribution question maps to this table:

```sql
CREATE TABLE cost_events (
    -- Identity
    event_id                  String,
    request_id                String,
    feature_id                LowCardinality(String),
    tenant_id                 LowCardinality(String),
    api_key_id                LowCardinality(String),

    -- Vendor + model
    vendor                    LowCardinality(String),  -- anthropic / azure_openai / bedrock
    model                     LowCardinality(String),  -- claude-sonnet-4-5 / gpt-4o / llama-3-1-70b-instruct / ...
    pricing_snapshot_id       LowCardinality(String),  -- which row of model_pricing was used

    -- Tokens + cost
    query_tokens              UInt32,
    response_tokens           UInt32,
    cached_tokens             UInt32 DEFAULT 0,
    cost_usd                  Decimal64(6),
    cost_reconciled           UInt8 DEFAULT 0,         -- 1 after vendor-billing-API reconcile

    -- Performance
    latency_ms                UInt32,
    ttfb_ms                   UInt32,                  -- time to first byte

    -- Composition metadata
    event_timestamp           DateTime64(3, 'UTC'),
    composed_at               DateTime64(3, 'UTC'),
    region                    LowCardinality(String)
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/cost_events', '{replica}')
PARTITION BY toYYYYMM(event_timestamp)
ORDER BY (event_timestamp, feature_id, tenant_id)
TTL event_timestamp + INTERVAL 730 DAY DELETE;        -- 2 years hot; archive to S3 thereafter

-- Daily rollup materialized view (the per-feature attribution surface)
CREATE MATERIALIZED VIEW cost_events_daily_per_feature
ENGINE = ReplicatedSummingMergeTree('/clickhouse/tables/{shard}/cost_events_daily_per_feature', '{replica}')
PARTITION BY toYYYYMM(day)
ORDER BY (day, feature_id, tenant_id, model)
AS SELECT
    toDate(event_timestamp) AS day,
    feature_id,
    tenant_id,
    model,
    sum(cost_usd) AS daily_cost,
    count() AS call_count,
    sum(query_tokens) AS query_tokens_total,
    sum(response_tokens) AS response_tokens_total
FROM cost_events
GROUP BY day, feature_id, tenant_id, model;
```

### The feature catalog (Postgres)

The source of truth for what a feature IS, separate from what its cost LOOKS LIKE.

```sql
CREATE TABLE feature_catalog (
    feature_id                    TEXT PRIMARY KEY,
    feature_name                  TEXT NOT NULL,
    owner_team                    TEXT NOT NULL,
    business_line                 TEXT NOT NULL,        -- retail / wealth / enterprise
    model_used                    TEXT NOT NULL,
    status                        TEXT NOT NULL,        -- active / dormant / decommissioned
    deployed_date                 DATE NOT NULL,
    revenue_attribution_path      TEXT,                  -- Snowflake table.column pointer (NULL for cost-center features)
    eval_suite_family             TEXT,                  -- which EvalForge family probes this feature
    monthly_budget_envelope_usd   NUMERIC(12,2),
    current_status_updated_by     TEXT,
    current_status_updated_at     TIMESTAMPTZ,
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_feature_catalog_status ON feature_catalog (status);
CREATE INDEX idx_feature_catalog_owner ON feature_catalog (owner_team);
CREATE INDEX idx_feature_catalog_business_line ON feature_catalog (business_line);

-- The substitution recommender's decision log
CREATE TABLE substitution_recommendations (
    recommendation_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id                    TEXT NOT NULL REFERENCES feature_catalog(feature_id),
    current_model                 TEXT NOT NULL,
    candidate_model               TEXT NOT NULL,
    accuracy_delta_pct            NUMERIC(5,2),
    monthly_savings_usd           NUMERIC(12,2),
    confidence                    TEXT NOT NULL,         -- high / medium / low
    rationale                     TEXT NOT NULL,
    eval_suite_run_id             TEXT,                  -- pointer to the EvalForge run
    generated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_by                   TEXT,                  -- feature_owner who accepted
    accepted_at                   TIMESTAMPTZ,
    rejected_reason               TEXT
);

CREATE INDEX idx_subs_feature ON substitution_recommendations (feature_id);
CREATE INDEX idx_subs_pending ON substitution_recommendations (feature_id) WHERE accepted_at IS NULL;
```

### Six-deficiency → source-signal mapping

The table that compiles the composition contract. Every cell maps a deficiency to the raw signal that feeds it.

| # | Deficiency | Primary source | Secondary source | Composer action |
| --- | --- | --- | --- | --- |
| 1 | Per-feature attribution | OpenTelemetry span attribute `feature_id` | Vendor billing API (for reconcile) | Aggregate `cost_events` by `feature_id`; materialize the daily-rollup view. |
| 2 | Per-tenant attribution | OpenTelemetry span attribute `tenant_id` | API key tenancy map | Aggregate by `(feature_id, tenant_id)`; segment-level rollup. |
| 3 | Runaway detection | `cost_events_daily_per_feature` rollup | Trailing-7-day baseline | SPC check: alert when day > 3x trailing-7-day baseline AND baseline > $50/day. |
| 4 | Substitution recommender | [EvalForge](../04-evalforge-llm-eval-platform/) probe-set pass rates per (feature_family, candidate_model) | `model_pricing` snapshot | Score each (feature, candidate) pair; recommend if accuracy_delta acceptable AND cost_delta meaningful. |
| 5 | Dead-feature flagger | `feature_catalog.status` vs sampled traffic from `cost_events` | Feature-owner ack workflow | Flag when status=dormant/decommissioned AND sampled_calls > 0 in trailing 60d. |
| 6 | Per-feature ROI | Snowflake `product_revenue_attribution` table | `feature_catalog.revenue_attribution_path` pointer | Join by `feature_id`; net = revenue - cost; ranked view. Lag tolerance: 7 days. |

### Retention & data classification

| Data class | Retention | Storage | Justification |
| --- | --- | --- | --- |
| `cost_events` rows | 2 years hot, 7 years archived | ClickHouse hot for 24 months; archive to S3 thereafter | FinOps audit + SOX support for the AI line item |
| `cost_events_daily_per_feature` rollup | 5 years | ClickHouse | Long-horizon trend analysis |
| Vendor billing-API raw exports | 7 years | S3 with Object Lock | Audit-of-record for vendor invoices |
| CFO packs (PDF + CSV exports) | 5 years | S3 + cross-region replication | Quarterly review audit trail |
| `substitution_recommendations` | 3 years | Postgres | Decision history for FinOps process audit |
| `feature_catalog` | Indefinite | Postgres | Source of truth for the fleet |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with envelope encryption. Customer-Managed Encryption Keys (CMK / CMEK) in AWS KMS / Cloud KMS / Azure Key Vault. Bank's key rotation policy applies (typically 90 days). Keys are region-scoped — never cross region boundary.
- **In transit.** TLS 1.3 minimum north-south. mTLS on east-west via service mesh.
- **Field-level.** `tenant_id` is hashed (SHA-256 with a KMS-managed pepper) before write — InferenceLens does not need to recover raw tenant IDs to do per-segment aggregation. Customer-segment metadata is in the Snowflake side of the join.
- **Database-level.** Aurora TDE on PostgreSQL; ClickHouse encrypted-disk; Snowflake native encryption; Redis encryption-at-rest.

### Secrets management

- **Primary store.** HashiCorp Vault (most BFSI shops already run it) or AWS Secrets Manager.
- **Application secrets** fetched at boot via Workload Identity Federation. No env-var secrets in container manifests. Rotation: 90 days, zero-downtime via dual-credential rolling.
- **Service account keys.** None. IRSA (AWS) / Workload Identity (GCP) / Managed Identity (Azure).
- **Vendor billing-API keys.** Stored in Vault with audit logging on every read; rotation 30 days.

### Identity provider & user management

- **IdP.** Whatever the bank already runs — Okta, Microsoft Entra ID, or Ping Identity. SAML 2.0 + OIDC. We do not run our own.
- **MFA.** Required by bank policy. Enforced at the IdP. Passkey / FIDO2 preferred; TOTP fallback.
- **Sessions.** OIDC ID token + signed session cookie (HttpOnly, Secure, SameSite=Strict). 8-hour absolute expiry, 30-minute idle timeout.
- **Service-to-service identity.** IRSA (AWS) / SPIFFE IDs (mesh-native). Each component has a unique workload identity. mTLS enforces identity at every hop.

### RBAC matrix

Five roles, mapped to bank roles, scoped per region:

| Role | Permissions | Maps to (bank role) |
| --- | --- | --- |
| `il:viewer` | Read fleet-level spend rollup; no per-feature drill-down | Exec read-only, board reporting |
| `il:finops_analyst` | `viewer` + per-feature drill-down + CFO-pack export | FinOps team analyst |
| `il:feature_owner` | `viewer` + read-write on their own feature's catalog row; accept/reject substitution recommendations | Line-1 PMs |
| `il:cfo` | `finops_analyst` + cross-region read; ROI ranking view | CFO's office |
| `il:admin` | Full config, role management, integration config, vendor billing-API credentials | AI Platform engineering lead |

Authorization via Open Policy Agent (OPA) + Rego policies. Every API call evaluates policy at the gateway. Every decision logged to the audit log.

### Network controls

- **Perimeter.** AWS PrivateLink + Network Firewall / VPC Service Controls (GCP) / Azure Private Endpoints. Egress to public internet only via Secure Web Proxy with allow-list.
- **Lateral.** AWS Security Groups + Network ACLs / Cloud NGFW / Azure NSGs. Layer-7 inspection on the service mesh.
- **Ingress.** AWS WAF / Cloud Armor / Azure WAF with OWASP CRS + custom rules for the API surface.
- **Zero-trust.** All inter-service calls authenticated via SPIFFE mTLS. No "trusted internal network" assumption.

### Threat model — what we explicitly defend against

| Threat | Mitigation |
| --- | --- |
| Compromised API token | Short-lived tokens, mTLS service-to-service, IdP-side revocation propagates ≤5 min |
| Insider — analyst pulls all tenant cost data | `tenant_id` is hashed; RBAC limits feature_owner to their own feature scope |
| Compromised cost-event row (cost poisoning to hide a runaway) | Cost reconciled daily against vendor billing API; mismatch > 2% pages on-call |
| Vendor billing-API compromise (forged invoices) | InferenceLens treats OTEL-derived cost as primary; vendor invoice as cross-check |
| Database exfiltration via SQL injection | Parameterized queries only; ORM-only (SQLAlchemy + Pydantic) at the API boundary; WAF rule set |
| Egress data exfiltration | VPC Service Controls + Secure Web Proxy allow-list |
| Substitution recommender poisoning (bad eval-suite data) | Eval-suite runs are signed at the EvalForge boundary; signature verified at the InferenceLens recommender |

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs | CloudWatch / Cloud Logging / Azure Monitor + Datadog | Existing SOC pane |
| Distributed traces | OpenTelemetry → Datadog APM | The same substrate InferenceLens consumes |
| Metrics | Prometheus + Grafana (or Datadog metrics) | RED-method per service |
| Aggregator-completeness time-series | ClickHouse view `aggregator_health` | Self-monitoring (eats its own dog food) |
| Audit log | Postgres `audit_log` + S3 Object Lock | SOX support |

### Alerting

| Severity | Channel | SLO |
| --- | --- | --- |
| P1 (aggregator down >5 min, OR runaway detected on any feature) | PagerDuty primary + secondary, Slack #ai-platform-incident | Acknowledge ≤5 min |
| P2 (vendor billing reconcile drift >5% in any 24h window) | PagerDuty (lower urgency), Slack | Acknowledge ≤30 min |
| P3 (dead-feature flag not acked by feature owner in 7 days) | Slack only | Triaged in weekly FinOps standup |
| P4 (informational - new substitution recommendations) | Daily digest email | None |

### Backup & DR

- **ClickHouse.** Weekly backup to S3. ReplicatedMergeTree gives HA within region.
- **PostgreSQL.** Continuous WAL streaming to S3. Daily snapshots, 35-day retention. Point-in-time recovery within retention window.
- **Object stores.** Object Lock + versioning + cross-region replication for CFO-pack archive (within same regulatory region only).
- **DR drill cadence.** Quarterly. Full failover to US-West, validate RTO 4h / RPO 1h for the ClickHouse aggregate, fail back. Runbook in `docs/runbooks/dr-failover.md`.

### Runbooks (one paragraph each in the repo)

- `dr-failover.md` — full region failover
- `aggregator-stuck.md` — when the OTel-tail fan-in stalls
- `vendor-billing-reconcile-drift.md` — when InferenceLens-computed cost diverges from vendor invoice
- `runaway-alert-triage.md` — what to do when a 3x-baseline alert fires
- `dead-feature-kill.md` — operational steps to retire an endpoint after a dead-feature alert
- `substitution-rollout.md` — how to canary a substitution rec from 1% to 100% over 14 days

---

## 6. Compliance posture

| Framework | Posture |
| --- | --- |
| **SOC 2 Type II** | All six components in scope. Annual external audit. |
| **PCI-DSS** | Out of scope (InferenceLens does not process card data; it composes cost about features that may). PCI scope minimization via tenant-hash + no raw customer IDs. |
| **GLBA** | Customer financial-data adjacency only — we do not read inference payloads, only token counts. Access controls + audit trail apply. |
| **FinOps Foundation framework** | [FinOps Foundation](https://www.finops.org/framework/) Level 3 maturity (Inform / Optimize / Operate phases) is the target posture for the AI / inference cost domain. |
| **NIST AI RMF 1.0** | Govern function on kill-criterion (dead-feature flagger); Map function on per-feature attribution (every feature has a cost surface and an owner). |
| **EU AI Act Article 12** | Per-feature cost is part of the record-keeping surface for high-risk AI systems. Interlocks with [LineageLog](../09-lineagelog-ai-decision-audit/) for the decision-grain side. |
| **GDPR** | EU instance enforces data residency. No PII in InferenceLens — only `tenant_id` hash. |
| **India RBI data localization** | Indian retail-arm features run on the India regional instance; cost-event data does not leave the region. |
| **SOX (for the public BHC parent)** | AI line item in the cost report is auditable per-feature. Vendor billing-API reconcile provides the cross-check. |

---

## 7. What is deliberately not here

- **A custom logging vendor.** We read OpenTelemetry. We compose, we do not collect.
- **A custom billing platform.** Anthropic, Azure, AWS remain the vendor-of-record for invoicing. We reconcile against their APIs.
- **A custom eval suite.** We read [EvalForge](../04-evalforge-llm-eval-platform/) probe-set pass rates per (feature_family, candidate_model).
- **A budget-enforcement gateway.** That lives on the request path (the bank's GenAI gateway). We are off the request path.
- **A customer-facing surface.** Internal FinOps / AI Platform tool only.
- **A standalone authentication system.** We integrate with the bank's IdP.

That last list is the discipline. Every internal-build I have watched die has died on scope creep into one of those.

---

## Appendix — sample API contract

```python
# GET /v1/features/{feature_id}/economics
# Auth: OIDC bearer; role: il:viewer or higher
# Response 200:
{
    "feature_id": "FT_001",
    "feature_name": "customer-service-assistant",
    "owner_team": "line1.contact-center",
    "business_line": "retail",
    "model_used": "claude-sonnet-4-5",
    "status": "active",

    "attribution_30d": {
        "modeled_monthly_spend_usd": 144872.00,
        "modeled_cost_per_call_usd": 0.0345,
        "monthly_query_volume": 4200000,
        "per_tenant_breakdown": [
            {"tenant_segment": "retail_t1", "spend_usd": 88420.00},
            {"tenant_segment": "retail_t2", "spend_usd": 56452.00}
        ]
    },

    "runaway_alert": {
        "active": true,
        "first_seen": "2026-05-01",
        "multiplier": 3.7,
        "daily_overspend_usd": 4334.00,
        "modeled_total_overspend_usd": 195030.00,
        "likely_cause": "retrieval_depth_misconfig"
    },

    "substitution_recommendation": {
        "candidate_model": "claude-haiku-4-5",
        "accuracy_delta_pct": -1.4,
        "monthly_savings_usd": 182000.00,
        "confidence": "high",
        "eval_suite_run_id": "evf_2026_06_10_customer_service"
    },

    "dead_feature_flag": null,

    "roi": {
        "modeled_monthly_revenue_usd": 0,
        "modeled_monthly_cost_usd": 144872.00,
        "modeled_monthly_net_usd": -144872.00,
        "verdict": "cost_center"
    },

    "composed_at": "2026-06-15T09:12:30Z",
    "composition_seconds": 0.004
}
```

OpenAPI spec lives at `apps/api/openapi.yaml` and is the source of truth for both the CLI and the UI clients.
