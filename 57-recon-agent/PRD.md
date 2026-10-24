# PRD: recon-agent

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a finance operations review. It is not a record of a PRD landed at a named bank. The rules, the planted month and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and the approver in every run is a script I wrote.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | recon-agent: a command that matches a bank statement to a cash book with five rules, cites the lines and facts behind every match, re-checks each match before it posts, and holds the riskier ones for a recorded approval |
| **Owner** | The operations analyst who closes the month, with the finance controller as co-owner of the approval policy and the limit |
| **Stage** | Portfolio prototype on synthetic data; no model call, no posting to a ledger system |
| **Primary user** | The operations analyst who closes the month |
| **Secondary users** | The reviewer who approves the matches that are not obvious; the controller who owns the policy; internal audit |
| **Problem** | Two ledgers describe the same cash for one month, the bank's and the company's, and the totals do not agree. Someone reads both to find out why. A script that pairs lines by amount and date makes the gap look smaller, but it cannot say why two lines were paired, and some of its pairs are wrong. In the planted month, 🟢 there are 383 bank lines and 438 book lines, 821 to read side by side, and a lookup on amount and date posts 316 matches, 25 of them wrong, with a recorded reason for 0 of 316 (`step_01_two_ledgers_unmatched.py`, `step_02_amount_and_date_lookup.py`). |
| **Solution** | Five rules in a fixed order propose matches. Every match prints the rule, the lines and the facts it rests on. The rule is re-run on exactly those lines before a match posts, and again on a finished list. Only `ref_exact`, at or below the limit and with the names agreeing, posts on its own; every other match waits for an approval bound to that exact proposal, from someone other than the agent. Every line not posted is listed with a reason. |
| **North-star metric** | Share of month-end bank and book lines that end the close either in a posted match with a recorded rule, evidence and approver, or in the open list with a reason. Target 🔴 100%. Today in this model: a lookup records a reason for 0 of 316 matches. |
| **Measured metrics (synthetic)** | 🟢 218 matches posted on their own, 0 wrong; 101 held for a person; 93 posted on approval and 8 rejected; 0 posted where the policy needs an approval and none is on record; 169 open lines, each with a reason; a person looks at 385 of 821 lines (`step_04_with_gate.py`). |
| **Modeled metrics** | 🟡 Utility (25 − 6) × 12 = 228 wrong matches a year not posted compared with a lookup on amount and date, assuming 12 month-end closes of this size a year. 🟡 Reading all 821 lines at one minute each is 13.7 hours; the one minute is an assumption (`step_01_two_ledgers_unmatched.py`). |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted month and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real pair of ledgers and report the planted numbers and the real numbers apart. |
| **Risk #2** | The approver is a gate on a name, not on care. 🟢 The scripted approver approved all 21 `ref_near` proposals, and 6 were distinct invoices one edit from a real one (`step_04_with_gate.py`). Mitigation: show the reviewer the invoice for every `ref_near` match, and count approvals that turn out wrong before widening what may post on its own. |
| **Risk #3** | The window, the fee schedule, the limit and the gate policy are assumptions, and amounts must match to the cent. Mitigation: they are parameters in one place, `Params`; read the real fee schedule and limit from the bank's and the controller's own documents before a pilot. |
| **Out of scope** | Any model call; currency conversion; amount tolerances; subset-sum search for splits with no batch id; a queue or user interface for approvers; posting to a ledger; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is bank lines, matches or lines, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Re-check before posting** (the rule is re-run on exactly the cited lines; a failure blocks the match) | 383 bank lines | 3 | 0.9 | 1 | 1034.1 | Built in prototype |
| 2 | **Approval gate bound to the exact proposal** (self-approval refused, stale and conflicting approvals refused) | 383 bank lines | 3 | 0.9 | 1.5 | 689.4 | Built in prototype |
| 3 | **Evidence on every match** (reference, amount, date gap, counterparty) | 383 bank lines | 2 | 0.9 | 1 | 689.4 | Built in prototype |
| 4 | **Open list with a reason per line** (no counterpart, reference conflict, ambiguous, duplicate, currency differs and more) | 821 lines | 2 | 0.8 | 2 | 656.8 | Built in prototype |
| 5 | **Input validation** (empty, truncated, wrong-type or duplicate-id input exits 2, never a traceback) | 383 bank lines | 2 | 0.8 | 1 | 612.8 | Built in prototype |
| 6 | **Verify a finished match list** (catches a swapped line, a relabelled approval, a copied match) | 311 matches | 2 | 0.8 | 1 | 497.6 | Built in prototype |
| 7 | **Five-rule ladder** (`ref_exact`, `ref_fee`, `batch_sum`, `ref_near`, `name_amount`) | 383 bank lines | 2 | 0.8 | 2 | 306.4 | Built in prototype |
| 8 | **Decision record per match and per approval** (rule, lines, hashes of both files, approver, policy version) | 383 bank lines | 2 | 0.6 | 4 | 114.9 | Sequenced for v0.2 |
| 9 | **Approver queue that shows the cited lines** | 101 matches | 2 | 0.6 | 3 | 40.4 | Sequenced for v0.2 |
| 10 | **Invoice lookup for `ref_near` matches** (the reviewer sees the invoice, not only the reference) | 21 matches | 3 | 0.6 | 2 | 18.9 | Sequenced for v0.2 |
| 11 | **Counterparty alias table kept per customer** (the table knows three abbreviations, the generator uses four) | 4 lines | 1 | 0.5 | 2 | 1.0 | Queued |
| 12 | **Subset-sum search for splits with no batch id** | 4 lines | 2 | 0.5 | 4 | 1.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from recon-agent | What they fear |
| --- | --- | --- | --- |
| **Operations analyst** | Owner, closes the month | Fewer lines to read, and for each match a reason they can check in seconds. | A tool that posts a wrong match under their name, or leaves a pile of open items with no explanation. |
| **Reviewer / approver** | Approves the matches that are not obvious | The cited lines on one screen, and an approval that binds to exactly what they read. | Becoming a rubber stamp for a queue too long to read. |
| **Finance controller** | Owns the approval policy and the limit | Control over which rules may post on their own, and a record of who approved what. | A rule widened to auto-post without a decision, or a limit changed quietly. |
| **Treasury / cash management** | Consulted | A cash position that is right at month end and open items that are named. | A wrong match that hides a real difference until it is a loss. |
| **Internal audit** | Reader | A path from any posted match to the rule, the lines and the person who approved it. | An approval that cannot be tied to a proposal, or an edited list that still looks clean. |
| **Security / CISO** | Approver | No ledger credentials held by the tool, nothing leaving the boundary, strings from input kept out of logs and spreadsheets. | Another tool in the close process holding write access to the ledger. |
| **Platform / ledger system owner** | Consulted | A clear contract for what the tool reads and what it hands back for posting. | A tool that posts directly and bypasses the system's own controls. |

