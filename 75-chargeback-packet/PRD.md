# PRD: chargeback packet check

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a merchant-services review. It is not a record of a PRD landed at a named bank. The reason codes, evidence lists and windows are invented, and the 100 dispute cases are planted by me; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | chargeback-packet: a command-line tool that takes a dispute case and its packet, looks up the evidence list for the reason code, runs the response clock, checks that the documents agree with the case, and prints READY, FIX or LATE |
| **Owner** | The person in merchant operations, or a bank's merchant-services team, who assembles and sends the packet, with the reviewer who signs it off as co-owner of the evidence list |
| **Stage** | Portfolio prototype on synthetic data; no CI wrapper or export adapter is built |
| **Primary user** | The person who assembles and sends the dispute response packet |
| **Secondary users** | The reviewer who signs it off; the merchant-services manager who owns the queue; finance, who carries the disputed value; internal audit |
| **Problem** | A merchant who disputes a chargeback has one response window and one packet to send. Each reason code asks for different evidence, some of it either-or. People assemble the packet from whatever they can find, and nothing compares it with the list or watches the clock until the answer comes back. In the planted set, 🟢 57 of 100 packets go out with a planted fault, carrying $58,502.91 of $103,404.68 in disputed value (`step_01_no_check.py`). |
| **Solution** | Looks up the evidence list for the case's reason code and reports each required item that is missing, naming the alternatives. Runs the response clock: days left for a draft, on time or late for a sent packet, with the last day counting. Checks consistency: every document names this order, post-purchase documents are not dated before the purchase, none is dated after the check date, the order record covers the disputed amount, the packet stays inside the page limit. Prints READY, FIX or LATE per packet and exits 1 when any is not READY, 2 when the input cannot be read. |
| **North-star metric** | Share of dispute packets sent after a check against the acquirer's list and the clock, with the decision recorded. Target 🔴 100%. Today in this model: no packet is checked. |
| **Measured metrics (synthetic)** | 🟢 34 of 34 visible faults sent to FIX; 14 of 14 late packets marked LATE; 0 of 43 ready packets flagged; the decision matches the planted truth in 91 of 100; a person opens 48 of 100 packets (`step_04_with_check.py`). |
| **Modeled metrics** | 🟡 Utility (37/57 − 9/57) × 200 = 98.2 faulty packets a year that counting documents would send and the check holds, assuming 200 faulty packets a year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The recipe for a good packet and the rules share an author, so the numbers are a ceiling, although the set includes five kinds of hard negative and two kinds of fault the rules cannot see. Mitigation: run it on one real queue, with the acquirer's list, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The evidence list is invented and has to be replaced with the one a real acquirer publishes before the output means anything for a live dispute. Mitigation: load the published list into `rules.json` with a version and a source, reviewed by merchant services, before any pilot. |
| **Risk #3** | The checker never opens a file, so a document with the right label and the wrong content passes. 🟢 9 of 9 wrong-file packets pass as READY (`step_04_with_check.py`). Mitigation: a person still opens the packets the check cannot see into; a later version adds a hash or page-count check against the file. |
| **Out of scope** | Reading the documents themselves; predicting whether a dispute is won; any card network's real reason codes, lists or deadlines (the bundled ones are invented); weekends, holidays and time zones; filing the response; any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is cases or packets, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Completeness check** (required items per reason code, either-or alternatives named) | 100 cases | 3 | 0.9 | 1 | 270.0 | Built in prototype |
| 2 | **Response clock** (calendar days from receipt, last day counts, draft judged on the check date, sent packet on its sent date) | 100 cases | 3 | 0.9 | 1 | 270.0 | Built in prototype |
| 3 | **Input validation** (empty, wrong-type or truncated input exits 2, never a traceback; strings from input escaped) | 100 cases | 2 | 0.9 | 1 | 180.0 | Built in prototype |
| 4 | **Consistency checks** (order id, dates, amount, page limit) | 100 cases | 3 | 0.8 | 2 | 120.0 | Built in prototype |
| 5 | **Load the acquirer's published list** in place of the invented one | 100 cases | 3 | 0.7 | 2 | 105.0 | Sequenced for v0.2 |
| 6 | **Business-day option for the window** | 100 cases | 2 | 0.6 | 2 | 60.0 | Sequenced for v0.2 |
| 7 | **Days-left alert** (escalate a FIX with 3 or fewer days left) | 34 drafts | 2 | 0.6 | 1 | 40.8 | Sequenced for v0.2 |
| 8 | **Export adapter** (read open disputes from the case system) | 100 cases | 2 | 0.5 | 4 | 25.0 | Sequenced for v0.2 |
| 9 | **Decision record per run** (rules version, case hash, findings) | 100 cases | 1 | 0.6 | 4 | 15.0 | Sequenced for v0.2 |
| 10 | **Second presentment and pre-arbitration stages** | 100 cases | 2 | 0.3 | 8 | 7.5 | Queued |
| 11 | **Evidence strength** (a weak document against a strong one) | 100 cases | 1 | 0.2 | 8 | 2.5 | Queued |
| 12 | **Hash or page-count check against the file itself** (the wrong-file case) | 9 packets | 3 | 0.3 | 8 | 1.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from chargeback-packet | What they fear |
| --- | --- | --- | --- |
| **Packet assembler** | Owner | A list of what is missing, with the alternatives, and the days left, before the packet leaves. | A checker that holds good packets and gets bypassed. |
| **Reviewer** | Approver of the evidence list | A packet that arrives with its findings, so sign-off is a read and not a hunt. | Signing a packet that carries the wrong file. |
| **Merchant-services manager** | Owner of the queue | A count of packets to open and of drafts with few days left. | Finding out about a missed window from the other side. |
| **Finance** | Informed | The disputed value inside packets that are FIX or LATE. | A write-off nobody saw coming. |
| **Security / CISO** | Approver | Case and document metadata only, nothing leaving the boundary, strings from input kept out of logs. | Customer records copied into a CI log. |
| **Internal audit** | Reader | A path from a send decision to the list version and the case it used. | An evidence list edited silently between two runs. |

