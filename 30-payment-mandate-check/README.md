# 🧾 Payment Mandate Check: does the agent have the authority to pay this?

**I wanted to know what stands between an AI agent and a payment its customer never delegated, and how much of that a check at the point of release can stop. This is a command-line tool that compares each payment instruction with the customer's mandate (limits, payees, expiry) before anything is released, prints RELEASE, HOLD or REJECT with the reasons, and writes a hash-chained audit record.** It takes two ideas from earlier projects: from [23 ScopeKeeper](../23-scopekeeper-agent-permission-review/), that an agent's permission says which call it may make and not how much or to whom; from [27 AgentKit](../27-agentkit-reference-agent-and-playbook/), a gate where the agent stops and a person answers, and an audit trail chained by hashes. I wrote both ideas again here and import nothing across folders.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 30-payment-mandate-check/src && python3 payment_mandate_check.py --demo
```

It prints:

```text
  S-0001 RELEASE    180.00 USD to PY-D1 on M-DEMO  inside the mandate
  S-0002 HOLD       320.00 USD to PY-D2 on M-DEMO  OVER_CONFIRM_THRESHOLD: a person confirms above 250.00
  S-0003 RELEASE    240.00 USD to PY-D1 on M-DEMO  inside the mandate
  S-0004 REJECT      90.00 USD to PY-X9 on M-DEMO  PAYEE_NOT_LISTED: payee_id is not on the mandate
  S-0005 RELEASE    240.00 USD to PY-D2 on M-DEMO  inside the mandate
  S-0006 RELEASE    240.00 USD to PY-D1 on M-DEMO  inside the mandate
  S-0007 REJECT     100.00 USD to PY-D2 on M-DEMO  OVER_DAILY_LIMIT: 900.00 already released today, limit 900.00
7 instructions: 4 RELEASE, 1 HOLD, 2 REJECT
audit: 7 records, chain ok, head 22108ed6fa24
```

Standard library only, Python 3.9 or newer. To check your own files:

```bash
python3 payment_mandate_check.py check mandates.json instructions.csv --audit audit.jsonl
python3 payment_mandate_check.py verify audit.jsonl --head <the head hash you recorded>
```

`check` prints the HOLD and REJECT lines (add `--show all` for every line) and exits 1 when an instruction reaches `--fail-on` (default `reject`; `hold` and `never` also work). It exits 2 with one line on stderr for a file it cannot read as a mandate list or an instruction table. The columns and the mandate fields are listed at the top of [`src/payment_mandate_check.py`](./src/payment_mandate_check.py).

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 475 planted instructions against 14 mandates; the script is named in brackets):

- 🟢 No mandate check: 475 of 475 instructions released, 164 of them forbidden by the mandate and 62 that needed a person; 37,521.25 USD of the forbidden ones parse as an amount (`step_01`)
- 🟢 A flat 1,000.00 cap plus a list of 70 approved payee names releases 136 of 164 forbidden instructions and 60 of 62 that needed a person, stops 6 of 249 legitimate ones, and lets 12 of 12 look-alike payees through (same name, different payee id) (`step_02`)
- 🟢 The per-instruction checks alone release 28 forbidden instructions and 30 that needed a person; the ledger alone releases 133 and 46. The ledger is what stops 10 daily-limit breaches, 10 repeated instruction ids and 14 near-duplicates (`step_03`)
- 🟢 The full check releases 249 of 249 instructions that are inside the mandate, holds 46 of 62 that need a person, rejects 156 of 164 that are outside it, and releases 49 of 49 hard negatives (a limit to the cent, the last second of a mandate, hostile text in the memo); 451 of 475 decisions match the planted truth (`step_04`)
- 🟢 The audit record chains 475 records; one decision edited after the fact is found at record 238; cutting records off the end is found only when the head hash was recorded elsewhere (`step_04`)

🟡 **Modeled, assumptions named:** the near-duplicate window is 600 seconds (my choice); the daily limit runs over a UTC calendar day of the time the gateway received the instruction; only released payments use up the day; "confirm above" means strictly above; a mandate's expiry second is still inside it and its revocation second is outside; the flat cap in step 2 is read as the same number in any currency. None of these comes from a rule.

🔴 **Hypothetical:** capturing the customer's consent in a form the gateway can check, delivering a revocation to the gateway in time, and what a person sees when an instruction is held. I did not build or test any of that.

## What it still gets wrong

- 🟢 24 of 475 instructions are released that should not be, and the scripts print them (`step_03`, `step_04`). Sixteen are the second and third pieces of 8 payments split so that each piece sits under the confirmation threshold while the total does not; the rules look at one instruction at a time against a daily total, and nothing adds up one payee over an hour. Eight are payments whose declared category is allowed and whose memo says gift cards for resale. The check does not read the memo, on purpose, because it is the agent's free text.
- **The data and the rules share an author.** I planted the scenarios and wrote the rules. Eight kinds of hard negative and two kinds of hard miss are in the set on purpose, but 0 stopped of 249 legitimate is a ceiling for these rules, not a rate on real traffic, which I have not tested.
- **The instruction describes itself.** Category, rail and account are what the agent says. The check compares them with the mandate. It does not verify that an account belongs to the payee or that the goods were bought.
- **The audit chain proves consistency, not authorship.** Anyone who can write the file can rebuild every hash after an edit. Keep the head hash somewhere the gateway cannot write.
- Money is a decimal with at most two places, one currency per mandate, no exchange rates. The day is a calendar day, not a rolling window. A held instruction does not use up the day, so an agent can queue many holds; I do not cap how many.
- Times must be `YYYY-MM-DDTHH:MM:SSZ` and `received_at` must be stamped by the gateway. If the agent supplies its own clock, the validity checks mean nothing.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What goes out when the agent's credential is the only control? | `step_01_no_mandate_check.py` |
| 2 | What does a flat cap and a payee-name list stop? | `step_02_flat_cap_and_name_list.py` |
| 3 | Where does each half of the mandate check fail alone, and what is the known limit? | `step_03_deficiencies_exposed.py` |
| 4 | What do the rules, the ledger and the audit record catch together? | `step_04_with_mandate_check.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` at the repository root confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The tests (`tests/`, 52 in all) pin those numbers and cover malformed input, hostile strings, the edges of every limit and the audit chain. `python3 -m unittest discover -s tests` from this folder runs them.

## Aligned to

Governor Christopher Waller's speech ["Payments in the Age of AI Agents"](https://www.federalreserve.gov/newsevents/speech/waller20260928a.htm), given at Sibos 2026 in Miami (the page is dated September 29, 2026; its address ends 20260928a; I read it on 2026-10-23). In his description of the agent-delegated model the buyer sets constraints and guardrails and the agent then pays on its own; the authentication question changes from whether the buyer is an authorized payer to whether the agent has authority to pay for the buyer; and card networks are publishing specifications that include registering agents and logging cardholders' approvals. This tool is one reading of that: the mandate is the buyer's constraint, the check asks whether this instruction is inside it, and the audit record logs the answer. I have not read the card-network specifications he mentions, and I cite no regulation. It is a prototype, aligned to that theme and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer, bank or real payee; company names are made up from syllables. A prototype on synthetic data, not a production case study. The scenarios, the planted truth and the assumptions are listed in [`data/README.md`](./data/README.md).

## Fork it

Swap `data/mandates.json` and `data/instructions.csv` for your own and keep the columns, or point `check` at two files from your gateway. Delete `truth.csv` if you have no planted labels; the tool never reads it, only the step scripts do. Read the [PRD](./PRD.md) for the scope I held to.
