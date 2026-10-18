# Architecture — AdoptionPulse

The systems doc most PM writeups skip. Databases, where the code runs, encryption posture, user management, network, operational runbooks. What you'd hand to your CISO, your privacy reviewer and your data platform lead on day one.

> **Status.** This is the design for the production shape. The repo implements the product mechanic as a prototype (stage rules read from a policy file, a unit funnel and leak, a retention curve, a ranked list and a rule-based action, over synthetic data, with a Streamlit app). Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

This doc is cloud-agnostic. It names service classes (a managed Postgres, a scheduled job runner, object storage with a retention lock) and leaves the choice of provider to the bank's own platform. The design does not depend on one.

![AdoptionPulse flow](./assets/adoptionpulse-flow.svg)

---

## 1. Logical architecture

AdoptionPulse is a read-only measurement layer. It does not sit between a person and the assistant, it never stores prompt text, and it does not change what anyone can use. It joins weekly usage counts to the staff directory, the training record and the champion roster, and answers one question per unit: where do people stop?

Seven components. Three are in the weekly run; four are not.

| Component | Responsibility | Language / framework | In the weekly run? | Stateful? |
| --- | --- | --- | --- | --- |
| `ap-ingest` | Pulls weekly per-user counts (logins, sessions, prompts, accepted outputs, advanced-feature uses) from the assistant's usage log. Replaces the staff id with a pseudonymous key at the boundary. | Python 3, scheduled job | Yes | No |
| `ap-store` | Holds usage, stages, policy versions and unit reports. | PostgreSQL 15 | Yes | Stateful |
| `ap-stager` | Applies the four stage rules from the approved policy to every licensed user for the week. The prototype's `stage_of`. | Python | Yes | No |
| `ap-report` | Builds the unit funnel, conversions, leak, training and champion reads and the retention curve. Applies the minimum group size. | Python | No, after the run | No |
| `ap-ranker` | Ranks units by the habitual users they would gain at the estate rate and attaches the rule-based action. | Python | No | No |
| `ap-console` | Read-only report for the program lead, unit heads and champions, role-checked. | React + Next.js + Tailwind | No | No |
| `ap-telemetry` | OpenTelemetry spans and metrics from every component, exported off the run path. | OTel Collector to the platform's monitoring | No, async | No |

**What is in the weekly run, and what is not.** Ingest, store and stager produce the stage rows. The report, ranker and console read them. Nothing here is in a person's request path: if AdoptionPulse is down, nobody loses access to anything, and the report is late.

**Repo structure** (production shape; monorepo):

```
adoptionpulse/
├── apps/
│   ├── ingest/         # scheduled pull, pseudonymization at the boundary
│   ├── stager/         # stage rules, policy loader
│   ├── report/         # unit cuts, leak, retention, group-size rule
│   ├── ranker/         # ranking and rule-based actions
│   └── console/        # read-only report UI
├── libs/
│   ├── policy/         # policy model, versioning, approval check
│   └── privacy/        # minimum group size, roll-up, suppression
├── infra/
│   ├── terraform/      # IaC
│   ├── kubernetes/     # charts and overlays
│   └── policies/       # access policies, network policies
├── docs/
│   ├── ARCHITECTURE.md
│   ├── runbooks/
│   └── api/            # OpenAPI spec
└── tests/
    ├── unit/
    ├── integration/
    └── calibration/    # staged users against a manager sample review
```

---

## 2. Physical / deployment architecture

### Runtime

| Component | Service class | Why |
| --- | --- | --- |
| `ap-ingest` | Scheduled container job | A weekly pull; no always-on process |
| `ap-stager` | Scheduled container job | Stateless, short-lived, one run per week |
| `ap-report`, `ap-ranker` | Scheduled container job chained after the stager | Cheap aggregates over the stage table |
| `ap-console` | Container service behind the bank's single sign-on | Stateless UI, low traffic |
| `ap-store` | Managed PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** A late or partial usage feed never produces a stage. The stager runs only on a complete week; otherwise the report shows the last complete week and says so. A unit under the minimum group size is rolled up, never shown alone. If the policy cannot be loaded, the run stops rather than falling back to defaults.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Usage feed late or partial | No stage computed for the week; the report states the last complete week | P2 |
| Directory join fails for some users | Users staged but counted as unassigned; the bucket is suppressed under the minimum size | P3 |
| Policy missing or unapproved | Run stops; the last approved version stays in force | P2 |
| Store unavailable | Run fails and retries; the console serves the last snapshot | P2 |
| Report build fails | The previous week's report stays up with its date | P3 |
| Telemetry sink down | Buffer locally, drop with a counter once full | P4 |

