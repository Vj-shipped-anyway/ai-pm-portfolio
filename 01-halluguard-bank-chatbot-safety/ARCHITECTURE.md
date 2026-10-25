# Architecture — HalluGuard

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO and your platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (mock chatbot responses, fixed mock verifier scores, a Streamlit app). Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. Most banks run on AWS, GCP, or Azure (or two of three). GCP is shown as primary; AWS and Azure equivalents are called out inline.

![HalluGuard flow](./assets/halluguard-flow.svg)

---

## 1. Logical architecture

HalluGuard is a containment layer. It does not replace the chatbot, the retriever, or the foundation model. It sits between the chatbot's draft answer and the customer and decides one thing: ship, or abstain.

Eight components. Four are in the customer's request path; four are not.

| Component | Responsibility | Language / framework | In request path? | Stateful? |
| --- | --- | --- | --- | --- |
| `hg-gateway` | Receives `(question, retrieved_rows, draft)` from the chatbot, calls verifier and calibrator, returns the final text. Fails closed on error. | Python 3.11, FastAPI, Pydantic v2 | Yes, sync | No |
| `hg-verifier` | Scores how well the draft is grounded in the retrieved rows. | LoRA-fine-tuned Llama 3.1 8B served with vLLM on 2x L4 GPUs | Yes, sync | No (read-only model artifacts) |
| `hg-calibrator` | Maps a verifier score to ship or abstain using a per-use-case threshold (design values: 0.82 for rates and regulation, 0.65 for general). | Python; config in Postgres, cached in Redis | Yes, sync | No |
| `hg-abstainer` | Replaces a blocked draft with the abstention message and the banker handoff payload. | Python | Yes, sync | No |
| `hg-probe-runner` | Nightly regression run of the probe set against the pinned vendor snapshot. Writes pass/fail per failure mode. | Python on Airflow / Cloud Composer / MWAA | No, async | Stateful (DAG runs) |
| `hg-vendor-pin` | Pins `model_id + snapshot_date` at the gateway; a daily diff job flags when a vendor snapshot changes. | Python on Cloud Functions / Lambda | No, async | No |
| `hg-console` | Line-2 review console: abstention queue, threshold history, probe trends. Embeds in the MRM workbench. | React + Next.js + Tailwind | No | No |
| `hg-telemetry` | OpenTelemetry spans from gateway, verifier, and calibrator, exported off the request path. | OTel Collector to Langfuse, Datadog, ClickHouse | No, async | No |

**What is in the customer's request path, and what is not.** Only the gateway, verifier, calibrator, and abstainer. Telemetry, probes, vendor-pin diffing, and the console are out of band. A 5 ms add-on in the request path multiplies across every chat turn at peak, so nothing that can be async is sync.

**Repo structure** (production shape; monorepo via Bazel or Pants, or pnpm workspaces if the org is JS-comfortable):

```
halluguard/
├── apps/
│   ├── gateway/        # FastAPI: verify, decide, abstain
│   ├── verifier/       # vLLM serving config + model card
│   ├── probe-runner/   # nightly DAG
│   ├── vendor-pin/     # snapshot pin + diff job
│   └── console/        # review UI
├── training/
│   ├── data/           # labeled (question, rows, answer, label) triples
│   ├── lora/           # fine-tune configs, eval harness
│   └── distill/        # DeBERTa distillation (next)
├── probes/             # failure-mode probe sets, versioned (this repo ships 3 sample files)
├── infra/
│   ├── terraform/      # multi-cloud IaC (gcp, aws, azure)
│   ├── kubernetes/     # Helm charts + Kustomize overlays
│   └── policies/       # OPA bundles, IAM templates, network policies
├── docs/
│   ├── ARCHITECTURE.md
│   ├── runbooks/
│   └── api/            # OpenAPI spec
└── tests/
    ├── unit/
    ├── integration/
    └── load/           # k6 / locust
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `hg-gateway` | GKE, same cluster as the chatbot | EKS | AKS | Co-locate with the chatbot so the extra hop stays on the cluster network |
| `hg-verifier` | GKE GPU node pool, 2x L4, vLLM, autoscale on QPS | EKS GPU nodes (g6) | AKS GPU node pool (pick the closest current SKU, then re-size batch settings) | Small model, GPU-served; scale on queue depth and keep a warm minimum |
| `hg-probe-runner` | Cloud Composer | MWAA | Data Factory or Airflow on AKS | Existing skill set in most BFSI ops teams |
| `hg-vendor-pin` | Cloud Functions gen 2 | Lambda + EventBridge | Functions + Event Grid | Small scheduled job |
| `hg-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI |

