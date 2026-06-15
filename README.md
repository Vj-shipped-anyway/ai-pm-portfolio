# 🚀 AI PM Developer Portfolio — Vijay Saharan

A working portfolio of AI Product Manager case studies, each shipped as a **walkthrough you can actually run on your laptop**: use case → sample data → before-LLM solution → with-LLM solution → defects exposed → containment fix → utility math.

The portfolio is live in one tier. **All ten flagships are fully built** with sample data, four step scripts each, and a static `demo.html` (LeaseGuard, HalluGuard, DriftSentinel, EvalForge, LineageLog, AgentWatch, PromptShield, DealSentry, OversightOps, and now InferenceLens).

---

## 📌 Note on framing

These are **portfolio prototypes** — not production case studies. The deficiency taxonomies, architectures, RICE backlogs, schemas, and walkthroughs reflect how I'd approach these problems as a Senior PM, not work I shipped at a named bank.

Where I cite SR 11-7, NIST AI RMF, OWASP LLM Top 10, EU AI Act Article 12, OCC supervisory guidance, and similar frameworks, those are the standards the work would have to meet — they are not engagements I led through. The synthetic data, prototype code, deficiency analysis, architecture diagrams, and PRDs are mine; the production validation (MRM committee read, OCC exam, FRB horizontal review, validator co-design, fleet rollout) is what the next role does.

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

## 🚀 The Ten Flagships (live)

These are the polished case studies — full walkthrough README, sample data CSVs, four step-by-step Python scripts (`step_01_*.py` through `step_04_*.py`), utility math, and a PRD.

