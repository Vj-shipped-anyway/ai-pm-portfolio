# Architecture — SchemaWatch

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO and your platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (a structural diff, a description heuristic, a strict validator and a gate, over synthetic data, with a Streamlit app). Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. The design assumes the bank runs on AWS, GCP or Azure (or two of three). GCP is shown as primary; AWS and Azure equivalents are called out inline.

![SchemaWatch flow](./assets/schemawatch-flow.svg)

---

## 1. Logical architecture

SchemaWatch is a consumer-side control. It does not replace the tool registry, the tool owners' tests or the agent. It sits between a published schema revision and the agent that will call it, and decides one thing: let the release through, ask a person, or hold it.

Eight components. Four are in the release path; four are not.

| Component | Responsibility | Language / framework | In release path? | Stateful? |
| --- | --- | --- | --- | --- |
| `sw-collector` | Pulls schema revisions from the tool registry on a schedule and on publish events. Writes each as an immutable revision keyed by content hash. | Python 3.11 on Cloud Functions / Lambda / Functions | Yes, async trigger | No |
| `sw-store` | Holds revisions, findings, replay results and decisions. | PostgreSQL 15 | Yes | Stateful |
| `sw-differ` | Structural diff and classifier (breaking, non-breaking, behavior-risk) plus the description heuristic (numbers and units). Emits findings with reasons. | Python; the prototype's `diff_schemas` | Yes, sync | No |
| `sw-replay` | Validates recorded tool calls against the new revision with a strict validator. Returns would-break counts per tool and example calls. | Python workers; the prototype's `strict_validate` | No, async, but the gate waits on it | No |
| `sw-ranker` | Ranks tools by recorded calls broken or flagged as changing meaning. | Python | No, async | No |
| `sw-gate` | Combines findings, replay and ranking into BLOCK, REVIEW or ALLOW with a reason. Exposes the check the owner's pipeline calls and sets the hold state in the registry. | Python, FastAPI, Pydantic v2 | Yes, sync | No |
| `sw-console` | Review console: open decisions, evidence bundles, owner attestations, bypass log. | React + Next.js + Tailwind | No | No |
| `sw-telemetry` | OpenTelemetry spans and metrics from every component, exported off the release path. | OTel Collector to the platform's monitoring | No, async | No |

**What is in the release path, and what is not.** The collector, store, differ and gate decide whether a release proceeds. Everything else supports them or reports on them. The agent's own request path is untouched: SchemaWatch never sits between the agent and a tool at call time. Runtime failure handling stays with AgentWatch.

**Repo structure** (production shape; monorepo):

```
schemawatch/
├── apps/
│   ├── collector/      # poller + publish hook handler
│   ├── differ/         # structural diff, classifier, description heuristic
│   ├── replay/         # strict validator workers
│   ├── gate/           # FastAPI: check endpoint, hold state
│   └── console/        # review UI
├── libs/
│   ├── schema/         # revision model, content hashing
│   └── validator/      # strict validator (types, enums, required, bounds, unknown keys)
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
    └── calibration/    # replay predictions vs real server rejections
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `sw-collector` | Cloud Functions gen 2 + Cloud Scheduler | Lambda + EventBridge | Functions + Event Grid | Small scheduled job plus an event handler |
| `sw-differ` | Cloud Run jobs | ECS Fargate tasks | Container Apps jobs | Stateless, short-lived, bursty |
| `sw-replay` | GKE worker pool, autoscale on queue depth | EKS worker pool | AKS worker pool | CPU-bound over many recorded calls; scale on queue age |
| `sw-gate` | Cloud Run (min instances 1) | ECS Fargate | Container Apps | Stateless API; a warm instance keeps decisions fast |
| `sw-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI |
| `sw-store` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The gate has two modes and the mode is per tool. In advisory mode a gate outage fails open: the owner's pipeline proceeds, the bypass is logged and counted. In blocking mode, used for tools that move money, a gate outage fails closed: the registry publish waits. Any fail-open setting on a blocking tool needs a named owner and a line-2 sign-off. Replay with too few recorded calls, or a schema feature the validator does not support, produces REVIEW and never ALLOW.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Collector misses a publish event | The next poll finds the new content hash; the decision opens late and is marked late | P3 |
| Replay workers down or queue aging | Gate says REVIEW with "replay unavailable"; advisory mode proceeds, blocking mode holds | P2 |
| Too few recorded calls for the tool | REVIEW, reason names the call count | P4 |
| Validator meets an unsupported schema feature | REVIEW, reason names the feature | P3 |
| Store unavailable | Gate fails per its mode; collector buffers revisions locally | P2 |
| Telemetry sink down | Buffer locally, drop with a counter once full | P4 |

