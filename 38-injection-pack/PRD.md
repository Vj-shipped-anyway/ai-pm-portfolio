# PRD: Injection Pack regression suite

## Problem
A prompt gateway is a set of rules in front of an internal assistant. Teams edit those rules in pull requests: a pattern narrowed to stop a false alarm, a rule removed because nobody remembers why it is there, a domain added to an allow-list. The unit tests on the code pass. Nobody replays injection cases, so a change can make the gateway weaker without any check failing, and the first signal is an incident.

## Who it is for
An engineer or security reviewer who owns the rules of a gateway, and the person who approves changes to them.

## What it does
1. Holds a test pack as a CSV: attack and benign cases, each tagged with the channel it arrives on (user input, retrieved document, tool call, model response, session memory).
2. Runs the pack on one rule file (`run`) and reports blocked attacks, blocked benign cases and the misses, by channel.
3. Compares two rule files on the pack (`compare`): a case the old rules got right and the new rules get wrong is a regression, and any regression fails the check.
4. Says so when a changed rule matches no case in the pack, so a silent pass is not mistaken for a safe change.
5. Optional floors for the catch rate and the false-block rate. GitHub annotations on request. A staged Action wraps the command.

## Out of scope
Calling a live gateway or a model; testing the layers in combination; non-English rules; regex timeouts; generating new attacks; hosting. A Marketplace listing is a later, separate step.

## Success, as the scripts print it
Harmful rule changes stopped (21 of 25 on the planted set); harmless ones stopped (1 of 26); decisions that match the held-out truth (46 of 51); the known misses named (4 of 25 harmful changes pass, one of them because the pack has no case for that technique).

## Risks
The pack, the held-out population, the rules and the rule changes share an author, so the numbers are a ceiling. The harm line (one percentage point) is an assumption. Regex rules stand in for a gateway that, in a real deployment, includes a classifier model this prototype does not have.

## Next
Run it on the rule file of one real gateway whose owner is allowed to share it; add a mode that posts cases to a live endpoint; add combined-layer cases; publish the Action from its own repository.
