# 🧾 recon-agent (match with evidence): a ledger reconciler that has to show why two lines are one

**I wanted to know whether an agent that reconciles two ledgers can be made to show its work, and what that costs. This is a command-line tool that matches a bank statement to a cash book with five plain rules, cites the lines and the facts behind every match, re-runs the rule on those lines before anything posts, and holds the riskier matches for a person's approval.** On 383 bank lines and 438 book lines of synthetic data it posted 218 matches on its own with none wrong, held 101 for a person, and listed every one of the 169 lines still open with a reason. The part that does not hold is the person: the stand-in approver passed 6 look-alike invoices that were not matches.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 57-recon-agent/src && python3 recon_agent.py --demo
```

It prints, for a worked month of 11 bank lines and 15 book lines:

```text
recon-agent: 11 bank lines, 15 book lines, date window 3 days, a person approves above 10000.00 and for every rule except ref_exact
M-0001 posted_auto     ref_exact   BK-000001 = GL-000001
    ref inv-10453 = INV-10453 | amount 1250.00 USD = 1250.00 USD | gap 0 days | names agree
M-0002 posted_approved ref_fee     BK-000002 = GL-000002 by reviewer-1
    ref INV-10460 = INV-10460 | amount 4998.50 USD + fee 1.50 = 5000.00 | gap 0 days | names agree
M-0003 posted_approved batch_sum   BK-000003 = GL-000003,GL-000004,GL-000005 by reviewer-1
    ref BT-0304 is the batch id on 3 book lines | amount 3000.00 USD = 1000.00 + 1200.00 + 800.00 | gap 0 days | names agree
M-0004 posted_auto     ref_exact   BK-000004 = GL-000006
    ref PMT-004517 = PMT-4517 | amount -780.00 USD = -780.00 USD | gap 1 day | names agree
M-0005 rejected        ref_near    BK-000005 = GL-000007 by reviewer-2
    ref INV-10481 vs INV-10418, one edit apart | amount 2200.00 USD = 2200.00 USD | gap 0 days | names agree
M-0006 pending         name_amount BK-000006 = GL-000008
    ref bank blank, book INV-10477 | amount 6400.00 USD = 6400.00 USD | gap 0 days | names agree
M-0007 pending         ref_exact   BK-000010 = GL-000013
    ref INV-10500 = INV-10500 | amount 15000.00 USD = 15000.00 USD | gap 0 days | names agree
M-0008 posted_auto     ref_exact   BK-000011 = GL-000014
    ref INV-10490 = INV-10490 | amount 410.00 USD = 410.00 USD | gap 0 days | names agree
refused: reviewer-1 on name_amount:BK-000006:GL-000016:640000: stale: no current proposal has this key
refused: recon-agent on ref_exact:BK-000010:GL-000013:1500000: self-approval: the proposer cannot approve
open items: 14
  A BK-000005   2200.00 rejected_by_reviewer: M-0005 ref_near rejected by reviewer-2
  A BK-000006   6400.00 awaiting_approval: M-0006 name_amount needs a person because no reference on one side
  A BK-000007    900.00 ambiguous_candidates: cannot be told apart from: GL-000009, GL-000010
  A BK-000008    -35.00 no_counterpart: nothing on the other side meets any rule
  A BK-000009   1200.00 reference_conflict: same amount, counterparty and window as GL-000012, but the references...
  A BK-000010  15000.00 awaiting_approval: M-0007 ref_exact needs a person because the amount is above 10000.00
  B GL-000007   2200.00 rejected_by_reviewer: M-0005 ref_near rejected by reviewer-2
  B GL-000008   6400.00 awaiting_approval: M-0006 name_amount needs a person because no reference on one side
  B GL-000009    900.00 ambiguous_candidates: cannot be told apart from: BK-000007
  B GL-000010    900.00 ambiguous_candidates: cannot be told apart from: BK-000007
  B GL-000011  -2150.00 no_counterpart: nothing on the other side meets any rule
  B GL-000012   1200.00 reference_conflict: same amount, counterparty and window as BK-000009, but the references...
  B GL-000013  15000.00 awaiting_approval: M-0007 ref_exact needs a person because the amount is above 10000.00
  B GL-000015    410.00 possible_duplicate: identical in every compared field to GL-000014, which is in a match o...
