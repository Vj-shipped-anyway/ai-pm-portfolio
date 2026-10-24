# 🏷️ Tag Chargeback: who pays for the cloud bill when the tags are typed by hand

**I wanted to know how much of a bank's monthly cloud bill can be charged to the team that caused it when the only evidence is tags that people typed, and what a tag check cannot see. This is a command-line tool: it reads a billing export, a cost-center registry, an account map and a tag policy, allocates each line by rule, reports tag compliance, and lists the spend nobody owns. It exits 1 when too much is unowned.** It extends the idea of per-owner spend attribution from [07 InferenceLens](../07-inferencelens-inference-finops/), which attributes inference cost to features; the code and the data here are new.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 71-tag-chargeback/src && python3 tag_chargeback.py --demo
```

It reads a 14-line sample bill and prints:

```text
bill: example_bill.csv   14 lines   period 2026-03   net spend $11,490.00
tag compliance: 4 of 12 lines that need tags carry every required tag (2 exempt: zero cost or shared service)
  after alias and format repair: 5 of 12; by dollars 24.8% strict, 59.1% repaired
allocation by rule      lines             usd    share
  tag                       3       $1,900.00    16.5%
  tag_repaired              2       $4,300.00    37.4%
  shared_split              1       $1,000.00     8.7%
  inherit                   1         $140.00     1.2%
  account_default           1         $900.00     7.8%
  zero_cost                 1           $0.00     0.0%
  unallocated               5       $3,250.00    28.3%
unallocated by reason   lines             usd
  no_owner_found            2       $1,150.00
  closed_cost_center        1       $1,100.00
  conflicting_tags          1         $700.00
  unknown_cost_center       1         $300.00
largest unallocated resources
  res-demo-06                  $1,100.00  closed_cost_center
  res-demo-08                    $700.00  conflicting_tags
  res-demo-05                    $650.00  no_owner_found
  res-demo-10                    $500.00  no_owner_found
  res-demo-07                    $300.00  unknown_cost_center
chargeback        direct  inherited  acct default     shared          total
  CC-1001      $1,100.00      $0.00         $0.00    $151.93      $1,251.93
  CC-1002        $800.00      $0.00         $0.00    $110.50        $910.50
  CC-1003          $0.00      $0.00       $900.00    $124.31      $1,024.31
  CC-1004      $2,500.00    $140.00         $0.00    $364.64      $3,004.64
  CC-1005      $1,800.00      $0.00         $0.00    $248.62      $2,048.62
result: unallocated 28.3% of net spend, limit 10.0%: OVER
```

Standard library only, Python 3.9 or newer. For your own export:

```bash
python3 tag_chargeback.py report bill.csv --policy policy.json --cost-centers cost_centers.csv \
  --accounts accounts.csv --max-unallocated-pct 10 --chargeback-csv chargeback.csv --lines-csv lines.csv
```

It exits 1 above the limit, so a pipeline step can fail on it, and 2 for malformed input with one line on stderr. `--format github` prints annotations; bill text is escaped before it is echoed. That path has not run on GitHub. The column layout is in [`data/README.md`](./data/README.md).

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 1,284 billing lines, 12 accounts and 14 cost centers for one month; the script is named in brackets):

- 🟢 Chargeback by account puts $435,971.77 (55.8% of net spend) on the planted owner and $56,251.32 (7.2%) on another team, and parks $288,890.21 (37.0%) in a central pool (`step_01`)
- 🟢 Grouping by the tag as written gives 34 distinct values for a registry of 14, 20 of them not registry ids; $499,835.82 (64.0%) reaches the owner, $71,586.46 (9.2%) sits in buckets that are not cost centers and $180,467.03 (23.1%) is "Unallocated" (`step_02`)
- 🟢 Each rule adds correct spend: exact tag 64.0%, alias and format repair 75.5%, inherit from the same resource 78.2%, account default 83.6%, shared split 89.9% (`step_03`)
- 🟢 The full tool puts $702,526.86 (89.9%) on the planted owner, $37,705.69 (4.8%) on the wrong team and leaves $40,880.75 (5.2%) for a person; allocated plus unallocated equals the bill to the cent (`step_04`)
- 🟢 Tag compliance is 630 of 1244 lines written exactly (63.1% of dollars) and 694 of 1244 after alias and format repair (74.3%) (`step_04`)
- 🟢 Hard negatives handled correctly: 24 of 24 zero-cost untagged lines, 16 of 16 shared-service lines, 10 of 10 credit lines, 36 of 36 lines of resources tagged for their own team inside another team's account, 56 of 56 tags in another case or with spaces (`step_04`)

## What it still gets wrong

- 🟢 24 lines ($20,618.63) carry a valid tag for the wrong cost center. The tool charges all of them as tagged, and 20 of 24 pass the tag compliance check. This is the known limit left in on purpose (`step_03` prints it).
- 🟢 36 lines ($16,460.42) belong to an untagged resource of one team inside another team's dedicated account, so the account default charges the wrong team. The default placed $59,311.25 in all, and $16,668.39 (28.1%) of that belongs to another team (`step_03`). It runs last for that reason.
- 🟢 Coverage costs accuracy. The plain tag report charged $29,223.99 (3.7%) to the wrong cost center; the tool charges $37,705.69 (4.8%). It finds an owner for far more spend and is wrong about more of it (`step_02`, `step_04`).
- 🟢 24 lines use a key the policy does not list: $13,014.07 is recovered by the account default and $590.88 is left. 16 lines ($1,731.48) have the hyphen dropped from the value and are all left (`step_04`).
- 🟢 What is left for a person: conflicting_tags $12,362.31, no_owner_found $10,431.25, unknown_cost_center $9,320.29, closed_cost_center $8,766.90 (`step_04`). A present tag that is bad is refused, not overridden by the account default, so these need a human.
- **The data and the rules share an author.** I planted the defects and wrote the rules, so 89.9% is a ceiling for these rules on this mix, not a rate on a real bill. The mix itself is my guess. Four planted kinds are hard on purpose, and the rules miss all of them.
- Not covered: bills that span months, commitment amortisation, tags on resources that bill under another resource id, and any cost center hierarchy. Matching ignores case and spaces and nothing else.

## Modeled and hypothetical

- 🟡 The required tags (`cost-center`, `app`, `env`), the alias spellings, the 10.0% unallocated limit and the proportional split of shared services are my choices. Change them in `data/policy.json`; the split basis changes who pays the shared pool.
- 🔴 Whether a real bank's tag errors look like this mix is hypothetical. I have not run this on a real bill.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does chargeback by account give today? | `step_01_no_allocation.py` |
| 2 | What does a report grouped by the tag as written give? | `step_02_exact_tag_report.py` |
| 3 | What does each rule add, and what does the account default cost? | `step_03_deficiencies_exposed.py` |
| 4 | What does the whole tool do, including the hard cases? | `step_04_with_tool.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. `python3 _build_demo.py` rebuilds the page from `src/out/`.

## Aligned to

Nothing published. I did not read a standard or a regulation for this project, so I claim no alignment. It is a prototype on synthetic data and is not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real cloud account. A prototype on synthetic data, not a production case study. The [PRD](./PRD.md) holds the scope.

## Fork it

Swap `data/billing_export.csv`, `cost_centers.csv`, `accounts.csv` and `policy.json` for your own and keep the columns. Name your own tag keys and aliases in the policy. Without a truth file, steps 1 to 4 will not run; the `report` command does not need one.
