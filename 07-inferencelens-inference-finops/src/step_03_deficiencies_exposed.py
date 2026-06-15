"""
Step 3 - Six named deficiencies, each illustrated on the real-feeling fleet.

This script takes the synthetic 18-feature fleet and walks the six deficiencies
one by one. For each, it surfaces the CFO-style question a real Finance team
asks at quarter-end, and shows what aggregate vendor-console reports return
today.

Each gap has a real, dollar-shaped consequence. The FT_001 runaway is the
loudest, but the dead feature (FT_009), the dormant feature (FT_016), and the
over-tiered features (Opus on customer-service queries) all contribute.

Run:
    python step_03_deficiencies_exposed.py

Output: prints six exam questions + the gap each one exposes;
writes src/out/step_03_deficiency_examples.csv.
"""

import csv
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


DEFICIENCIES = [
    {
        "n": 1,
        "label": "No per-feature attribution",
        "cfo_question": (
            "Of our $4.18M May compute spend, what did customer-service-assistant "
            "cost vs. wealth-portfolio-summary vs. kyc-doc-reader?"
        ),
        "what_logs_return": (
            "Vendor invoices are per-vendor totals. Vendor consoles are per-API-key. "
            "Both aggregate multiple features behind the same key. The feature catalog "
            "lives in the platform team's Confluence; nothing joins it to the spend."
        ),
        "consequence": (
            "CFO asks 'what are we paying for' at quarterly review. AI Platform PM "
            "answers 'we are looking into it' for the third quarter in a row."
        ),
    },
    {
        "n": 2,
        "label": "No per-tenant / customer-segment attribution",
        "cfo_question": (
            "Of the customer-service-assistant spend, what did retail-Tier-1 customers "
            "consume vs. retail-Tier-2 vs. internal-employee testing?"
        ),
        "what_logs_return": (
            "API key separation is at the line-of-business level (retail / wealth / "
            "enterprise). It does NOT separate customer segment within a line. "
            "Internal employee dogfood traffic runs on the same key as real customers."
        ),
        "consequence": (
            "Cannot answer 'is the high-value-customer segment paying for itself.' "
            "Cannot bill internal teams for their share. Cannot detect a single "
            "power-user account that is consuming 20x its segment's average."
        ),
    },
    {
        "n": 3,
        "label": "No runaway detection",
        "cfo_question": (
            "FT_001 daily spend was ~$1,600 on April 30 and ~$6,000 on May 2. "
            "It is now June 14. Why did nobody flag the 3.7x daily-spend spike?"
        ),
        "what_logs_return": (
            "The daily-spend spike is invisible because it lives inside a $4M "
            "aggregate. No statistical-process-control threshold on per-feature spend. "
            "No alert fires until the monthly vendor invoice arrives - 6 weeks late."
        ),
        "consequence": (
            "Feature ran with mis-set retrieval depth (50 docs instead of 5) for 45 "
            "days. Modeled overspend: ~$195k before InferenceLens catches it on day "
            "1 in the walkthrough. The fix took 12 minutes once named."
        ),
    },
    {
        "n": 4,
        "label": "No cheaper-model substitution recommender",
        "cfo_question": (
            "Why is the customer-service-assistant on Sonnet when Haiku would work? "
            "Why is the compliance-summarizer on Opus when Sonnet would?"
        ),
        "what_logs_return": (
            "Model choice gets made at feature-build time, by a developer, with the "
            "quickstart's default model in the snippet. Nothing re-evaluates whether "
            "the choice is still right. No eval suite that maps probe-set accuracy "
            "across the model-pricing tiers."
        ),
        "consequence": (
            "Modeled 27% of the fleet is over-tiered. ~$240k/mo of avoidable spend "
            "across the customer-service-assistant + compliance-summarizer + branch-"
            "banker-copilot + kyc-doc-reader. Pure inertia tax."
        ),
    },
    {
        "n": 5,
        "label": "No dead-feature detection",
        "cfo_question": (
            "FT_009 (internal-research-copilot) UI was shut down on March 15. Why "
            "is the endpoint still receiving 4,700 calls/day?"
        ),
        "what_logs_return": (
            "Status in the feature catalog is updated by the product team manually. "
            "Endpoint stays live until someone files a ticket. Decommissioning is "
            "everyone's job and no one's KPI."
        ),
        "consequence": (
            "Leaked SDK key + a downstream batch job nobody remembered to decommission "
            "is generating ~$28k/mo of zero-business-value inference cost. The dormant "
            "FT_016 adds another ~$180/mo - small alone, governance smell at fleet scale."
        ),
    },
    {
        "n": 6,
        "label": "No per-feature ROI dashboard",
        "cfo_question": (
            "Which GenAI features are generating revenue and which are burning cash? "
            "The board is asking for the AI-platform ROI number at the May offsite."
        ),
        "what_logs_return": (
            "Cost lives in vendor invoices. Revenue attribution lives in the data "
            "warehouse, tagged by product surface. No join key. AI Platform PM hand-"
            "builds a spreadsheet quarterly that is stale by the time it ships."
        ),
        "consequence": (
            "Cannot defend the AI roadmap with per-feature ROI. Cannot kill features "
            "that have negative ROI. Board frames AI spend as 'cost'; the spend that "
            "is paying for itself gets lumped with the spend that is not."
        ),
    },
]


