# Architecture — IncidentLedger

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO and your platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (a classifier, a severity rubric, a clock engine, a follow-up tracker and a linker, over synthetic data, with a Streamlit app). Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. Every BFSI shop is on AWS, GCP or Azure (or two of three). GCP is shown as primary; AWS and Azure equivalents are called out inline.

![IncidentLedger flow](./assets/incidentledger-flow.svg)

---

## 1. Logical architecture

IncidentLedger is an incident layer on top of the bank's existing incident system. It does not replace the incident process, the on-call rota or the people who decide an incident is real. It sits between a filed ticket and the notices that are owed, and decides four things: how severe the incident is, which clocks run, how many hours are left, and whether the follow-ups have evidence.

Nine components. Four are in the countdown path; five are not.

| Component | Responsibility | Language / framework | In countdown path? | Stateful? |
| --- | --- | --- | --- | --- |
| `il-intake` | Receives a ticket from the incident system (API or webhook), validates the five rubric fields and writes the incident. Runs the classifier. | Python 3.11 on Cloud Run / Fargate / Container Apps | Yes, sync | No |
| `il-rubric` | Computes S1 to S4 from the five fields and records the rubric lines that fired. The prototype's `rubric`. | Python | Yes, sync | No |
| `il-clock` | Reads the signed policy and the determination time, evaluates every clock that applies on a fixed interval, writes the status and emits countdown and breach events. The prototype's `evaluate_clocks`. | Python worker with a scheduler | Yes, async on a timer | No |
| `il-policy` | Holds the notification policy as versioned configuration: hours, applicability, anchor, approver, effective date. | Git-backed config service | Yes, read | Stateful |
| `il-tracker` | Follow-up actions, with a rule that closure needs an evidence link. The prototype's `track_action`. | Python | No | No |
| `il-linker` | Groups tickets by system and change id, else system and category in a window. The prototype's `link_incidents`. | Python | No, async | No |
| `il-record` | Writes the evidence record for the model-risk file: rating, determination, notices, actions. | Python | No, async | No |
| `il-console` | Incident manager console: open clocks sorted by hours left, determination prompts, follow-ups, linked tickets. | React + Next.js + Tailwind | No | No |
| `il-telemetry` | OpenTelemetry spans and metrics from every component, exported off the countdown path. | OTel Collector to the platform's monitoring | No, async | No |

**What is in the countdown path, and what is not.** Intake, rubric, policy and the clock evaluation decide whether a person sees a countdown in time. Everything else supports them or reports on them. IncidentLedger never sends a notice to a regulator, a customer or an executive itself: people send, and the tool records what was sent and when. Runtime detection stays with AgentWatch.

**Repo structure** (production shape; monorepo):

```
incidentledger/
├── apps/
│   ├── intake/         # API + classifier
│   ├── rubric/         # severity rubric
│   ├── clock/          # scheduler + clock evaluation
│   ├── tracker/        # follow-ups, evidence rule
│   ├── linker/         # root-cause linking
│   ├── record/         # evidence record writer
│   └── console/        # incident manager UI
├── libs/
│   ├── policy/         # policy model, versioning
│   └── taxonomy/       # seven classes, keyword lists, field rules
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
    └── calibration/    # classifier and linker vs labeled real tickets
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `il-intake`, `il-rubric` | Cloud Run | ECS Fargate | Container Apps | Stateless API; a warm instance keeps intake fast |
| `il-clock` | Cloud Run jobs + Cloud Scheduler | ECS scheduled tasks + EventBridge | Container Apps jobs + Logic Apps | A small job on a fixed interval; scale is the number of open clocks |
| `il-tracker`, `il-linker`, `il-record` | Cloud Run | ECS Fargate | Container Apps | Stateless, short-lived |
| `il-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI |
| `il-store` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |
| `il-policy` | Git repository + config service | Git repository + AppConfig | Git repository + App Configuration | Versioned, reviewed, signed |

**Failure behavior (the decision that matters most).** A missed countdown is worse than a noisy one. If the clock job cannot reach the store, it fails loudly: the console shows 'clock evaluation stale' with the last good time, and the on-call for the incident manager is paged. If the policy service is down, the engine uses the last signed version and marks every clock 'policy version stale'. A ticket the classifier cannot place becomes 'needs a person', never a guess. A missing determination shows as 'not started' with the hours since detection, never as 'no clock'.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Clock job misses an interval | The next run evaluates every open clock; the gap is shown on the console | P2 |
| Policy service unavailable | Last signed version used; clocks marked stale | P3 |
| Intake receives a ticket with missing rubric fields | Stored as 'incomplete', severity shown as 'unknown', a prompt goes to the reporter | P4 |
| Determination missing past the set time | Prompt to the named role; the incident stays in the top of the console | P3 |
| Store unavailable | Console read-only from cache; intake queues tickets locally | P2 |
| Telemetry sink down | Buffer locally, drop with a counter once full | P4 |