posted 5 (3 on their own, 2 on approval); waiting 2; rejected 1; blocked by the check 0; approvals refused 2
```

Standard library only, Python 3.9 or newer. To run it on your own two CSV files: `python3 recon_agent.py reconcile bank.csv book.csv --approvals approvals.csv --out out/`, then `python3 recon_agent.py verify bank.csv book.csv out/matches.csv` to re-check the finished list. `verify` exits 1 when a posted match no longer re-checks; bad input exits 2 with one line.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: one month, two ledgers, an answer key built by the generator; the script is named in brackets. 🟡 is modeled, with the assumption named):

- 🟢 Two ledgers and no matching: 383 bank lines and 438 book lines, 821 to read side by side, and the USD totals differ by 139980.34. The total does not say which lines are out (`step_01`)
- 🟡 Reading all 821 lines at one minute each is 13.7 hours. The one minute is my assumption, not a measurement (`step_01`)
- 🟢 A lookup on amount and date posts 316 matches: 291 right, 25 wrong, and a recorded reason for 0 of 316 beyond amount and date (`step_02`)
- 🟢 Its 25 wrong matches are currency_clash 5, lookalike_conflict 10, near_ref_distinct 6 and twin_payments 4. It cannot make fee_netted 20 or batch 12 at all (`step_03`)
- 🟢 The five-rule ladder alone, with every proposal posted at once, posts 319 matches, 6 of them wrong; 101 are matches the policy says a person must see (`step_03`)
- 🟢 With the check and the gate: 218 matches post on their own and 0 are wrong; 101 wait for a person; 93 post on approval and 8 are rejected (`step_04`)
- 🟢 Posted where the policy needs an approval and none is on record: 0. Self-approval by the agent, in three spellings, is refused 101 of 101 times; an approval for a proposal that no longer exists is refused 101 of 101; an approve and a reject on one proposal leave 10 of 10 pending (`step_04`)
- 🟢 Re-checking a finished list catches hand edits: one book line swapped for another 299 of 299, an approved match relabelled as posted on its own 93 of 93, a match copied under a second id 311 of 311 (`step_04`)
- 🟢 A person looks at 385 of 821 lines instead of 821, and the 169 open lines each carry a reason: no_counterpart 89, reference_conflict 28, ambiguous_candidates 18, rejected_by_reviewer 16, currency_differs 10, possible_duplicate 8 (`step_04`)

## What it still gets wrong

- 🟢 18 true matches never get a proposal: no_ref_abbrev 4, out_of_window 6, ref_garbled 4 and split_no_batch 4. A split deposit with no batch id on the book lines is the one I left in on purpose (BK-000029, BK-000217, BK-000254 and BK-000279; `step_03` prints each). They sit in the open list with a reason, so nobody is told they matched (`step_03`, `step_04`)
- 🟢 The gate records who approved. It does not make the approver careful. The scripted approver approved all 21 ref_near proposals, and 6 of them are distinct invoices one edit away from a real one, so 6 wrong matches posted with a name on them. The same script rejected 8 right matches because the payer name differed. The 15 real typos and the 6 look-alikes need the invoice to tell apart, and the script never opens it (`step_04`)
- **The approver here is a script I wrote, not a person.** It reads what is printed with each proposal and approves unless the counterparty names differ. Its blind spots are my choice. How a real reviewer behaves is 🔴 hypothetical: I have not tested one.
- **The data and the rules share an author.** I planted the cases and wrote the five rules, so 0 wrong among 218 matches posted on their own shows the rules cover what I planted. The first draft of the data was easier. I then added the hard cases: look-alike invoices, a currency clash, twin payments, and four kinds of true match the rules cannot reach. Treat the numbers as a ceiling for these rules, not a rate on a real bank. The date lag on the ordinary pairs is 0 to 3 days and the window is 3 days, so the window covers them by construction; only the out_of_window kind falls outside it.
- Amounts must match to the cent. There is no tolerance for rounding and no currency conversion. A fee is netted only from a credit, and only if it is on the fee schedule I gave the tool. The name table knows three abbreviations; the generator uses four.
- 🟡 The window (3 days), the approval limit (10000.00), the fee schedule (1.50, 2.50 and 15.00) and the rule that only `ref_exact` may post on its own are assumptions, not taken from any rule or bank. They are parameters at the top of `src/recon_agent.py`.
- There is no model in this folder. The proposer is a rule ladder. If a model were to propose matches, the check and the gate are the part I would keep; I have not tested that. 🔴
- I ran it on about 800 lines. I have not measured it on thousands.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What is in front of a person with two ledgers and nothing matched? | `step_01_two_ledgers_unmatched.py` |
| 2 | What does a lookup on amount and date post, and what can anyone check? | `step_02_amount_and_date_lookup.py` |
| 3 | Where does each version fail against the answer key? | `step_03_deficiencies_exposed.py` |
| 4 | What do evidence, a re-check and an approval gate change? | `step_04_with_gate.py` |

Run any of them from `src/`. Step 4 writes `src/out/` (git-ignored), and `python3 _build_demo.py` turns that into `demo.html`. The data comes from [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

The five rules, in order: `ref_exact` (same reference, amount, currency, within the window; posts on its own below the limit when the names agree), `ref_fee` (reference equal, amount short by a scheduled fee), `batch_sum` (the bank reference is the explicit batch id on 2 to 6 book lines that add up), `ref_near` (references one edit apart), `name_amount` (no reference on one side; same name and amount). Every rule except the first waits for a person. When two book lines fit equally well and are not identical, the bank line is parked for a person instead of guessed. Each proposal prints a key such as `ref_fee:BK-000002:GL-000002:499850`; an approval binds to exactly that key.

## Aligned to

Nothing. I have not mapped this to a standard, a regulation or a published control, so I claim no alignment. It is a prototype on synthetic data.

It borrows a pattern from [27 AgentKit](../27-agentkit-reference-agent-and-playbook/): a person-held gate, a scripted stand-in for the person, and no approval from the agent itself. I wrote the matching rules here and copied no code from that folder.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real bank, and the counterparty names are invented. A prototype on synthetic data, not a production case study. The files and the planted kinds are listed in [`data/README.md`](./data/README.md).

## Fork it

Swap `data/ledger_a.csv` and `data/ledger_b.csv` for your own exports and keep the columns, or point `reconcile` at two files from your system. Change the window, the fee schedule or the limit in `Params`. Read the [PRD](./PRD.md) for the scope I held to.
