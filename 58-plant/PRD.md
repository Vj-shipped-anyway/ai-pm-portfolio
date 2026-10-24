# PRD: plant

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an evaluation or model-risk review. It is not a record of a PRD landed at a named bank. The spec, the planted ledger and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and the checker in the demo is a stand-in I wrote.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | plant: a command that writes test data from a spec, keeps the answer key in a separate file, and scores what a checker flagged against the key, behavior by behavior |
| **Owner** | The engineer who owns a checker, an eval or a guardrail, with the model-risk or evaluation reviewer as co-owner of the spec and the minimum recall |
| **Stage** | Portfolio prototype on synthetic data; no model call, no hosting |
| **Primary user** | An engineer or reviewer who owns a checker, an eval or a guardrail and needs to know what it misses before it meets real data |
| **Secondary users** | The evaluation owner who writes specs; the second-line reviewer who reads the weakest-behavior line; internal audit |
| **Problem** | A checker or an eval is only as trustworthy as the data it was tried on. Test data made by corrupting rows at random and adding an is_bad column gives a recall and a precision, and hides which failures were found, which were never found, and what the checker does to rows that merely look like failures. On five synthetic files, 🟢 the tuned rules read recall 0.89 and precision 0.92 while finding 0 of 50 paraphrased injections (`step_02_is_bad_column.py`, `step_03_what_it_hides.py`). |
| **Solution** | Reads a spec: a seed, columns, and named behaviors with a role (failure or look-alike), an exact count and the change to make. Writes the data with no label column, a separate key (one line per planted row: behavior, role, exact change) and a manifest with hashes. Scores a flags file against the key: failures found, look-alikes flagged, clean rows flagged. Exits 1 under a chosen minimum recall; exits 2 with one line on input it cannot use. |
| **North-star metric** | Share of checkers that gate a release whose release note names the weakest behavior and the look-alike false alarms from a keyed file. Target 🔴 100%. Today in this model: the is_bad column names neither. |
| **Measured metrics (synthetic)** | 🟢 With a key of 114 rows (84 failures and 30 look-alikes) in a 644-row file, the naive rules find 71 of 84 failures and flag 29 of 30 look-alikes; the tuned rules find 72 of 84 and flag 0 of 30. A rerun with the same seed gives identical bytes, and 84 failures are planted under each of seeds 58 to 62 (`step_04_with_a_key.py`). |
| **Modeled metrics** | 🟡 Utility (1 − 0) × 10 = 10 failure behaviors a year that a checker misses entirely, named instead of hidden, assuming 10 checker evaluations a year and one such behavior in each. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The spec and the checker share an author, so the scores are a ceiling. Mitigation: have someone other than the checker's author write the specs, and report planted scores and real scores apart. |
| **Risk #2** | The key measures the variants I planted, not the variants that exist. 🟢 A checker that only memorizes the 3 planted paraphrase sentences finds 12 of 12 (`step_04_with_a_key.py`). Mitigation: draw variants from a source other than the checker's author, and rotate them. |
| **Risk #3** | Scoring is by row, so a checker that flags the right row for the wrong reason gets full credit, and 🟢 9 rows carried two failures in the corrupted files (`step_03_what_it_hides.py`). Mitigation: keep one behavior per row, and queue a scoring-by-reason option. |
| **Out of scope** | Time series, joins, free-text synthesis, two failures on one row, scoring by reason rather than by row, any model call, hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is checker evaluations or specs, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Separate answer key** (one line per planted row: behavior, role, exact change; the data file has no label column) | 10 evaluations | 3 | 0.9 | 1 | 27.0 | Built in prototype |
| 2 | **Per-behavior scoring** (failures found, look-alikes flagged, clean rows flagged, weakest behavior named) | 10 evaluations | 3 | 0.9 | 1 | 27.0 | Built in prototype |
| 3 | **Exact counts, no overlapping rows** (a behavior is planted on exactly the rows it asks for) | 10 evaluations | 3 | 0.9 | 1.5 | 18.0 | Built in prototype |
| 4 | **Spec validation** (a bad spec exits 2 with one line, never a traceback) | 10 evaluations | 2 | 0.9 | 1 | 18.0 | Built in prototype |
| 5 | **Manifest with seed and hashes** (a rerun gives identical bytes; the key is checked against its hash) | 10 evaluations | 2 | 0.9 | 1 | 18.0 | Built in prototype |
| 6 | **Look-alike behaviors** (a negative role: rows the checker should leave alone) | 10 evaluations | 2 | 0.8 | 1 | 16.0 | Built in prototype |
| 7 | **Minimum-recall exit code** (`--min-recall`, exit 1 when a failure behavior falls under it) | 10 evaluations | 2 | 0.8 | 1 | 16.0 | Built in prototype |
| 8 | **Variants from a source other than the checker's author** | 10 evaluations | 3 | 0.5 | 3 | 5.0 | Sequenced for v0.2 |
| 9 | **Two failures on one row, as an option** | 10 evaluations | 2 | 0.5 | 3 | 3.3 | Sequenced for v0.2 |
| 10 | **Spec and key registry with a run record** (the manifest hash tied to a release) | 10 evaluations | 2 | 0.6 | 4 | 3.0 | Sequenced for v0.2 |
| 11 | **Scoring by reason, not only by row** | 10 evaluations | 2 | 0.5 | 4 | 2.5 | Queued |
| 12 | **Time series and joins** | 3 specs | 2 | 0.4 | 8 | 0.3 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from plant | What they fear |
| --- | --- | --- | --- |
| **Checker owner** | Owner | A keyed file they can run a change against and see which behavior moved. | A key so hard that nothing passes, or so easy that it flatters. |
| **Evaluation owner** | Writes specs | A spec format small enough to read in a review, and counts that do not move between seeds. | A generator that quietly changes what it plants between runs. |
| **Second-line reviewer** | Reads the weakest-behavior line | A named behavior and a look-alike count, not one recall figure. | Approving a checker on a number that hides a zero. |
| **Model-risk lead** | Approver of the minimum recall | A rule that a checker below the line does not ship. | A threshold set to the checker's own score. |
| **Internal audit** | Reader | A path from a score to the spec, the seed and the hashes that produced it. | A key edited after the fact to match the result. |
| **Security / CISO** | Approver | No real data in specs, nothing leaving the boundary, strings from input kept out of logs. | A planted file mistaken for real data, or a spec carrying a real record. |

