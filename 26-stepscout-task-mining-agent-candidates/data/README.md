# Sample Data — StepScout walkthrough

Six files drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`SEED = 20261018` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files. The generator uses only the Python standard library and runs on Python 3.9. **No real bank, process, vendor or person. The desktop events and the status events are written by the generator, not by a miner or a case system, and no model is used anywhere in this repo.** The one real log this project touches is not stored here: [`real/`](./real/README.md) holds a fetch script and the terms for a public loan-application log that the real-data mode reads. Worker ids are pseudonymous (`W01` to `W14`), and the desktop events carry a count of typed characters and never the text.

**The truth is known because the data is synthetic.** The generator decides which steps exist, how long each takes, what a worker does in it and which steps an agent can take over, so it can score every call. A real estate does not hand you that: the first job in a real deployment is a sample of steps that a person who knows the work has classified by hand.

**Parameters.** Every generator parameter (the step timings, the waits, the override and free-text levels, the reason mix, the reopen rate, the phone-call share) is my assumption about how such a queue behaves. The parameters set the size of every effect in the walkthrough, so each result is a property of this data and not an estimate of a real queue. I planted the behavior the classifier reads, and the answer key follows the same design, so classification accuracy shows the method works on this data, not on a real one.

The headline scenario the walkthrough resolves: **a wire-repair queue handles 1,500 cases in 30 days through 16 steps, 14 workers and 6 applications. The interview map describes a path that 24.8% of cases follow. The case-system log never records 3 steps, and 44.8% of touch time is outside the case system. Its volume-first top 10 holds 6 agent-ready steps. StepScout's holds 9, and one judgment hidden in a phone call is the known miss.**

What the generator prints when it runs:

```
cases.csv             1,500 cases, 151 variants, 140 reopened
desktop_events.csv   53,584 events, 1,308 without a step label
system_events.csv    19,050 status events
exact happy path, no reopen: 372 cases (24.8%)
overlapping events for one worker: 0
```

---

## Time and the calendar

Workers work 08:00 to 18:00, Monday to Friday, with no holidays. Hour zero is a constant (`EPOCH = 2026-09-01`, a Tuesday; the clock is never read). Cases are created on the 22 working days from 1 to 30 September 2026, weighted toward the morning and slightly toward Monday. Every wait is in working time, so no wait contains a night or a weekend; cases that are slow to finish run into October. Timestamps are local wall-clock, `YYYY-MM-DDTHH:MM:SS`.

## `cases.csv` — 1,500 cases

| Column | Type | What it is |
| --- | --- | --- |
| `case_id` | string | `C00001` to `C01500`, in order of creation. |
| `created` | timestamp | When the exception landed in the queue. |
| `first_closed`, `final_closed` | timestamp | The first and the last CLOSED status. They differ only for a reopened case. |
| `reason_code` | string | Why the payment was returned. It drives the odds of an ambiguous match, a reply from another party and a cutoff check. |
| `variant_id` | string | `V01` is the most common true path, `V02` the next, and so on. The path includes rework. |
| `reopened` | 0 or 1 | The reopen flag. |
| `primary_worker` | string | The operator who handles most steps of the case. |
| `offdesk_min_truth` | number | **Truth.** Minutes of work off the desktop (phone calls) on the case. No event file records it. The step scripts use it only to say what is still invisible. |
| `true_path` | string | **Truth.** The steps the case took, in order, rework included. Step 3 uses it for the share of cases on the documented path. |

| case_id | created | first_closed | final_closed | reason_code | variant_id | reopened | primary_worker | offdesk_min_truth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `C00001` | 2026-09-01T08:06:59 | 2026-09-02T09:16:43 | 2026-09-02T09:16:43 | `R02_name_mismatch` | `V62` | 0 | `W08` | 13.2 |
| `C00002` | 2026-09-01T08:07:01 | 2026-09-01T12:28:06 | 2026-09-01T12:28:06 | `R06_cutoff_missed` | `V02` | 0 | `W05` | 0.0 |
| `C00003` | 2026-09-01T08:07:06 | 2026-09-02T16:38:01 | 2026-09-02T16:38:01 | `R05_missing_field` | `V03` | 0 | `W06` | 13.7 |
| `C00004` | 2026-09-01T08:08:50 | 2026-09-02T14:53:53 | 2026-09-02T14:53:53 | `R05_missing_field` | `V08` | 0 | `W04` | 15.0 |
| `C00005` | 2026-09-01T08:20:30 | 2026-09-01T16:11:11 | 2026-09-01T16:11:11 | `R02_name_mismatch` | `V01` | 0 | `W09` | 0.0 |

