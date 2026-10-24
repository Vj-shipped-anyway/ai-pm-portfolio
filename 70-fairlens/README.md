# 🔬 fairlens: a six-test pack for a scorecard, run from a scores file

**I wanted to know what a validator sees when the decline reasons on a scorecard look consistent across groups, and a feature inside the score still moves approvals by group. This is a command-line tool: give it a CSV of scores with a group column and it prints PASS, REVIEW or FAIL for six tests. On 36 synthetic portfolios, each with a planted mechanism, the reason-code check passed almost every planted proxy, and the proxy ablation caught about half of them.** It extends [17 FairLens](../17-fairlens-credit-model-fairness/): the six-test shape and the planted postcode proxy come from there, and the command line, the interval-based ratio test, the accuracy check on the ablation and the scored set with hard cases are new here.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 70-fairlens/src && python3 fairlens_pack.py --demo
```

It prints:

```text
fairlens: 830 applicants in 3 groups, cutoff 126, reference Group A
  T1 approval gap    REVIEW  approval Group A 79.3%, Group B 55.7%, Group C 70.0%, spread 23.6 points
  T2 AIR by group    FAIL    AIR Group B 0.702 (0.626 to 0.783) FAIL; Group C 0.882 (0.750 to 0.997) REVIEW
  T3 cutoff sweep    FAIL    lowest AIR 0.702 at cutoff 126; no cutoff within 30 points above clears the screen
  T4 proxy ablation  FAIL    lowest AIR 0.702 -> 0.936, accuracy 71.8% -> 73.9%, 55 decisions turn to approve and 48 to decline
  T5 reason pairs    PASS    101 of 149 cross-group pairs differ in top reason (67.8%) against 66.3% within Group A (+1.5 points)
  T6 reason naming   PASS    3 of 55 declines that turn on the proxy do not list R05 (5.5%)
