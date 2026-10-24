# PRD: Entitlement Canary

## Problem
An assistant that retrieves from internal documents must return a document only to a user who may open it. The usual retrieval eval in CI scores relevance. A document that matches the question is a relevant result whether or not the asker may read it, so the eval passes pull requests that leak.

## Who it is for
The engineer who owns the retrieval layer, and the reviewer who approves changes to it: index settings, the access filter, the cache, a new document source.

## What it does
1. Builds a pack of canaries from an access export: pairs where the user may not open the document, chosen from four strata (stale access list, nested deny, direct deny, ordinary) with a minimum per document source.
2. Reads the results your test harness recorded for the pack, including a control query by an entitled user.
3. Checks every returned document against the access export on the pull request's branch, not only the canary's target.
4. Prints ALLOW, REVIEW or BLOCK, exits non-zero at a chosen level, and writes GitHub annotations on request.

## Out of scope
Running or hosting a retrieval system; reading generated answers for leaked content; chunk-level access rules; any model call; a Marketplace listing (staged in `action/`).

## Success, as the scripts print it
Leaking pull requests blocked (27 of 28 on the planted set); clean pull requests blocked (0 of 22); people reading fewer pull requests than all of them (30 of 50); the known miss named (PR-011, one leaked pair).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. The harness is the user's code: a control query that never runs hides a shared cache. The pack is a sample, so a leak that touches one pair can pass.

## Next
Run it on one retrieval system the owner may share; add a chunk-to-document mapping helper; publish the Action from its own repository.
