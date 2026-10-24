# PRD: fairlens six-test pack

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a model validation review. It is not a record of a PRD landed at a named bank. The six tests, the 36 planted portfolios and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. Every threshold is an assumption. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | fairlens: a command-line pack that reads a CSV of scores with a group column and prints PASS, REVIEW or FAIL for six tests, then an overall verdict |
| **Owner** | The head of model validation, with the fair-lending or compliance reviewer as co-owner of the thresholds |
| **Stage** | Portfolio prototype on synthetic data; no model, no hosted service |
| **Primary user** | A model risk analyst who receives a scores file from a credit team and has an afternoon |
| **Secondary users** | The credit analyst who has to answer the finding; the compliance reviewer; internal audit |
| **Problem** | A validator reviews a points scorecard. The decline reasons look consistent from one group to the next, and the model card shows accuracy and approval rate and nothing split by group. A feature inside the score can still move approvals by group, and neither view shows it. In the planted set, 🟢 the model card runs 0 of 6 fairness tests and a reason-code review passes 13 of 14 planted proxies (`step_01_model_card_only.py`, `step_02_reason_code_review.py`). |
| **Solution** | Reads a CSV with a group column, a score, an outcome and, optionally, the points of one suspected proxy and the listed decline reasons. Runs six tests: approval gap, adverse impact ratio with a bootstrap interval, cutoff sweep, proxy ablation with an accuracy check, reason-code pairs, reason naming. Prints PASS, REVIEW or FAIL for each, with the numbers and the rule behind them, and an overall verdict. Exits 1 at a chosen level, 2 on malformed input, and prints GitHub annotations on request. |
| **North-star metric** | Share of in-scope scorecard validations that include a fairlens run with a recorded verdict, a named proxy column and the production cutoff. Target 🔴 100%. Today in this model: the model card shows no test split by group. |
| **Measured metrics (synthetic)** | 🟢 T4 marks 7 of 14 planted proxies FAIL and 1 of 22 others; overall FAIL on 10 of 14 planted-proxy portfolios and 2 of 22 others; reason pairs pass on 6 of the 8 portfolios where the ablation fails (`step_04_with_fairlens.py`). |
| **Modeled metrics** | 🟡 Utility (10/14 − 0/14) × 7 = 5.0 scorecard portfolios a year with a proxy marked overall FAIL that a reason-code review would pass, assuming 7 such portfolios reach a validator each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces and of validator time has not been sized. |
| **Risk #1** | The planted set and the rules share an author, and I adjusted group sizes, proxy weights and coefficients after looking at earlier output. The numbers are a ceiling. Mitigation: run it on one real scores file the owner may share and report the planted numbers and the real numbers apart. |
| **Risk #2** | The thresholds are assumptions and the tool names one proxy column. 🟢 7 of 14 planted proxies are not marked FAIL by T4, and one portfolio with no proxy is (`step_04_with_fairlens.py`). Mitigation: calibrate the lines on the real portfolio's own noise; a list of proxy columns is next in the backlog. |
| **Risk #3** | Real credit files rarely carry group labels, so the tool reads a column it cannot check. Mitigation: the validator supplies labels from a governed source; a group-inference step with its own error check is queued. |
| **Out of scope** | Training or fitting a model; inferring groups from other fields; more than one proxy column; legal conclusions; any hosted service. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is portfolios, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Input validation** (empty file, repeated header, missing column, non-numeric score, outcome not 0 or 1, one group: exit 2, never a traceback) | 36 portfolios | 2 | 0.9 | 1 | 64.8 | Built in prototype |
| 2 | **T2 adverse impact ratio per group with a 95% bootstrap interval** | 36 portfolios | 3 | 0.8 | 2 | 43.2 | Built in prototype |
| 3 | **T1 approval gap** (REVIEW at a spread of 10 points, never FAIL alone) | 36 portfolios | 1 | 0.9 | 1 | 32.4 | Built in prototype |
| 4 | **T4 proxy ablation with an accuracy check** | 36 portfolios | 3 | 0.7 | 3 | 25.2 | Built in prototype |
| 5 | **T3 cutoff sweep** (30 points either side of the policy cutoff) | 36 portfolios | 2 | 0.7 | 2 | 25.2 | Built in prototype |
| 6 | **CI output** (text and GitHub annotations, `--fail-on` levels, escaped strings) | 36 portfolios | 1 | 0.9 | 2 | 16.2 | Built in prototype |
| 7 | **T5 reason pairs** (matched declines within 5 score points, with a within-group control) | 36 portfolios | 2 | 0.6 | 3 | 14.4 | Built in prototype |
| 8 | **T6 reason naming** (declines that turn on the proxy and omit its code) | 36 portfolios | 2 | 0.6 | 3 | 14.4 | Built in prototype |
| 9 | **Noise-aware accuracy guard** (an estimate of how noisy the accuracy change is, to replace the fixed 1-point line; closes the C14 false alarm) | 22 portfolios | 2 | 0.5 | 2 | 11.0 | Sequenced for v0.2 |
| 10 | **Run record** (file hash, thresholds, tests, verdict) | 36 portfolios | 2 | 0.6 | 4 | 10.8 | Queued |
| 11 | **Group-inference step with its own error check** | 36 portfolios | 3 | 0.4 | 5 | 8.6 | Queued |
| 12 | **A list of proxy columns** (closes the `two_proxies` miss) | 14 portfolios | 3 | 0.6 | 4 | 6.3 | Sequenced for v0.2 |

