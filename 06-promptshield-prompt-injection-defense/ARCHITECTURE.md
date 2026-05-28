# Architecture — PromptShield

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network topology, operational runbooks, threat model. What you would hand to your CISO and your platform engineering lead on day one.

This doc is cloud-agnostic where the design allows it and explicit where it does not. Primary stack shown on Google Cloud because the design aligns directly with the *Building secure multi-agent systems on Google Cloud* reference paper (Kannan, Sizemore, Herriford et al., 2025); AWS and Azure equivalents are called out inline.

---

## 1. Logical architecture

PromptShield is a **five-layer defense-in-depth gateway**, not a foundation-model vendor and not a logging vendor. It sits in the request path between the user / banker and the LLM, and in the response path between the LLM and the user. Six components, each independently deployable.

| Component | Responsibility | Language / framework | Stateful? |
| --- | --- | --- | --- |
| `promptshield-api` | REST + gRPC API. Auth, RBAC, configuration of the five layers, policy admin, observability surface. | Python 3.11 + FastAPI + Pydantic v2 | No |
| `promptshield-l1` | L1 Input Classifier service. Llama Guard 3 / fine-tuned DeBERTa inference on T4 / L4 GPUs. | Python + FastAPI + Triton inference server | No |
| `promptshield-l2` | L2 Retrieval Scanner service. Same classifier as L1, FP-tolerant calibration. | Python + FastAPI + Triton | No |
| `promptshield-l3` | L3 Tool-Call Gate. OPA / Rego sidecar evaluates every tool invocation against the policy bundle. | Go + OPA SDK | No (OPA state is in-memory bundle) |
| `promptshield-l4` | L4 Egress Filter. DLP regex pack + Cloud DLP / Nightfall / BigID call-out for the heavy PII detection. | Python + FastAPI | No |
| `promptshield-l5` | L5 Per-Session Memory Boundary. Redis-backed session memory with TTL; enforces SPIFFE-keyed isolation. | Go + Redis client | Stateful (Redis-backed) |
| `promptshield-ui` | Configuration / observability panel. Per-layer fire-rate dashboards, policy admin, attack-scenario walkthrough. | React 19 + Next.js 15 + TypeScript + Tailwind | No |
| `promptshield-scheduler` | Daily ETL: red-team probe runs, classifier-pin diffs, retention cleanup, attestation-pack auto-assembly. | Python + Airflow 2.9 / Cloud Composer / MWAA | Stateful (DAG runs) |

All components except `promptshield-l5` and `promptshield-scheduler` are stateless. State lives in the data layer.

**Repo structure** (monorepo via Bazel or pnpm workspaces):

```
promptshield/
├── apps/
│   ├── api/             # FastAPI control plane
│   ├── l1/              # L1 Input Classifier service
│   ├── l2/              # L2 Retrieval Scanner service
│   ├── l3/              # L3 Tool-Call Gate (OPA sidecar)
│   ├── l4/              # L4 Egress Filter service
│   ├── l5/              # L5 Session Memory Boundary
│   ├── ui/              # Next.js admin / observability panel
│   └── scheduler/       # Airflow DAGs (red-team probes, pin diffs)
├── packages/
│   ├── classifier/      # Shared Llama Guard 3 / DeBERTa serving code
│   ├── policy/          # Shared OPA bundle build + lint
│   ├── domain/          # Shared domain models (proto + codegen TS/Python)
│   └── telemetry/       # OpenTelemetry helpers
├── policies/            # OPA Rego bundles, one directory per tool
│   ├── send_email/
│   ├── crm_update/
│   ├── run_query/
│   └── ...
├── infra/
│   ├── terraform/       # Multi-cloud IaC (gcp, aws, azure)
│   ├── kubernetes/      # Helm charts + Kustomize overlays
│   └── network/         # VPC SC, Network Firewall, NSG templates
├── docs/
│   ├── ARCHITECTURE.md
│   ├── runbooks/
│   └── api/             # OpenAPI spec
└── tests/
    ├── unit/
    ├── integration/     # uses fake LLM + fake retrieval
    ├── red_team/        # quarterly probe runs
    └── load/            # k6 / locust against the gateway
```

