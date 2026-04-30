"""
Production Model Drift Sentinel — Streamlit prototype.

Author: Vijay Saharan
Run:    streamlit run app.py

A walkthrough of the four-step product story as a single interactive surface:

  Tab 1 — Live Fleet:  drift health badges across the 8 production models.
  Tab 2 — Detect:      PSI/KS time-series with the Day 60 drift event marker.
  Tab 3 — Diagnose:    feature-contribution chart, segment slicer, lineage callout.
  Tab 4 — Decide:      bounded recommendation card and the auto-assembled
                       MRM evidence bundle as expandable JSON.

The data is loaded from data/inference_logs.csv, models.csv, drift_events.csv,
and vendor_snapshots.csv. Same files the four step scripts use.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy.stats import ks_2samp

# -------------------------------------------------------------------------
# Page setup
# -------------------------------------------------------------------------

st.set_page_config(
    page_title="Drift Sentinel",
    layout="wide",
    page_icon=None,
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).parent.parent / "data"
DRIFT_DAY = 60
TOTAL_DAYS = 90


@st.cache_data
def load_data():
    inf = pd.read_csv(DATA_DIR / "inference_logs.csv")
    inf["date"] = pd.to_datetime(inf["date"])
    inf["day"] = (inf["date"] - inf["date"].min()).dt.days
    models = pd.read_csv(DATA_DIR / "models.csv")
    events = pd.read_csv(DATA_DIR / "drift_events.csv")
    snaps = pd.read_csv(DATA_DIR / "vendor_snapshots.csv")
    return inf, models, events, snaps


inf, models_df, events_df, snaps_df = load_data()


# -------------------------------------------------------------------------
# Drift math
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


def ks_value(reference: np.ndarray, current: np.ndarray) -> float:
    reference = reference[~pd.isna(reference)]
    current = current[~pd.isna(current)]
    if len(reference) == 0 or len(current) == 0:
        return float("nan")
    return float(ks_2samp(reference, current).statistic)


def status_label(psi_val: float) -> str:
    if pd.isna(psi_val):
        return "N/A"
    if psi_val < 0.10:
        return "GREEN"
    if psi_val < 0.25:
        return "YELLOW"
    return "RED"


def status_color(label: str) -> str:
    return {"GREEN": "#1f9d55", "YELLOW": "#d6a700", "RED": "#c92a2a", "N/A": "#666"}[label]


def features_for(model_id: str) -> list[str]:
    if model_id in ("credit_pd_v3", "credit_loss_v2", "heloc_pd_v1", "auto_pd_v4"):
        return ["feature_dti", "feature_fico", "feature_ltv", "prediction"]
    if model_id == "fraud_card_v7":
        return ["feature_dti", "feature_fico", "prediction"]
    if model_id == "fraud_ach_v3":
        return ["feature_fico", "prediction"]
    if model_id == "aml_sar_v2":
        return ["prediction"]
    if model_id == "support_qa_v2":
        return ["feature_dti", "feature_fico", "feature_ltv", "prediction"]
    return []


def feature_label(model_id: str, col: str) -> str:
    """Map the schema's narrow column names to the meaning per model."""
    mapping = {
        ("credit_pd_v3", "feature_dti"): "DTI",
        ("credit_pd_v3", "feature_fico"): "FICO",
        ("credit_pd_v3", "feature_ltv"): "LTV",
        ("credit_pd_v3", "prediction"): "PD score",
        ("fraud_card_v7", "feature_dti"): "Velocity",
        ("fraud_card_v7", "feature_fico"): "Txn amount",
        ("fraud_card_v7", "prediction"): "Fraud score",
        ("support_qa_v2", "feature_dti"): "Refusal flag",
        ("support_qa_v2", "feature_fico"): "Response length",
        ("support_qa_v2", "feature_ltv"): "Groundedness",
        ("support_qa_v2", "prediction"): "Groundedness score",
    }
    return mapping.get((model_id, col), col.replace("feature_", "").upper())


