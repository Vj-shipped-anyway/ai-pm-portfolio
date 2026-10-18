# Architecture — StepScout

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO, your data-protection officer and your platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (merge, classify, screen, rank and brief, over synthetic events, with a Streamlit app). Nothing below is claimed as deployed or load-tested. The prototype's desktop and status events are written by a generator, so the collector and the labeler are a design and not a build. Where a figure is a design target, it says so (🔴).

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. Every BFSI shop is on AWS, GCP or Azure (or two of three). GCP is shown as primary; AWS and Azure equivalents are called out inline.

![StepScout flow](./assets/stepscout-flow.svg)

---

## 1. Logical architecture

StepScout is an evidence layer. It does not replace the case system, the process-mining pass, the intake process or the agent build. It sits between "we should put an agent here" and an engineer's first line of code, and decides one thing per workflow step: leave it to a person, or make it a candidate with a class, a control screen and an estimate.

Ten components. One runs on employees' machines; nine do not.

| Component | Responsibility | Language / framework | On a worker's machine? | Stateful? |
| --- | --- | --- | --- | --- |
| `ss-collector` | Records application, action, start, end and a count of typed characters. Pseudonymizes the worker id on the device. No screen capture, no keystroke content. | Signed desktop agent | Yes | Local buffer |
| `ss-labeler` | Maps application and action patterns to step ids, with a confidence. Events it cannot place stay unlabeled. | Python | No | No |
| `ss-store` | Holds events, occurrences, features, classes, register versions, rankings, briefs and the audit log. | PostgreSQL 15 | No | Stateful |
| `ss-merge` | Groups labeled events into step occurrences per case, joins the case-system log, checks that each status event lands on an occurrence of the right step. The prototype's `build_occurrences` and `match_status_events`. | Python | No | No |
| `ss-classifier` | Computes step features (overrides, typed characters, repeats, timing spread, writes, outbound email, cross-application copy) and the class. The prototype's `step_stats` and `classify`. | Python | No | No |
| `ss-register` | The control and data-classification flags per step (four-eyes, restricted data, gated by), versioned, with an owner and an approver. | Python, PostgreSQL | No | Stateful |
| `ss-ranker` | Applies the control screen, then ranks by modeled hours at stake times readiness. The prototype's `control_screen` and `rank_candidates`. | Python | No | No |
| `ss-brief` | Writes build-brief/v1 packs for the top candidates and validates each one against the schema. The prototype's `make_brief` and `validate_brief`. | Python, Pydantic v2 | No | No |
| `ss-console` | Aggregate views by step, the candidate list, the class explanations, the briefs. No view by worker. | React + Next.js + Tailwind | No | No |
| `ss-telemetry` | OpenTelemetry spans and metrics from every component. | OTel Collector to the platform's monitoring | No | No |

**What touches a worker and what does not.** The collector is the only component on a worker's machine. Everything after it sees a pseudonymous id, and the console shows aggregates by step with a minimum group size. Re-identifying a worker is a separate, logged, two-person process that the design does not use for this product.

**Keeping the answer out of the classifier.** The register and the events are the classifier's only inputs. In the prototype the answer key lives in a different column and a different loader, and a check shuffles it and shows every class unchanged. In production there is no answer key; a hand-labeled sample is used to calibrate the thresholds and to report disagreement, and it never feeds a class.

**Repo structure** (production shape; monorepo):

```
stepscout/
├── apps/
│   ├── collector/      # desktop agent: events, pseudonymization, local buffer
│   ├── labeler/        # application and action patterns to step ids
│   ├── merge/          # occurrences, the join with the case-system log
│   ├── classifier/     # features and classes
│   ├── ranker/         # control screen and ranking
│   ├── brief/          # build-brief/v1 writer and validator
│   └── console/        # aggregate views
├── libs/
│   ├── schema/         # build-brief/v1, event and step schemas
│   ├── features/       # override rate, typed characters, repeats, spread
│   └── privacy/        # pseudonymization, minimum group size
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
    └── calibration/    # classes compared with a hand-labeled sample of steps
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `ss-collector` | Managed device deployment | Managed device deployment | Managed device deployment | Runs on employee machines under the bank's own device management |
| `ss-labeler`, `ss-merge`, `ss-classifier` | Cloud Run jobs | ECS Fargate tasks | Container Apps jobs | Stateless, scheduled batch |
| `ss-ranker`, `ss-brief` | Cloud Run | ECS Fargate | Container Apps | Stateless, run after the batch |
| `ss-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI |
| `ss-register` | Cloud Run + Cloud SQL | ECS Fargate + RDS | Container Apps + Azure Database | Small service with an approval flow |
| `ss-store` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** Every component has one rule for failure: keep the last good result and mark it stale. A step keeps its last class, the list shows a stale marker, and nothing is promoted to a brief from stale data. The one exception is the register: a step with a missing flag is held out of the candidate list until the control owner answers. Any change to that rule needs a named owner and a line-2 sign-off.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Collector down on some machines | Coverage drops; the affected queue is marked partial | P2 |
| Labeler cannot place an event | The event counts toward handling time and no step; the unlabeled share is tracked | P4 |
| Case-system log late | The merge runs on desktop events alone and flags steps that lose their anchor | P3 |
| Register missing a flag | The step is held out of the list | P3 |
| Classifier and the hand-labeled sample disagree beyond the tolerance | The list is marked uncalibrated | P3 |
| Telemetry sink down | Buffer locally, drop with a counter once full | P4 |