**Failure behavior (the decision that matters most).** The gateway fails closed. If the verifier times out, errors, or is unreachable, the customer gets the abstention message, not the unverified draft. That trades availability of direct answers for safety, the right default for rate, fee, and regulation questions. It is configurable per use case, and any fail-open setting needs a named owner and a line-2 sign-off.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Verifier timeout or 5xx | Abstain, hand to banker | P2 if error rate is above threshold for 5 min |
| Calibrator config unreadable | Use last cached thresholds; if none, abstain | P2 |
| Vendor snapshot changed vs pin | Keep serving the pinned snapshot, open a drift event, run the probe set immediately | P3; P2 if probes regress |
| Probe-runner DAG fails | Serving unaffected; yesterday's result stays the baseline | P3 |
| Telemetry sink down | Buffer locally, drop with a counter once the buffer fills | P4 |

**Latency.** The verifier forward pass is the only new cost in the customer's wait. The budget has to be set against the chatbot's turn SLA, and it has not been measured in this repo. Two levers if it is too slow: batch scoring on the GPU, and distill the verifier to a DeBERTa-class model (listed under "what's next" in the README).

### Network topology

```
Customer channel (web / app / chat widget)
   │
   ▼
[Cloud Armor / AWS WAF / Azure Front Door WAF]        (the chatbot's existing front door)
   │
   ▼
[Existing chatbot service] ── retrieval ──► [Postgres + pgvector knowledge base]
   │   sends (question, retrieved rows, draft)
   ▼   mTLS via service mesh (Istio / Cloud Service Mesh)
[hg-gateway]   ← only caller allowed: the chatbot service identity
   │
   ├──► [hg-verifier, GPU node pool]        (cluster-internal, no ingress from outside)
   ├──► [hg-calibrator] ──► [PostgreSQL: thresholds]  /  [Redis: cache]   (private endpoints)
   └──► async: [OTel Collector] ──► Langfuse / Datadog / ClickHouse

Out of band:
   [hg-probe-runner] ──► chatbot test endpoint ──► vendor APIs
        egress only via [Secure Web Proxy] with an allow-list of vendor URLs
        [VPC Service Controls / Network Firewall] for data-exfiltration prevention
```

### Region & DR

- Primary and DR regions follow the chatbot's own footprint. HalluGuard does not get a different recovery objective than the system it protects.
- Region-specific instances where data residency applies (EU, India). Each has its own database and key ring; there is no cross-region replication of customer text.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15 + pgvector** | Thresholds, verification decisions, abstentions, probe results, vendor snapshots, audit log. pgvector also backs the chatbot's retrieval index in the reference design. | Relational integrity for the audit trail; the bank's ops team already runs it |
| **ClickHouse** | Per-decision verifier scores and drift time series | High-volume, append-only, queried by date range |
| **Redis** | Threshold cache, idempotency keys, rate limits | TTL eviction handles cleanup |
| **Object storage with Object Lock (WORM)** | Archived decision records and probe-run artifacts | Write-once-read-many for the record-keeping policy |

### PostgreSQL schema (the consequential tables)

