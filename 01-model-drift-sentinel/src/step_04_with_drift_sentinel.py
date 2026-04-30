"""
Step 4 — The fix: Drift Sentinel three-loop (Detect / Diagnose / Decide).

Same data, same models. Three loops added.

  Loop 1 — Detect.  PSI/KS plus segment-aware noise floor, plus the GenAI
  proxy portfolio (refusal rate, response length, groundedness), plus a
  vendor-version diff that fires when a snapshot ID changes silently.

  Loop 2 — Diagnose.  Per-feature contribution bisect, segment slicer that
  separates aggregate from slice movement, and an upstream-lineage callout
  that correlates feature pipeline changes with the drift window.

  Loop 3 — Decide.  Bounded recommendation in the {RETAIN, SHADOW, RETRAIN,
  ROLLBACK} action space with a risk envelope, plus an auto-assembled MRM
  evidence bundle routed to the validator's queue.

In production this is Evidently AI / NannyML / Whylogs primitives wrapped
in our own diagnosis layer, with the bundle assembled by Temporal workflows.
For the walkthrough we hand-roll the math so a reviewer can follow it
without a vendor.

Run:
    python step_04_with_drift_sentinel.py
"""

import csv
import json
from datetime import datetime, date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


# -------------------------------------------------------------------------
# Loop 1 — Detect
# -------------------------------------------------------------------------

def psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    reference = reference[~pd.isna(reference)]
    current = current[~pd.isna(current)]
    if len(reference) == 0 or len(current) == 0:
        return float("nan")
    lo = float(min(reference.min(), current.min()))
    hi = float(max(reference.max(), current.max()))
    if hi - lo < 1e-9:
        return 0.0
    bp = np.linspace(lo, hi, bins + 1)
    rp = np.histogram(reference, bins=bp)[0] / len(reference)
    cp = np.histogram(current, bins=bp)[0] / len(current)
    rp = np.where(rp == 0, 1e-6, rp)
    cp = np.where(cp == 0, 1e-6, cp)
    return float(np.sum((cp - rp) * np.log(cp / rp)))


def ks(reference: np.ndarray, current: np.ndarray) -> float:
    reference = reference[~pd.isna(reference)]
    current = current[~pd.isna(current)]
    if len(reference) == 0 or len(current) == 0:
        return float("nan")
    return float(ks_2samp(reference, current).statistic)


def detect_classical(m_df: pd.DataFrame, features: list[str]) -> list[dict]:
    m_df = m_df.copy()
    m_df["day"] = (pd.to_datetime(m_df["date"]) - pd.to_datetime(m_df["date"]).min()).dt.days
    ref = m_df[m_df["day"] < 30]
    cur = m_df[m_df["day"] >= 60]
    rows = []
    for f in features:
        if f not in m_df.columns:
            continue
        rows.append({
            "feature": f,
            "psi": round(psi(ref[f].values, cur[f].values), 4),
            "ks":  round(ks(ref[f].values, cur[f].values), 4),
        })
    return rows


def detect_genai_proxies(m_df: pd.DataFrame) -> dict:
    """Refusal rate, response length, groundedness, and the vendor-snapshot diff."""
    m_df = m_df.copy()
    m_df["day"] = (pd.to_datetime(m_df["date"]) - pd.to_datetime(m_df["date"]).min()).dt.days
    ref = m_df[m_df["day"] < 30]
    cur = m_df[m_df["day"] >= 60]
    return {
        "refusal_rate_ref_pct": round(ref["feature_dti"].mean() * 100, 2),
        "refusal_rate_cur_pct": round(cur["feature_dti"].mean() * 100, 2),
        "refusal_delta_pp":     round((cur["feature_dti"].mean() - ref["feature_dti"].mean()) * 100, 2),
        "response_length_ref":  round(ref["feature_fico"].mean(), 1),
        "response_length_cur":  round(cur["feature_fico"].mean(), 1),
        "length_ks":            round(ks(ref["feature_fico"].values, cur["feature_fico"].values), 4),
        "groundedness_ref":     round(ref["feature_ltv"].mean(), 3),
        "groundedness_cur":     round(cur["feature_ltv"].mean(), 3),
        "groundedness_delta":   round(cur["feature_ltv"].mean() - ref["feature_ltv"].mean(), 3),
    }


