# 🧾 payment-repair (AgentKit extension): a repair agent for pacs.008-style messages, with approval gates

**I wanted to know how much of a missing-field queue a repair agent can clear without guessing, and where it has to stop. This is a command-line tool and a synthetic set of 500 pacs.008-style payment messages. It finds the required fields that are missing, blank, placeholders or malformed, fills the ones a bank table can supply, holds the ones that decide where the money goes until a person approves that exact change, and sends back the rest untouched.** It extends [27 AgentKit](../27-agentkit-reference-agent-and-playbook/) with a message set and a repair tool, and imports nothing from it.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 36-payment-repair/src && python3 payment_repair.py --demo
```

It prints:

```text
M-0003  REPAIRED  1 change(s) applied; rule tier AUTO, no person needed
    debtor agent BIC: missing, value from bank directory (bank code 99106254, one active row) -> DUMONL22XXX  [AUTO]
M-0005  HOLD      waiting for a person to approve this plan
    creditor agent BIC: blank, value from bank directory (bank code 95013987, one active row) -> BOTAIT22XXX  [APPROVAL]
    digest 2581f72594c6d6453a03ab2f00d771836f2feb2802a736c333be474915346b0b
M-0076  RETURN    back to the originator; nothing was changed
    creditor name: blank; no table may supply a beneficiary name; a saved payee list can be stale
