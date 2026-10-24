# 📅 Deprecation Impact: which of your features a model retirement hits

**A vendor writes that a model version retires on a date. I wanted to know which of my features call it, how long each one has to move, and what the move costs. This is a command-line tool: it reads a model catalog, an alias table and a feature register, and prints a retirement calendar, a hit list with a tier per dependency, and a check queue for the strings it cannot resolve.** It takes the idea of a notice date and a successor from [13 SwapBrief](../13-swapbrief-model-migration/) and the shape of a feature register and a price table from [07 InferenceLens](../07-inferencelens-inference-finops/). I read their data files for the logic and wrote my own code and data; nothing is imported and no number is carried over.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 66-deprecation-impact/src && python3 deprecation_impact.py --demo
```

It prints:

```text
as of 2026-09-01: 7 usages read, 5 hit a retiring model, 1 to check, 1 clear
calendar
  2026-10-05  vb-mini@2025-04       34 days  1 feature  12,000 calls/mo  LATE
  2026-11-15  va-fast@2025-03       75 days  2 features  490,000 calls/mo  LATE
  2027-01-20  vb-core@2025-01      141 days  1 feature  60,000 calls/mo  ROOM
  2027-02-25  vc-reason@2025-02    177 days  1 feature  3,000 calls/mo  ROOM
hits
  LATE     dispute-summary fallback on vb-mini@2025-04 retires 2026-10-05 slack -26 days (needs 60)
  TIGHT    dispute-summary primary on va-fast@2025-03 retires 2026-11-15 slack 15 days (needs 60)
  LATE     statement-explainer primary on ft-dispute-v2 retires 2026-11-15 slack -30 days (needs 105) [ft-dispute-v2 is built on va-fast@2025-03]
  ROOM     kyc-doc-reader primary on vb-core@2025-01 retires 2027-01-20 slack 81 days (needs 60) [alias vb-core-stable -> vb-core@2025-01]
  ROOM     statement-explainer judge on vc-reason@2025-02 retires 2027-02-25 slack 103 days (needs 74)
check (a person has to look)
  complaint-classifier primary "va-fast": no snapshot is pinned and the family has retiring snapshot(s) va-fast@2025-03
cost per month on the named successors: $1,424.80 -> $1,545.01 (+$120.21); 1 without a priced successor
decision: LATE
```

Standard library only, Python 3.9 or newer. To check your own files: `python3 deprecation_impact.py report --features features.csv --usages usages.csv --models models.csv --aliases aliases.csv --as-of 2026-09-01`. It exits 1 when the worst tier reaches `--fail-on` (LATE by default), 2 when an input file cannot be read, and `--format json` prints the same result as JSON. The columns each file needs are in the [data README](./data/README.md) and at the top of `src/deprecation_impact.py`.

## What the numbers say

Tags: 🟢 measured by a script in this folder, 🟡 modeled with the assumption named, 🔴 hypothetical.

**What it shows** (🟢 measured on synthetic data: 60 features, 87 true dependencies of which 42 reach a retiring model; the script is named in brackets):

- 🟢 With no feature-to-model map, 7 retirement notices are open and 42 dependencies in 36 of 60 features sit on the models they retire, carrying 11,048,120 calls a month (`step_01`)
- 🟢 Filtering the primary model column for the id in the notice finds 7 of 42 and flags no row that is not affected (`step_02`)
- 🟢 A family-name search over every model string in every role finds 30 of 42, flags 62 rows of which 32 are not affected, and sends a reader to 46 features (`step_03`)
- 🟢 This tool finds and dates 29 of 42, sends 6 more to a check queue and misses 7; none of its 29 hits is a false alarm (`step_04`)
- 🟢 A person opens 35 features instead of 46, and the check queue has 13 entries: 4 proved affected, 6 did not, and 3 are features with no model recorded (`step_04`)
- 🟡 With assumed lead times the 32 hits sort into 1 PAST, 6 LATE, 3 TIGHT, 19 ROOM and 3 SUNSETS. The lead times are 60, 30 and 14 days by criticality, plus 30 with no evaluation set, 14 for a judge and 45 for a fine-tune, with a 30-day margin. Change them and the tiers move
- 🟡 On made-up prices, the dependencies with a priced successor cost $96,964.34 a month now and $82,901.51 on the named successors. Token counts are held fixed except for an assumed input-count factor
- 🔴 Filling the models file from a vendor's own deprecation page is not built and not tested

## What it still gets wrong

- 🟢 7 of the 42 affected dependencies pass with no flag, and `step_04` prints each one. Four are fallback models that no registry row records. Three are features whose alias entry (`va-large-default`) was recorded 12 days before the as-of date and does not match what the vendor serves. The tool trusts a recent alias table. The family-name search finds those three, because it matches the text and not the table.
- 🟢 The check queue is noisy by design: 6 of 13 entries did not need a look. I take that over calling an unknown string clear.
- **The data and the rules share an author.** I planted the dependencies and wrote the resolver, so 29 of 42 shows the rules cover what I planted. I added the hard cases after the first version: neighboring family names, an alias that already points at a live snapshot, a fine-tune on a live base, features that sunset first, and the two misses above. Treat the result as a ceiling for these rules, not a rate on a real register, which I have not tested.
- **The tool reads the registry.** A model chosen at run time from a list kept elsewhere is invisible unless the usage file says what it chooses from. Only three roles exist: primary, fallback and judge. Embedding models, and the cost of re-indexing after a swap, are not modeled.
- **Tiers depend on lead times I assumed.** A real team's lead time depends on its change process, and a vendor can move a retirement date; the tool reads the date in the file.
- **The cost view is a first pass.** It holds output tokens fixed. A successor that writes longer answers costs more than the view says. Fine-tunes have no priced successor because they must be retrained.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does a notice cover when nothing maps models to features? | `step_01_no_map.py` |
| 2 | What does filtering the model column for the id in the notice find? | `step_02_exact_match.py` |
| 3 | Where does each simple lookup fail? | `step_03_deficiencies_exposed.py` |
| 4 | What do resolving, dating and pricing find together? | `step_04_with_map.py` |

Run any of them from `src/`. Data is produced by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. Step 4 writes `src/out/`, which `src/_build_demo.py` turns into `demo.html`.

## Aligned to

Nothing published. I claim no alignment with a standard, regulation or vendor policy. The vendors, model names, notice dates and prices are made up. This is a prototype, not a production case study.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer, bank or real model catalog. A prototype on synthetic data.

## Fork it

Replace `data/models.csv`, `data/aliases.csv`, `data/features.csv` and `data/usages.csv` with exports from your own register and keep the columns, or call `report` on your files directly. Put your own lead times in a JSON file and pass it with `--policy`. Read the [PRD](./PRD.md) for the scope I held to.