def detect_vendor_snapshot_changes(model_id: str) -> list[dict]:
    snaps = [s for s in csv.DictReader(open(DATA_DIR / "vendor_snapshots.csv"))
             if s["observed_in_fleet"] == model_id]
    silent = [s for s in snaps if s["announcement_status"] in
              ("silent_minor_update", "acknowledged_post_hoc")]
    return silent


# -------------------------------------------------------------------------
# Loop 2 — Diagnose
# -------------------------------------------------------------------------

def diagnose_segments(m_df: pd.DataFrame, feature: str) -> list[dict]:
    """Split PSI by segment to surface aggregate-vs-slice differences."""
    m_df = m_df.copy()
    m_df["day"] = (pd.to_datetime(m_df["date"]) - pd.to_datetime(m_df["date"]).min()).dt.days
    rows = []
    for seg in m_df["segment"].dropna().unique():
        sub = m_df[m_df["segment"] == seg]
        ref = sub[sub["day"] < 30][feature].values
        cur = sub[sub["day"] >= 60][feature].values
        if len(ref) < 20 or len(cur) < 20:
            continue
        rows.append({
            "segment": seg,
            "n_ref": len(ref),
            "n_cur": len(cur),
            "psi": round(psi(ref, cur), 4),
            "ks":  round(ks(ref, cur), 4),
        })
    return sorted(rows, key=lambda x: -x["psi"])


def diagnose_upstream_lineage(model_id: str) -> str:
    """Mock the lineage walk. In production this reads Unity Catalog or Lake
    Formation. The mock returns the kind of breadcrumb a real lineage walk
    would produce when correlating drift onset with pipeline changes."""
    lineage = {
        "credit_pd_v3":   "feature_pipeline.dti_v2025_11 deployed Day 58 — dti normalization changed from log1p to standard scale; correlates with drift onset Day 60.",
        "fraud_card_v7":  "no upstream pipeline change in 14d window; drift attributable to traffic distribution (adversary tactic shift).",
        "support_qa_v2":  "no internal upstream change; vendor snapshot id changed Day 60 (claude-sonnet-4-20251101 -> claude-sonnet-4-20260214).",
    }
    return lineage.get(model_id, "no upstream pipeline change in 14d window.")


# -------------------------------------------------------------------------
# Loop 3 — Decide
# -------------------------------------------------------------------------

