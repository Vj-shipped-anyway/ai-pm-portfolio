# PRD · ShadowScan — Unsanctioned AI Discovery, Ranked by Data Exposure

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for an information-security and AI-governance read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to a joint security and AI governance review in the seat. It is not a record of a PRD landed at a named bank. The deficiency taxonomy, the exposure index, the next-action vocabulary, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. RICE scores and rollout durations below are planning estimates (🔴), not measurements.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | ShadowScan — discovery of AI tools staff use that nobody approved, ranked by data exposure |
| **Owner** | AI Governance Lead (line-1), with the Information-Security Lead as co-owner of the review queue |
| **Stage** | Portfolio prototype; security and governance read |
| **Primary users** | Information-security lead, who owns the proxy, the resolver logs and the blocklist; AI governance lead, who owns the approved catalog and the approval path |
| **Secondary users** | Department owners who get a next action; model risk reviewer, who needs the AI inventory to be true; privacy officer, who owns the user-level data question |
| **Problem** | A bank approves a set of AI tools and keeps a blocklist of known AI domains. Staff use other AI tools anyway. New AI domains appear faster than the list is edited, AI features arrive inside software already approved as ordinary software, and a hit count says nothing about how much sensitive data left. In the synthetic data, 🟢 4,200 sessions go to 30 unsanctioned AI domains and 🟢 1,200 more use an AI feature inside an approved product. The blocklist finds 2,275 of the 4,200. |
| **Solution** | A read-only layer over proxy and DNS logs: a catalog lookup, a known-AI feed lookup, a generation-style path pattern and an upload-size test that discover domains the feed lacks, an exposure ranking (bytes out x department sensitivity weight x distinct staff) and a block, sanction or coach recommendation with an owner department. A person confirms before anything is blocked. |
| **North-star metric** | Share of the top 10 domains by exposure that have a resolved decision (blocked, sanctioned or coached) within one review cycle. Target 🔴 100%. Today in this model: 0%, no process exists. |
| **Measured metrics (synthetic)** | 🟢 3,948 of 4,200 unsanctioned AI sessions found (94.0%) against 2,275 for the blocklist (54.2%); 🟢 28 of 30 domains found, 14 hit by the list; 🟢 top 10 by exposure matches the truth ranking on 9 of 10; 🟢 the hit-count top 10 shares 0 of 10 with the exposure top 10. |
| **Modeled metrics** | 🟡 Utility about 13,070 extra unsanctioned AI sessions brought into view per two-week window, assuming 10,000 staff of whom 15% use AI outside the catalog. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on log volume and has not been sized. |
| **Risk #1** | A false positive blocks a legitimate tool. 🟢 542 sessions on 2 benign domains are called unsanctioned AI, and one ranks #3 by exposure. Mitigation: the output is a recommendation, a person confirms every block, and the department can contest it. |
| **Risk #2** | Staff move to personal devices once the visible tools are blocked. 🟢 600 sessions, 12.5% of all unsanctioned AI sessions, already sit in no log. Mitigation: pair blocks with a sanctioned alternative and a fast path to approval (TierGate), and treat personal-device use as a policy and device-management question, not a log question. |
| **Risk #3** | User-level logs are personal data. Mitigation: pseudonymize user identifiers before the classifier, rank by department, and give names to nobody; an open question below asks who may re-identify. |
| **Out of scope** | Prompt-injection and egress defense on sanctioned models (PromptShield, 06); vendor due diligence (VendorLens, 18); agent permission review (ScopeKeeper, 23); reading the content of what was sent. |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is departments or products, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Feed and catalog refresh process** (owner, cadence, retired entries removed) | 10 depts | 2 | 0.8 | 1 | 16.00 | Sequenced for v0.1 |
| 2 | **Catalog and feed lookup** (R1 to R3) | 10 depts | 3 | 0.9 | 2 | 13.50 | Built in prototype; v0.1 |
| 3 | **Exposure ranking** (bytes out x weight x distinct staff) | 10 depts | 3 | 0.8 | 2 | 12.00 | Built in prototype; v0.1 |
| 4 | **Next-action rules and owner assignment** | 10 depts | 2 | 0.7 | 2 | 7.00 | Built in prototype; v0.1 |
| 5 | **Log collector, directory join and pseudonymization** | 10 depts | 3 | 0.9 | 4 | 6.75 | Sequenced for v0.1 |
| 6 | **Discovery rules** (path pattern and size test) | 10 depts | 2 | 0.7 | 3 | 4.67 | Built in prototype; v0.2 |
| 7 | **Intake handoff** to TierGate for sanction candidates | 10 depts | 2 | 0.6 | 3 | 4.00 | Sequenced for v0.2 |
| 8 | **Review queue** with a contest path for departments | 10 depts | 3 | 0.6 | 5 | 3.60 | Sequenced for v0.2 |
| 9 | **Inventory of AI features inside approved SaaS** (tenant settings, vendor attestations) | 5 products | 3 | 0.5 | 5 | 1.50 | Sequenced for v0.3 |
| 10 | **Personal-device signals** (managed browser, device management) | 10 depts | 3 | 0.4 | 8 | 1.50 | Queued |
| 11 | **Branch proxy coverage** (close the DNS-only gap) | 4 depts | 3 | 0.6 | 5 | 1.44 | Queued |
| 12 | **TLS inspection scope** for pinned desktop and mobile clients | 10 depts | 2 | 0.4 | 6 | 1.33 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from ShadowScan | What they fear |
| --- | --- | --- | --- |
| **AI Governance Lead** (line-1) | Owner | An inventory that is true, with a ranked list of what to approve, block or coach first, and a path to approve what staff clearly need. | A list nobody acts on; a block that kills a tool the business relies on. |
| **Information-Security Lead** | Co-owner of the review queue | A ranking by what actually left, not by hits; fewer false alarms than the keyword rule raises. | Another alert stream; a control that depends on one log source. |
| **Department owners** | Receive the next action | Notice before a block, the reason, and an approved tool that does the job. A way to contest. | Being singled out; losing a tool they need with no replacement. |
| **Model risk reviewer** (line-2) | Auditor | A record of which AI tools were found, when, and what was decided, to keep the AI inventory complete. | A discovery heuristic presented as a guarantee. |
| **Privacy officer and works council** | Approver | Pseudonymized user data, department-level reporting, a stated retention period and no content inspection. | User-level browsing data copied into yet another store. |
| **Procurement and vendor management** | Consulted | A queue of sanction candidates with usage evidence, to start due diligence in order. | Approving a tool because many people already use it. |
| **IT operations** | Consulted | Block lists that are small, current and owned. | A second list to maintain. |

