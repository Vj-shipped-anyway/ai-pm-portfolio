# PRD · VendorLens — AI Vendor Due Diligence Scored on Evidence, Concentration and Exit

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a third-party-risk read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to a third-party risk review in the seat. It is not a record of a PRD landed at a named bank. The evidence rule, the scoring structure, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. RICE scores and rollout durations below are planning estimates (🔴), not measurements.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | VendorLens — AI vendor due diligence scored on evidence, concentration and exit |
| **Owner** | Third-party risk lead (line-1), with the business owner of each AI service as co-owner of the decision |
| **Stage** | Portfolio prototype; third-party-risk read |
| **Primary user** | Third-party risk manager, who decides which AI vendors get a deep review |
| **Secondary users** | Business owner of the AI service; procurement and legal (contract terms); model risk reviewer (line-2); information security |
| **Problem** | A bank buys AI from dozens of vendors and assesses them with a questionnaire the vendor fills in. It rewards over-claiming, it cannot see that many vendors run on the same upstream model provider, and it never asks how the bank would leave. In the synthetic data, 🟢 29 of 40 vendors pass, including 6 of the 10 that are truly high risk, and 🟢 27 of those 29 passes have a missing, stale or out-of-scope document. |
| **Solution** | A scoring layer on the vendor record: an evidence-adjusted control score (each answer weighed against a document or the contract), a concentration flag on the upstream model provider, an exit-readiness score, a risk class (HIGH, MEDIUM, LOW) weighted by criticality and data access, and a review cadence by tier. Every score carries its reasons. |
| **North-star metric** | Share of in-scope AI vendors with an evidence-adjusted score and a review date inside their tier cadence. Target 🔴 100% of in-scope vendors. Today in this model: 0%, nothing is scored. |
| **Measured metrics (synthetic)** | 🟢 5 of 8 vendors rated HIGH are truly high risk (62.5%), against 4 of 11 for a failed questionnaire (36.4%); 🟢 5 of 10 truly high-risk vendors found, against 4 of 10; 🟢 at the same queue size of 11, 6 of 10 against 4; 🟢 MP-1 flagged at 42.9% of 56 critical use cases. |
| **Modeled metrics** | 🟡 26 of 40 vendors would take longer to exit than the allowed window (8 of 10 critical), assuming 180 days with no exit clause and 1.5 times the stated days for an untested plan. 🟡 Utility (0.125 − 0.100) × 120 = 3.0 more high-risk vendors found, assuming 120 vendors in a bank's AI estate. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on document volume and reviewer time and has not been sized. |
| **Risk #1** | Vendors do not supply documents, so the score punishes everyone. Mitigation: a missing document earns a fraction of a yes, not zero; the score names the document that would move it; start in shadow mode and show vendors what they would need. |
| **Risk #2** | The weights are treated as truth. 🟢 Moving the concentration line from 40% to 45% takes HIGH flags from 8 vendors to 3. Mitigation: weights live in a policy file owned by line-2, every score shows its parts, and the sensitivity table ships with the score. |
| **Risk #3** | A valid-looking document says nothing good, or is not real. Evidence authenticity is not verified: 🟢 V-32 and V-19 are truly high risk, pass the questionnaire and are rated LOW. Mitigation: a named reader records having read each document; the score says "a document is on file", never "the control works". |
| **Out of scope** | The content of the questionnaire; contract negotiation; vendor financial health; spend per vendor (InferenceLens, 07); the model-swap decision (SwapBrief, 13); runtime monitoring of the vendor's output. |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is vendors or roles, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Evidence-adjusted control score** (answer weighed against a document or the contract) | 40 vendors | 3 | 0.9 | 3 | 36.0 | Built in prototype; v0.1 |
| 2 | **Provider disclosure request** (a questionnaire item and a contract term naming the upstream provider) | 40 vendors | 3 | 0.6 | 2 | 36.0 | Sequenced for v0.2 |
| 3 | **Risk class with reasons** (HIGH, MEDIUM, LOW weighted by tier and data access) | 40 vendors | 3 | 0.8 | 3 | 32.0 | Built in prototype; v0.1 |
| 4 | **Exit-readiness score** (clause, test, modeled time to exit against the allowed window) | 40 vendors | 2 | 0.8 | 2 | 32.0 | Built in prototype; v0.1 |
| 5 | **Review cadence by tier** (HIGH reviewed twice as often) | 40 vendors | 2 | 0.8 | 2 | 32.0 | Built in prototype; v0.2 |
| 6 | **Concentration map and flag** (share of critical use cases by provider, HHI) | 40 vendors | 3 | 0.7 | 3 | 28.0 | Built in prototype; v0.1 |
| 7 | **Vendor register ingest and evidence store** (type, issue date, scope, named reader) | 40 vendors | 3 | 0.9 | 4 | 27.0 | Sequenced for v0.1 |
| 8 | **Contract field extraction** (audit right, notice days, exit clause) | 40 vendors | 2 | 0.7 | 4 | 14.0 | Sequenced for v0.2 |
| 9 | **Evidence request workflow** with expiry reminders | 40 vendors | 2 | 0.7 | 4 | 14.0 | Sequenced for v0.3 |
| 10 | **Model-swap trigger** (SwapBrief interlock: a swap reopens the concentration view) | 40 vendors | 2 | 0.5 | 4 | 10.0 | Queued |
| 11 | **Spend-per-vendor join** (InferenceLens interlock) | 40 vendors | 1 | 0.6 | 3 | 8.0 | Queued |
| 12 | **Exit-test tracking** (KillSwitch interlock) | 10 critical vendors | 3 | 0.5 | 3 | 5.0 | Sequenced for v0.3 |
| 13 | **Decision record export** to the third-party risk system | 3 roles | 2 | 0.9 | 2 | 2.7 | Sequenced for v0.3 |
| 14 | **Calibration of weights and lines** against the bank's own review outcomes | 3 roles | 3 | 0.6 | 5 | 1.1 | Sequenced for v0.3 |

