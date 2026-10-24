# PRD: tag-chargeback (cost allocation check)

## Problem
A cloud bill arrives by account and by service. A bank wants it by cost center, and the only evidence of who owns a line is a tag someone typed. Some tags are missing, some are misspelled, some name a cost center that no longer exists, and some are valid and wrong. A report that groups by the tag as written looks complete and leaves money with no one to bill.

## Who it is for
The person in cloud finance who produces the monthly chargeback, and the platform engineer who is asked to fix the tags.

## What it does
1. Reads a billing export, a cost-center registry, an account map and a tag policy.
2. Allocates each line by rule: tag, shared-service split, inherit from the same resource, account default. A tag that is present and bad is refused, not overridden.
3. Reports tag compliance twice, strict and after alias and format repair.
4. Prints the unallocated spend by reason and the largest unallocated resources, and exits 1 above a limit.

## Out of scope
Fetching a real bill; amortizing commitments; forecasting; choosing a shared-cost basis for the user; any model call; hosting.

## Success, as the scripts print it
Spend landing on the planted owner (89.9% against 64.0% for a plain tag report); allocated plus unallocated equal to the bill to the cent; hard negatives not refused or flagged; the known misses named with their dollars.

## Risks
The planted data and the rules share an author, so the numbers are a ceiling. The account default is the least reliable rule and is last for that reason. Wrong dollars rise when coverage rises; the report says so.

## Next
Run it on one real export the owner may share; add a successor field so a closed cost center can suggest its replacement; let the shared-cost basis be chosen in the policy.
