# Architecture — DriftSentinel

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO and your platform engineering lead on day one.

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. Every BFSI shop is on either AWS, GCP, or Azure (or two of three). I'll show the GCP flavor as primary because it aligns with the *Building secure multi-agent systems on Google Cloud* reference architecture this portfolio cites elsewhere; AWS and Azure equivalents are called out inline.

---

## 1. Logical architecture

Six components. Each is independently deployable and independently scalable.

| Component | Responsibility | Language / framework | Stateful? |
| --- | --- | --- | --- |
| `drift-sentinel-api` | REST + gRPC API. Auth, RBAC, request routing, evidence-bundle assembly. | Python 3.11 + FastAPI + Pydantic v2 | No |
| `drift-sentinel-worker` | Async drift compute (PSI/KS, segment slicer, lineage correlation). Triggered by Airflow / Cloud Composer / Step Functions. | Python on Spark (PySpark) for heavy aggs; pandas/numpy for the diagnosis logic | No |
| `drift-sentinel-ui` | Validator workbench, fleet health view, evidence-bundle editor. Embeds in the existing MRM workbench (Archer / ServiceNow GRC). | React 19 + Next.js 15 (App Router) + TypeScript + Tailwind | No |
| `drift-sentinel-cli` | Probe runner, replay, ad-hoc operator commands. | Python + Click | No |
| `drift-sentinel-events` | Vendor-snapshot diff job + alerting fan-out. Long-lived consumer on the model-output event spine. | Python + Faust (Kafka) or Cloud Functions (Pub/Sub) | No (commits offsets) |
| `drift-sentinel-scheduler` | Cron + DAG runner for nightly PSI sweeps, weekly reports, monthly retraining-recommendation refresh. | Airflow 2.9 / Cloud Composer / MWAA | Stateful (DAG runs) |

All six are stateless except the scheduler. State lives in the data layer (next section). Stateless components scale horizontally; the scheduler is a single-leader with a cold standby.

**Repo structure** (monorepo via Bazel or Pants for the bank shop; or pnpm workspaces if the org is JS-comfortable):

```
drift-sentinel/
├── apps/
│   ├── api/           # FastAPI service
│   ├── worker/        # Spark + pandas pipeline
│   ├── ui/            # Next.js app
│   ├── cli/           # Click CLI
│   ├── events/        # Kafka/Pub/Sub consumer
│   └── scheduler/     # Airflow DAGs
├── packages/
│   ├── domain/        # Shared TypeScript + Python domain models (codegen from a single proto)
│   ├── auth/          # Shared SSO/OIDC libs
│   └── telemetry/     # OpenTelemetry helpers
├── infra/
│   ├── terraform/     # Multi-cloud IaC (gcp, aws, azure)
│   ├── kubernetes/    # Helm charts + Kustomize overlays
│   └── policies/      # OPA bundles, IAM templates, network policies
├── docs/
│   ├── ARCHITECTURE.md
│   ├── runbooks/
│   └── api/           # OpenAPI spec
└── tests/
    ├── unit/
    ├── integration/
    └── load/          # k6 / locust
```

---

## 2. Physical / deployment architecture

### Runtime

**Primary on GCP (matches the Google Cloud reference architecture):**

| Component | Runtime | Why |
| --- | --- | --- |
| `api` | Cloud Run (managed) | Stateless HTTP, autoscale 0-N, request-based billing |
| `worker` | Dataproc Serverless (Spark) | Bursty drift compute; pay-per-job |
| `ui` | Cloud Run | Static + SSR Next.js |
| `cli` | Local + Cloud Build for CI runs | Operator tool, not a service |
| `events` | Cloud Functions (gen 2) on Pub/Sub | Event-driven, autoscaling |
| `scheduler` | Cloud Composer 3 (managed Airflow) | Existing skill set in most BFSI ops teams |

**AWS equivalent:** ECS Fargate or EKS for `api`/`ui`; EMR Serverless for `worker`; Lambda + EventBridge for `events`; MWAA for `scheduler`.

**Azure equivalent:** Container Apps for `api`/`ui`; Synapse Spark Pool for `worker`; Functions + Event Grid for `events`; Data Factory or Airflow on AKS for `scheduler`.

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
[Cloud Run / ECS Fargate ─ api, ui]   ← public subnet, no direct DB access
   │
   ▼ (Service Mesh: mTLS, Istio or Cloud Service Mesh)
   │
