# Sample Data — AgentKit walkthrough

Eight CSVs drive Steps 1 through 4 of the walkthrough and the tests. Everything is synthetic, seeded (`SEED = 20261027` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files (a test checks that, and that the committed files equal what the generator writes). The generator uses only the Python standard library and runs on Python 3.9. **No customer data. No real bank, payment system, watch list, vendor or person. The party names are invented from syllables; the account numbers carry a check digit the generator computes; the worker ids are pseudonyms. No model is used anywhere in this repo.**

**The answer key is the generator's own.** The generator builds each case from a named recipe (a scenario), so it knows what the case is. The recorded human outcome follows the recipe, not any matcher's score. It is the generator's idea of a careful worker, not a gold label from a real operation, and a real worker would disagree with it sometimes. `case_truth.csv` holds the recipe name per case. The kit never reads it; the step scripts use it only to explain a result.

**Seed and parameters.** `SEED = 20261027` was chosen before any result was computed and was not re-rolled. The scenario counts, the name-edit types, the outcome rules and the fault schedule were set from design reasoning about the workflow, before any agent result was computed. The acceptance limits in the brief were written before the first run. The kit's thresholds (close at 0.90, ambiguous from 0.65, watch-list hit at 0.85) were set before the first run and not changed after it.

**It is a test set, not an estimate of real-world frequency.** 600 cases in 30 days with about a fifth of them planted edge cases is dense on purpose, so that each failure mode appears often enough to count. How many cases a real queue sees is a separate, named assumption in the README's utility section.

The headline scenario the walkthrough resolves: **a modeled bank's payment exception queue holds 600 returned or exception payments in 30 days. A happy-path script resubmits 515 of them with no approval and fails silently on 52. AgentKit, run from a build brief in shadow mode, proposes an outcome for 548 and agrees with the recorded human outcome on 522, sends 454 to a person, 12 back to the human queue, and leaves one acceptance test failing.**

---

## Time

Hour 0 is a constant epoch; the clock is never read. `opened_hour` runs from 0 to 712 in this file, inside the 720-hour (30-day) window. Cases are in arrival order, and a duplicate delivery always arrives 1 to 6 hours after its first delivery.

## `cases.csv` — 600 rows (the input an agent sees)

| Column | Type | What it is |
| --- | --- | --- |
| `case_id` | string | `C-0001` to `C-0600`, in arrival order. One per delivery. |
| `exception_ref` | string | The exception's own reference. A redelivery repeats it. |
| `delivery_no` | int | 1 for the first delivery, 2 for a redelivery. |
| `opened_hour` | int | Hours since the epoch, 0 to 712 in this file (the window is 720 hours). |
| `payment_id` | string | The original payment. Blank in three malformed cases; a payment that does not exist in three others. |
| `reason_code` | string | `RX01` to `RX04`, or `RX99` (unknown) in three malformed cases. |
| `returned_name` | string | The name the receiving side holds for the account. |
| `returned_account` | string | The account as the receiving side saw it. |
| `advised_value` | string | The value the return advice says would fix it: an account (`RX01`, and `RX03` when a successor exists), a name (`RX02`) or a bank code (`RX04`). Empty for a plain closed account. |
| `amount`, `currency` | string | The payment's amount and currency. |

The first rows:

| case_id | exception_ref | delivery_no | opened_hour | payment_id | reason_code | returned_name | returned_account | advised_value | amount | currency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C-0001 | EX-00001 | 1 | 0 | P-00017 | `RX01` | Pratalvin Paper Solutions Limited | 4555039055 | 4555309055 | 110305.23 | EUR |
| C-0002 | EX-00002 | 1 | 2 | P-00116 | `RX01` | Pelom Ceramics Enterprises Inc | 9021490752 | 9012490752 | 10683.20 | EUR |
| C-0003 | EX-00003 | 1 | 4 | P-00015 | `RX01` | Loryor Foods Distribution Co | 6351874332 | 6351873432 | 8341.63 | USD |

## `human_outcomes.csv` — 600 rows (the recorded human outcome)

| Column | Type | What it is |
| --- | --- | --- |
| `case_id` | string | Joins to `cases.csv`. |
| `human_outcome` | string | `RESUBMIT`, `RETURN_TO_ORIGINATOR`, `ESCALATE_COMPLIANCE` or `DUPLICATE_CLOSED`. |
| `corrected_field`, `corrected_value` | string | For a resubmit: the field the worker corrected and the value they wrote. Empty otherwise. |
| `touch_minutes` | float | Minutes the worker spent: the generator's per-step minutes for the steps on that path, times case-level noise. 🟡 Modeled, not a time study. |
| `handled_by` | string | A pseudonymous worker id, `W01` to `W12`. The kit never reads it. |

Outcome mix: 432 resubmit, 132 return to originator, 22 escalate to compliance, 14 duplicate closed.

## `case_truth.csv` — 600 rows (the generator's answer key)

`case_id`, `scenario` (the recipe), `planted` (1 for an edge case the generator plants on purpose) and `note`. Not an input to the kit.

| Scenario | Cases | Reason | Recipe | Recorded human outcome |
| --- | --- | --- | --- | --- |
| `fix_account_clean` | 210 | `RX01` | The payment's account has two digits transposed; the advice carries the right one. | Resubmit with the advised account |
| `fix_name_style` | 70 | `RX02` | The returned name is the payment's name in another style: case, punctuation, legal form, an abbreviation. | Resubmit with the returned name |
| `fix_name_typo` | 20 | `RX02` | One letter changed in one word. | Resubmit with the returned name |
| `fix_name_affiliate` | 14 | `RX02` | An affiliate entity: the payment's name with a place or numeral added (UK, Asia, II, 2, Global). A different legal party that looks like a close match. | Return to originator |
| `fix_name_ambiguous` | 36 | `RX02` | The first two words match, the third differs (Group, Holdings, Associates, Ventures, Capital). | 24 of 36 judged the same party and resubmitted, 12 judged different and returned (the generator draws at 60% and 40%; this seed gave 24 and 12) |
| `fix_name_unrelated` | 40 | `RX02` | A different company altogether. | Return to originator |
| `closed_account` | 60 | `RX03` | The account is closed; no advice. | Return to originator |
| `closed_successor` | 6 | `RX03` | The account is closed and the advice carries a successor account. | Resubmit with the successor account |
| `missing_bank_code` | 90 | `RX04` | The payment has no bank code; the advice carries one. | Resubmit with the advised code |
| `watch_exact` | 10 | `RX01`/`RX02`/`RX04` | The beneficiary name equals a watch-list entry. | Escalate to compliance |
| `watch_variant` | 12 | `RX01`/`RX02`/`RX04` | A variant of a watch-list name: style (2), one-letter typo (4), words swapped (2), two typos (4). | Escalate to compliance |
| `watch_lookalike` | 6 | `RX01`/`RX02`/`RX04` | A watch-list name with a place added. A person cleared it. | Resubmit |
| `malformed` | 12 | various | Three each of: blank payment id, unknown reason code, an advised account with letters, a payment id that does not exist. | Fixed by hand: 6 resubmit, 6 return |
| `duplicate` | 14 | as the original | A redelivery of an earlier resubmit case, same `exception_ref`, 1 to 6 hours later. | Duplicate closed |

Planted edge cases: the affiliate names, the ambiguous names, the closed accounts with a successor, the watch-list hits and look-alikes, the malformed records and the duplicate deliveries. Also planted, without a scenario of their own: leading-zero account numbers (about one in ten accounts starts with a zero), which a spreadsheet hop corrupts.

**The abbreviation variants.** The generator writes company names in eight abbreviation styles (`Services` to `Svcs`, and so on). The kit's name matcher knows five of them. That is deliberate: a real name list holds abbreviations no table knows, and the ones the table misses land in the ambiguous band or the mismatch band.

## `payments.csv` — 686 rows (the synthetic payments table)

`payment_id`, `originator`, `beneficiary_name`, `beneficiary_account`, `beneficiary_bank_code`, `amount`, `currency`, `value_hour`. 586 payments for the 586 first deliveries and 100 filler payments no case uses. Six of the 586 belong to malformed cases whose `payment_id` is blank or points at a payment that does not exist, so 106 payments in all are never read by a case. Bank codes look like `SYNB0042` (blank where the case is `RX04`). The account numbers are ten digits with a Luhn check digit; the transposed accounts fail it.

## `parties_watchlist.csv` — 60 rows (a synthetic party watch list)

`party_id`, `name`, `list_code` (`SYN-A` or `SYN-B`), `added_hour`. Invented names. The screening service in the simulated environment reports candidates at or above a similarity of 0.70; the kit counts a hit at 0.85.

## `reason_codes.csv` — 4 rows (the rule table)

| code | description | repair rule | field to correct |
| --- | --- | --- | --- |
| `RX01` | account number invalid | `FIX_ACCOUNT` | `beneficiary_account` |
| `RX02` | beneficiary name does not match the account | `FIX_NAME` | `beneficiary_name` |
| `RX03` | account closed | `NOT_REPAIRABLE` | |
| `RX04` | beneficiary bank code missing | `FIX_BANK_CODE` | `beneficiary_bank_code` |

The codes are synthetic and are not a payment scheme's codes.

## `fault_schedule.csv` — 24 rows (the fault-injection schedule)

`fault_id`, `case_id`, `step`, `tool`, `action`, `attempts` (`1`, `1,2` or `*` for every attempt), `fault_type`, `payload`. Used by step 4 and by the tests.

| Fault type | Rows | What it does |
| --- | --- | --- |
| `timeout` | 11 | The tool call raises a timeout. Eight are transient (first attempt only); three are persistent. |
| `malformed_output` | 6 | The tool answers with a garbled payload. Four transient, two persistent (both on the watch-list screen). |
| `rogue_call` | 4 | Before the named step the agent tries a call outside the brief's scope: `payments_db.update_payment` (twice), `payments_gateway.cancel_payment`, `watchlist.remove_party`. |
| `duplicate_delivery` | 3 | The replay delivers the same case twice. |

A fifth fault type, `timeout_after_write` (the write is applied and the answer is lost), is built in the tests and in step 4's live pass rather than scheduled here, because a write is a dry run in shadow mode.

## `step_minutes.csv` — 12 rows

The generator's per-step touch minutes, with each step's catalog class. S01 2, S02 1, S03 3, S04 4, S05 3, S06 2, S07 8, S08 5, S09 4, S10 2, S11 3, S12 1. An assumption set before any result.

---

## What the data does not contain

- Any real bank, payment, watch-list entry, customer or person.
- A real model's output. The only drafting stand-in is a deterministic stub.
- A held-out period. The kit has no fitted parameter, so nothing was tuned on a subset; the thresholds are design values. If you tune one, evaluate on cases the tuning did not see.
- Evidence that the recorded outcomes are right. They are the generator's idea of a careful worker.

## Using your own data

Replace `cases.csv`, `payments.csv`, `parties_watchlist.csv` and `reason_codes.csv` with exports from your own systems and keep the columns. `human_outcomes.csv` needs your recorded outcomes for the shadow replay. `case_truth.csv` and `fault_schedule.csv` exist only because the data is synthetic; on real exports you build a fault schedule yourself and the by-scenario lines in the step outputs cannot be computed.
