# 🚀 AI PM Developer Portfolio — Vijay Saharan

A working portfolio of AI Product Manager case studies, each shipped as a **walkthrough you can actually run on your laptop**: use case → sample data → before-LLM solution → with-LLM solution → defects exposed → containment fix → utility math.

The portfolio is live in three tiers. **Three flagships are fully built** with sample data, four step scripts each, and clickable Streamlit prototypes. **Seven more are on the roadmap**, each scoped with the bleed, the deficiency, and the utility-math formula it'll use when built.

---

## 📐 The thesis

I price product impact by one formula:

> **Utility = (my solution − current state of the art) × number of people it affects**

Reducing a metric by 71% is not an outcome. *Reducing a metric by 71% across 14 million customer interactions per year is.* Every case study below leads with the multiplied number, not the percentage.

That framing also forces honesty about three things most AI portfolios fudge: what the SOTA actually is, what the lift actually is, and how big the population actually is. If any of those numbers is shaky, the utility number is shaky, and the value story falls apart.

---

## 🚀 The Three Flagships (live)

These are the polished case studies — full walkthrough README, sample data CSVs, four step-by-step Python scripts (`step_01_*.py` through `step_04_*.py`), a clickable Streamlit prototype, utility math, CHANGELOG with admitted mistakes, and a PRD.

