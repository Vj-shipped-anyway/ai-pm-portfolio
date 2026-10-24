# PRD: Payment Repair

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a payments-operations review. It is not a record of a PRD landed at a named bank. The tiers, the planted message set and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and the approver in every run is a scripted test double.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Payment Repair: a command-line repair tool for pacs.008-style payment messages. It finds required fields that are missing, blank, placeholders or malformed, fills what a bank table can supply, holds what decides where the money goes until a person approves that exact change, and returns the rest untouched |
| **Owner** | The payments-operations lead who owns the repair queue, with the reviewer role as co-owner of the tiers |
| **Stage** | Portfolio prototype on synthetic data (500 messages, 374 damaged fields) |
| **Primary user** | The payments-operations lead who owns the repair queue |
| **Secondary users** | The reviewer who approves a repair before it goes out; the originator who gets a message back; the reference-data owner; internal audit |
| **Problem** | A payment message with a missing or unusable required field is rejected at the next hop and lands in a repair queue, where a person fixes it by hand. A script that fills every empty field clears the queue fast and writes wrong values into messages that then move money: a currency from the wrong account, the first of two BICs, a beneficiary name from a stale payee list. In the planted set, 🟢 the next hop rejects 319 of 500 messages and a fill-every-field script releases 126 of 500 with a wrong or unusable required value. |
| **Solution** | (1) Finds the required fields that are missing, blank, placeholders or malformed; optional fields are never touched. (2) Proposes a value only from a table the policy allows, and records the source. (3) Applies it without a person only for fields that do not change where the money goes (tier AUTO). (4) Holds a plan that changes routing or the payment's identity until an approval carries the digest of that exact plan, from an active person with the reviewer role who did not enter the order (tier APPROVAL). (5) Returns the message whole, with the reasons, when any field has no allowed source (tier NEVER): amount, currency, creditor name, account numbers. (6) Writes one audit row per applied change and exits non-zero when something is held or returned. |
| **North-star metric** | Share of released messages that carry a correct required value with an audit row for every change. Target 🔴 100%. Prototype today: 21 of 371 released messages carry a wrong or unusable value. |
| **Measured metrics (synthetic)** | 🟢 Routes match the planted intent on 488 of 500; 90 of 90 repairs made without a person equal the true value; 766 of 766 bad approvals blocked; 129 of 129 returned messages left untouched; 21 of 371 released messages with a wrong or unusable value, against 126 of 500 for the basic script (`step_04_with_repair_tool.py`, `step_03_deficiencies_exposed.py`). |
| **Modeled metrics** | 🟡 Utility (126/500 − 21/500) × 1,000 = 210 messages a year not released with a wrong or unusable required value, assuming 1,000 messages enter the tool each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted data and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real queue export and report the planted numbers and the real numbers apart. |
| **Risk #2** | The approver in the run is a test double and an approval is a CSV row, not an identity. 🟢 9 wrong proposals reach the gate and 9 are applied (`step_04_with_repair_tool.py`). Mitigation: shadow run with a real reviewer, count what the reviewer rejects, and take approvals only from an identity system before enforcement. |
| **Risk #3** | The directory snapshot can be stale in ways the tool cannot see, and a well-formed BIC from another bank passes. 🟢 12 of 12 planted pass (`step_04_with_repair_tool.py`). Mitigation: a BIC-to-IBAN consistency check and a dated reference table, both are in the backlog below. |
| **Out of scope** | Validation against the ISO 20022 schema; structured postal addresses; more than one transaction per message; sanctions screening; a real approval workflow or identity check; any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is messages, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Damaged-field detection** (missing, blank, placeholder, malformed; optional fields untouched) | 500 messages | 2 | 0.9 | 1 | 900.0 | Built in prototype |
| 2 | **Tier policy and whole-message refusal** (AUTO, APPROVAL, NEVER; one refusal returns the message untouched) | 500 messages | 3 | 0.9 | 2 | 675.0 | Built in prototype |
| 3 | **Input validation and safe output** (bad input exits 2; control characters escaped; formula cells neutralized) | 500 messages | 2 | 0.9 | 2 | 450.0 | Built in prototype |
| 4 | **Digest-bound approval gate** (registry, reviewer role, four-eyes, changed message voids the approval) | 500 messages | 3 | 0.8 | 3 | 400.0 | Built in prototype |
| 5 | **Derivation from allowed tables** (exactly one active row; source recorded) | 500 messages | 2 | 0.7 | 2 | 350.0 | Built in prototype |
| 6 | **BIC-to-IBAN consistency check** (catches a well-formed BIC from another bank) | 500 messages | 2 | 0.5 | 2 | 250.0 | Sequenced for v0.2 |
| 7 | **Audit record per change** (old and new value, source, tier, approver, digest) | 500 messages | 2 | 0.7 | 3 | 233.3 | Built in prototype |
| 8 | **Dated reference tables with an age alert** | 500 messages | 2 | 0.5 | 3 | 166.7 | Sequenced for v0.2 |
| 9 | **Shadow run on one real queue with a real reviewer** (measure what the reviewer rejects) | 125 messages | 3 | 0.6 | 2 | 112.5 | Sequenced for v0.2 |
| 10 | **Identity-backed approvals** (signed workflow step instead of a CSV row) | 125 messages | 3 | 0.8 | 3 | 100.0 | Sequenced for v0.2 |
| 11 | **Multi-transaction messages and XML input** | 500 messages | 2 | 0.4 | 6 | 66.7 | Queued |
| 12 | **Reviewer evidence view** (source and evidence beside each proposed value) | 125 messages | 2 | 0.6 | 4 | 37.5 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Payment Repair | What they fear |
| --- | --- | --- | --- |
| **Payments-operations lead** | Owner | A shorter queue and a reason on every message that stays. | A tool that clears the queue by guessing and puts the wrong value on a payment. |
| **Reviewer** | Approver of held plans | The proposed value, where it came from and the evidence, in one place. | Becoming a rubber stamp, or being blamed for a value the table got wrong. |
| **Originator** | Consulted | A message that comes back untouched, with a reason they can act on. | A returned message that has already been changed. |
| **Reference-data owner** | Informed | Their directory and master used as given, with the age shown. | A stale row blamed on the tool. |
| **Payments technology** | Consulted | A tool that reads the export as it is, with exit codes a job can use. | A new component that sits in the release path and fails silently. |
| **Security / CISO** | Approver | No vendor key in the path, nothing leaving the boundary, strings from messages kept out of logs and sheets. | Another tool holding credentials, or an approval anyone can type. |
| **Internal audit** | Reader | A path from every changed field to its source, tier and approver. | A repair with no record of who agreed to it. |

