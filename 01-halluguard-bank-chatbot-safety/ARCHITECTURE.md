# Architecture — HalluGuard

The systems doc most PM writeups skip: where the code runs, what sits in the request path, what happens when a component fails, and what you would hand to a CISO and a platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (mock chatbot responses, a mock verifier score, a Streamlit app). Nothing below is claimed as deployed or load-tested. Where a figure is a design target it says so.

Cloud-agnostic where the design allows it. GCP is shown as primary; AWS and Azure equivalents are inline.

![HalluGuard flow](./assets/halluguard-flow.svg)

---

## 1. Logical architecture

HalluGuard is a containment layer. It does not replace the chatbot, the retriever, or the foundation model. It sits between the chatbot's draft answer and the customer, and decides: ship, or abstain.

| Component | Responsibility | Stack | In request path? | Stateful? |
| --- | --- | --- | --- | --- |
| `hg-gateway` | Receives `(question, retrieved_rows, draft)` from the chatbot, calls verifier + calibrator, returns the final text. Fail-closed on error. | Python 3.11, FastAPI, Pydantic v2 | Yes, sync | No |
| `hg-verifier` | Scores how well the draft is grounded in the retrieved rows. | LoRA-fine-tuned Llama 3.1 8B served with vLLM on 2x L4 GPUs | Yes, sync | No (model weights are read-only artifacts) |
| `hg-calibrator` | Maps a verifier score to ship or abstain using a per-use-case threshold (design values: 0.82 for rates and regulation questions, 0.65 for general). | Python, config read from Postgres, cached in Redis | Yes, sync | No |
| `hg-abstainer` | Replaces a blocked draft with the abstention message and the banker handoff payload. | Python | Yes, sync | No |
| `hg-probe-runner` | Nightly regression run of the probe set against the pinned vendor snapshot. Writes a pass/fail per failure mode. | Python, Airflow / Cloud Composer / MWAA | No, async | Stateful (DAG runs) |
| `hg-vendor-pin` | Pins `model_id + snapshot_date` at the gateway; daily diff job flags when a vendor snapshot changes. | Python, Cloud Functions / Lambda | No, async | No |
| `hg-console` | Line-2 review console: abstention queue, threshold history, probe trends. Embeds in the MRM workbench. | React + Next.js + Tailwind | No | No |
| `hg-telemetry` | OpenTelemetry spans from gateway, verifier, calibrator, exported off the request path. | OTel Collector to Langfuse, Datadog, ClickHouse | No, async | No |

**What is in the customer's request path, and what is not.** Only the gateway, verifier, calibrator, and abstainer. Telemetry, probes, vendor-pin diffing, and the console are all out of band. That is deliberate: a 5 ms add-on in the request path multiplies across every chat turn at peak.

**Repo structure** (production shape):

```
halluguard/
├── apps/
│   ├── gateway/        # FastAPI: verify + decide + abstain
│   ├── verifier/       # vLLM serving config + model card
│   ├── probe-runner/   # nightly DAG
│   ├── vendor-pin/     # snapshot pin + diff job
│   └── console/        # review UI
├── training/
│   ├── data/           # labeled (question, rows, answer, label) triples
│   ├── lora/           # fine-tune configs, eval harness
│   └── distill/        # DeBERTa distillation (next)
├── probes/             # 8 failure-mode probe sets, versioned (this repo ships 3 sample files)
├── infra/              # terraform, helm, OPA policies
└── docs/               # this file, runbooks, OpenAPI
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `hg-gateway` | GKE (same cluster as the chatbot) | EKS | AKS | Co-locate with the chatbot to keep the extra hop on the cluster network |
| `hg-verifier` | GKE GPU node pool, 2x L4, vLLM, autoscale on QPS | EKS GPU nodes (g6) | AKS GPU node pool (pick the closest current SKU, then re-size batch settings) | Small model, GPU-served; scale on queue depth, keep a warm minimum |
| `hg-probe-runner` | Cloud Composer | MWAA | Data Factory / Airflow on AKS | Existing skill set in most BFSI ops teams |
| `hg-vendor-pin` | Cloud Functions gen 2 | Lambda + EventBridge | Functions + Event Grid | Small scheduled job |
| `hg-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI |

### Failure behavior (the decision that matters most)

