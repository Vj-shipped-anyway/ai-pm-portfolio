# Architecture — LeaseGuard

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to an asset-management VP, your CISO, and your platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the verification mechanic as a prototype: mock extraction outputs, rule validators, a router, and a Streamlit app, all on six synthetic leases. Nothing below is claimed as deployed or load-tested. CRE is a personal study interest, not an active investment practice.

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. CRE operators are mostly on AWS or Azure, with GCP in the mix; AWS names are used where a single example helps and the equivalents are called out inline.

![LeaseGuard flow](./assets/leaseguard-flow.svg)

---

## 1. Logical architecture

LeaseGuard does not replace the deployed lease-NLP pipeline, the OCR layer, or the system of record. It takes the primary pipeline's output, verifies every field, and holds back anything doubtful until a paralegal resolves it.

Eight components, each independently deployable.

| Component | Responsibility | Language / framework | Stateful? |
| --- | --- | --- | --- |
| `lg-intake` | Receives the lease document set (main lease, amendments, side letters, exhibits). Checks that every referenced attachment was ingested. | Python 3.11, FastAPI | No |
| `lg-primary-adapter` | Reads the existing pipeline's 12-field output. Does not modify the primary. | Python | No |
| `lg-secondary` | Re-extracts the 12 fields over the same OCR text with a different model (GPT-4o, or a fine-tuned Mistral 7B Instruct). | Python, vendor SDKs | No |
| `lg-rules` | Structural validators per field type: rent is a dollar amount, term is a sane number of months, dates parse, escalation type is in the known set, ROFO is Yes/No. | Pure Python, no ML | No |
| `lg-router` | Combines the checks into one status per field and an action: `auto-clear` or `triage`. | Python | No |
| `lg-triage-ui` | Queue plus document viewer. Shows the primary value, the second model's value, and the source clause highlighted. | React + Next.js + Tailwind, embedded in the system of record where possible | No |
| `lg-writeback` | Writes cleared or resolved values back to the lease-record table. Refuses to write a field that is still flagged. | Python, one connector per system of record | No |
| `lg-scheduler` | Re-verification on amendment events and on a periodic sweep. | Airflow / MWAA / Composer | Stateful (DAG runs) |

All components are stateless except the scheduler. State lives in the data layer (section 3).

### The router's vocabulary (matches the prototype)

| Status | Meaning | Action |
| --- | --- | --- |
| `PASS` | Rules pass, both models agree, no tripwire | auto-clear |
| `DISAGREEMENT` | Second model returned a different value | triage |
| `RULE_VIOLATION` | Value fails its field validator | triage |
| `MISSING` | Primary says `none` for a kick-out or exclusivity clause, but the lease text contains clause language | triage |
| `SIDE_LETTER_TRIPWIRE` | Primary says no ROFO, but the text mentions a side letter, amendment, ROFO, or ROFR | triage |

The triage queue is ordered by modeled dollar exposure per field. In the prototype, a missed kick-out is weighted highest, then exclusivity, CAM cap, and ROFO; a tenant name error is weighted lowest.

### What the prototype measured, and what that implies for the design

On the six-lease synthetic set (72 fields), the deployed pipeline got 55 right. LeaseGuard routed 21 fields to triage: 16 of the 17 wrong fields plus 5 false flags. One wrong field was not routed. Three design consequences follow.

1. **Triage load is a product metric, not a rounding error.** Roughly 3 in 10 fields were routed on this deliberately hard sample. On a real portfolio dominated by standard leases the rate would be lower, but it has to be measured, because queue depth drives paralegal cost.
2. **False flags are cheap if the UI makes them fast.** The span-highlighted view, with both values side by side, is what keeps a false flag to seconds. That is why the viewer is in scope and not an afterthought.
3. **The residual miss is structural.** When both models return the same incomplete value and no rule fires (the `lease_06` kick-out: co-tenancy captured, sales-based clause missed), nothing downstream can see it. Closing that class needs a different check, such as a clause-completeness pass that counts distinct kick-out triggers in the text. It is listed under "what's deliberately not here" because the prototype does not claim to solve it.

**Repo structure** (production shape; monorepo via Bazel or Pants, or pnpm workspaces if the org is JS-comfortable):

