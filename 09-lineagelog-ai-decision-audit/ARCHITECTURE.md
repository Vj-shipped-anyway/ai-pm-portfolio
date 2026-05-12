# Architecture — LineageLog

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network topology, operational runbooks. What you would hand to your CISO and your platform engineering lead on day one.

This doc is cloud-agnostic where the design allows it and explicit where it does not. Primary stack shown on Google Cloud because the design aligns directly with the *Building secure multi-agent systems on Google Cloud* reference paper (Kannan, Sizemore, Herriford et al., 2025); AWS and Azure equivalents are called out inline.

---

## 1. Logical architecture

LineageLog is a **composition layer**, not a logging vendor. It does not collect logs; it composes existing log fragments into a single decision-grain record. Six components, each independently deployable.

| Component | Responsibility | Language / framework | Stateful? |
| --- | --- | --- | --- |
| `lineagelog-api` | REST + gRPC API. Auth, RBAC, exam-pack rendering, lineage record reads. | Python 3.11 + FastAPI + Pydantic v2 | No |
| `lineagelog-composer` | Async composition worker. Subscribes to four log topics; binds at `(decision_id, customer_id_hash, timestamp)`; writes immutable lineage row. | Python + Cloud Functions / Lambda + Pydantic | No (commits offsets) |
| `lineagelog-ui` | Compliance / audit workbench. Drill-into-decision view, exam-pack rendering, legal-hold management. | React 19 + Next.js 15 + TypeScript + Tailwind | No |
| `lineagelog-cli` | Operator tool — backfill, replay, ad-hoc exam-pack export, legal-hold bulk operations. | Python + Click | No |
| `lineagelog-ingesters` | Four sidecar consumers, one per source: Cloud Logging tail, Cloud Audit tail, Agent Identity tail, OTel collector. | Python + Faust (Kafka) / Cloud Functions (Pub/Sub) | No (commit offsets) |
| `lineagelog-scheduler` | Daily ETL: outcome backlinks, vendor-pin diffs, retention cleanup. | Airflow 2.9 / Cloud Composer / MWAA | Stateful (DAG runs) |

All six are stateless except the scheduler. State lives in the data layer. Stateless components scale horizontally; the scheduler is single-leader with a cold standby.

**Repo structure** (monorepo via Bazel or pnpm workspaces):

```
lineagelog/
├── apps/
│   ├── api/             # FastAPI service
│   ├── composer/        # Cloud Functions composer
│   ├── ui/              # Next.js app
│   ├── cli/             # Click CLI
│   ├── ingesters/       # 4 sidecar consumers
│   └── scheduler/       # Airflow DAGs
├── packages/
│   ├── domain/          # Shared domain models (proto + codegen TS/Python)
│   ├── auth/            # Shared OIDC/SAML libs
│   └── telemetry/       # OpenTelemetry helpers
├── infra/
│   ├── terraform/       # Multi-cloud IaC (gcp, aws, azure)
│   ├── kubernetes/      # Helm charts + Kustomize overlays
│   └── policies/        # OPA bundles, IAM templates, network policies
├── docs/
│   ├── ARCHITECTURE.md
│   ├── runbooks/
│   └── api/             # OpenAPI spec
└── tests/
    ├── unit/
    ├── integration/     # uses fake log surfaces
    └── load/            # k6 / locust against the composer
```

---

## 2. Physical / deployment architecture

### Runtime

**Primary on GCP (matches the Google Cloud reference architecture):**

| Component | Runtime | Why |
| --- | --- | --- |
| `api` | Cloud Run (managed) | Stateless HTTP, autoscale 0-N, request-based billing |
| `composer` | Cloud Functions gen 2 on Pub/Sub | Event-driven, autoscaling, no idle cost |
| `ui` | Cloud Run | Static + SSR Next.js, embedded in MRM workbench iframes |
| `cli` | Local + Cloud Build for CI runs | Operator tool, not a service |
| `ingesters` | Cloud Functions gen 2 | One per log source; commit offsets via Pub/Sub |
| `scheduler` | Cloud Composer 3 (managed Airflow) | Existing skill set in most BFSI ops teams |

