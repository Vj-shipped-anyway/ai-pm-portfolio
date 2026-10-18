# PRD · TierGate — AI Use-Case Intake and Risk Tiering

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a pre-AI-governance-committee read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an AI governance committee in the seat. It is not a record of a PRD landed at a named bank. The deficiency taxonomy, the rubric, the architecture and the rollout plan are mine; the numbers are measured or modeled on 150 synthetic submissions; the production validation is what the next role does. The reference tier in the prototype is true by construction, so accuracy figures describe recovery of a written rubric from noisy inputs, not how real banks behave.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | TierGate — AI use-case intake and risk tiering for a regulated bank |
| **Owner** | AI governance lead (line 2), with the model risk reviewer lead as co-owner of the evidence checklist |
| **Stage** | Portfolio prototype; pre-AI-governance-committee read |
| **Primary users** | AI governance lead; model risk reviewer |
| **Secondary users** | Use-case sponsors (line 1); the CRO; data catalog stewards; internal audit |
| **Problem** | A sponsor fills in an intake form and self-declares the risk tier. High-risk cases get a light review, low-risk cases wait behind heavy ones, and required evidence is requested ad hoc. Nobody can say how many AI use cases exist, which tier each sits in, or what evidence each owes. 🟢 On the synthetic set the declared tier is wrong on 30.7% of submissions and 32 of 116 approvals lack evidence the reference tier requires (`step_02`). |
| **Solution** | Recompute the tier with the bank's written rubric on cross-checked inputs (data catalog, vendor registry, text), flag each discrepancy with a reason, link duplicate submissions, gate approval on the evidence checklist of the recomputed tier, and order the review queue by tier. |
| **North-star metric** | Share of AI use cases in the register whose tier was recomputed from a second source and whose approval was gated on that tier's checklist. Design target: 100%. Current basic approach: 0%, because no tier is recomputed. |
| **Measured metrics (synthetic set)** | 🟢 Tier accuracy 69.3% → 86.0%; 🟢 tier 3-4 recall 75.7% → 100.0%; 🟢 evidence-gap detection 51.5% → 95.5%; 🟢 approvals with required evidence missing 32 of 116 → 3 of 76; 🟢 duplicate pairs proposed 9 of 10, with 5 false proposals (`step_02`, `step_04`) |
| **Modeled metrics** | 🟡 Tier 3-4 mean queue wait 2.9 → 1.2 business days when the same review times are ordered by tier (3 reviewers, 200 seeded replications); 🟡 tier 1-2 wait 3.4 → 9.7 days; 🟡 reviewer hours 900.0 (spreadsheet), 714.0 (declared tier), 837.0 (TierGate) |
| **Utility** | 🟡 (30.7% − 14.0%) × 375 submissions a year = 62.5 mis-tiered use cases avoided per year at a modeled $50B-asset US retail bank that sees the intake rate of the synthetic set (🟢 error rates, 🟡 volume) |
| **Cost** | Not modeled in the prototype. Reviewer hours are modeled (above); build and run cost for a real engagement is not estimated here. |
| **Risk #1** | Over-tiering floods reviewers. 🟢 13 of 150 submissions are tiered above the reference, and the customer-facing text cue was right on 6 of 25 flags. Mitigation: flags are proposals a sponsor clears with a named confirmation; false-flag rate is tracked per rule and a rule below its floor is retired. |
| **Risk #2** | The catalog is stale or the form and the catalog are both wrong, so the recompute agrees with the wrong answer. 🟢 6 synthetic cases, 2 at the wrong tier. Mitigation: catalog freshness check, a third source for data class (lineage scan), and the known-limit count shown on the governance lead's console. |
| **Risk #3** | Sponsors learn the cues and write around them. Mitigation: the catalog and the registry are second sources the sponsor does not control; discrepancy rate per sponsor unit goes to the governance lead; the free-text cue is replaced by a structured channel question (backlog item 2). |
| **Risk #4** | Tier ordering starves low-risk cases. 🟡 Tier 1-2 wait rises from 3.4 to 9.7 business days in the model. Mitigation: an aging cap, designed and not built (🔴). |
| **Out of scope** | Monitoring of running models (02 DriftSentinel); eval runs (04 EvalForge); the human review design itself (08 OversightOps); decision-level audit lineage (09 LineageLog); benefit tracking after approval (12 ValueLedger); prompt-injection defense (06 PromptShield); inference cost (07 InferenceLens). |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Effort in PM-weeks. Reach counts people or units affected: 4 is the three modeled reviewers plus the governance lead, 19 is the number of sponsor units in the synthetic set. All four inputs are my judgment, not measurements (🔴). The build order differs from the RICE order where one item depends on another: the gate needs the recomputed tier first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Cross-check data class against the data catalog** | 19 sponsor units | 3 | 0.8 | 4 | 11.4 | Sequenced for v0.1 |
| 2 | **Structured customer-facing channel question** (replaces the free-text cue) | 19 sponsor units | 2 | 0.6 | 2 | 11.4 | Sequenced for v0.2 |
| 3 | **Cross-check vendor model against the vendor registry** | 19 sponsor units | 2 | 0.8 | 3 | 10.1 | Sequenced for v0.1 |
| 4 | **Sponsor flag-confirm workflow** (clear, correct or contest a flag) | 19 sponsor units | 2 | 0.8 | 5 | 6.1 | Sequenced for v0.2 |
| 5 | **Rubric as versioned configuration** (proposer and a different approver) | 4 | 3 | 0.9 | 2 | 5.4 | Sequenced for v0.1 |
| 6 | **Tier-ordered queue with an aging cap** | 4 | 3 | 0.8 | 3 | 3.2 | Sequenced for v0.2 |
| 7 | **Register view for the governance lead and CRO** | 5 | 2 | 0.9 | 3 | 3.0 | Sequenced for v0.2 |
| 8 | **Evidence checklist gate per tier** | 4 | 3 | 0.9 | 4 | 2.7 | Sequenced for v0.1 |
| 9 | **Catalog freshness check** | 3 | 2 | 0.7 | 2 | 2.1 | Sequenced for v0.3 |
| 10 | **Handoff to 12 ValueLedger after approval** | 4 | 1 | 0.7 | 2 | 1.4 | Queued |
| 11 | **Evidence interlocks with 04, 08 and 09** | 3 | 2 | 0.7 | 4 | 1.1 | Sequenced for v0.3 |
| 12 | **Duplicate link proposals with reviewer confirm** | 4 | 1 | 0.7 | 3 | 0.9 | Sequenced for v0.3 |
| 13 | **Third source for data class** (lineage scan) | 3 | 3 | 0.5 | 8 | 0.6 | Queued |
| 14 | **Map tiers to EU AI Act categories** (with legal review) | 2 | 1 | 0.5 | 5 | 0.2 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from TierGate | What they fear |
| --- | --- | --- | --- |
| **AI governance lead** (line 2) | Owner | One register of every AI use case with its tier by written rule, the flags that changed it, and what evidence each one owes. Authority to hold an approval. | A tool the business routes around; owning the false flags; the rubric becoming a negotiation per case. |
| **Model risk reviewer** | Primary user | The riskiest cases first, with the evidence in hand when the review starts, not requested one email at a time. | Tier 1-2 volume piling up behind the ordering; flags they cannot explain to a sponsor. |
| **Use-case sponsors** (line 1) | Submitters | To know up front what the tier requires and why it changed. A fast path for low-risk cases. | A second form, a hold that arrives late, a tier raised for a keyword. |
| **CRO** | Sponsor of the program | How many tier 3 and tier 4 use cases exist and whether any was approved on thin evidence, without a meeting. | A surprise at an exam: an AI use case nobody had in the inventory. |
| **Data catalog stewards** | Consulted | Their catalog entries used, and told when one looks stale. | Being blamed for the downstream tier when an entry is old. |
| **Vendor risk and procurement** | Consulted | The registry read, so a vendor dependency is not missed because the sponsor forgot. | A second registry that drifts from theirs. |
| **Internal audit** | Reader | A decision record per tier with the inputs, the flags and who confirmed what. | A record that can be edited after the fact. |
| **Legal and compliance** | Consulted | Regulatory scope captured early enough to route the legal review that tier 4 requires. | A tier scale that reads as a legal classification when it is not. |

