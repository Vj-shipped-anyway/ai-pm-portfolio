# Architecture — PortfolioBoard

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO and your platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (evidence status rules, a capacity grid, dependency propagation, a pull rule and a benefit rollup, over synthetic data, with a Streamlit app). Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. Every BFSI shop is on AWS, GCP or Azure (or two of three). GCP is shown as primary; AWS and Azure equivalents are called out inline.

![PortfolioBoard flow](./assets/portfolioboard-flow.svg)

---

## 1. Logical architecture

PortfolioBoard is a read-and-compute layer. It does not replace the stage-gate process, the review teams' systems or the resourcing plan. It reads what they already produce, applies a fixed set of rules and puts one board in front of the head of the AI program office. It decides nothing: it suggests.

Nine components. Six produce the board; three support or report on it.

| Component | Responsibility | Language / framework | In the board run? | Stateful? |
| --- | --- | --- | --- | --- |
| `pb-ingest` | Pulls attestations, planned demand, supply, dependencies and stage events from source systems on a schedule and on webhooks. Writes each as an immutable event with its evidence date. | Python on Cloud Functions / Lambda / Functions | Yes, async trigger | No |
| `pb-store` | Holds programs, criteria, attestations, statuses, decisions and the audit log. | PostgreSQL 15 | Yes | Stateful |
| `pb-status` | Evidence status per program: criteria in force at the stage, met, freshness, slipped. Emits the reason. The prototype's `evidence_flags` and `build_board`. | Python | Yes, sync | No |
| `pb-deps` | Walks the dependency register and returns the red or slipped upstream programs behind each program, direct or through a chain. The prototype's `upstream_issues`. | Python | Yes, sync | No |
| `pb-grid` | Planned demand against supply by team and quarter; pro-rata share where short. The prototype's `capacity_grid`. | Python | Yes, sync | No |
| `pb-pull` | Work in progress against the limit per stage; pause suggestions; review supply by value per FTE. The prototype's `pull_rule`. | Python | Yes, sync | No |
| `pb-rollup` | Benefit at risk by status, labeled modeled. Reads the benefit estimate, or ValueLedger's measured figure when it exists. | Python | No, async | No |
| `pb-console` | The board for the head of the AI program office: statuses, reasons, the grid, the pause list, owner challenges. | React + Next.js + Tailwind | No | No |
| `pb-telemetry` | OpenTelemetry spans and metrics from every component, exported off the board run. | OTel Collector to the platform's monitoring | No, async | No |

**What is in the board run, and what is not.** Ingest, store, status, dependencies, grid and the pull rule produce the board. The console and the rollup report on it. Nothing here sits in a delivery path: a program is never blocked by PortfolioBoard. It is told what the evidence says and who should look.

**Repo structure** (production shape; monorepo):

```
portfolioboard/
├── apps/
│   ├── ingest/         # pullers + webhook handlers per source system
│   ├── status/         # evidence rules, freshness, slipped
│   ├── grid/           # capacity grid
│   ├── pull/           # WIP limits, pause and defer
│   ├── rollup/         # benefit at risk
│   └── console/        # board UI
├── libs/
│   ├── rules/          # status and dependency rules, one module, versioned
│   └── calendar/       # week and quarter conventions
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
    └── audit/          # sample-audit results vs "met" flags
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `pb-ingest` | Cloud Functions gen 2 + Cloud Scheduler | Lambda + EventBridge | Functions + Event Grid | Small scheduled pulls plus webhook handlers |
| `pb-status`, `pb-deps`, `pb-grid`, `pb-pull` | Cloud Run jobs | ECS Fargate tasks | Container Apps jobs | Stateless, short-lived, run on a schedule and on new attestations |
| `pb-rollup` | Cloud Run jobs | ECS Fargate tasks | Container Apps jobs | Same |
| `pb-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI |
| `pb-store` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The board is advisory, so every failure degrades toward showing less rather than showing something wrong. A source system that cannot be read leaves its last attestation in place; the attestation keeps aging, and past its freshness rule the criterion turns stale on its own. A criterion with no attestation counts as not met. A missing demand or supply figure shows as unknown, never as zero. A board older than its schedule says so in the header.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Source system unreachable | Last attestation stands and ages; the board header names the source and its last good pull | P3 |
| Webhook missed | The next scheduled pull finds the event; the status updates late and is marked late | P3 |
| Dependency register stale | Blocked-by is shown with the register's last-updated date | P4 |
| Status run fails | The previous board stays up, marked with its run time | P2 |
| Store unavailable | Console read-only from cache; ingest buffers events locally | P2 |
| Telemetry sink down | Buffer locally, drop with a counter once full | P4 |

