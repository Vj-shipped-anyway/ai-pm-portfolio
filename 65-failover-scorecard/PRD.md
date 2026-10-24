# PRD: Failover Scorecard

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an operational-resilience review. It is not a record of a PRD landed at a named bank. The rule, the windows, the planted service map and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Failover Scorecard (KillSwitch extension): a command-line scorecard that reads a service map and a drill log and prints one status per service, READY or the single reason it is not, with a decision on the tier-1 services |
| **Owner** | The person who owns operational resilience for a set of services, with each service owner as co-owner of that service's drill record |
| **Stage** | Portfolio prototype on synthetic data; not deployed, and no CI Action is staged |
| **Primary user** | The person who owns operational resilience for a set of services, and the engineer who has to answer "which of these would we bet on?" before an audit or a real event |
| **Secondary users** | The service owner who receives a status and a reason; the engineer who runs the drills; second-line operational risk; internal audit |
| **Problem** | A bank can list the services that are supposed to come back in a second region. It is harder to say which of them have shown it. A plan on paper, a drill that passed two years ago, a drill that exercised one availability zone, or a service whose own drill passed while the service it needs was never tested all look the same in a status column. In the planted map, 🟢 owners state a plan for 42 of 48 services and only 16 of those 42 would recover (`step_01_self_reported.py`), and reading a service as green when its latest drill passed leaves 20 of 36 green services that would not recover (`step_02_last_drill_passed.py`). |
| **Solution** | Reads a service map and a drill log. Applies one readiness rule per service: a live drill of the right scenario, passed, inside the service's own recovery target, against the current secondary region and config version, inside the window for its tier, with every declared dependency also ready. Prints a status per service (READY, NOT_REQUIRED, NO_PATH, UNTESTED, FAILED, SLOW, CHANGED, STALE, DEPENDENCY) with the reason in one line, a count per domain, and a decision for the tier-1 services. Exits 1 when a tier-1 service has no tested way back, 2 on bad input or when it checked nothing. |
| **North-star metric** | Share of tier-1 services whose status rests on a live drill row inside its window, with a named owner for every status that is not READY. Target 🔴 100%. Today in this model: 🟢 7 of 18 tier-1 services have a tested way back (`step_04_with_scorecard.py`). |
| **Measured metrics (synthetic)** | 🟢 25 of 28 not-ready services flagged and 0 of 16 ready ones; 4 of 4 accepted gaps kept apart from real ones; 45 of 48 statuses match the planted truth (`step_04_with_scorecard.py`). |
| **Modeled metrics** | 🟡 Utility (20/28 − 3/28) × 14 = 8.5 services that would not recover and show as having a tested way back are caught on a map that holds 14 of them. 🟡 The windows (180, 365 and 540 days by tier) are my assumption. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rule share an author, so the numbers are a ceiling. Mitigation: run it on one real service map and drill log, and report the planted numbers and the real numbers apart. |
| **Risk #2** | A drill row is taken at its word. The rule cannot tell a rehearsed drill from a real one, or when the recovery clock started. Mitigation: add a drill owner and an evidence link to each row so a reviewer can open the record behind a READY (sequenced for v0.2). |
| **Risk #3** | The dependency check is only as good as the map. 🟢 3 services score READY and would not recover because a dependency is not listed (`step_04_with_scorecard.py`). Mitigation: compare declared edges with a call-graph export (queued); until then, read the READY count as a ceiling. |
| **Out of scope** | Data-loss targets, partial failover, capacity in the secondary region, cost, dependencies that are not declared, reading runbooks, any model call, hosting, a staged CI Action. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is services or drill rows, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Live drill of the right scenario, latest one passed** (tabletop and availability-zone drills do not count) | 48 services | 3 | 0.9 | 1 | 129.6 | Built in prototype |
| 2 | **Region and config version check** (the drill must match today's secondary region and config) | 48 services | 3 | 0.8 | 1 | 115.2 | Built in prototype |
| 3 | **Input validation** (empty, truncated, wrong-type, duplicate or unknown-reference input exits 2, never a traceback) | 48 services | 2 | 0.9 | 1 | 86.4 | Built in prototype |
| 4 | **Dependency propagation** (a service is READY only if its declared dependencies are) | 48 services | 2 | 0.8 | 1 | 76.8 | Built in prototype |
| 5 | **Recovery-time check against the service's own target** | 48 services | 2 | 0.8 | 1 | 76.8 | Built in prototype |
| 6 | **Window by tier and the accepted-risk rule for tier 3** | 48 services | 2 | 0.7 | 1 | 67.2 | Built in prototype |
| 7 | **CI output** (text and GitHub annotations, `--fail-on` scopes, escaped strings) | 48 services | 2 | 0.9 | 2 | 43.2 | Built in prototype |
| 8 | **Drill owner and evidence link on each drill row** | 54 drill rows | 2 | 0.6 | 2 | 32.4 | Sequenced for v0.2 |
| 9 | **Scorecard record per run** (policy, input hashes, statuses) | 48 services | 2 | 0.7 | 4 | 16.8 | Sequenced for v0.2 |
| 10 | **Recovery data-loss target column** | 48 services | 2 | 0.5 | 3 | 16.0 | Sequenced for v0.2 |
| 11 | **Compare declared dependencies with a call-graph export** | 48 services | 3 | 0.4 | 5 | 11.5 | Queued |
| 12 | **Windows set per tier from the owners' own drill cadence** (a reviewed policy file) | 18 services | 2 | 0.6 | 2 | 10.8 | Sequenced for v0.3 |

---

## Stakeholder map

| Stakeholder | Role | What they want from Failover Scorecard | What they fear |
| --- | --- | --- | --- |
| **Operational resilience owner** | Owner | A status per service with a reason they can defend, and a tier-1 decision they can put in front of a committee. | A READY count read as a promise, then an outage. |
| **Service owner** | Receives statuses | A reason that says what to fix: rerun the drill on today's config, test the service it needs. | Being scored for a gap in someone else's service. |
| **Platform reliability engineer** | Runs the drills | Drill rows read as they are, with no new form, and a drill schedule driven by what is stale or untested. | A scorecard that asks for drills faster than the platform can run them. |
| **Second-line operational risk** | Approver of windows and accepted gaps | Windows set on purpose, and an accepted gap shown apart from a failure. | A tier-3 acceptance stretched to hide a tier-1 gap. |
| **Shared-platform owner** | Consulted | One root cause shown once, with the chain that ends at it. | One failed drill turning every dependent service red with no explanation. |
| **Security / CISO** | Approver | Nothing leaving the boundary, strings from input kept out of logs, no credentials in the job. | Another job reading inventory and drill evidence with broad access. |
| **Internal audit** | Reader | A path from a status to the drill row and the policy it used. | Windows changed silently between two runs. |

---

## User stories (top 4)

1. **As the operational resilience owner**, I want a service to count as recoverable only on a live drill of the right scenario, so a plan on paper or a tabletop does not read as proof.
2. **As a service owner**, I want each status to say what it saw and what to do next, so I can rerun the right drill without a meeting.
3. **As second-line operational risk**, I want an owner-accepted gap shown as NOT_REQUIRED and kept apart from a failure, so I can review the acceptance itself.
4. **As internal audit**, I want each status tied to the drill row, the date it was judged against and the windows it used, so I can reproduce it later.

---

## KPIs

**North star:** share of tier-1 services whose status rests on a live drill row inside its window, with a named owner for every status that is not READY. Target 🔴 100%.

**Inputs (leading):**
- Services with a tier, a secondary region, a failover mode, a recovery target, a config version and declared hard dependencies recorded (the prototype map has 🟢 48 services: 18 tier 1, 24 tier 2 and 6 tier 3, from `data/README.md`).
- Drill rows that record the region failed over to and the config version they ran on (the prototype log has 🟢 54 drill rows: 51 live and 3 tabletop, from `data/README.md`).
- Drill rows with an owner and an evidence link (target: every live row; not in the prototype).
- Windows set against each tier's own drill cadence (target: every tier; the prototype's are assumptions).