[Private subnet ─ worker, events, scheduler]
   │
   ├──► [PostgreSQL — Cloud SQL / RDS] (private endpoint only)
   ├──► [ClickHouse — managed via Aiven / Altinity, or self-hosted] (private endpoint)
   ├──► [Snowflake / Databricks] (private connectivity: PrivateLink / Private Service Connect)
   └──► [Redis — Memorystore / ElastiCache] (private endpoint)

Egress to vendor APIs (Anthropic, Azure OpenAI, Bedrock, etc.):
   [Secure Web Proxy / Squid] ─ allow-list of vendor URLs only
   [VPC Service Controls / Network Firewall] ─ data exfiltration prevention
```

### Region & DR

- **Primary:** US-East (us-east1 GCP / us-east-1 AWS / East US Azure)
- **DR:** US-West (us-west1 / us-west-2 / West US 2). Active-passive. RTO 4h, RPO 15min for Tier-1 fleet metadata.
- **EU instance:** Frankfurt (europe-west3 / eu-central-1 / Germany West Central). Required for GDPR — feature distributions of EU customers cannot egress region.
- **India instance:** Mumbai (asia-south1 / ap-south-1 / Central India). Required for RBI data localization on Indian retail arms.
- Each regional instance has its own database, its own KMS key ring, its own Identity-Aware Proxy. No cross-region database replication — each is sovereign.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** (Cloud SQL / RDS) | Model metadata, drift events, recommendations, evidence bundles, attestations, validator activity, audit log | Relational integrity, joins, mature transactions, cheap at this scale. Bank ops teams know it. |
| **ClickHouse** (Aiven / Altinity managed, or Bytebase OSS) | Daily/hourly drift-signal time-series (PSI, KS, segment-level distributions). High-cardinality, append-only, queried by date range. | 10-50x cheaper than RDS for time-series at this volume. Sub-second p95 on the dashboard queries that drive the Streamlit prototype. |
| **Snowflake / Databricks** (read-only, no copy) | Inference logs, feature snapshots — owned by the existing data warehouse team | Already exists at every Tier-1 BFSI shop. We don't introduce a third lake. |
| **Redis** (Memorystore / ElastiCache) | Session cache (UI), idempotency keys (recommendation engine), rate-limiting counters | TTL-based eviction handles cleanup; multi-AZ for high availability |
| **GCS / S3 / Blob Storage** (with Object Lock) | Immutable evidence bundles (PDF + JSON), audit log archive, model registry artifacts referenced by URI | Object Lock = WORM (write-once-read-many) for SR 11-7 7-year retention |

### PostgreSQL schema (the consequential tables)

```sql
-- Model metadata (read-replicated from the existing model registry where possible)
CREATE TABLE models (
    model_id            TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    family              TEXT NOT NULL,        -- credit / fraud / aml / genai
    tier                SMALLINT NOT NULL,
    vendor              TEXT NOT NULL,
    owner_team          TEXT NOT NULL,
    snapshot_id         TEXT NOT NULL,         -- vendor model version pin
    deployed_at         TIMESTAMPTZ NOT NULL,
    last_attested_at    TIMESTAMPTZ,
    last_attested_by    TEXT,                  -- validator user_id
    classification_lvl  SMALLINT NOT NULL,     -- data classification (PCI/PII/internal/public)
    region              TEXT NOT NULL,         -- us-east, us-west, eu, india
    metadata            JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_models_tier ON models (tier);
CREATE INDEX idx_models_family_tier ON models (family, tier);

-- Drift events
CREATE TABLE drift_events (
    event_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id            TEXT NOT NULL REFERENCES models(model_id),
    detected_at         TIMESTAMPTZ NOT NULL,
    feature             TEXT NOT NULL,
    psi                 NUMERIC(8,4) NOT NULL,
    ks                  NUMERIC(8,4),
    severity            TEXT NOT NULL,         -- GREEN / YELLOW / RED
    detected_by         TEXT NOT NULL,         -- basic_psi / drift_sentinel / proxy_metric
    diagnosis           JSONB,                 -- driver, segment, lineage, root_cause
    recommendation      TEXT,                  -- RETAIN / SHADOW / RETRAIN / ROLLBACK / WATCH
    risk_envelope       JSONB,
    bundle_id           UUID REFERENCES evidence_bundles(bundle_id),
    status              TEXT NOT NULL,         -- open / triaged / attested / closed
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_drift_events_model_detected ON drift_events (model_id, detected_at DESC);
CREATE INDEX idx_drift_events_status ON drift_events (status);

-- Evidence bundles (the artifact MRM attests against)
CREATE TABLE evidence_bundles (
    bundle_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drift_event_id      UUID NOT NULL,
    assembled_at        TIMESTAMPTZ NOT NULL,
    assembly_seconds    NUMERIC(6,2) NOT NULL,
    storage_uri         TEXT NOT NULL,         -- gs://bucket/path/bundle.json
    pdf_uri             TEXT,                  -- gs://bucket/path/bundle.pdf
    sha256              TEXT NOT NULL,         -- integrity check
    edited_by           TEXT,                  -- validator user_id (if human-edited)
    edited_at           TIMESTAMPTZ,
    edit_reason         TEXT,
    attested_by         TEXT,
    attested_at         TIMESTAMPTZ,
    attestation_decision TEXT                  -- approve / reject / request_changes
);

-- Attestations (immutable append-only — no UPDATE, only INSERT)
CREATE TABLE attestations (
    attestation_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bundle_id           UUID NOT NULL REFERENCES evidence_bundles(bundle_id),
    validator_id        TEXT NOT NULL,
    decision            TEXT NOT NULL,
    reasoning           TEXT NOT NULL,
    signed_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signature           TEXT NOT NULL,         -- digital signature, validator's cert
    cert_thumbprint     TEXT NOT NULL
);

-- Vendor snapshot history (the feature that catches GenAI silent updates)
CREATE TABLE vendor_snapshots (
    snapshot_id         TEXT PRIMARY KEY,
    vendor              TEXT NOT NULL,         -- anthropic / azure_openai / bedrock / mistral
    base_model          TEXT NOT NULL,         -- claude-sonnet-4 / gpt-4o / etc.
    first_observed_at   TIMESTAMPTZ NOT NULL,
    observed_in_models  TEXT[],                -- which fleet models use this snapshot
    announcement_status TEXT,                  -- announced / silent_minor_update / acknowledged_post_hoc
    diff_severity       TEXT,                  -- vs prior snapshot: low / med / high
    notes               TEXT
);

-- Audit log (immutable, append-only, partitioned by month)
CREATE TABLE audit_log (
    audit_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id            TEXT NOT NULL,
    actor_type          TEXT NOT NULL,         -- user / agent / service_account
    action              TEXT NOT NULL,
    resource_type       TEXT NOT NULL,
    resource_id         TEXT NOT NULL,
    request_id          TEXT NOT NULL,
    source_ip           INET,
    user_agent          TEXT,
    payload             JSONB,
    result              TEXT NOT NULL          -- success / failure / forbidden
) PARTITION BY RANGE (occurred_at);
```

### ClickHouse schema (the time-series tables)

```sql
CREATE TABLE drift_signals (
    model_id          LowCardinality(String),
    feature           LowCardinality(String),
    observed_at       DateTime64(3, 'UTC'),
    psi               Float32,
    ks                Float32,
    n_reference       UInt32,
    n_current         UInt32,
    segment           LowCardinality(String) DEFAULT '',
    region            LowCardinality(String)
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/drift_signals', '{replica}')
PARTITION BY toYYYYMM(observed_at)
ORDER BY (model_id, feature, observed_at)
TTL observed_at + INTERVAL 730 DAY DELETE;  -- 2-year retention; archive to GCS after
```

### Retention & data classification

| Data class | Retention | Storage | Justification |
| --- | --- | --- | --- |
| Model metadata | indefinite (while deployed) | PostgreSQL | Operational |
| Drift events + bundles | 7 years | PostgreSQL hot for 90d, archive to GCS Object Lock | SR 11-7 |
| Attestations | 7 years | PostgreSQL append-only + GCS Object Lock | SR 11-7 + audit |
| Audit log | 7 years | PostgreSQL partitioned + GCS Object Lock | Audit |
| Drift time-series | 2 years hot | ClickHouse | Operational; aggregate longer history archived |
| Inference logs | (existing warehouse retention) | Snowflake / Databricks | Read-only access; we don't own retention |
| Validator session data | 8 hours | Redis | Operational |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with envelope encryption. Customer-Managed Encryption Keys (CMEK / CMK) in Cloud KMS / AWS KMS / Azure Key Vault. Bank's key rotation policy applies (typically 90 days). Same key ring per region — keys never cross region boundary.
- **In transit.** TLS 1.3 minimum on north-south. mTLS on east-west via service mesh (Istio / Cloud Service Mesh / AWS App Mesh). Outbound to vendor APIs over TLS 1.3 with cert-pinning where available.
- **Field-level.** Any PII feature in inference logs is hashed (SHA-256 with KMS-managed pepper) before drift compute writes to `drift_signals`. Raw PII never touches DriftSentinel storage. The Data Vault Agent pattern from Google's Warranty Claim System reference applies here directly.
- **Database-level.** Cloud SQL Transparent Data Encryption (TDE) on PostgreSQL; ClickHouse encrypted-EBS / encrypted-disk; Snowflake native encryption; Redis encryption-at-rest enabled.

### Secrets management

- **Primary store.** HashiCorp Vault (most BFSI shops already run it) or Cloud Secret Manager / AWS Secrets Manager / Azure Key Vault. No long-lived static credentials.
- **Application secrets** (DB passwords, vendor API keys for Anthropic/Azure OpenAI/Bedrock): fetched at boot via Workload Identity Federation. No env-var secrets in container manifests. Rotation: 90 days with zero-downtime via dual-credential rolling.
- **Service account keys.** None. Workload Identity (GCP) / IAM Roles for Service Accounts (AWS IRSA) / Managed Identity (Azure). Aligns with Google's *Building secure multi-agent systems* guidance to never use long-lived service account keys.
- **Code-signing certs.** HSM-backed (Cloud HSM / CloudHSM / Azure Dedicated HSM) for Binary Authorization signing of container images.

### Identity provider & user management

- **IdP.** Whatever the bank already runs — typically Okta, Microsoft Entra ID (Azure AD), or Ping Identity. SAML 2.0 + OIDC. We don't run our own.
- **MFA.** Required by bank policy. Enforced at the IdP, not the app. Passkey / FIDO2 preferred; TOTP fallback.
- **Sessions.** OIDC ID token + signed session cookie (HttpOnly, Secure, SameSite=Strict). 8-hour absolute expiry, 30-minute idle timeout. Refresh tokens 7 days, single-use, rotation on every refresh.
- **Session storage.** Redis with PII-redacted backups for offline forensics.
- **Service-to-service identity.** SPIFFE IDs (matches Google Cloud Agent Identity pattern). Each component has a unique workload identity. mTLS enforces identity at every hop.

### RBAC matrix

Five roles, mapped to bank roles, scoped per region:

| Role | Permissions | Maps to (bank role) |
| --- | --- | --- |
| `ds:viewer` | Read fleet view, read drift events | Audit, exec, read-only stakeholders |
| `ds:validator` | Viewer + edit evidence bundles + attest | Line-2 model validators (MRM team) |
| `ds:ops` | Validator + trigger ROLLBACK on Tier-2/3 + threshold tuning per use-case | Line-1 ML Ops Lead |
| `ds:cro` | Viewer + audit-trail export + cross-region read | CRO, Head of MRM |
| `ds:admin` | Full config, role management, integration config | Platform engineering lead |

Authorization implemented via Open Policy Agent (OPA) + Rego policies. Every API call evaluates policy at the gateway. Decisions logged to `audit_log`.

### Network controls

- **Perimeter.** VPC Service Controls (GCP) / AWS PrivateLink + Network Firewall / Azure Private Endpoints. Egress to public internet only via Secure Web Proxy with allow-list (Anthropic, Azure OpenAI, Bedrock, vendor URLs, NTP).
- **Lateral.** Cloud Next-Gen Firewall / AWS Security Groups + Network ACLs / Azure NSGs. Layer-7 inspection on the service mesh.
- **Ingress.** Cloud Armor / AWS WAF / Azure WAF with the OWASP Core Rule Set + custom rules for the API surface (rate limit per user, anomaly detection on request patterns).
- **Zero-trust.** All inter-service calls authenticated via SPIFFE mTLS. No "trusted internal network" assumption.

### Threat model — what we explicitly defend against

| Threat | Mitigation |
| --- | --- |
| Compromised API token | Short-lived tokens, mTLS service-to-service, IdP-side revocation propagates ≤ 5 min |
| Insider — validator pulls all customer data | Field-level encryption + hashed customer identifiers + RBAC limits validator to drift-events scope, not raw inference logs |
| Compromised drift event payload (poisoning) | All writes signed by component identity; tamper detection via SHA-256 on bundles |
| Vendor model silent update | Snapshot pin tracked as model attribute; daily diff job surfaces the change as an audit event (this is the v0.5 shipped in CHANGELOG) |
| Database exfiltration via SQL injection | Parameterized queries everywhere; ORM-only (SQLAlchemy + Pydantic) at the API boundary; Cloud Armor WAF rule set |
| Egress data exfiltration | VPC Service Controls + Secure Web Proxy allow-list |
| Privileged escalation via misconfigured IAM | OPA policy review on every PR; quarterly access review with the head of MRM and the bank's CISO |

---

## 4a. APIs consumed and exposed

The systems doc most people skip on. DriftSentinel is a glue product — it talks to a lot of things over the wire. Every external dependency is listed here with the protocol, the auth model, and what we do when it goes down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol | Auth | What we call | Failure mode |
| --- | --- | --- | --- | --- |
| **Foundation model — Anthropic Claude** | REST + JSON, `https://api.anthropic.com` | API key from Vault, rotated 90 days | LLM-as-judge for GenAI proxy metrics; batched, off the request path | Circuit-breaker → fall back to Azure OpenAI gpt-4o judge; alert P3 |
| **Foundation model — Azure OpenAI** | REST + JSON, regional endpoint | Managed Identity (no key) | Secondary judge for cross-vendor reliability check | Degrades to Anthropic-only judging; reliability flag goes amber |
| **Foundation model — AWS Bedrock** | AWS SigV4 over HTTPS | IAM Role (IRSA) | Tertiary judge for vendor-diversity coverage; on-prem-equivalent fallback path | Optional path; failure does not affect primary flow |
| **MLflow Model Registry** | REST `/api/2.0/mlflow/*` | OIDC bearer (the bank's IdP) | Read-only: model metadata, tier, owner, version | Cached for 60 min; if MLflow is down >60 min, drift compute pauses for affected models, alert P2 |
| **AWS SageMaker Model Registry** | AWS SigV4 over HTTPS | IRSA, scoped to `sagemaker:Describe*` | Same as MLflow when the bank is AWS-native | Same 60-min cache, same fallback |
| **Vertex AI Model Registry** | gRPC + REST | Workload Identity | Same role for GCP-native banks | Same 60-min cache |
| **Tecton Feature Store** | REST + gRPC `/v1/...` | OIDC service token | Read-only: feature snapshots for the reference and current windows | Snapshot served from a 24-hour S3 archive if Tecton is down; flagged in evidence bundle |
| **Databricks Feature Store** | REST `/api/2.0/feature-store/*` | OAuth M2M (machine-to-machine) | Same role | Same 24h archive fallback |
| **Snowflake** | JDBC / Python connector via private link | Key-pair auth (RSA), rotated 30 days | Read-only on the inference-log lake | Read-replica failover to secondary region |
| **Identity provider — Okta / Entra ID / Ping** | SAML 2.0 + OIDC | mTLS to the IdP signing endpoint | User authentication, role lookup, MFA enforcement | Cached SAML assertion for 8 hours; if IdP is down, sessions in flight continue, no new logins |
| **HashiCorp Vault** | REST `/v1/*` over mTLS | Kubernetes auth method (SPIFFE-bound) | Secrets fetch at boot + on rotation events | Init container retries 5x with backoff; fail-fast on no secrets |
| **Cloud KMS / AWS KMS / Azure Key Vault** | Cloud SDK (gRPC under the hood) | Workload Identity | Encrypt / decrypt envelope keys for at-rest data | Cached for 5 min; longer outage causes degraded write performance |
| **Datadog / Cloud Logging / CloudWatch** | HTTPS + DD-API-KEY (or native SDK) | API key from Vault | Telemetry sink (RED metrics, traces, logs) | Local buffering up to 30 min; spillover dropped with metric `dropped_spans_total` |
| **PagerDuty** | REST `/v2/incidents` | API key from Vault | Severity-1/2 alert routing | Slack-webhook fallback; manual paging if both fail |
| **Slack** | Incoming webhook + Block Kit | Webhook URL from Vault | P3 alerts, daily digest, validator-channel notifications | Email digest as fallback |
| **Archer / ServiceNow GRC / MetricStream** | REST (vendor-specific) | OIDC + per-vendor service principal | Write evidence-bundle metadata + attestation status into the bank's GRC tool | Local audit trail continues; GRC sync resumes when the dependency is back |
| **Vendor model snapshot manifests** | REST (Anthropic public docs feed) + custom polling against `messages.create` response headers | API key | Daily diff job to detect silent vendor updates | If the manifest endpoint is down, snapshot diff continues from last known state; an unannounced update may still be flagged via response-header drift |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol | Auth | Consumers |
| --- | --- | --- | --- |
| `drift-sentinel-api` REST | OpenAPI 3.1 over HTTPS | OIDC bearer, role-checked via OPA | UI, CLI, MRM workbench iframes, GRC tool integrations |
| `drift-sentinel-api` gRPC (internal only) | gRPC + protobuf | mTLS via service mesh (SPIFFE) | Worker, scheduler, events |
| **Webhooks (outbound)** | HTTPS POST + HMAC-SHA256 signature | Pre-shared HMAC secret per consumer | Bank's incident management, Compliance dashboard |
| **MCP server (optional, GCP-native deployments)** | Anthropic Model Context Protocol | OIDC + Agent Identity | Allows the bank's agents to query drift status as a tool — interlocks with [Project 04 — AgentWatch](../05-agentwatch-agent-observability/) |
| **OpenAPI spec endpoint** | `/openapi.json` | Public (no auth) | Discovery for the CLI, UI, integration tools |

### API-design opinions (the choices a reviewer will ask about)

- **REST + OpenAPI is the surface, not GraphQL.** GraphQL is overkill for the surface area we expose. OpenAPI lets us auto-generate the CLI client, the TypeScript SDK for the UI, and the bank's integration stubs. One spec, three consumers.
- **gRPC is internal only.** External callers get REST. Internal east-west uses gRPC for the latency budget on the worker → API path.
- **Webhooks are signed, not just authenticated.** HMAC-SHA256 with a per-consumer rotating secret. A leaked URL doesn't grant write access.
- **No customer PII in URLs ever.** Customer IDs are SHA-256 hashes; raw IDs only ever appear in request bodies under TLS.
- **Idempotency keys on all POSTs that trigger compute.** UUID v4 in the `Idempotency-Key` header; Redis-backed dedupe with 24-hour TTL.
- **Rate limits exposed as headers.** `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`. Validators get higher limits than viewers.
- **Versioning via URL path** (`/v1/`, `/v2/`). Deprecation headers (`Sunset`) on the 6-month deprecation window.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs | Cloud Logging + Datadog / CloudWatch / Azure Monitor | Existing SOC pane |
| Distributed traces | Cloud Trace + OpenTelemetry → Datadog APM | Chain-of-thought when applicable |
| Metrics | Prometheus + Grafana (or Datadog metrics) | RED-method dashboards per service |
| LLM-specific traces | Langfuse (self-hosted) for the GenAI portion of the fleet only | Not used outside the GenAI proxy-metric path |
| Drift-event high-cardinality store | ClickHouse (above) | Datadog rates would bankrupt this volume |
| Audit log | PostgreSQL `audit_log` + GCS Object Lock | SR 11-7 retention |

### Alerting

| Severity | Channel | SLO |
| --- | --- | --- |
| P1 (Tier-1 model RED + recommendation = ROLLBACK) | PagerDuty primary + secondary, Slack #ml-ops-incident, MRM lead text | Acknowledge ≤ 5 min |
| P2 (Tier-1 RED, recommendation ≠ ROLLBACK) | PagerDuty (lower urgency), Slack | Acknowledge ≤ 30 min |
| P3 (Tier-2 RED, all YELLOWs) | Slack only | Triaged in next business day |
| P4 (informational) | Daily digest email | None |

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to GCS / S3. Daily snapshots, 35-day retention. Point-in-time recovery within retention window.
- **ClickHouse.** Weekly backup to GCS / S3. ReplicatedMergeTree gives HA within region.
- **Object stores.** Object Lock + versioning + cross-region replication for evidence bundles and audit log.
- **DR drill cadence.** Quarterly. Full failover to US-West, validate RTO 4h / RPO 15min, fail back. Documented runbook in `docs/runbooks/dr-failover.md`.

### Runbooks (one paragraph each in the repo)

- `dr-failover.md` — full region failover
- `vendor-silent-update.md` — when the daily diff job flags a new snapshot
- `validator-onboarding.md` — provision a new line-2 validator with cert + role
- `false-positive-storm.md` — when alert volume spikes (the v0.2 lesson learned from CHANGELOG, codified)
- `audit-evidence-export.md` — pulling a complete decision lineage for an OCC exam

---

## 6. Compliance posture

| Framework | Posture |
| --- | --- |
| **SOC 2 Type II** | All six components in scope. Annual external audit. |
| **PCI-DSS** | In scope only when the underlying model touches cardholder data. DriftSentinel itself doesn't process card data; it processes feature distributions. PCI scope minimization via field-level encryption and tokenization at the source. |
| **GLBA** | Customer financial data handled with field-level encryption + access controls + audit trail. Right-to-be-forgotten cascades to drift events via customer-ID hash deletion. |
| **SR 11-7** | This is the existence-proof regulation. DriftSentinel is the implementation surface for "ongoing monitoring" the SR letter has required since 2011. PRD references the specific paragraphs. |
| **NIST AI RMF + EU AI Act Article 12** | Decision-grain lineage maintained for the recommendation engine. Interlocks with Project 08 (LineageLog) for the full lineage surface. |
| **GDPR** | EU instance enforces data residency. Right-to-erasure handled via customer-hash deletion cascade. DPO sign-off documented. |
| **India RBI data localization** | Indian retail-arm fleet runs on the India regional instance only. No cross-border replication. |
| **OCC / Fed / CFPB exam readiness** | Audit-pack export builds in <12 minutes per decision. Continuous, not annual. |

---

## 7. What's deliberately not here

- **A custom model registry.** We read from MLflow / SageMaker Model Registry / Vertex AI Model Registry. DriftSentinel is not in the business of replacing the model registry the bank already runs.
- **A custom feature store.** Same logic. We consume from Tecton / Databricks Feature Store / Vertex AI Feature Store.
- **A retraining engine.** DriftSentinel recommends. The bank's existing MLOps platform executes the retraining. We pass a candidate-spec JSON that the platform consumes.
- **A consumer-facing surface.** This is an internal operational tool for line-1 / line-2 / CRO. End customers never see it.
- **A standalone authentication system.** We integrate with the bank's IdP. We don't run our own.

That last list is the discipline. Every internal-build I've seen die has died on scope creep into one of those five.

---

## Appendix — sample API contract

```python
# POST /v1/drift-events
# Auth: OIDC bearer token; role: ds:ops or higher
# Request:
{
    "model_id": "credit_pd_v3",
    "feature": "feature_dti",
    "psi": 0.42,
    "ks": 0.31,
    "detected_at": "2026-03-04T08:14:00Z",
    "detected_by": "drift_sentinel"
}
# Response 201:
{
    "event_id": "ee5f8c1a-...",
    "diagnosis": {
        "driver": "feature_dti",
        "segment": "subprime FICO<660",
        "segment_psi": 0.71,
        "lineage": "no upstream pipeline change in 48h",
        "root_cause_hypothesis": "exogenous: rate-cycle DTI shift"
    },
    "recommendation": "SHADOW",
    "risk_envelope": {
        "expected_default_delta_if_retain": "+0.4%",
        "expected_default_delta_if_shadow": "+0.1%"
    },
    "bundle": {
        "bundle_id": "...",
        "storage_uri": "gs://drift-sentinel-bundles/.../bundle.json",
        "assembly_seconds": 3.2
    },
    "status": "open"
}
```

OpenAPI spec lives at `apps/api/openapi.yaml` and is the source of truth for both the CLI and the UI clients.
