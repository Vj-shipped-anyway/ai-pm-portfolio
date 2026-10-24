# PRD: fairlens six-test pack

## Problem
A validator reviews a points scorecard. The decline reasons look consistent from one group to the next, and the model card shows accuracy and approval rate and nothing split by group. A feature inside the score can still move approvals by group, and neither view shows it.

## Who it is for
A model risk analyst who receives a scores file from a credit team and has an afternoon, and the credit analyst who has to answer the finding.

## What it does
1. Reads a CSV with a group column, a score, an outcome and, optionally, the points of one suspected proxy and the listed decline reasons.
2. Runs six tests: approval gap, adverse impact ratio with a bootstrap interval, cutoff sweep, proxy ablation with an accuracy check, reason-code pairs, reason naming.
3. Prints PASS, REVIEW or FAIL for each, with the numbers and the rule behind them, and an overall verdict.
4. Exits 1 at a chosen level, 2 on malformed input, and prints GitHub annotations on request.

## Out of scope
Training or fitting a model; inferring groups from other fields; more than one proxy column; legal conclusions; any hosted service.

## Success, as the scripts print it
Planted proxies marked FAIL by the ablation (7 of 14); other portfolios marked FAIL by it (1 of 22); reason pairs passed where the ablation failed (6 of 8); the known misses named (7 of 14 planted proxies not marked FAIL).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. Every threshold is an assumption. Real portfolios rarely carry group labels. The ablation names one column.

## Next
Run it on one real scores file the owner is allowed to share; accept a list of proxy columns; add a group-inference step with its own error check.