---

## User stories (top 4)

1. **As the operations analyst**, I want every match to show the rule and the facts behind it, so I can check a match in seconds and see which lines the tool could not explain.
2. **As a reviewer**, I want an approval to bind to the exact lines and amount I read, so a changed proposal cannot inherit my yes.
3. **As the finance controller**, I want only the narrowest rule to post on its own, and every other match to wait for a named person, so the policy is a table I can read and change.
4. **As internal audit**, I want to re-check a finished list against the ledgers, so an edited match, a swapped line or a relabelled approval shows up without trusting the file.

---

## KPIs

**North star:** share of month-end bank and book lines that end the close either in a posted match with a recorded rule, evidence and approver, or in the open list with a reason. Target 🔴 100%.

**Inputs (leading):**
- Ledger exports that carry the columns the rules read: a reference on both sides where one exists, and an explicit batch id on the book side (prototype: 🟢 383 bank lines and 438 book lines, from `data/README.md`).
- Approvals with a named person who is not the agent (target: every held match).
- A fee schedule and an approval limit read from the bank's and the controller's own documents (target: both written down).

**Outputs (lagging):** prototype baselines from the planted month.
- Wrong matches posted on their own. 🟢 0 of 218, against 25 wrong among 316 posted by a lookup on amount and date (`step_04_with_gate.py`, `step_02_amount_and_date_lookup.py`).
- Posted where the policy needs an approval and none is on record. 🟢 0 (`step_04_with_gate.py`).
- Open lines with a reason. 🟢 169 of 169 (`step_04_with_gate.py`).
- Lines a person has to look at. 🟢 385 of 821 (`step_04_with_gate.py`).
- Wrong matches posted on approval. 🟢 6 of 93, all near_ref_distinct, by a scripted approver (`step_04_with_gate.py`).
- Known miss. 🟢 18 true matches never proposed (`step_03_deficiencies_exposed.py`).
- Approvals overturned after review: not measured; the planted month has no human reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run it on one real month beside the manual close. Post nothing. Compare the proposals and the open list with what the analyst did. |
| 1: Calibration | 4w | Read the real fee schedule and limit. Set the window against the real date lag. Add the aliases the real names need. Count wrong proposals by rule. |
| 2: Approvals recorded | 6w | A named reviewer approves held matches in a queue that shows the cited lines. Only `ref_exact` may post on its own. Every approval is stored with its proposal key. |
| 3: Verify at close | 4w | Run `verify` on the finished list before the close is signed. Open items carry an owner and a date. |
| 4: Decision record and monitoring | 8w | Write a record per match and per approval. Count approvals overturned after review, and widen what may post on its own only if the count supports it. |

