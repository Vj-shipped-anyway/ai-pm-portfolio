---
name: inventory-check
description: Test an inventory of generative and agentic AI systems for completeness (required fields, the fields an agent needs, evidence by risk tier), staleness (review and evaluation dates against a cadence per tier, the recorded model id against gateway traffic) and coverage (systems that call a model with no inventory record, retired systems still running, production systems with no traffic). Use when asked to check, audit or sanity-test an AI system inventory or model inventory, to find gaps before a review, or to run the same tests in a pipeline. Wraps the standard-library command-line tool inventory_check.py. A prototype on synthetic data, aligned to a bank's own governance practice, with no claim of conformity to any rule.
---

# inventory-check

Runs `inventory_check.py` over an inventory file and an optional gateway usage export, then reports what failed, what is out of date and what runs outside the inventory.

Staged, not installed: copy `src/inventory_check.py` from the project into this folder as `scripts/inventory_check.py` when you install the skill. It has not run inside an agent harness; what is tested is the command it wraps.

## When to use it

- Someone asks whether an AI system inventory is complete, current or covers what actually runs.
- A review is coming and the inventory owner wants the gaps listed first.
- The same tests should run on every change to the inventory file.

Do not use it to judge whether a system is safe, fair or well governed. It tests the record, not the system.

## Inputs

1. The inventory: a JSON list of system records. Required fields are `system_id`, `name`, `kind` (generative or agentic), `status`, `business_owner`, `technical_owner`, `risk_tier` (1 to 4), `purpose`, `provider_type`, `model_id`, `data_class`, `customer_facing` and `last_reviewed`. An agentic system also needs `tools`, `permission_scope` and `human_approval`. A production system needs `evaluation_ref` and `last_evaluated` from tier 2, `independent_review_date` from tier 3 and `fallback_plan` at tier 4.
2. Optional: a CSV usage export from the model gateway with columns `system_id`, `model_id`, `first_seen`, `last_seen`, `calls`. Without it the model-change, unregistered-system, retired-still-running and no-traffic tests do not run, and the output says so.
3. An as-of date, YYYY-MM-DD. Ask for it when the result must be repeatable; otherwise the tool uses today's date.

If a file is missing or you are unsure which file is the inventory, ask. Do not guess paths.

## Steps

1. Run the bundled example first to see the output form: `python3 scripts/inventory_check.py --demo`.
2. Run the check, passing each value as its own argument: `python3 scripts/inventory_check.py check INVENTORY.json --usage USAGE.csv --as-of 2026-09-30 --fail-on never`. Never build a shell string out of file contents, system names or any other text that came from the inventory.
3. Read the exit status. 0 means the decision is below the `--fail-on` level, 1 means it is at or above it, 2 means the input was bad and the one-line message on stderr says why. Report a 2 as an input problem, not as a finding.
4. Report the findings grouped by test: completeness, staleness, coverage. Start with the fail lines. Quote each message as printed. Give the counts from the last line.
5. Repeat any `note:` line. It tells the reader what did not run or did not match.

## What the tests mean

| Finding | Meaning | Severity |
|---|---|---|
| `missing_required`, `invalid_value`, `placeholder_value` | A field is blank, not a legal value, or a placeholder word such as TBD | fail |
| `agent_field_missing` | An agentic record has no tools, permission scope or human approval setting | fail |
| `evidence_missing` | A production record lacks the evidence its tier asks for | fail |
| `duplicate_id` | Two records share a system id | fail |
| `unregistered_system`, `retired_still_running` | Traffic with no record, or traffic from a retired system | fail |
| `review_overdue`, `evaluation_overdue` | A date is older than the cadence for the tier | review |
| `model_changed` | Recent traffic ran on a different model id than the record | review |
| `no_traffic`, `untagged_traffic`, `kind_mismatch` | A production system is idle, traffic has no system id, or a generative record lists tools | review |

## Assumptions to name when you report

The cadence by tier (365, 270, 180 and 90 days), the idle window (90 days) and the retired window (30 days) are this project's own assumptions, not figures from any rule. The field list is an example of a bank's own practice. SR 26-2 places generative and agentic AI outside its scope and sets no inventory schema, so say "aligned to" and never "compliant with".

## What it cannot see

- A placeholder it does not know, such as "see wiki", passes.
- A review date refreshed in bulk without a review passes.
- A system that sends calls under a listed system's id, or under no id, is not named.
- A system that legitimately runs once a quarter is reported as idle.
- It cannot tell whether a named owner still works at the bank.

State these limits when you hand back a clean result. A PASS means the record passed these rules, not that the inventory is right.