How a case is generated, in order: a reason code is drawn; the reason sets the odds that the match is ambiguous (S07 runs, and 12% of the time twice), that a reply from the originator is needed (S16, then S13 one or more times), and that a cutoff check runs (S15). A route is chosen (S14) in 85% of cases that had an ambiguity or a reply and in 20% of the others. The draft goes to the second person (S08 then S09); 10% of cases are sent back for a second draft and 3% of cases twice. Then S10, S11 and S12. 9% of cases are reopened after the first close: the operator opens it again after a wait of about a day and a half, then S03, S13 (once or twice), S14 (half the time), S08, S09, S10, S11, S12.

| reason_code | share of cases | ambiguous match | needs a reply | cutoff check |
| --- | --- | --- | --- | --- |
| `R01_invalid_account` | 26% | 12% | 30% | 15% |
| `R02_name_mismatch` | 22% | 62% | 30% | 10% |
| `R03_closed_account` | 14% | 10% | 45% | 15% |
| `R04_wrong_bank_id` | 16% | 10% | 20% | 20% |
| `R05_missing_field` | 12% | 5% | 70% | 10% |
| `R06_cutoff_missed` | 10% | 5% | 10% | 90% |

## `desktop_events.csv` — 53,584 events

| Column | Type | What it is |
| --- | --- | --- |
| `case_id` | string | The case the worker was working. |
| `worker_id` | string | Pseudonymous worker. |
| `application` | string | `case_system`, `payments_hub`, `spreadsheet`, `matching_tool`, `screening_app` or `email`. |
| `action` | string | `open`, `read`, `search`, `copy`, `paste`, `type`, `select`, `edit_cell`, `submit`, `send` or `override_value` (the worker changed a value the system proposed). |
| `step_id` | string | The step the miner infers from application and action. Empty for 2.4% of events, where it cannot tell. **Steps 1 to 3 never read it; step 4 does.** |
| `start`, `end` | timestamp | The event. Touch time is the sum of the durations. |
| `typed_chars` | int | How many characters were typed in the event. A count, never the text. |

| case_id | worker_id | application | action | step_id | start | end | typed_chars |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `C00004` | `W04` | `case_system` | `open` | `S01` | 2026-09-01T08:32:39 | 2026-09-01T08:33:42 | 0 |
| `C00004` | `W04` | `case_system` | `read` | `S02` | 2026-09-01T08:34:04 | 2026-09-01T08:35:20 | 0 |
| `C00004` | `W04` | `case_system` | `copy` | `S03` | 2026-09-01T08:35:40 | 2026-09-01T08:35:51 | 0 |
| `C00004` | `W04` | `payments_hub` | `paste` | `S03` | 2026-09-01T08:35:53 | 2026-09-01T08:35:59 | 0 |
| `C00004` | `W04` | `payments_hub` | `search` | `S03` | 2026-09-01T08:36:01 | 2026-09-01T08:38:07 | 0 |

Events of one step run are close together (seconds apart); a step run is a new occurrence when the step changes or the gap passes 10 minutes. A worker never has two overlapping events: the generator books each worker's time in 10-second slots, and a case waits for a free worker.

## `system_events.csv` — 19,050 status changes

