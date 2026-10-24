# PRD: Deprecation Impact

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a platform review. It is not a record of a PRD landed at a named bank. The resolver, the lead times, the planted register and the rollout plan are mine; the vendors, model names, dates and prices are made up, and the numbers are measured on synthetic data I generated or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Deprecation Impact: a command-line tool that reads a model catalog, an alias table and a feature register and prints a retirement calendar, a hit list with a tier per dependency, and a check queue for the strings it cannot resolve |
| **Owner** | The person who runs the AI platform or the feature register, with each feature owner as owner of the move for their feature |
| **Stage** | Portfolio prototype on synthetic data; not deployed |
| **Primary user** | The person who runs the AI platform or the feature register, and the owners who get a ticket when a notice lands |
| **Secondary users** | The evaluation owner who knows which features have an evaluation set; the vendor manager who tracks notices; the FinOps lead who reads the cost view; internal audit |
| **Problem** | A vendor announces that a model version retires on a date. The notice names a model. The people who have to act own features, and nothing tells them which features call that snapshot, directly or through a floating alias, a fine-tune, a fallback or an evaluation judge. They learn from failed calls, or they search by hand and trust the search. In the planted register, 🟢 42 dependencies in 36 of 60 features sit on the models they retire, and filtering the primary model column for the id in the notice finds 7 of 42 (`step_01_no_map.py`, `step_02_exact_match.py`). |
| **Solution** | Reads a model catalog with notice and retirement dates, an alias table, a feature register and the model each feature names in each role. Resolves every model string: exact id, alias (with the date it was recorded), family name, or the base model of a fine-tune. A string it cannot resolve goes to a check queue, never to clear. Prints a retirement calendar, a hit list with days left, the lead time the feature needs and a tier, and the monthly cost on the named successor. Exits 1 when the worst tier reaches a chosen level, so a scheduled job can fail; exits 2 on input it cannot read. |
| **North-star metric** | Share of retirement notices for which every dependency on the retiring model is on a dated hit list or in the check queue within one business day of the notice. Target 🔴 100%. Today in this model: nothing maps models to features, and 🟢 42 dependencies in 36 of 60 features are on retiring models (`step_01_no_map.py`). |
| **Measured metrics (synthetic)** | 🟢 29 of 42 affected dependencies found and dated, 6 more in the check queue, 7 missed; 0 of 29 hits are false alarms; a person opens 35 features instead of 46 (`step_04_with_map.py`). |
| **Modeled metrics** | 🟡 Utility (29/42 − 7/42) × 21 = 11 dependencies found and dated that a primary-column filter would not find, assuming 21 such dependencies in a register. 🟡 Tiers on assumed lead times: 1 PAST, 6 LATE, 3 TIGHT, 19 ROOM and 3 SUNSETS. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The data and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real register, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The tool reads the registry. A dependency that no row records, or a recent alias entry that is wrong, passes as clear. 🟢 7 of 42 pass with no flag (`step_04_with_map.py`). Mitigation: fill the registry from the configuration each service reads, and refresh the alias table on every run (sequenced for v0.2). |
| **Risk #3** | Lead times are assumptions and decide the tiers; prices are made up. Mitigation: replace both with the team's own actuals in shadow mode, before any tier fails a job. |
| **Out of scope** | Fetching vendor notices; migrating or testing the successor; embedding models and re-indexing; reading code or configuration to find model strings; any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is usage rows, dependencies or features, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Check queue** (a string it cannot resolve, a stale alias, an unpinned family or a feature with no model is listed, never counted as clear) | 80 usage rows | 3 | 0.9 | 1 | 216.0 | Built in prototype |
| 2 | **All three roles** (primary, fallback and judge are read) | 80 usage rows | 2 | 0.9 | 1 | 144.0 | Built in prototype |
| 3 | **Input validation** (empty, truncated, wrong-type or dangling input exits 2, never a traceback) | 80 usage rows | 2 | 0.9 | 1 | 144.0 | Built in prototype |
| 4 | **Resolver** (exact id, alias with its recorded date, family name, fine-tune base) | 80 usage rows | 3 | 0.9 | 2 | 108.0 | Built in prototype |
| 5 | **CI output** (text and JSON, `--fail-on` levels, escaped strings) | 60 features | 2 | 0.9 | 1 | 108.0 | Built in prototype |
| 6 | **Tiers from days left against the lead time** (PAST, LATE, TIGHT, ROOM, SUNSETS) | 87 dependencies | 3 | 0.8 | 2 | 104.4 | Built in prototype |
| 7 | **Lead-time policy file** (`--policy`) | 60 features | 2 | 0.7 | 1 | 84.0 | Built in prototype |
| 8 | **Ticket per hit with an owner and a due date** | 87 dependencies | 2 | 0.6 | 3 | 34.8 | Sequenced for v0.2 |
| 9 | **Monthly cost on the named successor** | 87 dependencies | 1 | 0.6 | 2 | 26.1 | Built in prototype |
| 10 | **Impact record per run** (inputs, policy, hits, check queue) | 60 features | 2 | 0.7 | 4 | 21.0 | Sequenced for v0.2 |
| 11 | **Fill the registry from service configuration** | 80 usage rows | 3 | 0.4 | 6 | 16.0 | Queued |
| 12 | **Vendor-page reader** as a separate, checked step | 60 features | 3 | 0.4 | 5 | 14.4 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Deprecation Impact | What they fear |
| --- | --- | --- | --- |
| **AI platform owner** | Owner | One dated list per notice, and a scheduled job that fails when a feature is late. | A list that reads as complete when the registry is not. |
| **Feature owner** | Receives the hit | A date, the lead time the move needs and the successor named, early enough to plan. | A ticket with no reason, or a tier set by a lead time they never agreed to. |
| **Evaluation owner** | Consulted | Lead times that count the evaluation set a feature has or lacks. | A swap shipped without the evaluation the lead time assumed. |
| **Vendor manager** | Informed | Notice dates matched to features, and the successor each notice names. | Learning of a retirement from a failed call. |
| **FinOps lead** | Reader of the cost view | A first estimate of the monthly cost on the successor, with the gaps named. | A made-up price read as a quote. |
| **Security / CISO** | Approver | Nothing leaving the boundary, strings from input kept out of logs, no vendor key in the tool. | Another tool that holds credentials for the vendor. |
| **Internal audit** | Reader | A path from a tier to the registry rows, the alias entry and the lead times it used. | Lead times changed silently between two runs. |

