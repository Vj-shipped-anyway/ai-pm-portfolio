# Architecture — EvalForge

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network controls, operational runbooks. What you'd hand to your CISO and your platform engineering lead on day one.

EvalForge sits between the AI Platform team's prompt PR and the production deploy pipeline. It is a pre-deploy CI gate, not an observability tool — that distinction drives every architecture choice below.

---

## 1. Logical architecture

Six components. Each is independently deployable and independently scalable.

| Component | Responsibility | Language / framework | Stateful? |
| --- | --- | --- | --- |
| `evalforge-api` | REST + gRPC API. Auth, RBAC, request routing, evidence-bundle assembly. | Python 3.11 + FastAPI + Pydantic v2 | No |
| `evalforge-runner` | Probe execution: sends each probe to the deployed assistant, captures the response, persists for judging. | Python on K8s Jobs (one job per eval run, fan-out per probe) | No |
| `evalforge-judge` | Judge orchestrator: fan-out to Claude + GPT-4o + in-VPC Llama; rubric scoring; kappa computation. | Python + asyncio | No |
| `evalforge-ui` | L2 Trust-and-Safety authoring UI (rubrics, calibration anchors, override-audit viewer). | React 19 + Next.js 15 + TypeScript + Tailwind | No |
| `evalforge-gate` | GitHub Action / Argo CD pre-deploy hook. Reads the run verdict, posts a PR check, fails the merge if FAIL. | TypeScript Action + Go binary fallback | No |
| `evalforge-scheduler` | Cron for nightly regression runs against the production assistant snapshot; weekly judge re-anchor. | Argo Workflows / Cloud Composer | Stateful (workflow runs) |

All six are stateless except the scheduler. State lives in the data layer (next section).

**Repo structure** (monorepo via pnpm workspaces or Bazel for a bank shop):

```
evalforge/
├── apps/
│   ├── api/           # FastAPI service
│   ├── runner/        # K8s Jobs harness
│   ├── judge/         # Judge fan-out + kappa
│   ├── ui/            # Next.js authoring UI
│   ├── gate/          # GitHub Action + Argo CD hook
│   └── scheduler/     # Argo Workflows
├── packages/
│   ├── domain/        # Shared TypeScript + Python domain models
│   ├── auth/          # Shared SSO/OIDC libs
│   └── telemetry/     # OpenTelemetry helpers
├── infra/
│   ├── terraform/     # Multi-cloud IaC
│   ├── kubernetes/    # Helm charts + Kustomize overlays
│   └── policies/      # OPA bundles, IAM templates
├── docs/
│   ├── ARCHITECTURE.md
│   ├── runbooks/
│   └── api/           # OpenAPI spec
└── tests/
```

---

## 2. Physical / deployment architecture

### Runtime

**Primary on GCP (matches the Google Cloud reference architecture):**

| Component | Runtime | Why |
| --- | --- | --- |
| `api` | Cloud Run (managed) | Stateless HTTP, autoscale 0-N |
| `runner` | GKE (K8s Jobs) | Parallel probe execution, per-run isolation |
| `judge` | Cloud Run + Cloud Functions for fan-out | Bursty, event-driven |
| `ui` | Cloud Run | Static + SSR Next.js |
| `gate` | GitHub Actions runner + self-hosted Argo CD plugin | Customer's CI/CD environment |
| `scheduler` | Cloud Composer 3 (Argo on Composer) | Existing skill set |

**AWS equivalent:** ECS Fargate or EKS for `api`/`ui`; Batch + EKS for `runner`; Lambda for `judge` fan-out; MWAA for `scheduler`.

**Azure equivalent:** Container Apps for `api`/`ui`; AKS for `runner`; Functions for `judge`; Data Factory for `scheduler`.

### Network topology

```
Bank's GitHub / GitLab
        │
        ▼ (HMAC-signed webhook)
[evalforge-gate] - posts PR check, calls API
        │
        ▼
[Cloud Armor / AWS WAF / Azure Front Door WAF]
        │
        ▼
[Identity-Aware Proxy / ALB OIDC] - SSO + MFA
        │
        ▼
[Cloud Run / ECS Fargate - api, ui]   ← public subnet, no direct DB access
        │
        ▼ (Service Mesh: mTLS)
        │
[Private subnet - runner, judge, scheduler]
        │
        ├──► [PostgreSQL - Cloud SQL / RDS] (private endpoint only)
        ├──► [ClickHouse - managed via Aiven / Altinity] (private endpoint)
        ├──► [Snowflake / Databricks] (private connectivity)
        └──► [Redis - Memorystore / ElastiCache] (private endpoint)

Egress to vendor judges (Anthropic, Azure OpenAI):
   [Secure Web Proxy / Squid] - allow-list of vendor URLs only
   [VPC Service Controls] - data exfiltration prevention
   In-VPC Llama judge: no egress needed
```

