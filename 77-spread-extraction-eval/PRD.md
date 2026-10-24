# PRD: spread-extraction-eval

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a model-change review. It is not a record of a PRD landed at a named bank. The statements, the layouts and the two extractors are mine and rule-based; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and no model has been scored.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | spread-extraction-eval: a seeded generator of synthetic financial statements in six layouts, a field-level scorer that groups results by layout, and a drift gate that names the layout that slipped |
| **Owner** | The owner of an extraction step in a lending workflow, with the reviewer who decides whether a new model or prompt may replace the old one as co-owner of the gate limits |
| **Stage** | Portfolio prototype on synthetic data; scores two rule-based stand-ins, not a model |
| **Primary user** | The owner of an extraction step in a lending workflow |
| **Secondary users** | The reviewer who approves a model change; the credit analyst who spreads statements; the model-risk reviewer; internal audit |
| **Problem** | A credit analyst spreads a borrower's statements into a standard template. An extraction model that reads them is tuned and tested on the layouts someone had to hand. When a statement arrives in another layout (thousands instead of units, parentheses for losses, relabelled lines, a balance sheet printed in two halves, a column of note numbers) the single accuracy number on the test set says nothing about it. In the planted set, 🟢 a pilot on the layout the extractor was written against finds 880 of 880 values right, and 100 of 120 statements (83.3%) sit in layouts the pilot never touched (`step_01_pilot_only.py`). |
| **Solution** | Generates synthetic statements in six layouts with the true value of every field, 22 fields in 2 periods. Scores any predictions file field by field and groups the result by an explicit layout column. Names the error class of each wrong value: missing, scale, sign, wrong period, compound, wrong line, other. Gates on drift: a layout under a floor, or too far under the best layout, fails the run (exit 1). Runs a tie-out check that needs no truth: do the figures obey the accounting identities. |
| **North-star metric** | Share of extraction model or prompt changes released after a layout-level gate on a labeled sample that includes a held-out layout. Target 🔴 100%. Today in this model: a pooled number only. |
| **Measured metrics (synthetic)** | 🟢 The pooled number and the worst layout side by side: 94.7% against 68.4%. The gate passes `alias_aware` on the 5 development layouts and fails it on all 6. 24 loss and deficit statements are read with every field right and raise 0 tie-out false alarms (`step_03_deficiencies_exposed.py`, `step_04_layout_scorer.py`). |
| **Modeled metrics** | 🟡 Utility (136 + 142) / 20 × 600 = 8,340 wrong values a year held out of the spread, assuming 600 statements a year arrive in a layout that has drifted. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces, and of labeling a real sample, has not been sized. |
| **Risk #1** | One author wrote the data and the rules, so the numbers are a ceiling. Mitigation: score one real model's output on a labeled sample from real layouts, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The extractors are rules, so they do not show how a model fails: a model can invent a figure, differ between runs and read a scanned page worse. Mitigation: run one real model through `score` and add its failure classes before any threshold is trusted. |
| **Risk #3** | Twenty statements per layout is a small sample, and the tie-out check cannot see every wrong value. 🟢 It passes 15 of the 100 statements `fixed_label` reads wrong (`step_03_deficiencies_exposed.py`). Mitigation: the gate also prints how many statements are right in full; add intervals; keep a labeled sample as the arbiter. |
| **Out of scope** | Any model call; image or scanned input; materiality weighting; confidence intervals; statements other than the income statement and balance sheet; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is statements, fields or layouts, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Drift gate** (a layout under a floor, or too far under the best layout, fails the run; a layout with too few statements is not gated; exit 1) | 120 statements | 3 | 0.8 | 1 | 288.0 | Built in prototype |
| 2 | **Input validation** (empty, wrong-type, truncated or duplicate input exits 2, never a traceback; strings from input escaped) | 120 statements | 2 | 0.9 | 1 | 216.0 | Built in prototype |
| 3 | **Field-level scorer by layout** with error classes | 120 statements | 3 | 0.9 | 2 | 162.0 | Built in prototype |
| 4 | **Score a real model's output** on a labeled sample | 120 statements | 3 | 0.6 | 2 | 108.0 | Sequenced for v0.2 |
| 5 | **Predictions contract and stand-in extractors** (`predict`) | 120 statements | 1 | 0.8 | 1 | 96.0 | Built in prototype |
| 6 | **Tie-out check** (ten accounting identities, no truth needed) | 120 statements | 2 | 0.7 | 2 | 84.0 | Built in prototype |
| 7 | **Labeled sample per real layout**, with one held out | 120 statements | 3 | 0.6 | 4 | 54.0 | Sequenced for v0.2 |
| 8 | **CI step that fails a model change on a failing gate** | 120 statements | 2 | 0.5 | 3 | 40.0 | Sequenced for v0.2 |
| 9 | **Scanned input and a cash-flow statement** | 120 statements | 3 | 0.4 | 8 | 18.0 | Queued |
| 10 | **Gate record per model change** (limits, sample hash, result) | 120 statements | 1 | 0.6 | 4 | 18.0 | Sequenced for v0.2 |
| 11 | **Materiality weighting** (a wrong tax line against a wrong revenue line) | 22 fields | 2 | 0.5 | 3 | 7.3 | Queued |
| 12 | **Intervals** so a layout with few statements is not over-read | 6 layouts | 2 | 0.5 | 3 | 2.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from spread-extraction-eval | What they fear |
| --- | --- | --- | --- |
| **Extraction owner** | Owner | A result by layout that names the slipping layout and the error class, so the fix is a rule or a prompt and not a hunt. | A gate that fails on noise and gets bypassed. |
| **Model-change reviewer** | Approver of a model or prompt change | One page that shows the pooled number and the worst layout together. | Approving a change on an average that hides a layout. |
| **Credit analyst** | Consulted | Statements in a failing layout routed to manual spreading, not silently mis-spread. | Finding a wrong figure in a spread after the credit decision. |
| **Model-risk reviewer** | Reader | A held-out layout and the limits written down. | Limits that were chosen after the result. |
| **Security / CISO** | Approver | Real statements kept inside the boundary, and no document text in the scorer's path. | Customer financials copied into a CI log. |
| **Internal audit** | Reader | A path from a released model to the labeled sample and the limits it passed. | A gate limit changed to let a model through. |

