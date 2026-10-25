# Architecture — PolicyNeedle

The systems doc most PM writeups skip. Where the sweep runs, what is stored, who can change a gold answer, what leaves the building, and what the operations team does when the gate fails. What you'd hand to your CISO and your platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (synthetic manuals, four stub readers that are not models, a scoring harness, a gate and a Streamlit app). Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

This doc is cloud-agnostic. PolicyNeedle runs on whatever container platform, queue, scheduler and database the bank already operates; the choices below are defaults, and each has an equivalent.

![PolicyNeedle flow](./assets/policyneedle-flow.svg)

---

## 1. Logical architecture

PolicyNeedle is a pre-release test layer. It does not sit in the customer's request path and it does not replace the assistant, the retriever or the foundation model. It runs a probe set against a release candidate and returns one decision: pass the release, or block it with a list of the slices that failed.

Ten components. None is in a customer's request path.

| Component | Responsibility | Language / framework | In request path? | Stateful? |
| --- | --- | --- | --- | --- |
| `pn-corpus` | Ingests policy manuals from the bank's document store as plain text with block boundaries; assigns a content hash per manual version. | Python 3.11 | No | Yes (object store plus Postgres) |
| `pn-planter` | Builds probes: plants synthetic needles at controlled depth in a copy of a manual, and pairs real clauses with questions the policy owner has signed. Six forms: plain, superseded, exception, table, two-section, distractor. | Python, standard library for the generator | No | No |
| `pn-registry` | Stores versioned, content-addressed probe sets with gold answers, the manual version each cites and the sign-off record. | Postgres | No | Yes |
| `pn-adapter` | One adapter per assistant under test. Implements `reader(document_text, question) -> answer_text` and nothing else. | Python | No | No |
| `pn-runner` | Sends each (manual, question) to the adapter; records manual version, reader version and raw answer for every call. Fans out across workers. | Python workers on a queue | No | No (queue state only) |
| `pn-scorer` | Normalized exact match. Design: a tolerant scorer for paraphrase, verbosity and unit conversion, with every tolerant pass logged and sampled by a human. | Python | No | No |
| `pn-matrix` | Builds the form × length × depth matrix, flags cells, localizes faults and names the kind of wrong answer. | Python | No | No |
| `pn-gate` | Applies thresholds, returns PASS, REVIEW or FAIL, handles overrides, and hands the verdict to the release pipeline and to the EvalForge gate. | Python, FastAPI | No (pre-release only) | No (reads Postgres) |
| `pn-console` | Results UI for the policy owner and the model risk reviewer: slice list, manual viewer with the planted clause highlighted. | React | No | No |
| `pn-telemetry` | OpenTelemetry spans from runner, scorer and gate, exported off the critical path. | OTel Collector to Langfuse, Datadog, ClickHouse | No | No |

**Prototype mapping.** `data/_generate.py` is the planter; `src/harness.py` holds the reader interface, the four stub readers, the scorer, the matrix helpers and the gate; the step scripts are the runner and the reports; `src/app.py` stands in for the console. The registry, the corpus ingest, telemetry, the tolerant scorer and the REVIEW state are design only.

**Repo structure** (production shape; one repo, or a monorepo package):

