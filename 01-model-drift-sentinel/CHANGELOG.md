# Changelog — DriftSentinel

Working backwards through the **design iterations** of this portfolio prototype. Each entry is framed as: **what the design pivots on**, **what the version contains**, **what it changes about the product shape**.

> Framing: this is the build journey of a portfolio prototype, not a release log from a production deployment. The technical reasoning (why segment-aware noise floor, why vendor pin, why the Decide loop comes after Diagnose) is mine. The "shipped to a partner bank" framing earlier drafts used would have been wrong — this is design work, not deployment history.

---

## v0.5 — Design iteration 6: vendor snapshot pinning

**Pivot.** The Anthropic minor snapshot update on Feb 24, 2026 (publicly observable refusal-pattern shift on `claude-sonnet-4-20250215`) was the reference incident this design is calibrated against. Any drift product that doesn't track the vendor snapshot ID has no signal on GenAI drift — it sees the *consequence* of the update post-hoc, not the update itself.

**What this version contains.** Vendor snapshot ID as a tracked attribute on every GenAI inference. Daily diff job that flags any new snapshot ID as a drift event before any aggregate metric trips.

**What it changes.** Vendor silent-update detection moves from "9 days post-hoc via aggregate metric" to "<24 hours via snapshot diff." The version diff is now itself a recognized drift event class. This single design choice closes the GenAI deficiency in the v0.3 taxonomy.

---

## v0.4 — Design iteration 5: the Decide loop

**Pivot.** A Diagnose loop without a Decide loop puts the validator in a worse spot, not a better one — they now know the cause but still have to hand-type the recommendation and the evidence pack into a Word doc. The bottleneck moves; it doesn't go away. Decide is what closes the loop end-to-end.

**What this version contains.** Recommendation engine (RETAIN / SHADOW / RETRAIN / ROLLBACK) with bounded risk envelope per use-case archetype. Auto-assembled MRM evidence bundle (PSI/KS, slice plots, lineage, macro context) routed to the MRM workbench.

**What it changes.** Modeled validator attestation cycle: 3 weeks → 1 day. Bundle assembly: 3 weeks of manual collation → 3.2 seconds of automation. Validator capacity reclaimed: ~2 days/week per validator (modeled).

The hard call is authority. For Tier-1 the design is recommendation only — never auto-execute; validator attestation required. For Tier-2/3 with audit-trail wiring, ROLLBACK to N-1 can auto-execute. That split is calibrated against SR 11-7 expectations on consumer credit decisions; it's the line I'd hold against an MRM committee asking for more automation on Tier-1.

---

## v0.3 — Design iteration 4: the Diagnose loop

**Pivot.** A "smarter pager" is the wrong product. PSI on its own trips alerts at a rate that drives validators away from the channel within two weeks — and once they mute the channel, the product is functionally dead. Detection isn't the product. Diagnosis is. Anyone can compute PSI. The hard part is going from "feature X drifted" to "subprime slice, exogenous macro cause, action = SHADOW" in one working day.

**What this version contains.** Feature-contribution bisect, segment slicer, upstream pipeline-change correlation. Output is "DTI shifted on the subprime slice; no upstream pipeline change in 48h; co-correlated with macro signal" — actionable, not just true.

**What it changes.** Modeled false-positive rate: 31% → 7%. The validator pager moves from "muted" to "real signal." This is the design pivot the rest of the product depends on; without it, the v0.2 detection layer is just noise.

---

## v0.2 — Design iteration 3: continuous PSI on the modeled 8-model fleet

**Pivot.** Synthetic data hides the noise floor. Real production traffic at a Tier-1 BFSI shape has roughly 3x the noise of synthetic — a known, documented assumption that drives the v0.3 design.

**What this version contains.** Continuous PSI/KS sweep wired to MLflow + Tecton. Daily alerts to a Slack channel with a webhook. 8 modeled Tier-1 models instrumented end-to-end.

**What it changes.** Coverage in the modeled fleet: 22% → 100% on Tier-1. Surfaces the false-positive crisis that motivates v0.3 — and that's the real lesson encoded here: shipping detection without diagnosis on a real fleet is how you lose the room. The v0.3 pivot is the recovery, and it's the recovery shape any drift product has to design for from day one.

---

## v0.1 — Design iteration 2: ride open-source primitives

**Pivot.** PSI/KS from scratch is a nine-figure-of-engineer-time mistake. The open-source ecosystem (Evidently, NannyML, Whylogs) is mature enough that the build-vs-buy call is buy. The product is the orchestration, diagnosis, and routing layer on top of those primitives.

**What this version contains.** Basic PSI/KS detector against the synthetic 90-day inference log. Drift on day 60 detected cleanly. Documented assumption that real-world traffic would be noisier (which is what v0.2 confirms and v0.3 fixes).

**What it changes.** Saves the v0.2 conversation later — when the FP crisis hits, the documented noise-floor assumption lets v0.3 land as "the planned next step," not "we got it wrong." Predicting the next pivot in the changelog is part of the discipline.

---

## v0.0 — Design iteration 1: the failure-mode taxonomy

**Pivot.** Two weeks of work, no code. The instinct is to start building a detector. Pull back: build the failure-mode taxonomy first.

**What this version contains.** The five-deficiency taxonomy that becomes Step 3 of the walkthrough. The taxonomy is calibrated against published BFSI MRM exam-finding patterns — not a single bank's exam history, but the public shape of what regulators flag as inadequate ongoing monitoring.

**What it changes.** Highest-leverage two weeks of the project. Without this taxonomy, every subsequent design decision drifts. Hamel Husain's "evals before models" thesis applied to monitoring: deficiencies before detectors.

---

## Pre-v0 — The kickoff frame

The frame the product is designed against: a Tier-1 retail bank receives a draft OCC exam finding citing inadequate ongoing monitoring of a credit decisioning model. The validator team has been pasting KS test results into a Word doc once a quarter and signing it. The OCC finding is technically true. Head of MRM asks product: "what would 'real' continuous monitoring look like?"

The right first move is: design the failure-mode taxonomy. You can't fix what you can't categorize.

That framing is the existence-proof for this product, and it's calibrated against public SR 11-7 expectations and the published shape of recent OCC and FRB supervisory letters on AI/ML ongoing monitoring.

---

## What's queued in the design

- **v0.6** — Auto-rollback authority for Tier-2/3 models (with full audit trail)
- **v0.7** — Expansion to a credit-card pricing model fleet (additional 14 models in the modeled fleet)
- **v0.8** — Integration with the GRC tool the bank already uses (Archer or ServiceNow GRC)
- **v1.0** — MRM-attested production rollout to all Tier-1 models in the engagement that takes this prototype forward
