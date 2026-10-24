# PRD: Shadow Score

## Problem
An agent runs in shadow mode and people record their own outcome for the same cases. The report that follows is usually one agreement rate. It drops the cases the agent skipped, carries no interval, hides a weak segment, a bad week or an unusual reviewer, and treats every disagreement as equal.

## Who it is for
The person who owns an agent pilot and has to say whether it should leave shadow mode, and the steering group that reads the answer.

## What it does
1. Joins a proposals file and an outcomes file on case_id and reports what did not join.
2. Prints the first-report rate with a 95% interval, the rate that counts abstentions as misses, and the rate of a rule that always proposes the most common outcome.
3. Splits agreement by recorded outcome, segment, week, reviewer and stated confidence, and judges a group only when it has enough proposals.
4. Runs ten checks, each PASS, FAIL or SKIP with the reason, and prints HOLD or CLEAR. Exits 1 on HOLD.

## Out of scope
Deciding that an agent may act; a second-reviewer audit of agreements; per-class agreement floors; correction for many comparisons; any model call; hosting.

## Success, as the scripts print it
Planted problems found (4 of 5 on the synthetic set); look-alikes that fail a check (0 of 3); the single-number report passing a 90% bar while the scorecard prints HOLD with 6 of 10 checks failing; the known misses named (one planted week passes, 17 agreements are both wrong).

## Risks
The planted set and the checks share an author and the planted rates were tuned to be visible, so the numbers are a ceiling. The human outcome is not ground truth. Thresholds are my defaults, not a standard's.

## Next
Run it on one real shadow log its owner can share; add a second-reviewer sample for the agreements; add an agreement floor per outcome class.
