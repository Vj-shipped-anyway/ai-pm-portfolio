# 🧾 feature-contract (schema check): a data contract for model inputs

**I wanted to know how much of a changed model input a header and type check lets through, and what a contract with type, range and null checks stops before the model scores the batch. This is a command-line gate and a staged GitHub Action: you write a contract for a feature table, it checks each delivery of data against it and prints PASS, WARN or FAIL.** It follows the strict validator and the exit-code convention of [28 Tool Schema Drift](../28-tool-schema-drift/), moves the schema-gate idea of [15 SchemaWatch](../15-schemawatch-tool-schema-drift/) from tool inputs to model inputs, and leaves distribution monitoring to [02 DriftSentinel](../02-driftsentinel-model-drift-monitoring/).

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 53-feature-contract/src && python3 feature_contract.py --demo
```

It prints:

```text
contract: credit_triage_features 1.0.0   batch: 100 rows, 7 columns
  [FAIL] above_max         dti_ratio            100 of 100 values (100.0%) are above the maximum 1.5; first seen '64.51'; allowed 2.0%
decision: FAIL
```

The ratio of debt to income started arriving as a percent. The column name and the type did not change, so a header and type check passes it. Standard library only, Python 3.9 or newer. To check your own files: `python3 feature_contract.py check contract.json batch.csv`. It exits 1 on FAIL, so a CI step fails; `--format github` prints annotations; a `.jsonl` batch is checked with its JSON types.

## The contract

One JSON file per feature table. Per field: `type` (string, integer, number, boolean), `min` and `max` (inclusive), `allowed` values, `max_null_rate`, and a `unit` for the reader. Per file: `max_bad_rate`, the share of rows that may break a type, range or allowed-values rule before the field fails, and `unexpected_columns` (allow, warn or fail). Unknown keys are rejected, so a misspelt `maximum` cannot become a check that does nothing. See [`data/contract_credit_triage.json`](./data/contract_credit_triage.json).

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 90 planted deliveries of 100 rows from three feeds; the script is named in brackets):

- 🟢 No input check: 0 of 90 batches stopped, 47 of 90 carry a changed field, and 3,323 of the 4,700 rows in those 47 hold a changed value (`step_01`)
- 🟢 A header and type check stops 16 of 47 bad batches and blocks 14 of 43 harmless ones, so 46.7% of its blocks are harmless (`step_02`)
- 🟢 The structure layer alone stops 16 of 47 and blocks 0 of 43. The value layer alone, with zero tolerance, stops 22 of 47 and blocks 5 of 43; with a 2.0% tolerance it stops 21 of 47 and blocks 0 of 43 (`step_03`)
- 🟢 Structure and values together: 37 of 47 bad batches stopped, 0 of 43 harmless blocked, 5 of 43 warned. A person reads 42 of 90 batches (37 failures and 5 warnings); the step 2 check blocked 30 (`step_04`)

## What it still gets wrong

- 🟢 Ten of the 47 bad batches pass (`step_04` prints each one): null_zero_fill 3, unit_in_range 5 and unit_cents 2. A zero-fill replaces missing values with 0, which is inside every range, so an outage turns into a valid-looking value. Days become weeks and months become years under the same column name, and the new numbers still sit inside the declared range. This is the known limit: a change that stays inside the declared type, range and null rate is not seen.
- 🟢 The two unit_cents misses are both on `txn_total_30d_usd`, whose declared maximum (10,000,000) is wide enough to hold the values multiplied by 100. A range that can hold the wrong scale cannot see it. Zero tolerance stops one more batch (22 against 21 in `step_03`), a cents change in which a single value left the range, and costs the 5 harmless batches with isolated bad rows.
- **The test set and the checker share an author.** I planted the changes and wrote the contracts, and I chose the hard cases on purpose, so 37 of 47 shows the rules cover what I planted. Treat it as a ceiling for these rules, not a rate on real feeds, which I have not tested.
- 🟡 The 2.0% tolerance for isolated bad rows and the 5.0% null allowance on four fields are my assumptions, not taken from any rule. The five harmless batches with one or two bad rows are harmless only under that tolerance; a stricter team would label them differently.
- 🔴 That a real feed changes in these ways, at these shares, is hypothetical. The eleven kinds of change are ones I think a feed can make; I have no log of real ones.
- No distribution check: a shift inside the range is the job of a monitor such as [02](../02-driftsentinel-model-drift-monitoring/), and I make no claim about how many of the ten it would catch.
- A null is an empty cell or a JSON null. "NA" or "null" in a numeric column is reported as a type mismatch. There is no row-count check, so a clean delivery of one row passes. Not supported: dates, patterns, cross-field rules, uniqueness, freshness.
- The contract is written by hand. There is no command that drafts one from a reference batch.

## Use it in CI

[`action/`](./action/README.md) holds a staged GitHub Action and the steps to publish it from its own repository, which a Marketplace listing requires. It has not been published and has not run on GitHub. What is tested is the command it wraps (`tests/test_cli.py`; 74 tests in all).

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What reaches the model when nothing checks the data? | `step_01_no_check.py` |
| 2 | What does a header and type check stop, and what does it block for no reason? | `step_02_header_and_type.py` |
| 3 | Where does each part of the contract fail alone? | `step_03_deficiencies_exposed.py` |
| 4 | What do structure and values catch together? | `step_04_with_contract.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

Nothing. I claim no alignment to a standard or a regulation, and I did not read a source to cite. A data contract is a working pattern, and this is a prototype.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real bank. The generator keeps the process that draws the values apart from the contracts that check them, and the truth label of each batch is the change that was planted. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/contract_*.json` for the contract of one of your own feature tables and point `check` at a sample export, or skip the data and check a file from your pipeline. Read the [PRD](./PRD.md) for the scope I held to.
