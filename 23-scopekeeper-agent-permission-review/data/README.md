# Sample Data — ScopeKeeper walkthrough

Six CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`SEED = 20261023` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files. The generator uses only the Python standard library and runs on Python 3.9. **No customer data. No real bank, agent, platform, vendor or incident. The calls are written by the generator, not by an agent or a model, and no model is used anywhere in this repo.**

**The truth is known because the data is synthetic.** The generator decides which scopes each agent needs and writes the calls from that decision, so it can say exactly which grants are unneeded and which are quarterly. A real estate does not hand you that; the first job in a real deployment is exporting a real grant store and a real tool-call log.

The headline scenario the walkthrough resolves: **a modeled bank runs 15 AI agents that hold 184 grants over 30 scopes. An annual recertification approves 182 of them. The call log shows 69 grants with no call in 90 days, and the generator's truth says 71 grants are not needed. With ScopeKeeper, the grants are compared with 7,994 calls and the agents get a smaller set that still covers every call.**

**Seed and settings.** The seed is one number chosen once, and no other seed was run. The agent definitions, scope lists, call rates and the settings in the table at the end were fixed from the design before the first run and were not changed after seeing results. The data is a test set built to exercise every effect often enough to count, not an estimate of how often real agents hold access they do not need.

---

## `agents.csv` — 15 agents

| Column | Type | What it is |
| --- | --- | --- |
| `agent_id` | string | `A-01` to `A-15`. |
| `owner` | string | An invented team code and name, for example `T-16 Payments`. |
| `purpose` | string | One line on what the agent does. |
| `service_account` | string | The credential the agent calls tools with. 7 agents share 3 accounts (`SA-01`, `SA-02`, `SA-03`); the rest have their own. |
| `risk_tier` | string | `high`, `medium` or `low`. An assumption of the modeled bank. |
| `launched_on` | date | When the agent went live. Grants dated this day are launch grants; later ones are after-launch grants. |

## `scope_catalog.csv` — 30 scopes

| Column | Type | What it is |
| --- | --- | --- |
| `scope` | string | `namespace:action`, for example `payments:initiate_wire`. A wildcard is `namespace:*`. |
| `kind` | string | `specific` or `wildcard`. 5 wildcards: `accounts:*`, `ledger:*`, `payments:*`, `messages:*`, `cases:*`. |
| `impact` | string | `read`, `write`, `external_message` or `money_movement`. A wildcard takes the highest impact of the scopes it reaches. |
| `needs_human_approval` | yes/no | Whether the catalog says a person must approve the call. A wildcard is `yes` if any scope it reaches is `yes`. |

A wildcard grant reaches every specific scope in its namespace. Calls always name a specific scope; a wildcard is only ever a grant.

## `grants.csv` — 184 grants

| Column | Type | What it is |
| --- | --- | --- |
| `agent_id` | string | Who holds the scope. |
| `scope` | string | The scope, specific or wildcard. No agent holds both a wildcard and a specific scope under it. |
| `granted_on` | date | Launch date for launch grants. After-launch grants are dated 45 days or more after launch and 21 or more days before the window starts. |
| `ticket_id` | string | The ticket that asked for the grant. Blank on 2 of 184 grants. The ticket is blank by a random draw that does not look at whether the grant is needed. |

32 of 184 grants (17.4%) were added after launch. The annual recertification reads only this file and the ticket column.

## `calls.csv` — 7,994 calls over 90 days

| Column | Type | What it is |
| --- | --- | --- |
| `call_id` | string | `C00001` onward, in day order. |
| `agent_id` | string | The agent tag in the log. Empty on a call through a shared service account when the tag was not logged. |
| `day` | int | 1 to 90. Day 1 is 2026-07-20 and day 90 is 2026-10-17, the review date. |
| `scope_used` | string | The specific scope the call used. |
| `human_approved` | string | `yes`, `no` or `not_required`. `no` on a scope that needs approval is a call logged without the approval the catalog requires. |
| `service_account` | string | The credential the call was made with. |

