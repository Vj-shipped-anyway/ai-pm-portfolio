# 🧾 swapbrief: a go or no-go brief for a model migration, from two files

**A vendor retires the model behind a production feature. The successor scores higher on the team's evaluation set, so the team moves. I wanted one command that reads the evaluation results and the price table and says what the average does not: what a correct answer now costs, how bad the slow tail is, which slice fell, and what to write down as a rollback trigger before launch.** This is a command-line tool with a fixed two-file input contract. It extends [13 SwapBrief](../13-swapbrief-model-migration/), which walks the same idea through four scripts and a Streamlit app; here the idea is a tool you can point at your own export.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 47-swapbrief/src && python3 swapbrief.py --demo
```

It prints:

```text
swapbrief: incumbent -> successor   600 paired items, 6 slices
  accuracy          81.8% -> 85.3%   +3.5 pp   interval +0.3 to +7.0 pp   the average says GO
  cost per correct  $0.00572 -> $0.00780   1.36x   interval 1.31x to 1.42x   BLOCK
  p95 latency       4889 ms -> 8853 ms   1.81x   interval 1.50x to 2.57x   BLOCK   (p50 0.96x)
  slices            1 inconclusive, 4 ok, 1 improved
    account_closure (40 items): +5.0 pp, interval -7.6 to +17.6 pp   INCONCLUSIVE
decision: NO-GO
  because: cost per correct answer is at least 1.25x the baseline at the interval's lower bound (1.31x)
  because: p95 latency is at least 1.50x the baseline at the interval's lower bound (1.50x)
rollback triggers (write these down before launch):
  - cost per correct answer >= 1.25x baseline over 24 hours: send traffic back to the baseline
  - p95 latency >= 1.50x baseline over 1 hour, 3 windows in a row: send traffic back to the baseline
```

Standard library only, Python 3.9 or newer. For your own files:

```bash
python3 swapbrief.py brief results.csv prices.csv --baseline current-model --candidate successor-model \
    --critical card_disputes,wire_exceptions
