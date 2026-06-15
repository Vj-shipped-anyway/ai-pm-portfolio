"""
Step 1 - Before InferenceLens: the monthly aggregate cost report.

This is what Finance gets today at a Tier-1 retail bank. The vendor invoice
arrives on the 5th of each month. AWS Bedrock, Anthropic, and Azure OpenAI
each send their own invoice. The CFO's office aggregates them into a single
line in the AI Platform cost report: "GenAI compute - $4.18M (May 2026)."

There is no per-feature breakdown. There is no per-tenant breakdown. There
is no daily trend. The CFO learns about a runaway feature six weeks after
it started, when the next quarterly cost review surfaces a YoY anomaly that
nobody can explain.

This script does NOT do per-feature attribution. That is the whole point.
It prints the report Finance actually sees: one number per vendor, one big
total, no business context.

Run:
    python step_01_aggregate_only.py

Output: prints the aggregate report; writes
src/out/step_01_aggregate_report.csv.
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


def load_logs() -> list[dict]:
    with open(DATA_DIR / "inference_logs.csv") as f:
        return list(csv.DictReader(f))


def load_features() -> dict[str, dict]:
    with open(DATA_DIR / "features.csv") as f:
        return {r["feature_id"]: r for r in csv.DictReader(f)}


def main() -> None:
    logs = load_logs()
    features = load_features()

    # The sample logs are ~1:N stratified samples of full traffic.
    # We scale by (monthly_volume / sampled_calls_per_feature) to get the
    # modeled aggregate spend the way a vendor invoice would show it.
    feature_sample_counts: dict[str, int] = {}
    for r in logs:
        feature_sample_counts[r["feature_id"]] = (
            feature_sample_counts.get(r["feature_id"], 0) + 1
        )

    by_vendor: dict[str, float] = {}
    total_modeled = 0.0
    sample_count = 0
    sample_cost = 0.0

    # 60-day window in the data. Scale each sample row to the full window's
    # traffic, then divide by 2 to report MONTHLY aggregate (the way Finance
    # actually reads the vendor invoice).
    WINDOW_MONTHS = 2.0
    for r in logs:
        fid = r["feature_id"]
        ft = features.get(fid)
        if ft is None:
            continue
        monthly_vol = int(ft["monthly_query_volume"])
        n_sample = feature_sample_counts[fid]
        # Each sample represents (monthly_vol * WINDOW_MONTHS / n_sample)
        # real calls; divide by WINDOW_MONTHS to express as monthly cost.
        scale = (monthly_vol / n_sample) if n_sample > 0 and monthly_vol > 0 else 0
        modeled_cost = float(r["cost_usd"]) * scale
        # Map model -> vendor
        model = r["model"]
        if model.startswith("claude-"):
            vendor = "Anthropic"
        elif model.startswith("gpt-"):
            vendor = "Azure OpenAI"
        else:
            vendor = "AWS Bedrock"
        by_vendor[vendor] = by_vendor.get(vendor, 0) + modeled_cost
        total_modeled += modeled_cost
        sample_count += 1
        sample_cost += float(r["cost_usd"])

    print("\n" + "=" * 80)
    print("Step 1 - The vendor-invoice view (what Finance sees today)")
    print("=" * 80)
    print()
    print("Reporting period:    April 15, 2026 - June 14, 2026 (60-day window)")
    print(f"Sampled inference calls in the log: {sample_count:,}")
    print(f"Raw sample cost:                    ${sample_cost:,.2f}")
    print()
    print("-" * 80)
    print("Monthly aggregate by vendor (the only view the CFO gets today)")
    print("-" * 80)
    for v, amount in sorted(by_vendor.items(), key=lambda kv: -kv[1]):
        print(f"  {v:<20} ${amount:>14,.2f}")
    print("-" * 80)
    print(f"  {'TOTAL':<20} ${total_modeled:>14,.2f}")
    print()
    print("What this report does NOT tell the CFO:")
    print("  - Which features cost what")
    print("  - Which customer segments drive the spend")
    print("  - Whether any single feature is running away")
    print("  - Whether the spend is paying for revenue or burning cash")
    print("  - Whether decommissioned features are still hitting the API")
    print()
    print("The aggregate hides everything. A single feature burning $50k/day")
    print("is invisible against the $4M monthly total. Step 2 (basic per-vendor")
    print("dashboards) helps a little. Step 3 names the six deficiencies.")
    print("Step 4 (InferenceLens) closes all six.")
    print()

    out_path = OUT_DIR / "step_01_aggregate_report.csv"
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vendor", "modeled_monthly_spend_usd"])
        for v, amount in sorted(by_vendor.items(), key=lambda kv: -kv[1]):
            w.writerow([v, round(amount, 2)])
        w.writerow(["TOTAL", round(total_modeled, 2)])

    print(f"Wrote: {out_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
