# PRD: Review Capacity calculator

## Problem
A human-in-the-loop queue is sized by feel or by dividing the day's work by the hours in a shift. Both leave the queue to absorb every cluster of arrivals and every long case, and the reviewers who absorb it are the ones asked to look carefully. The program manager who has to defend a headcount number has no small, inspectable tool to produce one.

## Who it is for
The person who owns a review queue behind an AI system and has to say how many reviewers it needs, and whoever approves the headcount.

## What it does
1. `size` reads one row of assumptions per queue (arrival rate, opening batch, handling time and its spread, wait target, utilization cap, shrinkage) and prints the reviewers needed at the desk, the roster that implies, and the answer from Erlang C on the mean rate for comparison.
2. Compares the roster with a current headcount when one is given, and exits 1 when a queue is short, with GitHub annotations on request.
3. `fit` measures the assumption columns from a case log, so the inputs are not guesses.

## Out of scope
Priority classes, skill-based routing, abandonment, time-of-day staffing beyond the opening batch, shift scheduling, cost, any model call, any measure of review quality, hosting.

## Success, as the scripts print it
Fewer queues short than Erlang C leaves (the tool meets both limits on 12 of 13 against 10); the two opening-batch queues sized right (7 and 7 against a true 7 and 7); two hard negatives not over-staffed (2 of 2); the known misses named (one bursty queue short, one queue whose volume rose after the history was taken).

## Risks
The synthetic queues and the rules share an author, so the numbers are a ceiling. Each true number is one 10-day replay. The variability term is not shown to help on 13 queues. Inputs measured on a quiet fortnight will under-staff the busy one.

## Next
Run it on one real queue's log that its owner may share; add a second replay with priority classes; check the sizing against several replays of the same assumptions instead of one.
