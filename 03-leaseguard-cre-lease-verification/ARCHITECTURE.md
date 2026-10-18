# Architecture — LeaseGuard

The systems doc most PM writeups skip: what runs where, what is stored, what a failure does, and what you would hand to an asset-management VP, a CISO, and a platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the verification mechanic as a prototype: mock extraction outputs, rule validators, a router, and a Streamlit app, all on six synthetic leases. Nothing below is claimed as deployed or load-tested. CRE is a personal study interest, not an active investment practice.

Cloud-agnostic where the design allows it; AWS names are used where a single example helps.

![LeaseGuard flow](./assets/leaseguard-flow.svg)

---

## 1. Logical architecture

LeaseGuard does not replace the deployed lease-NLP pipeline, the OCR layer, or the system of record. It takes the primary pipeline's output, verifies every field, and holds back anything doubtful until a paralegal resolves it.

| Component | Responsibility | Stack | Stateful? |
| --- | --- | --- | --- |
| `lg-intake` | Receives the lease document set (main lease, amendments, side letters, exhibits). Checks that every referenced attachment was ingested. | Python 3.11, FastAPI | No |
| `lg-primary-adapter` | Reads the existing pipeline's 12-field output. Does not modify the primary. | Python | No |
| `lg-secondary` | Re-extracts the 12 fields over the same OCR text with a different model (GPT-4o, or a fine-tuned Mistral 7B Instruct). | Python, vendor SDKs | No |
| `lg-rules` | Structural validators per field type: rent is a dollar amount, term is a sane number of months, dates parse, escalation type is in the known set, ROFO is Yes/No. | Pure Python, no ML | No |
| `lg-router` | Combines the checks into one status per field and an action: `auto-clear` or `triage`. | Python | No |
| `lg-triage-ui` | Queue plus document viewer. Shows the primary value, the second model's value, and the source clause highlighted. | React + Next.js + Tailwind, embedded in the system of record where possible | No |
| `lg-writeback` | Writes cleared or resolved values back to the lease-record table. Refuses to write a field that is still flagged. | Python, connectors per system of record | No |
| `lg-scheduler` | Re-verification on amendment events and on a periodic sweep. | Airflow / MWAA / Composer | Stateful (DAG runs) |

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
2. **False flags are cheap if the UI makes them fast.** The span-highlighted view, with both values side by side, is what keeps a false flag to seconds. This is why the viewer is in scope and not an afterthought.
3. **The residual miss is structural.** When both models return the same incomplete value and no rule fires (the `lease_06` kick-out: co-tenancy captured, sales-based clause missed), nothing downstream can see it. Closing that class needs a different check, such as a clause-completeness pass that counts distinct kick-out triggers in the text. It is listed under "what is not here" below because the prototype does not claim to solve it.

**Repo structure** (production shape):

```
leaseguard/
├── apps/
│   ├── intake/  primary-adapter/  secondary/  rules/  router/
│   ├── triage-ui/        # Next.js
│   ├── writeback/        # Yardi / MRI / Argus connectors
│   └── scheduler/        # Airflow DAGs
├── packages/
│   ├── fields/           # the 12-field schema, validators, dollar weights
│   └── telemetry/
├── eval/                 # synthetic leases + ground truth (this repo's data/)
└── infra/                # terraform, helm, OPA policies
```

---

## 2. Physical / deployment architecture

| Component | Runtime | Why |
| --- | --- | --- |
| `intake`, `router`, `rules`, `writeback`, API | Containers on the operator's existing Kubernetes (EKS / AKS / GKE) or a managed container service | Stateless, scales horizontally |
| `secondary` | Same cluster; calls a vendor API, or a self-hosted Mistral 7B behind vLLM if the operator will not send lease text to a second vendor | A data-residency decision, made per operator |
| `triage-ui` | Container behind the operator's SSO; embedded in the system of record where it supports extensions | Asset managers work where they already work |
| `scheduler` | Managed Airflow | Existing skill set |

