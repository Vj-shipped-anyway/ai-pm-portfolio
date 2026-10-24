# 🧾 report-trace: lineage for report cells

**I wanted to know what it takes to answer "where does this number come from?" for one cell of a filed report, and which ways a number drifts away from its source rows after filing. This is a small command-line tool that records, for every cell, the rule and the exact source rows behind it, then checks each cell against the source as it stands today and prints the path back.** It extends the idea in [09 LineageLog](../09-lineagelog-ai-decision-audit/) from one AI decision to one reported number. Nothing is imported from that project.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 74-report-trace/src && python3 report_trace.py --demo
```

It prints:

```text
14 cells: 6 leaf (3 traced, 1 adjusted, 1 unexplained, 1 with source changes), 8 derived (8 foot, 0 do not)
  card.current         UNEXPLAINED              -29,750.00 of the filed value is in no source row and no logged adjustment
  card.d01_59          SOURCE_CHANGED           source changed since filing: L000010 balance_cents 457478 -> 498651
  open loans in no cell: 1, first L000029
result: 2 cells need a person; open loans in no cell: 1; logged adjustments that match no leaf cell: 0
cell card.d01_59   card / d01_59   leaf   filed 25,722.15
  rule: product card, status open, booked on or before 2026-06-30, days past due 1 to 59
  source rows at filing: 6, sum 25,722.15
  logged adjustments: 0, sum 0.00
  unexplained amount: 0.00
  against the current source: 1 difference(s)
    L000010 balance_cents 457478 -> 498651
  verdict: SOURCE_CHANGED
```

Standard library only, Python 3.9 or newer. On your own files: `build` captures the lineage from the source as it stood at filing, `verify` checks every cell against a current copy, `trace` prints one cell's path. `verify` exits 1 when a cell needs a person, 2 on malformed input, and `--format github` prints annotations. The report is an invented loan schedule, not any regulator's form.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: a report of 71 cells over a loan table, with planted problems and planted hard negatives; the script is named in brackets):

- 🟢 No recorded path: 0 of 71 filed cells point to a source row. A reviewer reads 3724 rows of the loan table to find the loans behind one cell, where a leaf cell has a median of 15.5 rows behind it and at most 467. A first guess at the rule from the column label reproduces the filed value on 5 of 48 leaf cells (`step_01`)
- 🟢 A mapping sheet re-run against today's table flags 31 of 48 leaf cells. It finds 15 of 18 planted problems, passes 3 of 3 offsetting changes, raises 16 flags on cells that are not problems (4 logged adjustments, 12 cells where rows were booked after the as-of date), flags 23 of 23 derived cells, and names no row. A reviewer reads a median of 28 rows to explain a flagged cell (`step_02`)
- 🟢 The next fix people try, comparing every column of every row to the filing snapshot, finds offsetting 3 of 3, restated 5 of 5 and removed 3 of 3. It finds 0 of 3 late arrivals and flags 4 of 4 cells where only a note changed. 7 open loans with a blank days-past-due sit in no cell and nothing flags them. A cross-foot of the filed numbers finds the 3 footing errors that the live re-run buries among 23 flags (`step_03`)
- 🟢 Row-level lineage, checked against the source today: 21 of 21 planted problems found and 0 false alarms on 46 cells that are fine or only explained by the log. 12 of 12 cells with rows booked after the as-of date and 4 of 4 cells where only a note changed stay quiet. The rows it names are exactly the planted rows on 14 of 14 cells with a source change, so a reviewer reads 18 rows instead of 611. All 7 open loans that sit in no cell are found (`step_04`)

**Modeled and hypothetical**

- 🟡 Rows read stands in for reviewer effort. I did not time anyone, and a row is not a minute.
- 🔴 A production reporting job emitting this capture at acceptable cost and size is a design I reasoned about and did not test.

## What it still gets wrong

- 🟢 4 of 4 cells that hold a wrong source row still verify as TRACED (`step_04` prints each one, for example auto.d60_89 with a recorded days-past-due of 85 and a true value of 171). The row is real and unchanged, so nothing in the lineage disagrees. Lineage shows where a number came from, not whether the source was right.
- **The data and the rules share an author.** I planted the problems and wrote the checks, so 21 of 21 shows the rules cover what I planted. The set includes cases built to trip them (offsetting changes that keep the sum, a note edited on a reported row, rows booked after the as-of date, adjustments that are logged and exact) and one case built to beat them, the wrong source row. Treat the result as a ceiling for these rules, not a rate on a real report.
- **The source has to be a position table that is corrected in place, with later loans appended.** A live ledger that moves every day would flag every cell. Lineage needs a frozen or versioned source.
- A row whose days past due was corrected into another bucket flags the cell it left and not the cell it joined. That case is covered by a unit test, not by the planted set.
- Cells are sums of balances and ratios in basis points. No counts, no joins, no rounding tolerance. A join that double counts a loan is not modeled. An adjustment aimed at a derived cell is reported as unmatched.
- The capture here is a reference implementation of the aggregation, run after the fact on a snapshot. It has not been put inside a real job.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does a reviewer have when a filed number carries no path back? | `step_01_no_trace.py` |
| 2 | What does a mapping sheet re-run against today's table catch? | `step_02_mapping_sheet.py` |
| 3 | Where does it fail, and what does the next obvious fix cost? | `step_03_deficiencies_exposed.py` |
| 4 | What does row-level lineage catch, and what does it leave? | `step_04_with_lineage.py` |

Run any of them from `src/`. Step 4 writes `src/out/`, which `_build_demo.py` turns into `demo.html`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The tests (`tests/`, 51 in all) pin the numbers, the exit codes on empty, wrong-type and truncated input, and hostile strings in loan ids and adjustment reasons.

## Aligned to

Nothing. I read no regulation or standard for this project and claim no alignment to one. The report is an invented schedule. It is a prototype on synthetic data, not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real bank. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/loans_filed.csv`, `data/loans_now.csv`, `data/report_filed.csv`, `data/adjustments.csv` and `data/report_spec.json` for your own and keep the columns. The spec names every cell and its inputs explicitly; structure never comes from cell names. Read the [PRD](./PRD.md) for the scope I held to.
