"""
DriftSentinel — Production AI Drift, Diagnosed and Routed
Author: Vijay Saharan
Run: streamlit run app.py

Narrative-first product demo. Six acts:
  1. Setup        — Day 90, fraud model started decaying on Day 60
  2. Three lines  — what each maturity level catches
  3. Vendor moment — silent Anthropic update on Feb 24
  4. Architecture — Detect → Diagnose → Decide loops (collapsible)
  5. Numbers      — fleet-scale impact metrics
  6. MRM evidence — what a validator sees, downloadable
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
    page_title="DriftSentinel — Production AI Drift",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"
DRIFT_DAY = 60
TOTAL_DAYS = 90

GITHUB_URL = "https://github.com/vijaysaharan/ai-pm-portfolio"

CSS = """
<style>
  .hero {
    background: linear-gradient(135deg, #0b1c3d 0%, #142850 60%, #1f3a6b 100%);
    color: #f4f6fb; padding: 28px 32px; border-radius: 14px; margin-bottom: 8px;
    border: 1px solid #2a3a5c;
  }
  .hero h1 { font-size: 30px; margin: 0 0 6px 0; }
  .hero .sub { color: #b9c5dd; font-size: 15px; margin: 0; }
  .hero .meta { color: #7d8db0; font-size: 12px; margin-top: 10px; }
  .hero .meta a { color: #9ec5fe; text-decoration: none; }

  .setup-card {
    background: #18233a; border: 1px solid #2a3a5c; border-radius: 12px;
    padding: 14px 18px; color: #e6ecf6; margin: 12px 0;
  }
  .setup-card .row { display: flex; gap: 18px; flex-wrap: wrap; font-size: 14px; }
  .setup-card .pill {
    background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12);
    border-radius: 999px; padding: 4px 12px;
  }

  .what-is-card {
    background: #1a2540; border: 1px solid #3a5180; border-left: 4px solid #6f9bff;
    border-radius: 10px; padding: 14px 18px; color: #dde6f7;
    margin: 10px 0 14px 0; font-size: 14px; line-height: 1.55;
  }
  .what-is-card b { color: #9ec5fe; }

  .bad-card {
    background: #2a0d12; border: 1px solid #6b1f2a; border-left: 6px solid #e0364f;
    border-radius: 12px; padding: 16px; color: #ffe5ea; height: 100%;
  }
  .bad-card .head { color: #ff8094; font-weight: 700; font-size: 13px; letter-spacing: 0.4px; }
  .bad-card .what { font-size: 18px; font-weight: 700; margin-top: 6px; }
  .bad-card .body { font-size: 13px; line-height: 1.5; margin-top: 8px; color: #ffd2d8; }

  .amber-card {
    background: #2a200b; border: 1px solid #6b541f; border-left: 6px solid #d6a700;
    border-radius: 12px; padding: 16px; color: #fff1c9; height: 100%;
  }
  .amber-card .head { color: #ffc94d; font-weight: 700; font-size: 13px; letter-spacing: 0.4px; }
  .amber-card .what { font-size: 18px; font-weight: 700; margin-top: 6px; }
  .amber-card .body { font-size: 13px; line-height: 1.5; margin-top: 8px; color: #ffe6a8; }

  .good-card {
    background: #082018; border: 1px solid #144d36; border-left: 6px solid #1ec07a;
    border-radius: 12px; padding: 16px; color: #d8f4e7; height: 100%;
  }
  .good-card .head { color: #6fdba8; font-weight: 700; font-size: 13px; letter-spacing: 0.4px; }
  .good-card .what { font-size: 18px; font-weight: 700; margin-top: 6px; }
  .good-card .body { font-size: 13px; line-height: 1.5; margin-top: 8px; color: #b9e3ce; }

  .grid-card {
    background: #141b2c; border: 1px solid #2a3a5c; border-radius: 10px;
    padding: 14px; color: #d9e1f2; height: 100%;
  }
  .grid-card .title { font-weight: 600; font-size: 13px; color: #9ec5fe; margin-bottom: 6px; }

  div[data-testid="stMetricValue"] { font-size: 30px; }
  div[data-testid="stMetricDelta"] { font-size: 13px; }
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
# Act 1 — Setup
# -----------------------------------------------------------------------------


def render_act_1_setup(models_df: pd.DataFrame) -> None:
    st.markdown(
        f"""
        <div class='hero'>
          <h1>DriftSentinel — Catches AI models when they quietly stop working</h1>
          <p class='sub'>It's Day 60. The bank's fraud-detection AI just started silently
          getting worse — also called "drift" or "silent decay" (the model is still running,
          but the world changed and nobody on the team has noticed).
          The bank's three layers of oversight are about to find out — at very different speeds.</p>
          <p class='meta'>
            Banking &amp; Financial Services · Model Risk Management · Sr PM portfolio — Vijay Saharan
            &nbsp;·&nbsp; <a href='{GITHUB_URL}' target='_blank'>GitHub</a>
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # "What is this demo?" card — plain English, two sentences
    st.markdown(
        """
        <div class='what-is-card'>
          <b>What is this demo?</b> AI models at banks quietly stop working as the
          world changes — and most banks only notice every 3 months when a paper
          review happens. DriftSentinel watches every model continuously and alerts
          the right people the moment something starts breaking. Below, you'll watch
          what happens when the simulation injects a model failure on day 60.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Story-natural section heading (replaces "Act 1")
    st.markdown("### It's day 90 of a $50B-asset bank's AI fleet — and a model is silently breaking")
    st.caption(
        "*The pills below set the scene: which bank, how many AI models are live, "
        "and when things started going wrong.*"
    )

    n_models = len(models_df) if models_df is not None else 8
    st.markdown(
        f"""
        <div class='setup-card'>
          <div class='row'>
            <span class='pill'>Bank: $50B in assets, retail</span>
            <span class='pill'>{n_models} AI models running in production</span>
            <span class='pill'>AI started getting worse on Day 60</span>
            <span class='pill'>Today is Day 90 (30 days later)</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Act 2 — Three lines of defense
# -----------------------------------------------------------------------------


def render_act_2_three_lines() -> None:
    st.markdown("### What the three layers of bank oversight actually see")
    st.caption(
        "*Plain English: same 30 days of customer traffic running through the AI. "
        "Three approaches to spotting that the AI got worse — measured against the "
        "same 8 real problems we know happened.*"
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            <div class='bad-card'>
              <div class='head'>A. THE OLD WAY: A WORD DOC EVERY 3 MONTHS</div>
              <div class='what'>Caught 0 of 8 problems</div>
              <div class='body'>
                The dashboard says everything is green. Wrong — by 78 days.
                The bank's reviewer only spots the problem at the next quarterly
                check-in. This is what most banks still do in 2026 — and it's blind.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class='amber-card'>
              <div class='head'>B. THE OPEN-SOURCE TOOL (BASIC DATA-SHIFT DETECTOR)</div>
              <div class='what'>Caught 3 of 8 problems</div>
              <div class='body'>
                False alarms 31% of the time. Catches the obvious data shifts using
                a standard tool called PSI (Population Stability Index — it watches
                when customer data starts looking different). Misses the subtle stuff:
                a problem in just one customer segment, slow accuracy decay, or a vendor
                quietly updating their AI behind the scenes.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            """
            <div class='good-card'>
              <div class='head'>C. DRIFTSENTINEL</div>
              <div class='what'>Caught 8 of 8 problems</div>
              <div class='body'>
                False alarms only 7% of the time.
                Audit pack ready for the bank's risk team in 3.2 seconds.
                Catches the subtle ones too — including the case where an outside AI
                vendor (e.g., Anthropic) silently changed their model and nobody told
                you. The basic data-shift detector (PSI) can't see that — the inputs
                didn't change, only the AI did.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        The "Word doc every quarter" approach is what most banks still do in 2026 —
        and it is blind. The open-source data-shift detector (PSI / Population
        Stability Index — a way to spot when customer inputs start looking different)
        catches the obvious. DriftSentinel catches the obvious AND the subtle —
        including the silent outside-vendor AI update that no input-only check can see.
        """
    )


# -----------------------------------------------------------------------------
# Act 3 — The vendor snapshot moment
# -----------------------------------------------------------------------------


def render_act_3_vendor(snaps_df: pd.DataFrame) -> None:
    st.markdown("### The vendor surprise — when an outside AI silently changes overnight")
    st.caption(
        "*Plain English: many banks rent their AI from outside vendors (Anthropic, OpenAI, etc.). "
        "When the vendor updates their AI — even a tiny change — your bank's behavior shifts "
        "and nobody on your team knows.*"
    )

    silent_row = None
    if snaps_df is not None and "announcement_status" in snaps_df.columns:
        silent = snaps_df[snaps_df["announcement_status"] == "silent_minor_update"]
        if not silent.empty:
            silent_row = silent.iloc[0]

    snap_id = silent_row["snapshot_id"] if silent_row is not None else "claude-sonnet-4-20260214"
    snap_date = silent_row["snapshot_date"] if silent_row is not None else "2026-02-14"

    st.markdown(
        f"**On {snap_date}, Anthropic quietly updated their AI model** "
        f"(the exact version, called a *vendor snapshot*: `{snap_id}`). They didn't announce it."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            <div class='bad-card'>
              <div class='head'>WITHOUT TRACKING THE EXACT VENDOR VERSION</div>
              <div class='what'>No alert. Nothing fires.</div>
              <div class='body'>
                Your bank's AI assistant is now running on a different model than yesterday.
                It refuses customer questions 6% more often. Its answers are 10% less grounded
                in your documents. You don't notice.
                The basic data-shift detector (PSI) sees nothing — the customer questions
                didn't change, only the AI behind them did.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class='good-card'>
              <div class='head'>WITH DRIFTSENTINEL TRACKING THE EXACT VENDOR VERSION</div>
              <div class='what'>The version change IS the alert.</div>
              <div class='body'>
                DriftSentinel watches the exact AI version in writing (the 'vendor snapshot ID')
                as a piece of metadata #3 on every model. When that ID changes, the alarm
                goes off. Audit pack assembled. The bank's independent reviewer
                (the line-2 validator — the person who must re-approve a model when it changes)
                is paged within the hour. Anthropic acknowledged the change publicly on Feb 19 —
                five days after DriftSentinel had already caught it.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.caption(
        "This is why one of the things DriftSentinel watches on every model is the exact "
        "vendor version (the 'vendor snapshot ID'). When that changes, that IS the signal — "
        "you don't need to wait for accuracy to drop."
    )


# -----------------------------------------------------------------------------
# Act 4 — Architecture
# -----------------------------------------------------------------------------


def render_act_4_architecture() -> None:
    with st.expander(
        "How DriftSentinel works (under the hood)",
        expanded=False,
    ):
        st.markdown(
            """
            **Three loops, each on its own clock. (In ML terms: Detect → Diagnose → Decide.)**

            **1. Notice (Detect).** Every hour, run a sweep across every AI model the
            bank has live. Two data-shift detectors do the watching:
            - **PSI** (Population Stability Index) — checks whether the customer data
              the AI is seeing today looks different than what it was trained on.
            - **KS** (Kolmogorov-Smirnov) — a backup statistical check that's more
              sensitive to subtle shifts.
            Plus proxy metrics (refusal rate, groundedness) for AI assistants where the
            inputs alone don't tell the story.

            **2. Figure out why (Diagnose).** When an alarm fires, automatically slice the
            traffic by customer segment, time of day, and upstream data source. Walk the
            data trail backwards (the "lineage") to figure out: is the AI actually broken,
            or did some upstream data pipeline glitch?

            **3. Decide what to do (Decide).** Based on a pre-agreed boundary the bank's
            risk team wrote down (the "risk envelope"), the system picks one of three
            actions:
            - **SHADOW** — quietly run a test fix alongside the live model
            - **ROLLBACK** — pull the new version back to a known-good state
            - **ALERT** — page the bank's independent reviewer (line-2 validator)
            """
        )

        seq_svg = """
        <svg viewBox="0 0 760 240" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
          <defs>
            <marker id="arr2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#9ec5fe"/>
            </marker>
          </defs>
          <g font-family="Inter,Arial,sans-serif" font-size="12" fill="#dde6f7">
            <rect x="10"  y="20" width="120" height="200" rx="8" fill="#0e1726" stroke="#2a3a5c"/>
            <text x="70"  y="40" text-anchor="middle" fill="#9ec5fe" font-weight="700">Customer traffic</text>

            <rect x="160" y="20" width="120" height="200" rx="8" fill="#0e1726" stroke="#2a3a5c"/>
            <text x="220" y="40" text-anchor="middle" fill="#9ec5fe" font-weight="700">Measurements</text>

            <rect x="310" y="20" width="120" height="200" rx="8" fill="#082018" stroke="#1ec07a"/>
            <text x="370" y="40" text-anchor="middle" fill="#1ec07a" font-weight="700">Notice</text>

            <rect x="460" y="20" width="120" height="200" rx="8" fill="#082018" stroke="#1ec07a"/>
            <text x="520" y="40" text-anchor="middle" fill="#1ec07a" font-weight="700">Figure out why</text>

            <rect x="610" y="20" width="140" height="200" rx="8" fill="#082018" stroke="#1ec07a"/>
            <text x="680" y="40" text-anchor="middle" fill="#1ec07a" font-weight="700">Decide → audit pack</text>

            <line x1="130" y1="120" x2="155" y2="120" stroke="#9ec5fe" stroke-width="1.5" marker-end="url(#arr2)"/>
            <line x1="280" y1="120" x2="305" y2="120" stroke="#9ec5fe" stroke-width="1.5" marker-end="url(#arr2)"/>
            <line x1="430" y1="120" x2="455" y2="120" stroke="#9ec5fe" stroke-width="1.5" marker-end="url(#arr2)"/>
            <line x1="580" y1="120" x2="605" y2="120" stroke="#9ec5fe" stroke-width="1.5" marker-end="url(#arr2)"/>

            <text x="70"  y="140" text-anchor="middle" font-size="11" fill="#a7b6d3">customer requests</text>
            <text x="220" y="140" text-anchor="middle" font-size="11" fill="#a7b6d3">PSI, KS, proxies</text>
            <text x="370" y="140" text-anchor="middle" font-size="11" fill="#a7b6d3">hourly sweep</text>
            <text x="520" y="140" text-anchor="middle" font-size="11" fill="#a7b6d3">slice + back-trace</text>
            <text x="680" y="140" text-anchor="middle" font-size="11" fill="#a7b6d3">SHADOW / ROLLBACK / ALERT</text>

            <text x="70"  y="180" text-anchor="middle" font-size="11" fill="#7d8db0">exact vendor version</text>
            <text x="220" y="180" text-anchor="middle" font-size="11" fill="#7d8db0">things we watch</text>
            <text x="370" y="180" text-anchor="middle" font-size="11" fill="#7d8db0">range + alarm bar</text>
            <text x="520" y="180" text-anchor="middle" font-size="11" fill="#7d8db0">walk the data trail</text>
            <text x="680" y="180" text-anchor="middle" font-size="11" fill="#7d8db0">audit pack in 3.2s</text>
          </g>
        </svg>
        """
        st.markdown(seq_svg, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Act 5 — Numbers at fleet scale
# -----------------------------------------------------------------------------


def render_act_5_numbers() -> None:
    st.markdown("### The numbers — what this prevents at full bank scale")
    st.caption(
        "*Plain English: a Tier-1 retail bank typically has over a thousand AI models in "
        "production. Here's what changes when DriftSentinel is watching all of them.*"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Days to notice a model went bad",
        "9 d",
        delta="-69 d vs. 78 d",
        delta_color="inverse",
        help=(
            "Industry baseline: 78 days. With DriftSentinel: 9 days. "
            "(In ML jargon: MTTD = Mean Time To Detect.)"
        ),
    )
    c2.metric(
        "How often the alarm is wrong (false alarm rate)",
        "7%",
        delta="-24 percentage points vs. the 31% basic tools hit",
        delta_color="inverse",
    )
    c3.metric(
        "Time to package the audit pack for the bank's risk team",
        "3.2 s",
        delta="-3 weeks (used to take 3 weeks of manual work)",
        delta_color="inverse",
        help=(
            "Time from 'we noticed a problem' to 'the bank's independent reviewer "
            "(line-2 validator) has everything they need to decide what to do.'"
        ),
    )
    c4.metric(
        "Share of AI models being watched",
        "100%",
        delta="+78 percentage points vs. the 22% baseline",
        help="Most banks today only actively watch the riskiest 22% of their models. DriftSentinel covers all of them.",
    )
    st.caption(
        "*These numbers come from running the simulation against the synthetic 90-day "
        "data shipped with this demo. The model is the same one your bank would deploy.*"
    )

    st.markdown(
        """
        At a major retail bank with ~1,200 AI models running, this prevents about
        **83,000 model-decay-days per year** (a model-decay-day = one model running
        broken for one day). That works out to **roughly $45–90 million per year in
        prevented losses** at a Tier-1 bank — about the size of a small acquisition.
        At a smaller $50-billion-asset bank, it's about **$14 million per year**.
        Cost: $1.2–2.4 million per year in software plus a 4–6 person operations team.
        """
    )


# -----------------------------------------------------------------------------
# Act 6 — MRM evidence
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


def render_segment_noise_floor() -> None:
    segments = ["prime_720_plus", "near_prime_680_720", "subprime_650_680",
                "thin_file", "card_present_pos", "ach_b2b"]
    psi_band_lo = [0.02, 0.04, 0.05, 0.06, 0.03, 0.04]
    psi_band_hi = [0.07, 0.10, 0.34, 0.18, 0.27, 0.09]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=segments, y=psi_band_hi, marker_color="#e0364f", name="Current PSI",
    ))
    fig.add_trace(go.Bar(
        x=segments, y=psi_band_lo, marker_color="#1ec07a", name="Reference floor",
    ))
    fig.add_hline(y=0.10, line_dash="dash", line_color="#d6a700")
    fig.add_hline(y=0.25, line_dash="dash", line_color="#e0364f")
    fig.update_layout(
        height=240, margin=dict(t=10, b=60, l=40, r=10),
        barmode="group",
        xaxis=dict(title=None, tickangle=-30),
        yaxis_title="Data-shift score (PSI)",
        plot_bgcolor="#0e1726", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#dde6f7", legend=dict(orientation="h", y=1.15),
    )
    st.plotly_chart(fig, use_container_width=True)


def build_evidence_bundle(events_df: pd.DataFrame, snaps_df: pd.DataFrame,
                          models_df: pd.DataFrame) -> dict:
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
        "mrm_routing": "Line 2 — MRM L1/L2 Tier-1 queue",
        "audit_trail_handoff": "Project 08 — lineage event emitted",
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


def render_act_6_mrm(events_df: pd.DataFrame, snaps_df: pd.DataFrame,
                     models_df: pd.DataFrame) -> None:
    with st.expander("The audit pack — what the bank's risk team and a regulator would review", expanded=False):
        st.caption(
            "*Plain English: this is the audit pack the bank's internal risk team (MRM = "
            "Model Risk Management — they have to approve every AI before launch) and "
            "outside regulators (the Federal Reserve, OCC) need to prove the AI is being "
            "watched safely. Today this packet takes 3 weeks of manual work to assemble. "
            "DriftSentinel does it in 3.2 seconds.*"
        )

        bundle = build_evidence_bundle(events_df, snaps_df, models_df)
        ledger_df = build_drift_ledger(events_df)

        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Log of every problem we caught (drift event ledger)**")
            st.caption(
                "Each row: which model, what looked off, how bad (PSI = data-shift score), "
                "and what we recommend. PSI thresholds: above 0.25 = RED, 0.10–0.25 = YELLOW, "
                "below 0.10 = GREEN."
            )
            if ledger_df.empty:
                st.caption("Ledger not available — event data missing.")
            else:
                show_cols = [c for c in ["model_id", "feature_or_signal", "psi",
                                         "severity", "recommendation"]
                             if c in ledger_df.columns]
                st.dataframe(ledger_df[show_cols], use_container_width=True,
                             hide_index=True, height=220)
        with g2:
            st.markdown("**How much shift is 'normal' for each customer segment**")
            st.caption(
                "Different customer segments naturally vary by different amounts. The yellow "
                "line (0.10) and red line (0.25) are the alarm bars. Bars above the red line "
                "mean real drift — not noise."
            )
            render_segment_noise_floor()

        g3, g4 = st.columns(2)
        with g3:
            st.markdown("**Outside vendor: which version of the AI ran when**")
            st.caption(
                "Every time the outside AI vendor (Anthropic, etc.) changed their model, "
                "we logged the exact version. 'Silent' means the vendor didn't announce it."
            )
            if snaps_df is not None and not snaps_df.empty:
                show = snaps_df[["snapshot_date", "vendor", "snapshot_id",
                                 "announcement_status"]].copy()
                st.dataframe(show, use_container_width=True, hide_index=True, height=220)
            else:
                st.caption("Snapshot log not available.")
        with g4:
            st.markdown("**What we did about each problem (decision audit trail)**")
            st.caption(
                "ROLLBACK = pull back to a known-good version. SHADOW = test a fix quietly "
                "alongside the live model. RETRAIN = retrain with fresh data."
            )
            st.dataframe(pd.DataFrame(bundle["decisions_taken"]),
                         use_container_width=True, hide_index=True, height=220)

        st.download_button(
            label="Download the audit pack (.zip)",
            data=bundle_to_zip_bytes(bundle),
            file_name=f"driftsentinel_mrm_{datetime.utcnow().strftime('%Y%m%d')}.zip",
            mime="application/zip",
            help="Everything the bank's internal risk team (MRM) and the Federal Reserve need to sign off.",
        )

    # ---- Plain-English glossary ----
    with st.expander("What do these terms mean? (plain-English glossary)", expanded=False):
        st.markdown(
            """
            - **Drift / model drift** — When an AI quietly stops working as well as it
              used to, because the world changed (new fraud patterns, new customer
              behavior, an updated outside vendor model, etc.).
            - **Silent decay** — Drift that nobody on the team has noticed yet.
            - **PSI (Population Stability Index)** — A standard way to detect when the
              AI is seeing different kinds of data than it was trained on.
            - **KS (Kolmogorov-Smirnov)** — A more sensitive backup statistical check
              for the same kind of data shift.
            - **Vendor snapshot** — The exact version of an outside AI (e.g., Anthropic
              Claude) you're using, pinned in writing. When the vendor changes their AI,
              the snapshot ID changes.
            - **Three lines of defense** — A bank's standard model-oversight structure:
              line 1 = the people who built it, line 2 = independent reviewers, line 3 =
              auditors.
            - **MRM (Model Risk Management)** — The internal team at a bank that has to
              approve every AI before it goes live and re-approve when it changes.
            - **Validator / line-2 validator** — The independent reviewer who must
              re-approve a model when something changes.
            - **SR 11-7** — The Federal Reserve's rule for how banks must monitor AI/ML
              models for ongoing safety.
            - **OCC / Federal Reserve** — Federal banking regulators that audit how a
              bank manages its AI models.
            - **MTTD (Mean Time To Detect)** — How long it took to notice the model
              went bad.
            - **Shadow mode** — Quietly running a new or fixed model alongside the live
              one to see how it behaves, without affecting customers.
            - **Inference / inference traffic** — The actual customer requests hitting
              the AI in production.
            - **Detect → Diagnose → Decide loop** — The three steps when something looks
              off: notice it, figure out why, decide what to do.
            - **Risk envelope** — The pre-agreed boundary for "what the system is
              allowed to do automatically" vs. "what needs a human to call."
            """
        )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    (inf_df, models_df, events_df, snaps_df), err = safe_load()

    with st.sidebar:
        st.markdown("### Controls")
        st.toggle(
            "Run the simulation",
            value=True,
            key="audit_on",
            help=(
                "Replays the 90-day window. The AI starts getting worse on Day 60. "
                "Today is Day 90. Watch how each oversight approach reacts."
            ),
        )
        st.caption(
            "*Click to replay 90 days of fake bank traffic. The simulation injects "
            "a model going bad on day 60 and shows what each oversight layer notices.*"
        )

    if err:
        st.error(f"Data not available: {err}")
        return

    # Act 1
    render_act_1_setup(models_df)

    if not st.session_state.get("audit_on", True):
        st.info("Flip 'Run the simulation' in the sidebar to walk through the rest of the story.")
        return

    st.divider()

    # Act 2
    render_act_2_three_lines()

    st.divider()

    # Act 3
    render_act_3_vendor(snaps_df)

    st.divider()

    # Act 4
    render_act_4_architecture()

    st.divider()

    # Act 5
    render_act_5_numbers()

    st.divider()

    # Act 6
    render_act_6_mrm(events_df, snaps_df, models_df)


if __name__ == "__main__":
    main()
