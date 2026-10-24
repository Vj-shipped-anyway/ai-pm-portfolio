# PRD: Deprecation Impact

## Problem
A vendor announces that a model version retires on a date. The notice names a model. The people who have to act own features, and nothing tells them which features call that snapshot, directly or through a floating alias, a fine-tune, a fallback or an evaluation judge. They learn from failed calls, or they search by hand and trust the search.

## Who it is for
The person who runs the AI platform or the feature register, and the owners who get a ticket when a notice lands.

## What it does
1. Reads a model catalogue with notice and retirement dates, an alias table, a feature register and the model each feature names in each role.
2. Resolves every model string: exact id, alias (with the date it was recorded), family name, or the base model of a fine-tune. A string it cannot resolve goes to a check queue, never to clear.
3. Prints a retirement calendar, a hit list with days left, the lead time the feature needs and a tier, and the monthly cost on the named successor.
4. Exits 1 when the worst tier reaches a chosen level, so a scheduled job can fail; exits 2 on input it cannot read.

## Out of scope
Fetching vendor notices; migrating or testing the successor; embedding models and re-indexing; reading code or configuration to find model strings; any model call; hosting.

## Success, as the scripts print it
Affected dependencies found and dated (29 of 42 on the planted set); no false alarm among the hits (0 of 29); a person opens fewer features than a family-name search sends them to (35 against 46); the misses named (7 of 42 with no flag).

## Risks
The data and the rules share an author, so the numbers are a ceiling. The tool reads the registry: a dependency that no row records, or a recent alias entry that is wrong, passes as clear. Lead times are assumptions and decide the tiers. Prices are made up.

## Next
Run it on one real register the owner may share; add the embedding role and the re-index cost; write the vendor-page reader as a separate, checked step.
