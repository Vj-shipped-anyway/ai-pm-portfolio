# 🌱 plant (synthetic data with answer keys): plant the failure, keep the key

**I could not say how good a checker was, because the test data never recorded what was wrong with it. plant is a command-line tool: you give it a seed and a list of behaviors to plant, and it writes the data, a separate answer key and a manifest, then scores whatever a checker flags against the key, behavior by behavior.** It turns the `_generate.py` pattern I used in earlier projects, for example [28 Tool Schema Drift](../28-tool-schema-drift/), into one tool you point at a spec.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 58-plant/src && python3 plant.py --demo
```

It prints:

```text
spec demo seed 58: 644 rows, 7 behaviors, 114 rows in the answer key, data sha256 b2534df4
naive checker flagged 126 rows: found 71 of 84 planted failures, flagged 29 of 30 planted look-alikes and 26 of 530 clean rows
weakest behavior: memo_injection_paraphrase, found 0 of 12
```

Standard library only, Python 3.9 or newer. To plant your own: `python3 plant.py generate spec.json --out out` writes `NAME_data.csv`, `NAME_truth.csv` and `NAME_manifest.json`. To score a checker: `python3 plant.py score out/NAME flags.csv --min-recall 0.9`, where `flags.csv` has a `row_id` column. It exits 1 when any failure behavior is found less often than that, and 2 when it cannot use the input.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: five test files corrupted the usual way, and one file planted by the tool; the script is named in brackets):

- 🟢 With no key, five test files give 91 to 120 flags from the naive rules and 69 to 89 from the tuned ones, and 508 rows to read by hand to learn which naive flags are right (`step_01`)
- 🟢 With an is_bad column, pooled over the five files: naive recall 0.88 and precision 0.70, tuned recall 0.89 and precision 0.92 (`step_02`)
- 🟢 The same column hides that the tuned rules find 0 of 50 paraphrased injections, that 9 rows carry two failures and in 3 of them one failure is credited without being found, and that a checker reading the column scores recall 1.00. Recall moves between 0.84 and 0.92 from file to file (`step_03`)
- 🟢 With a planted key (644 rows, 114 in the key: 84 failures and 30 look-alikes), the naive rules find 71 of 84 failures, flag 29 of 30 look-alikes and 26 of 530 clean rows, precision 0.56. The tuned rules find 72 of 84, flag 0 of 30 and 8 of 530, precision 0.90 (`step_04`)
- 🟢 Take the look-alikes out of the file and naive precision goes from 0.56 to 0.73. The is_bad column had no look-alikes to count (`step_04`)
- 🟢 The same spec under seeds 58 to 62 plants 84 failures each time. Tuned recall stays at 0.86 and naive recall runs 0.83 to 0.87 (`step_04`)

🟡 Modeled: the amount range per merchant, the merchant weights, the ceilings in the checker and the count per behavior are my assumptions about a small card ledger. None comes from a bank.

🔴 Hypothetical: that a team evaluating a real model would see the same gap between a boolean column and a keyed file. I have not tested that.

## What it still gets wrong

- 🟢 The tuned rules miss all 12 paraphrased injections. plant makes the miss visible; it does not close it (`step_04`)
- 🟢 The key scores the variants I planted. The paraphrase behavior uses 3 sentences, and a checker that only memorizes them finds 12 of 12 (`step_04`). Variants should come from someone other than the checker's author, and mine do not.
- **The data and the rules share an author.** I wrote the spec and both rule sets, and I set the utilities ceiling a little low on purpose so the key had a false alarm to find. Treat every score here as a ceiling for these rules, not a rate on a real ledger, which I have not tested.
- plant keeps planted rows apart: one behavior per row. In the corrupted files 9 rows carried two failures, and that is where credit gets muddy (`step_03`). plant cannot test it.
- Scoring is by row. A checker that flags the right row for the wrong reason gets full credit; the `rules` column in a flags file is ignored. The planted row of a duplicate is the copy, so a checker that flags the original gets a miss and a false alarm.
- Look-alikes are only as hard as I wrote them. My repeat purchase differs from a duplicate by its reference. A real repeat may not.
- Few building blocks: column kinds sequence, choice, int_range, int_offset and by_column; operations scale, shift, set, append and duplicate. No time series, no free-text synthesis beyond lists you supply, no joins.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What can you say about a checker when the test data has no record of what was added? | `step_01_no_key.py` |
| 2 | What does a single is_bad column buy? | `step_02_is_bad_column.py` |
| 3 | What does that column hide? | `step_03_what_it_hides.py` |
| 4 | What changes when the key is a separate file with roles and exact counts? | `step_04_with_a_key.py` |

Run any of them from `src/`. Data is written by [`data/_generate.py`](./data/README.md), which calls the tool on `data/demo_spec.json`; the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The stand-in checker lives in `src/_ledger_rules.py`; it is a prop, not the product.

## Aligned to

Nothing. I claim no alignment to a standard or a regulation. This is a prototype.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Merchants are generic categories, not companies. Nothing comes from any employer, customer or real bank. A prototype on synthetic data, not a production case study.

## Fork it

Write a spec: a name, a seed, a row count, columns, and behaviors. Each behavior has an id, a role (`positive` for a failure, `negative` for a look-alike), an exact count and one or more operations.

```json
{"name": "mine", "seed": 7, "rows": 200,
 "columns": [{"name": "kind", "kind": "choice", "values": ["a", "b"]},
             {"name": "amount", "kind": "by_column", "of": "kind", "ranges": {"a": [1, 9], "b": [10, 99]}}],
 "behaviors": [{"id": "cents", "role": "positive", "count": 10, "ops": [{"op": "scale", "column": "amount", "factor": 100}]}]}
```

Run `generate`, point your checker at `mine_data.csv`, write the row ids it flags to a CSV, and run `score`. Bad specs exit 2 with a one-line reason. Read the [PRD](./PRD.md) for the scope I held to.
