# Data for project 62

Synthetic. Produced by `_generate.py` with a fixed seed, so a rerun reproduces every file byte for byte. Nothing here comes from a real agent, customer, bank or employer. The trace shape follows [project 05](../../05-agentwatch-agent-observability/); no row is copied from it.

| File | What it holds |
|---|---|
| `runs.csv` | 60 runs that an alert flagged: `run_id`, `agent_id`, `agent_role`, `customer_id`, `started_at`, `cost_cap_usd`, `n_calls`, `total_cost_usd`, `ticket_note` (what the on-call engineer wrote) |
| `tool_calls.csv` | 3591 calls: `call_id`, `run_id`, `step_index`, `tool_name`, `args_json`, `response_kind` (ok, malformed, empty, not_found), `response_flag` (instruction_like when an upstream scanner marked the response), `cost_usd` |
| `truth.csv` | The planted truth per run: `scenario`, `worthy` (a failure worth a case study), `truth_techniques` (the ATLAS ids a careful reader would assign) and `planted_strings` (identifiers and names written into the ticket that must not reach a draft). It comes from the scenario that was planted, not from the tool |
| `identifier_keys.json` | The fields whose values are identifiers, in the run and in call arguments |
| `example_bundle.json` | One run in the bundle shape the tool reads; the worked example behind `python3 atlas_case_study.py --demo` (the shortest poisoned run that reached its cost cap) |

Planted scenarios (60): benign 14, benign batch 8, retry storm 12, poisoned loop 10, not-found walk 6, short storm 5, alternating loop 5. Failures: retry storm, poisoned loop, short storm, alternating loop. Four kinds are hard on purpose: the batch (30 to 120 ok lookups with distinct ids) and the not-found walk (6 to 18 calls with a storm's argument shape) could raise false alarms; the short storm (12 to 18 calls) and the alternating loop (two tools in turn) are failures the loop rule should miss.

Truth techniques are my judgment of what the trace shows. I map a loop to Denial of AI Service (AML.T0029); an instruction-like response next to the loop adds Indirect (AML.T0051.001), under LLM Prompt Injection; a run whose cost reached its cap adds Cost Harvesting (AML.T0034). ATLAS describes these as adversary actions; the trace shows the effect only. Truth is set from the planted scenario and the planted cost, not from the tool.

🟡 Assumptions: the upstream scanner that sets `response_flag` exists and is right; the 20-call and 0.9 thresholds are mine; the rates of identifiers (about 7 in 10 tickets) and names (about 4 in 10) in tickets are a guess, so the leak counts in steps 2 and 4 show a mechanism, not a rate.

## ATLAS sources read, 2026-10-24

- `https://github.com/mitre-atlas/atlas-data` (README, format version 6.0.0, case-studies key)
- `dist/schemas/atlas_contribution_schema.json` and `dist/schemas/atlas_website_case_study_schema.json` (contribution schema 1.0.0, website schema 1.1): required study fields name, summary, incident-date, incident-date-granularity (YEAR, MONTH, DATE) and procedure; reporter required for an incident, in the contribution schema only; case-study-type incident or exercise; procedure steps with tactic, technique and description; id patterns
- `dist/v6/ATLAS-2026.09.yaml` (collection 2026.09, modified 2026-09-15): AML.T0029 and AML.T0034 achieve AML.TA0011 (Impact); AML.T0051.001 achieves AML.TA0005 (Execution)