---

## User stories (top 4)

1. **As an information-security lead**, I want the AI domains in our proxy and DNS logs ranked by how much sensitive data goes to them, so I look first at the tool receiving contracts and not the one receiving the most chat prompts.
2. **As an AI governance lead**, I want a list of AI tools staff use that are not in the catalog, with the owning department and a recommended next step, so I can approve the ones the business needs and stop the ones it should not use.
3. **As a department owner**, I want to know which tools my team uses outside the catalog and what approved tool does the same job, so a block does not stop the work.
4. **As a model risk reviewer**, I want the discovered AI tools, with the evidence for each and the decision taken, so the AI inventory behind the model-risk record is complete and dated. SR 11-7, SR 26-2 and the NIST AI RMF are the design basis here, as analogy, not a claim of coverage.

---

## KPIs

**North star:** share of the top 10 domains by exposure with a resolved decision within one review cycle. Target 🔴 100%.

**Inputs (leading):**
- Share of proxy and DNS rows that carry a user, a department and a domain (target: every row).
- Age of the feed and the catalog (target: refreshed on a fixed cadence; retired entries removed).
- Share of discovered domains with an owner department named (target: every one).
- Review-queue age (🔴 design target: no item older than one cycle).

**Outputs (lagging):**
- Unsanctioned AI sessions found against the truth. Prototype: 🟢 3,948 of 4,200 with the new layer, 2,275 with the blocklist.
- Unsanctioned AI domains found. Prototype: 🟢 28 of 30, against 14 hit by the list.
- Precision. Prototype: 🟢 87.9% for ShadowScan, 66.4% for the list.
- False-positive domains reaching the queue. Prototype: 🟢 2 domains, 542 sessions.
- AI features inside approved SaaS found. Prototype: 🟢 491 of 1,200 sessions (40.9%).
- Sessions in no log (the known limit). Prototype: 🟢 600, 12.5% of all unsanctioned AI sessions.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Shadow | 4w | Collector and classifier on one log source. Nothing shown to departments. Compare the ranking with what the security team already knows. |
| 1 — Calibrate | 4w | Review a sample of flagged and unflagged domains by hand. Set the sensitivity weights with data owners. Measure the false-positive rate on real logs. |
| 2 — Advisory queue | 6w | Recommendations posted to the review queue. No blocks. Departments contest or confirm. Count decisions. |
| 3 — Blocking for the top of the ranking | 6w | Confirmed blocks applied for the highest-exposure domains, each with a named alternative. Sanction candidates open intake. |
| 4 — Estate and interlocks | 8w | Branch coverage, AI features inside approved SaaS, interlocks to intake, due diligence and acceptable-use mapping. |

