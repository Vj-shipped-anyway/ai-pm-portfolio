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
        <div class="hero">
          <h1>DriftSentinel — Production AI Drift, Diagnosed and Routed</h1>
          <p class="sub">It's Day 60. Your fraud model just started silently decaying.
          Your three lines of defense are about to find out — at very different speeds.</p>
          <p class="meta">
            BFSI · MRM · Sr PM portfolio — Vijay Saharan
            &nbsp;·&nbsp; <a href="{GITHUB_URL}" target="_blank">GitHub</a>
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    n_models = len(models_df) if models_df is not None else 8
    st.markdown(
        f"""
        <div class="setup-card">
          <div class="row">
            <span class="pill">Bank: $50B-asset retail</span>
            <span class="pill">{n_models} production AI models</span>
            <span class="pill">Decay injected on Day 60</span>
            <span class="pill">Today is Day 90</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Act 2 — Three lines of defense
# -----------------------------------------------------------------------------


def render_act_2_three_lines() -> None:
    st.markdown("### Act 2 — What the three lines of defense see")
    st.caption(
        "Same 30 days of inference traffic. Three different surveillance regimes."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            <div class="bad-card">
              <div class="head">CARD A · QUARTERLY ATTESTATION (WORD DOC)</div>
              <div class="what">0 of 8 drifts caught</div>
              <div class="body">
                Says GREEN. Wrong by 78 days.
                Validator sees the drift only at the next quarterly review.
                The BFSI default in 2026 — and it is blind.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="amber-card">
              <div class="head">CARD B · BASIC PSI DRIFT (OPEN-SOURCE)</div>
              <div class="what">3 of 8 drifts caught</div>
              <div class="body">
                False-positive rate: 31%.
                Catches the obvious shifts. Misses slice drift,
                proxy-metric decay, and silent vendor model swaps.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            """
            <div class="good-card">
              <div class="head">CARD C · DRIFTSENTINEL</div>
              <div class="what">8 of 8 drifts caught</div>
              <div class="body">
                False-positive rate: 7%.
                MRM bundle assembled in 3.2s.
                Catches the subtle ones too — including silent vendor updates
                that no input-distribution PSI can see.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        Quarterly attestation is the BFSI default in 2026 — it is blind.
        Basic PSI (Population Stability Index — a way to detect when the input
        data shifts) catches the obvious. DriftSentinel catches the obvious AND
        the subtle, including the GenAI silent vendor update that no input-PSI
        can see.
        """
    )


# -----------------------------------------------------------------------------
# Act 3 — The vendor snapshot moment
# -----------------------------------------------------------------------------


def render_act_3_vendor(snaps_df: pd.DataFrame) -> None:
    st.markdown("### Act 3 — The vendor snapshot moment")

    silent_row = None
    if snaps_df is not None and "announcement_status" in snaps_df.columns:
        silent = snaps_df[snaps_df["announcement_status"] == "silent_minor_update"]
        if not silent.empty:
            silent_row = silent.iloc[0]

    snap_id = silent_row["snapshot_id"] if silent_row is not None else "claude-sonnet-4-20260214"
    snap_date = silent_row["snapshot_date"] if silent_row is not None else "2026-02-14"

    st.markdown(
        f"**Anthropic silently updated their model on {snap_date}** "
        f"(snapshot `{snap_id}`)."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            <div class="bad-card">
              <div class="head">WITHOUT SNAPSHOT PIN</div>
              <div class="what">0 detection signal</div>
              <div class="body">
                Your GenAI assistant is now using a different model.
                Refusal rate ticked up 6 points. Groundedness dropped 0.10.
                You don't know. Input-distribution PSI sees nothing because
                the inputs didn't change.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="good-card">
              <div class="head">WITH SNAPSHOT PIN</div>
              <div class="what">Version diff is the alert</div>
              <div class="body">
                Sentinel's tracked attribute #3 is the vendor snapshot ID.
                The diff fires the alert. MRM bundle assembled.
                Validator on call within the hour.
                Anthropic acknowledged the update post-hoc on Feb 19.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.caption(
        "This is why Tracked Attribute #3 in DriftSentinel is the vendor "
        "snapshot ID. The version diff IS the signal."
    )


# -----------------------------------------------------------------------------
# Act 4 — Architecture
# -----------------------------------------------------------------------------


def render_act_4_architecture() -> None:
    with st.expander("Act 4 — How DriftSentinel works (architecture)", expanded=False):
        st.markdown(
            """
            **Three loops. Each one runs on its own clock.**

            **Detect loop.** PSI/KS/proxy-metric sweep, runs hourly per model.
            PSI compares input distributions. KS (Kolmogorov-Smirnov — a
            statistical test for whether two samples come from the same
            distribution) backs it up. Proxy metrics catch the GenAI cases
            where input PSI is silent.

            **Diagnose loop.** When a signal fires, the system segments the
            traffic, bisects on time, and walks lineage upstream to find
            whether the drift is real or a pipeline artifact.

            **Decide loop.** Chooses an action — SHADOW, ROLLBACK-staging,
            or ALERT-validator — based on a bounded risk envelope written
            into the model's MRM file.
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
            <text x="70"  y="40" text-anchor="middle" fill="#9ec5fe" font-weight="700">Inference</text>

            <rect x="160" y="20" width="120" height="200" rx="8" fill="#0e1726" stroke="#2a3a5c"/>
            <text x="220" y="40" text-anchor="middle" fill="#9ec5fe" font-weight="700">Telemetry</text>

            <rect x="310" y="20" width="120" height="200" rx="8" fill="#082018" stroke="#1ec07a"/>
            <text x="370" y="40" text-anchor="middle" fill="#1ec07a" font-weight="700">Detect</text>

            <rect x="460" y="20" width="120" height="200" rx="8" fill="#082018" stroke="#1ec07a"/>
            <text x="520" y="40" text-anchor="middle" fill="#1ec07a" font-weight="700">Diagnose</text>

            <rect x="610" y="20" width="140" height="200" rx="8" fill="#082018" stroke="#1ec07a"/>
            <text x="680" y="40" text-anchor="middle" fill="#1ec07a" font-weight="700">Decide → MRM</text>

            <line x1="130" y1="120" x2="155" y2="120" stroke="#9ec5fe" stroke-width="1.5" marker-end="url(#arr2)"/>
            <line x1="280" y1="120" x2="305" y2="120" stroke="#9ec5fe" stroke-width="1.5" marker-end="url(#arr2)"/>
            <line x1="430" y1="120" x2="455" y2="120" stroke="#9ec5fe" stroke-width="1.5" marker-end="url(#arr2)"/>
            <line x1="580" y1="120" x2="605" y2="120" stroke="#9ec5fe" stroke-width="1.5" marker-end="url(#arr2)"/>

            <text x="70"  y="140" text-anchor="middle" font-size="11" fill="#a7b6d3">requests / responses</text>
            <text x="220" y="140" text-anchor="middle" font-size="11" fill="#a7b6d3">PSI, KS, proxies</text>
            <text x="370" y="140" text-anchor="middle" font-size="11" fill="#a7b6d3">hourly sweep</text>
            <text x="520" y="140" text-anchor="middle" font-size="11" fill="#a7b6d3">segment + bisect</text>
            <text x="680" y="140" text-anchor="middle" font-size="11" fill="#a7b6d3">SHADOW / ROLLBACK / ALERT</text>

            <text x="70"  y="180" text-anchor="middle" font-size="11" fill="#7d8db0">vendor snapshot id</text>
            <text x="220" y="180" text-anchor="middle" font-size="11" fill="#7d8db0">tracked attributes</text>
            <text x="370" y="180" text-anchor="middle" font-size="11" fill="#7d8db0">band + threshold</text>
            <text x="520" y="180" text-anchor="middle" font-size="11" fill="#7d8db0">lineage walk</text>
            <text x="680" y="180" text-anchor="middle" font-size="11" fill="#7d8db0">bundle in 3.2s</text>
          </g>
        </svg>
        """
        st.markdown(seq_svg, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Act 5 — Numbers at fleet scale
# -----------------------------------------------------------------------------


def render_act_5_numbers() -> None:
    st.markdown("### Act 5 — The numbers at Tier-1 fleet scale")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Drift MTTD", "9 d", delta="-69 d vs. 78 d", delta_color="inverse",
              help="MTTD = Mean Time To Detect. Industry baseline: 78 days.")
    c2.metric("False-positive rate", "7%", delta="-24 pp vs. 31%", delta_color="inverse")
    c3.metric("MRM evidence bundle", "3.2 s", delta="-3 weeks", delta_color="inverse",
              help="Time from drift signal to validator-ready evidence package.")
    c4.metric("Model coverage", "100%", delta="+78 pp vs. 22%")

    st.markdown(
        """
        At Tier-1 fleet scale (~1,200 production models), this is **~83,000
        model-decay-days prevented annually**. **~$45–90M/yr modeled
        prevented loss** at a Tier-1 retail bank. **~$14M/yr** at the
        $50B-asset shape. Cost: $1.2–2.4M/yr software plus a 4–6 person ops team.
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
        yaxis_title="PSI",
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
    with st.expander("Act 6 — What MRM / a validator sees", expanded=False):
        st.caption(
            "Auto-assembled MRM evidence bundle. Same shape MRM teams attest "
            "against today — they just don't have to wait three weeks for it."
        )

        bundle = build_evidence_bundle(events_df, snaps_df, models_df)
        ledger_df = build_drift_ledger(events_df)

        g1, g2 = st.columns(2)
        with g1:
            st.markdown('<div class="grid-card"><div class="title">Drift event ledger</div>',
                        unsafe_allow_html=True)
            if ledger_df.empty:
                st.caption("Ledger not available — event data missing.")
            else:
                show_cols = [c for c in ["model_id", "feature_or_signal", "psi",
                                         "severity", "recommendation"]
                             if c in ledger_df.columns]
                st.dataframe(ledger_df[show_cols], use_container_width=True,
                             hide_index=True, height=220)
            st.markdown("</div>", unsafe_allow_html=True)
        with g2:
            st.markdown('<div class="grid-card"><div class="title">Segment-aware noise floor</div>',
                        unsafe_allow_html=True)
            render_segment_noise_floor()
            st.markdown("</div>", unsafe_allow_html=True)

        g3, g4 = st.columns(2)
        with g3:
            st.markdown('<div class="grid-card"><div class="title">Vendor snapshot diff log</div>',
                        unsafe_allow_html=True)
            if snaps_df is not None and not snaps_df.empty:
                show = snaps_df[["snapshot_date", "vendor", "snapshot_id",
                                 "announcement_status"]].copy()
                st.dataframe(show, use_container_width=True, hide_index=True, height=220)
            else:
                st.caption("Snapshot log not available.")
            st.markdown("</div>", unsafe_allow_html=True)
        with g4:
            st.markdown('<div class="grid-card"><div class="title">Decision audit trail</div>',
                        unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(bundle["decisions_taken"]),
                         use_container_width=True, hide_index=True, height=220)
            st.markdown("</div>", unsafe_allow_html=True)

        st.download_button(
            label="Download MRM evidence pack (.zip)",
            data=bundle_to_zip_bytes(bundle),
            file_name=f"driftsentinel_mrm_{datetime.utcnow().strftime('%Y%m%d')}.zip",
            mime="application/zip",
        )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    (inf_df, models_df, events_df, snaps_df), err = safe_load()

    with st.sidebar:
        st.markdown("### Controls")
        st.toggle("Run the audit", value=True, key="audit_on",
                  help="Replays the 90-day window with the drift event injected on Day 60.")

    if err:
        st.error(f"Data not available: {err}")
        return

    # Act 1
    render_act_1_setup(models_df)

    if not st.session_state.get("audit_on", True):
        st.info("Toggle 'Run the audit' in the sidebar to advance through Acts 2–6.")
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
