# PRD: Payment Mandate Check

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a payments release review for an agent-initiated payment feature. It is not a record of a PRD landed at a named bank. The mandates, the planted instruction set, the rules and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Payment Mandate Check: a command-line tool that compares each payment instruction an agent submits with the customer's mandate and prints RELEASE, HOLD or REJECT before anything is released, with a hash-chained audit record |
| **Owner** | The engineer who owns the payment gateway an agent submits to, with the person who approves holds as co-owner of the thresholds |
| **Stage** | Portfolio prototype on synthetic data |
| **Primary user** | The engineer who owns the payment gateway an agent submits to |
| **Secondary users** | The person who approves what the gateway holds for review; the owner of the agent product; fraud and dispute operations; internal audit |
| **Problem** | A customer lets an agent pay on their behalf, inside limits: these payees, up to this amount, until this date. The credential the agent signs in with says it may submit payments. It does not say how much, to whom, or until when. Without a check at the point of release, the limits live in a document and the agent's own prompt. In the planted set, 🟢 a gateway with no mandate check releases 475 of 475 instructions, 164 of them forbidden by the mandate and 62 that needed a person (`step_01_no_mandate_check.py`). |
| **Solution** | Reads a mandate file (limits, payees pinned to an account, rails, categories, validity, revocation) and a batch of instructions. Decides each instruction in the order the gateway received it: RELEASE, HOLD for a person, or REJECT, with a reason code and a plain sentence for each reason. Keeps a ledger of what was released, for the daily limit and for repeated instructions. Writes one hash-chained audit record per decision and verifies a file of them. Exits 1 when an instruction reaches the level you chose, and 2 for malformed input. |
| **North-star metric** | Share of agent-submitted payment instructions that reach release only through a recorded mandate decision. Target 🔴 100%. Today in this model: none are checked. |
| **Measured metrics (synthetic)** | 🟢 249 of 249 legitimate instructions released and 0 stopped; 46 of 62 that need a person held; 156 of 164 forbidden ones rejected; 49 of 49 hard negatives released; the decision matches the planted truth on 451 of 475; 24 of 475 still released that should not be (`step_04_with_mandate_check.py`). |
| **Modeled metrics** | 🟡 Utility (156/164 − 28/164) × 500 = 390.2 forbidden instructions a year stopped that a flat cap and name list would release, assuming 500 forbidden instructions reach the gateway each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling. Mitigation: run it in shadow on one real log a payments team may share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The check trusts what the instruction says about itself (category, rail, account), and split payments under the threshold pass. 🟢 16 of 16 split pieces and 8 of 8 memo cases are released (`step_03_deficiencies_exposed.py`). Mitigation: a same-payee aggregate over a rolling window is next in the backlog; the memo is not read, on purpose. |
| **Risk #3** | The audit chain shows consistency, not authorship. Anyone who can write the file can rebuild every hash after an edit. 🟢 Cutting records off the end is found only when the head hash was recorded elsewhere (`step_04_with_mandate_check.py`). Mitigation: store the head hash where the gateway cannot write. |
| **Out of scope** | Capturing or signing the customer's consent; moving money; verifying that an account belongs to a payee; reading the memo or any free text; foreign exchange; rolling windows; any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is instructions, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Input validation** (malformed, truncated or NUL-byte input exits 2, never a traceback) | 475 instr | 2 | 0.9 | 1 | 855.0 | Built in prototype |
| 2 | **Per-instruction rules** (mandate, agent, validity, revocation, payee and pinned account, currency, rail, category, amount) | 475 instr | 3 | 0.8 | 2 | 570.0 | Built in prototype |
| 3 | **Ledger rules** (daily limit, repeated instruction id, near-duplicate within 600 seconds) | 475 instr | 3 | 0.6 | 2 | 427.5 | Built in prototype |
| 4 | **Hash-chained audit record and verify** | 475 instr | 2 | 0.8 | 2 | 380.0 | Built in prototype |
| 5 | **Command output** (`--fail-on` levels, `--show`, escaped strings) | 475 instr | 2 | 0.7 | 2 | 332.5 | Built in prototype |
| 6 | **Head-hash anchor stored outside the gateway** | 475 instr | 2 | 0.6 | 2 | 285.0 | Sequenced for v0.2 |
| 7 | **Same-payee aggregate over a rolling window** (the second and third piece of a split) | 475 instr | 3 | 0.5 | 3 | 237.5 | Sequenced for v0.2 |
| 8 | **Fail-closed gateway integration** (a synchronous call; no answer means HOLD) | 475 instr | 3 | 0.5 | 5 | 142.5 | Sequenced for v0.2 |
| 9 | **Rolling daily limit** in place of the calendar day | 475 instr | 1 | 0.6 | 3 | 95.0 | Queued |
| 10 | **Hold queue for a person** (what they see, how they answer) | 62 instr | 3 | 0.6 | 4 | 27.9 | Sequenced for v0.2 |
| 11 | **Mandate registry** (consent capture and revocation delivery) | 14 mandates | 3 | 0.5 | 6 | 3.5 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Payment Mandate Check | What they fear |
| --- | --- | --- | --- |
| **Payment gateway owner** | Owner | A decision with a reason code on every instruction, and a stop that does not depend on the agent's own prompt. | A check that holds legitimate payments and gets bypassed. |
| **Approver of holds** | Co-owner of thresholds | Few holds, each with a plain sentence about why a person is asked. | A queue that fills with noise until holds are approved without reading. |
| **Customer** | Delegating party | That the agent pays only inside the limits they set, and stops when they revoke. | Learning of a payment from a statement. |
| **Agent product owner** | Consulted | Clear reasons when an instruction is rejected, so the agent can be corrected. | A rejection with no reason that cannot be reproduced. |
| **Fraud and dispute operations** | Informed | An audit record that shows what was decided and from which inputs. | A record that can be rewritten after a dispute starts. |
| **Security / CISO** | Approver | Strings from instructions kept out of logs, no credential in the check's path, nothing leaving the boundary. | Memo or payee text that forges a log line or a command. |
| **Internal audit** | Reader | A path from a decision to the exact instruction row and the rule set that decided it. | A chain that proves nothing about who wrote it. |