def compute_drift_for(model_id: str, ref_window: tuple[int, int],
                      cur_window: tuple[int, int], induced_drift: bool) -> pd.DataFrame:
    sub = inf[inf["model_id"] == model_id].copy()
    if not induced_drift:
        # Use only pre-drift days for both reference and current windows.
        sub = sub[sub["day"] < DRIFT_DAY]
    ref = sub[(sub["day"] >= ref_window[0]) & (sub["day"] < ref_window[1])]
    cur = sub[(sub["day"] >= cur_window[0]) & (sub["day"] < cur_window[1])]
    out = []
    for col in features_for(model_id):
        if col not in sub.columns:
            continue
        p = psi(ref[col].values, cur[col].values)
        k = ks_value(ref[col].values, cur[col].values)
        out.append({
            "feature": feature_label(model_id, col),
            "raw_col": col,
            "psi": p,
            "ks": k,
            "status": status_label(p),
        })
    return pd.DataFrame(out)


def fleet_health(induced_drift: bool, ref_window: tuple[int, int],
                 cur_window: tuple[int, int]) -> pd.DataFrame:
    rows = []
    for _, m in models_df.iterrows():
        d = compute_drift_for(m["model_id"], ref_window, cur_window, induced_drift)
        worst_psi = d["psi"].max() if not d.empty else 0.0
        worst_status = status_label(worst_psi)
        rows.append({
            "model_id": m["model_id"],
            "name": m["name"],
            "family": m["family"],
            "tier": m["tier"],
            "vendor": m["vendor"],
            "owner": m["owner"],
            "worst_psi": round(worst_psi, 3),
            "status": worst_status,
            "snapshot_id": m["snapshot_id"],
        })
    return pd.DataFrame(rows)


def vendor_silent_for(model_id: str) -> pd.DataFrame:
    return snaps_df[
        (snaps_df["observed_in_fleet"] == model_id) &
        (snaps_df["announcement_status"].isin(["silent_minor_update", "acknowledged_post_hoc"]))
    ]


# -------------------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## Drift Sentinel")
    st.caption("Project 01 · BFSI · MRM · Vijay Saharan")
    st.divider()

    selected_model = st.selectbox(
        "Model",
        options=models_df["model_id"].tolist(),
        index=0,
    )

    day_range = st.slider(
        "Date range (day index from 2026-01-01)",
        min_value=0, max_value=TOTAL_DAYS, value=(0, 90), step=1,
    )

    induce_drift = st.toggle("Induce drift on day 60 (demo)", value=True,
                             help="Off: replay only the pre-drift first 60 days. "
                                  "On: full 90 days, drift event injected on Day 60.")

    st.divider()
    st.caption("**Reference window:** days 0–30")
    st.caption("**Current window:** days 60–90 if drift induced, else 30–60")

    ref_window = (0, 30)
    cur_window = (60, 90) if induce_drift else (30, 60)

    st.divider()
    st.caption("Stack: Evidently AI primitives, NannyML for delayed-truth, "
               "MLflow registry, Snowflake reference store, Temporal for the "
               "decide-loop workflow, Langfuse for the GenAI traces.")


# -------------------------------------------------------------------------
# Header
# -------------------------------------------------------------------------

st.title("Production Model Drift Sentinel")
st.caption("Three loops — Detect, Diagnose, Decide — across credit, fraud, AML, and GenAI.")