---

## 2. Physical / deployment architecture

### Runtime

**Primary on GCP (matches the Google Cloud reference architecture):**

| Component | Runtime | Why |
| --- | --- | --- |
| `api` | Cloud Run (managed) | Stateless HTTP, autoscale 0-N |
| `l1`, `l2` | GKE on T4 / L4 GPU node pool | Classifier inference; ~80ms P99 budget |
| `l3` | Cloud Run, OPA sidecar pattern | Stateless policy evaluation; <1ms P99 |
| `l4` | Cloud Run (calls out to Cloud DLP) | Stateless DLP scan; <10ms P99 |
| `l5` | GKE workload + Memorystore Redis | Redis-backed session memory |
| `ui` | Cloud Run | Static + SSR Next.js |
| `scheduler` | Cloud Composer 3 (managed Airflow) | Existing skill set in most BFSI ops teams |

**AWS equivalent:** ECS Fargate for `api`/`l3`/`l4`/`ui`; EKS GPU node pool for `l1`/`l2`; ElastiCache Redis for `l5`; MWAA for `scheduler`. Egress goes via Bedrock Guardrails for vendor-LLM-side defense + AWS Network Firewall for VPC-level egress.

**Azure equivalent:** Container Apps for `api`/`l3`/`l4`/`ui`; AKS GPU node pool for `l1`/`l2`; Azure Cache for Redis for `l5`; Data Factory or Airflow on AKS for `scheduler`. Egress goes via Azure AI Content Safety / Prompt Shields for vendor-LLM-side defense + Azure Private Endpoints.

### Network topology

```
Internet (banker browser, RM workstation)
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
[Private subnet — l1, l2, l3, l4, l5, scheduler]
   │
   ├──► [PostgreSQL — Cloud SQL / RDS]                 (private endpoint only)
   ├──► [ClickHouse — Aiven / Altinity managed]        (private endpoint)
   ├──► [Redis Cluster — Memorystore / ElastiCache]    (private endpoint, AUTH + TLS)
   ├──► [GCS Object Lock / S3 Object Lock]             (private endpoint)
   └──► [LLM endpoints — Anthropic, Azure OpenAI, Bedrock] (egress via Secure Web Proxy)

Egress to vendor APIs (Anthropic, Azure OpenAI, Bedrock):
   [Secure Web Proxy / Squid] — allow-list of vendor URLs only
   [VPC Service Controls / Network Firewall] — data exfiltration prevention
```

### Region & DR

- **Primary:** US-East (`us-east1` GCP / `us-east-1` AWS / East US Azure)
- **DR:** US-West. Active-passive. RTO 30min, RPO 5min for the `attack_log` table; RPO 0 for L1-L4 (stateless).
- **EU instance:** Frankfurt. Required for [EU AI Act](https://eur-lex.europa.eu/eli/reg/2024/1689/oj) and GDPR — lineage of EU bankers' queries cannot egress region.
- **India instance:** Mumbai. Required for RBI data localization on Indian retail-arm copilots.
- Each regional instance has its own database, its own KMS key ring, its own Redis cluster. **No cross-region replication for the `attack_log` table** — each region is sovereign for its own request lineage.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** (Cloud SQL / RDS) | `attack_log` immutable table, OPA bundle audit log, policy-admin trail. | Relational integrity, joins, mature transactions, well-understood by BFSI ops. Append-only via insert-only role + trigger guard. |
| **Redis Cluster** (Memorystore / ElastiCache) | Per-session memory. TTL-based eviction. Multi-AZ for high availability. Keys: `(spiffe_id, session_id)`. | Sub-millisecond reads. Native TTL. Standard pattern at every Tier-1 shop. |
| **ClickHouse** (Aiven / Altinity managed) | High-cardinality observability — per-layer fire-rate, per-pattern hit count, per-classifier-confidence histogram. | 10-50x cheaper than Postgres for time-series at this volume. Interlocks with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/)'s ClickHouse. |
| **GCS / S3 / Blob Storage with Object Lock** | **WORM archive of the `attack_log` table** + classifier-corpus snapshots + OPA bundle history. | Object Lock = Write-Once-Read-Many for the 7-year retention. |
| **Pub/Sub / Kinesis / Event Hubs** | Real-time stream of every block / allow decision. Composer-side fan-out to SOC pane + LineageLog + Datadog. | Native to the cloud; replay-able; decouples the gateway from downstream consumers. |

