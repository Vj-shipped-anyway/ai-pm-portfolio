# PRD: Shadow Score

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an agent-governance review. It is not a record of a PRD landed at a named bank. The checks, the thresholds, the planted problems and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Shadow Score: a command-line scorecard over two CSV files, the proposals an agent made in shadow mode and the outcomes people recorded, that prints HOLD or CLEAR |
| **Owner** | The person who owns the agent pilot, with a second-line reviewer as co-owner of the thresholds and the list of costly disagreements |
| **Stage** | Portfolio prototype on synthetic data |
| **Primary user** | The person who owns an agent pilot and has to say whether it should leave shadow mode |
| **Secondary users** | The steering group that reads the answer; the operations lead whose reviewers recorded the outcomes; the second-line reviewer; internal audit |
| **Problem** | An agent runs in shadow mode and people record their own outcome for the same cases. The report that follows is usually one agreement rate. It drops the cases the agent skipped, carries no interval, hides a weak segment, a bad week or an unusual reviewer, and treats every disagreement as equal. In the synthetic set, 🟢 the report says 851 of 930 proposals agreed (91.5%) and splits the number by nothing (`step_01_one_number.py`). |
| **Solution** | Joins the two files on `case_id` and reports what did not join. Prints the first-report rate with a 95% interval, the rate that counts abstentions as misses, and the rate of a rule that always proposes the most common outcome. Splits agreement by recorded outcome, segment, week, reviewer and stated confidence, and judges a group only when it has enough proposals. Runs ten checks, each PASS, FAIL or SKIP with the reason, and prints HOLD or CLEAR. Exits 1 on HOLD. |
| **North-star metric** | Share of shadow-mode exit decisions that rest on a scorecard with an interval, the group splits and a named list of costly disagreements. Target 🔴 100% of exit decisions. Today in this model: the decision rests on one rate. |
| **Measured metrics (synthetic)** | 🟢 HOLD with 6 of 10 checks failing, while the single rate meets its 90% bar; 4 of 5 planted problems found; 0 of 3 look-alikes fail a check (`step_04_with_scorecard.py`). |
| **Modeled metrics** | 🟡 Utility (4/5 − 0/5) × 10 = 8.0 weak spots a year named that a single rate hides, assuming 10 real weak spots sit in the shadow runs read each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the checks share an author and the planted rates were tuned to be visible, so the numbers are a ceiling. Mitigation: run it on one real shadow log and report the planted numbers and the real numbers apart. |
| **Risk #2** | The human outcome is not ground truth. 🟢 Of 69 outcome disagreements, the generator's truth sides with the person in 50 and with the agent in 19, and 17 of 851 agreements are both wrong (`step_03_deficiencies_exposed.py`). Mitigation: add a second-reviewer sample for the agreements; until then the scorecard says it measures agreement and not correctness. |
| **Risk #3** | The thresholds are my defaults, not a standard's, and a flat floor is a cliff. 🟢 Week 13 is a planted problem at 85.5% against a floor of 85.0% and passes (`step_04_with_scorecard.py`). Mitigation: a pilot owner and a second-line reviewer set the thresholds before the first real readout; a margin rule is next in the backlog. |
| **Out of scope** | Deciding that an agent may act; a second-reviewer audit of agreements; per-class agreement floors; correction for many comparisons; any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is readouts, or groups, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Input validation and join report** (empty, truncated, wrong-type or duplicate input exits 2; pending and unmatched cases counted) | 10 readouts | 3 | 0.9 | 1 | 27.0 | Built in prototype |
| 2 | **First-report rate with interval** (95% interval; abstentions also counted as misses) | 10 readouts | 3 | 0.9 | 1 | 27.0 | Built in prototype |
| 3 | **Group splits with a minimum size** (class, segment, week, reviewer; 30 proposals to be judged) | 33 groups | 3 | 0.8 | 3 | 26.4 | Built in prototype |
| 4 | **Margin rule for floors** (a group just above the floor is shown as near, not clear) | 33 groups | 2 | 0.5 | 2 | 16.5 | Sequenced for v0.2 |
| 5 | **Baseline check** (lift over a rule that always proposes the most common outcome) | 10 readouts | 2 | 0.8 | 1 | 16.0 | Built in prototype |
| 6 | **Confidence-band check** (agreement at stated confidence of 0.90 or more) | 10 readouts | 2 | 0.7 | 1 | 14.0 | Built in prototype |
| 7 | **Ten checks with a reason on each** (PASS, FAIL or SKIP; `--detail` and `--format json`) | 10 readouts | 3 | 0.9 | 2 | 13.5 | Built in prototype |
| 8 | **Risky-pair check** (`--risky PROPOSED:HUMAN`; costly disagreements as a share of proposals) | 10 readouts | 3 | 0.6 | 2 | 9.0 | Built in prototype |
| 9 | **Correction for many comparisons** (fourteen weeks, six segments and nine reviewers are judged separately) | 33 groups | 2 | 0.4 | 3 | 8.8 | Queued |
| 10 | **Agreement floor per outcome class** (REQUEST_DOCS sits at 82.8% and passes today) | 4 classes | 2 | 0.7 | 1 | 5.6 | Sequenced for v0.2 |
| 11 | **Second-reviewer sample for agreements** (both-wrong cases) | 10 readouts | 3 | 0.5 | 5 | 3.0 | Sequenced for v0.2 |
| 12 | **Shadow log feed and readout record** | 10 readouts | 2 | 0.6 | 4 | 3.0 | Sequenced for v0.3 |

---

## Stakeholder map

