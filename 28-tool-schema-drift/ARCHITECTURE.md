# Architecture: Tool Schema Drift gate

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/tool_schema_drift.py`, that reads two revisions of a tool schema and an optional file of recorded calls, classifies each change, validates the recorded calls against the new schema and prints ALLOW, REVIEW or BLOCK, run here over 67 synthetic pull requests. A GitHub Action is staged in `action/` and has not been published or run on GitHub. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![Tool Schema Drift flow](./assets/tool-schema-drift-flow.svg)

---

## 1. Logical architecture

Tool Schema Drift is a function between a pull request and a merge: two schemas and a calls file in, a decision out. It does not call a tool or run an agent. Replay validates the arguments of a recorded call against a schema and never sends the call anywhere.

Eight components: five decide the outcome, three support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `tsd-ingest` | Loads both schemas and the calls file. Rejects a missing file, a non-object, a missing `parameters.properties` or a malformed call. | Python 3.9+, stdlib. Prototype: `check_shape`, `load_calls` in `src/tool_schema_drift.py` | Yes, by refusing: exit 2 | No |
| `tsd-diff` | The structural classifier: renames, removed and required fields, types, enums, bounds, defaults. Each finding is breaking, behavior_risk or non_breaking. | Python. Prototype: `diff_schemas`, `_detect_renames` | Yes | No |
| `tsd-units` | Reads the (number, unit) pairs in a changed description. A different pair is a behavior_risk finding. | Python. Prototype: `description_signature`, `fmt_signature` | Yes | No |
| `tsd-replay` | Validates each recorded call against the new schema. | Python. Prototype: `strict_validate`, `replay` | Yes | No |
| `tsd-verdict` | Takes the highest class, forces BLOCK on a failed replay, maps the decision to an exit code. | Python. Prototype: `decide`, `DECISION_RANK`, `run_check` | Yes | No |
| `tsd-report` | Prints text or GitHub annotations, escaped. The staged Action wraps this command. | Python. Prototype: `render`, `escape_annotation`, `safe`; `action/action.yml` (staged) | No | No |
| `tsd-calllog` | Captures production calls, name and arguments, as the replay input (design). Prototype analog: `data/recorded_calls.csv`. | Log pipeline to object storage (design) | No, but it bounds what replay sees | Stateful |
| `tsd-ledger` | Appends one record per decision (design). Prototype analog: `src/out/step_04_decisions.csv`. | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |

**What decides the outcome.** The input check, the classifier, the unit check, the replay and the verdict. The report, the Action wrapper, the call capture and the ledger carry or record the decision. The classifier reads the keywords type, enum, required, minimum, maximum, maxLength, default and items; anything else in a schema is ignored, not judged.

**Repo structure** (production shape):

```
tool-schema-drift/
├── gate/       # ingest, diff, units, replay, verdict, report
├── action/     # composite Action wrapper
├── units/      # the unit table, changed by pull request
├── calllog/    # capture and sampling of production calls
├── ledger/     # decision record writer
├── infra/      # terraform for gcp, aws, azure
└── tests/      # unit, golden (planted-set numbers), hostile strings
```

---

## 2. Physical and deployment architecture

The check is one short-lived process in the pipeline that already builds the tool catalogue. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Check process (ingest, diff, units, replay, verdict, report) | Cloud Build step or Cloud Run job | CodeBuild step or ECS Fargate task | Azure Pipelines step or Container Apps job | Stateless, one pass, runs where the pull-request check runs |
| Old schema | Read from the base branch of the repo | Same | Same | The reference must not come from the pull request being judged |
| `tsd-calllog` | Cloud Storage, partitioned by tool and day | S3, partitioned | Blob Storage, partitioned | The agent platform writes, the check reads a sample |
| `tsd-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The check must never silently pass. A schema that cannot be read, or lacks the shape the diff needs, does not become ALLOW: it ends the run with exit 2 and a one-line reason, and that exit fails the CI step even with `--fail-on never`. A calls file with no rows for the tool is said out loud, not skipped.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Schema missing, not JSON, not an object, no `parameters.properties`, `required` not a list, or a property that is not an object | Exit 2, one `input error` line on stderr, CI step fails | P2 if repeated on one catalogue, else P3 |
| Calls file missing, malformed, or a row without `args_json` | Exit 2 with the reason | P3 |
| Calls file has no rows for this tool | Prints that nothing was replayed. Structure and units still decide | P3: the log does not cover the tool |
| A recorded call fails on the new schema | BLOCK, even if the diff alone said ALLOW or REVIEW | P3 |
| Ledger or call capture unavailable (design) | The decision and exit code stand; the record queues locally | P3 |

