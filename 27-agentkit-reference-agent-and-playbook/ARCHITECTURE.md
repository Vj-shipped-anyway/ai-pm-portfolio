# Architecture — AgentKit

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO and your platform engineering lead on day one.

> **Status.** This is the design for the production shape. The repo implements the mechanic as a prototype: a brief loader, a tool registry, an orchestrator, an append-only audit log, a shadow harness and a deterministic reasoning stub, in Python standard library only, over synthetic data, with 242 unit tests, four step scripts and a Streamlit app. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so (🔴).

This doc is cloud-agnostic where the design allows it and explicit where it doesn't. Every BFSI shop is on AWS, GCP or Azure (or two of three). GCP is shown as primary; AWS and Azure equivalents are called out inline.

![AgentKit flow](./assets/agentkit-flow.svg)

---

## 1. Logical architecture

AgentKit is a delivery kit for an agent that takes over a rule-based operations workflow. It does not replace the systems the workflow runs on, the people who hold the approval steps, the permission review, or the observability stack. It sits between a build brief and a running agent and makes four things checkable: what the agent may touch, where a person must answer, what it did, and how it compares with the people it replaces.

Ten components. Four sit in the path of a case; six do not.

| Component | Responsibility | Language / framework | In the case path? | Stateful? |
| --- | --- | --- | --- | --- |
| `ak-brief` | Validates a `build-brief/v1` file (exact keys, cross-checks; a step id outside the catalog is a warning and the brief cannot be run), versions it, derives the workflow config and the acceptance tests. The prototype's `brief.py`. | Python 3, Pydantic v2 in production | No, at deploy | Stateful (versions) |
| `ak-gateway` | The one choke point between the agent and a system. Checks the kill switch, the scope from the brief, the approval a write needs, the idempotency key and the output shape; writes one audit event per call. The prototype's `tools.py`. | Python, FastAPI | Yes | Stateful (keys) |
| `ak-orchestrator` | Runs the step state machine per case: retries, fallback to the human queue, gate parking, the S10 approval check. The prototype's `orchestrator.py` and `skills/`. | Python workers | Yes | Stateful (case state) |
| `ak-approvals` | The S07 and S09 queue. Parks a case at a gate, records who answered, and checks the answer (a person, the gate's role, not the preparer, the right correction digest). | Python, FastAPI; the bank's own work-queue product where one exists | Yes | Stateful |
| `ak-audit` | Append-only, hash-chained store of every decision, tool call, gate, approval and route, with a chain check and a completeness check. The prototype's `audit.py`. | PostgreSQL 15 plus object storage with Object Lock | Yes (write) | Stateful |
| `ak-killswitch` | An operator flag every orchestrator and the gateway read before acting; engage and release are recorded actions. | Existing flag service, or a thin service | Yes (read) | Stateful |
| `ak-reasoner` | The drafting step behind two methods, `draft_correction` and `draft_case_note`. The prototype ships a deterministic stub; a model could sit behind the same interface after an evaluation gate. | Python | No, called by workers | No |
| `ak-shadow` | Replays historical cases read-only with every write a dry run, joins the proposals to the recorded outcome and writes the scorecard. The prototype's `shadow.py`. | Python batch jobs | No | No |
| `ak-console` | Case view, audit trace viewer, approval screen, scorecard, brief viewer. | React + Next.js + Tailwind | No | No |
| `ak-telemetry` | OpenTelemetry spans and metrics, exported off the case path; feeds the platform's observability (05 AgentWatch). | OTel Collector | No, async | No |

**What is in the case path, and what is not.** A case touches the orchestrator, the gateway, the approval queue and the audit store. If the console, the shadow job, the telemetry exporter or the reasoner were down, cases that do not need a drafted correction would continue; a case that needs one parks. If the audit store is unreachable the gateway refuses writes: a case does not proceed without a trace (🔴 design stance; the prototype writes to memory and a file).

**The reasoner is a stub in this repo.** The two drafting methods are deterministic templates labelled STUB in code, README and app. They are not a model and nothing about them describes model behavior. A model behind the same interface is a later, separate decision with its own evaluation gate.

**Repo structure** (prototype, as built):

```
27-agentkit-reference-agent-and-playbook/
├── briefs/wire_repair_agent_brief.json     # a sample build-brief/v1, hand-written
├── briefs/stepscout_snapshot/              # three briefs StepScout (26) wrote, copied, not hand-written
├── playbook/DELIVERY_PLAYBOOK.md           # eight gates and engineering standards (a design)
├── data/                                   # generator and eight CSVs (synthetic)
├── src/
│   ├── agentkit/
│   │   ├── brief.py                        # validate, derive config and acceptance tests
│   │   ├── tools.py                        # registry: scope, approval, idempotency, output shape
│   │   ├── orchestrator.py                 # state machine, gates, four-eyes, kill switch, fallback
│   │   ├── audit.py                        # append-only JSONL, hash chain, completeness
│   │   ├── reasoning_stub.py               # STUB: deterministic drafting templates
│   │   ├── shadow.py                       # replay, scoring, auto-wrong
│   │   ├── handoff.py                      # runbook skeleton, monitoring signals, exit status
│   │   ├── environment.py faults.py gates.py approvers.py matching.py data_io.py kit.py catalog.py errors.py
│   │   └── skills/                         # one module per agent step: S01-S06, S08, S10-S12
│   ├── step_01 ... step_04, common.py, app.py, _build_demo.py
└── tests/                                  # unittest, standard library
```

Production shape (🔴 design; monorepo):

```
agentkit/
├── services/
│   ├── gateway/        # FastAPI: scope, approval, idempotency, audit write
│   ├── orchestrator/   # workers: step state machine
│   ├── approvals/      # S07 and S09 queue and answer checks
│   ├── audit/          # writer, chain verifier, completeness job
│   ├── shadow/         # replay and scorecard jobs
│   └── console/        # review UI
├── libs/
│   ├── brief/          # schema, validator, derivation
│   ├── skills/         # one module per step
│   └── matching/       # name and account matching, with calibration tests
├── briefs/             # versioned, approver per version
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
    └── calibration/    # shadow replays on labeled history
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| `ak-gateway` | Cloud Run (min instances 2) | ECS Fargate | Container Apps | Stateless; a choke point needs a warm pair |
| `ak-orchestrator` | GKE worker pool | EKS worker pool | AKS worker pool | Long-running per-case work with retries |
| `ak-approvals` | Cloud Run | ECS Fargate | Container Apps | Stateless API over the case store |
| `ak-audit` writer | Cloud Run | ECS Fargate | Container Apps | Single-writer ordering per chain |
| `ak-shadow` | Cloud Run jobs | ECS Fargate tasks | Container Apps jobs | Batch; read-only credentials |
| `ak-console` | Cloud Run | ECS Fargate | Container Apps | Stateless UI |
| Stores | Cloud SQL for PostgreSQL; Cloud Storage with Object Lock | RDS; S3 Object Lock | Azure Database for PostgreSQL; Blob immutability | The platform team already runs them |

**Failure behavior (the decision that matters most).** The orchestrator has one rule for every failure it cannot resolve: the case goes back to the human queue with the reason, and nothing is guessed or dropped. A tool that keeps failing, a malformed record, a call outside scope, a draft that fails its rule check and a kill switch all end the same way.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Tool timeout or malformed answer | Retried to the attempt limit (prototype: 3), then the case goes to the human queue | P3 on a rate rise |
| Watch-list screen unavailable | The case never proceeds unscreened; it goes to the human queue | P2 |
| Audit store unreachable | The gateway refuses writes; cases park (🔴 design) | P1 |
| Approval service unreachable | Cases park at the gate; nothing resubmits | P2 |
| Kill switch engaged | No new step, no tool call; open cases go to the human queue with their trace | P2 |
| Out-of-scope call attempted | Refused and logged; the case goes to the human queue | P3, P2 on a burst |
| Duplicate delivery | Closed once as a duplicate; a write keyed by the exception cannot repeat | P4 on a rate rise |
| A brief names a step the kit has no skill for | The brief validates with a warning; deriving a runnable config or starting the orchestrator is refused with a named error | P4 |
| A pack starts mid-workflow and a step lacks an earlier step's result | The case goes to the human queue with the reason `prerequisite_missing`; no tool is called | P3 on a rate rise |
| Hash chain or completeness check fails | Alert; the owner decides whether to pause | P1 |

**Latency.** The only new wait on a step is the gateway's scope check, the audit write and, at a gate, a person. 🔴 Design target: gateway overhead under 50 ms per call at the 95th percentile. It has not been measured in this repo; the prototype replays 600 cases in about two seconds with every call logged.

### Network topology

```
Work queue / case system / payments systems
   │   per-tool credentials, least privilege (read-only where the brief says read)
   ▼
[ak-gateway] ◄── scope, approval, idempotency from the brief ◄── [ak-brief] (versions, approvers)
   │      └──► [ak-audit] ──► PostgreSQL (hash chain) ──► object storage (Object Lock)
   ▼
[ak-orchestrator] ──► [ak-reasoner] (stub now; a model later, behind the same interface)
   │
   ├──► [ak-approvals] ◄── S07 analyst, S09 reviewer, in the bank's SSO ◄── [ak-console]
   └──► human queue (the fallback for everything unresolved)

Out of band:
   [ak-shadow] replays history read-only and writes the scorecard
   [ak-killswitch] flag read by gateway and orchestrator
   [ak-telemetry] OTel ──► the platform's observability (05 AgentWatch)
   Interlocks (all designed, none built): TierGate (11), ValueLedger (12), ScopeKeeper (23), AgentWatch (05), KillSwitch (25), StepScout (26)
```

### Region & DR

- Primary and DR regions follow the workflow's own footprint. AgentKit does not get a different recovery objective from the process it takes over.
- Region-specific instances where data residency applies. Each has its own database and key ring.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | Briefs and versions, case state, step records, approvals, idempotency keys, shadow runs, acceptance results, kill-switch events, the audit events | Relational integrity for the trail; the platform team already runs it |
| **Object storage with Object Lock (WORM)** | Archived audit segments and scorecard bundles | Write-once-read-many for the record-keeping policy |
| **Redis** (optional) | The kill-switch flag's cache and short-lived idempotency lookups | TTL eviction handles cleanup |

### PostgreSQL schema (the consequential tables)

```sql
-- One row per version of a build brief; the derived config and acceptance tests come from here
CREATE TABLE brief_versions (
    brief_id       TEXT NOT NULL,
    version        INT  NOT NULL,
    body           JSONB NOT NULL,                -- the build-brief/v1 file
    validated_at   TIMESTAMPTZ NOT NULL,
    approved_by    TEXT NOT NULL,                 -- the approver of this version
    approved_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (brief_id, version)
);

-- One row per case the orchestrator has taken
CREATE TABLE cases (
    case_id        TEXT PRIMARY KEY,
    exception_ref  TEXT NOT NULL,
    brief_id       TEXT NOT NULL,
    brief_version  INT  NOT NULL,
    mode           TEXT NOT NULL,                 -- shadow / live
    state          TEXT NOT NULL,                 -- running / waiting_s07 / waiting_s09 / closed / escalated / queued_human / killed
    route          TEXT,                          -- auto / to_person / human_queue
    proposed_outcome TEXT,
    reason_kind    TEXT,
    opened_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- A write's idempotency key; a replay returns the first answer and runs nothing
CREATE TABLE idempotency_keys (
    idem_key       TEXT PRIMARY KEY,
    case_id        TEXT NOT NULL,
    tool           TEXT NOT NULL,
    action         TEXT NOT NULL,
    result         JSONB NOT NULL,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- A person's answer at a gate; append-only
CREATE TABLE approvals (
    approval_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id        TEXT NOT NULL,
    step           TEXT NOT NULL,                 -- S07 / S09
    actor_id       TEXT NOT NULL,                 -- a person identity, never an agent identity
    role           TEXT NOT NULL,
    result         TEXT NOT NULL,                 -- accepted / declined / rejected_invalid
    correction_digest TEXT,                       -- the exact correction the answer covers
    problem        TEXT,
    decided_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Every decision, tool call, gate, approval and route; hash-chained; partitioned by month
CREATE TABLE audit_events (
    seq            BIGINT NOT NULL,
    case_id        TEXT NOT NULL,
    step           TEXT,
    kind           TEXT NOT NULL,                 -- case_start / decision / tool_call / gate / approval / retry / fallback / kill_switch / route
    actor          TEXT NOT NULL,
    detail         JSONB NOT NULL,
    prev_hash      CHAR(64) NOT NULL,
    hash           CHAR(64) NOT NULL,
    occurred_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (seq, occurred_at)
) PARTITION BY RANGE (occurred_at);

-- A shadow replay and what it found
CREATE TABLE shadow_runs (
    run_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_id       TEXT NOT NULL,
    brief_version  INT  NOT NULL,
    cases          INT  NOT NULL,
    scorecard      JSONB NOT NULL,                -- agreement by class, routes, confusion, disagreements
    acceptance     JSONB NOT NULL,                -- one row per acceptance test: measured, limit, passed
    miss_list      JSONB NOT NULL,                -- the known misses, attached to the scorecard
    ran_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Engage and release of the kill switch, each a recorded action
CREATE TABLE killswitch_events (
    event_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action         TEXT NOT NULL,                 -- engage / release
    actor_id       TEXT NOT NULL,
    reason         TEXT NOT NULL,
    occurred_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**What is stored about customers.** In the prototype, synthetic names and account numbers appear in the audit values because the data is synthetic. 🔴 Production design: the audit log carries field names, digests and masked values; full values stay in the system of record and the trace points to them by case id.

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-keeping schedule before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Audit events | 7 years | Postgres partitions, archive to Object Lock | Confidential |
| Approvals and kill-switch events | 7 years | Postgres, archive to Object Lock | Confidential |
| Brief versions and shadow scorecards | 7 years | Postgres | Confidential |
| Case state | 2 years after closure | Postgres | Confidential |
| Idempotency keys | 90 days | Postgres | Internal |
| Kill-switch flag cache | TTL, minutes | Redis | Internal |

---

## 4. Security architecture

An agent that can write to payment systems is a privileged system. It is designed as one.

### Encryption

- **At rest.** AES-256 with customer-managed keys (CMEK / CMK) in Cloud KMS, AWS KMS or Azure Key Vault, one key ring per region.
- **In transit.** TLS 1.3 north-south. mTLS east-west through the service mesh.
- **Database-level.** Transparent data encryption on PostgreSQL; encryption at rest on Redis.

### Secrets management

- **Primary store.** HashiCorp Vault or the cloud secret manager. No long-lived static credentials.
- **Per-tool credentials.** One credential per tool in the brief, with the least privilege that does the listed actions. A tool the brief calls `read` gets a read-only credential, so that a bug in the gateway cannot write.
- **Service-account keys.** None. Workload Identity on GCP, IAM Roles for Service Accounts on AWS, Managed Identity on Azure.

### Identity provider & user management

- **IdP.** Whatever the bank already runs (Okta, Microsoft Entra ID, Ping). SAML 2.0 and OIDC. AgentKit does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Person and agent identities are different namespaces.** An approval is accepted only from a person identity. An agent identity can never approve, whatever role it is given.
- **Service-to-service identity.** SPIFFE IDs; mTLS at every hop.

### RBAC matrix

Authorization is enforced at the gateway and the approval service with OPA, and every decision is written to the audit store.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `ak:viewer` | Read cases, traces, scorecards and briefs | Audit, executives |
| `ak:analyst` | Answer an S07 gate | Payments operations analyst |
| `ak:reviewer` | Answer an S09 gate, never for a case they judged at S07 | Payments operations reviewer |
| `ak:operator` | Engage the kill switch; release it with a second person | On-call engineer |
| `ak:engineer` | Propose a brief change or a code change | Platform engineer |
| `ak:owner` | Approve a brief version | Process owner, owning team lead |
| `ak:admin` | Config, integrations, role management | Platform engineering lead |

No role can both prepare and approve the same correction. A brief change and a code change that widens scope need different people.

### Network controls

- **Perimeter.** VPC Service Controls (GCP), PrivateLink plus Network Firewall (AWS) or Private Endpoints (Azure). No public ingress for the gateway or the approval service.
- **Lateral.** Network policies; the gateway reaches only the systems named in the brief's tools, on an allow-list.
- **Ingress.** The console and the approval screens sit behind the bank's SSO.
- **Zero-trust.** Every inter-service call is authenticated.

### Threat model

| Threat | Mitigation |
| --- | --- |
| The agent, or a model behind it, is steered to call something outside its remit (an excessive-agency failure) | Scope is enforced by the gateway from the brief, independent of the reasoner. An out-of-scope call is refused, logged and ends the case in the human queue. |
| The agent approves its own work | Approval is accepted only from a person identity, in the gate's role, different from the S07 judge and the preparer, for the exact correction digest. |
| An approval is replayed for a different correction | The approval carries the correction digest; the gateway and the orchestrator both check it. |
| A retry or a redelivery pays twice | Every write carries an idempotency key; the gateway replays the first answer and the downstream system dedupes on its side. A lost answer after a write is retried with the same key. |
| A tool's answer is garbled or hostile | Every tool declares an output shape; an answer that does not match is not used and is retried, then the case goes to the human queue. Tool output is data, never instructions. |
| The audit log is edited or truncated | Append-only store, hash chain, a completeness check against the gateway's call counts and the orchestrator's step, gate and approval counts, WORM archive. |
| The kill switch is abused or forgotten | Engage and release are recorded actions; release needs a second person (🔴 design; the prototype records who). |
| The reason-code table is changed quietly | The table is versioned, owned by the process owner, and a change is a brief change with an approver. |
| A shadow scorecard becomes a league table of workers | Pseudonymous ids, aggregate-only views, no per-worker output in the console. A works-council read is needed before any real program (🔴 designed, not built). |

---

## 4a. APIs consumed and exposed

AgentKit is a glue layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Exception work queue | Vendor or internal API, read-only credential | Fetch the exception | Retried; the case goes to the human queue after the attempt limit |
| Reason-code rule table | Read-only API | Look up a code | Same |
| Payments database | Read-only credential | Get the original payment | Same |
| Watch-list screening service | Vendor REST, workload identity | Screen a name | The case never proceeds unscreened; it goes to the human queue |
| Repair worksheet | Internal API, write on one resource | Write the five beneficiary fields as text and read them back | A copy that differs from the source is a malformed record |
| Case system | Internal API, write | Open, append a note, close, escalate | Retried; the trace continues locally |
| Payments gateway | Internal API, write, idempotency key, approval required | Resubmit a corrected payment | Retried with the same key; never without an approval |
| Bank IdP (Okta / Entra / Ping) | SAML 2.0 + OIDC | Console login, role lookup | Existing sessions continue |
| Monitoring (OpenTelemetry to the platform's stack) | OTLP over TLS | Metrics and traces | Local buffer |
| Paging and chat | REST / webhook | Alert routing | Email fallback |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `POST /v1/cases` | OpenAPI 3.1 over HTTPS, mTLS service identity | The work queue's dispatcher |
| `GET /v1/cases/{case_id}/trace` | mTLS or OIDC, role-checked by OPA | Console, audit |
| `POST /v1/gates/{case_id}/{step}/answer` | OIDC, person identity only | Approval screens |
| `POST /v1/killswitch` and `DELETE /v1/killswitch` | OIDC, `ak:operator`; release needs a second person | Console, runbook |
| `GET /v1/briefs/{brief_id}/acceptance` | mTLS service identity | Rollout controller, dashboards |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Incident management (19 IncidentLedger), AgentWatch (05) |

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** A handful of resources, each with a clear owner.
- **A write is never accepted without an idempotency key.** A retried click or a redelivered message must not create a second effect.
- **The answer to a gate carries the digest of the correction it covers.** An approval for one correction is not an approval for another.
- **The response carries the reason, not only the state.** A case's state, route and reason kind come back every time, so an on-call person can read it without a meeting.
- **Webhooks are signed, not just authenticated.** HMAC-SHA256 with a per-consumer rotating secret.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry into the platform's existing monitoring | The on-call person's existing pane |
| Gate queue depth and age | Metrics | The bottleneck is a person |
| Tool error and timeout rate by tool | Metrics | The early sign of a failing dependency |
| Queue-return rate, by reason kind | Postgres + dashboards | What the agent cannot do |
| Scope blocks, gate violations | Metrics and alerts | A control doing its job, or a bug |
| Chain and completeness check results | Scheduled job | The trail is itself a monitored system |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **Resubmissions without a valid approval** | Zero. The control the whole kit exists for. |
| **Out-of-scope calls executed** | Zero. |
| **Audit completeness** | 1.0, with the chain intact. |
| **Agreement on a weekly sample** | The drift signal against the people the agent replaces. |
| **Share of cases returned to the human queue** | Too high and the agent is not doing the work; too low and something is being forced through. |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P1 | A resubmission without an approval; the audit store unreachable; a chain or completeness failure | Paging |
| P2 | Watch-list screen down; approval service down; kill switch engaged; a burst of scope blocks | Paging (low urgency) + chat |
| P3 | Tool error rate up; an out-of-scope attempt | Chat |
| P4 | A duplicate-delivery rate rise; daily digest of cases returned to the human queue | Email |

### Rollout

Offline tests, then shadow mode, then a limited share of live cases with both gates held by people, then the full queue with the gates retained, as laid out in the delivery playbook. The kit falls back to the human queue for anything it cannot resolve.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **Object stores.** Object Lock and versioning for archived audit segments.
- **Kill-switch flag.** Its last state is also written to the store, so a rebuilt flag service starts from the truth.
- **DR drill cadence.** Quarterly failover validated against the workflow's own recovery objective.

### Runbooks (one page each, in `docs/runbooks/`)

- `RB-01-killswitch.md` — engage and release the kill switch
- `RB-02-read-a-trace.md` — read the audit trace for one case and verify the chain
- `RB-03-human-queue-case.md` — work a case that came back, by reason kind
- `RB-04-tool-timeouts.md` — respond to a burst of tool timeouts
- `RB-05-duplicate-delivery.md` — handle a duplicate delivery alert
- `RB-06-scope-change.md` — change a tool's scope through a change request
- `RB-07-rollback.md` — return intake to the human-only process

`handoff.build_runbook` drafts a skeleton of these from the brief. The skeleton carries what the brief already knows and marks the operator's steps TO WRITE. Nobody has run it.

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against. Obligation statements are paraphrases written for this exercise, not the text of any rule.

| Framework | How the design relates |
| --- | --- |
| **NIST AI RMF** | Govern: the brief, its approver and the role split. Map: the step classification and the scope. Measure: the shadow scorecard and the acceptance tests. Manage: the kill switch, the fallback to the human queue and the post-launch review. |
| **EU AI Act, human oversight** | The expectation that a person can oversee, intervene in and interrupt a high-risk system. S07 and S09 are always a person, and the kill switch is the interrupt. |
| **OWASP LLM Top 10 (excessive agency)** | The scope is enforced outside the reasoner, so a model behind the drafting step could not widen it. |
| **Record-keeping and audit expectations** | The append-only, hash-chained trace with a completeness check is the record for a decision, a tool call, a gate and an approval. |
| **SOC 2 Type II, GDPR, India data localization** | Regional instances, masked values in the log, role-based access, append-only audit. |

---

## 7. What's deliberately not here

- **Intake and the business case.** 11 TierGate and 12 ValueLedger.
- **The permission review itself.** 23 ScopeKeeper reviews what an agent may do; AgentKit enforces the result.
- **Agent observability in production.** 05 AgentWatch watches; AgentKit emits what it watches.
- **The fallback trigger and the drills.** 25 KillSwitch designs the trigger, the per-segment switch and the drill scorecard; AgentKit has a manual switch and a route back to the human queue.
- **A model.** The drafting step is a stub. A model needs its own evaluation gate (04 EvalForge) and is a separate decision.
- **The brief generator.** 26 StepScout emits the brief shape; the sample brief here is hand-written.
- **A claim that the playbook works.** It is a design. Nobody has run it on a live program in this repo.
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each one is already owned by another system or another phase.

---

## Appendix — sample API contract

```python
# GET /v1/cases/C-0001/trace
# Auth: OIDC, role-checked by OPA
# Response 200
{
    "case_id": "C-0001",
    "brief": {"brief_id": "BB-001", "version": 1},
    "mode": "shadow",
    "state": "WAITING_S09",
    "route": "to_person",
    "proposed_outcome": "RESUBMIT",
    "reason_kind": "",
    "chain": {"intact": true, "events": 20},
    "events": [
        {"seq": 1, "kind": "case_start", "step": null, "actor": "agent", "detail": {"mode": "shadow", "brief": "BB-001"}},
        {"seq": 2, "kind": "tool_call", "step": "S01", "actor": "agent",
         "detail": {"tool": "exception_queue", "action": "fetch_exception", "outcome": "ok", "attempt": 1}},
        {"seq": 17, "kind": "gate", "step": "S09", "actor": "agent",
         "detail": {"approver_role": "payments_operations_reviewer", "digest": "48391ac7a132e688"}}
    ],
    "evidence_uri": "object-lock://agentkit/audit/..."
}
```
