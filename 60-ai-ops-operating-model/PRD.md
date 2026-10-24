# PRD: AI ops operating model review skill

## Problem
A program owner says an AI use case in bank operations is "in rollout" or "handed off". The status deck repeats it. Nobody checks that the proof for each earlier stage exists, is current and was produced by someone other than the builder, so the program office learns the real stage from an incident or an audit.

## Who it is for
The lead of an AI program office, and the reviewer who has to say whether a claimed stage holds.

## What it does
1. A skill walks the eight stages of OPERATING_MODEL.md. For each owed item it asks for an artifact reference, who produced it and its date, and records nothing when it gets no reference.
2. A command compares the register with the checklist: tier-aware owed list, placeholder test, future-date test, freshness (1.5 times the cycle) and independence from the builder.
3. It prints the stage the evidence reaches and CONFIRMED, OVERCLAIM or UNDERCLAIM against the claim, with a first-90-days count, and exits 1 on an overclaim.
4. It names what a person must open: one artifact per stage marked OK, and the sentence to confirm in it.

## Out of scope
Reading the artifacts; computing the tier (project 11 does that); approving a program; mapping to a rule clause by clause; any model call; a skill marketplace listing.

## Success, as the scripts print it
Stage reached equals the planted truth for 45 of 60 programs against 16 of 60 for owners' reports and 19 of 60 for a flat checklist; 30 of 36 claims above the truth flagged, none of the 24 others flagged; the known misses named (0 of 19 hollow artifacts rejected, 6 of 36 overclaims pass).

## Risks
The planted data and the rules share an author, so the numbers are a ceiling. Tiers, cycles and the first-90-days mapping are assumptions. The audit-sample step is designed and not measured. The skill has not been run by anyone.

## Next
Run the command on one real register the owner may share; test the audit sample on artifacts, with a second reader; add a check that the same reference is not cited for two items.