# Headline KPIs
fleet_df = fleet_health(induce_drift, ref_window, cur_window)
red_count = int((fleet_df["status"] == "RED").sum())
yellow_count = int((fleet_df["status"] == "YELLOW").sum())
green_count = int((fleet_df["status"] == "GREEN").sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric("Models monitored", len(fleet_df), delta=None)
k2.metric("Drifting (red)", red_count, delta=f"{red_count} of {len(fleet_df)}")
k3.metric("Watch (yellow)", yellow_count)
k4.metric("Median MTTD", "9 d", delta="-69 d vs SOTA",
          help="Drift Sentinel median time-to-detect across the pilot fleet, "
               "modeled against an industry baseline of 78 days.")

st.divider()


# -------------------------------------------------------------------------
# Tabs
# -------------------------------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs(["Live Fleet", "Detect", "Diagnose", "Decide"])


# ---- Tab 1 — Live Fleet ----
with tab1:
    st.subheader("Live fleet — drift health by model")
    st.caption("Status badge reflects worst feature-level PSI across the model's tracked inputs.")

    cols = st.columns(4)
    for i, row in fleet_df.iterrows():
        with cols[i % 4]:
            color = status_color(row["status"])
            tier_badge = f"Tier {row['tier']}"
            vendor_badge = row["vendor"].upper()
            silent = vendor_silent_for(row["model_id"])
            silent_badge = " · VENDOR-DIFF" if not silent.empty and induce_drift else ""
            st.markdown(
                f"""
                <div style="border:1px solid #2a2a2a;border-left:5px solid {color};
                            border-radius:6px;padding:14px;margin-bottom:12px;">
                  <div style="font-weight:600;font-size:15px;">{row['name']}</div>
                  <div style="color:#888;font-size:12px;margin-bottom:8px;">
                    {row['model_id']} · {tier_badge} · {vendor_badge}{silent_badge}
                  </div>
                  <div style="color:{color};font-weight:700;font-size:14px;">
                    {row['status']}
                  </div>
                  <div style="color:#aaa;font-size:12px;">
                    Worst PSI: {row['worst_psi']}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("##### Fleet table")
    show_df = fleet_df[["model_id", "name", "family", "tier", "vendor", "owner",
                        "worst_psi", "status", "snapshot_id"]]
    st.dataframe(show_df, use_container_width=True, hide_index=True)


# ---- Tab 2 — Detect ----
with tab2:
    st.subheader(f"Detect — PSI/KS time-series · {selected_model}")
    st.caption("Reference: days 0–30. Each bar shows PSI on a 7-day rolling current window.")

    sub = inf[inf["model_id"] == selected_model].copy()
    if not induce_drift:
        sub = sub[sub["day"] < DRIFT_DAY]

    feat_cols = features_for(selected_model)
    feature_pick = st.selectbox(
        "Feature",
        options=feat_cols,
        format_func=lambda c: feature_label(selected_model, c),
    )

    ref_vals = sub[(sub["day"] >= 0) & (sub["day"] < 30)][feature_pick].values
    psi_series = []
    ks_series = []
    days_series = []
    for d_end in range(7, sub["day"].max() + 1):
        cur_vals = sub[(sub["day"] >= d_end - 7) & (sub["day"] < d_end)][feature_pick].values
        psi_series.append(psi(ref_vals, cur_vals))
        ks_series.append(ks_value(ref_vals, cur_vals))
        days_series.append(d_end)

    ts = pd.DataFrame({"day": days_series, "PSI": psi_series, "KS": ks_series})

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ts["day"], y=ts["PSI"], mode="lines+markers",
                             name="PSI", line=dict(color="#4f86f7", width=2)))
    fig.add_trace(go.Scatter(x=ts["day"], y=ts["KS"], mode="lines+markers",
                             name="KS", line=dict(color="#c0a000", width=2, dash="dot"),
                             yaxis="y2"))
    fig.add_hline(y=0.10, line_dash="dash", line_color="#999",
                  annotation_text="PSI watch (0.10)", annotation_position="right")
    fig.add_hline(y=0.25, line_dash="dash", line_color="#c92a2a",
                  annotation_text="PSI drift (0.25)", annotation_position="right")
    if induce_drift:
        fig.add_vline(x=DRIFT_DAY, line_dash="dash", line_color="#ff6b35",
                      annotation_text="Drift event (Day 60)", annotation_position="top")
    fig.update_layout(
        height=420,
        yaxis=dict(title="PSI"),
        yaxis2=dict(title="KS", overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.1),
        margin=dict(t=40, b=40, l=40, r=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("##### Vendor snapshot history")
    if selected_model == "support_qa_v2":
        show = snaps_df[snaps_df["observed_in_fleet"] == selected_model][
            ["snapshot_date", "vendor", "snapshot_id", "announcement_status", "notes"]]
        st.dataframe(show, use_container_width=True, hide_index=True)
    else:
        st.caption("Internal model — no vendor snapshot lineage to track.")


# ---- Tab 3 — Diagnose ----
with tab3:
    st.subheader(f"Diagnose — drivers and slices · {selected_model}")

    drift_df = compute_drift_for(selected_model, ref_window, cur_window, induce_drift)

    if drift_df.empty:
        st.info("No features to diagnose for this model.")
    else:
        c1, c2 = st.columns([3, 2])

        with c1:
            st.markdown("###### Feature contribution")
            colors = [status_color(s) for s in drift_df["status"]]
            fig = go.Figure(go.Bar(
                x=drift_df["psi"], y=drift_df["feature"], orientation="h",
                marker=dict(color=colors),
                hovertemplate="PSI=%{x:.3f}<extra></extra>",
            ))
            fig.add_vline(x=0.10, line_dash="dash", line_color="#999")
            fig.add_vline(x=0.25, line_dash="dash", line_color="#c92a2a")
            fig.update_layout(
                height=320, margin=dict(t=20, b=20, l=10, r=10),
                xaxis_title="PSI (current window vs reference)",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("###### Segment slicer")
            sub = inf[inf["model_id"] == selected_model].copy()
            if not induce_drift:
                sub = sub[sub["day"] < DRIFT_DAY]
            segs = sorted(sub["segment"].dropna().unique().tolist())
            top = drift_df.iloc[drift_df["psi"].idxmax()]
            top_col = top["raw_col"]
            seg_pick = st.selectbox("Segment", options=["(all)"] + segs, index=0)
            ref_seg = sub[(sub["day"] >= ref_window[0]) & (sub["day"] < ref_window[1])]
            cur_seg = sub[(sub["day"] >= cur_window[0]) & (sub["day"] < cur_window[1])]
            if seg_pick != "(all)":
                ref_seg = ref_seg[ref_seg["segment"] == seg_pick]
                cur_seg = cur_seg[cur_seg["segment"] == seg_pick]
            seg_psi = psi(ref_seg[top_col].values, cur_seg[top_col].values)
            seg_status = status_label(seg_psi)
            st.metric(
                f"PSI on {top['feature']} · {seg_pick}",
                f"{seg_psi:.3f}",
                delta=seg_status,
                delta_color="off",
            )
            st.caption(
                f"Aggregate PSI on {top['feature']} is {top['psi']:.3f}. "
                f"Try the subprime slice on credit_pd_v3 to see the slice-vs-aggregate gap."
            )

        st.markdown("###### Distribution overlay")
        sub = inf[inf["model_id"] == selected_model].copy()
        if not induce_drift:
            sub = sub[sub["day"] < DRIFT_DAY]
        ref_vals = sub[(sub["day"] >= ref_window[0]) & (sub["day"] < ref_window[1])][top_col].dropna().values
        cur_vals = sub[(sub["day"] >= cur_window[0]) & (sub["day"] < cur_window[1])][top_col].dropna().values
        dist_df = pd.DataFrame({
            "value": np.concatenate([ref_vals, cur_vals]),
            "window": ["Reference (0-30)"] * len(ref_vals) + ["Current"] * len(cur_vals),
        })
        fig = px.histogram(
            dist_df, x="value", color="window", barmode="overlay", nbins=40,
            color_discrete_map={"Reference (0-30)": "#4f86f7", "Current": "#ff6b35"},
        )
        fig.update_traces(opacity=0.55)
        fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10),
                          xaxis_title=top["feature"])
        st.plotly_chart(fig, use_container_width=True)

        # Lineage callout
        st.markdown("###### Upstream lineage")
        lineage = {
            "credit_pd_v3":  ("feature_pipeline.dti_v2025_11 deployed Day 58 — "
                              "DTI normalization changed from log1p to standard scale. "
                              "Correlates with drift onset Day 60. Source: Unity Catalog."),
            "fraud_card_v7": ("No upstream pipeline change in the 14-day window. "
                              "Drift attributable to traffic distribution; "
                              "adversary tactic shift likely. Source: lineage walk + "
                              "fraud-ops monthly report."),
            "support_qa_v2": ("No internal upstream change. Vendor snapshot ID "
                              "changed Day 60 (claude-sonnet-4-20251101 → "
                              "claude-sonnet-4-20260214). Cross-judge gpt-4o agrees "
                              "behavior shifted. Source: vendor-version diff."),
        }
        text = lineage.get(selected_model,
                           "No upstream pipeline change in the 14-day window. "
                           "Lineage walk found no correlated event.")
        st.info(text)


# ---- Tab 4 — Decide ----
with tab4:
    st.subheader(f"Decide — bounded recommendation · {selected_model}")

    drift_df = compute_drift_for(selected_model, ref_window, cur_window, induce_drift)
    silent = vendor_silent_for(selected_model)
    has_silent = (not silent.empty) and induce_drift

    sub = inf[inf["model_id"] == selected_model].copy()
    if not induce_drift:
        sub = sub[sub["day"] < DRIFT_DAY]

    # Best-segment PSI on top feature
    top_psi = drift_df["psi"].max() if not drift_df.empty else 0.0
    top_row = drift_df.iloc[drift_df["psi"].idxmax()] if not drift_df.empty else None
    worst_seg_psi = 0.0
    if top_row is not None:
        for seg in sub["segment"].dropna().unique():
            ref_s = sub[(sub["day"] >= ref_window[0]) & (sub["day"] < ref_window[1]) & (sub["segment"] == seg)]
            cur_s = sub[(sub["day"] >= cur_window[0]) & (sub["day"] < cur_window[1]) & (sub["segment"] == seg)]
            seg_psi = psi(ref_s[top_row["raw_col"]].values, cur_s[top_row["raw_col"]].values)
            if not pd.isna(seg_psi) and seg_psi > worst_seg_psi:
                worst_seg_psi = seg_psi

    # Decide
    if has_silent:
        decision, color = "ROLLBACK", status_color("RED")
        reason = (f"Vendor snapshot changed silently to "
                  f"{silent.iloc[-1]['snapshot_id']}. "
                  "GenAI proxy portfolio (refusal +6pp, length distribution "
                  "shifted, groundedness -0.10) confirms behavior change. Pin "
                  "to previous snapshot until probe suite re-runs clean.")
        envelope = ("If pinned snapshot fails probe re-run, escalate to "
                    "RETRAIN of downstream RAG layer.")
    elif top_psi >= 0.25:
        decision, color = "RETRAIN", status_color("RED")
        reason = (f"Aggregate PSI {top_psi:.3f} crosses red threshold; "
                  "performance proxy regressing.")
        envelope = ("Candidate must hold AUC within -0.5pp of incumbent "
                    "on backtest before promotion. If not, ROLLBACK to N-1.")
    elif worst_seg_psi >= 0.25:
        decision, color = "SHADOW", status_color("YELLOW")
        reason = (f"Aggregate PSI {top_psi:.3f} within attested envelope; "
                  f"slice PSI {worst_seg_psi:.3f} crosses red. Deploy "
                  "candidate alongside, monitor slice for 14 days.")
        envelope = "If slice PSI > 0.40 sustained for 7 days, escalate to RETRAIN."
    else:
        decision, color = "RETAIN", status_color("GREEN")
        reason = f"Aggregate PSI {top_psi:.3f} within attested envelope."
        envelope = "Continue continuous monitoring; re-evaluate at next window."

    st.markdown(
        f"""
        <div style="border:1px solid #2a2a2a;border-left:6px solid {color};
                    border-radius:8px;padding:18px;margin-bottom:18px;">
          <div style="color:{color};font-weight:700;font-size:22px;">{decision}</div>
          <div style="margin-top:8px;font-size:14px;line-height:1.5;">{reason}</div>
          <div style="margin-top:10px;color:#888;font-size:13px;">
            <b>Risk envelope:</b> {envelope}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Top feature PSI", f"{top_psi:.3f}")
    c2.metric("Worst slice PSI", f"{worst_seg_psi:.3f}")
    c3.metric("Vendor silent update?", "yes" if has_silent else "no")

    # Evidence bundle
    model_row = models_df[models_df["model_id"] == selected_model].iloc[0].to_dict()
    bundle = {
        "bundle_version": "1.0",
        "assembled_at": datetime(2026, 4, 28, 9, 0, 0).isoformat(),
        "model": {
            "model_id": model_row["model_id"],
            "name": model_row["name"],
            "tier": int(model_row["tier"]),
            "owner_line1": model_row["owner"],
            "vendor": model_row["vendor"],
            "snapshot_id": model_row["snapshot_id"],
            "deployed_date": model_row["deployed_date"],
            "last_attested": model_row["last_attested"],
        },
        "detect": {
            "classical_drift": [
                {"feature": r["feature"], "psi": round(float(r["psi"]), 4),
                 "ks": round(float(r["ks"]), 4), "status": r["status"]}
                for _, r in drift_df.iterrows()
            ],
            "vendor_silent_updates": (
                silent[["snapshot_date", "snapshot_id", "announcement_status"]]
                .to_dict(orient="records") if has_silent else []
            ),
        },
        "diagnose": {
            "top_feature": top_row["feature"] if top_row is not None else None,
            "aggregate_psi": round(top_psi, 4),
            "worst_slice_psi": round(worst_seg_psi, 4),
        },
        "decide": {
            "decision": decision,
            "reason": reason,
            "risk_envelope": envelope,
        },
        "validator_routing": "MRM L2 — Tier-1 queue",
        "audit_trail_handoff": "Project 08 — lineage event emitted",
        "attestation_template_prefilled": True,
        "human_edit_before_signoff": True,
    }

    with st.expander("MRM evidence bundle (auto-assembled — preview)", expanded=False):
        st.json(bundle)

    with st.expander("Comparable Step-1 quarterly attestation (the world before this product)"):
        st.code(
            f"""QUARTERLY MODEL ATTESTATION — {model_row['name']}
Model:           {model_row['model_id']}
Tier:            {model_row['tier']}
Vendor:          {model_row['vendor']} / {model_row['snapshot_id']}
Last attested:   {model_row['last_attested']}
Ongoing monitoring plan:  Monthly PSI review by model owner. (not enforced)
Validator sign-off:       on file (Word doc, p. 28)
""",
            language="text",
        )


# -------------------------------------------------------------------------
# Footer — utility math
# -------------------------------------------------------------------------

st.divider()

with st.container():
    st.markdown("##### Utility math")
    st.markdown(
        """
        **The way I price product impact: utility = (my solution − SOTA) × people it affects.**

        - SOTA median drift MTTD: **78 days** (industry baseline).
        - Drift Sentinel median MTTD: **9 days**.
        - Per-model lift: **~69 days** caught earlier.
        - Affected: **800–1,500 production models** per Tier-1 BFSI fleet.
        - **~83,000 model-decay-days prevented per year** at fleet scale.
        - Modeled prevented loss: **~$14M/yr** at the partner-bank shape (modeled, not measured).
        - Cost: **$1.2–2.4M/yr** software, plus a 4–6 person ops team.

        Drift MTTD: 78d → 9d × 800–1,500 production models = ~83,000 model-decay-days prevented annually at fleet scale.
        """
    )

    st.caption(
        "Numbers are modeled at the $50B-asset retail-bank shape. Every shop is "
        "different. The point is the structure: catching decay 69 days earlier, "
        "across the whole fleet, is the unit of value — not the PSI dashboard."
    )
