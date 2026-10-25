# Architecture — VendorLens

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO and your platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (an evidence rule, a concentration view, an exit score, a risk class and a cadence, over synthetic data, with a Streamlit app). Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. Most bank platform teams run on AWS, GCP or Azure (or two of three). GCP is shown as primary; AWS and Azure equivalents are called out inline.

![VendorLens flow](./assets/vendorlens-flow.svg)

---

## 1. Logical architecture

VendorLens is a decision-support layer on the vendor record. It does not replace the vendor register, the questionnaire tool, the contract repository or the third-party risk team's judgment. It reads them, scores what can be checked, and writes a decision with its reasons that a person accepts, changes or overrides.

Nine components. Six are in the decision path; three are not.

| Component | Responsibility | Language / framework | In the decision path? | Stateful? |
| --- | --- | --- | --- | --- |
| `vl-ingest` | Pulls vendors, answers and contract terms from the register, the questionnaire tool and the contract repository on a schedule and on change events. Writes each as an immutable snapshot keyed by content hash. | Python 3.11 on Cloud Functions / Lambda / Functions | Yes, async trigger | No |
| `vl-store` | Holds snapshots, evidence metadata, scores, decisions and resolutions. | PostgreSQL 15 | Yes | Stateful |
| `vl-evidence` | The evidence rule: classes each answer as backed, unbacked, unverifiable or contradicted from document type, issue date, scope and contract fields; computes the control score. The prototype's `control_score` and `answer_support`. | Python | Yes, sync | No |
| `vl-concentration` | Maps vendors to upstream providers, computes the share of critical use cases and the HHI, applies the flag, and reports the unknown bucket and the upper bound. The prototype's `concentration_view`. | Python | Yes, sync | No |
| `vl-exit` | Exit-readiness score from clause, test and modeled time to exit against the allowed window. The prototype's `exit_readiness`. | Python | Yes, sync | No |
| `vl-scorer` | Combines the parts with the policy file into a risk score and class, with reasons, and writes the decision. Exposes the score API. | Python, FastAPI, Pydantic v2 | Yes, sync | No |
| `vl-cadence` | Sets the next review date from tier and class, and raises reminders and expiry notices for documents. | Python | No, scheduled | No |
| `vl-console` | Review console: queue, vendor page with reasons, evidence list with named reader, resolutions, policy versions. | React + Next.js + Tailwind | No | No |
| `vl-telemetry` | OpenTelemetry spans and metrics from every component, exported off the decision path. | OTel Collector to the platform's monitoring | No, async | No |

**What is in the decision path, and what is not.** Ingest, store, the three rule components and the scorer produce the score. Everything else supports them or reports on them. VendorLens never sits between the bank and a vendor at runtime: it does not proxy a vendor's API, and it does not read the vendor's model output.

**Repo structure** (production shape; monorepo):

```
vendorlens/
├── apps/
│   ├── ingest/         # connectors and snapshot writer
│   ├── scorer/         # FastAPI: score API, decision writer
│   ├── cadence/        # review scheduler, expiry notices
│   └── console/        # review UI
├── libs/
│   ├── evidence/       # answer support rule, control score
│   ├── concentration/  # provider map, share, HHI, flag
│   ├── exit/           # exit readiness
│   └── policy/         # versioned policy file loader
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
    └── calibration/    # scores vs the bank's own review outcomes
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `vl-ingest` | Cloud Functions gen 2 + Cloud Scheduler | Lambda + EventBridge | Functions + Event Grid | Small scheduled job plus change-event handlers |
| `vl-evidence`, `vl-concentration`, `vl-exit` | Cloud Run jobs | ECS Fargate tasks | Container Apps jobs | Stateless, short-lived, run per snapshot |
| `vl-scorer` | Cloud Run (min instances 1) | ECS Fargate | Container Apps | Stateless API; a warm instance keeps decisions quick |
| `vl-cadence` | Cloud Run jobs + Cloud Scheduler | ECS scheduled tasks | Container Apps jobs | Daily batch |
| `vl-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI |
| `vl-store` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |
| Evidence documents | Cloud Storage with retention lock | S3 Object Lock | Blob Storage immutability policy | Write-once documents with a legal-hold option |