**Latency.** The only new wait is the clock evaluation interval. 🔴 Design target: a countdown warning inside one evaluation interval of its threshold. It has not been measured in this repo. The levers if it is slow: evaluate only open clocks, and index open clocks by due time.

### Network topology

```
Incident system (existing)
   │   ticket event (signed webhook) or poll
   ▼
[il-intake + classifier]  ──►  [PostgreSQL: incidents, ratings]
   │                                   │
   ▼                                   ▼
[il-rubric]  ──►  [il-clock]  ◄──  [il-policy (signed, versioned)]
                      │
        ┌─────────────┼──────────────────┐
        ▼             ▼                  ▼
  countdown/breach  [il-tracker] ──►  [il-record] ──► object store (Object Lock)
  events (chat,        │                  │
  email, paging)   [il-linker]            └──► model-risk record (GRC tool)
        │
        ▼
 incident manager (people send the notices)

Out of band:
   [il-console] behind the bank's SSO  ──►  [il API] (role-checked by OPA)
   Interlocks: AgentWatch (05), OversightOps (08), LineageLog (09), SchemaWatch (15), SwapBrief (13),
               ControlMap (16), KillSwitch (25) over service-to-service calls (all designed, none built)
```

### Region & DR

- Primary and DR regions follow the incident system's own footprint. IncidentLedger does not get a different recovery objective than the process it supports.
- Region-specific instances where data residency applies. Each has its own database and key ring; incident text does not replicate across regions.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | Incidents, ratings, clock evaluations, notices, actions, links, policy versions, audit log | Relational integrity for the audit trail; the platform team already runs it |
| **Object storage with Object Lock (WORM)** | The evidence record and archived incidents | Write-once-read-many for the record-keeping policy |
| **Git** | The policy file, with reviewers and approvers | Every hour value has a history and a named approver |

### PostgreSQL schema (the consequential tables)