```
leaseguard/
├── apps/
│   ├── intake/            # FastAPI: document-set intake + attachment check
│   ├── primary-adapter/   # reads the existing pipeline's output
│   ├── secondary/         # second-model re-extraction
│   ├── rules/             # field validators
│   ├── router/            # status + action per field
│   ├── triage-ui/         # Next.js
│   ├── writeback/         # Yardi / MRI / Argus connectors
│   └── scheduler/         # Airflow DAGs
├── packages/
│   ├── fields/            # the 12-field schema, validators, dollar weights
│   ├── auth/              # shared SSO / OIDC libs
│   └── telemetry/         # OpenTelemetry helpers
├── eval/                  # synthetic leases + ground truth (this repo's data/)
├── infra/
│   ├── terraform/         # multi-cloud IaC
│   ├── kubernetes/        # Helm charts + Kustomize overlays
│   └── policies/          # OPA bundles, IAM templates, network policies
├── docs/
│   ├── ARCHITECTURE.md
│   ├── runbooks/
│   └── api/               # OpenAPI spec
└── tests/
    ├── unit/
    ├── integration/
    └── load/              # k6 / locust
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | Runtime (AWS shown) | GCP | Azure | Why |
| --- | --- | --- | --- | --- |
| `intake`, `router`, `rules`, `writeback`, API | EKS or ECS Fargate | GKE or Cloud Run | AKS or Container Apps | Stateless, scales horizontally |
| `secondary` | Same cluster; vendor API, or self-hosted Mistral 7B behind vLLM on GPU nodes | Same | Same | A data-residency decision made per operator: some will not send lease text to a second vendor |
| `triage-ui` | ECS Fargate behind the operator's SSO | Cloud Run | Container Apps | Asset managers work where they already work |
| `scheduler` | MWAA | Cloud Composer | Data Factory or Airflow on AKS | Existing skill set |

**Throughput shape.** Verification runs per lease, not per customer request, and it is asynchronous. A lease is verified in the minutes after the primary finishes, and nothing is written back until the router and, where needed, a paralegal have cleared it. There is no customer-facing latency budget; the operational budget is time to clear the queue.

**Failure behavior.**

| Failure | Behavior |
| --- | --- |
| Secondary extractor unavailable | Fields are verified by rules and tripwires only; every field the secondary would have checked is marked `UNVERIFIED_SECONDARY` and routed by a stricter policy (configurable: triage the high-dollar fields, hold the rest) |
| Rule layer error | Fail closed: field routed to triage |
| Write-back target unavailable | Resolved values stay in the queue as `READY_TO_WRITE`; retry with backoff; nothing is dropped |
| OCR produced no text for an attachment | Intake flags the document set as incomplete before extraction is trusted |

### Network topology

```
Operator ingestion pipeline / system of record (Yardi, MRI)
   │  event: new or amended document set
   ▼
[WAF + API gateway, OIDC]
   │
   ▼
[lg-intake] ──► [Object storage: versioned, Object Lock]       (private endpoint)
   │
   ▼  queue (SQS / Pub/Sub / Service Bus)
[lg-primary-adapter]  [lg-secondary]  [lg-rules]  [lg-router]   ← private subnet
                          │
                          └──► egress via [Secure Web Proxy], allow-list ──► second-model vendor
                               (or stays in-cluster if the secondary is self-hosted)
   │
   ▼
[PostgreSQL] (private endpoint)      [Redis / queue state]
   │
   ├──► [lg-triage-ui]  ← users via SSO, scoped by asset book
   └──► [lg-writeback] ──► Yardi / MRI / Argus over private connectivity
