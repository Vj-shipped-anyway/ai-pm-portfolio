# PRD: name-match-eval

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a screening-threshold review. It is not a record of a PRD landed at a named bank. The watchlist, the customer names, the variant mix and both targets are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and it is not a screening product.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | name-match-eval: a command-line evaluator and a synthetic set that run three matchers (exact, character edit similarity, and a word-based matcher), sweep the alert threshold, and print how many planted matches each one catches and how many clear names it alerts on |
| **Owner** | The analyst or program lead who owns a name-screening step and has to defend its threshold, with the engineer who tunes it as co-owner of the matcher |
| **Stage** | Portfolio prototype on synthetic data; an evaluator, not a screening product |
| **Primary user** | The analyst or program lead who owns the screening step |
| **Secondary users** | The engineer who tunes the threshold; the reviewer who clears the alert queue; the model-risk or compliance reviewer who approves a threshold change; internal audit |
| **Problem** | A screening team picks a name-match threshold without seeing what it costs. A strict one misses reordered, shortened and respelled names; a loose one floods reviewers with clear names that resemble a listed one. The two costs are rarely printed side by side. In the planted set, 🟢 exact match catches 24 of 150 planted matches (16.0%) and misses 126 of 150 (`step_01_exact_match.py`). |
| **Solution** | Scores a customer name against every listed name with three matchers: exact, whole-name edit similarity, and folded words aligned in any order with rarity weights. Sweeps the threshold and prints, per matcher, planted matches caught and clear names alerted. Finds the threshold for a false-alert limit and for a recall target, and exits 1 when no threshold meets both. Breaks results down by the kind of spelling change that was planted. |
| **North-star metric** | Share of threshold changes that reach review with a sweep on a labelled sample from the real list, both columns shown. Target 🔴 100%. Today in this model: the threshold is chosen without one. |
| **Measured metrics (synthetic)** | 🟢 Edit similarity at a 10.0% false-alert limit: threshold 0.93, recall 36.0%. The word matcher at the same limit: recall 57.3% (86 of 150) with 24 false alerts. No threshold meets both targets; the word matcher reaches 85.0% recall at 0.73 with 18.4% false alerts (`step_02_edit_similarity.py`, `step_04_token_matcher.py`). |
| **Modeled metrics** | 🟡 Utility (86/150 − 54/150) × 500 = 106.7 more listed-party matches a year caught at the same false-alert limit, assuming 500 true matches a year reach screening. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The same author wrote the data and the rules, so the numbers are a ceiling. Mitigation: run it on one real list and a labelled sample the owner may share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The variant mix and both targets are assumptions. A different mix moves every number. Mitigation: replace the mix with counts from reviewed alerts, and set the false-alert limit from what the review team can clear. |
| **Risk #3** | The word matcher is worse than edit on two planted kinds. 🟢 A particle joined to its surname is caught 2 of 8 at 0.75 against 8 of 8 for edit, and translit_heavy 5 of 10 against 10 of 10 (`step_04_token_matcher.py`). Mitigation: read the by-kind table before a change, and keep both matchers in shadow on the real sample. |
| **Out of scope** | Phonetic codes, non-Latin scripts, secondary identifiers, list updates, any model call, and any claim about a regulator's expectations. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is customer names, clear names or planted matches, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Input validation** (empty, wrong-type or truncated files, a truth row for every customer, a match only for a listed entity: exit 2, never a traceback) | 400 names | 2 | 0.9 | 1 | 720.0 | Built in prototype |
| 2 | **Exact and edit baselines** with a `score` command for two names | 400 names | 2 | 0.8 | 1 | 640.0 | Built in prototype |
| 3 | **Results by planted kind** (which spelling change each matcher catches or misses) | 400 names | 2 | 0.7 | 1 | 560.0 | Built in prototype |
| 4 | **Sweep and target lines** (lowest threshold for a false-alert limit, highest for a recall target, exit 1 when none meets both) | 400 names | 3 | 0.9 | 2 | 540.0 | Built in prototype |
| 5 | **Word matcher** (folded words, any order, initials credited, rarity weights) | 400 names | 3 | 0.7 | 3 | 280.0 | Built in prototype |
| 6 | **Load a real list and a labelled sample** from reviewed alerts | 400 names | 3 | 0.6 | 4 | 180.0 | Sequenced for v0.2 |
| 7 | **False-alert limit from review capacity** | 250 clear names | 2 | 0.5 | 3 | 83.3 | Sequenced for v0.2 |
| 8 | **Threshold-change evidence record** (list version, sample hash, both columns, approver) | 400 names | 1 | 0.7 | 4 | 70.0 | Sequenced for v0.2 |
| 9 | **Second identifier** to separate namesakes | 250 clear names | 3 | 0.4 | 5 | 60.0 | Queued |
| 10 | **Phonetic code comparison** | 150 matches | 2 | 0.4 | 3 | 40.0 | Queued |
| 11 | **Non-Latin scripts** (transliteration before comparison) | 150 matches | 3 | 0.3 | 8 | 16.9 | Queued |
| 12 | **Alias-carrying list workflow** (a party known by an unlisted name) | 10 matches | 3 | 0.5 | 3 | 5.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from name-match-eval | What they fear |
| --- | --- | --- | --- |
| **Screening program lead** | Owner | Both columns of a threshold change on one page, with the kind of name each one affects. | Defending a threshold with one number. |
| **Screening engineer** | Co-owner of the matcher | A matcher that can be swapped in without changing the evaluator, and a sweep that names the threshold. | A new matcher that wins on the planted set and loses on the real list. |
| **Alert reviewer** | Consulted | A false-alert limit they can clear in a day. | A change that doubles the queue overnight. |
| **Model-risk or compliance reviewer** | Approver of a threshold change | A record of the sample, the list version and what the change gives up. | Approving a change on numbers from data the team wrote. |
| **List owner** | Informed | Findings that point at the list: aliases that are missing, namesakes that need a second identifier. | A score change presented as a fix for a list problem. |
| **Security / CISO** | Approver | Real names kept inside the boundary, nothing sent out, strings from input kept out of logs. | A labelled sample of real customer names in a CI log. |
| **Internal audit** | Reader | A path from a threshold in production to the sweep that justified it. | A threshold that moved with no sweep behind it. |

