# Architecture: MCP Scope Lint

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/mcp_scope_lint.py`, that reads a tool manifest, expands wildcards, applies five rules, scores breadth and prints a proposal that never adds a scope, run here over 30 synthetic manifests with 218 tools. Nothing is staged for CI. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![MCP Scope Lint flow](./assets/mcp-scope-lint-flow.svg)

---

## 1. Logical architecture

MCP Scope Lint is a function between a server's repository and its release: one manifest in, findings, a score, a proposal and an exit code out. It does not call a server, read a token, read a tool description or call a model.

Eight components: five decide the outcome or shape the proposal, three support.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `sl-ingest` | Parses tools, scope catalog and grant. Rejects anything malformed. | Python 3.9+, standard library. Prototype: `parse_manifest`, `load_manifest` in `src/mcp_scope_lint.py` | Yes, by refusing: exit 2 | No |
| `sl-rules` | Expands wildcards, applies the five rules and computes breadth. | Python. Prototype: `members`, `reach`, `hint_ceiling`, `lint` | Yes | No |
| `sl-propose` | Cuts tools back to their hints, then keeps, narrows or removes each grant. Never adds a scope. | Python. Prototype: `propose` | Yes, for the proposal, which is advice | No |
| `sl-verdict` | Maps the highest severity to an exit code at `--fail-on`. | Python. Prototype: `SEVERITY_RANK`, the exit logic in `run_lint` | Yes | No |
| `sl-report` | Prints text or GitHub annotations and escapes untrusted strings. | Python. Prototype: `render_text`, `render_github`, `clean`, `escape_annotation` | No | No |
| `sl-export` | Builds the manifest from the server's own configuration and tool list (design). | The server's build (design) | No, it supplies the input | No |
| `sl-policy` | The `--fail-on` level per server and accepted findings, each with an approver and an expiry (design). | A reviewed file in the server repo (design). Prototype: the `--fail-on` flag | Yes, config | Stateful, in git |
| `sl-ledger` | One record per lint run, and counts for monitoring (design). Prototype analog: `src/out/step_04_findings.csv`. | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |

**What decides the outcome.** The parser, the scope arithmetic, the five rules and the verdict. The proposal is advice: it is printed and never applied. The report, the export and the ledger carry or record the result. 

**Repo structure** (production shape):

```
mcp-scope-lint/
├── lint/       # ingest.py, rules.py, propose.py, verdict.py, report.py
├── export/     # manifest export hooks for a server build
├── policy/     # fail-on level and accepted findings, by pull request
├── ledger/     # lint record writer
├── infra/      # terraform for gcp, aws, azure
└── tests/      # unit, golden (planted-set numbers), hostile strings
```

---

## 2. Physical and deployment architecture

The lint is one short-lived process in the pipeline that already builds the server. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Lint process (`sl-ingest` to `sl-report`) | Cloud Build step or Cloud Run job | CodeBuild step or ECS Fargate task | Azure Pipelines step or Container Apps job | Stateless, one pass, runs where the server is built |
| `sl-export`, `sl-policy` | A step and a file in the server repo | Same | Same | They change in the same history as the grant |
| Manifest store | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Versioning keeps the exact bytes a result used |
| `sl-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The lint must never silently pass. A missing, empty, truncated or malformed manifest does not become a clean result: it ends the run with exit 2 and a one-line reason, and that exit fails the CI step even with `--fail-on never`. A tool with no usable hint is listed as not checked, never shown as fine.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Manifest missing, empty, truncated, not an object, not UTF-8 or nested too deeply | Exit 2, one line on stderr, CI step fails | P2 if repeated on one server, else P3 |
| A tool names a scope not in the catalog; a name appears twice; a hint is not true or false | Exit 2 with the reason | P3 |
| No scopes are granted | Not an error: the report says there is nothing to lint on the grant side | P4 |
| A tool carries no usable hint | Listed under "not checked", not judged | P4 in a weekly digest |
| The export is older than the tool list, or the ledger is down (design) | A stale manifest fails the step. The result and exit code stand if only the ledger is down; the record queues | P3 |

**Latency.** The prototype is one pass over one small file; I have not timed it. 🔴 Design target: a lint result within 30 seconds of the pipeline step starting.

Recovery is a re-run from the same versioned manifest and policy.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Manifest | `server.name`, plus a content hash (design) | One server's catalog, grant and tools | `data/manifests.json`: `server`, `scope_catalog`, `granted_scopes`, `tools` (each with `name`, `requires_scopes`, optional `annotations`; `description` and `inputSchema` are validated, not read) |
| Scope | `id` | A resource and an access level | `scope_catalog` entries: `id`, `resource`, `access` (`read`, `write`, `delete`, `admin` or `any`) |
| Finding and proposal | `kind`, `tool`, `scope` | Severity, message, and keep, narrow or remove per grant | `src/out/step_04_findings.csv`, `step_04_changes.csv` |
| Lint record | `record_id` | Design: server, manifest hash, rules version, policy used, findings, breadth, proposal, exit code, time | Prototype: `src/out/step_04_summary.json` |
| Planted truth | `server`, `scope` | Whether a scope is needed, and the profile that planted it. Exists only because the data is synthetic | `data/entitlement_truth.csv`: `server`, `scope`, `needed`, `planted`; `data/tool_scope_truth.csv` adds `tool` |

**Retention** is a design choice, not a measurement; confirm it against the bank's own record-retention schedule.

🔴 Design default: lint records and findings are kept 7 years in PostgreSQL, archived to object storage with a retention lock; the manifests a result used are kept as long as the record, in versioned object storage, so a result can be reproduced.

**Lineage.** A result traces back in three hops: the record names the server, rules version, policy and manifest hash; the versioned store returns those bytes; and the rules are deterministic (findings are sorted, no clock or random draw), so a re-run reproduces them.

