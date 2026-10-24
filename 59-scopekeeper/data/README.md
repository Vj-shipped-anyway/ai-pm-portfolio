# Data for project 59

Synthetic, seeded (`SEED = 5920261024` in `_generate.py`), and reproducible: a rerun writes every file byte for byte. The generator uses only the Python standard library and runs on Python 3.9. Nothing here comes from a real bank, agent, platform, vendor or incident. The calls are drawn by the generator from fixed rates; no model wrote them.

**The truth is known because the data is synthetic.** The generator decides which scopes each agent needs and writes the calls from that decision, so it can say which grants are unneeded and which are used once a quarter. The rules in `src/scopekeeper.py` never read the two truth files; only the step scripts do, to score the rules. The same author wrote the generator and the rules, so every score is a ceiling for these rules, not a rate on a real environment.

The design (agents, grant kinds, call rates, the settings below) was fixed before the first run. After the first run I added seven low-volume grants on shared service accounts, because the first version had too few needed grants whose calls are mostly untagged to exercise that case. No other change was made after seeing results.

| File | What it holds |
|---|---|
| `agents.csv` | 14 agents: `agent_id`, `owner`, `purpose`, `service_account`, `launched_on`. Seven agents share three service accounts (`SVC-04`, `SVC-07`, `SVC-09`); the other seven have their own |
| `scope_catalog.csv` | 33 rows: `scope`, `reaches`. Six are group scopes such as `accounts:*`; `reaches` lists the specific scopes a group stands for, separated by semicolons. A plain scope has an empty `reaches` |
| `grants.csv` | 167 grants: `agent_id`, `scope`, `granted_on`, `ticket_id`. The ticket is blank on 8 grants, drawn without looking at whether the grant is needed |
| `calls.csv` | 5210 calls over 90 days: `call_id`, `agent_id`, `day`, `scope_used`, `service_account`. Day 1 is 2026-07-26 and day 90 is 2026-10-23. On a shared service account the agent tag is logged on half the calls, so 1155 calls have a blank `agent_id` |
| `needed_truth.csv` | Truth, one row per grant: `needed` (yes or no), `basis`, and `needed_scopes` (for a group, the members the agent really calls) |
| `periodic_truth.csv` | Truth for the 10 grants used once a quarter: last use, cycle, next use, how many calls the next use makes, and why |
| `example_*.csv` | A small hand-built example (3 agents, 9 grants, 94 calls) behind `python3 scopekeeper.py --demo` |

## Planted grant kinds (167)

Daily use 49, occasional use 30, used once a quarter 10, added after launch and used 9, group grant partly used 7, launch leftover never called 41, added after launch and never called 18, group grant never called 1, stray use 2.

- **Occasional use** is drawn with at least one call, and 10 of the 30 have an expected volume of 1.2 to 1.5 calls. They are the hard negatives for a call-count threshold, and on a shared service account they are the hard negatives for a report that ignores untagged calls.
- **Used once a quarter** grants have their last use before day 1 and their next use 2 to 25 days after day 90. A 90-day log never shows them. This is the known limit.
- **Stray use** grants are not needed, but a smoke test called them once or twice in the window. The diff keeps them. This is a planted miss.
- **Launch leftovers** that share a scope with a sibling on the same service account are the second planted miss: the sibling's untagged calls are credited to them.

## Settings (🟡 assumptions of a modeled bank, not measured)

- Window of 90 days; call volume scaled to about 5200 calls; Saturday and Sunday carry 0.3 of a weekday.
- Agent tag logged on 0.5 of calls on a shared service account.
- Ticket missing on 0.03 of launch grants and 0.08 of after-launch grants.
- The annual review in step 2 approves a grant with a ticket and revokes one without. I did not observe any review; this is the simplest rule that uses only what the list shows.

Rerun with `cd data && python3 _generate.py`.