---

## User stories (top 4)

1. **As the screening program lead**, I want the cost of a threshold printed as caught matches and false alerts side by side, so I can defend the choice and not one number.
2. **As the screening engineer**, I want results broken down by the kind of spelling change, so I see that a better score on order swaps costs a worse one on joined particles.
3. **As an alert reviewer**, I want the evaluator to say plainly when no threshold meets both targets, so a team does not read a pass into a trade.
4. **As internal audit**, I want each threshold change tied to the sweep, the sample and the list version it used, so I can reproduce the decision later.

---

## KPIs

**North star:** share of threshold changes that reach review with a sweep on a labelled sample from the real list, both columns shown. Target 🔴 100%.

**Inputs (leading):**
- Listed names with an entity id and a name type (prototype: 🟢 90 listed names for 60 entities, `data/README.md`).
- Labelled customer names (prototype: 🟢 400, of which 150 are planted matches and 250 are clear, `data/README.md`).
- Kinds of change represented in the sample (prototype: 🟢 10 planted match kinds, from `data/README.md`).
- Lists with a named owner and a version (target: every list).

**Outputs (lagging):** prototype baselines from the planted set.
- Recall at a 10.0% false-alert limit, edit. 🟢 36.0% at threshold 0.93 (`step_02_edit_similarity.py`).
- Recall at the same limit, word matcher. 🟢 57.3% (86 of 150) at threshold 0.93 (`step_04_token_matcher.py`).
- False alerts at 85.0% recall, word matcher. 🟢 18.4% of clear names at threshold 0.73 (`step_04_token_matcher.py`).
- Built-in misses. 🟢 alias_unlisted 0 of 10, namesake 8 of 8 (`step_04_token_matcher.py`).
- Alerts a reviewer cleared that were real: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run `sweep` on one real list and a labelled sample from reviewed alerts, with the matcher in use. Print both columns, change nothing. |
| 1: Calibration | 4w | Replace my variant mix with counts from the real sample. Set the false-alert limit from review capacity. Read the by-kind table with the list owner. |
| 2: Second matcher in shadow | 6w | Run the word matcher beside the current one for a full cycle. Compare caught matches and alerts by kind. |
| 3: Threshold change by evidence | 4w | A threshold change needs a sweep, the sample and a different approver. |
| 4: Second identifier and record | 10w | Add a second identifier to separate namesakes and write a record per change. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Which number gives, the false-alert limit or recall?** No threshold met both here. Recommendation: set the false-alert limit from what the review team can clear, and report recall at that limit.
2. **Where does the labelled sample come from?** Reviewed alerts carry labels only for names that alerted. Recommendation: label a random sample of customers as well as the reviewed alerts, and report the two apart.
3. **What variant mix is real?** Mine is invented. Recommendation: replace it with counts from reviewed alerts, kind by kind, before any threshold moves.
4. **Should a matcher separate namesakes?** It cannot: 🟢 namesake alerts 8 of 8 at 1.00 under all three matchers (`step_04_token_matcher.py`). Recommendation: treat it as a second-identifier decision, not a score decision.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **An evaluator, not a screener.** It scores every customer against every listed name, so it runs on a labelled sample and stops at 2,000,000 pairs. Production adds a labelled-sample store and a change record, all designed and none built.
- **Never silent.** A missing, empty, truncated or mistyped file, a customer with no truth row or a match for an unlisted entity exits 2. A sweep with no matches or no clear names says the figure is not defined.
- **Strings from input are data.** Names, paths and ids are escaped and cut before they reach a log.
- **Changes to a matcher are changes to a number.** A golden test pins the planted-set numbers, so a matcher change that moves recall or false alerts shows in the diff.

**What is next.** Run it on a real list and customer extract that the owner is allowed to share; add a second identifier to separate namesakes; compare a phonetic code.

**What would have to be true before a pilot.**
- A labelled sample from the real list exists, with a random part and a reviewed-alert part.
- The false-alert limit is set from review capacity.
- A named person owns the list and will act on alias and namesake findings.
- Real names can be held in one controlled place.
- The team agrees which number it will give up, if no threshold meets both.

---

*This PRD names [50 Review Capacity](../50-review-capacity/), [72 Scam Friction Sim](../72-scam-friction-sim/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built).*
