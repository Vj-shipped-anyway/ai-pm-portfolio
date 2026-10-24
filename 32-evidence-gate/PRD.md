# PRD: Evidence Gate

## Problem
A team says a use case has the evidence its risk tier requires. The pull request that changes the use case has a template with a checklist, and nothing reads it. Boxes get ticked, lines get deleted, a link points at a file that was never added, a date is a year ahead. The reviewer finds out by opening every link, or does not.

## Who it is for
An engineer who ships changes to an AI use case, the reviewer who approves them, and the governance lead who owns the tier-to-evidence table.

## What it does
1. Reads the AI change record in the pull request description: use case, declared tier, one line per evidence item. Comments and code fences are ignored.
2. Takes the tier from the registry when the use case is listed, and looks up the evidence that tier requires (cumulative: a higher tier owes everything below it).
3. Checks that each required item is listed, ticked, references a file that is in the repository and carries a valid date within its freshness limit.
4. Prints ALLOW, REVIEW or BLOCK, exits non-zero at a chosen level, and writes GitHub annotations on request.

## Out of scope
Reading the evidence itself; proving a date or a signature; mapping evidence items to a framework's identifiers; a full markdown parser; any model call; hosting. A Marketplace listing is a later, separate step.

## Success, as the scripts print it
Should-block pull requests blocked (49 of 59 on the planted set); fine ones blocked (3 of 42, all evidence written as a table); wrong-tier labels sent to a person (6 of 6); the known misses named (7 of 59 pass, 3 of 59 reach review only).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. The freshness limits are assumptions. The gate trusts a typed date and a file that exists. A registry that is not kept current sets the wrong bar.

## Next
Run it on one real repository whose owner will share the pull request descriptions; add a content check for the one or two evidence types that can be machine-read; publish the Action from its own repository.