---

## Stakeholder map

| Stakeholder | Role | What they want from VendorLens | What they fear |
| --- | --- | --- | --- |
| **Third-party risk manager** (line-1) | Owner | A short queue with the reason for each place in it, and the document or term that would move a vendor out of it. | A score they cannot defend to the vendor; a queue that is too long to work. |
| **Business owner of the AI service** | Co-owner | To know before renewal whether the vendor they depend on shares a provider with ten others, and what leaving would take. | A HIGH rating that stalls a launch with no path to MEDIUM. |
| **Procurement and legal** | Consulted | Clear contract asks: audit right, notice of model changes, an exit clause, disclosure of the upstream provider. | New terms that vendors refuse and that delay every renewal. |
| **Model risk reviewer** (line-2) | Auditor and policy owner | A record of what backed each answer, who read each document and which weights were in force on the day. | A heuristic presented as a guarantee; weights changed without a trail. |
| **Information security** | Consulted | Evidence from independent reports and tests, current and in scope. | Vendor documents uploaded without scanning; reports that cover another product. |
| **Vendors** | Subject | A clear list of what to supply and why. | Being scored on documents they cannot share. |
| **Internal audit** | Consulted | A decision record that shows reasons, dates and approvers. | A parallel record that disagrees with the third-party risk system. |

---

## User stories (top 4)

1. **As a third-party risk manager**, I want every AI vendor scored on what a document or the contract backs, so I can see which passes rest on a claim nobody checked.
2. **As a business owner**, I want to see which upstream model provider my vendor runs on and how much of the bank's critical use depends on it, so a renewal decision includes the fourth party.
3. **As a model risk reviewer**, I want each score to show its parts and the weights in force, so ongoing monitoring, a theme in SR 26-2 and SR 23-4, is documented per vendor and not only at onboarding.
4. **As procurement**, I want a list of contract terms ranked by how much they would move the score, so negotiation time goes where it changes the risk.

---

## KPIs

**North star:** share of in-scope AI vendors with an evidence-adjusted score and a review date inside their tier cadence. Target 🔴 100%.

**Inputs (leading):**
- Vendors with a named upstream provider on file (target: every in-scope vendor). Prototype: 🟢 5 of 40 do not disclose it.
- Valid documents per vendor, by type (target: all three types valid and in scope for every critical vendor). Prototype: 🟢 36 of the passing vendors' 87 vendor-document slots are valid.
- Vendors with a tested exit (target: every critical vendor). Prototype: 🟢 33 of 40 have no tested exit.
- Reader attestation rate on documents (target: 100%).