**Latency.** There is no real-time path. 🔴 Design target: the report is ready at the start of each week. Not built and not timed. The lever if the run is slow is to stage only the weeks that changed.

### Network topology

```
AI assistant usage log (read-only view, per-user weekly counts, no prompt text)
   │   scheduled pull
   ▼
[ap-ingest]  ── pseudonymize at the boundary ──►  [PostgreSQL: usage_weekly]
                                                         │
Staff directory ──► (unit, role, licensed week) ─────────┤
Training record ──► (trained week) ──────────────────────┤
Champion roster ──► (unit, active weeks) ────────────────┤
                                                         ▼
                                                    [ap-stager] ──► user_stage_weekly
                                                         │
                                                         ▼
                                            [ap-report] ──► [ap-ranker] ──► unit_week_report
                                                                                │
                                         ┌──────────────────────────────────────┼───────────────┐
                                         ▼                                      ▼               ▼
                                   report snapshot                        OTel Collector   ap-console
                                   (retention lock)                       ──► monitoring   (single sign-on)

Out of band:
   Interlocks: ValueLedger (12), TierGate (11), PortfolioBoard (24), InferenceLens (07) over service-to-service reads
```

### Region & DR

- Primary and DR regions follow the data platform's own footprint. AdoptionPulse does not get a different recovery objective than the platform it reads from.
- Where data residency applies, each region keeps its own database and key ring; usage rows do not replicate across regions.

---

## 3. Data architecture

### Databases by purpose

| Store | Purpose | Why this store |
| --- | --- | --- |
| **PostgreSQL 15** | Usage, stages, policy versions, unit reports, audit log | Relational integrity for the audit trail; the platform team already runs it |
| **Object storage with a retention lock** | Report snapshots | Write-once records of what was shown to whom |
| **Separate restricted schema** | Pseudonym map (user key to staff id) | Reachable only by the pseudonymization service; never by the report or the console |

### PostgreSQL schema (the consequential tables)

```sql
-- The stage rules in force: one row per approved version of funnel_policy
CREATE TABLE stage_policies (
    policy_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version       INT NOT NULL UNIQUE,
    parameters    JSONB NOT NULL,                 -- the rows of funnel_policy.csv
    proposed_by   TEXT NOT NULL,
    approved_by   TEXT NOT NULL,
    approved_at   TIMESTAMPTZ NOT NULL,
    CHECK (proposed_by <> approved_by)            -- a change needs a proposer and a different approver
);

-- One row per person per week of usage; counts only, no prompt text
CREATE TABLE usage_weekly (
    user_key          TEXT NOT NULL,              -- pseudonymous key, not the staff id
    week_start        DATE NOT NULL,
    logins            INT NOT NULL,
    ai_sessions       INT NOT NULL,
    prompts           INT NOT NULL,
    outputs_accepted  INT NOT NULL,
    advanced_uses     INT NOT NULL,
    ingested_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_key, week_start)            -- the partition key is part of the key
) PARTITION BY RANGE (week_start);

-- One row per person per week: the stage and the numbers behind it
CREATE TABLE user_stage_weekly (
    user_key              TEXT NOT NULL,
    week_start            DATE NOT NULL,
    policy_id             UUID NOT NULL REFERENCES stage_policies,
    org_unit              TEXT NOT NULL,
    stage                 TEXT NOT NULL,          -- licensed / activated / habitual / proficient
    active_weeks_last6    INT NOT NULL,
    advanced_weeks_last6  INT NOT NULL,
    accept_rate_last6     NUMERIC(4,3),
    PRIMARY KEY (user_key, week_start)
) PARTITION BY RANGE (week_start);

-- One row per unit per week; what the console reads. Never one row per person.
CREATE TABLE unit_week_report (
    org_unit        TEXT NOT NULL,
    week_start      DATE NOT NULL,
    policy_id       UUID NOT NULL REFERENCES stage_policies,
    licensed        INT NOT NULL,
    activated       INT NOT NULL,
    habitual        INT NOT NULL,
    proficient      INT NOT NULL,
    suppressed      BOOLEAN NOT NULL,             -- true when the group is under the minimum size
    leak            TEXT,                         -- licensed to activated / activated to habitual / habitual to proficient
    action          TEXT,
    unit_rank       INT,
    users_to_gain   NUMERIC(6,1),
    PRIMARY KEY (org_unit, week_start)
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
    PRIMARY KEY (audit_id, occurred_at)     -- the partition key is part of the key
) PARTITION BY RANGE (occurred_at);
```

