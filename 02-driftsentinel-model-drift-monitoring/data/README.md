# Sample Data — DriftSentinel walkthrough

Four CSVs that drive Steps 1 through 4 of the walkthrough. Everything here is synthetic, seeded, and reproducible. No customer data. No PII. The shapes are modeled on the general layout of a Tier-1 BFSI model fleet, not on any bank's data.

---

## `models.csv` — the production fleet (8 rows)

The fleet I model in the walkthrough. Eight production models across credit, fraud, AML, and one customer-facing GenAI. Every Tier-1 ML/AI org has some version of this list.

| Field | Description |
| --- | --- |
| `model_id` | Stable identifier used in `inference_logs.csv` and `drift_events.csv`. |
| `name` | Human-readable label. |
| `family` | `credit`, `fraud`, `aml`, or `genai`. |
| `tier` | 1 or 2 — MRM tier, drives monitoring cadence and SLA. |
| `owner` | Line-1 owning team. |
| `deployed_date` | When the current version went to production. |
| `last_attested` | Most recent quarterly Word-doc attestation date (Step 1 world). |
| `vendor` | `internal` for in-house models; `anthropic` / `azure_openai` / `bedrock` for hosted. |
| `snapshot_id` | Vendor model snapshot ID at deploy time. The whole point of `vendor_snapshots.csv` is tracking when this changes silently. |

Composition: 4 credit (2 Tier-1, 2 Tier-2), 2 fraud (both Tier-1), 1 AML (Tier-1), 1 GenAI Q&A (Tier-1, Anthropic). By count that is a 50/25/12.5/12.5 split (4/2/1/1 of 8), biased toward credit because that's where the money is.

---

## `inference_logs.csv` — 90 days of synthetic production traffic (~18k rows)

Daily inference rows for every model in the fleet. Schema is intentionally narrow — production tables are 60+ columns, this is a three-feature reduction (`feature_dti`, `feature_fico`, `feature_ltv`) so the walkthrough scripts stay readable.

| Field | Description |
| --- | --- |
| `date` | Calendar date of the inference batch. |
| `model_id` | Foreign key to `models.csv`. |
| `feature_dti` | Primary input for credit models; repurposed as `velocity` (fraud), `refusal` (GenAI). Empty for `credit_loss_v2`, `fraud_ach_v3` and `aml_sar_v2`. Production tables would have all features named separately. |
| `feature_fico` | FICO for credit; transaction amount for fraud; response length for GenAI. Empty for `aml_sar_v2`. |
| `feature_ltv` | LTV for credit; groundedness for GenAI; null elsewhere. |
| `segment` | Slice for diagnosis: `subprime_650_680`, `prime_720_plus`, `card_present_pos`, `all`. |
| `prediction` | Model output. PD for credit, fraud probability for fraud, groundedness score for GenAI. |
| `confidence` | Distance from decision boundary, rough proxy. |

**The drift injection.** Day 60 is the cutover. Three intentional shifts:

1. **`credit_pd_v3`** — DTI distribution moves up. The shift is concentrated in the subprime slice (`subprime_650_680` mean: 0.34 to 0.44, days 0-29 vs days 60-89) while the prime slice does not move (0.32 to 0.32). Aggregate PSI looks merely yellow; subprime PSI is firmly red. This is the "aggregate PSI hides slice disasters" failure mode, with real numbers behind it.
2. **`fraud_card_v7`** — adversaries shift velocity from Poisson(2.4) to Poisson(1.6), a real tactic for evading velocity-based detection.
3. **`support_qa_v2`** — vendor silent update at day 60. Refusal rate moves from 4.5% to 11.17%, response length distribution shifts longer, groundedness drops. No code change on the bank side. This is the vendor-version-blindness failure mode.

The other five models are quiet — they're the false-positive control. Step 2's noise floor problem comes from running PSI/KS over them and watching benign features wiggle.

---

## `drift_events.csv` — flagged events with their deficiency class (10 rows)

Hand-curated outcome of running both the SOTA detector (Step 2) and DriftSentinel (Step 4) over the inference logs. Each row tags which of the five Step-3 deficiencies the event illustrates and whether each system caught it.

| Field | Description |
| --- | --- |
| `event_id` | Stable identifier. |
| `detected_date` | Date the alert would fire under each system. |
| `model_id` | Affected model. |
| `feature_or_signal` | What drifted. For GenAI: proxy metrics. |
| `psi`, `ks` | Drift statistics where applicable; `N/A` for proxy/categorical signals. |
| `segment` | Slice the event was localized to. Aggregate-vs-slice contrast is visible by comparing DE001 and DE002. |
| `deficiency_class` | One of: `aggregate_psi_hides_slice`, `no_diagnosis_routing`, `genai_proxy_gap`, `vendor_version_blindness`, `no_bounded_recommendation`. |
| `sota_caught` | `yes` / `no` / `partial` — what a vanilla PSI/KS pipeline alone produced. |
| `sentinel_caught` | What the three-loop product produced. |
| `recommendation` | The Decide-loop output: `RETAIN`, `SHADOW`, `RETRAIN`, or `ROLLBACK`. |

---

## `vendor_snapshots.csv` — vendor model snapshot history (6 rows)

The flight log for hosted-model snapshot IDs. The whole reason this file exists: a snapshot ID change is itself a drift event in the Sentinel taxonomy, and most legacy MRM tooling does not see it.

| Field | Description |
| --- | --- |
| `snapshot_date` | When the snapshot was first observed. |
| `vendor` | `anthropic`, `azure_openai`, `bedrock`. |
| `model_family` | E.g. `vendor-balanced-4`, `gpt-4o`. |
| `snapshot_id` | The version string. |
| `observed_in_fleet` | Which production model ran on this snapshot, or `offline_eval_only`. |
| `announcement_status` | `announced` (vendor told us) / `silent_minor_update` (we found it via probe regression) / `acknowledged_post_hoc` (vendor confirmed after escalation). |
| `notes` | Free-text. |

The interesting row is the Feb 14 entry: `vendor-balanced-4-20260214` showed up with the same API contract but a +6.67pp shift in refusal rate. The Sentinel caught it via vendor-version diff plus refusal-rate proxy. The file records the vendor confirming the weights update five days later (synthetic). This is the failure mode that quarterly Word docs literally cannot represent.

---

## How the four files connect

```
models.csv  ──┬──>  inference_logs.csv  (90 days × 8 models)
              │              │
              │              v
              │      Steps 2 / 4 detectors
              │              │
              │              v
              ├────>  drift_events.csv  (what each system caught)
              │
              v
        vendor_snapshots.csv  (silent-update flight log)
```

Timeline note: the vendor snapshot file dates the silent update 2026-02-14, which is day 44 of the logs, while the inference logs inject the `support_qa_v2` shift at day 60 (2026-03-02). The scripts join the two by model, not by date, so the gap changes no printed number.

Reproducibility: the inference logs were generated with `np.random.seed(42)`. The generator script is not in this repo, so the committed CSV is the source of truth. The scripts only read it, so re-running `python src/step_02_basic_drift_detection.py` prints the same PSI/KS values every time.

## Model labels

Hosted-model names in this project are neutral labels, not product ids. Every id has the shape `vendor-<tier>-<version>[-<release date>]`: `vendor-balanced-4` is the model family in `models.csv` and `vendor_snapshots.csv`, and `vendor-balanced-4-20251101`, `vendor-balanced-4-20260214` and `vendor-balanced-4-20250215` are pinned snapshots. `balanced` is the mid-priced hosted model. GPT-4o keeps its real name. No number in this project depends on the label.