```

### Region & DR

- Primary and DR regions follow the operator's own footprint.
- Lease content is commercial and tenant-confidential, so regional instances keep documents and extractions in-region. Each regional instance has its own database and key ring; there is no cross-region replication of lease text.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL** | Lease records (mirroring the system of record's lease ID), field extractions, verification results, triage items, resolutions, audit log | Relational integrity and joins; the operator's team already runs it |
| **Object storage (S3 / Blob / GCS) with versioning and Object Lock** | Source PDFs, redlines, OCR artifacts, side letters. Immutable once ingested. | The source of truth for any later dispute |
| **Warehouse (Snowflake / Databricks), read-only** | Portfolio analytics the acquisitions team already queries; LeaseGuard publishes verified fields to it and does not own it | No third lake |
| **Redis or a queue (SQS / Pub/Sub)** | Work distribution for secondary extraction and triage assignment | Simple, TTL-based |

### PostgreSQL schema (the consequential tables)

```sql
CREATE TABLE field_verifications (
    verification_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lease_id          TEXT NOT NULL,
    document_set_sha  TEXT NOT NULL,       -- hash of every ingested file
    field_name        TEXT NOT NULL,       -- one of the 12 fields
    primary_value     TEXT,
    secondary_value   TEXT,
    status            TEXT NOT NULL,       -- PASS / DISAGREEMENT / RULE_VIOLATION / MISSING / SIDE_LETTER_TRIPWIRE
    action            TEXT NOT NULL,       -- auto-clear / triage
    dollar_weight     INT NOT NULL,        -- drives queue order
    verified_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    primary_model     TEXT NOT NULL,       -- model + snapshot, for later forensics
    secondary_model   TEXT
);
CREATE INDEX idx_fv_queue ON field_verifications (action, dollar_weight DESC) WHERE action = 'triage';

-- Append-only: a correction is a new row, never an UPDATE
CREATE TABLE triage_resolutions (
    resolution_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verification_id   UUID NOT NULL REFERENCES field_verifications(verification_id),
    resolved_value    TEXT NOT NULL,
    source_span       TEXT NOT NULL,       -- page + character range of the clause relied on
    reviewer_id       TEXT NOT NULL,
    reason            TEXT NOT NULL,
    resolved_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    written_back_at   TIMESTAMPTZ
);

