# PRD: agent-breaker

## Problem
An agent that starts failing keeps taking cases. A person sees it late, flips a switch that nothing flips back, and afterwards nobody can show what happened or why the agent was allowed back.

## Who it is for
The engineer or operations owner of an agent that calls tools in a regulated workflow, and the second-line reader who asks how it was stopped.

## What it does
1. Keeps one breaker per agent (a field in the data) with four states: CLOSED, OPEN, HALF_OPEN and FORCED_OPEN.
2. Trips on a critical failure kind, on N failures in a row, or on a failure rate over a time window that holds enough calls. Warns at a fraction of the trip level.
3. Holds the agent's calls for a person, doubles the hold after a failed probe, and closes only after several good probes.
4. Has an operator switch that releases into probes, never straight to closed.
5. Writes a hash-chained log of every call, transition, warn and control, and verifies it by replaying the calls through a fresh breaker.
6. Exits 1 when it tripped or the log fails, 2 for input it cannot read.

## Out of scope
Reading whether an outcome was right; fitting thresholds; a live service, timeouts and cross-process state; signing the log; any model call; hosting.

## Success, as the scripts print it
Must-trip faults tripped (12 of 14 on the planted set); harmful calls served against the common breaker (142 against 168 of 312); harmless calls held and their price (267 against 140); the log verifies and the tamper tests are caught (3 of 4 from the log alone, 4 of 4 with the head hash); the known misses named (silent errors, a slow burn, a quiet agent, long blips).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. Every threshold is an assumption and the trip rate was not fitted. A strict probe rule makes the way back slow. The chain proves consistency, not authorship.

## Next
Back-test on one real tool-call log the owner is allowed to share; add a second signal that can see a wrong answer reported as ok; anchor the head hash outside the file by default.