**Deliberately not stored.** Tool descriptions, input schemas, tokens and call payloads. The lint needs scope ids, tool names, the resource and access of each scope, and two hints.

---

## 4. Security architecture

**Identity and roles.** The lint runs under the CI platform's workload identity and has no user account of its own.

| Role | Can |
| --- | --- |
| `sl:runner` (the CI identity) | Read the manifest and policy; write a lint record |
| `sl:approver` (security or platform reviewer) | Approve a policy change or accepted finding, never for their own server |
| `sl:auditor` (internal audit) | Read records, findings and config history |
| `sl:admin` (platform lead) | Manage roles, buckets and the ledger |

**Secrets.** The lint holds none and never calls a model or a server, so no token is in its path. The CI identity reaches the store and ledger through workload identity. `sl-export` must not read credentials (design).

**Data classification and what leaves the boundary.** Scope names, tool names and hints are internal; a real manifest shows how a bank's permissions are laid out, so treat it as confidential. In the prototype nothing leaves the machine. In the design three things leave the job: the exit code, the annotations and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a tool or server name echoed into a log or annotation | A tool name holding a newline and text that looks like a workflow command | `escape_annotation` rewrites `%`, carriage return and newline; `clean` shows control characters as escapes. `tests/test_cli.py` covers both |
| A hint is edited to make an error go away | A tool changed to read-only, or a hint removed so the tool becomes unjudged | Hints live in the server repo under review; the record stores the manifest hash; a tool that moves from judged to not checked shows in the digest |
| The proposal is applied unread | A needed scope removed because a read-only hint was wrong | The proposal lists every tool change and is applied by pull request with the tool's own tests |

---

## 5. Operational architecture

**SLIs.** Errors and warnings per run by rule; breadth per server over time (prototype baseline: 🟢 38 of 260 reachable scopes that no tool requires, `step_04_with_lint.py`); share of tools with a usable hint (prototype: 🟢 150 of 218, `step_01_no_lint.py`); input rejections; accepted findings past expiry; time to a result.

**SLOs (all 🔴 design targets, none measured).**
- A lint result within 30 seconds of the pipeline step starting.
- Every in-scope release passes through the lint and leaves a record; 99.9 percent of records written.
- Every error read by a named person within one business day (planning estimate).

**Alerts.** P2: repeated input rejections on one server, or the ledger down for a day. P3: an `unused_grant` or `tool_scope_above_hint` error on a production server, or a stale export. P4: a weekly digest of warnings, unjudged tools and accepted findings near expiry. Nobody is paged for a warning.

**Runbooks** (one page each, in `docs/runbooks/`):
- `unused-grant.md`: confirm no tool needs the scope, remove it, re-run.
- `tool-above-hint.md`: decide whether the hint or the scope is wrong, fix it, test.
- `applying-a-proposal.md`: one tool change read at a time, the tool's tests, a re-run.
- `changing-a-rule-or-policy.md`: propose, re-run the planted set, compare with the golden numbers, approve.

**Ownership.** The server owner owns the manifest, hints and grant. The platform team owns the runner and runbooks. The security reviewer approves policy changes and accepted findings.

**Change control.** Rules and policy are versioned; a change needs a proposer and a different approver. Before merge, the planted set is re-run against the numbers pinned in `tests/test_golden.py`, so a change that moves the cut count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README cites two sources, restated with the same wording about what was read: the [MCP specification's security best practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices) (draft version, read 2026-10-24), section "Scope Minimization", which describes the harm of broad tokens, lists publishing every scope and using wildcard or omnibus scopes as common mistakes, and recommends a progressive, least-privilege model; and the [OWASP MCP Top 10](https://owasp.org/www-project-mcp-top-10/) (read 2026-10-24; the page shows a 2025 designation and a beta phase), item MCP02, privilege escalation via scope creep.

- **What the design does.** It checks the static part of that guidance: a grant no tool needs, a wildcard used in part, a tool that asks for more than it says it does, and a smaller grant that never adds a scope.
- **What it does not claim.** It does not model the run-time step-up flow. It is not compliant with either source or any other standard, holds no certification, and I have not read or mapped any other source.

---

## 7. What is deliberately not here

- **Unneeded scopes that stay reachable.** 🟢 22 of 83 stay (`step_04_with_lint.py`): a write scope on a tool with no hint, a scope inside a hint that allows write, a tool nobody calls, and a wildcard on a tool with no hint.
- **A way to know a hint is true.** 🟢 3 needed scopes are cut where a read-only hint is wrong (`step_04_with_lint.py`). The lint compares the claim with the scopes and does not prove what the tool does.
- **Tools with no usable hint.** They are listed and not judged. 🟢 150 of 218 tools carry a hint (`step_01_no_lint.py`).
- **Scope hierarchies, run-time step-up and a manifest export.** Only an `any` scope covers others; there is no export from a live server.
- **Tool descriptions, input schemas and a fully used wildcard.** Poisoning and schema drift are out of scope (see [28 Tool Schema Drift](../28-tool-schema-drift/)); a wildcard that every scope behind it uses is left alone.
- **Real-server numbers, a call log or hosting.** The planted set and the rules share an author, so the numbers are a ceiling.

---

## Appendix: sample contract

The call is the prototype's own. Its output for the bundled `--demo` run is under "Run one now" in the README.

```bash
python3 mcp_scope_lint.py lint manifest.json --propose --fail-on error --format text
```

The input is the manifest shape in section 3; `data/example_clean.json` is one with no findings and `data/example_manifest.json` is the one behind `--demo`. Exit status: 0 below `--fail-on`, 1 at or above it, 2 for bad input.
