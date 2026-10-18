# PRD · ScopeKeeper — Agent Permission Review for Tool-Calling AI Agents

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for an access-governance read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an agent platform review in the seat. It is not a record of a PRD landed at a named bank. The six-deficiency taxonomy, the proposal rule, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. RICE scores and rollout durations below are planning estimates (🔴), not measurements.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | ScopeKeeper — permission review for tool-calling AI agents |
| **Owner** | Agent Platform Owner (line-1), with the access-governance reviewer as co-owner of the approval step |
| **Stage** | Portfolio prototype; access-governance read |
| **Primary users** | Agent platform owner, who owns the agents and the scopes they hold; access-governance reviewer, who runs the recertification |
| **Secondary users** | Agent owners (the managers who ask for scopes and approve the list); model risk reviewer; security |
| **Problem** | An AI agent is granted scopes at launch and gains more over time. The control is an annual recertification where the manager approves the list; nobody compares the grants with the calls. In the synthetic data, 🟢 the review approved 182 of 184 grants (98.9%) and removed 2, while 🟢 69 of 184 grants (37.5%) had no call in 90 days and the generator's truth says 71 grants are not needed. |
| **Solution** | A review layer that compares grants with 90 days of calls: a usage-versus-grant diff that credits shared-account calls conservatively, a breadth score, a proposed least-privilege scope set (keep, remove, narrow a wildcard), a dry-run replay of the calls under the proposal, and a risk ranking. A person approves every change. |
| **North-star metric** | Share of in-scope agents whose scope set was compared with the last 90 days of calls and decided in the last quarter. Target 🔴 100% of in-scope agents. Today in this model: 0%, nothing runs. |
| **Measured metrics (synthetic)** | 🟢 61 of 71 unneeded grants removed (85.9%), against 1 for the annual review; 🟢 211 effective entitlements cut to 126 (40.3% cut); 🟢 0 of 7,994 calls denied in the in-sample replay (by construction). |
| **Modeled metrics** | 🟡 Utility about 800 unneeded grants removed, assuming 200 agents in a bank's estate; 🟡 about 680 legitimate calls denied next quarter at the same mix until owners attest the periodic scopes. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on call-log volume and has not been sized. |
| **Risk #1** | Owners approve the removal list the way they approved the grant list, so nothing is removed. Mitigation: show the usage next to every proposal, count the share of proposals approved as a first-class metric, and require a separate approver for any change to a high-impact scope. |
| **Risk #2** | A scope used once a quarter looks unused in a 90-day window. 🟢 8 legitimate quarterly grants are removed, and the next quarter would deny 51 legitimate calls. Mitigation: an owner attestation question on every removal ("is this scope periodic?"); 🔴 designed, never tested with real owners. |
| **Risk #3** | Shared service accounts make usage ambiguous. 🟢 21.6% of calls carry no agent tag and 10 unneeded grants stay as the cost of never marking a grant in use as unused. Mitigation: one service account per agent. |
| **Out of scope** | Runtime observability (AgentWatch, 05); the tool-call gate and prompt-injection defense (PromptShield, 06); the human-approval workflow (OversightOps, 08); tool schema changes (SchemaWatch, 15); mapping access obligations to controls (ControlMap, 16). |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is agents or roles, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Usage-versus-grant diff** (wildcards expanded, shared-account crediting) | 15 agents | 3 | 0.9 | 3 | 13.5 | Built in prototype; v0.1 |
| 2 | **Proposed scope set** (keep, remove, narrow, with a reason per row) | 15 agents | 3 | 0.9 | 3 | 13.5 | Built in prototype; v0.1 |
| 3 | **Dry-run replay** (denied-call count before any change) | 15 agents | 3 | 0.9 | 3 | 13.5 | Built in prototype; v0.1 |
| 4 | **Risk ranking** (impact-weighted unused access, unapproved calls, shared account) | 15 agents | 2 | 0.8 | 2 | 12.0 | Built in prototype; v0.2 |
| 5 | **Approval-gap report** (high-impact calls with no human approval) | 15 agents | 2 | 0.8 | 2 | 12.0 | Built in prototype; v0.2 |
| 6 | **Collector** (nightly grant snapshots, read-only call-log view) | 15 agents | 3 | 0.9 | 4 | 10.1 | Sequenced for v0.1 |
| 7 | **Owner attestation question** on every removal (periodic scope?) | 15 agents | 3 | 0.5 | 3 | 7.5 | Sequenced for v0.2 |
| 8 | **Re-run on a tool change** (SchemaWatch interlock) | 15 agents | 2 | 0.5 | 3 | 5.0 | Sequenced for v0.3 |
| 9 | **Apply hook** (remove or narrow only, never add) | 15 agents | 3 | 0.5 | 5 | 4.5 | Sequenced for v0.3 |
| 10 | **Newly launched agent rule** (no proposal until a full window exists) | 15 agents | 1 | 0.5 | 3 | 2.5 | Sequenced for v0.3 |
| 11 | **One service account per agent** (migration plan for shared accounts) | 7 agents | 3 | 0.6 | 6 | 2.1 | Sequenced for v0.3 |
| 12 | **Argument-aware usage** (what a call did with the scope) | 15 agents | 2 | 0.4 | 6 | 2.0 | Queued |
| 13 | **Evidence bundle exporter** to the access-governance record | 2 reviewers | 2 | 0.9 | 2 | 1.8 | Sequenced for v0.3 |
| 14 | **Review queue** with a separate approver for high-impact scopes | 2 reviewers | 3 | 0.7 | 5 | 0.8 | Sequenced for v0.3 |