| Flagship | What it does | Utility delivered | Live demo |
| --- | --- | --- | --- |
| **🛡️ [HalluGuard](./03-hallucination-containment/)** — Bank chatbot hallucination containment | Wraps deployed chatbots; catches 8 named foundation-model failure modes (paraphrase blindness, negation flip, multi-hop, citation fabrication, …); routes low-confidence to abstention | ~3.85M wrong answers prevented per year (partner bank); ~40M at fleet scale | [Streamlit (coming)](#) |
| **🛰️ [DriftSentinel](./01-model-drift-sentinel/)** — Production model drift & decay | Three-loop sentinel (Detect → Diagnose → Decide) over the credit / fraud / AML / GenAI fleet; auto-assembles MRM evidence bundle | Drift MTTD 78d → 9d × ~1,200 production models = ~83,000 model-decay-days prevented annually at fleet scale; $14M/yr modeled prevented loss | [Streamlit (coming)](#) |
| **🏢 [LeaseGuard](./09-cre-lease-abstraction-detector/)** — CRE lease abstraction error detector | Ensemble verification (primary model + re-extraction + rule-based) over deployed lease-NLP outputs; catches CAM caps, escalation clauses, and tenant rights buried in non-standard / redlined leases | Per-lease accuracy 88% → 98.2%; ~$4.2M/yr modeled recovered rent at 220-asset partner; ~$95M/yr at national-operator scale | [Streamlit (coming)](#) |

Run any flagship on your laptop:

```bash
cd <flagship-folder>/src
pip install -r requirements.txt
python step_01_*.py    # before
python step_02_*.py    # with LLM
python step_03_*.py    # defects exposed
python step_04_*.py    # the fix
streamlit run app.py   # interactive demo
```

---

## 🧩 The Roadmap (7 more, scoped and queued)

Each of these has a placeholder folder with the bleed, the named model deficiency, the use case sketch, and the utility-math formula. They get built in the same flagship format on the schedule below.

| # | Project | Domain | Scoped utility | Target |
| --- | --- | --- | --- | --- |
| 02 | **🧪 [EvalForge](./02-eval-first-console/)** — Eval-First Console for Regulated AI | AI Platform / QA | < 2% post-deployment regression vs. ~14% SOTA × 12-20 GenAI features per Tier-1 BFSI shop | Q3 2026 |
| 04 | **🤖 [AgentWatch](./04-agent-reliability-console/)** — Agent Reliability & Tool-Use Observability | AI Platform / Ops | Runaway $/incident → 0; MTTR 4h → 10min × every deployed agent | Q3 2026 |
| 05 | **🛡️ [PromptShield](./05-prompt-injection-defense/)** — Prompt-Injection & Egress Defense | AI Platform / Security | Detection 30-50% → 96%+ × every internal copilot over confidential data | Q3 2026 |
| 06 | **💰 [InferenceLens](./06-inference-economics/)** — Inference Economics Dashboard | AI Platform / FinOps | 0% → 100% per-feature cost visibility; ~25-30% modeled spend reduction | Q4 2026 |
| 07 | **👥 [OversightOps](./07-hitl-designer/)** — HITL Workflow Designer | AI Platform / Governance | Rubber-stamp rate ~94% → ≤4%; review SLA 24h+ → 35min × every HITL pipeline | Q4 2026 |
| 08 | **📜 [LineageLog](./08-ai-audit-trail/)** — AI Audit Trail & Decision Lineage | BFSI / Compliance | Time-to-audit-evidence 14d → 12min × every regulated AI decision (50-200M/yr at Tier-1 retail bank) | Q4 2026 |
| 10 | **🏗️ [DealSentry](./10-cre-underwriting-reliability/)** — CRE AI Underwriting Reliability | CRE / PropTech | Comp-fabrication 12-18% → <1% × 800-1,200 deals/yr screened | Q4 2026 |

---

## 💡 How to Navigate

**If you're a hiring manager who wants the punchline:** read the master flagship — [HalluGuard](./03-hallucination-containment/) — top to bottom. It's a 15-minute read with the walkthrough format, the 8-deficiency taxonomy, the LoRA training trail, the utility math, and the CHANGELOG with admitted mistakes.

**If you're a technical reviewer:** pick any flagship, `cd <folder>/src`, install requirements, run the four step scripts in order. Each writes a CSV to `out/`. Then `streamlit run app.py` for the interactive view.

**If you're a non-technical reader:** every flagship walkthrough is designed to be read with the code blocks skipped. The plain-English explanations and the output tables tell the story.

**If you're triaging the 7 roadmap projects:** each placeholder has the bleed paragraph, the named deficiency, and the utility-math formula. Pick the one closest to your problem and ask me to prioritize building it.

---

## 🏛️ Reference frameworks the portfolio aligns to

These products don't exist in isolation. Each one slots into a published industry framework or reference architecture. When I'm in front of a CISO or a Head of AI, this is the conversation that turns the portfolio into procurement-ready conversation.

- **Google Cloud — *Building secure multi-agent systems on Google Cloud*** (Anirudh Kannan, Christine Sizemore, Connor Herriford, et al., 2025) — the cleanest published spec of the defensible multi-agent pattern. Gemini Enterprise Agent Platform, ADK, Agent Identity, Agent Gateway, Model Armor, Agent Registry, the double-guardrail (IAM + semantic). [Project 04 — AgentWatch](./04-agent-reliability-console/), [05 — PromptShield](./05-prompt-injection-defense/), [07 — OversightOps](./07-hitl-designer/), and [08 — LineageLog](./08-ai-audit-trail/) all reference this paper directly and map their controls to its primitives.
- **Google's Secure AI Framework (SAIF)** — model controls + agent controls + supply-chain controls. The framework backbone for projects 04, 05, 07, 08.
- **OWASP LLM Top 10** — LLM01 Prompt Injection, LLM09 Misinformation, LLM06 Sensitive Information Disclosure. [Project 03 — HalluGuard](./03-hallucination-containment/) and [05 — PromptShield](./05-prompt-injection-defense/) anchor here.
- **NIST AI RMF + EU AI Act Article 12** — decision-grain lineage requirements. [Project 08 — LineageLog](./08-ai-audit-trail/) is the implementation surface.
- **SR 11-7 (Federal Reserve Supervisory Letter on Model Risk Management)** — ongoing-monitoring requirement. [Project 01 — DriftSentinel](./01-model-drift-sentinel/) is the implementation surface.
- **The eval-first thesis** — Hamel Husain, Karpathy, Greg Kamradt's needle-in-haystack work, Lilian Weng on LLM patterns. Cited in [Project 02 — EvalForge](./02-eval-first-console/) and the [HalluGuard probe taxonomy](./03-hallucination-containment/probes/).

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

## 🎯 Career Goal

Sr / Principal Product Manager at an AI-first BFSI org, AI platform team, or PropTech operator — where the work is shipping production AI under regulated constraint (drift, evals, hallucination, agent reliability, audit lineage) and where my dual context (enterprise AI delivery + commercial real estate investment) gets used, not parked.

---

## 👤 Author

**Vijay Saharan** · Sr Product Manager · AI in BFSI · Enterprise AI Platforms · Commercial Real Estate

- **LinkedIn:** [linkedin.com/in/vijaysaharan](https://www.linkedin.com/in/vijaysaharan/)
- **Resume:** `./resume/Vijay_Saharan_Resume.pdf` *(drop your latest PDF in the `/resume` folder before pushing — link goes live)*
- **Email:** open to inbound from hiring managers and recruiters; LinkedIn DM is the fastest path

**Certifications — 500+ total, distributed across:**

| Domain | Approx. count | Anchors |
| --- | --- | --- |
| Cloud (AWS / GCP / Azure) | ~140 | Solutions Architect, ML Engineer, AI Practitioner, Security Specialty |
| AI / ML (Anthropic, OpenAI, Google AI, Databricks) | ~95 | Anthropic API, OpenAI Production, Vertex AI, Databricks ML Practitioner |
| Program / Project Management (PMI, Scaled Agile, Scrum) | ~80 | PMP, PMI-ACP, SAFe Agilist, SAFe Product Owner / Product Manager, CSM, CSPO |
| BFSI domain (risk, compliance, fintech, payments) | ~110 | NACD CERT, GARP / FRM modules, ABA AI in Banking, Reg E / Reg Z / SR 11-7 short courses |
| Commercial real estate (CCIM, NAIOP, ULI tracks) | ~75 | CCIM 101/102, NAIOP Underwriting, ULI Capital Markets, Yardi/Argus operator certs |

The certs are the audit trail of how I've stayed current across the regulated-AI + CRE + program-management lanes. They're not a substitute for shipped work — the projects in this repo are.

**Delivery experience that aligns to typical Sr / Principal PM job specs:**

- **Agile / SAFe at scale.** Multi-team release trains, dependency mapping across 5+ squads, sprint-zero through cutover. SAFe Product Manager + PO certified; have run PI Planning sessions in BFSI program contexts.
- **Regulated AI delivery lifecycle.** SR 11-7, NIST AI RMF, EU AI Act Article 12 — these aren't names I learned for this README. I've shipped through MRM committees, OCC exams, and FRB horizontal reviews.
- **Program management heritage.** PMP, multi-year multi-million-dollar programs in BFSI. The discipline shows up in every project's Rollout table and RACI.
- **Dual context.** Enterprise AI delivery + active commercial real estate investment practice. Projects 09 and 10 are not academic — they're the same product muscle applied to a portfolio I'm an LP in.

**Why this maps to AI-first BFSI Sr / Principal PM specs:**

- Owning AI roadmap under regulated constraint? → [DriftSentinel](./01-model-drift-sentinel/), [HalluGuard](./03-hallucination-containment/), [LineageLog](./08-ai-audit-trail/) all start with the deficiency taxonomy and end at MRM attestation.
- Shipping copilots / agents into production? → [HalluGuard](./03-hallucination-containment/), [AgentWatch](./04-agent-reliability-console/), [PromptShield](./05-prompt-injection-defense/) cover the four production failure classes (hallucination, agent reliability, prompt injection, observability).
- FinOps / inference-cost ownership? → [InferenceLens](./06-inference-economics/) is the spec.
- Cross-functional with risk, compliance, infosec? → Every PRD in this repo names the line-1 / line-2 / line-3 stakeholders explicitly and tracks a stakeholder map.

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

This grows. The three flagships are the foundation. The seven roadmap projects fill in over Q3-Q4 2026, and the next batch after that is queued (foundation-model regression detection, long-context fidelity probes, schema-drift detection for tool-calling agents). Each new project follows the same shape: pick a bleed, name the deficiency, build the test set, build the containment, ship the walkthrough.

Watch this repo. The pattern is: deep over wide. Three projects done excellently puts you in top 1%. Ten done mediocrely puts you nowhere.