| Stakeholder | Role | What they want from Shadow Score | What they fear |
| --- | --- | --- | --- |
| **Agent pilot owner** | Owner | One readout that says HOLD or CLEAR and names the weak segment, week, reviewer or class, so the exit decision can be defended. | A CLEAR read as permission to act, or a HOLD with no reason that can be acted on. |
| **Steering group** | Reader of the decision | A short answer with the reason, and a clear line between "the agent agrees with people" and "the agent is right". | Approving an exit on one rate that hid a weak spot. |
| **Reviewers** | Source of the outcomes | Not being judged by the tool; a gap against peers read as a question, not a finding. | A reviewer gap used to rank people, when it may be the agent that is wrong. |
| **Operations lead** | Owner of the queue | A list of the segments and weeks to look at before go-live. | A flat floor that flags noise and sends the team after a group of eight cases. |
| **Second-line reviewer** | Approver of thresholds and risky pairs | Thresholds and the list of costly pairs written down and versioned. | Thresholds tuned until the result is CLEAR. |
| **Security / CISO** | Approver | Nothing leaving the boundary, no key in the path, strings from the files kept off the terminal. | Reviewer ids and case ids pasted into a ticket. |
| **Internal audit** | Reader | A path from a readout to the exact files, thresholds and risky pairs it used. | Thresholds changed silently between two readouts. |

---

## User stories (top 4)

1. **As the owner of an agent pilot**, I want the readout to show the interval and the rate that counts abstentions, so I do not defend a headline number whose denominator the agent partly chose.
2. **As the owner of an agent pilot**, I want a weak segment, week, reviewer or outcome class to fail a named check, so the exit decision names what to fix first.
3. **As a member of the steering group**, I want groups too small to judge shown as too few and not counted, so a handful of cases does not trigger a HOLD.
4. **As a second-line reviewer**, I want the thresholds and the costly pairs recorded with each readout, so I can reproduce it later.

---

## KPIs

**North star:** share of shadow-mode exit decisions that rest on a scorecard with an interval, the group splits and a named list of costly disagreements. Target 🔴 100% of exit decisions.

**Inputs (leading):**
- Shadow runs exported in the two CSV layouts with a stable `case_id` (the prototype set has 🟢 1000 proposals and 989 outcomes, from `data/README.md`).
- Reviewers with at least 30 proposals each, so a gap can be judged (prototype: 🟢 nine reviewers, one with 6 proposals shown as too few to judge, `step_04_with_scorecard.py`).
- Costly pairs named by the business before the first readout (target: every readout).
- Thresholds recorded with an approver (target: every readout).

**Outputs (lagging):** prototype baselines from the planted set.
- Planted problems found. 🟢 4 of 5 (`step_04_with_scorecard.py`).
- Look-alikes that failed a check. 🟢 0 of 3 (`step_04_with_scorecard.py`).
- Checks failed on the demo run. 🟢 6 of 10, decision HOLD (`step_04_with_scorecard.py`).
- Weak groups the single rate hid. 🟢 two drift weeks at 82.4% on 131 proposals against 93.0% elsewhere, with the all-weeks rate at 91.5% (`step_03_deficiencies_exposed.py`).
- Known miss. 🟢 week 13 passes at 85.5% against a floor of 85.0% (`step_04_with_scorecard.py`).
- HOLDs overturned after review: not measured; the planted set has no steering group.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the scorecard on one real shadow log beside the existing report. Print the decision, change nothing, and compare with what the steering group did. |
| 1: Calibration | 4w | Set the thresholds and the costly pairs with the pilot owner and a second-line reviewer. Read the SKIP lines and the groups shown as too few. |
| 2: Advisory readout | 4w | Attach the scorecard to every exit review for one agent. HOLD is a question for the steering group, not a block. |
| 3: Exit criterion | 6w | The steering group uses the lower end of the interval and the group checks as part of the exit criterion, with a written reason when it overrides a HOLD. |
| 4: Feed and record | 8w | Export the shadow log on a schedule, write a readout record, and add the second-reviewer sample and the per-class floor. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Who names the costly disagreements?** The demo marks three pairs, which are my call. Recommendation: the business owner of the queue names them in phase 1, and the list is versioned with the thresholds.
2. **What does the person's outcome stand for?** The truth sides with the person in 50 of 69 disagreements only because I wrote the truth. Recommendation: add a second-reviewer sample on a slice of agreements and disagreements before treating a reviewer gap as a finding about the reviewer.
3. **Should a floor have a margin?** A week half a point above the floor is clear today. Recommendation: add a "near" band in v0.2 and keep the floor as the only thing that fails a check.
4. **Where do the thresholds come from?** They are my defaults, from no standard. Recommendation: start there in shadow, then set them with the second-line reviewer against the first real log.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, two files.** The scorecard is stateless: it reads two exports and options and returns a decision. Production adds a reviewed config, a scheduled export and a readout record, all designed and none built.
- **Never silent.** Empty, truncated, mistyped or duplicate input exits 2 with one line. A check that cannot run prints SKIP with the reason, and the decision line counts the skips.
- **Strings from the files are data.** Group names and ids are printed with control characters escaped, so a hostile reviewer id cannot forge a line.
- **Changes to a check are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves a count shows in the diff.

**What is next.** Run it against one real shadow log whose owner can share the files; add a margin rule, a per-class floor and a second-reviewer sample.

**What would have to be true before a pilot.**
- The agent's proposals and the recorded outcomes share a stable case id and cover the same period.
- The business names the costly disagreements and a second-line reviewer approves the thresholds.
- One real log can be shared, so the false-alarm rate is measured on real cases and not mine.
- The steering group agrees that CLEAR means no check failed, not that the agent may act.

---

*This PRD names [27 AgentKit](../27-agentkit-reference-agent-and-playbook/), [05 AgentWatch](../05-agentwatch-agent-observability/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). Shadow Score copies none of 27's code and reads none of its data.*