---

## User stories (top 4)

1. **As the payments-operations lead**, I want fields that do not move money repaired without a person, so the queue shrinks without someone touching each message.
2. **As a reviewer**, I want each held plan to show the proposed value, its source and its evidence, and a digest that ties my approval to that exact change, so I approve what I read and nothing else.
3. **As an originator**, I want a returned message to come back untouched with the reason, so I supply the real amount, currency or name instead of a guess.
4. **As internal audit**, I want one record for every field the tool changed, with its source, tier and approver, so I can trace any value on a released message.

---

## KPIs

**North star:** share of released messages that carry a correct required value with an audit row for every change. Target 🔴 100%. Prototype baseline: 21 of 371 released messages carry a wrong or unusable value.

**Inputs (leading):**
- Share of reference rows that carry an as-of date (target: every table; the prototype tables have none).
- Approvers in the registry with a role and an active flag (target: every approver is a named person).
- Messages where the person who entered the order is known (target: every order).
- Hard negatives left alone: 🟢 30 of 30 with missing optional fields, 8 of 8 names containing "unknown" or "N/A", 6 of 6 eight-character BICs (`step_04_with_repair_tool.py`).

**Outputs (lagging):** prototype baselines from the planted set.
- Routes match the planted intent. 🟢 488 of 500 (`step_04_with_repair_tool.py`).
- Repairs without a person equal the true value. 🟢 90 of 90 (`step_04_with_repair_tool.py`).
- Bad approvals blocked. 🟢 766 of 766, and 125 of 125 valid approvals applied (`step_04_with_repair_tool.py`).
- Returned messages left untouched. 🟢 129 of 129 (`step_04_with_repair_tool.py`).
- Released with a wrong or unusable required value. 🟢 21 of 371, against 126 of 500 for the basic script (`step_04_with_repair_tool.py`, `step_03_deficiencies_exposed.py`).
- Audit rows. 🟢 225 rows for 225 fields changed, none without a source (`step_04_with_repair_tool.py`).
- Known misses. 🟢 12 well-formed wrong BICs pass; 9 wrong proposals are applied (`step_04_with_repair_tool.py`).
- Reviewer catch rate on wrong proposals, time per held plan, wrong values found after release: not measured.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the tool on one real queue export with `--fail-on never`. Print the routes, change nothing, and compare with what the team did by hand. |
| 1: Calibration | 4w | Read the HOLD and RETURN reasons with a real reviewer. Count rejections among the proposals. Date the reference tables. |
| 2: AUTO enforced | 4w | Release the AUTO repairs and PASS messages. HOLD and RETURN go to people as they do today. |
| 3: APPROVAL enforced | 8w | Take approvals only from an identity system or a signed workflow step. Add the BIC-to-IBAN consistency check. |
| 4: Audit store and wider input | 8w | Write the audit rows to a store with a retention lock. Add multi-transaction messages. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should the creditor country, taken from the IBAN prefix, sit behind a person?** In the prototype it does; that is my policy, not a measurement. 🟢 4 wrong country proposals are applied where the creditor lives outside the IBAN country (`step_04_with_repair_tool.py`). Recommendation: keep it in APPROVAL until the pilot shows how often a reviewer rejects it.
2. **Which fields are required?** The list is the policy table, not a reading of the ISO 20022 text, which I could not read. Recommendation: have the standards owner confirm the list against the bank's own usage guidelines before it is treated as more than an assumption.
3. **Who may approve?** In the prototype: an active person with the reviewer role who did not enter the order. Recommendation: keep that rule and take the approval from an identity system, so a row cannot be typed.
4. **How old may a directory snapshot be?** The tool reads tables as given. Recommendation: stamp each table with an as-of date and let the pilot set the age that raises an alert.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One batch process.** The tool is stateless: it reads a message file, four tables and optional approvals and returns a route per message. Production adds identity-backed approvals, an audit store and dated tables, all designed and none built.
- **Never silent.** Malformed input exits 2. A field with no allowed source returns the whole message untouched. An approval that does not count leaves the message on HOLD with the reason.
- **Strings from input are data.** Output escapes control characters and audit cells neutralize formulas, so a hostile message id or old value cannot forge a line or run in a sheet.
- **Changes to a tier are changes to a number.** A golden test pins the planted-set numbers, so a tier change that moves a count shows in the diff.

**What is next.** Run it on one real queue export the owner is allowed to share, with a real reviewer, and count what the reviewer catches among the proposals that are wrong; add a BIC-to-IBAN consistency check; read the ISO 20022 usage rules before the required-field list is treated as more than an assumption.

**What would have to be true before a pilot.**
- A named reviewer group exists in the approver registry, and the person who entered each order is recorded.
- The reference tables carry an as-of date, or the pilot accepts the stale-row risk in writing.
- One real queue export can be shared, so the tiers are set against a real mix and not mine.
- Approvals come from an identity system or a signed workflow step, not a file.
- The team agrees which route fails the job.

---

*This PRD names [27 AgentKit](../27-agentkit-reference-agent-and-playbook/), [08 OversightOps](../08-oversightops-hitl-workflow/), [34 audit-chain](../34-audit-chain/) and [30 payment-mandate-check](../30-payment-mandate-check/) as designed interlocks (🔴 designed, none built). The code here imports nothing from them.*
