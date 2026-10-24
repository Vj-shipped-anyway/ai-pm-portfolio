# Architecture: Payment Repair

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/payment_repair.py`, that finds damaged required fields in pacs.008-style messages, proposes values only from sources the policy allows, applies the ones that do not move money, holds the rest for an approval bound to a digest of the exact plan, and returns a message untouched when a field has no allowed source. It runs here over 500 synthetic messages. Nothing below is claimed as deployed or load-tested; a design target says so.

GCP is primary; AWS and Azure sit beside it.

![Payment Repair flow](./assets/payment-repair-flow.svg)

---

## 1. Logical architecture

Payment Repair sits between a repair queue and the next hop: messages, four tables and optional approvals in, a route per message out. It makes no model call; every step is a plain rule.

Eight components: five decide the outcome, three support, report or record.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `pr-ingest` | Loads messages, tables and approvals; rejects malformed input | Python 3.9+, standard library. Prototype: `load_messages`, `check_messages`, `load_refs`, `load_approvals` | Yes, by refusing: exit 2 | No |
| `pr-policy` | Tier per required field (AUTO, APPROVAL, NEVER), shape checks, reviewer role | Reviewed config (design). Prototype: `POLICY`, `NEVER_REASON`, `REVIEWER_ROLE` | Yes, config | Stateful, in git |
| `pr-detect` | Marks each required field missing, blank, placeholder or malformed; optional fields untouched | Python. Prototype: `classify`, `find_defects` | Yes | No |
| `pr-derive` | Proposes a value only from an allowed table, with its source; refuses unless exactly one usable value | Python. Prototype: `propose`, `make_plan` | Yes | No |
| `pr-gate` | Computes the plan digest, checks each approval against the registry, picks the route, applies edits | Python. Prototype: `plan_digest`, `judge_approval`, `repair_message`, `repair_all` | Yes | No |
| `pr-report` | Prints routes, reasons and digest; escapes strings and neutralizes formulas | Python. Prototype: `render`, `clean`, `csv_safe` | No | No |
| `pr-audit` | One row per applied change | Prototype: `audit_rows`, `write_audit`. Design: PostgreSQL plus object storage with a retention lock | No | Stateful (design) |
| `pr-approvals` | Takes an approval from an identity system or a signed workflow step | Design only. Prototype analog: the `--approvals` CSV and `approvers.csv` | No: the gate judges it | Stateful (design) |

**What decides the outcome.** The input check, the policy, the finder, the derivation and the gate; the rest carry or record it. The gate does not judge whether a proposed value is right: it checks that the table gave exactly one, that the tier allows it and that a qualified person approved that exact plan.

**Repo structure** (production shape):

```
payment-repair/
├── repair/     # ingest, policy, detect, derive, gate, report
├── policy/     # field tiers, changed by pull request
├── approvals/  # approval intake from the identity system (design)
├── audit/      # audit row writer
├── infra/      # terraform for gcp, aws, azure
├── docs/runbooks/
└── tests/      # unit, golden (planted-set numbers), hostile strings
```

---

## 2. Physical and deployment architecture

One short-lived batch process reads a queue export and the tables. No server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Repair process | Cloud Run job | ECS Fargate task | Container Apps job | Stateless, one pass per export |
| Messages and tables | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Keeps the bytes a plan was drawn from |
| `pr-approvals` | Cloud Run service behind the bank's identity provider | ECS service, same | Container Apps service, same | An approval must come from an identity, not a file |
| `pr-audit` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The tool must never silently pass and never silently repair. Malformed input ends the run with exit 2. A field with no allowed source gets no best guess: the whole message returns untouched. An approval that does not count leaves the message on HOLD with the reason.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Message file empty, not a list, a non-string value, no `GrpHdr.MsgId` or a duplicate id | Exit 2, nothing released | P2 if repeated, else P3 |
| A table or the approvals file missing, a missing column, a bad `decision` | Exit 2 with the reason | P3 |
| An empty table, no or two active rows, no order, a joint or closed account, an unusable table value | Field refused, message returns whole with the reason; an empty table also prints a note | P4 digest |
| Approval for another plan, an agent, an inactive person, no reviewer role, the order's own initiator | Message stays HOLD with the reason | P3 on a spike |
| Output or audit file cannot be written | Exit 2; the audit is written before the released file | P2 |

**Latency.** I have not timed the prototype. 🔴 Design target: a route within 5 seconds of a message landing in the queue.

---

## 3. Data architecture

| Entity | Key | Real columns in the prototype |
| --- | --- | --- |
| Message | `GrpHdr.MsgId` | `data/messages.json`: 500 messages, each mapping a pacs.008-named dotted path to a string |
| Directory row | `country`, `bank_code` | `bic_directory.csv`: `country`, `bank_code`, `bic`, `status` |
| Customer row | `iban` | `customer_master.csv`: `iban`, `customer_id`, `name`, `account_ccy`, `status` |
| Payment order | `end_to_end_id` | `payment_orders.csv`: `end_to_end_id`, `uetr`, `charge_bearer`, `initiator_id` |
| Approver | `approver_id` | `approvers.csv`: `approver_id`, `kind`, `role`, `active` |
| Approval | `msg_id`, `plan_digest` | CSV: `msg_id`, `plan_digest`, `approver_id`, `decision` |
| Audit row | `msg_id`, `path` | `step_04_audit.csv`: `msg_id`, `path`, `kind`, `old`, `new`, `source`, `tier`, `approved_by`, `plan_digest` |

**Retention** is a design choice, not a measurement; confirm it against the bank's record-retention schedule. 🔴 Design default: audit rows and plan digests 7 years, in PostgreSQL archived to object storage with a retention lock; the input file and table snapshots a plan used, the same period, in versioned storage.

**Lineage.** A change traces back in three hops. The audit row names the message, field, source table and plan digest. The digest covers the message as it stood and every proposed change, so the versioned inputs can be checked against it. The rules are deterministic, so re-running `repair_message` on the same inputs reproduces the plan. Tables carry no as-of date, which weakens the second hop; the design adds one.

**Deliberately not stored.** Anything beyond the paths the tool reads. `beneficiary_book.csv` is read only by the basic script in step 2, never by the tool: a saved payee list can be stale.

---

## 4. Security architecture

**Identity and roles.** The process runs under the platform's workload identity with no user account. Approvals come from people. `pr:runner` reads inputs and writes released messages and audit rows. `pr:reviewer` approves or rejects one plan, never for an order they entered (the `payments_reviewer` role in the registry). `pr:auditor` reads audit rows and config history. `pr:admin` manages roles, buckets and the audit store.

**Secrets.** None. The tool calls no model, so no vendor key is in its path.

**Data classification and what leaves the boundary.** Payment messages carry account numbers and names; treat them as restricted. In the prototype everything is synthetic and nothing leaves the machine. In the design three things leave the job: the released messages, the audit rows and an approval request.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string echoed into output or a spreadsheet | A message id holding a newline and a fake `REPAIRED` line, or an old value starting with `=` | `clean` writes control characters as escapes; `csv_safe` neutralizes formulas. `tests/test_cli.py` covers both |
| A forged or replayed approval | A digest copied from another message, or reused after the message changed | The approval must carry this plan's digest; a changed message changes it. `tests/test_repair.py` covers both |
| An approver who should not count | An agent, a person who left, no reviewer role, the order's initiator | `judge_approval` reads a registry field per check. 🟢 766 of 766 bad approvals blocked (`step_04_with_repair_tool.py`) |
| A stale or wrong table row | The directory still lists an old BIC as active | The design stamps tables with an as-of date. The prototype cannot see it: 🟢 9 wrong proposals applied (`step_04_with_repair_tool.py`) |

---

## 5. Operational architecture

**SLIs.** Routes per field per week (prototype baseline, run A: 🟢 156 pass, 90 repaired without a person, 125 hold for approval, 129 return, `step_04_with_repair_tool.py`); input rejections; invalid approvals; HOLD age; share of held plans rejected; table age.

**SLOs (all 🔴 design targets, none measured).**
- A route within 5 seconds of a message landing in the queue.
- Every applied change has an audit row before release (100 percent).
- Every HOLD read by a named reviewer within one business day (planning estimate).
- No approval accepted from outside the identity system.

**Alerts.** P2: repeated input rejections, or the audit store down. P3: a spike in invalid approvals, a HOLD older than a business day, or an old table. P4: a daily digest of RETURN reasons.

**Runbooks** (in `docs/runbooks/`): `held-plan.md` (read the evidence, approve, reject or send back); `returned-message.md` (what the originator fixes); `stale-directory.md` (refresh, re-run held plans); `changing-a-tier.md` (propose, re-run the planted set, approve).

**On-call and ownership.** The payments-operations lead owns the queue and runbooks; the reviewer role owns approvals. Nobody is paged for a HOLD or a RETURN.

**Change control.** Tiers and shape rules are versioned in the repo. Moving a field from APPROVAL to AUTO needs a proposer, a different approver and a re-run of the planted set against `tests/test_golden.py`, so a change that moves a count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites two things. Governor Waller's speech ["Payments in the Age of AI Agents"](https://www.federalreserve.gov/newsevents/speech/waller20260928a.htm), Sibos 2026, which I read on 2026-10-23, covers AI in payments, including agents that shop and pay for a buyer, and does not mention ISO 20022 or message repair; I borrowed the framing only. The pacs.008 element names label the paths; I could not read the standard (the ISO site returned HTTP 403 on 2026-10-23), so I cite nothing from it. From [27 AgentKit](../27-agentkit-reference-agent-and-playbook/) I took the digest-bound approval, an approver who is not the proposer, and an audit record.

- **What the design does.** It keeps the fields that decide where money goes behind a named person and a plan digest, and refuses the fields no table may supply.
- **What it does not claim.** It is not validated against the ISO 20022 schema, the required-field list is my policy table, and it holds no certification. It makes no claim of conformity to the speech or to any standard, and I have not read or mapped any other source.

---

## 7. What is deliberately not here

- **A check that a proposed value is right.** 🟢 12 well-formed creditor BICs from another bank pass, and 9 wrong proposals are approved (`step_04_with_repair_tool.py`). The tool checks presence and shape, not consistency between the BIC and the IBAN's bank code.
- **A real approval identity.** An approval here is a CSV row, which the prototype cannot tell from a typed line; the design takes approvals from the identity system. A real reviewer's catch rate is not measured.
- **Schema validation.** The set is pacs.008-style; required fields are the policy table.
- **More than one transaction per message, XML, address checks, IBAN check digits, sanctions screening.**
- **A dated reference table or a wider placeholder list.** Tables are read as given; the list is short and English only.
- **Hosting, queue integration, a model call.**

---

## Appendix: sample contract

The call is the prototype's own; the `--demo` output is in the README.

```bash
python3 payment_repair.py check messages.json --refs refdir --approvals approvals.csv \
    --fail-on return --out released.json --audit-out audit.csv
```

Approvals file, one row per decision on one plan: `msg_id,plan_digest,approver_id,decision`. Exit status: 0 below `--fail-on`, 1 at or above it, 2 for bad input.