**Why `unit_week_report` has no person column.** The console reads only this table. A unit under the minimum group size is stored with `suppressed = true` and its counts rolled into a parent unit before display. 🔴 Design target for the minimum group size: 10. In the synthetic data one unit (Internal Audit, 9 people) is under it.

### Retention & data classification

The retention periods below are design defaults. Confirm each against the bank's own record-retention schedule and the rules that apply to employee data before use.

| Data class | Retention (design default) | Storage | Classification |
| --- | --- | --- | --- |
| Weekly usage counts (pseudonymous) | 2 years | PostgreSQL, partitioned by week | Confidential |
| Weekly stages | 2 years | PostgreSQL, partitioned by week | Confidential |
| Unit reports and snapshots | 7 years | PostgreSQL, snapshots in locked object storage | Internal |
| Policy versions | Life of the product | PostgreSQL | Internal |
| Pseudonym map | Only as long as the usage rows it keys | Restricted schema | Restricted |
| Audit log | 7 years | PostgreSQL partitioned, archive to locked object storage | Confidential |
| Prompt text | Never stored | n/a | n/a |

---

## 4. Security architecture

### Encryption

- **At rest.** AES-256 with customer-managed keys in the bank's key service, one key ring per region. Keys never cross a region boundary.
- **In transit.** TLS 1.3 north-south. Mutual TLS east-west.
- **Field-level.** The staff id is replaced with a pseudonymous key at ingest. The map lives in its own schema with its own key.
- **Database-level.** Transparent data encryption on PostgreSQL.

### Secrets management

- **Primary store.** The bank's secret manager. No long-lived static credentials.
- **Application secrets** (usage-log read token, database passwords): fetched at boot through workload identity, rotated on the bank's schedule.
- **Service-account keys.** None. Workload identity for every job.

### Identity provider & user management

- **IdP.** Whatever the bank already runs. SAML and OIDC. AdoptionPulse does not run its own.
- **MFA.** Enforced at the IdP, not in the app.
- **Sessions.** OIDC ID token plus a signed session cookie (HttpOnly, Secure, SameSite=Strict), with expiry set by bank policy.
- **Service-to-service identity.** Each component has its own workload identity and mutual TLS enforces it at every hop.

### RBAC matrix

Authorization is enforced at the report API and every read is written to `audit_log`.

| Role | Can | Maps to (bank role) |
| --- | --- | --- |
| `ap:unit` | Read the report for their own unit | Unit head, champion |
| `ap:program` | Read all unit reports, see policy versions, export unit-level snapshots | AI enablement program lead |
| `ap:privacy` | Read the audit log and the suppression settings; approve a policy change | HR and privacy reviewer |
| `ap:platform` | Run and monitor the jobs; no access to unit reports by default | Data platform engineer |
| `ap:admin` | Config, integrations, role management | Platform engineering lead |

No role can read an individual's stage through the console. Where an individual view is ever offered (🔴 queued, opt-in only), it is a separate surface with its own review.

### Network controls

