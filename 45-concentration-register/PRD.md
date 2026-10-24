# PRD: Concentration Register

## Problem
A register of critical services records where each one runs and who owns it. It does not say what happens when one cloud provider or one region fails. A count of services per provider understates a provider that sits under many others, and overstates one whose services have a standby elsewhere.

## Who it is for
A technology risk or third-party risk analyst who keeps the register, and the reviewer who has to say whether the critical estate is concentrated.

## What it does
1. Reads a services file (placement, criticality, standby) and an optional dependencies file (hard or soft).
2. Runs one outage scenario per provider and per provider-region, follows hard dependencies and working standbys, and counts the critical services lost.
3. Prints that count next to a direct count of services on the provider or region, flags scenarios above a chosen limit, and lists critical services with no placement.
4. Exits 1 when a scenario is above the limit, 2 on malformed input; `--format json` for other tools.

## Out of scope
Capacity of a standby, recovery time, availability zones, shared control planes, dependencies outside the register, any model call, hosting, discovery of placements from cloud accounts.

## Success, as the scripts print it
Scenarios truly above the limit that the tool flags (4 of 4 on the planted set, against 1 of 4 for a direct count); false flags (0); lost pairs found (64 of 74); the misses named and traced to their cause (10 to 4 to 2 to 0).

## Risks
The world and the rules share an author, so the numbers are a ceiling. The 30% limit is an assumption. The tool understates by design when the register has gaps, and a decision near the limit can flip.

## Next
Run it on one register the owner is allowed to share; add a field for tested failover so a claimed standby is not taken on trust; read the 2021 proposal and compare its concentration language with the final text.
