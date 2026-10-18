# PRD · CorpusGate — Entitlement-Aware Retrieval for an Internal AI Assistant

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a pre-launch security read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an assistant platform review in the seat. It is not a record of a PRD landed at a named bank. The scope, the failure taxonomy, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. RICE scores and rollout durations below are planning estimates (🔴), not measurements.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | CorpusGate — entitlement-aware retrieval for an internal AI assistant |
| **Owner** | Assistant Platform Owner (line-1), with the information-security reviewer as co-owner of the test pack |
| **Stage** | Portfolio prototype; pre-launch security read |
| **Primary users** | Assistant platform owner, who owns retrieval and its eval; information-security reviewer, who has to answer "could this user have seen that document" |
| **Secondary users** | Document owners; identity and access team; privacy officer; model risk reviewer; assistant users |
| **Problem** | An internal assistant retrieves from a document corpus and the retrieval eval measures relevance only. Nobody tests whether a user can pull back a document they are not entitled to, whether an ACL change reached the index, or whether personal data was ingested into text anyone can retrieve. In the synthetic data, 🟢 291 of 1,000 results go to a user who may not read them, and 🟢 283 of those score as correct in the eval. |
| **Solution** | An entitlement layer between the assistant and its index: an effective-ACL resolver (nested groups, explicit denies), an ACL drift check against the source, a pre-filter before ranking, an ingestion scan with quarantine or masking, and a canary pack that must come back empty. |
| **North-star metric** | Share of assistant retrieval requests served through the entitlement filter with a logged decision. Target 🔴 100% of in-scope assistants. Today in this model: 0%, nothing runs. |
| **Measured metrics (synthetic)** | 🟢 Leaked results 291 to 11 of 1,000; 🟢 canaries leaking 120 to 7 of 120; 🟢 personal data found 50 of 60; 🟢 readable recall@5 0.707 to 0.812. |
| **Modeled metrics** | 🟡 Utility about 168,000 unreadable results kept from users, assuming 1,200 assistant users each running 100 queries. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on corpus size, query volume and sync frequency, and has not been sized. |
| **Risk #1** | The document store's ACL and the group directory disagree with each other, so the resolver is faithful to a wrong answer. Mitigation: start in shadow, compare decisions with what the source system itself allows for a sample of users, and keep the canary pack running. |
| **Risk #2** | The ACL-sync window. 🟢 3 changes made after the last sync leave 103 user and document pairs wrongly allowed and 7 of 120 canaries leaking. Mitigation: a change feed with a fail-closed overlay for changed documents (🔴 designed, not built), and a canary stratum for "changed after the last sync". |
| **Risk #3** | The personal-data policy costs usefulness. 🟢 Holding SSN-like and account-like documents out of the index takes 0.070 off readable recall@5; masking instead would give 0.882. Mitigation: run both in shadow and let the privacy officer choose with the price in front of them. |
| **Out of scope** | Whether an answer is grounded in what was retrieved (HalluGuard, 01); instructions hidden in documents (PromptShield, 06); which documents informed a decision, as a record (LineageLog, 09); long-context fidelity (PolicyNeedle, 14); mapping obligations to controls (ControlMap, 16); agent tool permissions (ScopeKeeper, 23). |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is the 40 assistant users, or the number of roles or teams a back-office item serves, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. Dependencies override the score: the resolver and sync come first because everything else needs them.

