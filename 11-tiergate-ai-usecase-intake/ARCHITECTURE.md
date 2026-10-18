# Architecture — TierGate

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO, your data governance lead and your platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (a seeded synthetic data generator, four standard-library step scripts and a Streamlit app, all on 150 synthetic submissions). Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. GCP is shown as primary; AWS and Azure equivalents are called out inline.

![TierGate flow](./assets/tiergate-flow.svg)

---

## 1. Logical architecture

TierGate is a decision layer between the intake form and the review queue. It does not replace the intake form, the data catalog, the vendor registry, the model inventory or the model risk review. It decides three things for each submission: what tier, what evidence the tier owes, and where the review sits in the queue.

Eight components. Four are in the sponsor's submit path; four are not.

| Component | Responsibility | Language / framework | In submit path? | Stateful? |
| --- | --- | --- | --- | --- |
| `tg-intake` | Receives the form, validates the fields, stores an immutable form version. A change after submission is a new version. | Python 3.11, FastAPI, Pydantic v2 | Yes, sync | No (writes Postgres) |
| `tg-checker` | Cross-checks the form against the catalog's recorded class, the vendor registry and the text. Emits flags, each with a reason code and a reason sentence. Reads form fields only. | Python | Yes, sync | No |
| `tg-rubric` | Applies the versioned rubric to the checked inputs and writes the tier decision with its inputs and rubric version. | Python; rubric config in Postgres, cached | Yes, sync | No (reads config) |
| `tg-evidence` | Holds the checklist per tier, computes the gate state (READY or HOLD), requests missing items up front, stores evidence hashes. | Python | Yes, sync for gate state; item intake async | Stateful |
| `tg-linker` | Proposes duplicate or overlapping links by token overlap over an inverted index. Proposals only. | Python | No, async | Stateful (index) |
| `tg-queue` | Priority queue keyed by recomputed tier, then arrival, with an aging cap (design). Assigns reviewers. | Python | No | Stateful |
| `tg-console` | Console for the governance lead, reviewers, sponsors and the CRO: the register, the flag list, the queue, the decision record. | React, Next.js | No | No |
| `tg-telemetry` | OpenTelemetry spans and metrics from every component, exported off the submit path. | OTel Collector to the bank's monitoring | No, async | No |

**What is in the submit path, and what is not.** Only the intake, the checker, the rubric and the gate state. The linker, the queue, telemetry and the console are out of band. A sponsor sees the recomputed tier, the flags and the evidence list within the submission flow (the latency is a design target, not measured here); the duplicate proposal and the queue position can arrive after.

**Where the prototype stops.** The four step scripts implement the recompute, the flags, the similarity score, the gate and the queue simulation on synthetic CSVs. Everything on this page that touches a real catalog, registry, identity provider or queue is a design.

**Repo structure** (production shape; monorepo):

```
tiergate/
├── apps/
│   ├── intake/         # form capture, versioning
│   ├── checker/        # cross-checks and flags
│   ├── rubric/         # tier decision writer
│   ├── evidence/       # checklist, gate, item requests
│   ├── linker/         # duplicate proposals
│   ├── queue/          # tier-ordered queue, aging cap
│   └── console/        # governance and reviewer UI
├── config/
│   ├── rubric/         # versioned points tables and tier cuts (proposer and approver)
│   └── checklist/      # evidence items per tier, with interlock tags
├── golden/             # labeled sample for regression runs (the audit sample, never customer data)
├── infra/
│   ├── terraform/
│   ├── kubernetes/
│   └── policies/       # OPA bundles, IAM templates, network policies
├── docs/
│   ├── ARCHITECTURE.md
│   ├── runbooks/
│   └── api/            # OpenAPI spec
└── tests/
    ├── unit/
    ├── integration/
    └── load/
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `tg-intake`, `tg-checker`, `tg-rubric`, `tg-evidence` | GKE, same cluster as the bank's other governance tools | EKS | AKS | Stateless services; the volume is hundreds of submissions a year in the model, so a small replica count is enough (design) |
| `tg-linker`, `tg-queue` | GKE, one replica each, leader-elected | EKS | AKS | Small stateful workers; the index is rebuilt from Postgres on start |
| `tg-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI behind the bank's SSO |
| Scheduled jobs (catalog snapshot, freshness check) | Cloud Scheduler plus Cloud Run jobs | EventBridge plus Fargate tasks | Logic Apps or Container Apps jobs | Small and scheduled |