```sql
-- One row per incident ticket
CREATE TABLE incidents (
    incident_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_ref       TEXT NOT NULL,                -- ticket id in the existing incident system
    system_name        TEXT NOT NULL,
    change_id          TEXT,                         -- release or model change, when known
    title              TEXT NOT NULL,
    description_ref    TEXT NOT NULL,                -- pointer; the text stays in the source system
    reporter_priority  TEXT NOT NULL,                -- kept as a field, never used for the rating
    reporter_category  TEXT NOT NULL,
    customers_affected INT NOT NULL,
    regulated_decision BOOLEAN NOT NULL,
    pii_exposed        BOOLEAN NOT NULL,
    impact_band        TEXT NOT NULL,                -- none / low / medium / high
    duration_hours     INT NOT NULL,
    detected_at        TIMESTAMPTZ NOT NULL,
    reported_at        TIMESTAMPTZ NOT NULL,
    determined_at      TIMESTAMPTZ,                  -- NULL until a person records it
    determined_by      TEXT,
    UNIQUE (external_ref)
);

-- Append-only: a new row for every re-rating
CREATE TABLE ratings (
    rating_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id        UUID NOT NULL REFERENCES incidents,
    severity           TEXT NOT NULL,                -- S1 to S4
    severity_reasons   JSONB NOT NULL,               -- the rubric lines that fired
    category           TEXT NOT NULL,                -- seven classes or needs_review
    category_rule      TEXT NOT NULL,
    confidence         TEXT NOT NULL,                -- field / keywords / review
    confirmed_by       TEXT,                         -- a person confirms every S1 and S2
    rated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The signed policy: one row per clock per version
CREATE TABLE policy_clocks (
    policy_version     INT NOT NULL,
    clock_id           TEXT NOT NULL,
    clock_name         TEXT NOT NULL,
    applies_to         TEXT NOT NULL,                -- sev_s1 / notification_incident / pii_exposed / serious_incident
    hours              INT NOT NULL,
    anchor             TEXT NOT NULL,                -- determination / detection
    approved_by        TEXT NOT NULL,
    effective_from     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (policy_version, clock_id)
);

-- Notices sent: one row answers one clock of one incident. People send; the tool records.
CREATE TABLE notifications (
    notification_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id        UUID NOT NULL REFERENCES incidents,
    clock_id           TEXT NOT NULL,
    sent_at            TIMESTAMPTZ NOT NULL,
    sent_by            TEXT NOT NULL,
    evidence_uri       TEXT
);

-- Follow-up actions. A closed action must carry evidence.
CREATE TABLE actions (
    action_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id        UUID NOT NULL REFERENCES incidents,
    action_text        TEXT NOT NULL,
    owner              TEXT NOT NULL,
    due_at             TIMESTAMPTZ NOT NULL,
    status             TEXT NOT NULL,                -- open / in_progress / closed
    closed_at          TIMESTAMPTZ,
    evidence_uri       TEXT,
    CHECK (status <> 'closed' OR evidence_uri IS NOT NULL)
);

-- Which tickets share a root cause (derived, then confirmed by a person)
CREATE TABLE incident_links (
    incident_id        UUID NOT NULL REFERENCES incidents,
    linked_incident_id UUID NOT NULL REFERENCES incidents,
    basis              TEXT NOT NULL,                -- change_id / system_category_window
    confirmed_by       TEXT,
    PRIMARY KEY (incident_id, linked_incident_id)
);

-- Every clock evaluation, append-only, partitioned by month
CREATE TABLE clock_evaluations (
    evaluation_id      UUID NOT NULL DEFAULT gen_random_uuid(),
    evaluated_at       TIMESTAMPTZ NOT NULL,
    incident_id        UUID NOT NULL,
    clock_id           TEXT NOT NULL,
    policy_version     INT NOT NULL,
    status             TEXT NOT NULL,                -- on_time / late / breached / running / not_started
    hours_left         INT,
    hours_over         INT,
    PRIMARY KEY (evaluation_id, evaluated_at)
) PARTITION BY RANGE (evaluated_at);

-- Audit log (immutable, append-only, partitioned by month)
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

**Incident text.** The rubric needs five facts and the classifier needs the title and description. The design keeps the description text in the source incident system and stores a pointer; the classifier reads the text in memory and stores only its result and the rule that fired. Where a reviewer needs the original, it is fetched from the source system under that system's access rules. IncidentLedger does not become a second copy of sensitive descriptions.

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-retention schedule before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Incidents, ratings and links | 7 years | Postgres, archive to Object Lock | Confidential |
| Notices and follow-ups | 7 years | Postgres, archive to Object Lock | Confidential |
| Evidence records | 7 years | Object storage with Object Lock | Confidential |
| Clock evaluations | 2 years hot | Postgres, partitioned | Internal |
| Policy versions | Life of the product plus 7 years | Git, archive to Object Lock | Internal |
| Incident description text | Not stored by IncidentLedger | The source incident system | Governed by that system |
| Audit log | 7 years | Postgres partitioned, archive to Object Lock | Confidential |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with customer-managed keys (CMEK / CMK) in Cloud KMS, AWS KMS or Azure Key Vault, one key ring per region. Keys never cross a region boundary.
- **In transit.** TLS 1.3 north-south. mTLS east-west through the service mesh.
- **Field-level.** Titles are stored; descriptions are pointers. Free text that reaches the console is escaped, never rendered as markup.
- **Database-level.** Transparent data encryption on PostgreSQL, encrypted disks, encryption at rest on object storage.

### Secrets management

- **Primary store.** HashiCorp Vault or the cloud secret manager. No long-lived static credentials.
- **Application secrets** (incident-system token, webhook signing secret, database passwords): fetched at boot through workload identity, rotated on the bank's schedule with dual-credential rolling.
- **Service-account keys.** None. Workload Identity on GCP, IAM Roles for Service Accounts on AWS, Managed Identity on Azure.
- **Webhook secrets.** Per-source signing secret, rotated; intake verifies the signature before it reads anything.

### Identity provider & user management

- **IdP.** Whatever the bank already runs (Okta, Microsoft Entra ID, Ping). SAML 2.0 and OIDC. IncidentLedger does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Sessions.** OIDC ID token plus signed session cookie (HttpOnly, Secure, SameSite=Strict), with absolute and idle expiry set by bank policy.
- **Service-to-service identity.** SPIFFE IDs; each component has its own workload identity and mTLS enforces it at every hop.

### RBAC matrix

Authorization is enforced at the API with OPA, and every decision is written to `audit_log`.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `il:viewer` | Read incidents, clocks and trends | Audit, executives |
| `il:reporter` | File and update a ticket's facts | Anyone who reports an incident |
| `il:manager` | Viewer + record determination, record notices sent, manage follow-ups, confirm links | AI incident manager |
| `il:policy` | Propose a policy change | Regulatory liaison |
| `il:approver` | Approve a policy change, or a downgrade of S1 or S2 (a proposer cannot approve their own) | Counsel, line-2 model risk |
| `il:admin` | Config, integrations, role management | Platform engineering lead |

A policy change and a downgrade of S1 or S2 need a proposer and a different approver. Both are recorded.

### Network controls

- **Perimeter.** VPC Service Controls (GCP), PrivateLink plus Network Firewall (AWS) or Private Endpoints (Azure). No public ingress for the API; intake reaches only the incident system's endpoints on an allow-list.
- **Lateral.** Network policies and layer-7 inspection on the service mesh.
- **Ingress.** The incident system calls intake over mTLS; the console sits behind the bank's SSO.
- **Zero-trust.** Every inter-service call is authenticated. No "trusted internal network" assumption.

### Threat model

| Threat | Mitigation |
| --- | --- |
| A reporter under-rates an incident, by habit or to avoid escalation | The rating comes from facts, not the reporter's priority, which is kept as a field. A downgrade of S1 or S2 needs a different approver. |
| Determination is delayed to delay the clock | Hours since detection are shown while the clock waits; both anchors are displayed; late determination is its own metric. |
| Policy hours are changed without sign-off | Hours are versioned with an approver and an effective date; every clock evaluation records the policy version used. |
| A closed action has no evidence | A database check rejects closure without an evidence link; line-2 samples links for existence and relevance. |
| Incident text carries instructions meant for a reader or a model | Text is treated as data: rule-based classification only, escaped on display. If a model is ever added to the classifier, its input is untrusted by default. |
| The record becomes a second store of sensitive descriptions | Pointers, not text; originals stay in the source system. |
| Classifier is wrong with no flag | Clocks run on rubric fields, not on category; a person confirms the category of every S1 and S2. |

---

## 4a. APIs consumed and exposed

IncidentLedger is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Incident system (existing) | REST or event stream, read token from Vault | Ticket events; ticket fields and links to descriptions | Poller continues; late intake is flagged |
| Notification channels (chat, email, paging) | REST / webhook | Send countdown and breach messages to the incident manager | Email fallback; the breach is also written to the console |
| Bank IdP (Okta / Entra / Ping) | SAML 2.0 + OIDC | Console login, role lookup | Existing sessions continue |
| Model-risk record (GRC tool) | Vendor REST, service principal | File the evidence record | Local audit trail continues; sync resumes later |
| Monitoring (OpenTelemetry to the platform's stack) | OTLP over TLS | Metrics and traces | Local buffer |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/incidents` | OpenAPI 3.1 over HTTPS, mTLS service identity | The incident system |
| `GET /v1/incidents/{id}` | mTLS service identity | Console; AgentWatch (05); LineageLog (09) |
| `POST /v1/incidents/{id}/determination` | OIDC bearer, role-checked by OPA | Console |
| `POST /v1/incidents/{id}/notifications` | OIDC bearer, role-checked by OPA | Console |
| `GET /v1/clocks?due_within=24` | mTLS service identity | Console; paging |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Paging, chat, the model-risk record |

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** The surface is a few resources and a console. OpenAPI generates the incident-system client and the console SDK from one spec.
- **Idempotency key on every write.** A retried webhook must not open a second incident or record a second notice. UUID v4 in the `Idempotency-Key` header.
- **The response carries the reason, not just the verdict.** Severity, the rubric lines that fired, the category rule and each clock's hours come back every time, so a manager can act without asking.
- **Determination is its own call.** The clock starts on a person's explicit action, never inferred.
- **Webhooks are signed, not just authenticated.** HMAC-SHA256 with a per-consumer rotating secret.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry into the platform's existing monitoring | The on-call's existing pane |
| Clocks over time | Postgres + dashboards | On time, late, breached and running per clock and per week |
| Clock evaluation lag | Metrics | Drives the stale-clock alert |
| Audit log | Postgres, archived to Object Lock | Record-keeping |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **Notification deadlines met on time or still running** | The north star. Everything else supports it. |
| **Incidents with a determination within the set time of detection** | The clock cannot start without it. |
| **Clock evaluation lag** | A stale countdown is worse than none. 🔴 Design target is one evaluation interval; not measured. |
| **Follow-ups closed with evidence** | The cost side of closing quickly. |
| **Policy staleness** | A clock on an unsigned or old policy is false comfort. |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P1 | A deadline on an S1 incident is about to pass with no notice recorded | Paging |
| P2 | Clock evaluation stale; store unavailable | Paging (low urgency) + chat |
| P3 | Determination missing past the set time; policy service unavailable | Chat |
| P4 | Incomplete ticket; daily digest of overdue actions | Email |

