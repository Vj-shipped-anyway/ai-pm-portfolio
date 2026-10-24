# 🧭 Concentration Register (VendorLens extension): which critical services sit on one cloud provider or one region

**I wanted to know how much of the critical estate goes dark when one cloud provider or one region fails, and I did not trust a count of services per provider to tell me. This is a command-line tool that reads a register of services and the dependencies between them, takes each provider and each region out in turn, and prints how many critical services are left standing, next to what a direct count would have said.** It extends the upstream-provider view in [18 VendorLens](../18-vendorlens-ai-vendor-due-diligence/): that project counts critical use cases per model provider; this one follows hard dependencies and standbys, and scores the answer against a world whose truth is known.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 45-concentration-register/src && python3 concentration_register.py --demo
```

It prints:

```text
register: 10 services (7 critical), 3 providers, 5 regions; 7 hard and 2 soft dependencies
critical services lost per outage scenario (limit 30%)
  scenario     direct view      with dependencies and failover
  P:CP-2       1 of 7 (14.3%)   6 of 7 (85.7%)  OVER
  R:CP-2/R1    1 of 7 (14.3%)   6 of 7 (85.7%)  OVER
  P:CP-1       3 of 7 (42.9%)   2 of 7 (28.6%)
  R:CP-1/R1    2 of 7 (28.6%)   2 of 7 (28.6%)
  P:CP-3       2 of 7 (28.6%)   1 of 7 (14.3%)
  R:CP-3/R1    1 of 7 (14.3%)   1 of 7 (14.3%)
  (2 more scenarios; --format json lists all)
unplaced: 1 critical service with no provider or region (S-05 fraud screening engine); the figures above are a lower bound
standby in the same provider and region as the primary: 1 service (S-06 statement delivery batch)
decision: OVER LIMIT (2 of 8 scenarios lose more than 30% of critical services)
```

The example is ten hand-written services. `CP-2` hosts one critical service, so a count says 14.3%. That service is the identity platform, and the others hard-depend on it, so a `CP-2` outage costs 6 of 7. `CP-1` looks worst by count (42.9%) and is fine once its standbys are counted (28.6%).

Standard library only, Python 3.9 or newer. To check your own files: `python3 concentration_register.py check services.csv --deps dependencies.csv --limit-pct 30`. It exits 1 when a scenario loses more than the limit, 2 on malformed input; `--format json` prints every scenario. `--demo` always exits 0.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 64 services, 25 of them critical, 4 invented providers, 12 outage scenarios; the script is named in brackets):

- 🟢 The register lists a provider and region for 55 of 64 services, lists 96 hard dependencies, and measures 0 of 12 outage scenarios; in the generator's world 4 of 12 lose more than 30% of the critical services (`step_01`)
- 🟢 A direct share by provider flags 1 of 12 scenarios (`P:CP-1`, 36.0%) and so catches 1 of the 4 that truly cross the limit; it counts 44 critical (scenario, service) pairs, 31 of them real and 13 that survive on a standby (`step_02`)
- 🟢 The misses are dependency-driven: `P:CP-3` shows 12.0% by count and loses 52.0%; `P:CP-2` shows 20.0% and loses 40.0%; `R:CP-1/R1` shows 24.0% and loses 52.0% (`step_03`)
- 🟢 Walking the dependencies but counting a soft one as hard flags 5 of 12 scenarios, 1 of them not over the limit in truth, and counts 17 pairs that are not lost (`step_03`)
- 🟢 Following hard dependencies and standbys flags 4 of the 4 scenarios that truly cross 30%, with 0 false flags, and reports 64 of the 74 lost pairs, all of them real (`step_04`)

**Assumed, not measured:**

- 🟡 The 30% limit is mine. The guidance I read names no number (see Aligned to), so every flag in this README depends on that choice. `step_04` reruns it from 20% to 50%.

**Not tested:**

- 🔴 A real environment will have far more unlisted dependencies than the 6 planted here, and its placement data will be wrong in ways this generator does not draw. I have not run the tool on a real register.

## What it still gets wrong

- 🟢 It understates and never overstates: 10 of the 74 lost pairs are missed (recall 86.5%). Supplying what the register lacks, one thing at a time, takes the misses from 10 to 4 (true placement of the 3 critical services with no placement), to 2 (the 6 unlisted hard dependencies), to 0 (the 1 standby that does not take over). The last step landing on 0 is also a check that the generator's loss and the tool's loss agree where the register is complete (`step_04`).
- 🟢 The understatement can move a decision. `P:CP-1` is 48.0% by the tool against 60.0% in truth, and `R:CP-1/R1` is 40.0% against 52.0%. At a 40% limit 3 scenarios truly cross it and the tool flags 2; at a 50% limit it flags 1 of 3 (`step_04`).
- **Same author.** I wrote the world and the rules. The two propagation routines are separate code, but they share the idea, so agreement where the register is complete is by construction. The numbers are a ceiling for these rules on data I drew, not a rate on a real bank.
- **The failover result rests on one service.** The generator makes a warm standby fail to take over with probability 0.30; this draw produced 1 among 15 and I kept it (see [data/README.md](./data/README.md)).
- The model is binary and static: a service is up or lost. It has no capacity check on a standby, no recovery time, no shared control plane between regions of one provider, and nothing outside the register (a shared DNS or payment network is invisible unless it is a row). Provider and region names are compared exactly, so `CP-1` and `cp-1` count as two providers.
- A region outage is a whole region of one provider. Partial failures, a single availability zone and a provider-wide control-plane event are not modeled.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does a register hold when nothing adds it up? | `step_01_status_quo.py` |
| 2 | What does a count of critical services per provider say? | `step_02_direct_share.py` |
| 3 | Where does that count fail, and what is left in on purpose? | `step_03_deficiencies_exposed.py` |
| 4 | What do hard dependencies and standbys add, and what do they still miss? | `step_04_with_register_model.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. `python3 _build_demo.py` rebuilds `demo.html` from what step 4 writes to `src/out/`.

## Aligned to

The interagency [Guidance on Third-Party Relationships: Risk Management](https://www.federalreserve.gov/supervisionreg/srletters/SR2304.htm) (SR 23-4, issued 7 June 2023). I read the text as published in the Federal Register on 9 June 2023 ([govinfo copy](https://www.govinfo.gov/content/pkg/FR-2023-06-09/html/2023-12340.htm)) on 24 October 2026, through a fetch tool that answers questions about the page, so I checked only the passages this project leans on, not the whole document. Among the factors a bank weighs, the guidance lists dependence on a single provider for several activities (under operational resilience and under reliance on subcontractors) and the geographic location of subcontractors. It names no numeric concentration limit, which is why the limit here is an assumption. The Fed's PDF of the guidance is a scan that the fetch could not read. I did not read the 2021 proposal, so I do not cite it. This is a prototype, aligned to that guidance and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, bank or real cloud provider; provider codes are invented. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/services.csv` and `data/dependencies.csv` for your own exports and keep the columns (listed in the header of [`src/concentration_register.py`](./src/concentration_register.py)), or write the two files by hand and run `check`. Read the [PRD](./PRD.md) for the scope I held to.