---

## Stakeholder map

| Stakeholder | Role | What they want from ScopeKeeper | What they fear |
| --- | --- | --- | --- |
| **Agent Platform Owner** (line-1) | Owner | To know which scopes each agent uses, and a smaller set that still covers every call, with the replay to prove it. | An agent that stops working because a scope was cut; a review nobody finishes. |
| **Access-governance reviewer** | Co-owner of the approval step | Evidence per agent, a queue they can clear, and a record of who approved what. | A second review process that competes with the recertification; a proposal presented as a decision. |
| **Agent owners** (managers) | Approvers | A short list with the usage next to each line and a way to say "this scope is periodic". | Being asked to approve removals they cannot judge; being blamed when a quarterly job fails. |
| **Model risk reviewer** (line-2) | Auditor | A record of what each deployed agent was allowed to do against what it did. | A heuristic presented as a guarantee; a proposal built on a thin log. |
| **Security / CISO** | Approver | Least-privilege reads of the grant store and the call log; no call arguments stored. | Call values copied into yet another store. |
| **SRE on call** | Consulted | To know that a denied call after a cut was approved and why. | Pages for a scope that was removed on purpose. |
| **Agent feature product owners** | Consulted | Warning before an agent loses a scope its feature uses. | Finding out from a failed quarter-end job. |

---

## User stories (top 4)

1. **As an agent platform owner**, I want every agent's scope set compared with the last 90 days of calls, so I know which grants are used, which are not, and which wildcards are wider than the agent needs.
2. **As an access-governance reviewer**, I want a proposed smaller set per agent with the replay result and the reason on every row, so I can clear the queue without opening the call log myself.
3. **As an agent owner**, I want to mark a scope as periodic before it is removed, so a quarter-end job does not fail on a cut I could not see coming.
4. **As a model risk reviewer**, I want the record of what each deployed agent was allowed to do, what it did, and who approved the change, so the ongoing-monitoring story under SR 26-2 and the NIST AI RMF is documented per review and not only at attestation time.

---

## KPIs

**North star:** share of in-scope agents with a scope set compared and decided in the last quarter. Target 🔴 100%.

**Inputs (leading):**
- Agents with grants and 90 days of calls captured (target: every in-scope agent).
- Share of calls with an agent tag (target: 100%; prototype: 🟢 21.6% of calls untagged).
- Owner response rate on attestation questions (target: every removal proposal answered before it is applied).
- Review queue age (🔴 design target: inside the review cycle, not a separate backlog).