**AWS equivalent:** ECS Fargate or EKS for `api`/`ui`; Lambda + EventBridge for `composer` and `ingesters`; MWAA for `scheduler`.

**Azure equivalent:** Container Apps for `api`/`ui`; Functions + Event Grid for `composer` and `ingesters`; Data Factory or Airflow on AKS for `scheduler`.

### Network topology

```
Internet
   │
   ▼
[Cloud Armor / AWS WAF / Azure Front Door WAF]
   │   (rate-limit, geo-block, OWASP rule set)
   ▼
[Identity-Aware Proxy / ALB OIDC / App Gateway]
   │   (SSO check, MFA enforced)
   ▼
[Cloud Run / ECS Fargate — api, ui]   ← public subnet, no direct DB access
   │
   ▼ (Service Mesh: mTLS, Cloud Service Mesh / Istio / AWS App Mesh)
   │
[Private subnet — composer, ingesters, scheduler]
   │
   ├──► [PostgreSQL — Cloud SQL / RDS]                 (private endpoint only)
   ├──► [ClickHouse — Aiven / Altinity managed]        (private endpoint)
   ├──► [Snowflake / Databricks]                       (PrivateLink / PSC)
   ├──► [Redis — Memorystore / ElastiCache]            (private endpoint)
   └──► [GCS Object Lock / S3 Object Lock]             (private endpoint)

Egress to vendor APIs (Anthropic, Azure OpenAI, Bedrock):
   [Secure Web Proxy / Squid] — allow-list of vendor URLs only
   [VPC Service Controls / Network Firewall] — data exfiltration prevention
```

### Region & DR

- **Primary:** US-East (us-east1 GCP / us-east-1 AWS / East US Azure)
- **DR:** US-West (us-west1 / us-west-2 / West US 2). Active-passive. RTO 4h, RPO 5min for the `decision_lineage` table.
- **EU instance:** Frankfurt (europe-west3 / eu-central-1 / Germany West Central). Required for EU AI Act and GDPR — lineage of EU customers cannot egress region.
- **India instance:** Mumbai (asia-south1 / ap-south-1 / Central India). Required for RBI data localization on Indian retail arms.
- Each regional instance has its own database, its own KMS key ring, its own Identity-Aware Proxy. **No cross-region replication for the `decision_lineage` table** — each region is sovereign for its own decisions. The WORM archive replicates cross-region within the same regulatory boundary only.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** (Cloud SQL / RDS) | `decision_lineage` immutable table, attestation history, audit log, legal-hold flags. | Relational integrity, joins, mature transactions, well-understood by BFSI ops. Append-only via insert-only role + trigger guard. |
| **ClickHouse** (Aiven / Altinity managed) | High-cardinality observability — composer latency, source-tail lag, composition-completeness time series. | 10-50x cheaper than Postgres for time-series at this volume. Interlocks with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/)'s ClickHouse for shared drift-signal querying. |
| **Snowflake / Databricks** (read-only) | Inference logs, retrieval-set captures, feature-store temporal lookups. | Already exists at every Tier-1 BFSI shop. We don't introduce a third lake. |
| **Redis** (Memorystore / ElastiCache) | Session cache (UI), idempotency keys (composer), rate-limit counters. | TTL-based eviction. Multi-AZ for high availability. |
| **GCS / S3 / Blob Storage with Object Lock** | **WORM archive of lineage records** + exam-pack PDFs + JSON + cross-region replication. | Object Lock = Write-Once-Read-Many for the SR 11-7 / EU AI Act seven-year retention. |
| **Pub/Sub / Kinesis / Event Hubs** | Source-tail topics, one per log surface. Composer fan-in subscription. | Native to the cloud; ordered delivery within a partition; replay-able. |

### The decision-grain composition table

The consequential schema. Every regulator question maps to one of these columns:

