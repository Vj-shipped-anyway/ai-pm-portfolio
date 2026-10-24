# 🚧 plan-guard (plan JSON policy checks): a gate between `terraform plan` and apply

**I wanted to know how much cloud change risk is already visible in a Terraform plan before anything is applied, and what a text search, a parser and ten rules each stop. This is a command-line check and a staged GitHub Action: it reads the JSON form of a plan, applies ten rules to what the plan creates or updates, and prints ALLOW, REVIEW or BLOCK.** It uses the ALLOW, REVIEW, BLOCK gate shape and exit codes of [28 Tool Schema Drift](../28-tool-schema-drift/), on a different input.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 46-plan-guard/src && python3 plan_guard.py --demo
```

It prints:

```text
plan: example_plan.json   format_version 1.2   7 resource changes, 5 checked
  [block ] PG04 sg_world_admin_port         aws_security_group.bastion: ingress from 0.0.0.0/0 reaches admin port 22
  [block ] PG01 s3_public_acl               aws_s3_bucket.exports: acl is public-read, a canned ACL that opens the bucket beyond its owner
  [review] PG10 lb_plain_http_listener      aws_lb_listener.web: the listener accepts plain HTTP and its default action does not redirect to HTTPS
  [review] PG07 rds_unencrypted             aws_db_instance.reports: `storage_encrypted` is not known until apply, so database storage encryption cannot be checked in the plan
decision: BLOCK
```

Standard library only, Python 3.9 or newer. To check your own plan: `terraform show -json tfplan > plan.json`, then `python3 plan_guard.py check plan.json`. It exits 1 on BLOCK, so a CI step fails; `--fail-on review` also fails on REVIEW, and `--format github` prints annotations. Bad or malformed input exits 2 with one line on stderr.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 86 planted plans with 388 resource changes; the script is named in brackets):

- 🟢 No plan check: 0 of 86 plans stopped, and 42 of 86 apply a risky resource unchecked (`step_01`)
- 🟢 A text search with 8 patterns flags 58 of 86 plans; 23 of those 58 flags (39.7%) are harmless, and 17 of 52 risky plans are never flagged (`step_02`)
- 🟢 Rules that ignore each resource's action block 7 of 34 harmless plans, all deleted or unchanged resources; rules that treat a value unknown until apply as fine flag only 3 of 10 plans that need a look (`step_03`)
- 🟢 Parser, ten rules and unknown handling together: 33 of 42 risky plans blocked, each on the planted resource with the expected rule; 10 of 10 need-a-look plans sent to review; 0 of 34 harmless plans blocked; a person reads 46 of 86 plans where the text search sent 58 (`step_04`)

## What it still gets wrong

- 🟢 9 of 42 risky plans pass (`step_04` prints each one). Three split the open internet into two half-range CIDRs (PLAN-019, PLAN-042 and PLAN-059): the rule reads exact world CIDRs, and the two halves together are the whole internet. Three allow a wildcard principal behind a condition that matches everything (PLAN-008, PLAN-029 and PLAN-057): any condition passes. Three are a world-open queue policy (PLAN-041, PLAN-049 and PLAN-060): there is no rule for that resource type. The text search from step 2 flags 6 of these 9 (`step_03`).
- 🟢 3 of 34 harmless plans go to review (`step_04`). They are plain HTTP listeners on an internal load balancer. The rules look at one resource at a time and never join the listener to its load balancer.
- **The plans and the rules share an author.** I planted the changes and wrote the rules, so 33 of 42 shows the rules cover what I planted. The nine hard misses and the harmless look-alikes (a Deny policy for `*`, a deleted public bucket, port 443 open to the world, an unchanged risky resource) are in the data on purpose, so the score is not a clean sweep. Treat the result as a ceiling for these rules, not a rate on real plans, which I have not tested.
- 🔴 **No plan here came from a Terraform run.** `data/_generate.py` writes plans in the shape of `terraform show -json` as I know it: `resource_changes`, each with `type`, `address` and a `change` holding `actions`, `before`, `after` and `after_unknown`. I did not check them against real output. How a real provider reports an unset attribute (absent, null or unknown) varies, so the three forms are all in the data.
- 🟡 The parameters are my assumptions: admin ports 22 and 3389; database ports 1433, 1521, 3306, 5432, 6379 and 27017; three canned ACLs counted as public; an unset encryption flag read as off; one medium rule (a plain HTTP listener) and nine high. None is taken from a standard or a regulation. Account-wide defaults, such as default encryption set outside the plan, are not visible to the rules.
- Scope: AWS provider, 12 resource types behind ten rules. Single-instance RDS only, not clusters. A bucket ACL granted through `access_control_policy` is not read. Only `resource_changes` is read, not `configuration` or `planned_values`. A plan file can carry values you would not want in a log; the tool prints only the value it flags, but keep the file out of build artifacts.

## Use it in CI

[`action/`](./action/README.md) holds a staged GitHub Action and the steps to publish it from its own repository, which a Marketplace listing requires. It has not been published and has not run on GitHub. What is tested is the command it wraps (`tests/test_cli.py`; the folder holds 46 tests across the rules, the command line and the golden numbers).

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What reaches apply when nothing reads the plan? | `step_01_no_gate.py` |
| 2 | What does a text search for known-bad strings cost and miss? | `step_02_text_search.py` |
| 3 | Where does a parser fail when it ignores the action or the unknowns? | `step_03_deficiencies_exposed.py` |
| 4 | What do the ten rules catch with both handled? | `step_04_with_guard.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

The ten rules sit in the subject areas of the [Cloud Security Alliance Cloud Controls Matrix](https://cloudsecurityalliance.org/research/cloud-controls-matrix): Change Control and Configuration Management, Cryptography, Encryption and Key Management, Data Security and Privacy, Infrastructure and Virtualization Security, and Identity and Access Management. I read the matrix page on 2026-10-24: it names version 4.1, 197 control objectives and 17 domains, and shows no release date. I did not read the control text, so there is no control-by-control mapping.

I also tried to read the FFIEC statement on security in a cloud computing environment and the FFIEC IT Handbook booklet on architecture, infrastructure and operations on 2026-10-24. The site returned HTTP 403 to my fetch, so I cite neither. This is a prototype, aligned to the CSA matrix's subject areas and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real cloud account. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/plans.csv` and `data/plan_truth.csv` for your own exports and keep the columns, or skip the data and point `check` at a plan file from your pipeline. To add a rule, write a function that returns `("violation", text)` or `("unverified", text)` hits and add a row to `RULES` in `src/plan_guard.py`. Read the [PRD](./PRD.md) for the scope I held to.
