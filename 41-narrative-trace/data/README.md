# Data for project 41

Synthetic. Built by `_generate.py` with a fixed seed, so a rerun reproduces every file byte for byte. Nothing here comes from a real bank, customer, employer or filing. Counterparty names are invented; any resemblance to a real business is coincidence.

| File | What it holds |
|---|---|
| `transactions.csv` | 478 records in 40 cases: `txn_id`, `case_id`, `date`, `amount`, `direction` (in or out), `channel` (cash, wire, ach, check, card), `counterparty` (empty for cash) |
| `narratives.json` | 40 narratives, one per case: `case_id` and `text`. 408 sentences, each citing records as `[txn: ID]` |
| `truth.csv` | One row per sentence: `case_id`, `sent_no`, `start` and `end` (character offsets into the narrative), `kind` and `expected` (ok or flag). The label comes from what was planted, not from the rules |
| `example_txns.csv`, `example_narrative.txt` | The worked example behind `python3 narrative_trace.py --demo` (case EX-1; a record of case EX-2 is cited by mistake) |

Planted sentences (408). Fine, 268: plain 110, other formats of the same figure 40, counterparty ending in "Inc." or "Ltd." 24, count and total over several records 24, numbers that are not amounts 20, "cash-intensive" as an adjective 8, citation after the period 16, connecting sentence with nothing to compare 16, a date that is not a transaction date 10. Defects, 140: uncited 20, dangling ID 14, ID from another case 12, wrong amount 14, wrong date 12, wrong counterparty 12, wrong direction 10, wrong channel 10, wrong count 8, wrong total 8, laundered 12, mixed record 8.

Two defect kinds are hard on purpose. A laundered sentence cites a real record and says something no field of it can confirm. A mixed-record sentence states amounts and dates that are each right for some cited record, bound to the wrong one. The rules cannot see either. Two fine kinds are hard on purpose as well: a connecting sentence looks the same to the rules as a laundered one, and a sentence about an opening date raises a false alarm.

No threshold, limit or deadline from a regulation is used in the data or the rules.
