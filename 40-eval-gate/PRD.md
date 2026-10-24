# PRD: Eval Gate

## Problem
A team calls a hosted model through a name. The vendor can change the snapshot behind it, and the pass rate on the team's probe set may not move enough to notice, or may move on a few high-severity probes while the average hides it. Nothing in the deploy pipeline compares which snapshot answered with which one the team decided to use.

## Who it is for
The engineer who owns a deploy pipeline for a model-backed feature, and the reviewer who signs off on moving to a new snapshot.

## What it does
1. Reads a probe file (severity and baseline per probe) and a results file (passes, trials and the snapshot id each response reported).
2. Blocks when any probe was served by an id other than the pin, or when a probe has no result.
3. Blocks or sends to review when the mean pass rate falls under the baseline, and blocks when a high-severity probe collapses.
4. Prints ALLOW, REVIEW or BLOCK, exits non-zero at a chosen level, and writes GitHub annotations on request.

## Out of scope
Running the probes; judging answers; production monitoring; refreshing baselines; any model call; hosting. A Marketplace listing is a later, separate step.

## Success, as the scripts print it
Should-block deploys stopped (25 of 25 on the planted set); fine deploys blocked (0 of 31); the known miss named (3 subtle drifts pass).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. The thresholds are assumptions. The gate trusts the snapshot id the harness records. Ten trials per probe leave noise on the mean: the worst clean run in the planted set sat 3.3 points under its baseline.

## Next
Run it against one real harness whose owner can share the output; add a per-slice drop rule; publish the Action from its own repository.