---

## Open questions

1. **May a match whose references are one edit apart ever post on one approval?** In the prototype it waits for a person and the scripted approver approved all of them. Recommendation: keep it approval-only, show the invoice with the proposal, and require a second reader if the invoice is not on screen.
2. **Where should the 10000.00 limit come from?** It is my assumption. Recommendation: the controller sets it from the close policy, and it stays a parameter with a recorded change history.
3. **Should the tool tolerate rounding or convert currency?** Today amounts must match to the cent and a currency clash is left open. Recommendation: keep it exact for the pilot and list the cases a tolerance would have caught, so the choice is made against real examples.
4. **What should happen to split deposits with no batch id?** Four sit in the open list. Recommendation: ask the book side to carry a batch id, which makes the rule safe, before building a search that could guess.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One batch job at month end.** The tool is stateless: it reads two ledger exports and an approvals file and writes a match list and an open list. Production adds an approver queue, a decision record and telemetry, all designed and none built.
- **Never silent.** A missing, empty or malformed input exits 2. A line with no match is in the open list with a reason, and nothing is dropped.
- **The check does not trust the proposer.** The rule is re-run on the cited lines before a match posts, and again by `verify` on a finished list.
- **Strings from input are data.** Output text escapes control characters and neutralizes spreadsheet formulas, so a hostile counterparty name cannot forge a line or run in a spreadsheet.

**What is next.** Run it on one real pair of ledgers the owner is allowed to share, with a real reviewer, and count the approvals that were wrong.

**What would have to be true before a pilot.**
- A named reviewer, who is not the agent, reads the cited lines before approving.
- The fee schedule and the approval limit are written down by their owners.
- The book side carries an explicit batch id for grouped deposits.
- One real month can be shared, so the window and the aliases are set against real data and not mine.
- Posting to the ledger stays with the ledger system's own controls, outside this tool.

---

*This PRD names [27 AgentKit](../27-agentkit-reference-agent-and-playbook/), [08 OversightOps](../08-oversightops-hitl-workflow/), [09 LineageLog](../09-lineagelog-ai-decision-audit/) and [05 AgentWatch](../05-agentwatch-agent-observability/) as designed interlocks (🔴 designed, none built). The gate pattern comes from 27; no code was copied from it.*