| Rank | Item | Reach | I | C | E | RICE (🔴 planning estimate) | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Entitlement test cases in the retrieval eval** | 40 users | 3 | 0.8 | 2 | 48.0 | Sequenced for v0.2 |
| 2 | **Canary pack and scheduled runner** | 40 users | 3 | 0.9 | 3 | 36.0 | Built in prototype; v0.1 |
| 3 | **Pre-filter inside the retrieval query** | 40 users | 3 | 0.9 | 4 | 27.0 | Built in prototype; v0.1 |
| 4 | **Group resolver and ACL sync (source ACLs, group tree, change log)** | 40 users | 3 | 0.9 | 5 | 21.6 | Built in prototype; v0.1 |
| 5 | **Score floor so a thin result set returns fewer than 5** | 40 users | 2 | 0.5 | 2 | 20.0 | Queued |
| 6 | **Ingestion scan with quarantine queue** | 40 users | 2 | 0.8 | 4 | 16.0 | Built in prototype; v0.2 |
| 7 | **ACL change feed with fail-closed overlay (closes the sync window)** | 40 users | 3 | 0.5 | 5 | 12.0 | Sequenced for v0.2 |
| 8 | **More pattern formats and a review queue for misses** | 40 users | 1 | 0.6 | 3 | 8.0 | Sequenced for v0.3 |
| 9 | **Source-system connectors beyond the first two** | 40 users | 2 | 0.6 | 8 | 6.0 | Queued |
| 10 | **ACL drift report (index copy vs source)** | 4 roles | 2 | 0.9 | 2 | 3.6 | Built in prototype; v0.1 |
| 11 | **Access decision log (who was shown what)** | 3 roles | 2 | 0.9 | 3 | 1.8 | Sequenced for v0.2 |
| 12 | **Label-quality check (labels vs ACL breadth)** | 7 teams | 1 | 0.6 | 3 | 1.4 | Sequenced for v0.3 |

---

## Stakeholder map

| Stakeholder | Role | What they want from CorpusGate | What they fear |
| --- | --- | --- | --- |
| **Assistant Platform Owner** (line-1) | Owner | A retrieval layer that never shows a user a document they may not read, and an eval that can fail when it does. | A filter that hides useful documents; a second system to keep in sync with the first. |
| **Information-security reviewer** | Co-owner of the test pack | Canaries that run on a schedule, a decision record per question, and a clear statement of what the layer cannot see. | A control that looks complete because it agrees with its own data. |
| **Document owners** | Consulted; own the access lists | Their ACLs respected as written, and a quarantine review that does not take their week. | Being blamed for a leak caused by a late sync; a review queue with no owner. |
| **Identity and access team** | Consulted; own the groups | Read-only use of the directory; no second copy of group logic that drifts. | A resolver that disagrees with the directory and nobody knows which is right. |
| **Privacy officer** | Approver of the ingestion policy | Personal data kept out of retrievable text, with the price of holding versus masking stated. | Values in formats the scan cannot see; a scan presented as a guarantee. |
| **Model risk reviewer** (line-2) | Auditor | A record of which documents each answer could draw on, and evidence of ongoing testing. | A parallel record that competes with the model inventory. |
| **Assistant users** | Beneficiaries | Answers from documents they are allowed to read, without being told what they may not. | Empty answers and no explanation. |

---

## User stories (top 4)

1. **As an assistant platform owner**, I want every retrieval call filtered by the asker's effective access before ranking, so that no user is shown a document they may not read and unreadable documents do not take result slots.
2. **As an information-security reviewer**, I want a canary pack that runs on a schedule and on every ACL or index change, so that a leak is found by a test and not by a user.
3. **As a privacy officer**, I want documents scanned for personal data before they are indexed, with a quarantine queue and an owner review, so that SSN-like and account-like values do not sit in text anyone can retrieve.
4. **As a model risk reviewer**, I want each answer's retrieval decision recorded (user, documents returned, number withheld, ACL version used), so that the ongoing-monitoring story under SR 26-2 and the NIST AI RMF 'Measure' function is documented per question and not only at attestation time.

---

## KPIs

**North star:** share of assistant retrieval requests served through the entitlement filter with a logged decision. Target 🔴 100% of in-scope assistants.

**Inputs (leading):**
- Document stores connected to the sync (target: every store behind the assistant).
- ACL sync lag per store (🔴 design target: set from the first calibration phase).
- Canary strata covered (prototype: 5 strata; target: one per known failure class).
- Quarantine queue age (🔴 design target: owner decision inside an agreed window).

