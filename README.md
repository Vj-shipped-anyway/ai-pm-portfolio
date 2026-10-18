# 🚀 AI PM Developer Portfolio — Vijay Saharan

A working portfolio of AI Product Manager case studies, each shipped as a **walkthrough you can actually run on your laptop**: use case → sample data → before-LLM solution → with-LLM solution → defects exposed → containment fix → utility math.

**Live site:** https://vj-shipped-anyway.github.io/ai-pm-portfolio/ has a clickable demo for all twenty-five, no install. **All twenty-five flagships are fully built** with sample data, four step scripts each, and a static `demo.html`. The static demos are all live. The Streamlit apps are live for HalluGuard, DriftSentinel and LeaseGuard; the other twenty-two are not deployed yet.

---

## 📌 Note on framing

These are **portfolio prototypes** — not production case studies. The deficiency taxonomies, architectures, RICE backlogs, schemas, and walkthroughs reflect how I'd approach these problems as a Senior PM, not work I shipped at a named bank.

Where I cite SR 11-7, NIST AI RMF, OWASP LLM Top 10, EU AI Act Article 12, OCC supervisory guidance, and similar frameworks, those are the standards the work would have to meet — they are not engagements I led through. The synthetic data, prototype code, deficiency analysis, architecture diagrams, and PRDs are mine; the production validation (MRM committee read, OCC exam, FRB horizontal review, validator co-design, fleet rollout) is what the next role does.

**A note on SR 11-7.** Several projects were designed against SR 11-7, the 2011 model risk management guidance. On April 17, 2026 the Federal Reserve, OCC and FDIC replaced it with [SR 26-2, Revised Guidance on Model Risk Management](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm), which describes a risk-based approach tailored to each bank's model risk profile and the size and complexity of its operations. Where a project README says "SR 11-7", read it as the 2011 guidance the design was first mapped to. The projects have not yet been re-mapped clause by clause to SR 26-2.

The CRE projects (LeaseGuard, DealSentry) apply the same PM rigor to a domain I follow as a personal study interest. I am not an LP in any CRE portfolio and am not actively investing; I read the lease forms, the operator playbooks, and the PropTech vendor literature because the data-quality and AI-reliability problems in CRE map cleanly to the problems I work on professionally.

Read this portfolio as: *this is how Vijay reasons about regulated AI product surfaces, what taxonomies he builds, what architectures he designs, and what backlog he'd run on day one.*

---

## 📊 Reading the numbers

Every numerical claim in this portfolio is tagged with one of three credibility tiers, so a reviewer can tell at a glance which numbers are real, which are extrapolated, and which are design intent. The tiers are:

- 🟢 **Measured** — actual output from a real run on real or synthetic data the user can see in this repo. Reproducible by cloning the repo and running the script. Examples: probe-set pass rates, prototype assembly times, synthetic-fleet detection counts.
- 🟡 **Modeled** — extrapolated from synthetic data plus published industry baselines. Every modeled number gets a one-line "what we assumed" note. Examples: dollar-loss prevention figures, fleet-scale MTTD, "wrong answers per year."
- 🔴 **Hypothetical** — designed and reasoned about, never validated against real production. Examples: "auto-attestable in 12 minutes," "validator co-design compresses sign-off from 3 weeks to 1 day."

I'd rather under-claim and over-deliver. Every flagship README and live demo carries the same tags inline, and every modeled number names its assumption set. When a hiring manager asks "is this real?", the answer is on the page next to the number.

---

## 📐 The thesis

I price product impact by one formula:

> **Utility = (my solution − current state of the art) × number of people it affects**

Reducing a metric by 71% is not an outcome. *Reducing a metric by 71% across 14 million customer interactions per year is.* Every case study below leads with the multiplied number, not the percentage.

That framing also forces honesty about three things most AI portfolios fudge: what the SOTA actually is, what the lift actually is, and how big the population actually is. If any of those numbers is shaky, the utility number is shaky, and the value story falls apart.

---

## 🚀 The Twenty-Five Flagships (live)

These are the polished case studies — full walkthrough README, sample data CSVs, four step-by-step Python scripts (`step_01_*.py` through `step_04_*.py`), utility math, and a PRD.

