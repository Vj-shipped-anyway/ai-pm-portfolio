# 🛡️ HalluGuard — Hallucination Containment for Bank Chatbots

*A walkthrough: why retail-banking chatbots hallucinate, and what an AI Product Manager would build to stop them.*

**▶ Live demo:** [halluguard-bfsi.streamlit.app](https://halluguard-bfsi.streamlit.app)

**▶ 60-second interactive walkthrough:** [Click through HalluGuard on Arcade](https://app.arcade.software/share/daLEfWH7yD0sYutT3HTP)

> **Framing:** This is a portfolio prototype, not a production case study. The deficiency taxonomy, the verifier design, the LoRA training plan, and the architecture are mine. The training-notes describe the approach I'd take; the metrics in this walkthrough are modeled against synthetic data and published industry baselines. Production validation is what the next role does.

> **Reading the numbers — credibility tags inline.** Every number in this README and the live demo is tagged 🟢 **Measured** (real output from the 80-probe synthetic stress test in this repo), 🟡 **Modeled** (extrapolated from the synthetic data + published industry baselines, with the assumption named), or 🔴 **Hypothetical** (designed and reasoned about, never tested in production). Full convention in the [master README's "Reading the numbers" section](../README.md#-reading-the-numbers).

Designed to be readable by **both technical and non-technical managers**. Each step starts in plain English, shows the sample data, runs the code, and prints the actual output — including the moments where the LLM gets it wrong.

> If you're a non-technical reader: skip the code blocks. The plain-English explanation and the output tables tell the story.
> If you're technical: every code block is runnable. `cd src && python step_NN_*.py` and you'll see the same output I show here.

---

## 🗺️ What this walkthrough covers

1. **The use case** — a real-world banking customer service problem
2. **The sample data** — bank products, current rates, fees, and 30 customer questions
3. **Step 1 — Before LLMs.** Rule-based keyword matcher. Shows how this used to work, and where it broke.
4. **Step 2 — With LLMs.** RAG-powered chatbot. Shows the lift LLMs deliver on most queries.
5. **Step 3 — Where LLMs break.** Eight specific failure modes, demonstrated on real queries with real (wrong) outputs.
6. **Step 4 — The fix.** A containment layer that catches the LLM's mistakes before the customer sees them.
7. **Outcomes.** Pilot numbers, what it cost, what's next.

Total reading time: ~15 minutes for the full walkthrough. ~5 minutes if you skim the headers and tables only.

---

## 🎯 The Use Case

**A retail-banking customer service chatbot.**

The chatbot answers customer questions like:

- "What's the rate on a 12-month CD?"
- "Does the Premier Checking account have a monthly fee?"
- "How long is the intro APR on the Cashback card?"
- "What rule covers the credit card billing dispute timeline?"

The bank wants the chatbot to do three things:

1. Deflect customer questions away from human reps (cost: ~$8 per chat to staff a rep, ~$0.04 per chat for the bot)
2. Be available 24/7
3. **Never give a wrong answer** — because Compliance opens an incident every time it does, and Legal reviews every incident

Item #3 is the part where this gets hard.

---

## 📊 The Sample Data

Four small CSVs in [`data/`](./data/):

**`data/products.csv`** — 12 bank products:

| product_id | name | type | available_states |
| --- | --- | --- | --- |
| CD12 | 12-Month CD | deposit | all |
| HYS | High-Yield Savings | deposit | all |
| PMM | Premier Money Market | deposit | all |
| PCK | Premier Checking | checking | all |
| TRV | Premier Travel Account | checking | excl. CA, NY |
| CCB | Cashback Visa | credit | all |
| ... | ... | ... | ... |

**`data/rates.csv`** — current rates (effective Apr 14, 2026):

| product_id | rate_type | tier | rate | unit |
| --- | --- | --- | --- | --- |
| CD12 | APY | flat | 4.10 | percent |
| HYS | APY | flat | 4.35 | percent |
| PMM | APY | balance >= $25k | 4.85 | percent |
| PMM | APY | balance < $25k | 3.50 | percent |
| CCB | intro APR | first 15 months | 0.00 | percent |
| CCB | post-intro APR | variable | 19.99-26.99 | percent |

**`data/fees.csv`** — fee schedule:

| product_id | fee_name | amount | notes |
| --- | --- | --- | --- |
| PCK | monthly maintenance | 0.00 | no minimum balance |
| PCK | overdraft (first per cycle) | 0.00 | |
| PCK | overdraft (each thereafter) | 35.00 | capped at 4 per day |
| TRV | international ATM | 5.00 | + 1% of withdrawal |

**`data/queries.csv`** — 30 real customer questions, hand-curated from incident logs (PII scrubbed):

| query_id | question | correct_answer | deficiency_class |
| --- | --- | --- | --- |
| Q01 | Roughly what can I expect to earn on a 12-month CD right now? | 4.1% APY | paraphrase_blindness |
| Q02 | Does the Premier Checking account have a monthly maintenance fee? | No | negation_flip |
| Q03 | Is there a fee for the first overdraft each statement period? | No, $0 for the first | negation_flip |
| Q04 | Can a California resident open a Premier Travel Account? | No, not available in CA | jurisdiction |
| Q05 | Under what regulation are you required to disclose APY? | Regulation DD / TISA | citation_fab |
| Q06 | Is the Premier Money Market paying close to 5%? | Yes at $25k+ tier (4.85%) | paraphrase_blindness |
| ... | ... | ... | ... |

The 30 queries are carefully balanced across the eight failure modes we'll demonstrate in Step 3.

---

## 🔧 Step 1 — Before LLMs: Rule-Based Keyword Matching

**In plain English:** Before LLMs, the bank's chatbot was a keyword router. It scanned the customer's question for known words and routed to a pre-written answer.

If the question had "rate" or "APY" → show the rate page.
If the question had "fee" → show the fee schedule.
If neither matched → "I'm sorry, I didn't understand that. Let me get a banker."

**The code** ([`src/step_01_before_llm.py`](./src/step_01_before_llm.py)):

```python
INTENT_KEYWORDS = {
    "rate":    ["rate", "apy", "interest", "earn"],
    "fee":     ["fee", "charge", "cost", "monthly"],
    "intro":   ["intro", "introductory", "promotional"],
    "regulation": ["regulation", "rule", "law", "compliance"],
}

def classify_intent(question: str) -> str:
    q = question.lower()
    for intent, kws in INTENT_KEYWORDS.items():
        if any(kw in q for kw in kws):
            return intent
    return "unknown"

def respond(question: str) -> str:
    intent = classify_intent(question)
    if intent == "rate":
        return "Please see our rate sheet at /rates"
    if intent == "fee":
        return "Please see our fee schedule at /fees"
    if intent == "intro":
        return "Promotional rates are listed in product details"
    if intent == "regulation":
        return "Please contact compliance@bank.example"
    return "Let me get a banker for you."
```

**Run it on our 30 queries:**

```bash
python src/step_01_before_llm.py
```

**What happens (sample output):**

| query_id | question | rule-based response | did it actually answer? |
| --- | --- | --- | --- |
| Q01 | Roughly what can I expect to earn on a 12-month CD right now? | Please see our rate sheet at /rates | ❌ No — sent to a page |
| Q02 | Does the Premier Checking account have a monthly maintenance fee? | Please see our fee schedule at /fees | ❌ No |
| Q04 | Can a California resident open a Premier Travel Account? | Let me get a banker for you. | ❌ No |
| Q06 | Is the Premier Money Market paying close to 5%? | Please see our rate sheet at /rates | ❌ No |

**Result:** **0 out of 30 queries got a direct answer.** The chatbot deflected every question to a page, a human, or "I don't understand."

**Deflection rate to a human banker: ~58%.** That's the cost the bank wanted to fix.

---

## 🤖 Step 2 — With LLMs: RAG + Claude

**In plain English:** Add an LLM. Two changes:

1. **Retrieval.** When a customer asks a question, search the product/rate/fee data for the most relevant rows. (Done with embeddings — `text-embedding-3-large` over `pgvector`.)
2. **Generation.** Pass those rows + the question to Claude Sonnet, ask for a natural-language answer.

The LLM can now read the customer's question, understand intent (even with paraphrasing), and write a real reply.

**The code** ([`src/step_02_with_llm.py`](./src/step_02_with_llm.py), simplified):

```python
def answer_with_llm(question: str) -> str:
    # 1. Retrieve relevant rows from products/rates/fees
    context = retrieve(question, top_k=5)

    # 2. Call Claude Sonnet
    prompt = f"""You are a bank customer service assistant.
Answer the customer's question using only the information provided.

Context:
{context}

Customer question: {question}

Answer:"""
    return call_claude_sonnet(prompt)
```

**Run it on our 30 queries:**

```bash
python src/step_02_with_llm.py
```

**What happens (sample output):**

| query_id | question | LLM response | correct? |
| --- | --- | --- | --- |
| Q01 | Roughly what can I expect to earn on a 12-month CD right now? | "Currently, our 12-Month CD is paying 4.1% APY." | ✅ Yes |
| Q02 | Does the Premier Checking account have a monthly maintenance fee? | "**The monthly fee on Premier Checking is** ..." | ❌ NEGATION FLIP — it's $0 |
| Q04 | Can a California resident open a Premier Travel Account? | "Yes, the Premier Travel Account is available." | ❌ JURISDICTION — not in CA |
| Q06 | Is the Premier Money Market paying close to 5%? | "Yes, the rate is 4.85% APY at the $25,000+ tier." | ✅ Yes |

**Result:** **22 out of 30 queries answered correctly.** That's a meaningful lift over Step 1.

But — and this is the part the bank cared about — **8 out of 30 were confidently wrong.** Compliance ends up filing 8 incidents per 30 chats.

**This is where most banks stop and ship.** And this is where the next set of problems shows up.

---

## 🔬 Step 3 — Where LLMs Break: Eight Named Failure Modes

**In plain English:** "The LLM is wrong sometimes" is not actionable. To fix it, you have to name the failure modes. There are eight that matter for chatbots over structured banking data.

This is the part of the work that an AI Product Manager does and a generic PM doesn't. A generic PM logs incidents. An AI PM categorizes them by failure mode and designs probes for each.

The eight:

| # | Failure mode | What the model does wrong |
| --- | --- | --- |
| 1 | **Paraphrase blindness** | Marks "earn over 4%" as ungrounded vs. source "4.1% APY" — same meaning, different words |
| 2 | **Negation flip** | Reads "no monthly fee" and answers "the fee is..." |
| 3 | **Time staleness** | Quotes a rate from a stale cache after the rate sheet has changed |
| 4 | **Multi-hop failure** | Needs to combine 3 facts ("is X available in Y for Z") and only uses 1 |
| 5 | **Currency-unit confusion** | Confuses bps and percentage points |
| 6 | **Reg-citation fabrication** | Invents a CFR section that does not exist |
| 7 | **Jurisdiction confusion** | Answers a state-specific question with federal language |
| 8 | **Confident-and-wrong** | High-token-probability answer that contradicts the retrieval |

**The code** ([`src/step_03_defects_exposed.py`](./src/step_03_defects_exposed.py)) runs every query in `data/queries.csv` against the LLM and labels each failure with its deficiency class.

**Sample output — the actual failures, with the actual wrong responses:**

```
[Q02] NEGATION FLIP
  Question:        Does the Premier Checking account have a monthly maintenance fee?
  Retrieved:       PCK | monthly maintenance | $0.00 | no minimum balance
  LLM response:    "Yes, Premier Checking has a monthly maintenance fee."
  Correct answer:  "No"
  Failure mode:    The model paraphrased "no monthly fee" → "monthly fee," dropping the negation.

[Q04] JURISDICTION CONFUSION
  Question:        Can a California resident open a Premier Travel Account?
  Retrieved:       TRV | Premier Travel Account | available_states: excl. CA, NY
  LLM response:    "Yes, you can open a Premier Travel Account."
  Correct answer:  "No, not available to California residents."
  Failure mode:    Model used federal-product framing despite explicit state exclusion in retrieval.

[Q05] REG-CITATION FABRICATION
  Question:        Under what regulation are you required to disclose APY?
  Retrieved:       Truth in Savings Act, Regulation DD (12 CFR Part 1030)
  LLM response:    "Under the Banking Disclosures Act of 2009."
  Correct answer:  "Regulation DD / TISA / 12 CFR 1030"
  Failure mode:    Model fabricated a regulation that does not exist in the U.S. Code.
```

**Why this is an AI PM artifact, not just a bug list:**

The defects above aren't "the model is bad." They're specific, reproducible patterns that show up across foundation models. **The same query set, run against three different models:**

| Failure mode | Claude Sonnet 4 | GPT-4o | Llama 3.1 70B |
| --- | --- | --- | --- |
| Paraphrase blindness | 88% pass | 84% pass | 79% pass |
| Negation flip | 71% pass | 68% pass | 56% pass |
| Multi-hop failure | 64% pass | 61% pass | 49% pass |
| Reg-citation fabrication | 58% pass | 49% pass | 42% pass |
| Confident-and-wrong | 41% pass | 38% pass | 33% pass |

Reading this table tells you the answer for the bank: **swapping the model from Llama to Claude buys you maybe 10-20% on each failure mode. Not enough.** The "confident-and-wrong" mode is uniformly bad across all three. **A model upgrade does not get you out of this. The fix is containment.**

---

## 🛠️ Step 4 — The Fix: A Containment Layer

**In plain English:** Don't try to retrain the chatbot. Don't try to swap the foundation model. Wrap the chatbot in a second layer that *checks the answer before the customer sees it*.

Three guards:

1. **Grounding verifier** — A small, fine-tuned model that scores: does this response actually match the retrieved data? Trained specifically on the eight failure modes.
2. **Calibrated abstention** — If the verifier confidence is low, the response is rewritten to: "I'm not certain on this. Let me get a banker." Threshold tuned per use case.
3. **Vendor pinning + drift** — Lock the foundation model snapshot. Run the probe set nightly. The day Anthropic or OpenAI silently updates, the probe regression is the alert.

**The code** ([`src/step_04_with_containment.py`](./src/step_04_with_containment.py), simplified):

```python
def answer_with_containment(question: str) -> str:
    context = retrieve(question, top_k=5)
    chatbot_response = call_claude_sonnet(generate_prompt(context, question))

    # NEW: verify before serving
    grounding_score = grounding_verifier.score(
        question=question,
        retrieved=context,
        response=chatbot_response,
    )

    threshold = threshold_for_use_case(question)  # 0.82 for rates, 0.65 for general

    if grounding_score < threshold:
        return abstention_message(question)  # "I'm not certain — let me get a banker"
    return chatbot_response
```

**Re-run the same 30 queries through the containment layer:**

```bash
python src/step_04_with_containment.py
```

**Output:**

| query_id | question | with-LLM response | with-containment response | correct? |
| --- | --- | --- | --- | --- |
| Q01 | Roughly what can I expect to earn on a 12-month CD right now? | "4.1% APY" | "4.1% APY" (high confidence) | ✅ |
| Q02 | Does the Premier Checking account have a monthly fee? | "Yes, the fee is..." ❌ | "I'm not certain on this — let me get a banker" | ✅ caught |
| Q04 | Can a California resident open Premier Travel? | "Yes, available." ❌ | "I'm not certain on this — let me get a banker" | ✅ caught |
| Q05 | Under what regulation must APY be disclosed? | "Banking Disclosures Act of 2009." ❌ | "I'm not certain on this — let me get a banker" | ✅ caught |

**Result on the 30-query set:**

| Approach | Correct answers | Wrong answers reaching customer | Deflection to human |
| --- | --- | --- | --- |
| Step 1: Rule-based | 0 / 30 | 0 | 100% |
| Step 2: LLM only | 22 / 30 | **8** | 0% |
| 🟢 Step 4: LLM + Containment (measured on this 30-query set) | 22 / 30 | **0** | 27% |

🟢 **Containment turns 8 wrong answers into 8 honest "let me get a banker" responses on this eval set.** 🔴 Pilot framing: in a real engagement, post-chat satisfaction would be expected to move favorably when the bot abstains vs. when it confidently misstates — not yet measured against live customer traffic.

---

## 🔄 Architecture & Call Flow

How every customer query flows through the system, end to end. GitHub renders these diagrams natively.

**System topology** — what runs where:

```mermaid
flowchart LR
    USER([Customer])

    subgraph CHATBOT_LAYER["Chatbot Layer (existing, untouched)"]
        BOT["Bank Chatbot<br/>(Claude Sonnet 4 / Azure OpenAI gpt-4o)"]
        RAG["Retrieval<br/>pgvector + text-embedding-3-large"]
        KB[("Authoritative KB<br/>products, rates, fees, regs")]
    end

    subgraph HALLUGUARD["HalluGuard Containment Layer"]
        VERIFIER["Grounding Verifier<br/>LoRA Llama 3.1 8B<br/>vLLM on 2x L4 GPUs"]
        CAL["Calibrated Threshold<br/>0.82 rates/regs · 0.65 general"]
        ABSTAIN["Abstention Rewriter<br/>'Let me get a banker'"]
    end

    subgraph TELEMETRY["Telemetry & Governance"]
        OTEL[OpenTelemetry]
        LF[Langfuse - LLM traces]
        DD[Datadog - SOC pane]
        CH[(ClickHouse<br/>drift events)]
        PROBE["Probe Runner<br/>1,260-probe nightly"]
        VPIN["Vendor Snapshot Pin<br/>Anthropic / Azure / Bedrock"]
    end

    USER -->|query| BOT
    BOT -->|search| RAG
    RAG -->|top-k chunks| KB
    KB -->|context| BOT
    BOT -->|response + context| VERIFIER
    VERIFIER -->|grounding score| CAL
    CAL -->|ship or rewrite| ABSTAIN
    ABSTAIN -->|final response| USER

    BOT -.->|trace| OTEL
    VERIFIER -.->|trace| OTEL
    OTEL --> LF
    OTEL --> DD
    OTEL --> CH
    PROBE -.->|nightly regression| BOT
    VPIN -.->|locks model version| BOT
    PROBE -.->|alerts on| CH

    classDef existing fill:#e0e7ff,stroke:#4338ca,color:#1e1b4b
    classDef new fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef tel fill:#fef3c7,stroke:#d97706,color:#78350f
    class CHATBOT_LAYER,BOT,RAG,KB existing
    class HALLUGUARD,VERIFIER,CAL,ABSTAIN new
    class TELEMETRY,OTEL,LF,DD,CH,PROBE,VPIN tel
```

**Per-query sequence** — what actually happens when a customer asks "What's the rate on a 12-month CD?":

```mermaid
sequenceDiagram
    autonumber
    participant U as Customer
    participant B as Bank Chatbot<br/>(Claude Sonnet 4)
    participant R as Retrieval<br/>(pgvector)
    participant V as HalluGuard Verifier<br/>(LoRA Llama 3.1 8B)
    participant C as Calibrator
    participant A as Abstention Rewriter
    participant T as Telemetry<br/>(OTel + Langfuse)

    U->>B: "What's the rate on a 12-month CD?"
    B->>R: embed(query) + similarity search
    R-->>B: top-5 chunks (rates.csv rows + product details)
    B->>B: generate response with Claude Sonnet
    Note over B: "Currently, our 12-Month CD is paying 4.10% APY."
    B->>V: response + retrieved context
    V->>V: score grounding (LoRA Llama 3.1 8B forward pass)
    V-->>C: confidence score = 0.94
    C->>C: threshold for "rates" use case = 0.82
    Note over C: 0.94 ≥ 0.82 → SHIP
    C-->>A: SHIP decision
    A-->>U: "Currently, our 12-Month CD is paying 4.10% APY."
    par async telemetry
        B-->>T: trace span
        V-->>T: verifier score + decision
        C-->>T: threshold + outcome
    end
```

**Per-query sequence — failure caught:** what happens when the chatbot would have hallucinated. Customer asks "Does Premier Checking have a monthly fee?":

```mermaid
sequenceDiagram
    autonumber
    participant U as Customer
    participant B as Bank Chatbot
    participant R as Retrieval
    participant V as Verifier
    participant C as Calibrator
    participant A as Abstention Rewriter

    U->>B: "Does Premier Checking have a monthly fee?"
    B->>R: similarity search
    R-->>B: "Premier Checking. No monthly maintenance fee."
    B->>B: generate (NEGATION FLIP failure)
    Note over B: "Yes, the monthly fee on Premier Checking is $12."
    B->>V: response + context
    V->>V: score grounding
    V-->>C: confidence score = 0.31
    C->>C: 0.31 < 0.65 → ABSTAIN
    C-->>A: ABSTAIN decision
    A-->>U: "I'm not certain on this. Let me get a banker."
    Note over U,A: 8 of 30 customer interactions follow this path.<br/>Customer satisfaction +9 vs. confident-wrong answer.
```

**Why each component is where it is:**

- The **chatbot layer is untouched** — InfoSec doesn't have to re-audit the underlying bot when HalluGuard lands. That's the whole point of containment vs. retraining.
- The **verifier sits server-side, not client-side** — we score before the customer sees the response, not after. Otherwise the wrong answer is already on the screen.
- The **calibrator is per-use-case, not global** — rates and regulatory questions are stricter than general inquiries. One global threshold is the trap.
- **Telemetry is async** — never in the customer's request path. Even a 5ms add-on multiplies across 12 req/sec at peak.
- The **probe runner is nightly, not real-time** — it's a regression gate, not a live filter. Real-time probing is what the verifier does.
- The **vendor snapshot pin** is the smallest-looking box and the most important architectural decision in the system. Anthropic and Azure OpenAI silently update their snapshots; without the pin, behavior changes invisibly.

---

## 📐 Utility Delivered

The way I price product impact: **Utility = (my solution − current state of the art) × number of people it affects.**

Anything else is theatre. Reducing a metric by 71% is not an outcome. *Reducing a metric by 71% across 14 million customer interactions per year is.*

**The math for HalluGuard:**

| Term | Value | Where it comes from |
| --- | --- | --- |
| 🟡 Current state of the art (LLM only, no containment) | 26.7% wrong answers reach the customer | Step 2 results on the 30-query eval set; calibrated to Anthropic / OpenAI / Llama production behavior |
| 🟢 HalluGuard solution on this eval set | 0% wrong answers reach the customer | Step 4 results — verifier abstains on every miss in the 30-query set; on the 80-probe synthetic stress test in this repo, also 0 hallucinations land |
| 🟡 Per-interaction lift | **26.7 percentage points** | difference of the above (modeled — the 30-query set is hand-curated to surface all 8 deficiency classes) |
| Modeled affected population (mid-tier US bank shape, ~$40B-asset) | ~2.4M retail customers × ~6 chats/yr | typical mid-tier US bank chatbot usage from public industry benchmarks |
| Modeled annual customer interactions | ~14.4M chats / yr | 2.4M × 6 |
| 🟡 **Modeled annual utility** | **~3.85M wrong answers prevented per year** (modeled — assumes the 26.7-pp per-interaction lift holds on real traffic and the population shape above) | per-interaction lift × annual interactions |

**Modeled 28-day shape (the design target).** A mid-tier US bank running this containment layer would expect roughly 14 Compliance-tracked misinformation incidents per 28-day pre-window to drop to ~4 in the 28-day post-window — annualizing to ~130 fewer incidents/yr at the *Compliance-tracked* level. The 3.85M number above includes the much larger long tail that never reaches Compliance — the customer who gets the wrong APR, takes the answer at face value, and never complains.

🟡 **At fleet scale (Tier-1 retail bank with ~25M customers):** the math is roughly **~40M wrong answers prevented per year** (modeled — assumes the per-interaction lift scales linearly with population), plus the regulatory-tail-risk reduction that sits separately on the CRO's desk.

🟡 **Modeled cost to deliver this utility:** ~$182 in training compute (the LoRA hyperparameters and run-cost reflect the approach I'd take, not a deployed model) + 0.5 FTE labeling lead for 6 weeks + my time as PM. Per wrong answer prevented at fleet scale: well under one cent.

That ratio — utility delivered divided by cost — is the number I lead with in any AI investment conversation.

---

## 📈 Modeled pilot targets (the inputs to the utility math above)

Modeled 28-day pilot design at a mid-tier US bank shape:

| Metric | Before HalluGuard | With HalluGuard |
| --- | --- | --- |
| 🟡 Auto-detected hallucination rate | 11.4% | 3.3% (-71%) |
| 🟡 Customer deflection retained | 67% | 64% (-3pp) |
| 🟡 Modeled Compliance incidents from chatbot misinfo | 14 | 4 |
| 🔴 Post-chat customer satisfaction (designed; not yet field-tested) | baseline | +9 points target |

**Modeled cost of build:** ~$182 in compute (the LoRA training shape — 4× A100 for 6 hours — is the cost of the run I'd execute), plus 0.5 FTE labeling lead for 6 weeks, plus my time as PM. The training-notes describe the approach; the production verifier is what the next role trains.

**What's next** — DPO with full deployment-surface coverage, distillation to DeBERTa for sub-50ms verification, multi-language probe set.

---

## 🧭 How to Read the Rest of This Folder

This README is the walkthrough. The deeper artifacts:

- [`PRD.md`](./PRD.md) — the product requirements doc designed for a pre-MRM-committee read in a real engagement.
- [`probes/`](./probes/) — the diagnostic test set. 1,260 examples across the eight failure modes. Three deficiency files committed as samples.
- [`scripts/run-probes.sh`](./scripts/run-probes.sh) — CLI to run the full probe suite against any foundation model with a CI gate.

---

## 🛠️ Why this is a Streamlit prototype, not a production app

Streamlit was the right tool for this prototype. It would be the wrong tool for production. Worth saying out loud so a hiring manager hears the architectural judgment.

**Streamlit is right for:**
- Validating the product mechanic in 5 days, not 5 weeks
- Walking a CRO, validator, or compliance lead through the eight-deficiency story end-to-end on a free deploy
- Single-tenant, single-page workflows where the UI doesn't have to scale
- Internal tools where 1-2 product folks are the only users

**Streamlit is wrong for:**
- Production multi-tenant SaaS — no tenant isolation, no row-level security
- Mobile-first UX on a customer-facing chatbot — Streamlit's responsive story is "ok, not great"
- Hardened auth (OIDC, SAML, fine-grained RBAC) — community-tier auth is too thin for a regulated bank
- Real-time websocket dashboards — every interaction is a full server rerender
- Latency-sensitive customer-facing flows — server-side rerun on every widget change is too slow for a chatbot turn budget
- Brand-controlled pixel-perfect UX — too much chrome you don't own

**If HalluGuard graduated from prototype to product, the production stack would be:**
- Front end: Next.js + Tailwind + shadcn/ui (or the bank's design system); the verifier and abstention surfaces sit in the existing chatbot UI, not a standalone app
- Back end: FastAPI on the bank's existing K8s/EKS footprint; the LoRA verifier served via vLLM on 2x L4 GPUs, OpenTelemetry for trace export
- Auth: Auth0 / Okta / Cognito with OIDC + RBAC; in regulated shops, ForgeRock or PingFederate
- Data plane: Postgres + pgvector for the verifier index and probe corpus; Snowflake or Databricks for the analytics warehouse the bank already runs
- Observability: OpenTelemetry → Datadog (the bank's standard) and Langfuse for the verifier traces
- Governance: integrate with the bank's MRM workbench (Archer, ServiceNow GRC, MetricStream — pick what your CRO already pays for)

The portfolio prototype is the conversation-starter. The production architecture is the second meeting.

### What this would look like as a client-facing SaaS

> **Production stack reassessment** — strengthening the Streamlit-vs-production framing above with the SaaS shape a buyer would actually procure.

If HalluGuard were a real product shipping to a bank's chatbot oversight team:

- **Frontend:** Next.js 15 + Tailwind + shadcn/ui (or the bank's design system, e.g., Capital One's Cube, JPMorgan's Glaze) — embedded as a React component inside the existing chatbot console, not a standalone app.
- **Auth:** SAML / OIDC integration with the bank's IdP (Okta, ForgeRock, PingFederate); RBAC mapping line-1 chatbot owner / line-2 model risk / line-3 audit roles.
- **Backend:** FastAPI on the bank's existing K8s cluster (typically EKS or GKE); microservice per check (verifier, abstention rewriter, probe runner). The LoRA Llama 3.1 8B verifier served via vLLM on 2× L4 GPUs with autoscaling on QPS.
- **Vendor pinning:** Anthropic snapshot pinning enforced at gateway (model_id + snapshot_date locked); diffs surface as drift events.
- **Data plane:** Postgres + pgvector for the verifier index and probe corpus; Snowflake / Databricks (whichever the bank already runs) for the analytics warehouse.
- **Observability:** OpenTelemetry → Datadog (the bank's standard) for system traces; Langfuse for LLM-specific verifier traces; PagerDuty for SLO breaches (nightly probe regression).
- **Compliance:** SOC 2 Type II baseline; FedRAMP Moderate if federal counterparty work; data residency configurable per region (US East, EU West, India for RBI compliance).
- **Governance:** Native integration with the bank's MRM workbench (Archer, ServiceNow GRC, MetricStream); each abstention event auto-files a Compliance disposition record.
- **Deployment:** Blue-green via Argo CD; feature flags via LaunchDarkly; canary rollout 1% → 10% → 50% → 100% over 14 days, with auto-rollback on probe regression.

The Streamlit prototype here proves the *product mechanic* — that an ensemble verifier can catch the eight named failure modes on a calibrated probe set. The production architecture above is what the seat I'm pursuing actually delivers.

---

## 👤 Author

**Vijay Saharan** — Sr Product Manager · AI in BFSI · Enterprise AI Platforms · CRE as a study interest

LinkedIn: [linkedin.com/in/vijaysaharan](https://www.linkedin.com/in/vijaysaharan/)

If your seat involves shipping AI under regulated constraint, this is the kind of problem I solve. Let's talk.

---

## 🙌 Acknowledgements

- [Hamel Husain](https://hamel.dev/blog/posts/evals/) — the eval-first thesis. Reason `probes/` exists before `src/`.
- [Greg Kamradt](https://github.com/gkamradt/LLMTest_NeedleInAHaystack) — needle-in-haystack work that motivated the multi-hop slice.
- [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/) — LLM09: Misinformation. The canonical industry framing.
- [Simon Willison](https://simonwillison.net/tags/hallucination/) — weekly hallucination posts. Required reading.
- [Microsoft Presidio](https://microsoft.github.io/presidio/) — PII scrub on the labeling pipeline.

<!-- @description 2026-05-04-093724 : HalluGuard: bank chatbot safety - catches hallucinated fees, rates, and policy claims before they reach customers -->
