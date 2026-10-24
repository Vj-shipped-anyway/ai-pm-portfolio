# PRD: dispute-clock

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a dispute-operations review. It is not a record of a PRD landed at a named bank. The windows, the holiday calendar, the planted disputes and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and I did not read Regulation E or any other rule for this project.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | dispute-clock: a command-line tool that puts each step of a customer dispute on its own clock, counts business days against a holiday file, and prints which clocks were missed and which are about to be |
| **Owner** | The operations lead who owns a dispute queue, with counsel or compliance as co-owner of the windows and the holiday calendar |
| **Stage** | Portfolio prototype on synthetic data |
| **Primary user** | The operations lead who owns a dispute queue |
| **Secondary users** | The second-line reviewer who asks which deadlines were missed and which are about to be; the dispute analysts who work the cases; internal audit |
| **Problem** | A dispute is not one deadline. The bank owes the customer an acknowledgement, a decision on provisional credit, an investigation result and a final notice, each with its own window and its own start. A case system with one flat target date cannot show which of these was missed, and a calendar-day countdown gets the due date wrong whenever a weekend or a holiday falls inside the window. In the planted set, 🟢 a flat 30-day target shows 32 of the 151 missed clocks and none of the 50 missed acknowledgements. |
| **Solution** | Reads a policy file of clocks (anchor event, window, business or calendar days, the events that satisfy it), a holiday file and a dispute file. Starts each clock at the date its policy row names, counts business days against the holiday file, and prints for every dispute each clock as on time, late, breached, running with days left, or not started. Lists missed clocks and clocks due soon, exits 1 when a clock was missed, and prints GitHub annotations on request. |
| **North-star metric** | Share of missed dispute clocks that the queue owner saw in the clock report by the next business day. Target 🔴 100%. Today in this model: a flat target shows a fraction of them. |
| **Measured metrics (synthetic)** | 🟢 519 of 524 statuses match the planted truth (99.0%); 150 of 151 missed clocks found; 4 false alarms; right on 108 of 109 clocks that land on the due day and 57 of 57 across a holiday (`step_04_business_day_clocks.py`). |
| **Modeled metrics** | 🟡 Utility (150/151 − 126/151) × 100 = 15.9 missed clocks a year found that a calendar-day countdown would miss, assuming 100 missed clocks reach the report each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The data and the rules share an author, so the numbers are a ceiling. The windows are assumptions, and the holiday file is a modeled calendar. Mitigation: run it on one real queue export, take the windows from counsel's reading of the rule that applies, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The tool ignores pauses. Four clocks on paused investigations are called missed when the plan says they were not, and one missed clock passes because its window class was recorded wrong (`step_04_business_day_clocks.py`). Mitigation: list paused and extended-class disputes for a person to confirm until a pause rule and a window-class audit exist. |
| **Risk #3** | A missing closure in the holiday file shifts every business-day due date after it, and both the tool and the truth use the same list. Mitigation: the tool prints a note when the file is empty or when a due date reaches a year with no holiday in it; the calendar changes by pull request with a named owner. |
| **Out of scope** | Reading any regulation; pausing or restarting a clock by rule; cut-off times within a day; business-day rollover of a due date that lands on a day off; sending notices; a model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is clocks or disputes, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Business-day clocks** (weekends and a holiday file skipped; calendar windows counted in calendar days) | 524 clocks | 3 | 0.9 | 1 | 1414.8 | Built in prototype |
| 2 | **Anchor events from the policy** (first contact for four clocks, the conclusion for the final notice, the earliest of several events satisfies a clock) | 524 clocks | 3 | 0.8 | 1 | 1257.6 | Built in prototype |
| 3 | **Missed and due-soon lists** (oldest due first, exit 1 when a clock was missed) | 524 clocks | 2 | 0.8 | 1 | 838.4 | Built in prototype |
| 4 | **Counsel-reviewed policy and holiday files** (a change by pull request, a source named per window) | 524 clocks | 3 | 0.6 | 3 | 314.4 | Sequenced for v0.2 |
| 5 | **Input validation** (empty, truncated, wrong-type, bad date or repeated id exits 2, never a traceback) | 150 disputes | 2 | 0.9 | 1 | 270.0 | Built in prototype |
| 6 | **Clock ledger** (one record per clock per as-of date, with file hashes) | 524 clocks | 2 | 0.5 | 4 | 131.0 | Sequenced for v0.2 |
| 7 | **CI output** (GitHub annotations, `--fail-on`, escaped strings) | 150 disputes | 2 | 0.8 | 2 | 120.0 | Built in prototype |
| 8 | **Pause rule** (information requested and received stop the investigation clock) | 150 disputes | 3 | 0.6 | 3 | 90.0 | Sequenced for v0.2 |
| 9 | **Cut-off times** (a notice after close of business counts for the next day) | 524 clocks | 1 | 0.5 | 4 | 65.5 | Sequenced for v0.3 |
| 10 | **Rollover option** (a calendar due date on a day off moves to the next business day) | 150 disputes | 1 | 0.5 | 2 | 37.5 | Sequenced for v0.3 |
| 11 | **Window-class audit** (list extended-class disputes for a person to confirm) | 17 disputes | 2 | 0.6 | 1 | 20.4 | Sequenced for v0.2 |
| 12 | **Several calendars** (one holiday file per jurisdiction or product) | 150 disputes | 1 | 0.4 | 5 | 12.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from dispute-clock | What they fear |
| --- | --- | --- | --- |
| **Dispute queue owner** | Owner | One report that says which step of which dispute was missed and which are due this week, with the days counted the way the policy counts them. | A report that calls a clock missed when the analyst can show the bank was waiting for the customer, so the report stops being read. |
| **Dispute analyst** | User | Their own cases listed with a due date and days left, and a status they can check by hand. | A tool that second-guesses a recorded date and gives them work to defend. |
| **Counsel or compliance** | Approver of windows and calendar | Every window traceable to a source they have read, and a change history for the policy file. | Windows copied from a prototype into production without a reading of the rule that applies. |
| **Second-line reviewer** | Reader | Missed clocks listed with the due date, the date done and the days over, reproducible from the inputs. | A due date that moved between two runs because a calendar changed without a record. |
| **Case-system owner** | Provider of the extract | A tool that reads the columns the system already holds, with a first-contact date among them. | A new feed to keep up for a report nobody asked for. |
| **Internal audit** | Reader | A path from a status back to the dates, the policy row and the holiday list that produced it. | Statuses that cannot be reproduced after the policy changes. |

