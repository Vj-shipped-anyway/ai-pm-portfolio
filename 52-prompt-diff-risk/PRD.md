# PRD: prompt-diff-risk (PR check)

## Problem
A system prompt is edited in a pull request like any other file. The unit tests on the code around it still pass. The assistant then refuses what it used to answer, drops a rule, or gains a tool, and the first signal is a customer. Running the full probe set on every edit is slow and costly, and reading every diff does not say which probes matter.

## Who it is for
An engineer or product owner who maintains the prompt of a customer-facing assistant, and the reviewer who approves changes to it.

## What it does
1. Splits two prompt revisions into statements and aligns them.
2. Classifies each changed statement as constraints, scope, tone, tools or other, with a risk class a reader can act on.
3. Reads tool grants from a catalogue with an explicit read or write access field.
4. Maps each finding to probe slices and prints how many probes to run.
5. Prints ALLOW, REVIEW or BLOCK, exits non-zero at a chosen level, and writes GitHub annotations on request.

## Out of scope
Running the probes; calling any model; judging whether a sentence is true or safe; non-English prompts; prompts in structured formats other than plain text; order and heading effects; hosting. A Marketplace listing is a later, separate step.

## Success, as the scripts print it
High-risk pull requests blocked (19 of 22 on the planted set); harmless ones blocked (2 of 18); people reading fewer pull requests than a text diff would send (52 of 70 against 70); probe runs cut against running the full set every time (504 of 3780); the known misses named (7 of 52 risky pull requests pass).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling, although the set includes cases the rules miss and cases that raise false alarms. The failing probes are simulated. A swapped word in a long sentence passes. The thresholds are assumptions.

## Next
Run it on one real prompt repository the owner is allowed to share and count the false alarms; compare the slices it names with the probes that actually failed after past prompt changes; publish the Action from its own repository.
