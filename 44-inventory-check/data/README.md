# Data for project 44

Synthetic. Written by `_generate.py` with a fixed seed (`SEED = 44`), so a rerun reproduces every file byte for byte. The generator uses only the Python standard library and one seeded `random.Random`. Nothing here comes from a real inventory, bank, vendor, gateway or employer. System names, owner codes, evaluation references and model ids are invented, and the usage export has the shape I chose for it.

**The truth is separate from the rules.** Each record is built as one case (a clean record, or a clean record with one planted change). The label in `inventory_truth.csv` is the case, not the output of `src/inventory_check.py`. The generator and the checker share two assumptions, the cadence by tier and the as-of date, so their agreement on those holds by construction. The part that is not by construction is whether a field-level or traffic-level rule recognises the planted change.

## Files

| File | What it holds |
|---|---|
| `as_of.txt` | The as-of date, 2026-09-30. Nothing in the project reads the clock |
| `inventory.json` | 100 system records, sorted by `system_id`. Some fields are absent, blank or wrong on purpose |
| `inventory_truth.csv` | Per record: `case_kind`, `truth_class` (defective or clean) and a one-line `detail` of what was planted |
| `usage.csv` | 105 gateway usage rows: `system_id`, `model_id`, `first_seen`, `last_seen`, `calls`. One row per system and model id |
| `shadow_truth.csv` | The 7 systems that call a model without a usable inventory record, and how each hides |
| `example_inventory.json`, `example_usage.csv` | The 6 records and 8 usage rows behind `python3 inventory_check.py --demo` |

## Record fields

Required on every record: `system_id`, `name`, `kind` (generative or agentic), `status` (development, pilot, production or retired), `business_owner`, `technical_owner`, `risk_tier` (1 to 4), `purpose`, `provider_type` (vendor_api or self_hosted), `model_id`, `data_class` (public, internal, confidential or restricted), `customer_facing` (yes or no) and `last_reviewed` (YYYY-MM-DD).

Required by condition: `tools`, `permission_scope` (read_only, read_write or transact) and `human_approval` (none, on_exception or before_action) for an agentic system. For a production system: `evaluation_ref` and `last_evaluated` from tier 2, `independent_review_date` from tier 3, and `fallback_plan` of yes at tier 4. The tiers are the four-step scale of [project 11](../11-tiergate-ai-usecase-intake/), and the evidence that grows with the tier follows its checklist. I did not import it.

## 🟡 Assumptions

None of these comes from a rule. SR 26-2 places generative and agentic AI outside its scope and sets no inventory schema, so the field list and every number below is mine.

| Assumption | Value |
|---|---|
| Longest gap between reviews, and between evaluations, by tier | tier 1: 365 days, tier 2: 270, tier 3: 180, tier 4: 90 |
| A production system unseen in the usage export for longer than this is reported idle | 90 days |
| A retired system seen more recently than this is reported still running | 30 days |
| Placeholder words (whole value only) | tbd, tba, tbc, n/a, na, none, unknown, null, nil, todo, -, --, ?, ??, xxx |

The staleness idea (a date is stale once it is older than a multiple of its cycle) comes from [project 16](../16-controlmap-ai-obligation-crosswalk/), which uses 1.5 times the test cycle. Here the cadence is the limit itself.

## The 100 records, by case

Defective (57): missing_required 6, invalid_value 5, placeholder_known 4, agent_gap 5, evidence_gap 6, misclassified_kind 3 (a generative record that lists tools), review_overdue 6, evaluation_overdue 4, model_changed 5, retired_running 3, listed_no_traffic 4, and two kinds the rules are expected to miss: placeholder_novel 3 (a placeholder the word list does not hold) and rubber_stamp 3 (a review date refreshed in bulk four days before the as-of date, with the last real review long before).

Clean (43), 27 of them built to look wrong: boundary_review_age 3 and boundary_eval_age 2 (exactly on the cadence), case_only_model_id 3, model_migrated_recorded 4 (traffic moved to a new model and the record says so), pre_production_no_evidence 4 (a pilot or development system at tier 3 or 4 with no evaluation yet), retired_old_traffic 4 (retired, last traffic 31 or more days ago, old review date), idle_boundary 2 (production, last traffic exactly 90 days ago), placeholder_in_sentence 3 (a purpose sentence that contains the word unknown or none), and seasonal_quiet 2 (a production process that runs once a quarter and has been quiet for 100 to 200 days). The 16 plain clean records make up the rest. seasonal_quiet is a false alarm the rules cannot avoid, and it stays in on purpose.

Every record has exactly one case. The case decides the status, the tier and the usage rows, so a record planted as `retired_running` is retired and has traffic in the last 30 days.

## The usage export and the shadow systems

`usage.csv` holds one row per listed system and model id. A system that moved models has two rows. It also holds the shadow traffic in `shadow_truth.csv`:

| How it hides | Count | Visible to the checker? |
|---|---|---|
| Under its own name, which no record carries | 4 | Yes, by `system_id` |
| With a blank `system_id` | 1 | Reported as untagged traffic, not attributed to a system |
| Under a listed production system's id, on the same model id | 2 | No. Its calls are added to that system's row |

## What this data does not do

- It does not model real inventories. Real fields are free text, copied between sheets, and wrong in ways nobody planted.
- Every defect is single. A real record can be stale, incomplete and mislabelled at once.
- The usage export is complete and well formed. A real gateway drops calls, logs model aliases and shares keys.
- Owners are codes. Whether an owner still works at the bank is not in the data and not in the checks.

## How the files map to the steps

| Step | Reads |
|---|---|
| 1 | `inventory.json`, `usage.csv`, `inventory_truth.csv`, `shadow_truth.csv` |
| 2 | `inventory.json`, `inventory_truth.csv` |
| 3 | all of the above |
| 4 | all of the above; writes `src/out/` for the demo |