**Latency.** Nothing here is in a customer decision or in a worker's path. 🔴 Design target: the merge, classify and rank batch finishes overnight for one queue. It has not been measured in this repo; the prototype runs the whole walkthrough in seconds on synthetic events.

### Network topology

```
Employee desktops (managed devices)
   │   pseudonymous events, signed, over TLS
   ▼
[ss-collector gateway] ──► [PostgreSQL: events]
                                  │
Case system ── read-only API ──►  │
                                  ▼
                       [ss-labeler] ──► [ss-merge] ──► [ss-classifier]
                                                              │
        [ss-register] ──────────────────────────────────►    ▼
                                                        [ss-ranker] ──► [ss-brief]
                                                              │             │
                                                              ▼             ▼
                                              [ss-console] behind the bank's SSO   briefs to engineering

Out of band:
   [ss-telemetry] ──► OTel Collector ──► monitoring
   Interlocks (all designed, none built): TierGate (11), ValueLedger (12), AdoptionPulse (21), ScopeKeeper (23), KillSwitch (25), AgentKit (27)
```

### Region & DR

- Primary and DR regions follow the bank's own footprint. StepScout does not get a recovery objective stricter than the queue it studies.
- Region-specific instances where data residency applies. Each has its own database and key ring; events do not replicate across regions.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | Events, occurrences, step features, classes, register versions, rankings, briefs, audit log | Relational integrity for the audit trail; the platform team already runs it |
| **Object storage with Object Lock (WORM)** | Evidence bundles per brief: the features, the register version and the ranking it came from | Write-once-read-many for the record-keeping policy |
| **Redis** (optional) | Console cache and idempotency keys for the brief API | TTL eviction handles cleanup |

### PostgreSQL schema (the consequential tables)

