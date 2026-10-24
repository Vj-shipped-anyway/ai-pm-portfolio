# PRD: spread-extraction-eval

## Problem
A credit analyst spreads a borrower's statements into a standard template. An extraction model that reads them is tuned and tested on the layouts someone had to hand. When a statement arrives in another layout (thousands instead of units, parentheses for losses, relabelled lines, a balance sheet printed in two halves, a column of note numbers) the single accuracy number on the test set says nothing about it.

## Who it is for
The owner of an extraction step in a lending workflow, and the reviewer who decides whether a new model or prompt may replace the old one.

## What it does
1. Generates synthetic statements in six layouts with the true value of every field, 22 fields in 2 periods.
2. Scores any predictions file field by field and groups the result by an explicit layout column.
3. Names the error class of each wrong value: missing, scale, sign, wrong period, compound, wrong line, other.
4. Gates on drift: a layout under a floor, or too far under the best layout, fails the run (exit 1).
5. Runs a tie-out check that needs no truth: do the figures obey the accounting identities.

## Out of scope
Any model call; image or scanned input; materiality weighting; confidence intervals; statements other than the income statement and balance sheet; hosting.

## Success, as the scripts print it
The pooled number and the worst layout side by side (94.7% against 68.4%); the gate failing the held-out layout; no false alarm on the 24 loss and deficit statements; the known limit named (15 of 100 wrong statements tie out).

## Risks
One author wrote the data and the rules, so the numbers are a ceiling. The extractors are rules, so they do not show how a model fails. Twenty statements per layout is a small sample.

## Next
Run one real model's output through `score`; add a statement of cash flows and a scanned-input layout; weight fields by materiality; add intervals so a layout with few statements is not over-read.
