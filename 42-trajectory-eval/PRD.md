# PRD: Trajectory Eval

## Problem
A team that evaluates an operations agent usually checks the final answer. A run can reach the right answer after skipping a check, acting before an approval, calling a tool the task forbids, or looping. The final-answer eval passes those runs, and the reviewer who owns the process never sees them.

## Who it is for
An AI operations lead or engineer who owns an agent in a rule-based workflow, and the control owner who decides which steps must happen first.

## What it does
1. Holds a task as a rubric: graded steps (tools that count, arguments that must match, which earlier steps each must follow), forbidden tools, stop signals, a call budget and the expected final answer.
2. Grades a recorded run against the rubric and prints PASS or FAIL with the reason, a partial-credit score and an exit code.
3. Lets independent steps come in any order and lists equivalent tools, so a different but valid path is not punished.
4. Ships 20 synthetic bank-operations tasks and 240 recorded runs, with the planted truth kept apart from the scorer.

## Out of scope
Running an agent; reading free text inside arguments or the wording of a final answer; finding unsafe actions nobody listed; prompt-injection or hijacking tests; any model call; hosting.

## Success, as the scripts print it
Defective runs caught (90 of 96, against 12 of 96 for a final-answer check); defective runs with a right final answer caught (78 of 84); the known miss named (6 free-text leaks pass); the known false alarm named (6 sound runs that use an unlisted equivalent tool fail).

## Risks
The runs and the rubric share an author, so the numbers are a ceiling. The call budget is an assumption. A real rubric needs a review against real traces, and the unlisted-tool rate on real traces is unknown.

## Next
Run it on a few days of traces from one agent the owner may share; add a way to propose rubric alternatives from the tools that fail most often; add a check for sensitive patterns in free-text arguments.