**Failure behavior (the decision that matters most).** The score is advice with reasons, so every failure degrades toward showing the last known decision, marked stale, and never toward silence or a clean score. A missing document, an unavailable contract repository or an unreadable file produces a lower score with the reason named, not an error page.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Contract repository unavailable | Last snapshot used and marked stale; contract-backed answers keep their last status | P3 |
| Document has no issue date or scope | Counts as not valid; reason names the missing field | P4 |
| Vendor does not disclose its provider | Half a concentration flag; the upper bound for each provider is shown | Info |
| Policy file fails to load | Scoring stops; the console shows the last decision with its policy version | P2 |
| Store unavailable | Console read-only from cache; ingest buffers snapshots locally | P2 |
| Telemetry sink down | Buffer locally, drop with a counter once full | P4 |

**Latency.** The only new wait is the score call when an analyst opens a vendor. 🔴 Design target: a decision inside one analyst session. It has not been measured in this repo. The levers if it is slow: precompute scores on every snapshot, and cache the concentration view for the estate.

### Network topology

```
Vendor register / questionnaire tool / contract repository
   │   change event (signed webhook) or poll
   ▼
[vl-ingest]  ── read-only tokens ──►  [source systems]
   │
   ▼
[PostgreSQL: snapshots]  ──►  [vl-evidence] [vl-concentration] [vl-exit]
                                     │
                                     ▼
Evidence documents (object storage) ──►  [vl-scorer]  ◄── policy file (versioned)
                                     │
                    ┌────────────────┼───────────────────┐
                    ▼                ▼                   ▼
             decision record   review queue (console)   OTel Collector ──► monitoring

Out of band:
   [vl-console] behind the bank's SSO  ──►  [vl-scorer API] (role-checked by OPA)
   Interlocks (🔴 designed, none built): InferenceLens (07), SwapBrief (13), SchemaWatch (15), ControlMap (16), KillSwitch (25)
```

### Region & DR

- Primary and DR regions follow the bank's third-party risk platform. VendorLens does not get a different recovery objective than the record it feeds.
- Region-specific instances where data residency applies. Each has its own database and key ring; vendor documents do not replicate across regions.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | Vendors, snapshots, answers, evidence metadata, scores, decisions, resolutions, policy versions, audit log | Relational integrity for the audit trail; the platform team already runs it |
| **Object storage with Object Lock (WORM)** | Vendor documents and decision bundles | Write-once-read-many for the record-keeping policy |
| **Redis** (optional) | Cache for the estate concentration view, idempotency keys | TTL eviction handles cleanup |

### PostgreSQL schema (the consequential tables)

