# PRD: scam-friction-sim

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a payments product review. It is not a record of a PRD landed at a named bank. The scenarios, the risk score and the rollout plan are mine, and every customer response is an invented assumption; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and no stopped percentage is a finding.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | scam-friction-sim: a small simulator that replays a file of payments against a hold policy and prints the scam value stopped next to the legitimate payments held, lost and delayed |
| **Owner** | The payments product owner deciding whether to build a hold, with the fraud operations lead as co-owner of the friction budget |
| **Stage** | Portfolio prototype on synthetic data; no model, no payment rail |
| **Primary user** | A fraud or payments product owner deciding whether to build a hold |
| **Secondary users** | The reviewer who has to say how many legitimate customers it will touch; customer care; internal audit |
| **Problem** | A bank that sees a suspicious real-time payment can hold it for a short time and hope the customer thinks again. The hold has two sides. It stops some scam payments, depending on what a held victim does. It also makes people who are paying a solicitor or a seller wait, and some of them give up. Teams usually look at the first side with a made-up stop rate and leave the second to a complaints report. In the planted set, 🟢 a blanket hold holds 336 of 11670 legitimate payments (2.9%) to stop 21.6% of scam value (`step_02_blanket_hold.py`). |
| **Solution** | Replays a file of payments against a policy: no hold, a blanket hold on first payments to a new payee, or a scored hold with a warning band. Prints the scam value stopped next to the legitimate payments held, lost and delayed, and the legitimate holds per scam payment stopped. Takes every customer response as a named assumption in a JSON file, so the same data can be rerun under different beliefs. Exits 1 when a friction budget or a stop target is broken, 2 for bad input. |
| **North-star metric** | Legitimate payments held per scam payment stopped, within a friction budget, measured in a controlled trial on one rail. Target 🔴 set by the trial and the bank's own tolerance. Today in this model: the stop side is invented, so no stop rate is a finding. |
| **Measured metrics (synthetic)** | 🟢 Scored hold: 20.1% of scam value stopped, 52 legitimate payments held, 2 lost and 1.1 legitimate holds per scam payment stopped, against 21.6%, 336, 10 and 6.6 for the blanket rule (`step_04_scored_hold.py`, `step_02_blanket_hold.py`). |
| **Modeled metrics** | 🟡 Utility (336/11670 − 52/11670) × 1,000,000 = 24,336 legitimate payments a year not held, assuming 1,000,000 legitimate payments a year reach the screen. It prices the friction only. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of a trial, a hold and the support it creates has not been sized. |
| **Risk #1** | The stop side rests on invented probabilities and the model has no hold-length curve. 🟢 Scaling the give-up probabilities by 0.5 and 1.5 moves the blanket rule from 15.5% to 31.3% (`step_03_deficiencies_exposed.py`). Mitigation: report the friction column as the result, and replace the assumptions with a controlled trial. |
| **Risk #2** | The data and the rules share an author, so the numbers are a ceiling for these rules, not a rate on real payments. The share of scams is far above any real share. 🟢 At one-tenth as common the blanket rule holds 65.9 legitimate payments per scam stopped (`step_03_deficiencies_exposed.py`). Mitigation: print the ratio at several scam shares, as step 3 does. |
| **Risk #3** | Scams to a payee the customer has paid before pass untouched. 🟢 144 of 330 scam payments get neither a hold nor a warning, including all 60 to an established payee (`step_04_scored_hold.py`). Mitigation: the report names the number every run, and a detector for this case is queued. |
| **Out of scope** | Any real stop rate, any claim that a hold of this length is permitted or advisable on a real rail, repeat attempts, payments moved to another rail, support calls, recovery after money has left, model calls, hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is planted scenarios, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates; items that wait on a trial score low on purpose, because confidence is low until it runs. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Named assumptions in a JSON file** (every probability and length checked, so a run can be redone under other beliefs) | 8 scenarios | 3 | 0.9 | 1 | 21.6 | Built in prototype |
| 2 | **Friction metrics** (legitimate payments held, lost and delayed, minutes waited, holds per scam stopped) | 8 scenarios | 3 | 0.9 | 1 | 21.6 | Built in prototype |
| 3 | **Input validation** (a bad column, a draw outside 0 to 1 or a bad assumption exits 2, never a traceback) | 8 scenarios | 2 | 0.9 | 1 | 14.4 | Built in prototype |
| 4 | **Blanket hold policy** (first payment to a new payee of 500 or more) | 8 scenarios | 2 | 0.9 | 1 | 14.4 | Built in prototype |
| 5 | **Budget flags** (`--max-held-pct` and `--min-stopped-pct` exit 1 when broken) | 8 scenarios | 2 | 0.8 | 1 | 12.8 | Built in prototype |
| 6 | **Scored hold with a warning band** (hold at a score, warn at the next band) | 8 scenarios | 3 | 0.8 | 2 | 9.6 | Built in prototype |
| 7 | **Sensitivity sweeps** (response probabilities, coaching, scam share, hold length) | 8 scenarios | 3 | 0.7 | 2 | 8.4 | Built in prototype |
| 8 | **Score fitted on real labeled data** (replaces my weights) | 8 scenarios | 3 | 0.4 | 5 | 1.9 | Sequenced for v0.2 |
| 9 | **Hold-length curve from a controlled trial** (replaces the assumptions) | 4 scenarios | 3 | 0.4 | 5 | 1.0 | Sequenced for v0.2 |
| 10 | **Repeat attempts after a release and a second rail** | 4 scenarios | 2 | 0.4 | 5 | 0.6 | Queued |
| 11 | **Established-payee detector** (closes the known miss) | 1 scenario | 3 | 0.3 | 4 | 0.2 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from scam-friction-sim | What they fear |
| --- | --- | --- | --- |
| **Payments product owner** | Owner and primary user | A comparison of policies they can take to a review, with the friction side as visible as the stop side. | A stop rate quoted as a finding when it rests on invented probabilities. |
| **Fraud operations lead** | Co-owner of the friction budget | A policy that stops scam value without a queue of holds nobody can work. | A blanket rule that holds so many legitimate payments that analysts stop trusting it. |
| **Customer care lead** | Consulted | A count of how many legitimate customers wait, and how many give up. | A hold that turns into a wave of calls from people paying a solicitor or a seller. |
| **Second-line risk reviewer** | Approver of the friction budget | A number for legitimate customers touched, and the assumptions written down. | A hold launched with no limit on who it delays. |
| **Legal counsel** | Approver of any live hold | A clear statement that nothing here says a hold is permitted on any rail. | A prototype read as advice that a 20-minute hold is allowed. |
| **Security / CISO** | Approver | Payment data kept inside the boundary and hostile strings kept out of logs. | Payment histories copied outside the platform to tune a score. |
| **Internal audit** | Reader | A path from a policy result to the file, the assumptions and the thresholds it used. | Assumptions changed between two runs with no record. |

