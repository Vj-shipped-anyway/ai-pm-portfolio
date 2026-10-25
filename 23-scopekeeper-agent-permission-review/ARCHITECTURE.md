# Architecture — ScopeKeeper

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO and your platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (a usage-versus-grant diff, a proposal rule, a dry-run replay and a risk ranking, over synthetic data, with a Streamlit app). Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. GCP is shown as primary; AWS and Azure equivalents are called out inline.

![ScopeKeeper flow](./assets/scopekeeper-flow.svg)

---

## 1. Logical architecture

ScopeKeeper is a review control. It does not replace the grant store, the access-governance workflow or the tool-call gate. It reads what each agent may do and what it did, and proposes one thing: a smaller scope set, to be approved by a person before anything changes.

Nine components. Three are in the change path; six are not.

| Component | Responsibility | Language / framework | In change path? | Stateful? |
| --- | --- | --- | --- | --- |
| `sk-collector` | Snapshots grants nightly and reads the tool-call log through a read-only view. Writes daily usage facts: counts per agent, service account, scope and day. No call arguments. | Python 3.11 on Cloud Functions / Lambda / Functions | No, async | No |
| `sk-store` | Holds grant snapshots, proposals, decisions, attestations and the audit log. Usage history sits in the columnar store. | PostgreSQL 15 | Yes | Stateful |
| `sk-differ` | Usage-versus-grant diff with wildcard expansion and conservative crediting of untagged calls. Emits per-grant usage and the breadth score. | Python; the prototype's `usage_index` and `grant_usage` | No, async | No |
| `sk-proposer` | Builds the smallest scope set that covers every logged call: keep, remove, narrow a wildcard, each with a reason. | Python; the prototype's `propose` | No, async | No |
| `sk-replay` | Replays the logged calls under the proposed set and returns the denied-call count and examples. | Python workers; the prototype's `replay_calls` | No, async, but review waits on it | No |
| `sk-ranker` | Ranks agents by impact-weighted unused access, unapproved calls and shared accounts. | Python | No, async | No |
| `sk-review` | The queue and API: owner attestation, a separate approver for high-impact scopes, and the hook that applies an approved change in the grant store. | Python, FastAPI, Pydantic v2 | Yes, sync | No |
| `sk-console` | Review console: open proposals, usage next to each line, replay results, attestation answers. | React + Next.js + Tailwind | Yes | No |
| `sk-telemetry` | OpenTelemetry spans and metrics from every component, exported off the change path. | OTel Collector to the platform's monitoring | No, async | No |

**What is in the change path, and what is not.** The store, the review service and the console decide whether a grant changes. Everything else prepares or reports. The agent's own request path is untouched: ScopeKeeper never sits between the agent and a tool at call time. The tool-call gate stays with PromptShield.

**Repo structure** (production shape; monorepo):

```
scopekeeper/
├── apps/
│   ├── collector/      # grant snapshots + call-log reader
│   ├── differ/         # usage-versus-grant diff, breadth score
│   ├── proposer/       # keep / remove / narrow rule
│   ├── replay/         # dry-run workers
│   ├── review/         # FastAPI: queue, attestation, apply hook
│   └── console/        # review UI
├── libs/
│   ├── catalog/        # scope catalog, wildcard expansion
│   └── attribution/    # tag handling, shared-account crediting
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
    └── calibration/    # proposals vs what owners approve and what later fails
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `sk-collector` | Cloud Functions gen 2 + Cloud Scheduler | Lambda + EventBridge | Functions + Event Grid | Small nightly job |
| `sk-differ`, `sk-proposer` | Cloud Run jobs | ECS Fargate tasks | Container Apps jobs | Stateless, short-lived, bursty |
| `sk-replay` | GKE worker pool, autoscale on queue depth | EKS worker pool | AKS worker pool | CPU-bound over many logged calls; scale on queue age |
| `sk-ranker` | Cloud Run jobs | ECS Fargate tasks | Container Apps jobs | Small and batch |
| `sk-review` | Cloud Run (min instances 1) | ECS Fargate | Container Apps | Stateless API; a warm instance keeps the queue responsive |
| `sk-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI |
| `sk-store` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** A removal is the risky action, so the system fails closed on changes and open on reporting. If the review service, the store or the replay workers are down, nothing is applied and no proposal is marked approved. If the call-log feed is missing a day, the diff marks that agent's window incomplete and proposes nothing for it. If an agent has fewer calls than the minimum, the proposal is withheld and the grant list stays with the ordinary review.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Call-log feed missing a day | Window marked incomplete for affected agents; no proposal | P3 |
| Replay workers down or queue aging | Proposals wait; nothing is applied | P2 |
| Agent tag missing on a shared account | Credit every agent that could have made the call; report the count per account | P4 |
| Store unavailable | Review API refuses writes; collector buffers snapshots locally | P2 |
| Apply hook fails after an approval | The approval stays recorded; the change is retried and the failure is alerted | P2 |
| Telemetry sink down | Buffer locally, drop with a counter once full | P4 |

