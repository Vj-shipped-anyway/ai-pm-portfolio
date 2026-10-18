# Sample Data — TierGate walkthrough

Five CSVs drive the four steps. Everything is synthetic, seeded (`SEED = 20261011` in `_generate.py`) and reproducible: run `python3 _generate.py` and you get the same files byte for byte, because the generator uses only the Python standard library and a single seeded `random.Random`. **No real bank, vendor, person or intake submission appears anywhere.** Names of datasets, business units and use cases are invented.

**The reference tier is true by construction.** It is the written rubric below, applied to the hidden true attributes of each submission. So every accuracy number in the walkthrough measures how well a method recovers that reference tier from noisy inputs. It does not measure how real banks tier AI use cases, and the error rates below are generator parameters I chose, not observations.

---

## The rubric (arithmetic, written down)

Points on the six true attributes, summed:

| Attribute | Points |
| --- | --- |
| `customer_facing` | yes 2 · no 0 |
| `decision_autonomy` | advisory 0 · assisted 1 · automated 3 |
| `data_class` | public 0 · internal 1 · confidential 2 · restricted 3 |
| `vendor_model` | none 0 · self_hosted 1 · vendor_api 2 |
| `regulatory_scope` | none 0 · privacy 1 · aml 2 · udaap 2 · fair_lending 3 |
| `financial_exposure_band` | lt_1m 0 · 1m_10m 1 · 10m_50m 2 · gt_50m 3 |

