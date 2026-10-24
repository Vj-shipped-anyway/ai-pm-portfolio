# PRD: plant

## Problem
A checker or an eval is only as trustworthy as the data it was tried on. Test data made by corrupting rows at random and adding an is_bad column gives a recall and a precision, and hides which failures were found, which were never found, and what the checker does to rows that merely look like failures.

## Who it is for
An engineer or reviewer who owns a checker, an eval or a guardrail and needs to know what it misses before it meets real data.

## What it does
1. Reads a spec: a seed, columns, and named behaviors with a role (failure or look-alike), an exact count and the change to make.
2. Writes the data with no label column, a separate key (one line per planted row: behavior, role, exact change) and a manifest with hashes.
3. Scores a flags file against the key, behavior by behavior: failures found, look-alikes flagged, clean rows flagged.
4. Exits 1 under a chosen minimum recall; exits 2 with one line on input it cannot use.

## Out of scope
Time series, joins, free-text synthesis, two failures on one row, scoring by reason rather than by row, any model call, hosting.

## Success, as the scripts print it
The key shows what an is_bad column hides (0 of 50 paraphrased injections found; 29 of 30 look-alikes flagged by the naive rules); a rerun with the same seed gives identical bytes; the denominators do not move between seeds (84 failures each time).

## Risks
The spec and the checker share an author, so the scores are a ceiling. The key measures the variants planted, not the variants that exist.

## Next
Run it on one checker whose owner can share a real, redacted sample, and plant that sample's failure shapes; add a second failure on one row as an option; draw variants from a source other than the checker's author.
