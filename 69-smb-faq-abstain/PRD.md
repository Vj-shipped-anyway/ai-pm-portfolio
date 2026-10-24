# PRD: SMB FAQ abstention gate

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a review of a small-business chat channel. It is not a record of a PRD landed at a named bank. The checks, the 30 questions, the stored drafts and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | smb-faq-abstain: a rule-based gate that reads a question, a drafted answer and a short knowledge base and prints SERVE or ABSTAIN, so a small-business FAQ assistant hands off instead of guessing |
| **Owner** | The product owner of the bank's small-business chat channel, with the owner of the knowledge base as co-owner of the passages and the thresholds |
| **Stage** | Portfolio prototype on synthetic data; no model call, no chat integration |
| **Primary user** | The product owner of a bank's small-business chat channel |
| **Secondary users** | The banker who receives the handoffs; the owner of the product sheets the passages come from; a second-line reviewer; internal audit |
| **Problem** | A small-business FAQ assistant that drafts answers about deposit and lending products will, some of the time, state a fee, rate, term or availability the bank does not offer, or answer a question nobody should answer from an FAQ. The customer cannot tell which drafts are wrong. In the planted set, 🟢 serving every draft puts 18 wrong answers in front of customers, 60.0% of the 30 questions (`step_02_draft_only.py`). |
| **Solution** | Reads a question, a drafted answer and a short knowledge base. Holds back the draft when it already declines, when the question asks for advice, when no passage covers the question, or when the question fits more than one product. Otherwise checks every number, citation, yes or no and named state in the draft against the best passage and serves it only when all are supported. Prints SERVE or ABSTAIN with a one-line reason and exits 0, 1 or 2 so a script can use it. |
| **North-star metric** | Share of customer-facing drafts on in-scope products that pass through the gate with a recorded decision, where a served draft is supported by a named passage and everything else is a handoff. Target 🔴 100%. Today in this model: no check sits between the draft and the customer. |
| **Measured metrics (synthetic)** | 🟢 3 of 30 wrong answers served against 18; 15 of 18 wrong drafts held back; 7 of 10 correct drafts served; 20 of 30 (66.7%) handed to a banker (`step_04_with_gate.py`). |
| **Modeled metrics** | 🟡 Utility (15/18 − 0/18) × 120 = 100 wrong drafts a year kept from customers, assuming the assistant produces 120 wrong drafts a year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces and of banker time for handoffs has not been sized. |
| **Risk #1** | The set and the rules share an author, so the numbers are a ceiling. Mitigation: run it on real drafts and a real knowledge base the owner may share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The drafts are stored stand-ins, and three wrong drafts pass because the number they quote is real. 🟢 Q05, Q10 and Q16 pass all checks (`step_04_with_gate.py`). Mitigation: a units and period check is next in the backlog, and a person samples wrong-number drafts in shadow mode. |
| **Risk #3** | Blunt cues hold back correct drafts and the handoff rate is high. 🟢 3 correct drafts are held back by mistake and 20 of 30 go to a banker, from a set built from failure cases (`step_04_with_gate.py`). Mitigation: shadow mode first, so the live handoff rate is measured before any draft is held back. |
| **Out of scope** | A trained verifier, a language model call, a live chat integration, units and meaning of numbers, synonyms, state abbreviations, any regulation or standard. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is questions or passages, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Input validation** (a missing column, an empty or truncated file, a duplicate passage or a bad state name exits 2, never a traceback) | 30 questions | 2 | 0.9 | 1 | 54.0 | Built in prototype |
| 2 | **Scope check** (a question that asks for advice or a decision is held) | 30 questions | 2 | 0.7 | 1 | 42.0 | Built in prototype |
| 3 | **Source check** (no passage covers enough of the question: held) | 30 questions | 2 | 0.7 | 1 | 42.0 | Built in prototype |
| 4 | **Ambiguity check** (the question fits more than one product equally well: held) | 30 questions | 2 | 0.7 | 1 | 42.0 | Built in prototype |
| 5 | **Grounding check** (every number, citation, yes or no and named state in the draft must be in the best passage) | 30 questions | 3 | 0.8 | 2 | 36.0 | Built in prototype |
| 6 | **Handoff check and one-line output** (a draft that declines is a handoff; control characters shown as escapes) | 30 questions | 1 | 0.9 | 1 | 27.0 | Built in prototype |
| 7 | **Shadow mode on real drafts** (log the decision, hold nothing back, measure the live handoff rate) | 30 questions | 3 | 0.6 | 3 | 18.0 | Sequenced for v0.2 |
| 8 | **Units and period check** (a number must match the unit and the period it answers; closes the Q05 and Q10 kind of miss) | 30 questions | 2 | 0.5 | 3 | 10.0 | Sequenced for v0.2 |
| 9 | **Spelled-out numbers and state abbreviations** (reads "ninety days" and "TX") | 30 questions | 1 | 0.6 | 2 | 9.0 | Sequenced for v0.2 |
| 10 | **Decision record** (question, draft, passage, reason, thresholds, file hashes) | 30 questions | 2 | 0.6 | 4 | 9.0 | Queued |
| 11 | **Reviewed knowledge base** (an owner and a review date per passage, excluded states checked against a list) | 12 passages | 3 | 0.6 | 3 | 7.2 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from smb-faq-abstain | What they fear |
| --- | --- | --- | --- |
| **Channel product owner** | Owner | A chat channel that answers routine questions and never states a fee or rate the bank does not offer. | A gate that hands off so many questions that the assistant is not worth running. |
| **Banker on the handoff queue** | Primary user of the output | Handoffs that carry the question, the draft and the reason, and are mostly questions that need a person. | A queue full of routine questions the assistant could have answered. |
| **Knowledge base owner** | Owns the passages and the product sheets | Passages used as written, with a stale or missing one showing up as a handoff and not as a guess. | A gate that quietly rewrites or overrides the passages. |
| **Second-line reviewer** | Approver of thresholds and rule changes | A record of which passage supported a served draft, and who changed a threshold. | A threshold relaxed to lower the handoff rate with nobody looking. |
| **Security / CISO** | Approver | No customer text outside the boundary, no model key in the gate's path, hostile strings kept out of logs. | Another service holding customer questions. |
| **Internal audit** | Reader | A path from a served or held draft to the question, the draft and the passage it used. | A passage edited after the fact, with no trace. |
| **Small-business customer** | Affected, not a decision maker | A correct answer fast, or a person who can give one. | Acting on a fee or rate that turns out to be wrong. |