```
policyneedle/
├── apps/
│   ├── planter/       # needle planting and probe authoring
│   ├── runner/        # queue workers, adapter loader
│   ├── scorer/        # exact match, tolerant scorer
│   ├── gate/          # thresholds, verdicts, overrides
│   └── console/       # results UI
├── adapters/          # one folder per assistant under test
├── probes/            # versioned probe sets (this repo ships the synthetic set)
├── infra/
│   ├── kubernetes/    # manifests
│   └── policies/      # network policy, IAM templates
├── docs/
│   ├── ARCHITECTURE.md
│   └── runbooks/
└── tests/
    ├── unit/
    ├── integration/
    └── stub_control/  # the four stub readers, re-run on every harness release
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | Placement | Why |
| --- | --- | --- |
| `pn-gate` | Service on the bank's container platform, same cluster as the release pipeline | The gate is called from the pipeline; keep the hop short |
| `pn-runner` | Queue workers, autoscaled on queue depth | A sweep is many independent reader calls |
| `pn-planter`, `pn-scorer`, `pn-matrix` | Jobs invoked by the runner | Stateless and batch |
| `pn-registry`, `pn-corpus` | Managed Postgres and object storage with write-once retention | Relational integrity for the audit trail |
| `pn-console` | Stateless web service behind the bank's single sign-on | Read-mostly UI |
| `pn-telemetry` | OTel Collector sidecar | Spans leave the critical path |

**Failure behavior (the decision that matters most).** The gate fails closed. If the sweep is incomplete, the reader endpoint is unreachable, or the scorer errors, the verdict is REVIEW, never PASS. The release is held until a person looks. That trades release speed for a record that every PASS came from a full sweep.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Reader endpoint down or timing out | Sweep marked incomplete; verdict REVIEW | P2 if the release is blocked for more than one working day |
| Scorer error on a probe | That probe counts as a fail and is listed; verdict cannot be PASS | P3 |
| Manual changed since the probes were signed | Probes citing changed clauses are held out and reported, not scored | P3 |
| Registry unreachable | Gate returns REVIEW with the last known probe-set version | P2 |
| Telemetry sink down | Buffer locally, drop with a counter once full | P4 |

**Latency and cost.** There is no customer-facing latency budget. The cost driver is reader calls: 🟢 in the prototype, each probe sends its whole manual, so one sweep of one reader is 270 calls and 64,894,140 characters of manual text (`step_04_with_policyneedle.py`). 🟡 About 16 million tokens at 4 characters per token. Two design levers, not measured: ask all questions for one manual in one cached session, and run a sampled grid on every commit with the full grid on release candidates only.

### Network topology

```
Release pipeline (existing)
   │   candidate build id
   ▼
[pn-gate]  ← only caller allowed: the release pipeline service identity
   │
   ├──► [Postgres: probe sets, runs, results, decisions]   (private endpoint)
   ├──► [pn-runner queue] ──► [pn-adapter] ──► assistant under test (in-boundary endpoint)
   │                              egress only to approved endpoints via an allow-listed proxy
   └──► async: [OTel Collector] ──► Langfuse / Datadog / ClickHouse

Out of band:
   [pn-corpus] ◄── bank document store (read-only service account)
   [pn-console] ── single sign-on ── policy owner, model risk reviewer