```sql
-- Append-only. Immutability enforced via insert-only role + DENY on UPDATE/DELETE
-- to anyone except the legal-hold service account (which can flag, not modify).
-- Partitioned by month for retention cycling and exam-window queries.

CREATE TABLE decision_lineage (
    -- Identity
    lineage_id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id                   TEXT NOT NULL,
    customer_id_hash              TEXT NOT NULL,            -- SHA-256 with KMS-managed pepper
    decision_type                 TEXT NOT NULL,            -- loan_approval / claims_triage / kyc_review / fraud_screen
    decision_timestamp            TIMESTAMPTZ NOT NULL,
    decision_outcome              TEXT NOT NULL,
    decision_value                NUMERIC(14,2),

    -- Deficiency #1 — prompt versioning
    prompt_template_id            TEXT NOT NULL,
    prompt_template_effective_at  DATE NOT NULL,
    prompt_policy_hash            TEXT NOT NULL,            -- SHA-256 of the template body

    -- Deficiency #2 — retrieval-set capture
    retrieval_set                 JSONB NOT NULL,           -- [{doc_id, doc_version, retrieved_at}, ...]

    -- Deficiency #3 — model-snapshot pin
    model_id                      TEXT NOT NULL,
    model_vendor                  TEXT NOT NULL,            -- internal / anthropic / azure_openai / bedrock
    model_snapshot_id             TEXT NOT NULL,
    model_training_date           DATE,
    model_pin_verified            BOOLEAN NOT NULL,         -- response-header pin == registry pin?

    -- Deficiency #4 — feature-at-decision-time
    feature_snapshot              JSONB NOT NULL,           -- {fico, dti, ltv, ...} as of decision_timestamp
    feature_pipeline_version      TEXT NOT NULL,
    feature_source                TEXT NOT NULL,            -- temporal_api / cached_pit / reconstructed

    -- Deficiency #5 — reviewer attribution
    reviewer_actor_type           TEXT NOT NULL,            -- human_user_delegated / agent_autonomous
    reviewer_actor_id             TEXT,                     -- user_id if delegated, NULL if autonomous
    reviewer_agent_identity       TEXT NOT NULL,            -- SPIFFE ID
    reviewer_delegation_token_id  TEXT,                     -- NULL if autonomous

    -- Deficiency #6 — outcome backlink
    outcome_type                  TEXT,                     -- repaid_on_time / charge_off_30d / customer_complaint_cfpb / ...
    outcome_value                 TEXT,
    outcome_date                  DATE,
    outcome_observed              BOOLEAN NOT NULL DEFAULT FALSE,

    -- Cross-references to raw log surfaces
    cloud_logging_ref             TEXT NOT NULL,
    cloud_audit_ref               TEXT NOT NULL,
    agent_identity_ref            TEXT NOT NULL,
    otel_trace_ref                TEXT NOT NULL,

    -- Composition + retention metadata
    composed_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    composition_seconds           NUMERIC(6,4) NOT NULL,
    lineage_complete              BOOLEAN NOT NULL,
    legal_hold                    BOOLEAN NOT NULL DEFAULT FALSE,
    legal_hold_set_by             TEXT,
    legal_hold_set_at             TIMESTAMPTZ,
    retention_until               TIMESTAMPTZ NOT NULL,     -- decision_timestamp + 7 years by default
    row_hash                      TEXT NOT NULL             -- SHA-256 of all fields above, HSM-signed
) PARTITION BY RANGE (decision_timestamp);

CREATE UNIQUE INDEX idx_decision_lineage_decision_id
    ON decision_lineage (decision_id);
CREATE INDEX idx_decision_lineage_customer
    ON decision_lineage (customer_id_hash, decision_timestamp DESC);
CREATE INDEX idx_decision_lineage_model
    ON decision_lineage (model_id, decision_timestamp DESC);
CREATE INDEX idx_decision_lineage_outcome
    ON decision_lineage (outcome_type) WHERE outcome_observed = TRUE;
CREATE INDEX idx_decision_lineage_legal_hold
    ON decision_lineage (legal_hold) WHERE legal_hold = TRUE;

-- Immutability guard. UPDATE allowed only on legal_hold fields.
CREATE OR REPLACE FUNCTION decision_lineage_immutability_guard()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.decision_id      IS DISTINCT FROM OLD.decision_id) OR
           (NEW.prompt_template_id IS DISTINCT FROM OLD.prompt_template_id) OR
           (NEW.retrieval_set    IS DISTINCT FROM OLD.retrieval_set) OR
           (NEW.model_snapshot_id IS DISTINCT FROM OLD.model_snapshot_id) OR
           (NEW.feature_snapshot IS DISTINCT FROM OLD.feature_snapshot) OR
           (NEW.reviewer_actor_id IS DISTINCT FROM OLD.reviewer_actor_id) OR
           (NEW.row_hash         IS DISTINCT FROM OLD.row_hash) THEN
            RAISE EXCEPTION 'decision_lineage is immutable except for outcome backlink + legal_hold fields';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'decision_lineage rows cannot be deleted; use retention_until cycling instead';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER decision_lineage_guard
    BEFORE UPDATE OR DELETE ON decision_lineage
    FOR EACH ROW EXECUTE FUNCTION decision_lineage_immutability_guard();
```