```sql
-- One row per vendor in the register
CREATE TABLE vendors (
    vendor_id          TEXT PRIMARY KEY,
    service_type       TEXT NOT NULL,
    criticality        TEXT NOT NULL,                -- critical / important / standard
    data_access        TEXT NOT NULL,                -- customer_pii / internal / none
    critical_use_cases INT  NOT NULL DEFAULT 0,
    model_provider     TEXT,                         -- NULL when not disclosed
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One row per immutable snapshot of a vendor's questionnaire and contract terms
CREATE TABLE vendor_snapshots (
    snapshot_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id          TEXT NOT NULL REFERENCES vendors,
    content_sha256     TEXT NOT NULL,
    answers_json       JSONB NOT NULL,               -- question_id -> yes / partial / no
    contract_json      JSONB NOT NULL,               -- exit_clause, exit_tested, portability_days, audit_right, notice_days
    last_assessed_on   DATE,
    observed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (vendor_id, content_sha256)
);

-- One row per document a vendor supplied
CREATE TABLE evidence_documents (
    document_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id          TEXT NOT NULL REFERENCES vendors,
    doc_type           TEXT NOT NULL,                -- independent_control_report / penetration_test / model_documentation
    issued_on          DATE,
    covers_ai_service  BOOLEAN,                      -- NULL until a reader records scope
    read_by            TEXT,                         -- named reader; NULL means not read
    read_at            TIMESTAMPTZ,
    object_uri         TEXT NOT NULL,                -- the Object Lock copy
    sha256             TEXT NOT NULL,
    UNIQUE (vendor_id, sha256)
);

-- One row per scoring decision; append-only, partitioned by month.
-- The partition key is part of the primary key.
CREATE TABLE score_decisions (
    decision_id        UUID NOT NULL DEFAULT gen_random_uuid(),
    decided_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    vendor_id          TEXT NOT NULL,
    snapshot_id        UUID NOT NULL,
    policy_version     TEXT NOT NULL,
    control_score      NUMERIC(5,1) NOT NULL,
    exit_score         INT NOT NULL,
    concentration_flag BOOLEAN NOT NULL,
    risk_score         NUMERIC(5,1) NOT NULL,
    risk_class         TEXT NOT NULL,                -- high / medium / low
    next_review_on     DATE NOT NULL,
    reasons_json       JSONB NOT NULL,               -- the sentences an analyst reads
    PRIMARY KEY (decision_id, decided_at)
) PARTITION BY RANGE (decided_at);

-- A person accepts, changes or overrides a decision; a change needs a proposer and a different approver.
-- No foreign key to the partitioned table: decision_id plus decided_at is carried as plain columns.
CREATE TABLE decision_resolutions (
    resolution_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id        UUID NOT NULL,
    decided_at         TIMESTAMPTZ NOT NULL,
    resolved_by        TEXT NOT NULL,
    approved_by        TEXT NOT NULL,
    outcome            TEXT NOT NULL,                -- accepted / class_changed / overridden
    new_class          TEXT,
    reason             TEXT NOT NULL,
    resolved_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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

**Vendor documents.** A document is stored once, hashed and locked. Scope (`covers_ai_service`) and the named reader are recorded by a person, not inferred by the service, so the evidence rule counts a document only after someone has read it. VendorLens does not run a model over documents.

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-retention schedule before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Vendor records and snapshots | Life of the contract plus 7 years | Postgres, archive to Object Lock | Confidential |
| Vendor documents | Life of the contract plus 7 years | Object storage with Object Lock | Confidential |
| Score decisions and resolutions | 7 years | Postgres, archive to Object Lock | Confidential |
| Policy versions | Permanent | Postgres | Internal |
| Audit log | 7 years | Postgres partitioned, archive to Object Lock | Confidential |
| Concentration cache | TTL, hours | Redis | Internal |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with customer-managed keys (CMEK / CMK) in Cloud KMS, AWS KMS or Azure Key Vault, one key ring per region. Keys never cross a region boundary.
- **In transit.** TLS 1.3 north-south. mTLS east-west through the service mesh.
- **Field-level.** Vendor documents and contract terms are classed Confidential and encrypted with a separate data key from the one that protects scores.
- **Database-level.** Transparent data encryption on PostgreSQL; encryption at rest on Redis and object storage.

### Secrets management

- **Primary store.** HashiCorp Vault or the cloud secret manager. No long-lived static credentials.
- **Application secrets** (read tokens for the register, the questionnaire tool and the contract repository; webhook signing secrets; database passwords): fetched at boot through workload identity, rotated on the bank's schedule with dual-credential rolling.
- **Service-account keys.** None. Workload Identity on GCP, IAM Roles for Service Accounts on AWS, Managed Identity on Azure.
- **Webhook secrets.** Per-source signing secret, rotated; `vl-ingest` verifies the signature before it fetches anything.

### Identity provider & user management

- **IdP.** Whatever the bank already runs (Okta, Microsoft Entra ID, Ping). SAML 2.0 and OIDC. VendorLens does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Sessions.** OIDC ID token plus signed session cookie (HttpOnly, Secure, SameSite=Strict), with absolute and idle expiry set by bank policy.
- **Service-to-service identity.** SPIFFE IDs; each component has its own workload identity and mTLS enforces it at every hop.

### RBAC matrix

Authorization is enforced at the score API with OPA, and every action is written to `audit_log`.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `vl:viewer` | Read decisions, scores and the concentration view | Audit, executives |
| `vl:analyst` | Viewer + record a document's scope and reader, propose a resolution | Third-party risk analyst |
| `vl:owner` | Analyst rights across vendors + accept a decision | Third-party risk manager |
| `vl:business` | Viewer + read the vendor pages for their own services | Business owner of the AI service |
| `vl:validator` | Viewer + approve a resolution that overrides a class + approve policy changes | Line-2 model risk |
| `vl:admin` | Config, integrations, role management | Platform engineering lead |

A resolution that overrides a class needs a proposer and a different approver. Both are recorded in `decision_resolutions`. A policy change needs `vl:validator` approval and creates a new policy version.

### Network controls

- **Perimeter.** VPC Service Controls (GCP), PrivateLink plus Network Firewall (AWS) or Private Endpoints (Azure). No public ingress for the score API; `vl-ingest` reaches only the source systems on an allow-list.
- **Lateral.** Network policies and layer-7 inspection on the service mesh; the rule components read snapshots and policy only.
- **Ingress.** The score API is called by the console and by sibling services over mTLS; the console sits behind the bank's SSO.
- **Zero-trust.** Every inter-service call is authenticated. No "trusted internal network" assumption.

### Threat model

| Threat | Mitigation |
| --- | --- |
| A vendor supplies a report that is forged or covers another product | The score counts a document only after a named reader records its scope; a reader attestation rate is a first-class metric. Authenticity is not verified by the service, and the score says "a document is on file". |
| A vendor uploads a file that carries malware | Uploads go through scanning before they reach the evidence store; documents are served only as downloads, never rendered inline. |
| An analyst edits scores to move a vendor out of the queue | Scores are computed, not typed. Class changes go through `decision_resolutions` with a proposer and a different approver, and a weekly report lists overrides. |
| The weights are quietly changed | The policy file is versioned; each decision records the version; a change needs `vl:validator` approval and is written to `audit_log`. |
| Provider disclosure is false | The disclosed provider is a claim: it is shown with its source, and a contract term makes a false disclosure a breach. The concentration view always shows the unknown bucket and the upper bound. |
| A score is read as a guarantee | Every decision lists what it cannot see: evidence authenticity, risk no field reveals, undisclosed providers. |

---

## 4a. APIs consumed and exposed

VendorLens is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Vendor register | REST or export, read-only token from Vault | Vendors, criticality, data access, provider, critical use cases | Last snapshot used and marked stale |
| Questionnaire tool | REST or export, read-only token | Answers per vendor | Last snapshot used and marked stale |
| Contract repository | REST or export, read-only token | Exit clause, exit test, portability days, audit right, notice days, contract end | Contract-backed answers keep their last status; P3 |
| Bank IdP (Okta / Entra / Ping) | SAML 2.0 + OIDC | Console login, role lookup | Existing sessions continue |
| Third-party risk record | Vendor REST, service principal | File decisions and resolutions | Local audit trail continues; sync resumes later |
| Monitoring (OpenTelemetry to the platform's stack) | OTLP over TLS | Metrics and traces | Local buffer |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/vendors/{id}/score` | OpenAPI 3.1 over HTTPS, mTLS service identity | Console; scheduled re-score |
| `GET /v1/vendors/{id}/decision` | mTLS service identity | Console; third-party risk record |
| `GET /v1/concentration` | mTLS service identity | Console; SwapBrief (13) |
| `GET /v1/vendors/{id}/exit` | mTLS service identity | KillSwitch (25) |
| Console API | OIDC bearer, role-checked by OPA | `vl-console` |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Third-party risk record, ticketing |