---

## User stories (top 4)

1. **As the AI platform owner**, I want a notice to become a dated list of features, so I do not start each retirement with a search.
2. **As a feature owner**, I want to see the days left, the lead time my feature needs and the successor, so I can plan the move before it is late.
3. **As the AI platform owner**, I want a string the tool cannot resolve to land in a check queue and never in clear, so an unknown does not read as safe.
4. **As internal audit**, I want each tier tied to the registry rows, the alias entry and the lead times it used, so I can reproduce it later.

---

## KPIs

**North star:** share of retirement notices for which every dependency on the retiring model is on a dated hit list or in the check queue within one business day of the notice. Target 🔴 100%.

**Inputs (leading):**
- Usage rows that record the model string and the role for every feature (the prototype register has 🟢 60 features and 80 registry rows, from `data/README.md`; 🟢 4 fallbacks are used that no registry row records, `step_03_deficiencies_exposed.py`).
- Features with a criticality and an evaluation-set flag recorded (target: every feature).
- Alias entries recorded within the 90-day trust limit (an assumption; target: every entry).
- Lead times set from the team's own past migrations (target: every criticality; the prototype's are assumptions).

**Outputs (lagging):** prototype baselines from the planted set.
- Affected dependencies found and dated. 🟢 29 of 42 (`step_04_with_map.py`), against 7 of 42 for a filter on the primary column (`step_02_exact_match.py`).
- Hits that are not affected. 🟢 0 of 29 (`step_04_with_map.py`).
- Features a person opens. 🟢 35, against 46 for a family-name search (`step_04_with_map.py`).
- Check queue. 🟢 13 entries: 4 proved affected, 6 did not, and 3 are features with no model recorded (`step_04_with_map.py`).
- Known miss. 🟢 7 affected dependencies pass with no flag (`step_04_with_map.py`).
- Moves finished before their model retired: not measured; the planted set has no owners.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the tool on one real register for each vendor notice, with `--fail-on never`. Compare the hit list with what the team found by hand. |
| 1: Calibration | 4w | Add the fallback and judge rows the registry lacks. Replace the assumed lead times with the team's own. Pin snapshots where a family name is used. |
| 2: Check queue owned | 4w | Name an owner for the check queue and clear it within an agreed time. Refresh the alias table on each run. |
| 3: Enforced | 6w | A scheduled job fails when the worst tier reaches LATE, and each hit becomes a ticket with an owner and a due date. |
| 4: Record and sources | 8w | Write an impact record per run. Test filling the registry from service configuration, and the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should a bare family name be a hit or a check?** The tool sends it to the check queue when the family has a retiring snapshot. Recommendation: keep it as a check, and ask the owner to pin a snapshot so the entry stops recurring.
2. **Where do the lead times come from?** They are my assumptions: 60, 30 and 14 days by criticality, plus 30 with no evaluation set, 14 for a judge and 45 for a fine-tune. Recommendation: start there in shadow mode, then replace them with the team's actuals from its last two migrations.
3. **How long is an alias entry trusted?** The tool trusts one for 90 days (an assumption), and 🟢 3 features sit behind a recent entry that does not match what the vendor serves (`step_04_with_map.py`). Recommendation: refresh the alias table on every run, so the age limit stops carrying weight.
4. **Who clears the check queue?** Recommendation: the platform owner triages it, and the feature owner confirms or clears each entry in a week (planning estimate).

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, run on a schedule and on each new notice.** The tool is stateless: it reads four files and a date and returns a calendar, hits and a check queue. Production adds a reviewed policy file, an impact record and telemetry, all designed and none built.
- **Never silent.** Unreadable input exits 2. A string that cannot be resolved is a check entry, not a clear row, and a feature with no model recorded is one too.
- **Strings from input are data.** Output strips control characters, so a hostile feature name cannot forge a line.
- **Changes to a lead time are changes to a number.** A golden test pins the planted-set numbers, so a policy change that moves a tier count shows in the diff.

**What is next.** Run it on one real register whose owner can share it; add the embedding role and the re-index cost; write the vendor-page reader as a separate, checked step.

**What would have to be true before a pilot.**
- The registry records the model each feature names in each role, taken from the configuration the service reads.
- The model catalog carries notice and retirement dates and a named successor.
- A named person owns the check queue and the lead times.
- One real register can be shared, so the lead times and the tiers are set against real work and not mine.
- The team agrees which tier fails the job.

---

*This PRD names [13 SwapBrief](../13-swapbrief-model-migration/), [07 InferenceLens](../07-inferencelens-inference-finops/), [40 Eval Gate](../40-eval-gate/) and [44 Inventory Check](../44-inventory-check/) as designed interlocks (🔴 designed, none built). The prototype reads no file from 13 or 07 and imports nothing from either.*