The trigger guards the immutable columns at the database level — a compromised application credential cannot rewrite history. The `outcome_observed`, `outcome_type`, `outcome_value`, `outcome_date`, and legal-hold fields are deliberately mutable because they materialize over time.

### Six-deficiency → log-source mapping

The table that compiles the composition contract. Every cell maps a deficiency to the raw log surface that feeds it.

| # | Deficiency | Primary source | Secondary source | Composer action |
| --- | --- | --- | --- | --- |
| 1 | Prompt versioning | Prompt-template registry (Postgres) | Cloud Logging request body | Join by `(model_id, effective_at <= decision_timestamp)`; write `template_id` + `policy_hash`. |
| 2 | Retrieval-set capture | RAG sidecar Pub/Sub topic | Vector store retention | Subscribe; bind by `decision_id`; write retrieved doc list with versions. |
| 3 | Model-snapshot pin | Vendor response headers | Model registry (MLflow / SageMaker / Vertex) | Extract header pin; cross-check vs registry; flag `model_pin_verified=false` on mismatch. Interlocks with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) v0.5. |
| 4 | Feature-at-decision-time | Feature store temporal API (Tecton / Databricks / Vertex AI Feature Store) | Snowflake / Databricks point-in-time table | Call with `(customer_id, decision_timestamp)`; fall back to cached PIT if API down. |
| 5 | Reviewer attribution | Agent Identity Auth Manager (SPIFFE) | Cloud Audit Log principal | Distinguish `human_user_delegated` (with `delegation_token_id`) from `agent_autonomous` (with SPIFFE ID). |
| 6 | Outcome backlink | Daily ETL from loss-event lake | CFPB complaint system + claims platform + servicing platform | Match by `customer_id_hash` + time window; flag `outcome_observed=true` when match found. |

### ClickHouse schema (observability time-series)

```sql
CREATE TABLE composer_telemetry (
    composer_instance  LowCardinality(String),
    decision_id        String,
    composed_at        DateTime64(3, 'UTC'),
    composition_ms     UInt32,
    lineage_complete   UInt8,
    deficiencies_open  UInt8,                 -- 0-6
    source_lag_ms      Map(LowCardinality(String), UInt32),  -- per-source tail lag
    region             LowCardinality(String)
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/composer_telemetry', '{replica}')
PARTITION BY toYYYYMM(composed_at)
ORDER BY (composed_at, decision_id)
TTL composed_at + INTERVAL 730 DAY DELETE;   -- 2 years hot, archive to GCS thereafter
```

### Retention & data classification

