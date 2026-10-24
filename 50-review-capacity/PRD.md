# PRD: Review Capacity calculator

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a headcount review for an AI-assisted process. It is not a record of a PRD landed at a named bank. The queues, the targets and the sizing rules are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Review Capacity: a command-line calculator that returns the reviewers needed at the desk, and the roster that implies, for a human-in-the-loop queue, with a command that measures its inputs from a case log |
| **Owner** | The person who owns a review queue behind an AI system, with whoever approves the headcount as co-owner of the targets |
| **Stage** | Portfolio prototype on synthetic data |
| **Primary user** | The person who owns a review queue behind an AI system and has to say how many reviewers it needs |
| **Secondary users** | Whoever approves the headcount; the workforce planner who turns seats into a roster; the program manager who has to defend the number; the second-line reviewer who asks whether reviewers are rushed |
| **Problem** | A human-in-the-loop queue is sized by feel or by dividing the day's work by the hours in a shift. Both leave the queue to absorb every cluster of arrivals and every long case, and the reviewers who absorb it are the ones asked to look carefully. The program manager who has to defend a headcount number has no small, inspectable tool to produce one. In the planted set, 🟢 staffing to the average workload meets both limits on 0 of 13 queues and leaves 2300 of 7049 cases (32.6%) waiting past their target. |
| **Solution** | `size` reads one row of assumptions per queue (arrival rate, opening batch, handling time and its spread, wait target, utilization cap, shrinkage) and prints the reviewers needed at the desk, the roster that implies, and the answer from Erlang C on the mean rate for comparison. It compares the roster with a current headcount when one is given, exits 1 when a queue is short, and prints GitHub annotations on request. `fit` measures the assumption columns from a case log, so the inputs are not guesses. |
| **North-star metric** | Share of review-queue headcount decisions where the approved number meets both the wait target and the utilization cap on the days that follow. Target 🔴 100%. Today in this model: a mean-workload number meets both on none of the planted queues. |
| **Measured metrics (synthetic)** | 🟢 12 of 13 queues meet both limits; 10 of 13 land on the true number and 13 of 13 within one; 260 of 7049 cases (3.7%) are late against 11.4% for Erlang C; the two opening-batch queues are sized right and 2 of 2 hard negatives are not over-staffed (`step_04_with_review_capacity.py`). |
| **Modeled metrics** | 🟡 Utility (12/13 − 10/13) × 20 = 3.1 queue sizings a year that meet both limits where Erlang C on the mean would not, assuming 20 queues are sized each year. The wait targets, the 0.85 utilization cap and the 25% shrinkage are my choices. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The synthetic queues and the rules share an author, so the numbers are a ceiling. Each true number is one 10-day replay. Mitigation: run it on one real queue's log that its owner may share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | Inputs measured on a quiet fortnight will under-staff the busy one. 🟢 One queue that rose after the history was taken gets 4 reviewers where 5 were needed (`step_04_with_review_capacity.py`). Mitigation: a drift guard that compares the latest days with the days fitted; until then, fit on a long window and a short one and size on the higher. |
| **Risk #3** | The variability term is not shown to help on 13 queues, and one bursty queue is still short. 🟢 The variability term changed 2 of 13 answers, one better and one worse (step 3). Mitigation: the table shows the mean-only column beside the seats, and the bursty case is listed for a person to size by hand. |
| **Out of scope** | Priority classes, skill-based routing, abandonment, time-of-day staffing beyond the opening batch, shift scheduling, cost, any model call, any measure of review quality, hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is queues. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Seats from the wait target and the utilization cap** (raise reviewers at the desk until both hold) | 13 queues | 3 | 0.9 | 1 | 35.1 | Built in prototype |
| 2 | **Roster and headcount check** (seats divided by one minus shrinkage, rounded up; exit 1 when a queue is short) | 13 queues | 2 | 0.9 | 1 | 23.4 | Built in prototype |
| 3 | **Input validation** (empty, truncated, wrong-type, out-of-range or repeated input exits 2, never a traceback) | 13 queues | 2 | 0.8 | 1 | 20.8 | Built in prototype |
| 4 | **Opening-batch drain** (cases that land at open are worked off at the rate the seats serve) | 13 queues | 3 | 0.8 | 2 | 15.6 | Built in prototype |
| 5 | **`fit` from a case log** (arrival rate, spread of gaps, handling time and its spread measured from logged days) | 13 queues | 3 | 0.6 | 2 | 11.7 | Built in prototype |
| 6 | **Back-test job** (replay the latest days against the recommended seats and report the late share) | 13 queues | 3 | 0.6 | 3 | 7.8 | Sequenced for v0.2 |
| 7 | **CI output** (GitHub annotations, `--fail-on`, escaped strings) | 13 queues | 1 | 0.8 | 2 | 5.2 | Built in prototype |
| 8 | **Drift guard** (compare the latest days with the days fitted and warn when the live rate moved) | 13 queues | 2 | 0.5 | 3 | 4.3 | Sequenced for v0.2 |
| 9 | **Several replays per sizing** (a band around the true number instead of one 10-day replay) | 13 queues | 2 | 0.6 | 4 | 3.9 | Sequenced for v0.3 |
| 10 | **Variability term** (arrival and handling spread scale the tail of the wait) | 13 queues | 1 | 0.4 | 2 | 2.6 | Built in prototype |
| 11 | **Priority classes and skill routing** | 13 queues | 2 | 0.4 | 6 | 1.7 | Queued |
| 12 | **Time-of-day staffing and shift scheduling** | 13 queues | 2 | 0.4 | 8 | 1.3 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Review Capacity | What they fear |
| --- | --- | --- | --- |
| **Review queue owner** | Owner | A headcount number they can defend line by line, with the assumptions listed beside it. | A number that looks precise, is wrong by a reviewer or two, and is the one they signed. |
| **Headcount approver** | Approver | One page: seats, roster, what is held today and the gap. | Paying for reviewers the model asked for because an input was a guess. |
| **Reviewers** | Affected | A queue that is not run flat out, so a careful look is possible. | A cap that exists on paper while the queue runs hot. |
| **Workforce planner** | Consulted | Seats separated from the roster, with shrinkage as an explicit input they own. | A shrinkage figure they did not set. |
| **Second-line reviewer** | Reader | A sizing that can be reproduced from the log, and a clear statement that review quality is not measured. | A utilization cap presented as a finding. |
| **Program manager for the AI system** | User | A short path from case log to a defensible number. | A tool that needs a model or a vendor to run. |