**The gateway fails closed.** If the verifier times out, errors, or is unreachable, the customer gets the abstention message, not the unverified draft. This trades availability of direct answers for safety, which is the right default for rate, fee, and regulation questions. It is configurable per use case, and any fail-open setting needs a named owner and a line-2 sign-off.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Verifier timeout or 5xx | Abstain, hand to banker | P2 if error rate above threshold for 5 min |
| Calibrator config unreadable | Use last cached thresholds; if none, abstain | P2 |
| Vendor snapshot changed vs pin | Keep serving on the pinned snapshot, open a drift event, run the probe set immediately | P3, P2 if probes regress |
| Probe-runner DAG fails | Serving unaffected; yesterday's result stays the baseline | P3 |
| Telemetry sink down | Buffer locally, drop with a counter after the buffer fills | P4 |

### Latency

The verifier forward pass is the only new cost in the customer's wait. The budget has to be set against the chatbot's turn SLA, and the number has not been measured in this repo. Two levers if it is too slow: batch scoring on the GPU, and distill the verifier to a DeBERTa-class model (listed under "what's next" in the README).

### Regions and DR

- Primary and DR regions follow the chatbot's own footprint. HalluGuard does not get a different recovery objective than the system it protects.
- Region-specific instances where data residency applies (EU, India). Each has its own database and key ring; no cross-region replication of customer text.

---

## 3. Data architecture

| Store | Purpose | Notes |
| --- | --- | --- |
| **PostgreSQL 15 + pgvector** | Thresholds, verification decisions, abstentions, probe results, vendor snapshots, audit log. pgvector also backs the chatbot's retrieval index in the reference design. | Relational integrity for the audit trail |
| **ClickHouse** | Per-decision verifier scores and drift time series | High-volume, append-only, queried by date range |
| **Redis** | Threshold cache, idempotency keys, rate limits | TTL eviction |
| **Object storage with Object Lock (WORM)** | Archived decision records and probe-run artifacts | Retention set by the bank's record-keeping policy |

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
    failure_mode    TEXT NOT NULL,          -- one of the eight classes
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
```

**Raw customer text.** The design stores a hash of `(question, rows, draft)` and the decision, not the conversation. Where Compliance needs the text to adjudicate a complaint, it is fetched from the chatbot's own conversation store by `trace_id`, under that system's retention and access rules. HalluGuard does not become a second copy of customer conversations.

---

## 4. Security architecture

### Data handling

- **PII.** Customer identifiers are hashed before any HalluGuard write. The training and labeling pipeline scrubs PII first (Microsoft Presidio, as noted in the README acknowledgements).
- **Encryption.** AES-256 at rest with customer-managed keys per region; TLS 1.3 north-south, mTLS east-west through the service mesh.
- **Secrets.** Vault or the cloud secret manager; vendor API keys fetched at boot through workload identity, rotated on the bank's schedule. No static service-account keys.

### Identity and RBAC

Authentication is delegated to the bank's IdP (SAML / OIDC, MFA enforced there). Authorization is enforced at the gateway with OPA.

| Role | Can | Maps to |
| --- | --- | --- |
| `hg:viewer` | Read decisions, probe trends | Audit, executives |
| `hg:chatbot-owner` | Viewer + propose threshold changes | Line-1 chatbot product owner |
| `hg:validator` | Viewer + approve threshold changes + review abstention samples | Line-2 model risk |
| `hg:admin` | Config, integrations, role management | Platform engineering |

A threshold change needs a proposer and a different approver. Both are recorded in `thresholds`.

### Threat model

| Threat | Mitigation |
| --- | --- |
| Customer text steers the verifier (prompt injection in the question) | Verifier input is framed as data to score, never as instructions; the verifier emits a score, not free text, so there is nothing to hijack into an answer. Layered with [PromptShield](../06-promptshield-prompt-injection-defense/) at the chatbot edge. |
| Poisoned or stale retrieval rows make a wrong draft look "grounded" | HalluGuard checks the draft against the rows, so it cannot detect a wrong row. Mitigation sits upstream: rate and fee tables are loaded from the system of record with an effective-date check; the time-staleness probe set runs nightly. |
| Threshold quietly lowered to cut abstentions | Append-only `thresholds` with proposer and approver; weekly report of abstention rate beside incident rate |
| Silent vendor model update | Snapshot pinned at the gateway; daily diff; nightly probe run |
| Verifier model drift or tampering | Model artifact signed and checksum-verified at load; the verifier's own held-out set is re-scored on every release |
| Over-abstention erodes the chatbot's value | Abstention rate is a first-class SLO with an owner; see operations |

---

## 4a. APIs consumed and exposed

### Consumed

| Service | Protocol / auth | Use | If it is down |
| --- | --- | --- | --- |
| Foundation-model vendors (Anthropic, Azure OpenAI, Bedrock) | REST, key from Vault or managed identity | Used by the **chatbot** and by the probe runner, not by the verifier | Chatbot's own fallback; probe run skipped and alerted |
| Bank IdP (Okta / Entra / Ping) | SAML 2.0 + OIDC | Console login, role lookup | Existing sessions continue |
| MRM workbench (Archer / ServiceNow GRC / MetricStream) | Vendor REST, service principal | File an abstention disposition and threshold-change records | Local audit trail continues, sync resumes later |
| Datadog / Langfuse | HTTPS, key from Vault | Metrics and LLM traces | Local buffer |
| PagerDuty / Slack | REST / webhook | Alert routing | Email fallback |

### Exposed

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/verify` | OpenAPI 3.1 over HTTPS, mTLS service identity | The chatbot service |
| Console API | OIDC bearer, role-checked by OPA | `hg-console`, MRM workbench iframe |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Incident management, Compliance dashboard |