**Failure behavior (the decision that matters most).** The gate fails closed and the recompute never fails down.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Catalog unreachable | Use the form's data class, flag the case "class unverified", never lower a tier | P3 |
| Vendor registry unreachable | Use the form's vendor model, flag "vendor unverified" | P3 |
| Checklist configuration unreadable | Gate state is HOLD for every case until it loads | P2 |
| Rubric configuration unreadable | Use the last cached version and mark each decision with it; if none is cached, no decision is written and the case waits | P2 |
| Linker or queue worker down | Submissions still get a tier and a gate state; duplicate proposals and queue order resume on restart | P3 |
| Telemetry sink down | Buffer locally; drop with a counter once the buffer fills | P4 |

**Latency.** There is no latency measurement in this repo. The recompute is arithmetic on a few lookups, and the budget a sponsor feels is the catalog and registry reads. That has to be set against the real systems.

### Network topology

```
Sponsor / reviewer / governance lead / CRO
   │  (browser, bank SSO)
   ▼
[Bank WAF / API gateway]                               (the bank's existing front door)
   │
   ▼
[tg-console]  ── OIDC bearer ──►  [tg-intake] ─► [tg-checker] ─► [tg-rubric] ─► [tg-evidence]
                                         │              │
                                         │              ├──► [data catalog API]       (read-only, private endpoint)
                                         │              └──► [vendor registry API]    (read-only, private endpoint)
                                         ▼
                              [PostgreSQL: register, decisions, flags, evidence hashes]
                              [Object storage, write-once: evidence files]
   async: [tg-linker] [tg-queue] [OTel Collector] ──► the bank's monitoring

Egress: none to the public internet. Catalog, registry, identity provider and monitoring are all inside the bank's network.
```

### Region & DR

- The primary and DR regions follow the bank's own footprint. TierGate gets the recovery objective of the register it feeds, not a different one.
- Region-specific instances where data residency applies. Each has its own database and key ring; nothing replicates across a residency boundary.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | The use-case register, form versions, tier decisions, flags, evidence records, duplicate proposals, queue state, rubric versions, audit log | Relational integrity for the decision record; the bank's operations team already runs it |
| **Object storage with write-once retention** | Evidence files (validation reports, privacy reviews, legal reviews, sign-offs) | The register stores hashes; the files cannot be altered after the fact |
| **Read-only connectors** | The data catalog and the vendor registry | Source of truth stays where it is; TierGate holds a dated snapshot of what it read, per decision |

### PostgreSQL schema (the consequential tables)

