# Data for project 66

Synthetic. Produced by `_generate.py` with a fixed seed, so a rerun reproduces every file byte for byte. The vendors, model names, dates, prices and features are made up. Nothing here comes from a real vendor, bank, employer or model catalogue.

The truth about what each feature depends on is built first, from planted dependency kinds. The registry the tool reads is written from it afterwards, with gaps on purpose. The tool never opens the `truth_*` files (a test checks that); only the step scripts do, to score it.

| File | What it holds |
|---|---|
| `models.csv` | 17 model snapshots across 3 made-up vendors: family, notice date, retirement date, named successor, prices, and `base_model_id` for the 3 fine-tunes. 7 snapshots carry a retirement notice of their own |
| `aliases.csv` | 7 floating names (such as `vb-core-stable`) with the snapshot each was recorded as pointing to, and the date it was recorded |
| `features.csv` | 60 features: criticality, whether an evaluation set exists, and a sunset date for 4 of them |
| `usages.csv` | 80 registry rows: which model string each feature names, in which role (primary, fallback, judge), with monthly calls and average tokens |
| `truth_dependencies.csv` | 87 true dependencies, with the planted kind, the model really called, the retiring root if any, and whether the dependency is affected (42 are) |
| `truth_aliases.csv` | For each alias, the recorded target next to the target the vendor really uses. 2 differ |
| `policy.json` | The assumed lead times. Equal to `DEFAULT_POLICY` in `src/deprecation_impact.py`; a test checks it |
| `example_*.csv` | The 5-feature worked example behind `python3 deprecation_impact.py --demo` |

Planted primary kinds (60 features): exact id on a retiring model 7, the same with odd case or stray spaces 2, exact id on a live model 17, alias to a retiring model 6, alias to a live model 4, fine-tune built on a retiring base 6, fine-tune on a live base 2, bare family name that is really a retiring snapshot 3, bare family name that is really a live one 2, alias whose recorded target is wrong and recent 3, alias that is old and now points at a live model 2, unrecognised string that hides a retiring model 1, unrecognised string that does not 2, no model recorded for a feature and the feature uses a retiring model 2, no model recorded and it does not 1.

Planted fallbacks and judges: 19 fallbacks (6 on a retiring model, 1 on a model that retired before the as-of date, 8 on live models, 4 that no registry row records) and 8 judges (4 on a retiring model, 4 on live ones). Of the 60 features, 4 sunset: 2 before their model retires and 2 after.

Hard on purpose: the first half tests for a false alarm, the second half for a miss.
- Hard negatives: a neighbouring family whose name contains another's (`va-fast-lite` and `va-fast`), a floating alias that already points at a live snapshot, a fine-tune on a live base, a bare family name on a live snapshot, and features that sunset before their model retires.
- Hard cases the rules should miss: a fallback model that no registry row records (4), and an alias entry recorded 12 days before the as-of date that does not match what the vendor serves (3 features use it).

🟡 Assumptions, none of them measured: every price (USD per 1 million tokens, `models.csv`) is a made-up parameter, not a vendor price. `successor_input_token_factor` is an assumed difference in how the successor counts input tokens (1.04, 1.06 and 1.08 where it is not 1.00). The lead times in `policy.json` are assumed: 60, 30 and 14 days by criticality, plus 30 days when there is no evaluation set, 14 for a judge, 45 for a fine-tune that must be retrained, a 30-day margin for TIGHT, and 90 days after which a recorded alias counts as stale.

As-of date for every run: 2026-09-01. Run `python3 _generate.py` from this folder to rebuild the files.