```sql
-- One row per chatbot answer that passed through the gateway
CREATE TABLE verification_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_hash    TEXT NOT NULL,          -- hashed, never the raw customer id
    use_case        TEXT NOT NULL,          -- rates / fees / eligibility / regulation / general
    verifier_score  NUMERIC(4,3) NOT NULL,
    threshold       NUMERIC(4,3) NOT NULL,
    decision        TEXT NOT NULL,          -- SHIP / ABSTAIN / ABSTAIN_ON_ERROR
    vendor_model    TEXT NOT NULL,
    snapshot_id     TEXT NOT NULL,          -- the pinned snapshot in force
    prompt_sha256   TEXT NOT NULL,          -- hash of question+rows+draft, not the text
    trace_id        TEXT NOT NULL
);

CREATE TABLE thresholds (
    use_case        TEXT NOT NULL,
    threshold       NUMERIC(4,3) NOT NULL,
    effective_from  TIMESTAMPTZ NOT NULL,
    set_by          TEXT NOT NULL,          -- user_id
    approved_by     TEXT NOT NULL,          -- line-2 approver
    reason          TEXT NOT NULL,
    PRIMARY KEY (use_case, effective_from)  -- append-only: a change is a new row
);

CREATE TABLE probe_runs (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ran_at          TIMESTAMPTZ NOT NULL,
    snapshot_id     TEXT NOT NULL,
    failure_mode    TEXT NOT NULL,          -- one of the failure classes
    n_probes        INT NOT NULL,
    n_passed        INT NOT NULL,
    baseline_passed INT NOT NULL,
    verdict         TEXT NOT NULL           -- PASS / REGRESSION
);

CREATE TABLE vendor_snapshots (
    snapshot_id        TEXT PRIMARY KEY,
    vendor             TEXT NOT NULL,       -- anthropic / azure_openai / bedrock
    first_observed_at  TIMESTAMPTZ NOT NULL,
    announced          BOOLEAN NOT NULL,
    probe_verdict      TEXT
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
    result          TEXT NOT NULL           -- success / failure / forbidden
) PARTITION BY RANGE (occurred_at);
```

**Raw customer text.** The design stores a hash of `(question, rows, draft)` and the decision, not the conversation. Where Compliance needs the text to adjudicate a complaint, it is fetched from the chatbot's own conversation store by `trace_id`, under that system's retention and access rules. HalluGuard does not become a second copy of customer conversations.

### ClickHouse schema (the time-series tables)

```sql
CREATE TABLE verifier_scores (
    use_case        LowCardinality(String),
    observed_at     DateTime64(3, 'UTC'),
    verifier_score  Float32,
    threshold       Float32,
    decision        LowCardinality(String),
    snapshot_id     LowCardinality(String),
    region          LowCardinality(String)
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/verifier_scores', '{replica}')
PARTITION BY toYYYYMM(observed_at)
ORDER BY (use_case, observed_at)
TTL observed_at + INTERVAL 730 DAY DELETE;  -- 2-year hot retention, matching the table below
```

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-retention schedule before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Verification events (hashed ids, scores, decisions) | 7 years | Postgres hot for 90 days, then archive to Object Lock | Confidential, no raw PII |
| Threshold changes and approvals | Life of the model plus 7 years | Postgres, append-only | Internal |
| Probe runs and vendor snapshots | 7 years | Postgres, archive to Object Lock | Internal |
| Verifier score time series | 2 years hot | ClickHouse | Internal |
| Audit log | 7 years | Postgres partitioned, archive to Object Lock | Confidential |
| Customer conversation text | Not stored by HalluGuard | The chatbot's conversation store | Governed by that system |
| Session and cache data | TTL, hours | Redis | Internal |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with customer-managed keys (CMEK / CMK) in Cloud KMS, AWS KMS, or Azure Key Vault, one key ring per region. Keys never cross a region boundary.
- **In transit.** TLS 1.3 north-south. mTLS east-west through the service mesh.
- **Field-level.** Customer identifiers are hashed before any HalluGuard write. The training and labeling pipeline scrubs PII first (Microsoft Presidio, as noted in the README acknowledgements).
- **Database-level.** Transparent data encryption on PostgreSQL, encrypted disks on ClickHouse, encryption at rest on Redis.

### Secrets management

- **Primary store.** HashiCorp Vault or the cloud secret manager. No long-lived static credentials.
- **Application secrets** (database passwords, vendor API keys): fetched at boot through workload identity, rotated on the bank's schedule with dual-credential rolling.
- **Service-account keys.** None. Workload Identity on GCP, IAM Roles for Service Accounts on AWS, Managed Identity on Azure.
- **Model artifacts.** The verifier is signed and checksum-verified at load.

### Identity provider & user management

- **IdP.** Whatever the bank already runs (Okta, Microsoft Entra ID, Ping). SAML 2.0 and OIDC. HalluGuard does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Sessions.** OIDC ID token plus signed session cookie (HttpOnly, Secure, SameSite=Strict), with absolute and idle expiry set by bank policy.
- **Service-to-service identity.** SPIFFE IDs; each component has its own workload identity and mTLS enforces it at every hop.