**Tier = min(4, 1 + points // 4).** Points 0-3 are tier 1, 4-7 tier 2, 8-11 tier 3, 12 and above tier 4. The maximum is 16.

`step_04_with_tiergate.py` prints a worked example (one submission, three columns: the sponsor's form, what TierGate checked, the true value) and checks that this rubric reproduces the committed `reference_tier` on all 150 rows.

Tier labels are an internal four-step scale. They are not the EU AI Act's risk categories. Mapping them to those categories is a design item that needs legal review.

---

## Files

| File | Rows | What it is |
| --- | --- | --- |
| `intake_submissions.csv` | 150 | What the sponsor filled in, plus the hidden truth and the reference tier |
| `data_catalog.csv` | 34 | Dataset name to the class the catalog records, plus the true class |
| `vendor_registry.csv` | 62 | Use case to vendor model, partial coverage |
| `evidence_checklist.csv` | 25 | Evidence required per tier, cumulative, long form |
| `evidence_on_file.csv` | 964 | Which evidence items each submission has attached |
| `_generate.py` | | The seeded generator for all five |

### `intake_submissions.csv`

| Column | Visible to TierGate? | What it is |
| --- | --- | --- |
| `use_case_id` | yes | `UC-001` to `UC-150`, in submission order |
| `submitted_date` | queue only | Business days from 2026-01-05 to 2026-05-22 (20 weeks, four of them busier) |
| `sponsor_unit`, `title`, `description` | yes | Free text. Duplicates are reworded and come from a different unit |
| `dataset_name` | yes | The dataset the sponsor says the use case reads |
| `customer_facing` | yes | `yes`, `no`, `unsure` or blank |
| `decision_autonomy` | yes | `advisory`, `assisted`, `automated` |
| `data_class` | yes | `public`, `internal`, `confidential`, `restricted` (as the sponsor declared it) |
| `vendor_model` | yes | `none`, `self_hosted`, `vendor_api` (as the sponsor declared it) |
| `regulatory_scope` | yes | `none`, `privacy`, `aml`, `udaap`, `fair_lending` |
| `financial_exposure_band` | yes | `lt_1m`, `1m_10m`, `10m_50m`, `gt_50m` |
| `self_declared_tier` | yes | 1 to 4, what the sponsor wrote on the form |
| `true_*` (six columns) | **no** | The hidden true attributes |
| `reference_score`, `reference_tier` | **no** | The rubric on the true attributes |
| `duplicate_group` | **no** | `DG-01` to `DG-08` for members of a duplicate group, blank otherwise |

TierGate's `recompute()` receives only the visible form columns, the catalog's recorded class and the vendor registry. The hidden columns are read afterwards, to score the result. The same applies to `true_class` and `catalog_status` in `data_catalog.csv`.

### Injected error: how the form deviates from the truth

These are the generator's documented parameters. The last column is the realized count on this seed, printed by `python3 _generate.py`.

| What goes wrong on the form | Parameter | Realized on this seed |
| --- | --- | --- |
| Data class understated by one level | 10% of true internal, 30% of true confidential, 30% of true restricted | 40 of 150 forms below the true class |
| Vendor dependency omitted (form says `none`) | 35% of true `vendor_api`, 20% of true `self_hosted` | 31 of 107 vendor-dependent use cases |
| Customer-facing answer wrong, blank or unsure | true yes: 22% `no`, 8% `unsure`, 4% blank. True no: 3% `yes`, 5% `unsure`, 3% blank | 27 of 150 |
| Declared tier shaded from the sponsor's own rubric result | down one tier 18% (above tier 1), up one tier 3% (below tier 4) | 14 down, 3 up |

The sponsor's own rubric result is the rubric applied to the form answers as written (a blank or `unsure` customer-facing answer scores 0). `decision_autonomy`, `regulatory_scope` and `financial_exposure_band` are copied from the truth with no injected error, so TierGate has no way to be wrong about them here and no second source for them.

### `data_catalog.csv`

| Column | Visible to TierGate? | What it is |
| --- | --- | --- |
| `dataset_name` | yes | `d_` plus a descriptive name |
| `steward_unit` | yes | Owning unit |
| `catalog_class` | yes | The class the catalog records |
| `true_class` | no | The true class |
| `catalog_status` | no | `current`, `stale_understated` or `stale_overstated` |

34 datasets. Four entries are stale: 3 understate the true class and 1 overstates it. A use case's true data class is the true class of its dataset. Where the form also understates, the form and the catalog agree on the wrong answer. That is the known limit.

### `vendor_registry.csv`

`use_case_id`, `vendor_model`, `source`. It lists 62 of the 107 vendor-dependent use cases (a 65% coverage parameter) and is accurate wherever it has an entry. No vendor names appear; the registry only records the model type.

### `evidence_checklist.csv` and `evidence_on_file.csv`

Required evidence per tier, cumulative (a higher tier owes everything below it):

| Tier | Items required | Added at this tier | Interlock |
| --- | --- | --- | --- |
| 1 | 2 | E01 use-case card with named line-1 owner; E02 data-source attestation | |
| 2 | 4 | E03 evaluation plan and results summary; E04 privacy and data-handling review | 04 EvalForge (E03) |
| 3 | 8 | E05 independent validation with effective challenge; E06 human review design for the tier; E07 decision logging and lineage plan; E08 vendor and third-party due diligence | 08 OversightOps (E06), 09 LineageLog (E07) |
| 4 | 11 | E09 regulatory-scope legal review; E10 fallback and exit plan; E11 CRO sign-off | |

`evidence_on_file.csv` has one row per (submission, item) attached. A sponsor attaches each item on the checklist of the tier they declared with probability 95%, and each item from a higher tier with probability 25%. That is a simple behavior model, not an observation.

### Duplicates

Eight groups: seven pairs and one triple, 17 submissions and 10 true pairs. A duplicate shares its original's true attributes and dataset, comes from a different sponsor unit, is submitted 3 to 30 business days later, and has its own independent form answers, so the two forms can disagree. 30% of duplicates use a different phrasing of the description, and every matching synonym is swapped with probability 65%.

### Description text

Descriptions come from 38 archetypes with three phrasings each. Whether a description mentions customers is a generator parameter (85% for a customer-facing case, 60% for an internal case whose subject is customer material, 4% otherwise). The keyword check in TierGate therefore measures how it behaves on this synthetic text, not on real text.

---

## What this data does not do

- It does not model real sponsor behavior, real catalogs, real registries or real review effort. Every rate above is a parameter.
- It does not inject error into autonomy, regulatory scope or exposure. A real form would misstate those too.
- The vendor registry is never wrong where it has an entry, and the catalog is never silent about a dataset. Both are kinder than a real estate would be.
- Duplicate linking is scored on 10 true pairs. That is a small set.

## How the files map to the steps

| Step | Reads |
| --- | --- |
| 1 | `intake_submissions.csv` (arrival dates, and the reference tier to label who is high risk) |
| 2 | `intake_submissions.csv`, `evidence_checklist.csv`, `evidence_on_file.csv` |
| 3 | the above plus `data_catalog.csv` and `vendor_registry.csv` |
| 4 | all five. Form columns, `catalog_class` and the registry feed `recompute()`; everything hidden is used only to score |
