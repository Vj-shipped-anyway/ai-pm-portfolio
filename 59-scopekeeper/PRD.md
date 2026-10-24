# PRD: scopekeeper, a usage-versus-grant diff

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an access-governance review for an agent platform. It is not a record of a PRD landed at a named bank. The rules, the planted estate and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and the tool has never been run on a real grant store.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | scopekeeper: a command that reads who holds which scope and a log of calls, proposes removing grants nobody used and narrowing group grants to the scopes called, and replays the proposal against the same calls before anyone applies it |
| **Owner** | The person who runs the access review for an agent platform, with the platform's security architect as co-owner of the thresholds |
| **Stage** | Portfolio prototype on synthetic data; it proposes and never applies |
| **Primary user** | The person who runs the access review for an agent platform |
| **Secondary users** | The owner of each agent, who has to say what it may do; internal audit; the platform engineer who applies approved changes |
| **Problem** | An AI agent calls tools through scopes. Scopes are granted at launch from a template and added for one-off tasks, and some grants are groups such as `accounts:*`. The control is an annual review that approves what is on the list. The list shows names, dates and tickets. It does not show a single call, so a grant nobody has used looks the same as one used every day. On the planted estate, 🟢 62 of 167 grants (37.1%) are not needed and the review removes 4 of those 62 (`step_01_no_comparison.py`, `step_02_annual_review.py`). |
| **Solution** | Reads a grant list and a call log (CSV), plus an optional catalog of what each group scope reaches and an optional list of which agents share a service account. For each grant it asks whether a scope it reaches was called: no call is a removal, a group called on some members is a narrowing. A call with no agent tag is credited to every agent on its service account that holds the scope. It replays the proposal against the same calls and counts the calls newly denied. Prints a report or GitHub annotations; exits 1 on a proposal and 2 on unreadable input. |
| **North-star metric** | Share of live agents whose grants were compared with at least a quarter of calls in the last review cycle, with every removal answered by an owner. Target 🔴 100%. Today in this model: 🟢 0 of 167 grants are checked against calls (`step_01_no_comparison.py`). |
| **Measured metrics (synthetic)** | 🟢 46 of 62 unneeded grants removed (74.2%) against 4 of 62 (6.5%) for the review; entitlements cut from 190 to 123 (67 cut, 35.3%); 0 of 5210 calls newly denied in the replay, which is in-sample; the review's removals deny 155 (`step_04_with_diff.py`). |
| **Modeled metrics** | 🟡 Utility (46/62 − 4/62) × 100 = 67.7 more unneeded grants removed a year than the annual review, assuming 100 unneeded grants in the estate under review. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted estate and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real export and a log longer than a quarter, and report the planted numbers and the real numbers apart. |
| **Risk #2** | A scope used less often than the log is long looks unused. 🟢 10 grants are legitimate and used once a quarter; the diff removes 8, and the first quarter after the cut would deny 44 legitimate calls (`step_04_with_diff.py`). Mitigation: ask each owner whether a removal is periodic before it is applied, and use a longer log. |
| **Risk #3** | The replay is in-sample: the proposal is built from the calls it is replayed on. 🟢 Dropping payments:read_status from AG-03 denies 266 calls, so the check is not vacuous (`step_04_with_diff.py`). Mitigation: treat 0 newly denied as a property of the method and say so in every report. |
| **Out of scope** | Applying any change; reading a real grant store; risk scoring; any model call; a longer log than the one given; hosting. Project 23 holds the risk ranking and the architecture notes. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is grants or proposals, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Usage-versus-grant diff** (no call in the log: propose removal) | 167 grants | 3 | 0.9 | 1 | 450.9 | Built in prototype |
| 2 | **Sibling credit** (an untagged call is credited to every agent on its service account that holds the scope) | 167 grants | 3 | 0.8 | 1 | 400.8 | Built in prototype |
| 3 | **Replay against the same calls** (count the calls newly denied) | 167 grants | 3 | 0.8 | 1 | 400.8 | Built in prototype |
| 4 | **Input validation** (empty, truncated, wrong-type input exits 2; a group grant with no catalog entry is refused, not guessed) | 167 grants | 2 | 0.9 | 1 | 300.6 | Built in prototype |
| 5 | **Call-count threshold** (`--min-calls`, with the price printed both ways) | 167 grants | 2 | 0.7 | 1 | 233.8 | Built in prototype |
| 6 | **CI output** (GitHub warnings, `--fail-on`, escaped strings) | 167 grants | 2 | 0.9 | 1.5 | 200.4 | Built in prototype |
| 7 | **Longer or merged logs** (a window of more than one quarter) | 167 grants | 3 | 0.5 | 3 | 83.5 | Sequenced for v0.2 |
| 8 | **Owner question "is this scope periodic?" on each removal** | 54 proposals | 3 | 0.7 | 1.5 | 75.6 | Sequenced for v0.2 (designed in project 23, not built) |
| 9 | **Decision record** (grants, calls hash, proposal, owner answer) | 167 grants | 2 | 0.6 | 4 | 50.1 | Sequenced for v0.2 |
| 10 | **Scope impact weighting** | 167 grants | 2 | 0.4 | 6 | 22.3 | Queued |
| 11 | **Group narrowing from a catalog** (a group called on some members only) | 8 group grants | 3 | 0.8 | 1 | 19.2 | Built in prototype |
| 12 | **Hand-off of approved changes** (a reviewed change to the platform, never applied by the tool) | 60 proposals | 2 | 0.6 | 4 | 18.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from scopekeeper | What they fear |
| --- | --- | --- | --- |
| **Access reviewer** | Owner, runs the review | A list of proposals each with a reason a person can check, and a count of calls it would deny. | A proposal that breaks a live agent, so the review goes back to approving the list. |
| **Agent owner** | Answers the periodic-scope question | To keep what the agent really uses, and to be asked before anything is removed. | A removal that lands in the quarter-end run with no warning. |
| **Platform engineer** | Applies approved changes | A change list in the platform's own format, small enough to review. | A tool that applies changes itself. |
| **Security architect** | Approver of thresholds | Narrower reach per agent, with a record of what was removed and why. | A proposal that keeps an unneeded grant alive on a sibling's calls and calls it safe. |
| **Internal audit** | Reader | A path from a removal to the grants, the log window and the owner's answer. | A log window that was too short, hidden in a summary. |
| **Security / CISO** | Approver | No platform credential in the tool, nothing leaving the boundary, strings from input kept out of logs and annotations. | A grant export that maps an agent estate's weak points ending up in the wrong place. |

