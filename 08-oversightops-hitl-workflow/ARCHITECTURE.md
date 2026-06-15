# Architecture — OversightOps

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network topology, operational runbooks. What you would hand to your CISO, your platform engineering lead, and your reviewer-operations director on day one.

This doc is cloud-agnostic where the design allows it and explicit where it does not. Primary stack shown on Google Cloud because the design aligns directly with the *Building secure multi-agent systems on Google Cloud* reference paper (Kannan, Sizemore, Herriford et al., 2025); AWS and Azure equivalents are called out inline.

---

## 1. Logical architecture

OversightOps is a **routing and calibration layer**, not a BPM platform. It does not own case storage; it composes routing decisions on top of the bank's existing case-management workflow (Pega / Appian / ServiceNow). Six components, each independently deployable.

| Component | Responsibility | Language / framework | Stateful? |
| --- | --- | --- | --- |
| `oversightops-api` | REST + gRPC API. Auth, RBAC, case ingestion, queue claim, decision write. | Python 3.11 + FastAPI + Pydantic v2 | No |
| `oversightops-router` | Difficulty router + escalation rules. Receives "flag for review" event; routes to tier queue. | Python + Cloud Functions / Lambda | No (commits offsets) |
| `oversightops-blocker` | Rubber-stamp blocker. Validates time-to-decision against tier floor; rejects sub-floor; re-queues. | Python + Cloud Functions | No |
| `oversightops-ui` | Reviewer workbench panel. Embedded inside Pega / Appian / ServiceNow as an iframe. Rubric attestation; SLA timer; decision form. | React 19 + Next.js 15 + TypeScript + Tailwind | No |
| `oversightops-drift` | Daily / weekly calibration drift detector. Per-reviewer override rate vs cohort. | Python + Airflow / Cloud Composer / MWAA | Stateful (DAG runs) |
| `oversightops-backfill` | Daily ETL from downstream signals (SAR, OFAC, CFPB, charge-off, loss-event lake). | Python + Airflow / Cloud Composer | Stateful (DAG runs) |
| `oversightops-temporal` | SLA timer engagement (8m / 3m / 1m by tier). PagerDuty breach alerts. | Temporal Cloud / Temporal self-hosted | Stateful (timers) |
| `oversightops-cli` | Operator tool — backfill, replay, ad-hoc calibration packet, queue-depth dump. | Python + Click | No |

All components are stateless except the drift / backfill schedulers (Airflow DAGs) and the SLA timers (Temporal). State lives in the data layer. Stateless components scale horizontally.

**Repo structure** (monorepo via Bazel or pnpm workspaces):

```
oversightops/
├── apps/
│   ├── api/             # FastAPI service
│   ├── router/          # Cloud Functions difficulty router
│   ├── blocker/         # Cloud Functions rubber-stamp blocker
│   ├── ui/              # Next.js reviewer panel
│   ├── drift/           # Airflow drift detector
│   ├── backfill/        # Airflow ground-truth ETL
│   ├── temporal/        # Temporal workers for SLA timers
│   └── cli/             # Click CLI
├── packages/
│   ├── domain/          # Shared domain models (proto + codegen TS/Python)
│   ├── auth/            # Shared OIDC/SAML libs
│   ├── routing/         # Difficulty-router + blocker logic (the product opinion)
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
    ├── integration/     # uses fake BPM
    └── load/            # k6 / locust against the router
```

---

## 2. Physical / deployment architecture

### Runtime

**Primary on GCP (matches the Google Cloud reference architecture):**

| Component | Runtime | Why |
| --- | --- | --- |
| `api` | Cloud Run (managed) | Stateless HTTP, autoscale 0-N, request-based billing |
| `router` | Cloud Functions gen 2 on Pub/Sub | Event-driven, autoscaling, no idle cost |
| `blocker` | Cloud Functions gen 2 | Triggered on reviewer-decision-submit |
| `ui` | Cloud Run | Static + SSR Next.js, embedded as iframe in BPM |
| `drift` | Cloud Composer 3 (managed Airflow) | Daily DAGs; existing skill set in BFSI ops |
| `backfill` | Cloud Composer 3 | Daily ETL DAGs |
| `temporal` | Temporal Cloud (managed) | Battle-tested for long-running workflows with timers |
| `cli` | Local + Cloud Build for CI runs | Operator tool, not a service |

**AWS equivalent:** ECS Fargate or EKS for `api`/`ui`; Lambda + EventBridge for `router` and `blocker`; MWAA for `drift` and `backfill`; Step Functions or Temporal on EKS for `temporal`.