| Flagship | What it does | Utility delivered | Live demo |
| --- | --- | --- | --- |
| **🛡️ [HalluGuard](./01-halluguard-bank-chatbot-safety/)** — Bank chatbot hallucination containment | Wraps deployed chatbots; is designed to catch 8 named foundation-model failure modes (paraphrase blindness, negation flip, multi-hop, citation fabrication, …); routes low-confidence to abstention | 🟢 19 wrong answers before containment, 0 after, on the 30-query eval set (fixed mock verifier scores) · 🟡 \~3.85M wrong answers/yr prevented at a modeled mid-tier US bank shape (\~$40B-asset, \~2.4M retail customers, \~6 chats/customer/yr); \~40M at Tier-1 fleet scale (both need re-modeling: built on an earlier Step 2 figure) | **▶ [Live demo](https://halluguard-bfsi.streamlit.app)** · **▶ [Static demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/01-halluguard-bank-chatbot-safety/demo.html)** · **▶ [60-sec walkthrough](https://app.arcade.software/share/daLEfWH7yD0sYutT3HTP)** |
| **🛰️ [DriftSentinel](./02-driftsentinel-model-drift-monitoring/)** — Production model drift & decay | Three-loop sentinel (Detect → Diagnose → Decide) over the credit / fraud / AML / GenAI fleet; auto-assembles MRM evidence bundle | 🟡 Drift MTTD 78d → 9d (modeled — assumes the synthetic 90-day shipped data and a Tier-1-style fleet) × \~1,200 production models = \~83,000 model-decay-days/yr prevented at Tier-1 fleet scale; 🟡 \~$14M/yr modeled prevented loss at the $50B-asset bank shape (assumes 8-model fleet, MTTD compression, published loss-per-quarter-of-decay benchmarks) | **▶ [Live demo](https://driftsentinel-bfsi.streamlit.app)** · **▶ [Static demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/02-driftsentinel-model-drift-monitoring/demo.html)** · **▶ [60-sec walkthrough](https://app.arcade.software/share/mHOnNZCi66FsK0IFyiLs)** |
| **🏢 [LeaseGuard](./03-leaseguard-cre-lease-verification/)** — CRE lease abstraction error detector | Ensemble verification (primary model + re-extraction + rule-based) over deployed lease-NLP outputs; catches CAM caps, escalation clauses, and tenant rights buried in non-standard / redlined leases | 🟢 16 of 17 wrong fields routed to triage on the 6-lease synthetic eval set (76.4% → 98.6% after triage; 1 known miss) · 🟡 88% → 98.2% per-lease accuracy projected at portfolio scale (assumes 220-asset retail-and-office mix, paralegal triage clears flagged fields); 🟡 \~$4.2M/yr modeled recovered rent at the 220-asset shape; \~$95M/yr at national-operator scale | **▶ [Live demo](https://leaseguard-cre.streamlit.app)** · **▶ [Static demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/03-leaseguard-cre-lease-verification/demo.html)** · **▶ [60-sec walkthrough](https://app.arcade.software/share/hQWTvQIAmgkpQgjHC7iP)** |
| **🧪 [EvalForge](./04-evalforge-llm-eval-platform/)** — Eval-first console for regulated AI | Versioned probe sets + calibrated rubrics + cross-vendor LLM-as-judge + CI gate (GitHub Actions / Argo CD pre-deploy hook) that blocks the deploy on regression | 🟢 Both silent vendor-snapshot updates in the 50-run synthetic dataset blocked on first eval run; 🟡 silent post-deploy regression rate 14% → <2% (modeled — assumes an industry baseline of ~14% and the Tier-1-shaped GenAI fleet) × 12-20 customer-facing GenAI features per Tier-1 BFSI shop = 🟡 ~25-40 silent regressions prevented per year at fleet scale (assumes ~15 shipped changes per feature per year); tens of thousands to hundreds of thousands of bad responses caught before customer impact | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/04-evalforge-llm-eval-platform/demo.html)** |
| **🔍 [LineageLog](./09-lineagelog-ai-decision-audit/)** — AI decision audit trail & decision lineage | Immutable decision-grain composition layer that binds Cloud Logging + Cloud Audit Logs + Agent Identity Logs + OpenTelemetry traces at `(decision_id, customer_id_hash, timestamp)`; six-deficiency taxonomy closed; auto-assembled exam-pack export | 🟢 6 of 6 deficiencies closed on the headline decision, all 200 decisions composed in the synthetic corpus (29 of the 200 outcome rows are none_observed); 🟢 composition latency in milliseconds per decision on the prototype (step_04 prints it; varies by run); 🟡 audit-pack assembly time 3 weeks → 3 seconds (modeled — assumes the synthetic 200-decision corpus + Tier-1-style four-model fleet); 🟡 exam-readiness coverage 22% → 100% (modeled — assumes published BFSI baseline for sample-based vs continuous readiness); 🔴 time-to-decision-evidence 14d → 12min (designed) × 🟡 50-200M regulated AI decisions/yr at Tier-1 retail bank = continuous exam-readiness | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/09-lineagelog-ai-decision-audit/demo.html)** |
| **🤖 [AgentWatch](./05-agentwatch-agent-observability/)** — Agent reliability & tool-use observability | Sidecar over LangGraph / AutoGen / Bedrock Agents / OpenAI Assistants; classifies failure under a six-deficiency taxonomy (runaway tool loops, hallucinated tool args, silent drift, blast-radius unbounded, missing reasoning trace, cost detached from outcomes); enforces per-incident dollar cap; auto-assembled incident pack routed to SRE on-call + line-1 owner | 🟢 24 of 24 detected incidents composed into six-deficiency records on the 500-run synthetic corpus; 🟢 composition latency <50ms per incident on the prototype; 🟢 headline runaway cut off at $4,218 against a $250 per-agent cap; Step 1 prints $47,978 of undetected runaway cost over the 30 days; 🟡 APM-only detection rate \~25% → AgentWatch 100% (modeled — assumes Datadog with standard p99 thresholds); 🔴 MTTR 4h+ → <10min (designed) × 🟡 8-20 deployed agents at Tier-1 BFSI fleet scale = \~24 runaways/yr bounded ($120k - $1.2M of bounded spend) | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/05-agentwatch-agent-observability/demo.html)** |
| **🛡️ [PromptShield](./06-promptshield-prompt-injection-defense/)** — Prompt-injection & egress defense for internal BFSI copilots | Five-layer defense-in-depth gateway between user input and the LLM: L1 input classifier (Llama Guard 3 / fine-tuned DeBERTa), L2 retrieval scanner (catches indirect injection in retrieved RAG content), L3 tool-call gate (OPA / Rego), L4 egress filter (DLP regex pack), L5 per-session memory boundary (Redis + SPIFFE); six-class deficiency taxonomy (direct, indirect, tool-call abuse, egress, cross-session leak, jailbreak) closed | 🟢 99% catch rate on the 100-prompt synthetic attack suite (measured) vs. 43% on regex baseline; 🟢 1% false-positive rate on the 200-prompt legitimate-banker corpus; 🟢 100% accuracy on the 50-call tool-gate ground-truth set; 🟡 modeled production catch 96%+ at 4% FP (assumes fine-tuned classifier replaces the regex pack + continuous red-team probes); 🔴 designed data-exfiltration incidents → 0 × 🟡 4-12 internal copilots over confidential data at every Tier-1 BFSI shop = modeled $4-15M of prevented loss per confirmed customer-data breach avoided | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/06-promptshield-prompt-injection-defense/demo.html)** |
| **💰 [InferenceLens](./07-inferencelens-inference-finops/)** — Per-feature inference economics for the BFSI GenAI portfolio | Per-feature inference-economics layer over OpenTelemetry span attributes + vendor billing-API reconcile; five derived views (per-feature attribution, runaway detection, cheaper-model substitution recommender, dead-feature flagger, per-feature ROI ranking); six-deficiency taxonomy (no per-feature attribution, no per-tenant attribution, no runaway detection, no substitution recommender, no dead-feature flagger, no per-feature ROI) closed | 🟢 6 of 6 deficiencies closed on every feature in the 18-feature synthetic fleet; 🟢 all five derived views composed in <10ms on the prototype; 🟢 headline runaway (FT_001 retrieval-depth misconfig) flagged day 1 with modeled overspend \~$195k caught vs. 45 days undetected; 🟡 $301,800/mo of modeled substitution savings across 6 candidates (sum of CSV inputs); 🟢 dead-feature spend $25,991/mo flagged on FT_009; 🟡 modeled fleet-scale spend reduction 25-30% (assumes typical Tier-1 BFSI portfolio shape) × 🟡 $8-30M/yr aggregate inference spend at Tier-1 BFSI scale = **\~$2-9M/yr saved** | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/07-inferencelens-inference-finops/demo.html)** |
| **👥 [OversightOps](./08-oversightops-hitl-workflow/)** — HITL workflow designer | Calibrated, role-aware human-in-the-loop layer: difficulty-stratified routing (case + AI confidence + customer tier + country risk), rubber-stamp blocker (tier-specific time-on-task floor), reviewer calibration drift detection, escalation path for hard cases, SLA-by-tier with timer engagement, ground-truth feedback loop closed via downstream signals (SAR / OFAC / CFPB / charge-off) | 🟢 a verdict composed for all 1,000 cases in the synthetic KYC corpus; 🟢 composition latency under 1 ms per case on the prototype (the script prints the measured time); 🟢 125 of 146 private-banking reviews under the 60-second floor flagged by the blocker; 🟡 Tier-1 rubber-stamp rate 94% → 4% (modeled — assumes published BFSI baseline + OversightOps blocker engaged on Tier-1 queues); 🟡 reviewer-vs-ground-truth divergence 38% → 8% (modeled — assumes the 6-12-month tail + calibration packet engaged weekly); 🔴 Tier-1 KYC review SLA 9s → 8 min (designed) × 🟡 every regulated AI workflow with a HITL step (typical Tier-1: 6-15 such pipelines × thousands of high-stakes decisions per year per pipeline) = real oversight instead of theatrical | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/08-oversightops-hitl-workflow/demo.html)** |
| **🏗️ [DealSentry](./10-dealsentry-cre-underwriting/)** — CRE AI underwriting reliability | Three-path verifier behind the AI underwriting copilot: comp existence (CoStar / Reonomy / Cherre dereference), symbolic re-run (pandas + sympy in the design, plain Python in the prototype, for T-12 / cap rate / occupancy / exit-cap spread), submarket-stat cross-feed; six-class deficiency taxonomy (comp fabrication, T-12 rollforward, stat staleness, cap-rate math, occupancy discrepancy, exit-cap mismatch) closed | 🟢 all 6 designed deficiency classes caught across the 6-memo eval set, including 3 of 3 fabricated comps, vs. 0 of 3 on face-value trust and 0 of 3 on the analyst spot-check at the script's fixed seed (about 18% expected across seeds); 🟡 $6.78M modeled bid risk caught on the synthetic eval set (flat $2.1M per FAIL, $480K per REVIEW); 🟡 \~28% → 100% catch on fabricated comps × \~800-1,200 deals/yr screened at a national CRE operator = 🟡 \~3-5 bad bids/yr prevented × \~$1.8M each ≈ **\~$7.2M/yr modeled**; 🟡 at top-5 institutional fleet scale (\~$25B+ AUM): \~15-25 bad bids/yr ≈ \~$35M/yr modeled (the annual figures need re-modeling: built on an earlier \~28% spot-check baseline); 🟡 per-memo verifier runtime <90s p95 | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/10-dealsentry-cre-underwriting/demo.html)** |
| **🧭 [TierGate](./11-tiergate-ai-usecase-intake/)** — AI use-case intake & risk tiering | Recomputes each intake's risk tier from the form, the data catalog and the vendor registry; flags every discrepancy with a reason; links duplicates; gates approval on the evidence the tier requires; orders review by tier | 🟢 tier accuracy 69.3% → 86.0% and tier 3-4 recall 75.7% → 100.0% on 150 synthetic submissions; 🟢 approvals missing required evidence 32 of 116 → 3 of 76; 🟡 tier 3-4 queue wait 2.9 → 1.2 business days (tier 1-2 wait rises 3.4 → 9.7); 🟡 62.5 mis-tiered use cases avoided per year at a modeled 375 submissions; 🟢 known limit: 6 cases where the form and the catalog are both wrong | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/11-tiergate-ai-usecase-intake/demo.html)** |
| **📒 [ValueLedger](./12-valueledger-ai-benefit-tracking/)** — AI benefit realization tracking | Holdout cohort, difference-in-differences, net of rework, decay curve, overlap deduplication and a hard-versus-soft ledger tied to the budget table | 🟢 against the synthetic answer key: vendor-style claim +152%, before-and-after +111%, ValueLedger +5% (interval covers the truth); 🟢 9% of the claimed value ($33,706 of $372,329) is cash a budget line can absorb; 🟡 about 94,200 hours of overstated benefit removed per 14 weeks at a modeled 5,000 staff (modeled — assumes the same overstatement pattern holds at a bank's headcount and mix); 🟢 known limit: a hidden post-launch change leaves a residual bias | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/12-valueledger-ai-benefit-tracking/demo.html)** |
| **🔀 [SwapBrief](./13-swapbrief-model-migration/)** — Model migration decision brief | Per-slice paired bootstrap intervals, cost per correct answer, p50 and p95 latency, a prompt-fair comparison, and a GO / GO WITH GUARDRAILS / NO-GO decision with explicit rollback triggers | 🟢 over 200 simulated scenarios whose problem mix I defined: false-GO rate 96.9% for a headline-average rule, 67.0% for an aggregate significance test, 8.2% for SwapBrief; 🟢 missed-regression rate 94.7%, 54.7%, 8.0%; 🟢 on the committed set the average says GO (+4.3 pp) while cost per correct answer is +8.8% and p95 is +25.9%; 🟡 2.2 bad migrations avoided per year at a modeled 6 migrations a year; 🟢 known limit: 5 of 75 true slice regressions left inconclusive and 6 missed | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/13-swapbrief-model-migration/demo.html)** |
| **📖 [PolicyNeedle](./14-policyneedle-long-context-fidelity/)** — Long-context fidelity probes | Synthetic policy manuals with facts planted at controlled depth in six forms (plain, superseded, exception, table, two-section, sibling distractor), a plug-in reader interface, a per-slice sweep and a CI-style gate | 🟢 against four stub readers with known faults: 190 of 190 fault cells flagged, 0 missed, 0 false flags, versus 0 of 190 for a short-document test; no model is tested; 🟡 8 launches a year at a modeled assistant count; 🟢 known limit: 5 probe types cannot be scored by exact match | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/14-policyneedle-long-context-fidelity/demo.html)** |
| **🔭 [SchemaWatch](./15-schemawatch-tool-schema-drift/)** — Tool-schema drift detection | Structural diff classifier, description heuristic for unit changes, replay of recorded calls against the new schema, blast-radius ranking and a release gate | 🟢 without monitoring 742 of 2,500 recorded calls fail; 🟢 replay predicts 742 of 742 with no false positives; 🟢 41 of 45 changes classified as in the ledger; 🟢 a version check catches only 16 of 25 releases that need action; 🟡 about 296 broken or misread calls per quarter avoided at a modeled 12 changes a quarter; 🟢 known limit: 3 meaning changes with no number or unit go undetected | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/15-schemawatch-tool-schema-drift/demo.html)** |
| **🗺️ [ControlMap](./16-controlmap-ai-obligation-crosswalk/)** — AI obligation crosswalk | Maps AI obligations (EU AI Act, model-risk guidance, NIST AI RMF, ECOA / Regulation B) to controls and evidence: theme dictionary, scope check, evidence-freshness check, orphan-control list, one consolidated evidence request per theme | 🟢 right status on 46 of 48 obligations against 23 of 48 for a keyword spreadsheet; 🟢 20 evidence requests instead of 48; 🟢 10 of 11 orphan controls listed; 🟡 (46/48 − 23/48) × 288 = 138 obligation entries given the right status per exam cycle (assumes six business lines each track a copy of the 48); 🟢 known limit: 6 true control links missed because their wording is outside the dictionary | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/16-controlmap-ai-obligation-crosswalk/demo.html)** |
| **⚖️ [FairLens](./17-fairlens-credit-model-fairness/)** — Credit-model fairness test pack | Fairness test pack for a stub credit scorecard: approval rate and adverse impact ratio by group with a bootstrap interval, cutoff sweep, proxy ablation, reason-code consistency, PASS / REVIEW / FAIL per test | 🟢 overall accuracy 87.1% while the lowest adverse impact ratio is 0.750 (screen 0.80); 🟢 5 of 6 tests return REVIEW or FAIL; 🟢 neutralizing the postcode proxy points moves the lowest ratio 0.750 to 0.871 and accuracy 87.1% to 89.2%; 🟡 1.00 × 20,000 = 20,000 decisions a year under a full test pack (assumed volume); 🟢 known limit: the reason-code test passes while the proxy is present, and a failing screen passes at 14.8% label error | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/17-fairlens-credit-model-fairness/demo.html)** |
| **🏢 [VendorLens](./18-vendorlens-ai-vendor-due-diligence/)** — AI vendor due diligence | Scores 40 synthetic AI vendors on what can be checked: each answer against a document or the contract, upstream model-provider concentration, exit readiness, review cadence by tier | 🟢 the questionnaire passes 29 of 40 vendors, including 6 of the 10 truly high-risk; 🟢 27 of 29 passes have a missing, stale or out-of-scope document; 🟢 one upstream provider carries 42.9% of 56 critical use cases and the questionnaire asks 0 of 20 questions about it; 🟢 VendorLens rates 8 HIGH, 5 truly high-risk (precision 62.5%, recall 50.0%); 🟡 3.0 more high-risk vendors found per full review of a modeled 120-vendor estate; 🟢 known limit: 5 of 10 high-risk vendors not rated HIGH | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/18-vendorlens-ai-vendor-due-diligence/demo.html)** |
| **🚨 [IncidentLedger](./19-incidentledger-ai-incident-response/)** — AI incident response | Rule-based classifier, severity rubric, notification-clock engine, follow-up tracker and root-cause linking over 120 synthetic incidents; clock lengths are assumptions of a modeled bank | 🟢 39 of 87 notification deadlines missed and the ticket queue shows none; 🟢 30 of 65 S1 or S2 incidents filed as P3 or P4; 🟢 category right on 110 of 120; 🟢 starting every clock at detection counts 65 missed deadlines against 39 from determination; 🟡 (0.392 − 0.067) × 60 = about 19.5 missed deadlines avoided a quarter at a modeled 60 incidents a quarter; 🟢 known limit: 10 categories wrong and determination time is a human call | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/19-incidentledger-ai-incident-response/demo.html)** |
| **🚪 [CorpusGate](./20-corpusgate-rag-entitlements/)** — Entitlement-aware retrieval | Effective access through nested groups, index ACL copy checked against the source, filter before ranking, personal-data scan at ingestion, canary leak tests; stub TF-IDF retriever, not a model | 🟢 291 of 1,000 results go to a user who may not read them and the relevance eval scores 283 of them as correct; 🟢 11 of 1,000 still leak after the gate, all from 3 ACL changes after the last sync; 🟢 canary pack 7 of 120 leak against 120 of 120; 🟢 the personal-data scan finds 50 of 60 injected values; 🟡 (145.50 − 5.50) × 1,200 = about 168,000 unreadable results kept from users (assumes 1,200 users at 100 queries each); 🟢 known limit: 10 injected values in unusual formats missed | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/20-corpusgate-rag-entitlements/demo.html)** |
| **📈 [AdoptionPulse](./21-adoptionpulse-ai-enablement-funnel/)** — AI enablement funnel | Four-stage funnel (licensed, activated, habitual, proficient) from weekly usage telemetry, cut by org unit, with training-to-usage conversion, champion coverage and a retention curve | 🟢 the login view reports 88.0% adoption while 27.6% are habitual; 🟢 337 of 558 activated users never became habitual; 🟢 habitual rate by unit runs 4.0% to 66.7% against 70.0% to 100.0% on logins; 🟢 762 of 800 users staged as the generator decided, against 407 of 800 for a login flag at its best; 🟡 (95.2% − 50.9%) × 800 = about 355 users correctly staged (assumes 800 licensed in scope); 🟢 known limit: 13 of 80 users staged proficient produce poor work the telemetry cannot see | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/21-adoptionpulse-ai-enablement-funnel/demo.html)** |
| **🔦 [ShadowScan](./22-shadowscan-unsanctioned-ai-discovery/)** — Unsanctioned AI discovery | Classifies synthetic proxy and DNS logs against a sanctioned catalog and a feed, flags generation-style paths and upload-heavy ratios, ranks by data exposure, recommends block, sanction or coach | 🟢 a blocklist finds 2,275 of 4,200 unsanctioned AI sessions; ShadowScan finds 3,948 (recall 94.0%, precision 87.9% against 66.4%); 🟢 28 of 30 unapproved AI domains found against 14 hit by the list; 🟢 the top 10 by hits shares 0 of 10 with the top 10 by exposure; 🟡 (20.562 − 11.849) × 1,500 = about 13,070 extra sessions in view per two weeks (assumes 1,500 staff using AI outside the catalog); 🟢 known limit: 600 off-network sessions in no log, 542 false-positive sessions on 2 benign domains | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/22-shadowscan-unsanctioned-ai-discovery/demo.html)** |
| **🔑 [ScopeKeeper](./23-scopekeeper-agent-permission-review/)** — Agent permission review | Usage-versus-grant diff, breadth score, proposed least-privilege scope set per agent, dry-run replay of 90 days of calls, risk ranking | 🟢 annual recertification removes 2 of 184 grants while 69 of 184 had no call in 90 days; 🟢 61 of 71 unneeded grants removed, effective entitlements 211 to 126; 🟢 replay denies 0 of 7,994 calls (by construction); 🟢 118 of 1,243 high-impact calls had no human approval; 🟡 (4.07 − 0.07) × 200 = about 800 unneeded grants removed per review (assumes 200 agents); 🟢 known limit: 10 quarterly grants, 8 removed, 51 legitimate calls would be denied next quarter | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/23-scopekeeper-agent-permission-review/demo.html)** |
| **🧭 [PortfolioBoard](./24-portfolioboard-ai-program-portfolio/)** — AI program portfolio | Evidence-based status per program, capacity grid for scarce reviewers, dependency propagation, work-in-progress pull rule, benefit-at-risk rollup over 30 synthetic programs | 🟢 23 of 30 statuses change once gate evidence is applied; 🟢 6 of 16 team-quarters over capacity, model risk review 4 of 4; 🟢 true status shown for 27 of 30 programs against 7 of 30 in the report (by construction, apart from 3 planted false attestations); 🟡 $20.25M of $60.35M owner-estimated benefit sits on red-by-evidence programs; 🟡 (27 − 7) ÷ 30 × 35 = about 23.3 owners and sponsors see a true status; 🟢 known limit: 3 programs show AMBER but are truly RED, 10 of 30 carry stale evidence | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/24-portfolioboard-ai-program-portfolio/demo.html)** |
| **🛑 [KillSwitch](./25-killswitch-ai-fallback-drills/)** — AI fallback and degradation drills | Per-segment warn and trip thresholds with hysteresis, a drill scorecard and a recovery tracker over 90 synthetic days and 12 degradation events; thresholds fitted on days 1-60, scored on days 61-90; the manual plan is modeled | 🟢 on the 30 held-out days it trips on 4 of 5 events, median 2.5 hours in, with 1 false trip; 🟢 223 bad decisions per event against 255 for a tuned single threshold; 🟢 0 of 17 returns re-tripped; 🟢 4 of 10 drills failed, 3 on a stale rules version; 🟡 (255 − 223) × 4 = 128 bad decisions avoided per quarter (assumes 4 such events a quarter); 🟢 known limit: 3 silent errors never trip and 340 bad decisions are served | **▶ [Demo](https://vj-shipped-anyway.github.io/ai-pm-portfolio/25-killswitch-ai-fallback-drills/demo.html)** |

Run any flagship on your laptop:

```bash
cd <flagship-folder>/src
pip install -r requirements.txt
python step_01_*.py    # before
python step_02_*.py    # with LLM
python step_03_*.py    # defects exposed
python step_04_*.py    # the fix
```

---

## 💡 How to Navigate

**If you're a hiring manager who wants the punchline:** read the master flagship — [HalluGuard](./01-halluguard-bank-chatbot-safety/) — top to bottom. It's a 15-minute read with the walkthrough format, the 8-deficiency taxonomy, the LoRA training plan, and the utility math.

**If you're a technical reviewer:** pick any flagship, `cd <folder>/src`, install requirements, run the four step scripts in order. Each writes a CSV to `out/`.

**If you're a non-technical reader:** every flagship walkthrough is designed to be read with the code blocks skipped. The plain-English explanations and the output tables tell the story.

**If you're a hiring manager:** each flagship's README is its own 12-minute story. Pick the one closest to your team's failure mode and let's talk.

---

## 🏛️ Reference frameworks the portfolio aligns to

These products don't exist in isolation. Each one slots into a published industry framework or reference architecture. The framework alignment is what turns "AI prototype" into "procurement-ready conversation" with a CISO or Head of AI — and is the lens I bring to a Sr / Principal PM seat in this space.

- **Google Cloud — *Building secure multi-agent systems on Google Cloud*** (Anirudh Kannan, Christine Sizemore, Connor Herriford, et al., 2025) — the cleanest published spec of the defensible multi-agent pattern. Gemini Enterprise Agent Platform, ADK, Agent Identity, Agent Gateway, Model Armor, Agent Registry, the double-guardrail (IAM + semantic). [Project 05 — AgentWatch](./05-agentwatch-agent-observability/), [06 — PromptShield](./06-promptshield-prompt-injection-defense/), [08 — OversightOps](./08-oversightops-hitl-workflow/), and [09 — LineageLog](./09-lineagelog-ai-decision-audit/) all reference this paper directly and map their controls to its primitives.
- **Google's Secure AI Framework (SAIF)** — model controls + agent controls + supply-chain controls. The framework backbone for projects 05, 06, 08, 09.
- **OWASP LLM Top 10** — LLM01 Prompt Injection, LLM09 Misinformation, LLM06 Sensitive Information Disclosure. [Project 01 — HalluGuard](./01-halluguard-bank-chatbot-safety/) and [06 — PromptShield](./06-promptshield-prompt-injection-defense/) anchor here.
- **NIST AI RMF + EU AI Act Article 12** — decision-grain lineage requirements. [Project 09 — LineageLog](./09-lineagelog-ai-decision-audit/) is the implementation surface.
- **SR 11-7 (2011) and its replacement [SR 26-2](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm) (April 2026)** — model risk management guidance from the Federal Reserve, OCC and FDIC. SR 11-7's ongoing-monitoring requirement is what [Project 02 — DriftSentinel](./02-driftsentinel-model-drift-monitoring/) was first mapped to; it has not yet been re-mapped to SR 26-2.
- **The eval-first thesis** — Hamel Husain, Karpathy, Greg Kamradt's needle-in-haystack work, Lilian Weng on LLM patterns. Cited in [Project 04 — EvalForge](./04-evalforge-llm-eval-platform/) and the [HalluGuard probe taxonomy](./01-halluguard-bank-chatbot-safety/probes/).

The phrase that sells this in BFSI: *"Each project is the implementation surface for a published framework regulators and Google have already endorsed."* The portfolio isn't proposing new compliance; it's the missing product layer between the framework and the production system.

---

## 🛠️ Tech Stack across the portfolio

| Layer | What I use |
| --- | --- |
| **Foundation models** | Anthropic Claude Sonnet 4 (default), Azure OpenAI gpt-4o, fine-tuned Llama 3.1 8B / Mistral 7B for in-VPC workloads |
| **Fine-tuning** | LoRA via PEFT (HalluGuard verifier: rank 16, alpha 32, 4× A100 for 6 hours, ~$182 modeled training compute, not run) |
| **Retrieval** | Postgres + pgvector for moderate scale; Pinecone / Weaviate when latency budgets are tight; OpenSearch for hybrid lexical+semantic; `text-embedding-3-large` |
| **Drift / eval primitives** | Evidently AI, NannyML, Whylogs, custom Python on Spark for GenAI proxy metrics |
| **Orchestration** | LangGraph for agent workflows, Temporal for long-running approvals, Airflow for retraining pipelines, Kafka / Kinesis for the event spine |
| **Observability** | OpenTelemetry as the substrate, Langfuse for LLM traces, Datadog for SOC pane, ClickHouse for high-cardinality drift events |
| **Compute** | A100 / H100 for training and high-throughput serving; T4 / L4 for guardrail layers and LLM-as-judge; CPU-only for most drift math |
| **Data plane** | Snowflake / Databricks; Unity Catalog or Lake Formation for lineage; MLflow / SageMaker Model Registry; Tecton / Databricks Feature Store |
| **Demo / front end** | Streamlit Community Cloud for the prototypes; plotly for charts; pandas / numpy / scipy throughout |
| **Security baseline** | SOC 2 Type II, GLBA, PCI-DSS where in scope, FedRAMP Moderate where federal counterparty work demands it |
| **CRE-specific** | CoStar, Reonomy, Cherre, CompStak for source-of-truth verification; Yardi Voyager / MRI / Argus Enterprise for system integration |

---

## 🛠️ Why Streamlit (and when it's the wrong stack)

Streamlit was the right tool for these prototypes. It would be the wrong tool for production. The distinction matters and a hiring manager should hear it explicitly.

**Streamlit is right for:**
- Validating the product mechanic in 5 days, not 5 weeks
- Walking a stakeholder through a story end-to-end on a free deploy
- Running internal tools where 1-2 product folks are the only users
- Single-tenant, single-page workflows where the UI doesn't have to scale

**Streamlit is wrong for:**
- Production multi-tenant SaaS — no native tenant isolation, no row-level security
- Mobile-first UX — Streamlit's responsive story is "ok, not great"
- Hardened auth (OIDC, SAML, fine-grained RBAC) — community-tier auth is too thin for regulated environments
- Real-time websocket dashboards — every interaction is a full server rerender
- Brand-controlled pixel-perfect UX — too much chrome you don't own
- Latency-sensitive customer-facing flows — server-side rerun on every widget change

**If any flagship in this portfolio graduated from prototype to product, the production stack would be:**
- Front end: Next.js + Tailwind + shadcn/ui (or the bank's design system)
- Back end: FastAPI or NestJS, deployed on the bank's existing K8s/EKS footprint
- Auth: Auth0 / Okta / Cognito with OIDC + RBAC; in regulated shops, ForgeRock or PingFederate
- Data plane: Snowflake or Databricks (whichever the bank already runs); Postgres + pgvector for the verifier index
- Observability: OpenTelemetry → Datadog (the bank's standard) and Langfuse for LLM-specific traces
- Governance: integrate with the bank's MRM workbench (Archer, ServiceNow GRC, MetricStream — pick what your CRO already pays for)

The portfolio prototype is the conversation-starter. The production architecture is the second meeting.

---

## 🎯 Career Goal

Sr / Principal Product Manager at an AI-first BFSI org, AI platform team, or PropTech operator — where the work is shipping production AI under regulated constraint (drift, evals, hallucination, agent reliability, audit lineage). I follow commercial real estate as a personal study interest and the lease-NLP and underwriting-reliability problems map cleanly to the same AI-quality work.

---

## 👤 Author

**Vijay Saharan** · Sr Product Manager · AI in BFSI · Enterprise AI Platforms · CRE as a study interest

- **LinkedIn:** [linkedin.com/in/vijaysaharan](https://www.linkedin.com/in/vijaysaharan/) — primary contact, full work history, recommendations
- **Resume:** available on request via LinkedIn DM
- **Open to:** Sr / Principal PM roles in AI Platform, AI in BFSI, and PropTech

**Credentials, employers, and detailed work history:** see [LinkedIn](https://www.linkedin.com/in/vijaysaharan/). The projects in this repo are how I think — the analysis, taxonomies, architectures, and PM artifacts I'd bring to the seat. LinkedIn is the verified work-history record.

**Why this maps to AI-first BFSI Sr / Principal PM specs:**

- Owning AI roadmap under regulated constraint? → [DriftSentinel](./02-driftsentinel-model-drift-monitoring/), [HalluGuard](./01-halluguard-bank-chatbot-safety/), [LineageLog](./09-lineagelog-ai-decision-audit/) all start with the deficiency taxonomy and end at MRM attestation as the design target.
- Shipping copilots / agents into production? → [HalluGuard](./01-halluguard-bank-chatbot-safety/), [AgentWatch](./05-agentwatch-agent-observability/), [PromptShield](./06-promptshield-prompt-injection-defense/) cover the four production failure classes (hallucination, agent reliability, prompt injection, observability).
- FinOps / inference-cost ownership? → [InferenceLens](./07-inferencelens-inference-finops/) is the spec.
- Cross-functional with risk, compliance, infosec? → Every PRD in this repo names the line-1 / line-2 / line-3 stakeholders explicitly and sketches a stakeholder map.

If your seat maps to one of these projects, pick that one and let's talk about it. I'd rather have a 45-minute conversation about your specific failure mode in production than send you a deck.

---

## 🙌 Acknowledgements

- [Hamel Husain](https://hamel.dev/blog/posts/evals/) — the eval-first thesis. Reason every flagship has a probe set committed before any model code.
- [Greg Kamradt](https://github.com/gkamradt/LLMTest_NeedleInAHaystack) — needle-in-haystack work. Reason multi-hop is a separate slice in HalluGuard.
- [Chip Huyen](https://huyenchip.com/) — silent-decay and ML-systems writing that shaped the DriftSentinel framing.
- [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/) — canonical industry framing for hallucination and prompt injection.
- [Simon Willison](https://simonwillison.net/) — weekly required reading on prompt injection, hallucination, and where the field is actually moving.
- [Evidently AI](https://www.evidentlyai.com/) and the [NannyML](https://www.nannyml.com/) team — the open-source drift primitives the Sentinel sits on top of.

---

## 🧩 Portfolio Progression

The twenty-five flagships are the foundation. Still being scoped: foundation-model regression detection.

Each new project follows the same shape: pick a bleed, name the deficiency, build the test set, build the containment, ship the walkthrough. Depth over breadth — four projects done well say more than ten done shallow.
