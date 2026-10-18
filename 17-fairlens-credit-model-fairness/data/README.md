# Sample Data — FairLens walkthrough

Three CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`SEED = 20261018` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files. The generator uses only the Python standard library and runs on Python 3.9. **No customer data. No real bank, applicant, postcode, vendor or model. The group labels are synthetic and encode no real protected class. The "model" that scores the applicants is a hand-written points scorecard, a stub, not a trained model.**

**The truth is known because the data is synthetic.** The generator decides who defaulted, and it decides that the postcode band has no effect on default. A real lender does not hand you that, and does not hand you group labels either; the first job in a real deployment is capturing a real decision log and a defensible group-inference step.

The headline scenario the walkthrough resolves: **a modeled bank scores 6,000 applicants in three synthetic groups. At the policy cutoff of 190 points the model card reports 87.1% accuracy and 75.7% approved. Behind those two numbers the approval rates are 83.5%, 64.3% and 62.7% by group. With FairLens, six tests turn that into an adverse impact ratio by group with an interval, a cutoff sweep, a proxy ablation, a reason-code check and a verdict for each.**

---

## `applicants.csv` — 6,000 synthetic applicants

One row per applicant. The order is shuffled with the seeded generator, so the groups interleave.

| Column | Type | What it is |
| --- | --- | --- |
| `applicant_id` | string | `AP-00001` onward, in file order. |
| `group` | string | `Group A`, `Group B` or `Group C`. Synthetic labels. Group A has 3,600 applicants, Group B 1,950 and Group C 450: the smallest group is small on purpose, so its uncertainty is visible. |
| `income` | integer | Annual income, rounded to 100. Log-normal around a per-group median, clipped to a floor and a ceiling. |
| `dti` | decimal | Debt-to-income ratio, two decimals, clipped. |
| `history_months` | integer | Length of credit history in months, clipped. |
| `utilization` | decimal | Share of available credit in use, two decimals, between 0 and 1. |
| `prior_delinq` | integer | Prior delinquencies, 0 to 3 (3 means 3 or more). |
| `postcode_band` | string | `P1` (best) to `P5`. **A stand-in for group by construction**: each group has its own postcode mix (below). It has no effect on default. |
| `defaulted` | 0/1 | The outcome the generator decided. |

First rows (real rows from the file):

| applicant_id | group | income | dti | history_months | utilization | prior_delinq | postcode_band | defaulted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `AP-00001` | Group B | 67700 | 0.28 | 113 | 0.47 | 0 | P4 | 0 |
| `AP-00002` | Group C | 26100 | 0.38 | 11 | 0.56 | 2 | P4 | 1 |
| `AP-00003` | Group B | 78400 | 0.44 | 93 | 0.38 | 0 | P5 | 0 |
| `AP-00004` | Group A | 37600 | 0.29 | 98 | 0.19 | 0 | P2 | 0 |
| `AP-00005` | Group B | 71900 | 0.13 | 137 | 0.56 | 0 | P4 | 0 |

### How the outcome is decided

`defaulted` is drawn from a logistic function of **income, dti, history_months, utilization and prior_delinq only**. The group and the postcode band are not inputs to it (read `true_default_probability` in `_generate.py`). The groups differ mildly in income, dti, history and utilization, so part of any approval gap comes from legitimate inputs, and the default rates differ by group:

| Group | Applicants | Defaulted | Share |
| --- | --- | --- | --- |
| Group A | 3,600 | 707 | 19.6% |
| Group B | 1,950 | 583 | 29.9% |
| Group C | 450 | 137 | 30.4% |

### How the proxy is planted

Each group has its own postcode mix. The shares below are printed by `src/step_01_model_card_only.py` from the file:

| Group | P1 | P2 | P3 | P4 | P5 |
| --- | --- | --- | --- | --- | --- |
| Group A | 31.7% | 31.6% | 21.3% | 10.3% | 5.1% |
| Group B | 4.3% | 11.4% | 26.4% | 34.2% | 23.8% |
| Group C | 10.2% | 16.4% | 27.8% | 28.2% | 17.3% |

Group C's mix is milder than Group B's on purpose, so that its AIR sits near the 0.80 screen and its small size decides whether the interval straddles it.

## `scorecard_points.csv` — the stub

| Column | Type | What it is |
| --- | --- | --- |
| `component` | string | One of `income`, `dti`, `history_months`, `utilization`, `prior_delinq`, `postcode_band`. |
| `bucket` | string | A readable label for the bucket. |
| `low`, `high` | decimal | The bucket is `low <= value < high`. An empty `high` means no upper bound. Empty for `postcode_band`, which matches on the label. |
| `points` | integer | Points earned in that bucket. |

The points were set by hand and **never fitted to this data**. The maximum score is 350. `postcode_band` carries up to 35 points (P1 35, P2 25, P3 15, P4 5, P5 0), and that is the planted flaw: it moves decisions without adding information about default. A score at or above the policy cutoff (a constant in `src/step_01_model_card_only.py`) is an approval.

## `reason_codes.csv` — reason codes

| Column | Type | What it is |
| --- | --- | --- |
| `component` | string | The scorecard component. |
| `reason_code` | string | `R01` to `R06`. |
| `plain_language` | string | The sentence a declined applicant would be shown. |

The principal reasons for a decline are the components with the most points lost against their maximum, with ties broken in file order. That is one simple method, not the only one; the pack tests whichever method a bank uses.

---

## Seed and parameter choice (stated plainly)

- `SEED = 20261018` was the first and only seed run through this generator. I did not search over seeds.
- The group parameters (per-group income median, dti, history and utilization means, delinquency mix and postcode mix) were set by hand over several trial runs of a scratch version of the generator, using seeds 1, 2 and 3, until three things appeared at once: an approval gap that accuracy by group does not show, a proxy whose removal lifts the lowest AIR above 0.80, and a smallest group whose AIR interval straddles 0.80. So the data is shaped to show those effects. It is a test set, not an estimate of how often any of them happens in the real world.
- After fixing the seed I ran seeds 1 to 5 once, only to see whether the pattern was an accident of one draw. Group B stayed below 0.80 and the postcode ablation lifted the lowest AIR above 0.80 on all five; Group C's interval straddled 0.80 on four of the five. Those runs are not kept and were not used to choose anything. To repeat them, change `SEED` in `_generate.py`.
- The bootstrap seed (`20261019`, in `src/step_03_deficiencies_exposed.py`) and the label-error seed (`20261020`, in `src/step_04_with_fairlens.py`) were set once and not tuned.
- Thresholds in the pack (0.80, 15 points, 10 points and the rest) are assumptions of a modeled bank, not legal advice. Change them and the verdicts change.

## What is not claimed

- No claim that these groups, postcode bands or default rates resemble any real population.
- No claim that a real model's gap would be this size, or that a real proxy would be this easy to find. Here the proxy is planted and the label is exact.
- No claim that AIR below 0.80 is a legal finding. It is a screening statistic, and the 0.80 line comes from employment guidance (29 CFR 1607).

---

## Headline scenario — Group B at the policy cutoff

| Source | What it gives you |
| --- | --- |
| `applicants.csv` | 1,950 Group B applicants, 583 of whom defaulted. |
| `scorecard_points.csv` | The points each of them earns, including up to 35 from the postcode band. |
| `reason_codes.csv` | The reason code attached to each component, for the declined. |

Run the walkthrough and you see the same group three ways: the model card (87.1% accuracy, nothing by group), accuracy by group (84.2%, looks fine), and FairLens (approval 64.3% against 83.5%, AIR 0.769, interval 0.742 to 0.797, FAIL).