---

## User stories (top 4)

1. **As the person who runs the access review**, I want each grant compared with the calls, so a grant nobody has used no longer looks the same as one used every day.
2. **As an agent owner**, I want a grant in use never proposed for removal, so the diff is safe to read even when calls on a shared service account carry no agent tag.
3. **As a platform engineer**, I want the proposal replayed against the same calls, so I know before I apply it how many calls it would deny.
4. **As internal audit**, I want each removal to say why in one line, and to see which grants were kept only on a sibling's calls, so I can judge what the diff cannot see.

---

## KPIs

**North star:** share of live agents whose grants were compared with at least a quarter of calls in the last review cycle, with every removal answered by an owner. Target 🔴 100%.

**Inputs (leading):**
- Calls that carry an agent tag (prototype: 🟢 5210 calls, of which 1155 carry none, 22.2%, `step_01_no_comparison.py`; target: every call).
- Agents on a service account of their own (prototype: 🟢 14 agents on 10 service accounts, 7 sharing 3 of them; target: one account per agent).
- Log length against the longest cycle in use (prototype: 🟢 90 days; target: longer than a quarter).
- Group scopes with a catalog entry (target: every group scope).

**Outputs (lagging):** prototype baselines from the planted estate.
- Unneeded grants removed. 🟢 46 of 62, against 4 of 62 for the review (`step_04_with_diff.py`).
- Needed grants removed. 🟢 8, the quarterly ones, against 4 for the review (`step_04_with_diff.py`).
- Entitlements cut. 🟢 67 of 190 (35.3%) (`step_04_with_diff.py`).
- Calls newly denied in the replay. 🟢 0 of 5210, in-sample (`step_04_with_diff.py`).
- Known misses. 🟢 14 unneeded grants kept on sibling credit, 2 kept after a smoke test (`step_04_with_diff.py`).
- Removals refused by an owner: not measured; the planted estate has no owner.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run `diff --fail-on never` on one real export and a log longer than a quarter. Apply nothing. Read the proposals with the agent owners. |
| 1: Calibration | 4w | Collect the owner answers. Count the removals that are periodic. Set `--min-calls` and the window against what the owners say. Fix tagging on shared service accounts. |
| 2: Owner question in the loop | 6w | Every removal proposal goes to its owner with the periodic-scope question. Nothing is applied without an answer. |
| 3: Approved changes handed off | 6w | Approved removals go to the platform as a reviewed change. The replay result is attached. |
| 4: Decision record | 8w | Write a record per proposal. Move toward one service account per agent so sibling credit is no longer needed. |

---

## Open questions

1. **Should a grant with no call in the log be proposed for removal by default?** The prototype says yes, with the owner asked. Recommendation: yes, as a question to the owner and not a change, until a log longer than a quarter exists.
2. **Should sibling credit stay?** It keeps 14 unneeded grants alive so that no grant in use is ever proposed for removal. Recommendation: keep it, report the grants it keeps, and remove the cause with one service account per agent.
3. **What is a safe `--min-calls`?** At 1 call the stray-use grants stay; at 3 they go and so do needed grants. Recommendation: keep 1 for the pilot and list the stray-use grants for owner review.
4. **Who may approve a removal?** Recommendation: the agent's owner, with the access reviewer as a second reader when the grant is a group or touches payments or customer data.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One batch step.** The tool is stateless: it reads two to four CSV files and writes a report. Production adds an owner queue, a hand-off and a decision record, all designed and none built.
- **Never silent.** Empty, truncated or wrong-type input exits 2. A calls file that matches no grant is an error, not a request to remove everything. A group grant with no catalog entry is refused, not guessed.
- **Proposes, never applies.** The tool holds no platform credential. Applying a change stays with the platform and its own approvals.
- **Strings from input are data.** Output text and annotations escape control characters, so a hostile scope or agent name cannot forge a line or a workflow command.

**What is next.** Run it on one real grant export and call log that the owner may share; add the owner question "is this scope periodic?" to each removal proposal, which is designed in project 23 and not built here.

**What would have to be true before a pilot.**
- A call log longer than the longest review cycle in use, or an owner who can say which scopes are periodic.
- An agent tag on calls, or an agents file that says which agents share a service account.
- A catalog entry for every group scope.
- A named owner for each agent who will answer the question.
- Applying a change stays outside the tool.

---

*This PRD names [23 ScopeKeeper](../23-scopekeeper-agent-permission-review/), [05 AgentWatch](../05-agentwatch-agent-observability/), [08 OversightOps](../08-oversightops-hitl-workflow/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). This folder shares no code or numbers with 23.*
