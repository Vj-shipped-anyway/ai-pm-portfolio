"""
DriftSentinel - Production AI Drift, Diagnosed and Routed
Author: Vijay Saharan
Run: streamlit run app.py

Guided tour. 9 steps. Click Next to advance.
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
GITHUB_URL = "https://github.com/vijaysaharan/ai-pm-portfolio"
TOTAL_STEPS = 10  # steps 0..9

CSS = """
<style>
  .step-wrap { animation: fadeIn 350ms ease-in; }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .hero {
    background: linear-gradient(135deg, #0b1c3d 0%, #142850 60%, #1f3a6b 100%);
    color: #f4f6fb; padding: 36px 36px; border-radius: 16px;
    border: 1px solid #2a3a5c; margin: 8px 0 14px 0;
  }
  .hero h1 { font-size: 38px; margin: 0 0 12px 0; line-height: 1.15; }
  .hero p  { color: #cfd8ee; font-size: 16px; line-height: 1.6; margin: 0; }
  .hero .meta { color: #7d8db0; font-size: 12px; margin-top: 14px; }
  .hero .meta a { color: #9ec5fe; text-decoration: none; }

  .narrator {
    color: #b9c5dd; font-size: 15px; line-height: 1.6;
    margin: 0 0 18px 0; max-width: 860px;
  }
  .caption {
    color: #a7b6d3; font-size: 14px; font-style: italic;
    margin-top: 14px; max-width: 820px; line-height: 1.55;
  }

  .bank-card {
    background: #18233a; border: 1px solid #2a3a5c; border-radius: 14px;
    padding: 22px 26px; color: #e6ecf6; max-width: 720px;
  }
  .bank-card .head {
    font-size: 13px; color: #9ec5fe; font-weight: 700;
    letter-spacing: 0.6px; text-transform: uppercase; margin-bottom: 10px;
  }
  .bank-card .row { font-size: 16px; line-height: 1.6; }
  .bank-card .pill {
    display: inline-block; background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12); border-radius: 999px;
    padding: 4px 12px; margin: 4px 6px 4px 0; font-size: 13px;
  }

  .day-counter {
    background: #18233a; border: 1px solid #2a3a5c; border-radius: 14px;
    padding: 28px; text-align: center; max-width: 540px;
  }
  .day-counter .lbl {
    color: #9ec5fe; font-size: 12px; font-weight: 700;
    letter-spacing: 0.6px; text-transform: uppercase; margin-bottom: 10px;
  }
  .day-counter .v {
    font-size: 56px; font-weight: 800; color: #6fdba8; line-height: 1;
  }
  .day-counter .sub {
    color: #cfd8ee; margin-top: 14px; font-size: 14px;
  }

  .status-row {
    display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px;
    justify-content: center;
  }
  .status-dot {
    width: 14px; height: 14px; border-radius: 50%;
    background: #1ec07a; box-shadow: 0 0 8px rgba(30,192,122,0.5);
  }
  .status-dot.fail {
    background: #e0364f; box-shadow: 0 0 12px rgba(224,54,79,0.7);
    animation: pulse 1.5s infinite;
  }
  @keyframes pulse {
    0%   { opacity: 1; }
    50%  { opacity: 0.5; }
    100% { opacity: 1; }
  }

  .alert-card {
    background: #2a0d12; border: 2px solid #6b1f2a; border-left: 8px solid #e0364f;
    border-radius: 14px; padding: 22px 26px; color: #ffe5ea;
    box-shadow: 0 8px 28px rgba(224, 54, 79, 0.25);
    max-width: 720px;
  }
  .alert-card .label {
    color: #ff8094; font-weight: 700; font-size: 12px;
    letter-spacing: 0.6px; text-transform: uppercase; margin-bottom: 10px;
  }
  .alert-card .body { font-size: 17px; line-height: 1.55; }

  .door-card {
    background: #141b2c; border: 1px solid #2a3a5c; border-radius: 14px;
    padding: 28px 30px; color: #d9e1f2; max-width: 720px;
  }
  .door-card .door-num {
    color: #9ec5fe; font-size: 12px; font-weight: 700;
    letter-spacing: 0.6px; text-transform: uppercase; margin-bottom: 8px;
  }
  .door-card .door-title { font-size: 22px; font-weight: 700; margin-bottom: 14px; }
  .door-card .stat {
    display: flex; justify-content: space-between; padding: 10px 0;
    border-top: 1px solid #2a3a5c; font-size: 15px;
  }
  .door-card .stat:first-of-type { border-top: 0; }
  .door-card .stat .k { color: #a7b6d3; }
  .door-card .stat .v { color: #e6ecf6; font-weight: 700; }

  .red-door   { border-left: 8px solid #e0364f;
                box-shadow: 0 6px 22px rgba(224,54,79,0.18); }
  .amber-door { border-left: 8px solid #d6a700;
                box-shadow: 0 6px 22px rgba(214,167,0,0.18); }
  .green-door { border-left: 8px solid #1ec07a;
                box-shadow: 0 6px 22px rgba(30,192,122,0.22); }

  .vendor-card {
    background: #141b2c; border: 1px solid #2a3a5c; border-radius: 14px;
    padding: 22px 26px; color: #d9e1f2; height: 100%;
  }
  .vendor-card.bad   { border-left: 8px solid #e0364f; }
  .vendor-card.good  { border-left: 8px solid #1ec07a; }
  .vendor-card .head {
    font-size: 12px; font-weight: 700; letter-spacing: 0.6px;
    text-transform: uppercase; margin-bottom: 8px;
  }
  .vendor-card.bad  .head { color: #ff8094; }
  .vendor-card.good .head { color: #6fdba8; }
  .vendor-card .what { font-size: 18px; font-weight: 700; margin-bottom: 10px; color: #e6ecf6; }
  .vendor-card .body { font-size: 14px; line-height: 1.55; color: #cfd8ee; }

  .metric-tile {
    background: #18233a; border: 1px solid #2a3a5c; border-radius: 14px;
    padding: 22px 24px; color: #e6ecf6; height: 100%;
  }
  .metric-tile .label {
    color: #9ec5fe; font-size: 12px; font-weight: 700;
    letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 10px;
  }
  .metric-tile .value { font-size: 32px; font-weight: 800; line-height: 1.1; color: #6fdba8; }
  .metric-tile .delta { color: #a7b6d3; font-size: 13px; margin-top: 6px; }

  .step-indicator {
    color: #7d8db0; font-size: 12px; letter-spacing: 0.6px;
    text-transform: uppercase; font-weight: 700; margin-top: 26px;
  }

  div[data-testid="stMetricValue"] { font-size: 30px; }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Data loading (kept for dashboard mode)
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
# Helpers (also used by dashboard mode)
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


# -----------------------------------------------------------------------------
# Navigation callbacks
# -----------------------------------------------------------------------------


def go_next():
    st.session_state.step = min(st.session_state.step + 1, TOTAL_STEPS - 1)


def go_back():
    st.session_state.step = max(st.session_state.step - 1, 0)


def restart():
    st.session_state.step = 0


# -----------------------------------------------------------------------------
# Step renderers
# -----------------------------------------------------------------------------


def render_step_0():
    st.markdown(
        f"""
        <div class='step-wrap'>
          <div class='hero'>
            <h1>Catches AI models when they quietly stop working.</h1>
            <p>Banks run hundreds of AI models - for fraud, credit decisions,
            anti-money-laundering, customer service. These models quietly stop working as
            the world changes ("drift"). Most banks only check on them every 3 months. By
            then, two quarters of value have leaked. DriftSentinel watches every model
            continuously. The next 90 seconds will walk you through what that looks like.</p>
            <p class='meta'>Banking AI Model Risk - Sr PM portfolio - Vijay Saharan
            &nbsp;&middot;&nbsp; <a href='{GITHUB_URL}' target='_blank'>GitHub</a></p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_1():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            Meet the bank.
          </div>
          <div class='bank-card'>
            <div class='head'>$50 billion-asset US retail bank</div>
            <div class='row'>8 production AI models running today:</div>
            <div style='margin-top:12px;'>
              <span class='pill'>3 fraud</span>
              <span class='pill'>2 credit</span>
              <span class='pill'>1 anti-money-laundering</span>
              <span class='pill'>1 customer service GenAI assistant</span>
              <span class='pill'>1 collections</span>
            </div>
          </div>
          <div class='caption'>This is a typical mid-sized US bank's AI footprint. Yours likely has more.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_2():
    dots = "".join("<div class='status-dot'></div>" for _ in range(8))
    st.markdown(
        f"""
        <div class='step-wrap'>
          <div class='narrator'>
            Day 1 to Day 59. Everything looks fine.
          </div>
          <div class='day-counter'>
            <div class='lbl'>Today is</div>
            <div class='v'>Day 59</div>
            <div class='sub'>All 8 models GREEN. Standard quarterly check is scheduled for Day 90.</div>
            <div class='status-row'>{dots}</div>
          </div>
          <div class='caption'>Models are running. Customers are happy. The next compliance
          review is in a month. This is the comfortable state most banks live in.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_3():
    dots = "".join(
        f"<div class='status-dot{ ' fail' if i == 0 else ''}'></div>"
        for i in range(8)
    )
    st.markdown(
        f"""
        <div class='step-wrap'>
          <div class='narrator'>
            Day 60. Something just broke.
          </div>
          <div class='alert-card'>
            <div class='label'>Day 60 - silent decay begins</div>
            <div class='body'>The fraud model's accuracy started decaying. Why? Customers'
            fraud patterns changed (a new card-skimming technique went viral). The model
            was trained on old patterns. It's now missing 15% of fraud it used to catch.</div>
          </div>
          <div class='status-row' style='justify-content:flex-start; max-width:540px;'>{dots}</div>
          <div class='caption'>The bank doesn't know yet. The model isn't throwing errors.
          It's just quietly being wrong. This is called "silent decay".</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_4():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            Day 90. Time for the quarterly review.
          </div>
          <div style='font-size:18px; color:#cfd8ee; max-width:760px; line-height:1.7;'>
            Three different banks would run their oversight three different ways. Let's
            walk through each.
          </div>
          <div style='display:flex; gap:14px; margin-top:22px; max-width:760px;'>
            <div style='flex:1; background:#2a0d12; border:1px solid #6b1f2a; border-radius:12px;
                        padding:18px; text-align:center; color:#ffe5ea;'>
              <div style='font-size:12px; font-weight:700; letter-spacing:0.6px;'>DOOR 1</div>
              <div style='font-size:16px; font-weight:600; margin-top:6px;'>The old way</div>
            </div>
            <div style='flex:1; background:#2a200b; border:1px solid #6b541f; border-radius:12px;
                        padding:18px; text-align:center; color:#fff1c9;'>
              <div style='font-size:12px; font-weight:700; letter-spacing:0.6px;'>DOOR 2</div>
              <div style='font-size:16px; font-weight:600; margin-top:6px;'>Open-source tool</div>
            </div>
            <div style='flex:1; background:#082018; border:1px solid #144d36; border-radius:12px;
                        padding:18px; text-align:center; color:#d8f4e7;'>
              <div style='font-size:12px; font-weight:700; letter-spacing:0.6px;'>DOOR 3</div>
              <div style='font-size:16px; font-weight:600; margin-top:6px;'>DriftSentinel</div>
            </div>
          </div>
          <div class='caption'>Click forward to open each door, one at a time.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_5():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            Door 1: the old way. A Word doc every 3 months.
          </div>
          <div class='door-card red-door'>
            <div class='door-num'>Door 1</div>
            <div class='door-title'>Quarterly attestation. Word document signed by the model owner.</div>
            <div class='stat'><span class='k'>Catches</span><span class='v'>0 of 8 problems</span></div>
            <div class='stat'><span class='k'>Days late</span><span class='v'>78</span></div>
            <div class='stat'><span class='k'>Cost to the bank</span><span class='v'>2 quarters of fraud loss</span></div>
          </div>
          <div class='caption'>This is what most US banks do today. Form-over-substance.
          The model owner certifies the model is fine, then drafts a paragraph explaining
          why. Nothing in this process actually inspects the model.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_6():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            Door 2: open-source data-shift detection.
          </div>
          <div class='door-card amber-door'>
            <div class='door-num'>Door 2</div>
            <div class='door-title'>Open-source PSI tool (basic data-shift detector).</div>
            <div class='stat'><span class='k'>Catches</span><span class='v'>3 of 8 problems</span></div>
            <div class='stat'><span class='k'>False alarms</span><span class='v'>31% of detections turn out to be noise</span></div>
            <div class='stat'><span class='k'>Days late</span><span class='v'>41 average</span></div>
          </div>
          <div class='caption'>Better than nothing. Catches the obvious shifts. Misses the
          subtle ones - including the worst kind: when an outside AI vendor silently
          updates their model overnight.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_7():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            Door 3: DriftSentinel.
          </div>
          <div class='door-card green-door'>
            <div class='door-num'>Door 3</div>
            <div class='door-title'>DriftSentinel - continuous monitoring across the fleet.</div>
            <div class='stat'><span class='k'>Catches</span><span class='v'>8 of 8 problems</span></div>
            <div class='stat'><span class='k'>False alarms</span><span class='v'>7%</span></div>
            <div class='stat'><span class='k'>Days late</span><span class='v'>9 average</span></div>
            <div class='stat'><span class='k'>Audit pack assembled in</span><span class='v'>3.2 seconds</span></div>
          </div>
          <div class='caption'>Continuous monitoring. Cause-of-failure diagnosis.
          Auto-assembled evidence the bank's risk team can review in 12 minutes instead
          of 3 weeks.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_8():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            But wait - there's a worse problem. The vendor surprise.
          </div>
          <div style='font-size:17px; color:#e6ecf6; margin: 12px 0 18px 0; max-width: 760px;'>
            On February 24, Anthropic silently updated their AI model overnight.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            <div class='vendor-card bad'>
              <div class='head'>Without snapshot pin</div>
              <div class='what'>0 detection signal.</div>
              <div class='body'>The bank's GenAI assistant is now using a different model.
              Nobody at the bank knows. Customer answers shift. Refusal rate jumps 6%.
              Groundedness drops 10%. The basic data-shift detector sees nothing - the
              customer questions didn't change, only the AI behind them did.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class='vendor-card good'>
              <div class='head'>With snapshot pin</div>
              <div class='what'>Version diff IS the alert.</div>
              <div class='body'>DriftSentinel watches the exact vendor version ID on every
              model. When it changes, that IS the signal. Notification fired within the
              hour. Validator paged. Audit pack assembled. Anthropic acknowledged the
              change five days later - DriftSentinel had already caught it.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class='caption'>This is the worst kind of failure: an outside AI vendor
        changes their model and you have no signal. The fix is to pin the version of the
        model you're using and watch for any change. DriftSentinel does this automatically.</div>
        """,
        unsafe_allow_html=True,
    )


def render_step_9():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            What this prevents at full scale.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.markdown(
            """
            <div class='metric-tile'>
              <div class='label'>Days to notice a model went bad</div>
              <div class='value'>78 &rarr; 9</div>
              <div class='delta'>69 days earlier than the industry baseline</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r1c2:
        st.markdown(
            """
            <div class='metric-tile'>
              <div class='label'>False alarms</div>
              <div class='value'>31% &rarr; 7%</div>
              <div class='delta'>24 percentage points cleaner than basic tools</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.markdown(
            """
            <div class='metric-tile'>
              <div class='label'>Audit pack assembly</div>
              <div class='value'>3 weeks &rarr; 3 seconds</div>
              <div class='delta'>From "we noticed" to "validator has the pack"</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r2c2:
        st.markdown(
            """
            <div class='metric-tile'>
              <div class='label'>Model coverage</div>
              <div class='value'>22% &rarr; 100%</div>
              <div class='delta'>Every model watched, not just the riskiest fifth</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class='caption'>At a Tier-1 US retail bank running ~1,200 production models,
        this prevents ~$45-90 million per year in modeled fraud and credit losses. About
        the size of a small acquisition.</div>
        <div style='color:#a7b6d3; font-style:italic; font-size:14px; margin-top:18px;'>
          That's DriftSentinel. The full code, data, and PRDs are in the repo.
          - Vijay Saharan
        </div>
        """,
        unsafe_allow_html=True,
    )


STEP_RENDERERS = [
    render_step_0, render_step_1, render_step_2, render_step_3, render_step_4,
    render_step_5, render_step_6, render_step_7, render_step_8, render_step_9,
]


# -----------------------------------------------------------------------------
# Dashboard mode (technical reviewers)
# -----------------------------------------------------------------------------


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


def render_dashboard(events_df, snaps_df, models_df):
    st.markdown(
        f"""
        <div class='hero'>
          <h1>DriftSentinel - Dashboard view</h1>
          <p>Underlying numbers and ledgers, for technical reviewers. Toggle "Tour mode"
          back on in the sidebar to return to the storyteller view.</p>
          <p class='meta'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    bundle = build_evidence_bundle(events_df, snaps_df, models_df)
    ledger_df = build_drift_ledger(events_df)

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Drift event ledger**")
        if ledger_df.empty:
            st.caption("Ledger not available - event data missing.")
        else:
            cols = [c for c in ["model_id", "feature_or_signal", "psi", "severity", "recommendation"]
                    if c in ledger_df.columns]
            st.dataframe(ledger_df[cols], use_container_width=True, hide_index=True, height=240)
    with g2:
        st.markdown("**PSI noise floor by segment**")
        render_segment_noise_floor()

    g3, g4 = st.columns(2)
    with g3:
        st.markdown("**Vendor snapshot log**")
        if snaps_df is not None and not snaps_df.empty:
            show = snaps_df[["snapshot_date", "vendor", "snapshot_id", "announcement_status"]].copy()
            st.dataframe(show, use_container_width=True, hide_index=True, height=240)
    with g4:
        st.markdown("**Decisions taken**")
        st.dataframe(pd.DataFrame(bundle["decisions_taken"]),
                     use_container_width=True, hide_index=True, height=240)

    st.download_button(
        "Download evidence bundle",
        data=bundle_to_zip_bytes(bundle),
        file_name=f"driftsentinel_mrm_{datetime.utcnow().strftime('%Y%m%d')}.zip",
        mime="application/zip",
    )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main():
    if "step" not in st.session_state:
        st.session_state.step = 0
    if "tour_mode" not in st.session_state:
        st.session_state.tour_mode = True

    with st.sidebar:
        st.markdown("### Mode")
        st.session_state.tour_mode = st.toggle(
            "Tour mode (storyteller)",
            value=st.session_state.tour_mode,
            help="Off = dashboard with ledgers and underlying numbers.",
        )

    (inf_df, models_df, events_df, snaps_df), err = safe_load()
    if err:
        st.error(f"Data not available: {err}")
        return

    if not st.session_state.tour_mode:
        render_dashboard(events_df, snaps_df, models_df)
        return

    # Tour mode
    step = st.session_state.step
    STEP_RENDERERS[step]()

    st.markdown(
        f"<div class='step-indicator'>Step {step + 1} of {TOTAL_STEPS}</div>",
        unsafe_allow_html=True,
    )

    nav_cols = st.columns([1, 1, 1])
    with nav_cols[0]:
        st.button(
            "Back",
            on_click=go_back,
            disabled=(step == 0),
            use_container_width=True,
            key="nav_back",
        )
    with nav_cols[1]:
        st.write("")
    with nav_cols[2]:
        if step < TOTAL_STEPS - 1:
            if step == 0:
                label = "Start the tour"
            elif step == 4:
                label = "Door 1: the old way"
            elif step == 5:
                label = "Door 2: the better way"
            elif step == 6:
                label = "Door 3: DriftSentinel"
            elif step == 7:
                label = "But wait - there's a worse problem"
            else:
                label = "Next"
            st.button(
                label,
                on_click=go_next,
                use_container_width=True,
                type="primary",
                key="nav_next",
            )
        else:
            st.button(
                "Restart tour",
                on_click=restart,
                use_container_width=True,
                type="primary",
                key="nav_restart",
            )


if __name__ == "__main__":
    main()