**Latency.** There is no call-time wait. The review cycle is nightly collection, a diff and proposal, and a queue. 🔴 Design target: proposals ready by the next business day after the run. It has not been measured in this repo. The levers if it is slow: precompute usage facts incrementally, and replay only the agents whose grants or usage changed.

### Network topology

```
Agent platform grant store (read-only)      Tool-call log (read-only view, counts only)
   │                                           │
   ▼                                           ▼
[sk-collector] ───────────────►  [PostgreSQL: snapshots, usage facts]
                                              │
                                              ▼
                      [sk-differ] ──► [sk-proposer] ──► [sk-replay workers]
                                              │                 │
                                              ▼                 ▼
                                         [sk-ranker] ──► [sk-review]  ◄── owner and approver (OIDC)
                                                              │
                                   ┌──────────────────────────┼───────────────────────┐
                                   ▼                          ▼                       ▼
                         grant store apply hook        evidence bundle        OTel Collector ──► monitoring

Out of band:
   [sk-console] behind the bank's SSO  ──►  [sk-review API] (role-checked by OPA)
   Interlocks: AgentWatch (05), PromptShield (06), OversightOps (08), SchemaWatch (15) over service-to-service calls; ControlMap (16), ShadowScan (22) and KillSwitch (25) as drawn in the README
```

### Region & DR