### Region & DR

- **Primary:** US-East. **DR:** US-West, active-passive, RTO 4h, RPO 15min.
- **EU instance:** Frankfurt (GDPR — probe responses cannot egress region).
- **India instance:** Mumbai (RBI data localization).

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | Probes (with version SHA), rubrics, eval runs, judge overrides, evidence bundles, audit log | Relational integrity; mature transactions. |
| **ClickHouse** | Per-probe per-judge score time-series; high-cardinality kappa computation source data | 10-50x cheaper than RDS at this volume; sub-second p95 on the dashboard queries. |
| **Snowflake / Databricks** (read-only) | Historical scoring data for the rubric-calibration model; cohort analysis | Already exists at every Tier-1 BFSI shop. |
| **Redis** | Session cache, idempotency keys, rate-limiting counters | TTL-based eviction. |
| **GCS / S3 / Blob Storage** (Object Lock) | Immutable evidence bundles, audit log archive | WORM for 7-year retention. |

### PostgreSQL schema (the consequential tables)

```sql
-- Probes — versioned, content-addressed
CREATE TABLE probes (
    probe_id            TEXT NOT NULL,
    version             TEXT NOT NULL,        -- probes-v0.7, probes-v1.0, etc.
    sha256              TEXT NOT NULL,        -- content hash, tamper detection
    question            TEXT NOT NULL,
    expected_behavior   TEXT NOT NULL,
    deficiency_class    TEXT NOT NULL,
    slice               TEXT NOT NULL,
    severity            TEXT NOT NULL,         -- high / med / low
    owning_role         TEXT NOT NULL,         -- l1_product / l2_trust_safety
    created_by          TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retired_at          TIMESTAMPTZ,           -- never deleted, only retired
    PRIMARY KEY (probe_id, version)
);
CREATE INDEX idx_probes_version ON probes (version);
CREATE INDEX idx_probes_deficiency ON probes (deficiency_class);

-- Rubrics — 12 criteria with calibration anchors
CREATE TABLE rubrics (
    rubric_id           TEXT NOT NULL,
    version             TEXT NOT NULL,
    criterion           TEXT NOT NULL,
    scale_low           SMALLINT NOT NULL,
    scale_high          SMALLINT NOT NULL,
    calibration_anchors JSONB NOT NULL,        -- {"1": "...", "3": "...", "5": "..."}
    deficiency_class    TEXT NOT NULL,
    owning_role         TEXT NOT NULL,
    sha256              TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retired_at          TIMESTAMPTZ,
    PRIMARY KEY (rubric_id, version)
);

-- Eval runs — one row per nightly or pre-deploy run
CREATE TABLE eval_runs (
    eval_run_id         TEXT PRIMARY KEY,
    run_date            TIMESTAMPTZ NOT NULL,
    triggered_by        TEXT NOT NULL,         -- ci_pr / nightly_cron / manual
    model_version       TEXT NOT NULL,
    probe_set_version   TEXT NOT NULL,
    n_probes            INTEGER NOT NULL,
    pass_rate           NUMERIC(6,4) NOT NULL,
    judge_id            TEXT NOT NULL,
    judge_snapshot      TEXT NOT NULL,
    inter_judge_kappa   NUMERIC(6,4),
    ci_gate_verdict     TEXT NOT NULL,         -- PASS / FAIL / REVIEW
    regression_flagged  TEXT NOT NULL,         -- yes / no / partial
    human_override_count INTEGER NOT NULL DEFAULT 0,
    rolling_baseline    NUMERIC(6,4),
    notes               TEXT,
    bundle_id           UUID REFERENCES evidence_bundles(bundle_id)
);
CREATE INDEX idx_eval_runs_date ON eval_runs (run_date DESC);
CREATE INDEX idx_eval_runs_verdict ON eval_runs (ci_gate_verdict);

-- Judge overrides — every human-overrode-the-judge event
CREATE TABLE judge_overrides (
    override_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    eval_run_id         TEXT NOT NULL REFERENCES eval_runs(eval_run_id),
    probe_id            TEXT NOT NULL,
    rubric_id           TEXT NOT NULL,
    judge_score         SMALLINT NOT NULL,
    human_score         SMALLINT NOT NULL,
    reviewer_id         TEXT NOT NULL,
    override_reason     TEXT NOT NULL,
    deficiency_class    TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_overrides_run ON judge_overrides (eval_run_id);
CREATE INDEX idx_overrides_rubric ON judge_overrides (rubric_id);
CREATE INDEX idx_overrides_reviewer ON judge_overrides (reviewer_id);

-- Evidence bundles — the artifact L2 attests against
CREATE TABLE evidence_bundles (
    bundle_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    eval_run_id         TEXT NOT NULL REFERENCES eval_runs(eval_run_id),
    assembled_at        TIMESTAMPTZ NOT NULL,
    storage_uri         TEXT NOT NULL,         -- gs://bucket/path/bundle.json
    pdf_uri             TEXT,
    sha256              TEXT NOT NULL,
    routed_to           TEXT,                  -- L2 queue / L3 queue / archived
    attested_by         TEXT,
    attested_at         TIMESTAMPTZ
);

-- Audit log — append-only, partitioned by month
CREATE TABLE audit_log (
    audit_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id            TEXT NOT NULL,
    action              TEXT NOT NULL,
    resource_type       TEXT NOT NULL,
    resource_id         TEXT NOT NULL,
    payload             JSONB,
    result              TEXT NOT NULL
) PARTITION BY RANGE (occurred_at);
```

