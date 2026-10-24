# PRD: challenge-pack

## Problem
A second-line challenger gets a risk tier and has to decide what to test and what evidence to ask for. In practice the request list is copied from the last review, the tier on the form is taken as written, and the evidence that comes back is checked by eye. Vendor products and use cases outside the model definition get no extra questions, and stale or mis-versioned evidence passes.

## Who it is for
A model-risk or AI-governance reviewer who challenges use cases, and the first-line owner who has to supply the evidence.

## What it does
1. Looks the tier up in a tier-to-test-plan table (13 core items, four depths) and raises the tier when a rubric recomputed from the form says so.
2. Adds a vendor overlay and a scope overlay for use cases outside the guidance's model definition.
3. Reconciles each plan item against the evidence row: missing, wrong version, prepared inside the developer's unit (only where an outside preparer is required), stale on the latest of the evidence date and the reaffirmation date.
4. Writes a challenge memo per use case from a template, and a summary CSV. Exits 1 when any use case has a gap. A staged Agent Skill wraps the command.

## Out of scope
Reading the evidence itself; deciding whether a use case may go live; a validation of any model; the tier recompute beyond the rubric (see [11](../11-tiergate-ai-usecase-intake/)); control crosswalks (see [16](../16-controlmap-ai-obligation-crosswalk/)); any model call; hosting.

## Success, as the scripts print it
Owed items asked for (1403 of 1486 against 876 for a generic list and 1080 for the tier table alone); planted evidence defects found (360 of 437); hard negatives flagged (0 of each kind); known misses named (hollow evidence, a tier below the truth).

## Risks
The data and the rules share an author, so the numbers are a ceiling. The tier table, the windows and the independence rule are assumptions. The checks read metadata only.

## Next
Run it on one real evidence export the owner is allowed to share; add a check that a reaffirmation names who reaffirmed; ask a second reviewer to try to break the tier table.