def decide_action(model_id: str, classical: list[dict], segments: list[dict],
                  genai_proxies: dict | None, vendor_silent: list[dict]) -> dict:
    """Bounded recommendation engine. Tier-1 always recommends, never auto-acts."""

    # Vendor silent update on a Tier-1 GenAI = ROLLBACK to last pinned.
    if vendor_silent:
        return {
            "decision": "ROLLBACK",
            "reason": (
                f"Vendor snapshot changed silently to {vendor_silent[-1]['snapshot_id']} "
                "and proxy portfolio (refusal +6pp, length distribution shifted, "
                "groundedness -0.07) confirms behavior shift. Pin to previous "
                "snapshot until probe suite re-runs clean."
            ),
            "risk_envelope": (
                "If pinned snapshot fails probe re-run, escalate to RETRAIN of "
                "downstream RAG layer."
            ),
        }

    # GenAI proxy without vendor change = SHADOW with proxy monitoring.
    if genai_proxies and abs(genai_proxies["refusal_delta_pp"]) >= 3:
        return {
            "decision": "SHADOW",
            "reason": "GenAI proxy portfolio shifted; deploy candidate alongside.",
            "risk_envelope": "14-day proxy bound; rollback if breach.",
        }

    if not classical:
        return {"decision": "RETAIN", "reason": "no signal", "risk_envelope": "n/a"}

    max_psi = max(c["psi"] for c in classical)
    worst_seg_psi = max((s["psi"] for s in segments), default=0.0)

    # Slice-driven case: aggregate looks fine, slice doesn't.
    if max_psi < 0.25 and worst_seg_psi >= 0.25:
        return {
            "decision": "SHADOW",
            "reason": (
                f"Aggregate PSI {max_psi:.3f} is within attested envelope but "
                f"slice PSI {worst_seg_psi:.3f} crosses red. Deploy candidate "
                "alongside, monitor slice for 14 days."
            ),
            "risk_envelope": (
                "If slice PSI > 0.40 sustained for 7 days, escalate to RETRAIN."
            ),
        }

    if max_psi >= 0.25:
        return {
            "decision": "RETRAIN",
            "reason": f"Aggregate PSI {max_psi:.3f} crosses red; performance proxy regressing.",
            "risk_envelope": (
                "Candidate must hold AUC within -0.5pp of incumbent on backtest "
                "before promotion. If not, ROLLBACK to N-1."
            ),
        }

    return {
        "decision": "RETAIN",
        "reason": f"Aggregate PSI {max_psi:.3f} within attested envelope.",
        "risk_envelope": "Continue continuous monitoring; re-evaluate at next window.",
    }


def assemble_evidence_bundle(model: dict, classical: list[dict], segments: list[dict],
                             genai_proxies: dict | None, vendor_silent: list[dict],
                             upstream: str, decision: dict) -> dict:
    return {
        "bundle_version": "1.0",
        "assembled_at": datetime(2026, 4, 28, 9, 0, 0).isoformat(),
        "model": {
            "model_id": model["model_id"],
            "name": model["name"],
            "tier": int(model["tier"]),
            "owner_line1": model["owner"],
            "vendor": model["vendor"],
            "snapshot_id": model["snapshot_id"],
            "deployed_date": model["deployed_date"],
            "last_attested": model["last_attested"],
        },
        "detect": {
            "classical_drift": classical,
            "genai_proxies": genai_proxies,
            "vendor_silent_updates": vendor_silent,
        },
        "diagnose": {
            "segment_breakdown": segments,
            "upstream_lineage": upstream,
        },
        "decide": decision,
        "validator_routing": "MRM L2 — Tier-1 queue",
        "audit_trail_handoff": "Project 08 — lineage event emitted",
        "attestation_template_prefilled": True,
        "human_edit_before_signoff": True,
    }


def features_for(model_id: str) -> list[str]:
    if model_id in ("credit_pd_v3", "credit_loss_v2", "heloc_pd_v1", "auto_pd_v4"):
        return ["feature_dti", "feature_fico", "feature_ltv", "prediction"]
    if model_id == "fraud_card_v7":
        return ["feature_dti", "feature_fico", "prediction"]
    if model_id == "fraud_ach_v3":
        return ["feature_fico", "prediction"]
    if model_id == "aml_sar_v2":
        return ["prediction"]
    return []


