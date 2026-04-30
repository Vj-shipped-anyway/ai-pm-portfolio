# PM Proof — DriftSentinel

The artifacts that show how I'd run this product if I owned it: the 1-page PRD I'd bring to a steering read, the RICE-prioritized backlog I'd run, and the six product principles the work surfaces.

> Framing: this is a portfolio prototype. The deficiency taxonomy, the architecture, and the backlog below are mine. The pilot, the validator co-design, and the MRM committee read are the work the next role does.

---

## 1-Page PRD Stub

| Field | Value |
| --- | --- |
| **Product** | DriftSentinel |
| **Owner** | Vijay Saharan, Sr PM |
| **Stage** | Portfolio prototype with a 90-day modeled pilot design; intended to land at an MRM committee read in a real engagement |
| **Primary user** | Production ML Operations Lead (line 1) |
| **Secondary user** | Model Validator (line 2) |
| **Tertiary user** | CRO / Head of MRM (line 2 oversight); Business Owner (line 1 accountability) |
| **Problem (one sentence)** | Production ML and GenAI models silently decay because SR 11-7 ongoing monitoring is met today with quarterly Word docs; by the time a business KPI moves, two quarters of value have leaked. |
| **Solution (one sentence)** | A three-loop monitoring layer — Detect, Diagnose, Decide — that sits on the existing model registry and feature store and turns silent decay into a tiered, actionable, auto-bundled MRM event. |
| **North-star metric** | % of Tier-1 production models with drift MTTD ≤ 14 days |
| **Modeled pilot targets** | MTTD 78d → 9d; FP rate 31% → 7%; bundle assembly 3w → 3.2s; coverage 22% → 100% |
| **Modeled pilot cost** | ~$280k for a 90-day pilot (compute + 1 PM + 0.5 FTE engineer + line-2 partner time) |
| **Modeled steady-state cost** | ~$1.2-2.4M/yr software/compute + 4-6 FTE ops at $50B-asset bank shape |
| **Modeled prevented loss** | $14M/yr at $50B-asset shape; ~$45-90M/yr at Tier-1 fleet shape |
| **Risk #1** | Validator rejects auto-bundle. Mitigation: co-design with line-2 from week one; bundle is editable, never auto-attested. |
| **Risk #2** | False-positive crisis. Mitigation: Diagnose loop; segment-aware noise floor; 2-of-3 signal rule before paging. |
| **Risk #3** | Vendor model silent updates. Mitigation: snapshot ID as a tracked attribute (the Anthropic Feb-24 minor update is the public reference incident this design is calibrated against). |
| **Out of scope** | Model registry replacement, feature store replacement, retraining engine. DriftSentinel reads from existing registries and recommends; never executes for Tier-1. |

---

## RICE-Prioritized Backlog

Scoring: **Reach** (% of Tier-1 fleet affected) × **Impact** (1-3) × **Confidence** (0-1) ÷ **Effort** (engineer-weeks).

Status reflects the **design sequence** I'd run if I owned this product on day one — not work shipped at a named bank.

| # | Item | R | I | C | E | RICE | Sequence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Decide loop with bounded risk envelope | 100 | 3 | 0.9 | 8 | **34** | Sequenced for v0.4 |
| 2 | Diagnose loop (bisect, slice, lineage) | 100 | 3 | 0.95 | 10 | **29** | Sequenced for v0.3 |
| 3 | Vendor snapshot pin + diff | 12 | 3 | 0.95 | 3 | **11** | Sequenced for v0.5 |
| 4 | Auto-bundle MRM evidence pack | 100 | 2 | 0.9 | 6 | **30** | Sequenced for v0.4 |
| 5 | Segment-aware noise floor | 100 | 2 | 0.85 | 5 | **34** | Sequenced for v0.3 |
| 6 | GenAI proxy metric portfolio (refusal/groundedness/length/judge drift) | 12 | 3 | 0.8 | 8 | **3.6** | Sequenced for v0.3 |
| 7 | Auto-rollback authority for Tier-2/3 with audit trail | 65 | 2 | 0.7 | 6 | **15.2** | Queued v0.6 |
| 8 | Expansion to credit-card pricing model fleet (14 models) | 100 | 2 | 0.9 | 4 | **45** | Queued v0.7 |
| 9 | GRC tool integration (Archer / ServiceNow GRC) | 100 | 2 | 0.85 | 12 | **14.2** | Queued v0.8 |
| 10 | Line-2 sign-off on auto-bundle template | 100 | 3 | 0.7 | 4 | **52.5** | Top of queue (political dep) |
| 11 | Multi-region instance for EU GDPR | 100 | 2 | 0.6 | 16 | **7.5** | v1.0 |
| 12 | India RBI data localization instance | 30 | 2 | 0.6 | 16 | **2.3** | v1.1 |
| 13 | LLM-as-judge cross-vendor reliability check | 12 | 2 | 0.5 | 4 | **3** | Investigating |
| 14 | Federated drift across multiple bank entities | 100 | 1 | 0.3 | 24 | **1.25** | Parking lot |

