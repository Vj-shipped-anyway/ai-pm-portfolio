# PRD: TierGate Intake Check

## Problem
A sponsor fills in an intake form and writes the risk tier on it. That tier decides how deep the review goes. Nobody recomputes it, and the answers behind it come from the same person who benefits from a light review.

## Who it is for
The AI governance lead who triages intake forms, and the model risk reviewer who receives the ones sent to full review.

## What it does
1. Applies a written rubric (six inputs, summed, four tiers) to each form.
2. Cross-checks the data class against the data catalog, the vendor model against the vendor registry, and the customer-facing answer against the words in the title and description.
3. Prints every form whose declared tier is below the recomputed tier, with the reason, and exits non-zero so a pipeline step can stop.
4. Ships as a command line, GitHub annotations on request, and a staged Agent Skill that runs the command and reports what it printed.

## Out of scope
Duplicate linking, the evidence gate and the review queue (project 11); any model call; reading descriptions for meaning beyond a keyword; a registry or catalog integration; publishing the skill.

## Success, as the scripts print it
Recomputed tier equals the reference on 170 of 200 forms against 137 for the declared tier; 87 of 93 full-review forms reach full review against 63; forms below the reference fall from 57 to 11; the known misses are named (11 forms) and the false alarms are counted (19 above the reference, up from 6).

## Risks
The data and the rules share an author, so the numbers are a ceiling. The recompute is only as good as the catalog and the registry; a stale catalog entry agrees with a wrong form. The conservative rules raise some internal tools. The rubric points are an assumption.

## Next
Run it on one real intake export the owner may share; add a second source for autonomy, regulatory scope and exposure, which the forms here never get wrong; publish the skill from its own repository.