### The `attack_log` immutable table

The consequential schema. Every block / allow decision lands here. Same DDL discipline as LineageLog — append-only, row-hash signed, immutability-trigger guarded.

```sql
-- Append-only. Immutability enforced via insert-only role + DENY on UPDATE/DELETE
-- to anyone except the legal-hold service account (which can flag, not modify).
-- Partitioned by month for retention cycling.

CREATE TABLE attack_log (
    -- Identity
    log_id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id                   TEXT NOT NULL,
    session_id                   TEXT NOT NULL,
    user_id_hash                 TEXT NOT NULL,            -- SHA-256 with KMS pepper
    spiffe_id                    TEXT NOT NULL,
    copilot_id                   TEXT NOT NULL,            -- rm_copilot / kyc_copilot / claims_copilot / qa_copilot
    timestamp                    TIMESTAMPTZ NOT NULL,

    -- Request trace (hashes only, never raw text — PII discipline)
    user_prompt_hash             TEXT NOT NULL,            -- SHA-256 of the user prompt
    retrieved_chunk_hashes       JSONB NOT NULL,           -- [{chunk_id, sha256, retrieved_at}, ...]
    model_snapshot_id            TEXT NOT NULL,            -- the foundation model that would have answered
    tool_calls_attempted         JSONB NOT NULL,           -- [{tool_name, args_hash, intended_destination, ...}]
    response_hash                TEXT,                     -- SHA-256 of the model's response (NULL if blocked before LLM)

    -- Verdict
    overall_action               TEXT NOT NULL,            -- ALLOW / BLOCK / FLAG
    blocked_at_layer             TEXT,                     -- L1 / L2 / L3 / L4 / L5 / NULL
    matched_pattern              TEXT,                     -- which rule fired
    matched_evidence             TEXT,                     -- short evidence snippet (hashed if PII)
    attack_class_predicted       TEXT,                     -- direct / indirect / tool / egress / cross_session / jailbreak
    classifier_confidence        NUMERIC(4,3),             -- 0.000-1.000

    -- Per-layer trace (always populated, even if layer didn't fire)
    layer_trace                  JSONB NOT NULL,           -- [{layer, fired, latency_ms, evidence_hash}, ...]

    -- Audit
    composed_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    composition_ms               NUMERIC(6,2) NOT NULL,
    row_hash                     TEXT NOT NULL,            -- SHA-256 of all fields above, HSM-signed
    retention_until              TIMESTAMPTZ NOT NULL      -- timestamp + 7 years by default
) PARTITION BY RANGE (timestamp);

CREATE INDEX idx_attack_log_request
    ON attack_log (request_id);
CREATE INDEX idx_attack_log_session
    ON attack_log (session_id, timestamp DESC);
CREATE INDEX idx_attack_log_user
    ON attack_log (user_id_hash, timestamp DESC);
CREATE INDEX idx_attack_log_blocks
    ON attack_log (blocked_at_layer, timestamp DESC) WHERE overall_action = 'BLOCK';
CREATE INDEX idx_attack_log_class
    ON attack_log (attack_class_predicted, timestamp DESC) WHERE attack_class_predicted IS NOT NULL;

-- Immutability guard. UPDATE only allowed on legal_hold-related fields (added in v0.5).
CREATE OR REPLACE FUNCTION attack_log_immutability_guard()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.request_id          IS DISTINCT FROM OLD.request_id) OR
           (NEW.user_prompt_hash    IS DISTINCT FROM OLD.user_prompt_hash) OR
           (NEW.response_hash       IS DISTINCT FROM OLD.response_hash) OR
           (NEW.overall_action      IS DISTINCT FROM OLD.overall_action) OR
           (NEW.blocked_at_layer    IS DISTINCT FROM OLD.blocked_at_layer) OR
           (NEW.row_hash            IS DISTINCT FROM OLD.row_hash) THEN
            RAISE EXCEPTION 'attack_log is immutable except for legal_hold fields';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'attack_log rows cannot be deleted; use retention_until cycling';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER attack_log_guard
    BEFORE UPDATE OR DELETE ON attack_log
    FOR EACH ROW EXECUTE FUNCTION attack_log_immutability_guard();
```

