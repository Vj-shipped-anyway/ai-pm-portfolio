# PRD: Inventory Check

## Problem
Model risk guidance that banks built their model inventory around now places generative and agentic AI outside its scope. A bank's own governance has to carry those systems, and the inventory is where that starts. Inventories for them are kept by hand. A record can be blank, stale, or missing entirely, and a system can run for months with no record. Nobody tests the file.

## Who it is for
The person who owns the inventory of AI systems, and the model risk reviewer who relies on it.

## What it does
1. Completeness: required fields, legal values, the fields an agent needs (tools, permission scope, human approval), and the evidence a production system owes at its risk tier.
2. Staleness: review and evaluation dates against a cadence per tier, and the recorded model id against the model recent traffic used.
3. Coverage: traffic from systems with no record or no system id, retired systems still running, production systems with no traffic.
4. Prints PASS, REVIEW or FAIL with the finding behind each, exits non-zero at a chosen level, and prints GitHub annotations on request. A staged agent skill wraps the command.

## Out of scope
Judging whether a system is safe or well governed; reading a purpose statement for meaning; checking that an owner is still employed; any model call; hosting; a mapping to any rule clause. The field list and every number is an assumption, because SR 26-2 prescribes none.

## Success, as the scripts print it
Defective records flagged (51 of 57 on the planted set); clean records flagged (2 of 43); people opening fewer records than a full read (53 of 100); the known misses named (6 defective records pass, 3 of 7 shadow systems stay unnamed).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. The usage tests depend on a gateway that logs the system id and the model id. The cadences are assumptions and a bank would set its own.

## Next
Run it on one real inventory the owner is allowed to share; add a check for owners no longer in the staff list; decide with the model risk team what a REVIEW finding obliges.
