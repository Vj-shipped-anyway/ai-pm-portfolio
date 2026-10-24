# PRD: Entitlement Canary

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a retrieval-layer change review. It is not a record of a PRD landed at a named bank. The strata, the planted pull-request set and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and the retrieval system in the runs is a toy stand-in.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Entitlement Canary: a command-line leak test for retrieval, with a staged GitHub Action. It builds a pack of canaries from an access export, reads what the team's test harness got back for each one, checks every returned document against the access export on the pull request's branch and prints ALLOW, REVIEW or BLOCK |
| **Owner** | The engineer who owns the retrieval layer, with a second-line reviewer as co-owner of the quotas and the access rules the check reads |
| **Stage** | Portfolio prototype on synthetic data (120 documents, 20 users, 50 planted pull requests); the Action is staged and unpublished |
| **Primary user** | The engineer who owns the retrieval layer |
| **Secondary users** | The reviewer who approves changes to it (index settings, the access filter, the cache, a new document source); the access owner who produces the export; internal audit |
| **Problem** | An assistant that retrieves from internal documents must return a document only to a user who may open it. The usual retrieval eval in CI scores relevance. A document that matches the question is a relevant result whether or not the asker may read it, so the eval passes pull requests that leak. In the planted set, 🟢 the relevance eval stops 7 of 28 leaking pull requests and 9 of 22 clean ones (`step_01_relevance_only.py`). |
| **Solution** | (1) Builds a pack of canaries from an access export: pairs where the user may not open the document, chosen from four strata (stale access list, nested deny, direct deny, ordinary) with a minimum per document source. (2) Reads the results your test harness recorded for the pack, including a control query by an entitled user. (3) Checks every returned document against the access export on the pull request's branch, not only the canary's target. (4) Prints ALLOW, REVIEW or BLOCK, exits non-zero at a chosen level, and writes GitHub annotations on request. |
| **North-star metric** | Share of leaking pull requests blocked before merge, with a recorded decision. Target 🔴 100%. Prototype today: 27 of 28 blocked. |
| **Measured metrics (synthetic)** | 🟢 27 of 28 leaking pull requests blocked; 0 of 22 clean pull requests blocked and 3 of 22 sent to review; a person reads 30 of 50 (`step_04_with_canary.py`). |
| **Modeled metrics** | 🟡 Utility (27/28 − 7/28) × 12 = 8.6 leaking pull requests a year stopped that a relevance eval would pass, assuming 12 leaking pull requests reach the check each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real retrieval system and report the planted numbers and the real numbers apart. |
| **Risk #2** | The harness is the user's code: a control query that never runs hides a shared cache, and the check reads the `primed` column as written. Mitigation: a harness contract test and a signed results file. |
| **Risk #3** | The pack is a sample, so a leak that touches one pair can pass. 🟢 PR-011 leaks one pair with no canary aimed at it and passes (`step_04_with_canary.py`). Mitigation: delegation-aware canaries, and a pack rebuilt on a schedule with a new seed. |
| **Out of scope** | Running or hosting a retrieval system; reading generated answers for leaked content; chunk-level access rules; any model call; a Marketplace listing (staged in `action/`). |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is pull requests, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Check of every returned document** (against the branch's access export, not only the target) | 50 PRs | 3 | 0.9 | 1 | 135.0 | Built in prototype |
| 2 | **Effective-access resolver** (nested groups, deny wins, no allow entry is closed) | 50 PRs | 3 | 0.9 | 2 | 67.5 | Built in prototype |
| 3 | **Stratified pack builder** (four strata, minimum per source, seeded) | 50 PRs | 3 | 0.8 | 2 | 60.0 | Built in prototype |
| 4 | **Input validation and safe output** (bad input exits 2; annotations and text escaped) | 50 PRs | 2 | 0.9 | 2 | 45.0 | Built in prototype |
| 5 | **Control query and review notes** (inert, unprimed, no result, unknown id, thin source) | 50 PRs | 2 | 0.8 | 2 | 40.0 | Built in prototype |
| 6 | **Harness contract test** (fails when `primed` is claimed and the control did not run) | 50 PRs | 3 | 0.5 | 2 | 37.5 | Sequenced for v0.2 |
| 7 | **Id-only annotations** (omit document titles from pull request output) | 50 PRs | 1 | 0.7 | 1 | 35.0 | Queued |
| 8 | **Publish the Action from its own repository** | 50 PRs | 2 | 0.6 | 2 | 30.0 | Sequenced for v0.2 (staged in `action/`, not published) |
| 9 | **Decision ledger** (hashes of the three files, tool version, leaks, notes) | 50 PRs | 2 | 0.7 | 4 | 17.5 | Sequenced for v0.2 |
| 10 | **Chunk-to-document mapping helper** | 50 PRs | 2 | 0.5 | 3 | 16.7 | Queued |
| 11 | **Scheduled access export per branch** | 50 PRs | 2 | 0.6 | 4 | 15.0 | Sequenced for v0.3 |
| 12 | **Delegation-aware canaries** (aim one at each delegated pair) | 28 PRs | 3 | 0.5 | 3 | 14.0 | Sequenced for v0.3 |

---

## Stakeholder map

| Stakeholder | Role | What they want from Entitlement Canary | What they fear |
| --- | --- | --- | --- |
| **Retrieval-layer engineer** | Owner | A step that fails with the leaked pair named, and passes a change that only changes ranking. | A check that blocks good changes and gets switched off. |
| **Change reviewer** | Approver of retrieval changes | A decision that says what was tested and what was not, so the review is about the gaps. | Signing off on a green check that could not see the leak. |
| **Access owner** | Owns the access export and the ACLs | The check reads the export as it is, and a wrong ACL shows as a finding, not a blame. | A tool that redefines who may open what. |
| **Document source owner** | Informed | Their source covered by canaries, and a new source ingested without ACLs caught. | Learning of a leak from a user. |
| **Security / CISO** | Approver | No production credentials in the check, nothing leaving the boundary, no titles in public output. | A test harness that holds real users' tokens. |
| **Internal audit** | Reader | A path from a decision to the exact export, pack and results it used. | A pack tuned to pass. |

---

## User stories (top 4)

1. **As the retrieval-layer engineer**, I want the pipeline to fail when a change returns a document to someone who may not open it, even when that document answers the question, so a relevant leak does not count as a pass.
2. **As a reviewer**, I want REVIEW when the control query did not run or did not return the target, so a clean probe is not read as proof.
3. **As the access owner**, I want canaries built from my export, including pairs that were open under the index copy and are closed now, so a stale ACL copy shows up.
4. **As internal audit**, I want each decision tied to the hashes of the export, pack and results it used, so I can reproduce it.

---

## KPIs

**North star:** share of leaking pull requests blocked before merge, with a recorded decision. Target 🔴 100%. Prototype baseline: 27 of 28 blocked.

**Inputs (leading):**
- Pack shape (prototype: 🟢 62 canaries: direct_deny 15, nested_deny 15, ordinary 22, stale_acl 10, `step_04_with_canary.py`).
- Canaries with a control query (prototype: 🟢 3 of 62 have none because nobody may open the target today, `step_04_with_canary.py`).
- Harnesses that run the control first and write `primed` from what happened (target: every harness).
- Access exports taken from the branch under test (target: every pull request).

**Outputs (lagging):** prototype baselines from the planted set.
- Leaking pull requests blocked. 🟢 27 of 28, against 7 of 28 for the relevance eval (`step_04_with_canary.py`, `step_01_relevance_only.py`).
- Clean pull requests blocked. 🟢 0 of 22; 3 of 22 sent to review; access-grant pull requests allowed 5 of 5 (`step_04_with_canary.py`).
- Pull requests a person has to read. 🟢 30 of 50 (`step_04_with_canary.py`).
- Blocks with no canary aimed at a leaked pair. 🟢 7 of 27 (`step_04_with_canary.py`).
- Known miss. 🟢 1 leaking pull request passes: PR-011 (`step_04_with_canary.py`).
- BLOCKs overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Build a pack from a real access export and run it on one retrieval repository with `--fail-on never`. Print the decision, fail nothing, and compare with what the review found. |
| 1: Calibration | 4w | Read every NOTE. Fix the harness where the control does not run. Set the quotas and the minimum per source against the real export. |
| 2: BLOCK enforced | 4w | Fail the step on BLOCK on one repository. REVIEW stays advisory. |
| 3: REVIEW enforced and Action published | 6w | Fail on inert and unprimed canaries. Publish the Action from its own repository. |
| 4: Ledger and delegation-aware canaries | 8w | Write a decision record per run. Add canaries aimed at delegated pairs and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should a REVIEW fail the step?** In the prototype it does not (`--fail-on block` is the default). Recommendation: advisory during shadow, then fail on REVIEW for inert and unprimed canaries, because those mean the test could not see.
2. **How large should the pack be?** The default quotas give 62 canaries here. 🟢 The stratified pack catches 15 of 28 unprimed and 20 of 28 with a control query first (`step_03_deficiencies_exposed.py`). Recommendation: start with the defaults and raise the quota of the stratum that misses most on the real harness.
3. **Where does the access export come from, and how fresh must it be?** Recommendation: a scheduled export per branch with a recorded hash; the stale-ACL stratum needs `acl_at_index`, which many systems cannot produce, so say so in the pilot.
4. **Who runs the harness, with which identities?** Recommendation: the retrieval-layer owner, with test identities that hold no production rights.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the pipeline.** The check is stateless: it reads an export, a pack and a results file and returns a decision. Production adds a scheduled export, a decision ledger and a published Action, all designed and none built.
- **Never silent.** Malformed input exits 2. A canary with no result, an unprimed canary, an inert canary, an unknown id or a thin source is a REVIEW, not an ALLOW.
- **Strings from input are data.** Annotations and text output escape control characters, so a hostile title cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves a count shows in the diff.

**What is next.** Run it on one retrieval system the owner may share; add a chunk-to-document mapping helper; publish the Action from its own repository.

**What would have to be true before a pilot.**
- The harness runs the control first and writes `primed` from what happened.
- The access export comes from the branch under test and carries `acl_at_index` if the stale-ACL stratum is wanted.
- Test identities hold no production rights.
- One real system can be shared, so the quotas are set against a real estate and not mine.
- The team agrees which level fails the step.

---

*This PRD names [20 CorpusGate](../20-corpusgate-rag-entitlements/), [28 Tool Schema Drift](../28-tool-schema-drift/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The code here imports nothing from them.*