---

## User stories (top 4)

1. **As the channel product owner**, I want a drafted answer held back when its number, citation, yes or no or state is not in the bank's own passage, so a customer is not told something the bank does not stand behind.
2. **As a banker on the handoff queue**, I want each handoff to say why it was held (no source, ambiguous, out of scope, ungrounded), so I start from the reason and not from a blank page.
3. **As the knowledge base owner**, I want a question no passage covers to become a handoff, so a gap in my passages shows up as a count and not as an invented answer.
4. **As internal audit**, I want each served or held decision tied to the question, the draft and the passage it used, so I can reproduce it later.

---

## KPIs

**North star:** share of customer-facing drafts on in-scope products that pass through the gate with a recorded decision, where a served draft is supported by a named passage and everything else is a handoff. Target 🔴 100%.

**Inputs (leading):**
- Passages with an owner and a review date (the prototype has 🟢 12 passages, from `data/README.md`).
- Excluded states named in full in every passage that has them.
- Questions in the evaluation set by class (the prototype has 🟢 30 questions: answerable 14, not_in_kb 6, out_of_scope 4, state_specific 3 and ambiguous 3, from `data/README.md`).
- Real drafts reviewed in shadow mode (target: a week of live traffic before any draft is held back).

**Outputs (lagging):** prototype baselines from the planted set.
- Wrong answers served. 🟢 3 of 30 with the gate, against 18 of 30 when every draft is served (`step_04_with_gate.py`, `step_02_draft_only.py`).
- Wrong drafts held back. 🟢 15 of 18 (`step_04_with_gate.py`).
- Correct drafts served. 🟢 7 of 10, with 3 held back by mistake (`step_04_with_gate.py`).
- Handed to a banker. 🟢 20 of 30 (66.7%), 2 of them because the draft already declined (`step_04_with_gate.py`).
- Known misses. 🟢 3 wrong drafts pass, Q05, Q10 and Q16 (`step_04_with_gate.py`).
- Handoffs a banker judged unnecessary, and customers who prefer a handoff to a wrong answer: not measured; the planted set has no banker and no customer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the gate on a week of real drafts and a real knowledge base. Log each decision, hold nothing back, and have a person sample both the held and the served drafts. |
| 1: Calibration | 4w | Set the coverage minimum and the tie margin against the shadow data. Fix passages that are missing or stale. Add the units and period check. |
| 2: Hold back for one product line | 6w | Hold back on one deposit product line. The banker queue receives the handoffs with their reasons. |
| 3: All in-scope products | 6w | Extend to the lending products and the state-specific questions. Spelled-out numbers and state abbreviations are read. |
| 4: Decision record and review | 8w | Write a record per decision. Passages carry an owner and a review date. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should an ambiguous question be handed off, or should the assistant ask which product?** The data sets the right answer for these as "ask which one, or hand to a banker". Recommendation: hand off in v0.1, because it is one rule and testable, and test a clarifying question after shadow mode shows how often it comes up.
2. **Where should the coverage minimum and the tie margin come from?** Both are assumptions I set before running anything and did not tune. Recommendation: keep them until shadow mode, then set them against real drafts with a person sampling the held ones.
3. **Is a handoff rate of 20 of 30 acceptable?** It comes from a set built from failure cases, and live traffic is mostly routine. Recommendation: do not read it as a forecast; measure the live rate in shadow mode and decide against the banker queue's capacity.
4. **Who owns a passage when it is wrong?** A wrong passage makes the gate serve a wrong draft with a clean record. Recommendation: the product sheet owner, with a review date on each passage and a handoff, not a guess, when the date has passed.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One synchronous check in front of the customer.** The gate is stateless: it reads a question, a draft and the passages and returns a decision. Production adds a reviewed knowledge base, a banker queue, a decision record and telemetry, all designed and none built.
- **Never silent.** A missing, empty or malformed knowledge base or input exits 2. In the design, a gate that cannot decide hands the customer to a banker; it never shows the draft.
- **Strings from input are data.** Question, draft and passage text are written as one escaped line, so a hostile string cannot start a new log line or forge a workflow command.
- **Changes to a check are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the served-wrong count shows in the diff.

**What is next.** Run the gate on real drafts and a real knowledge base the owner may share; add a units check; replace word overlap with a retriever; measure the handoff rate on live traffic.

**What would have to be true before a pilot.**
- A knowledge base with an owner, a review date per passage and excluded states named in full.
- A week of real drafts that can be shared, so the thresholds are set against real traffic and not mine.
- A banker queue with the capacity to take the handoff rate shadow mode measures.
- The channel's integration fails closed: a gate error hands the customer to a banker.
- The product owner and the second-line reviewer agree which reasons hold a draft back.

---

*This PRD names [01 HalluGuard](../01-halluguard-bank-chatbot-safety/), [08 OversightOps](../08-oversightops-hitl-workflow/), [09 LineageLog](../09-lineagelog-ai-decision-audit/) and [05 AgentWatch](../05-agentwatch-agent-observability/) as designed interlocks (🔴 designed, none built). No code or number was copied from them.*