The sibling consumers named above (SwapBrief 13, KillSwitch 25) are 🔴 designed, none built.

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** The surface is one score endpoint, one decision endpoint, one estate view and a console. OpenAPI generates the client and the console SDK from one spec.
- **Idempotency key on `score`.** A retried call must not open a second decision. UUID v4 in the `Idempotency-Key` header.
- **The response carries the reasons, not just the class.** The control score and its parts, the concentration flag, the exit state, the cadence and the sentences an analyst reads come back every time, so a vendor can be told what would move the score.
- **The policy version is in every response.** A score without its weights is not auditable.
- **Webhooks are signed, not just authenticated.** HMAC-SHA256 with a per-consumer rotating secret.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry into the platform's existing monitoring | The on-call engineer's existing pane |
| Decisions over time | Postgres + dashboards | HIGH, MEDIUM and LOW counts per tier; overrides per week |
| Evidence age and coverage | Metrics | Stale and missing documents per vendor type |
| Audit log | Postgres, archived to Object Lock | Record-keeping |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **In-scope vendors with a score and a review date inside cadence** | The north star. Everything else supports it. |
| **Documents read by a named person** | Without a reader, the evidence rule counts presence, not reading. |
| **Override rate** | Too high and the weights are wrong or the score is being gamed. |
| **Vendors with a named upstream provider** | The concentration view is a lower bound until this is complete. |
| **Decision latency** | 🔴 Design target is one analyst session; not measured |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P1 | A critical vendor's document expired and the cadence date has passed | Paging |
| P2 | Policy file fails to load; store unavailable | Paging (low urgency) + chat |
| P3 | Contract repository unavailable; a provider crosses the concentration line | Chat |
| P4 | Document without an issue date; weekly override report | Email |