---

## Open questions

1. **Who may block?** Does a confirmed recommendation go straight to the proxy, or to the information-security lead? Recommendation: the queue recommends, the security lead applies, and the department can contest within a fixed window.
2. **Who may re-identify a user?** The ranking needs departments, not names. Recommendation: pseudonymize before the classifier and let only the privacy officer's process re-identify, for a stated reason.
3. **Who owns the sensitivity weights?** The prototype uses one weight per department (an assumption). Recommendation: data owners set them, review them yearly, and the ranking states the weights it used.
4. **What counts as an AI feature inside approved software?** The path pattern finds some and misses vendor-specific paths (🟢 491 of 1,200 found). Recommendation: ask vendors for a list of AI features and the tenant setting that controls each, and treat the pattern as a cross-check.
5. **What is the stance on personal devices?** 🟢 600 sessions are in no log. Recommendation: treat it as an acceptable-use and device-management question and measure it with a survey, not a log.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Collector:** a reader on the log pipeline the security team already runs, joining each row to the directory and pseudonymizing the user.
- **Classifier and ranker:** stateless workers that hold the catalog, the feed and the weights and write per-day aggregates by domain, department and user bucket.
- **Review queue:** a console behind the bank's SSO, with decisions, contest and evidence.
- **Storage:** Postgres for domains, decisions and resolutions; a columnar store for per-session aggregates; object storage with retention for evidence.

**Throughput envelope and latency budget.**
- The prototype classifies 22,500 log rows with a plain Python loop. Production volumes have not been sized.
- Time from a log row to a recommendation: 🔴 design target is one daily batch. Not built, not timed.

**Failure modes and degradation strategy.**
- Feed or catalog stale: the classifier reports the age of each and flags the ranking as stale beyond a set age.
- A log source is missing or late: the ranking says which source is missing; it never presents a partial view as complete.
- A domain crosses the discovery threshold by mistake: the recommendation is advisory until a person confirms.
- Directory join fails for a user: the row counts toward the domain and not toward a department; the share of unjoined rows is a metric.

**Migration path from current state.**
- Keep the blocklist. It is a useful tripwire; ShadowScan is what ranks and explains.
- If there is no catalog with an AI-scope field, start with that: the classifier needs to know which approvals covered AI behavior.

**Org dependencies.**
- Security must share proxy and resolver logs with governance in a pseudonymized form.
- Governance must keep the catalog current, with the AI-scope field, and own the approval path that a sanction recommendation leads to.
- Privacy must agree the retention period and who may re-identify.

---

*This PRD interlocks with [Project 06 (PromptShield)](../06-promptshield-prompt-injection-defense/) and [Project 11 (TierGate)](../11-tiergate-ai-usecase-intake/). Interlocks with [16 ControlMap](../16-controlmap-ai-obligation-crosswalk/), [18 VendorLens](../18-vendorlens-ai-vendor-due-diligence/) and [23 ScopeKeeper](../23-scopekeeper-agent-permission-review/) are 🔴 designed, none built.*
