# PRD · SchemaWatch — Tool-Schema Drift Detection for Tool-Calling Agents

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a pre-release-governance read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an agent platform review in the seat. It is not a record of a PRD landed at a named bank. The change taxonomy, the gate vocabulary, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. RICE scores and rollout durations below are planning estimates (🔴), not measurements.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | SchemaWatch — tool-schema drift detection for tool-calling agents |
| **Owner** | Agent Platform Lead (line-1), with tool (API) owners as co-owners of the gate |
| **Stage** | Portfolio prototype; pre-release-governance read |
| **Primary user** | Agent platform lead, who owns the agent and the tools it is allowed to call |
| **Secondary users** | Tool (API) owners who ship the schemas; SRE on call; model risk reviewer |
| **Problem** | An agent calls tools, and each tool is an API with a JSON schema owned by another team. Owners rename a parameter, tighten a type, add a required field, drop an enum value or change a unit in a description without telling the agent team. Calls fail loudly, or worse, succeed with the wrong meaning. In the synthetic data, 🟢 742 of 2,500 recorded calls fail in the week after the releases land and 🟢 538 more pass and mean something different. |
| **Solution** | A consumer-side check on every schema release: structural diff and classifier (breaking, non-breaking, behavior-risk), a description heuristic for numbers and units, replay of recorded calls against the new schema, blast-radius ranking, and a release gate (BLOCK, REVIEW, ALLOW) with a reason. |
| **North-star metric** | Share of in-scope tool-schema releases that receive a SchemaWatch decision before they reach the agent. Target 🔴 100% of in-scope tools. Today in this model: 0%, nothing runs. |
| **Measured metrics (synthetic)** | 🟢 41 of 45 changes classified as the ledger says; 🟢 742 of 742 broken calls predicted with 0 false positives; 🟢 5 of 5 unit-swap changes flagged; 🟢 gate matches the ledger-derived answer on 27 of 31 releases. |
| **Modeled metrics** | 🟡 Median 15.9 hours from release to a person hearing about a break with no monitoring, at best (alert on the 5th failed call, instant delivery). 🟡 Utility about 296 calls per quarter, assuming 12 schema changes a quarter and that every hold is acted on. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on call-log volume and has not been sized. |
| **Risk #1** | Owners treat the gate as a speed bump and deploy around the registry. Mitigation: start advisory, count bypasses as a first-class metric, hold only what passes through a registry or pipeline the owners agreed to use. |
| **Risk #2** | Replay runs on a stale or thin call log and gives false comfort. Mitigation: a minimum recorded-call count per tool; below it the gate says REVIEW, not ALLOW. |
| **Risk #3** | The description heuristic gives false confidence. It reads numbers and units only; 🟢 0 of 3 meaning changes with no number or unit were flagged. Mitigation: an owner attestation field ("does this release change what any parameter means?") and a human read of description diffs for tools that move money. |
| **Out of scope** | Runtime failure detection (AgentWatch, 05); the tool-call gate and prompt-injection defense (PromptShield, 06); decision-level audit lineage (LineageLog, 09); contract tests on the owner's side. |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is tools or roles, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. Rows are grouped by the release that carries them (v0.1, v0.2, v0.3, then queued). In v0.1 the order is build order, because the diff, the replay and the gate read the collector's revisions; in the other groups it is RICE order.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Collector and revision store** (content-hashed schema revisions per tool) | 28 tools | 3 | 0.9 | 4 | 18.9 | Sequenced for v0.1 |
| 2 | **Structural diff and classifier** (breaking, non-breaking, behavior-risk, with reasons) | 28 tools | 3 | 0.9 | 3 | 25.2 | Built in prototype; v0.1 |
| 3 | **Replay validator** (would-break count per tool from recorded calls) | 28 tools | 3 | 0.9 | 3 | 25.2 | Built in prototype; v0.1 |
| 4 | **Release gate** (check API for the owner's pipeline, hold state in the registry) | 28 tools | 3 | 0.7 | 5 | 11.8 | Sequenced for v0.1 |
| 5 | **Description heuristic** (numbers and units in descriptions) | 28 tools | 2 | 0.8 | 2 | 22.4 | Built in prototype; v0.2 |
| 6 | **Revision-hash stamp on the decision lineage record** (LineageLog interlock) | 28 tools | 2 | 0.8 | 2 | 22.4 | Sequenced for v0.2 |
| 7 | **Owner attestation field** (does this release change what a parameter means?) | 28 tools | 3 | 0.5 | 2 | 21.0 | Sequenced for v0.2 |
| 8 | **Blast-radius ranking** (by recorded calls hit) | 4 roles | 2 | 0.9 | 2 | 3.6 | Built in prototype; v0.2 |
| 9 | **Constraint diff** (minimum, maximum, maxLength, pattern) | 28 tools | 2 | 0.8 | 3 | 14.9 | Sequenced for v0.3 |
| 10 | **Known-drift label for runtime failures** (AgentWatch interlock) | 28 tools | 2 | 0.7 | 3 | 13.1 | Sequenced for v0.3 |
| 11 | **Replay calibration** against real server rejections | 28 tools | 3 | 0.6 | 4 | 12.6 | Sequenced for v0.3 |
| 12 | **Evidence bundle exporter** to the model-risk record | 2 reviewers | 2 | 0.9 | 2 | 1.8 | Sequenced for v0.3 |
| 13 | **Fallback routing for tools under BLOCK** (PromptShield interlock) | 28 tools | 2 | 0.5 | 4 | 7.0 | Queued |
| 14 | **Nested objects, oneOf and anyOf in the validator** | 9 tools | 2 | 0.6 | 5 | 2.2 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from SchemaWatch | What they fear |
| --- | --- | --- | --- |
| **Agent Platform Lead** (line-1) | Owner | To hear about a release before the agent does, with the calls it breaks and the order to read them in. | A gate that blocks benign changes; a tool nobody owns. |
| **Tool (API) owners** | Co-owners of the gate | A clear verdict and the evidence behind it, fast, inside the pipeline they already use. A way to say "this is cosmetic" and be believed. | Another approval step run by a team that does not own their roadmap; false BLOCKs on harmless edits. |
| **SRE on call** | Consumer of the alerts | To be told "this failure is known drift from release X" instead of debugging a new incident. | Pages for changes that were already allowed; a second alert stream that duplicates the first. |
| **Model risk reviewer** (line-2) | Auditor | A record of which schema revision each decision ran under, and evidence that changes were assessed before release. | A parallel attestation surface that competes with the model inventory; a heuristic presented as a guarantee. |
| **Security / CISO** | Approver | No customer values stored in the replay log beyond what replay needs; least-privilege reads from the tool registry. | Argument values copied into yet another store. |
| **Release engineering** | Consulted | A check that runs in the owner's pipeline without adding a long step. | A slow or flaky gate that gets disabled. |
| **Agent feature product owners** | Consulted | To know why a feature's behavior changed in the same week. | Finding out from customers. |

---

## User stories (top 4)

1. **As an agent platform lead**, I want every tool-schema release scored against the calls my agent actually sends, so I know which releases break calls before they reach production and which only change meaning.
2. **As a tool owner**, I want a verdict with reasons and example calls when I publish a schema revision, so I can fix a real break or mark a change cosmetic without a meeting.
3. **As an SRE on call**, I want a runtime tool failure to carry the open SchemaWatch decision for that tool, so I can tell known drift from a new incident in the first minute.
4. **As a model risk reviewer**, I want the schema revision each tool call ran under, with the gate decision that let it through, so the ongoing-monitoring story is documented per release and not only at attestation time (SR 11-7 and the NIST AI RMF 'Measure' function are the guidance the work is compared with).

---

## KPIs

**North star:** share of in-scope tool-schema releases with a SchemaWatch decision before reaching the agent. Target 🔴 100%.

**Inputs (leading):**
- Tools with a revision history captured (target: every in-scope tool).
- Recorded calls per tool in the replay window (target: a minimum per tool; below it the gate says REVIEW).
- Owner attestation rate on releases (target: 100% of REVIEW and BLOCK releases).
- Gate decision latency (🔴 design target: inside the owner's pipeline step, not a separate queue).

**Outputs (lagging):**
- Calls broken or misread per change. Prototype baseline: 🟢 28.44 with no gate, 3.76 with the gate on synthetic data.
- Releases shipped without a version bump that SchemaWatch caught. Prototype: 🟢 9 of 25 releases needing action were unbumped; the gate held 8 of those 9.
- False REVIEW rate (target: trending down as owners attest). Prototype: 🟢 1 of 31.
- Gate bypass count: releases that reached the agent with no decision.
- Meaning changes found after release by a person (the known-limit class). Prototype: 🟢 3 changes, 169 calls.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Shadow | 4w | Collector and diff on a handful of tools. No verdicts shown to owners; compare the classifier against what actually broke. |
| 1 — Replay | 4w | Feed the recorded tool-call log to the replay validator. Calibrate would-break counts against real rejections. |
| 2 — Advisory gate | 6w | Verdicts posted on the owner's pipeline as a non-blocking check. Owner attestation field live. Count bypasses. |
| 3 — Blocking for money-moving tools | 6w | BLOCK holds the registry publish for payments, cards and lending tools. REVIEW needs a named approver. |
| 4 — Estate and interlocks | 8w | Remaining tools; AgentWatch known-drift label; LineageLog revision stamp; evidence bundles to the model-risk record. |

---

## Open questions

1. **Gate authority.** Does BLOCK hold a release, or only advise? Recommendation: advisory first, blocking only for tools that move money, and only on what passes through a registry or pipeline the owners agreed to use. An owner who deploys around the registry is caught by the poller as a fast alert, not a hold.
2. **Who owns the tool-call log?** Replay needs recorded arguments. Recommendation: the agent platform team owns capture; values are tokenized because replay needs types and enum values, not customer text.
3. **Meaning changes with no number or unit.** The heuristic cannot see them (🟢 0 of 3). Recommendation: owner attestation plus a human read of description diffs on money-moving tools, measured against the next ledger.
4. **How many recorded calls are enough?** The prototype replays 2,500 calls. Recommendation: set a per-tool minimum from the first calibration phase; below it, REVIEW.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Collector:** a scheduled poller plus a publish hook on the tool registry, writing immutable revisions keyed by content hash.
- **Differ and replay:** stateless workers. The differ runs the structural classifier and the description heuristic; replay validates recorded calls against the new revision.
- **Gate:** an HTTP check the owner's pipeline calls, plus a hold state in the registry.
- **Storage:** Postgres for revisions, findings and decisions; a columnar store for replay results; object storage with retention for evidence bundles.

**Throughput envelope and latency budget.**
- Replay work is recorded calls per tool times releases. The prototype replays 2,500 calls across 31 releases with a plain Python loop. Production volumes have not been sized.
- Gate latency: 🔴 design target is a decision inside the owner's pipeline step. Not built, not timed.

**Failure modes and degradation strategy.**
- Collector misses a publish: the poller catches the new content hash on its next pass and opens the decision late; the late-detection count is a metric.
- Too few recorded calls for a tool: REVIEW, never ALLOW.
- Validator meets a schema feature it does not support (pattern, nested objects, oneOf): REVIEW with the unsupported feature named.
- Gate service unavailable: the owner's pipeline check fails open with a logged bypass in advisory mode, and fails closed in blocking mode for money-moving tools.

**Migration path from current state.**
- If the platform compares version strings or hashes today: keep them. The hash is a useful tripwire; SchemaWatch is what runs when it fires.
- If there is no revision history: start the collector first. Replay and the gate need two revisions to compare.

**Org dependencies.**
- Tool owners must agree to publish through a registry or call a check. Without that the gate can only alert.
- The agent platform team must capture and retain tool-call arguments in a form replay can use.
- The model-risk team must accept the evidence bundle as part of its record. Without that interlock the audit story is incomplete.

---

*This PRD interlocks with [Project 05 (AgentWatch)](../05-agentwatch-agent-observability/), [Project 06 (PromptShield)](../06-promptshield-prompt-injection-defense/) and [Project 09 (LineageLog)](../09-lineagelog-ai-decision-audit/).*