---

## User stories (top 4)

1. **As the AI governance lead**, I want every submission's tier recomputed from the form, the catalog and the vendor registry, with each change carrying its reason, so I can defend the register to the CRO and to an examiner without re-doing the review.
2. **As a model risk reviewer**, I want the queue ordered by tier and the evidence checklist for that tier already attached, so my first hours go to the cases that need independent challenge.
3. **As a use-case sponsor**, I want to see the evidence my tier requires and why my declared tier changed, before the review starts, so I do not learn about a missing document three weeks in.
4. **As the CRO**, I want the count of tier 3 and tier 4 use cases and the number approved with required evidence missing on one screen, so I can answer the question without convening a meeting.

---

## KPIs

**North star:** share of AI use cases whose tier was recomputed from a second source and whose approval was gated on the recomputed tier's checklist. Design target: 100%.

**Inputs (leading):**
- Tier accuracy on a labelled audit sample drawn by the governance lead. The prototype measures 86.0% on the synthetic set; a real target is set after the first audit sample, not before.
- Share of submissions with a cross-check flag. The prototype shows 74 of 150.
- Flag precision per rule. The prototype shows 34 of 38 for the catalog rule, 21 of 21 for the registry rule, 6 of 25 for the text cue, 3 of 12 for the ambiguous-answer rule.
- Catalog freshness: share of entries reviewed inside the steward's own cycle.
- Evidence-gap detection on the audit sample. The prototype shows 95.5%.

