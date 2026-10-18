# Sample Data — ValueLedger walkthrough

Seven files drive the four steps. Everything here is synthetic, seeded, and reproducible. No real bank, employee, copilot, vendor or customer is represented. [`_generate.py`](./_generate.py) writes every file, uses only the standard library, and produces byte-identical output on every run.

```bash
python3 _generate.py     # rewrites the seven files in this folder
```

**The answer key.** Two of the files hold the true effect the generator injected: `truth_person_week.csv` and `truth_parameters.json`. They exist only because the data is synthetic. A real bank has no answer key, which is the whole difficulty with measuring AI benefit. The step scripts use them for one purpose: scoring each method's error after the method has run. No estimator reads them.

---

## What a measurement team could observe

### `teams.csv` — 24 teams and the non-random selection rule

| Field | Description |
| --- | --- |
| `team_id` | `T01` to `T24`. |
| `cost_center_id` | One of eight cost centers; three teams each. |
| `headcount` | People on the team (10 to 17; 320 in total). |
| `enthusiasm_score` | A 1 to 5 score, standing in for an internal enthusiasm survey. |
| `cohort` | `treated` or `holdout`. |

**The rule.** The 12 teams with the highest enthusiasm score got the copilots first. That is not random, so treated teams differ from the holdout before any tool arrives: they are faster at baseline (selection on a visible trait). The generator redraws the enthusiasm scores until every cost center holds at least one treated and one holdout team, so the per-cost-center ledger has something to compare against.

### `employees.csv` — 320 people

| Field | Description |
| --- | --- |
| `employee_id` | `E0001` to `E0320`. |
| `team_id`, `cost_center_id` | Where the person sits. |
| `cohort` | Same as the team's cohort: 160 treated, 160 holdout. |
| `copilots` | `none` for the holdout. For treated people: `A` (drafting copilot), `B` (meeting and notes copilot), or `AB` (both, so the same task can be logged twice). |

### `panel.csv` — 320 people × 26 weeks = 8,320 rows

| Field | Description |
| --- | --- |
| `employee_id`, `week` | Person and week, 1 to 26. Copilots launch in week 13. |
| `tasks_completed` | Tasks finished that week. A task is one unit of knowledge work (a case file, a draft, a memo section). Volume is demand-driven in this world, so freed minutes show up as capacity, not extra output. |
| `minutes_per_task` | Average minutes per completed task that week. Excludes rework. |
| `events_a`, `events_b` | Tasks where copilot A or B was used. These are the usage logs each vendor-style business case multiplies. |
| `events_both` | Tasks where both copilots' logs share the task ID. The same task is inside `events_a` and `events_b`, so distinct assisted tasks = `events_a + events_b − events_both`. In a real deployment this column needs a shared task key across the two logs; here it is given. |
| `rework_minutes` | Minutes spent correcting copilot output that week. Zero for the holdout and for pre-launch weeks. |

### `budget.csv` — 8 cost-center lines

| Field | Description |
| --- | --- |
| `cost_center_id`, `cost_center_name` | `CC-101` to `CC-108`. |
| `headcount` | People in the cost center (computed from `employees.csv`). |
| `loaded_cost_per_hour_usd` | Used to value hours. Invented. |
| `freed_time_can_become_cash` | `yes` if the line has a cash lever that freed hours could displace; `no` if freed time can only become capacity. |
| `cash_lever` | The lever, in words (contractor and overtime cover, temporary staffing, overtime), or `none, fixed salaried headcount`. |
| `addressable_spend_usd_annual` | The most a cost center can take out of that lever in a year. Hard benefit is capped at this, scaled to the window. Invented. |

Three cost centers can turn freed time into cash (`CC-101`, `CC-102`, `CC-103`). Five cannot. The figures are invented to show the mechanic, not to describe any bank.

### `copilots.csv` — the two overlapping copilots

| Field | Description |
| --- | --- |
| `copilot_id`, `copilot_name` | `A` Drafting copilot, `B` Meeting and notes copilot. Generic names; no product is modeled. |
| `use_case_id` | A synthetic ID in the `UC-###` format that project 11 TierGate uses. These two IDs are not rows in that project's data. The join to a use-case register is a design, not a built link. |
| `assumed_minutes_saved_per_use` | The vendor-style assumption: 12 for both. This is the number Step 1 multiplies by usage events. |
| `seat_cost_usd_per_month` | Synthetic seat price, the cost side of return (project 07 InferenceLens would supply the real record). |
| `approval_status` | Synthetic. ValueLedger books benefit only for approved use cases. |

---

## The answer key (do not feed this to a method)

### `truth_person_week.csv` — treated people, post-launch weeks only (2,240 rows)

| Field | Description |
| --- | --- |
| `true_assisted_tasks` | Distinct tasks a copilot touched that week. |
| `true_gross_saved_min` | Minutes the copilot truly saved on those tasks, before rework. |
| `true_rework_min` | Same as `rework_minutes` in the panel. |
| `true_net_saved_min` | Gross minus rework. |
| `true_hidden_drift_min` | The injected change that is not caused by the copilot (see below). It is not part of the true net. |

### `truth_parameters.json` — the constants the generator injected

| Parameter | Value | What it does |
| --- | --- | --- |
| Steady-state saving | 5.5 min per assisted task | What the copilot saves once novelty has worn off. |
| Novelty bonus | 6.0 min per assisted task in launch week | Decays as `exp(−0.25 × weeks since launch)`: a half-life of 2.77 weeks. |
| Person skill | mean 1.0, sd 0.18 | Multiplies the saving per person. |
| Rework | per cost center, e.g. 18% of assisted tasks need an 8-minute fix; `CC-104` is 42% and 10 minutes | The cost of copilot errors. `CC-104` (credit risk reporting) is the cost center where speed is bought with errors. |
| Overlap | a person holding both copilots uses both on 60% of assisted tasks | Creates the double-counted hour. |
| Seasonal workload | additive, 2.0 minutes per task at the week-5 peak, easing afterwards | Hits every person equally, so any before-and-after comparison sees an improvement no tool caused. |
| Team-week shock | sd 1.1 min per task, shared by a team in a week | Creates the clustering that the bootstrap resamples by team. |
| Selection | −1.8 min per task at baseline per +1 sd of team enthusiasm | Treated teams start faster. |
| **Hidden drift** | **0.45 min per task, treated teams only, post-launch** | The enthusiastic teams also changed how they work after launch. It lowers their minutes per task, no column records it, and the copilot did not cause it. This is the known limit ValueLedger cannot see. |

Both copilots have the same per-task effect; the generator does not model one being better than the other. A treated person's `copilots` value changes which logs record the task, not how much time it saves.

---

## How the files connect

```
teams.csv ──> employees.csv ──> panel.csv ──────────> Steps 1, 2, 3, 4 (methods)
                   │                                          │
                   └──> budget.csv, copilots.csv ──> Steps 1 to 4 (assumed minutes, value at loaded rates; Step 4 adds ledger, cost, booking)
                                                              │
truth_person_week.csv, truth_parameters.json ──> scoring only: error against the answer key
```

**Reproducibility.** `_generate.py` seeds one `random.Random` and draws in a fixed order. Run it twice and `diff` the folders: no differences. The step scripts read these CSVs and print numbers that the README and the demo quote.
