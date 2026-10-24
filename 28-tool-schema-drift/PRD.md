# PRD: Tool Schema Drift gate

## Problem
Agents call tools through a schema they were given. When a team changes that schema in a pull request, the unit tests on the code behind the tool still pass. The agent then meets rejected calls, or calls that still validate and now mean something else.

## Who it is for
An engineer who owns a tool catalogue behind an agent, and the reviewer who approves changes to it.

## What it does
1. Compares two schema files and classifies each change as breaking, behavior-risk or non-breaking, with a reason a reader can act on.
2. Checks numbers and units in every description that changed.
3. Replays recorded calls against the new schema.
4. Prints ALLOW, REVIEW or BLOCK and exits non-zero at a chosen level, with GitHub annotations on request.

## Out of scope
Reading descriptions for malicious instructions; semantic-version policy; nested or composed schemas; any model call; hosting. A Marketplace listing is a later, separate step.

## Success, as the scripts print it
Breaking pull requests blocked (25 of 25 on the planted set); harmless ones blocked (0 of 27); people reading fewer pull requests than a text diff would send (34 of 67 against 67); the known misses named (6 of 15 behavior-risk changes pass).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling, although the set now includes cases the rules miss. Replay depends on the recorded calls. The unit check misses a scale change that keeps the unit word.

## Next
Run it on one real tool catalogue the owner is allowed to share; add a version-policy check; publish the Action from its own repository.
