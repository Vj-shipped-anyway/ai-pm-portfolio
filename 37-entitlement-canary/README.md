# 🐤 Entitlement Canary (leak test for retrieval)

**I wanted to know whether a pull request to a retrieval system can return a document to someone who may not open it, and whether the checks most teams run would notice. A relevance eval does not: a leaked document that matches the question counts as a correct answer. This is a command-line tool and a staged GitHub Action: it builds a pack of canaries from an access export, reads what your test harness got back for each one, and prints ALLOW, REVIEW or BLOCK.** It extends the canary pack in [20 CorpusGate](../20-corpusgate-rag-entitlements/) into a check that runs on a pull request, in the shape of [28 Tool Schema Drift](../28-tool-schema-drift/).

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 37-entitlement-canary/src && python3 entitlement_canary.py --demo
```

It prints:

```text
access: 5 documents, 3 users, 5 groups
pack: 6 canaries (nested_deny 1, direct_deny 1, ordinary 4)
LEAK CAN-001 [nested_deny] U2 was returned D1 "Payments runbook [DOC-0001]": an ACL entry denies grp-contractors
canaries run 6 of 6; leaks 1; retired (the user may now open the target) 0; inert 0; unprimed 0
decision: BLOCK
```

Standard library only, Python 3.9 or newer. To use it on your own files: `python3 entitlement_canary.py build-pack access.json --out pack.csv`, run the pack through your retrieval system with your own harness (the contract is in [`action/README.md`](./action/README.md)), then `python3 entitlement_canary.py check access.json pack.csv results.csv`. It exits 1 on BLOCK, so a CI step fails; `--format github` prints annotations.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 120 documents, 20 users, 50 planted pull requests, 28 of which leak; the script is named in brackets):

- 🟢 The usual gate is a relevance eval. It stops 7 of 28 leaking pull requests, and 9 of 22 clean ones. In the eval runs of the leaking pull requests, 923 results went to a user who may not open them and 739 of those were scored as correct answers (`step_01`)
- 🟢 Twelve hand-picked canaries with a string match catch 3 of 28 and flag 5 of 22 clean pull requests, all five of them access grants (`step_02`)
- 🟢 A pack of 60 random canaries catches 15 of 28; the stratified pack catches 15 of 28 unprimed and 20 of 28 with a control query run first; each flags 5 of 22 clean pull requests (`step_03`)
- 🟢 Checking every returned document against the access export of the pull request's branch, not only the canary's target: 27 of 28 caught, 0 of 22 clean flagged (`step_03`)
- 🟢 The full gate blocks 27 of 28 leaking pull requests and 0 of 22 clean ones, sends 3 of 22 clean ones to review, and a person reads 30 of 50 (`step_04`)

## What it still gets wrong

- 🟢 One leaking pull request passes: PR-011, a delegation change that leaks one (user, document) pair, with no canary aimed at it (`step_04` prints it). The other three delegation pull requests are blocked, one of them by a canary aimed at its pair.
- 🟢 7 of the 27 blocks have no canary aimed at a leaked pair: some other canary's results held a document its user may not open, and the check reads every returned document. That is luck as much as design, and a smaller or differently drawn pack could miss them (`step_04`).
- 🟢 Stratifying the pack does not beat drawing it at random on its own: both catch 15 of 28 unprimed. The random pack caught the flat-group change in all 5 pull requests by luck of the draw and the stratified pack in none; checking every returned document caught all 5 on the stratified pack (`step_03`).
- 🟢 3 of 62 canaries have no control query, because nobody may open the target today (`step_04`).
- **The test set and the rules share an author.** I planted the changes and wrote the check, so 27 of 28 shows the rules cover what I planted. I changed the data design and the prime-user rule after early runs (the data README says how). Treat the result as a ceiling for these rules, not a rate on a real retrieval system, which I have not tested.
- **The retrieval system is a stand-in**: a keyword index with an entitlement filter and a few settings. A real one has chunks, embeddings, a reranker and answer generation. The tool sees only the document ids your harness reports, so a leak that appears only in generated text is invisible to it.
- **The check trusts the harness.** It reads the `primed` column; it cannot tell whether the control query really ran first, and a cache shared between users shows only when it did.
- **The access rules are the ones in the module docstring**: a deny entry wins, nested membership counts, a document with no allow entry is closed. A system that treats a missing ACL as public needs different rules. The stale-ACL stratum needs an `acl_at_index` export, which many systems cannot produce.
- Group names and ACL entries are plain strings. Role-based, attribute-based and per-chunk rules are not modelled.

## Use it in CI

[`action/`](./action/README.md) holds a staged GitHub Action and the steps to publish it from its own repository, which a Marketplace listing requires. It has not been published and has not run on GitHub. What is tested is the command it wraps (`tests/test_check.py`, 41 tests in all).

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does a relevance-only eval let through? | `step_01_relevance_only.py` |
| 2 | What does a short hand-written canary list with a string match catch? | `step_02_string_match.py` |
| 3 | What does each part of the pack and the run buy, and where is the limit? | `step_03_deficiencies_exposed.py` |
| 4 | What does the full gate decide on all 50 pull requests? | `step_04_with_canary.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

The [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/llm-top-10/) lists sensitive information disclosure (LLM02:2025, [page](https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/), read 2026-10-23), where it recommends least-privilege access to data, and vector and embedding weaknesses (LLM08:2025, [page](https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/), read 2026-10-23), where it calls for permission-aware vector stores and warns of context leaking between users who share a store. This tool does not build a permission-aware store. It tests, on each change, whether the store you built still returns only what the asker may open. It is a prototype, aligned to that guidance and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real system. The 0.02 tolerance for the relevance eval in step 1 is an assumption (🟡), not taken from any standard. A prototype on synthetic data, not a production case study.

## Fork it

Replace `data/access_base.json` with an export of your own groups, users and document ACLs and keep the keys, build a pack with `build-pack`, and write a harness that records what your retrieval system returns. Read the [PRD](./PRD.md) for the scope I held to.
