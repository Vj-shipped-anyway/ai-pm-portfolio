# Architecture — FairLens

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO and your model-risk platform lead on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (a stub points scorecard, six tests, a seeded bootstrap and verdict rules, over synthetic data, with a Streamlit app). Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so and carries 🔴.

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. Every BFSI shop is on AWS, GCP or Azure (or two of three). GCP is shown as primary; AWS and Azure equivalents are called out inline.

![FairLens flow](./assets/fairlens-flow.svg)

---

## 1. Logical architecture

FairLens is a reviewer-side control. It does not replace the model, the validators' own testing or counsel's read. It sits next to a credit-decision model's scoring log and decides one thing per run: for each of six tests, PASS, REVIEW or FAIL, with the numbers.

Ten components. Six are in the release check path; four are not.

| Component | Responsibility | Language / framework | In release path? | Stateful? |
| --- | --- | --- | --- | --- |
| `fl-reader` | Reads scored decisions, outcomes and scores from the model's scoring log on a schedule and on release events. Writes each read as an immutable snapshot keyed by content hash. | Python 3.11 on Cloud Functions / Lambda / Functions | Yes, async trigger | No |
| `fl-groups` | Supplies a group label for each decision: a label the bank lawfully holds, or the output of a separate inference step with its own validation. **The prototype has neither; it reads the label from the file.** | Python; adapter interface | Yes | No |
| `fl-store` | Holds snapshots (metadata), runs, test results, verdicts, exceptions and the audit trail. | PostgreSQL 15 | Yes | Stateful |
| `fl-air` | Approval rate and AIR by group, with a seeded percentile bootstrap. The prototype's `group_stats` and `bootstrap_air`. | Python workers | Yes, sync | No |
| `fl-sweep` | Re-runs approval and AIR across a range of cutoffs; reports where the lowest AIR crosses the screen and what passing costs. The prototype's `sweep` and `crossing`. | Python workers | Yes, sync | No |
| `fl-ablate` | Neutralizes one named input and re-runs the tests; counts the decisions that turn. The prototype's `ablate_postcode`. | Python workers | No, async, but the verdict waits on it | No |
| `fl-reasons` | Matched-pair reason-code consistency against a within-group control, and the naming check for declines a proxy alone causes. | Python workers | No, async, but the verdict waits on it | No |
| `fl-verdict` | Applies the verdict rules (configuration) to the test results. Exposes the check the release pipeline calls and records exceptions. | Python, FastAPI, Pydantic v2 | Yes, sync | No |
| `fl-console` | Review console: runs, verdicts, evidence, sensitivity to label error, exceptions. | React + Next.js + Tailwind | No | No |
| `fl-telemetry` | OpenTelemetry spans and metrics from every component, exported off the release path. | OTel Collector to the platform's monitoring | No, async | No |

**What is in the release path, and what is not.** The reader, group adapter, store, AIR/sweep workers and verdict decide whether a release or a cutoff change proceeds. Everything else supports them or reports on them. FairLens never sits between a customer and a decision: it reads decisions after they are made, and it never changes a score or a cutoff.

**Repo structure** (production shape; monorepo):