The trigger guards the immutable columns at the database level — a compromised application credential cannot rewrite history. The row hash is HSM-signed at write time. Tamper-evidence is bidirectional: row-hash mismatch on read is logged + paged.

### Redis schema for L5 session memory

```
# Key pattern: ps:session:{spiffe_id}:{session_id}
# Value: JSON-encoded session state, TTL: 8 hours absolute, 30-minute idle
# Read access: ONLY the layer-5 service; never read across sessions.

Key:    ps:session:spiffe://bank.com/rm-copilot/sa-prod:sess_a8f3b21
Value:  {
          "spiffe_id": "spiffe://bank.com/rm-copilot/sa-prod",
          "user_id_hash": "sha256:a3f7...",
          "session_id": "sess_a8f3b21",
          "created_at": "2026-05-12T13:21:08Z",
          "last_seen_at": "2026-05-12T14:45:33Z",
          "request_count": 47,
          "kv_cache_pointer": "redis:cache:sess_a8f3b21",
          "tool_invocation_log": [...]
        }
TTL:    28800  # 8 hours absolute
ACL:    promptshield-l5-sa:RW; everyone-else:DENIED
```

Cross-session reads are physically impossible — the L5 service rejects any read where the requesting principal's `spiffe_id` does not match the key's `spiffe_id`. The TTL is enforced by Redis. The audit-log of every L5 read is written to ClickHouse for the forensic trail.

### Six-deficiency → defense-layer mapping (threat model)

The table that compiles the defense contract. Every cell maps a deficiency class to the layer that defends it and the secondary control.

| # | Deficiency | Primary layer | Catch action | Secondary control | Failure mode if primary misses |
| --- | --- | --- | --- | --- | --- |
| 1 | Direct injection in user input | L1 Input classifier | Llama Guard 3 scores user prompt; refuse on score > threshold | L4 (catches if model leaks system prompt in response) | If both miss: classifier-pin verifier alerts on the regression next cycle |
| 2 | Indirect injection in retrieved docs | L2 Retrieval scanner | Same classifier on every retrieved RAG chunk before model sees it | L3 (catches if model attempts the embedded tool call), L4 (catches embedded URL in response) | Three layers must miss; very low probability |
| 3 | Tool-call abuse | L3 Tool-call gate | OPA / Rego evaluates every tool invocation against the bank's allow-list | L1 (catches the user-input variant), L4 (catches response leak) | Three layers must miss |
| 4 | Egress channel | L4 Egress filter | DLP regex pack on response; refuse on PII / known-bad URL / markdown pixel | L1 (catches the user-input variant that asks for the exfil vector) | Two layers must miss |
| 5 | Cross-session leak | L5 Session memory boundary | SPIFFE-keyed isolation; cross-session prompts physically cannot read another's state | L1 (catches the user-prompt variant) | Two layers must miss |
| 6 | Jailbreak via role-play | L1 Input classifier | Same classifier — generalizes past hand-tuned regex to the long tail | L4 (catches if jailbroken model emits PII in response) | Two layers must miss |

### ClickHouse schema (observability time-series)