---

## User stories (top 4)

1. **As the dispute queue owner**, I want each step of each dispute on its own clock, so a missed acknowledgement is not hidden behind an investigation that is still inside its window.
2. **As an analyst**, I want a due date counted in business days from the day the customer first reported, so a Monday holiday or a late log does not make an on-time notice look late.
3. **As a second-line reviewer**, I want missed clocks and clocks due within a few days in one list, oldest due date first, so I read the worst first.
4. **As internal audit**, I want every status tied to the policy row, the holiday file and the dates that produced it, so I can reproduce it later.

---

## KPIs

**North star:** share of missed dispute clocks that the queue owner saw in the clock report by the next business day. Target 🔴 100%.

**Inputs (leading):**
- Disputes with a first-contact date recorded that is the day the customer first told the bank (the prototype set has 🟢 150 disputes, and the log date is later than first contact on 98 of them, from `data/README.md`).
- Policy rows with a window that counsel has confirmed against a named source (target: every row; today 5 rows are assumptions).
- Years covered by the holiday file for every year a due date can reach (prototype: 🟢 11 holidays in 2026).
- Age of the case-system extract at the time of the run (target: under one business day).

**Outputs (lagging):** prototype baselines from the planted set.
- Statuses that match the planted truth. 🟢 519 of 524, against 454 of 524 for a calendar-day countdown (`step_04_business_day_clocks.py`, `step_02_calendar_countdown.py`).
- Missed clocks found. 🟢 150 of 151, against 32 of 151 shown by a flat target (`step_04_business_day_clocks.py`, `step_01_flat_target.py`).
- False alarms. 🟢 4, all on paused investigations (`step_04_business_day_clocks.py`).
- Disputes with at least one missed clock. 🟢 107 of 150 (`step_04_business_day_clocks.py`).
- Running clocks due within 5 days. 🟢 14 on 14 disputes (`step_04_business_day_clocks.py`).
- Known misses. 🟢 4 paused clocks called missed and 1 missed clock passed on a wrongly recorded window class (`step_04_business_day_clocks.py`).
- Missed clocks cleared within a day of the report: not measured; the planted set has no analyst.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the tool on one queue export beside the case system's flat target. Print the report, change nothing, and compare with what the queue owner already knew. |
| 1: Calibration | 4w | Counsel confirms each window and the holiday list against a named source. Hand-check a sample of statuses against the analysts' own count, including the paused and extended-class cases. |
| 2: Daily report | 6w | A scheduled run produces the missed and due-soon lists for the queue owner each business day. Exit 1 stays a flag, not a gate on anything. |
| 3: Pause and window-class rules | 6w | Add the pause rule and the window-class audit once counsel has said what a pause is. Re-run the planted set and compare with the pinned numbers. |
| 4: Ledger and audit | 8w | Write a clock record per as-of date with file hashes. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Which windows apply?** The five are mine and none is read from a rule. Recommendation: take them from counsel's reading of the rule that governs your products, put the source in the policy file's `basis` column, and re-run the planted set to see what moves.
2. **Where does the start date come from?** The tool starts clocks at the first-contact date. If a case system holds only the date the case was opened, the lift falls to what business days alone give: 🟢 37 wrong of 524 against 5 wrong with both fixes (`step_03_deficiencies_exposed.py`). Recommendation: capture first contact at intake; until then run both starts and report the gap.
3. **Should a paused investigation stop its clock?** The tool ignores `info_requested_on` and `info_received_on`, which produces 4 false alarms in the planted set. Recommendation: add the pause rule only after counsel confirms what a pause is, and until then list the paused disputes for a person.
4. **Who owns the holiday file?** A missing closure shifts every business-day due date after it. Recommendation: the operations calendar owner, changed by pull request, checked each January.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One scheduled job.** The tool is stateless: it reads three files and an as-of date and prints a report. Production adds a case-system extract, a reviewed policy config, a clock ledger and telemetry, all designed and none built.
- **Never silent.** A missing, empty or malformed input exits 2 and fails the run, even with `--fail-on never`. An empty holiday file, or a due date that reaches a year with no holiday in the file, prints a note.
- **Strings from input are data.** Text and annotations escape control characters, so a hostile dispute id cannot forge a workflow command.
- **Changes to a window are changes to a number.** A golden test pins the planted-set numbers, so a change that moves the missed count shows in the diff.

**What is next.** Run it against one real queue export that the owner may share; take the windows from counsel's reading of the rule that applies; add a pause rule; add cut-off times.

**What would have to be true before a pilot.**
- The case system exports a first-contact date, not only the date the case was opened.
- Counsel has confirmed each window and the holiday calendar against a named source.
- A named person owns the policy file and the holiday file.
- One real export can be shared, so the statuses are checked against real cases and not mine.
- The team agrees what the report is for: a flag for the queue owner, not a gate on any release.

---

*This PRD names [19 IncidentLedger](../19-incidentledger-ai-incident-response/), [50 Review Capacity](../50-review-capacity/), [75 Chargeback Packet](../75-chargeback-packet/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The clock vocabulary comes from 19; the engine here was rewritten and imports nothing from it.*