| Column | Type | What it is |
| --- | --- | --- |
| `case_id` | string | The case. |
| `status` | string | `RECEIVED` (written by the system), `OPENED`, `REASON_CODED`, `MATCH_CHECKED`, `SCREENED`, `MATCH_REVIEWED`, `INFO_REQUESTED`, `REPLY_LOGGED`, `ROUTE_SET`, `CORRECTION_DRAFTED`, `APPROVED`, `RESUBMITTED`, `NOTE_ADDED`, `CLOSED` or `REOPENED`. |
| `ts` | timestamp | When the status changed, within seconds of the end of the step that posts it. |
| `worker_id` | string | Who changed it, or `system`. |

| case_id | status | ts | worker_id |
| --- | --- | --- | --- |
| `C00001` | `RECEIVED` | 2026-09-01T08:06:59 | `system` |
| `C00001` | `OPENED` | 2026-09-01T08:51:49 | `W08` |
| `C00001` | `REASON_CODED` | 2026-09-01T08:53:17 | `W08` |
| `C00001` | `MATCH_CHECKED` | 2026-09-01T09:09:52 | `W08` |
| `C00001` | `SCREENED` | 2026-09-01T09:15:12 | `W08` |

Three steps post no status: S03 (the lookup in the payments hub), S04 (the copy through a spreadsheet) and S15 (the cutoff check). Work in those steps is real, and the log never records that it happened.

## `sme_process_map.csv` — the interview

| Column | Type | What it is |
| --- | --- | --- |
| `seq`, `step_id`, `step` | | The 11 steps of the happy path, in order. S07, S13, S14, S15 and S16 are not on it. |
| `systems_named` | string | The system the expert names for the step: three of the six applications. |
| `owner_role` | string | Who does it. |
| `minutes_per_step` | int | The expert's estimate. Total 38 minutes. |

| seq | step_id | step | systems_named | owner_role | minutes_per_step |
| --- | --- | --- | --- | --- | --- |
| 1 | `S01` | Open the exception from the queue | case system | operator | 2 |
| 2 | `S02` | Read the reason code | case system | operator | 2 |
| 3 | `S03` | Look up the original payment | payments hub | operator | 5 |
| 4 | `S04` | Copy the beneficiary details | case system | operator | 3 |

## `step_catalog.csv` — the register, the answer key and the planted parameters

16 steps. Three groups of columns:

- **Register** (what a team could supply): `step_id`, `step_name`, `process_order`, `status_event` (the status the step posts, empty if none), `restricted_data`, `control_flag` (the step is a four-eyes control), `gated_by` (the step may run only after this one) and `data_fields`.
- **Answer key:** `truth_class`, the generator's own. `AGENT` is rule-based and data-complete, `AGENT_HITL` is a step where an agent drafts or acts and a person approves, `HUMAN_JUDGMENT` is left to a person, `HUMAN_CONTROL` is a control that must stay with a person. The classifier never reads this column; step 4 loads the register and the key through separate functions and checks that shuffling the key leaves every class unchanged.
- **Planted parameters** (`planted_*`): what the generator does in the events for the step. They are documented here so a reader can compare them with what step 4 measures; no step reads them except the app, to show planted against measured.

| step_id | step_name | process_order | status_event | restricted_data | control_flag | gated_by | truth_class |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `S01` | `open_exception` | 1 | `OPENED` | 0 | 0 |  | `AGENT` |
| `S02` | `read_reason_code` | 2 | `REASON_CODED` | 0 | 0 |  | `AGENT` |
| `S15` | `check_cutoff_and_value_date` | 3 |  | 0 | 0 |  | `AGENT` |
| `S03` | `lookup_original_payment` | 4 |  | 0 | 0 |  | `AGENT` |
| `S04` | `copy_beneficiary_fields` | 5 |  | 0 | 0 |  | `AGENT` |
| `S05` | `match_name_account` | 6 | `MATCH_CHECKED` | 0 | 0 |  | `AGENT` |
| `S06` | `screen_watchlist` | 7 | `SCREENED` | 1 | 0 |  | `AGENT` |
| `S07` | `judge_ambiguous_match` | 8 | `MATCH_REVIEWED` | 1 | 0 |  | `HUMAN_JUDGMENT` |
| `S16` | `request_info_from_originator` | 9 | `INFO_REQUESTED` | 0 | 0 |  | `AGENT_HITL` |
| `S13` | `triage_beneficiary_bank_reply` | 10 | `REPLY_LOGGED` | 0 | 0 |  | `HUMAN_JUDGMENT` |
| `S14` | `choose_resolution_route` | 11 | `ROUTE_SET` | 0 | 0 |  | `HUMAN_JUDGMENT` |
| `S08` | `draft_correction` | 12 | `CORRECTION_DRAFTED` | 0 | 0 |  | `AGENT_HITL` |
| `S09` | `approve_four_eyes` | 13 | `APPROVED` | 0 | 1 |  | `HUMAN_CONTROL` |
| `S10` | `resubmit_payment` | 14 | `RESUBMITTED` | 0 | 0 | `S09` | `AGENT_HITL` |
| `S11` | `write_case_note` | 15 | `NOTE_ADDED` | 0 | 0 |  | `AGENT` |
| `S12` | `close_case` | 16 | `CLOSED` | 0 | 0 |  | `AGENT` |

