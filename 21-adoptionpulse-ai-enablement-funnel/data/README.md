# Sample Data — AdoptionPulse walkthrough

Seven CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`SEED = 20261018` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files. The generator uses only the Python standard library and runs on Python 3.9. **No customer or employee data. No real bank, vendor, product or incident. The usage counts are written by the generator, not by people or a model.**

**The truth is known because the data is synthetic.** The generator decides what kind of user each person is (never used, tried once, casual, lapsed, habitual, proficient), so it can say whether the stage rules got the person right. A real estate does not hand you that; the first job in a real deployment is a real usage feed and a sample review of what staged users actually do.

The headline scenario the walkthrough resolves: **a modeled bank licensed an AI assistant to 800 staff in 20 org units and reports adoption as licenses issued and people who logged in. The login view reads as high. Staged from weekly usage, far fewer people use it every week, the units differ widely, and the program lead can see where each team loses people.**

**Seed and parameters.** One seed was used, chosen once before any output was looked at, and no other seed was tried. The generator parameters (shares, thresholds, effect sizes) were fixed from design reasoning before the first run and were not changed after seeing results. Two additions were made later, and neither changed any number in the other files (the checksums of those files were identical before and after): the policy row `leak_min_users` was added to `funnel_policy.csv` while writing step 4, after step 3's output had been seen, because a rate over a handful of users is not a leak; and `unit_truth.csv` was added after the first run of step 4, so the champion read could print the unit appetite that explains the gap between the planted and the measured champion effect.

**It is a test set, not an estimate of how real staff behave.** The shares of each behavior type were chosen by the generator. They are not taken from any benchmark or any real rollout.

---

## `users.csv` — 800 licensed staff

| Column | Type | What it is |
| --- | --- | --- |
| `user_id` | string | `U0001` onward. Ids are assigned after a shuffle, so they do not reveal the unit. |
| `org_unit` | string | One of 20 units, from 9 to 100 people. |
| `role` | string | `associate`, `specialist`, `analyst`, `engineer`, `relationship manager` or `manager`. Each unit has its own mix of roles. |
| `licensed_week` | int | 1 to 4. Units were licensed in waves (units per wave: 8 in week 1, 6 in week 2, 4 in week 3, 2 in week 4); each person has a 20% chance of landing one week after their unit's wave, capped at week 4. |
| `champion_in_unit` | yes/no | Whether the unit has an assigned champion. It is a property of the unit: 12 of 20 units have one. |
| `trained_week` | int or empty | The week the person completed training, 0 to 5 weeks after licensing. Empty if not trained. The generator draws each unit's completion rate between 25% and 90%; the realized share runs from 22.7% to 90.0%. |

```
user_id,org_unit,role,licensed_week,champion_in_unit,trained_week
U0001,Mortgage Servicing,associate,3,yes,4
U0002,Customer Service,associate,1,no,
U0003,Branch Network,relationship manager,3,no,
U0004,Branch Network,relationship manager,3,no,
U0005,Mortgage Servicing,associate,3,yes,6
```

## `usage_weekly.csv` — 800 users x 12 weeks = 9,600 rows

| Column | Type | What it is |
| --- | --- | --- |
| `user_id`, `week` | string, int | Join key and the week, 1 to 12. Week 1 starts on Monday 2026-07-06 and week 12 ends 2026-09-27 (constants in the generator). |
| `logins` | int | Sign-ins to the assistant portal that week. A week with any AI session has at least one login. |
| `ai_sessions` | int | AI conversations that week. |
| `prompts` | int | Prompts across those sessions. |
| `outputs_accepted` | int | Outputs the person kept, at most `prompts`. |
| `advanced_feature_uses` | int | Uses of the assistant's advanced features. |

Weeks before a person is licensed are zero.

```
user_id,week,logins,ai_sessions,prompts,outputs_accepted,advanced_feature_uses
U0001,1,0,0,0,0,0
U0001,2,0,0,0,0,0
U0001,3,1,2,11,4,0
U0001,4,1,2,6,2,0
U0001,5,2,4,15,2,0
```

## `champions.csv` — 60 champions

| Column | Type | What it is |
| --- | --- | --- |
| `champion_id` | string | `CH-001` onward. |
| `org_unit` | string | The unit the champion serves. Only the 12 units with a champion appear. Each has at least 2; the rest are shared out in proportion to unit size. |
| `active_weeks` | int | Weeks out of 12 in which the champion was active, 4 to 12. |

```
champion_id,org_unit,active_weeks
CH-001,Payments Operations,8
CH-002,Payments Operations,7
CH-003,Payments Operations,11
```

## `funnel_policy.csv` — the stage definitions

These are assumptions of a modeled bank, not advice and not a standard. The stage rules in `src/step_01` read this file; changing a value changes the funnel.