```sql
-- One row per AI use case in the register
CREATE TABLE use_cases (
    use_case_id     TEXT PRIMARY KEY,           -- UC-nnn
    sponsor_unit    TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_tier    SMALLINT,                   -- latest recomputed tier, derived from tier_decisions
    gate_state      TEXT                        -- READY / HOLD, derived from evidence records
);

-- Immutable: a change after submission is a new version
CREATE TABLE form_versions (
    use_case_id     TEXT NOT NULL REFERENCES use_cases,
    version         INT NOT NULL,
    submitted_at    TIMESTAMPTZ NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    dataset_name    TEXT NOT NULL,
    customer_facing TEXT NOT NULL,              -- yes / no / unsure / blank
    decision_autonomy TEXT NOT NULL,
    data_class      TEXT NOT NULL,
    vendor_model    TEXT NOT NULL,
    regulatory_scope TEXT NOT NULL,
    exposure_band   TEXT NOT NULL,
    declared_tier   SMALLINT NOT NULL,
    PRIMARY KEY (use_case_id, version)
);

-- Append-only: every recompute is a new row with its inputs and the rubric version
CREATE TABLE tier_decisions (
    decision_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    use_case_id     TEXT NOT NULL,
    form_version    INT NOT NULL,
    rubric_version  TEXT NOT NULL,
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checked_inputs  JSONB NOT NULL,             -- class, vendor, customer-facing as checked, plus the other three
    catalog_snapshot TEXT NOT NULL,             -- id of the dated catalog read
    registry_snapshot TEXT NOT NULL,
    points          SMALLINT NOT NULL,
    recomputed_tier SMALLINT NOT NULL,
    declared_tier   SMALLINT NOT NULL
);

CREATE TABLE flags (
    flag_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id     UUID NOT NULL REFERENCES tier_decisions,
    code            TEXT NOT NULL,              -- DATA_CLASS_BELOW_CATALOG, VENDOR_NOT_DECLARED, ...
    reason          TEXT NOT NULL,              -- the sentence a reviewer reads
    status          TEXT NOT NULL,              -- open / confirmed / cleared / contested
    resolved_by     TEXT,
    resolved_at     TIMESTAMPTZ
);

CREATE TABLE rubric_versions (
    rubric_version  TEXT PRIMARY KEY,
    effective_from  TIMESTAMPTZ NOT NULL,
    points_table    JSONB NOT NULL,
    tier_cuts       JSONB NOT NULL,
    proposed_by     TEXT NOT NULL,
    approved_by     TEXT NOT NULL,              -- a different person from proposed_by
    reason          TEXT NOT NULL
);

CREATE TABLE evidence_items (
    evidence_id     TEXT NOT NULL,              -- E01 ...
    checklist_version TEXT NOT NULL,
    first_tier      SMALLINT NOT NULL,          -- cumulative: required at this tier and above
    item            TEXT NOT NULL,
    interlock       TEXT,                       -- 04 EvalForge, 08 OversightOps, 09 LineageLog
    PRIMARY KEY (evidence_id, checklist_version)
);

CREATE TABLE evidence_submissions (
    use_case_id     TEXT NOT NULL,
    evidence_id     TEXT NOT NULL,
    file_sha256     TEXT NOT NULL,
    attached_by     TEXT NOT NULL,
    attached_at     TIMESTAMPTZ NOT NULL,
    accepted_by     TEXT,                       -- reviewer who accepted it
    PRIMARY KEY (use_case_id, evidence_id, file_sha256)
);

CREATE TABLE duplicate_links (
    use_case_id     TEXT NOT NULL,              -- the later submission
    linked_to       TEXT NOT NULL,              -- the best earlier match
    overlap         NUMERIC(4,3) NOT NULL,
    status          TEXT NOT NULL,              -- proposed / confirmed / rejected
    confirmed_by    TEXT,
    PRIMARY KEY (use_case_id, linked_to)
);

-- Audit log (immutable, append-only, partitioned by month)
CREATE TABLE audit_log (
    audit_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id        TEXT NOT NULL,
    actor_type      TEXT NOT NULL,              -- user / service_account
    action          TEXT NOT NULL,
    resource_type   TEXT NOT NULL,
    resource_id     TEXT NOT NULL,
    request_id      TEXT NOT NULL,
    payload         JSONB,
    result          TEXT NOT NULL               -- success / failure / forbidden
) PARTITION BY RANGE (occurred_at);
```

**What the decision record has to answer.** For any use case, an auditor can ask: which form version, which rubric version, which catalog and registry snapshots, which flags, who cleared them, and which evidence hashes were on file when approval was granted. Every one of those is a column above.

### ClickHouse schema (the time-series tables)

Not in the reference design, on purpose. At the intake volume the model uses (375 submissions a year) the time series are small: queue age, flag counts by rule, tier changes by sponsor unit. They are a few Postgres tables and views. A columnar time-series store would add an operational burden with no query that needs it. The trigger to revisit is a register that grows to tens of thousands of use cases or per-event telemetry from many services; until then:

```sql
CREATE TABLE queue_events (
    use_case_id     TEXT NOT NULL,
    event           TEXT NOT NULL,              -- queued / review_started / review_done / held / released
    tier            SMALLINT NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL
);
-- queue wait by tier is a view over queue_events; flag precision by rule is a view over flags
```

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-retention schedule before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Form versions and tier decisions | Life of the use case plus 7 years | Postgres, append-only | Confidential |
| Flags and their resolutions | Same as the decision | Postgres | Confidential |
| Evidence files | Life of the use case plus 7 years | Object storage, write-once | Confidential to restricted, by content |
| Evidence hashes | Same as the files | Postgres | Internal |
| Rubric and checklist versions | Permanent | Postgres, append-only | Internal |
| Catalog and registry snapshots read per decision | Same as the decision | Postgres | Internal |
| Queue events | 3 years | Postgres | Internal |
| Audit log | 7 years | Postgres partitioned, archived to write-once storage | Confidential |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with customer-managed keys in Cloud KMS, AWS KMS or Azure Key Vault, one key ring per region. Keys never cross a region boundary.
- **In transit.** TLS 1.3 north-south. mTLS east-west through the service mesh.
- **Evidence files.** Encrypted at rest with the object store's customer-managed keys; the register stores only the SHA-256 and a pointer.
- **Database-level.** Transparent data encryption on PostgreSQL.

### Secrets management

- **Primary store.** HashiCorp Vault or the cloud secret manager. No long-lived static credentials.
- **Application secrets** (database passwords, read-only connector credentials): fetched at boot through workload identity, rotated on the bank's schedule.
- **Service-account keys.** None. Workload Identity on GCP, IAM Roles for Service Accounts on AWS, Managed Identity on Azure.

### Identity provider & user management

- **IdP.** Whatever the bank already runs (Okta, Microsoft Entra ID, Ping). SAML 2.0 and OIDC. TierGate does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Sessions.** OIDC ID token plus signed session cookie (HttpOnly, Secure, SameSite=Strict), with absolute and idle expiry set by bank policy.
- **Service-to-service identity.** SPIFFE IDs; each component has its own workload identity and mTLS enforces it at every hop.

### RBAC matrix

Authorization is enforced at the API with OPA, and every decision is written to `audit_log`. Row-level access follows the sponsor unit.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `tg:sponsor` | Submit and revise forms for their own unit; read their decisions; answer flags; attach evidence | Line-1 use-case sponsor |
| `tg:reviewer` | Read the queue; accept or reject evidence; confirm or reject duplicate links; record a review | Model risk reviewer |
| `tg:governance-lead` | Reviewer rights plus propose rubric and checklist changes; resolve contested flags; read the full register | AI governance lead (line 2) |
| `tg:approver` | Approve rubric and checklist changes proposed by someone else | CRO's delegate |
| `tg:viewer` | Read the register and the decision record | CRO, internal audit |
| `tg:steward` | Read flags raised against their datasets; update the catalog in the catalog system, not here | Data catalog steward |
| `tg:admin` | Configuration, integrations, role management | Platform engineering lead |

A rubric or checklist change needs a proposer and a different approver. Both are recorded in `rubric_versions`.

### Network controls

- **Perimeter.** VPC Service Controls (GCP), PrivateLink plus Network Firewall (AWS), or Private Endpoints (Azure). No egress to the public internet.
- **Lateral.** Network policies and layer-7 inspection on the service mesh; the checker may call the catalog and registry read endpoints and nothing else.
- **Ingress.** Only the console and the API gateway, behind the bank's SSO.
- **Zero-trust.** Every inter-service call is authenticated. No "trusted internal network" assumption.

### Threat model