| Flagship | What it does | Utility delivered | Live demo |
| --- | --- | --- | --- |
| **🛡️ [HalluGuard](./01-halluguard-bank-chatbot-safety/)** — Bank chatbot hallucination containment | Wraps deployed chatbots; catches 8 named foundation-model failure modes (paraphrase blindness, negation flip, multi-hop, citation fabrication, …); routes low-confidence to abstention | 🟢 100% wrong-answer cut on the 80-probe synthetic stress test in this repo · 🟡 ~3.85M wrong answers/yr prevented at a modeled mid-tier US bank shape (~$40B-asset, ~2.4M retail customers, ~6 chats/customer/yr); ~40M at Tier-1 fleet scale | **▶ [Live demo](https://halluguard-bfsi.streamlit.app)** · **▶ [60-sec walkthrough](https://app.arcade.software/share/daLEfWH7yD0sYutT3HTP)** |
| **🛰️ [DriftSentinel](./02-driftsentinel-model-drift-monitoring/)** — Production model drift & decay | Three-loop sentinel (Detect → Diagnose → Decide) over the credit / fraud / AML / GenAI fleet; auto-assembles MRM evidence bundle | 🟡 Drift MTTD 78d → 9d (modeled — assumes the synthetic 90-day shipped data and a Tier-1-style fleet) × ~1,200 production models = ~83,000 model-decay-days/yr prevented at Tier-1 fleet scale; 🟡 ~$14M/yr modeled prevented loss at the $50B-asset bank shape (assumes 8-model fleet, MTTD compression, published loss-per-quarter-of-decay benchmarks) | **▶ [Live demo](https://driftsentinel-bfsi.streamlit.app)** · **▶ [60-sec walkthrough](https://app.arcade.software/share/mHOnNZCi66FsK0IFyiLs)** |
| **🏢 [LeaseGuard](./03-leaseguard-cre-lease-verification/)** — CRE lease abstraction error detector | Ensemble verification (primary model + re-extraction + rule-based) over deployed lease-NLP outputs; catches CAM caps, escalation clauses, and tenant rights buried in non-standard / redlined leases | 🟢 6/6 hard-case leases caught in the synthetic eval set · 🟡 88% → 98.2% per-lease accuracy projected at portfolio scale (assumes 220-asset retail-and-office mix, paralegal triage clears flagged fields); 🟡 ~$4.2M/yr modeled recovered rent at the 220-asset shape; ~$95M/yr at national-operator scale | **▶ [Live demo](https://leaseguard-cre.streamlit.app)** · **▶ [60-sec walkthrough](https://app.arcade.software/share/hQWTvQIAmgkpQgjHC7iP)** |
| **🧪 [EvalForge](./04-evalforge-llm-eval-platform/)** — Eval-first console for regulated AI | Versioned probe sets + calibrated rubrics + cross-vendor LLM-as-judge + CI gate (GitHub Actions / Argo CD pre-deploy hook) that blocks the deploy on regression | 🟢 Both silent vendor-snapshot updates in the 50-run synthetic dataset blocked on first eval run; 🟡 silent post-deploy regression rate 14% → <2% (modeled — assumes the published BFSI baseline and the Tier-1-shaped GenAI fleet) × 12-20 customer-facing GenAI features per Tier-1 BFSI shop = 🟡 ~25-40 silent regressions prevented per year at fleet scale; tens of thousands to hundreds of thousands of bad responses caught before customer impact | **▶ [Live demo](https://evalforge-bfsi.streamlit.app)** *(placeholder)* · **▶ [60-sec walkthrough](https://app.arcade.software/share/evalforge-placeholder)** *(placeholder)* |
| **🔍 [LineageLog](./09-lineagelog-ai-decision-audit/)** — AI decision audit trail & decision lineage | Immutable decision-grain composition layer that binds Cloud Logging + Cloud Audit Logs + Agent Identity Logs + OpenTelemetry traces at `(decision_id, customer_id_hash, timestamp)`; six-deficiency taxonomy closed; auto-assembled exam-pack export | 🟢 6 of 6 deficiencies closed on every decision in the 200-decision synthetic corpus; 🟢 composition latency <50ms per decision on the prototype; 🟡 audit-pack assembly time 3 weeks → 3 seconds (modeled — assumes the synthetic 200-decision corpus + Tier-1-style four-model fleet); 🟡 exam-readiness coverage 22% → 100% (modeled — assumes published BFSI baseline for sample-based vs continuous readiness); 🔴 time-to-decision-evidence 14d → 12min (designed) × 🟡 50-200M regulated AI decisions/yr at Tier-1 retail bank = continuous exam-readiness | **▶ [Live demo](https://lineagelog-bfsi.streamlit.app)** *(placeholder)* · **▶ [60-sec walkthrough](https://app.arcade.software/share/lineagelog-placeholder)** *(placeholder)* |
| **🤖 [AgentWatch](./05-agentwatch-agent-observability/)** — Agent reliability & tool-use observability | Sidecar over LangGraph / AutoGen / Bedrock Agents / OpenAI Assistants; classifies failure under a six-deficiency taxonomy (runaway tool loops, hallucinated tool args, silent drift, blast-radius unbounded, missing reasoning trace, cost detached from outcomes); enforces per-incident dollar cap; auto-assembled incident pack routed to SRE on-call + line-1 owner | 🟢 24 of 24 detected incidents bounded on the 500-run synthetic corpus; 🟢 composition latency <50ms per incident on the prototype; 🟢 headline runaway capped at $4,218 vs. modeled $42k+ undetected bleed; 🟡 APM-only detection rate ~25% → AgentWatch 100% (modeled — assumes Datadog with standard p99 thresholds); 🔴 MTTR 4h+ → <10min (designed) × 🟡 8-20 deployed agents at Tier-1 BFSI fleet scale = ~24 runaways/yr bounded ($120k - $1.2M of bounded spend) | **▶ [Live demo](https://agentwatch-bfsi.streamlit.app)** *(placeholder)* · **▶ [60-sec walkthrough](https://app.arcade.software/share/agentwatch-placeholder)** *(placeholder)* |
| **🛡️ [PromptShield](./06-promptshield-prompt-injection-defense/)** — Prompt-injection & egress defense for internal BFSI copilots | Five-layer defense-in-depth gateway between user input and the LLM: L1 input classifier (Llama Guard 3 / fine-tuned DeBERTa), L2 retrieval scanner (catches indirect injection in retrieved RAG content), L3 tool-call gate (OPA / Rego), L4 egress filter (DLP regex pack), L5 per-session memory boundary (Redis + SPIFFE); six-class deficiency taxonomy (direct, indirect, tool-call abuse, egress, cross-session leak, jailbreak) closed | 🟢 99% catch rate on the 100-prompt synthetic attack suite (measured) vs. ~37% on regex baseline; 🟢 1% false-positive rate on the 200-prompt legitimate-banker corpus; 🟢 100% accuracy on the 50-call tool-gate ground-truth set; 🟡 modeled production catch 96%+ at 4% FP (assumes fine-tuned classifier replaces the regex pack + continuous red-team probes); 🔴 designed data-exfiltration incidents → 0 × 🟡 4-12 internal copilots over confidential data at every Tier-1 BFSI shop = modeled $4-15M of prevented loss per confirmed customer-data breach avoided | **▶ [Live demo](https://promptshield-bfsi.streamlit.app)** *(placeholder)* · **▶ [60-sec walkthrough](https://app.arcade.software/share/promptshield-placeholder)** *(placeholder)* |
| **💰 [InferenceLens](./07-inferencelens-inference-finops/)** — Per-feature inference economics for the BFSI GenAI portfolio | Per-feature inference-economics layer over OpenTelemetry span attributes + vendor billing-API reconcile; five derived views (per-feature attribution, runaway detection, cheaper-model substitution recommender, dead-feature flagger, per-feature ROI ranking); six-deficiency taxonomy (no per-feature attribution, no per-tenant attribution, no runaway detection, no substitution recommender, no dead-feature flagger, no per-feature ROI) closed | 🟢 6 of 6 deficiencies closed on every feature in the 18-feature synthetic fleet; 🟢 all five derived views composed in <10ms on the prototype; 🟢 headline runaway (FT_001 retrieval-depth misconfig) flagged day 1 with modeled overspend ~$195k caught vs. 45 days undetected; 🟢 $301,800/mo of substitution savings surfaced across 6 candidates; 🟢 dead-feature spend $25,991/mo flagged on FT_009; 🟡 modeled fleet-scale spend reduction 25-30% (assumes typical Tier-1 BFSI portfolio shape) × 🟡 $8-30M/yr aggregate inference spend at Tier-1 BFSI scale = **~$2-9M/yr saved** | **▶ [Live demo](https://inferencelens-bfsi.streamlit.app)** *(placeholder)* · **▶ [60-sec walkthrough](https://app.arcade.software/share/inferencelens-placeholder)** *(placeholder)* |
| **👥 [OversightOps](./08-oversightops-hitl-workflow/)** — HITL workflow designer | Calibrated, role-aware human-in-the-loop layer: difficulty-stratified routing (case + AI confidence + customer tier + country risk), rubber-stamp blocker (tier-specific time-on-task floor), reviewer calibration drift detection, escalation path for hard cases, SLA-by-tier with timer engagement, ground-truth feedback loop closed via downstream signals (SAR / OFAC / CFPB / charge-off) | 🟢 6 of 6 deficiencies closed on every case in the 1,000-case synthetic KYC corpus; 🟢 composition latency ~0.13ms per case on the prototype; 🟢 125 rubber-stamps blocked of 125 sub-floor private-banking reviews; 🟡 Tier-1 rubber-stamp rate 94% → 4% (modeled — assumes published BFSI baseline + OversightOps blocker engaged on Tier-1 queues); 🟡 reviewer-vs-ground-truth divergence 38% → 8% (modeled — assumes the 6-12-month tail + calibration packet engaged weekly); 🔴 Tier-1 KYC review SLA 9s → 8 min (designed) × 🟡 every regulated AI workflow with a HITL step (typical Tier-1: 6-15 such pipelines × thousands of high-stakes decisions per year per pipeline) = real oversight instead of theatrical | **▶ [Live demo](https://oversightops-bfsi.streamlit.app)** *(placeholder)* · **▶ [60-sec walkthrough](https://app.arcade.software/share/oversightops-placeholder)** *(placeholder)* |
| **🏗️ [DealSentry](./10-dealsentry-cre-underwriting/)** — CRE AI underwriting reliability | Three-path verifier behind the AI underwriting copilot: comp existence (CoStar / Reonomy / Cherre dereference), symbolic re-run (pandas + sympy for T-12 / cap rate / occupancy / exit-cap spread), submarket-stat cross-feed; six-class deficiency taxonomy (comp fabrication, T-12 rollforward, stat staleness, cap-rate math, occupancy discrepancy, exit-cap mismatch) closed | 🟢 100% catch on 6 designed deficiencies across the 6-memo eval set vs. 0% on face-value trust and ~28% on analyst spot-check (10% sample); 🟢 $6.78M bid risk caught on the synthetic eval set; 🟡 ~28% → 100% catch on fabricated comps × ~800-1,200 deals/yr screened at a national CRE operator = 🟡 ~3-5 bad bids/yr prevented × ~$1.8M each ≈ **~$7.2M/yr modeled**; 🟡 at top-5 institutional fleet scale (~$25B+ AUM): ~15-25 bad bids/yr ≈ ~$35M/yr modeled; 🟡 per-memo verifier runtime <90s p95 | **▶ [Live demo](https://dealsentry-cre.streamlit.app)** *(placeholder)* · **▶ [60-sec walkthrough](https://app.arcade.software/share/dealsentry-placeholder)** *(placeholder)* |

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

**If you're a hiring manager who wants the punchline:** read the master flagship — [HalluGuard](./01-halluguard-bank-chatbot-safety/) — top to bottom. It's a 15-minute read with the walkthrough format, the 8-deficiency taxonomy, the LoRA training trail, and the utility math.

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
- **SR 11-7 (Federal Reserve Supervisory Letter on Model Risk Management)** — ongoing-monitoring requirement. [Project 02 — DriftSentinel](./02-driftsentinel-model-drift-monitoring/) is the implementation surface.
- **The eval-first thesis** — Hamel Husain, Karpathy, Greg Kamradt's needle-in-haystack work, Lilian Weng on LLM patterns. Cited in [Project 04 — EvalForge](./04-evalforge-llm-eval-platform/) and the [HalluGuard probe taxonomy](./01-halluguard-bank-chatbot-safety/probes/).

The phrase that sells this in BFSI: *"Each project is the implementation surface for a published framework regulators and Google have already endorsed."* The portfolio isn't proposing new compliance; it's the missing product layer between the framework and the production system.

---

## 🛠️ Tech Stack across the portfolio

| Layer | What I use |
| --- | --- |
| **Foundation models** | Anthropic Claude Sonnet 4 (default), Azure OpenAI gpt-4o, fine-tuned Llama 3.1 8B / Mistral 7B for in-VPC workloads |
| **Fine-tuning** | LoRA via PEFT (HalluGuard verifier: rank 16, alpha 32, 4× A100 for 6 hours, $182 end-to-end) |
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

The ten flagships are the foundation. Future candidates being scoped: foundation-model regression detection, long-context fidelity probes, schema-drift detection for tool-calling agents.

Each new project follows the same shape: pick a bleed, name the deficiency, build the test set, build the containment, ship the walkthrough. Depth over breadth — four projects done well say more than ten done shallow.
