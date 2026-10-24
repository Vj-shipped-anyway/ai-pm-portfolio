# Data for project 36

Synthetic. Produced by `_generate.py` with a fixed seed (`SEED = 36`), so a rerun reproduces every file byte for byte (`tests/test_data.py` and `tools/check_repo.py` both check it). Nothing here comes from a real bank, customer, payment system or employer. Company names are invented from syllables. BICs are invented four-letter codes joined to real country codes, so a coincidence with a live BIC is possible but not intended. IBANs are IBAN-shaped strings (two letters, two digits, an eight-digit bank code, ten digits); the two check digits are arbitrary, so almost none is a valid IBAN. Bank codes sit at positions 5 to 12 in every country here, which real IBANs do not do.

**How the answer key is made.** Each message is built complete, then one named recipe removes or overwrites fields. The true value of every damaged field is the value the generator took out, written to `defects_truth.csv`. The rules in `src/payment_repair.py` never see that file. The intended route per recipe (`message_truth.csv`) is my policy written down a second time, by the same person who wrote the rules, so route agreement is a ceiling and not a rate on real traffic.

**The message shape is pacs.008-style.** One credit transfer per message, flattened to dotted paths named after the pacs.008 elements (for example `CdtTrfTxInf.Cdtr.Nm`, and `CdtTrfTxInf.IntrBkSttlmAmt@Ccy` for the currency attribute). I could not read the ISO 20022 text (the ISO site refused the fetch on 2026-10-23), so the set is not validated against the schema. 🟡 Which fields count as required, and the shape checks on BIC, IBAN, currency, charge bearer and UETR, are assumptions of this project's rule table.

| File | What it holds |
|---|---|
| `messages.json` | 500 messages as a JSON list; each maps a path to a string; a missing field is an absent key or an empty string |
| `message_truth.csv` | `msg_id`, `recipe`, `intended_route` (PASS, REPAIRED, HOLD or RETURN), `hardness` (plain, hard_negative, trap or known_miss) |
| `defects_truth.csv` | one row per damaged field: `msg_id`, `path`, `kind` (missing, blank, placeholder, malformed, wrong), `true_value`, `source_available` (where the true value could be found: message, directory, master, order, iban_prefix, book or none) |
| `bic_directory.csv` | the bank directory snapshot the tool reads: `country`, `bank_code`, `bic`, `status` (active or retired) |
| `customer_master.csv` | the bank's own customers, one row per account holder: `iban`, `customer_id`, `name`, `account_ccy`, `status` |
| `payment_orders.csv` | the originating orders: `end_to_end_id`, `uetr`, `charge_bearer`, `initiator_id` (who entered the order) |
| `beneficiary_book.csv` | a saved payee list, read only by the basic script in step 2 and never by the tool |
| `approvers.csv` | the approver registry: `approver_id`, `kind` (person, agent, service), `role`, `active` |
| `example_messages.json` | three messages behind `python3 payment_repair.py --demo` |

Planted recipes (500 messages). The directory snapshot is derived from the true banks and then spoiled on purpose: some bank codes have two active BICs, some only a retired row, some no row, and two still list an old BIC as active.

| Recipe | Messages | Intended route | Hardness | What it plants |
|---|---|---|---|---|
| `clean` | 100 | PASS | plain | Complete; both optional fields present. |
| `optional_absent` | 30 | PASS | hard_negative | Complete; purpose code and remittance text missing in one or both. Nothing to repair. |
| `lookalike_name` | 8 | PASS | hard_negative | Creditor name contains a placeholder word ("Unknown Pleasures Trading Ltd", "N/A Logistics GmbH"). A real name. |
| `bic8_valid` | 6 | PASS | hard_negative | Creditor BIC given as 8 characters, a valid form. |
| `nbtxs_missing` | 24 | REPAIRED | plain | Number of transactions absent or blank. Derivable from the message. |
| `dbtr_bic_missing` | 36 | REPAIRED | plain | Debtor agent BIC absent or blank. The bank directory has one active row. |
| `dbtr_name_missing` | 30 | REPAIRED | plain | Debtor name absent or blank. The customer master has one holder. |
| `dbtr_name_joint` | 8 | RETURN | trap | Debtor name absent on a joint account (two holders in the master). |
| `cdtr_bic_missing` | 40 | HOLD | plain | Creditor agent BIC absent or blank. One active directory row. |
| `cdtr_bic_malformed` | 8 | HOLD | plain | Creditor agent BIC truncated, lower-case or with a trailing space. |
| `cdtr_bic_ambiguous` | 10 | RETURN | trap | Creditor agent BIC missing; the bank code has two active BICs. |
| `cdtr_bic_retired` | 6 | RETURN | trap | Creditor agent BIC missing; the directory holds only a retired row. |
| `cdtr_bic_no_row` | 6 | RETURN | trap | Creditor agent BIC missing; the bank code is not in the directory. |
| `cdtr_bic_stale` | 5 | HOLD | known_miss | Creditor agent BIC missing; the directory still lists the bank's old BIC as active. Known miss. |
| `cdtr_ctry_missing` | 24 | HOLD | plain | Creditor country absent or blank. The IBAN prefix gives the true value. |
| `cdtr_ctry_foreign` | 4 | HOLD | known_miss | Creditor country missing; the creditor lives outside the IBAN country. Known miss. |
| `uetr_missing_order` | 20 | HOLD | plain | UETR missing; one payment order carries it. |
| `uetr_missing_no_order` | 6 | RETURN | trap | UETR missing; no payment order exists. |
| `chrgbr_missing_order` | 14 | HOLD | plain | Charge bearer missing; one payment order carries it. |
| `chrgbr_missing_no_order` | 5 | RETURN | trap | Charge bearer missing; no payment order exists. |
| `ccy_missing` | 24 | RETURN | trap | Currency missing; in 10 of 24 it differs from the debit account's currency. |
| `amount_missing` | 10 | RETURN | plain | Amount absent, blank or 0.00. |
| `cdtr_name_missing_book` | 13 | RETURN | trap | Creditor name missing; the saved payee list holds the true name. |
| `cdtr_name_missing_stale_book` | 5 | RETURN | trap | Creditor name missing; the saved payee list holds an old name for that IBAN. |
| `cdtr_name_missing_no_book` | 6 | RETURN | plain | Creditor name missing; nobody holds it. |
| `cdtr_name_placeholder` | 14 | RETURN | trap | Creditor name is N/A, spaces, NOTPROVIDED, UNKNOWN, a dash or TBD. |
| `cdtr_iban_missing` | 8 | RETURN | plain | Creditor IBAN absent or blank. |
| `two_holds` | 10 | HOLD | plain | Creditor agent BIC and creditor country both missing: one plan, two changes. |
| `auto_and_return` | 8 | RETURN | trap | Number of transactions and currency both missing: an AUTO repair next to a refusal. |
| `bic_present_wrong` | 12 | HOLD | known_miss | Creditor BIC present, well-formed, and from a different bank. Known miss. |

Hard negatives look like damage and are not. Traps give a table answer that looks usable. Known misses are the ones the rules cannot see; step 3 and step 4 print them.
