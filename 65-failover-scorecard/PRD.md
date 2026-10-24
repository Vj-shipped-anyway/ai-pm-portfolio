# PRD: Failover Scorecard

## Problem
A bank can list the services that are supposed to come back in a second region. It is harder to say which of them have shown it. A plan on paper, a drill that passed two years ago, a drill that exercised one availability zone, or a service whose own drill passed while the service it needs was never tested all look the same in a status column.

## Who it is for
The person who owns operational resilience for a set of services, and the engineer who has to answer "which of these would we bet on?" before an audit or a real event.

## What it does
1. Reads a service map and a drill log.
2. Applies one readiness rule per service: a live drill of the right scenario, passed, inside the service's own recovery target, against the current secondary region and config version, inside the window for its tier, with every declared dependency also ready.
3. Prints a status per service (READY, NOT_REQUIRED, NO_PATH, UNTESTED, FAILED, SLOW, CHANGED, STALE, DEPENDENCY) with the reason in one line, a count per domain, and a decision for the tier-1 services.
4. Exits 1 when a tier-1 service has no tested way back, 2 on bad input or when it checked nothing.

## Out of scope
Data-loss targets, partial failover, capacity in the secondary region, cost, dependencies that are not declared, reading runbooks, any model call, hosting, a staged CI Action.

## Success, as the scripts print it
Services that would not recover and are flagged (25 of 28 on the planted set); services that would recover and are flagged (0 of 16, with the old-but-valid and fixed-after-failure cases among them); owner-accepted gaps kept apart from real gaps (4 of 4); the known misses named (3 services pass because of a dependency the map omits).

## Risks
The planted set and the rule share an author, so the numbers are a ceiling. The windows are my assumption. A drill row is taken at its word. The dependency check is only as good as the map.

## Next
Run it on one real service map and drill log that the owner is allowed to share; add a recovery-data-loss column; add a check that compares the declared dependencies with a traffic or call-graph export.
