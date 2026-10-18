# Sample Data — KillSwitch walkthrough

Five CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`SEED = 20261018` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files. The generator uses only the Python standard library and runs on Python 3.9. **No customer data. No real bank, service, model, vendor or incident. The hourly metrics and the drill log are written by the generator, not by a service or a model, and no model is used anywhere in this repo.**

**The truth is known because the data is synthetic.** The generator decides when the service is degraded, which segments an event hits and what share of their decisions it spoils, so it can say exactly how many bad decisions each event caused. A real estate does not hand you that; the first job in a real deployment is a history of real degradations, labeled after the fact.

**Seed and parameters.** `SEED = 20261018` was chosen before any result was computed and was not re-rolled. Every generator parameter (the segment baselines, the event list and effect sizes, the noise levels, the drill failure chances) was set from design reasoning about how such a service behaves, before any detection result was computed. No generator parameter was changed after results were seen.

**It is a test set, not an estimate of real-world frequency.** 12 degradation events in 90 days is dense on purpose, so that every effect (a small segment hidden by a big one, a silent error, a drift that builds slowly, an outage that ends before a person can act) appears often enough to count. How often a real service degrades is a separate, named assumption in the README's utility section.

The headline scenario the walkthrough resolves: **an AI decision service with four customer segments and a rules-engine fallback suffers 12 degradation events in 90 days; 8 hit one segment and 3 are silent errors. The manual plan switches before the event ends for 2 of 12. KillSwitch trips for 9 of 12, moves only the hurt segments, comes back when the signals are clean, and scores the 10 drills.**

---

## Time and the split

Hour 0 is a constant epoch (`EPOCH = 2026-07-01 00:00` in `_generate.py`; the clock is never read). `hour` is the number of hours since then, 0 to 2159. **Days 1-60 are hours 0-1439: the fit period, where thresholds are set. Days 61-90 are hours 1440-2159: held out, scored only.** Every result in the walkthrough is reported for both. An event is active for `start_hour <= h < end_hour`, so `end_hour` is the first healthy hour.

## `metrics_hourly.csv` — 8,640 rows: 90 days × 24 hours × 4 segments

| Column | Type | What it is |
| --- | --- | --- |
| `hour` | int | Hours since the epoch, 0 to 2159. |
| `segment` | string | `consumer`, `small_business`, `affluent` or `new_to_bank`. |
| `decisions` | int | Decisions made in that hour. Follows an hour-of-day profile (busiest 09:00 to 17:00), is lower on Saturday and Sunday by segment, and has day-to-day and hour-to-hour noise. |
| `error_rate` | float | Share of requests that returned an error, a timeout or an invalid output. Binomial noise: a small segment at night is very noisy. |
| `latency_p95_ms` | float | 95th percentile latency. Gaussian noise of 8% of the segment mean; no dependence on load. |
| `drift_score` | float | A 0-to-1 style input drift score. Gaussian noise of 0.015. |
| `override_rate` | float | Share of decisions a human reviewer overrode. Binomial noise. |
| `complaints` | int | Customer complaints that hour. Poisson, proportional to decisions, plus a lagged term proportional to the bad decisions an event causes. |

The first rows:

| hour | segment | decisions | error_rate | latency_p95_ms | drift_score | override_rate | complaints |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | `consumer` | 80 | 0.0125 | 165.2 | 0.0881 | 0.0125 | 0 |
| 0 | `small_business` | 20 | 0.0 | 206.7 | 0.0804 | 0.0 | 0 |
| 0 | `affluent` | 11 | 0.0 | 162.1 | 0.0606 | 0.0 | 0 |
| 0 | `new_to_bank` | 10 | 0.1 | 264.6 | 0.089 | 0.0 | 0 |
| 1 | `consumer` | 55 | 0.0 | 175.1 | 0.08 | 0.01818 | 0 |
| 1 | `small_business` | 16 | 0.0 | 201.0 | 0.0552 | 0.1875 | 0 |

Segment baselines (generator inputs, so a small segment is noisier than a large one):

| segment | decisions per hour at the weekday peak | error rate | latency p95 ms | drift score | override rate | Saturday and Sunday volume |
| --- | --- | --- | --- | --- | --- | --- |
| `consumer` | 420 | 0.008 | 180 | 0.08 | 0.02 | 0.85 x |
| `small_business` | 95 | 0.011 | 210 | 0.085 | 0.035 | 0.35 x |
| `affluent` | 60 | 0.007 | 170 | 0.075 | 0.03 | 0.6 x |
| `new_to_bank` | 45 | 0.016 | 240 | 0.09 | 0.06 | 0.7 x |

The metrics describe the **model path** whether or not it is serving. That assumes the model path keeps scoring in shadow while a segment runs on the rules path, so recovery can be judged. The shadow scoring is a design requirement (🔴 not built), not something the prototype does.

