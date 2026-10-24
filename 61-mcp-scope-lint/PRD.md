# PRD: MCP Scope Lint

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a security and platform review. It is not a record of a PRD landed at a named bank. The rules, the planted manifests and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | MCP Scope Lint: a command-line linter that reads a tool manifest for an MCP server, scores how broad its grant is and prints a smaller grant that never adds a scope |
| **Owner** | The engineer who owns the MCP server, with the security or platform reviewer who approves the grant as co-owner of the policy |
| **Stage** | Portfolio prototype on synthetic data; no CI wrapper is staged |
| **Primary user** | An engineer who owns an MCP server |
| **Secondary users** | The security or platform reviewer who approves what the server may be granted; the tool author who writes the hints; internal audit |
| **Problem** | An MCP server is granted a set of scopes, and its tools each ask for some of them. Nobody compares the two. A scope that no tool asks for stays. A wildcard stays whole although the tools use one scope behind it. A tool marked read-only can still ask for write. The review approves a list of names. In the planted set, 🟢 83 of 260 reachable scopes are not needed (31.9%) and 17 of 30 manifests grant a scope that no tool asks for (`step_01_no_lint.py`). |
| **Solution** | Parses a tool manifest into tools, a scope catalog and a grant, and rejects anything malformed with exit 2. Applies five rules: an unused grant, a wildcard used in part, a tool that asks for more than its hints allow, a tool with no hint that asks for a wildcard, a tool that requires a scope that is not granted. Scores breadth, the share of reachable scopes that no tool requires. Proposes a smaller grant that never adds a scope and lists the tools it changes. Prints text or GitHub annotations and exits non-zero at a chosen level. |
| **North-star metric** | Share of in-scope MCP servers in production whose grant has been linted, with every finding cleared or accepted by a named person. Target 🔴 100%. Today in this model: nothing compares the tools with the grant. |
| **Measured metrics (synthetic)** | 🟢 Unneeded scopes cut: 61 of 83, against 53 of 83 for a blocklist that also cuts 18 needed ones; no finding on the hard negatives built to look risky (0 on 15, 6 and 8 tools); the known limits named (22 of 83 unneeded scopes stay, 3 needed ones are cut) (`step_04_with_lint.py`, `step_02_blocklist.py`). |
| **Modeled metrics** | 🟡 Utility (61/83 − 53/83) × 100 = 9.6 more unneeded scopes removed than a blocklist would remove, assuming 100 unneeded scopes are granted across the servers an organization runs. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling, not a rate on a real server catalog. Mitigation: run it on one real manifest its owner is allowed to share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | A hint is a claim by the tool's author, and a wrong read-only hint makes the proposal cut a needed scope. 🟢 3 needed scopes are cut in the planted set (`step_04_with_lint.py`). Mitigation: the proposal is advisory, lists every tool it changes, and a person reads each one before anything is removed. |
| **Risk #3** | A manifest shows less slack than there is, because tools that over-ask look like need. 🟢 The manifests alone show 38 of 260 reachable scopes that no tool requires, and the generator's truth says 83 (`step_04_with_lint.py`). Mitigation: compare with a call log, as in 23 ScopeKeeper, to find what the manifest cannot show. |
| **Out of scope** | Reading tool descriptions or input schemas; scope hierarchies other than a per-resource wildcard; run-time scope step-up; exporting a manifest from a live server; any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is manifests, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Unused-grant rule** (a granted scope that no tool requires: error) | 30 manifests | 3 | 0.9 | 1 | 81.0 | Built in prototype |
| 2 | **Tool-above-hint rule** (a tool requires more than its hints allow: error) | 30 manifests | 3 | 0.7 | 1 | 63.0 | Built in prototype |
| 3 | **Manifest parsing and validation** (empty, truncated, wrong-type, unknown or duplicate names exit 2, never a traceback) | 30 manifests | 2 | 0.9 | 1 | 54.0 | Built in prototype |
| 4 | **Wildcard rules** (a wildcard used in part: warn; a tool with no hint that requires a wildcard: warn) | 30 manifests | 2 | 0.8 | 1 | 48.0 | Built in prototype |
| 5 | **Least-privilege proposal** (keep, narrow, remove; tool changes; never adds a scope) | 30 manifests | 3 | 0.7 | 2 | 31.5 | Built in prototype |
| 6 | **CI output** (text and GitHub annotations, `--fail-on` levels, escaped strings) | 30 manifests | 2 | 0.9 | 2 | 27.0 | Built in prototype |
| 7 | **Scope-not-granted rule** (a tool requires a scope the grant does not cover: error) | 30 manifests | 1 | 0.8 | 1 | 24.0 | Built in prototype |
| 8 | **CI wrapper** (a staged Action or pipeline step, inputs through environment variables) | 30 manifests | 2 | 0.6 | 2 | 18.0 | Sequenced for v0.2 |
| 9 | **Lint record** (manifest hash, rules version, findings, who accepted what) | 30 manifests | 2 | 0.7 | 4 | 10.5 | Sequenced for v0.2 |
| 10 | **Call-log comparison** (find the tool nobody calls, with 23 ScopeKeeper) | 30 manifests | 2 | 0.5 | 3 | 10.0 | Sequenced for v0.3 |
| 11 | **Manifest export from server configuration** | 30 manifests | 3 | 0.5 | 5 | 9.0 | Sequenced for v0.2 |
| 12 | **Scope hierarchies** (an admin scope that implies read) | 30 manifests | 1 | 0.4 | 3 | 4.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from MCP Scope Lint | What they fear |
| --- | --- | --- | --- |
| **MCP server owner** | Owner | A step that fails with a reason a person can act on, and a smaller grant they can apply without breaking a tool. | A proposal that cuts a scope a tool needs and breaks it in production. |
| **Security or platform reviewer** | Approver of the grant and of accepted findings | A list of what is granted and not needed, and a record of who accepted what. | Approving a list of names again because the lint was too noisy to read. |
| **Tool author** | Consulted | A clear message when a hint and a scope disagree, so they fix the hint or the scope. | Being blamed for a hint they wrote in good faith. |
| **Identity and access team** | Informed | Scope names that carry an explicit resource and access level, so the lint reads fields and not spellings. | A new tool that infers meaning from how a scope is named. |
| **Agent product owner** | Consulted | A grant review that does not slow a release. | A surprise error late in a release. |
| **Security / CISO** | Approver | No credential in the lint's path, nothing leaving the boundary, strings from input kept out of logs. | Another tool in the pipeline holding tokens. |
| **Internal audit** | Reader | A path from a lint result to the exact manifest and rules version it used. | A grant that changed between two reviews with no record. |

