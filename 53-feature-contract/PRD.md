# PRD: Feature Contract gate

## Problem
A model reads fields that another team owns. When one of them changes (a column renamed, a ratio sent as a percent, a null rate that jumps) the pipeline still runs and the model still scores. The first sign is a score that moved.

## Who it is for
An engineer who owns a feature table behind a model, and the owner of the model who wants the inputs stated in one file.

## What it does
1. Reads a contract: per field a type, a range or allowed values, and a null allowance; per file a tolerance for isolated bad rows and a policy for columns it does not list.
2. Checks one delivery of data (CSV, or JSON lines with their JSON types) against it.
3. Prints PASS, WARN or FAIL with the share of rows behind each finding, and exits non-zero at a chosen level, with GitHub annotations on request.

## Out of scope
Distribution drift and any shift inside the declared range; cross-field rules; dates and patterns; row-count and freshness checks; drafting a contract from data; any model call; hosting. A Marketplace listing is a later, separate step.

## Success, as the scripts print it
Bad batches stopped (37 of 47 on the planted set); harmless ones blocked (0 of 43); the known misses named (10 of 47 pass: zero-filled nulls, unit changes that stay in range, and a cents change on a field with a wide range).

## Risks
The planted set and the contracts share an author, so the numbers are a ceiling. The 2.0% tolerance and the 5.0% null allowance are assumptions that decide which isolated problems count as harmless. A contract written by hand drifts from the feed it describes.

## Next
Run it on one real feature table the owner is allowed to share; add a command that drafts a contract from a reference batch; pair it with a distribution monitor for the changes a range cannot see; publish the Action from its own repository.