### ClickHouse schema (per-probe per-judge scores)

```sql
CREATE TABLE probe_scores (
    eval_run_id       LowCardinality(String),
    probe_id          LowCardinality(String),
    rubric_id         LowCardinality(String),
    judge_id          LowCardinality(String),
    judge_snapshot    LowCardinality(String),
    score             Float32,
    response_text     String,
    scored_at         DateTime64(3, 'UTC'),
    slice             LowCardinality(String),
    severity          LowCardinality(String)
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/probe_scores', '{replica}')
PARTITION BY toYYYYMM(scored_at)
ORDER BY (eval_run_id, probe_id, rubric_id, judge_id)
TTL scored_at + INTERVAL 730 DAY DELETE;  -- 2-year retention; archive to GCS after
```

### Retention & data classification

| Data class | Retention | Storage |
| --- | --- | --- |
| Probes + rubrics | indefinite | PostgreSQL |
| Eval runs + bundles | 7 years | PostgreSQL hot 90d, GCS Object Lock archive |
| Judge overrides | 7 years | PostgreSQL append-only + GCS Object Lock |
| Audit log | 7 years | Partitioned PostgreSQL + GCS Object Lock |
| Probe scores time-series | 2 years hot | ClickHouse |
| Probe response text | 90 days | ClickHouse, hashed for PII before write |
| Session data | 8 hours | Redis |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with envelope encryption. CMEK / CMK in Cloud KMS / AWS KMS / Azure Key Vault. Bank's key rotation policy applies (90 days).
- **In transit.** TLS 1.3 minimum north-south. mTLS east-west via service mesh.
- **Field-level.** Probe response text is hashed (SHA-256 with KMS-managed pepper) for any PII pattern before write to ClickHouse. Raw PII never persists.

### Secrets management

- **Primary store.** HashiCorp Vault or Cloud Secret Manager.
- **Vendor judge API keys** (Anthropic, Azure OpenAI): fetched at boot via Workload Identity Federation; rotated 90 days.
- **Service account keys.** None. Workload Identity / IRSA / Managed Identity only.

### Identity provider & user management

- **IdP.** Whatever the bank already runs — Okta, Microsoft Entra ID, or Ping.
- **MFA.** Required by bank policy.
- **Sessions.** OIDC ID token + signed session cookie; 8-hour absolute, 30-min idle.
- **Service-to-service identity.** SPIFFE IDs; mTLS enforces identity at every hop.

### RBAC matrix