**Outputs (lagging):**
- Unneeded grants removed per agent. Prototype baseline: 🟢 0.07 with the annual review, 4.07 with ScopeKeeper, on synthetic data.
- Share of effective entitlements cut. Prototype: 🟢 40.3%.
- Legitimate calls denied after a cut (the known-limit class). Prototype: 🟢 51 calls from 8 quarterly grants.
- Calls to approval-required scopes logged without approval. Prototype: 🟢 118 of 1,243.
- Agents on a shared service account. Prototype: 🟢 7 of 15.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Shadow | 4w | Collector and diff on a handful of agents. Nothing shown to owners; compare the proposal with what the agents actually need when asked. |
| 1 — Replay | 4w | Replay the call log under the proposals and review every denied call with the owner. Calibrate the window length. |
| 2 — Advisory queue | 6w | Proposals posted to owners with the usage and the periodic-scope question. Nothing is applied. Measure the share approved and the share marked periodic. |
| 3 — Apply for low-impact scopes | 6w | Approved removals applied automatically for read scopes. A separate approver for any write, message or money-movement scope. |
| 4 — Estate and interlocks | 8w | Remaining agents; one service account per agent; interlocks to AgentWatch, PromptShield, OversightOps and SchemaWatch; evidence bundles to the access-governance record. |

---

## Open questions

1. **Who may apply a change?** Does an approved proposal change the grant store, or only open a ticket? Recommendation: tickets first, automatic apply only for read scopes after phase 2 shows owners approve what is proposed.
2. **Who owns the call log?** The diff needs scope names and counts per agent and day, not arguments. Recommendation: the agent platform team owns capture; ScopeKeeper stores counts only.
3. **How long is the window?** The prototype uses 90 days, which hides quarterly scopes (🟢 8 grants). Recommendation: keep 90 days for the diff, add the owner question for anything removed, and measure how many answers are "periodic" before lengthening the window.
4. **What about an agent launched last week?** There is no history to propose from. Recommendation: no proposal until the agent has a full window; the grant list stays under the ordinary review.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Collector:** a nightly snapshot of the grant store and a read-only view of the tool-call log, written as daily usage facts.
- **Differ, proposer and replay:** stateless workers. The differ credits calls to agents; the proposer builds the smaller set; replay counts the calls the set would deny.
- **Review queue:** owner attestation, a separate approver for high-impact scopes, and a hook that applies an approved change.
- **Storage:** Postgres for grants, proposals, decisions and attestations; a columnar store for usage facts; object storage with retention for evidence bundles.

**Throughput envelope and latency budget.**
- Work is agents times days times scopes. The prototype diffs 15 agents and 7,994 calls with a plain Python loop. Production volumes have not been sized.
- Review latency: 🔴 design target is a proposal ready by the next business day after the nightly run. Not built, not timed.

**Failure modes and degradation strategy.**
- Call log feed missing for a day: the diff marks the window incomplete and proposes nothing for that agent.
- Fewer calls than a minimum for an agent: no proposal; the grant list goes to the ordinary review.
- Agent tag missing on a shared account: credit every agent that could have made the call, and report the count of such calls per account.
- Review queue unavailable: nothing is applied. The system fails closed on changes, because a removal is the risky action.

**Migration path from current state.**
- If the annual recertification runs today: keep it. It is the control of record; ScopeKeeper feeds it a usage column and a proposal.
- If calls are not tagged per agent: move to one service account per agent first, or add an agent header to the tool gateway.

**Org dependencies.**
- Agent owners must answer the periodic-scope question. Without that the known limit stays open.
- The agent platform team must capture and retain the call log in a form the diff can read.
- The access-governance team must accept the proposal as part of its record. Without that the audit story is incomplete.

---

*This PRD interlocks with [Project 05 (AgentWatch)](../05-agentwatch-agent-observability/), [Project 06 (PromptShield)](../06-promptshield-prompt-injection-defense/), [Project 08 (OversightOps)](../08-oversightops-hitl-workflow/) and [Project 15 (SchemaWatch)](../15-schemawatch-tool-schema-drift/); all interlocks are 🔴 designed, none built.*
