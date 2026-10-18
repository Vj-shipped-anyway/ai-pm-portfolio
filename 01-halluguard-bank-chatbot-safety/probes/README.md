# Probes

Sample probe records for the failure modes in the main README. Each file is JSON Lines, one probe per line.

| File | Failure mode | Probes |
| --- | --- | --- |
| `01_paraphrase_blindness.jsonl` | Paraphrase blindness | 5 |
| `02_negation_flip.jsonl` | Negation flip | 5 |
| `06_reg_citation_fabrication.jsonl` | Regulation-citation fabrication | 5 |

The file numbers follow the eight-mode taxonomy in the main README. The other five modes have no probe file yet.

## Record fields

Every record has `id`, `input` (the customer question), `retrieved_context` (the rows the chatbot sees), `expected_grounded`, `valid_responses`, `invalid_responses`, and `deficiency_tested`.

One record per file also carries `real_world_source`, a date-stamped label such as `incident_log_2026-01-09`. The repo holds no incident log behind that label, so read the probes as synthetic.

## Running them

`scripts/run-probes.sh` wraps a runner, `run_probes.py`, that is not in this repo yet. Until it is added, the script stops with a message instead of running.