def load_logs() -> list[dict]:
    with open(DATA_DIR / "inference_logs.csv") as f:
        return list(csv.DictReader(f))


def load_features() -> dict[str, dict]:
    with open(DATA_DIR / "features.csv") as f:
        return {r["feature_id"]: r for r in csv.DictReader(f)}


def quantify_runaway(logs: list[dict], features: dict[str, dict]) -> dict:
    """Quantify the FT_001 runaway: daily cost before/after 2026-05-01."""
    fid = "FT_001"
    ft = features.get(fid)
    if ft is None:
        return {}
    monthly_vol = int(ft["monthly_query_volume"])
    sample_count = sum(1 for r in logs if r["feature_id"] == fid)
    scale = (monthly_vol / sample_count / 30) if sample_count > 0 else 0  # daily scale

    pre = []
    post = []
    for r in logs:
        if r["feature_id"] != fid:
            continue
        cost = float(r["cost_usd"]) * scale
        if r["timestamp"] < "2026-05-01":
            pre.append(cost)
        else:
            post.append(cost)
    pre_avg_daily = sum(pre) if pre else 0
    post_avg_daily = sum(post) / max(1, len([r for r in logs if r["feature_id"] == fid and r["timestamp"] >= "2026-05-01"]))
    return {
        "fid": fid,
        "pre_runaway_daily_modeled": round(sum(pre) / max(1, len(pre)) * sample_count / 30, 0),
        "post_runaway_daily_modeled": round(sum(post) / max(1, len(post)) * sample_count / 30, 0),
    }


def main() -> None:
    logs = load_logs()
    features = load_features()

    print("\n" + "=" * 80)
    print("Step 3 - Six deficiencies in InferenceLens' taxonomy, each named")
    print("=" * 80)
    print()
    print("Today's posture: aggregate vendor invoices + per-API-key dashboards.")
    print("Six gaps a CFO asks about and Finance cannot answer.")
    print()

    for d in DEFICIENCIES:
        print("-" * 80)
        print(f"  Deficiency #{d['n']}: {d['label']}")
        print(f"    CFO question:    {d['cfo_question']}")
        print(f"    Today returns:   {d['what_logs_return']}")
        print(f"    Consequence:     {d['consequence']}")

    print()

    # Quantify the headline runaway from the actual sample logs
    print("-" * 80)
    print("Headline runaway quantified from the synthetic data")
    print("-" * 80)
    fid = "FT_001"
    ft = features[fid]
    monthly_vol = int(ft["monthly_query_volume"])
    daily_vol = monthly_vol / 30  # modeled real daily calls
    pre_costs: list[float] = []
    post_costs: list[float] = []
    for r in logs:
        if r["feature_id"] != fid:
            continue
        day = r["timestamp"][:10]
        if day < "2026-05-01":
            pre_costs.append(float(r["cost_usd"]))
        else:
            post_costs.append(float(r["cost_usd"]))
    avg_pre_per_call = sum(pre_costs) / max(1, len(pre_costs)) if pre_costs else 0
    avg_post_per_call = sum(post_costs) / max(1, len(post_costs)) if post_costs else 0
    pre_daily = avg_pre_per_call * daily_vol
    post_daily = avg_post_per_call * daily_vol
    multiplier = post_daily / pre_daily if pre_daily else float("inf")

    print(f"  Feature:                                 {fid} ({ft['feature_name']})")
    print(f"  Modeled cost / call BEFORE 2026-05-01:   ${avg_pre_per_call:>8,.4f}")
    print(f"  Modeled cost / call AFTER  2026-05-01:   ${avg_post_per_call:>8,.4f}")
    print(f"  Modeled DAILY spend BEFORE 2026-05-01:   ${pre_daily:>10,.0f}")
    print(f"  Modeled DAILY spend AFTER  2026-05-01:   ${post_daily:>10,.0f}")
    if pre_daily:
        print(f"  Multiplier:                              {multiplier:.1f}x")
    days_undetected = 45  # 2026-05-01 -> 2026-06-14 in scenario
    overspend = (post_daily - pre_daily) * days_undetected
    print(f"  Days undetected:                         {days_undetected}")
    print(f"  Modeled overspend before detection:      ${overspend:>10,.0f}")
    print()
    print("  Without per-feature attribution, this is invisible. Step 4 catches")
    print("  it on day 1.")
    print()

    # Write to CSV
    out_path = OUT_DIR / "step_03_deficiency_examples.csv"
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n", "label", "cfo_question", "what_today_returns", "consequence"])
        for d in DEFICIENCIES:
            w.writerow([d["n"], d["label"], d["cfo_question"], d["what_logs_return"], d["consequence"]])

    print(f"Wrote: {out_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