---

## Stakeholder map

| Stakeholder | Role | What they want from fairlens | What they fear |
| --- | --- | --- | --- |
| **Model risk analyst** | Primary user | A verdict with the numbers and the rule behind each test, from one scores file, in an afternoon. | A tool that flags everything or nothing, so the finding does not survive the credit team's reply. |
| **Head of model validation** | Owner | One repeatable set of tests across scorecards, with thresholds that are written down. | Thresholds changed between two validations with no record. |
| **Credit analyst** | Answers the finding | The exact column and the exact cutoff that produced a FAIL, so the answer is a fact and not a debate. | A FAIL on a feature that earns its place. |
| **Compliance / fair-lending reviewer** | Approver of thresholds | Clear wording that a ratio is a screen and not a legal finding. | A statistic read as a legal conclusion. |
| **Legal counsel** | Consulted | No claim that goes beyond what was read and tested. | A prototype quoted as evidence about a real portfolio. |
| **Security / CISO** | Approver | Applicant-level files kept inside the boundary, hostile strings kept out of logs. | A scores file copied to a laptop or a hosted tool. |
| **Internal audit** | Reader | A path from a verdict to the file, the cutoff and the thresholds it used. | A re-run that gives a different answer. |

---

## User stories (top 4)

1. **As a model risk analyst**, I want one command to run six tests on a scores file and print a verdict for each, so my review does not depend on which tests I remembered to run.
2. **As a model risk analyst**, I want the ablation to say what happens to the lowest approval ratio and to accuracy when a column's points are removed, so I can tell a proxy from a feature that earns its place.
3. **As a credit analyst**, I want a FAIL to name the test, the group, the numbers and the rule, so I can answer with a fact.
4. **As internal audit**, I want each verdict tied to the file, the cutoff and the thresholds it used, so I can reproduce it later.

---

## KPIs

**North star:** share of in-scope scorecard validations that include a fairlens run with a recorded verdict, a named proxy column and the production cutoff. Target 🔴 100%.

**Inputs (leading):**
- Scores files with group labels from a governed source (the prototype set has 🟢 36 portfolios of 760 to 830 applicants each, 29,460 applicants in all, from `step_01_model_card_only.py`).
- Scorecards with a named suspected proxy column and reason codes on file.
- Real portfolios whose clean-run noise is known, so the thresholds can be set against it (the prototype set has 🟢 22 portfolios with no planted proxy).
- Mechanisms in the evaluation set (the prototype has 7: clean, legit_gap, small_group_noise, proxy_gap, proxy_predictive, two_proxies, quiet_proxy, from `data/README.md`).