**Azure equivalent:** Container Apps for `api`/`ui`; Functions + Event Grid for `router` and `blocker`; Data Factory or Airflow on AKS for `drift` and `backfill`; Durable Functions or Temporal on AKS for `temporal`.

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
[Private subnet — router, blocker, drift, backfill, temporal]
   │
   ├──► [PostgreSQL — Cloud SQL / RDS]                 (private endpoint only)
   ├──► [ClickHouse — Aiven / Altinity managed]        (private endpoint)
   ├──► [Snowflake / Databricks]                       (PrivateLink / PSC)
   ├──► [Redis — Memorystore / ElastiCache]            (private endpoint)
   ├──► [GCS Object Lock / S3 Object Lock]             (private endpoint)
   └──► [Temporal Cloud]                               (private link)

Egress to BPM API (Pega / Appian / ServiceNow):
   [Secure Web Proxy / Squid] — allow-list of BPM URLs only
   [VPC Service Controls / Network Firewall] — data exfiltration prevention
```

### Region & DR

- **Primary:** US-East (us-east1 GCP / us-east-1 AWS / East US Azure)
- **DR:** US-West (us-west1 / us-west-2 / West US 2). Active-passive. RTO 4h, RPO 5min for the `oversight_decisions` table.
- **EU instance:** Frankfurt (europe-west3 / eu-central-1 / Germany West Central). Required for EU AI Act Article 14 and GDPR — oversight records of EU customers cannot egress region.
- **India instance:** Mumbai (asia-south1 / ap-south-1 / Central India). Required for RBI data localization on Indian retail arms.
- Each regional instance has its own database, KMS key ring, IAP, Temporal namespace. **No cross-region replication for the `oversight_decisions` table** — each region is sovereign for its own oversight evidence. The WORM archive replicates cross-region within the same regulatory boundary only.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** (Cloud SQL / RDS) | `oversight_decisions` immutable table, queue claim state, calibration drift snapshots, legal-hold flags. | Relational integrity, joins, mature transactions, well-understood by BFSI ops. Append-only via insert-only role + trigger guard. |
| **Temporal Cloud** | SLA timers; long-running review workflow state. | Mature long-running ops primitives; PagerDuty integration native; saves us from rebuilding the timer engine. |
| **ClickHouse** (Aiven / Altinity managed) | High-cardinality observability — reviewer throughput, SLA breach time-series, drift signal series. | 10-50x cheaper than Postgres for time-series at this volume. Interlocks with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) for shared drift-signal querying. |
| **Snowflake / Databricks** (read-only) | Downstream signals (SAR system, OFAC list, CFPB system, charge-off log, loss-event lake). | Already exists at every Tier-1 BFSI shop. We don't introduce a third lake. |
| **Redis** (Memorystore / ElastiCache) | Session cache (UI), idempotency keys (router), queue depth counters. | TTL-based eviction. Multi-AZ for HA. |
| **GCS / S3 / Blob Storage with Object Lock** | **WORM archive of oversight records** + calibration packets + cross-region replication. | Object Lock = WORM for the SR 11-7 / EU AI Act seven-year retention. |
| **Pub/Sub / Kinesis / Event Hubs** | "Case flagged for review" event spine; queue-claim event; decision-submit event. | Native to the cloud; ordered delivery within a partition; replay-able. |

### The oversight-decision table

The consequential schema. Every reviewer decision under OversightOps produces one row:

```sql
-- Append-only. Immutability enforced via insert-only role + DENY on UPDATE/DELETE
-- to anyone except the legal-hold service account (which can flag, not modify).
-- Partitioned by month for retention cycling and reviewer-quality queries.