**Top of queue on day one:** #10 (line-2 sign-off on the bundle template) and #8 (credit-card fleet expansion). #10 is a political dependency, not an engineering one — the steady-state shape doesn't ship without it.

---

## Stakeholder Map

If I owned this product, this is the stakeholder map I'd run. Influence and stance are what I'd expect at a typical Tier-1 BFSI shop based on the published shape of the role; cadence is what I'd push to land in the first 30 days.

| Stakeholder | Role | Influence | Expected stance | What I'd push for |
| --- | --- | --- | --- | --- |
| Head of MRM | L2 owner | High | Champion (the product gives them validator capacity back) | Embedded co-design from week one; co-author the bundle template |
| CRO | Executive sponsor | High | Champion if there's an active OCC / FRB lens on ongoing monitoring | One-page exam-readiness view as the steering artifact |
| ML Ops Lead | L1 user | High | Champion (this is the screen they want) | Daily working session through the Detect/Diagnose pilot |
| Lead Validators (3) | Daily users | Medium | Mixed early; converts as Diagnose loop proves out | Co-design the diagnosis rubric, not just the UI |
| InfoSec / Cloud Sec | Gatekeeper | Medium | Cautious — wants on-prem option for GenAI | Architecture review at v0.1 and again pre-pilot |
| Internal Audit (L3) | Reviewer | Medium | Neutral until v1.0 | Read-only access from day one; no surprises at the v1 review |
| Business Owner (Credit) | Indirect user | Medium | Champion once the modeled $14M/yr lands | Monthly metrics review in their cadence, not a new one |
| Business Owner (Fraud) | Indirect user | Medium | Wait-and-see | Quarterly read until the proxy-metric portfolio earns credibility |
| OCC / FRB examiner | Regulator | High (existential) | Will see at exam — the design target | Audit-pack export builds in <12 minutes per decision |
| Existing chatbot vendor | External | Low | Hostile (the product documents their failure rate) | Contract review at the next cycle |

The map is structural, not relational — it's the line-1 / line-2 / line-3 / regulator shape that any drift product has to land into. I'd build the actual relationships in the seat.

---

## Six Product Principles I'd Take Into the Role

These are what the design surfaces — the lessons I'd carry from the prototype work into a real engagement on day one.

1. **Diagnosis is the product, not detection.** Anyone can compute PSI. The hard part is "which segment, which upstream cause, what action" in one working day. A detect-only product dies in week three of its first pilot.

2. **The taxonomy work is the unsexy part. Do it anyway.** The deficiency taxonomy is the highest-leverage two weeks of the project. Everything downstream — alert thresholds, bundle template, recommendation logic — rests on it.

3. **Co-design with line 2 from week one.** A bundle template designed alone gets rejected. A bundle template co-authored with the lead validator gets attested in one round. The political dependency is the engineering dependency.

4. **The vendor snapshot pin is unsexy and saves the GenAI portfolio.** Anthropic and Azure OpenAI silently update. Without the pin, you have no signal on GenAI drift. With the pin, the version diff is itself the alert. The Anthropic Feb-24 minor update is the public reference for why this matters.

5. **Don't pick a fight with the existing model registry.** Read from MLflow / SageMaker; don't replace. Embed in the existing MRM workbench; don't build a parallel UI. The internal-build graveyard is full of products that died on this one.

6. **Auto-rollback authority for Tier-1 will be never; for Tier-2/3 with audit trail, it's the right call.** The committee math here is calibrated against SR 11-7 expectations on consumer credit decisions. Stop asking for Tier-1; push hard on Tier-2/3.
