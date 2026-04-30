# PM Proof — DriftSentinel

The artifacts that show this was shipped, not just sketched.

---

## 1-Page PRD Stub

| Field | Value |
| --- | --- |
| **Product** | DriftSentinel |
| **Owner** | Vijay Saharan, Sr PM |
| **Stage** | Pilot complete (90 days) → MRM committee read |
| **Primary user** | Production ML Operations Lead (line 1) |
| **Secondary user** | Model Validator (line 2) |
| **Tertiary user** | CRO / Head of MRM (line 2 oversight); Business Owner (line 1 accountability) |
| **Problem (one sentence)** | Production ML and GenAI models silently decay because SR 11-7 ongoing monitoring is met today with quarterly Word docs; by the time a business KPI moves, two quarters of value have leaked. |
| **Solution (one sentence)** | A three-loop monitoring layer — Detect, Diagnose, Decide — that sits on the existing model registry and feature store and turns silent decay into a tiered, actionable, auto-bundled MRM event. |
| **North-star metric** | % of Tier-1 production models with drift MTTD ≤ 14 days |
| **Pilot metrics (achieved)** | MTTD 78d → 9d; FP rate 31% → 7%; bundle assembly 3w → 3.2s; coverage 22% → 100% |
| **Cost (pilot)** | ~$280k for 90-day pilot (compute + 1 PM + 0.5 FTE engineer + MRM partner time) |
| **Cost (steady state)** | ~$1.2-2.4M/yr software/compute + 4-6 FTE ops at $50B-asset bank shape |
| **Modeled prevented loss** | $14M/yr at partner-bank shape; ~$45-90M/yr at Tier-1 fleet shape |
| **Risk #1** | Validator rejects auto-bundle. Mitigated by co-design with MRM L2 from week one; bundle is editable, never auto-attested. |
| **Risk #2** | False-positive crisis (already happened in v0.2). Mitigated by Diagnose loop; segment-aware noise floor; 2-of-3 signal rule before paging. |
| **Risk #3** | Vendor model silent updates. Mitigated by snapshot ID as tracked attribute (shipped in v0.5 after the Anthropic Feb 24 incident). |
| **Out of scope** | Model registry replacement, feature store replacement, retraining engine. DriftSentinel reads from existing registries and recommends; never executes for Tier-1. |

---

## RICE-Prioritized Backlog

Scoring: **Reach** (% of Tier-1 fleet affected) × **Impact** (1-3) × **Confidence** (0-1) ÷ **Effort** (engineer-weeks).

| # | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Decide loop with bounded risk envelope | 100 | 3 | 0.9 | 8 | **34** | Shipped v0.4 |
| 2 | Diagnose loop (bisect, slice, lineage) | 100 | 3 | 0.95 | 10 | **29** | Shipped v0.3 |
| 3 | Vendor snapshot pin + diff | 12 | 3 | 0.95 | 3 | **11** | Shipped v0.5 |
| 4 | Auto-bundle MRM evidence pack | 100 | 2 | 0.9 | 6 | **30** | Shipped v0.4 |
| 5 | Segment-aware noise floor | 100 | 2 | 0.85 | 5 | **34** | Shipped v0.3 |
| 6 | GenAI proxy metric portfolio (refusal/groundedness/length/judge drift) | 12 | 3 | 0.8 | 8 | **3.6** | Shipped v0.3 |
| 7 | Auto-rollback authority for Tier-2/3 with audit trail | 65 | 2 | 0.7 | 6 | **15.2** | Queued v0.6 |
| 8 | Expansion to credit-card pricing model fleet (14 models) | 100 | 2 | 0.9 | 4 | **45** | Queued v0.7 |
| 9 | GRC tool integration (Archer / ServiceNow GRC) | 100 | 2 | 0.85 | 12 | **14.2** | Queued v0.8 |
| 10 | MRM L2 sign-off on auto-bundle template | 100 | 3 | 0.7 | 4 | **52.5** | In flight |
| 11 | Multi-region instance for EU GDPR | 100 | 2 | 0.6 | 16 | **7.5** | v1.0 |
| 12 | India RBI data localization instance | 30 | 2 | 0.6 | 16 | **2.3** | v1.1 |
| 13 | LLM-as-judge cross-vendor reliability check | 12 | 2 | 0.5 | 4 | **3** | Investigating |
| 14 | Federated drift across multiple bank entities | 100 | 1 | 0.3 | 24 | **1.25** | Parking lot |