---

## User stories (top 4)

1. **As the owner of a checker**, I want each planted failure to carry its behavior and the exact change, so a miss tells me what to fix.
2. **As a reviewer**, I want look-alikes planted and counted, so I can see a checker that buys recall by flagging everything.
3. **As an evaluation owner**, I want a rerun with the same seed to give identical bytes and exact counts, so a score changes only when the checker does.
4. **As internal audit**, I want the key tied to a hash in the manifest, so an edited key is refused instead of scored.

---

## KPIs

**North star:** share of checkers that gate a release whose release note names the weakest behavior and the look-alike false alarms from a keyed file. Target 🔴 100%.

**Inputs (leading):**
- Checkers with a spec that names at least one look-alike per failure behavior (prototype: 🟢 7 behaviors in the demo spec, 5 failures and 2 look-alikes, from `data/README.md`).
- Specs written by someone other than the checker's author (target: every spec).
- Variants per failure drawn from outside the checker's author (prototype: 🟢 3 distinct changes for memo_injection_paraphrase, `step_04_with_a_key.py`).

**Outputs (lagging):** prototype baselines from the demo spec.
- Failures found, naive and tuned. 🟢 71 of 84 and 72 of 84 (`step_04_with_a_key.py`).
- Look-alikes flagged, naive and tuned. 🟢 29 of 30 and 0 of 30 (`step_04_with_a_key.py`).
- Clean rows flagged. 🟢 26 of 530 naive and 8 of 530 tuned (`step_04_with_a_key.py`).
- Precision against the key. 🟢 0.56 naive and 0.90 tuned (`step_04_with_a_key.py`).
- Known miss. 🟢 12 paraphrased injections found by neither rule set (`step_04_with_a_key.py`).
- Checkers changed after a key was shown to their owner: not measured; the prototype has no such owner.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Pick one checker whose owner can share a redacted sample. Plant that sample's failure shapes. Score the checker and report the weakest behavior beside the recall figure the team already uses. |
| 1: Calibration | 4w | Add look-alikes for each failure. Read the false alarms. Set a minimum recall per behavior with the model-risk lead. |
| 2: Spec review | 6w | Specs go through pull request with a reviewer who did not write the checker. Variants come from outside the checker's author. |
| 3: Gate in CI | 4w | Run `score --min-recall` on every checker change and fail the step. Store the manifest hash with the run. |
| 4: Registry and run record | 8w | Keep specs, keys and manifests versioned. Record which key every release was scored against. |

---

## Open questions

1. **Who writes the failure variants?** In the prototype I do, which is why the scores are a ceiling. Recommendation: the reviewer or a red-team owner writes at least half, and the checker's author never sees them before the run.
2. **How many look-alikes per failure are enough?** The demo plants 2 look-alike behaviors for 5 failures. Recommendation: one per failure behavior as a floor, then add the false alarms that production review actually finds.
3. **Should scoring look at the reason a row was flagged?** Today a right row for the wrong reason gets full credit. Recommendation: keep row scoring for the pilot and list the cases where the reason differs, so the cost of the change is known.
4. **What minimum recall should block a release?** The prototype leaves it to the caller. Recommendation: set it per behavior, not pooled, and start with the value the team already reports so the first run changes nothing.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, two jobs.** `generate` and `score` are stateless: a spec in, three files out; a key and a flags file in, a score out. Production adds a registry, a run record and a CI step, all designed and none built.
- **Never silent.** A bad spec, a key that does not match its manifest hash, or a flags file with an unusable row id exits 2. A run with no flagged rows says that every planted failure is missed.
- **The key stays out of the data.** The data file has no label column, so a checker cannot read the answer.
- **Strings from input are data.** Output text escapes control characters, so a hostile behavior name cannot forge a line.

**What is next.** Run it on one checker whose owner can share a real, redacted sample, and plant that sample's failure shapes; add a second failure on one row as an option; draw variants from a source other than the checker's author.

**What would have to be true before a pilot.**
- A checker owner who will run a keyed file and read the weakest-behavior line.
- A redacted sample, so the planted shapes are the shapes that occur.
- A reviewer who is not the checker's author writes or approves the specs.
- A minimum recall per behavior agreed before the first run.
- No real record enters a spec.

---

*This PRD names [04 EvalForge](../04-evalforge-llm-eval-platform/), [40 Eval Gate](../40-eval-gate/), [38 Injection Pack](../38-injection-pack/) and [28 Tool Schema Drift](../28-tool-schema-drift/) as designed interlocks (🔴 designed, none built). No code is shared with any of them.*
