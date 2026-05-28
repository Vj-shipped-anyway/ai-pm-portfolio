# Architecture — AgentWatch

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network topology, operational runbooks. What you would hand to your CISO and your platform engineering lead on day one.

This doc is cloud-agnostic where the design allows it and explicit where it does not. Primary stack shown on Google Cloud because the design aligns directly with the [*Building secure multi-agent systems on Google Cloud*](https://cloud.google.com/) reference paper (Kannan, Sizemore, Herriford et al., 2025); AWS and Azure equivalents are called out inline. The substrate AgentWatch reads from is [OpenTelemetry](https://opentelemetry.io/) — which all four agent frameworks (LangGraph, AutoGen, Bedrock Agents, OpenAI Assistants) export to natively.

---

## 1. Logical architecture

AgentWatch is a **sidecar observability layer**, not an agent runtime. It does not orchestrate agents; it observes them. Six components, each independently deployable.

| Component | Responsibility | Language / framework | Stateful? |
| --- | --- | --- | --- |
| `agentwatch-api` | REST + gRPC API. Auth, RBAC, incident-pack rendering, agent_incidents reads. | Python 3.11 + FastAPI + Pydantic v2 | No |
| `agentwatch-sidecar` | Per-agent OTel consumer. Classifies deficiency under 6-class taxonomy; writes immutable `agent_incidents` row. | Python + Cloud Functions / Lambda + Pydantic | No (commits offsets) |
| `agentwatch-cap` | Per-agent dollar-cap enforcer. Pre-flight check before each tool call; auto-terminate on breach. | Python + Cloud Functions / Lambda | No |
| `agentwatch-ui` | SRE on-call + line-1 owner workbench. Drill-into-run view, incident-pack rendering, legal-hold management. | React 19 + Next.js 15 + TypeScript + Tailwind | No |
| `agentwatch-cli` | Operator tool — backfill, replay, ad-hoc incident-pack export, cap override. | Python + Click | No |
| `agentwatch-scheduler` | Daily ETL: cost-attribution backlinks, drift baseline updates, retention cleanup. | Airflow 2.9 / Cloud Composer / MWAA | Stateful (DAG runs) |

All six are stateless except the scheduler. State lives in the data layer. Stateless components scale horizontally; the scheduler is single-leader with a cold standby.

**Repo structure** (monorepo via Bazel or pnpm workspaces):

```
agentwatch/
├── apps/
│   ├── api/             # FastAPI service
│   ├── sidecar/         # Cloud Functions OTel consumer
│   ├── cap/             # Cloud Functions dollar-cap enforcer
│   ├── ui/              # Next.js app
│   ├── cli/             # Click CLI
│   └── scheduler/       # Airflow DAGs
├── packages/
│   ├── domain/          # Shared domain models (proto + codegen TS/Python)
│   ├── auth/            # Shared OIDC/SAML libs
│   ├── otel/            # OTel parser + helper utilities
│   └── telemetry/       # OpenTelemetry instrumentation
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
    ├── integration/     # uses fake OTel exporter + fake LLM proxy
    └── load/            # k6 / locust against the sidecar
```

---

## 2. Physical / deployment architecture

### Runtime

**Primary on GCP (matches the Google Cloud reference architecture):**

| Component | Runtime | Why |
| --- | --- | --- |
| `api` | Cloud Run (managed) | Stateless HTTP, autoscale 0-N, request-based billing |
| `sidecar` | Cloud Functions gen 2 on Pub/Sub | Event-driven, autoscaling, no idle cost |
| `cap` | Cloud Functions gen 2 — same Pub/Sub topic with a separate subscription | Pre-flight low-latency enforcement |
| `ui` | Cloud Run | Static + SSR Next.js, embedded in SRE on-call workflow iframes |
| `cli` | Local + Cloud Build for CI runs | Operator tool, not a service |
| `scheduler` | Cloud Composer 3 (managed Airflow) | Existing skill set in most BFSI ops teams |

**AWS equivalent:** ECS Fargate or EKS for `api`/`ui`; Lambda + EventBridge for `sidecar` and `cap`; MWAA for `scheduler`.

**Azure equivalent:** Container Apps for `api`/`ui`; Functions + Event Grid for `sidecar` and `cap`; Data Factory or Airflow on AKS for `scheduler`.

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
[Private subnet — sidecar, cap, scheduler]
   │
   ├──► [PostgreSQL — Cloud SQL / RDS]                 (private endpoint only)
   ├──► [ClickHouse — Aiven / Altinity managed]        (private endpoint)
   ├──► [Snowflake / Databricks]                       (PrivateLink / PSC)
   ├──► [Redis — Memorystore / ElastiCache]            (private endpoint)
   └──► [GCS Object Lock / S3 Object Lock]             (private endpoint)

Agent runtime emits OTel spans:
   [LangGraph / AutoGen / Bedrock / OpenAI Assistants]
   → [OTel collector] → [Pub/Sub / Kinesis / Event Hubs]
   → [sidecar + cap]
```

### Region & DR

- **Primary:** US-East (us-east1 GCP / us-east-1 AWS / East US Azure)
- **DR:** US-West (us-west1 / us-west-2 / West US 2). Active-passive. RTO 4h, RPO 5min for the `agent_incidents` table.
- **EU instance:** Frankfurt (europe-west3 / eu-central-1 / Germany West Central). Required for EU AI Act Article 14 and GDPR — incidents involving EU-customer agent runs cannot egress region.
- **India instance:** Mumbai (asia-south1 / ap-south-1 / Central India). Required for RBI data localization on Indian retail arms.
- Each regional instance has its own database, its own KMS key ring, its own Identity-Aware Proxy. **No cross-region replication for the `agent_incidents` table** — each region is sovereign for its own incidents. The WORM archive replicates cross-region within the same regulatory boundary only.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** (Cloud SQL / RDS) | `agent_incidents` immutable table, attestation history, audit log, legal-hold flags. | Relational integrity, joins, mature transactions, well-understood by BFSI ops. Append-only via insert-only role + trigger guard. |
| **ClickHouse** (Aiven / Altinity managed) | High-cardinality reasoning-trace events — per-tool-call span with chain-of-thought text, drift baseline time-series. | 10-50x cheaper than Postgres for time-series at this volume. Interlocks with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/)'s ClickHouse for shared drift-signal querying. |
| **Snowflake / Databricks** (read-only) | Downstream business outcomes (claims platform, KYC case database, dispute system) for cost-attribution ETL. | Already exists at every Tier-1 BFSI shop. We don't introduce a third lake. |
| **Redis** (Memorystore / ElastiCache) | Session cache (UI), idempotency keys (sidecar), rate-limit counters, SOT lookup cache for the schema validator. | TTL-based eviction. Multi-AZ for high availability. |
| **GCS / S3 / Blob Storage with Object Lock** | **WORM archive of incident packs** + reasoning-trace replays + 7-year SR 11-7 audit archive. | Object Lock = Write-Once-Read-Many for the SR 11-7 / EU AI Act seven-year retention. |
| **Pub/Sub / Kinesis / Event Hubs** | OTel ingester topic. Sidecar + cap subscribe with at-least-once semantics; partition-sharded by `agent_id`. | Native to the cloud; ordered delivery within a partition; replay-able. |

### The agent-incident composition table

The consequential schema. Every deficiency in the taxonomy maps to one of these JSONB columns:

```sql
-- Append-only. Immutability enforced via insert-only role + DENY on UPDATE/DELETE
-- to anyone except the legal-hold service account (which can flag, not modify).
-- Partitioned by month for retention cycling and audit-window queries.

CREATE TABLE agent_incidents (
    -- Identity
    incident_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                   TEXT NOT NULL,
    agent_id                 TEXT NOT NULL,
    customer_id_hash         TEXT,                      -- SHA-256 + KMS pepper, null if no customer in scope
    deficiency_class         TEXT NOT NULL,             -- runaway_loop / hallucinated_args / silent_drift /
                                                        --   blast_unbounded / no_reasoning_trace / cost_detached
    severity                 TEXT NOT NULL,             -- P1 / P2 / P3
    detected_at              TIMESTAMPTZ NOT NULL,

    -- Deficiency #1 — runaway tool loops
    runaway_check            JSONB NOT NULL,
    -- example: {"tool_call_count": 1847, "exceeds_loop_threshold": true,
    --           "loop_signature": "same_tool_with_arg_variation"}

    -- Deficiency #2 — hallucinated tool arguments
    schema_validation        JSONB NOT NULL,
    -- example: {"args_validated": true, "args_rejected_count": 32,
    --           "rejection_signature": "customer_id_not_in_sot"}

    -- Deficiency #3 — silent agent drift
    drift_signal             JSONB NOT NULL,
    -- example: {"baseline": {"claim_lookup": 0.18, ...},
    --           "observed": {"claim_lookup": 0.91, ...},
    --           "max_delta_pct": 0.73, "drift_detected": true}

    -- Deficiency #4 — blast-radius unbounded
    blast_radius_check       JSONB NOT NULL,
    -- example: {"tool_calls_attempted": 1847, "distinct_tools_touched": 1,
    --           "cap_usd": 250, "cost_at_cutoff_usd": 4218.34, "cap_exceeded": true}

    -- Deficiency #5 — no reasoning trace capture
    reasoning_trace          JSONB NOT NULL,
    -- example: {"trace_captured": true,
    --           "trace_store": "agentwatch_replay_store",
    --           "trace_replay_url": "https://agentwatch.bank/runs/RUN_00095/replay",
    --           "synthesized_for_incident": false}

    -- Deficiency #6 — cost attribution
    cost_attribution         JSONB NOT NULL,
    -- example: {"run_cost_usd": 4218.34, "outcome_id": "OUT_RUN_00095",
    --           "outcome_type": "agent_terminated_by_cap", "attributed": true}

    -- Cross-references to raw agent log surfaces
    framework_otel_ref       TEXT NOT NULL,
    llm_proxy_ref            TEXT NOT NULL,
    cloud_logging_ref        TEXT NOT NULL,
    agent_identity_ref       TEXT NOT NULL,

    -- Composition + retention metadata
    composed_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    composition_seconds      NUMERIC(6,4) NOT NULL,
    agentwatch_action        TEXT NOT NULL,             -- auto_cutoff_at_blast_radius_cap / schema_validator_blocked /
                                                        --   drift_alert_routed_to_owner / circuit_breaker_tripped /
                                                        --   trace_replay_synthesized / cost_attributed_to_outcome
    cost_at_cutoff_usd       NUMERIC(12,2) NOT NULL,
    mttr_minutes             INTEGER,
    routed_to                TEXT[],                    -- e.g., ['sre_oncall', 'line1_owner', 'finops_queue']
    legal_hold               BOOLEAN NOT NULL DEFAULT FALSE,
    legal_hold_set_by        TEXT,
    legal_hold_set_at        TIMESTAMPTZ,
    retention_until          TIMESTAMPTZ NOT NULL,      -- detected_at + 7 years by default
    row_hash                 TEXT NOT NULL              -- SHA-256 of all fields above, HSM-signed
) PARTITION BY RANGE (detected_at);

CREATE UNIQUE INDEX idx_agent_incidents_dedup
    ON agent_incidents (run_id, deficiency_class);
CREATE INDEX idx_agent_incidents_agent
    ON agent_incidents (agent_id, detected_at DESC);
CREATE INDEX idx_agent_incidents_class
    ON agent_incidents (deficiency_class, detected_at DESC);
CREATE INDEX idx_agent_incidents_severity
    ON agent_incidents (severity, detected_at DESC);
CREATE INDEX idx_agent_incidents_legal_hold
    ON agent_incidents (legal_hold) WHERE legal_hold = TRUE;

-- Immutability guard. UPDATE allowed only on legal_hold fields.
CREATE OR REPLACE FUNCTION agent_incidents_immutability_guard()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.run_id              IS DISTINCT FROM OLD.run_id) OR
           (NEW.agent_id            IS DISTINCT FROM OLD.agent_id) OR
           (NEW.deficiency_class    IS DISTINCT FROM OLD.deficiency_class) OR
           (NEW.runaway_check       IS DISTINCT FROM OLD.runaway_check) OR
           (NEW.schema_validation   IS DISTINCT FROM OLD.schema_validation) OR
           (NEW.drift_signal        IS DISTINCT FROM OLD.drift_signal) OR
           (NEW.blast_radius_check  IS DISTINCT FROM OLD.blast_radius_check) OR
           (NEW.reasoning_trace     IS DISTINCT FROM OLD.reasoning_trace) OR
           (NEW.cost_attribution    IS DISTINCT FROM OLD.cost_attribution) OR
           (NEW.row_hash            IS DISTINCT FROM OLD.row_hash) THEN
            RAISE EXCEPTION 'agent_incidents is immutable except for legal_hold fields';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'agent_incidents rows cannot be deleted; use retention_until cycling instead';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER agent_incidents_guard
    BEFORE UPDATE OR DELETE ON agent_incidents
    FOR EACH ROW EXECUTE FUNCTION agent_incidents_immutability_guard();