summary: 3 messages: 0 pass, 1 repaired, 1 hold, 1 return
```

Standard library only, Python 3.9 or newer. To check your own files: `python3 payment_repair.py check messages.json --refs refdir --approvals approvals.csv`. It exits 1 when a message is held or returned (`--fail-on return` ignores holds) and 2 for malformed input. `--out` writes the released messages and `--audit-out` writes one row per applied change.

Read the three routes in that output. The debtor's bank code has one active directory row, so the tool fills the BIC without a person (tier AUTO). The creditor's BIC comes from the same directory but decides where the money goes, so the plan waits for a person, and the 64-character digest is what an approval has to carry. The creditor name has no allowed source, so the message goes back untouched.

## The policy table

🟡 Modeled: this table is my assumption. It is not a reading of any rulebook, and the required fields are the ones this project's rules name, not the ones the ISO 20022 text names.

| Field | Source the tool may use | Tier | Refuses when |
|---|---|---|---|
| number of transactions | the message itself (one transaction) | AUTO | never |
| debtor agent BIC | bank directory by the debtor IBAN's bank code | AUTO | not exactly one active row in that country |
| debtor name | customer master by the debtor IBAN | AUTO | no row, a joint account, or an account that is not open |
| creditor agent BIC | bank directory by the creditor IBAN's bank code | APPROVAL | not exactly one active row in that country |
| creditor country | first two letters of the creditor IBAN | APPROVAL | the IBAN is itself unusable |
| UETR, charge bearer | the payment order with the same end-to-end id | APPROVAL | not exactly one order |
| amount, currency, creditor name, both IBANs, end-to-end id | none | NEVER | always |

A message with any refusal is returned whole: no partial repair. A message with only AUTO changes is repaired. A message with an APPROVAL change waits for an approval that carries the digest of that exact plan, from an active person with the reviewer role who did not enter the payment order.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 500 messages with 374 damaged fields; the script is named in brackets):

- 🟢 Status quo: a presence check at the next hop rejects 319 of 500 messages, catches 340 of 374 damaged fields and lets 34 through as if complete; a table or the message itself holds the true value for 249 of the 374, and only the originator can say for 125 (`step_01`)
- 🟢 A script that fills every empty field and releases: 310 required fields filled, 62 written wrong, and 126 of 500 messages released with a wrong or unusable required value (`step_02`, `step_03`)
- 🟢 The same script: 204 of its 310 changes land on fields the policy puts behind a person; it has no approval step and keeps no record of source or approver for any of its 350 changed fields (`step_03`)
- 🟢 The tool: 488 of 500 routes match the planted intent; 90 of 90 repairs made without a person equal the true value; 129 of 129 returned messages are left untouched; none of the 144 messages that should pass was touched (`step_04`)
- 🟢 The gate: 766 of 766 bad approvals blocked (no approval, another plan's digest, an agent, a person who left the team, a person without the reviewer role, the person who entered the order, a message changed after the plan was drawn up) and 125 of 125 valid approvals applied (`step_04`)
- 🟢 After approval: 126 of 135 approved changes equal the true value, and 21 of 371 released messages carry a wrong or unusable required value, against 126 of 500 for the basic script (`step_04`)
- 🟢 Record: 225 audit rows for 225 fields changed, none without a source (`step_04`)
- 🟢 Hard negatives left alone: 30 of 30 messages with missing optional fields, 8 of 8 names that contain "unknown" or "N/A", 6 of 6 eight-character BICs (`step_04`)

## What it still gets wrong

- 🟢 Twelve messages carry a well-formed creditor BIC that belongs to a different bank, and all 12 pass (`step_03`, `step_04`). The tool checks presence and shape, not consistency between the BIC and the IBAN's bank code.
- 🟢 Nine wrong proposals reach the gate and 9 are applied: 5 where the directory still lists a bank's old BIC as active, 4 where the creditor lives outside the IBAN country (`step_04`). The approver in this run is a scripted test double that approves any plan whose digest matches. 🔴 How many of the 9 a real reviewer would catch is not measured.
- **The data and the rules share an author.** I planted the damage and wrote the rules, and I wrote the intended route per recipe, so 488 of 500 shows the rules cover what I planted. The true values come from the generator, which removed them from complete messages; the intended routes are my policy stated twice. Treat the result as a ceiling, not a rate on real traffic, which I have not tested.
- **An approval here is a row in a CSV file.** The tool checks the digest and the registry, not who typed the row. A production version needs approvals that come from an identity system or a signed workflow step. 🔴 Designed, not built.
- One transaction per message, flat dotted paths and not XML, and no address checks. Unknown keys are ignored, so a misspelt path shows up as a missing field and an extra key. The placeholder list is short and English only, and a creditor whose whole name is a placeholder word, such as "NA", is treated as missing. BIC, IBAN and currency checks are shape checks of my own; IBAN check digits are not computed.
- Reference tables are read as given, with no as-of date. A stale directory is exactly the case the second bullet counts.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does the next hop do with a message that has a missing field? | `step_01_no_repair.py` |
| 2 | What does one script that fills every empty field do? | `step_02_fill_script.py` |
| 3 | Where does that script go wrong, scored against the answer key? | `step_03_deficiencies_exposed.py` |
| 4 | What do derivation, a refusal list, an approval gate and an audit record change? | `step_04_with_repair_tool.py` |

Run any of them from `src/`. Data is produced by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The `tests/` folder holds 75 unittest tests, including a golden test that pins these numbers and tests for malformed input and hostile strings.

## Aligned to

Governor Christopher Waller's speech ["Payments in the Age of AI Agents"](https://www.federalreserve.gov/newsevents/speech/waller20260928a.htm), Sibos 2026, Miami, 2026-09-29, which I read on 2026-10-23. It is about agents that shop and pay for a buyer. It says the delegated model needs more extensive trust mechanisms and guardrails, asks who is on the hook when an agent makes the wrong purchase, and asks what balance between convenience and "purposeful friction" suits agent authorization. It does not mention ISO 20022 or the repair of payment messages. I borrowed the framing only: here the friction is the approval gate and the refusal list, applied to an agent inside a bank.

The message names follow the ISO 20022 pacs.008 element names. I could not read the standard (the ISO site returned HTTP 403 on 2026-10-23), so I cite nothing from it: the set is pacs.008-style, not validated against the schema, and the required fields are the policy table above. From [27 AgentKit](../27-agentkit-reference-agent-and-playbook/) I took the pattern of an approval bound to a digest of the exact correction, an approver who must be a person and not the proposer, and an audit record. The code here is written from scratch. This is a prototype, aligned to those ideas and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real bank, and every company, BIC and account is invented. A prototype on synthetic data, not a production case study. [`data/README.md`](./data/README.md) lists every file and every planted recipe. [`PRD.md`](./PRD.md) holds the scope I held to.

## Fork it

Swap `data/messages.json` and the four reference CSV files for your own exports and keep the column names, then run `check` with your approvals file. Change the tiers in `POLICY` at the top of `src/payment_repair.py` to match your own rule table, and re-run the steps to see which of your fields move from AUTO to APPROVAL. If you tune a rule, score it on messages the tuning did not see.
