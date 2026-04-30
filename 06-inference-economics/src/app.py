"""
AI Inference Economics Dashboard — Streamlit Prototype
Author: Vijay Saharan
Run: streamlit run app.py

Demonstrates the three-loop FinOps surface (Meter → Compare → Govern) over
90 days of synthetic inference traffic across five deployed features. Tabs
for cost decomposition, model-mix, cost-quality frontier, and budget guard.
"""

import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# Synthetic inference traffic — 5 features × 90 days
# -----------------------------------------------------------------------------

np.random.seed(7)
DAYS = 90
START = datetime(2026, 1, 1)

# Vendor model pricing (synthetic, $ per 1K tokens — input + output blended)
PRICING = {
    "gpt-4-class":    {"vendor": "VendorA", "in": 0.010, "out": 0.030, "quality": 0.92},
    "gpt-3.5-class":  {"vendor": "VendorA", "in": 0.0005, "out": 0.0015, "quality": 0.81},
    "claude-class":   {"vendor": "VendorB", "in": 0.008, "out": 0.024, "quality": 0.93},
    "haiku-class":    {"vendor": "VendorB", "in": 0.00025, "out": 0.00125, "quality": 0.79},
    "open-weight-7b": {"vendor": "Internal", "in": 0.0001, "out": 0.0004, "quality": 0.74},
}

FEATURES = [
    {"id": "support_copilot",  "segment_mix": {"retail": 0.7, "smb": 0.3},
     "default_model": "gpt-4-class",   "calls_per_day": 5200, "avg_in": 900, "avg_out": 320, "adoption": 0.72},
    {"id": "internal_research", "segment_mix": {"investment": 0.5, "credit": 0.5},
     "default_model": "claude-class",  "calls_per_day": 1100, "avg_in": 1800, "avg_out": 700, "adoption": 0.61},
    {"id": "fraud_narrative",   "segment_mix": {"ops": 1.0},
     "default_model": "gpt-4-class",   "calls_per_day": 3300, "avg_in": 1200, "avg_out": 240, "adoption": 0.88},
    {"id": "kyc_summary",       "segment_mix": {"onboarding": 1.0},
     "default_model": "gpt-3.5-class", "calls_per_day": 2200, "avg_in": 1400, "avg_out": 280, "adoption": 0.66},
    {"id": "rm_prep_brief",     "segment_mix": {"wealth": 1.0},
     "default_model": "claude-class",  "calls_per_day": 380,  "avg_in": 2200, "avg_out": 950, "adoption": 0.18},  # dead-feature candidate
]


def gen_traffic():
    rows = []
    for d in range(DAYS):
        date = START + timedelta(days=d)
        for f in FEATURES:
            # call volume with adoption + slight growth + a runaway on day 55 for support_copilot
            n = int(f["calls_per_day"] * f["adoption"] * (1 + 0.002 * d))
            if f["id"] == "support_copilot" and d >= 55:
                n = int(n * 2.4)  # runaway prompt explosion
            for seg, share in f["segment_mix"].items():
                seg_n = int(n * share)
                in_tok = np.random.normal(f["avg_in"], f["avg_in"] * 0.15, seg_n).clip(50, None)
                out_tok = np.random.normal(f["avg_out"], f["avg_out"] * 0.20, seg_n).clip(20, None)
                # 10% of traffic on cheaper model already (mixed)
                models = np.where(np.random.random(seg_n) < 0.1,
                                  "gpt-3.5-class" if "gpt" in f["default_model"] else "haiku-class",
                                  f["default_model"])
                for i in range(seg_n):
                    p = PRICING[models[i]]
                    cost = (in_tok[i] / 1000) * p["in"] + (out_tok[i] / 1000) * p["out"]
                    rows.append({
                        "date": date, "feature": f["id"], "segment": seg,
                        "model": models[i], "vendor": p["vendor"],
                        "in_tok": in_tok[i], "out_tok": out_tok[i],
                        "cost": cost,
                    })
    return pd.DataFrame(rows)


@st.cache_data
def load():
    return gen_traffic()


df = load()

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

st.set_page_config(page_title="AI Inference Economics", layout="wide")
st.title("AI Inference Economics Dashboard")
st.caption("Project 06 · AI Platform · FinOps · BFSI — Vijay Saharan")

with st.sidebar:
    st.header("Loops")
    st.markdown("**Meter → Compare → Govern**")
    feature_filter = st.multiselect("Feature", sorted(df["feature"].unique()),
                                     default=sorted(df["feature"].unique()))
    seg_filter = st.multiselect("Segment", sorted(df["segment"].unique()),
                                 default=sorted(df["segment"].unique()))
    st.divider()
    st.caption("90 days synthetic traffic, 5 features, 5 models, 3 vendors")

filtered = df[(df["feature"].isin(feature_filter)) & (df["segment"].isin(seg_filter))]

# Headline metrics
total_spend = filtered["cost"].sum()
total_calls = len(filtered)
avg_cost = total_spend / max(total_calls, 1)

c1, c2, c3, c4 = st.columns(4)
c1.metric("90-day spend", f"${total_spend:,.0f}")
c2.metric("Total calls", f"{total_calls:,}")
c3.metric("Avg $/call", f"${avg_cost:.4f}")
c4.metric("Features metered", f"{filtered['feature'].nunique()}/{df['feature'].nunique()}")

tab1, tab2, tab3, tab4 = st.tabs(
    ["Cost decomposition", "Model mix", "Cost-quality frontier", "Budget guard"])