- **Perimeter.** No public ingress. The jobs reach only the usage log view, the directory and the store, on an allow-list.
- **Lateral.** Network policies between components; the report and console cannot reach the pseudonym schema.
- **Ingress.** The console sits behind the bank's single sign-on.
- **Zero-trust.** Every inter-service call is authenticated. No "trusted internal network" assumption.

### Threat model

| Threat | Mitigation |
| --- | --- |
| A manager uses usage data to rate a person | Unit-level reports only; minimum group size with roll-up; no individual surface; every read logged; an HR and privacy review of what is shown. |
| Small-group disclosure by differencing (two reports a week apart reveal one person) | Roll-up under the minimum size; a policy-change week prints both versions; counts under a threshold are suppressed, not rounded. |
| The usage feed becomes a second copy of staff activity | Counts only, pseudonymous key, no prompt text, 2-year retention, separate pseudonym schema. |
| Thresholds changed quietly to flatter a unit | `stage_policies` is versioned with a proposer and a different approver; every report prints the policy version. |
| "Proficient" read as "good at the work" | The label always carries its definition; the manager sample review is the check; the console states what it cannot see. |
| Report used as a league table | The ranking is by habitual users to gain, framed as where help goes, and is shown to the program lead and the unit's own head only. |

---

## 4a. APIs consumed and exposed

AdoptionPulse is a measurement layer. Every external dependency is listed with its protocol, auth model, and what happens when it is down.

### APIs consumed (north-bound, what we depend on)

