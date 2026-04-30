# Changelog — DriftSentinel

Working backwards. Each iteration is framed as: **what we pivoted on**, **what we shipped**, **what it moved**.

---

## v0.5 — Mar 11, 2026 — Iteration 6: Pivoted on the Anthropic incident, shipped vendor snapshot pinning

**Pivot.** Tuesday Mar 3, the customer-support GenAI started refusing 2x more often than the prior week. Investigation surfaced a silent Anthropic minor update on Feb 24. Nine days of behavior drift, invisible to every existing detector.

**Shipped.** Vendor snapshot ID as a tracked attribute on every GenAI inference. Daily diff job that flags any new snapshot ID as a drift event before any aggregate metric trips.

**Impact.** Vendor silent-update detection time went from "9 days post-hoc" to "<24 hours." The version diff is now itself a recognized drift event class. This single change closed the GenAI deficiency in our v0.3 taxonomy.

---

## v0.4 — Mar 4, 2026 — Iteration 5: Pivoted on validator triage time, shipped the Decide loop

**Pivot.** Two weeks of v0.3 in pilot showed validators still spending 3 weeks per drift event — Diagnose was working but the validator was hand-typing the recommendation and the evidence pack into a Word doc. The bottleneck moved.

**Shipped.** Recommendation engine (RETAIN / SHADOW / RETRAIN / ROLLBACK) with bounded risk envelope per use-case archetype. Auto-assembled MRM evidence bundle (PSI/KS, slice plots, lineage, macro context) routed to the MRM workbench.

**Impact.** Validator attestation cycle time: 3 weeks → 1 day. Bundle assembly: 3 weeks of manual collation → 3.2 seconds of automation. Validator capacity reclaimed: ~2 days/week per validator.

The hard call was authority. For Tier-1 we never auto-execute; recommendation only, validator attestation required. For Tier-2/3 with audit-trail wiring, ROLLBACK to N-1 can auto-execute. Non-negotiable with the MRM committee.

---

## v0.3 — Feb 24, 2026 — Iteration 4: Pivoted away from "smarter pager," shipped the Diagnose loop

**Pivot.** v0.2 was tripping 12-15 alerts/week with 31% false-positive rate. Validators ignored the channel after week 2. The product was about to die. The MRM committee scheduled a "do we continue" review for the following Monday.

The realization: detection isn't the product. Diagnosis is. Anyone can compute PSI. The hard part is going from "feature X drifted" to "subprime slice, exogenous macro cause, action = SHADOW" in one working day.

**Shipped.** Feature-contribution bisect, segment slicer, upstream pipeline-change correlation. Output is "DTI shifted on the subprime slice; no upstream pipeline change in 48h; co-correlated with macro signal" — actionable, not just true.

**Impact.** False-positive rate: 31% → 7% in two weeks. Validator pager went from "muted" to "real signal." Saved the project. Got us through the MRM continue/kill review with the committee asking when we'd ship the rest of the loops, not whether we'd continue.

---

## v0.2 — Feb 14, 2026 — Iteration 3: Pivoted on real-world noise, shipped continuous PSI on the 8-model pilot

**Pivot.** v0.1 worked on synthetic data. Real partner-bank traffic had ~3x the noise. We knew this would happen and had documented the assumption — but the noise floor problem was worse than expected once it landed against the production fleet.

**Shipped.** Continuous PSI/KS sweep wired to MLflow + Tecton. Daily alerts to a Slack channel with a webhook. 8 Tier-1 models instrumented end-to-end.

**Impact.** First real "model fleet on continuous monitoring" the bank had ever run. Coverage went from 22% → 100% on Tier-1. But also generated the false-positive crisis that drove v0.3.

The lesson is in the changelog because it shaped the v0.3 pivot: shipping detection without diagnosis on a real fleet is how you lose the room. We almost did. The recovery shaped the rest of the product.

---

## v0.1 — Feb 3, 2026 — Iteration 2: Pivoted from "build new" to "ride open-source primitives," shipped the basic detector

**Pivot.** Initial spec was to build PSI/KS from scratch. Realized the open-source ecosystem (Evidently, NannyML, Whylogs) was mature enough that the build-vs-buy call was buy. Saved an engineer-quarter.

**Shipped.** Basic PSI/KS detector against the synthetic 90-day inference log. Drift on day 60 detected cleanly. Documented the assumption that real-world traffic would be noisier.

**Impact.** Pilot greenlight from MRM. Saved the v0.2 conversation later — when the FP crisis hit, we could point at the documented noise-floor assumption and credibly position v0.3 as "the planned next step," not "we got it wrong."

---

## v0.0 — Jan 22, 2026 — Iteration 1: Pivoted before any code, shipped the failure-mode taxonomy

**Pivot.** Two weeks of work, no code. The instinct was to start building a detector. Pulled back: build the failure-mode taxonomy first.

**Shipped.** The five-deficiency taxonomy that became Step 3 of the walkthrough. Read 18 months of the partner bank's MRM exam reports. Categorized every drift-related finding. Workshopped the taxonomy with the lead validator and the head of MRM until they agreed it was complete.

**Impact.** Highest-leverage two weeks of the project. Without this taxonomy, every subsequent design decision would have drifted. Hamel Husain's "evals before models" thesis applied to monitoring: deficiencies before detectors.

---

## Pre-v0 — Jan 8, 2026 — Iteration 0: The kickoff conversation

The partner bank's CRO had just received a draft OCC exam finding citing inadequate ongoing monitoring of credit_pd_v3. The validator team had been pasting KS test results into a Word doc once a quarter and signing it. The OCC finding was technically true.

Head of MRM asked product: "what would 'real' continuous monitoring look like?"

I said: "Let me design the failure-mode taxonomy first. We can't fix it if we can't categorize what 'good' actually catches."

That was the actual start. Four weeks to ship the v1 plan to the MRM committee. Six iterations later it was running on the 8-model pilot.

---

## What's queued (next iteration)

- **v0.6** — Auto-rollback authority for Tier-2/3 models (with full audit trail)
- **v0.7** — Expansion to the credit-card pricing model fleet (additional 14 models)
- **v0.8** — Integration with the GRC tool the bank already uses (Archer or ServiceNow GRC, depending on partner)
- **v1.0** — MRM-attested production rollout to all Tier-1 models across the bank