**Outputs (lagging):**
- Unreadable results per 100 queries. Prototype baseline: 🟢 145.50 with no filter, 5.50 with CorpusGate on synthetic data.
- Canaries leaking. Prototype: 🟢 120 of 120 with no control, 7 of 120 with CorpusGate.
- Stale index entries found. Prototype: 🟢 36 of 500 documents (7.2%) differ from the source at the last sync.
- Personal data found at ingestion. Prototype: 🟢 50 of 60, with 9 look-alikes flagged and 10 missed (the known-limit class).
- Readable recall@5. Prototype: 🟢 0.707 to 0.812.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Shadow | 4w | Sync ACLs and groups for one assistant, compute decisions, change nothing the user sees. Compare the resolver with what the source system allows for a sample of users. |
| 1 — Canary pack | 4w | Build the first pack from known denied pairs; run it against the live assistant and report. Add a stratum for recently changed ACLs. |
| 2 — Filter on, one assistant | 6w | The pre-filter serves one low-risk assistant. Decision log live. Watch result counts per question and user complaints about missing answers. |
| 3 — Ingestion scan | 6w | Scan at ingestion in advisory mode, then quarantine for SSN-like and account-like hits, with the owner review queue. Price quarantine against masking. |
| 4 — Estate and interlocks | 8w | Remaining assistants and stores; change feed with the fail-closed overlay; decision records to the lineage and control records. |

---

## Open questions

1. **Whose ACL wins?** When the document store and the index disagree, the source wins every time; index tags are a hint for speed. Recommendation: say so in the standard, and measure drift as a metric.
2. **Hold or mask?** The prototype prices it: 🟢 0.070 of readable recall@5. Recommendation: mask in the first phase, hold only SSN-like values until the privacy officer has seen the price.
3. **What does the assistant say when the best matches are withheld?** The prototype fills the list with the next-best readable documents. Recommendation: add a score floor so a thin result set returns fewer results, and never name a withheld document to the asker.
4. **Who owns the canary pack?** Recommendation: the information-security reviewer owns it, the platform owner runs it, and a failed canary blocks the next release of the assistant.
5. **How fresh must ACLs be?** The sync window is the largest measured gap. Recommendation: set a revocation-propagation target from the first calibration phase and test it with the post-sync canary stratum.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Sync:** a scheduled pull plus a change feed from each document store and the group directory, writing versioned ACLs and group edges.
- **Resolver and filter:** a stateless service that returns the user's effective groups and applies them as a clause inside the retrieval query.
- **Ingestion scan:** a stage in the indexing pipeline with a quarantine queue.
- **Storage:** PostgreSQL for ACLs, group edges, decisions and findings; the retrieval store keeps documents with ACL tags as a hint.

**Throughput envelope and latency budget.**
- The prototype resolves 40 users against 500 documents (20,000 pairs) in a plain Python loop in seconds. Production volumes have not been sized.
- Filter latency: 🔴 design target is a decision inside the assistant's existing response budget. Not built, not timed.

**Failure modes and degradation strategy.**
- Resolver or store unavailable: the filter fails closed and returns no results for that user, never unfiltered results.
- Sync late or a store unreachable: documents from that store are withheld after a staleness limit; the lag is a metric.
- Group missing from the directory or a cycle in the tree: unknown groups deny; the resolver tracks visited groups.
- Scan unavailable at ingestion: documents wait in a held state rather than being indexed unscanned.

**Migration path from current state.**
- If the index already stores ACL tags: keep them as a hint, add the filter on the source ACL, and let the drift report tell you how stale they are.
- If there is no relevance eval with users in it: add the user to the eval set first, so entitlement cases can be written.

**Org dependencies.**
- Document owners must keep the source ACL authoritative. Without that the gate is faithful to the wrong answer.
- The identity team must expose the group tree read-only, including nested groups and deny entries.
- The privacy officer must own the ingestion policy and the review queue.

---

*This PRD interlocks (🔴 designed, none built) with [Project 01 (HalluGuard)](../01-halluguard-bank-chatbot-safety/), [Project 06 (PromptShield)](../06-promptshield-prompt-injection-defense/), [Project 09 (LineageLog)](../09-lineagelog-ai-decision-audit/) and [Project 14 (PolicyNeedle)](../14-policyneedle-long-context-fidelity/), and with 16 ControlMap and 23 ScopeKeeper.*
