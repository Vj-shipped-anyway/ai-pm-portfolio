# PRD: runbook-dryrun

## Problem
An incident runbook is usually a page. Its first real test is the incident, when the person following it finds an unfilled parameter, a precondition that is not true, or an approval that covers a different target. A dry-run flag that prints the commands does not help with any of those.

## Who it is for
The owner of an AI-operations runbook (model rollback, fallback routing, tool switch-off) and the person who is asked to approve one of its steps.

## What it does
1. Reads a runbook in a small YAML subset: steps with an effect, a risk, a command, preconditions, declared state changes, an optional approval gate and a rollback.
2. Lints the runbook alone: unfilled parameters, high-risk writes with no gate, state keys nobody declares, repeated step ids, missing rollbacks (a warning).
3. Walks the steps against a copy of a state snapshot, applying the declared changes, and stops at the first precondition that fails.
4. Holds at each approval gate until a record exists from a different person, in the right role, for the digest of the exact rendered command, inside its time limit.
5. Prints READY, WAITING or BLOCKED and exits non-zero at a chosen level, with GitHub annotations on request. Nothing is executed.

## Out of scope
Running commands; branches, loops and parallel steps; full YAML; a directory lookup for roles; reading a command to infer its effect; any model call; hosting.

## Success, as the scripts print it
Blocked cases caught before the run (46 of 53 on the planted set); waiting cases held at the gate (8 of 8); the missing rollback warned (4 of 4); the known misses named (7 of 53 pass) and the known false alarms named (3 of 41).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. The tool trusts the declared effects and the snapshot. A strict type check blocks a clean case whose snapshot holds a number as text.

## Next
Run it on one real runbook the owner is allowed to share; add a staleness limit on the snapshot; let a gate name a directory group instead of a role string.