**Outputs (lagging):** prototype baselines from the planted set.
- Not-ready services flagged. 🟢 25 of 28 (`step_04_with_scorecard.py`). Reading a service as green when its latest drill passed leaves 🟢 20 of 36 green services that would not recover (`step_02_last_drill_passed.py`).
- Ready services flagged. 🟢 0 of 16 (`step_04_with_scorecard.py`).
- Accepted gaps kept apart from real ones. 🟢 4 of 4 (`step_04_with_scorecard.py`).
- Status matches the planted truth. 🟢 45 of 48 (`step_04_with_scorecard.py`).
- Tier-1 services with a tested way back. 🟢 7 of 18, and 2 of those 7 would not recover (`step_04_with_scorecard.py`).
- Known miss. 🟢 3 services pass on an undeclared dependency (`step_04_with_scorecard.py`).
- Statuses overturned by a later real test: not measured; the planted set has no live test.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the scorecard on one real service map and drill-register export with `--fail-on never`. Print the statuses, fail nothing, and compare with what the owners say. |
| 1: Calibration | 4w | Fix drill rows that lack the region or config version. Set the three windows against each tier's own cadence. Add the hard dependencies the owners know of. |
| 2: Tier 1 enforced | 4w | Fail the pipeline step when a tier-1 service has no tested way back. Statuses go to the service owners with the reason. |
| 3: All tiers | 6w | Widen to every tier with `--fail-on any`. Tier-3 acceptances go through second-line review. |
| 4: Edges and record | 8w | Compare declared dependencies with a call-graph export. Write a scorecard record per run and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **How old may a passing drill be?** The windows (180, 365 and 540 days by tier) are my assumption. 🟡 Moving the tier-1 window to 90, 180 and 365 days gives 6, 7 and 8 of 18 tier-1 services READY (`step_04_with_scorecard.py`). Recommendation: start at 180 days for tier 1, then set each tier from the real drill cadence and what second-line risk will accept.
2. **Who may accept having no way back?** The rule honors an acceptance for tier 3 only. Recommendation: keep it to tier 3, require second-line approval, and add an expiry date to the acceptance (not built).
3. **Should one failed dependency turn every dependent service red?** The rule does, and names where the chain ends. Recommendation: keep it, and show the root cause once in the report.
4. **Can a real regional event count as a live drill?** The rule cannot tell a drill from an event. Recommendation: accept an event only as a row with the same fields and a named reviewer, after the drill owner and evidence link exist.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, run on a schedule.** The scorecard is stateless: it reads two files and a date and returns statuses. Production adds a reviewed policy file, a scorecard record and telemetry, all designed and none built.
- **Never silent.** A missing, empty or malformed input exits 2. A service with no live drill is UNTESTED, not READY, and a map with no tier-1 service is an error because nothing was checked.
- **Strings from input are data.** Text output and annotations strip or escape control characters, so a hostile service name cannot forge a line or a workflow command.
- **Changes to a window are changes to a number.** A golden test pins the planted-set numbers, so a policy change that moves the flagged count shows in the diff.

**What is next.** Run it on one real service map whose owner can share it; add the drill owner and evidence link; compare declared dependencies with a call-graph export.

**What would have to be true before a pilot.**
- The service map carries a tier, a secondary region, a failover mode, a recovery target, a config version and the hard dependencies the owner knows.
- Drill rows record the region failed over to and the config version they ran on.
- A named person owns the windows and the acceptance of gaps.
- One real export can be shared, so the windows are set against real cadence and not mine.
- The team agrees which scope fails the step.

---

*This PRD names [25 KillSwitch](../25-killswitch-ai-fallback-drills/), [54 Runbook Dry-run](../54-runbook-dryrun/), [19 IncidentLedger](../19-incidentledger-ai-incident-response/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The prototype shares no code or data with 25.*
