# Sample Data — AgentWatch walkthrough

Four CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`random.seed(20260512)`), and reproducible. No customer data. No PII. Shapes are calibrated against what a Tier-1 BFSI agent fleet actually looks like across claims triage, KYC refresh, dispute reconciliation, and loan-package assembly.

The headline incident the walkthrough resolves is `INC_0001` on run `RUN_00095` — a `claims_triage_v3` runaway loop on **April 14, 2026** that burned **$4,218.34** of inference cost across **1,847 redundant Anthropic API calls** before AgentWatch's runaway-detector fires. Without AgentWatch: the bank discovers it 3 weeks later in the FinOps review. With AgentWatch: bounded at 6 minutes, incident routed to a validator.

---

## `agents.csv` — 4 deployed agents

The agent-fleet definition. Without this row, deficiency #3 (silent agent drift) and deficiency #4 (blast-radius unbounded) are not classifiable by agent.

| Column | Type | What it is |
| --- | --- | --- |
| `agent_id` | string | Primary key. |
| `name` | string | Human-readable agent name. |
| `framework` | string | `langgraph`, `bedrock_agents`, `openai_assistants`, `autogen`. |
| `vendor` | string | The model vendor. |
| `model` | string | The exact vendor snapshot in effect at deploy. |
| `tier` | int | Bank's three-tier risk classification. |
| `owner_team` | string | The line-1 team. Routes incidents. |
| `deployed_at` | date | First production deploy date. |
| `n_tools` | int | Count of tools wired up to the agent. The blast-radius population. |
| `blast_radius_cap_usd` | int | Per-incident dollar cap AgentWatch enforces. |

4 rows.

## `agent_runs.csv` — 500 agent runs over 30 days

Every agent execution the bank produced in the 30-day window starting April 1, 2026, across the four deployed agents.

| Column | Type | What it is |
| --- | --- | --- |
| `run_id` | string | Format `RUN_NNNNN`. Stable join key across tool_calls and incidents. |
| `agent_id` | string | Foreign key to `agents.csv`. |
| `started_at` | ISO-8601 | When the agent run began. UTC. |
| `ended_at` | ISO-8601 | When it terminated (either naturally or via AgentWatch cut-off). |
| `status` | string | `COMPLETED`, `FAILED_RETRYABLE`, `TIMEOUT`, `BOUNDED_BY_AGENTWATCH`. |
| `total_tool_calls` | int | Number of tool invocations during the run. For runaways: in the thousands. |
| `total_cost_usd` | float | Inference + tool execution dollars. |
| `blast_radius` | int | Count of distinct tool-call attempts (a proxy for compounded reach). |
| `duration_s` | int | Wall-clock seconds. |
| `customer_id_hash` | string | Hashed customer identifier. Never raw PII. |

500 rows.

## `tool_calls.csv` — 2,633 tool-call events

One row per tool invocation the agent makes within a run. The substrate AgentWatch composes its taxonomy on. For runaway runs we sample the first 6 calls so the CSV stays browsable; the real production composer ingests every call.

| Column | Type | What it is |
| --- | --- | --- |
| `call_id` | string | Format `TC_NNNNNN`. |
| `run_id` | string | Foreign key to `agent_runs.csv`. |
| `agent_id` | string | Foreign key to `agents.csv`. |
| `step_index` | int | Zero-indexed position of this call within the run. |
| `tool_name` | string | The internal tool name. For runaway runs this is the same tool over and over. |
| `args_json` | JSON | The argument payload, normalized. Source signal for deficiency #2 (hallucinated tool arguments). |
| `called_at` | ISO-8601 | Tool-call moment. |
| `latency_ms` | int | Tool round-trip latency. |
| `status` | string | `OK`, `ERROR_NOT_FOUND`, `ERROR_TIMEOUT`. |
| `cost_usd` | float | Dollar cost of this single call. |

2,633 rows.

## `incidents.csv` — 24 detected incidents, by deficiency class

The product's classification table. Every incident is mapped to one of the six named deficiencies. Without this, the AgentWatch console is just a generic alert feed.

| Column | Type | What it is |
| --- | --- | --- |
| `incident_id` | string | Format `INC_NNNN`. |
| `run_id` | string | Foreign key. |
| `agent_id` | string | Foreign key. |
| `detected_at` | ISO-8601 | When AgentWatch raised the alert. |
| `deficiency_class` | string | One of: `runaway_loop`, `hallucinated_args`, `silent_drift`, `blast_unbounded`, `no_reasoning_trace`, `cost_detached`. The product taxonomy. |
| `scenario_note` | string | One-line plain-English description. |
| `severity` | string | `P1` / `P2` / `P3`. |
| `agentwatch_action` | string | What AgentWatch's sidecar did. `auto_cutoff_at_blast_radius_cap`, `schema_validator_blocked`, `drift_alert_routed_to_owner`, `circuit_breaker_tripped`, `trace_replay_synthesized`, `cost_attributed_to_outcome`. |
| `cost_at_cutoff_usd` | float | Dollar cost at the moment of the cut-off (the "bleed" capped by AgentWatch). |
| `tool_calls_at_cutoff` | int | Tool-call count at the cut-off. |
| `mttr_minutes_with_agentwatch` | int | Mean-time-to-recover MEASURED on the prototype (alert → mitigation routed). |
| `modeled_mttr_without_agentwatch_hours` | int | Modeled MTTR if AgentWatch were not present. Sourced from published BFSI agent-incident review intervals. |

24 rows distributed across the six deficiencies: 6 runaway loops, 4 hallucinated-args, 4 silent-drift, 3 blast-unbounded, 4 no-reasoning-trace, 3 cost-detached.

---

## Headline incident walk — `INC_0001` / `RUN_00095`

This is the incident the walkthrough resolves. Walk the four CSVs and you get the full reliability picture in one record:

| Source | What it gives you |
| --- | --- |
| `agents.csv` | The agent is `claims_triage_v3` on Anthropic Claude Sonnet 4 on the LangGraph framework. Wired up with 9 tools. Per-incident dollar cap = $250. |
| `agent_runs.csv` | Run `RUN_00095` started `2026-04-14T03:12:08Z`, ran for 4,860s (1h21m), made `1,847` tool calls, burned `$4,218.34` of inference cost, and was `BOUNDED_BY_AGENTWATCH`. |
| `tool_calls.csv` | The agent kept calling `claim_lookup` with slightly different `claim_id` arguments. The first lookup returned a malformed response; the agent's planner retried with `retry=1`, `retry=2`, … forever. |
| `incidents.csv` | AgentWatch classified this as `runaway_loop`, severity `P1`, action `auto_cutoff_at_blast_radius_cap`. MTTR with AgentWatch: 6 minutes. Modeled MTTR without AgentWatch: 240 hours (the FinOps review cycle). |

In raw-log form: scattered across 3 vendors × 2 cloud accounts × the LLM trace tail. In AgentWatch: one record, indexed by `(agent_id, run_id, deficiency_class)`, the bleeding bounded in 6 minutes, the incident routed for human review.