**Outputs (lagging):**
- Precision and recall of HIGH against what reviewers find. Prototype: 🟢 62.5% and 50.0% against the generator's truth.
- Passes that rest on unbacked answers. Prototype: 🟢 27 of 29 passes have a missing, stale or out-of-scope document.
- Vendors overdue on tier cadence. Prototype: 🟡 6 of 40, all critical, against 0 on the flat cycle.
- Concentration: share of critical use cases on the top provider. Prototype: 🟢 42.9% shown; the synthetic truth is 53.6% because 5 vendors do not disclose.
- Truly high-risk vendors not rated HIGH (the known-limit class). Prototype: 🟢 5 of 10.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Shadow | 4w | Score the existing estate from the register and the questionnaire already on file. Show nothing to vendors. Compare the class with what reviewers would have chosen. |
| 1 — Evidence | 6w | Ask critical vendors for the three document types. Record a named reader for each. Show vendors what would move their score. |
| 2 — Provider and exit | 6w | Add the provider disclosure request and the exit questions to the questionnaire and the contract template. Map concentration; start exit-test planning with KillSwitch. |
| 3 — Queue and cadence | 6w | The review queue and tier cadence go live for critical and important vendors. Decisions are written to the third-party risk record. |
| 4 — Estate and interlocks | 8w | Remaining vendors; spend join (InferenceLens); model-swap trigger (SwapBrief); schema-change trigger (SchemaWatch); obligation crosswalk (ControlMap). |

---

## Open questions

1. **Who attests a document?** Evidence authenticity is not verified. Recommendation: a named analyst records having read each document and what it covers; a document counts only after that. Measure how often the reader finds the document does not cover the AI service.
2. **What does a flagged provider trigger?** A flag is a fact, not a decision. Recommendation: a flagged provider requires a documented fallback for each critical use case on it, owned by the business, reviewed with the exit drills; it does not block onboarding by itself.
3. **Who owns the weights?** Recommendation: line-2 owns the policy file; line-1 proposes changes; every change is versioned and every score records the version. Re-set the HIGH line from the real review queue size, not from this repo.
4. **How to treat a vendor that will not name its provider?** In this prototype it counts half a concentration flag. Recommendation: make disclosure a contract term; until then show the upper bound for each provider and say it is a bound.
5. **What replaces the questionnaire?** Nothing yet. Recommendation: keep it as the vendor's claim and score the claim; shorten it only after the evidence rule has run for a cycle.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Ingest:** connectors to the vendor register, the questionnaire tool and the contract repository, writing immutable snapshots keyed by content hash.
- **Scoring:** a stateless service that reads a snapshot and the policy file and writes a decision with its reasons. The evidence rule, the concentration view and the exit score are separate, testable functions, as in the prototype.
- **Evidence store:** object storage with retention for documents; a relational table for type, issue date, scope and named reader.
- **Storage:** Postgres for vendors, answers, evidence metadata, scores and decisions.

**Throughput envelope and latency budget.**
- Scoring work is vendors times answers. The prototype scores 40 vendors across 20 answers with a plain Python loop. Production volumes have not been sized.
- Decision latency: 🔴 design target is a decision inside one analyst session, not a batch overnight. Not built, not timed.

**Failure modes and degradation strategy.**
- A document has no issue date or scope: it counts as not valid and the reason says so.
- A vendor does not disclose its provider: half a concentration flag, and the upper bound shown for each provider.
- The contract repository is unavailable: the last snapshot is used and marked stale; contract-backed answers keep their last status.
- The policy file changes: scores are recomputed, and the old decision stays on the record with its policy version.

**Migration path from current state.**
- If the bank has a questionnaire and a register today: keep both. The questionnaire becomes the vendor's claim; VendorLens is what runs on it.
- If there is no evidence store: start with the three document types for critical vendors only.

**Org dependencies.**
- Procurement and legal must agree to add the provider disclosure and exit terms to the contract template. Without that, the concentration view stays a lower bound.
- The third-party risk team must name a reader for each document. Without that, the evidence rule counts presence, not reading.
- The model-risk team must own the policy file. Without that, the weights are mine, not the bank's.

---

*This PRD names interlocks with [Project 07 (InferenceLens)](../07-inferencelens-inference-finops/), [Project 13 (SwapBrief)](../13-swapbrief-model-migration/) and [Project 15 (SchemaWatch)](../15-schemawatch-tool-schema-drift/), and with [Project 16 (ControlMap)](../16-controlmap-ai-obligation-crosswalk/) and [Project 25 (KillSwitch)](../25-killswitch-ai-fallback-drills/). All five links are 🔴 designed, none built.*
