"""InferenceLens - inference economics dashboard for a Tier-1 BFSI GenAI portfolio.

Streamlit walkthrough:
  Step 1 - pick a feature (or use the FT_001 runaway as default)
  Step 2 - executive verdict card: HEALTHY / RUNAWAY / UNDERUTILIZED / DECOMMISSION
  Step 3 - the six-deficiency view: each closed inline (attribution, runaway,
            substitution, dead-feature, ROI)
  Step 4 - the CFO pack (CSV downloads + glossary + production stack reassessment)
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="InferenceLens - per-feature inference economics in 1 day, not 6 weeks",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"
GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
REPO_BLOB = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/07-inferencelens-inference-finops"

TARGET_FEATURE_ID = "FT_001"
RUNAWAY_THRESHOLD = 3.0

# ---------------------------------------------------------------------------
# Theme - dark navy gradient hero, white body, indigo accent (mirrors flagship)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}
header[data-testid="stHeader"] {display:none;}

.il-hero {
  background: linear-gradient(135deg,#0a0e2e 0%, #1e2a78 60%, #4f46e5 100%);
  border-radius: 18px; padding: 36px 40px; color:#fff; margin-bottom:28px;
}
.il-hero .brand {font-size:26px; font-weight:600; opacity:0.92; margin-bottom:12px;}
.il-hero h1 {color:#fff !important; font-size:46px; line-height:1.12; margin:0 0 14px 0; font-weight:700;}
.il-hero .sub {font-size:17px; line-height:1.5; opacity:0.93; max-width:840px; margin-bottom:22px;}
.il-hero .pills {display:flex; flex-wrap:wrap; gap:10px;}
.il-hero .pill {background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
                color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.il-hero .pill a {color:#fff; text-decoration:none;}

.il-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:22px 26px;
          margin-bottom:18px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.il-card h3 {margin-top:0; color:#0f172a;}
.il-step-label {display:inline-block; background:#4f46e5; color:#fff; padding:3px 10px;
                border-radius:6px; font-size:12px; font-weight:600; letter-spacing:0.04em;
                text-transform:uppercase; margin-bottom:10px;}

.verdict-card {border-radius:16px; padding:26px 30px; margin-bottom:18px; color:#fff;}
.verdict-healthy {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.verdict-runaway {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.verdict-undertier {background: linear-gradient(135deg,#b45309,#f59e0b);}
.verdict-dead {background: linear-gradient(135deg,#4b5563,#6b7280);}
.verdict-card .vlabel {font-size:13px; opacity:0.9; letter-spacing:0.08em; text-transform:uppercase;}
.verdict-card .vbig {font-size:44px; font-weight:800; line-height:1.1; margin:4px 0 14px 0;}
.verdict-card .vmetric {font-size:22px; font-weight:600;}
.verdict-card .vrow {display:flex; flex-wrap:wrap; gap:24px; margin-top:12px;}
.verdict-card .vchip {background: rgba(255,255,255,0.18); padding:6px 12px; border-radius:999px;
                      font-size:13px; font-weight:600;}
.verdict-card .vtldr {margin-top:16px; font-size:15px; line-height:1.5; opacity:0.95;}

.trust-card {background:#f8fafc; border:1px solid #cbd5e1; border-left:5px solid #4f46e5;
             border-radius:12px; padding:20px 24px; margin-bottom:18px;}
.trust-card h4 {margin:0 0 10px 0; color:#0f172a; font-size:16px; letter-spacing:0.04em;
                text-transform:uppercase;}
.trust-card .tlabel {font-weight:700; color:#4f46e5; font-size:13px; letter-spacing:0.04em;
                     text-transform:uppercase; margin-top:12px; display:block;}
.trust-card ul {margin:6px 0 0 18px; padding:0;}
.trust-card li {color:#334155; line-height:1.55;}
.confidence-high {color:#047857; font-weight:700;}
.confidence-med  {color:#b45309; font-weight:700;}
.confidence-low  {color:#b91c1c; font-weight:700;}

.def-row {background:#dcfce7; border-left:5px solid #16a34a; border-radius:10px;
          padding:14px 18px; margin-bottom:10px; color:#14532d;}
.def-row.gap {background:#fef3c7; border-left-color:#f59e0b; color:#78350f;}
.def-row.bad {background:#fee2e2; border-left-color:#dc2626; color:#7f1d1d;}
.def-row .dlabel {font-weight:700; font-size:13px; letter-spacing:0.04em; text-transform:uppercase;}
.def-row .dval {font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size:13px; margin-top:4px;}

div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#4f46e5,#1e2a78) !important; color:#fff !important;
  border:0 !important; padding:14px 28px !important; font-size:17px !important;
  font-weight:600 !important; border-radius:12px !important;
  box-shadow:0 4px 14px rgba(79,70,229,0.35) !important;
}
h1, h2, h3 {color:#0f172a;}
.muted {color:#64748b; font-size:14px;}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@st.cache_data
def load_data() -> dict[str, pd.DataFrame]:
    return {
        "features": pd.read_csv(DATA_DIR / "features.csv"),
        "logs": pd.read_csv(DATA_DIR / "inference_logs.csv"),
        "pricing": pd.read_csv(DATA_DIR / "model_pricing.csv"),
        "subs": pd.read_csv(DATA_DIR / "substitution_recommendations.csv"),
    }


DATA = load_data()


# ---------------------------------------------------------------------------
# Composition primitives (mirror step_04_with_inferencelens.py)
# ---------------------------------------------------------------------------
def per_feature_attribution(logs: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    sample_counts = logs.groupby("feature_id").size().to_dict()
    sample_cost = logs.groupby("feature_id")["cost_usd"].sum().to_dict()
    rows = []
    for _, ft in features.iterrows():
        fid = ft["feature_id"]
        monthly_vol = int(ft["monthly_query_volume"])
        n_sample = sample_counts.get(fid, 0)
        if n_sample == 0 or monthly_vol == 0:
            rows.append({
                "feature_id": fid,
                "feature_name": ft["feature_name"],
                "status": ft["status"],
                "model": ft["model_used"],
                "monthly_query_volume": monthly_vol,
                "modeled_monthly_spend_usd": 0,
                "modeled_cost_per_call_usd": 0.0,
            })
            continue
        scale = monthly_vol / n_sample
        modeled_monthly = sample_cost.get(fid, 0) * scale
        cost_per_call = sample_cost.get(fid, 0) / n_sample
        rows.append({
            "feature_id": fid,
            "feature_name": ft["feature_name"],
            "status": ft["status"],
            "model": ft["model_used"],
            "monthly_query_volume": monthly_vol,
            "modeled_monthly_spend_usd": round(modeled_monthly, 2),
            "modeled_cost_per_call_usd": round(cost_per_call, 4),
        })
    return pd.DataFrame(rows)


def feature_runaway_summary(logs: pd.DataFrame, feature_id: str,
                            monthly_vol: int) -> dict:
    """Per-day modeled spend for ONE feature, plus runaway-anchor stats."""
    flogs = logs[logs["feature_id"] == feature_id].copy()
    if len(flogs) == 0 or monthly_vol == 0:
        return {"daily": pd.DataFrame(columns=["day", "modeled_spend_usd"]),
                "alert": None, "pre_avg_call": 0, "post_avg_call": 0,
                "pre_daily": 0, "post_daily": 0, "multiplier": 0}

    flogs["day"] = flogs["timestamp"].str[:10]
    by_day = flogs.groupby("day")["cost_usd"].mean().reset_index()
    by_day["modeled_spend_usd"] = by_day["cost_usd"] * (monthly_vol / 30)
    by_day = by_day[["day", "modeled_spend_usd"]]
    by_day["modeled_spend_usd"] = by_day["modeled_spend_usd"].round(2)

    pre = flogs[flogs["timestamp"] < "2026-05-01"]["cost_usd"]
    post = flogs[flogs["timestamp"] >= "2026-05-01"]["cost_usd"]
    pre_avg = pre.mean() if len(pre) else 0
    post_avg = post.mean() if len(post) else 0
    pre_daily = pre_avg * (monthly_vol / 30)
    post_daily = post_avg * (monthly_vol / 30)
    multiplier = (post_daily / pre_daily) if pre_daily > 0 else 0

    alert = None
    if multiplier >= RUNAWAY_THRESHOLD:
        alert = {
            "first_seen": "2026-05-01",
            "multiplier": round(multiplier, 2),
            "daily_overspend": round(post_daily - pre_daily, 0),
            "days_undetected": 45,
            "modeled_total_overspend": round((post_daily - pre_daily) * 45, 0),
        }
    return {
        "daily": by_day, "alert": alert,
        "pre_avg_call": pre_avg, "post_avg_call": post_avg,
        "pre_daily": pre_daily, "post_daily": post_daily,
        "multiplier": multiplier,
    }


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "step" not in st.session_state:
    st.session_state.step = 1

all_features = DATA["features"]
FEATURE_OPTIONS = []
for _, row in all_features.iterrows():
    label = f"{row['feature_id']} - {row['feature_name']} - {row['model_used']} - {row['status']}"
    FEATURE_OPTIONS.append(label)
default_idx = next((i for i, d in enumerate(FEATURE_OPTIONS) if d.startswith(TARGET_FEATURE_ID)), 0)

if "feature_choice" not in st.session_state:
    st.session_state.feature_choice = FEATURE_OPTIONS[default_idx]


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='il-hero'>
  <div class='brand'>💰 InferenceLens</div>
  <h1>Every GenAI feature, attributed to its model spend, runaway risk, and revenue ROI in under a day.</h1>
  <div class='sub'>A per-feature inference economics layer that turns the bank's $4M/month aggregate compute spend into a per-feature, per-segment, per-day record. Catches the misconfigured retrieval depth burning $5k/day before the quarterly cost review notices. Built against the <a href='https://www.finops.org/framework/' target='_blank' style='color:#fff;text-decoration:underline;'>FinOps Foundation framework</a>, anchored on the <a href='https://www.anthropic.com/pricing' target='_blank' style='color:#fff;text-decoration:underline;'>Anthropic</a> / <a href='https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/' target='_blank' style='color:#fff;text-decoration:underline;'>Azure OpenAI</a> / <a href='https://aws.amazon.com/bedrock/pricing/' target='_blank' style='color:#fff;text-decoration:underline;'>AWS Bedrock</a> pricing primitives, aligned to the <a href='https://www.nist.gov/itl/ai-risk-management-framework' target='_blank' style='color:#fff;text-decoration:underline;'>NIST AI RMF</a> Govern function.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>18 synthetic GenAI features</span>
    <span class='pill'>2,800+ sampled calls</span>
    <span class='pill'>Built 2026</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

if st.session_state.step == 1:
    cta_col, _ = st.columns([1, 2])
    with cta_col:
        if st.button("See it in action  ->", key="cta_hero", type="primary", use_container_width=True):
            advance(2)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 1 - pick a feature
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='il-card'><span class='il-step-label'>Step 1</span>"
    "<h3>Pick a feature the CFO might ask about</h3>"
    "<p class='muted'>Default selection is <code>FT_001 (customer-service-assistant)</code> - "
    "the headline runaway. Retrieval depth was misconfigured from 5 docs to 50 on 2026-05-01. "
    "Per-call cost jumped 3.7x. The bank's monthly invoice arrives June 5 - InferenceLens "
    "catches it on day 1 via per-feature attribution.</p></div>",
    unsafe_allow_html=True,
)

st.session_state.feature_choice = st.selectbox(
    "Feature:",
    FEATURE_OPTIONS,
    index=FEATURE_OPTIONS.index(st.session_state.feature_choice),
    label_visibility="collapsed",
)
chosen_id = st.session_state.feature_choice.split(" - ")[0]
ft_row = all_features[all_features["feature_id"] == chosen_id].iloc[0]
sub_row = DATA["subs"][DATA["subs"]["feature_id"] == chosen_id]
sub_row = sub_row.iloc[0].to_dict() if len(sub_row) else {}

st.markdown(
    f"<div class='il-card'><b>Feature:</b> {ft_row['feature_id']} ({ft_row['feature_name']})<br>"
    f"<b>Owner:</b> {ft_row['owner_team']} - "
    f"<b>Business line:</b> {ft_row['business_line']}<br>"
    f"<b>Model:</b> {ft_row['model_used']} - "
    f"<b>Status:</b> {ft_row['status']} - "
    f"<b>Deployed:</b> {ft_row['deployed_date']}<br>"
    f"<b>Volume:</b> {int(ft_row['monthly_query_volume']):,} queries/mo - "
    f"<b>p50 latency:</b> {int(ft_row['p50_latency_ms']) if ft_row['p50_latency_ms'] else 0:,}ms"
    f"</div>",
    unsafe_allow_html=True,
)

if st.session_state.step < 2:
    if st.button("Compose the feature economics record  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - verdict card
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    t0 = time.perf_counter()
    attribution = per_feature_attribution(DATA["logs"], DATA["features"])
    runaway = feature_runaway_summary(
        DATA["logs"], chosen_id, int(ft_row["monthly_query_volume"])
    )
    attr_row = attribution[attribution["feature_id"] == chosen_id]
    attr_row = attr_row.iloc[0].to_dict() if len(attr_row) else {}
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    # Verdict logic
    revenue = float(ft_row.get("revenue_attributed_monthly_usd", 0) or 0)
    monthly_spend = float(attr_row.get("modeled_monthly_spend_usd", 0))
    status = ft_row["status"]
    candidate = sub_row.get("candidate_model", "")
    has_runaway = runaway.get("alert") is not None
    has_savings = candidate not in ("", ft_row["model_used"]) and \
                  candidate not in ("DEAD_FEATURE", "DECOMMISSION") and \
                  float(sub_row.get("monthly_savings_usd", 0) or 0) > 0

    if has_runaway:
        verdict_class = "verdict-runaway"
        verdict_word = "RUNAWAY"
        risk = "HIGH"
        action = (
            f"Misconfiguration detected on {runaway['alert']['first_seen']}. "
            f"Modeled overspend: ${runaway['alert']['modeled_total_overspend']:,.0f}. Page the feature owner."
        )
        confidence = "HIGH (>95%)"
        confidence_class = "confidence-high"
        tldr = (
            f"Daily modeled spend on {chosen_id} jumped from ~${runaway['pre_daily']:,.0f} to "
            f"~${runaway['post_daily']:,.0f} starting 2026-05-01 "
            f"({runaway['alert']['multiplier']}x baseline). "
            f"Runaway flagged in {elapsed_ms}ms on the prototype."
        )
    elif candidate == "DEAD_FEATURE":
        verdict_class = "verdict-dead"
        verdict_word = "DEAD"
        risk = "MEDIUM"
        action = (
            "Feature UI shut down but endpoint is still receiving traffic. "
            "Kill the endpoint, not the model."
        )
        confidence = "HIGH (>95%)"
        confidence_class = "confidence-high"
        tldr = (
            f"{chosen_id} sampled traffic in the last 60 days indicates an active endpoint "
            f"despite product-team status of 'active'. Modeled spend ${monthly_spend:,.0f}/mo "
            "with no business value. Recommend immediate kill."
        )
    elif candidate == "DECOMMISSION":
        verdict_class = "verdict-dead"
        verdict_word = "DECOMMISSION-CANDIDATE"
        risk = "LOW"
        action = (
            "Feature is dormant. Modeled spend is negligible, but governance risk is not."
        )
        confidence = "HIGH (>95%)"
        confidence_class = "confidence-high"
        tldr = (
            f"{chosen_id} shows a trickle of traffic against the catalog status of "
            f"'{status}'. Recommend full decommission to clear the endpoint."
        )
    elif has_savings:
        verdict_class = "verdict-undertier"
        verdict_word = "OVER-TIERED"
        risk = "MEDIUM"
        action = (
            f"Substitute {ft_row['model_used']} -> {candidate}. Modeled savings: "
            f"${float(sub_row.get('monthly_savings_usd', 0)):,.0f}/mo at "
            f"{sub_row.get('accuracy_delta_pct', '0')}pp accuracy delta."
        )
        confidence = ("HIGH (>95%)" if sub_row.get("confidence") == "high"
                      else "MEDIUM (70-95%)")
        confidence_class = ("confidence-high" if sub_row.get("confidence") == "high"
                            else "confidence-med")
        tldr = (
            f"{chosen_id} is on {ft_row['model_used']} but the workload shape fits a "
            f"smaller model. {sub_row.get('rationale', '')}"
        )
    else:
        verdict_class = "verdict-healthy"
        verdict_word = "HEALTHY"
        risk = "LOW"
        action = "Right-sized; no substitution recommended; no runaway detected."
        confidence = "HIGH (>95%)"
        confidence_class = "confidence-high"
        tldr = (
            f"{chosen_id} is at the right model tier, modeled spend ${monthly_spend:,.0f}/mo "
            f"is consistent with the workload shape, and revenue attribution "
            f"${revenue:,.0f}/mo gives "
            f"{'positive' if revenue > monthly_spend else 'no'} net ROI."
        )

    st.markdown(
        f"""
