# 🔎 What surprised me

Each prototype in this repo ends with a known miss. These ten results changed how I read the common approach to the same problem. All data is synthetic, and every number is 🟢 measured: the script named next to it prints it, so you can run it and see the same line. They show the method working on data I generated, not how any real bank behaves.

[Back to the portfolio](./README.md) · [Open the demos](https://vj-shipped-anyway.github.io/ai-pm-portfolio/)

---

**1. A confident wrong answer can be the common case.** On a 30-question bank-chatbot set, a keyword router answers 2 and sends the other 28 to a person. Adding an LLM, here as stored answers because no live model is called, answers 11 correctly and 19 wrongly, in fluent language. → [01 HalluGuard](./01-halluguard-bank-chatbot-safety/), `step_02`.

**2. The sponsor's own risk tier is wrong about 3 times in 10.** The tier typed on the intake form matches the reference tier on 104 of 150 submissions (69.3%). Recomputing it from the form, the data catalog and the vendor registry matches on 129 (86.0%). → [11 TierGate](./11-tiergate-ai-usecase-intake/), `step_02` and `step_04`.

**3. The usual benefit numbers overstate by more than the benefit.** Usage times an assumed saving reads 5,166 hours against a true net of 2,046: +152%. A before-and-after read gives 4,311 hours, +111%, and its 95% interval does not cover the answer key. → [12 ValueLedger](./12-valueledger-ai-benefit-tracking/), `step_04`.

**4. Annual access review almost never removes what it should.** Of the 71 grants no agent needs, the annual recertification removes 1 (1.4%). Reading the calls instead removes 61 (85.9%). → [23 ScopeKeeper](./23-scopekeeper-agent-permission-review/), `step_04`.

**5. A retrieval eval can score a leak as a win.** A relevance-only eval scores 283 of the 291 leaked results as correct answers, because it cannot express "must not return". → [20 CorpusGate](./20-corpusgate-rag-entitlements/), `step_02`.

**6. The adoption number rose while use fell.** The login-based view rises from 83.2% to 88.0% over the same weeks that the share of activated users with an AI session falls from 51.6% (week 4) to 36.4% (week 12). → [21 AdoptionPulse](./21-adoptionpulse-ai-enablement-funnel/), `step_02` and `step_03`.

**7. A fairness check can pass while the proxy does the work.** In the six-test pack, the reason-code check (T5) passes: matched pairs from different groups differ in top reason 78.6% of the time, against 75.4% within one group. The proxy ablation (T4) fails: neutralizing the postcode points moves the lowest adverse-impact ratio from 0.750 to 0.871 and turns 295 declines into approvals. → [17 FairLens](./17-fairlens-credit-model-fairness/), `step_04`.

**8. The simple threshold wins where both fire.** On the 3 held-out events that both approaches tripped on, a tuned single threshold served fewer bad decisions than the per-segment switch: 678 against 1,219. The drill scorecard also reports 0 of 7 scenarios ready. → [25 KillSwitch](./25-killswitch-ai-fallback-drills/), `step_04`.

**9. Ranking by volume puts controls at the top of the automation list.** A volume-first top 10 holds 6 steps an agent can take over; counted separately, 4 of the 10 touch restricted data or a four-eyes control. → [26 StepScout](./26-stepscout-task-mining-agent-candidates/), `step_03` and `step_04`.

**10. A script without controls resubmits everything; the kit still misses.** The happy-path script resubmits 515 payments with 0 approved. The kit blocks 1,164 unapproved attempts, and 15 of the 134 cases it finishes on its own still differ from the recorded human outcome. → [27 AgentKit](./27-agentkit-reference-agent-and-playbook/), `step_03` and `step_04`.

---

Each project README states its own limit next to its numbers. If a result here looks too tidy, open the project, run the step script and check the line.