```sql
CREATE TABLE layer_telemetry (
    layer            LowCardinality(String),                   -- L1 / L2 / L3 / L4 / L5
    copilot_id       LowCardinality(String),
    fired_at         DateTime64(3, 'UTC'),
    inference_ms     UInt32,
    fired            UInt8,
    classifier_score Float32,                                  -- 0.0-1.0
    matched_pattern  String,
    attack_class     LowCardinality(String),
    region           LowCardinality(String)
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/layer_telemetry', '{replica}')
PARTITION BY toYYYYMM(fired_at)
ORDER BY (fired_at, layer)
TTL fired_at + INTERVAL 730 DAY DELETE;   -- 2 years hot, archive to GCS thereafter
```

### Retention & data classification

| Data class | Retention | Storage | Justification |
| --- | --- | --- | --- |
| `attack_log` rows | 7 years (10 years for EU) | Postgres hot for 12 months; archive to GCS Object Lock after | SR 11-7, EU AI Act Article 12 alignment |
| Per-layer telemetry | 2 years hot | ClickHouse; aggregate longer history archived | Operational + drift detection |
| Redis session state | 8 hours absolute / 30 min idle | Memorystore / ElastiCache | Operational; session memory only |
| Classifier corpus snapshots | 7 years | GCS Object Lock | Reproducibility — every catch must be re-explainable from the corpus that was deployed at the time |
| OPA bundle history | 7 years | Git + GCS Object Lock | Reproducibility of every block / allow decision |
| Audit log on `attack_log` reads | 7 years | Postgres partitioned + GCS Object Lock | Audit-on-audit |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with envelope encryption. Customer-Managed Encryption Keys (CMEK / CMK) in Cloud KMS / AWS KMS / Azure Key Vault. Bank's key rotation policy applies (typically 90 days). Keys are region-scoped.
- **In transit.** TLS 1.3 minimum north-south. mTLS on east-west via service mesh.
- **Field-level.** `user_id_hash` is SHA-256 with a KMS-managed pepper. Raw user / customer IDs never touch PromptShield storage.
- **Row-level hash.** Every `attack_log` row has a `row_hash` signed by an HSM-backed code-signing key. Tamper detection.
- **Database-level.** Cloud SQL TDE on PostgreSQL; ClickHouse encrypted-disk; Redis AUTH + TLS + encryption-at-rest.

### Secrets management