```
parameter,value,applies_to,definition
activation_window_weeks,2,activated,"Activated = at least 1 AI session in the first 14 days after licensing. Weekly data, so the licensing week and the next week."
habit_window_weeks,6,habitual,Look-back window for habit and proficiency: the last 6 weeks of the data (weeks 7 to 12).
habit_min_active_weeks,4,habitual,Habitual = AI sessions in at least 4 of the last 6 weeks.
proficient_min_advanced_weeks,2,proficient,Proficient also needs advanced-feature use in at least 2 of the last 6 weeks.
proficient_min_accept_rate,0.6,proficient,"Proficient also needs accepted outputs divided by prompts over the last 6 weeks at or above this value. A proxy for skill, not a measure of it."
leak_min_gap_points,5,action,A stage conversion counts as a leak when a unit is at least this many points below the estate rate.
leak_min_users,5,action,A stage conversion is judged for a unit only when at least this many users entered the stage before it.
```

## `user_truth.csv` — what the generator decided for each user

Used only to score the staging. No stage rule reads it.

| Column | Type | What it is |
| --- | --- | --- |
| `user_id` | string | Join key. |
| `latent_type` | string | `never`, `one_time`, `casual`, `lapsed`, `habitual` or `proficient`. |
| `true_stage` | string | `licensed` for never, `activated` for one_time, casual and lapsed, then `habitual` and `proficient`. |
| `work_quality` | string | `good` or `poor` for anyone who used the tool, `none` for a user who never did. Drawn independently of every count in `usage_weekly.csv`, so telemetry cannot see it. This is what makes the known limit measurable. |

Truth totals: 242 never used, 139 tried once, 100 casual, 72 lapsed, 161 habitual, 86 proficient. 79 users who used the tool produce poor work.

```
user_id,latent_type,true_stage,work_quality
U0001,habitual,habitual,good
U0002,casual,activated,good
U0003,never,licensed,none
```

## `unit_truth.csv` — what the generator decided for each unit

| Column | Type | What it is |
| --- | --- | --- |
| `org_unit`, `licensed` | string, int | The unit and its size. |
| `rollout_week` | int | The unit's licensing wave. |
| `champion_in_unit` | yes/no | As in `users.csv`. Chosen by a shuffle that does not look at appetite. |
| `appetite_logit` | float | The hidden unit effect on the chance that a person becomes habitual, on the logit scale. Drawn from a normal distribution, independent of champion assignment. |
| `training_rate` | float | The unit's training completion rate. |

```
org_unit,licensed,rollout_week,champion_in_unit,appetite_logit,training_rate
Branch Network,70,3,no,-0.106,0.34
Collections,35,3,yes,0.27,0.263
Commercial Lending,58,2,yes,-0.069,0.668
```

## `planted_effects.csv` — the two effects the generator planted

| Column | Type | What it is |
| --- | --- | --- |
| `effect` | string | `champion_in_unit` or `training_completed`. |
| `planted_logit_shift` | float | The shift the generator adds to the logit of a person's chance of becoming habitual or proficient. |
| `users_affected` | int | Users who have the effect (in a champion unit, or trained). |
| `avg_p_habitual_or_better_without`, `..._with` | float | The average chance for those users without and with the shift, given everything else about them. |
| `planted_gap_points` | float | The difference, in percentage points. |

```
effect,planted_logit_shift,users_affected,avg_p_habitual_or_better_without,avg_p_habitual_or_better_with,planted_gap_points
champion_in_unit,0.7,420,0.2429,0.3823,13.9
training_completed,0.55,428,0.2365,0.3364,10.0
```

Both effects are planted by construction. Training and champion assignment are random with respect to a person's propensity here. In real data both would be confounded: motivated people choose training and motivated units get champions. A with-and-without comparison on this data recovers the planted effect only up to noise, and the champion read is noisier because there are only 20 units.

---

## How the weekly counts are generated

Each person gets one latent type. The chance of being an adopter (habitual or proficient) is a logistic function of a base rate, the unit's appetite, the person's role, and the two planted shifts. Among adopters, a share are proficient (higher for engineers and analysts). Everyone else is split into never used, tried once, casual and lapsed.

| Type | Weekly behavior |
| --- | --- |
| never | No AI sessions. Logs in now and then, mostly in the first two weeks after licensing. |
| one_time | Sessions in one week only: the licensing week or the next. |
| casual | First session in the licensing week or the next, then a low and uneven weekly chance, higher in the first three weeks. |
| lapsed | Active for 2 to 4 weeks from the first session, then nothing. |
| habitual | First session in the licensing week or the next, then a high weekly chance that differs by person. A few miss enough weeks to fall under the habitual line. |
| proficient | As habitual, with advanced-feature use in most active weeks and a high accepted-output rate. |

The data includes two hard cases on purpose: casual users who sometimes reach four active weeks in the last six, and habitual users who miss enough weeks to fall under the line. Both produce staging errors that step 4 counts. Every type that uses the tool has a first session inside the activation window, so the funnel nests (every habitual user is also activated); step 4 prints the check.

---

## Headline unit — Customer Service

| Source | What it gives you |
| --- | --- |
| `users.csv` | 100 Customer Service staff, 85 of whom completed training, no champion. |
| `usage_weekly.csv` | Their weekly sessions. Most show nothing after the first weeks. |
| `user_truth.csv` | 53 never used the tool, 14 tried it once, 20 are casual, 9 lapsed, 2 are habitual and 2 proficient. |

Replay the walkthrough and you see the same unit three ways: the login view (it reads as healthy), the truth (a handful of habitual users), and AdoptionPulse (the leak is between activated and habitual, with a rule-based action).
