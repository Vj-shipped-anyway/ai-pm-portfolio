# PRD · OversightOps — Calibrated HITL Workflow Designer

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype, designed for engagement
**Date:** 2026-Q2

> **Framing:** This PRD is the product I would bring to a Tier-1 retail bank's Head of Compliance, MRM lead, and Reviewer Operations director in the seat. It is not a record of a PRD landed at a named bank. The six-deficiency taxonomy, the routing architecture, and the rollout plan are mine; the production validation is what the next role does.

---

## 1-page PRD stub

| Field | Value |
| --- | --- |
| **Product** | OversightOps — calibrated, role-aware HITL workflow designer that replaces single-queue rubber-stamp review with difficulty-stratified routing, a rubber-stamp blocker, calibration drift detection, and a ground-truth feedback loop. |
| **Owner** | Vijay Saharan, Sr PM (BFSI AI Platform). |
| **Stage** | Portfolio prototype, designed for engagement. Synthetic data, no production deployment. |
| **Users** | Primary: Head of Compliance, Reviewer Operations director. Secondary: MRM lead, Internal Audit (L3), CRO. Tertiary: Line-1 model owners, regulator-facing teams (OCC liaison, EU AI Act competent-authority liaison). |
| **Problem** | Every Tier-1 bank's regulated AI workflow with a HITL step (KYC, fraud step-up, dispute, credit waterfall, claims SIU) routes to a flat reviewer queue with no SLA on review depth, no calibration measurement, and no signal back to the reviewer when outcomes contradict their decisions. 🟡 ~94% of Tier-1 KYC reviews complete in under 10 seconds. The HITL exists on paper to satisfy [EU AI Act Article 14](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng) and SR 11-7. It does not produce oversight. |
| **Solution** | Six routing primitives composed in one workflow: (1) difficulty-stratified routing by AI confidence + customer tier + country risk, (2) rubber-stamp blocker that rejects sub-floor reviews on Tier-1 cases, (3) calibration drift detector that flags reviewer outliers vs cohort, (4) escalation path for hard cases, (5) tier-specific SLA timers (8m / 3m / 1m), (6) ground-truth backfill from downstream signals with a weekly reviewer calibration packet. |
| **North-star metric** | Tier-1 rubber-stamp rate — % of Tier-1 review decisions completed below the procedure-manual time-on-task floor. Target: ≤ 4%. |
| **Modeled metrics (12-month horizon)** | 🟡 Tier-1 rubber-stamp rate: **94% → 4%** (assumes the published BFSI baseline and the OversightOps blocker engaged on Tier-1 queues). 🟡 Reviewer-vs-ground-truth divergence: **38% → 8%** (assumes the published Tier-1 6-12-month tail and the calibration packet engaged weekly). 🔴 Review SLA on Tier-1 KYC: **9 seconds → 8 minutes** (designed against the bank's procedure manual; not yet tested in production). |
| **Modeled cost** | 🔴 ~$380k for a 90-day engagement in a real deployment (compute on existing BPM infra + 1 PM + 1.5 FTE engineers + 0.5 FTE compliance partner + reviewer-ops co-design time) — designed, not executed. |
| **Risk #1** | Reviewer operations pushback — leads will hate the blocker because their queue depth goes up. Solution: pair the blocker with a workforce-planning model that quantifies headcount needed for true 8-minute SLA on Tier-1; bring it to Reviewer Ops as a staffing case, not a discipline case. |
| **Risk #2** | False-positive rubber-stamp blocks on genuinely easy cases. Solution: tier-specific floor (60s on private banking, 30s on SME, 8s on retail); a high-confidence-AI + easy-difficulty + low-country-risk case is allowed to clear at the retail-tier floor. |
| **Risk #3** | Compliance pushback on the calibration packet — reviewers may push back on per-reviewer drift visibility. Solution: route the calibration packet through Reviewer Ops, not to the reviewer's manager directly; treat it as a training signal, not a disciplinary one. |
| **Out of scope** | (1) Replacing the bank's BPM platform (Pega / Appian / ServiceNow) — we integrate, we do not replace. (2) Reviewer staffing decisions — we provide signal, not headcount. (3) Real-time decision blocking on the AI path — we are off the AI's hot path. (4) Customer-facing surfaces — internal compliance tool only. (5) Building a new IdP — we integrate with the bank's existing Okta / Entra ID / Ping. |

---

## 2. Stakeholder map

| Role | Line | Stake | What they want from OversightOps |
| --- | --- | --- | --- |
| **Head of Compliance** | L2 | Owns regulator-facing posture on AI oversight | Tier-1 rubber-stamp rate dashboard; the calibration packet as the recurring artifact for board-level oversight reporting. |
| **Reviewer Operations director** | L1 ops | Owns the reviewer queues, headcount, and SLA | Difficulty-stratified routing that load-balances appropriately across the roster; staffing-model signal for hiring planning. |
| **MRM lead** | L2 | Owns model-risk governance | Per-reviewer override rate vs cohort drift; integration with the bank's MRM workbench (Archer / ServiceNow GRC / MetricStream). |
| **CRO** | L2 oversight | Owns model risk at the portfolio level | Fleet-level HITL health metric; aging-cases-without-resolution report. |
| **Internal Audit (L3)** | L3 | Owns the bank's effective-challenge function | Read-only access to immutable oversight records; ability to sample-pull on any case and see the full routing rationale. |
| **Regulator-facing teams (OCC liaison, EU AI Act competent-authority liaison)** | L2 | Owns the bank's regulator-facing relationship | Pre-formatted oversight evidence for any specific HITL workflow; audit trail showing the calibration packet cycle. |
| **Line-1 Model Owners** | L1 | Owns the deployed AI model | Reviewer-vs-AI agreement rate as a model-quality signal; ground-truth backfill as a retraining signal. |
| **Platform Engineering** | Platform | Owns the AI platform substrate | Routing layer is platform-owned, integrates with the existing BPM, no new workflow vendor introduced. |
| **InfoSec (CISO)** | L2 | Owns the bank's data-handling posture | All routing runs inside the bank's VPC; immutable decision log; field-level encryption on `customer_id_hash`; SR 11-7 + SOC 2 + GLBA alignment. |
| **Legal (E&G)** | L2 | Owns disclosure and consent posture | Oversight records have legal-hold flag; cannot be deleted while a matter is open; GDPR right-to-erasure cascades to hash deletion. |

---

## 3. RICE-prioritized backlog

> RICE = (Reach × Impact × Confidence) ÷ Effort.
> Status: "Sequenced for v0.x" = committed to a release. "Queued" = will be sequenced after v0.5.

| # | Item | Reach | Impact | Confidence | Effort | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | **Difficulty router (v0.1)** — case + AI confidence + customer tier + country risk → queue tier. | 4.5M | 3 | 0.9 | 8 | 1.52 | Sequenced for v0.1 |
| 02 | **Tier-stratified queues** — Postgres-backed queue per tier; reviewer claim-based concurrency control. | 4.5M | 3 | 0.9 | 13 | 0.93 | Sequenced for v0.1 |
| 03 | **Rubber-stamp blocker (v0.1)** — tier-specific time-on-task floor; sub-floor reviews rejected; case re-queued to a higher tier. | 4.5M | 3 | 0.85 | 8 | 1.43 | Sequenced for v0.1 |
| 04 | **Streamlit prototype** — single-case drill-down, executive verdict card, six-deficiency display. | 1k | 2 | 1.0 | 5 | 0.0004 | Sequenced for v0.1 (this repo) |
| 05 | **Tier SLA timer with PagerDuty escalation** — 8m / 3m / 1m timers per tier; PagerDuty breach alerts. | 4.5M | 3 | 0.8 | 13 | 0.83 | Sequenced for v0.2 |
| 06 | **Rubric attestation UI** — reviewer must check tier-specific rubric items; checkbox state immutable in the oversight log. | 4.5M | 2 | 0.8 | 8 | 0.90 | Sequenced for v0.2 |
| 07 | **Calibration drift detector** — weekly per-reviewer override-rate vs cohort; flag at ≥ 1.5 sigma. | 4.5M | 3 | 0.75 | 13 | 0.78 | Sequenced for v0.3 |
| 08 | **Reviewer calibration packet** — auto-emailed weekly to each reviewer with their drift, top contradicted decisions, recommended training modules. | 4.5M | 2 | 0.7 | 8 | 0.79 | Sequenced for v0.3 |
| 09 | **Ground-truth backfill ingester** — daily ETL from loss-event lake, SAR system, OFAC list, CFPB system, charge-off log; bind by `(customer_id_hash, case_ingested_at)`. | 4.5M | 3 | 0.7 | 21 | 0.45 | Sequenced for v0.4 |
| 10 | **Escalation path config** — per-use-case archetype escalation rules (KYC, dispute, fraud step-up, claims SIU, credit waterfall). | 4.5M | 2 | 0.75 | 13 | 0.52 | Sequenced for v0.4 |
| 11 | **MRM workbench integration** — push oversight record IDs to Archer / ServiceNow GRC / MetricStream; bidirectional sync on attestation status. | 4.5M | 2 | 0.6 | 13 | 0.42 | Sequenced for v0.5 |
| 12 | **Pega / Appian / ServiceNow adapter** — embedded reviewer-workbench panel; case claim and decision write back to the BPM as the system of record. | 4.5M | 2 | 0.6 | 21 | 0.26 | Queued (post v0.5) |

---

## 4. Why now

- **EU AI Act Article 14** (human oversight) is in effect. High-risk AI systems (which includes BFSI credit, KYC, claims) must be designed so they can be effectively overseen by natural persons. Calibrated review — not the rubber-stamp queue — is the implementation surface.
- **OCC supervisory letters** are shifting toward asking *how* the human oversight is calibrated, not just *whether* it exists. The published shape of recent letters increasingly asks for reviewer-quality measurement: override rates by reviewer, time-on-task distributions, ground-truth feedback evidence.
- **NIST AI RMF 1.0** specifies the HITL section as a measurement requirement, not a checkbox.
- **Anthropic's Constitutional AI** work and OpenAI's usage policy both name human oversight as the safety lever for high-stakes AI decisions — but neither names the calibration mechanism. OversightOps is the calibration mechanism.
- **The substrate is finally there.** BPM platforms (Pega, Appian, ServiceNow Workflow) are productized at every Tier-1 bank, and ADK confirmation primitives are published. The calibration layer is the missing piece.

## 5. Goals (12-month horizon)

| Goal | Metric | Target | Tier |
| --- | --- | --- | --- |
| Reduce Tier-1 rubber-stamp rate | % of Tier-1 review decisions completed below the procedure-manual floor | 94% → 4% | 🟡 |
| Reduce reviewer-vs-ground-truth divergence | % of reviewer decisions contradicted by downstream signals within 6-12 months | 38% → 8% | 🟡 |
| Reduce review SLA breaches on Tier-1 | % of Tier-1 KYC reviews completed below the 8-minute SLA | 100% → < 5% | 🔴 |
| Detect calibration drift | # of reviewer outliers flagged at ≥ 1.5 sigma off cohort, weekly | 0 → cohort-appropriate | 🟢 |

## 6. Non-goals

- Not a BPM platform — we integrate with Pega / Appian / ServiceNow as the system of record.
- Not a reviewer-staffing model — we provide the signal; HR / Reviewer Ops decides headcount.
- Not in the AI request path — we sit between the AI's "flag for review" event and the reviewer-workbench claim event.
- Not a customer-facing surface — internal-only.
- Not a fourth line of defense — line-2 tooling that line-3 audits.

## 7. User stories

- **As Head of Compliance**, I want a Tier-1 rubber-stamp rate dashboard so I can report calibrated oversight to the board, not theatrical oversight.
- **As Reviewer Operations director**, I want difficulty-stratified routing so my leads are working on the cases that need them, not picking up retail-tier auto-approvals.
- **As MRM lead**, I want per-reviewer calibration drift so I can name the reviewers whose override rate sits 2 sigma off cohort and route them to training, not to the audit committee.
- **As Internal Audit (L3)**, I want read-only access to the immutable oversight log so I can sample-pull any case and see the full routing rationale and SLA evidence without filing a data request.
- **As a Regulator-facing team member**, I want the calibration packet cycle visible end-to-end so when the OCC asks "how do you know your HITL is real?" the answer is the cycle itself.

## 8. Solution detail — the six-deficiency composition

The product is a routing layer. Each deficiency maps to a specific primitive and a specific composition action.

| # | Deficiency | Routing primitive | Composition action |
| --- | --- | --- | --- |
| 1 | No difficulty stratification | `difficulty_route(case)` | Compose AI confidence + customer tier + country risk + difficulty score → tier-stratified queue (lead / senior / junior). |
| 2 | No calibration drift detection | Weekly per-reviewer aggregation | Compare each reviewer's override rate to cohort mean; flag at ≥ 1.5 sigma; emit calibration packet to Reviewer Ops. |
| 3 | No rubber-stamp detection | `rubber_stamp_blocker(case, time_to_decide)` | Tier-specific floor (60s on PB, 30s on SME, 8s on retail); sub-floor reviews rejected; case re-queued one tier up. |
| 4 | No escalation path | Per-use-case archetype rules | Configurable rules (e.g., difficulty=5 OR country_tier≥3 → lead queue regardless of base routing). |
| 5 | No time-on-task SLA | Temporal timer per tier | Engage tier-specific timer (8m / 3m / 1m) on case claim; PagerDuty breach alert on overflow. |
| 6 | No ground-truth feedback loop | Daily ETL from downstream systems | Match downstream signals by `(customer_id_hash, case_ingested_at + 2-180d window)`; bind contradicted decisions to the original reviewer; emit calibration packet. |

## 9. Rollout

| Phase | Duration | Scope |
| --- | --- | --- |
| 0 — Foundation | 6w | Postgres `oversight_decisions` schema; difficulty router; tier-stratified queues; 1 pilot workflow (`kyc_review_v4`). |
| 1 — Rubber-stamp blocker | 8w | Tier-specific floor enforcement; case re-queue logic; reviewer-ops dashboards for queue depth by tier. |
| 2 — SLA + rubric | 8w | Temporal SLA timer with PagerDuty integration; rubric attestation UI embedded in the BPM workbench. |
| 3 — Calibration drift | 8w | Weekly per-reviewer drift detector; calibration packet generator; Reviewer Ops escalation workflow. |
| 4 — Ground-truth backfill | 12w | ETL from loss-event lake + SAR + OFAC + CFPB + charge-off log; binding by customer + time window; reviewer feedback loop closed. |
| 5 — MRM integration + multi-workflow | 12w | Archer / ServiceNow GRC / MetricStream integration; rollout to dispute, fraud step-up, claims SIU, credit waterfall workflows. |
| 6 — Multi-region | 12w | EU instance (Frankfurt) + India instance (Mumbai); independent KMS rings. |

## 10. Open questions

1. **Floor calibration per tier.** Is 60 seconds the right floor for private-banking KYC, or should it be the bank's procedure manual's 480-second SLA target? Default: floor at 60s (the "no real adjudication is plausible below this" threshold); SLA target at 480s (the procedure manual line); both tracked.
2. **Calibration packet recipient.** Reviewer's manager or Reviewer Ops? Default: Reviewer Ops first (training signal); manager only if a reviewer crosses 2 sigma for 4 consecutive weeks.
3. **Escalation queue depth.** What happens when the LEAD queue gets backlogged because the blocker pushes Tier-1 cases up? Default: queue-depth-aware staffing dashboard; alert at p95 queue-age 30m on LEAD tier.
4. **BPM integration primacy.** Pega first, Appian second, ServiceNow third — depends on the bank's existing license. Default: build the integration as a generic adapter so the second vendor is an API-config change.

## 11. Build & scale notes

**Reference architecture.** Routing runs on Cloud Run (stateless) backed by Pub/Sub fan-in from the AI model's "flag for review" event. Postgres (Cloud SQL with HA + read replicas) holds the immutable `oversight_decisions` table; Temporal holds the SLA timers; ClickHouse holds the high-cardinality reviewer-throughput stream; GCS Object Lock + cross-region replication holds the WORM evidence bundles for the 7-year audit archive.

**Throughput envelope.** ~4,500 cases/week on the headline KYC workflow = ~0.7 cases/second average, ~5 cases/second peak. The composition is dominated by the routing decision (sub-millisecond on the prototype) and the SLA timer write (Temporal, ~10ms). The constraint is the reviewer-workbench UI roundtrip, not the OversightOps composition itself.

**Failure modes.**
- *AI's "flag for review" event lost.* Daily reconciliation job compares cases-flagged-by-AI vs cases-in-OversightOps-queues; backfill on detection.
- *Temporal SLA timer fires after reviewer has claimed but not finished.* Grace period (90s) before PagerDuty alert; reviewer can extend timer with rubric attestation.
- *Ground-truth ETL stale.* Calibration packet falls back to the prior week's drift profile; flagged in the packet as "stale ground truth."

**Migration path.** If the bank is already running Pega / Appian / ServiceNow with HITL queues: OversightOps inserts itself between the AI model and the existing queue. The BPM remains the system of record. If the bank is on a Word-doc quarterly review cycle: 12-week Phase 0 to wire up the difficulty router first; calibrated review becomes the side-effect over a 12-month transition.

**Org dependencies.** Reviewer Operations co-designs the difficulty-router thresholds and the SLA floors (they own the queues and the staffing). Internal Audit (L3) signs off on the immutability properties of the oversight log. Head of Compliance signs the regulator-facing narrative.

---

*This PRD interlocks with [LineageLog](../09-lineagelog-ai-decision-audit/) (oversight evidence ↔ decision lineage), [AgentWatch](../05-agentwatch-agent-observability/) (HITL gate as agent runtime primitive), and [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) (reviewer-vs-AI agreement as a model-quality signal).*