| Threat | Mitigation |
| --- | --- |
| Sponsor writes the description to avoid the customer cue | The catalog and the registry are second sources the sponsor does not control; the structured channel question replaces the free-text cue (PRD backlog item 2); discrepancy rate per sponsor unit is reported to the governance lead |
| Sponsor edits the form after a decision to change the tier | Form versions are immutable; an edit is a new version and a new tier decision; both are kept |
| Rubric quietly changed to lower tiers | Rubric versions are append-only with a proposer and a different approver; every decision records the version it used; a weekly report shows tier mix by rubric version |
| Evidence file swapped after acceptance | The register stores the SHA-256 at acceptance; files sit in write-once storage; a mismatch on read opens an incident |
| Catalog entry edited to hide a class | TierGate has read-only access and stores a dated snapshot with each decision; a snapshot diff job flags class decreases between snapshots |
| Form and catalog both wrong (the known limit) | Not closed. Mitigated by the catalog freshness check, a third source for data class (lineage scan, backlog item 13) and the known-limit count on the governance lead's console |
| Tier ordering starves low-risk cases | Aging cap on the queue (design, not built); tier 1-2 wait is a reported metric with an owner |
| Cross-unit reading of submissions | Row-level access by sponsor unit enforced at the API; reviewer and governance roles are explicit grants |
| Free text steering an automated reader | There is no model reading the free text; the cue check is a keyword match. If a future version added one, the text should be treated as data to score, never as instructions, layered with [PromptShield](../06-promptshield-prompt-injection-defense/) |

---

## 4a. APIs consumed and exposed

