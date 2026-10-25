# Sample Data — IncidentLedger walkthrough

Five CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`SEED = 20261018` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files. The generator uses only the Python standard library and runs on Python 3.9. **No customer data. No real bank, system, vendor, regulator dataset or incident. The titles and descriptions are filled-in templates written by the generator, not by a person or a model.**

**The truth is known because the data is synthetic.** The generator decides each incident's true category, true severity and root cause, and which notices were sent late or never. A real queue does not hand you that; the first job in a real deployment is a labeled sample of real incident tickets, labeled by people.

The headline scenario the walkthrough resolves: **a modeled bank logs 120 AI incidents in one quarter in a ticket queue. 87 notification deadlines apply under its policy, 39 are missed (17 sent late, 22 never sent), and the queue shows none of them. With IncidentLedger, every incident is rated by rubric, every clock is evaluated, and every missed deadline is flagged.**

---

## `incidents.csv` — 120 incident tickets

One row per ticket, as a queue would hold it. Times are integer hours from `EPOCH` (hour 0 = 2026-07-01T00:00).

| Column | Type | What it is |
| --- | --- | --- |
| `incident_id` | string | `INC-0001` onward, in the order tickets were reported. |
| `reported_at` | int (hours) | When the ticket was filed. Between hour 88 and hour 2251 (2026-07-04 to 2026-10-02); the generator's window is hour 72 to hour 2290. |
| `reporter_priority` | `P1` to `P4` | The priority the reporter picked. This is what the queue sorts on. |
| `reporter_category` | free text | What the reporter typed in the category box: 81 distinct strings, with mixed case, stray spaces and question marks. |
| `title`, `description` | text | Filled in from templates for the incident's true category. Some are written to be hard (below). |
| `system` | string | One of 14 invented system names such as `retail-chat-assistant` or `fraud-alert-ranker`. |
| `change_id` | string | The release or model change the reporter linked, when they knew one. Empty otherwise. |
| `customers_affected`, `regulated_decision_involved`, `pii_exposed`, `financial_impact_band`, `duration_hours` | int / 0-1 / 0-1 / `none`, `low`, `medium`, `high` / int | The five facts the severity rubric reads. |
| `detected_at` | int (hours) | When anyone first noticed the problem. Never later than `reported_at`. |
| `determined_at` | int (hours) or empty | When the bank decided this was a real incident. Empty means nobody has recorded it at `AS_OF`: 5 incidents. |

`AS_OF` is hour 2304 (2026-10-05T00:00). Nothing reads the clock; the scripts use this constant.

## `truth.csv` — what the generator decided

| Column | Type | What it is |
| --- | --- | --- |
| `incident_id` | string | Join key. |
| `true_category` | string | One of seven classes: wrong output, unfair outcome, data exposure, security and injection, availability, regression after change, misuse. |
| `true_severity` | `S1` to `S4` | The rubric applied to the five fields. |
| `root_cause_key` | string | `RC-001` onward. Tickets with the same key are the same root cause: 78 keys for 120 tickets. |
| `hard_case` | string or empty | Marks the 10 incidents written to be hard for the classifier (below). Empty for the rest. |

Class sizes: wrong output 26, unfair outcome 12, data exposure 16, security and injection 16, availability 20, regression after change 20, misuse 10. Severity: S1 17, S2 48, S3 26, S4 29.

**The rubric** (assumptions of a modeled bank, not a statement of any rule). The first level that fires wins.

| Level | Fires when |
| --- | --- |
| S1 | financial impact band is high; or personal data is exposed for 100 customers or more; or a regulated decision affects 500 customers or more |
| S2 | band is medium; or personal data is exposed; or a regulated decision is involved; or 2000 customers or more; or the incident lasted 48 hours or more |
| S3 | band is low; or 100 customers or more; or 12 hours or more |
| S4 | none of the above |

The financial impact bands are labels, not dollar amounts in the data.

## `policy.csv` — the notification clocks of a modeled bank

These are **assumptions of a modeled bank, not legal advice or a statement of any rule.** The hour values are assumed values to confirm with counsel. Every clock starts at determination.

| clock_id | clock_name | applies_to | hours | anchor |
| --- | --- | --- | --- | --- |
| CK1 | Internal executive notice | sev_s1 | 4 | determination |
| CK2 | Regulator notice | notification_incident | 36 | determination |
| CK3 | Customer notice | pii_exposed | 720 | determination |
| CK4 | Serious-incident report to an AI regulator | serious_incident | 360 | determination |

`applies_to` is a small vocabulary: `sev_s1` (the incident is S1), `notification_incident` (S1, or S2 with personal data exposed or a regulated decision involved), `pii_exposed`, `serious_incident` (S1 with personal data exposed or a regulated decision involved). Under the rubric, 43 incidents are notification incidents, 16 expose personal data and 11 are serious incidents.

## `notifications.csv` — what was actually sent

| Column | Type | What it is |
| --- | --- | --- |
| `notification_id` | string | `N-0001` onward. |
| `incident_id`, `clock_id` | string | Which incident, and which clock the notice answers. |
| `sent_at` | int (hours) | When it went. Never after `AS_OF`. |