- Primary and DR regions follow the agent platform's own footprint. ScopeKeeper does not get a different recovery objective than the platform whose agents it reviews.
- Region-specific instances where data residency applies. Each has its own database and key ring; usage facts do not replicate across regions.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | Grant snapshots, proposals, decisions, attestations, audit log | Relational integrity for the audit trail; the platform team already runs it |
| **ClickHouse** (or the platform's columnar store) | Usage history (counts per day, account, scope and agent tag), replay results | High volume, append-only, queried by agent and date range |
| **Object storage with Object Lock (WORM)** | Evidence bundles and archived decisions | Write-once-read-many for the record-keeping policy |
| **Redis** (optional) | Queue cache, idempotency keys | TTL eviction handles cleanup |

### PostgreSQL schema (the consequential tables)

```sql
-- One row per grant per nightly snapshot; partitioned by month, the partition key is in the primary key
CREATE TABLE grant_snapshots (
    snapshot_date   DATE NOT NULL,
    agent_id        TEXT NOT NULL,
    scope           TEXT NOT NULL,                 -- specific, or namespace:* for a wildcard
    granted_on      DATE NOT NULL,
    ticket_id       TEXT,                          -- null when the grant has no ticket
    PRIMARY KEY (snapshot_date, agent_id, scope)
) PARTITION BY RANGE (snapshot_date);

-- One row per agent per review run
CREATE TABLE proposals (
    proposal_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        TEXT NOT NULL,
    window_start    DATE NOT NULL,
    window_end      DATE NOT NULL,
    reach_before    INT NOT NULL,
    reach_after     INT NOT NULL,
    replay_calls    INT NOT NULL,
    replay_denied   INT NOT NULL,
    risk_points     INT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One row per grant in a proposal
CREATE TABLE proposal_items (
    item_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id     UUID NOT NULL REFERENCES proposals,
    scope           TEXT NOT NULL,
    action          TEXT NOT NULL,                 -- keep / remove / narrow
    replace_with    TEXT[],                        -- scopes a wildcard is narrowed to
    reason          TEXT NOT NULL,
    calls_tagged    INT NOT NULL,
    calls_credited  INT NOT NULL                   -- untagged calls credited by the shared-account rule
);

-- The owner answers once per removal; a change needs a proposer and a different approver
CREATE TABLE decisions (
    decision_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id         UUID NOT NULL REFERENCES proposal_items,
    attested_by     TEXT NOT NULL,
    periodic        BOOLEAN NOT NULL,              -- "is this scope used less often than every 90 days?"
    approved_by     TEXT NOT NULL,
    outcome         TEXT NOT NULL,                 -- applied / kept / rejected
    reason          TEXT NOT NULL,
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Audit log (immutable, append-only, partitioned by month; the partition key is in the primary key)
CREATE TABLE audit_log (
    audit_id        UUID NOT NULL DEFAULT gen_random_uuid(),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id        TEXT NOT NULL,
    actor_type      TEXT NOT NULL,          -- user / service_account
    action          TEXT NOT NULL,
    resource_type   TEXT NOT NULL,
    resource_id     TEXT NOT NULL,
    request_id      TEXT NOT NULL,
    payload         JSONB,
    result          TEXT NOT NULL,          -- success / failure / forbidden
    PRIMARY KEY (audit_id, occurred_at)
) PARTITION BY RANGE (occurred_at);
```

### ClickHouse schema (the time-series tables)

```sql
-- One row per day, service account, scope and agent tag; counts only, no call arguments
CREATE TABLE usage_history (
    usage_date        Date,
    service_account   LowCardinality(String),
    agent_key         LowCardinality(String),     -- agent id, or empty string when the log has no tag
    scope             LowCardinality(String),     -- always a specific scope
    calls             UInt32,
    unapproved_calls  UInt32                      -- calls to approval-required scopes with no approval
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/usage_history', '{replica}')
PARTITION BY toYYYYMM(usage_date)
ORDER BY (agent_key, scope, usage_date)
TTL usage_date + INTERVAL 730 DAY DELETE;  -- 2-year hot retention, matching the table below
```

**Call data.** The diff needs the scope name, the agent tag, the service account, the day and whether a human approved the call. It does not need arguments or free text. The design stores counts only. Where a reviewer needs the original call to judge a case, it is fetched from the agent platform's own tool-call log by call id, under that system's retention and access rules. ScopeKeeper does not become a second copy of customer data.

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-retention schedule before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Grant snapshots | 7 years | Postgres, archive to Object Lock | Internal |
| Usage facts (counts only) | 2 years hot | ClickHouse | Internal |
| Proposals and decisions | 7 years | Postgres, archive to Object Lock | Confidential |
| Evidence bundles | 7 years | Object storage with Object Lock | Confidential |
| Audit log | 7 years | Postgres partitioned, archive to Object Lock | Confidential |
| Queue cache | TTL, hours | Redis | Internal |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with customer-managed keys (CMEK / CMK) in Cloud KMS, AWS KMS or Azure Key Vault, one key ring per region. Keys never cross a region boundary.
- **In transit.** TLS 1.3 north-south. mTLS east-west through the service mesh.
- **Database-level.** Transparent data encryption on PostgreSQL, encrypted disks on ClickHouse, encryption at rest on Redis.

### Secrets management

- **Primary store.** The bank's secret manager or the cloud secret manager. No long-lived static credentials.
- **Application secrets** (grant-store read token, call-log view credential, database passwords): fetched at boot through workload identity, rotated on the bank's schedule with dual-credential rolling.
- **Service-account keys.** None. Workload Identity on GCP, IAM Roles for Service Accounts on AWS, Managed Identity on Azure.
- **Apply hook credential.** The only write path into the grant store. Scoped to the change types an approval can authorize, and used only by `sk-review`.

### Identity provider & user management

- **IdP.** Whatever the bank already runs. SAML 2.0 and OIDC. ScopeKeeper does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Sessions.** OIDC ID token plus signed session cookie (HttpOnly, Secure, SameSite=Strict), with absolute and idle expiry set by bank policy.
- **Service-to-service identity.** SPIFFE IDs; each component has its own workload identity and mTLS enforces it at every hop.

### RBAC matrix

Authorization is enforced at the review API with OPA, and every decision is written to `audit_log`.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `sk:viewer` | Read proposals, usage and trends | Audit, executives |
| `sk:owner` | Viewer + answer attestation questions for their own agents and propose approval | Agent owner |
| `sk:platform` | Owner rights across agents + configure the window, the minimum calls and the weights | Agent platform owner |
| `sk:approver` | Viewer + approve a change to a high-impact scope; cannot approve their own proposal | Access-governance reviewer, line-2 |
| `sk:admin` | Config, integrations, role management | Platform engineering lead |

A change to a scope the catalog marks as needing human approval needs an owner who attests and a different person who approves. Both are recorded in `decisions`.

### Network controls

- **Perimeter.** VPC Service Controls (GCP), PrivateLink plus Network Firewall (AWS) or Private Endpoints (Azure). No public ingress for the review API; the collector reaches only the grant store and the call-log view on an allow-list.
- **Lateral.** Network policies and layer-7 inspection on the service mesh; workers read the call log through a read-only view and can reach nothing else.
- **Ingress.** The console sits behind the bank's SSO; the review API is called over mTLS by the console and the interlocks.
- **Zero-trust.** Every inter-service call is authenticated. No "trusted internal network" assumption.

### Threat model

| Threat | Mitigation |
| --- | --- |
| A proposal is applied without a person reading it | The apply hook accepts only an approval record with a different approver than the proposer; the approval carries the replay result. |
| Owners approve every proposal as they approve every grant | The share of proposals approved without opening the usage is a first-class metric; high-impact changes need a second approver. |
| A quarterly scope is removed and a quarter-end job fails | An attestation question on every removal; denied calls after a change are reported against the decision that caused them. |
| A thin or stale call log makes a scope look unused | A minimum call count per agent and a complete-window check; below either, no proposal. |
| Usage facts become a second copy of customer data | Counts only; originals are fetched by call id from the agent platform's log. |
| The apply hook becomes a way to widen access | The hook can remove or narrow only; it has no path to add a grant. |
| A malicious agent description or ticket text tries to steer a reviewer | Free text is treated as data and escaped in the console; no text is passed to a model. See also [PromptShield](../06-promptshield-prompt-injection-defense/) for the tool-call side. |

---

## 4a. APIs consumed and exposed

ScopeKeeper is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Agent platform grant store | REST or database view, read-only token from the secret manager | Nightly list of grants with dates and tickets | Collector retries; the window is marked incomplete |
| Tool-call log (agent platform) | Read-only view, workload identity | Counts per agent tag, service account, scope, day and approval flag | Diff withheld for the affected days |
| Bank identity provider | SAML 2.0 + OIDC | Console login, role lookup | Existing sessions continue |
| Access-governance tool | Vendor REST, service principal | File decisions and evidence bundles | Local audit trail continues; sync resumes later |
| Monitoring (OpenTelemetry to the platform's stack) | OTLP over TLS | Metrics and traces | Local buffer |
| Paging and chat | REST / webhook | Alert routing | Email fallback |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/reviews/run` | OpenAPI 3.1 over HTTPS, mTLS service identity | Scheduler, access-governance tool |
| `GET /v1/agents/{agent}/proposal` | mTLS service identity | AgentWatch (05), PromptShield (06), OversightOps (08) |
| `POST /v1/proposals/{id}/decisions` | OIDC bearer, role-checked by OPA | `sk-console` |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Incident management, access-governance record |

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** The surface is one run endpoint, one proposal endpoint and a decision endpoint. OpenAPI generates the console SDK and the interlock clients from one spec.
- **Idempotency key on `run`.** A retried scheduler call must not open a second proposal. UUID v4 in the `Idempotency-Key` header.
- **The response carries the reason, not just the action.** Every item returns its action, its reason and the counts behind it, so a reviewer can decide without opening the log.
- **The proposal is read-only for consumers.** PromptShield reads the approved set; it cannot change it.
- **Webhooks are signed, not just authenticated.** HMAC-SHA256 with a per-consumer rotating secret.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry into the platform's existing monitoring | The SRE's existing pane |
| Proposals and decisions over time | ClickHouse + dashboards | Approval rate, periodic-scope rate and denied-call rate per owner |
| Replay queue age and worker health | Metrics | Drives the wait and the failure mode |
| Audit log | Postgres, archived to Object Lock | Record-keeping |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **In-scope agents with a decided proposal this quarter** | The north star. Everything else supports it. |
| **Denied calls after an applied change** | The cost of a wrong removal. It is the known-limit class. |
| **Share of calls with an agent tag** | A shared account without tags makes every proposal conservative. |
| **Attestation response time** | A queue that owners ignore removes nothing. |
| **Review latency** | 🔴 Design target is a proposal by the next business day; not measured |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P1 | Calls denied after an applied change on a money-movement scope | Paging |
| P2 | Replay unavailable or queue aging; store unavailable; apply hook failing | Paging (low urgency) + chat |
| P3 | Call-log gap; window incomplete | Chat |
| P4 | Untagged calls on a shared account; daily digest | Email |

### Rollout

Shadow first: collect and propose, show nothing to owners, and compare the proposal with what owners say the agent needs. Then replay, then an advisory queue, then apply for read scopes, as laid out in the PRD. Automatic rollback to advisory if the denied-call rate after applied changes breaches its threshold.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **ClickHouse.** Weekly backup to object storage; replicated engine for HA inside a region.
- **Object stores.** Object Lock and versioning for evidence bundles and archived decisions.
- **Snapshots.** Immutable by design; any day can be rebuilt from the grant store's own history where it keeps one.
- **DR drill cadence.** Quarterly failover to the secondary region, validated against the agent platform's own recovery objective.

### Runbooks (one page each, in `docs/runbooks/`)

- `proposal-review.md` — read a proposal: usage first, then the reason, then the replay
- `attestation.md` — answer the periodic-scope question and what each answer does
- `denied-after-change.md` — a call was denied after an applied change: find the decision, restore the scope, record the miss
- `call-log-gap.md` — a day of the call log is missing
- `shared-account.md` — untagged calls on a shared account: count them and plan the split
- `evidence-pull.md` — pull the decision and the usage behind a grant for an auditor

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against.

| Framework | How the design relates |
| --- | --- |
| **SR 26-2 / model risk management** (the 2011 predecessor was SR 11-7) | A record of what each deployed agent was allowed to do, what it did, and who approved the change is ongoing-monitoring evidence about how an agent is used. Paraphrase written for this exercise, not the text of the guidance. SR 26-2 sets no enforceable standards and places generative AI and agentic AI outside its scope (see the README's regulatory note), so this row names a design basis and an analogy, not a requirement. |
| **NIST SP 800-53 Rev 5, AC-6 least privilege** | The proposal is the least-privilege theme applied to agent scopes: give each account only the access its function needs. Paraphrase written for this exercise, not the text of the control. |
| **NIST AI RMF** | The Measure and Manage functions map to the usage diff and the owner decision. |
| **OWASP LLM Top 10, excessive agency** | Shrinking the scope set limits what an agent can be made to do. |
| **SOC 2 Type II, GDPR, India data localization** | Regional instances, counts-only usage facts, append-only audit. |

---

## 7. What's deliberately not here

- **A runtime proxy between the agent and its tools.** ScopeKeeper decides at review time. The tool-call gate is PromptShield; runtime observability is AgentWatch.
- **A replacement for the owners' own judgment.** The owner knows whether a scope is periodic; ScopeKeeper knows what the log shows.
- **A claim that the logs show everything.** A quarterly scope looks unused in a 90-day window, and a shared account blurs who called what. Both are known limits, covered by owner attestation and one service account per agent.
- **Argument-aware usage in v1.** The diff reads scope names and counts, not what a call did with the scope.
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each one is already owned by another system or another phase.

---

## Appendix — sample API contract

```python
# GET /v1/agents/A-07/proposal
# Auth: mTLS service identity
{
    "proposal_id": "9d2e41c0-...",
    "agent_id": "A-07",
    "window": {
        "start": "2026-07-20",
        "end": "2026-10-17"
    },
    "reach": {
        "before": 15,
        "after": 7
    },
    "grants": {
        "keep": 5,
        "remove": 6,
        "narrow": 1
    },
    "replay": {
        "calls": 907,
        "denied": 0
    },
    "risk": {
        "rank": 1,
        "points": 146
    },
    "items": [
        {
            "scope": "documents:upload",
            "action": "remove",
            "replace_with": [],
            "reason": "no call in 90 days",
            "calls_tagged": 0,
            "calls_credited": 0,
            "ask_owner": "is this scope periodic?"
        },
        {
            "scope": "ledger:*",
            "action": "narrow",
            "replace_with": [
                "ledger:read_entry",
                "ledger:write_entry"
            ],
            "reason": "2 of 4 scopes it reaches were called",
            "calls_tagged": 509,
            "calls_credited": 0,
            "ask_owner": null
        }
    ]
}
```

The counts, the actions and the reasons in the example are the prototype's `step_04` output for A-07 on the synthetic data. The proposal id is illustrative.

OpenAPI spec lives at `docs/api/openapi.yaml` and is the source of truth for the console and the interlock clients.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/23-scopekeeper-agent-permission-review/demo.html).