```

The trigger guards the immutable columns at the database level — a compromised application credential cannot rewrite history. The `legal_hold` fields are deliberately mutable because legal hold is set asynchronously by counsel.

### Six-deficiency → log-source mapping

The table that compiles the composition contract. Every cell maps a deficiency to the raw agent log surface that feeds it.

| # | Deficiency | Primary source | Secondary source | Sidecar action |
| --- | --- | --- | --- | --- |
| 1 | Runaway tool loops | Framework OpenTelemetry export (per-tool-call span) | Cloud Logging on the tool-call HTTP surface | Counter; threshold-based + signature-based detection; auto-terminate on per-agent cap. |
| 2 | Hallucinated tool arguments | Tool-call `args_json` payload from OTel | SOT lookup (BigQuery / Snowflake / mainframe DB2) | Pre-flight schema validator; reject before tool fires. |
| 3 | Silent agent drift | 30-day rolling tool-call mix per agent | ClickHouse `agent_tool_mix_baseline` table | Daily diff vs baseline; alert when any tool's share deviates &gt; 20 pp. |
| 4 | Blast-radius unbounded | Per-run distinct-tool count + accumulated cost | Per-agent `blast_radius_cap_usd` from `agents` table | Circuit breaker: per-incident tool-call cap + per-agent dollar ceiling. |
| 5 | No reasoning trace capture | LLM proxy trace tail (Langfuse / Helicone / vendor-native) | Framework OTel export (fallback synthesis) | Long-term ClickHouse-backed replay store; query by `run_id`. |
| 6 | Cost telemetry detached from outcomes | Daily ETL from downstream business systems | Per-run cost from OTel + LLM proxy | Join run cost to downstream business event via `outcome_id`. |

### ClickHouse schema (reasoning-trace replay + drift baseline)

```sql
-- Long-term reasoning-trace event store. The replay surface for deficiency #5.
CREATE TABLE reasoning_trace_events (
    run_id              String,
    agent_id            LowCardinality(String),
    span_id             String,
    parent_span_id      String,
    span_kind           LowCardinality(String),       -- 'plan', 'tool_call', 'reflection', 'final'
    span_name           String,
    started_at          DateTime64(3, 'UTC'),
    duration_ms         UInt32,
    chain_of_thought    String,                       -- the agent's recorded justification
    tool_name           LowCardinality(String),
    args_json           String,
    status              LowCardinality(String),
    cost_usd            Decimal(10, 4)
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/reasoning_trace_events', '{replica}')
PARTITION BY toYYYYMM(started_at)
ORDER BY (run_id, started_at, span_id)
TTL started_at + INTERVAL 2555 DAY DELETE;  -- 7 years per SR 11-7

-- Per-agent tool-call-mix baseline. Updated daily by the scheduler.
CREATE TABLE agent_tool_mix_baseline (
    agent_id            LowCardinality(String),
    tool_name           LowCardinality(String),
    snapshot_date       Date,
    call_share          Float32,                      -- 0.0 - 1.0
    n_runs              UInt32,
    n_calls             UInt32
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/agent_tool_mix_baseline', '{replica}')
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (agent_id, snapshot_date, tool_name)
TTL snapshot_date + INTERVAL 730 DAY DELETE;  -- 2 years hot, archive to GCS thereafter
```

### Retention & data classification

| Data class | Retention | Storage | Justification |
| --- | --- | --- | --- |
| `agent_incidents` rows | 7 years (10 years for EU) | Postgres hot for 12 months; archive to GCS Object Lock after | SR 11-7 ongoing-monitoring evidence |
| Incident packs (JSON + text) | 7 years | GCS Object Lock + cross-region replication | Same |
| Reasoning-trace events | 7 years | ClickHouse hot for 12 months; archive to GCS thereafter | Same |
| Tool-call mix baseline | 2 years hot | ClickHouse; aggregate longer history archived | Operational |
| Audit log on incident access | 7 years | Postgres partitioned + GCS Object Lock | Audit-on-audit |
| SOT lookup cache | 60 seconds | Redis | Operational |
| Validator session data | 8 hours | Redis | Operational |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with envelope encryption. Customer-Managed Encryption Keys (CMEK / CMK) in Cloud KMS / AWS KMS / Azure Key Vault. Bank's key rotation policy applies (typically 90 days). Keys are region-scoped — never cross region boundary.
- **In transit.** TLS 1.3 minimum north-south. mTLS on east-west via service mesh.
- **Field-level.** `customer_id_hash` is SHA-256 with a KMS-managed pepper. Raw customer IDs never touch AgentWatch storage. The Data Vault Agent pattern from Google's *Building secure multi-agent systems* reference applies directly here.
- **Row-level hash.** Every `agent_incidents` row has a `row_hash` (SHA-256 of all fields) signed by an HSM-backed code-signing key at write time. Tamper detection.
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

Five roles, mapped to bank roles, scoped per region:

| Role | Permissions | Maps to (bank role) |
| --- | --- | --- |
| `aw:viewer` | Read fleet-level reliability health; no incident-level access | Exec read-only, board reporting |
| `aw:agent_owner` | Read incidents for their own agents; trace-replay access | Line-1 agent owners (claims ops, KYC ops, payments ops) |
| `aw:validator` | `agent_owner` + cross-agent read for attestation | Line-2 validators (MRM team) |
| `aw:platform_admin` | `validator` + cap configuration + ingester health | AI Platform team, SRE on-call |
| `aw:cro` | `platform_admin` + cross-region read on portfolio scope; export at fleet level | CRO, Head of AI Platform |

Authorization implemented via Open Policy Agent (OPA) + Rego policies. Every API call evaluates policy at the gateway. Every decision logged to the audit log.

### Network controls

- **Perimeter.** VPC Service Controls (GCP) / AWS PrivateLink + Network Firewall / Azure Private Endpoints. Egress to public internet only via Secure Web Proxy with allow-list.
- **Lateral.** Cloud NGFW / AWS Security Groups + Network ACLs / Azure NSGs. Layer-7 inspection on the service mesh.
- **Ingress.** Cloud Armor / AWS WAF / Azure WAF with OWASP CRS + custom rules for the API surface.
- **Zero-trust.** All inter-service calls authenticated via SPIFFE mTLS. No "trusted internal network" assumption.

### Threat model — what we explicitly defend against

| Threat | Mitigation |
| --- | --- |
| Compromised API token | Short-lived tokens, mTLS service-to-service, IdP-side revocation propagates &lt;=5 min |
| Insider — agent owner pulls all customer data | `customer_id_hash` (not raw IDs); RBAC limits agent owner to their own agent's incidents, not cross-agent bulk queries |
| Compromised incident row (poisoning) | Row-hash HSM-signed at write; immutability trigger + insert-only role; periodic re-verification job |
| Adversarial agent input (prompt injection) | Out of scope here — covered by [PromptShield](../06-promptshield-prompt-injection-defense/) at the agent gateway. AgentWatch records the resulting incident if PromptShield catches it post-fire. |
| Database exfiltration via SQL injection | Parameterized queries only; ORM-only (SQLAlchemy + Pydantic) at the API boundary; Cloud Armor WAF rule set |
| Egress data exfiltration | VPC Service Controls + Secure Web Proxy allow-list |
| Tampering with immutable history | Database trigger denies UPDATE/DELETE on immutable fields; row-hash mismatch detection job runs nightly |
| Sidecar back-pressure on agent runtime | Fail-open contract: if the sidecar topic saturates, the agent continues without observability; AgentWatch raises an internal P2 |

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs | Cloud Logging + Datadog / CloudWatch / Azure Monitor | Existing SOC pane |
| Distributed traces | Cloud Trace + [OpenTelemetry](https://opentelemetry.io/) → Datadog APM | Sidecar fan-in latency |
| Metrics | Prometheus + Grafana (or Datadog metrics) | RED-method per service |
| Reasoning-trace events | ClickHouse `reasoning_trace_events` | The product's own replay surface |
| LLM-specific traces | Langfuse (self-hosted) for the GenAI proxy | Source signal for deficiency #5 |
| Audit log | Postgres `audit_log` + GCS Object Lock | SR 11-7 retention |

### Alerting

| Severity | Channel | SLO |
| --- | --- | --- |
| P1 (sidecar down &gt;5 min in any region, OR per-agent cap-enforcer failing open) | PagerDuty primary + secondary, Slack #agentwatch-incident | Acknowledge &lt;=5 min |
| P2 (composition completeness &lt;95% in a 1h window OR OTel ingester lag &gt; 5 min) | PagerDuty (lower urgency), Slack | Acknowledge &lt;=30 min |
| P3 (single-agent drift signal fired, or single-incident SOT lookup failed) | Slack only | Triaged next business day |
| P4 (informational) | Daily digest email | None |

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to GCS / S3. Daily snapshots, 35-day retention. Point-in-time recovery within retention window.
- **ClickHouse.** Weekly backup to GCS / S3. ReplicatedMergeTree gives HA within region.
- **Object stores.** Object Lock + versioning + cross-region replication for incident-pack WORM archive (within the same regulatory region only — never US ↔ EU).
- **DR drill cadence.** Quarterly. Full failover to US-West, validate RTO 4h / RPO 5min for the `agent_incidents` table, fail back. Runbook in `docs/runbooks/dr-failover.md`.

### Runbooks (one paragraph each in the repo)

- `dr-failover.md` — full region failover
- `sidecar-stuck.md` — when the OTel ingester fan-in stalls
- `cap-override.md` — line-1 owner requests a cap override with line-2 attestation
- `incident-pack-export.md` — pulling a complete incident pack for an MRM review
- `legal-hold-cascade.md` — applying legal hold when a customer files a complaint
- `right-to-erasure.md` — GDPR-compliant cascading deletion (with legal-hold override)
- `runaway-fleet-storm.md` — when multiple agents trip the cap simultaneously (typically a vendor model regression)

---

## 6. Compliance posture

| Framework | Posture |
| --- | --- |
| **SOC 2 Type II** | All six components in scope. Annual external audit. |
| **PCI-DSS** | In scope only when the underlying agent touches cardholder data. AgentWatch itself doesn't process card data; it observes agents that may. PCI scope minimization via `customer_id_hash` + KMS pepper at the source. |
| **GLBA** | Customer financial data handled with field-level hashing + access controls + audit trail. Right-to-be-forgotten cascades to incident records via `customer_id_hash` deletion (with legal-hold override). |
| **SR 11-7 / OCC Bulletin 2011-12** | The per-incident reliability evidence is the missing piece for "documented ongoing monitoring" of deployed agents. PRD references the relevant supervisory expectations. |
| **NIST AI RMF 1.0** | Per-agent incident composition maintained for the deployed fleet. AgentWatch is the implementation surface for the framework's "Measure" + "Manage" functions. |
| **EU AI Act Article 14** | Human oversight requirement for high-risk AI systems. AgentWatch surfaces the human-vs-autonomous reviewer distinction; the incident pack is the audit evidence. EU instance enforces data residency. |
| **OWASP LLM Top 10** | LLM06 (Sensitive Information Disclosure) and LLM09 (Misinformation) anchor the taxonomy. AgentWatch's schema validator catches the LLM06 / LLM09 surface that prompt-injection defense (PromptShield) misses. |
| **GDPR** | EU instance enforces data residency. Right-to-erasure cascades to `customer_id_hash` deletion with legal-hold override. DPO sign-off documented per region. |
| **India RBI data localization** | Indian retail-arm agent incidents run on the India regional instance only. No cross-border replication. |

---

## 7. What is deliberately not here

- **A custom agent runtime.** We sidecar on LangGraph / AutoGen / Bedrock Agents / OpenAI Assistants. We do not orchestrate.
- **A custom LLM proxy.** We read from Langfuse / Helicone / vendor-native trace tails.
- **A custom model registry.** We read from MLflow / SageMaker / Vertex.
- **A retraining engine.** AgentWatch provides incident outcome backlinks; the bank's existing MLOps platform retrains.
- **A customer-facing surface.** Internal AI-platform + SRE on-call + MRM tool only.
- **A standalone authentication system.** We integrate with the bank's IdP.
- **A prompt-injection defense layer.** Covered by [PromptShield](../06-promptshield-prompt-injection-defense/) at the agent gateway.

That last list is the discipline. Every internal-build I have watched die has died on scope creep into one of those.

---

## Appendix — sample API contract

```python
# GET /v1/incidents/{incident_id}
# Auth: OIDC bearer; role: aw:agent_owner (own agents) or aw:validator (cross-agent)
# Response 200:
{
    "incident_id": "INC_0001",
    "run_id": "RUN_00095",
    "agent_id": "claims_triage_v3",
    "deficiency_class": "runaway_loop",
    "severity": "P1",
    "detected_at": "2026-04-14T03:18:01Z",

    "runaway_check": {
        "tool_call_count": 1847,
        "exceeds_loop_threshold": true,
        "loop_signature": "same_tool_with_arg_variation"
    },
    "schema_validation": {
        "args_validated": true,
        "args_rejected_count": 0,
        "rejection_signature": "n/a"
    },
    "drift_signal": {
        "baseline": {"claim_lookup": 0.18, "policy_lookup": 0.15, "fraud_score": 0.12},
        "observed": {"claim_lookup": 1.0},
        "max_delta_pct": 0.82,
        "drift_detected": true
    },
    "blast_radius_check": {
        "tool_calls_attempted": 1847,
        "distinct_tools_touched": 1,
        "cap_usd": 250,
        "cost_at_cutoff_usd": 4218.34,
        "cap_exceeded": true
    },
    "reasoning_trace": {
        "trace_captured": true,
        "trace_store": "agentwatch_replay_store",
        "trace_replay_url": "https://agentwatch.bank/runs/RUN_00095/replay",
        "synthesized_for_incident": false
    },
    "cost_attribution": {
        "run_cost_usd": 4218.34,
        "outcome_id": "OUT_RUN_00095",
        "outcome_type": "agent_terminated_by_cap",
        "attributed": true
    },

    "agentwatch_action": "auto_cutoff_at_blast_radius_cap",
    "cost_at_cutoff_usd": 4218.34,
    "mttr_minutes": 6,
    "routed_to": ["sre_oncall", "line1.insurance-ops"],

    "framework_otel_ref": "otel/langgraph/RUN_00095",
    "llm_proxy_ref": "langfuse/traces/RUN_00095",
    "cloud_logging_ref": "projects/bank-prod/logs/agents/RUN_00095",
    "agent_identity_ref": "iam/agent-identity/RUN_00095",

    "composed_at": "2026-04-14T03:18:01Z",
    "composition_seconds": 0.04,
    "legal_hold": false,
    "row_hash": "sha256:c7d3...",
    "retention_until": "2033-04-14T03:18:01Z"
}
```

OpenAPI spec lives at `apps/api/openapi.yaml` and is the source of truth for both the CLI and the UI clients.
