# Sample Data — SchemaWatch walkthrough

Four CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`SEED = 20261017` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files. The generator uses only the Python standard library and runs on Python 3.9. **No customer data. No real bank, tool, API, vendor or incident. The recorded agent calls are written by the generator, not by an agent or a model.**

**The truth is known because the data is synthetic.** The generator decides what changed in each tool schema, so it can say exactly which recorded calls break and which still pass but mean something different. A real estate does not hand you that; the first job in a real deployment is capturing a real tool-call log.

The headline scenario the walkthrough resolves: **an agent platform calls 28 tools owned by other teams. Inside one quarter, 26 tools ship 45 schema changes and 17 of them ship with no version bump. Without monitoring, 742 of 2,500 recorded calls fail in the week after release and 538 more pass and mean something different. With SchemaWatch, every release is diffed, replayed and gated before the agent meets it.**

---

## `tool_schemas.csv` — 59 schema revisions

One row per tool revision: v1 for every tool, v2 for the 26 tools that changed, v3 for the 5 that changed twice.

| Column | Type | What it is |
| --- | --- | --- |
| `tool` | string | Tool name, for example `get_transaction_history`. |
| `rev` | string | `v1`, `v2` or `v3`. v1 is the revision the agent was built against. |
| `declared_version` | string | The version string the owner published. It does not change on every release: that is the point. |
| `released_at` | string | ISO timestamp. v1 on 2026-02-16, v2 between 2026-04-08 and 2026-05-22, v3 between 2026-06-02 and 2026-06-16. |
| `schema_json` | JSON | A JSON-schema-like dict: `name`, `version`, `description`, `parameters` with `properties` (type, description, enum, default, minimum, maximum, maxLength, items), `required` and `additionalProperties: false`. |

Descriptions carry units ("in US dollars", "in seconds", "in miles") because unit drift is one of the change types.

## `change_ledger.csv` — 45 injected changes (the ground truth)

Every revision after v1 is produced by applying these rows to the previous revision. Nothing in the pipeline reads this file to make a decision; it is used to score.

| Column | Type | What it is |
| --- | --- | --- |
| `change_id` | string | `CH-001` onward, in release order. |
| `tool`, `from_rev`, `to_rev`, `released_at` | strings | Which release the change belongs to. |
| `change_type` | string | One of `param_renamed`, `type_changed`, `required_added`, `enum_value_removed`, `enum_value_added`, `default_changed`, `unit_changed` (a unit changed in a description), `description_reworded` (cosmetic), `param_removed`, `optional_added`, `meaning_changed` (a meaning changed with no number or unit). |
| `param` | string | The parameter affected. Empty for a tool-level description. For a rename, the old name. |
| `old_value`, `new_value` | strings | The before and after: names, types, an enum value, a JSON default, or the description text. |
| `kind` | string | For `type_changed` only: `tighten` or `widen`. |
| `declared_version_before`, `declared_version_after`, `version_bumped` | strings | Whether the owner changed the version string with this release. 28 changes shipped with a bump, 17 without. |
| `true_class` | string | `breaking`, `non_breaking` or `behavior_risk`. |
| `semantic_kind` | string | `unit_signal` (a unit changed), `no_signal` (a meaning changed with no number or unit) or `none`. |

Mix: 4 renames, 5 type changes (3 tightening, 2 widening), 4 required fields added, 4 enum values removed, 4 enum values added, 4 defaults changed, 5 unit changes, 6 cosmetic rewordings, 2 parameters removed, 4 optional fields added, 3 meaning changes with no number or unit. 17 breaking, 16 non-breaking, 12 behavior-risk.

Two cases are hard on purpose. A cosmetic rewording writes "7 days" as "seven days", which the description heuristic reads as a changed number. And 3 changes alter what a parameter means without touching a number or a unit, which the heuristic cannot see.

The ledger is dense: 26 of 28 tools change inside one quarter. It is a test set that exercises every change type, not an estimate of how often real tools change.

## `recorded_calls.csv` — 2,500 recorded agent calls

| Column | Type | What it is |
| --- | --- | --- |
| `call_id` | string | `C0001` onward, in time order. |
| `tool` | string | The tool called. Volume is skewed: a few tools take most of the traffic. |
| `called_at` | string | ISO timestamp inside one week, 2026-03-02 to 2026-03-08, weighted to weekday business hours. |
| `args_json` | JSON | The argument dict. Required parameters are always present; optional parameters appear with a per-parameter probability. |

Every call is valid under v1. The generator asserts this before writing; step 4 re-checks it with the validator (2,500 of 2,500 pass).

## `call_truth.csv` — what each ledger change does to each call

Computed from the ledger rules (what a change does to a v1-shaped call), not by running a validator. The SchemaWatch replay in `src/step_04` is a separate implementation that validates the schema text; comparing the two is one of the measurements.

| Column | Type | What it is |
| --- | --- | --- |
| `call_id` | string | Join key to `recorded_calls.csv`. |
| `true_broken` | 0/1 | The call fails strict validation of the latest revision of its tool (unknown keys rejected). |
| `first_break_rev` | string | The first revision at which it fails: `v2`, `v3` or empty. |
| `true_misread_unit` | 0/1 | The call still validates, but a unit in a description it relies on changed. |
| `true_misread_meaning` | 0/1 | The call still validates, but a parameter it sends changed meaning with no number or unit. |
| `true_shifted_default` | 0/1 | The call still validates, but it omits a parameter whose default changed. |
| `cause_change_ids` | string | The ledger changes responsible, semicolon-separated. |

Rules: a rename or removal breaks calls that send the old name; a required field added breaks every call; a removed enum value breaks calls that send it; tightening a string to an integer breaks every call that sends it; tightening a number to an integer breaks calls whose value has a fractional part; widening, an added enum value, an added optional field and cosmetic edits break nothing. A call that is broken is counted as broken only; the other flags apply only to calls that still validate.

Truth totals: 742 broken, 228 unit-misread, 169 meaning-misread, 156 default-shifted.

---

## Headline scenario — the transaction-history rename

| Source | What it gives you |
| --- | --- |
| `tool_schemas.csv` | `get_transaction_history` v1 and v2. The declared version is 1.3.0 in both. |
| `change_ledger.csv` | CH-003: `limit` renamed to `page_size`, no bump. CH-004: default of `txn_type` changed from "all" to "debit". |
| `recorded_calls.csv` | 295 recorded calls to that tool. |
| `call_truth.csv` | 143 calls that send `limit` break; calls that omit `txn_type` pass and silently get a different default. |

Replay the walkthrough and you see the same thing three ways: nothing watching (calls fail, with no alert for the silent ones), a version check (silent, because the version never changed), and SchemaWatch (BLOCK, with the 143 calls and the reason).