| Data class | Retention | Storage | Justification |
| --- | --- | --- | --- |
| `decision_lineage` rows | 7 years (10 years for EU) | Postgres hot for 12 months; archive to GCS Object Lock after | SR 11-7, EU AI Act Article 12 |
| Exam-pack PDFs + JSON | 7 years | GCS Object Lock + cross-region replication | Same |
| Retrieval-set captures | 7 years | Postgres JSONB + GCS for the doc bodies | Same |
| Audit log on lineage access | 7 years | Postgres partitioned + GCS Object Lock | Audit-on-audit |
| Composer telemetry | 2 years hot | ClickHouse; aggregate longer history archived | Operational |
| Validator session data | 8 hours | Redis | Operational |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with envelope encryption. Customer-Managed Encryption Keys (CMEK / CMK) in Cloud KMS / AWS KMS / Azure Key Vault. Bank's key rotation policy applies (typically 90 days). Keys are region-scoped — never cross region boundary.
- **In transit.** TLS 1.3 minimum north-south. mTLS on east-west via service mesh.
- **Field-level.** `customer_id_hash` is SHA-256 with a KMS-managed pepper. Raw customer IDs never touch LineageLog storage. The Data Vault Agent pattern from Google's *Building secure multi-agent systems* reference applies directly here.
- **Row-level hash.** Every `decision_lineage` row has a `row_hash` (SHA-256 of all fields) signed by an HSM-backed code-signing key at write time. Tamper detection.
- **Database-level.** Cloud SQL TDE on PostgreSQL; ClickHouse encrypted-disk; Snowflake native encryption; Redis encryption-at-rest.

### Secrets management

- **Primary store.** HashiCorp Vault (most BFSI shops already run it) or Cloud Secret Manager.
- **Application secrets** fetched at boot via Workload Identity Federation. No env-var secrets in container manifests. Rotation: 90 days, zero-downtime via dual-credential rolling.
- **Service account keys.** None. Workload Identity (GCP) / IRSA (AWS) / Managed Identity (Azure). Aligns with Google's *Building secure multi-agent systems* guidance to never use long-lived service account keys.
- **Row-hash signing key.** HSM-backed (Cloud HSM / CloudHSM / Azure Dedicated HSM).

### Identity provider & user management

- **IdP.** Whatever the bank already runs — Okta, Microsoft Entra ID, or Ping Identity. SAML 2.0 + OIDC. We do not run our own.
- **MFA.** Required by bank policy. Enforced at the IdP. Passkey / FIDO2 preferred; TOTP fallback.
- **Sessions.** OIDC ID token + signed session cookie (HttpOnly, Secure, SameSite=Strict). 8-hour absolute expiry, 30-minute idle timeout.
- **Service-to-service identity.** SPIFFE IDs (matches Google Cloud Agent Identity pattern). Each component has a unique workload identity. mTLS enforces identity at every hop.

### RBAC matrix

Six roles, mapped to bank roles, scoped per region:

| Role | Permissions | Maps to (bank role) |
| --- | --- | --- |
| `ll:viewer` | Read fleet-level lineage health; no decision-level access | Exec read-only, board reporting |
| `ll:auditor_l3` | Read lineage records (no edit); export exam packs | Internal Audit (line 3) |
| `ll:validator` | `auditor_l3` + edit attestation metadata; cannot edit immutable lineage fields | Line-2 validators (MRM team) |
| `ll:compliance` | `validator` + set legal-hold flags; cross-region read on legal-matter scope | Head of Compliance, regulator-facing teams |
| `ll:cro` | `compliance` + cross-region read on portfolio scope; export at fleet level | CRO, Head of MRM |
| `ll:admin` | Full config, role management, integration config | Platform engineering lead |

Authorization implemented via Open Policy Agent (OPA) + Rego policies. Every API call evaluates policy at the gateway. Every decision logged to the audit log.

### Network controls

- **Perimeter.** VPC Service Controls (GCP) / AWS PrivateLink + Network Firewall / Azure Private Endpoints. Egress to public internet only via Secure Web Proxy with allow-list.
- **Lateral.** Cloud NGFW / AWS Security Groups + Network ACLs / Azure NSGs. Layer-7 inspection on the service mesh.
- **Ingress.** Cloud Armor / AWS WAF / Azure WAF with OWASP CRS + custom rules for the API surface.
- **Zero-trust.** All inter-service calls authenticated via SPIFFE mTLS. No "trusted internal network" assumption.

