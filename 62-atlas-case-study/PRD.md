# PRD: ATLAS case-study drafter

## Problem
An agent run goes wrong and an on-call engineer writes a ticket. The trace holds what happened, the ticket holds what someone thought, and neither is in a form a public threat catalog can use. Writing the case study by hand is slow, and a draft written from the ticket copies identifiers and names into a public place.

## Who it is for
An engineer or program owner who has a trace of an agent failure, permission to share it, and wants a first draft to edit before offering it to the MITRE ATLAS maintainers.

## What it does
1. Splits the calls of one run into phases of the same tool and argument shape and finds loops.
2. Writes procedure steps with a tactic, a technique and the call numbers behind each: a denial-of-service step for each loop, plus an injection step and a cost step where the trace shows them.
3. Redacts declared identifiers and never copies the ticket note.
4. Lints the draft against the rules of the ATLAS contribution schema and says which fields a person still owes.

## Out of scope
Reading ticket text; deciding whether an adversary was involved; submitting anything; techniques other than the three; full JSON Schema validation; any model call.

## Success, as the scripts print it
Failures drafted (22 of 32 on the planted set); harmless runs drafted (0 of 28); technique sets equal to the planted set (22 of 22); identifiers or planted strings in a draft (0 of 22); the known misses named (10 of 32 failures get no draft).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. The 20-call threshold is an assumption. A synthetic run is not an incident, and the maintainers decide whether a failure with no adversary is in scope.

## Next
Run it on one real trace its owner is allowed to share; ask the maintainers about scope before writing more; add a cycle rule for tools called in turn.
