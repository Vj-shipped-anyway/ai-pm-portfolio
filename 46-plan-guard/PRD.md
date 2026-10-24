# PRD: plan-guard

## Problem
A Terraform plan can create a public bucket, open a database port to the internet or leave storage unencrypted, and every one of those is valid Terraform. `terraform validate` and the plan itself pass. The first time anyone looks is a scanner after apply, or a person reading plan text under time pressure.

## Who it is for
An engineer who owns the pipeline that applies infrastructure changes, and the reviewer who approves them.

## What it does
1. Reads the JSON form of a plan (`terraform show -json`) and keeps resources the plan creates or updates.
2. Applies ten rules chosen by the exact `type` field: public bucket ACL, public access block off, bucket policy open to everyone, world-open admin and database ports, unencrypted volume, database and file system, public database, plain HTTP listener.
3. Says "unverified" and sends the plan to review when a value is only known after apply.
4. Prints ALLOW, REVIEW or BLOCK, exits non-zero at a chosen level, and prints GitHub annotations on request.

## Out of scope
Other providers; module configuration; `planned_values`; sensitive values; anything about resources already deployed and untouched by the plan; joins between resources; any model call; hosting. A Marketplace listing is a later, separate step.

## Success, as the scripts print it
Risky plans blocked (33 of 42 on the planted set); plans that need a look sent to review (10 of 10); harmless plans blocked (0 of 34); people reading fewer plans than a text search would send (46 of 86 against 58); the known misses named (9 of 42 risky plans pass).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. No plan in the data came from a Terraform run, so field names and the handling of unset attributes are unverified against real output. Port lists and severities are my assumptions. A split CIDR, a permissive condition and an uncovered resource type pass.

## Next
Run it on one real plan the owner is allowed to share; add a cross-resource join for listeners and load balancers; publish the Action from its own repository.