### Threat model — what we explicitly defend against

| Threat | Mitigation |
| --- | --- |
| Compromised API token | Short-lived tokens, mTLS service-to-service, IdP-side revocation propagates <=5 min |
| Insider — auditor pulls all customer data | `customer_id_hash` (not raw IDs); RBAC limits validator to decision-grain scope, not customer-grain bulk queries |
| Compromised lineage row (poisoning) | Row-hash HSM-signed at write; immutability trigger + insert-only role; periodic re-verification job |
| Vendor model silent update | Snapshot pin tracked per decision; response-header pin extraction (interlocks with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) v0.5) |
| Database exfiltration via SQL injection | Parameterized queries only; ORM-only (SQLAlchemy + Pydantic) at the API boundary; Cloud Armor WAF rule set |
| Egress data exfiltration | VPC Service Controls + Secure Web Proxy allow-list |
| Tampering with immutable history | Database trigger denies UPDATE/DELETE on immutable fields; row-hash mismatch detection job runs nightly |

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs | Cloud Logging + Datadog / CloudWatch / Azure Monitor | Existing SOC pane |
| Distributed traces | Cloud Trace + OpenTelemetry → Datadog APM | Composer fan-in latency |
| Metrics | Prometheus + Grafana (or Datadog metrics) | RED-method per service |
| Composer health time-series | ClickHouse `composer_telemetry` | Composer-specific dashboards |
| LLM-specific traces | Langfuse (self-hosted) for GenAI proxy | Only for the GenAI-decision lineage path |
| Audit log | Postgres `audit_log` + GCS Object Lock | SR 11-7 retention |

### Alerting

| Severity | Channel | SLO |
| --- | --- | --- |
| P1 (composer down >5 min in any region) | PagerDuty primary + secondary, Slack #lineage-incident | Acknowledge <=5 min |
| P2 (composition completeness <95% in a 1h window) | PagerDuty (lower urgency), Slack | Acknowledge <=30 min |
| P3 (single-source tail lag >5 min) | Slack only | Triaged next business day |
| P4 (informational) | Daily digest email | None |

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to GCS / S3. Daily snapshots, 35-day retention. Point-in-time recovery within retention window.
- **ClickHouse.** Weekly backup to GCS / S3. ReplicatedMergeTree gives HA within region.
- **Object stores.** Object Lock + versioning + cross-region replication for lineage WORM archive (within the same regulatory region only — never US ↔ EU).
- **DR drill cadence.** Quarterly. Full failover to US-West, validate RTO 4h / RPO 5min for the `decision_lineage` table, fail back. Runbook in `docs/runbooks/dr-failover.md`.

### Runbooks (one paragraph each in the repo)

- `dr-failover.md` — full region failover
- `composer-stuck.md` — when the composer's fan-in stalls
- `source-tail-lag-storm.md` — when one log source's tail grows beyond SLO
- `exam-pack-export.md` — pulling a complete decision lineage for an OCC exam
- `legal-hold-cascade.md` — applying legal hold when a customer files litigation
- `right-to-erasure.md` — GDPR-compliant cascading deletion (with legal-hold override)

---

## 6. Compliance posture

