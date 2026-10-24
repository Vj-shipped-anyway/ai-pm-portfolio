# Data for project 55

Synthetic. Produced by `_generate.py` with a fixed seed (`SEED = 20261024`), so a rerun reproduces every file byte for byte. Nothing here comes from a real bank, vendor, person or evidence file. Unit names, titles and document references are invented.

| File | What it holds |
|---|---|
| `use_cases.csv` | 150 AI use cases as the sponsor filled them in, with `declared_tier`. The columns are the ones `challenge_pack.py` reads |
| `evidence.csv` | 1342 evidence rows, at most one per use case and item: `ref`, `prepared_by_unit`, `covers_version`, `evidence_date`, `reaffirmed_date` |
| `truth_tier.csv` | The hidden true tier, vendor model and data class per use case. Used only to score |
| `truth_evidence.csv` | One row per owed item (and per item filed though not owed): `owed` and the planted status. Used only to score |
| `plan_items.csv`, `plan_tiers.csv` | The tier-to-test-plan table the generator reads. A test checks that it equals the table in `src/challenge_pack.py` |
| `example_use_cases.csv`, `example_evidence.csv` | The six hand-written use cases behind `python3 challenge_pack.py --demo`, judged as of 2026-10-01 |

## How the truth is made

Each use case gets hidden true attributes, and a true tier from the rubric of project 11 (points on six inputs; tier = min(4, 1 + points // 4)). The form then misstates some of them, and the sponsor shades the declared tier. The sponsor files evidence for the items they think they owe; each filed item gets a planted status. A missing item is simply not filed. The truth is the planted status, not the output of the rules in `src/`.

The parameters below are mine, not observations:

| What | Parameter |
|---|---|
| Vendor dependency left off the form | 25% of vendor-dependent use cases |
| Data class written one level low | 20% |
| Declared tier one below the rubric on the form as written | 20%; one above: 3% |
| An item the sponsor knows they owe is filed | 93%; an item owed only under the true tier: 20%; an item not owed: 15% |
| Planted status of a filed item | ok 62%, reaffirmed 12%, boundary 3%, stale 8%, wrong version 6%, not independent 6% (redrawn as ok where the item needs no outside preparer), hollow 3% |

Planted statuses on this seed (printed by `python3 _generate.py`): ok 829, reaffirmed 154, boundary 34, stale 92, wrong version 71, not independent 26, hollow 32, missing 248, and 104 items filed that the use case does not owe.

- **reaffirmed**: the evidence date is older than the window and a reaffirmation inside it covers the same version. A date-only rule flags it by mistake.
- **boundary**: dated exactly one window before the as-of date. Stale means strictly older than the window, so it is fine.
- **hollow**: on time, current, the right version, prepared outside the developer's unit, and empty of content. No field shows it. It is the known miss.
- First-line items (those that need no outside preparer) are prepared by the developer's own unit about four times in five. A rule that flags any evidence prepared inside the developer's unit flags all of them by mistake.

## Assumptions (🟡)

The tier-to-test-plan table is a modeled assumption. Item CH01 to CH13 and the overlays V01, V02 and G01 are placed at tiers by me. Evidence windows are 36, 24, 12 and 12 months for tiers 1 to 4. The items that need a preparer outside the developer's unit are CH07, CH08, CH10, CH11, CH12, CH13, V02 and G01. A vendor overlay applies to `self_hosted` as well as `vendor_api`, because a model you host but did not build is still a third-party product. None of these is taken from SR 26-2, which sets no tiers, windows or item lists.

## What this data does not do

It does not model real sponsor behavior, real evidence quality or real review effort. `model_type`, `decision_autonomy`, `regulatory_scope` and `financial_exposure_band` are never misstated on the form, so the check has no way to be wrong about them here. Evidence rows never contradict each other and every date is valid. A real export would be messier.