CREATE TABLE oversight_decisions (
    -- Identity
    decision_id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id                       TEXT NOT NULL,
    customer_id_hash              TEXT NOT NULL,            -- SHA-256 with KMS-managed pepper
    case_ingested_at              TIMESTAMPTZ NOT NULL,
    case_workflow                 TEXT NOT NULL,            -- kyc_review / dispute / fraud_step_up / claims_siu / credit_waterfall

    -- Routing signal (deficiency #1, #4)
    ai_confidence                 NUMERIC(4,3) NOT NULL,
    ai_decision                   TEXT NOT NULL,
    difficulty_score              SMALLINT NOT NULL,
    customer_tier                 TEXT NOT NULL,            -- private_banking / sme / retail
    country_risk_tier             SMALLINT NOT NULL,
    routed_to_queue               TEXT NOT NULL,            -- lead / senior / junior
    routing_rule_version          TEXT NOT NULL,            -- audit trail of which routing rule fired
    escalation_triggered          BOOLEAN NOT NULL DEFAULT FALSE,
    escalation_reason             TEXT,

    -- Reviewer attribution + SLA (deficiency #5)
    reviewer_id                   TEXT NOT NULL,
    reviewer_tenure               TEXT NOT NULL,
    reviewer_training_level       TEXT NOT NULL,
    sla_floor_sec                 INTEGER NOT NULL,
    sla_target_sec                INTEGER NOT NULL,
    time_to_decision_sec          NUMERIC(8,2) NOT NULL,
    sla_breach                    BOOLEAN NOT NULL,
    rubric_attestation            JSONB NOT NULL,           -- {item_id: checked_bool, ...} per the tier-specific rubric

    -- Rubber-stamp blocker (deficiency #3)
    rubber_stamp_blocked          BOOLEAN NOT NULL,
    rubber_stamp_re_queued_to     TEXT,                     -- the higher-tier queue if blocked
    rubber_stamp_re_queue_at      TIMESTAMPTZ,

    -- Calibration drift snapshot at time of decision (deficiency #2)
    cohort_override_rate          NUMERIC(4,3) NOT NULL,
    reviewer_override_rate        NUMERIC(4,3) NOT NULL,
    drift_sigma                   NUMERIC(4,2),
    drift_flagged                 BOOLEAN NOT NULL DEFAULT FALSE,

    -- Ground-truth backfill (deficiency #6, mutable until backfill closes)
    ground_truth_outcome          TEXT,
    downstream_signal             TEXT,                     -- regulatory_finding_ofac_match / sar_filed_later / customer_complaint_cfpb / charge_off_30d / fraud_loss / regulatory_finding_aml
    backfill_observed_at          DATE,
    modeled_loss_usd              NUMERIC(14,2),
    reviewer_was_wrong            BOOLEAN,

    -- Cross-references to source systems
    bpm_case_ref                  TEXT NOT NULL,            -- Pega / Appian / ServiceNow case ID
    ai_decision_log_ref           TEXT NOT NULL,            -- LineageLog decision_id (when interlocked)
    temporal_workflow_id          TEXT NOT NULL,

    -- Immutability + retention
    composed_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    row_hash                      TEXT NOT NULL,            -- HSM-signed
    retention_until               TIMESTAMPTZ NOT NULL      -- case_ingested_at + 7 years
) PARTITION BY RANGE (case_ingested_at);

CREATE INDEX idx_oversight_reviewer ON oversight_decisions (reviewer_id, case_ingested_at);
CREATE INDEX idx_oversight_workflow ON oversight_decisions (case_workflow, customer_tier);
CREATE INDEX idx_oversight_sla_breach ON oversight_decisions (sla_breach) WHERE sla_breach = TRUE;
CREATE INDEX idx_oversight_rubber_blocked ON oversight_decisions (rubber_stamp_blocked) WHERE rubber_stamp_blocked = TRUE;
```

The immutability trigger:

```sql
CREATE OR REPLACE FUNCTION oversight_immutability_guard()
RETURNS TRIGGER AS $$
BEGIN
    -- Only the legal_hold + backfill service accounts can update specific columns
    IF current_user NOT IN ('legal_hold_sa', 'backfill_sa', 'drift_sa') THEN
        RAISE EXCEPTION 'oversight_decisions is append-only';
    END IF;

    -- Even those accounts can only update a defined column subset
    IF current_user = 'backfill_sa' THEN
        IF NEW.case_id != OLD.case_id OR NEW.reviewer_id != OLD.reviewer_id THEN
            RAISE EXCEPTION 'backfill_sa cannot modify identity fields';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER oversight_immutability_trigger
BEFORE UPDATE OR DELETE ON oversight_decisions
FOR EACH ROW EXECUTE FUNCTION oversight_immutability_guard();
```

### Calibration drift table (snapshot every Sunday 02:00 UTC)

```sql
CREATE TABLE reviewer_calibration_snapshots (
    snapshot_id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_at                   TIMESTAMPTZ NOT NULL,
    reviewer_id                   TEXT NOT NULL,
    cohort_mean_override_rate     NUMERIC(4,3) NOT NULL,
    cohort_sd_override_rate       NUMERIC(4,3) NOT NULL,
    reviewer_override_rate        NUMERIC(4,3) NOT NULL,
    reviewer_n_cases              INTEGER NOT NULL,
    drift_sigma                   NUMERIC(4,2) NOT NULL,
    drift_flagged                 BOOLEAN NOT NULL,
    drift_packet_emitted          BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (snapshot_at, reviewer_id)
);
```

---

## 4. Security architecture

- **Encryption:** TLS 1.3 in transit; KMS-backed AES-256 at rest on Postgres + GCS Object Lock + ClickHouse. The `customer_id_hash` column uses SHA-256 + KMS-managed pepper.
- **RBAC:** OIDC role mapping `oo:reviewer_junior` → `oo:reviewer_senior` → `oo:reviewer_lead` → `oo:queue_admin` → `oo:compliance` → `oo:cro` → `oo:admin`. Each role's permissions defined in OPA bundles.
- **Service account model:** Workload identity federation (no long-lived JSON keys). Per-component service account: `router-sa`, `blocker-sa`, `drift-sa`, `backfill-sa`, `temporal-sa`, `legal_hold_sa`. Cross-component calls via SPIFFE-identified mTLS.
- **Threat model:** Reviewer tries to clear queue depth by bulk-approving — caught at the rubber-stamp blocker. Reviewer tries to game calibration drift by patterned overrides — caught by the ground-truth feedback loop on the 6-12-month tail. Insider tries to modify a decision after the fact — caught by the immutability trigger + row_hash chain.
- **Audit:** Every read of an oversight record produces an audit-on-audit log row (Cloud Audit Logs / CloudTrail). Internal Audit (L3) has read access to the audit-on-audit feed.

---

## 5. Operational architecture

### SLOs

| SLO | Target |
| --- | --- |
| Router decision latency p95 | < 200ms |
| Blocker decision latency p95 | < 50ms |
| Case-to-queue end-to-end p95 (AI flag → reviewer claim possible) | < 5s |
| Tier-1 SLA breach rate | < 5% |
| Calibration drift detector daily DAG runtime | < 30min |
| Ground-truth backfill daily DAG runtime | < 90min |
| Reviewer UI page load p95 | < 1.5s |

### Runbooks

Each runbook is a one-page Markdown file in `docs/runbooks/`:

- `runbook_router_down.md` — what to do when the router stops emitting routing decisions
- `runbook_temporal_timer_storm.md` — what to do when the SLA-timer queue backs up
- `runbook_blocker_false_positive.md` — what to do when the blocker rejects a legitimate review
- `runbook_drift_detector_skew.md` — what to do when the drift detector flags >50% of reviewers
- `runbook_backfill_stale.md` — what to do when ground-truth ETL is >24h late

### Alerting

PagerDuty integration:

- **P1 (page on-call):** Router down for >5min; Postgres write failure for >2min; ≥10 SLA breaches in 5min on Tier-1.
- **P2 (Slack):** Blocker rejecting >20% of incoming Tier-1 reviews (likely calibration issue); drift detector skipped a daily run.
- **P3 (email):** Single reviewer flagged at ≥ 2 sigma for 3 consecutive weeks (route to Reviewer Ops).

---

## 6. Integration with the bank's existing substrate

OversightOps integrates with three substrate vendors per workflow:

| Vendor class | Examples | Integration point |
| --- | --- | --- |
| BPM platform | Pega, Appian, ServiceNow Workflow | OversightOps UI iframe embedded in the case-handling screen; BPM remains the system of record; OversightOps writes back the decision + rubric attestation to the BPM case payload. |
| MRM workbench | Archer, ServiceNow GRC, MetricStream | Push `oversight_decision_id` to the workbench's attestation cycle; bidirectional sync on legal-hold state. |
| AI platform | Vertex AI, Bedrock, Azure AI Studio, internal model registry | Subscribe to the model's "flag for review" event topic; read AI confidence + decision from the model's response payload. |

The BPM remains the system of record. OversightOps is the routing + blocker + calibration + feedback layer that sits in front of the BPM's reviewer-workbench surface.

---

## 7. Interlocks with the rest of the portfolio

- **[LineageLog](../09-lineagelog-ai-decision-audit/)** — every OversightOps decision writes its `decision_id` into the LineageLog decision record (deficiency #5 of LineageLog: reviewer attribution). When the regulator asks "who reviewed this AI decision?", LineageLog returns OversightOps's record; OversightOps returns the routing rationale + rubric.
- **[DriftSentinel](../02-driftsentinel-model-drift-monitoring/)** — reviewer-vs-AI agreement rate at the workflow level is a model-quality signal; DriftSentinel ingests it as one of its three loops.
- **[AgentWatch](../05-agentwatch-agent-observability/)** — the ADK `require_human_approval` primitive emits to OversightOps when the gate is engaged in a multi-agent workflow.

---

*This is the systems doc for a portfolio prototype. The production version of this would have a separate threat-model doc, a separate data-flow diagram per regulatory regime (US OCC + EU AI Act + RBI), and a separate disaster-recovery runbook. Those are scoped post-engagement.*