| Framework | Posture |
| --- | --- |
| **SOC 2 Type II** | All six components in scope. Annual external audit. |
| **PCI-DSS** | In scope only when the underlying model touches cardholder data. LineageLog itself doesn't process card data; it composes lineage about decisions that may. PCI scope minimization via `customer_id_hash` + KMS pepper at the source. |
| **GLBA** | Customer financial data handled with field-level hashing + access controls + audit trail. Right-to-be-forgotten cascades to lineage records via `customer_id_hash` deletion (with legal-hold override). |
| **SR 11-7 / OCC Bulletin 2011-12** | The decision-grain lineage is the missing piece for "documented ongoing monitoring" of model decisions. PRD references the relevant supervisory expectations. |
| **NIST AI RMF 1.0** | Decision-grain lineage maintained for the four model families (credit, claims, KYC, fraud). LineageLog is the implementation surface for the framework's "Map" + "Measure" functions. |
| **EU AI Act Article 12** | Record-keeping requirement for high-risk AI systems. LineageLog is the explicit implementation surface. EU instance enforces data residency. |
| **GDPR** | EU instance enforces data residency. Right-to-erasure cascades to `customer_id_hash` deletion with legal-hold override. DPO sign-off documented per region. |
| **India RBI data localization** | Indian retail-arm fleet runs on the India regional instance only. No cross-border replication. |
| **OCC / Fed / CFPB exam readiness** | Sub-minute query per `decision_id`; exam-pack export in seconds. Continuous, not annual. |

---

## 7. What is deliberately not here

- **A custom logging vendor.** We read from Cloud Logging / Cloud Audit Logs / Agent Identity Auth Manager / OpenTelemetry. We compose, we do not collect.
- **A custom feature store.** We call the bank's existing Tecton / Databricks Feature Store / Vertex AI Feature Store temporal API.
- **A custom model registry.** We read from MLflow / SageMaker / Vertex.
- **A retraining engine.** LineageLog provides outcome backlinks; the bank's existing MLOps platform retrains.
- **A customer-facing surface.** Internal compliance and audit tool only.
- **A standalone authentication system.** We integrate with the bank's IdP.

That last list is the discipline. Every internal-build I have watched die has died on scope creep into one of those.

---

## Appendix — sample API contract

```python
# GET /v1/lineage/{decision_id}
# Auth: OIDC bearer; role: ll:auditor_l3 or higher
# Response 200:
{
    "lineage_id": "ee5f8c1a-...",
    "decision_id": "DEC_0150_20260312",
    "customer_id_hash": "CUST_851897",
    "decision_type": "loan_approval",
    "decision_timestamp": "2026-03-12T18:41:32Z",
    "decision_outcome": "DENY",
    "decision_value": 65673.12,

    "prompt": {
        "template_id": "template_loan_v3.2.2",
        "effective_at": "2026-03-05",
        "policy_hash": "sha256:5b9a3c...e7"
    },
    "retrieval_set": [
        {"doc_id": "policy_credit_v2_3", "doc_version": "v2.3", "retrieved_at": "2026-03-12T18:41:32Z"},
        {"doc_id": "disclosure_truth_in_lending", "doc_version": "v4.1", "retrieved_at": "2026-03-12T18:41:32Z"},
        {"doc_id": "rate_card_2026q1", "doc_version": "v1.0", "retrieved_at": "2026-03-12T18:41:32Z"},
        {"doc_id": "internal_underwriting_guide", "doc_version": "v8.7", "retrieved_at": "2026-03-12T18:41:32Z"}
    ],
    "model_snapshot": {
        "model_id": "loan_pd_v3",
        "vendor": "internal",
        "snapshot_id": "internal-xgb-3.2.1",
        "training_date": "2025-08-12",
        "pin_verified": true
    },
    "feature_at_decision_time": {
        "fico": 692,
        "dti": 0.20,
        "ltv": 0.67,
        "feature_pipeline_version": "fp_credit_v12.4",
        "snapshot_taken_at": "2026-03-12T18:41:32Z"
    },
    "reviewer": {
        "actor_type": "agent_autonomous",
        "agent_identity": "loan_pd_v3-sa@bank.iam"
    },
    "outcome": {
        "outcome_type": "repaid_on_time",
        "outcome_value": "closed_clean",
        "outcome_date": "2026-04-12",
        "observed": true
    },

    "composed_at": "2026-03-12T18:42:01Z",
    "composition_seconds": 0.31,
    "lineage_complete": true,
    "row_hash": "sha256:c7d3...",
    "retention_until": "2033-03-12T18:41:32Z"
}
```

OpenAPI spec lives at `apps/api/openapi.yaml` and is the source of truth for both the CLI and the UI clients.