**Outputs (lagging):** prototype baselines from the planted set.
- Planted proxies marked FAIL by the ablation. 🟢 7 of 14, with 1 of 22 others (`step_04_with_fairlens.py`).
- Overall verdict. 🟢 FAIL on 10 of 14 planted-proxy portfolios and 2 of 22 others (`step_04_with_fairlens.py`).
- Reason naming. 🟢 T6 is FAIL on 4, REVIEW on 25 and PASS on 7 of 36; no portfolio reads PASS overall, 0 of 36 (`step_04_with_fairlens.py`).
- Known misses. 🟢 7 of 14 planted proxies are not marked FAIL by T4 (`step_04_with_fairlens.py`).
- FAILs overturned after the credit analyst's reply: not measured; the planted set has no analyst.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the pack on one real scores file with `--fail-on never`. Print the verdict, escalate nothing, and compare with what the validator concluded by hand. |
| 1: Calibration | 4w | Confirm the group labels with their owner. Set the 0.80 screen, the 1-point accuracy guard and the reason-pair margins against the real portfolio's own noise. |
| 2: Advisory in validation reports | 6w | Include the verdict and the numbers in the validation report. A FAIL is a question to the credit analyst, not a finding. |
| 3: Required for scorecards in scope | 6w | A run with a named proxy column is part of every validation in scope. The noise-aware accuracy guard and a list of proxy columns are added. |
| 4: Run record and group inference | 10w | Write a record per run. Add a group-inference step with its own error check. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **What counts as no real cost in accuracy?** The 1-point guard is an assumption and I did not estimate how noisy the accuracy change is; the one false FAIL (C14) is a 30-applicant group that moves on a re-score. Recommendation: keep 1 point for the pilot, print the accuracy change next to every ablation, and build the noise-aware guard before any FAIL leaves the validation team.
2. **Should T6 keep every portfolio at REVIEW?** No portfolio reads PASS overall, because a reason list built from points lost rarely names the postcode points that tipped a decision. Recommendation: keep T6 as a finding about the notice, report it apart from the group verdict, and revisit once a real notice is tested.
3. **Where do the group labels come from?** Real credit files rarely carry them, and the tool reads a column and never infers one. Recommendation: the validator supplies them from a governed source, and the group-inference step stays queued until it can carry its own error check.
4. **Should a FAIL block anything?** Recommendation: no. It is a question to the credit analyst with the numbers attached. Whether to change a scorecard stays with its owners and legal counsel, and the 0.80 ratio is a screening statistic, not a legal finding.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One batch job inside the validation boundary.** The pack is stateless: it reads one scores file and returns six verdicts. Production adds reviewed thresholds, an intake with file hashes, a run record and telemetry, all designed and none built.
- **Never silent.** A missing, empty or malformed file exits 2. A test that lacks its columns prints NOT RUN and the overall line says which, so a missing proxy column cannot read as a pass.
- **Strings from input are data.** Group labels and column names are escaped before they reach a log or an annotation.
- **Changes to a threshold are changes to a number.** A golden test pins the planted-set numbers, so a threshold change that moves a verdict shows in the diff.

**What is next.** Run it on one real scores file the owner may share; accept a list of proxy columns; add a group-inference step with its own error check.

**What would have to be true before a pilot.**
- A scores file with group labels from a governed source, and an owner who can share it inside the boundary.
- A named suspected proxy column and a production cutoff.
- The compliance reviewer agrees the 0.80 ratio is a screen and agrees the thresholds in the pilot.
- A credit analyst who will answer a FAIL with the file and the cutoff.
- The validation team agrees which level fails the step.

---

*This PRD names [17 FairLens](../17-fairlens-credit-model-fairness/), [09 LineageLog](../09-lineagelog-ai-decision-audit/), [11 TierGate](../11-tiergate-ai-usecase-intake/) and [02 DriftSentinel](../02-driftsentinel-model-drift-monitoring/) as designed interlocks (🔴 designed, none built). The six-test shape and the planted postcode proxy come from 17; no code was imported.*