| Role | Permissions | Maps to (bank role) |
| --- | --- | --- |
| `ef:viewer` | Read eval runs, read overrides | Audit, exec, read-only |
| `ef:engineer` | Viewer + trigger eval runs + view CI gate verdicts | L1 AI platform engineer |
| `ef:reviewer` | Engineer + override judge scores + edit rubric authoring drafts | L2 trust-and-safety reviewer |
| `ef:approver` | Reviewer + approve rubric versions + bypass CI gate (with audit log) | L2 trust-and-safety lead |
| `ef:admin` | Full config, role management, integration config | AI platform engineering lead |

Authorization implemented via Open Policy Agent (OPA) + Rego policies. Every API call evaluates policy at the gateway. Decisions logged to `audit_log`.

### Threat model — what we explicitly defend against

| Threat | Mitigation |
| --- | --- |
| Compromised CI gate bypass | Bypass requires `ef:approver` role + audit log entry + named reason |
| Insider — reviewer downgrades scores to ship | Override audit log; quarterly review of override patterns by L2 lead |
| Vendor judge silently updated | Snapshot pin tracked; daily diff job; cross-vendor kappa floor enforced |
| Probe set tampering | Content-addressed by SHA; tamper detection at read time |
| Customer PII in probe responses | Hash-on-write; raw response never persists; vendor-judge requests strip PII before egress |
| Egress data exfiltration | VPC Service Controls + Secure Web Proxy allow-list |

---

## 4a. APIs consumed and exposed

### APIs consumed (north-bound)

| External service | Protocol | Auth | What we call | Failure mode |
| --- | --- | --- | --- | --- |
| **Anthropic Claude** | REST + JSON | API key from Vault, rotated 90 days | Primary LLM-as-judge | Circuit-breaker → fall back to GPT-4o judge; alert P3 |
| **Azure OpenAI** | REST + JSON, regional endpoint | Managed Identity | Secondary judge | Degrades to primary-only; cross-vendor kappa flagged |
| **In-VPC Llama 3.1 8B** | gRPC to Triton on bank's GPU pool | mTLS | Tertiary judge (in-VPC for sensitive features) | Optional path; failure does not affect primary flow |
| **GitHub / GitLab** | REST + Webhook | OAuth App + HMAC webhook | PR check posting; webhook receipt | Local queue retries 5x; manual sync if both fail |
| **Argo CD** | gRPC + REST | mTLS | Pre-deploy hook | Block the deploy on hook failure (fail-safe) |
| **Identity provider** | SAML + OIDC | mTLS to signing endpoint | User auth, role lookup | Cached SAML assertion for 8 hours |
| **HashiCorp Vault** | REST over mTLS | Kubernetes auth | Secrets fetch | Init container retries; fail-fast on no secrets |
| **Datadog / Cloud Logging** | HTTPS + API key | Vault | Telemetry sink | Local buffering 30 min; spillover dropped |
| **PagerDuty** | REST | Vault | P1/P2 alert routing | Slack fallback |
| **Archer / ServiceNow GRC** | REST | OIDC + service principal | Evidence bundle metadata sync | Local audit trail continues |

### APIs we expose (south-bound)

| Surface | Protocol | Auth | Consumers |
| --- | --- | --- | --- |
| `evalforge-api` REST | OpenAPI 3.1 over HTTPS | OIDC bearer, OPA-checked | UI, CI gate, GRC integrations |
| `evalforge-api` gRPC (internal) | gRPC + protobuf | mTLS (SPIFFE) | Runner, judge, scheduler |
| **Webhooks (outbound)** | HTTPS POST + HMAC-SHA256 | Pre-shared HMAC secret per consumer | Bank's CI/CD, GRC tools |
| **MCP server** (optional) | Anthropic Model Context Protocol | OIDC + Agent Identity | Lets agents query eval status as a tool (Project 05 interlock) |

### API-design opinions

- **REST + OpenAPI is the external surface, gRPC is internal.** One OpenAPI spec drives the CLI client, the UI SDK, and the bank's integration stubs.
- **Webhooks are HMAC-signed.** A leaked URL doesn't grant write access.
- **No probe content in URLs.** Probe IDs only; full content in request bodies under TLS.
- **Idempotency keys on all POSTs** that trigger compute (UUID v4 header, Redis dedupe, 24h TTL).
- **Versioning via URL path** (`/v1/`, `/v2/`). 6-month deprecation window.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs | Cloud Logging + Datadog | Existing SOC pane |
| Distributed traces | OpenTelemetry → Datadog APM | End-to-end probe → judge → verdict chain |
| Metrics | Prometheus + Grafana | RED-method dashboards per service |
| LLM-specific traces | Langfuse (self-hosted) | Judge prompt traces |
| Per-probe scores | ClickHouse | High-cardinality |
| Audit log | PostgreSQL + GCS Object Lock | SR 11-7 retention |