-- Audit log (immutable, append-only, partitioned by month)
CREATE TABLE audit_log (
    audit_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id     TEXT NOT NULL,
    actor_type   TEXT NOT NULL,            -- user / service
    action       TEXT NOT NULL,
    resource_id  TEXT NOT NULL,
    payload      JSONB
) PARTITION BY RANGE (occurred_at);
```

### Retention & data classification

| Data class | Retention | Storage | Classification |
| --- | --- | --- | --- |
| Field decisions and resolutions | 7 years, matching the REIT data-retention expectation named in the README | Postgres hot for 90 days, then archive to Object Lock | Confidential |
| Audit log | 7 years | Postgres partitioned, archive to Object Lock | Confidential |
| Source documents (PDFs, redlines, side letters) | The operator's lease-file retention policy, usually longer | Object storage, versioned, Object Lock | Confidential, tenant-sensitive |
| OCR artifacts | Same as the source document | Object storage | Confidential |
| Verified fields published to the warehouse | Governed by the warehouse's retention | Snowflake / Databricks | Internal |
| Queue and session state | TTL, hours | Redis / queue | Internal |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with customer-managed keys (CMEK / CMK) in KMS or Key Vault, one key ring per region. Documents, extractions, and database volumes are all covered.
- **In transit.** TLS 1.3 north-south, mTLS east-west through the service mesh.
- **Field-level.** Lease text is encrypted as a document. A tenant name can identify an individual (a small tenant trading under a personal name), so `tenant_name` is masked in logs and telemetry.
- **Database-level.** Transparent data encryption on PostgreSQL, encryption at rest on Redis and the queue.

### Secrets management

- **Primary store.** HashiCorp Vault or the cloud secret manager. No long-lived static credentials.
- **Application secrets** (database passwords, vendor API keys, system-of-record service principals): fetched at boot through workload identity and rotated on the operator's schedule.
- **Service-account keys.** None. IRSA on AWS, Workload Identity on GCP, Managed Identity on Azure.
- **Vendor agreements.** Calls to model vendors send lease text. The design requires a no-training, zero-retention agreement per vendor, or a self-hosted secondary for operators who will not send text out.

### Identity provider & user management

- **IdP.** The operator's own (Okta, Microsoft Entra ID). SAML 2.0 and OIDC. LeaseGuard does not run its own.
- **MFA.** Enforced at the IdP.
- **Sessions.** OIDC ID token plus signed session cookie (HttpOnly, Secure, SameSite=Strict); expiry set by operator policy.
- **Service-to-service identity.** Workload identity per component; mTLS enforces it at every hop.

### RBAC matrix

SSO through the operator's IdP. OPA enforces roles at the API. Roles are scoped per asset book.

| Role | Can | Maps to (operator role) |
| --- | --- | --- |
| `lg:analyst` | Resolve triage items on assigned asset books | Abstraction analyst / paralegal |
| `lg:abstraction-lead` | Analyst + resolve any item, reassign, settle disagreements between reviewers | Senior abstraction lead |
| `lg:asset-manager` | Read verified fields and open items for their book; approve high-dollar resolutions | Asset manager |
| `lg:acquisitions` | Read-only on verified fields and the open-item flag (a deal team should know a field is unresolved) | Acquisitions |
| `lg:admin` | Config, validators, connectors, roles | Platform engineering lead |

**Write-back requires a resolution.** `lg-writeback` will not write any field whose latest status is `triage` without a row in `triage_resolutions`. High-dollar fields can require a second approver.

### Network controls

- **Perimeter.** PrivateLink / Private Service Connect / Private Endpoints to the data stores and the system of record. Egress to the public internet only through a Secure Web Proxy with an allow-list (the second-model vendor, OCR service, NTP).
- **Lateral.** Network policies and layer-7 inspection on the service mesh; only `lg-secondary` may reach the egress proxy.
- **Ingress.** WAF and API gateway for the intake API; the triage UI sits behind the operator's SSO.
- **Zero-trust.** Every inter-service call is authenticated. No "trusted internal network" assumption.

### Leases are untrusted input

A lease PDF is a document from outside the building, often written by the tenant's counsel. Two consequences:

- **Prompt injection through the document.** Text inside a lease can contain instructions. Extraction prompts frame the lease as quoted data, the output is schema-constrained to the 12 fields, and anything that does not parse routes to triage. The rule layer is a second line of defense because it is plain code.
- **Redlines and hidden text.** Struck text, comments, and metadata are carried into OCR and must be tagged as such. The redline-blindness deficiency in the README is a correctness problem and an attack surface.

### Threat model

| Threat | Mitigation |
| --- | --- |
| Instructions embedded in a lease | Quoted-data framing, schema-constrained output, rules in plain code |
| Reviewer clears a flag without reading | Resolution requires the source span; random second-review sampling by the abstraction lead |
| Cross-book data exposure | Row-level security, per-book object prefixes, audit of every read |
| Silent change in the primary pipeline's model | Primary model and snapshot recorded per verification; a step change in the disagreement rate is itself an alert |
| Wrong value written to the system of record | Write-back only after clearance; each write carries the `verification_id` |
| Lease text sent to a vendor that retains it | Zero-retention agreement required, or self-hosted secondary |

---

## 4a. APIs consumed and exposed

LeaseGuard is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Primary extraction pipeline output | Table or event feed from the operator's existing pipeline | The values being verified | Intake queues documents |
| Second-model vendor (OpenAI / hosted Mistral) | REST, key from Vault | Re-extraction | See the failure table in section 2 |
| OCR (Textract / Tesseract), vision fallback for redlines | Cloud SDK | Text from scanned or redlined PDFs | Intake marks documents incomplete |
| Yardi Voyager / MRI / Argus Enterprise | Vendor REST or file import, service principal | Write-back of verified values; Argus import for the cash-flow side | Resolved values wait as `READY_TO_WRITE` |
| CoStar / CompStak / Cherre | REST | Auxiliary benchmark feeds | Skipped; not on the critical path |
| IdP, Vault, KMS, Datadog, PagerDuty | Standard | Auth, secrets, keys, telemetry, paging | Cached or buffered |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/verifications` (submit a document set) | OIDC bearer or mTLS | The operator's ingestion pipeline |
| `GET /v1/leases/{id}/fields` (verified fields plus open items) | OIDC bearer, role-checked | Asset management, acquisitions tools |
| Webhooks (outbound) | HTTPS POST, HMAC-signed | Workflow tools, CAM reconciliation |

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** Two read surfaces and one submit endpoint. OpenAPI generates the ingestion-side client and the UI SDK from one spec.
- **Open items travel with the values.** `GET /fields` returns each field with its status and whether a resolution exists, so a downstream tool can see that a value is still unresolved instead of treating it as final.
- **Idempotency key on submit.** Re-submitting the same document set (same `document_set_sha`) returns the existing verification instead of creating a second one.
- **Webhooks are signed, not just authenticated.** HMAC-SHA256 with a per-consumer rotating secret.
- **No tenant names or lease text in URLs.** Lease and document identifiers are opaque ids.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Logs and traces | OpenTelemetry to Datadog | The operator's existing pane |
| LLM extraction traces | Langfuse | Needed to debug one disputed field |
| Queue depth and age of oldest item | Datadog metrics | Stale items mean stale lease records |
| Audit log | Postgres, archived to Object Lock | Record-keeping |

