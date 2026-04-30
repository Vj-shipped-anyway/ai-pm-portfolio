# Changelog — Hallucination Containment

All notable changes for the chatbot containment build, working backwards.

Format: each entry is the date, the version, what changed, what broke, and what I learned.

---

## v0.5 — Mar 6, 2026 — DPO experiment, reverted

Tried Direct Preference Optimization on the "confident-and-wrong" slice (deficiency 8). Curated 480 preference pairs where the model produced a confidently-wrong answer and a paired correct answer.

Results: +2 points F1 on the held-out test set. Marginal.

Pushed to staging. Three days of canary traffic showed unexpected regressions on commercial deposit accounts — a slice I hadn't included in the DPO data because I'd assumed it was covered. Rolled back to v0.4.

Lesson: DPO is sensitive to slice coverage in a way SFT isn't. If you're going to do DPO, your preference dataset has to span the full deployment surface or you'll get exactly this kind of silent regression.

---

## v0.4 — Feb 18, 2026 — Pilot deployment + vendor pin

Verifier deployed to the partner bank's chatbot in shadow mode (containment scores logged but not enforced). 14 days of shadow, then hard cutover.

Week 1 production: 11 incidents caught that would have hit Compliance otherwise.

Tuesday Feb 24: post-hoc probe accuracy dropped 4 points in 24 hours with no code change on our side. Investigated. Anthropic had pushed an update to `claude-sonnet-4-20250215` that subtly shifted refusal patterns. The chatbot was now refusing slightly more, in slightly different ways, and the verifier hadn't been trained on the new distribution.

Fix: pinned vendor version on the chatbot side, added the model snapshot ID as a feature on every probe run. Going forward, a vendor minor-version change is treated as a drift event and triggers a probe-set re-run before the new version is allowed in production.

Lesson: vendor silent updates are real and frequent. Treat the snapshot ID as a model attribute. This was the single most important architectural decision I made on this project.

---

## v0.3 — Feb 5, 2026 — Span head fixed, paraphrase positives added

Re-trained verifier with revised annotation guidelines. F1 jumped from 84% to 89%.

False-positive rate was still uncomfortably high — 14% of grounded responses were flagged ungrounded. Investigation: the verifier itself had paraphrase blindness on the margin. "Earn over 4%" was being marked ungrounded against "4.1% APY" because the literal token overlap was low.

Fix: added 1,400 explicitly-marked paraphrase-positive training examples. Pulled FP rate to 5%.

Lesson: the verifier has to be calibrated against the same paraphrase variation the chatbot produces. If the verifier is brittler than the chatbot on paraphrase, it becomes the bottleneck on deflection rate.

---

## v0.2 — Jan 24, 2026 — Architecture switch + the worst week

Reset the architecture decision after v0.1's multi-hop disaster. Considered three options, picked LoRA on Llama 3.1 8B. Wrote up the trade-off in `build/architecture-decisions.md`.

Started training. The auxiliary span-prediction head wouldn't converge — loss kept exploding around step 1,800. Spent two days on hyperparameter tweaks, learning rate schedules, gradient clipping. Nothing worked.

Realized the problem wasn't the head — it was the labels. Two annotators on the gold 3,100 had been bracketing the ungrounded *spans* differently. One marked the entire wrong sentence; the other marked only the wrong noun phrase. Inconsistent supervision.

Rewrote the annotation guidelines (`docs/annotation-guidelines-v2.md`). Re-labeled all 3,100 examples. Took six days. Two annotators full-time.

Re-trained. Span head converged. F1 climbed to 84%.

Worst week of the project. Lost six days to a problem that was fundamentally about annotation discipline, not modeling. Should have caught the inter-annotator inconsistency earlier — the eventual fix was a one-day audit of 50 random examples that I should have done in week one.

Lesson: when training fails in a way that doesn't make sense, suspect the labels before the model.

---

## v0.1 — Jan 14, 2026 — First cut, wrong architecture

Initial verifier on DeBERTa-v3-large with a binary classification head. 8 hours of training on a single A100. F1 = 71% on the held-out 1,800-example test set.

Looked decent in aggregate. Then I broke it down by deficiency class and saw the multi-hop accuracy was 49%. The model couldn't handle anything that required combining information across two retrieved chunks.

Realized DeBERTa wasn't the right base. The classification head was operating on the pooled embedding of the input, which had no mechanism for cross-chunk reasoning. Different architecture choice.

Lesson: aggregate F1 on a balanced test set will hide a deficiency-class disaster. Always slice the eval before declaring v0.1 a success.

---

## v0.0 — Dec 21, 2025 — The probe set, before any model

Two weeks of work, no code. Just probe design.

Cataloged hallucination incidents from the partner bank's incident log over the prior six months — 47 distinct cases. Worked with two ex-customer-service reps and one Compliance lead to cluster them into the eight deficiency classes that became the probe taxonomy.

Wrote the first 320 probes by hand. Got Claude Opus to generate 14,200 synthetic ones to a tight specification. Hand-labeled 3,100 of the synthetic ones for inter-annotator agreement. (Did not re-check kappa until v0.3 — see lesson there.)

This was the highest-leverage two weeks of the project. Without the probe set, every subsequent metric would have been noise.

Lesson: spend the time on the eval set first. Hamel Husain has been telling people this for two years and I learned it the hard way one more time.

---

## Pre-v0 — Dec 2, 2025 — The kickoff conversation

The chatbot at the partner bank had quoted the wrong APY to a customer that morning. Compliance had opened an incident. Product asked: "should we just turn off the chatbot?"

I said: "Let me design a test set first. We can't fix it if we can't measure how broken it is."

That was the actual start.
