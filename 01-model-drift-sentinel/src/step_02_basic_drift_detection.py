"""
Step 2 — With basic drift detection: PSI/KS pipeline (the SOTA).

This is what most teams ship as 'continuous monitoring' today. A Python job
runs nightly, computes Population Stability Index and Kolmogorov-Smirnov
on each feature against a reference window, and pages the validator if any
PSI crosses 0.25.

It catches the obvious moves. It also produces a steady stream of alerts
on benign drift (seasonal patterns, week-over-week sample noise) and
gives the on-call zero diagnosis to work with. 'Feature dti drifted, PSI
0.34' lands in Slack at 2 AM and the validator has to answer 'is this real,
which segment, what changed upstream, what do we do about it' from scratch.

Run:
    python step_02_basic_drift_detection.py

Output: per-model PSI/KS sweep, prints the alert log a SOTA pipeline would
have produced, writes results to src/out/step_02_drift_sweep.csv.
"""

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

REF_DAYS = (0, 30)     # baseline window
CUR_DAYS = (60, 90)    # current window — drift starts day 60

PSI_WATCH = 0.10
PSI_DRIFT = 0.25


def psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index. Standard formula."""
    reference = reference[~pd.isna(reference)]
    current = current[~pd.isna(current)]
    if len(reference) == 0 or len(current) == 0:
        return float("nan")
    lo = float(min(reference.min(), current.min()))
    hi = float(max(reference.max(), current.max()))
    if hi - lo < 1e-9:
        return 0.0
    breakpoints = np.linspace(lo, hi, bins + 1)
    ref_pct = np.histogram(reference, bins=breakpoints)[0] / len(reference)
    cur_pct = np.histogram(current, bins=breakpoints)[0] / len(current)
    ref_pct = np.where(ref_pct == 0, 1e-6, ref_pct)
    cur_pct = np.where(cur_pct == 0, 1e-6, cur_pct)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def ks_stat(reference: np.ndarray, current: np.ndarray) -> float:
    reference = reference[~pd.isna(reference)]
    current = current[~pd.isna(current)]
    if len(reference) == 0 or len(current) == 0:
        return float("nan")
    return float(ks_2samp(reference, current).statistic)


def severity(psi_val: float) -> str:
    if pd.isna(psi_val):
        return "N/A"
    if psi_val < PSI_WATCH:
        return "GREEN"
    if psi_val < PSI_DRIFT:
        return "YELLOW"
    return "RED"


def slice_window(df: pd.DataFrame, day_start: int, day_end: int) -> pd.DataFrame:
    df = df.copy()
    df["day"] = (pd.to_datetime(df["date"]) - pd.to_datetime(df["date"]).min()).dt.days
    return df[(df["day"] >= day_start) & (df["day"] < day_end)]


def feature_columns_for(model_id: str) -> list[str]:
    """Which feature columns matter for which model — the SOTA pipeline runs
    PSI on whatever it's told to. Aggregate-level only, no segment slicing."""
    if model_id.startswith("credit_"):
        return ["feature_dti", "feature_fico", "feature_ltv", "prediction"]
    if model_id == "fraud_card_v7":
        return ["feature_dti", "feature_fico", "prediction"]  # velocity in dti col
    if model_id == "fraud_ach_v3":
        return ["feature_fico", "prediction"]
    if model_id == "aml_sar_v2":
        return ["prediction"]
    if model_id == "support_qa_v2":
        # The SOTA pipeline runs PSI on numeric features. It treats GenAI
        # like any other numeric model — which is exactly the gap.
        return ["feature_dti", "feature_fico", "feature_ltv", "prediction"]
    if model_id.startswith("auto_") or model_id.startswith("heloc_"):
        return ["feature_dti", "feature_fico", "feature_ltv", "prediction"]
    return ["prediction"]


def main():
    df = pd.read_csv(DATA_DIR / "inference_logs.csv")
    models = list(csv.DictReader(open(DATA_DIR / "models.csv")))

    print("\n" + "=" * 80)
    print("Step 2 — With basic drift detection: PSI/KS pipeline (the SOTA)")
    print("=" * 80)
    print(f"\nReference window: days {REF_DAYS[0]:>2} to {REF_DAYS[1]:>2}")
    print(f"Current window:   days {CUR_DAYS[0]:>2} to {CUR_DAYS[1]:>2}")
    print(f"Thresholds:       PSI < {PSI_WATCH:.2f} green, < {PSI_DRIFT:.2f} yellow, else red")
    print("Slicing:          aggregate only. No segments. (That's the SOTA gap.)")
    print()

    rows_out = []
    alerts_total = 0
    drift_alerts = 0
    by_status = defaultdict(int)

    for model in models:
        mid = model["model_id"]
        m_df = df[df["model_id"] == mid]
        ref = slice_window(m_df, *REF_DAYS)
        cur = slice_window(m_df, *CUR_DAYS)

        print("-" * 80)
        print(f"Model: {mid:<22} ({model['name']})")
        print("-" * 80)
        print(f"  ref n={len(ref):>5}   cur n={len(cur):>5}")

        for col in feature_columns_for(mid):
            if col not in m_df.columns:
                continue
            r = ref[col].values
            c = cur[col].values
            p = psi(r, c)
            k = ks_stat(r, c)
            sev = severity(p)
            by_status[sev] += 1
            alerts_total += 1
            if sev == "RED":
                drift_alerts += 1
            print(f"    {col:<18} PSI={p:>6.3f}  KS={k:>5.3f}  status={sev}")
            rows_out.append({
                "model_id": mid,
                "feature": col,
                "psi": round(p, 4) if not pd.isna(p) else "",
                "ks": round(k, 4) if not pd.isna(k) else "",
                "status": sev,
                "diagnosis": "(none — SOTA pipeline does not diagnose)",
                "recommendation": "(none — pages a human)",
            })
        print()

    out_path = OUT_DIR / "step_02_drift_sweep.csv"
    with open(out_path, "w", newline="") as out:
        w = csv.DictWriter(out, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    print("=" * 80)
    print("Alert log — what landed in the on-call's Slack")
    print("=" * 80)
    for r in rows_out:
        if r["status"] in ("YELLOW", "RED"):
            print(f"  [{r['status']:>6}]  {r['model_id']:<22}  {r['feature']:<18}  "
                  f"PSI={r['psi']}  KS={r['ks']}")

    print()
    print("=" * 80)
    print("Summary — the SOTA noise floor problem")
    print("=" * 80)
    print(f"  Total feature-level checks:    {alerts_total}")
    print(f"  Green:                         {by_status['GREEN']}")
    print(f"  Yellow (watch):                {by_status['YELLOW']}")
    print(f"  Red (drift):                   {by_status['RED']}")
    print()
    print("  What the on-call sees: a list of feature names with PSI numbers")
    print("  and a binary 'is it drifting' flag. No segment. No diagnosis.")
    print("  No upstream context. No retain/shadow/retrain/rollback call.")
    print()
    print("  Three things the SOTA pipeline literally cannot tell you:")
    print("    1. Which slice the drift is concentrated in.")
    print("    2. Whether a known upstream change explains it.")
    print("    3. What the GenAI model's silent vendor update did to refusal rate.")
    print()
    print("  Step 3 names these gaps. Step 4 fixes them.")
    print()
    print(f"Wrote: {out_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
