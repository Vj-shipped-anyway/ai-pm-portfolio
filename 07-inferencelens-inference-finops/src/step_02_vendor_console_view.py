"""
Step 2 - With basic vendor consoles: per-API-key spend, no business context.

Most banks call this "we have observability." Each vendor (Anthropic console,
Azure OpenAI metrics, AWS Bedrock CloudWatch) shows you cost per API key, per
day, per model. Better than the monthly aggregate, but still missing the only
view that matters: per-feature, per-tenant, with revenue alongside cost.

The API key is a tenancy artifact. A single API key serves multiple features.
A single feature uses multiple keys (one per environment). The vendor console
cannot answer "which BUSINESS feature is costing us this money?"

This script does NOT do per-feature attribution. It does per-API-key + per-model
+ per-day, which is the best the vendor consoles give you. Six of the bank's
deficiencies remain wide open.

Run:
    python step_02_vendor_console_view.py

Output: prints per-API-key, per-model, daily rollups; writes
src/out/step_02_vendor_console_view.csv.
"""

import csv
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


# Simulate the API-key tenancy model the bank uses. Multiple features per key.
# This is the lens the vendor console gives Finance.
FEATURE_TO_API_KEY = {
    "FT_001": "ak_retail_prod",
    "FT_002": "ak_wealth_prod",
    "FT_003": "ak_retail_prod",
    "FT_004": "ak_retail_prod",
    "FT_005": "ak_retail_prod",
    "FT_006": "ak_enterprise_prod",
    "FT_007": "ak_retail_prod",
    "FT_008": "ak_wealth_prod",
    "FT_009": "ak_enterprise_prod",  # the dead feature - hidden inside enterprise key
    "FT_010": "ak_retail_prod",
    "FT_011": "ak_retail_prod",
    "FT_012": "ak_retail_prod",
    "FT_013": "ak_retail_prod",
    "FT_014": "ak_wealth_prod",
    "FT_015": "ak_enterprise_prod",
    "FT_016": "ak_wealth_prod",
    "FT_017": "ak_retail_prod",
    "FT_018": "ak_retail_prod",
}


def load_logs() -> list[dict]:
    with open(DATA_DIR / "inference_logs.csv") as f:
        return list(csv.DictReader(f))


def load_features() -> dict[str, dict]:
    with open(DATA_DIR / "features.csv") as f:
        return {r["feature_id"]: r for r in csv.DictReader(f)}


def main() -> None:
    logs = load_logs()
    features = load_features()

    # Sample-to-monthly scaling
    feature_sample_counts: dict[str, int] = {}
    for r in logs:
        feature_sample_counts[r["feature_id"]] = (
            feature_sample_counts.get(r["feature_id"], 0) + 1
        )

    # Aggregate by (api_key, model)
    by_key_model: dict[tuple[str, str], float] = defaultdict(float)
    by_day: dict[str, float] = defaultdict(float)

    for r in logs:
        fid = r["feature_id"]
        ft = features.get(fid)
        if ft is None:
            continue
        monthly_vol = int(ft["monthly_query_volume"])
        n_sample = feature_sample_counts[fid]
        scale = (monthly_vol / n_sample) if n_sample > 0 and monthly_vol > 0 else 0
        modeled_cost = float(r["cost_usd"]) * scale
        api_key = FEATURE_TO_API_KEY.get(fid, "ak_unknown")
        model = r["model"]
        by_key_model[(api_key, model)] += modeled_cost
        day = r["timestamp"][:10]
        by_day[day] += modeled_cost

    print("\n" + "=" * 80)
    print("Step 2 - The vendor-console view (per-API-key, per-model)")
    print("=" * 80)
    print()
    print("Reporting period: May 15, 2026 - June 14, 2026")
    print()
    print("-" * 80)
    print(f"  {'API key':<24} {'Model':<26} {'Modeled monthly':>18}")
    print("-" * 80)
    for (key, model), amount in sorted(by_key_model.items(), key=lambda kv: -kv[1]):
        print(f"  {key:<24} {model:<26} ${amount:>16,.2f}")
    print("-" * 80)
    print()

    # Daily totals (last 7 days) - this is where a runaway WOULD be visible
    # if the operator clicked into the daily-trend chart
    print("Daily aggregate (last 7 days the vendor console shows by default):")
    last_7 = sorted(by_day.keys())[-7:]
    for day in last_7:
        bar = "#" * int(by_day[day] / 4000)
        print(f"  {day}  ${by_day[day]:>10,.0f}  {bar}")
    print()
    print("Notice: even the daily view aggregates everything. The FT_001 runaway")
    print("(retrieval depth misconfig on 2026-05-01) shows up only as a generic")
    print("uptick in 'ak_retail_prod'. The console cannot say WHICH feature inside")
    print("that key is responsible. Six deficiencies remain (Step 3).")
    print()

    out_path = OUT_DIR / "step_02_vendor_console_view.csv"
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["api_key", "model", "modeled_monthly_spend_usd"])
        for (key, model), amount in sorted(by_key_model.items(), key=lambda kv: -kv[1]):
            w.writerow([key, model, round(amount, 2)])

    print(f"Wrote: {out_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