**Top of queue right now:** #10 (MRM L2 sign-off) and #8 (credit-card fleet expansion). #10 is a political dependency, not an engineering one — can't ship steady-state without it.

---

## Validator Interview Quotes

Synthesis from 12 conversations with line-2 validators across the 90-day pilot. Quotes anonymized but representative.

> *"The bundle is the difference. I used to spend Monday and Tuesday pulling PSI plots and lineage screenshots into a Word doc. Now I'm spending those days on actual judgment calls."* — Senior Validator, Credit Risk

> *"I muted the Slack channel in week two of v0.2. The diagnosis layer brought me back. When the alert says 'subprime slice, exogenous macro, recommend SHADOW' I can act. When it says 'PSI=0.42 on feature_dti' I can't."* — Lead Validator, Fraud

> *"The Anthropic snapshot diff is the one I didn't know I needed. We had no signal at all on GenAI before. Now we have one within a day."* — MRM Lead, GenAI working group

> *"I want auto-rollback for the Tier-2/3 models. The Tier-1 governance is right — never auto-execute on consumer credit decisions. But on Tier-3 batch back-office models, the round trip is silly."* — Head of MRM Operations

> *"This is the first time I've seen a PM actually understand what we do. Most product people show up with a dashboard and ask us to use it. You showed up with the deficiency taxonomy first."* — Lead Validator, Credit Risk

The last quote is the one I think about most. It's why the v0.0 taxonomy work paid off.

---

## Stakeholder Map

| Stakeholder | Role | Influence | Stance | Cadence |
| --- | --- | --- | --- | --- |
| Head of MRM | L2 owner | High | Champion | Weekly 1:1 |
| CRO | Executive sponsor | High | Champion (post-OCC finding) | Bi-weekly steering |
| ML Ops Lead | L1 user | High | Champion | Weekly working session |
| Lead Validators (3) | Daily users | Medium | Mixed v0.2 → Champion v0.3+ | Co-design sessions |
| InfoSec / Cloud Sec | Gatekeeper | Medium | Cautious — wants on-prem option for GenAI | Quarterly review |
| Internal Audit (L3) | Reviewer | Medium | Neutral, will review at v1.0 | Annual |
| Business Owner (Credit) | Indirect user | Medium | Champion (modeled $14M/yr) | Monthly metrics review |
| Business Owner (Fraud) | Indirect user | Medium | Wait-and-see | Quarterly |
| OCC examiner | Regulator | High (existential) | Will see at exam | Annual exam cycle |
| Existing chatbot vendor | External | Low | Hostile (we document their failure rate) | Contract review |

---

## What I'd Tell My Successor PM

1. **Diagnosis is the product, not detection.** Anyone can compute PSI. The hard part is "which segment, which upstream cause, what action" in one working day. If you build detection without diagnosis, you'll be dead by week three of the pilot.

2. **The taxonomy work is the unsexy part. Do it anyway.** The v0.0 deficiency taxonomy was the highest-leverage two weeks of the project. Everything downstream rests on it.

3. **Co-design with line 2 from week one.** I made the mistake of designing the bundle template alone. The first version was rejected. The second version, co-authored with the lead validator, was attested in one round.

4. **The vendor snapshot pin is unsexy and saves the GenAI portfolio.** Anthropic and Azure OpenAI silently update. Without the pin, you have no signal on GenAI drift. With the pin, the version diff is itself the alert.

5. **Don't pick a fight with the existing model registry.** Read from MLflow / SageMaker; don't replace. Embed in the existing MRM workbench; don't build a parallel UI. Every internal-build I've seen die has died on this one.

6. **The MRM committee will tell you when to ship Auto-Rollback authority for Tier-1.** It will be never. Stop asking. For Tier-2/3 with audit trail, push for it.