# -----------------------------------------------------------------------------
# Tab 1 — Cost decomposition
# -----------------------------------------------------------------------------
with tab1:
    st.subheader("Loop 1 · Meter")
    by_feat = filtered.groupby("feature")["cost"].sum().reset_index().sort_values("cost", ascending=False)
    st.bar_chart(by_feat, x="feature", y="cost", height=260)
    st.markdown("**By segment**")
    by_seg = filtered.groupby(["feature", "segment"])["cost"].sum().reset_index()
    st.dataframe(by_seg.pivot(index="feature", columns="segment", values="cost").fillna(0).round(0),
                 use_container_width=True)
    st.markdown("**Daily spend trend (anomaly = runaway feature)**")
    daily = filtered.groupby(["date", "feature"])["cost"].sum().reset_index()
    pivot = daily.pivot(index="date", columns="feature", values="cost").fillna(0)
    st.line_chart(pivot, height=260)
    st.caption("support_copilot runaway visible from day 55 — ungoverned prompt expansion.")

# -----------------------------------------------------------------------------
# Tab 2 — Model mix
# -----------------------------------------------------------------------------
with tab2:
    st.subheader("Loop 2 · Compare — model mix")
    mix = filtered.groupby(["feature", "model"])["cost"].sum().reset_index()
    st.dataframe(mix.pivot(index="feature", columns="model", values="cost").fillna(0).round(0),
                 use_container_width=True)
    by_vendor = filtered.groupby("vendor")["cost"].sum().reset_index()
    st.bar_chart(by_vendor, x="vendor", y="cost", height=240)
    st.caption("Model-mix is a product decision per feature × segment, not a default.")

# -----------------------------------------------------------------------------
# Tab 3 — Cost-quality frontier
# -----------------------------------------------------------------------------
with tab3:
    st.subheader("Loop 2 · Compare — cost-quality frontier")
    rows = []
    for model, p in PRICING.items():
        rows.append({"model": model, "$/1k_blended": p["in"] * 0.7 + p["out"] * 0.3,
                     "quality_score": p["quality"]})
    fr = pd.DataFrame(rows)
    st.scatter_chart(fr, x="$/1k_blended", y="quality_score", size="quality_score", height=320)
    st.dataframe(fr.sort_values("quality_score", ascending=False), use_container_width=True)

    st.markdown("### Substitution simulator")
    feat = st.selectbox("Feature", sorted(filtered["feature"].unique()))
    candidate = st.selectbox("Candidate cheaper model",
                              [m for m in PRICING if m != "gpt-4-class"], index=0)
    feat_df = filtered[filtered["feature"] == feat]
    current_cost = feat_df["cost"].sum()
    p_cand = PRICING[candidate]
    cand_cost = ((feat_df["in_tok"].sum() / 1000) * p_cand["in"]
                 + (feat_df["out_tok"].sum() / 1000) * p_cand["out"])
    saved = current_cost - cand_cost
    quality_delta = p_cand["quality"] - PRICING[FEATURES[
        [f["id"] for f in FEATURES].index(feat)]["default_model"]]["quality"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Current spend", f"${current_cost:,.0f}")
    c2.metric("Candidate spend", f"${cand_cost:,.0f}",
              delta=f"-${saved:,.0f}" if saved > 0 else f"+${-saved:,.0f}")
    c3.metric("Quality delta", f"{quality_delta:+.2f}")
    if quality_delta < -0.05:
        st.warning("Quality drop > 5pts — require eval evidence and shadow-mode test before promoting.")
    else:
        st.success("Within tolerance — schedule shadow-mode test for 14 days.")

# -----------------------------------------------------------------------------
# Tab 4 — Budget guard
# -----------------------------------------------------------------------------
with tab4:
    st.subheader("Loop 3 · Govern — budget guard")
    feat = st.selectbox("Feature for envelope check", sorted(df["feature"].unique()), key="guard")
    monthly_envelope = st.number_input("Monthly envelope ($)", min_value=1000, value=80000, step=1000)
    feat_df = df[df["feature"] == feat].copy()
    feat_df["month"] = feat_df["date"].dt.to_period("M")
    monthly = feat_df.groupby("month")["cost"].sum().reset_index()
    monthly["pct_envelope"] = monthly["cost"] / monthly_envelope * 100

    def status(p):
        if p >= 100: return "BREACH — auto-throttle"
        if p >= 80:  return "Warn 80%"
        if p >= 60:  return "Notice 60%"
        return "OK"

    monthly["status"] = monthly["pct_envelope"].apply(status)
    st.dataframe(monthly, use_container_width=True)
    breach = monthly[monthly["pct_envelope"] >= 100]
    if not breach.empty:
        st.error(f"Envelope breach in {len(breach)} month(s) — kill-switch routed to feature owner.")
    else:
        st.success("All months within envelope.")

    st.markdown("### Dead-feature monitor")
    adoption_floor = st.slider("Adoption floor", 0.0, 1.0, 0.30, 0.05)
    dead = [f for f in FEATURES if f["adoption"] < adoption_floor]
    if dead:
        st.warning(f"Below floor: {', '.join(f['id'] for f in dead)} — kill-review queued.")
    else:
        st.success("No features below adoption floor.")

st.divider()
st.caption(
    "Prototype demonstrates the FinOps mechanic. In production: gateway metering "
    "(Project 05), per-vendor invoice reconciliation, eval-evidence link on every "
    "model swap (Project 02), and audit events to Project 08."
)
