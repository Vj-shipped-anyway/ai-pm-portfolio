# Sample Data — DealSentry Walkthrough

Four synthetic CSVs that drive the four-step walkthrough and the Streamlit app. These mirror the shape of a real CRE underwriting verification stack: a source-of-truth comp database, a source-of-truth submarket-stats feed (with quarterly versioning so staleness can be detected), six AI-drafted memos that exercise the named failure modes, and the deficiency-class taxonomy DealSentry checks against.

All data is synthetic. Property names, addresses, and dollar figures are invented. The submarket boundaries, asset classes, and price/cap-rate bands are calibrated against publicly published [CoStar](https://www.costar.com/), [Reonomy](https://www.reonomy.com/), [Cherre](https://cherre.com/), and [NCREIF](https://www.ncreif.org/) industry research as of late 2025.

## Files

| File | What it is |
| --- | --- |
| `sot_comps.csv` | 40 synthetic source-of-truth comp transactions across LA, NYC, Chicago, Dallas, Phoenix, Atlanta, Miami, Bellevue. Mix of industrial / office / multifamily / retail / medical office. Each row carries a `source_feed` pointer (CoStar / Reonomy / Cherre). |
| `sot_stats.csv` | Submarket vacancy / asking rent / cap-rate stats per (submarket, asset_class, quarter, feed). Quarterly versioning means the Q3 vs Q4 staleness check is a real comparison, not a flag. |
| `sample_memos.csv` | 6 synthetic AI-drafted memos covering the failure-mode mix: clean industrial, clean multifamily, T-12 math drift office, fabricated-comp retail, stale-stat medical office, multi-fault industrial. |
| `deficiency_classes.csv` | The 6 named deficiency classes DealSentry checks for, with definitions and example failure patterns. |

## The 6 deficiency classes

A CRE underwriting memo typically has 40-80 individually-verifiable claims (comp identity, comp economics, T-12 line items, submarket stats, IRR assumptions). DealSentry focuses on six classes because they are the ones that show up at IC as bad bids:

1. **`comp_citation_fabrication`** — comp doesn't exist in any SOT feed.
2. **`t12_noi_rollforward_error`** — arithmetic error in trailing-12-month NOI sum.
3. **`submarket_stat_staleness`** — stat from a prior quarter presented as current.
4. **`cap_rate_computational_error`** — stated cap rate doesn't match NOI / value math.
5. **`occupancy_rate_discrepancy`** — stated occupancy doesn't reconcile with rent roll.
6. **`exit_cap_assumption_mismatch`** — Year-5 exit cap inconsistent with going-in cap.

These six map directly to what an IC chair would flag in a senior-review pass, if the IC chair had time to read every page of every memo. DealSentry runs that pass deterministically.

## The 6 sample memos

| Memo | Asset | Failure mode designed in |
| --- | --- | --- |
| `MEMO_01` Atlanta SE Distribution Hub | 180k sf last-mile industrial | Clean — all 5 comps in SOT, T-12 reconciles, occupancy reconciles, exit-cap spread = +45 bps. Baseline pass. |
| `MEMO_02` Phoenix North Residences | 240-unit garden multifamily | Clean — 6 comps verified, T-12 with vacancy adjustment shown, occupancy reconciles. Baseline pass. |
| `MEMO_03` Dallas Uptown Tower | 320k sf Class-A office | T-12 math drift — sum of 12 monthly NOI rows is $5.10M; memo states $5.16M. $60K positive drift. |
| `MEMO_04` Brickell Crossing Retail | 92k sf grocery-anchored retail | Fabricated comps — Comp 4 (Pinecrest Pavilion) and Comp 6 (South Bay Galleria) do not exist in SOT. Exit cap = going-in cap (flat). |
| `MEMO_05` Bellevue MOB Plaza | 85k sf medical office | Stale submarket stat — memo cites 4.2% vacancy / $49.50 rent, which is 2024-Q3 CoStar; current Q4 2025 is 5.2% / $52.00. Also duplicate comp citation. |
| `MEMO_06` Chicago O'Hare Last-Mile | 410k sf last-mile industrial | Multi-fault — Comp 5 fabricated, cap-rate math wrong by 50 bps (memo says 5.50%, recompute = 6.00%), 4.5-point occupancy discrepancy, exit cap = going-in cap (flat). |

## How this maps to the walkthrough

- `step_01_face_value_trust.py` — does no verification. Reports whatever the memo says. Models the baseline (analyst skim only).
- `step_02_analyst_spotcheck.py` — analyst manually spot-checks 10% of comps. Shows which deficiencies slip through statistically.
- `step_03_deficiencies_exposed.py` — runs the deficiency classifier across all 6 memos and produces the failure table that anchors the README's deficiency narrative.
- `step_04_with_dealsentry.py` — runs the full DealSentry pipeline: comp existence against `sot_comps.csv`, T-12 arithmetic symbolic re-run, submarket-stat cross-feed against `sot_stats.csv`, cap-rate math check, occupancy reconciliation, exit-cap consistency. Prints per-memo findings and an aggregate verdict.

## Notes on synthetic SOT coverage

In production DealSentry would call live CoStar Real Estate Manager / Reonomy Properties / Cherre Property APIs. The 40-row SOT in this repo simulates the coverage shape — every submarket that appears in the memos has at least 3 SOT comps, and the fabricated comps in `MEMO_04` and `MEMO_06` are intentionally absent from the SOT so the comp-existence check has a real positive and a real negative on every memo.
