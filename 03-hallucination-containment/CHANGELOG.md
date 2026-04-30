# Changelog — Hallucination Containment

Working backwards through the **design iterations** of this portfolio prototype. Each entry is the date, the version, the design pivot, and what the iteration teaches about the product shape.

> Framing: this is the build journey of a portfolio prototype, not a release log from a production deployment. The architecture choices, the labelling discipline, and the vendor-pin design are mine. The "deployed at the partner bank" framing earlier drafts used would have been wrong — these are design iterations, not deployment history.

---

## v0.5 — Mar 6, 2026 — DPO design exploration

Considered Direct Preference Optimization on the "confident-and-wrong" slice (deficiency 8). The idea: curate ~480 preference pairs where the model produced a confidently-wrong answer alongside a paired correct answer, then DPO-tune the verifier to prefer the correct one.

The design lesson surfaces in the math: DPO is sensitive to slice coverage in a way SFT isn't. If the preference dataset doesn't span the full deployment surface (commercial deposit accounts, jurisdictions, regulatory citations, multi-hop), a DPO run that improves the held-out test F1 by ~2 points can still regress on a slice that wasn't in the preference data. The right sequence is: SFT verifier first, calibrate, deploy in shadow, *then* layer DPO on top with a preference dataset that explicitly covers every slice.

Lesson: the v0.5 design doesn't ship until the deployment-surface coverage is complete. Sequenced for a future iteration once the slice list is exhaustive.

---

## v0.4 — Feb 18, 2026 — Containment design + vendor pin

Containment-layer architecture (verifier → calibrator → abstention rewriter) finalized. The shape is what the README walkthrough shows.

The single most important architectural decision in this iteration is the vendor snapshot pin. The Anthropic minor update on Feb 24, 2026 (publicly observable refusal-pattern shift on `claude-sonnet-4-20250215`) is the reference incident the design is calibrated against — without the pin, a verifier trained on one snapshot's distribution silently degrades on the next snapshot, and the regression looks like an arbitrary 4-point F1 drop with no code change on our side.

Design move: pin the vendor version on the chatbot side; treat the snapshot ID as a feature on every probe run. A vendor minor-version change becomes a tracked drift event that triggers a probe-set re-run before the new version is allowed in production.

Lesson: vendor silent updates are real and frequent. Treat the snapshot ID as a model attribute. This is the architectural choice DriftSentinel's v0.5 also rests on; the same primitive solves both products' GenAI deficiency.

---

## v0.3 — Feb 5, 2026 — Span head fixed, paraphrase positives added

Re-trained verifier with revised annotation guidelines. F1 jumped from 84% to 89% on the held-out test set in the design run.

False-positive rate was uncomfortably high — 14% of grounded responses were flagged ungrounded. Investigation: the verifier itself had paraphrase blindness on the margin. "Earn over 4%" was being marked ungrounded against "4.1% APY" because the literal token overlap was low.

Fix: added 1,400 explicitly-marked paraphrase-positive training examples. Pulled FP rate to 5%.

Lesson: the verifier has to be calibrated against the same paraphrase variation the chatbot produces. If the verifier is brittler than the chatbot on paraphrase, it becomes the bottleneck on deflection rate. The probe taxonomy has to cover both the chatbot's failure modes AND the verifier's failure modes — those are not the same set.

---

## v0.2 — Jan 24, 2026 — Architecture switch + the worst week

Reset the architecture decision after v0.1's multi-hop disaster. Considered three options, picked LoRA on Llama 3.1 8B. Wrote up the trade-off in `build/architecture-decisions.md`.

Started training. The auxiliary span-prediction head wouldn't converge — loss kept exploding around step 1,800. Spent two days on hyperparameter tweaks, learning rate schedules, gradient clipping. Nothing worked.

Realized the problem wasn't the head — it was the labels. Two annotators on the gold 3,100 had been bracketing the ungrounded *spans* differently. One marked the entire wrong sentence; the other marked only the wrong noun phrase. Inconsistent supervision.

Rewrote the annotation guidelines (`docs/annotation-guidelines-v2.md`). Re-labeled all 3,100 examples. Took six days. Two annotators full-time on the design run.

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

The probe taxonomy is calibrated against the published shape of bank-chatbot hallucination incidents — public CFPB complaints, vendor incident postmortems, the OWASP LLM Top 10 (LLM09 Misinformation specifically), and Simon Willison's running commentary on the field. From that I derived 47 distinct hallucination-incident archetypes and clustered them into the eight deficiency classes that became the probe taxonomy.

Wrote the first 320 probes by hand. Got Claude Opus to generate 14,200 synthetic ones to a tight specification. Hand-labeled 3,100 of the synthetic ones for inter-annotator agreement. (Did not re-check kappa until v0.3 — see lesson there.)

This was the highest-leverage two weeks of the project. Without the probe set, every subsequent metric would have been noise.

Lesson: spend the time on the eval set first. Hamel Husain has been telling people this for two years and the discipline is the same every time.

---

## Pre-v0 — Dec 2, 2025 — The kickoff frame

The frame the product is designed against: a retail bank's chatbot quotes the wrong APY to a customer. Compliance opens an incident. Product asks: "should we just turn off the chatbot?"

The right first move is: design the test set first. You can't fix it if you can't measure how broken it is.

That framing is the existence-proof for this product, and it's calibrated against publicly-discussed bank-chatbot incidents over the past 24 months.