Total decisions over the 90 days: 758,236. Ten benign one-hour blips are scattered outside the events: six error-rate spikes (a retry storm) and four latency spikes (a slow minute). They are not degradations, so a trip on one is a false trip. They are not listed in any file; the generator prints their count.

## `degradation_events.csv` — 12 events (the truth)

| Column | Type | What it is |
| --- | --- | --- |
| `event_id` | string | `E01` to `E12`, in time order. |
| `start_hour`, `end_hour` | int | The event is active for `start_hour <= h < end_hour`. |
| `type` | string | `model_regression`, `upstream_outage`, `drift`, `tool_failure` or `silent_error`. |
| `segments` | string | The segments it hits, semicolon-separated. |
| `bad_decision_rate` | float | The share of decisions in the affected segments that are bad while the event is active, relative to a healthy model path. |
| `ramp_hours` | int | For `drift`, how many hours the effect takes to build to full strength (12). Otherwise 0. |
| `signal_scale` | float | A multiplier on how far the event moves the signals. Below 1 is a milder event. |

| event_id | start_hour | end_hour | type | segments | bad_decision_rate | ramp_hours | signal_scale |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E01 | 110 | 116 | `tool_failure` | `new_to_bank` | 0.3 | 0 | 1.0 |
| E02 | 246 | 306 | `drift` | `affluent` | 0.14 | 12 | 1.0 |
| E03 | 393 | 407 | `model_regression` | `consumer;small_business` | 0.18 | 0 | 1.0 |
| E04 | 561 | 565 | `upstream_outage` | `consumer;small_business;affluent;new_to_bank` | 0.35 | 0 | 1.0 |
| E05 | 730 | 766 | `silent_error` | `small_business` | 0.1 | 0 | 1.0 |
| E06 | 982 | 990 | `tool_failure` | `affluent;small_business` | 0.28 | 0 | 0.9 |
| E07 | 1232 | 1262 | `silent_error` | `new_to_bank` | 0.09 | 0 | 1.0 |
| E08 | 1499 | 1515 | `model_regression` | `affluent` | 0.2 | 0 | 1.0 |
| E09 | 1623 | 1628 | `upstream_outage` | `consumer;small_business` | 0.32 | 0 | 0.9 |
| E10 | 1737 | 1777 | `silent_error` | `affluent` | 0.11 | 0 | 1.0 |
| E11 | 1875 | 1923 | `drift` | `new_to_bank` | 0.2 | 12 | 1.0 |
| E12 | 2029 | 2041 | `model_regression` | `consumer` | 0.16 | 0 | 0.8 |

What each type does to the signals while it is active (generator inputs; a `silent_error` moves nothing enough to see, which is its definition):

| type | error rate added | override rate added | latency multiplier | drift score added | signals decay after the end (hours) | complaints per bad decision | complaint lag (hours) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `model_regression` | +0.03 | +0.04 | 1 x | +0.03 | none | 0.08 | 2 |
| `upstream_outage` | +0.2 | +0.015 | 3 x | +0.01 | 2 | 0.15 | 1 |
| `drift` | +0.006 | +0.02 | 1 x | +0.28 | 8 | 0.04 | 3 |
| `tool_failure` | +0.08 | +0.01 | 1.8 x | +0 | 1.5 | 0.1 | 1 |
| `silent_error` | +0.001 | +0.002 | 1 x | +0 | none | 0.003 | 3 |

Seven events fall in days 1-60 and five in days 61-90. Eight hit a single segment; one, E04, hits all four. Three are silent errors (E05, E07, E10). Complaints follow the bad decisions with a lag, so a small segment produces few of them: that is why a manual process notices small segments late or never.

## `fallback_rules.csv` — the rules path versus the model path (stubs)

**These are stub numbers set by the generator, not measurements of any real model or rules engine.** `quality_gap` is the share of decisions the rules path gets worse than a healthy model would, per segment. It is the cost of every decision moved to the rules path, and the thing that makes an unnecessary switch expensive. The thin-file `new_to_bank` segment has the widest gap.

| segment | model_path_quality | rules_path_quality | quality_gap |
| --- | --- | --- | --- |
| `consumer` | 0.94 | 0.9 | 0.04 |
| `small_business` | 0.91 | 0.84 | 0.07 |
| `affluent` | 0.93 | 0.85 | 0.08 |
| `new_to_bank` | 0.88 | 0.76 | 0.12 |

**How bad decisions are counted.** All counts are relative to a healthy model path and are expected values (decisions × rate), not sampled outcomes. On the model path during an event, a share of decisions equal to the event's `bad_decision_rate` is bad. On the rules path, a share equal to the segment's `quality_gap` is worse than a healthy model would have done. Both are written "bad decisions" in the walkthrough.

## `drills.csv` — 10 planned fallback drills