### RBAC matrix

Authorization is enforced at the gateway with OPA, and every decision is written to `audit_log`.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `hg:viewer` | Read decisions, probe trends | Audit, executives |
| `hg:chatbot-owner` | Viewer + propose threshold changes | Line-1 chatbot product owner |
| `hg:validator` | Viewer + approve threshold changes + review abstention samples | Line-2 model risk |
| `hg:admin` | Config, integrations, role management | Platform engineering lead |

A threshold change needs a proposer and a different approver. Both are recorded in `thresholds`.

### Network controls

- **Perimeter.** VPC Service Controls (GCP), PrivateLink plus Network Firewall (AWS), or Private Endpoints (Azure). Egress to the public internet only through a Secure Web Proxy with an allow-list of vendor URLs.
- **Lateral.** Network policies and layer-7 inspection on the service mesh; the verifier accepts calls only from the gateway identity.
- **Ingress.** HalluGuard has no public ingress. Its only caller is the chatbot service; the console sits behind the bank's SSO.
- **Zero-trust.** Every inter-service call is authenticated. No "trusted internal network" assumption.

### Threat model

| Threat | Mitigation |
| --- | --- |
| Customer text steers the verifier (prompt injection in the question) | Verifier input is framed as data to score, never as instructions, and it emits a score, not free text, so there is nothing to hijack into an answer. Layered with [PromptShield](../06-promptshield-prompt-injection-defense/) at the chatbot edge. |
| Poisoned or stale retrieval rows make a wrong draft look grounded | HalluGuard checks the draft against the rows, so it cannot detect a wrong row. Mitigation sits upstream: rate and fee tables load from the system of record with an effective-date check, and the time-staleness probes run nightly. |
| Threshold quietly lowered to cut abstentions | Append-only `thresholds` with proposer and approver; weekly report of abstention rate beside incident rate |
| Silent vendor model update | Snapshot pinned at the gateway; daily diff; nightly probe run |
| Verifier model drift or tampering | Signed artifact, checksum at load; the verifier's own held-out set is re-scored on every release |
| Over-abstention erodes the chatbot's value | Abstention rate is a first-class SLO with an owner (see operations) |

---

## 4a. APIs consumed and exposed