```

### Region & DR

- Follows the assistant's own footprint. PolicyNeedle does not get a different recovery objective than the release pipeline it gates.
- Where data residency applies, one instance per region with its own database and key ring. Manuals and results are not replicated across regions.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL** | Manual versions, probe sets, probes, runs, results, slice results, gate decisions, overrides, audit log | Relational integrity; the bank's operations team already runs it |
| **ClickHouse** | Per-slice pass rates over time, per reader version | High-volume, append-only, queried by date range |
| **Object storage with write-once retention** | Manual text snapshots and sweep evidence bundles | Evidence that cannot be edited after the fact |
| **Queue** | Runner work items | Fan-out of reader calls |

### PostgreSQL schema (the consequential tables)

```sql
-- One row per version of a policy manual (the text itself lives in object storage)
CREATE TABLE manual_versions (
    manual_version_id  TEXT PRIMARY KEY,            -- content hash
    manual_name        TEXT NOT NULL,
    effective_from     DATE NOT NULL,
    n_chars            BIGINT NOT NULL,
    storage_uri        TEXT NOT NULL,
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE probe_sets (
    probe_set_id       TEXT PRIMARY KEY,            -- content hash of all probes
    parent_id          TEXT REFERENCES probe_sets(probe_set_id),
    created_by         TEXT NOT NULL,
    approved_by        TEXT NOT NULL,               -- policy owner
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE probes (
    probe_id           TEXT NOT NULL,
    probe_set_id       TEXT NOT NULL REFERENCES probe_sets(probe_set_id),
    manual_version_id  TEXT NOT NULL REFERENCES manual_versions(manual_version_id),
    form               TEXT NOT NULL,               -- plain / superseded / exception / table / two_section / distractor
    depth_pct          SMALLINT NOT NULL,
    question           TEXT NOT NULL,
    expected_answer    TEXT NOT NULL,
    trap_label         TEXT NOT NULL,
    evidence_spans     TEXT NOT NULL,
    signed_by          TEXT,                        -- null for synthetic needles
    PRIMARY KEY (probe_set_id, probe_id)
);

CREATE TABLE sweep_runs (
    run_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    probe_set_id       TEXT NOT NULL REFERENCES probe_sets(probe_set_id),
    reader_id          TEXT NOT NULL,               -- the assistant under test
    reader_version     TEXT NOT NULL,
    scorer_version     TEXT NOT NULL,
    status             TEXT NOT NULL                -- COMPLETE / INCOMPLETE
);

CREATE TABLE probe_results (
    run_id             UUID NOT NULL REFERENCES sweep_runs(run_id),
    probe_id           TEXT NOT NULL,
    answer_text        TEXT NOT NULL,
    passed             BOOLEAN NOT NULL,
    scored_by          TEXT NOT NULL,               -- exact / tolerant
    kind_of_wrong      TEXT NOT NULL,               -- ok / no_answer / stale_version / ...
    PRIMARY KEY (run_id, probe_id)
);

CREATE TABLE gate_decisions (
    decision_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id             UUID NOT NULL REFERENCES sweep_runs(run_id),
    decided_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verdict            TEXT NOT NULL,               -- PASS / REVIEW / FAIL
    overall_pass_rate  NUMERIC(5,4) NOT NULL,
    broken_rules       JSONB NOT NULL,
    override_by        TEXT,                        -- named approver, if overridden
    override_reason    TEXT
);

-- Audit log (immutable, append-only, partitioned by month)
CREATE TABLE audit_log (
    audit_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id           TEXT NOT NULL,
    actor_type         TEXT NOT NULL,               -- user / service_account
    action             TEXT NOT NULL,
    resource_type      TEXT NOT NULL,
    resource_id        TEXT NOT NULL,
    payload            JSONB,
    result             TEXT NOT NULL
) PARTITION BY RANGE (occurred_at);
```

**Gold answers.** An expected answer is bound to a manual version and a signer. A new manual version does not silently inherit it: probes that cite a changed clause are held out until re-signed.

### ClickHouse schema (the time-series tables)

```sql
CREATE TABLE slice_pass_rates (
    run_started_at  DateTime64(3, 'UTC'),
    reader_id       LowCardinality(String),
    reader_version  LowCardinality(String),
    form            LowCardinality(String),
    length_pages    UInt16,
    depth_pct       UInt8,
    n_probes        UInt16,
    n_passed        UInt16
) ENGINE = MergeTree
PARTITION BY toYYYYMM(run_started_at)
ORDER BY (reader_id, form, length_pages, depth_pct, run_started_at)
TTL toDateTime(run_started_at) + INTERVAL 730 DAY DELETE;
```

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-retention schedule before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Manual text snapshots (real manuals) | Life of the manual version plus 7 years | Object storage, write-once | Internal; as classified by the policy owner |
| Probe sets, gold answers, sign-offs | Life of the assistant plus 7 years | Postgres, append-only | Internal |
| Sweep runs, results, gate decisions | 7 years | Postgres, archive to write-once storage | Internal |
| Slice pass-rate time series | 2 years hot | ClickHouse | Internal |
| Reader answers (may echo manual text) | Same as the run | Postgres | Same class as the manual |
| Audit log | 7 years | Postgres partitioned, archive to write-once storage | Confidential |
| Synthetic manuals and probes | Not sensitive | This repo | Public |

---

## 4. Security architecture

### Encryption

- **At rest.** Customer-managed keys for the database and object storage, one key ring per region.
- **In transit.** TLS 1.3 north-south. Mutual TLS between services.
- **Field-level.** Reader answers can echo manual text, so results carry the manual's classification. No customer data is needed or stored: probes ask about policy, not about customers.

### Secrets management

- **Primary store.** The bank's secret manager. No long-lived static credentials.
- **Reader credentials** (for the assistant under test): fetched at runtime through workload identity, scoped to the test endpoint, rotated on the bank's schedule.
- **Gold-answer signing.** Sign-off is a person acting through single sign-on, recorded in `probe_sets.approved_by` and `probes.signed_by`.

### Identity provider & user management

- **IdP.** Whatever the bank already runs. SAML 2.0 and OIDC. PolicyNeedle does not run its own.
- **MFA.** Enforced at the IdP.
- **Service identity.** Each component has its own workload identity; mutual TLS enforces it at every hop.

### RBAC matrix

Authorization is enforced at the gate and the registry, and every decision is written to `audit_log`.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `pn:viewer` | Read matrices, flagged cells, decisions | Audit, executives |
| `pn:product-owner` | Viewer + start sweeps on their assistant + request an override | Assistant product owner |
| `pn:policy-owner` | Viewer + author probes + sign gold answers | Policy owner |
| `pn:validator` | Viewer + approve or reject an override + review tolerant-scorer samples | Model risk reviewer |
| `pn:admin` | Config, adapters, thresholds, role management | AI platform lead |

An override needs a requester and a different approver. A change to a gate threshold needs a proposer and a different approver. Both are recorded.

### Network controls

- **Perimeter.** No public ingress. The gate's only caller is the release pipeline's service identity; the console sits behind single sign-on.
- **Egress.** Real manuals go only to in-boundary reader endpoints. Any hosted endpoint is on an allow-list and is approved by information security per manual classification.
- **Lateral.** Network policies between components; the adapter can reach only its configured endpoint.

### Threat model

| Threat | Mitigation |
| --- | --- |
| Manual text leaves the bank inside a test run | Egress allow-list; hosted endpoints approved per manual classification; synthetic manuals for anything outside the boundary |
| Probe set leaks into training data and inflates pass rates | Probe sets stay internal; a held-out rotating subset is never shown to the assistant team; probe-set versions are logged per decision |
| Synthetic needles reach a production manual | Needles are planted in copies stored under `pn-corpus`, never written back to the document store; a check rejects any manual version that contains a needle marker |
| A gold answer is wrong or tampered with | Signer and manual version recorded; append-only registry; changes need a second approver |
| Instructions hidden in a manual steer the reader | The runner passes the manual as data to the adapter; scorer treats the answer as a string and never evaluates it |
| Stale gold answer after a policy change | A new manual version or amendment holds out the probes that cite it until re-signed |
| Gate bypass by the team under delivery pressure | Override needs a named approver and a reason; monthly review of overrides |
| Exact-match scoring flags a correct but wordy answer | Tolerant scorer with every tolerant pass logged and sampled; the gate cannot block on a tolerant-scorer outage |

---

## 4a. APIs consumed and exposed

PolicyNeedle is a glue layer. Every external dependency is listed with its protocol, auth model and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Bank document store | Read-only service account | Fetch manual text and version metadata | Last ingested version stays in force; new versions wait |
| Assistant under test (per adapter) | HTTPS, key from the secret manager or workload identity | Send (manual, question); receive answer text | Sweep incomplete; verdict REVIEW |
| Bank IdP | SAML 2.0 and OIDC | Console login, role lookup | Existing sessions continue |
| Model risk workflow | Vendor REST, service principal | File an evidence bundle and override records | Local record continues; sync resumes later |
| Langfuse / Datadog | HTTPS | Reader-call traces and metrics | Local buffer |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/sweeps` | OpenAPI 3.1 over HTTPS, mutual TLS service identity | Release pipeline |
| `GET /v1/sweeps/{id}/gate` | Same | Release pipeline, EvalForge gate |
| Console API | OIDC bearer, role-checked | `pn-console` |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Model risk workflow |

### API-design opinions (the choices a reviewer will ask about)

- **The reader interface stays one function.** `reader(document_text, question) -> answer_text`. Adapters carry the assistant's quirks; the harness never learns them.
- **The verdict carries the reason.** The gate response lists the broken rules and the flagged cells, so a reviewer can reconstruct why a release was blocked.
- **Verdicts name versions.** Probe-set version, manual versions, reader version and scorer version are in every response.
- **Idempotency key on `POST /v1/sweeps`.** A retried call must not start a second sweep.
- **No customer identifiers anywhere.** Probes ask about policy.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry to Datadog | The operations team's existing pane |
| Reader-call traces (question, answer, latency) | Langfuse, self-hosted | Needed to debug one failed probe |
| Slice pass-rate time series | ClickHouse | A drift in one slice across releases |
| Audit log | Postgres, archived to write-once storage | Record-keeping |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **Share of releases with a COMPLETE sweep before launch** | A PASS from a partial sweep is worth nothing |
| **Gate decision latency after the sweep ends** | The gate must not be what delays a release |
| **Gate overrides per quarter** | The cost side of blocking; read it beside post-launch long-document faults |
| **Tolerant-scorer disagreement with the human sample** | Whether the scorer can be trusted to block |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P1 | A release shipped without a COMPLETE sweep | Paging |
| P2 | Reader endpoint down for the whole sweep window; registry unreachable | Paging, low urgency |
| P3 | Held-out probes after a manual change; scorer error | Chat |
| P4 | Daily digest of slice pass-rate drift | Email |

### Rollout

Shadow first: run the sweep on every release candidate, publish the matrix, block nothing. Then block on the superseded and exception forms, which are the customer-visible wrong answers. Then block on every threshold. As outlined in [`PRD.md`](./PRD.md); durations are design targets.

### Backup & DR

- **Postgres.** Continuous log archiving to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **ClickHouse.** Weekly backup to object storage.
- **Object storage.** Versioning and write-once retention for manual snapshots and evidence bundles.
- **Adapters.** Versioned with the repo; the previous adapter stays deployable.
- **DR drill cadence.** Quarterly failover, validated against the release pipeline's own recovery objective.

### Runbooks (one page each, in `docs/runbooks/`)

- `gate-returned-fail.md` — read the slice list, find the kind of wrong answer, route to the owner
- `sweep-incomplete.md` — the reader endpoint failed mid-sweep
- `manual-version-changed.md` — held-out probes after an amendment; re-sign
- `override-request.md` — request, approve, record, retest date
- `tolerant-scorer-disagreement.md` — switch back to exact match and review the sample

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against.

| Framework | How the design relates |
| --- | --- |
| **SR 11-7 / model risk management** | By analogy, an assistant that answers from policy is treated as a model in use, and its ongoing monitoring would need to show what was tested and what failed. The sweep, the matrix and the evidence bundle are the record the design would keep. This is not a claim that SR 11-7 or its replacement governs the assistant. PolicyNeedle is also a tool the validator relies on, so the stub control set is re-run on every harness release. |
| **NIST AI RMF** | The Measure function maps to the probe set, the scorer and the gate. |
| **OWASP LLM Top 10, LLM09 (Misinformation)** | The framing for a confident answer taken from the wrong clause. |
| **Bank record-retention schedule** | Retention periods above are defaults to be confirmed against it. |

---

## 7. What's deliberately not here

- **A new assistant, retriever or foundation model.** PolicyNeedle tests what exists.
- **Runtime answer checking.** Grounding a live answer is [HalluGuard](../01-halluguard-bank-chatbot-safety/)'s job; PolicyNeedle runs before launch.
- **A second probe registry and CI gate for the whole GenAI fleet.** The general registry and gate are [EvalForge](../04-evalforge-llm-eval-platform/)'s; PolicyNeedle supplies a probe set and hands its verdict over.
- **Contract and lease extraction.** That is [LeaseGuard](../03-leaseguard-cre-lease-verification/); the superseded and exception forms borrow its shapes.
- **A claim that the sweep finds faults nobody planted.** It finds faults in the forms the probe set contains.
- **Auto-lowering of thresholds.** A threshold changes by one person's proposal and another's approval.
- **A standalone authentication system.** It uses the bank's IdP.

Each item is something a team would be tempted to absorb, and each is already owned by another system.

---

## Appendix — sample API contract

```python
# POST /v1/sweeps
# Auth: mutual TLS service identity (release pipeline)
# Header: Idempotency-Key: <uuid>
{
    "reader_id": "policy-assistant",
    "reader_version": "2026.10.2",
    "probe_set_id": "ps-synthetic-v1",
    "scope": "full_grid"
}
# Response 202
{
    "run_id": "c1a7f0de-...",
    "status": "INCOMPLETE",
    "probes_queued": 270
}

# GET /v1/sweeps/c1a7f0de-.../gate   (after the sweep completes; illustrative values)
{
    "run_id": "c1a7f0de-...",
    "verdict": "FAIL",
    "overall_pass_rate": 0.222,
    "broken_rules": [
        "overall pass rate 22.2% is below 98%",
        "15 of 18 form-by-length slices are below 90%",
        "5 of 5 depth bands are below 90%"
    ],
    "flagged_cells": 75,
    "kinds_of_wrong_answer": {"stale_version": 45, "single_clause": 45, "sibling_answer": 45, "wrong_column": 45, "exception_missed": 30},
    "probe_set_id": "ps-synthetic-v1",
    "reader_version": "2026.10.2"
}
```

The values in the second response are the `step_04_with_policyneedle.py` output for the keyword-window stub, used as an illustration. The reader id and version are invented.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/14-policyneedle-long-context-fidelity/demo.html).
