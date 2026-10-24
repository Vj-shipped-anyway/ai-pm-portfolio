# 🧭 Failover Scorecard (KillSwitch extension): which services have a tested way back

**I wanted to know, for every service in a bank's map, whether anyone has shown that it can come back from the loss of its primary region, as opposed to saying that a plan exists. This is a command-line scorecard: it reads a service map and a drill log and prints READY, or the single reason a service is not.** It extends the drill scorecard in [25 KillSwitch](../25-killswitch-ai-fallback-drills/), which judged fallback drills for one AI decision service on three questions: did it work, was it fast enough, was the rules version fresh. Here the unit is every service, and the rule adds the region and config version a drill ran against, the window for the tier, and the dependencies.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 65-failover-scorecard/src && python3 failover_scorecard.py --demo
```

It prints:

```text
as of 2026-10-24: 8 services, 2 ready, 1 not required, 5 not ready
  [FAILED    ] tier 1  S03  cards-auth-gateway: latest live region_failover drill on 2026-08-11 was fail: traffic switch not applied in the secondary region
  [DEPENDENCY] tier 1  S04  channels-mobile-bff: depends on cards-auth-gateway (S03), which is FAILED
  [UNTESTED  ] tier 1  S05  onboarding-identity-check: no live region_failover drill (on record, not counted: 1 tabletop)
  [SLOW      ] tier 2  S06  payments-fx-quotes: latest drill on 2026-05-12 recovered in 140 min against a target of 120
  [STALE     ] tier 2  S07  cards-statement-batch: latest passing drill is 436 days old, the window for tier 2 is 365
by domain, ready of all: cards 0 of 2, channels 0 of 1, data-platform 0 of 1, onboarding 0 of 1, payments 2 of 3
decision: NOT READY (3 of 5 tier-1 services have no tested way back)
```

Standard library only, Python 3.9 or newer. To score your own files: `python3 failover_scorecard.py check services.csv drills.csv --as-of 2026-10-24`. The date is an argument because the tool never reads the clock. It exits 1 when a tier-1 service has no tested way back (`--fail-on any` widens that to every service, `never` only prints), 2 on malformed input or when the map has no tier-1 service and so nothing was checked. `--format github` prints annotations.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 48 services and 54 drill rows; the script is named in brackets):

- 🟢 Status quo: owners state a documented failover plan for 42 of 48 services, 16 of those 42 would recover, and 37 of 48 services have a live drill on record (`step_01`)
- 🟢 Green when the latest drill passed: 36 of 48 services are green, 20 of those 36 would not recover (10 of 15 at tier 1), and 4 of the 12 reds are owner-accepted gaps, not failures (`step_02`)
- 🟢 Take one part of the rule out and services slip through: without the region and config check 8 of 28 not-ready services pass (5 more than the full rule), without the window 6 of 28, without the dependency check 6 of 28, without the recovery-time check 5 of 28, without the live-drill check 5 of 28; the full rule lets 3 of 28 through (`step_03`)
- 🟢 The full scorecard flags 25 of 28 services that would not recover and 0 of 16 that would, with 3 fixed after a failed drill and 3 with an old drill still inside its window among the 16; it keeps 4 of 4 accepted gaps apart from real ones; 45 of 48 statuses match the planted truth (`step_04`)
- 🟢 At tier 1, 7 of 18 services have a tested way back, and 2 of those 7 would not recover (`step_04`)
- 🟡 The windows are my assumption, not a value from any rule: with the tier-1 window at 90, 180 and 365 days, 6, 7 and 8 of the 18 tier-1 services are READY (`step_04`)

## What it still gets wrong

- 🟢 Three services score READY and would not recover (`step_03` and `step_04` print each one; two are tier 1). Each has a clean drill and clean declared dependencies, and needs a service the map does not list. The rule follows only the edges it is given. A missing edge is invisible to it, and so is a service map that is out of date.
- **The planted set and the rule share an author.** I planted the stories and wrote the rule, so 25 of 28 shows the rule covers what I planted. Ten services are hard negatives (a drill that failed once and then passed, a passing drill that is old but inside its window, an accepted gap) and three are the hard misses above. Treat the result as a ceiling for this rule, not a rate on a real service map, which I have not tested.
- **A drill row is taken at its word.** The rule cannot tell a rehearsed, announced drill from a real one, or whether the clock on `minutes_to_recover` started when the outage started or when someone declared it.
- **The parts overlap.** Taking out the live-drill check lets in the 2 tabletop-only services, but the 2 services drilled only inside one availability zone are still caught, by the region check. That is the rule behaving as designed, and it means the step 3 counts are not additive.
- One primary and one secondary region per service; no recovery-point or data-loss target, no partial failover, no capacity in the secondary region. `depends_on` lists hard dependencies only. Only the latest counted drill is read.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What do we know when each owner says there is a plan? | `step_01_self_reported.py` |
| 2 | What does "the latest drill passed" get wrong? | `step_02_last_drill_passed.py` |
| 3 | Which part of the rule catches what, and what does no part catch? | `step_03_deficiencies_exposed.py` |
| 4 | What does the whole scorecard flag, and what does it leave? | `step_04_with_scorecard.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. `src/_build_demo.py` builds `demo.html` from what step 4 writes to `src/out/`.

## Aligned to

The Basel Committee's [Principles for operational resilience](https://www.bis.org/bcbs/publ/d516.htm), published 31 March 2021 (page read 2026-10-24). That page says the principles aim to improve banks' ability to withstand events such as technology failures and cyber incidents. My fetch tool returned only that page and not the 12-page text, so I do not quote or cite any individual principle, and I did not read any Financial Stability Board text, so I cite none. No window, target or tier in this project comes from a published text; each is marked as my assumption in [`data/README.md`](./data/README.md). This is a prototype, aligned to the general aim of showing that recovery works and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real bank, and no real company is a subject. A prototype on synthetic data, not a production case study. The extension of 25 is in the idea and the three drill questions; no code or data is shared with that folder.

## Fork it

Replace `data/services.csv` and `data/drills.csv` with exports from your own inventory and drill register and keep the columns (see [`data/README.md`](./data/README.md)). Change the windows in `default_policy()` in `src/failover_scorecard.py`. Read the [PRD](./PRD.md) for the scope I held to.
