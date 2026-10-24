# 🧮 Review Capacity: how many reviewers does the human-in-the-loop queue need?

**I wanted a headcount number for a review queue that I could defend line by line. The spreadsheet answer divides a day's work by the hours in a shift and leaves the queue to absorb every cluster of arrivals. Erlang C does better, until a batch lands at open. This is a small command-line calculator: you give it arrival and handling-time assumptions, a wait target and a utilization cap, and it returns the reviewers needed at the desk and the roster that implies.** It extends [08 OversightOps](../08-oversightops-hitl-workflow/), which models the review queue, and [24 PortfolioBoard](../24-portfolioboard-ai-program-portfolio/), which sets review capacity against demand by team. I took the questions from those two, not their numbers or their code.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 50-review-capacity/src && python3 review_capacity.py --demo
```

It prints:

```text
queue                   load  seats  util  mean-only  roster  have  status
morning_batch_review     1.9      7   28%          3      10     6  SHORT by 4
onboarding_exceptions    3.0      5   60%          5       7     6  SHORT by 1
complaint_escalations    2.7      5   53%          4       7     7  ok
decision: SHORT on 2 of 3 queues with a current_headcount
```

`seats` is reviewers at the desk, `mean-only` is Erlang C on the mean rate alone, `roster` is seats divided by one minus shrinkage, rounded up. Standard library only, Python 3.9 or newer. To size your own queues: `python3 review_capacity.py size queues.csv`, where each row holds the assumptions for one queue (the columns are listed at the top of the file). It exits 1 when a queue is short, and `--format github` prints annotations. `python3 review_capacity.py fit caselog.csv --days 1-10` measures the arrival and handling columns from a case log and leaves the target columns at defaults for you to edit.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 13 planted queues and 7049 replayed cases; the script is named at the start of each bullet):

- `step_01`: 🟢 Staffing to the average workload: 0 of 13 queues meet both the wait target and the utilization cap, 2300 of 7049 cases (32.6%) wait past their target, and the queues get 39 reviewers where 61 were needed
- `step_02`: 🟢 Erlang C on the mean rate: 10 of 13 queues meet both limits, 8 of 13 land on the true number and 802 of 7049 cases (11.4%) are late. The two opening-batch queues get 3 reviewers each where 7 were needed, with 47.1% and 55.1% of their cases late
- `step_03`: 🟢 Each half of the fix alone: draining the opening batch lifts the exact matches from 8 to 10 of 13 and moves two queues nearer the truth and none farther; scaling the tail by the measured spread moves two answers, one nearer and one farther
- `step_04`: 🟢 The tool: 10 of 13 queues land on the true number, 13 of 13 within one, 12 of 13 meet both limits, and 260 of 7049 cases (3.7%) are late, against 11.4% for Erlang C. It asks for 62 reviewers where 61 were needed and Erlang C gives 54
- `step_04`: 🟢 Two hard negatives, queues that look risky on paper, are not over-staffed: 2 of 2
- `step_04`: 🟢 With the assumptions measured on the previous 10 days instead of the replayed ones: 7 of 13 land on the true number, 12 of 13 within one, and 10 of 13 meet both limits
- 🟡 Modeled, assumptions named: the wait targets, the 0.85 utilization cap and the 25% shrinkage are my choices, set in `data/queues.csv`. The roster column is arithmetic on the shrinkage and is not tested against a replay.
- 🔴 Hypothetical: that a reviewer who runs near the cap reviews worse. 08 plants that effect in its data; nothing here measures it, so the cap is a policy choice and not a finding.

## What it still gets wrong

- `step_04` and `step_03`: 🟢 One bursty queue is still one reviewer short: `card_dispute_wave` gets 5 where 6 were needed, with 10.6% of its cases late against 10% allowed. The tool reads the spread of the gaps between arrivals, 1.64 for that queue, and busy and quiet spells hide inside a gap statistic: its hourly arrival counts have a variance over mean of 3.66, against 0.80 for a plain queue. One queue sitting just over the line cannot prove that is the cause.
- `step_04`: 🟢 Two queues get one reviewer more than needed, `onboarding_review` and `dispute_summary_check`, each with 5 against 4.
- `step_03`: 🟢 The variability term is not shown to help. It changed 2 of 13 answers, one better and one worse. I kept it because it is the standard form and the near-constant handling queue needs it; 13 queues cannot settle it.
- `step_04`: 🟢 A change after the history was taken is invisible to any method fitted on the history. `payment_limit_exceptions` ran at 5.31 live cases an hour on days 1 to 10 and 6.78 on days 11 to 20; fitted on days 1 to 10 the tool says 4 reviewers and 5 were needed.
- **The data and the rules share an author.** I planted the queues and wrote the sizing, so the numbers are a ceiling for these rules, not a rate on a real queue, which I have not tested. I did not change the queue parameters after seeing a result.
- **Each true number is one 10-day replay**, so a miss of one reviewer at the edge is partly noise. The replay starts every day empty, serves cases first come first served by identical reviewers, and has no priorities, no skill routing, no abandonment and no time-of-day staffing beyond the opening batch.
- The tail scaling is the usual Allen-Cunneen style adjustment of Erlang C. I wrote it from the standard form and have not checked it against the original papers; the replay is the only authority in this folder.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does staffing to the average workload leave? | `step_01_average_workload.py` |
| 2 | What does Erlang C on the mean rate fix, and where does it stop? | `step_02_erlang_c.py` |
| 3 | Where does each half of the fix fail alone? | `step_03_deficiencies_exposed.py` |
| 4 | What do variability and the opening batch give together, and what is left? | `step_04_with_review_capacity.py` |

Run any of them from `src/`. Steps 1 to 4 measure the assumptions on the days they replay, so the comparison tests the method and not a forecast; the last block of step 4 repeats the test with assumptions from the earlier days. Data is generated by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

Nothing. I did not build this against a published standard or a regulator's text, so I claim no alignment. It is a prototype on synthetic data.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real bank. A prototype on synthetic data, not a production case study. The planted kinds, the definition of the true number and the assumptions are in [`data/README.md`](./data/README.md).

## Fork it

Swap `data/cases.csv` for your own log with the columns `queue_id`, `day`, `arrival_min`, `handle_min` and `channel` (`live`, or `batch` for cases created in one run at open), run `fit` on it, edit the target columns and run `size`. Read the [PRD](./PRD.md) for the scope I held to. I have not run the exit code and annotations in a GitHub workflow; what is tested is the command (`tests/test_cli.py`, 55 tests across the folder).