**Latency.** The only new wait is the gate's decision inside the owner's pipeline. 🔴 Design target: a decision inside one pipeline step. It has not been measured in this repo. The levers if it is slow: precompute replay for the tool's last known revision, and cap the replay window per tool.

### Network topology

```
Tool owner pipeline / registry publish
   │   publish event (signed webhook) or poll
   ▼
[sw-collector]  ── read-only token ──►  [Tool registry]
   │
   ▼
[PostgreSQL: revisions]  ──►  [sw-differ]  ──►  findings
                                   │
                                   ▼
[Tool-call log (read-only view, tokenized values)] ──►  [sw-replay workers]
                                   │
                                   ▼
                              [sw-ranker] ──► [sw-gate]  ◄── owner pipeline check (mTLS)
                                                  │
                                   ┌──────────────┼───────────────┐
                                   ▼              ▼               ▼
                            registry hold   evidence bundle   OTel Collector ──► monitoring

Out of band:
   [sw-console] behind the bank's SSO  ──►  [sw-gate API] (role-checked by OPA)
   Interlocks: AgentWatch (05), PromptShield (06), LineageLog (09) over service-to-service calls
```

### Region & DR

- Primary and DR regions follow the agent platform's own footprint. SchemaWatch does not get a different recovery objective than the platform whose releases it checks.
- Region-specific instances where data residency applies. Each has its own database and key ring; recorded-call values do not replicate across regions.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | Revisions, findings, decisions, owner attestations, bypass log, audit log | Relational integrity for the audit trail; the platform team already runs it |
| **ClickHouse** (or the platform's columnar store) | Per-call replay results over time | High volume, append-only, queried by tool and date range |
| **Object storage with Object Lock (WORM)** | Evidence bundles and archived decisions | Write-once-read-many for the record-keeping policy |
| **Redis** (optional) | Decision cache for the gate, idempotency keys | TTL eviction handles cleanup |

### PostgreSQL schema (the consequential tables)

```sql
-- One row per immutable schema revision of one tool
CREATE TABLE schema_revisions (
    revision_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_name         TEXT NOT NULL,
    rev_seq           INT NOT NULL,                 -- 1 = the revision agents were built against
    declared_version  TEXT NOT NULL,                -- what the owner published, bumped or not
    content_sha256    TEXT NOT NULL,                -- hash of the canonical schema text
    schema_json       JSONB NOT NULL,
    observed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source            TEXT NOT NULL,                -- publish_hook / poll
    UNIQUE (tool_name, rev_seq),
    UNIQUE (tool_name, content_sha256)
);

-- One row per classified change between two revisions
CREATE TABLE findings (
    finding_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_revision     UUID NOT NULL REFERENCES schema_revisions,
    to_revision       UUID NOT NULL REFERENCES schema_revisions,
    kind              TEXT NOT NULL,                -- param_renamed / required_added / enum_value_removed / ...
    param             TEXT NOT NULL,                -- empty for tool-level description
    class             TEXT NOT NULL,                -- breaking / non_breaking / behavior_risk
    reason            TEXT NOT NULL,                -- the sentence an owner reads
    at_risk_calls     INT NOT NULL DEFAULT 0
);

-- One row per release decision; append-only
CREATE TABLE release_decisions (
    decision_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    to_revision       UUID NOT NULL REFERENCES schema_revisions,
    decided_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decision          TEXT NOT NULL,                -- BLOCK / REVIEW / ALLOW
    replay_calls      INT NOT NULL,
    would_break       INT NOT NULL,
    at_risk           INT NOT NULL,
    mode              TEXT NOT NULL,                -- advisory / blocking
    reason            TEXT NOT NULL,
    evidence_uri      TEXT NOT NULL                 -- the Object Lock bundle
);

-- Owners and reviewers resolve a REVIEW; a change needs a proposer and a different approver
CREATE TABLE decision_resolutions (
    resolution_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id       UUID NOT NULL REFERENCES release_decisions,
    resolved_by       TEXT NOT NULL,
    approved_by       TEXT NOT NULL,
    outcome           TEXT NOT NULL,                -- fix_agreed / cosmetic_confirmed / overridden
    attestation       TEXT NOT NULL,                -- "this release changes what a parameter means: yes/no"
    reason            TEXT NOT NULL,
    resolved_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
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

**Recorded calls.** Replay needs each argument's type and, for enum fields, its value. It does not need free text. The design tokenizes free-text and identifier values before they reach the replay store and keeps enum, boolean and numeric values as they are. Where a reviewer needs the original call to adjudicate, it is fetched from the agent platform's own tool-call log by `call_id`, under that system's retention and access rules. SchemaWatch does not become a second copy of customer data.

### ClickHouse schema (the time-series tables)

```sql
CREATE TABLE replay_results (
    tool_name       LowCardinality(String),
    to_revision     UUID,
    replayed_at     DateTime64(3, 'UTC'),
    call_id         String,
    would_break     UInt8,
    first_violation LowCardinality(String),   -- unknown_parameter / missing_required / enum_violation / type_mismatch
    at_risk         UInt8
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/replay_results', '{replica}')
PARTITION BY toYYYYMM(replayed_at)
ORDER BY (tool_name, replayed_at)
TTL replayed_at + INTERVAL 730 DAY DELETE;  -- 2-year hot retention, matching the table below
```

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-retention schedule before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Schema revisions and findings | Life of the tool plus 7 years | Postgres, archive to Object Lock | Internal |
| Release decisions and resolutions | 7 years | Postgres, archive to Object Lock | Confidential |
| Evidence bundles | 7 years | Object storage with Object Lock | Confidential |
| Replay results (tokenized) | 2 years hot | ClickHouse | Internal |
| Recorded call values | Not stored by SchemaWatch beyond tokenized replay fields | The agent platform's tool-call log | Governed by that system |
| Audit log | 7 years | Postgres partitioned, archive to Object Lock | Confidential |
| Decision cache | TTL, hours | Redis | Internal |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with customer-managed keys (CMEK / CMK) in Cloud KMS, AWS KMS or Azure Key Vault, one key ring per region. Keys never cross a region boundary.
- **In transit.** TLS 1.3 north-south. mTLS east-west through the service mesh.
- **Field-level.** Identifier and free-text argument values are tokenized before the replay store; the token key is separate from the data key.
- **Database-level.** Transparent data encryption on PostgreSQL, encrypted disks on ClickHouse, encryption at rest on Redis.

### Secrets management

- **Primary store.** HashiCorp Vault or the cloud secret manager. No long-lived static credentials.
- **Application secrets** (registry read token, webhook signing secret, database passwords): fetched at boot through workload identity, rotated on the bank's schedule with dual-credential rolling.
- **Service-account keys.** None. Workload Identity on GCP, IAM Roles for Service Accounts on AWS, Managed Identity on Azure.
- **Webhook secrets.** Per-registry signing secret, rotated; the collector verifies the signature before it fetches anything.

### Identity provider & user management

- **IdP.** Whatever the bank already runs (Okta, Microsoft Entra ID, Ping). SAML 2.0 and OIDC. SchemaWatch does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Sessions.** OIDC ID token plus signed session cookie (HttpOnly, Secure, SameSite=Strict), with absolute and idle expiry set by bank policy.
- **Service-to-service identity.** SPIFFE IDs; each component has its own workload identity and mTLS enforces it at every hop.

### RBAC matrix

Authorization is enforced at the gate API with OPA, and every decision is written to `audit_log`.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `sw:viewer` | Read decisions, findings and trends | Audit, executives |
| `sw:owner` | Viewer + read evidence for their own tools, attest and propose a resolution | Tool (API) owner |
| `sw:platform` | Owner rights across tools + configure gate mode per tool, manage the call-log feed | Agent platform lead |
| `sw:validator` | Viewer + approve a resolution that overrides a BLOCK | Line-2 model risk |
| `sw:admin` | Config, integrations, role management | Platform engineering lead |

A resolution that overrides a BLOCK needs a proposer and a different approver. Both are recorded in `decision_resolutions`.

### Network controls

- **Perimeter.** VPC Service Controls (GCP), PrivateLink plus Network Firewall (AWS) or Private Endpoints (Azure). No public ingress for the gate; the collector reaches only the registry endpoints on an allow-list.
- **Lateral.** Network policies and layer-7 inspection on the service mesh; replay workers read the tool-call log through a read-only view and can reach nothing else.
- **Ingress.** The gate is called by owner pipelines over mTLS; the console sits behind the bank's SSO.
- **Zero-trust.** Every inter-service call is authenticated. No "trusted internal network" assumption.

### Threat model

| Threat | Mitigation |
| --- | --- |
| A malicious or careless schema description tries to steer a model or a reviewer (instructions hidden in a description) | Descriptions are treated as data. The heuristic extracts numbers and units with fixed rules and never passes description text to a model. Descriptions render escaped in the console. See also [PromptShield](../06-promptshield-prompt-injection-defense/) for the tool-call side. |
| Owner deploys around the registry, so no revision event fires | The poller compares content hashes on every pass and opens a late decision; the late-detection count and bypass count are first-class metrics. |
| Replay store becomes a second copy of customer data | Tokenize identifiers and free text; keep only types and enum values; fetch originals from the tool-call log by `call_id`. |
| Gate decision quietly overridden | Append-only `decision_resolutions` with proposer and approver; weekly report of overrides beside incident rate. |
| Heuristic gives false confidence on a meaning change | The gate output states what it cannot see; owner attestation is required on REVIEW and BLOCK; description diffs on money-moving tools get a human read. |
| Stale or thin call log makes replay look clean | Minimum recorded calls per tool; below it the gate says REVIEW. |

---

## 4a. APIs consumed and exposed

SchemaWatch is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Tool registry | REST or event stream, read-only token from Vault | Fetch schema revisions; subscribe to publish events | Poller continues; late detection is flagged |
| Tool-call log (agent platform) | Read-only view, workload identity | Recorded arguments for replay, by tool and window | Replay unavailable: gate says REVIEW or holds per mode |
| Bank IdP (Okta / Entra / Ping) | SAML 2.0 + OIDC | Console login, role lookup | Existing sessions continue |
| Model-risk record (GRC tool) | Vendor REST, service principal | File decisions and evidence bundles | Local audit trail continues; sync resumes later |
| Monitoring (OpenTelemetry to the platform's stack) | OTLP over TLS | Metrics and traces | Local buffer |
| Paging and chat | REST / webhook | Alert routing | Email fallback |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/releases/check` | OpenAPI 3.1 over HTTPS, mTLS service identity | Tool owners' pipelines |
| `GET /v1/tools/{tool}/status` | mTLS service identity | AgentWatch (05), PromptShield (06) |
| `GET /v1/revisions/{hash}` | mTLS service identity | LineageLog (09) |
| Console API | OIDC bearer, role-checked by OPA | `sw-console` |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Incident management, model-risk record |

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** The surface is one decision endpoint, one status endpoint and a console. OpenAPI generates the owner-pipeline client and the console SDK from one spec.
- **Idempotency key on `check`.** A retried pipeline step must not open a second decision. UUID v4 in the `Idempotency-Key` header.
- **The response carries the reason, not just the verdict.** `decision`, the findings with their classes and reasons, the would-break count and example calls come back every time, so an owner can fix the release without a meeting.
- **Status is cheap and cacheable.** Runtime consumers ask "is there an open BLOCK or REVIEW for this tool" many times; the answer is a small document with a TTL.
- **Webhooks are signed, not just authenticated.** HMAC-SHA256 with a per-consumer rotating secret.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry into the platform's existing monitoring | The SRE's existing pane |
| Gate decisions over time | ClickHouse + dashboards | BLOCK, REVIEW and ALLOW rates per tool and owner |
| Replay queue age and worker health | Metrics | Drives the fail-open or fail-closed behavior |
| Audit log | Postgres, archived to Object Lock | Record-keeping |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **Releases with a decision before reaching the agent** | The north star. Everything else supports it. |
| **Late detections and bypasses** | The cost of owners who deploy around the registry |
| **False REVIEW rate** | The cost side of the gate. Too high and owners stop trusting it. |
| **Replay coverage** (tools with at least the minimum recorded calls) | Replay on a thin log is worse than no replay |
| **Gate decision latency** | 🔴 Design target is one pipeline step; not measured |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P1 | A BLOCK on a money-moving tool whose release already reached production (bypass) | Paging |
| P2 | Replay unavailable or queue aging; store unavailable | Paging (low urgency) + chat |
| P3 | Late detection; unsupported schema feature; collector missed a publish | Chat |
| P4 | Thin call log; daily digest | Email |

### Rollout

Shadow first: collect and classify, show nothing to owners, and compare the classifier's output with what actually broke. Then replay, then an advisory gate, then blocking for money-moving tools, as laid out in the PRD. Automatic rollback of a gate mode if the false REVIEW rate breaches its threshold.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **ClickHouse.** Weekly backup to object storage; replicated engine for HA inside a region.
- **Object stores.** Object Lock and versioning for evidence bundles and archived decisions.
- **Revisions.** Immutable by design; any revision can be re-fetched from the registry and re-hashed.
- **DR drill cadence.** Quarterly failover to the secondary region, validated against the agent platform's own recovery objective.

### Runbooks (one page each, in `docs/runbooks/`)

- `release-blocked.md` — a BLOCK landed: read the findings, find the example calls, contact the owner
- `review-resolution.md` — resolve a REVIEW: attest, approve, record
- `late-detection.md` — the poller found a revision with no publish event
- `replay-degraded.md` — queue aging or call-log feed down
- `heuristic-miss.md` — a meaning change shipped that the heuristic did not flag: add the case to the ledger
- `evidence-pull.md` — pull the decision and the revision hash for a tool call by `call_id`

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against.

| Framework | How the design relates |
| --- | --- |
| **SR 11-7 / model risk management** | A tool whose meaning changes under a deployed agent is a change to a component the model's output depends on. The decision log and evidence bundles are the ongoing-monitoring record for that dependency. |
| **NIST AI RMF** | The Measure and Manage functions map to replay, classification and the gate. |
| **EU AI Act, Article 12 record-keeping** | The revision-hash stamp on the decision lineage record (LineageLog interlock) is the record-keeping hook the design is written toward. This is not a claim that the Act applies or that the design meets it. |
| **OWASP LLM Top 10, excessive agency** | Treating tool schemas as a controlled interface limits what an agent can be made to do by an uncontrolled change. |
| **SOC 2 Type II, GDPR, India data localization** | Regional instances, tokenized call values, append-only audit. |

---

## 7. What's deliberately not here

- **A runtime proxy between the agent and its tools.** SchemaWatch decides at release time. Runtime failure handling is AgentWatch; the tool-call gate is PromptShield.
- **A replacement for the owners' own tests.** Owners know their API's behavior; SchemaWatch knows what the agent sends.
- **A claim that it detects every semantic change.** It reads numbers and units. Meaning changes with no number or unit are a known limit, covered by owner attestation and human review.
- **Constraint changes and nested schemas in v1.** The diff does not compare minimum, maximum, maxLength or pattern. The validator does not support pattern, nested objects or oneOf. Unsupported features produce REVIEW, not ALLOW.
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each one is already owned by another system or another phase.

---

## Appendix — sample API contract

```python
# POST /v1/releases/check
# Auth: mTLS service identity (owner pipeline)
# Header: Idempotency-Key: <uuid>
{
    "tool": "get_transaction_history",
    "from_revision": "v1",
    "to_revision": "v2",
    "declared_version": "1.3.0"
}
# Response 200
{
    "decision": "BLOCK",
    "mode": "advisory",
    "replay": {"calls": 295, "would_break": 143, "at_risk": 72},
    "findings": [
        {"kind": "param_renamed", "param": "limit", "class": "breaking",
         "reason": "`limit` is gone and `page_size` appears with the same type and description. Any call that still sends `limit` is rejected."},
        {"kind": "default_changed", "param": "txn_type", "class": "behavior_risk",
         "reason": "default of `txn_type` changed from \"all\" to \"debit\". Calls that omit it get the new value and still pass validation."}
    ],
    "evidence_uri": "object-lock://schemawatch/evidence/...",
    "decision_id": "c1a7f0de-..."
}
```

The counts, the findings and the reasons in the example are the prototype's `step_04` output for `get_transaction_history` release v2 on the synthetic data. The URI and ids are illustrative.

OpenAPI spec lives at `docs/api/openapi.yaml` and is the source of truth for the owner-pipeline client and the console.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/15-schemawatch-tool-schema-drift/demo.html).
