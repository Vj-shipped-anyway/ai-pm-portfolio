# Data for project 54

Synthetic. Produced by `_generate.py` with a fixed seed, so a rerun reproduces every file byte for byte. Nothing here comes from a real runbook, bank, vendor or employer, and the command names belong to no real product.

| File | What it holds |
|---|---|
| `cases.csv` | 94 drill cases: `case_id`, `requester`, `params_json` (overrides for the runbook's params), `world_json` (the state snapshot), `approvals_json` (the records on file), `runbook_yaml` |
| `truth.csv` | The planted truth per case: `case_kind`, `case_group` (clean, hard_negative, warning, waiting, lint, state, approval or hard_miss), `truth_verdict` (READY, WAITING or BLOCKED), `real_run` (completes, parks, stops, garbled or unsafe), `problem_index` (1-based step where a real run first goes wrong, 0 for none), `writes_before` (write steps already done by then), `expect_warning`, `detail`. The label comes from the defect that was planted, not from the tool |
| `example_runbook.yml`, `example_world.json`, `example_approvals.json` | The worked example behind `python3 runbook_dryrun.py --demo` (an approval given for scorer-v8 meets a run for scorer-v7) |

Planted kinds (94): clean 12, placeholder in a note 4, low-risk write with no gate 4, requester's own approval beside a valid one 3, approval exactly at its limit 3, snapshot with a number held as text 3, missing rollback 4, no approval on file 8, unfilled parameter 5, high-risk write with no gate 5, mistyped state key 4, repeated step id 3, failed precondition 6, a step that checks for the state an earlier step just changed 4, snapshot missing a key 3, approval by the requester 4, wrong role 4, approval for a different target 4, stale approval 4, a write declared as a read 4, snapshot gone stale 3. The kinds in the group `hard_negative` are cases a rule could flag by mistake. The group `hard_miss` is hard on purpose: a dry run cannot see those two kinds.

## Approval digest

An approval record is `{"step", "approver", "role", "digest", "age_minutes"}`. The digest is the first 12 hex characters of the SHA-256 of `runbook id`, a newline, `step id`, a newline and the command after `{{name}}` is filled in. The generator computes it with its own three lines; the tool prints the digest of every gate so an approver signs what will run.

## Runbook format

A YAML subset: block mappings and lists, plain, single-quoted and double-quoted scalars (`true`, `false`, whole numbers and decimals are typed; `yes`, `no`, `on`, `off`, `null` stay text), one-line `[a, b]` and `{k: v}`, `#` comments. Refused with a line number: anchors, aliases, tags, block scalars (`|`, `>`), values over several lines, several documents, tabs for indentation, control characters, nesting deeper than 8, files over 256 KB.

Top level: `runbook` (id), `title`, `reads` (state keys the runbook reads from the snapshot), `params` (name and default), `steps`. A step has `id`, `effect` (read, write, notify), `risk` (low, medium, high), `run`, and optionally `title`, `requires` (a list of `key == value`, also `!=`, `>=`, `<=`, `>`, `<`), `sets` (state changes it declares), `approval` (`role`, `ttl_minutes`), `rollback` (a command, or `none`) and `note` (never evaluated).

## Policy values (🟡 assumptions of a modeled team, not a rule)

A write at risk high needs an approval gate. A write at risk medium or high should name a rollback. An approval is valid for 30 minutes unless the gate says otherwise, and an age equal to the limit is still valid. The requester cannot approve their own change, compared without case or surrounding spaces.