```sql
-- One row per labeled step run. Worker ids are pseudonymous; the key lives in a separate service.
CREATE TABLE step_occurrences (
    occurrence_id  UUID NOT NULL DEFAULT gen_random_uuid(),
    queue          TEXT NOT NULL,
    case_id        TEXT NOT NULL,
    step_id        TEXT NOT NULL,
    worker_pseudo  TEXT NOT NULL,                 -- pseudonymous id, never a name
    started_at     TIMESTAMPTZ NOT NULL,
    ended_at       TIMESTAMPTZ NOT NULL,
    touch_seconds  INT NOT NULL,
    typed_chars    INT NOT NULL,                  -- a count; the text is never stored
    overridden     BOOLEAN NOT NULL,
    cross_app_copy BOOLEAN NOT NULL,
    writes_hub     BOOLEAN NOT NULL,
    sends_email    BOOLEAN NOT NULL,
    PRIMARY KEY (occurrence_id, started_at)
) PARTITION BY RANGE (started_at);

-- Step-level features and the class. Aggregate by construction.
CREATE TABLE step_classes (
    queue          TEXT NOT NULL,
    step_id        TEXT NOT NULL,
    computed_at    TIMESTAMPTZ NOT NULL,
    runs           INT NOT NULL,
    touch_hours    DOUBLE PRECISION NOT NULL,
    override_rate  DOUBLE PRECISION NOT NULL,
    typed_chars_mean DOUBLE PRECISION NOT NULL,
    repeats_per_case DOUBLE PRECISION NOT NULL,
    timing_spread  DOUBLE PRECISION NOT NULL,
    class          TEXT NOT NULL,                 -- AGENT / AGENT_HITL / HUMAN_JUDGMENT / HUMAN_CONTROL
    reasons        JSONB NOT NULL,                -- the sentences a reviewer reads
    rules_version  INT NOT NULL,
    PRIMARY KEY (queue, step_id, computed_at)
);

-- The control and data-classification flags, versioned, with an approver
CREATE TABLE register_versions (
    register_version INT NOT NULL,
    step_id        TEXT NOT NULL,
    restricted_data BOOLEAN NOT NULL,
    control_flag   BOOLEAN NOT NULL,              -- a four-eyes control: stays with a person
    gated_by       TEXT,                          -- may run only after this step is approved
    owner          TEXT NOT NULL,
    approved_by    TEXT NOT NULL,
    approved_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (register_version, step_id)
);

-- The ranking: modeled hours at stake times readiness, with the assumption named
CREATE TABLE candidate_rankings (
    ranking_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue          TEXT NOT NULL,
    computed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    removal_share  DOUBLE PRECISION NOT NULL,     -- the one named assumption
    register_version INT NOT NULL,
    rows           JSONB NOT NULL                 -- rank, step, class, hours at stake, control screen
);

-- Build briefs, one per top candidate pack
CREATE TABLE build_briefs (
    brief_id       TEXT PRIMARY KEY,              -- BB-001
    ranking_id     UUID NOT NULL REFERENCES candidate_rankings,
    schema_version TEXT NOT NULL,                 -- build-brief/v1
    body           JSONB NOT NULL,
    valid          BOOLEAN NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by    TEXT
);

-- Audit log (immutable, append-only, partitioned by month)
CREATE TABLE audit_log (
    audit_id       UUID NOT NULL DEFAULT gen_random_uuid(),
    occurred_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id       TEXT NOT NULL,
    actor_type     TEXT NOT NULL,                 -- user / service_account
    action         TEXT NOT NULL,
    resource_type  TEXT NOT NULL,
    resource_id    TEXT NOT NULL,
    request_id     TEXT NOT NULL,
    payload        JSONB,
    result         TEXT NOT NULL,                 -- success / failure / forbidden
    PRIMARY KEY (audit_id, occurred_at)
) PARTITION BY RANGE (occurred_at);
```

**What is stored about workers.** A pseudonymous id, the times of events and counts. Never a name, never the text a worker typed, never a screenshot. The mapping from the pseudonym back to a person is held by a separate service with its own access control and is not used by StepScout.

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-retention schedule and the data-protection review before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Raw desktop events | 90 days | Postgres, partitioned, dropped by partition | Confidential (employee data) |
| Step occurrences | 13 months | Postgres | Confidential (employee data) |
| Step features and classes | 7 years | Postgres | Internal |
| Register versions | 7 years | Postgres, archive to Object Lock | Confidential |
| Rankings and briefs | 7 years | Postgres, archive to Object Lock | Confidential |
| Evidence bundles | 7 years | Object storage with Object Lock | Confidential |
| Audit log | 7 years | Postgres partitioned, archive to Object Lock | Confidential |

---

## 4. Security architecture

A collector on employees' machines and a store of their activity are privileged and sensitive. They are designed as such.

### Encryption

- **At rest.** AES-256 with customer-managed keys (CMEK / CMK) in Cloud KMS, AWS KMS or Azure Key Vault, one key ring per region. Keys never cross a region boundary. The pseudonymization key sits in its own ring with its own access.
- **In transit.** TLS 1.3 north-south. mTLS east-west through the service mesh. Collector events are signed on the device.
- **Database-level.** Transparent data encryption on PostgreSQL, encryption at rest on Redis.

### Secrets management

- **Primary store.** HashiCorp Vault or the cloud secret manager. No long-lived static credentials.
- **Application secrets** (case-system read token, database passwords): fetched at boot through workload identity, rotated on the bank's schedule with dual-credential rolling.
- **Service-account keys.** None. Workload Identity on GCP, IAM Roles for Service Accounts on AWS, Managed Identity on Azure.

### Identity provider & user management

- **IdP.** Whatever the bank already runs (Okta, Microsoft Entra ID, Ping). SAML 2.0 and OIDC. StepScout does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Sessions.** OIDC ID token plus signed session cookie (HttpOnly, Secure, SameSite=Strict), with absolute and idle expiry set by bank policy.
- **Service-to-service identity.** SPIFFE IDs; each component has its own workload identity and mTLS enforces it at every hop.

### RBAC matrix