**API opinions.** REST and OpenAPI, not GraphQL. Idempotency key on `verify` so a retried call does not double-count. No customer identifiers in URLs. Versioned in the path.

---

## 5. Operational architecture

| Signal | Tool |
| --- | --- |
| Application logs and traces | OpenTelemetry to Datadog (the SOC's existing pane) |
| LLM-specific traces (verifier inputs/outputs, scores) | Langfuse, self-hosted |
| Score and drift time series | ClickHouse |
| Audit log | Postgres, archived to Object Lock storage |

### SLOs worth owning

| SLO | Why it is the PM's number |
| --- | --- |
| **Abstention rate** by use case | The cost side of containment. Too high and the bot stops being useful. |
| **Wrong answers served** (from Compliance incidents and sampled review) | The benefit side. Read it beside abstention rate; either alone misleads. |
| **Verifier error / timeout rate** | Drives fail-closed abstentions |
| **Nightly probe pass rate** per failure mode | The early warning for vendor changes |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P1 | Probe regression on rates/regulation plus a live spike in wrong-answer reports | PagerDuty |
| P2 | Verifier error rate above threshold; probe regression on any mode | PagerDuty (low urgency) + Slack |
| P3 | Vendor snapshot change; abstention rate drift | Slack |
| P4 | Daily digest | Email |

### Rollout

Shadow first (score and log, serve the draft unchanged) so the abstention rate and false-abstention rate are known before anyone is affected. Then canary 1% to 10% to 50% to 100% with automatic rollback on probe regression, as outlined in the README.

### Runbooks (one page each, in `docs/runbooks/`)

`vendor-snapshot-changed.md` · `verifier-degraded.md` · `threshold-change.md` · `abstention-rate-spike.md` · `complaint-evidence-pull.md`

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against.

| Framework | How the design relates |
| --- | --- |
| **SR 11-7 / model risk management** | HalluGuard is a model in its own right (the verifier) and a control over another model (the chatbot). Both need inventory entries, validation, and ongoing monitoring; the probe runner is the monitoring. |
| **Reg DD / Truth in Savings** | The citation-fabrication and rate probes exist because a wrong APY or invented regulation in a chatbot answer is a disclosure problem, not just a quality problem. |
| **UDAAP** | An abstention is an honest non-answer; a confident wrong fee is the exposure. |
| **OWASP LLM Top 10, LLM09 (Misinformation)** | The canonical framing for the eight failure modes. |
| **NIST AI RMF** | Measure and Manage functions map to probes and thresholds. |
| **SOC 2 Type II, GDPR, India data localization** | Regional instances, hashed identifiers, append-only audit. |

---

## 7. What is deliberately not here

- **A new chatbot or a new retriever.** HalluGuard wraps what exists; InfoSec does not re-audit the bot.
- **Model retraining of the foundation model.** The README's three-model comparison is the argument: swapping models moves each failure mode by a few points and leaves confident-and-wrong near the floor.
- **A claim that it detects wrong source data.** It checks the draft against the rows it was given. Bad rows are a data-quality problem upstream.
- **Auto-lowering of thresholds.** Thresholds change by a human proposal and a different human's approval.

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

The score and threshold in the example are illustrative, taken from the README's worked sequence.