---

## User stories (top 4)

1. **As a payments product owner**, I want the scam value stopped printed next to the legitimate payments held, lost and delayed, so I decide on both columns and not on a stop rate alone.
2. **As a reviewer**, I want every customer response written down as a named assumption in a file, so I can change it and rerun the same payments.
3. **As a fraud operations lead**, I want a friction budget that exits 1 when a policy holds more legitimate payments than I allow, so the check can sit in a review pipeline.
4. **As internal audit**, I want each run tied to the file, the assumptions and the thresholds it used, so I can reproduce it later.

---

## KPIs

**North star:** legitimate payments held per scam payment stopped, within a friction budget, measured in a controlled trial on one rail. Target 🔴 set by the trial and the bank's own tolerance.

**Inputs (leading):**
- Payments with the seven features a bank can see at the moment of payment (the prototype has 🟢 12,000 payments, from `data/README.md`).
- Labeled history with an explicit scenario for scams (the prototype has 🟢 330 scam payments in 4 scenarios, from `data/README.md`).
- Assumptions with a named source, belief or trial (the prototype's are all invented; 🟢 a held legitimate payment is abandoned with probability 0.03, `step_01_no_hold.py`).
- A friction budget agreed with the reviewer (the prototype assumes 0.5% of legitimate payments held, `step_04_scored_hold.py`).

**Outputs (lagging):** prototype baselines from the planted set.
- Legitimate payments held. 🟢 52 of 11670 (0.4%) with the scored hold, against 336 (2.9%) for the blanket rule (`step_04_scored_hold.py`).
- Legitimate payments lost. 🟢 2, against 10 (`step_04_scored_hold.py`).
- Minutes legitimate customers waited. 🟢 1158.5, against 6720 (`step_04_scored_hold.py`).
- Legitimate holds per scam payment stopped. 🟢 1.1, against 6.6 (`step_04_scored_hold.py`).
- Scam value stopped, under invented responses. 🟢 20.1%, against 21.6% (`step_04_scored_hold.py`).
- Known miss. 🟢 144 of 330 scam payments get neither a hold nor a warning (`step_04_scored_hold.py`).
- Complaints, calls and real victim behavior: not measured; the planted set has no customer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Replay | 4w | Run the simulator on one real labeled history the owner may share. Nothing is held; compare the friction column with the planted one. |
| 1: Calibration | 4w | Set the friction budget with the reviewer, refit the score on the real history, and get legal counsel's answer on whether a hold is permitted on the rail. |
| 2: Controlled trial | 12w | On one rail, hold a random share of the flagged payments and measure what held victims do, with the hold length as the variable. |
| 3: Replace the assumptions | 4w | Put the trial's results into the assumptions file and rerun every policy. Decide whether to build. |
| 4: Scored hold with a warning band | 8w | Live for a share of payments with a kill switch, a human release path and a run record. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **How long should the hold be?** The model gives the stop rate no dependence on length: 🟢 5, 20 and 60 minutes all stop 21.6% (`step_03_deficiencies_exposed.py`), an assumption and not a finding. Recommendation: make the length the variable in the trial, at 5, 20 and 60 minutes.
2. **What share of legitimate payments may be held?** The 0.5% budget is my assumption. Recommendation: have the reviewer and the fraud operations lead set it before the trial, from what customer care can absorb.
3. **Should a warning replace a hold for the middle band?** The scored rule warns at 6 and 7 and holds at 8 or more. Recommendation: keep the band for the trial, and compare it with a hold-only arm.
4. **Is a hold permitted on the rail at all?** I read no rule that sets or limits a hold on a real-time payment and cite none. Recommendation: legal counsel answers this before any trial is designed.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **An offline replay job.** The simulator is stateless: it reads a payments file, a truth file and an assumptions file, and returns a policy table. Production adds a controlled-trial feed, a reviewed policy, a run record and telemetry, all designed and none built.
- **Never silent.** A missing, empty or malformed file, a draw outside 0 to 1 or a probability outside its range exits 2. A policy run with a budget flag exits 1 when it is broken.
- **The labels do not come from the rules.** The scenario of each payment is drawn first and the rules never see it, and the draws are stored, so two policies see the same customers.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a threshold change that moves a column shows in the diff.

**What is next.** Replace the assumptions with results from a controlled trial the owner is allowed to run; add repeat attempts and a second rail; test a score fitted on real labeled data.

**What would have to be true before a pilot.**
- One real labeled history the owner may share, with the seven features.
- A friction budget agreed with the reviewer and the fraud operations lead.
- Legal counsel's answer on whether a hold is permitted on the rail.
- A way to run a controlled trial and to switch the hold off at once.
- The team agrees to quote the friction column and not an invented stop rate.

---

*This PRD names [08 OversightOps](../08-oversightops-hitl-workflow/), [25 KillSwitch](../25-killswitch-ai-fallback-drills/), [17 FairLens](../17-fairlens-credit-model-fairness/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). No code or data was imported from them.*