**Latency.** The prototype is one pass over two small schemas and a calls file; I have not timed it. 🔴 Design target: a decision within 120 seconds of a pull request update.

Recovery is a re-run from the same schemas and calls snapshot.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Tool schema | `name`, `version` | One tool: description, `parameters.properties`, `required` | `data/tools_base.json`: 🟢 10 tool schemas |
| Pull request | `pr_id` | The old and the new schema of one tool | `data/pr_cases.csv`: `pr_id`, `tool`, `old_schema_json`, `new_schema_json` |
| Recorded call | `call_id` | The tool name and the arguments sent | `data/recorded_calls.csv`: `call_id`, `tool`, `args_json` |
| Decision record, with its findings (`kind`, `param`, `class`, `reason` from `diff_schemas`) | `decision_id` | Design: pull request, tool, findings, calls replayed and failed, decision, SHA-256 of both schemas and the calls file, tool version, time | Prototype: `src/out/step_04_decisions.csv`: `pr_id`, `tool`, `change_kind`, `truth`, `decision`, `findings`, `broken_calls` |
| Planted truth | `pr_id` | The change planted and the class it deserves | `data/pr_truth.csv`: `pr_id`, `change_kind`, `truth_class`, `changed_param`. Exists only because the data is synthetic |

**Retention** is a design choice, not a measurement; confirm each value against the bank's own record-retention schedule.

| Data | Retention (🔴 design default) | Storage |
| --- | --- | --- |
| Decision records and findings | 7 years | PostgreSQL, archived to object storage with a retention lock |
| Recorded calls | 90 days | Restricted object storage; arguments can hold account identifiers and amounts |

**Lineage.** A decision traces back in three hops: the record names the pull request, both schema hashes and the calls-file hash; versioned storage returns the schemas, and the calls snapshot while it is retained; and the rules are deterministic, so re-running `diff_schemas` and `replay` reproduces the findings. After 90 days the record keeps the hash, the counts and the failing `call_id` values, not the arguments, so replay cannot be re-run. In the prototype the trace is a row of `step_04_decisions.csv`.

**Deliberately not stored.** Tool responses, agent prompts, conversation text and customer records. The check needs the schema and the argument values of a call.

---

## 4. Security architecture

**Identity and roles.** The check runs under the CI platform's workload identity and has no user account of its own.

| Role | Can | Maps to |
| --- | --- | --- |
| `tsd:runner` | Read both schemas and a call sample; write a decision record | The CI service identity for the repo |
| `tsd:approver` | Approve a change to the unit table or the level that fails the step, never on their own pull request | Second-line or agent-risk reviewer |
| `tsd:auditor` | Read decisions, findings and config history | Internal audit |
| `tsd:admin` | Manage roles, buckets and the ledger | Platform engineering lead |

**Secrets.** The check holds none and never calls a tool or a model. The CI identity reaches the call store and the ledger through workload identity. The staged Action passes inputs through environment variables and runs with `--format github`.

**Data classification and what leaves the boundary.** Schemas are internal. Recorded calls can carry account identifiers and amounts, so treat them as confidential; the prototype's calls are synthetic. In the prototype nothing leaves the machine. In the design three things leave the job: the exit code, the annotations and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a schema field echoed into a log or annotation | A parameter name holding a newline and text that looks like a workflow command | `escape_annotation` rewrites `%`, carriage return and newline in `--format github`; `safe` writes control characters and line separators as visible escapes (`\n`, `\r`, `\x1b`, `\u2028`) in the text format and in the one-line input error. `tests/test_cli.py` covers a hostile parameter name, tool name and description in both formats, and the error line |
| The reference schema or the calls file is edited in the same pull request | The old file is changed, or rows for the changed parameter are removed | Read the old schema from the base branch; calls come from `tsd-calllog` with a hash; an empty-rows line is an alert |
| A description carries instructions for the agent | A reworded description telling the agent to ignore a rule | Not read. The check flags a moved number or unit only; a scan is queued in the backlog |

