# PRD: Cost Gate

## Problem
A pull request changes a prompt, a retrieval depth or a model. The eval gate, if there is one, reports accuracy. Nothing reports what a right answer now costs, so an overspend shows up on the next invoice. A check on cost per call does not fix that: it passes a cheaper model that is right less often, and it fails a longer prompt that is right more often.

## Who it is for
The engineer who owns an AI feature's prompt and model, and the reviewer who approves changes to it. A finance partner who wants a budget with an owner reads the budget file.

## What it does
1. Reads one eval run (a CSV with item, slice, model, correct, input and output tokens) and a budget file (prices, `min_items`, an overall ceiling, a ceiling per slice).
2. Computes cost per correct answer for the whole run and for each slice, with a 95% interval.
3. Prints FAIL when the interval's lower end is over the ceiling, WARN when only the estimate is, PASS otherwise, and names any slice it did not judge.
4. Exits non-zero at a chosen level, with GitHub annotations on request.

## Out of scope
Accuracy gates; latency; caching, batch and per-request pricing; production traffic; forecasting the invoice; any model call; hosting. A Marketplace listing is a later, separate step.

## Success, as the scripts print it
Over-budget change requests stopped (13 of 21 on the planted set); within-budget ones stopped (0 of 19); slice regressions found that the whole-run check passes (4 of 4); the known misses named (3 of 21 over-budget change requests still pass).

## Risks
The planted set and the gate share an author, so the numbers are a ceiling. The interval is a normal approximation and ignores grader noise. The budget file goes stale when prices change. A small eval set leaves every slice unjudged.

## Next
Run it on one real eval export the owner is allowed to share; add a check that the price table is not older than a set age; publish the Action from its own repository.