Planted parameters, step by step (touch time is lognormal around the median; text and override levels are means per run; repeats are the expected runs per case that includes the step, from the path rules, rework excluded):

| step_id | step_name | truth_class | planted_median_touch_min | planted_timing_sigma | planted_text_chars | planted_override_rate | planted_cross_app_copy | planted_repeats_per_case | planted_offdesk_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `S01` | `open_exception` | `AGENT` | 1.5 | 0.25 | 0 | 0.0 | 0.0 | 1.0 | 0 |
| `S02` | `read_reason_code` | `AGENT` | 1.0 | 0.25 | 0 | 0.0 | 0.0 | 1.0 | 0 |
| `S15` | `check_cutoff_and_value_date` | `AGENT` | 1.5 | 0.2 | 0 | 0.0 | 0.0 | 1.0 | 0 |
| `S03` | `lookup_original_payment` | `AGENT` | 4.0 | 0.35 | 0 | 0.02 | 0.55 | 1.0 | 0 |
| `S04` | `copy_beneficiary_fields` | `AGENT` | 5.0 | 0.3 | 0 | 0.02 | 0.95 | 1.0 | 0 |
| `S05` | `match_name_account` | `AGENT` | 3.0 | 0.35 | 15 | 0.06 | 0.0 | 1.0 | 0 |
| `S06` | `screen_watchlist` | `AGENT` | 3.5 | 0.3 | 40 | 0.0 | 0.0 | 1.0 | 0 |
| `S07` | `judge_ambiguous_match` | `HUMAN_JUDGMENT` | 9.0 | 0.6 | 240 | 0.55 | 0.3 | 1.12 | 0.2 |
| `S16` | `request_info_from_originator` | `AGENT_HITL` | 4.5 | 0.35 | 150 | 0.1 | 0.1 | 1.0 | 0 |
| `S13` | `triage_beneficiary_bank_reply` | `HUMAN_JUDGMENT` | 7.0 | 0.55 | 420 | 0.35 | 0.5 | 1.62 | 0 |
| `S14` | `choose_resolution_route` | `HUMAN_JUDGMENT` | 2.0 | 0.12 | 0 | 0.02 | 0.0 | 1.0 | 1.0 |
| `S08` | `draft_correction` | `AGENT_HITL` | 6.0 | 0.4 | 150 | 0.22 | 0.0 | 1.13 | 0 |
| `S09` | `approve_four_eyes` | `HUMAN_CONTROL` | 2.5 | 0.4 | 0 | 0.01 | 0.0 | 1.13 | 0 |
| `S10` | `resubmit_payment` | `AGENT_HITL` | 2.5 | 0.3 | 0 | 0.0 | 0.7 | 1.0 | 0 |
| `S11` | `write_case_note` | `AGENT` | 3.0 | 0.3 | 210 | 0.04 | 0.0 | 1.0 | 0 |
| `S12` | `close_case` | `AGENT` | 1.0 | 0.2 | 0 | 0.0 | 0.0 | 1.0 | 0 |

Waits and phone calls:

| step_id | median wait before the step, working minutes | sigma | phone call before the step |
| --- | --- | --- | --- |
| `S01` | 75 | 0.8 | - |
| `S02` | 0.4 | 0.5 | - |
| `S15` | 0.4 | 0.5 | - |
| `S03` | 0.4 | 0.5 | - |
| `S04` | 0.4 | 0.5 | - |
| `S05` | 0.4 | 0.5 | - |
| `S06` | 1.0 | 0.5 | - |
| `S07` | 90 | 0.8 | 20% of runs, 3 to 8 min |
| `S16` | 10 | 0.6 | - |
| `S13` | 240 | 0.9 | - |
| `S14` | 15 | 0.6 | 100% of runs, 6 to 14 min |
| `S08` | 25 | 0.7 | - |
| `S09` | 110 | 0.8 | - |
| `S10` | 12 | 0.6 | - |
| `S11` | 2.0 | 0.5 | - |
| `S12` | 1.0 | 0.5 | - |

Workers are slower or faster by tenure band (under a year 1.15 times, one to three years 1.0, over three years 0.9).

## `workers.csv` — 14 workers

`worker_id`, `role` (operator, senior_operator or approver), `team` and `tenure_band`. Nine operators, three senior operators who handle S07, and two approvers; approvals (S09) are done by an approver or a senior operator who did not draft the case's correction.

---

## The decoys and the known miss

Two steps are decoys, added beyond the shared workflow:

- **S13 triage_beneficiary_bank_reply** is `HUMAN_JUDGMENT` and high volume. It posts a status, waits for a reply of about four hours, and repeats within a case. A ranking by volume times time puts it first.
- **S14 choose_resolution_route** is `HUMAN_JUDGMENT` and looks rule-based. On the desktop it is a short pick in the case system: a median of about two minutes, the tightest timing of any step, no free text, overrides in 2% of runs, one run per case. The worker makes the choice on a phone call before the pick (6 to 14 minutes, every run), and no event file records the call. It is the known miss.

S15 check_cutoff_and_value_date (`AGENT`) and S16 request_info_from_originator (`AGENT_HITL`) are ordinary additions.

## The six deficiencies and where they are planted

| # | Deficiency | Planted by |
| --- | --- | --- |
| 1 | The interview map covers one path | Reason-driven branches (S07, S15, S16, S13, S14), approval bounces and a 9% reopen rate: 151 true paths, 24.8% on the documented one |
| 2 | Off-system work is invisible | Five of six applications are outside the case system; S03, S04 and S15 post no status; the expert names three systems |
| 3 | Elapsed time is mostly wait | Waits of minutes to hours (a median of 240 minutes before a reply is triaged) against touch times of one to nine minutes; touch is 6.9% of elapsed time |
| 4 | Rework is hidden | Reopened cases repeat eight to ten step runs after a wait of about a day and a half; cycle time stops at the first close |
| 5 | Volume-first picks judgment-heavy steps | S13, S09, S07 and S14 post statuses and wait; the key marks them not agent-ready |
| 6 | No control screen | `restricted_data` on S06 and S07, `control_flag` on S09, `gated_by` on S10 |

## What it is not

It is a test set, not an estimate of any real queue. The signals the classifier reads were planted, and the key follows the same design. Real events are messier: workers override for reasons that are not judgment, a note can be long because a case is long, and a judgment can be made in a way no file records.

---

## Headline scenario — S04, the step the log never sees

| Source | What it gives you |
| --- | --- |
| `step_catalog.csv` | S04 copy_beneficiary_fields: `AGENT`, no status event, no restricted data, no control. |
| `desktop_events.csv` | 129.1 touch hours: values copied from the payments hub, pasted into a spreadsheet, copied again and pasted into the case system, in 94.9% of runs. |
| `system_events.csv` | Nothing: no status ever records S04. |
| `sme_process_map.csv` | The expert says 3 minutes. |

Replay the walkthrough and you see it three ways: the interview map has it at 3 minutes, the log never sees it, and StepScout measures its touch time, calls it `AGENT` and ranks it first.