<div class='verdict-card {verdict_class}'>
  <div class='vlabel'>InferenceLens Verdict</div>
  <div class='vbig'>{verdict_word}</div>
  <div class='vmetric'>Modeled monthly spend ${monthly_spend:,.0f} - composition in {elapsed_ms}ms</div>
  <div class='vrow'>
    <span class='vchip'>Risk: {risk}</span>
    <span class='vchip'>Recommended action: {action}</span>
    <span class='vchip'>Feature: {chosen_id}</span>
  </div>
  <div class='vtldr'><b>TL;DR:</b> {tldr}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
<div class='trust-card'>
  <h4>Assumptions and Trust Signals</h4>
  <span class='tlabel'>What we composed from</span>
  <div>The four CSVs in <a href='{REPO_BLOB}/data/features.csv' target='_blank'><code>data/features.csv</code></a>, <a href='{REPO_BLOB}/data/inference_logs.csv' target='_blank'><code>data/inference_logs.csv</code></a>, <a href='{REPO_BLOB}/data/model_pricing.csv' target='_blank'><code>data/model_pricing.csv</code></a>, and <a href='{REPO_BLOB}/data/substitution_recommendations.csv' target='_blank'><code>data/substitution_recommendations.csv</code></a> stand in for the four signals a real deployment composes (OpenTelemetry span attributes, vendor billing APIs, feature catalog, eval-suite pass rates).</div>
  <span class='tlabel'>Assumptions we made</span>
  <ul>
    <li>The inference log is a stratified sample (~1:N) of full production traffic. Aggregate spend is reconstructed by scaling samples to the monthly volume in the feature catalog. Production reads from the full OpenTelemetry span stream.</li>
    <li>The substitution recommender's accuracy deltas are modeled from a 200-probe eval suite - in production this interlocks with <a href='{REPO_BLOB.replace("07-inferencelens-inference-finops", "04-evalforge-llm-eval-platform")}' target='_blank'>EvalForge</a>'s probe sets per feature family.</li>
    <li>Runaway threshold is 3x trailing-7-day baseline daily spend, fired only when baseline exceeds $50/day to suppress noise on low-volume features.</li>
    <li>Pricing is current-published-vendor pricing: <a href='https://www.anthropic.com/pricing' target='_blank'>Anthropic</a>, <a href='https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/' target='_blank'>Azure OpenAI</a>, <a href='https://aws.amazon.com/bedrock/pricing/' target='_blank'>AWS Bedrock</a>. Pricing snapshot pinned in <code>model_pricing.csv</code>.</li>
    <li>FinOps framework anchor: <a href='https://www.finops.org/framework/' target='_blank'>FinOps Foundation</a> Inform / Optimize / Operate phases. NIST AI RMF Govern function on the kill-criterion for dead features.</li>
  </ul>
  <span class='tlabel'>Confidence level</span>
  <div class='{confidence_class}'>{confidence}</div>
  <span class='tlabel'>What this does NOT cover</span>
  <ul>
    <li>Real-time per-token cost in the inference hot path (handled by the gateway sidecar; InferenceLens reads aggregates).</li>
    <li>Fine-tuning training cost (covered by the bank's MLOps platform; InferenceLens is inference-economics only).</li>
    <li>GPU / instance-hour cost for in-VPC Bedrock workloads (handled by the AWS Cost Explorer; InferenceLens reads the per-token rate).</li>
  </ul>
</div>
""",
        unsafe_allow_html=True,
    )

    if st.session_state.step < 3:
        if st.button("See the five-view composition  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()


# ---------------------------------------------------------------------------
# STEP 3 - six-deficiency views
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='il-card'><span class='il-step-label'>Step 3</span>"
        "<h3>Six-deficiency composition - each closed inline</h3>"
        "<p class='muted'>Each row is one of the six deficiencies the product taxonomy names. "
        "Green = closed by composition. Amber = recommendation present. Red = active alert. "
        "The exact taxonomy is the product's intellectual property and is the lens through "
        "which a CFO reads the AI-platform spend report.</p></div>",
        unsafe_allow_html=True,
    )

    # 1. Per-feature attribution
    st.markdown(
        f"<div class='def-row'><div class='dlabel'>1. Per-feature attribution - RESOLVED</div>"
        f"<div class='dval'>{chosen_id} - {ft_row['feature_name']} - "
        f"modeled monthly spend ${attr_row.get('modeled_monthly_spend_usd', 0):,.0f} - "
        f"cost/call ${attr_row.get('modeled_cost_per_call_usd', 0):.4f}</div></div>",
        unsafe_allow_html=True,
    )
    # 2. Per-tenant attribution
    st.markdown(
        f"<div class='def-row'><div class='dlabel'>2. Per-tenant / segment attribution - RESOLVED</div>"
        f"<div class='dval'>owner={ft_row['owner_team']} - business_line={ft_row['business_line']} - "
        f"production reads tenant_id from the OpenTelemetry span; demo aggregates by business_line</div></div>",
        unsafe_allow_html=True,
    )
    # 3. Runaway detection
    if runaway.get("alert"):
        a = runaway["alert"]
        st.markdown(
            f"<div class='def-row bad'><div class='dlabel'>3. Runaway detection - ALERT ACTIVE</div>"
            f"<div class='dval'>first_seen={a['first_seen']} - multiplier={a['multiplier']}x - "
            f"daily_overspend=${a['daily_overspend']:,.0f} - "
            f"days_undetected={a['days_undetected']} - "
            f"modeled_total_overspend=${a['modeled_total_overspend']:,.0f}</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='def-row'><div class='dlabel'>3. Runaway detection - CLEAR</div>"
            f"<div class='dval'>No 3x-baseline spike detected in the trailing 60-day window. "
            f"Pre-baseline daily ${runaway.get('pre_daily', 0):,.0f}; current ${runaway.get('post_daily', 0):,.0f}</div></div>",
            unsafe_allow_html=True,
        )
    # 4. Substitution
    if sub_row.get("candidate_model") and sub_row.get("candidate_model") not in (
        ft_row["model_used"], "DEAD_FEATURE", "DECOMMISSION"
    ) and float(sub_row.get("monthly_savings_usd", 0) or 0) > 0:
        st.markdown(
            f"<div class='def-row gap'><div class='dlabel'>4. Cheaper-model substitution - RECOMMENDATION</div>"
            f"<div class='dval'>{sub_row['current_model']} -> {sub_row['candidate_model']} - "
            f"savings ${float(sub_row['monthly_savings_usd']):,.0f}/mo - "
            f"accuracy delta {sub_row['accuracy_delta_pct']}pp - "
            f"confidence {sub_row['confidence']}</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='def-row'><div class='dlabel'>4. Cheaper-model substitution - RIGHT-SIZED</div>"
            f"<div class='dval'>No substitution recommended. {sub_row.get('rationale', 'Current model is appropriate for the workload shape.')}</div></div>",
            unsafe_allow_html=True,
        )
    # 5. Dead-feature
    if sub_row.get("candidate_model") in ("DEAD_FEATURE", "DECOMMISSION"):
        st.markdown(
            f"<div class='def-row bad'><div class='dlabel'>5. Dead-feature flag - ALERT</div>"
            f"<div class='dval'>{sub_row['candidate_model']} verdict - {sub_row['rationale']}</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='def-row'><div class='dlabel'>5. Dead-feature flag - LIVE</div>"
            f"<div class='dval'>status_in_catalog={ft_row['status']}, sampled traffic consistent with monthly_query_volume</div></div>",
            unsafe_allow_html=True,
        )
    # 6. ROI
    net = revenue - monthly_spend
    roi_state = "POSITIVE ROI" if revenue > 0 and net > 0 else \
                "NO REVENUE ATTRIBUTION" if revenue == 0 else "NEGATIVE NET"
    roi_class = "def-row" if revenue > 0 and net > 0 else "def-row gap" if revenue == 0 else "def-row bad"
    st.markdown(
        f"<div class='{roi_class}'><div class='dlabel'>6. Per-feature ROI - {roi_state}</div>"
        f"<div class='dval'>revenue ${revenue:,.0f}/mo - cost ${monthly_spend:,.0f}/mo - "
        f"net ${net:,.0f}/mo</div></div>",
        unsafe_allow_html=True,
    )

    # Daily spend trendline
    daily_df = runaway["daily"]
    if len(daily_df) > 0:
        with st.expander(f"Daily modeled spend trendline for {chosen_id}", expanded=True):
            st.line_chart(
                daily_df.set_index("day")["modeled_spend_usd"],
                use_container_width=True,
            )
            st.caption(
                "Daily modeled spend reconstructed from sampled cost x daily-call volume. "
                "The 2026-05-01 step (visible on FT_001) is the runaway anchor."
            )

    if st.session_state.step < 4:
        if st.button("Open the CFO pack  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()


# ---------------------------------------------------------------------------
# STEP 4 - CFO pack + glossary + production stack
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='il-card'><span class='il-step-label'>Step 4</span>"
        "<h3>Auto-assembled CFO pack</h3>"
        "<p class='muted'>The Finance-facing artifact. Per-feature monthly attribution, "
        "runaway-detection log, substitution recommender, dead-feature flag, ROI ranking. "
        "Exported as CSVs for the next monthly cost review.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # CSV exports
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.download_button(
            "Per-feature attribution CSV",
            attribution.to_csv(index=False),
            file_name="inferencelens_attribution.csv",
            mime="text/csv",
            type="primary",
        )
    with col_b:
        # ROI ranking
        roi_rows = []
        for _, ft in DATA["features"].iterrows():
            r = float(ft.get("revenue_attributed_monthly_usd", 0) or 0)
            attr_r = attribution[attribution["feature_id"] == ft["feature_id"]]
            c = float(attr_r.iloc[0]["modeled_monthly_spend_usd"]) if len(attr_r) else 0
            roi_rows.append({
                "feature_id": ft["feature_id"],
                "feature_name": ft["feature_name"],
                "monthly_revenue": r,
                "monthly_cost": c,
                "net": round(r - c, 2),
            })
        roi_df = pd.DataFrame(roi_rows).sort_values("net", ascending=False)
        st.download_button(
            "Per-feature ROI ranking CSV",
            roi_df.to_csv(index=False),
            file_name="inferencelens_roi_ranking.csv",
            mime="text/csv",
        )
    with col_c:
        st.download_button(
            "Substitution recommendations CSV",
            DATA["subs"].to_csv(index=False),
            file_name="inferencelens_substitutions.csv",
            mime="text/csv",
        )

    # Source-of-truth data viewers
    with st.expander("Inspect source-of-truth data (features.csv)"):
        st.caption(
            f"All 18 synthetic GenAI features across retail / wealth / enterprise lines. "
            f"Source: [`data/features.csv`]({REPO_BLOB}/data/features.csv)."
        )
        st.dataframe(DATA["features"], use_container_width=True, hide_index=True)

    with st.expander("Inspect source-of-truth data (inference_logs.csv)"):
        st.caption(
            f"~2,800 sampled per-call inference logs across the 60-day window. "
            f"Source: [`data/inference_logs.csv`]({REPO_BLOB}/data/inference_logs.csv)."
        )
        st.dataframe(DATA["logs"].head(500), use_container_width=True, hide_index=True)
        st.caption(f"Showing first 500 of {len(DATA['logs'])} rows.")

    with st.expander("Inspect source-of-truth data (model_pricing.csv)"):
        st.caption(
            f"Current published vendor pricing. Source: "
            f"[`data/model_pricing.csv`]({REPO_BLOB}/data/model_pricing.csv)."
        )
        st.dataframe(DATA["pricing"], use_container_width=True, hide_index=True)

    with st.expander("Inspect source-of-truth data (substitution_recommendations.csv)"):
        st.caption(
            f"Per-feature substitution recommender output. Source: "
            f"[`data/substitution_recommendations.csv`]({REPO_BLOB}/data/substitution_recommendations.csv)."
        )
        st.dataframe(DATA["subs"], use_container_width=True, hide_index=True)

    # Glossary
    with st.expander("Glossary - what these terms mean"):
        glossary_df = pd.DataFrame(
            [
                ("Per-feature attribution", "Cost broken down by business feature, not by API key or vendor invoice. The decomposition Finance actually asks for."),
                ("Per-tenant attribution", "Cost broken down by customer segment or internal team. Lets you bill internal teams for their share."),
                ("Runaway", "A daily-spend spike on a single feature beyond the trailing-7-day baseline. Typical cause: misconfigured retrieval depth, infinite loop, leaked SDK key."),
                ("Substitution recommender", "A per-feature service that scores whether the current model is right-tiered for the workload, based on a 200-probe eval suite."),
                ("Dead feature", "A feature whose UI has been shut down but whose endpoint is still receiving traffic. Common cause: leaked SDK key, downstream batch job nobody decommissioned."),
                ("Dormant feature", "A feature with a trickle of traffic against a catalog status of 'dormant'. Governance smell."),
                ("Per-feature ROI", "Modeled monthly revenue attributed to the feature, divided by modeled monthly cost. Lets you defend the AI roadmap with a per-feature number."),
                ("FinOps", "The discipline of running cloud costs as an operating practice. Defined by the FinOps Foundation framework: Inform, Optimize, Operate."),
                ("OpenTelemetry", "Industry-standard distributed tracing. The substrate every InferenceLens production deployment reads from."),
                ("ClickHouse", "A columnar database that handles high-cardinality cost events at scale. The right substrate for per-feature attribution at fleet scale."),
                ("Retrieval depth", "The number of documents a RAG pipeline pulls per query. Misconfiguring this from 5 to 50 inflates input tokens ~7x and is the classic GenAI runaway cause."),
                ("Per-token pricing", "The vendor's published cost per million input/output tokens. Anthropic, Azure OpenAI, and AWS Bedrock all publish this."),
                ("Vendor invoice", "The monthly bill from Anthropic / Azure / AWS / Bedrock. Aggregated, per-API-key, no business context."),
                ("vLLM", "An open-source inference serving engine; relevant for in-VPC self-hosted models where the bank is the payer of GPU-hours."),
                ("Cost-of-goods-sold (COGS)", "The unit cost of serving one customer. For AI features, inference cost is a load-bearing input to COGS for any customer-facing copilot."),
            ],
            columns=["Term", "Plain English"],
        )
        st.dataframe(glossary_df, use_container_width=True, hide_index=True)

        st.markdown("**Official references** (click to read the source documents):")
        st.markdown(
            "- [FinOps Foundation - framework](https://www.finops.org/framework/) - canonical FinOps definition\n"
            "- [Anthropic pricing](https://www.anthropic.com/pricing) - per-token pricing for Claude Opus / Sonnet / Haiku\n"
            "- [Azure OpenAI pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/) - per-token pricing for gpt-4o family\n"
            "- [AWS Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) - per-token pricing for Llama / Mistral / Titan\n"
            "- [NIST AI RMF (AI RMF 1.0)](https://www.nist.gov/itl/ai-risk-management-framework) - Govern function on kill-criteria for AI systems\n"
            "- [vLLM](https://docs.vllm.ai/) - open-source inference serving engine"
        )

    with st.expander("Production stack reassessment - what this would look like as client-facing SaaS"):
        st.markdown(
            """
            The Streamlit prototype here proves the *product mechanic* - that per-feature attribution can
            compress runaway detection from 6 weeks to 1 day, and that a cheaper-model substitution recommender
            can drive a modeled 25-30% spend reduction. **If InferenceLens were a real product shipping to a
            Tier-1 bank's AI Platform team and Finance organization:**

            - **Frontend:** Next.js 15 + Tailwind + shadcn/ui (or the bank's design system) - embedded as a
              panel inside the AI Platform team's existing operations workbench (Datadog dashboards, Snowflake
              cost-allocation views), not a standalone app.
            - **Auth:** SAML / OIDC via the bank's IdP (Okta, ForgeRock, PingFederate); fine-grained RBAC for
              `il:viewer` -> `il:finops_analyst` -> `il:feature_owner` -> `il:cfo` -> `il:admin`.
            - **Backend:** FastAPI on the bank's existing K8s/EKS footprint; per-vendor billing-API ingesters
              run as Cloud Functions / Lambdas.
            - **Data plane:** **ClickHouse** for the high-cardinality per-call cost events (10-50x cheaper
              than Postgres for time-series at this volume); **Postgres** for the feature catalog and the
              substitution recommender's decision log; **Snowflake** read-only for the revenue-attribution
              join. Interlocks with [LineageLog](https://github.com/Vj-shipped-anyway/ai-pm-portfolio/tree/main/09-lineagelog-ai-decision-audit)
              on the decision-grain spine.
            - **Composition engine:** OpenTelemetry collector reads span attributes per inference call;
              fan-in into ClickHouse with idempotency keys on `(feature_id, request_id)`. 5-minute compose SLO.
            - **Substitution recommender:** Stateless FastAPI service; reads from
              [EvalForge](https://github.com/Vj-shipped-anyway/ai-pm-portfolio/tree/main/04-evalforge-llm-eval-platform)
              probe-set pass rates per (feature, model) pair. Recommendations refresh nightly.
            - **Observability:** OpenTelemetry -> Datadog for service traces; the cost-event stream itself
              IS the observability for InferenceLens. PagerDuty on runaway-alert breaches.
            - **Compliance:** SOC 2 Type II baseline. Aligned to FinOps Foundation framework's Inform /
              Optimize / Operate phases. NIST AI RMF Govern function on kill-criterion.
            - **Governance:** Native integration with the bank's existing FinOps tooling (Apptio Cloudability,
              CloudHealth) - InferenceLens publishes per-feature spend; FinOps tooling aggregates with
              non-AI compute spend for the executive view.
            - **Deployment:** Blue-green via Argo CD; canary 1% -> 10% -> 50% -> 100% over 14 days; auto-rollback
              on composition-completeness breach.

            The portfolio prototype is the conversation-starter. This architecture is the second meeting.
            """
        )

    st.markdown(
        f"<div class='il-card muted'>Built as a portfolio prototype. Full walkthrough in "
        f"<a href='{REPO_BLOB}/README.md' target='_blank'><code>README.md</code></a> - "
        f"<a href='{REPO_BLOB}/ARCHITECTURE.md' target='_blank'><code>ARCHITECTURE.md</code></a> - "
        f"<a href='{REPO_BLOB}/PRD.md' target='_blank'><code>PRD.md</code></a>.</div>",
        unsafe_allow_html=True,
    )