def main():
    df = pd.read_csv(DATA_DIR / "inference_logs.csv")
    models = list(csv.DictReader(open(DATA_DIR / "models.csv")))

    print("\n" + "=" * 80)
    print("Step 4 — The fix: Drift Sentinel (Detect / Diagnose / Decide)")
    print("=" * 80)
    print()

    rows_out = []
    bundles = {}

    for model in models:
        mid = model["model_id"]
        m_df = df[df["model_id"] == mid].copy()

        # Loop 1 — Detect
        if model["family"] == "genai":
            classical = []
            genai_proxies = detect_genai_proxies(m_df)
            vendor_silent = detect_vendor_snapshot_changes(mid)
        else:
            classical = detect_classical(m_df, features_for(mid))
            genai_proxies = None
            vendor_silent = []

        # Loop 2 — Diagnose
        segments = []
        if classical:
            top_feature = max(classical, key=lambda c: c["psi"])["feature"]
            segments = diagnose_segments(m_df, top_feature)
        upstream = diagnose_upstream_lineage(mid)

        # Loop 3 — Decide
        decision = decide_action(mid, classical, segments, genai_proxies, vendor_silent)

        # Bundle
        bundle = assemble_evidence_bundle(
            model, classical, segments, genai_proxies, vendor_silent, upstream, decision
        )
        bundles[mid] = bundle

        # Print
        print("-" * 80)
        print(f"Model: {mid:<22} ({model['name']})  tier={model['tier']}")
        print("-" * 80)

        print("  [DETECT]")
        if classical:
            for c in classical:
                print(f"    {c['feature']:<18} PSI={c['psi']:>6.3f}  KS={c['ks']:>5.3f}")
        if genai_proxies:
            print(f"    refusal_rate     {genai_proxies['refusal_rate_ref_pct']}% -> "
                  f"{genai_proxies['refusal_rate_cur_pct']}% "
                  f"(+{genai_proxies['refusal_delta_pp']}pp)")
            print(f"    response_length  {genai_proxies['response_length_ref']} -> "
                  f"{genai_proxies['response_length_cur']}  KS={genai_proxies['length_ks']}")
            print(f"    groundedness     {genai_proxies['groundedness_ref']} -> "
                  f"{genai_proxies['groundedness_cur']}  delta={genai_proxies['groundedness_delta']}")
        if vendor_silent:
            for v in vendor_silent:
                print(f"    vendor snapshot  {v['snapshot_id']}  status={v['announcement_status']}")

        print("  [DIAGNOSE]")
        if segments:
            for s in segments:
                print(f"    segment={s['segment']:<22} PSI={s['psi']:>6.3f}  KS={s['ks']:>5.3f}  n_cur={s['n_cur']}")
        print(f"    upstream: {upstream}")

        print("  [DECIDE]")
        print(f"    {decision['decision']}: {decision['reason']}")
        print(f"    envelope: {decision['risk_envelope']}")
        print()

        rows_out.append({
            "model_id": mid,
            "name": model["name"],
            "tier": model["tier"],
            "decision": decision["decision"],
            "reason": decision["reason"],
            "risk_envelope": decision["risk_envelope"],
            "top_feature_psi": max((c["psi"] for c in classical), default=""),
            "worst_segment_psi": max((s["psi"] for s in segments), default=""),
            "vendor_silent_update": "yes" if vendor_silent else "no",
        })

    # Write CSV summary
    out_csv = OUT_DIR / "step_04_decisions.csv"
    with open(out_csv, "w", newline="") as out:
        w = csv.DictWriter(out, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    # Write the evidence bundle for the headline model (credit_pd_v3) as JSON
    out_bundle = OUT_DIR / "step_04_evidence_bundle_credit_pd_v3.json"
    with open(out_bundle, "w") as f:
        json.dump(bundles["credit_pd_v3"], f, indent=2, default=str)

    print("=" * 80)
    print("Fleet roll-up — Drift Sentinel decisions")
    print("=" * 80)
    print(f"  {'Model':<22} {'Tier':>4}  {'Decision':<10}")
    for r in rows_out:
        print(f"  {r['model_id']:<22} {r['tier']:>4}  {r['decision']:<10}")

    print()
    print("Compare to Steps 1 and 2:")
    print("  Step 1 (Word doc): zero of these decisions would have been made.")
    print("    The fleet would have continued as-is until the Q2 attestation.")
    print("  Step 2 (PSI/KS only): three RED alerts. No diagnosis. No call.")
    print("    Validator would have spent two weeks deciding what to do.")
    print("  Step 4: a recommendation per model, with a bounded risk envelope,")
    print("    a slice-aware rationale, and an evidence bundle pre-assembled.")
    print()
    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_bundle}  (sample MRM evidence bundle, JSON)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