The generator decided, for each clock that applies to a determined incident, whether the notice went on time, late or not at all. The weights below are assumptions for this test set, not observed rates: on time / late / not sent is 55 / 25 / 20 for CK1, 50 / 25 / 25 for CK2, 45 / 25 / 30 for CK3 and 40 / 25 / 35 for CK4 (percent). A notice that would have gone after `AS_OF` is not in the file, so the clock is still running or already breached. 51 notices are in the file.

## `actions.csv` — follow-up actions

| Column | Type | What it is |
| --- | --- | --- |
| `action_id`, `incident_id` | string | `A-0001` onward, and the incident it belongs to. |
| `action`, `owner` | text | A follow-up from a short list per category, and an invented owner code such as `owner-07`. |
| `due_at` | int (hours) | Determination (or report time) plus 7, 14, 30 or 60 days. |
| `status` | `open`, `in_progress`, `closed` | |
| `closed_at` | int (hours) or empty | Only for closed actions. |
| `evidence_link` | `yes` / `no` | Whether evidence is attached. Open actions are `no`. |

200 actions. 109 closed, of which 27 have no evidence link; 57 of the 91 not closed are past due at `AS_OF`.

---

## How the hard cases were written

10 incidents are written to be hard for a fields-first, keywords-second classifier. They are marked in `truth.csv`:

| `hard_case` | Count | What is hard about it |
| --- | --- | --- |
| `tie` | 3 | The text carries one keyword for two classes (for example "timed out" and "incorrect"). |
| `outvoted` | 1 | The wrong class has more keywords than the right one. |
| `no_keyword` | 2 | The text says something is off and names nothing. |
| `cause_vs_effect` | 3 | Personal data is exposed, but the cause is an injection or a misuse. The field rule sees the effect. |
| `no_change_word` | 1 | A regression with a linked change id, but the reporter never wrote that anything changed. |

The clear cases use templates and keyword lists that I wrote, so the classifier scores well on them by construction. The number that carries information is what happens on the hard ones, and it is a property of this test set, not an estimate of how real incident text behaves.

Other deliberate features: 2 of 20 regression tickets carry no `change_id` (the reporter did not know); 6 tickets of other classes do carry one; 3 data exposure incidents expose no personal data; 29 root causes appear in more than one ticket.

## Seed choice and how the data was tuned

`SEED = 20261018` was chosen once and never searched. I did change distribution parameters, the rubric thresholds, the system lists per category, the end of the reporting window and the spacing of repeat tickets several times, and every change reshuffles every row. The first draft had three S4 incidents out of 120, and the clocks had almost no running examples. I kept adjusting until each severity level had at least 15 incidents, a few customer notices were still running at `AS_OF`, and the linker was not trivially wrong because every system carried every category. The committed files reflect the last run. The data is dense on purpose, 120 incidents in one quarter, so that every effect appears often enough to count. It is a test set, not an estimate of how often real AI incidents happen or how often real teams miss deadlines.

## First rows

**`incidents.csv`**

| incident_id | reported_at | reporter_priority | reporter_category | system | change_id | customers_affected | pii_exposed | detected_at | determined_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| INC-0001 | 88 | P4 | security | payments-routing-agent |  | 0 | 0 | 79 | 96 |
| INC-0002 | 104 | P2 | unfair decision | mortgage-prescreen-model |  | 898 | 0 | 96 | 124 |
| INC-0003 | 122 | P2 | quality drop | advisor-notes-tool | CHG-2508 | 4269 | 0 | 119 | 145 |

**`truth.csv`**

| incident_id | true_category | true_severity | root_cause_key | hard_case |
| --- | --- | --- | --- | --- |
| INC-0001 | security_injection | S3 | RC-001 |  |
| INC-0002 | unfair_outcome | S1 | RC-002 |  |
| INC-0003 | regression_after_change | S2 | RC-003 |  |

**`notifications.csv`**

| notification_id | incident_id | clock_id | sent_at |
| --- | --- | --- | --- |
| N-0001 | INC-0002 | CK1 | 131 |
| N-0002 | INC-0009 | CK1 | 272 |
| N-0003 | INC-0009 | CK2 | 271 |

**`actions.csv`**

| action_id | incident_id | action | owner | due_at | status | closed_at | evidence_link |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A-0001 | INC-0001 | Test the fix against the crafted input | owner-11 | 432 | closed | 540 | yes |
| A-0002 | INC-0001 | Add an input filter for the pattern | owner-07 | 432 | closed | 434 | yes |
| A-0003 | INC-0002 | Agree a remediation with the model owner | owner-02 | 844 | closed | 882 | yes |

## Headline scenario — INC-0102

| Source | What it gives you |
| --- | --- |
| `incidents.csv` | "Exposed loan file in an export" on `advisor-notes-tool`, filed by the reporter as P4. |
| `truth.csv` | The rubric says S1: personal data exposed for 390 customers (100 or more). Category: data exposure. |
| `notifications.csv` | What was sent, and when, for each clock that applies. |
| `actions.csv` | The follow-up actions and whether each has evidence. |

Replay the walkthrough and you see the same incident three ways: the ticket queue (position 110 of 120, no clock), the queue sorted by priority (the same), and IncidentLedger (S1, and 3 missed deadlines flagged: Internal executive notice breached (448 h); Regulator notice breached (416 h); Customer notice running (268 h left); Serious-incident report to an AI regulator breached (92 h)).