Authorization is enforced at the API with OPA, and every decision is written to `audit_log`.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `ss:viewer` | Read aggregate views by step, the candidate list and briefs | Operations leads, engineers |
| `ss:analyst` | Viewer + change thresholds in a draft, run a calibration against a labeled sample | Process-mining analyst |
| `ss:register-owner` | Edit and approve register flags for steps they own | Control and data-classification owners |
| `ss:privacy` | Read retention, access and pseudonymization audit; cannot read events | Data-protection officer |
| `ss:admin` | Config, integrations, role management | Platform engineering lead |

No role can see one worker's activity through the console. There is no view by worker. A change to a register flag needs a proposer and a different approver, both recorded.

### Network controls

- **Perimeter.** VPC Service Controls (GCP), PrivateLink plus Network Firewall (AWS) or Private Endpoints (Azure). No public ingress for the services; the collector gateway accepts only signed events from managed devices.
- **Lateral.** Network policies and layer-7 inspection on the service mesh; the labeler, merge and classifier can read the event store and write features, and can reach nothing else.
- **Ingress.** The console sits behind the bank's SSO.
- **Zero-trust.** Every inter-service call is authenticated. No "trusted internal network" assumption.

### Threat model

| Threat | Mitigation |
| --- | --- |
| The data is used to score or discipline individual workers | No view by worker; aggregate views with a minimum group size; no worker-level feature in any table; a stated purpose in the data-protection record. |
| A pseudonym is reversed | The key lives in a separate service with two-person access and an audit entry for every lookup; StepScout never calls it. |
| The collector captures more than designed (text, screens) | The agent has no keystroke or screen capability; a signed build is checked by the device-management team; a typed-character count is the only text-derived field. |
| A forged event stream changes a class | Signed events from managed devices, an allow-list of sources, and a calibration check that marks the list uncalibrated when classes move without a change in the register or the thresholds. |
| A register flag is dropped so an agent can be aimed at a four-eyes step | Flags are versioned with an approver; a step with a missing flag is held out of the list; a change needs a different approver. |
| A brief hides a control | The writer takes controls from the register and the class; the validator rejects a brief without the control fields; a person reads every brief. |
| A hidden judgment passes as a rule | Not closed by the classifier. The brief's shadow-mode test and a time-diary sample are the second line. |

---

## 4a. APIs consumed and exposed