### Rollout

Shadow first: rate and compute clocks for each ticket, show nothing to the manager, and compare with what was actually sent. Then the rubric beside the reporter's priority, then advisory countdowns for S1 and S2, then required evidence on closure, as laid out in the PRD. Automatic fall-back to advisory mode if clock evaluation lag breaches its threshold.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **Object stores.** Object Lock and versioning for evidence records and archived incidents.
- **Policy.** Git history; any version can be restored and re-signed.
- **DR drill cadence.** Quarterly failover to the secondary region, validated against the incident system's own recovery objective.

### Runbooks (one page each, in `docs/runbooks/`)

- `clock-evaluation-stale.md` — the job missed intervals: check the scheduler, run a manual evaluation
- `determination-overdue.md` — an incident has no determination past the set time: who to call
- `deadline-breached.md` — a deadline passed with no notice: record it, tell the liaison, open a follow-up
- `policy-change.md` — propose, approve, version, announce
- `classifier-miss.md` — a ticket was filed under the wrong class: add the case to the labeled sample
- `evidence-pull.md` — pull the record for an incident for line-2 or an examiner

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against. The statements are a paraphrase written for this exercise, not the text of any rule.

| Framework | How the design relates |
| --- | --- |
| **SR 26-2 / model risk management** (the current model-risk guidance; its 2011 predecessor was SR 11-7) | An incident that reveals a problem in a model has to feed ongoing monitoring and be explainable afterwards. The record holds the rating, the determination, the notices and the evidence. |
| **NIST AI RMF** | The Manage function: tracking, responding to and communicating about incidents. The clock engine and the tracker are that theme made concrete. |
| **SR 22-4** | The theme is knowing whom to notify and how. The policy file names the recipients per clock; the hours stay assumptions to confirm with counsel. |
| **EU AI Act, Article 73 serious-incident reporting** | The serious-incident clock models the theme with an assumed value. Which incidents are reportable, and by when, is for counsel. |
| **OWASP LLM Top 10** | The security and injection class uses its vocabulary. |
| **SOC 2 Type II, GDPR, India data localization** | Regional instances, pointers instead of copied text, append-only audit. |