overall: FAIL (3 FAIL, 1 REVIEW, 2 PASS)
```

The reason pairs pass: declined applicants with scores within 5 points of each other differ in their top reason about as often across groups (67.8%) as within Group A (66.3%). The ablation fails: take the postcode points out and the lowest ratio goes from 0.702 to 0.936 while accuracy rises. Standard library only, Python 3.9 or newer.

To check your own file:

```bash
python3 fairlens_pack.py check scores.csv --cutoff 126 --proxy-column postcode_points --proxy-code R05
```

The file needs `group`, `score` and `bad_outcome` (1 for a default). Optional: the proxy's points column, and `reason_1` to `reason_3` with the codes listed on the decline notice. A test that lacks its columns prints NOT RUN and the overall line says which. Exit 0 when the overall verdict is below `--fail-on` (default `fail`), 1 at or above it, 2 for malformed input with a one-line message. `--format github` prints annotations. Group labels are read from the `group` column and never inferred.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 36 planted portfolios of 760 to 830 applicants each, 14 with a planted proxy and 22 without; the script is named in brackets):

- 🟢 The model card runs 0 of 6 fairness tests. The lowest group approves under 0.80 of the reference rate in 22 of 36 portfolios, and mean accuracy is 73.3% with a planted proxy against 75.4% without (`step_01`)
- 🟢 The reason-code review alone passes 13 of 14 planted proxies, and flags 4 of the 22 others, all four for too few matched pairs (`step_02`)
- 🟢 A point-estimate ratio under 0.80 flags 22 of 36 portfolios, 10 of them with a planted proxy. It flags 6 of 6 portfolios whose groups were drawn identically; with the 95% interval, T2 fails 0 of those 6 and sends 6 to review (`step_03`)
- 🟢 Ablation alone, with no accuracy check, calls 10 of 14 planted proxies and 5 of the 22 others. It calls 4 of 5 portfolios whose postcode points also predict default; removing them there costs 3.3, 4.0, 5.1, 2.0 and 1.8 accuracy points (`step_03`)
- 🟢 The pack's ablation (T4) marks 7 of 14 planted proxies FAIL and 1 of 22 others. It marks 0 of 5 predictive-feature portfolios FAIL and 4 of 5 REVIEW (`step_04`)
- 🟢 Where the ablation fails a portfolio, the reason pairs pass on 6 of those 8 (`step_04`)
- 🟢 Overall FAIL: 10 of 14 planted-proxy portfolios and 2 of 22 others (`step_04`)

## What it still gets wrong

- 🟢 Seven of the 14 planted proxies are not marked FAIL by T4 (`step_04` prints each one). Three are `two_proxies` portfolios: the tool is pointed at the postcode column, removing it lifts the lowest ratio to 0.771, 0.783 and 0.797, and the region points that remain keep it under 0.80 (REVIEW). Three are `quiet_proxy` portfolios worth 8 to 12 points, where the lift is +0.005, +0.004 and -0.013 (PASS). One is a weak `proxy_gap` portfolio (C18, 0.818 to 0.861, PASS).
- 🟢 One of the 22 portfolios with no planted proxy is marked FAIL by T4, a `small_group_noise` portfolio (C14). A group of 30 applicants moves when you re-score it, and the ablation reads that movement as a proxy. The 1-point accuracy guard is an assumption 🟡 and I did not estimate how noisy the accuracy change is.
- 🟢 No portfolio reads PASS overall: T6 is REVIEW or FAIL on 29 of 36 (`step_04`). A decline reason list built from points lost rarely names the postcode points that tipped the decision. That is a finding about the notice, whatever the groups look like, and it keeps every clean portfolio at REVIEW. T6 can only FAIL when T4 did not pass.
- **The test set and the rules share an author.** I planted the mechanisms and wrote the tests, so 7 of 14 is what these rules do on what I planted, not a rate on a real portfolio. I also adjusted group sizes, proxy weights and coefficients after looking at earlier output (see [data/README.md](./data/README.md)). Treat every number as a ceiling.
- The reason lists here come from my own rule, the three components with the most points lost. A lender who ranks reasons another way changes T5 and T6. Three listed reasons is an assumption 🟡.
- 🔴 Real credit files rarely carry group labels. This tool reads a column. A group-inference step, with its own error check, would come first; [17 FairLens](../17-fairlens-credit-model-fairness/) stress-tests wrong labels, and this project does not.
- The ablation takes one column. It does not search for a second proxy or for a re-weighted scorecard. T1 never fails alone, and the cutoff sweep covers 30 points either side, a width that assumes a score scale of a few hundred.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does the model card show? | `step_01_model_card_only.py` |
| 2 | What does a review of the decline reasons catch? | `step_02_reason_code_review.py` |
| 3 | Where does each check fail alone? | `step_03_deficiencies_exposed.py` |
| 4 | What do the six tests catch together, and what gets through? | `step_04_with_fairlens.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The tests (`tests/`, 41 in all) pin the numbers, bad input and hostile strings.

## Aligned to

I read two CFPB pages on 2026-10-24. The first is [12 CFR 1002.9 (Regulation B)](https://www.consumerfinance.gov/rules-policy/regulations/1002/9/): the statement of reasons for adverse action must be specific and indicate the principal reason or reasons, and the commentary says no particular number of reasons is mandated, and that more than four is not likely to help the applicant. The second is [Circular 2022-03](https://www.consumerfinance.gov/compliance/circulars/circular-2022-03-adverse-action-notification-requirements-in-connection-with-credit-decisions-based-on-complex-algorithms/), published 2022-05-26: specific reasons are still required when a creditor uses a complex algorithm. T5 and T6 are checks on whether the reasons a scorecard lists are consistent across groups and name the factor that decided. This is a prototype, aligned to that reading and not compliant with or certified against anything. I did not read the rules on disparate impact for this project, so nothing here tests for it. The 0.80 ratio is a screening convention from employment-selection practice that I did not read; it is an assumption 🟡 and a screening statistic, not a legal finding.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, lender or real portfolio, and the group labels encode no real class. A prototype on synthetic data, not a production case study. Every threshold is an assumption 🟡 listed in [data/README.md](./data/README.md).

## Fork it

Swap `data/case_scores.csv` for your own export and keep the columns, or skip the data and point `check` at one scores file. Edit the constants at the top of `src/fairlens_pack.py` to change a threshold. Read the [PRD](./PRD.md) for the scope I held to.