---

## 5. Operational architecture

**SLIs.** Decisions per class per catalogue per week (prototype baseline on harmless synthetic pull requests: 🟢 0 of 27 blocked and 0 of 27 sent to review, `step_04_with_gate.py`); input rejections; pull requests where the calls file had no rows for the tool; calls replayed per pull request; REVIEW decisions cleared without a change; time to decision.

**SLOs (all 🔴 design targets, none measured).**
- Decision within 120 seconds of a pull request update.
- Every schema pull request on an in-scope catalogue leaves a record.
- Every BLOCK read by a named person within one business day (planning estimate).
- 99.9 percent of decisions written to the ledger.

**Alerts.** P2: repeated input rejections on one catalogue, or the ledger down for more than a day (low-urgency page to the pipeline owner). P3: a BLOCK that came from replay alone, which also goes to the agent owner, or a calls file with no rows for the tool (chat).

**Runbooks** (one page each, in `docs/runbooks/`):
- `breaking-change-blocked.md`: read the finding, choose a versioned new tool or a fix, re-run.
- `behavior-risk-review.md`: compare the old and new default or description, ask the agent owner.
- `calls-file-empty.md`: find why the log has no rows for the tool and restore capture.
- `changing-the-unit-table.md`: propose a unit, re-run the planted set, approve.

**On-call and ownership.** The pipeline owner owns the runner, the Action wrapper and the runbooks. The catalogue owner owns the schemas and the unit table. The agent owner owns call capture. The reviewer approves policy changes. Nobody is paged for a REVIEW.

**Change control.** The rules, the unit table and the rename-similarity setting are versioned in the repo. A change needs a proposer and a different approver, and the planted set is re-run against `tests/test_golden.py` before merge, so a change that moves the blocked count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites two sources: the [MCP specification's security guidance](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices) and the OWASP MCP Top 10 (linked in the README at https://owasp.org/www-project-mcp-top-10/). It says they treat tool definitions as inputs that need review when they change, and says nothing more about how much of either I read, so I add nothing here.

- **What the design does.** It makes the review of a changed tool definition a step in the pull request: a classified diff, a check of numbers and units, and a replay of recorded calls, with the decision recorded.
- **What it does not claim.** It does not read a description for malicious instructions and maps to no control identifier in either source. It is not compliant with the guidance or any other standard, holds no certification, and I have not read or mapped any other source.

---

## 7. What is deliberately not here

- **Six behavior-risk changes that pass.** 🟢 6 of 15 pass (`step_04_with_gate.py`): three meaning flips with no number or unit, and three scale changes where the unit word stays the same.
- **A model reading descriptions.** The check looks for moved numbers and units, never for instructions to the agent.
- **Schema keywords beyond eight.** Pattern, format, oneOf, anyOf and nested objects are not supported. The unit list is short and English only, and number words such as "seven" are not parsed.
- **A version policy.** A version bump alone is ALLOW.
- **Replay beyond the log.** 🟢 With 3 recorded calls per tool, replay blocks 23 of 25 breaking pull requests (`step_03_deficiencies_exposed.py`).
- **Rules tuned on real catalogues.** The rename-similarity setting and the unit table are mine, and the planted set and the rules share an author, so the numbers are a ceiling.
- **Running a tool, hosting, or a published Action.** A Marketplace listing is a later, separate step.

---

## Appendix: sample contract

The call is the prototype's own. Its output for the bundled `--demo` run is under "Run one now" in the README.

```bash
python3 tool_schema_drift.py check old.json new.json --calls calls.csv --fail-on block --format github
```

A schema is `{"name", "version", "description", "parameters": {"properties": {...}, "required": [...]}}`. A calls file has the columns `call_id`, `tool`, `args_json`. A finding carries `kind`, `param`, `class`, `reason`, `old` and `new`. Exit status: 0 below `--fail-on`, 1 at or above it, 2 for bad input.