**Throughput shape.** Verification runs per lease, not per request, and it is asynchronous. A lease is verified in the minutes after the primary finishes, and nothing is written back until the router and, where needed, a paralegal have cleared it. There is no customer-facing latency budget; the operational budget is time to clear the queue.

### Failure behavior

| Failure | Behavior |
| --- | --- |
| Secondary extractor unavailable | Fields are verified by rules and tripwires only; every field the secondary would have checked is marked `UNVERIFIED_SECONDARY` and routed according to a stricter policy (configurable: triage the high-dollar fields, hold the rest) |
| Rule layer error | Fail closed: field routed to triage |
| Write-back target unavailable | Resolved values stay in the queue as `READY_TO_WRITE`; retry with backoff; nothing is dropped |
| OCR produced no text for an attachment | Intake flags the document set as incomplete before extraction is trusted |

### Regions and DR

Primary and DR follow the operator's own footprint. Lease content is commercial and tenant-confidential, so regional instances keep documents and extractions in-region.

---

## 3. Data architecture

| Store | Purpose |
| --- | --- |
| **PostgreSQL** | Lease records (mirroring the system of record's lease ID), field extractions, verification results, triage items, resolutions, audit log |
| **Object storage (S3 / Blob / GCS) with versioning and Object Lock** | Source PDFs, redlines, OCR artifacts, side letters. Immutable once ingested. |
| **Warehouse (Snowflake / Databricks), read-only** | Portfolio analytics the acquisitions team already queries; LeaseGuard publishes verified fields to it, it does not own it |
| **Redis or a queue (SQS / Pub/Sub)** | Work distribution for secondary extraction and triage assignment |

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

**Retention.** Field decisions and the audit log are retained for seven years, matching the REIT data-retention expectation named in the README. Source documents follow the operator's lease-file retention policy, which is usually longer.

---

## 4. Security architecture

### Leases are untrusted input

A lease PDF is a document from outside the building, often written by the tenant's counsel. Two consequences:

- **Prompt injection through the document.** Text inside a lease can contain instructions. Extraction prompts frame the lease as quoted data, the output is schema-constrained to the 12 fields, and anything that does not parse routes to triage. The rule layer is a second line of defense because it is plain code.
- **Redlines and hidden text.** Struck text, comments, and metadata are carried into OCR and must be tagged as such. The redline-blindness deficiency in the README is a correctness problem and an attack surface.

### Data handling

- Leases contain tenant names, financial terms, sometimes personal guarantees. Documents encrypted at rest with customer-managed keys per region; TLS 1.3 in transit, mTLS between services.
- Tenant and asset-book isolation: row-level security in Postgres, per-book prefixes in object storage, role scopes by asset book.
- Vendor calls send lease text to model vendors. The design requires a no-training, zero-retention agreement per vendor, or a self-hosted secondary for operators who will not send text out.

### Identity and RBAC

SSO through the operator's IdP. OPA enforces roles at the API.

| Role | Can |
| --- | --- |
| `lg:analyst` | Resolve triage items on assigned asset books |
| `lg:abstraction-lead` | Analyst + resolve any item, reassign, resolve disagreements between reviewers |
| `lg:asset-manager` | Read verified fields and open items for their book; approve high-dollar resolutions |
| `lg:acquisitions` | Read-only on verified fields and the open-item flag (a deal team should know a field is unresolved) |
| `lg:admin` | Config, validators, connectors, roles |

**Write-back requires a resolution.** `lg-writeback` will not write any field whose latest status is `triage` without a row in `triage_resolutions`. High-dollar fields can require a second approver.

### Threat model

| Threat | Mitigation |
| --- | --- |
| Instructions embedded in a lease | Quoted-data framing, schema-constrained output, rules in plain code |
| Reviewer clears a flag without reading | Resolution requires the source span; random second-review sampling by the abstraction lead |
| Cross-book data exposure | Row-level security, per-book object prefixes, audit of every read |
| Silent change in the primary pipeline's model | Primary model and snapshot recorded per verification; a step change in the disagreement rate is itself an alert |
| Wrong value written to the system of record | Write-back only after clearance; each write carries the `verification_id` |

---

## 4a. APIs consumed and exposed

### Consumed

| Service | Protocol / auth | Use | If it is down |
| --- | --- | --- | --- |
| Primary extraction pipeline output | Table or event feed from the operator's existing pipeline | The values being verified | Intake queues documents |
| Second-model vendor (OpenAI / Mistral-hosted) | REST, key from Vault | Re-extraction | See failure table above |
| OCR (Textract / Tesseract), vision fallback for redlines | Cloud SDK | Text from scanned or redlined PDFs | Intake marks documents incomplete |
| Yardi Voyager / MRI / Argus Enterprise | Vendor REST or file import, service principal | Write-back of verified values; Argus import for the cash-flow side | Resolved values wait as `READY_TO_WRITE` |
| CoStar / CompStak / Cherre | REST | Auxiliary benchmark feeds | Skipped; not on the critical path |
| IdP, Vault, KMS, Datadog, PagerDuty | Standard | Auth, secrets, keys, telemetry, paging | Cached or buffered |

### Exposed

| Surface | Auth | Consumers |
| --- | --- | --- |
| `POST /v1/verifications` (submit a document set) | OIDC bearer or mTLS | The operator's ingestion pipeline |
| `GET /v1/leases/{id}/fields` (verified fields plus open items) | OIDC bearer, role-checked | Asset management, acquisitions tools |
| Webhooks (outbound, HMAC-signed) | Per-consumer secret | Workflow tools, CAM reconciliation |

---

## 5. Operational architecture

| Signal | Tool |
| --- | --- |
| Logs, traces | OpenTelemetry to Datadog |
| LLM extraction traces | Langfuse |
| Queue depth, age of oldest item | Datadog metrics |

### Metrics worth owning

| Metric | Why |
| --- | --- |
| **Triage rate** (fields routed / fields verified) | Drives paralegal cost |
| **False-flag rate** (routed fields where the primary was right) | Tells you whether the rules and tripwires are too loose |
| **Resolved-wrong rate** (second review overturns a resolution) | Quality of the human step |
| **Disagreement rate between primary and secondary**, by field | A step change means one model changed |
| **Age of oldest triage item** | Stale items mean stale lease records |

### Rollout

Run in shadow on one asset book first, starting with the redlined and non-standard subset where the lift is largest. Compare LeaseGuard's flags with what the existing CAM reconciliation process later found. Expand book by book.

### Runbooks

`secondary-model-down.md` · `queue-backlog.md` · `writeback-failure.md` · `new-lease-form-onboarding.md` · `reviewer-overturn-spike.md`

---

## 6. Compliance posture

Alignment, not certification.

| Framework | How the design relates |
| --- | --- |
| **SOC 2 Type II** | All components in scope; the audit log and access reviews are the evidence |
| **Record retention** | Seven-year field-decision retention, immutable source documents |
| **Data residency / GDPR** | Regional instances where lease content is in scope |
| **SOX-adjacent controls for REIT reporting** | The resolution trail (who, what, which clause) is the control evidence for a changed lease record |

---

## 7. What is deliberately not here

- **A replacement for the deployed extraction pipeline.** Fine-tuning the primary is not the strategy; the README's three-backend comparison shows no single model wins all six deficiency classes.
- **A new system of record.** Verified values flow back into Yardi, MRI, or Argus.
- **A new OCR engine.**
- **A clause-completeness check.** The one miss in the prototype (both models return a partial kick-out) needs a check that counts distinct trigger clauses in the text. Designed, not built.
- **Autonomous write-back of flagged fields.** A human clears them.

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

The dollar weights are the prototype's modeled values, not measured losses.