**Latency.** The board is a nightly product, so there is no request-path latency to protect. 🔴 Design target: a full run over the portfolio inside one scheduled window, and a status refresh for one program inside a minute of a new attestation. Neither has been measured in this repo.

### Network topology

```
Source systems (review teams, resourcing plan, dependency register, stage events)
   │   webhook (signed) or scheduled pull, read-only tokens
   ▼
[pb-ingest] ──► [PostgreSQL: attestations, demand, supply, dependencies, stage events]
                        │
        ┌───────────────┼────────────────┬──────────────┐
        ▼               ▼                ▼              ▼
   [pb-status]      [pb-grid]        [pb-deps]     [pb-rollup]
        └───────┬───────┴────────────────┘
                ▼
            [pb-pull] ──► board snapshot ──► object storage (retained)
                │
                ▼
          [pb-console] behind the bank's SSO ──► head of AI program office, sponsors, owners

Interlocks: TierGate (11), ValueLedger (12), ControlMap (16), IncidentLedger (19), AdoptionPulse (21)
over service-to-service calls (🔴 designed, none built)
```

### Region & DR

- Primary and DR regions follow the platform's own footprint. PortfolioBoard does not get a different recovery objective than the systems it reads.
- Region-specific instances where data residency applies. Each has its own database and key ring; attestations do not replicate across regions.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | Programs, criteria, attestations, statuses, decisions, challenges, audit log | Relational integrity for the audit trail; the platform team already runs it |
| **Object storage with Object Lock (WORM)** | Monthly board snapshots and archived decisions | Write-once-read-many for the record-keeping policy |
| **Redis** (optional) | Cache for the console, idempotency keys | TTL eviction handles cleanup |

### PostgreSQL schema (the consequential tables)