StepScout is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Case system | Read-only API, token from Vault | Status changes per case: status, timestamp, pseudonymous actor | The merge runs on desktop events alone; steps lose their anchor and are flagged |
| Device management | Vendor REST, workload identity | Collector version and coverage per queue | Coverage unknown; the queue is marked partial |
| Control and data-classification registers | Internal API, workload identity | Flags per step | The step is held out of the list |
| Bank IdP (Okta / Entra / Ping) | SAML 2.0 + OIDC | Console login, role lookup | Existing sessions continue |
| Monitoring (OpenTelemetry to the platform's stack) | OTLP over TLS | Metrics and traces | Local buffer |
| Paging and chat | REST / webhook | Alert routing | Email fallback |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `GET /v1/steps/{step}/candidate` | OpenAPI 3.1 over HTTPS, mTLS service identity | Console, intake and business-case tools (TierGate 11, ValueLedger 12) |
| `GET /v1/briefs/{brief_id}` | mTLS plus user token | Engineers, the permission review (ScopeKeeper 23), the agent build (AgentKit 27) |
| `POST /v1/register/{step}/flags` | mTLS plus user token, a different approver | Control and data-classification owners |
| Console API | OIDC bearer, role-checked by OPA | `ss-console` |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Benefit tracking, adoption measurement (AdoptionPulse 21) |

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** The surface is a candidate, a brief, a register flag and a console. OpenAPI generates the client for the console and for the agent build from one spec.
- **The response carries the reason, not just the class.** The class, the features it came from, the register version and the control screen come back every time, so a reviewer can read it without a meeting.
- **No endpoint returns a worker.** There is no path parameter for a worker and no field that identifies one.
- **Idempotency key on writes.** A retried approval must not create a second version. UUID v4 in the `Idempotency-Key` header.
- **Webhooks are signed, not just authenticated.** HMAC-SHA256 with a per-consumer rotating secret.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry into the platform's existing monitoring | The on-call person's existing pane |
| Label coverage and merge match rate | Metrics | A class built on poor coverage is worse than none |
| Class changes over time | Postgres + dashboards | A class that moves without a reason is a signal |
| Audit log | Postgres, archived to Object Lock | Record-keeping |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **Share of events that carry a step label** | The coverage of everything downstream. 🟢 Prototype: 2.4% unlabeled on generated events; a real miner's figure is unknown. |
| **Status events landing on an occurrence of the right step** | The merge's health. 🟢 Prototype: 98.8%. |
| **Agreement with a hand-labeled sample** | The calibration. 🔴 Not measurable until a sample exists. |
| **Briefs that pass the schema check** | The hand-off's health. 🟢 Prototype: all 3. |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P1 | A collector build is found to capture more than designed | Paging |
| P2 | Collector coverage drops on a queue | Paging (low urgency) + chat |
| P3 | A register flag is missing; a case-system log is late; the list is uncalibrated | Chat |
| P4 | Unlabeled share above the tolerance; telemetry sink down | Email |

### Rollout

Review first: no collection before the data-protection and works-council review. Then one queue on pseudonymous events and aggregate views, then a labeled sample and calibration, then the candidate list with the register's flags, then briefs and shadow mode, as laid out in the PRD.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **Object stores.** Object Lock and versioning for evidence bundles and archived rankings.
- **Pseudonymization key.** Backed up under its own two-person procedure; losing it means pseudonyms cannot be reversed, which is acceptable for this product.
- **DR drill cadence.** Quarterly failover to the secondary region, validated against the bank's own recovery objective.

### Runbooks (one page each, in `docs/runbooks/`)

- `collector-coverage-drop.md` — coverage fell on a queue: find the devices, mark the queue partial
- `unlabeled-share-high.md` — the labeler cannot place events: add a pattern, review the step definitions
- `register-flag-missing.md` — a step is held out: ask the owner, record the answer
- `calibration-drift.md` — classes disagree with the labeled sample: review thresholds, document the change
- `brief-rejected.md` — a brief failed the schema check or a reviewer: what to fix, who re-approves
- `privacy-request.md` — a worker or a representative asks what is collected: answer from the data-protection record

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against. Obligation statements are paraphrases written for this exercise, not the text of any rule.

| Framework | How the design relates |
| --- | --- |
| **NIST AI RMF** | The Map function: establish the context and the intended use before a system is built. The control screen, the class reasons and the build brief are where that context is written down. |
| **Data-protection law on employee monitoring** (for example GDPR) | Purpose limitation, data minimization and proportionality. Pseudonymous ids, counts instead of text, aggregate views, short raw retention and a data-protection review before collection. Whether a legal basis exists is a legal question. |
| **Works-council consultation** | Where it applies, monitoring tools need it before they are used. Collection is gated on it in the rollout. |
| **EU AI Act** | Systems that monitor or evaluate workers fall in a high-risk category. StepScout is designed to describe steps and never to score people; whether a given deployment is in scope is a legal question. |
| **Four-eyes and segregation-of-duties principles** | The register's control flag keeps an approval with a person, and a gated step runs only after it. |
| **SOC 2 Type II** | Append-only audit, least-privilege roles, regional instances. |

---

## 7. What's deliberately not here

- **Scoring or ranking of workers.** Never. No table, endpoint or view holds a worker-level measure.
- **Keystroke content and screen capture.** A count of typed characters is the only text-derived field.
- **The agent itself.** StepScout writes the brief. Building and running the agent is 27 AgentKit; its permissions are 23 ScopeKeeper; its fallback is 25 KillSwitch.
- **Intake, prioritization and the business case.** 11 TierGate and 12 ValueLedger own those; StepScout supplies the evidence.
- **A claim that it finds every hidden judgment.** A judgment made off the desktop is a known miss, covered by a shadow-mode test and a time diary that are designed here and not built.
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each one is already owned by another system or another phase.

---

## Appendix — sample API contract

```python
# GET /v1/steps/S04/candidate
# Auth: mTLS service identity
# Response 200
{
    "step": "S04",
    "name": "copy_beneficiary_fields",
    "class": "AGENT",
    "reasons": ["fixed timing (spread 0.33 of the mean)", "no overrides to speak of", "no free text to speak of", "moves values between applications in 95% of runs"],
    "control_screen": "clear",
    "touch_hours_30d": 129.1,
    "hours_at_stake_modeled": 90.4,
    "removal_share_assumed": 0.7,
    "rank": 1,
    "register_version": 1,
    "evidence_uri": "object-lock://stepscout/evidence/..."
}
```

The step, the class, the reasons, the touch hours, the hours at stake and the rank in the example are the prototype's `step_04` output on the synthetic data. The register version and the URI are illustrative.

OpenAPI spec lives at `docs/api/openapi.yaml` and is the source of truth for the console and the agent build.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/26-stepscout-task-mining-agent-candidates/demo.html).
