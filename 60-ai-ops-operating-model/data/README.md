# Data for project 60

Synthetic. Produced by `_generate.py` with a fixed seed, so a rerun reproduces every file byte for byte. Nothing here comes from a real bank, program, vendor or employer. The review date is in `as_of.txt` (2026-09-30); no script reads the clock.

| File | What it holds |
|---|---|
| `checklist.csv` | 23 evidence items across the 8 lifecycle stages of [OPERATING_MODEL.md](../../OPERATING_MODEL.md). Columns: `item_id`, `stage`, `stage_name`, `item`, `evidence` (what to ask for), `min_tier` (lowest tier that owes it), `cycle_days` (how often it should be renewed), `independent` (yes when someone other than the builder must have produced it), `day_window` (30, 60 or 90 when it falls in the first 90 days of a first candidate, 0 after), `must_show` (the sentence to confirm when the artifact is opened), `source` (the section of OPERATING_MODEL.md and the project it comes from) |
| `programs.csv` | 60 programs. Columns: `program_id`, `program_name`, `tier` (1 to 4), `builder` (a person id), `claimed_stage` (0 to 8, what the owner reports) |
| `evidence.csv` | 677 rows, at most one per program and item. Columns: `program_id`, `item_id`, `artifact_ref`, `produced_by`, `date` |
| `program_truth.csv` | Per program: `reach` (how far the work really got, the first draw of the generator), `true_stage` (the last stage whose owed items are all planted `ok`), `window90_ok` (1 when every owed item due in the first 90 days is planted `ok`) |
| `item_truth.csv` | 1380 rows, one per program and item: `owed` (1 when the program's tier owes it) and `planted_state` |
| `as_of.txt` | The review date |
| `example_programs.csv`, `example_evidence.csv` | A hand-built tier-3 program, EX-01, that claims stage 6 and carries three defects. It is the worked example behind `python3 ops_model_review.py --demo` |

## How the truth is made

The truth does not come from the review rules. For each program the generator draws `reach`, then draws a planted state for every item. Of the 1024 owed (program, item) pairs, 482 are `ok`, 483 `absent`, 24 `lapsed`, 19 `hollow`, 9 `blank_ref`, 5 `self_signed` and 2 `future`. The 356 pairs the tier does not owe are 136 with evidence and 220 without.

- `ok`: a real reference, a date inside the cycle (usually; for 2 percent of ok items the cycle ran late and the age is drawn from 1.52 to 1.8 times the cycle), a producer other than the builder where the item needs one.
- `absent`: no row.
- `lapsed`: a cycle was skipped. The age is drawn from 1.15 to 3.0 times the cycle, so some lapsed items are younger than the review's 1.5 times limit and pass.
- `blank_ref`: a row whose reference is empty, TBD, n/a or TODO.
- `future`: a date up to 30 days after the review date.
- `self_signed`: an item that needs an independent producer, produced by the builder.
- `hollow`: a row that looks complete for an artifact that does not show what the checklist names. The review reads rows, so it cannot tell.

The owner's claim is `reach` plus a shift (0 for 62 in 100 draws, +1, +2, +3 or -1 for the rest), clamped to 0 to 8. It does not look at the planted states, so an owner can be honest and still wrong.

## What is assumed (🟡)

The tier assigned to each item is mine, except where OPERATING_MODEL.md section 4 sets the evidence owed at a tier (E03, E05, E06, E07, E08 and E10). The cycle in days is mine. The freshness factor, 1.5 times the cycle, is the one OPERATING_MODEL.md section 8 gives for obligation evidence, itself an assumption. The first-90-days window of each item is my mapping of section 10 of that file. All planted rates are chosen by the author and do not describe any real bank.