| Column | Type | What it is |
| --- | --- | --- |
| `drill_id` | string | `D01` to `D10`. |
| `date_hour` | int | The hour the drill ran (same clock as the metrics). |
| `scenario` | string | `full_switch_off`, `segment_switch_off`, `upstream_outage`, `model_regression`, `tool_failure` or `recovery_return`. |
| `minutes_to_fallback` | int | Minutes until the fallback was live. Empty when the drill failed. |
| `success` | yes/no | Whether the fallback went live. |
| `failure_reason` | string | Why it failed. Empty on success. |
| `rules_version_age_days` | int | Age of the rules version the drill ran on. |

| drill_id | date_hour | scenario | minutes_to_fallback | success | failure_reason | rules_version_age_days |
| --- | --- | --- | --- | --- | --- | --- |
| D01 | 82 | `full_switch_off` |  | no | rules version stale: rejected current product codes | 38 |
| D02 | 250 | `full_switch_off` |  | no | rules version stale: rejected current product codes | 45 |
| D03 | 446 | `upstream_outage` | 47 | yes |  | 53 |
| D04 | 634 | `segment_switch_off` |  | no | rules version stale: rate table out of date | 61 |
| D05 | 851 | `model_regression` | 58 | yes |  | 2 |
| D06 | 1018 | `full_switch_off` | 53 | yes |  | 9 |
| D07 | 1239 | `recovery_return` |  | no | switch config not deployed to one segment | 18 |
| D08 | 1498 | `tool_failure` | 57 | yes |  | 29 |
| D09 | 1762 | `segment_switch_off` | 38 | yes |  | 3 |
| D10 | 2030 | `full_switch_off` | 48 | yes |  | 14 |

How the log is made: the ten dates and scenarios are fixed in the generator. The rules path is refreshed ad hoc (the generator's refresh calendar puts refreshes at days -35, 33 and 70), which sets each drill's `rules_version_age_days`. A drill fails with a 15% chance on any run, plus 45 more points when the rules version is older than 30 days. A drill that works takes 22 to 58 minutes plus a scenario add-on. The draws come from the seeded generator, so the same drills fail on every run; ten drills are far too few to estimate a real failure rate.

## `policy.csv` — the policy design and the assumptions

Window, persistence, warn and clear fractions, cool-off, recovery criteria, the false-trip budget, the manual process (when a person notices, how long the switch takes) and the drill targets. The **thresholds and weights here are assumptions of a modeled bank, not legal advice.** The trip level is the one value left as `fitted`: `src/step_04_with_killswitch.py` fits it on days 1-60 and writes it to `src/out/step_04_fitted_policy.csv`.

| parameter | scope | value | unit | set_by |
| --- | --- | --- | --- | --- |
| window_hours | all signals | 3 | hours | design |
| min_window_decisions | error_rate and override_rate | 60 | decisions | design |
| persistence_hours | trip and warn | 2 | hours | design |
| trip_level | per segment | fitted | standard errors | fitted_by_step_04 |
| warn_fraction | warn tier | 0.75 | fraction of trip level | design |
| clear_fraction | hysteresis band | 0.50 | fraction of trip level | design |
| clear_hours | recovery criteria | 4 | hours | design |
| cool_off_hours | fallback | 6 | hours | design |
| trip_level_candidates | fit grid | 3.0;3.5;4.0;4.5;5.0;5.5;6.0;7.0;8.0;10.0 | standard errors | design |
| false_trip_budget_days_1_60 | fit rule | 2 | false trips | assumption of a modeled bank |
| fit_days | scoring | 1-60 | days | design |
| held_out_days | scoring | 61-90 | days | design |
| justify_grace_hours | scoring | 6 | hours | design |
| re_trip_window_hours | scoring | 6 | hours | design |
| manual_cluster_complaints_3h | status quo | 12 | complaints in 3 hours, all segments | assumption of a modeled bank |
| manual_decision_delay_hours | status quo | 4 | hours | assumption of a modeled bank |
| drill_target_minutes | drill scorecard | 30 | minutes | assumption of a modeled bank |
| max_rules_version_age_days | drill scorecard | 30 | days | assumption of a modeled bank |
| drill_cadence_days | drill scorecard | 45 | days | assumption of a modeled bank |

---

## Headline scenario — E08, the affluent regression

| Source | What it gives you |
| --- | --- |
| `degradation_events.csv` | E08: a model regression in `affluent` from hour 1499 for 16 hours, 20% of the affected decisions bad. |
| `metrics_hourly.csv` | The affluent rows from hour 1499: error rate and override rate rise, drift score moves a little, latency does not. The segment makes few decisions an hour, so the rates are noisy. |
| `fallback_rules.csv` | Affluent's quality gap: 0.08. Moving it to the rules path costs eight bad decisions in a hundred while the model is healthy. |
| `policy.csv` | The window, persistence, cool-off and recovery rules that turn those rows into a trip and a return. |

Replay the walkthrough and you see it three ways: the manual plan never notices (the busiest 3 hours of complaints reach 8 against a notice level of 12), one threshold on the overall error rate never crosses, and KillSwitch warns, trips affluent only, and brings it back 5 hours after the event ends.