---

## 7. What's deliberately not here

- **Sending the notices.** People send them. The tool counts the hours and records what was sent.
- **Deciding that something is an incident.** Determination is a human call and the clock starts on it.
- **A legal reading of any obligation.** The policy file holds assumed hours that counsel confirms.
- **Runtime detection or observability.** That is AgentWatch (05).
- **A model.** The classifier is rules. If a model is added later, it goes behind the same 'needs a person' rule and is measured on a labeled sample first.
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each one is already owned by another system, another role or another phase.

---

## Appendix — sample API contract

`GET /v1/incidents/{id}`, auth by mTLS service identity or OIDC bearer, response 200:

```json
{
    "incident_id": "INC-0102",
    "system": "advisor-notes-tool",
    "reporter_priority": "P4",
    "severity": "S1",
    "severity_reasons": [
        "personal data exposed for 390 customers (100 or more)"
    ],
    "category": {
        "value": "data_exposure",
        "rule": "field: personal data exposed",
        "confidence": "field"
    },
    "determined_at": "2026-09-16 04:00",
    "clocks": [
        {
            "clock_id": "CK1",
            "status": "breached",
            "due": "2026-09-16 08:00",
            "hours_over": 448,
            "hours_left": null
        },
        {
            "clock_id": "CK2",
            "status": "breached",
            "due": "2026-09-17 16:00",
            "hours_over": 416,
            "hours_left": null
        },
        {
            "clock_id": "CK3",
            "status": "running",
            "due": "2026-10-16 04:00",
            "hours_over": null,
            "hours_left": 268
        },
        {
            "clock_id": "CK4",
            "status": "breached",
            "due": "2026-10-01 04:00",
            "hours_over": 92,
            "hours_left": null
        }
    ],
    "followups": {
        "total": 3,
        "overdue": 0,
        "closed_no_evidence": 0
    },
    "linked": []
}
```

The severity, the rule, the clock statuses and the hours are the prototype's `step_04` output for INC-0102 on the synthetic data at the read date 2026-10-05 00:00. The identifiers and the shape are illustrative.

OpenAPI spec lives at `docs/api/openapi.yaml` and is the source of truth for the incident-system client and the console.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/19-incidentledger-ai-incident-response/demo.html).