```
fairlens/
├── apps/
│   ├── reader/         # scoring-log reader, snapshot writer
│   ├── groups/         # group-label adapter (labels held, or inference step)
│   ├── runner/         # air, sweep, ablate, reasons workers
│   ├── verdict/        # FastAPI: run endpoint, status, exceptions
│   └── console/        # review UI
├── libs/
│   ├── tests/          # the six tests as pure functions
│   ├── bootstrap/      # seeded resampling
│   └── rules/          # verdict rules as versioned configuration
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
    └── calibration/    # label-error sensitivity, known planted cases
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `fl-reader` | Cloud Functions gen 2 + Cloud Scheduler | Lambda + EventBridge | Functions + Event Grid | Small scheduled job plus an event handler |
| `fl-groups` | Cloud Run | ECS Fargate | Container Apps | Stateless adapter; isolated so label access can be restricted separately |
| `fl-air`, `fl-sweep`, `fl-ablate`, `fl-reasons` | GKE worker pool, autoscale on queue depth | EKS worker pool | AKS worker pool | CPU-bound over many decisions and resamples; scale on queue age |
| `fl-verdict` | Cloud Run (min instances 1) | ECS Fargate | Container Apps | Stateless API; a warm instance keeps the check fast |
| `fl-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI |
| `fl-store` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The verdict check has two modes and the mode is per model tier. In advisory mode a runner outage fails open: the release proceeds, the bypass is logged and counted. In blocking mode, used for tier-1 credit models, an outage fails closed: the release or cutoff change waits. Any fail-open setting on a blocking model needs a named owner and a line-2 sign-off. A missing or stale group label, or a group below the minimum size, produces REVIEW and never PASS.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Scoring-log read fails | The run is recorded as incomplete; the check says REVIEW with "no data"; advisory proceeds, blocking holds | P2 |
| Group labels missing or stale | REVIEW with "labels unavailable"; never PASS | P2 |
| A group below the minimum size | REVIEW by rule for that group; the run continues | P4 |
| Runner queue aging | Check says REVIEW with "run pending"; mode decides | P2 |
| Model is not a points scorecard | Reason-code test reports "not applicable", not PASS | P4 |
| Store unavailable | Check fails per its mode; the reader buffers snapshots locally | P2 |
| Telemetry sink down | Buffer locally, drop with a counter once full | P4 |

**Latency.** The only new wait is the verdict inside the release pipeline. 🔴 Design target: a run inside one pipeline step. It has not been measured in this repo. The levers if it is slow: cache the bootstrap for an unchanged snapshot, cap the number of resamples, and run the sweep on a coarser grid first.

### Network topology

```
Model release pipeline / cutoff change request
   │   release event (signed webhook) or schedule
   ▼
[fl-reader]  ── read-only token ──►  [Model scoring log + outcome store]
   │
   ▼
[PostgreSQL: snapshots, runs]  ──►  [fl-groups]  ◄── label source / inference step (restricted)
                                         │
                                         ▼
                        [fl-air] [fl-sweep] [fl-ablate] [fl-reasons]   (worker pool)
                                         │
                                         ▼
                                    [fl-verdict] ◄── release pipeline check (mTLS)
                                         │
                      ┌──────────────────┼───────────────────┐
                      ▼                  ▼                   ▼
               release hold      evidence bundle     OTel Collector ──► monitoring

Out of band:
   [fl-console] behind the bank's SSO  ──►  [fl-verdict API] (role-checked by OPA)
   Interlocks: ControlMap (16), EvalForge (04), DriftSentinel (02), TierGate (11) over service-to-service calls
```

### Region & DR