**Metrics worth owning.**

| Metric | Why |
| --- | --- |
| **Triage rate** (fields routed / fields verified) | Drives paralegal cost |
| **False-flag rate** (routed fields where the primary was right) | Tells you whether the rules and tripwires are too loose |
| **Resolved-wrong rate** (second review overturns a resolution) | Quality of the human step |
| **Disagreement rate between primary and secondary**, by field | A step change means one model changed |
| **Age of oldest triage item** | Stale items mean stale lease records |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P2 | Write-back failing for more than a set window; secondary extractor down | PagerDuty (low urgency) + Slack |
| P3 | Triage queue age above SLA; disagreement-rate step change; reviewer-overturn spike | Slack |
| P4 | Daily digest of open items by asset book | Email |

### Rollout

Run in shadow on one asset book first, starting with the redlined and non-standard subset where the lift is largest. Compare LeaseGuard's flags with what the existing CAM reconciliation process later found. Expand book by book.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **Object stores.** Versioning and Object Lock for source documents and OCR artifacts; cross-region replication only where residency allows.
- **Queue state.** Rebuildable from `field_verifications` and the document-set hashes.
- **DR drill cadence.** Quarterly failover to the secondary region, validated against the operator's recovery objective.

### Runbooks (one page each, in `docs/runbooks/`)

- `secondary-model-down.md` — fall back to rules and tripwires with the stricter routing policy
- `queue-backlog.md` — triage queue age above SLA
- `writeback-failure.md` — resolved values stuck in `READY_TO_WRITE`
- `new-lease-form-onboarding.md` — add validators and a test lease for a new form type
- `reviewer-overturn-spike.md` — second review is reversing many resolutions

---

## 6. Compliance posture

Alignment, not certification.

| Framework | How the design relates |
| --- | --- |
| **SOC 2 Type II** | All components in scope; the audit log and access reviews are the evidence |
| **Record retention** | Seven-year field-decision retention; immutable source documents |
| **Data residency / GDPR** | Regional instances where lease content is in scope |
| **SOX-adjacent controls for REIT reporting** | The resolution trail (who, what, which clause) is the control evidence for a changed lease record |

---

## 7. What's deliberately not here

- **A replacement for the deployed extraction pipeline.** Fine-tuning the primary is not the strategy; the README's three-backend comparison (hypothetical inputs, not measured in this repo) shows no single model wins all six deficiency classes.
- **A new system of record.** Verified values flow back into Yardi, MRI, or Argus.
- **A new OCR engine.**
- **A clause-completeness check.** The one miss in the prototype (both models return a partial kick-out) needs a check that counts distinct trigger clauses in the text. Designed, not built.
- **Autonomous write-back of flagged fields.** A human clears them.
- **A standalone authentication system.** It uses the operator's IdP.

---

## Appendix — sample verification record

```python
# One row from the router for lease_04 / base_rent_psf (values from the synthetic eval set)
{
    "lease_id": "lease_04",
    "field_name": "base_rent_psf",
    "primary_value": "48.00",         # struck-through value read from the redline
    "secondary_value": "42.50",
    "status": "DISAGREEMENT",
    "action": "triage",
    "dollar_weight": 42000,           # prototype weight for a rent-per-SF error on a five-year lease
    "resolution": {"resolved_value": "42.50", "source_span": "lease_04_redlined_retail.txt, lines 19-20, BASE RENT [INSERT] block"}
}
```

The dollar weights are the prototype's modeled values, not measured losses. OpenAPI spec lives at `apps/intake/openapi.yaml` and is the source of truth for the ingestion-side client and the triage UI.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/03-leaseguard-cre-lease-verification/demo.html).
