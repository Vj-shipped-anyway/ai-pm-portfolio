# PRD: swapbrief, a go or no-go brief for a model migration

## Problem
A vendor retires the model behind a production GenAI feature. The team runs its evaluation set on the successor and sees the average rise. The average does not show what a correct answer now costs, whether the slow tail got worse while the median improved, or which slice fell. Nobody writes down what would send traffic back, so the first signal is a complaint.

## Who it is for
The AI platform lead who owns the migration, the model risk reviewer who has to accept the evidence, and the finance partner who asks what a correct answer costs.

## What it does
1. Reads two files: paired per-item results for the current and the candidate system, and a price table. The contract is documented in the README and refuses anything it cannot use, with exit status 2.
2. Reports the accuracy change, cost per correct answer, p50 and p95 latency, and a status per slice, each with a paired bootstrap interval.
3. Prints GO, GO WITH GUARDRAILS or NO-GO, with the reasons, and exits non-zero at a chosen level.
4. Prints rollback triggers: metric, threshold, window.

## Out of scope
Judging answers; comparing prompts (run it once per system); wiring triggers to a monitor; price changes over time; any model call; hosting.

## Success, as the scripts print it
On 80 simulated migrations, false GO falls from 41 of 45 (headline average) and 36 of 45 (average plus vendor sheet) to 2 of 45. Every real cost problem is flagged. The known miss is named: 4 of 26 slice regressions pass.

## Risks
The planted problems and the thresholds share an author, so the rates are a ceiling. The thresholds are assumptions taken from project 13. More than half of the good migrations (19 of 35) get guardrails, mostly because a critical slice is too thin to rule a loss out; that is the price of caution at these evaluation sizes.

## Next
Run it on one real evaluation export its owner can share; add a margin option for the headline rule; publish it as a CI step.