---

## User stories (top 4)

1. **As the packet assembler**, I want each missing required item reported with its either-or alternatives, so I know which one document would close the gap.
2. **As the packet assembler**, I want the days left on every draft, with the last day counting, so I fix the packets that are about to close first.
3. **As a reviewer**, I want a packet whose documents name a different order, are dated before the purchase or after the check date, or fall short of the disputed amount to arrive flagged, so I read the finding and not the whole packet.
4. **As the merchant-services manager**, I want READY, FIX and LATE counts for a list of packets, so I know how many to open and how many are already lost to the clock.

---

## KPIs

**North star:** share of dispute packets sent after a check against the acquirer's list and the clock, with the decision recorded. Target 🔴 100%.

**Inputs (leading):**
- Reason codes with a loaded list and window (prototype: 🟢 6 reason codes, 100 dispute cases, a page limit of 12, `data/README.md`).
- Open disputes exported with a received date and a reason code (target: every open dispute).
- Drafts checked with days left (prototype: 🟢 7 of 34 drafts to fix have 3 or fewer days left, `step_04_with_check.py`).
- Lists with a named source and a version (target: every list).

**Outputs (lagging):** prototype baselines from the planted set.
- Visible faults sent to FIX. 🟢 34 of 34 (`step_04_with_check.py`).
- Late packets marked LATE. 🟢 14 of 14 (`step_04_with_check.py`).
- Ready packets flagged by mistake. 🟢 0 of 43 (`step_04_with_check.py`).
- Packets a person opens. 🟢 48 of 100 (`step_04_with_check.py`).
- Known miss. 🟢 9 of 9 wrong-file packets pass (`step_04_with_check.py`).
- Disputes won or lost after the check: not measured; the planted set has no outcome.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the check on one reason code with the acquirer's published list loaded. Print findings, hold nothing, and compare with what the team did. |
| 1: Calibration | 4w | Check the window and slots against the acquirer's published text. Decide the days-left line that escalates a FIX. |
| 2: Hold on FIX | 4w | A FIX stops the send until a person clears it. LATE goes to the manager. |
| 3: All reason codes | 6w | Load every list the acquirer publishes. Add the business-day option. |
| 4: Export and record | 8w | Read open disputes from the case system and write a decision record per run. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Whose list is it?** The bundled list is invented. Recommendation: the acquirer's published list, loaded into `rules.json` with a source and a version, and changed only by a reviewed change.
2. **Calendar days or business days?** The prototype counts calendar days and has no weekend or holiday rule. Recommendation: keep calendar days as the conservative default until the business-day option exists, and always count the last day.
3. **At what days-left line does a FIX escalate?** 🟢 7 of 34 drafts to fix have 3 or fewer days left (`step_04_with_check.py`). Recommendation: start at 3 and set the line against the real queue.
4. **Can the checker ever see a wrong file?** Today it cannot. Recommendation: keep a person opening the packets the check cannot see into, and add a hash or page-count check against the file in a later version.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the send step.** The check is stateless: it reads a case file, an evidence list and a date, and returns a decision. Production adds a reviewed list, an export adapter and a decision record, all designed and none built.
- **Never silent.** A missing, empty or malformed case or rules file exits 2 and fails the step. A document type on no list is a note, not a pass. An empty case list says nothing was checked.
- **Strings from input are data.** Case ids, document ids and types are escaped and cut before they reach a log, so a hostile string cannot forge an output line.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the FIX or LATE count shows in the diff.

**What is next.** Load a real acquirer's published list; add a business-day option for the window; add a hash or page-count check against the file so a wrong file is at least sometimes visible.

**What would have to be true before a pilot.**
- The list loaded is the acquirer's own, with a source and a version.
- Open disputes can be exported with the received date, reason code and document metadata.
- A named person owns the list and will clear a FIX.
- The team agrees what days-left line escalates, and who sees a LATE.
- Case and document metadata can be held in one controlled place.

---

*This PRD names [49 Dispute Clock](../49-dispute-clock/), [68 KYB Packet Check](../68-kyb-packet-check/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built).*