---

## User stories (top 4)

1. **As the gateway owner**, I want an instruction that names a payee, an account, a rail or an amount outside the mandate to be rejected before release, so a valid credential is not the only control.
2. **As the approver of holds**, I want an instruction that needs a person to arrive as a HOLD with the reason in a sentence, so I can answer without reading the whole mandate.
3. **As the customer's representative in a dispute**, I want a repeated instruction or a second payment that breaks the daily limit to be stopped, so the same payment does not go out twice.
4. **As internal audit**, I want one audit record per decision, chained by hash, so an edited decision is found, and I know the head hash must be kept elsewhere.

---

## KPIs

**North star:** share of agent-submitted payment instructions that reach release only through a recorded mandate decision. Target 🔴 100%.

**Inputs (leading):**
- Mandates with a limit, a daily limit, validity dates, pinned payee accounts, rails and categories recorded (the prototype set has 🟢 14 mandates, from `data/README.md`).
- Instructions stamped by the gateway with the time it received them (target: every instruction; prototype: 🟢 475 instructions in the set).
- Revocations delivered to the check before the next instruction (target: every one).
- Head hashes recorded outside the gateway (target: every audit file).

**Outputs (lagging):** prototype baselines from the planted set.
- Legitimate instructions stopped. 🟢 0 of 249 with the check, against 6 of 249 with a flat cap and name list (`step_04_with_mandate_check.py`, `step_02_flat_cap_and_name_list.py`).
- Forbidden instructions rejected. 🟢 156 of 164, against 136 of 164 released with a flat cap and name list (`step_04_with_mandate_check.py`, `step_02_flat_cap_and_name_list.py`).
- Instructions held for a person. 🟢 46 of 62 (`step_04_with_mandate_check.py`).
- Hard negatives released. 🟢 49 of 49 (`step_04_with_mandate_check.py`).
- Decision matches the planted truth. 🟢 451 of 475 (`step_04_with_mandate_check.py`).
- Known miss. 🟢 24 of 475 released that should not be (`step_04_with_mandate_check.py`).
- Holds a person later overturned: not measured; the planted set has no approver.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the check beside the live gateway on one agent product with `--fail-on never`. Print the decisions, stop nothing, and compare with what customers disputed. |
| 1: Calibration | 4w | Read the HOLD and REJECT lines. Set the confirmation threshold, the near-duplicate window and the definition of a day against that product's real traffic. |
| 2: Reject enforced | 4w | Release only what the check does not reject. HOLD stays advisory. Record the audit head hash outside the gateway. |
| 3: Hold enforced | 6w | Route HOLD to a person through a queue, with the reason sentence. Fail closed when the check does not answer. |
| 4: Aggregate and registry | 8w | Add the same-payee aggregate over a rolling window, connect the mandate registry and its revocation feed, and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **What is a day?** The prototype uses a UTC calendar day of the gateway's `received_at`, and only released payments use it up. Recommendation: keep it for the pilot, and move to a rolling window once the aggregate rule exists.
2. **Should a held instruction use up the day?** It does not, so an agent can queue many holds, and I do not cap how many. Recommendation: cap queued holds per mandate in phase 3.
3. **Who stores the head hash?** Recommendation: a system the gateway cannot write, owned by someone other than the gateway owner, recorded at the end of each batch.
4. **Should the memo be read?** The check ignores it on purpose, because it is the agent's free text. 🟢 8 of 8 memo-contradicts-category payments are released (`step_03_deficiencies_exposed.py`). Recommendation: keep the gate free of free text and route memo screening to a separate step.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One synchronous check in front of release.** The prototype is a batch command; the production shape is a call the gateway makes per instruction, with a durable ledger of what was released. All of that is designed and none built.
- **Never silent.** A file that cannot be read as a mandate list or an instruction table exits 2 and fails the run, even with `--fail-on never`. In production, no answer from the check means HOLD, not RELEASE.
- **Strings from input are data.** Memo, payee name and ids are escaped before they reach a line of output, so a hostile string cannot forge a log line.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves a count shows in the diff.

**What is next.** Add a same-payee aggregate over a rolling window, which would hold the second and third piece of a split. Run the check on a log a payments team is allowed to share. Decide where the head hash of the audit chain is stored outside the gateway.

**What would have to be true before a pilot.**
- The gateway stamps `received_at` itself, and the agent cannot supply its own clock.
- The mandate file carries pinned payee accounts, limits and validity for every agent in scope.
- A revocation reaches the check before the next instruction is decided.
- A named person owns the thresholds and a different person holds the head hash.
- One real log can be shared, so the rules are measured on real payments and not on mine.

---

*This PRD names [27 AgentKit](../27-agentkit-reference-agent-and-playbook/), [34 Audit Chain](../34-audit-chain/), [08 OversightOps](../08-oversightops-hitl-workflow/) and [72 Scam Friction Sim](../72-scam-friction-sim/) as designed interlocks (🔴 designed, none built). The gate and audit ideas were written again here from 27 and 23; nothing is imported across folders.*