HalluGuard is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Foundation-model vendors (Anthropic, Azure OpenAI, Bedrock) | REST, key from Vault or managed identity | Used by the **chatbot** and by the probe runner, not by the verifier | Chatbot's own fallback; probe run skipped and alerted |
| Bank IdP (Okta / Entra / Ping) | SAML 2.0 + OIDC | Console login, role lookup | Existing sessions continue |
| MRM workbench (Archer / ServiceNow GRC / MetricStream) | Vendor REST, service principal | File an abstention disposition and threshold-change records | Local audit trail continues; sync resumes later |
| Datadog / Langfuse | HTTPS, key from Vault | Metrics and LLM traces | Local buffer |
| PagerDuty / Slack | REST / webhook | Alert routing | Email fallback |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/verify` | OpenAPI 3.1 over HTTPS, mTLS service identity | The chatbot service |
| Console API | OIDC bearer, role-checked by OPA | `hg-console`, MRM workbench iframe |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Incident management, Compliance dashboard |

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** The surface is one decision endpoint and a console. OpenAPI generates the chatbot-side client and the console SDK from one spec.
- **Idempotency key on `verify`.** A retried call must not double-count in the abstention-rate SLO. UUID v4 in the `Idempotency-Key` header, Redis-backed dedupe.
- **The response carries the reason, not just the verdict.** `decision`, `verifier_score`, `threshold`, and `snapshot_id` come back every time, so a reviewer can reconstruct why an answer was blocked.
- **Webhooks are signed, not just authenticated.** HMAC-SHA256 with a per-consumer rotating secret.
- **No customer identifiers in URLs.** Session ids are hashes; raw ids never appear.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry to Datadog | The SOC's existing pane |
| LLM-specific traces (verifier inputs and outputs, scores) | Langfuse, self-hosted | Needed to debug a single blocked answer |
| Score and drift time series | ClickHouse | High-cardinality, append-only |
| Audit log | Postgres, archived to Object Lock | Record-keeping |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **Abstention rate** by use case | The cost side of containment. Too high and the bot stops being useful. |
| **Wrong answers served** (Compliance incidents plus sampled review) | The benefit side. Read it beside abstention rate; either alone misleads. |
| **Verifier error and timeout rate** | Drives fail-closed abstentions |
| **Nightly probe pass rate** per failure mode | The early warning for vendor changes |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P1 | Probe regression on rates or regulation plus a live spike in wrong-answer reports | PagerDuty |
| P2 | Verifier error rate above threshold; probe regression on any mode | PagerDuty (low urgency) + Slack |
| P3 | Vendor snapshot change; abstention-rate drift | Slack |
| P4 | Daily digest | Email |

### Rollout

Shadow first: score and log, serve the draft unchanged, so the abstention rate and false-abstention rate are known before anyone is affected. Then canary 1% to 10% to 50% to 100%, with automatic rollback on probe regression. This is a design; the PRD holds the phase plan.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **ClickHouse.** Weekly backup to object storage; replicated engine for HA inside a region.
- **Object stores.** Object Lock and versioning for archived decisions and probe artifacts.
- **Verifier artifacts.** Versioned in the model registry; the previous version stays deployable for rollback.
- **DR drill cadence.** Quarterly failover to the secondary region, validated against the chatbot's own recovery objective.

### Runbooks (planned; one page each, in `docs/runbooks/` of the production repo)

- `vendor-snapshot-changed.md` — the daily diff flagged a new snapshot
- `verifier-degraded.md` — error or timeout rate above threshold
- `threshold-change.md` — propose, approve, and roll back a threshold
- `abstention-rate-spike.md` — when handoffs jump
- `complaint-evidence-pull.md` — pull the decision record for a complaint by `trace_id`

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against.

| Framework | How the design relates |
| --- | --- |
| **SR 11-7 / model risk management** | HalluGuard is a model in its own right (the verifier) and a control over another model (the chatbot). Both need inventory entries, validation, and ongoing monitoring; the probe runner is the monitoring. |
| **Reg DD / Truth in Savings** | The citation-fabrication and rate probes exist because a wrong APY or an invented regulation in a chatbot answer is a disclosure problem, not just a quality problem. |
| **UDAAP** | An abstention is an honest non-answer; a confident wrong fee is the exposure. |
| **OWASP LLM Top 10, LLM09 (Misinformation)** | The canonical framing for the failure modes. |
| **NIST AI RMF** | The Measure and Manage functions map to probes and thresholds. |
| **SOC 2 Type II, GDPR, India data localization** | Regional instances, hashed identifiers, append-only audit. |

---

## 7. What's deliberately not here

- **A new chatbot or a new retriever.** HalluGuard wraps what exists; InfoSec does not re-audit the bot.
- **Retraining of the foundation model.** The README's three-model comparison is the argument: swapping models moves each failure mode by 8 to 16 points of pass rate and leaves confident-and-wrong at 33% to 41% (stored values, not run in this repo).
- **A claim that it detects wrong source data.** It checks the draft against the rows it was given. Bad rows are a data-quality problem upstream.
- **Auto-lowering of thresholds.** Thresholds change by one person's proposal and a different person's approval.
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each one is already owned by another system.

---

## Appendix — sample API contract

```python
# POST /v1/verify
# Auth: mTLS service identity (chatbot service)
# Header: Idempotency-Key: <uuid>
{
    "use_case": "fees",
    "question": "Does Premier Checking have a monthly fee?",
    "retrieved": [
        {"source": "fees.csv", "row": "PCK | monthly maintenance | 0.00 | no minimum balance"}
    ],
    "draft": "Yes, the monthly fee on Premier Checking is $12.",
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
}
# Response 200
{
    "decision": "ABSTAIN",
    "verifier_score": 0.31,
    "threshold": 0.65,
    "final_text": "I'm not certain on this one. Let me get a banker for you who can confirm the details.",
    "snapshot_id": "pinned-2026-04-01",
    "event_id": "c1a7f0de-..."
}
```

The score and threshold in the example are the Step 4 values for Q02 (0.31 against 0.65). The snapshot id is illustrative.

OpenAPI spec lives at `apps/gateway/openapi.yaml` and is the source of truth for the chatbot-side client and the console.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/01-halluguard-bank-chatbot-safety/demo.html).