### Rollout

Shadow first: score the estate from what is already on file, show nothing to vendors, and compare the class with what reviewers would have chosen. Then evidence requests for critical vendors, then provider and exit terms, then the queue and cadence, as laid out in the PRD. Automatic rollback of a policy version if the override rate breaches its threshold.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **Object stores.** Object Lock and versioning for documents and decision bundles.
- **Snapshots.** Immutable by design; any snapshot can be re-fetched from the source and re-hashed.
- **DR drill cadence.** Quarterly failover to the secondary region, validated against the third-party risk platform's own recovery objective.

### Runbooks (one page each, in `docs/runbooks/`)

- `high-vendor.md` — a vendor moved to HIGH: read the reasons, find the document or term that would change it, contact the owner
- `override-review.md` — review a class override: proposer, approver, reason
- `document-intake.md` — receive a document, scan it, record scope and reader
- `provider-flag.md` — a provider crossed the concentration line: list the vendors and critical use cases, ask the business for the fallback
- `policy-change.md` — propose, approve and roll out a new policy version
- `evidence-pull.md` — pull the decision, the snapshot and the policy version for a vendor on a date

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against. The statements below are paraphrases written for this exercise, not the text of any rule, and none says what a rule requires.

| Framework | How the design relates (paraphrase written for this exercise, not the text of the rule) |
| --- | --- |
| **SR 23-4 / interagency third-party risk guidance** | The life of a vendor relationship runs from planning through due diligence, contract, ongoing monitoring and termination. The score covers due diligence and ongoing monitoring, the contract fields cover the contract stage, and the exit score covers termination. |
| **SR 26-2 / model risk management** (the 2011 predecessor was SR 11-7) | A vendor's model is still a model the bank is accountable for. The decision record and the policy version are the documentation and ongoing-monitoring trail for the vendor-model dependency. |
| **NIST AI RMF** | The Map and Govern functions relate to knowing which third-party components an AI system depends on; the provider map and the policy file are the artifacts. |
| **EU AI Act** | The split between a provider of an AI system and a deployer is the reason the design records the upstream provider behind each vendor service. |
| **SOC 2 Type II, GDPR, India data localization** | Regional instances, access-controlled documents, append-only audit. |

---

## 7. What's deliberately not here

- **A model that reads vendor documents.** The rule counts a document as valid after a person records its scope and reads it. A model that summarizes a report would add a second thing to validate.
- **A replacement for the contract review or the right to audit.** VendorLens tells you where to look; it does not replace looking.
- **A claim that it detects a weak vendor from the paper alone.** The prototype shows what it misses: risk no field reveals, undisclosed providers, documents that are present but say nothing good.
- **A runtime proxy to the vendor.** It decides at review time. Runtime failure handling is a different system.
- **Financial health scoring and spend.** Spend per vendor belongs to InferenceLens (07).
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each one is already owned by another system or another phase.

---

## Appendix — sample API contract

```python
# POST /v1/vendors/V-34/score
# Auth: mTLS service identity
# Header: Idempotency-Key: <uuid>
{
    "vendor_id": "V-34",
    "snapshot": "latest"
}
# Response 200
{
    "decision": {
        "risk_class": "high",
        "risk_score": 53.2,
        "control_score": 34.8,
        "parts": {"control": 28, "exit": 17, "contract": 8, "concentration": 0},   # rounded, as step 4 prints them
        "exit": {"score": 0, "state": "not ready", "modeled_days": 180, "allowed_days": 90},
        "concentration": {"flagged": False, "provider": "MP-4"},
        "cadence_days": 365,
        "next_review_on": "2027-04-28"
    },
    "reasons": [
        "control score 34.8 of 100; 11 yes answers with no valid document; 2 contradicted by the contract",
        "no exit clause",
        "no audit right, no notice of model changes"
    ],
    "policy_version": "illustrative",
    "decision_id": "c1a7f0de-..."
}
```

The scores, the reasons and the cadence in the example are the prototype's `step_04` output for V-34 on the synthetic data. The policy version and ids are illustrative.

OpenAPI spec lives at `docs/api/openapi.yaml` and is the source of truth for the client and the console.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/18-vendorlens-ai-vendor-due-diligence/demo.html).