---

## User stories (top 4)

1. **As the extraction owner**, I want accuracy scored layout by layout with the error class of each wrong value, so I see that a layout slipped and how.
2. **As the model-change reviewer**, I want the pooled number and the worst layout side by side, so an average does not hide a layout.
3. **As the model-change reviewer**, I want a gate that fails a layout under a floor or too far under the best layout and ignores a layout with too few statements, so a thin sample is not over-read.
4. **As the credit analyst**, I want a tie-out check that needs no truth and a plain statement of what it cannot see, so I know when only a labeled sample will do.

---

## KPIs

**North star:** share of extraction model or prompt changes released after a layout-level gate on a labeled sample that includes a held-out layout. Target 🔴 100%.

**Inputs (leading):**
- Layouts in the labeled set (prototype: 🟢 6 layouts of 20 statements each, 5 development and 1 held out, `data/README.md`).
- Labeled values (prototype: 🟢 5,280 true values, 22 fields in 2 periods, `data/README.md`).
- Layouts with at least the minimum statements to be gated (prototype: 🟢 10 statements, `data/README.md`).
- Gate limits written down before the run (prototype: 🟢 a floor of 95.0% and a gap of 3.0 points, `data/README.md`).

**Outputs (lagging):** prototype baselines from the planted set.
- Pooled accuracy against the worst layout. 🟢 94.7% against 68.4% (`step_03_deficiencies_exposed.py`).
- Gate on the held-out layout. 🟢 `alias_aware` passes the 5 development layouts and fails all 6 (`step_04_layout_scorer.py`).
- Statements with every field right. 🟢 100 of 120 (83.3%), against 94.7% of fields (`step_03_deficiencies_exposed.py`).
- Tie-out false alarms on loss and deficit statements. 🟢 0 of 24 (`step_04_layout_scorer.py`).
- Known limit. 🟢 15 of 100 wrong statements tie out (`step_03_deficiencies_exposed.py`).
- Wrong values caught that a person would have missed: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Score the current extractor on a labeled sample from real layouts. Print the table and the gate, change nothing. |
| 1: Calibration | 4w | Set the floor and the gap from the error the spreading step can absorb. Choose the held-out layout and write the limits down before any run. |
| 2: Gate in the change path | 6w | A model or prompt change needs a passing gate or a recorded exception from a different approver. |
| 3: Routing | 6w | A statement in a failing layout is routed to manual spreading until the layout passes. |
| 4: More layouts and record | 10w | Add scanned input and a cash-flow statement. Write a record per change. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Where do the floor and the gap come from?** Mine, 95.0% and 3.0 points, are assumptions. Recommendation: start there, then set them from the error the spreading step can absorb on the real queue.
2. **How many statements per layout are enough?** Twenty is thin and the values in a layout are not independent. Recommendation: keep the minimum for gating, print statements right in full beside field accuracy, and add intervals before a small layout is over-read.
3. **What counts as a layout?** Recommendation: an explicit field (a template, a vendor, a country), never inferred from the text.
4. **What happens when the gate fails on a layout?** Recommendation: route that layout's statements to manual spreading and hold the model change for that layout only; leave the decision on the rest to the owner.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **A scorer on a labeled set.** The scorer needs only a document id, a layout, and the field, period and value of each prediction; the document text is needed only to run a stand-in extractor. Production adds a labeled-set registry and a gate record, all designed and none built.
- **Never silent.** A missing, empty, truncated or mistyped file, a duplicate row or a bad period exits 2. Predictions that match no truth are not a silent pass. A layout with too few statements is listed as not gated.
- **Strings from input are data.** Layout names and ids are escaped and cut before they reach a log, so a hostile string cannot start a new line or a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves an accuracy shows in the diff.

**What is next.** Run one real model's output through `score`; add a statement of cash flows and a scanned-input layout; weight fields by materiality; add intervals so a layout with few statements is not over-read.

**What would have to be true before a pilot.**
- A labeled sample exists for each real layout, with one held out, and the limits are written before the run.
- The extraction job can write a predictions file in the truth shape.
- A named person owns the gate and will act on a failing layout.
- Real statements can be held in one controlled place.
- The team agrees what a failing layout does: a hold, a route to manual spreading, or an exception.

---

*This PRD names [51 Memo Tieout](../51-memo-tieout/), [40 Eval Gate](../40-eval-gate/) and [68 KYB Packet Check](../68-kyb-packet-check/) as designed interlocks (🔴 designed, none built).*
