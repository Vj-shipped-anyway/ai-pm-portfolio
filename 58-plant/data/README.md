# Data for project 58

Synthetic. Written by `_generate.py`, which runs the tool (`src/plant.py`) on `demo_spec.json`. Every draw comes from the seed in the spec, so a rerun reproduces every file byte for byte. Nothing here comes from a real ledger, bank or employer. Merchants are generic categories.

| File | What it holds |
|---|---|
| `demo_spec.json` | The input: seed 58, 600 base rows, 7 columns, 7 planted behaviors |
| `demo_data.csv` | 644 rows (600 base rows plus 44 inserted copies). Columns: `row_id`, `ref`, `account_id`, `merchant`, `day`, `posted_day`, `amount`, `memo`. No label column |
| `demo_truth.csv` | The answer key: 114 rows. `row_id`, `behavior`, `role` (positive or negative), `effect` (the change, without the data), `detail` (before and after), `source_row_id` (the original, for a copy). A row that is not listed is clean by construction |
| `demo_manifest.json` | Seed, row counts, a hash of the spec, of the data and of the key, and the count and number of distinct effects per behavior |
| `demo_flags_naive.csv` | The rows the naive stand-in checker flags (`row_id`, `rules`), the format `plant.py score` reads |

Planted behaviors (counts are exact): `duplicate_posting` 24, `amount_in_cents` 18, `posted_before_purchase` 16, `memo_injection_plain` 14, `memo_injection_paraphrase` 12 (all five are failures, 84 rows); `repeat_purchase_new_ref` 20 and `memo_ignore_previous_legit` 10 (look-alikes, 30 rows). Planted rows never overlap. The copy of a duplicate is the planted row and sits directly after its source.

The two look-alikes are hard on purpose: the repeat purchase matches a duplicate on account, merchant, amount and day and differs by its reference, and the legitimate memos use the words a naive injection rule looks for.

🟡 Assumptions, mine and not taken from any source: the amount range per merchant (grocery 20 to 180, fuel 25 to 90, pharmacy 5 to 60, transit 2 to 30, utilities 40 to 220, rent 900 to 2200), the merchant weights, a posting lag of 0 to 2 days, and the count per behavior.

Regenerate: `cd data && python3 _generate.py`.