- **Primary store.** HashiCorp Vault or Cloud Secret Manager.
- **Application secrets** fetched at boot via Workload Identity Federation. No env-var secrets in container manifests. Rotation: 90 days, zero-downtime via dual-credential rolling.
- **Service account keys.** None. [Workload Identity (GCP)](https://cloud.google.com/iam/docs/workload-identity-federation) / [IRSA (AWS)](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) / [Managed Identity (Azure)](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/overview).
- **Row-hash signing key.** HSM-backed (Cloud HSM / CloudHSM / Azure Dedicated HSM).
- **OPA bundle signing.** Cosign-signed; deploy gate verifies signature before activation.

### Identity provider & user management

- **IdP.** Whatever the bank already runs — Okta, Microsoft Entra ID, or Ping Identity. SAML 2.0 + OIDC.
- **MFA.** Required by bank policy. Enforced at the IdP.
- **Sessions.** OIDC ID token + signed session cookie (HttpOnly, Secure, SameSite=Strict). 8-hour absolute expiry, 30-minute idle timeout. Aligned with the L5 session-memory TTL.
- **Service-to-service identity.** [SPIFFE IDs](https://spiffe.io/). Each component has a unique workload identity. mTLS enforces identity at every hop. L5 session-memory keys are scoped by SPIFFE ID.

### RBAC matrix

Four roles, scoped per region:

| Role | Permissions | Maps to (bank role) |
| --- | --- | --- |
| `ps:viewer` | Read per-layer fire-rate dashboards; no policy edit | Exec read-only, board reporting |
| `ps:analyst` | `viewer` + read `attack_log`; can pull samples but not edit policy | Security analyst, SOC operator |
| `ps:policy_admin` | `analyst` + edit OPA bundles, edit L1/L2 classifier thresholds, edit L4 regex pack | Senior security engineer, AI Platform admin |
| `ps:ciso_admin` | Full config, role management, integration config, KMS key rotation | CISO + delegate |

Authorization implemented via Open Policy Agent (OPA) + Rego policies. Every API call evaluates policy at the gateway. Every decision logged to the audit log.

### Network controls

- **Perimeter.** [VPC Service Controls (GCP)](https://cloud.google.com/vpc-service-controls) / AWS PrivateLink + Network Firewall / Azure Private Endpoints. Egress to public internet only via Secure Web Proxy with allow-list.
- **Lateral.** Cloud NGFW / AWS Security Groups + Network ACLs / Azure NSGs. Layer-7 inspection on the service mesh.
- **Ingress.** Cloud Armor / AWS WAF / Azure WAF with OWASP CRS + custom rules for the API surface.
- **Zero-trust.** All inter-service calls authenticated via SPIFFE mTLS. No "trusted internal network" assumption.

### Threat model — what we explicitly defend against

| Threat | Mitigation |
| --- | --- |
| **Direct prompt injection** ([OWASP LLM01](https://genai.owasp.org/llm-top-10/)) | L1 input classifier |
| **Indirect prompt injection** ([OWASP LLM01](https://genai.owasp.org/llm-top-10/), [MITRE ATLAS AML.T0051](https://atlas.mitre.org/)) | L2 retrieval scanner |
| **Tool-call abuse** ([OWASP LLM07](https://genai.owasp.org/llm-top-10/) Insecure Plugin Design + [MITRE ATLAS AML.T0048](https://atlas.mitre.org/)) | L3 tool-call gate (OPA) |
| **Egress / exfil** ([OWASP LLM06](https://genai.owasp.org/llm-top-10/) Sensitive Information Disclosure) | L4 egress filter (DLP) |
| **Cross-session leakage** ([OWASP LLM06](https://genai.owasp.org/llm-top-10/), insider threat) | L5 SPIFFE-keyed session boundary |
| **Jailbreak / role-play** ([OWASP LLM01](https://genai.owasp.org/llm-top-10/)) | L1 input classifier (long-tail generalization) |
| Compromised API token | Short-lived tokens, mTLS service-to-service, IdP-side revocation propagates <=5 min |
| Insider — analyst pulls all `attack_log` rows | RBAC limits analyst to time-windowed sample queries; bulk export blocked |
| Compromised `attack_log` row (poisoning) | Row-hash HSM-signed at write; immutability trigger; periodic re-verification job |
| Vendor classifier silent update | Classifier-pin tracked per row; daily diff job; auto-rollback on catch-rate regression. Interlocks with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) v0.5 |
| Database exfiltration via SQL injection | Parameterized queries only; ORM-only (SQLAlchemy + Pydantic) at the API boundary; Cloud Armor WAF rule set |
| Egress data exfiltration | VPC Service Controls + Secure Web Proxy allow-list |
| Tampering with immutable history | Database trigger denies UPDATE/DELETE on immutable fields; row-hash mismatch detection job runs nightly |
| OPA bundle tampering | Cosign-signed bundles; deploy gate verifies signature; Argo CD distribution is itself audited |

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs | Cloud Logging + Datadog / CloudWatch / Azure Monitor | Existing SOC pane |
| Distributed traces | Cloud Trace + OpenTelemetry → Datadog APM | Per-request layer-trace |
| Metrics | Prometheus + Grafana (or Datadog metrics) | RED-method per service |
| Per-layer fire-rate time-series | ClickHouse `layer_telemetry` | Layer-specific dashboards |
| LLM-specific traces | [Langfuse](https://langfuse.com/) (self-hosted) for the LLM call lineage | Only for the GenAI-decision path |
| Audit log | Postgres `audit_log` + GCS Object Lock | Long retention |

### Alerting

| Severity | Channel | SLO |
| --- | --- | --- |
| P1 (any layer down >2 min in any region) | PagerDuty primary + secondary, Slack #promptshield-incident | Acknowledge <=5 min |
| P1 (catch_rate drops below 96% on the rolling-24h red-team probe) | PagerDuty (security on-call), Slack | Acknowledge <=15 min |
| P2 (FP rate spikes above 6% on the rolling-1h legitimate traffic) | PagerDuty (lower urgency), Slack | Acknowledge <=30 min |
| P2 (classifier inference P99 > 200ms) | PagerDuty, Slack | Acknowledge <=30 min |
| P3 (OPA bundle deploy failed) | Slack only | Triaged next business day |
| P4 (informational — daily red-team probe summary) | Daily digest email | None |

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to GCS / S3. Daily snapshots, 35-day retention. Point-in-time recovery within retention window.
- **ClickHouse.** Weekly backup to GCS / S3. ReplicatedMergeTree gives HA within region.
- **Redis.** Multi-AZ replication. Snapshots every 6h. Note: session memory is ephemeral by design; a Redis loss is a session reset, not data loss.
- **Object stores.** Object Lock + versioning + cross-region replication for the `attack_log` WORM archive (within the same regulatory region only — never US ↔ EU).
- **DR drill cadence.** Quarterly. Full failover to US-West; validate RTO 30min / RPO 5min for the `attack_log` table; fail back. Runbook in `docs/runbooks/dr-failover.md`.

### Runbooks (one paragraph each in the repo)

- `dr-failover.md` — full region failover
- `l1-down.md` — when the L1 classifier service is unavailable
- `catch-rate-regression.md` — when the rolling-24h catch rate drops below SLO
- `fp-rate-spike.md` — when the rolling-1h FP rate spikes above SLO
- `opa-bundle-rollback.md` — when a freshly-deployed OPA bundle causes a regression
- `red-team-probe-run.md` — quarterly red-team probe execution
- `classifier-retraining.md` — quarterly classifier retraining cycle
- `legal-hold-cascade.md` — applying legal hold on `attack_log` rows when litigation opens

---

## 6. Compliance posture

| Framework | Posture |
| --- | --- |
| **SOC 2 Type II** | All six components in scope. Annual external audit. |
| **PCI-DSS** | In scope when the underlying copilot touches cardholder data. PromptShield itself does not process card data; it scans for cards in egress. PCI scope minimization via `user_id_hash` + KMS pepper. |
| **GLBA Safeguards Rule** | Customer financial data handled with field-level hashing + access controls + audit trail. Right-to-be-forgotten cascades to lineage records via `user_id_hash` deletion (with legal-hold override). |
| **[OWASP LLM Top 10](https://genai.owasp.org/llm-top-10/)** | LLM01 (Prompt Injection), LLM06 (Sensitive Information Disclosure), LLM07 (Insecure Plugin Design) directly addressed by L1-L5. |
| **[MITRE ATLAS](https://atlas.mitre.org/)** | Calibrated against the published attacker-techniques catalog. Quarterly probe runs use ATLAS technique IDs. |
| **[NIST AI RMF 1.0](https://www.nist.gov/itl/ai-risk-management-framework)** | PromptShield is the implementation surface for the framework's "Map" (threat-model the deployed copilots), "Measure" (catch rate / FP rate metrics), and "Manage" (continuous red-team + classifier retraining) functions. |
| **[EU AI Act (Regulation 2024/1689)](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)** | EU instance enforces data residency. The `attack_log` is the record-keeping artifact for high-risk AI systems (internal BFSI copilots qualify under Annex III). |
| **GDPR** | EU instance enforces data residency. Right-to-erasure cascades to `user_id_hash` deletion with legal-hold override. DPO sign-off documented per region. |
| **India RBI data localization** | Indian retail-arm copilots run on the India regional instance only. No cross-border replication. |
| **[Google SAIF](https://safety.google/cybersecurity-advancements/saif/)** | Model controls (L1, L2), agent controls (L3, L5), supply-chain controls (classifier-pin verifier). |

---

## 7. What is deliberately not here

- **A custom foundation model.** We sit in front of the bank's existing vendor stack (Anthropic, Azure OpenAI, Bedrock, internal Llama). We do not host the LLM.
- **A custom retrieval / vector store.** We scan retrieved chunks; we do not store them.
- **A custom feature store / model registry.** Out of scope.
- **A customer-facing safety layer.** Different threat model (public abuse, not insider exfil). Different product.
- **A standalone authentication system.** We integrate with the bank's IdP.
- **A replacement for Bedrock Guardrails / Azure Prompt Shields / Google Model Armor.** We sit on top, adding BFSI-specific corpus + policy + tool-registry knowledge.

That last list is the discipline. Every internal-build I have watched die has died on scope creep into one of those.

---

## Appendix A — sample API contract

```python
# POST /v1/scan
# Auth: OIDC bearer; role: ps:viewer or higher; mTLS for service-to-service
# Body:
{
    "request_id": "req_a8f3b21",
    "session_id": "sess_a8f3b21",
    "user_id_hash": "sha256:a3f7...",
    "spiffe_id": "spiffe://bank.com/rm-copilot/sa-prod",
    "copilot_id": "rm_copilot",
    "user_prompt": "Summarize CUST_851897's wealth portfolio across all asset classes.",
    "retrieved_chunks": [
        {"chunk_id": "doc_disclosure_v4_1#p3", "text": "..."},
        {"chunk_id": "doc_rate_card_2026q2#p1", "text": "..."}
    ],
    "intended_tool_calls": [
        {"tool_name": "export_pdf", "args": {...}}
    ]
}

# Response 200:
{
    "overall_action": "BLOCK",
    "blocked_at_layer": "L2_retrieval_scanner",
    "attack_class_predicted": "indirect_injection",
    "matched_pattern": "AI ASSISTANT INSTRUCTION + 'forward to' detected",
    "classifier_confidence": 0.94,
    "layer_trace": [
        {"layer": "L1", "fired": false, "latency_ms": 78, "score": 0.04},
        {"layer": "L2", "fired": true,  "latency_ms": 92, "score": 0.94, "evidence_hash": "sha256:..."},
        {"layer": "L3", "fired": false, "latency_ms": 1,  "reason": "not_evaluated"},
        {"layer": "L4", "fired": false, "latency_ms": 0,  "reason": "no_response"},
        {"layer": "L5", "fired": false, "latency_ms": 1}
    ],
    "log_id": "ee5f8c1a-...",
    "composed_at": "2026-05-12T13:45:33.092Z",
    "composition_ms": 172.7
}
```

OpenAPI spec lives at `apps/api/openapi.yaml` and is the source of truth for the SDK clients.

## Appendix B — sample OPA policy (L3 tool-call gate)

```rego
package promptshield.tools.send_email

import future.keywords.if
import future.keywords.in

default allow := false

# Allow when destination is an internal bank domain AND request comes from
# a copilot's authorized SPIFFE ID.
allow if {
    is_internal_recipient(input.args.to)
    valid_copilot_principal(input.spiffe_id)
    not is_bulk_send(input.args)
}

is_internal_recipient(to) if {
    endswith(lower(to), "@bank.com")
}
is_internal_recipient(to) if {
    endswith(lower(to), "@securemail.bank.com")
}

valid_copilot_principal(spiffe) if {
    startswith(spiffe, "spiffe://bank.com/rm-copilot/")
}
valid_copilot_principal(spiffe) if {
    startswith(spiffe, "spiffe://bank.com/kyc-copilot/")
}

is_bulk_send(args) if {
    count(args.to_list) > 5
}

# Audit every decision.
decision := {
    "allow": allow,
    "matched_rule": (
        if allow then "send_email.allow.internal"
        else "send_email.deny.default"
    ),
    "evaluated_at": time.now_ns()
}
```

Bundle distribution: signed-via-Cosign, distributed by Argo CD, hot-reloaded by the L3 service without restart.
