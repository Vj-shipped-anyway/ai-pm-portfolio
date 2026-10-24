# 📋 Inventory Check: completeness, staleness and coverage tests for an inventory of generative and agentic systems

**I wanted to know whether the inventory of a bank's generative and agentic systems can be tested the way code is tested, because the current federal model risk guidance places those systems outside its scope. This is a command-line tool and a staged agent skill: it reads an inventory file and, if you have one, a model-gateway usage export, and prints PASS, REVIEW or FAIL with the finding behind each.** It takes its risk tiers and evidence-by-tier idea from [11 TierGate](../11-tiergate-ai-usecase-intake/), its stale-evidence idea from [16 ControlMap](../16-controlmap-ai-obligation-crosswalk/) and its command-line shape from [28 Tool Schema Drift](../28-tool-schema-drift/). I read their data and wrote my own code.

**▶ Static demo, no install:** [open demo.html](./demo.html)

Tags: 🟢 measured (a script in this folder prints the number), 🟡 modeled (the assumption is named), 🔴 hypothetical.

## Run one now

```bash
cd 44-inventory-check/src && python3 inventory_check.py --demo
```

It prints:

```text
inventory: 6 systems as of 2026-09-30; 8 usage rows
  [fail  ] AI-902             agent_field_missing    agentic system lists no `tools`, so what it can do cannot be reviewed
  [review] AI-903             review_overdue         last reviewed 2025-11-02 (332 days ago); tier 3 cadence is 180 days
  [review] AI-904             model_changed          traffic last seen 2026-09-27 ran on vendor-a-small-2026-08; the record says vendor-a-small-2026-03
  [fail  ] AI-905             placeholder_value      `technical_owner` is TBD, a placeholder and not a value
  [fail  ] scratch-notes-bot  unregistered_system    scratch-notes-bot made 412 calls from 2026-07-14 to 2026-09-28 and has no inventory record
decision: FAIL (3 fail, 2 review)
```

Standard library only, Python 3.9 or newer. To check your own files: `python3 inventory_check.py check inventory.json --usage usage.csv --as-of 2026-09-30`. It exits 1 on FAIL, so a CI step fails; `--fail-on review` is stricter and `--format github` prints annotations. Without `--as-of` it measures age from today's date, so pass one when you want a repeatable result. Without `--usage` it says which tests did not run.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 100 planted inventory records and 105 usage rows; the script is named in brackets):

- 🟢 With no tests on the inventory, 57 of 100 records are defective, 21 of the 35 production records at tier 3 or 4 among them, and 0 are flagged for a reviewer (`step_01`)
- 🟢 Seven shadow systems carry 85916 of 4167034 calls in the usage export, 2.1% of the traffic (`step_01`)
- 🟢 The common check, a blank-cell filter plus one 365-day review limit, flags 10 of 100 records, finds 8 of 57 defects, and 2 of its flags are harmless (`step_02`)
- 🟢 Completeness tests alone find 29 of 57 defective records, staleness and coverage alone find 22 of 57, and without the usage file the tool finds 39 of 57 (`step_03`)
- 🟢 Requiring every one of 20 columns on every row flags 41 of 43 clean records, because generative systems have no tools to list (`step_03`)
- 🟢 All three tests together flag 51 of 57 defective records and 2 of 43 clean ones, leave 25 of 27 look-alike clean records alone, and send a person to 53 of 100 records instead of all 100 (`step_04`)
- 🟢 The usage export names 4 of the 7 shadow systems, and reports the traffic with no system id without attributing it (`step_04`)

**What I assumed** (🟡 modeled, in [`data/README.md`](./data/README.md)): the longest gap between reviews by tier (365, 270, 180 and 90 days), the idle window for a production system (90 days) and the quiet window for a retired one (30 days). None of them comes from a rule.

## What it still gets wrong

- 🟢 Six of the 57 defective records pass (`step_04` prints each one). Three carry a placeholder the word list does not hold, such as "see wiki". Three carry a review date refreshed in bulk, which looks current and is not.
- 🟢 Two of the 43 clean records are flagged: production processes that run once a quarter look idle. Nothing in the record says so, so the idle test cannot know (`step_03`, `step_04`).
- 🟢 Three of the 7 shadow systems stay unnamed: one sends calls with no system id and two send theirs under a listed system's id on the same model (`step_03`).
- **The test set and the rules share an author.** I planted the changes and wrote the tests, so 51 of 57 shows the rules cover what I planted. The set includes cases built to be missed and cases built to look wrong, and I kept the quarterly false alarm in on purpose. Treat the result as a ceiling for these rules, not a rate on a real inventory, which I have not tested.
- A PASS means the record passed these rules. It does not mean the inventory is right. The tool cannot tell whether a named owner still works at the bank, whether a purpose statement is true, or whether a model id in the export is the one the vendor actually served.
- The usage tests need a gateway that logs a system id and a model id on every call, and the same ids in the inventory. When no usage row matches an inventory id, the tool says so.
- The inventory is read as JSON, and enum values are case-sensitive. The field list is mine.
- 🔴 Hypothetical: a real inventory has messier fields than this set, and the share of defects the tests find there will be lower. I have not run it on one.

## Use it as a skill

[`skill/inventory-check/SKILL.md`](./skill/inventory-check/SKILL.md) is a staged Agent Skill that tells an agent how to run the command, how to read the exit status, how to report findings by test and what to say it cannot see. It has not been installed or run inside an agent harness. What is tested is the command it wraps and the skill's frontmatter (`tests/test_skill.py`, 81 tests in all).

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What is wrong in an inventory nobody tests? | `step_01_no_test.py` |
| 2 | What does a blank-cell check with one review limit catch? | `step_02_blank_cells.py` |
| 3 | Where does each part fail alone, and what does a stricter sheet cost? | `step_03_deficiencies_exposed.py` |
| 4 | What do completeness, staleness and coverage catch together? | `step_04_with_checks.py` |

Run any of them from `src/`. Data is written by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. Read the [PRD](./PRD.md) for the scope I held to.

## Aligned to

[SR 26-2, Revised Guidance on Model Risk Management](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm) (Federal Reserve, OCC and FDIC, April 17, 2026). I read the letter and its attached guidance ([PDF](https://www.federalreserve.gov/supervisionreg/srletters/SR2602a1.pdf)) on 2026-10-23, and took two things from them. Footnote 3 says generative AI and agentic AI models are not within the scope of the guidance, and says a bank's own risk management and governance practices should guide the controls for them. The Model Inventory section says an effective inventory holds enough information to understand model risk for each model and in aggregate, and in that section it names no required fields and no review frequency. So this project is a design for a bank's own practice on the systems the guidance leaves out. I did not map it clause by clause.

It is a prototype, aligned to that reading and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real bank, and every system name, owner code and model id is invented. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/inventory.json` and `data/usage.csv` for your own exports and keep the field names, or skip the data and point `check` at two files from your own estate. If your inventory lives in a spreadsheet, export it to a JSON list with one object per system; list fields such as `tools` become JSON arrays. Change the cadence by editing `CADENCE_DAYS` at the top of `src/inventory_check.py` (and the same table in `data/_generate.py` if you rewrite the data), and say so wherever you quote a result.