### Alerting

| Severity | Channel | SLO |
| --- | --- | --- |
| P1 (CI gate down, blocking all deploys) | PagerDuty + Slack #ai-platform-incident | Ack ≤ 5 min |
| P2 (cross-vendor kappa floor breach for >24h) | PagerDuty | Ack ≤ 30 min |
| P3 (judge fallback active, primary down) | Slack only | Next business day |
| P4 (informational, weekly digest) | Email digest | None |

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming; daily snapshots; 35-day retention.
- **ClickHouse.** Weekly backup to GCS; ReplicatedMergeTree HA within region.
- **Object stores.** Object Lock + versioning + cross-region replication for bundles and audit log.
- **DR drill cadence.** Quarterly. Full failover to US-West.

### Runbooks

- `vendor-judge-silent-update.md` — when the daily diff job flags a new judge snapshot
- `kappa-collapse.md` — when cross-vendor kappa drops below floor
- `ci-gate-bypass-audit.md` — quarterly review of all bypass-the-gate events
- `rubric-recalibration.md` — quarterly anchor refresh procedure
- `evidence-bundle-export.md` — assembling a complete decision lineage for a regulator

---

## 6. Compliance posture

| Framework | Posture |
| --- | --- |
| **SOC 2 Type II** | All six components in scope. Annual external audit. |
| **PCI-DSS** | In scope only when the GenAI feature touches cardholder data; field-level encryption + tokenization. |
| **GLBA** | Customer financial data: field-level encryption + access controls + audit trail. |
| **SR 11-7** | Implementation surface for GenAI ongoing-monitoring expectations under the SR letter. |
| **NIST AI RMF + EU AI Act Article 12** | EvalForge is the implementation of the 'Measure' function. Decision-grain lineage interlocks with Project 09 (LineageLog). |
| **GDPR** | EU instance enforces data residency. Right-to-erasure cascades to probe-response hash deletion. |
| **India RBI** | India regional instance only. No cross-border replication. |

---

## 7. What's deliberately not here

- **A model registry.** EvalForge reads model_version from MLflow / SageMaker Model Registry / Vertex AI Model Registry. Not in the business of replacing it.
- **A production observability tool.** That's DriftSentinel. EvalForge is pre-deploy; DriftSentinel is post-deploy. The two products interlock at the shared probe registry.
- **A prompt-injection defender.** That's PromptShield. The CI gate runs in a pre-deploy context where the prompt is trusted.
- **A standalone authentication system.** Integrate with the bank's IdP.

---

## Appendix — sample API contract

```python
# POST /v1/eval-runs
# Auth: OIDC bearer; role: ef:engineer or higher
# Request:
{
    "model_version": "claude-sonnet-4-20260214",
    "probe_set_version": "probes-v1.0",
    "triggered_by": "ci_pr",
    "pr_number": 8417,
    "judge_config": {
        "primary": "claude-judge-v1",
        "secondary": "gpt-4o-judge"
    }
}
# Response 201:
{
    "eval_run_id": "ER0312",
    "status": "running",
    "estimated_completion": "2026-02-17T09:08:00Z",
    "ci_gate_pending": true
}

# GET /v1/eval-runs/ER0312
# Response 200 (after completion):
{
    "eval_run_id": "ER0312",
    "run_date": "2026-02-17T09:07:14Z",
    "pass_rate": 0.86,
    "inter_judge_kappa": 0.68,
    "ci_gate_verdict": "FAIL",
    "ci_gate_reason": "Regression of -7.0pp vs rolling baseline 0.93.",
    "ci_gate_action": "block_deploy",
    "bundle": {
        "bundle_id": "...",
        "storage_uri": "gs://evalforge-bundles/.../bundle.json"
    },
    "routed_to": "L2 trust-and-safety queue"
}
```

OpenAPI spec lives at `apps/api/openapi.yaml` and is the source of truth for the CLI, the UI, and the GitHub Action.