- Primary and DR regions follow the model platform's own footprint. FairLens does not get a different recovery objective than the system whose releases it checks.
- Region-specific instances where data residency applies. Each has its own database and key ring; decision-level data and group labels do not replicate across regions.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | Model versions, snapshot metadata, runs, test results, verdicts, exceptions, audit log | Relational integrity for the audit trail; the platform team already runs it |
| **ClickHouse** (or the platform's columnar store) | Per-decision test inputs and results, tokenized | High volume, append-only, queried by model version and date range |
| **Object storage with Object Lock (WORM)** | Evidence bundles and archived verdicts | Write-once-read-many for the record-keeping policy |
| **Redis** (optional) | Verdict cache for the release check, idempotency keys | TTL eviction handles cleanup |

### PostgreSQL schema (the consequential tables)

```sql
-- One row per model version under test, with the cutoff in force
CREATE TABLE model_versions (
    model_version_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name        TEXT NOT NULL,
    version           TEXT NOT NULL,
    tier              TEXT NOT NULL,                -- from TierGate
    cutoff_points     INT  NOT NULL,                -- the policy cutoff in force
    registered_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (model_name, version)
);

-- Where each run's group labels came from, and how much error was measured
CREATE TABLE group_label_sources (
    source_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind              TEXT NOT NULL,                -- held / inferred
    description       TEXT NOT NULL,
    measured_error    NUMERIC,                      -- share of labels wrong, when measured
    approved_by       TEXT NOT NULL,                -- counsel sign-off
    approved_at       TIMESTAMPTZ NOT NULL
);

-- One row per run of the pack; append-only; partitioned by month
CREATE TABLE test_runs (
    run_id            UUID NOT NULL DEFAULT gen_random_uuid(),
    run_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_version_id  UUID NOT NULL REFERENCES model_versions,
    cutoff_points     INT  NOT NULL,                -- the cutoff under test
    snapshot_sha256   TEXT NOT NULL,                -- hash of the decision snapshot
    label_source_id   UUID NOT NULL REFERENCES group_label_sources,
    bootstrap_seed    BIGINT NOT NULL,              -- stored so the run reproduces
    bootstrap_n       INT  NOT NULL,
    rules_version     TEXT NOT NULL,                -- the verdict rules in force
    mode              TEXT NOT NULL,                -- advisory / blocking
    PRIMARY KEY (run_id, run_at)
) PARTITION BY RANGE (run_at);

-- One row per test per run; the verdict and the numbers behind it
CREATE TABLE test_results (
    result_id         UUID NOT NULL DEFAULT gen_random_uuid(),
    run_id            UUID NOT NULL,
    run_at            TIMESTAMPTZ NOT NULL,
    test_id           TEXT NOT NULL,                -- T1 .. T6
    verdict           TEXT NOT NULL,                -- PASS / REVIEW / FAIL
    numbers           JSONB NOT NULL,               -- AIR, intervals, sweep rows, ablation, pairs
    rule_text         TEXT NOT NULL,                -- the rule that produced the verdict
    PRIMARY KEY (result_id, run_at),
    FOREIGN KEY (run_id, run_at) REFERENCES test_runs (run_id, run_at)
) PARTITION BY RANGE (run_at);

-- A recorded exception to a FAIL or REVIEW: a proposer and a different approver
CREATE TABLE exceptions (
    exception_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id         UUID NOT NULL,
    run_at            TIMESTAMPTZ NOT NULL,
    proposed_by       TEXT NOT NULL,
    approved_by       TEXT NOT NULL,
    reason            TEXT NOT NULL,
    expires_at        TIMESTAMPTZ NOT NULL,
    decided_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (result_id, run_at) REFERENCES test_results (result_id, run_at)
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

**Applicant-level data.** The tests need a score, a decision, an outcome and a group label per decision. They do not need names, addresses or free text. The design tokenizes the applicant identifier before it reaches the columnar store and keeps the group label in a separate, more restricted store joined only inside a run. Where a reviewer needs the original record to adjudicate, it is fetched from the model's own scoring log by token, under that system's retention and access rules. FairLens does not become a second copy of customer data, and a group inference is never written back to a customer record.

### ClickHouse schema (the time-series tables)

```sql
CREATE TABLE decision_results (
    model_version_id  UUID,
    scored_at         DateTime64(3, 'UTC'),
    applicant_token   String,
    score             Int32,
    approved          UInt8,
    defaulted         UInt8,
    group_label       LowCardinality(String),
    top_reason        LowCardinality(String),
    run_id            UUID
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/decision_results', '{replica}')
PARTITION BY toYYYYMM(scored_at)
ORDER BY (model_version_id, scored_at)
TTL scored_at + INTERVAL 730 DAY DELETE;  -- 2-year hot retention, matching the table below
```

### Retention & data classification

The retention periods below are 🔴 design defaults. Confirm each against the bank's own record-retention schedule before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Runs, results and verdicts | 7 years | Postgres, archive to Object Lock | Confidential |
| Exceptions and approvals | 7 years | Postgres, archive to Object Lock | Confidential |
| Evidence bundles | 7 years | Object storage with Object Lock | Confidential |
| Per-decision results (tokenized) | 2 years hot | ClickHouse | Restricted |
| Group labels and inferences | Shortest period counsel allows; never copied to a customer record | Separate restricted store | Restricted |
| Audit log | 7 years | Postgres partitioned, archive to Object Lock | Confidential |
| Verdict cache | TTL, hours | Redis | Internal |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with customer-managed keys (CMEK / CMK) in Cloud KMS, AWS KMS or Azure Key Vault, one key ring per region. Keys never cross a region boundary. The group-label store has its own key.
- **In transit.** TLS 1.3 north-south. mTLS east-west through the service mesh.
- **Field-level.** Applicant identifiers are tokenized before the columnar store; the token key is separate from the data key.
- **Database-level.** Transparent data encryption on PostgreSQL, encrypted disks on ClickHouse, encryption at rest on Redis.

### Secrets management

- **Primary store.** HashiCorp Vault or the cloud secret manager. No long-lived static credentials.
- **Application secrets** (scoring-log read token, webhook signing secret, database passwords): fetched at boot through workload identity, rotated on the bank's schedule with dual-credential rolling.
- **Service-account keys.** None. Workload Identity on GCP, IAM Roles for Service Accounts on AWS, Managed Identity on Azure.
- **Webhook secrets.** Per-pipeline signing secret, rotated; the reader verifies the signature before it reads anything.

### Identity provider & user management

- **IdP.** Whatever the bank already runs (Okta, Microsoft Entra ID, Ping). SAML 2.0 and OIDC. FairLens does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Sessions.** OIDC ID token plus signed session cookie (HttpOnly, Secure, SameSite=Strict), with absolute and idle expiry set by bank policy.
- **Service-to-service identity.** SPIFFE IDs; each component has its own workload identity and mTLS enforces it at every hop.

### RBAC matrix

Authorization is enforced at the verdict API with OPA, and every action is written to `audit_log`.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `fl:viewer` | Read verdicts, numbers and trends | Audit, executives |
| `fl:owner` | Viewer + read evidence for their own models, propose an exception | Model owner (line-1) |
| `fl:policy` | Viewer + read the sweep and propose a cutoff change | Credit policy |
| `fl:reviewer` | Owner rights across models + approve an exception, edit verdict rules under change control | Model risk (line-2) |
| `fl:counsel` | Viewer + read group-label sources and label-error sensitivity | Compliance, fair-lending counsel |
| `fl:admin` | Config, integrations, role management | Platform engineering lead |

An exception to a FAIL needs a proposer and a different approver. Both are recorded in `exceptions`. Nobody holds both `fl:owner` and `fl:reviewer` for the same model.

### Network controls

- **Perimeter.** VPC Service Controls (GCP), PrivateLink plus Network Firewall (AWS) or Private Endpoints (Azure). No public ingress for the verdict API; the reader reaches only the scoring-log and outcome endpoints on an allow-list.
- **Lateral.** Network policies and layer-7 inspection on the service mesh; workers read the decision snapshot through a read-only view and can reach nothing else. Only `fl-groups` can reach the label store.
- **Ingress.** The verdict API is called by release pipelines over mTLS; the console sits behind the bank's SSO.
- **Zero-trust.** Every inter-service call is authenticated. No "trusted internal network" assumption.

### Threat model

| Threat | Mitigation |
| --- | --- |
| The model owner re-tunes the cutoff to land just inside the screen | The sweep and its headroom are part of the verdict: a pass with under 10 points of headroom is REVIEW, and the cost of passing is printed beside it. |
| Group labels are wrong, so a failing screen passes | Label-source approval by counsel; measured label error stored with every run; sensitivity printed beside every verdict. The prototype's example: a failing screen passes at 14.8% label error. |
| A verdict is quoted as a legal finding or a compliance pass | The output says screen, prints its known limits, and carries no legal language. Counsel owns conclusions. |
| Protected-class inferences leak into other systems | A separate restricted store, its own key, access only through `fl-groups`, and a rule that inferences are never written to a customer record. |
| Thresholds changed quietly to turn a FAIL into a PASS | Verdict rules are versioned configuration under change control; the rules version is stored with every run; a change needs a proposer and a different approver. |
| The ablation only finds the proxy someone named | Roadmap item: ablate every input in turn and review inputs that correlate with group. Until then the console lists which inputs were ablated. |
| A thin or stale decision snapshot makes a run look clean | Minimum decisions per group; below it the verdict is REVIEW. The snapshot hash and its time window are stored with the run. |

---

## 4a. APIs consumed and exposed

FairLens is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Model scoring log and outcome store | Read-only view, workload identity | Scores, decisions, outcomes for a model version and window | Run is incomplete; check says REVIEW or holds per mode |
| Group-label source or inference step | Internal API, mTLS, restricted role | A label (or a probability) per tokenized applicant | Run says REVIEW with "labels unavailable" |
| Bank IdP (Okta / Entra / Ping) | SAML 2.0 + OIDC | Console login, role lookup | Existing sessions continue |
| Model-risk record (GRC tool) | Vendor REST, service principal | File runs, verdicts and evidence bundles | Local audit trail continues; sync resumes later |
| Monitoring (OpenTelemetry to the platform's stack) | OTLP over TLS | Metrics and traces | Local buffer |
| Paging and chat | REST / webhook | Alert routing | Email fallback |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/runs` | OpenAPI 3.1 over HTTPS, mTLS service identity | Release pipelines; EvalForge (04) as a runner |
| `GET /v1/models/{model}/status` | mTLS service identity | TierGate (11), DriftSentinel (02), ControlMap (16) |
| `GET /v1/runs/{run_id}` | mTLS service identity | Console, audit |
| Console API | OIDC bearer, role-checked by OPA | `fl-console` |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Model-risk record, incident management |

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** The surface is one run endpoint, one status endpoint and a console. OpenAPI generates the pipeline client and the console SDK from one spec.
- **Idempotency key on `runs`.** A retried pipeline step must not open a second run. UUID v4 in the `Idempotency-Key` header.
- **The response carries the numbers, not just the verdict.** Each test returns its verdict, the figures behind it and the rule that produced it, so a model owner can fix the model without a meeting.
- **The seed travels with the run.** The bootstrap seed and the number of resamples are inputs and are stored, so a run reproduces exactly.
- **Status is cheap and cacheable.** Consumers ask "is there an open FAIL for this model" many times; the answer is a small document with a TTL.
- **Webhooks are signed, not just authenticated.** HMAC-SHA256 with a per-consumer rotating secret.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry into the platform's existing monitoring | The on-call engineer's existing pane |
| Verdicts over time | ClickHouse + dashboards | PASS, REVIEW and FAIL rates per model and per test |
| Queue age and worker health | Metrics | Drives the fail-open or fail-closed behavior |
| Audit log | Postgres, archived to Object Lock | Record-keeping |

**SLOs worth owning (🔴 design targets, none measured).**

| SLO | Why it is the PM's number |
| --- | --- |
| **Releases and cutoff changes with a run before going live** | The north star. Everything else supports it. |
| **Label coverage** | A run on stale or missing labels is worse than no run |
| **Open FAILs that reached production** | The cost of a gate that is deployed around |
| **REVIEW verdicts a person later clears** | The cost side of the pack. Too many and reviewers stop reading it. |
| **Run latency** | 🔴 Design target is one pipeline step; not measured |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P1 | A release reached production with an open FAIL on a tier-1 model | Paging |
| P2 | Labels unavailable; scoring-log read failing; queue aging; store unavailable | Paging (low urgency) + chat |
| P3 | A rules-version change; a model with no run in its window | Chat |
| P4 | A group below the minimum size; daily digest | Email |

### Rollout

Shadow first: run the pack on historical decisions and compare each verdict with what the validators concluded by hand. Then validate the label source, then advisory runs, then blocking for tier-1 models, as laid out in the PRD. Automatic fallback of a blocking mode to advisory if the share of REVIEW verdicts a person later clears breaches its threshold.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **ClickHouse.** Weekly backup to object storage; replicated engine for HA inside a region.
- **Object stores.** Object Lock and versioning for evidence bundles and archived verdicts.
- **Runs.** Reproducible by design: the snapshot hash, the seed, the rules version and the label source are stored with every run.
- **DR drill cadence.** Quarterly failover to the secondary region, validated against the model platform's own recovery objective.

### Runbooks (one page each, in `docs/runbooks/`)

- `fail-on-release.md` — a FAIL landed: read the numbers, read the sweep, contact the owner
- `review-resolution.md` — resolve a REVIEW: confirm, collect more data or record an exception
- `labels-unavailable.md` — the label source is stale or down
- `small-group.md` — a group fell below the minimum size
- `label-error.md` — measured label error moved: rerun and compare
- `evidence-pull.md` — pull the run, the seed and the snapshot hash for a model version

---

## 6. Compliance posture

Alignment, not certification. These are the standards the design is written against. Obligation themes below are a paraphrase written for this exercise, not the text of any rule.

| Framework | How the design relates |
| --- | --- |
| **SR 26-2 / model risk management** | The current model-risk guidance (Federal Reserve, OCC and FDIC, April 2026; it replaced the 2011 predecessor, SR 11-7). The theme the design maps to is ongoing outcomes analysis on a model in use; the run record and evidence bundles are that analysis for the question of how groups are treated. |
| **Regulation B** | The theme is that credit decisions must not discriminate on a prohibited basis and that declined applicants are told the principal reasons. The pack's reason-code test supplies evidence on the second; the first is a legal question the pack does not answer. |
| **29 CFR 1607** | The four-fifths convention comes from employment guidance. The design uses it only as a screening convention and says so in every output. |
| **NIST AI RMF** | The Measure and Manage functions map to the six tests and to the exception process. |
| **EU AI Act** | Creditworthiness assessment of natural persons is among the topics the Act treats as high-risk. The design treats the full pack as mandatory for the highest tier. |

---

## 7. What's deliberately not here

- **A group-inference model.** Real credit data does not carry group labels. The design reserves a separate adapter with its own validation; the prototype does not build it.
- **A legal conclusion.** AIR is a screening statistic. Whether a model is unlawful is for counsel and the regulator.
- **A search for less discriminatory alternatives.** The pack runs one ablation per named input. A real search is a modeling exercise that belongs to the model owner.
- **Automatic cutoff changes.** FairLens prices a cutoff move; credit policy makes it.
- **A drift monitor or a generic eval harness.** Those are DriftSentinel (02) and EvalForge (04). FairLens is the fairness content they would run.
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each one is already owned by another system or another phase.

---

## Appendix — sample API contract

```python
# POST /v1/runs
# Auth: mTLS service identity (release pipeline)
# Header: Idempotency-Key: <uuid>
{
    "model": "credit-scorecard-stub",
    "version": "synthetic-1",
    "cutoff_points": 190,
    "bootstrap_seed": 20261019,
    "bootstrap_n": 1000
}
# Response 200
{
    "mode": "advisory",
    "tests": [
        {"id": "T1", "verdict": "FAIL",   "numbers": "approval 83.5% / 64.3% / 62.7%, spread 20.9 points"},
        {"id": "T2", "verdict": "FAIL",   "numbers": "lowest AIR 0.750 (Group C); 2 of 2 non-reference groups below 0.80"},
        {"id": "T3", "verdict": "FAIL",   "numbers": "screen holds up to cutoff 185; cutoff 190 is 5 points above"},
        {"id": "T4", "verdict": "FAIL",   "numbers": "lowest AIR 0.750 -> 0.871, accuracy 87.1% -> 89.2%"},
        {"id": "T5", "verdict": "PASS",   "numbers": "578 of 735 matched pairs differ (78.6%) against 75.4% within Group A"},
        {"id": "T6", "verdict": "REVIEW", "numbers": "Group C (n 450) AIR 0.750, interval 0.698 to 0.808, straddles 0.80"}
    ],
    "label_source": "held",
    "evidence_uri": "object-lock://fairlens/evidence/...",
    "run_id": "9d3e5b1a-..."
}
```

The verdicts and the numbers in the example are the prototype's `step_04` output on the synthetic data. The model name, the URI and the ids are illustrative.

OpenAPI spec lives at `docs/api/openapi.yaml` and is the source of truth for the pipeline client and the console.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/17-fairlens-credit-model-fairness/demo.html).