TierGate is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Data catalog | REST, service principal, read-only | Recorded class and freshness date per dataset name | Fall back to the form's class, flag "class unverified", never lower a tier |
| Vendor registry | REST, service principal, read-only | Vendor model per use case | Fall back to the form, flag "vendor unverified" |
| Model inventory | REST, service principal | Write the tier and the register id for approved use cases | Local register continues; sync resumes later |
| Bank IdP (Okta / Entra / Ping) | SAML 2.0 and OIDC | Console login, role lookup | Existing sessions continue |
| GRC tool | Vendor REST, service principal | File the decision record and open evidence requests | Local record continues; sync resumes later |
| Monitoring and paging | HTTPS, key from Vault | Metrics and alerts | Local buffer, email fallback |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/submissions` | OpenAPI 3.1 over HTTPS, OIDC bearer | The console; the bank's existing intake form if it keeps its own front end |
| `GET /v1/submissions/{id}/decision` | Same | The console, the model inventory, the interlocked projects |
| `POST /v1/flags/{id}/resolve` | Same, role-checked by OPA | The console |
| `GET /v1/register` | Same | CRO and audit views |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | 12 ValueLedger on approval; 09 LineageLog for the evidence trail; the GRC tool |

### API-design opinions (the choices a reviewer will ask about)

- **The response carries the reason, not just the verdict.** Every decision returns the tier, the points, the rubric version, each flag with its reason, and the missing evidence ids, so a reviewer can reconstruct why a tier changed.
- **Idempotency key on submit.** A retried submission must not create a second use case. UUID v4 in the `Idempotency-Key` header.
- **Flags are proposals with a status.** The recompute resolves an ambiguous answer conservatively so the tier is safe, and the flag stays open until the sponsor confirms or corrects.
- **REST and OpenAPI, not GraphQL.** The surface is a small set of resources. OpenAPI generates the client and the console SDK from one spec.
- **No sponsor free text in URLs.** Identifiers only.
- **Webhooks are signed, not just authenticated.** HMAC-SHA256 with a per-consumer rotating secret.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry to the bank's monitoring | The operations team's existing pane |
| Queue age and wait by tier | Postgres views, exported as metrics | The cost side of ordering by tier |
| Flag volume and precision by rule | Postgres views over `flags` | Tells the governance lead which rule to retire or tighten |
| Tier mix by rubric version | Postgres view over `tier_decisions` | Detects a rubric change that moved the mix |
| Audit log | Postgres, archived to write-once storage | Record-keeping |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **Tier 3-4 time to first review** | The benefit side of ordering. Read it beside tier 1-2 wait; either alone misleads. |
| **Tier 1-2 time to first review** | The cost side. The aging cap exists to bound it. |
| **Flag precision by rule** | Over-flagging is the main way the layer loses the business's trust. |
| **Approvals granted with required evidence missing** | The control outcome. Design target zero. |
| **Catalog freshness** | A recompute is only as good as the freshest entry. |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P1 | An approval granted while the recomputed tier's checklist was incomplete | Paging |
| P2 | Checklist or rubric configuration unreadable; flag precision under its floor for a rule | Paging (low urgency) |
| P3 | Catalog or registry unreachable; queue age above its limit for tier 3-4 | Chat channel |
| P4 | Weekly digest: tier mix, flag counts, known-limit count | Email |

### Rollout

Shadow first: recompute and log beside the declared tier and change nothing for sponsors, so flag precision per rule is known before anyone is affected. Then flags to sponsors, then the evidence gate for tier 3 and 4, then the ordered queue one business unit at a time, as set out in the PRD. Durations are design targets.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **Object stores.** Write-once retention and versioning for evidence files.
- **Configuration.** Rubric and checklist versions are rows in Postgres and also exported to the repo's `config/` directory on every approval.
- **DR drill cadence.** Quarterly failover to the secondary region, validated against the register's own recovery objective (design).

### Runbooks (one page each, in `docs/runbooks/`)

- `catalog-unreachable.md` — the recompute is falling back to the form
- `rubric-change.md` — propose, approve and roll back a rubric version
- `checklist-change.md` — the same for the evidence checklist
- `flag-precision-low.md` — a rule is over-flagging; tighten or retire it
- `evidence-hash-mismatch.md` — a file does not match the hash accepted
- `decision-record-pull.md` — pull the record for an examiner by use case id

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against.

| Framework | How the design relates |
| --- | --- |
| **SR 11-7 / model risk management** | A complete, tiered inventory; validation depth proportional to tier; effective challenge on tier 3 and above (evidence item E05). TierGate decides the tier and the evidence owed. It does not do the validation. |
| **NIST AI RMF, Govern** | One register, accountable owners, a written and versioned policy (the rubric and the checklist), separation of proposer and approver. |
| **NIST AI RMF, Map** | The six form questions capture context and impact per system; the recompute checks them against second sources. |
| **EU AI Act risk categories** | The four tiers are an internal scale, not the Act's categories. A mapping between them is a design item and needs legal review before any claim is made. |
| **The bank's record-retention schedule** | The retention periods above are defaults to be confirmed against it. |

---

## 7. What's deliberately not here

- **A model that reads the free text.** The cue check is a keyword match. A classifier would not fix the weak spot; a structured channel question on the form would.
- **A parallel inventory.** TierGate reads from and writes back to the model inventory the bank already runs.
- **Automatic approval.** TierGate holds or releases a gate state. A person approves.
- **Auto-lowering of a tier.** The recompute only takes the higher of two sources. A tier goes down by a person's decision on a contested flag, recorded.
- **A claim that it detects a wrong catalog.** When the form and the catalog agree on a wrong class, nothing disagrees. That limit is printed in the prototype and called out in the PRD.
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each one is already owned by another system or needs a decision that is not an engineering one.

---

## Appendix — sample API contract

```python
# GET /v1/submissions/UC-132/decision
# Auth: OIDC bearer, role tg:sponsor (own unit), tg:reviewer, tg:governance-lead or tg:viewer
{
    "use_case_id": "UC-132",
    "form_version": 1,
    "declared_tier": 1,
    "recomputed_tier": 3,
    "points": 9,
    "rubric_version": "design-example",
    "flags": [
        {"code": "DATA_CLASS_ABOVE_CATALOG",
         "reason": "form says restricted; the catalog records confidential for d_account_master; kept the higher class, steward to review the catalog entry",
         "status": "open"},
        {"code": "CUSTOMER_FACING_CUE",
         "reason": "form says internal; the text mentions 'consumers'; treated as customer-facing until the sponsor confirms",
         "status": "open"},
        {"code": "TIER_DECLARED_BELOW",
         "reason": "sponsor declared tier 1; the rubric on the checked inputs gives tier 3 (9 points)",
         "status": "open"}
    ],
    "gate": "HOLD",
    "missing_evidence": ["E05", "E06", "E08"],
    "duplicate_proposals": [],
    "decision_id": "c1a7f0de-..."
}
```

The tier, points, flags and missing evidence are the prototype's `step_04` output for `UC-132`. The rubric version, form version, flag status and decision id are illustrative.

OpenAPI spec lives at `apps/intake/openapi.yaml` and is the source of truth for the console and any client.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/11-tiergate-ai-usecase-intake/demo.html).