---

## User stories (top 4)

1. **As the MCP server owner**, I want the pipeline to fail when a scope is granted and no tool requires it, so a grant does not grow quietly and stay.
2. **As a reviewer who approves a grant**, I want each finding to name the tool or the scope and say what to read next, so I can accept it or ask for a change without a meeting.
3. **As a tool author**, I want the lint to flag a read-only tool that requires a write scope, so I fix the hint or the scope before the review does.
4. **As internal audit**, I want each lint result tied to the manifest and the rules version it used, so I can reproduce it later.

---

## KPIs

**North star:** share of in-scope MCP servers in production whose grant has been linted, with every finding cleared or accepted by a named person. Target 🔴 100%.

**Inputs (leading):**
- Tools that carry a usable hint (the prototype set has 🟢 150 of 218 tools, from `step_01_no_lint.py`; target: every tool).
- Manifests exported from the server's configuration and not written by hand (target: every server).
- Scopes in the catalog that carry an explicit `resource` and `access`, so the rules never read a spelling (target: every scope).
- Findings accepted with a named approver and an expiry (target: every accepted finding).

**Outputs (lagging):** prototype baselines from the planted set.
- Unneeded scopes cut. 🟢 61 of 83 with the lint, against 53 of 83 with a blocklist (`step_04_with_lint.py`, `step_02_blocklist.py`).
- Needed scopes cut. 🟢 3 with the lint, against 18 with a blocklist (`step_04_with_lint.py`, `step_02_blocklist.py`).
- Reachable scopes after the proposal. 🟢 260 before, 196 after, 24.6% cut (`step_04_with_lint.py`).
- Findings. 🟢 38 errors and 12 warnings across the 30 manifests (`step_04_with_lint.py`).
- False alarms on the hard negatives. 🟢 0 on 15, 6 and 8 tools (`step_04_with_lint.py`).
- Known miss. 🟢 22 of 83 unneeded scopes stay reachable (`step_04_with_lint.py`).
- Proposals applied that later broke a tool: not measured; the planted set has no running tools.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the lint on one server's manifest with `--fail-on never`. Read the findings and the proposal, change nothing, and compare with what the owner already knew. |
| 1: Manifest and hints | 4w | Export or hand-maintain the manifest in the server repo. Ask tool authors to add hints where there are none, since a tool with no hint is listed and not judged. |
| 2: Errors enforced | 4w | Fail the step on `unused_grant` and `tool_scope_above_hint`. A finding is cleared by changing the grant or accepted by a named person. |
| 3: Proposal applied by review | 6w | The owner applies the proposal through a pull request, one tool change read by a person at a time, with the tool's own tests run. Warnings stay advisory. |
| 4: Record and call log | 8w | Write a lint record per run. Compare with a call log, as in 23 ScopeKeeper, to find tools nobody calls. |

---

## Open questions

1. **Should a read-only tool that requires a write scope fail the pipeline?** In the prototype it does; that is my policy. Either the hint or the scope is wrong, and both deserve a look. Recommendation: keep it an error, and let the owner fix the hint or the scope or accept the finding with a named approver.
2. **Should a fully used wildcard be replaced with its list?** In the prototype it is left alone. Replacing it would shrink nothing today but would stop it covering scopes added later. Recommendation: leave it alone, and add an advisory note once the first real manifest shows whether anyone wants it.
3. **How does the manifest get exported when scopes are raised at run time?** I have not built the export. Recommendation: start with a manifest kept in the server repo and reviewed with the code, and build the export after the first pilot shows what it must read.
4. **Who may accept a finding?** Recommendation: a reviewer other than the server's owner, with an expiry date, recorded with the manifest hash.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the pipeline.** The lint is stateless: it reads one manifest and returns findings, a score, a proposal and an exit code. Production adds a manifest export, a reviewed policy and a lint record, all designed and none built.
- **Never silent.** A missing, empty, truncated or malformed manifest exits 2 and fails the step, even with `--fail-on never`. A tool with no hint is listed as not checked, not shown as fine.
- **Strings from input are data.** Text output and annotations escape control characters, so a hostile tool name cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the cut count shows in the diff.

**What is next.** Run it against one real server manifest its owner can share; add an export from a server's configuration; compare with a call log to catch the tool nobody calls.

**What would have to be true before a pilot.**
- The manifest comes from the server's code or configuration, not from memory.
- Scopes carry an explicit resource and access level.
- A named person owns the grant and will read each proposed tool change before it is applied.
- One real manifest can be shared, so the severity levels are set against a real server and not mine.
- The team agrees which level fails the step.

---

*This PRD names [23 ScopeKeeper](../23-scopekeeper-agent-permission-review/), [15 SchemaWatch](../15-schemawatch-tool-schema-drift/), [28 Tool Schema Drift](../28-tool-schema-drift/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The breadth score and the proposal idea are carried over from 23 by hand, not read from its files.*
