# PRD: Concentration Register

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a technology risk or third-party risk review. It is not a record of a PRD landed at a named bank. The scenarios, the planted register and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Concentration Register: a command-line tool that reads a services file and a dependencies file, takes each cloud provider and each provider-region out in turn, and prints how many critical services are lost, next to a direct count |
| **Owner** | The technology risk or third-party risk analyst who keeps the register, with the infrastructure owner as co-owner of the dependency list and the standby claims |
| **Stage** | Portfolio prototype on synthetic data; nothing is hosted |
| **Primary user** | A technology risk or third-party risk analyst who keeps the register |
| **Secondary users** | The reviewer who has to say whether the critical estate is concentrated; the platform owner who vouches for the dependency list; internal audit |
| **Problem** | A register of critical services records where each one runs and who owns it. It does not say what happens when one cloud provider or one region fails. A count of services per provider understates a provider that sits under many others, and overstates one whose services have a standby elsewhere. In the planted register, 🟢 the process measures 0 of 12 outage scenarios while 4 of 12 truly lose more than 30% of critical services (`step_01_status_quo.py`). |
| **Solution** | Reads a services file (placement, criticality, standby) and an optional dependencies file (hard or soft). Runs one outage scenario per provider and per provider-region, follows hard dependencies and working standbys, and counts the critical services lost. Prints that count next to a direct count of services on the provider or region, flags scenarios above a chosen limit, and lists critical services with no placement. Exits 1 when a scenario is above the limit, 2 on malformed input; `--format json` for other tools. |
| **North-star metric** | Share of critical services whose placement, standby and hard dependencies are all in the register and covered by a scenario run in the current period. Target 🔴 100%. Today in this model: 🟢 3 of 25 critical services have no placement listed (`step_01_status_quo.py`). |
| **Measured metrics (synthetic)** | 🟢 Scenarios truly above the limit that the tool flags: 4 of 4, against 1 of 4 for a direct count; false flags: 0; lost pairs found: 64 of 74, all of them real (`step_04_with_register_model.py`, `step_02_direct_share.py`). |
| **Modeled metrics** | 🟡 Utility (4/4 − 1/4) × 4 = 3 over-limit scenarios found that a direct count would miss, assuming 4 truly over-limit scenarios in one register. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The world and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real register export and report the planted numbers and the real numbers apart. |
| **Risk #2** | The 30% limit is an assumption, and a decision near it can flip. 🟢 At a 40% limit 3 scenarios truly cross it and the tool flags 2 (`step_04_with_register_model.py`). Mitigation: the limit is a reviewed setting, and the sensitivity run from 20% to 50% goes with every result. |
| **Risk #3** | The tool understates by design when the register has gaps. 🟢 10 of the 74 lost pairs are missed (recall 86.5%): critical services with no placement, hard dependencies nobody listed, and a standby that does not take over (`step_04_with_register_model.py`). Mitigation: the output says the figures are a lower bound when a critical service has no placement, and the dependency list has a named owner. |
| **Out of scope** | Capacity of a standby, recovery time, availability zones, shared control planes, dependencies outside the register, any model call, hosting, discovery of placements from cloud accounts. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is scenarios, critical services or services, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Input validation** (empty, truncated, wrong-type, duplicate, half-filled placement or a hard-dependency cycle exits 2, never a traceback) | 64 services | 2 | 0.9 | 1 | 115.2 | Built in prototype |
| 2 | **Unplaced and shared-fate reporting** (a critical service with no placement, a standby in the primary's provider and region) | 25 critical services | 2 | 0.9 | 1 | 45.0 | Built in prototype |
| 3 | **Provider and region scenarios with a limit flag** (exit 1 above the limit, JSON output) | 12 scenarios | 3 | 0.9 | 1 | 32.4 | Built in prototype |
| 4 | **Hard-dependency and standby propagation** (a service is lost when its placement is hit and no second placement survives, or a hard dependency is lost) | 25 critical services | 3 | 0.8 | 2 | 30.0 | Built in prototype |
| 5 | **Limit as a reviewed setting** (the percent and who approved it, stored with each result) | 12 scenarios | 2 | 0.7 | 1 | 16.8 | Sequenced for v0.2 |
| 6 | **Tested-failover field** (a claimed standby is backed by a drill, not taken on trust) | 15 services with a standby | 3 | 0.6 | 2 | 13.5 | Sequenced for v0.2 |
| 7 | **Text output with escaped strings** (names and ids cleaned before they reach a log) | 12 scenarios | 1 | 0.9 | 1 | 10.8 | Built in prototype |
| 8 | **Result ledger** (limit, file hashes, scenarios, services lost; a diff between two runs) | 12 scenarios | 2 | 0.7 | 3 | 5.6 | Sequenced for v0.2 |
| 9 | **Standby capacity check** (does the standby have room for the load it takes over) | 15 services with a standby | 2 | 0.4 | 4 | 3.0 | Sequenced for v0.3 |
| 10 | **Placement discovery from cloud accounts** (fill the blanks the owner did not disclose) | 9 unplaced services | 2 | 0.5 | 6 | 1.5 | Queued |
| 11 | **Second source of dependency edges** (a trace or gateway export to find hard dependencies nobody listed) | 6 unlisted dependencies | 3 | 0.4 | 5 | 1.4 | Queued |
| 12 | **Availability zones and shared control planes** (a scenario smaller or wider than a region) | 12 scenarios | 2 | 0.3 | 5 | 1.4 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Concentration Register | What they fear |
| --- | --- | --- | --- |
| **Register owner (technology risk analyst)** | Owner | One command that turns the register into a per-scenario answer, and an output that says when the answer is a lower bound. | A clean answer that hides a missing dependency, and a register that is out of date by the time it is read. |
| **Third-party risk reviewer** | Approver of the limit | A flag at a stated limit, a way to see what the limit changes, and the services behind each flagged scenario. | Signing off a concentration view built on a limit nobody can defend. |
| **Head of infrastructure or cloud platform** | Consulted, owns the dependency list | The dependency list read as it is, with the standbys and shared-fate rows named so the fixes are obvious. | A finding built on a dependency they never confirmed, or on a standby that was never drilled. |
| **Service owner (internal or SaaS)** | Informed | A fair reading of their service, and a clear ask when their placement is blank. | Being named as the unplaced critical service with no way to supply the answer. |
| **Vendor manager** | Informed | Concentration on a provider tied back to the contracts and the exit plans. | Learning of a provider concentration from the tool before the vendor review. |
| **Security / CISO** | Approver | Nothing leaving the boundary, no cloud credentials in the tool, strings from input kept out of logs. | The register itself, a map of which critical services share a provider, ending up somewhere wide. |
| **Internal audit** | Reader | A result that re-runs from the same files and limit. | A limit changed between two runs with no record. |

---

## User stories (top 4)

1. **As the register owner**, I want each provider and region outage to show the critical services lost, counting hard dependencies and standbys, so I am not reading a count that hides what sits underneath.
2. **As a reviewer who signs the concentration view**, I want a flag at a stated limit and a plain note when the figure is a lower bound, so I know whether a clean answer is clean.
3. **As an infrastructure owner**, I want the tool to name the critical services with no placement and the standbys that share the primary's provider and region, so I know which rows to fix first.
4. **As internal audit**, I want a result that re-runs from the same files and limit, so I can reproduce a figure later.

---

## KPIs

**North star:** share of critical services whose placement, standby and hard dependencies are all in the register and covered by a scenario run in the current period. Target 🔴 100%.

**Inputs (leading):**
- Critical services with a provider and region listed (the prototype register has 🟢 3 of 25 critical services with neither, from `step_01_status_quo.py`).
- Critical services held on one placement with no standby (prototype: 🟢 10 of 25, `step_01_status_quo.py`).
- Hard dependencies listed, with a named owner of the list (prototype: 🟢 96 listed, `step_01_status_quo.py`; the generator also plants 6 more that are not listed, from `data/README.md`).
- Standby claims backed by a drill (not measured; the prototype has no such field).
- Age of the register export when the tool reads it (not measured).

**Outputs (lagging):** prototype baselines from the planted register.
- Over-limit scenarios flagged. 🟢 4 of 4 with the tool, against 1 of 4 for a direct count (`step_04_with_register_model.py`).
- False flags. 🟢 0 (`step_04_with_register_model.py`).
- Lost (scenario, service) pairs found. 🟢 64 of 74, all of them real (`step_04_with_register_model.py`).
- Known miss. 🟢 10 of 74 pairs, traced from 10 to 4 to 2 to 0 as the register is completed (`step_04_with_register_model.py`).
- Decisions overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the tool on one register export the owner can share, advisory only. Print the table and the sensitivity run; compare with what the owner already believes. |
| 1: Calibration | 4w | Fill the placement of every critical service. The platform owner reviews the hard-dependency list. Set the limit against the owner's own appetite and record who approved it. |
| 2: Provider scenarios enforced | 4w | A provider outage over the limit fails the weekly run and needs an answer from the register owner. |
| 3: Region scenarios and tested failover | 6w | Add the region scenarios to the enforced set and the tested-failover field, so a standby that has never been drilled is not counted as one. |
| 4: Ledger and export feed | 8w | Write a result record per run, add the diff between two runs, and read the register export from its system of record rather than a file. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **What limit should flag a scenario?** The guidance I read names no number, so 30% is mine. Recommendation: keep 30% to start, run the sensitivity from 20% to 50% on the real register, and let the reviewer pick the limit and sign it; 🟢 at 40% the tool flags 2 of the 3 scenarios that truly cross, so the choice is a policy call and not a detail (`step_04_with_register_model.py`).
2. **Who vouches for the hard-dependency list?** The largest known miss is a dependency nobody listed. Recommendation: the platform owner confirms the list each quarter, and an unlisted dependency found after an incident is a defect in the register, not in the tool.
3. **Should a claimed standby be counted on trust?** In the prototype a standby counts if it is in a different placement. Recommendation: until the tested-failover field exists, keep printing the direct count next to the effective one so the reviewer sees what the standbys are worth, and add the field in v0.2.
4. **Is a whole-region outage the right unit?** It is the unit the prototype uses, and it leaves out zones and a provider-wide control-plane event. Recommendation: keep the whole-provider and whole-region scenarios as the first view and add smaller and wider ones after a pilot shows which questions reviewers ask.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, run on a schedule or after an export.** The tool is stateless: it reads two files and a limit and returns a table and an exit code. Production adds a reviewed limit config, an export feed and a result ledger, all designed and none built.
- **Never silent.** A missing, empty or malformed file, or a hard-dependency cycle, exits 2. A critical service with no placement is named, and the output says the figures are a lower bound. A run with no dependencies file says no dependency was followed.
- **Strings from input are data.** Names and ids are escaped before they reach a log, so a hostile service name cannot forge a line.
- **Changes to a rule are changes to a number.** A golden test pins the planted-register numbers, so a rule change that moves the flagged count shows in the diff.

**What is next.** Run it on one register the owner is allowed to share; add a field for tested failover so a claimed standby is not taken on trust; read the 2021 proposal and compare its concentration language with the final text.

**What would have to be true before a pilot.**
- Every critical service has a provider and a region, or is named as unplaced.
- The platform owner will vouch for the hard-dependency list and the standby claims.
- One real register export can be shared, so the limit is set against a real estate and not mine.
- The reviewer agrees what limit flags a scenario and who must answer a flag.
- The team accepts that the output is a lower bound and reads the unplaced line first.

---

*This PRD names [18 VendorLens](../18-vendorlens-ai-vendor-due-diligence/), [65 Failover Scorecard](../65-failover-scorecard/) and [44 Inventory Check](../44-inventory-check/) as designed interlocks (🔴 designed, none built). No file from those projects is read here.*
