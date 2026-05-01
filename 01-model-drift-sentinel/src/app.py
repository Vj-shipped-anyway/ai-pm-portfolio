"""
DriftSentinel - Production AI Drift, Diagnosed and Routed
Author: Vijay Saharan
Run: streamlit run app.py

One-page scrollable narrative. No tour scaffolding. One interactive element
(the model dropdown in Section 4).
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------------------------
# Page chrome
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="DriftSentinel - Production AI Drift",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"
GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
DEMO_URL = "https://driftsentinel.streamlit.app"
LINKEDIN_URL = "https://www.linkedin.com/in/vijay-saharan/"

CSS = """
<style>
  .block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1100px; }

  .pill-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 18px 0; }
  .pill {
    display: inline-block; background: #18233a; border: 1px solid #2a3a5c;
    color: #cfd8ee; border-radius: 999px; padding: 6px 14px; font-size: 13px;
    text-decoration: none;
  }
  .pill a { color: #9ec5fe; text-decoration: none; }
  .pill.author { border-color: #6f9bff; color: #9ec5fe; }

  .hero {
    background: linear-gradient(135deg, #0b1c3d 0%, #142850 60%, #1f3a6b 100%);
    color: #f4f6fb; padding: 36px 36px; border-radius: 16px;
    border: 1px solid #2a3a5c; margin: 0 0 14px 0;
  }
  .hero h1 { font-size: 38px; margin: 0 0 10px 0; line-height: 1.15; }
  .hero .subtitle { color: #cfd8ee; font-size: 18px; margin: 0 0 18px 0; }
  .hero .hook { color: #b9c5dd; font-size: 15px; line-height: 1.6; margin: 0 0 14px 0; max-width: 820px; }
  .hero .scroll-cue { color: #7d8db0; font-size: 13px; font-style: italic; margin-top: 10px; }

  .section-h {
    font-size: 28px; font-weight: 700; color: #e6ecf6;
    margin: 8px 0 14px 0; line-height: 1.2;
  }
  .section-lede {
    color: #cfd8ee; font-size: 16px; line-height: 1.65;
    max-width: 860px; margin: 0 0 18px 0;
  }
  .caption {
    color: #a7b6d3; font-size: 14px; font-style: italic;
    margin-top: 14px; max-width: 860px; line-height: 1.55;
  }

  .person-card {
    background: #18233a; border: 1px solid #2a3a5c; border-radius: 14px;
    padding: 22px 26px; color: #e6ecf6; max-width: 720px; margin: 0 0 14px 0;
  }
  .person-card .avatar {
    width: 56px; height: 56px; border-radius: 50%;
    background: linear-gradient(135deg, #6f9bff, #1ec07a);
    display: inline-flex; align-items: center; justify-content: center;
    color: #0b1c3d; font-weight: 800; font-size: 22px; margin-bottom: 10px;
  }
  .person-card .name { font-size: 19px; font-weight: 700; }
  .person-card .meta { color: #a7b6d3; font-size: 14px; margin-top: 4px; }
  .person-card .scenario {
    color: #cfd8ee; margin-top: 14px; font-size: 15px; line-height: 1.6;
  }
  .person-card .harm {
    color: #ff8094; margin-top: 10px; font-size: 14px; font-weight: 600;
  }
  .impact-line {
    color: #ffc94d; font-size: 15px; font-weight: 600;
    margin: 14px 0; max-width: 860px;
  }

  .mechanic-row {
    display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px;
    margin: 18px 0; max-width: 980px;
  }
  .mechanic-step {
    background: #18233a; border: 1px solid #2a3a5c; border-radius: 12px;
    padding: 18px 20px; color: #e6ecf6;
  }
  .mechanic-step .num {
    display: inline-block; width: 28px; height: 28px; line-height: 28px;
    text-align: center; background: #6f9bff; color: #0b1c3d;
    border-radius: 50%; font-weight: 800; margin-bottom: 10px;
  }
  .mechanic-step .title { font-size: 16px; font-weight: 700; margin-bottom: 6px; }
  .mechanic-step .desc { color: #cfd8ee; font-size: 14px; line-height: 1.5; }

  .compare-card {
    border-radius: 14px; padding: 20px 22px; height: 100%;
    color: #e6ecf6; min-height: 260px;
  }
  .compare-card .label {
    font-weight: 700; font-size: 11px; letter-spacing: 0.6px;
    text-transform: uppercase; margin-bottom: 10px;
  }
  .compare-card .what { font-size: 16px; font-weight: 700; margin-bottom: 10px; }
  .compare-card .body { font-size: 14px; line-height: 1.55; color: #cfd8ee; }
  .compare-card .stat-row {
    background: rgba(0,0,0,0.20); border-radius: 8px;
    padding: 10px 12px; margin: 10px 0; font-size: 14px;
    display: flex; justify-content: space-between;
  }
  .compare-card .stat-row .k { color: #a7b6d3; }
  .compare-card .stat-row .v { font-weight: 700; }
  .red-card {
    background: #2a0d12; border: 2px solid #d32f2f; border-left: 8px solid #e0364f;
  }
  .red-card .label { color: #ff8094; }
  .amber-card {
    background: #2a200b; border: 2px solid #f57c00; border-left: 8px solid #d6a700;
  }
  .amber-card .label { color: #ffc94d; }
  .green-card {
    background: #082018; border: 2px solid #2e7d32; border-left: 8px solid #1ec07a;
  }
  .green-card .label { color: #6fdba8; }

  .summary-line {
    color: #b9c5dd; font-size: 15px; font-style: italic;
    margin: 18px 0 0 0; max-width: 860px; line-height: 1.6;
    border-left: 3px solid #6f9bff; padding-left: 14px;
  }

  .metric-tile {
    background: #18233a; border: 1px solid #2a3a5c; border-radius: 14px;
    padding: 22px 24px; color: #e6ecf6; height: 100%;
  }
  .metric-tile .mlabel {
    color: #9ec5fe; font-size: 12px; font-weight: 700;
    letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 10px;
  }
  .metric-tile .mvalue { font-size: 30px; font-weight: 800; line-height: 1.1; color: #6fdba8; }
  .metric-tile .mdelta { color: #a7b6d3; font-size: 13px; margin-top: 8px; }

  .bullet-list {
    color: #e6ecf6; font-size: 16px; line-height: 1.75;
    max-width: 880px; padding-left: 22px;
  }
  .bullet-list li { margin-bottom: 8px; }
  .bullet-list b { color: #9ec5fe; }

  .second-order {
    color: #ffc94d; font-size: 15px; font-style: italic;
    margin-top: 14px; max-width: 860px;
    border-left: 3px solid #d6a700; padding-left: 14px; line-height: 1.6;
  }

  .audit-card {
    background: #141b2c; border: 1px solid #2a3a5c; border-radius: 12px;
    padding: 16px 18px; color: #d9e1f2; height: 100%;
  }
  .audit-card .title { font-size: 14px; color: #9ec5fe; font-weight: 700; margin-bottom: 8px; }
  .audit-card .desc  { font-size: 13px; color: #a7b6d3; line-height: 1.5; }

  .footer {
    color: #7d8db0; font-size: 13px; font-style: italic;
    margin: 36px 0 0 0; text-align: center; padding-top: 18px;
    border-top: 1px solid #2a3a5c;
  }
  .footer a { color: #9ec5fe; text-decoration: none; }

  div[data-testid="stMetricValue"] { font-size: 30px; }

  hr { border-color: #2a3a5c; margin: 32px 0; }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------------------


@st.cache_data
def load_data():
    inf = pd.read_csv(DATA_DIR / "inference_logs.csv")
    inf["date"] = pd.to_datetime(inf["date"])
    inf["day"] = (inf["date"] - inf["date"].min()).dt.days
    models = pd.read_csv(DATA_DIR / "models.csv")
    events = pd.read_csv(DATA_DIR / "drift_events.csv")
    snaps = pd.read_csv(DATA_DIR / "vendor_snapshots.csv")
    return inf, models, events, snaps


def safe_load():
    try:
        return load_data(), None
    except Exception as exc:
        return (None, None, None, None), str(exc)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def build_drift_ledger(events_df: pd.DataFrame) -> pd.DataFrame:
    if events_df is None or events_df.empty:
        return pd.DataFrame(columns=["model_id", "feature_or_signal",
                                     "psi", "severity", "recommendation"])
    cols = ["detected_date", "model_id", "feature_or_signal",
            "psi", "ks", "segment", "recommendation"]
    available = [c for c in cols if c in events_df.columns]
    out = events_df[available].copy()
    if "psi" in out.columns:
        def severity(p):
            if pd.isna(p) or p == "N/A":
                return "PROXY"
            try:
                pf = float(p)
            except (TypeError, ValueError):
                return "N/A"
            if pf >= 0.25:
                return "RED"
            if pf >= 0.10:
                return "YELLOW"
            return "GREEN"
        out["severity"] = out["psi"].apply(severity)
    return out


def build_evidence_bundle(events_df, snaps_df, models_df) -> dict:
    ledger = build_drift_ledger(events_df).to_dict(orient="records")
    silent = []
    if snaps_df is not None and "announcement_status" in snaps_df.columns:
        silent_df = snaps_df[snaps_df["announcement_status"].isin(
            ["silent_minor_update", "acknowledged_post_hoc"])]
        silent = silent_df.to_dict(orient="records")
    return {
        "bundle_version": "1.0",
        "assembled_at": datetime.utcnow().isoformat() + "Z",
        "product": "DriftSentinel",
        "fleet": {
            "n_models_monitored": int(len(models_df)) if models_df is not None else 8,
            "tiers_covered": [1, 2],
            "families": ["credit", "fraud", "aml", "genai"],
        },
        "drift_event_ledger": ledger,
        "vendor_silent_updates": silent,
        "decisions_taken": [
            {"ts": "2026-02-14T09:12:00Z", "model_id": "support_qa_v2",
             "decision": "ROLLBACK", "reviewer": "line2.mrm.l2", "duration_s": 3.2},
            {"ts": "2026-03-03T11:42:00Z", "model_id": "credit_pd_v3",
             "decision": "SHADOW", "reviewer": "line2.mrm.l2", "duration_s": 2.7},
            {"ts": "2026-02-28T08:01:00Z", "model_id": "fraud_card_v7",
             "decision": "RETRAIN", "reviewer": "line2.mrm.l1", "duration_s": 4.1},
        ],
        "mrm_routing": "Line 2 - MRM L1/L2 Tier-1 queue",
        "audit_trail_handoff": "Project 08 - lineage event emitted",
    }


def bundle_to_zip_bytes(bundle: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("evidence_bundle.json", json.dumps(bundle, indent=2, default=str))
        zf.writestr("README.txt",
                    "DriftSentinel MRM evidence bundle.\n"
                    "Auto-assembled. Sign with validator credentials before submission.\n")
    buf.seek(0)
    return buf.read()


def render_segment_noise_floor():
    segments = ["prime_720_plus", "near_prime_680_720", "subprime_650_680",
                "thin_file", "card_present_pos", "ach_b2b"]
    psi_band_lo = [0.02, 0.04, 0.05, 0.06, 0.03, 0.04]
    psi_band_hi = [0.07, 0.10, 0.34, 0.18, 0.27, 0.09]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=segments, y=psi_band_hi, marker_color="#e0364f", name="Current PSI"))
    fig.add_trace(go.Bar(x=segments, y=psi_band_lo, marker_color="#1ec07a", name="Reference floor"))
    fig.add_hline(y=0.10, line_dash="dash", line_color="#d6a700")
    fig.add_hline(y=0.25, line_dash="dash", line_color="#e0364f")
    fig.update_layout(
        height=240, margin=dict(t=10, b=60, l=40, r=10), barmode="group",
        xaxis=dict(tickangle=-30), yaxis_title="PSI",
        plot_bgcolor="#0e1726", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#dde6f7", legend=dict(orientation="h", y=1.15),
    )
    st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------------------------------
# Model dropdown options
# -----------------------------------------------------------------------------

MODELS = {
    "Fraud detection (credit-card transactions)": {
        "kind": "Card-Present Fraud (LightGBM, Tier-1)",
        "what_broke": "Silent decay starting day 60. A new card-skimming pattern emerged in retail POS terminals. The model was trained on older patterns and started missing about 15% of fraud it used to catch.",
        "old_way_status": "GREEN",
        "old_way_note": "Quarterly Word doc, signed and filed on day 45.",
        "ai_alone_days": 41,
        "ai_alone_caught": "Partial - PSI on velocity tripped, but no diagnosis or routing. False alarm rate 31%.",
        "driftsentinel_days": 9,
        "driftsentinel_caught": "Caught. Velocity PSI = 0.27 in card_present_pos segment. Recommendation: RETRAIN. Auto-routed to fraud-ops.",
        "loss_avoided": "~$8M in undetected fraud losses prevented in the gap between day 9 and day 41.",
        "summary": "DriftSentinel didn't fix the model. It told the bank what broke, where, and what to do next - 32 days earlier than the basic open-source detector would have.",
    },
    "Credit risk (consumer loans)": {
        "kind": "Consumer Credit PD (XGBoost, Tier-1)",
        "what_broke": "DTI distributions shifted as the economy changed. The model still looked fine in aggregate - but the subprime 650-680 segment had drifted hard. Aggregate PSI stayed at 0.06; segment PSI was 0.34.",
        "old_way_status": "GREEN",
        "old_way_note": "Aggregate PSI was below threshold. Owner attested green.",
        "ai_alone_days": 41,
        "ai_alone_caught": "Aggregate PSI tools missed it - the slice-level shift was hidden by the average. False alarm on a different feature.",
        "driftsentinel_days": 9,
        "driftsentinel_caught": "Caught. dti PSI = 0.34 in subprime_650_680. Recommendation: SHADOW the new vintage. Auto-routed to credit-risk.",
        "loss_avoided": "~$6M in mispriced credit risk over the lag window.",
        "summary": "Aggregate health hides slice-level rot. DriftSentinel slices first. The credit risk team got a specific actionable signal, not a vague green checkmark.",
    },
    "Anti-money-laundering (AML)": {
        "kind": "AML SAR Triage (XGBoost, Tier-1)",
        "what_broke": "OFAC added 200K entities to the watchlist after a new sanctions regime. The triage model started generating spurious 'low risk' signals on entities that should now alert. Behavior space shifted overnight.",
        "old_way_status": "GREEN",
        "old_way_note": "Quarterly attestation didn't catch the watchlist update.",
        "ai_alone_days": 60,
        "ai_alone_caught": "PSI on input features didn't move - the inputs were the same, only the truth labels changed. Open-source detectors saw nothing.",
        "driftsentinel_days": 7,
        "driftsentinel_caught": "Caught via reference-data version check. Recommendation: RETRAIN with new watchlist. Auto-routed to financial-crimes.",
        "loss_avoided": "Avoided regulatory exposure on potentially missed SARs - a single missed SAR can run $1-10M in penalties.",
        "summary": "The model didn't drift - the world it lived in did. DriftSentinel watches reference data versions, not just inputs. That's the catch.",
    },
    "GenAI customer-service assistant (Anthropic Claude)": {
        "kind": "Customer Support Q&A GenAI (Anthropic Claude, Tier-1)",
        "what_broke": "On Feb 24, the vendor silently updated the model overnight. Same API, different behavior. Refusal rate jumped 6%. Groundedness dropped 10%. Customer transcripts shifted in tone.",
        "old_way_status": "GREEN",
        "old_way_note": "No quarterly review until day 90. The bank had no signal.",
        "ai_alone_days": 78,
        "ai_alone_caught": "Open-source PSI tools saw zero - the input distribution was the same, customers asked the same questions. The change was downstream of input.",
        "driftsentinel_days": 1,
        "driftsentinel_caught": "Caught within an hour. Vendor snapshot ID changed - that IS the alert. Recommendation: ROLLBACK. Anthropic acknowledged the change five days later.",
        "loss_avoided": "Avoided a 5-day exposure window with a behaving-differently model serving customer disclosures.",
        "summary": "Vendor version pinning trades a 4-8 week update lag for governance signal. For a regulated bank, that's the right trade. DriftSentinel saw it before the vendor announced it.",
    },
    "Collections optimization": {
        "kind": "Collections Routing (Internal, Tier-2)",
        "what_broke": "A state law capped collection-call frequency at 7 per week per debtor. The model's optimal-call-time outputs started clustering around bounded values. Behavior changed but accuracy metrics still looked fine.",
        "old_way_status": "GREEN",
        "old_way_note": "Outcome metrics held steady. No quarterly review flag.",
        "ai_alone_days": 50,
        "ai_alone_caught": "Output PSI moved slightly but stayed below 0.10 threshold. Generic open-source tools missed it.",
        "driftsentinel_days": 11,
        "driftsentinel_caught": "Caught via output-bound monitoring. Recommendation: RETRAIN with new constraint. Auto-routed to collections-ops.",
        "loss_avoided": "Avoided a regulatory exposure of $500K-$2M in fines under FDCPA-equivalent state rules.",
        "summary": "Behavior-bounded drift is invisible to noise-floor PSI. DriftSentinel watches output distributions against policy bounds, not just statistical thresholds.",
    },
    "Marketing model": {
        "kind": "Marketing Propensity (Internal, Tier-2)",
        "what_broke": "Seasonal change in conversion patterns - the model was retrained on summer data and started misfiring on holiday traffic. Not catastrophic, but ROI on campaigns dropped 18%.",
        "old_way_status": "GREEN",
        "old_way_note": "Tier-2 model, semi-annual review. Drift wasn't on the radar.",
        "ai_alone_days": 35,
        "ai_alone_caught": "Open-source tool flagged it correctly but with high false-alarm rate - tier-2 noise vs signal was hard to separate.",
        "driftsentinel_days": 12,
        "driftsentinel_caught": "Caught with segment-aware noise floor. Recommendation: RETAIN but monitor; recommend retrain in 30 days. Routed to marketing.",
        "loss_avoided": "~$1.2M in wasted marketing spend over the gap window.",
        "summary": "Not every drift is a fire. DriftSentinel separates 'monitor and revisit' from 'pull the model now.' Tier-2 drift gets tier-2 routing.",
    },
}

MODEL_NAMES = list(MODELS.keys())


# -----------------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------------


def render_sidebar():
    with st.sidebar:
        with st.expander("About this demo", expanded=False):
            st.markdown(
                f"""
Vijay Saharan, AI PM portfolio prototype.
[GitHub]({GITHUB_URL}) - [LinkedIn]({LINKEDIN_URL})

Banking AI Model Risk. One of three demos in the portfolio.
""",
            )


# -----------------------------------------------------------------------------
# Section renderers
# -----------------------------------------------------------------------------


def render_hero():
    st.markdown(
        f"""
<div class='pill-row'>
  <a class='pill' href='{DEMO_URL}' target='_blank'>Live demo</a>
  <a class='pill' href='{GITHUB_URL}' target='_blank'>GitHub</a>
  <span class='pill author'>Vijay Saharan</span>
</div>
<div class='hero'>
  <h1>DriftSentinel</h1>
  <div class='subtitle'>Catches AI models when they quietly stop working.</div>
  <div class='hook'>Watch what happens when a fraud model quietly decays - same code, same API, but the world moved.
  Most banks won't notice for 78 days. The compliance audit will find it the quarter after that.
  Now watch what changes with continuous monitoring across the full model fleet.</div>
  <div class='scroll-cue'>Scroll to read.</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_section_problem():
    st.markdown(
        """
<div class='section-h'>What's the problem?</div>
<div class='section-lede'>Banks run hundreds of AI models - for fraud, credit decisions, anti-money-laundering, customer service, collections.
These models quietly stop working as the world changes. Customers' fraud patterns shift. The economy moves. A vendor updates their model overnight.
The model isn't broken - it isn't throwing errors - it's just been quietly wrong for a while. Most banks check on each model every 3 months. By then, two quarters of value have leaked.</div>
<div class='person-card'>
  <div class='avatar'>F</div>
  <div class='name'>Fraud model, day 60</div>
  <div class='meta'>$50B-asset US retail bank. 8 production AI models. Fraud model is Tier-1.</div>
  <div class='scenario'>A new card-skimming pattern emerges at retail POS terminals. The model was trained on older patterns. It starts missing about <b>15% of the fraud</b> it used to catch.
  No errors. No alarms. The model owner's quarterly attestation - signed on day 45 - says "GREEN."</div>
  <div class='harm'>Average time before anyone notices: 78 days. Two full quarters of fraud losses leak through before the bank sees it.</div>
</div>
<div class='impact-line'>At a Tier-1 US bank running ~1,200 production models, undetected drift modeled to bleed $45-90M per year - the size of a small acquisition, recurring annually.</div>
""",
        unsafe_allow_html=True,
    )


def render_section_solution():
    st.markdown(
        """
<div class='section-h'>What's the solution?</div>
<div class='section-lede'>DriftSentinel watches every model continuously, not quarterly. When a model's behavior starts changing,
DriftSentinel detects it, diagnoses what kind of drift it is (input shift, output shift, vendor update, reference-data change),
and routes the right alert to the right team with the evidence pre-assembled. The bank gets a 9-day signal instead of a 78-day one.</div>
<div class='mechanic-row'>
  <div class='mechanic-step'>
    <div class='num'>1</div>
    <div class='title'>Watch the fleet, continuously</div>
    <div class='desc'>Every model in production gets sampled and statistically tested every day. PSI, KS, segment-level, plus vendor snapshot IDs.</div>
  </div>
  <div class='mechanic-step'>
    <div class='num'>2</div>
    <div class='title'>Diagnose the drift class</div>
    <div class='desc'>Not all drift is equal. Aggregate vs slice. Input vs output. Vendor vs internal. The diagnosis tells you what to do.</div>
  </div>
  <div class='mechanic-step'>
    <div class='num'>3</div>
    <div class='title'>Route with evidence</div>
    <div class='desc'>Alert routes to the right team (credit-risk, fraud-ops, MRM L2) with the audit pack pre-assembled. Decision in minutes, not weeks.</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_section_inaction():
    st.markdown(
        "<div class='section-h'>See it in action - pick a model</div>",
        unsafe_allow_html=True,
    )

    selected = st.selectbox(
        "Model",
        MODEL_NAMES,
        index=0,
        key="selected_model",
        label_visibility="collapsed",
    )
    m = MODELS[selected]

    st.markdown(
        f"""
<div class='person-card' style='max-width: 100%; margin: 14px 0 18px 0;'>
  <div class='avatar'>{m['kind'][0]}</div>
  <div class='name'>{selected}</div>
  <div class='meta'>{m['kind']}</div>
  <div class='scenario'><b>What broke:</b> {m['what_broke']}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(
            f"""<div class='compare-card amber-card'>
  <div class='label'>Door 1 - the old way</div>
  <div class='what'>Quarterly Word doc, owner-signed</div>
  <div class='stat-row'><span class='k'>Quarterly status</span><span class='v'>{m['old_way_status']}</span></div>
  <div class='stat-row'><span class='k'>Days to notice</span><span class='v'>78+</span></div>
  <div class='body'>{m['old_way_note']} The form says the model is fine. Nothing in the process actually inspects the model. Most US banks live here.</div>
</div>""",
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(
            f"""<div class='compare-card red-card'>
  <div class='label'>Door 2 - open-source PSI tool</div>
  <div class='what'>Basic data-shift detector</div>
  <div class='stat-row'><span class='k'>Days to notice</span><span class='v'>{m['ai_alone_days']}</span></div>
  <div class='stat-row'><span class='k'>False alarms</span><span class='v'>31%</span></div>
  <div class='body'>{m['ai_alone_caught']} Better than nothing - but slow, noisy, and blind to the worst kind of failure (vendor updates and slice-level rot).</div>
</div>""",
            unsafe_allow_html=True,
        )
    with col_c:
        st.markdown(
            f"""<div class='compare-card green-card'>
  <div class='label'>Door 3 - DriftSentinel</div>
  <div class='what'>Continuous, diagnosed, routed</div>
  <div class='stat-row'><span class='k'>Days to notice</span><span class='v'>{m['driftsentinel_days']}</span></div>
  <div class='stat-row'><span class='k'>False alarms</span><span class='v'>7%</span></div>
  <div class='body'>{m['driftsentinel_caught']} Loss avoided: {m['loss_avoided']}</div>
</div>""",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div class='summary-line'>{m['summary']}</div>",
        unsafe_allow_html=True,
    )


def render_section_proof():
    st.markdown(
        """
<div class='section-h'>Does it actually work?</div>
<div class='section-lede'>We ran 90 days of synthetic bank traffic across 8 production models, with 8 drift events injected starting day 60.
The events span input drift, output drift, vendor updates, and reference-data shifts. We compared three oversight regimes
on the same data: quarterly attestation, basic open-source PSI, and DriftSentinel.</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            """<div class='metric-tile'>
  <div class='mlabel'>Days to notice (old way)</div>
  <div class='mvalue' style='color:#ff8094;'>78</div>
  <div class='mdelta'>Quarterly Word doc, owner-attested</div>
</div>""",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """<div class='metric-tile'>
  <div class='mlabel'>Days to notice (DriftSentinel)</div>
  <div class='mvalue'>9</div>
  <div class='mdelta'>69 days earlier than baseline</div>
</div>""",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            """<div class='metric-tile'>
  <div class='mlabel'>False alarms (old / new)</div>
  <div class='mvalue' style='color:#ffc94d;'>31% &rarr; 7%</div>
  <div class='mdelta'>24 percentage points cleaner than basic tools</div>
</div>""",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            """<div class='metric-tile'>
  <div class='mlabel'>Audit pack (old / new)</div>
  <div class='mvalue'>3 wks &rarr; 3 sec</div>
  <div class='mdelta'>From "we noticed" to "validator has the pack"</div>
</div>""",
            unsafe_allow_html=True,
        )


def render_section_help():
    st.markdown(
        """
<div class='section-h'>How does this help the bank?</div>
<ul class='bullet-list'>
  <li><b>About $45-90 million per year in modeled losses prevented</b> at a Tier-1 bank's scale - the size of a small acquisition, recurring annually.</li>
  <li><b>Model coverage 22% &rarr; 100%</b> - every model watched, not just the riskiest fifth that has bandwidth.</li>
  <li><b>Mean time to notice 78 &rarr; 9 days</b> - two months of leakage cut to one and a half weeks.</li>
  <li><b>False-alarm rate 31% &rarr; 7%</b> - the team trusts the alerts, so they actually act on them.</li>
</ul>
<div class='second-order'>The MRM evidence pack a regulator or internal validator would ask for is already prepared. Auto-assembled in seconds, not the 3-week scramble that's typical today.</div>
""",
        unsafe_allow_html=True,
    )


def render_section_caveats():
    st.markdown(
        """
<div class='section-h'>What to keep in mind</div>
<ul class='bullet-list'>
  <li><b>This is a portfolio prototype</b> - not a deployed bank product. Built to demonstrate the PM analysis and the architecture I'd bring to the seat.</li>
  <li><b>Vendor snapshot pinning trades a 4-8 week lag on model updates for governance signal.</b> That's the right trade-off for a regulated bank - but you'd revisit it for a fintech startup where speed-of-feature beats speed-of-disclosure.</li>
  <li><b>DriftSentinel notices what's broken. It doesn't fix the model.</b> Decisions about rollback, retraining, and routing are still human - that's the right answer for Tier-1 regulated AI.</li>
  <li><b>The 9-day mean is across the 8 injected events.</b> Tail cases (slice-level rot in low-volume segments) take longer; vendor version changes are caught within the hour. The mean isn't a guarantee for any single event.</li>
  <li><b>Designed against US banking expectations</b> - SR 11-7 model risk, OCC heightened standards, and the recent NIST AI RMF mappings. Other jurisdictions (EU AI Act, MAS Singapore) would need re-mapping of the routing taxonomy.</li>
</ul>
""",
        unsafe_allow_html=True,
    )


def render_section_audit(events_df, snaps_df, models_df):
    bundle = build_evidence_bundle(events_df, snaps_df, models_df)
    ledger_df = build_drift_ledger(events_df)

    with st.expander("Show the technical detail - the audit pack the bank's risk team would review", expanded=False):
        g1, g2 = st.columns(2)
        with g1:
            st.markdown(
                """<div class='audit-card'>
  <div class='title'>Drift event ledger</div>
  <div class='desc'>Every detected event with PSI, segment, and recommendation.</div>
</div>""",
                unsafe_allow_html=True,
            )
            if ledger_df.empty:
                st.caption("Ledger not available - event data missing.")
            else:
                cols = [c for c in ["model_id", "feature_or_signal", "psi", "severity", "recommendation"]
                        if c in ledger_df.columns]
                st.dataframe(ledger_df[cols], use_container_width=True, hide_index=True, height=240)
        with g2:
            st.markdown(
                """<div class='audit-card'>
  <div class='title'>Segment noise floor</div>
  <div class='desc'>PSI by segment vs reference floor. Subprime is hot.</div>
</div>""",
                unsafe_allow_html=True,
            )
            render_segment_noise_floor()

        g3, g4 = st.columns(2)
        with g3:
            st.markdown(
                """<div class='audit-card'>
  <div class='title'>Vendor snapshot diff log</div>
  <div class='desc'>Every external model version pinned. Silent updates flagged.</div>
</div>""",
                unsafe_allow_html=True,
            )
            if snaps_df is not None and not snaps_df.empty:
                show = snaps_df[["snapshot_date", "vendor", "snapshot_id", "announcement_status"]].copy()
                st.dataframe(show, use_container_width=True, hide_index=True, height=240)
        with g4:
            st.markdown(
                """<div class='audit-card'>
  <div class='title'>Decision audit trail</div>
  <div class='desc'>Who decided what, when, and how long it took.</div>
</div>""",
                unsafe_allow_html=True,
            )
            st.dataframe(pd.DataFrame(bundle["decisions_taken"]),
                         use_container_width=True, hide_index=True, height=240)

        st.download_button(
            "Download the full audit pack (.zip)",
            data=bundle_to_zip_bytes(bundle),
            file_name=f"driftsentinel_mrm_{datetime.utcnow().strftime('%Y%m%d')}.zip",
            mime="application/zip",
        )


def render_footer():
    st.markdown(
        f"""<div class='footer'>
Built by Vijay Saharan. Code, data, and PRDs at
<a href='{GITHUB_URL}' target='_blank'>github.com/Vj-shipped-anyway/ai-pm-portfolio</a>.
Connect on <a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a>.
</div>""",
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main():
    render_sidebar()

    (inf_df, models_df, events_df, snaps_df), err = safe_load()
    if err:
        st.error(f"Data not available: {err}")
        return

    render_hero()
    st.divider()
    render_section_problem()
    st.divider()
    render_section_solution()
    st.divider()
    render_section_inaction()
    st.divider()
    render_section_proof()
    st.divider()
    render_section_help()
    st.divider()
    render_section_caveats()
    st.divider()
    render_section_audit(events_df, snaps_df, models_df)
    render_footer()


if __name__ == "__main__":
    main()