```

It exits 0 for GO and GO WITH GUARDRAILS, 1 for NO-GO (`--fail-on guardrails` also fails on guardrails, `--fail-on never` never fails) and 2 for input it cannot use. `--format json` prints the whole brief as JSON.

## The two-file input contract

The tool reads exactly two files. Both are UTF-8 CSV with a header row. Columns are matched by name, so order does not matter and extra columns are ignored.

**`results.csv`**: one row per (item, system).

| Column | Type | Meaning |
|---|---|---|
| `item_id` | text, not empty | The evaluation item. Every item must appear once for the baseline and once for the candidate. |
| `slice` | text, not empty | The group the item belongs to. It must be the same for both systems of an item. |
| `system` | text | Which model and prompt produced the row. Matched by exact text to `--baseline` and `--candidate`. Rows of any other system are ignored, and the brief says how many. |
| `correct` | `0` or `1` | The grade from your own evaluation harness. The tool does not judge answers. |
| `input_tokens`, `output_tokens` | whole number, 0 or more | Tokens billed for the call. |
| `latency_ms` | number above 0 | Time to the full answer, in milliseconds. |

**`prices.csv`**: one row per system.

| Column | Type | Meaning |
|---|---|---|
| `system` | text | Same text as in `results.csv`. A system with two rows is an error. |
| `input_usd_per_1k`, `output_usd_per_1k` | number, 0 or more | Price per 1,000 tokens. Both zero for one system is an error: cost per correct answer would be undefined. |

What it refuses, with exit status 2 and one line on stderr: an empty file, a header with no rows, a missing column, a row with too few or too many fields, a value of the wrong type, a duplicate (item, system) row, an item that is missing for one of the two systems, an item whose slice differs between systems, a system name that matches no row, fewer than 30 paired items, a system with fewer than 5 correct answers, and a `--critical` slice that does not exist. Names taken from your files are escaped (`%` to `%25`, carriage return to `%0D`, newline to `%0A`) before they reach a log line or a workflow command.

To compare more than two systems, run it once per pair; the file can hold all of them. To compare model B under the old prompt and under a retuned prompt, give each its own `system` value.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: one committed set of 600 paired items and 80 simulated migrations with planted problems; the script is named in brackets):

- 🟢 On the committed set the headline average says GO: accuracy 81.8% to 85.3%, +3.5 pp (`step_01_headline_average.py`). A vendor-sheet check says GO too: list price per token 0.85x, median latency 0.96x (`step_02_average_plus_vendor_sheet.py`)
- 🟢 Cost per correct answer on the same set is 1.36x (interval 1.31x to 1.42x) and p95 latency is 1.81x (interval 1.50x to 2.57x). swapbrief says NO-GO and writes 2 rollback triggers (`step_04_with_swapbrief.py`)
- 🟢 Across 80 simulated migrations, 45 carry a real problem. A migration with a real problem gets GO from the headline average 41 of 45 times (91.1%), from the average plus the vendor sheet 36 of 45 (80.0%), and from swapbrief 2 of 45 (4.4%) (`step_01_headline_average.py`, `step_02_average_plus_vendor_sheet.py`, `step_04_with_swapbrief.py`)
- 🟢 Of the migrations with a real cost problem, 0 of 26 lacked a cost flag; of those with a real p95 problem, 1 of 11 lacked a p95 flag (`step_04_with_swapbrief.py`)
- 🟢 One sample is a noisy witness: across 20 fresh samples of the committed world the p95 ratio runs from 1.57x to 2.80x, so a single p95 number is not a finding (`step_03_deficiencies_exposed.py`)
- 🟢 The cost of caution: 0 of 35 good migrations were stopped, and 19 of 35 (54.3%) got GO WITH GUARDRAILS, 14 of them because a critical slice was too thin to rule a loss out. Of 8 planted good migrations whose true cost per correct answer sits just under the line (1.06x to 1.09x), 7 got guardrails (`step_04_with_swapbrief.py`)

## What it still gets wrong

- 🟢 Known limit, left in on purpose: 4 of 26 true slice regressions pass unflagged (`step_04_with_swapbrief.py` prints each). In scenario 7 (`card_disputes`, 98 items) the planted change is -11.7 pp, the sample shows -4.1 pp and the interval runs -12.2 to +4.1 pp. Scenario 74 (`fee_waivers`, 110 items) is the same story: planted -7.0 pp, sample -2.7 pp. Scenarios 15 and 55 are planted hard misses, a real fall in the 30-item `account_closure` slice: the samples show +20.0 pp and +10.0 pp, and in scenario 15 the interval (+6.7 to +33.3 pp) sits wholly above zero.
- 🟢 2 migrations with a real problem still get GO: scenarios 5 and 74. Of 8 planted hard misses, 1 got GO and 7 got guardrails.
- 🟢 1 of 11 real p95 problems gets no p95 flag. p95 needs a lot of items: the p95 interval on a few hundred calls is wide (the committed set's interval runs from 1.50x to 2.57x).
- **The data and the rules share an author.** I planted the problems and I wrote the thresholds, so 2 of 45 is a ceiling for these rules on worlds I defined, not a rate on a real migration. The mix of worlds (how often a slice regresses, how verbose the successor is, how often it hits a slow path) is my assumption. I changed two generator settings after a first look at the results, the size of the slow-path spike and the range of evaluation sizes, and then kept the seeds. The hard cases are planted on a schedule (every fifth scenario), which makes them more common than they would be by chance.
- 🟡 The thresholds are assumptions copied from [13 SwapBrief](../13-swapbrief-model-migration/data/policy.csv), not taken from any rule: a slice tolerance of 5 pp, cost per correct answer watched at 1.05x and blocking at 1.25x, p95 watched at 1.10x and blocking at 1.50x, a 95% interval, and the rollback windows (24 hours, 1 hour three times in a row, 7 days). Change them for your feature; `--tolerance-pp` is the only one on the command line.
- 🟡 "A real problem" in the simulation means a slice down 5 pp or more, cost per correct answer up 10% or more, or p95 up 25% or more in the true world. Those levels are mine.
- The headline rule here is "accuracy not lower". A team that requires a margin would behave differently; I did not test that.
- A file cut exactly between two items looks complete. The tool checks pairing, not completeness.
- It does not judge answers, compare prompts for you, check that latency is measured the same way for both systems, or wire the triggers to a monitor. The triggers are text to put in the launch plan.
- 🔴 Not tested on a real evaluation export.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does the headline average decide? | `step_01_headline_average.py` |
| 2 | What do the average, the list price per token and the median add? | `step_02_average_plus_vendor_sheet.py` |
| 3 | What do they miss? | `step_03_deficiencies_exposed.py` |
| 4 | What does the brief change? | `step_04_with_swapbrief.py` |

Run any of them from `src/`. The tool is `src/swapbrief.py`; step 4 runs the same code as the command line. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. There are 51 tests in `tests/`, including a golden test that pins the numbers in this README.

## Aligned to

The FSB's [Sound Practices for Responsible Adoption of Artificial Intelligence](https://www.fsb.org/uploads/P151026-1.pdf) (final report, 15 October 2026; I read it on 24 October 2026). Sound Practice 9 on performance management asks institutions to assess AI performance over time and lists recent changes to the model or system among the factors that set how often and how hard to assess; it also describes results that can indicate contingency plans should be triggered. Sound Practice 12 covers third-party AI providers and business continuity. A model migration is such a change, and this brief is one input to that assessment: it compares the two versions on paired items and writes the contingency trigger down before launch. The report does not mention cost per correct answer or p95 latency; those are my additions. This is a prototype, aligned to that guidance and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real bank, and no model was called. The prices are parameters, not any vendor's prices. A prototype on synthetic data, not a production case study. See [`data/README.md`](./data/README.md) for the files and the planted truth.

## Fork it

Export your evaluation results to the `results.csv` columns, put your price list in `prices.csv`, and run `brief`. Edit `POLICY` and `WINDOWS` at the top of `src/swapbrief.py` for your own thresholds. Read the [PRD](./PRD.md) for the scope I held to.