---

## User stories (top 4)

1. **As a review queue owner**, I want the reviewers needed at the desk for a wait target and a utilization cap, so I do not divide the day's work by a shift and hope.
2. **As a queue owner with an opening batch**, I want the cases that land at open worked off at the rate the seats serve, so the morning does not break the target that the average hid.
3. **As a program manager**, I want the arrival and handling columns measured from a case log, so the inputs to the sizing are not guesses.
4. **As a headcount approver**, I want the roster beside what is held today, and a non-zero exit when a queue is short, so the gap is a line I can act on.

---

## KPIs

**North star:** share of review-queue headcount decisions where the approved number meets both the wait target and the utilization cap on the days that follow. Target 🔴 100%.

**Inputs (leading):**
- Queues with a case log long enough to fit (the prototype set has 🟢 13 queues over 20 working days of 8 hours, from `data/README.md`).
- Queues whose wait target, share and utilization cap were set by the owner, not left at the defaults (target: every queue).
- Queues whose assumptions were measured on a window that was then back-tested (prototype: replayed on the 10 days after the 10 fitted).
- Shrinkage supplied by the workforce planner (prototype: 25% on every queue, my choice).

**Outputs (lagging):** prototype baselines from the planted set.
- Queues that meet both limits. 🟢 12 of 13, against 10 of 13 for Erlang C and 0 of 13 for the average workload (steps 4, 2 and 1).
- Queues that land on the true number. 🟢 10 of 13, and 13 of 13 within one (`step_04_with_review_capacity.py`).
- Cases late. 🟢 260 of 7049 (3.7%), against 802 of 7049 (11.4%) for Erlang C (`step_04_with_review_capacity.py`, `step_02_erlang_c.py`).
- Reviewers at the desk. 🟢 62 chosen where 61 were needed, against 54 for Erlang C (`step_04_with_review_capacity.py`).
- With assumptions measured on the previous 10 days. 🟢 7 of 13 land on the true number, 12 of 13 within one, and 10 of 13 meet both limits (`step_04_with_review_capacity.py`).
- Known misses. 🟢 One bursty queue is one reviewer short and two queues get one reviewer more than needed (`step_04_with_review_capacity.py`).
- Headcount decisions overturned after review: not measured; the planted set has no approver.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run `fit` and `size` on a few real queues from their case logs, beside the headcount held today. Print the table, change nothing. |
| 1: Calibration | 4w | Set the wait target, the share and the utilization cap with each queue owner, and the shrinkage with the workforce planner. Back-test the number on the days after the log. |
| 2: Headcount review | 6w | The sizing, its assumptions and the roster go into the headcount request. The approver sees the gap in the same table. |
| 3: Drift guard and back-test | 6w | A scheduled back-test and a warning when the live rate moves away from the fitted window. |
| 4: Record and priorities | 8w | Write a sizing record per run. Add a replay with priority classes and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Which wait target, share and utilization cap?** All three are policy, and the 0.85 cap is a stand-in for "a reviewer should not run flat out"; nothing here measures review quality. Recommendation: the queue owner and the approver set them per queue and record the reason beside the number.
2. **How many days of history?** The prototype fits on 10 days. A fortnight that was quiet under-staffs the busy one: one queue's live rate went from 5.31 cases an hour to 6.78 after the history. Recommendation: fit on a short and a long window and size on the higher until a drift guard exists.
3. **What about a bursty queue?** The tool reads the spread of the gaps between arrivals and does not see busy and quiet spells well: the hourly arrival counts of the bursty queue have a variance over mean of 3.66, against 0.80 for a plain queue. Recommendation: show the hourly dispersion beside the answer, and have a person size queues far from 1 by hand until real logs say how to treat them.
4. **Whose shrinkage?** 25% is mine and only converts seats into a roster. Recommendation: the workforce planner supplies it from leave and training records.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One calculator.** It is stateless: it reads a file and prints a table. Production adds a reviewed target config, a back-test job and a sizing record, all designed and none built.
- **Never silent.** Empty, truncated or out-of-range input exits 2. A file with no `current_headcount` prints that nothing was compared and does not claim the queues are covered.
- **Strings from input are data.** A queue id is checked against a pattern, and text and annotations are escaped, so a hostile id cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, and another checks that the tool's replay agrees with the generator's on all 13 queues.

**What is next.** Run it on one real queue's log that its owner may share; add a second replay with priority classes; check the sizing against several replays of the same assumptions instead of one.

**What would have to be true before a pilot.**
- A case log with `queue_id`, `day`, `arrival_min`, `handle_min` and `channel` for at least ten working days.
- The owner has set the wait target, the share and the cap, and knows they are policy.
- A named approver will read the assumptions beside the number.
- The queue is close enough to first-come-first-served that a replay without priorities means something.
- The team agrees that the output is a floor to defend, not a forecast.

---

*This PRD names [08 OversightOps](../08-oversightops-hitl-workflow/), [24 PortfolioBoard](../24-portfolioboard-ai-program-portfolio/) and [49 Dispute Clock](../49-dispute-clock/) as designed interlocks (🔴 designed, none built). The questions come from 08 and 24; their numbers and code are not used here.*