The rate for each line was set per agent and scope; Saturday and Sunday carry a lower share of traffic. On a shared account the tag is logged on half the calls, so 1,723 calls (21.6%) carry no agent tag. Every call is permitted by a grant of the agent that made it; the generator asserts this before writing.

## `rare_use_truth.csv` — 10 quarterly grants

| Column | Type | What it is |
| --- | --- | --- |
| `agent_id`, `scope` | strings | The grant. |
| `last_use_date` | date | Before the 90-day window starts. |
| `cycle_days` | int | Days between uses: a little over a quarter. |
| `next_use_date` | date | After the review date, so the 90-day window contains no use. |
| `calls_next_quarter` | int | How many calls the next use makes. This is what the cut would deny. |
| `why` | string | The reason the agent needs the scope, for example `quarter-end close pack`. |

These grants are legitimate and a 90-day review sees them as unused. 2 of them survive only because a sibling on a shared account calls the same scope; the other 8 are removed, and the first quarter after the cut would deny 51 calls.

## `needed_truth.csv` — what each grant is for

| Column | Type | What it is |
| --- | --- | --- |
| `agent_id`, `scope` | strings | The grant. |
| `needed` | yes/no | Whether the agent really needs it. |
| `basis` | string | `daily_use`, `occasional_use`, `quarterly_cycle`, `added_after_launch_used`, `wildcard_partly_used`, `wildcard_all_members_used`, `launch_leftover`, `added_after_launch_unused` or `wildcard_unused`. |
| `needed_scopes` | string | For a wildcard, the specific scopes the agent really calls, semicolon-separated. For a specific grant that is needed, the scope itself. Empty when not needed. |

Truth totals: 71 grants not needed (38.6%): launch leftovers, after-launch grants for a one-off task, and one wildcard no agent calls. 10 grants are quarterly. The rest are used every working day or now and then. Nothing in the pipeline reads this file to make a decision; it is used to score.

Three effects are built in on purpose. A shared account makes a sibling's calls look like the agent's own (it keeps unneeded grants alive). A quarterly scope looks unused in a 90-day window (the known limit). A few agents skip the human approval on a share of their high-impact calls.

---

## Headline scenario — A-13 and its two wildcards

| Source | What it gives you |
| --- | --- |
| `grants.csv` | A-13 holds `accounts:*` and `ledger:*` among 12 grants. |
| `scope_catalog.csv` | `accounts:*` reaches 5 specific scopes and `ledger:*` reaches 4. |
| `calls.csv` | A-13 calls one scope under each wildcard. |
| `needed_truth.csv` | The generator marks each wildcard as needed for that one scope only. |

Run the walkthrough and you see the same thing three ways: the annual review approves the 12 grants, the usage diff shows 6 of 19 reachable scopes called, and ScopeKeeper proposes a smaller set that the replay confirms still covers every call.

---

## Generator settings (design choices, not measurements)

These are constants at the top of `_generate.py`. They were set before the first run. The step scripts do not print them, so the numbers here are design settings, not results.

| Setting | Value | Why |
| --- | --- | --- |
| `TARGET_CALLS` | 8000 | Core call rates are scaled so the expected total is about this; the realized total is 7,994. |
| `SHARED_TAG_RATE` | 0.5 | On a shared account the agent tag is logged on half the calls. |
| `MISSING_TICKET_P_LAUNCH` | 0.03 | Share of launch grants drawn with no ticket reference. |
| `MISSING_TICKET_P_POST` | 0.08 | Same for after-launch grants. |
| `BASE_SKIP` | 0.01 | Background share of high-impact calls logged without approval. |
| per-agent skip | A-06 0.12, A-07 0.25, A-09 0.10, A-10 0.35 | Agents moved to an auto-send mode skip approval on a larger share of their high-impact calls. |
| `SATSUN_WEIGHT` | 0.3 | Saturday and Sunday traffic relative to a weekday. |
| quarterly timing | last use 90 to 100 days before the review date; next use 2 to 25 days after it | Keeps the last use before the window and the next use after the review date. |