| External service | Protocol / auth | What we call | Failure mode |
| --- | --- | --- | --- |
| Assistant usage log | Read-only view or export, workload identity | Weekly per-user counts | No stage for the week; report shows the last complete week |
| Staff directory | Read-only, service principal | Unit, role, licensing week | Users staged as unassigned; bucket suppressed under the minimum size |
| Training record | Read-only export | Training completion week | Training read shows "not available"; stages unaffected |
| Champion roster | Read-only export | Unit, active weeks | Champion read shows "not available"; stages unaffected |
| Bank IdP | SAML + OIDC | Console login, role lookup | Existing sessions continue |
| Monitoring (OpenTelemetry to the platform's stack) | OTLP over TLS | Metrics and traces | Local buffer |

### APIs we expose (south-bound, what others call us)

| Surface | Protocol / auth | Consumers |
| --- | --- | --- |
| `GET /v1/units/{unit}/weeks/{week}` | OpenAPI 3.1 over HTTPS, mTLS service identity or OIDC | `ap-console`; ValueLedger (12); PortfolioBoard (24) |
| `GET /v1/estate/weeks/{week}` | Same | Program lead; InferenceLens (07) for cost per active user |
| `GET /v1/policy` | Same | Anyone reading a report who needs the definitions |
| Webhooks (outbound) | HTTPS POST, HMAC-SHA256 signed | Reporting tools |

### API-design opinions (the choices a reviewer will ask about)

- **REST and OpenAPI, not GraphQL.** The surface is a few read endpoints. OpenAPI generates the console client and the interlock clients from one spec.
- **No endpoint returns a person.** There is no route keyed by user. That is a design property, not a permission.
- **The response carries the policy version and the definitions.** A number without its definition is how "proficient" gets misread.
- **Suppression is explicit.** A suppressed unit returns `suppressed: true` and no counts, not zeros.
- **Versioning in the path** (`/v1/`), with a deprecation window announced in headers.

---

## 5. Operational architecture

### Observability

| Signal | Tool | Why |
| --- | --- | --- |
| Application logs and traces | OpenTelemetry into the platform's existing monitoring | The on-call engineer's existing pane |
| Job freshness and completeness | Metrics | Drives the "last complete week" behavior |
| Report reads | Audit log in PostgreSQL | Who looked at which unit |
| Policy changes | Audit log | Who proposed, who approved |

**SLOs worth owning.**

| SLO | Why it is the PM's number |
| --- | --- |
| **Weeks with a complete report by the start of the week** | The north star for trust. A late report is read as a quiet week. |
| **Usage feed completeness** (licensed users with all weeks present) | Staging on a partial feed is worse than no staging |
| **Share of units shown above the minimum group size** | The cost side of the privacy rule |
| **Policy version on every report** | Without it a step change looks like a behavior change |
| **Report freshness** | 🔴 Design target is a report at the start of each week; not measured |

### Alerting

| Severity | Trigger | Channel |
| --- | --- | --- |
| P2 | Usage feed late or partial; policy missing; store unavailable | Paging (low urgency) + chat |
| P3 | Directory join failures; report build failure | Chat |
| P4 | Telemetry sink down; daily digest | Email |

### Rollout

Shadow first: stage a few units, show nothing, and compare the stages with a manager sample. Then calibrate, then a program-lead report, then unit heads, then the interlocks, as laid out in the PRD. A policy change rolls back by restoring the previous approved version.

### Backup & DR

- **PostgreSQL.** Continuous WAL streaming to object storage, daily snapshots, point-in-time recovery inside the retention window.
- **Object stores.** Retention lock and versioning for report snapshots.
- **Stages.** Re-derivable: any week can be recomputed from usage counts and the policy version that applied.
- **DR drill cadence.** Quarterly failover to the secondary region, validated against the data platform's own recovery objective.

### Runbooks (one page each, in `docs/runbooks/`)

- `feed-late.md` — the usage feed is late or partial: what the report says and who is told
- `policy-change.md` — propose, approve, publish; print both versions for one week
- `small-unit.md` — a unit falls under the minimum size: roll-up and suppression
- `sample-review.md` — run the manager sample review for staged-proficient users
- `access-review.md` — read the audit log for who looked at which unit

---

## 6. Compliance posture

Alignment, not certification. These are the frameworks the design is written against.

| Framework | How the design relates |
| --- | --- |
| **NIST AI RMF** | The 'Govern' function's attention to people, training and accountability is the theme behind measuring whether training and ownership change use. A paraphrase written for this exercise, not the text of the framework. |
| **Employee-data and monitoring rules** | These differ by jurisdiction and are not enumerated here. The design assumes a legal and HR review before any report leaves the program team, unit-level reporting only, and counts without prompt text. |
| **Internal record retention** | Retention periods above are design defaults to be replaced by the bank's own schedule. |

---

## 7. What's deliberately not here

- **A view of any individual.** No console route, API or export is keyed by person. An opt-in coaching view is queued, with its own review.
- **A judgment of work quality.** The weekly counts cannot see it. The manager sample review is the check, and it is a process, not a feature.
- **A benefit number.** What the usage is worth belongs to ValueLedger (12), which measures against a holdout.
- **Use-case enablement decisions.** Those belong to TierGate (11).
- **Prompt text.** Never read, never stored.
- **A standalone authentication system.** It uses the bank's IdP.

Holding that line is the scope discipline: each item above is something a team would be tempted to absorb, and each one is already owned by another system, another phase or a reviewer.

---

## Appendix — sample API contract

```python
# GET /v1/units/Customer Service/weeks/2026-09-21
# Auth: OIDC bearer, role ap:unit or ap:program
{
    "org_unit": "Customer Service",
    "week_start": "2026-09-21",
    "policy_version": 1,
    "suppressed": False,
    "stages": {"licensed": 100, "activated": 47, "habitual": 4, "proficient": 2},
    "leak": {"transition": "activated to habitual", "users": 43, "gap_points": 31.1},
    "action": "Users start and stop: 43 activated users are not habitual and the unit has no champion. Assign one (a hypothesis: the champion effect in this data is planted, not observed).",
    "unit_rank": 1,
    "users_to_gain": 23.6
}
```

The counts, the leak and the action in the example are the prototype's `step_04` output for Customer Service on the synthetic data. The date is week 12 of the synthetic window. The path and the policy version are illustrative.

OpenAPI spec lives at `docs/api/openapi.yaml` and is the source of truth for the console and the interlock clients.

See also: [README](./README.md), [PRD](./PRD.md), and the [clickable demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/21-adoptionpulse-ai-enablement-funnel/demo.html).