**Outputs (lagging):**
- Approvals granted with required evidence missing. The prototype shows 3 of 76; design target 0.
- Tier 3-4 time to first review, by tier. The model shows 1.2 business days ordered by tier against 2.9 first in first out.
- Tier 1-2 time to first review, so the cost of ordering stays visible. The model shows 9.7 days.
- Mis-tier rate on the audit sample (the prototype's error rate is 14.0% against 30.7% for the declared tier).
- Examination or audit findings on the AI inventory or on tiering (target zero).

---

## Rollout

All durations are design targets, not tested (🔴).

| Phase | Duration | Scope |
| --- | --- | --- |
| 0 — Register | 4w | Import the spreadsheet; back-fill the register so someone can say how many AI use cases exist. No tiering change. |
| 1 — Shadow | 8w | Recompute and log beside the declared tier. Nothing changes for sponsors. Measure flag precision per rule against a reviewer-labelled sample. |
| 2 — Flags to sponsors | 6w | Sponsors see the flags and clear, correct or contest them. The rubric and the checklist become versioned configuration with a proposer and a different approver. |
| 3 — Evidence gate | 8w | Gate approval on the recomputed tier's checklist for tier 3 and tier 4 first, then tier 2. |
| 4 — Ordered queue | 6w | Order by tier with an aging cap, one business unit at a time. |
| 5 — Interlocks | 8w | Evidence links to 04 EvalForge, 08 OversightOps and 09 LineageLog; handoff to 12 ValueLedger after approval. |

---

## Open questions

1. **Gate authority.** Does the AI governance lead have *blocking* authority on an approval, or only *advisory*? Recommendation: blocking for tier 3 and tier 4, advisory for tier 1 and tier 2, with every override recorded with a named approver.
2. **Who owns the rubric?** The points table is policy. Recommendation: the AI governance lead proposes, the CRO's delegate approves, every change is a new version with an effective date.
3. **Flag resolution.** Should an ambiguous customer-facing answer auto-resolve to yes, as the prototype does, or hold the case until the sponsor answers? Recommendation: auto-resolve for tiering, hold the evidence gate, require the sponsor's confirmation inside a set number of days.
4. **Duplicate handling.** When two linked submissions carry different tiers (4 of 13 linked submissions in the prototype), which one wins? Recommendation: the higher tier, until a reviewer merges them.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Register and decision record:** Postgres. Every recompute writes an append-only tier decision with its inputs, flags and rubric version; no update, no delete.
- **Second sources:** read-only connectors to the data catalog and the vendor registry; the recompute reads the class and the vendor model, never the sponsor's free text beyond the cue check.
- **Evidence:** the checklist is versioned configuration; evidence files live in write-once object storage and the register holds their hashes.
- **Queue:** a priority queue keyed by recomputed tier, then arrival, with an aging cap (design).

**Throughput envelope and latency budget.**
- The synthetic intake rate is 7.5 submissions a week, 375 a year in the model. Compute is not the constraint; reviewer time is.
- Duplicate linking compares every pair: 150 submissions is 11,175 pairs. A register of 10,000 use cases would be about 50 million pairs, so production needs an inverted index on tokens (design), not the all-pairs loop the prototype uses.
- Recompute on submit should answer a sponsor in seconds (design target). The prototype does not measure the latency of a service.

**Failure modes and degradation strategy.**
- Catalog unreachable: use the form's class, flag the case "class unverified", never lower a tier.
- Registry unreachable: same, for the vendor model.
- Checklist configuration missing for a tier: HOLD the approval (fail closed).
- Rubric configuration changed mid-flight: cases keep the version they were decided under; a re-decision is a new record.

**Migration path from current state.**
- If the intake is a spreadsheet: import it as the first register, mark every tier as "declared, unchecked", and run Phase 1 in shadow before any sponsor sees a flag.
- If a model inventory already exists: TierGate reads from it and writes the tier back; it does not create a parallel inventory.

**Org dependencies.**
- The AI governance lead owns the rubric and the checklist. Without that ownership the gate has no authority.
- Catalog stewards and procurement own the second sources. A recompute is only as good as the freshest entry; the catalog freshness check and the known-limit count make that visible.
- The model risk reviewers need capacity for tier 3 and tier 4 depth. 🟡 The model shows tier-depth review hours at 837.0 against 714.0 for declared tiers; if capacity is flat, the queue is the constraint.

---

*This PRD interlocks with [Project 04 (EvalForge)](../04-evalforge-llm-eval-platform/), [Project 08 (OversightOps)](../08-oversightops-hitl-workflow/), [Project 09 (LineageLog)](../09-lineagelog-ai-decision-audit/), and Project 12 (ValueLedger). It is written against the vocabulary of SR 11-7, the NIST AI RMF (Govern and Map) and the EU AI Act risk categories.*