```sql
-- Programs and their attributes at the time of the run
CREATE TABLE programs (
    program_id        TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    stage             TEXT NOT NULL,                -- idea / discovery / build / pilot / scale
    owner_code        TEXT NOT NULL,
    target_quarter    TEXT NOT NULL,
    est_benefit_usd   BIGINT NOT NULL,              -- the owner's estimate; never a measured figure
    benefit_confidence NUMERIC NOT NULL,
    reported_rag      TEXT NOT NULL                 -- what the owner picked, kept beside the status
);

-- The gate criteria, with who attests each and how long evidence stays fresh
CREATE TABLE gate_criteria (
    criterion_id      TEXT PRIMARY KEY,
    gate              INT NOT NULL,                 -- 1 admits to idea ... 5 admits to scale
    criterion         TEXT NOT NULL,
    attested_by       TEXT NOT NULL,
    max_age_days      INT NOT NULL                  -- freshness rule, set and signed by the attester
);

-- Attestations are append-only events; the latest one per program and criterion counts
CREATE TABLE attestations (
    attestation_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id        TEXT NOT NULL REFERENCES programs,
    criterion_id      TEXT NOT NULL REFERENCES gate_criteria,
    met               BOOLEAN NOT NULL,
    evidence_date     DATE NOT NULL,
    attested_by       TEXT NOT NULL,
    source_system     TEXT NOT NULL,
    document_ref      TEXT,                          -- pointer to the document, never its content
    recorded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One row per program per board run; partitioned by run date, so the key includes it
CREATE TABLE program_status (
    run_date          DATE NOT NULL,
    program_id        TEXT NOT NULL REFERENCES programs,
    evidence_status   TEXT NOT NULL,                -- GREEN / AMBER / RED
    board_status      TEXT NOT NULL,                -- after slipped and dependency rules
    unmet             TEXT[] NOT NULL DEFAULT '{}',
    stale             TEXT[] NOT NULL DEFAULT '{}',
    blocked_by        TEXT[] NOT NULL DEFAULT '{}',
    reason            TEXT NOT NULL,
    action            TEXT NOT NULL,                -- PAUSE / FUND / DEFER, a suggestion
    PRIMARY KEY (run_date, program_id)
) PARTITION BY RANGE (run_date);

-- Pause and defer suggestions and what the office did with them
CREATE TABLE pull_decisions (
    decision_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_date          DATE NOT NULL,
    program_id        TEXT NOT NULL REFERENCES programs,
    suggestion        TEXT NOT NULL,                -- PAUSE / DEFER
    reason            TEXT NOT NULL,
    decided_by        TEXT,                         -- blank until a person decides
    outcome           TEXT,                         -- accepted / declined
    decided_at        TIMESTAMPTZ
);

-- Audit log (immutable, append-only, partitioned by month; the key includes the partition column)
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

**Evidence content.** The board needs the attestation, its date and a pointer to the document. It does not need the document. The design stores `document_ref` and never copies the content, so PortfolioBoard does not become a second copy of the review teams' files.

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-retention schedule before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Attestations and statuses | Life of the program plus 7 years | Postgres, archive to Object Lock | Confidential |
| Pull decisions and challenges | 7 years | Postgres, archive to Object Lock | Confidential |
| Monthly board snapshots | 7 years | Object storage with Object Lock | Confidential |
| Demand and supply plans | 3 years | Postgres | Internal |
| Audit log | 7 years | Postgres partitioned, archive to Object Lock | Confidential |
| Console cache | TTL, hours | Redis | Internal |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with customer-managed keys (CMEK / CMK) in Cloud KMS, AWS KMS or Azure Key Vault, one key ring per region. Keys never cross a region boundary.
- **In transit.** TLS 1.3 north-south. mTLS east-west through the service mesh.
- **Database-level.** Transparent data encryption on PostgreSQL, encryption at rest on Redis and object storage.

### Secrets management

- **Primary store.** HashiCorp Vault or the cloud secret manager. No long-lived static credentials.
- **Application secrets** (source-system read tokens, webhook signing secrets, database passwords): fetched at boot through workload identity, rotated on the bank's schedule with dual-credential rolling.
- **Service-account keys.** None. Workload Identity on GCP, IAM Roles for Service Accounts on AWS, Managed Identity on Azure.
- **Webhook secrets.** Per-source signing secret, rotated; ingest verifies the signature before it reads anything.

### Identity provider & user management

- **IdP.** Whatever the bank already runs (Okta, Microsoft Entra ID, Ping). SAML 2.0 and OIDC. PortfolioBoard does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Sessions.** OIDC ID token plus signed session cookie (HttpOnly, Secure, SameSite=Strict), with absolute and idle expiry set by bank policy.
- **Service-to-service identity.** SPIFFE IDs; each component has its own workload identity and mTLS enforces it at every hop.

### RBAC matrix

Authorization is enforced at the API with OPA, and every action is written to `audit_log`.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `pb:viewer` | Read the board, statuses and reasons | Sponsors, audit |
| `pb:owner` | Viewer + attest what no review team owns, challenge a status on their own programs | Program owner |
| `pb:reviewer` | Viewer + attest criteria in their own queue, read their own demand and supply | Model risk review and security review leads |
| `pb:office` | Viewer + accept or decline pause and defer suggestions, set stage limits | Head of the AI program office |
| `pb:admin` | Config, integrations, role management | Platform engineering lead |

A change to a freshness rule needs a proposer and a different approver. Both are recorded.

### Network controls

- **Perimeter.** VPC Service Controls (GCP), PrivateLink plus Network Firewall (AWS) or Private Endpoints (Azure). No public ingress; ingest reaches only the source endpoints on an allow-list.
- **Lateral.** Network policies and layer-7 inspection on the service mesh; workers read source systems through read-only views and can reach nothing else.
- **Ingress.** The console sits behind the bank's SSO; service callers use mTLS.
- **Zero-trust.** Every inter-service call is authenticated. No "trusted internal network" assumption.

### Threat model

| Threat | Mitigation |
| --- | --- |
| A false attestation: "met" with fresh evidence that is not true | The known limit. A sample audit of "met" flags against the documents, with the failure rate published beside the board; the audit result feeds the status. |
| An owner inflates the benefit estimate to rank higher in the pull rule | The estimate is shown as an owner estimate; the sponsor and finance partner see it beside the board; ValueLedger's measured figure replaces it when it exists. |
| A pause suggestion quietly acted on without a decision | Suggestions are advisory; `pull_decisions` records who decided and when; unrecorded pauses show as a gap on the board. |
| Stale or missing feed makes the board look clean | Age is part of the status; a missing attestation counts as not met; a source's last good pull is in the header. |
| Evidence content copied into a second store | Only a document reference is stored; content stays in the source system under its own access rules. |
| Status quietly rewritten by an owner | Statuses are computed, never edited; a challenge is a recorded request, not an edit. |

---

## 4a. APIs consumed and exposed

PortfolioBoard is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Review-team systems (model risk, security) | REST or event stream, read-only token from Vault | Attestations with evidence date and document reference | Last attestation stands and ages; source named in the board header |
| Resourcing plan | REST or file export, read-only | Planned demand and supply by team and quarter | Cell shown as unknown, never zero |
| Dependency register | REST, read-only | Program dependencies and types | Stale register date shown |
| Stage events | Event stream | Stage entry, review request, exit | Late events marked late |
| Bank IdP (Okta / Entra / Ping) | SAML 2.0 + OIDC | Console login, role lookup | Existing sessions continue |
| Model-risk record (GRC tool) | Vendor REST, service principal | File monthly snapshots | Local audit trail continues; sync resumes later |
| TierGate, ControlMap, ValueLedger, IncidentLedger, AdoptionPulse | Service-to-service, mTLS | 🔴 designed, none built | Not applicable until built |
| Monitoring (OpenTelemetry to the platform's stack) | OTLP over TLS | Metrics and traces | Local buffer |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `GET /v1/board` | OpenAPI 3.1 over HTTPS, OIDC bearer | `pb-console`, sponsors' tooling |
| `GET /v1/programs/{id}` | OIDC bearer, role-checked by OPA | `pb-console`, owners |
| `POST /v1/programs/{id}/challenge` | OIDC bearer; idempotency key | Owners |
| `POST /v1/pull/{decision_id}/decision` | OIDC bearer, `pb:office` only | Head of the AI program office |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Model-risk record, notification tooling |

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** The surface is one board, one program view and two writes. OpenAPI generates the console SDK from one spec.
- **The response carries the reason, not just the status.** `board_status`, the unmet and stale criteria, the blockers and the action come back every time, so an owner can fix the right thing without a meeting.
- **Computed, never edited.** There is no write that sets a status. A challenge is a recorded request that a person answers.
- **Idempotency key on writes.** A retried challenge or decision must not create a second record. UUID v4 in the `Idempotency-Key` header.
- **Webhooks are signed, not just authenticated.** HMAC-SHA256 with a per-consumer rotating secret.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry into the platform's existing monitoring | The platform team's existing pane |
| Board history over time | Postgres + dashboards | Status mix, statuses that differ from the owner's color, ambers cleared per cycle |
| Feed lag per source | Metrics | Drives the stale-source banner |
| Audit log | Postgres, archived to Object Lock | Record-keeping |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **Programs whose status is computed from evidence** | The north star. Everything else supports it. |
| **Share of criteria within their freshness rule** | A board over stale evidence is a prettier report, nothing more |
| **Sample-audit failure rate on "met" flags** | The only direct measure of the known limit |
| **Ambers cleared per cycle** | Whether owners act on the board or learn to ignore it |
| **Board run age** | 🔴 Design target is one nightly run; not measured |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P2 | Status run failed; store unavailable | Paging (low urgency) + chat |
| P3 | A source unreachable or late; webhook missed | Chat |
| P4 | Dependency register stale; daily digest | Email |

### Rollout

Shadow first: compute statuses, show nothing to owners, compare with what the review teams say. Then the evidence feed, an advisory board beside the report, the capacity grid and pull rule, and finally the audit sample, as laid out in the PRD. Automatic rollback of a rule version if the share of ambers owners clear in a cycle falls below its threshold.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **Object stores.** Object Lock and versioning for board snapshots and archived decisions.
- **Rules.** Versioned in the repo; any past board can be recomputed from the attestations and the rule version recorded on its snapshot.
- **DR drill cadence.** Quarterly failover to the secondary region, validated against the platform's own recovery objective.

### Runbooks (one page each, in `docs/runbooks/`)

- `source-late.md` — a source system has not delivered: read the header, contact the attester
- `status-challenge.md` — an owner challenges a status: read the attestation, ask the attester, record the outcome
- `pause-decision.md` — accept or decline a pause suggestion: record the decider and the reason
- `audit-sample.md` — draw the monthly sample of "met" flags and record the result
- `rule-change.md` — change a freshness rule: propose, approve, version, recompute
- `snapshot-pull.md` — pull the board and its evidence for a given month

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against.

| Framework | How the design relates |
| --- | --- |
| **SR 26-2 / model risk management** | The current model risk guidance (it replaced its 2011 predecessor, SR 11-7, in April 2026). The monthly snapshot and the audit sample are the record a program office would show for how AI programs are tracked and checked over time. This mapping is a paraphrase written for this exercise, not the text of the rule. |
| **NIST AI RMF** | The Govern function maps to named owners, attested gate evidence and a recorded decision on every pause. |
| **Internal controls** | Computed statuses, append-only attestations and a recorded decider on every suggestion that is acted on. |

---

## 7. What's deliberately not here

- **Measuring benefit.** The rollup shows an owner estimate and says so. Measured benefit against a holdout is ValueLedger (12).
- **Intake and tiering.** Risk tier and intake registration come from TierGate (11), not from this layer.
- **Collecting control evidence.** ControlMap (16) holds it; PortfolioBoard reads the attestation.
- **A delivery gate.** PortfolioBoard never blocks a program. It tells the office what the evidence says.
- **A claim that it detects false attestations.** It reads "met" and an age. A sample audit is the mitigation, and the prototype leaves 3 planted misses in on purpose.
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each one is already owned by another system or another phase.

---

## Appendix — sample API contract

```python
# GET /v1/programs/P-14
# Auth: OIDC bearer, role pb:viewer
# Response 200
{
    "program_id": "P-14",
    "name": "Regulatory change digest",
    "stage": "scale",
    "reported": "green",
    "board_status": "RED",
    "unmet": ["K04", "K06"],
    "blocked_by": [],
    "action": "FUND",
    "action_is_suggestion": true,
    "benefit_is_owner_estimate": true
}
```

The status, the unmet criteria, the blockers and the action in the example are the prototype's `step_04` output for P-14 on the synthetic data. The shape of the response is a design.

OpenAPI spec lives at `docs/api/openapi.yaml` and is the source of truth for the console SDK.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/24-portfolioboard-ai-program-portfolio/demo.html).
