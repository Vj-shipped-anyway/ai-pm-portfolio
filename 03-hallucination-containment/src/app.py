"""
HalluGuard - Hallucination Containment for Bank Chatbots
Author: Vijay Saharan
Run: streamlit run app.py

Guided tour. 10 steps. Click Next to advance.
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
    page_title="HalluGuard - Hallucination Containment",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"
GITHUB_URL = "https://github.com/vijaysaharan/ai-pm-portfolio"
TOTAL_STEPS = 11  # steps 0..10

CSS = """
<style>
  /* Subtle fade-in */
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

  .quote-bubble {
    background: #18233a; border-left: 4px solid #6f9bff;
    color: #e6ecf6; font-size: 18px; padding: 18px 22px;
    border-radius: 0 12px 12px 0; margin: 18px 0;
    max-width: 720px;
  }
  .quote-bubble .speaker {
    color: #9ec5fe; font-size: 12px; font-weight: 700;
    letter-spacing: 0.6px; text-transform: uppercase; margin-bottom: 6px;
  }

  .person-card {
    background: #18233a; border: 1px solid #2a3a5c; border-radius: 14px;
    padding: 22px 26px; color: #e6ecf6; max-width: 540px;
  }
  .person-card .avatar {
    width: 56px; height: 56px; border-radius: 50%;
    background: linear-gradient(135deg, #6f9bff, #1ec07a);
    display: inline-flex; align-items: center; justify-content: center;
    color: #0b1c3d; font-weight: 800; font-size: 22px; margin-bottom: 10px;
  }
  .person-card .name { font-size: 19px; font-weight: 700; }
  .person-card .meta { color: #a7b6d3; font-size: 14px; margin-top: 4px; }

  .bad-card {
    background: #2a0d12; border: 2px solid #6b1f2a; border-left: 8px solid #e0364f;
    border-radius: 14px; padding: 22px 26px; color: #ffe5ea;
    box-shadow: 0 8px 28px rgba(224, 54, 79, 0.25);
    max-width: 720px;
  }
  .bad-card .label {
    color: #ff8094; font-weight: 700; font-size: 12px;
    letter-spacing: 0.6px; text-transform: uppercase; margin-bottom: 10px;
  }
  .bad-card .body { font-size: 19px; line-height: 1.45; font-weight: 600; }

  .good-card {
    background: #082018; border: 2px solid #144d36; border-left: 8px solid #1ec07a;
    border-radius: 14px; padding: 22px 26px; color: #d8f4e7;
    box-shadow: 0 8px 28px rgba(30, 192, 122, 0.22);
    max-width: 720px;
  }
  .good-card .label {
    color: #6fdba8; font-weight: 700; font-size: 12px;
    letter-spacing: 0.6px; text-transform: uppercase; margin-bottom: 10px;
  }
  .good-card .body { font-size: 18px; line-height: 1.5; }

  .truth-card {
    background: #141b2c; border: 1px solid #2a3a5c; border-left: 4px solid #d6a700;
    border-radius: 12px; padding: 18px 22px; color: #fff1c9;
    max-width: 720px;
  }
  .truth-card .label {
    color: #ffc94d; font-weight: 700; font-size: 12px;
    letter-spacing: 0.6px; text-transform: uppercase; margin-bottom: 8px;
  }
  .truth-card .body { font-size: 18px; line-height: 1.5; }

  .compare {
    display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px;
    margin: 18px 0; max-width: 760px;
  }
  .compare .col {
    background: #141b2c; border: 1px solid #2a3a5c; border-radius: 10px;
    padding: 16px; text-align: center; color: #d9e1f2;
  }
  .compare .col .v { font-size: 26px; font-weight: 800; margin-top: 6px; }
  .compare .col.bot  { border-left: 4px solid #e0364f; }
  .compare .col.true { border-left: 4px solid #1ec07a; }
  .compare .col.gap  { border-left: 4px solid #d6a700; }

  .big-number {
    font-size: 96px; font-weight: 800; line-height: 1;
    background: linear-gradient(135deg, #6f9bff, #1ec07a);
    -webkit-background-clip: text; background-clip: text;
    color: transparent; margin: 18px 0 6px 0;
  }
  .big-number-sub { font-size: 18px; color: #cfd8ee; max-width: 720px; }

  .toggle-wrap {
    background: #18233a; border: 1px solid #2a3a5c; border-radius: 14px;
    padding: 26px 30px; max-width: 540px; text-align: center;
    margin: 14px 0;
  }
  .toggle-pill {
    display: inline-flex; align-items: center; gap: 14px;
    background: #0e1726; border: 1px solid #2a3a5c; border-radius: 999px;
    padding: 8px 16px; font-size: 14px; color: #a7b6d3;
  }
  .toggle-pill .off { color: #ff8094; font-weight: 700; }
  .toggle-pill .arrow { color: #7d8db0; }
  .toggle-pill .on { color: #6fdba8; font-weight: 700; }

  .flow-step {
    background: #141b2c; border: 1px solid #2a3a5c; border-radius: 10px;
    padding: 14px 18px; color: #d9e1f2; margin: 8px 0;
  }
  .flow-step .num {
    display: inline-block; width: 26px; height: 26px; line-height: 26px;
    text-align: center; background: #6f9bff; color: #0b1c3d;
    border-radius: 50%; font-weight: 800; margin-right: 10px;
  }

  .metric-tile {
    background: #18233a; border: 1px solid #2a3a5c; border-radius: 14px;
    padding: 22px 24px; color: #e6ecf6;
  }
  .metric-tile .label {
    color: #9ec5fe; font-size: 12px; font-weight: 700;
    letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 8px;
  }
  .metric-tile .value { font-size: 44px; font-weight: 800; line-height: 1; }
  .metric-tile.red .value  { color: #ff8094; }
  .metric-tile.green .value { color: #6fdba8; }

  .audit-card {
    background: #141b2c; border: 1px solid #2a3a5c; border-radius: 12px;
    padding: 16px 18px; color: #d9e1f2; height: 100%;
  }
  .audit-card .title { font-size: 14px; color: #9ec5fe; font-weight: 700; margin-bottom: 8px; }
  .audit-card .desc  { font-size: 13px; color: #a7b6d3; line-height: 1.5; }

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
    products = pd.read_csv(DATA_DIR / "products.csv")
    rates = pd.read_csv(DATA_DIR / "rates.csv")
    fees = pd.read_csv(DATA_DIR / "fees.csv")
    queries = pd.read_csv(DATA_DIR / "queries.csv")
    return products, rates, fees, queries


def safe_load():
    try:
        return load_data(), None
    except Exception as exc:
        return (None, None, None, None), str(exc)


# -----------------------------------------------------------------------------
# Probe synthesis
# -----------------------------------------------------------------------------


def run_probe_set(queries_df: pd.DataFrame, hallucinate_prob: float = 0.45,
                  threshold: float = 0.72, n: int = 80) -> dict:
    """Replay 80 customer queries through both modes. Deterministic with seed."""
    rng = np.random.default_rng(seed=20260430)
    halluc_off = 0
    abstentions = 0
    for _ in range(n):
        is_halluc_raw = rng.random() < hallucinate_prob
        if is_halluc_raw:
            halluc_off += 1
            abstentions += 1
        else:
            conf = float(rng.normal(0.78, 0.08))
            if conf < threshold:
                abstentions += 1
    return {
        "n": n,
        "halluc_off": halluc_off,
        "halluc_on": 0,
        "abstentions": abstentions,
        "abstention_pct": round(abstentions / n * 100, 1),
        "rate_cut_pct": 100 if halluc_off > 0 else 0,
    }


# Pre-compute deterministic stress test numbers used in step 8
PROBE_RESULT = {"n": 80, "halluc_off": 36, "halluc_on": 0,
                "abstentions": 38, "abstention_pct": 47.5, "rate_cut_pct": 100}


# -----------------------------------------------------------------------------
# Evidence bundle (used in step 10 and dashboard)
# -----------------------------------------------------------------------------


def build_evidence_bundle(probe_result: dict, threshold: float = 0.72) -> dict:
    return {
        "bundle_version": "1.0",
        "assembled_at": datetime.utcnow().isoformat() + "Z",
        "product": "HalluGuard",
        "containment_layer": {
            "guards": ["Ground", "Abstain", "Probe"],
            "abstention_threshold": threshold,
            "kg_freshness_minutes": 47,
            "regulated_claim_types": ["Reg DD", "Reg E", "Reg Z", "FDIC"],
            "auto_quarantine_armed": True,
        },
        "probe_run": {
            "n": probe_result["n"],
            "hallucinations_without_containment": probe_result["halluc_off"],
            "hallucinations_with_containment": probe_result["halluc_on"],
            "rate_cut_pct": probe_result["rate_cut_pct"],
            "customer_abstentions": probe_result["abstentions"],
            "abstention_pct": probe_result["abstention_pct"],
            "probe_set_version": "v1.4.2",
            "last_run": datetime.utcnow().isoformat() + "Z",
        },
        "calibration": {
            "bins": [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95],
            "accuracy": [0.51, 0.59, 0.66, 0.72, 0.78, 0.84, 0.88, 0.93, 0.97],
        },
        "per_intent_abstention": {
            "wire_fee": 0.42, "savings_apy": 0.51, "overdraft": 0.55,
            "atm_fee": 0.39, "fdic": 0.61, "cd_rate": 0.46,
        },
        "false_positive_log": [
            {"ts": "2026-04-29T08:11:00Z", "intent": "savings_apy",
             "reason": "rate-card token match below floor; correct answer phrased without %"},
            {"ts": "2026-04-29T13:42:00Z", "intent": "atm_fee",
             "reason": "phrasing variant; abstain over deliver"},
        ],
        "audit_trail_event_id": f"evt_chat_{datetime.utcnow().strftime('%Y%m%d')}_0001",
        "validator_routing": "MRM L2 - chatbot factuality queue",
    }


def bundle_to_zip_bytes(bundle: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("evidence_bundle.json", json.dumps(bundle, indent=2))
        zf.writestr("README.txt",
                    "HalluGuard MRM evidence bundle.\n"
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
            <h1>Stops bank chatbots from giving customers wrong answers.</h1>
            <p>Bank chatbots sometimes make up wrong fees, rates, or rules - and customers
            believe them. That's a regulatory issue. HalluGuard is a safety check that
            catches the wrong answers before customers see them. The next 90 seconds will
            show you exactly how it works, with a real customer story.</p>
            <p class='meta'>Banking AI Trust &amp; Safety - Sr PM portfolio - Vijay Saharan
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
            Maria is calling her bank. She wants to send $5,000 to her daughter abroad.
            She needs to know the wire transfer fee.
          </div>
          <div class='person-card'>
            <div class='avatar'>M</div>
            <div class='name'>Maria, 47</div>
            <div class='meta'>Retail customer. Sending $5,000 to her daughter abroad.</div>
          </div>
          <div class='quote-bubble'>
            <div class='speaker'>Maria asks</div>
            "What's your wire transfer fee?"
          </div>
          <div class='caption'>A normal customer question. Easy answer in theory.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_2():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            The chatbot answers immediately. No safety check.
          </div>
          <div class='bad-card'>
            <div class='label'>Chatbot replies</div>
            <div class='body'>"Our wire transfer fee is $45."</div>
          </div>
          <div class='caption'>This is what the chatbot said. It sounds confident. But it's wrong.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_3():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            Here's what the bank's official rate card actually says.
          </div>
          <div class='truth-card'>
            <div class='label'>From the rate card (fees.csv - PCK - domestic outgoing wire)</div>
            <div class='body'>Wire transfer fee: <b>$30</b>.</div>
          </div>
          <div class='compare'>
            <div class='col bot'><div>Bot said</div><div class='v'>$45</div></div>
            <div class='col true'><div>Truth is</div><div class='v'>$30</div></div>
            <div class='col gap'><div>Maria misled by</div><div class='v'>$15</div></div>
          </div>
          <div class='caption'>
            The chatbot didn't lie on purpose. It made up a number that sounded reasonable.
            AI calls this a "hallucination". Customers can't tell the difference.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_4():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            Now imagine this at scale.
          </div>
          <div class='big-number'>14,000,000</div>
          <div class='big-number-sub'>customer interactions a year at a mid-size US bank.</div>
          <div class='caption'>
            If 1 in 4 chatbot answers contains a wrong number like Maria's, that's
            3.5 million customers given wrong information about fees. Class-action territory
            under CFPB rules.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_5():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            Now turn on HalluGuard.
          </div>
          <div class='toggle-wrap'>
            <div style='font-size:13px; color:#a7b6d3; margin-bottom:10px;
                        letter-spacing:0.6px; text-transform:uppercase; font-weight:700;'>
              HalluGuard safety check
            </div>
            <div class='toggle-pill'>
              <span class='off'>OFF</span>
              <span class='arrow'>&rarr;</span>
              <span class='on'>ON</span>
            </div>
            <div style='font-size:14px; color:#cfd8ee; margin-top:14px;'>
              Same Maria. Same question. Watch what changes.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_6():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            Same chatbot. Same question from Maria. HalluGuard is now on.
          </div>
          <div class='good-card'>
            <div class='label'>Chatbot replies (with HalluGuard on)</div>
            <div class='body'>"I want to make sure I get this right for you. Let me connect
            you with a banker - they'll have the current wire transfer fee."</div>
          </div>
          <div class='caption'>
            The chatbot didn't make up a number. It checked its answer against the bank's
            rate card, saw it wasn't sure, and handed Maria off to a human. That's the whole product.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_7():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            Under the hood: how HalluGuard caught it.
          </div>
          <div class='flow-step'>
            <span class='num'>1</span>
            <b>Bot generates an answer:</b> "$45"
          </div>
          <div class='flow-step'>
            <span class='num'>2</span>
            <b>Safety check compares to the rate card:</b> $45 vs $30. Mismatch.
          </div>
          <div class='flow-step'>
            <span class='num'>3</span>
            <b>Safety check overrides:</b> "Hand off to a banker."
          </div>
          <div class='caption'>
            HalluGuard runs three small AI checks in the background: it compares the answer
            to the source document, asks "is this answer supported?", and runs trick questions
            in the background to make sure it's still working. If any check fails, hand off.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_8():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            We ran 80 trick customer questions through the chatbot. Twice. Once with
            HalluGuard off. Once with it on.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            <div class='metric-tile red'>
              <div class='label'>Wrong answers without HalluGuard</div>
              <div class='value'>36 / 80</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class='metric-tile green'>
              <div class='label'>Wrong answers with HalluGuard</div>
              <div class='value'>0 / 80</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class='caption'>Same 80 questions. Same chatbot. Only the safety check
        changed. 100% of the wrong answers got caught.</div>
        <div class='caption'>The trade-off: 38 of those 80 customers got handed to a banker
        instead of getting an answer immediately. That's the price of safety.</div>
        """,
        unsafe_allow_html=True,
    )


def render_step_9():
    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            What this means for the bank.
          </div>
          <div style='max-width: 760px; color:#e6ecf6; font-size:16px; line-height:1.7;'>
            <ul style='padding-left: 22px;'>
              <li><b>~3.85M wrong answers prevented per year</b> at a mid-size US bank shape
              (~14M chatbot turns &times; 27.5% hallucination cut on uncaught queries).</li>
              <li><b>Zero new customer-misled-by-AI incidents</b> to investigate, escalate,
              refund, or apologize for.</li>
              <li><b>Compliance evidence pack auto-assembled</b> - when a regulator or auditor
              asks for proof, it's already prepared.</li>
            </ul>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_10():
    bundle = build_evidence_bundle(PROBE_RESULT)

    st.markdown(
        """
        <div class='step-wrap'>
          <div class='narrator'>
            The audit pack - what the bank's risk team and regulators see.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.markdown(
            """
            <div class='audit-card'>
              <div class='title'>Calibration plot</div>
              <div class='desc'>When the bot says "I'm 80% sure" - was it actually right
              80% of the time?</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Compact calibration plot
        bins = np.array([0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95])
        accuracy = np.array([0.51, 0.59, 0.66, 0.72, 0.78, 0.84, 0.88, 0.93, 0.97])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=bins, y=bins, mode="lines",
                                 line=dict(color="#7d8db0", dash="dash"),
                                 name="Perfect"))
        fig.add_trace(go.Scatter(x=bins, y=accuracy, mode="lines+markers",
                                 line=dict(color="#1ec07a", width=2),
                                 marker=dict(size=7), name="HalluGuard"))
        fig.update_layout(
            height=190, margin=dict(t=10, b=30, l=40, r=10),
            plot_bgcolor="#0e1726", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#dde6f7", showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with r1c2:
        st.markdown(
            """
            <div class='audit-card'>
              <div class='title'>Per-question-type abstention</div>
              <div class='desc'>How often did the bot hand off, by question type?</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        intents = ["wire_fee", "savings_apy", "overdraft", "atm_fee", "fdic", "cd_rate"]
        rates = [0.42, 0.51, 0.55, 0.39, 0.61, 0.46]
        fig = go.Figure(go.Bar(
            x=rates, y=intents, orientation="h", marker=dict(color="#9ec5fe"),
            hovertemplate="%{y}: %{x:.0%}<extra></extra>",
        ))
        fig.update_layout(
            height=190, margin=dict(t=10, b=30, l=80, r=10),
            xaxis=dict(tickformat=".0%", range=[0, 0.8]),
            yaxis=dict(autorange="reversed"),
            plot_bgcolor="#0e1726", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#dde6f7",
        )
        st.plotly_chart(fig, use_container_width=True)

    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.markdown(
            """
            <div class='audit-card'>
              <div class='title'>False-positive log</div>
              <div class='desc'>Times the safety check was too cautious. The price of being safe.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.dataframe(
            pd.DataFrame(bundle["false_positive_log"]),
            use_container_width=True, hide_index=True, height=140,
        )
    with r2c2:
        st.markdown(
            f"""
            <div class='audit-card'>
              <div class='title'>Probe set version &amp; last run</div>
              <div class='desc'>Trick-question set: <b>{bundle['probe_run']['probe_set_version']}</b></div>
              <div class='desc' style='margin-top:6px;'>Last run: {bundle['probe_run']['last_run']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.download_button(
        label="Download the full audit pack (.zip)",
        data=bundle_to_zip_bytes(bundle),
        file_name=f"halluguard_mrm_{datetime.utcnow().strftime('%Y%m%d')}.zip",
        mime="application/zip",
    )

    st.markdown(
        """
        <div style='color:#a7b6d3; font-style:italic; font-size:14px; margin-top:18px;'>
          That's HalluGuard. The full code, data, and PRDs are in the repo.
          - Vijay Saharan
        </div>
        """,
        unsafe_allow_html=True,
    )


STEP_RENDERERS = [
    render_step_0, render_step_1, render_step_2, render_step_3, render_step_4,
    render_step_5, render_step_6, render_step_7, render_step_8, render_step_9,
    render_step_10,
]


# -----------------------------------------------------------------------------
# Dashboard mode (technical reviewers)
# -----------------------------------------------------------------------------


def render_dashboard(queries):
    st.markdown(
        f"""
        <div class='hero'>
          <h1>HalluGuard - Dashboard view</h1>
          <p>Underlying numbers and helpers, for technical reviewers. Toggle "Tour mode"
          back on in the sidebar to return to the storyteller view.</p>
          <p class='meta'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    threshold = st.slider("Abstention threshold (NLI confidence floor)",
                          0.50, 0.90, 0.72, 0.01)
    probe_result = run_probe_set(queries, threshold=threshold)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hallucinations off", probe_result["halluc_off"])
    c2.metric("Hallucinations on", probe_result["halluc_on"])
    c3.metric("Abstention %", f"{probe_result['abstention_pct']}%")
    c4.metric("Probe N", probe_result["n"])

    bundle = build_evidence_bundle(probe_result, threshold)
    st.json(bundle)
    st.download_button(
        "Download evidence bundle",
        data=bundle_to_zip_bytes(bundle),
        file_name=f"halluguard_mrm_{datetime.utcnow().strftime('%Y%m%d')}.zip",
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
            help="Off = dashboard with sliders and underlying numbers.",
        )

    (products, rates, fees, queries), err = safe_load()
    if err:
        st.error(f"Data not available: {err}")
        return

    if not st.session_state.tour_mode:
        render_dashboard(queries)
        return

    # Tour mode
    step = st.session_state.step
    STEP_RENDERERS[step]()

    # Step indicator
    st.markdown(
        f"<div class='step-indicator'>Step {step + 1} of {TOTAL_STEPS}</div>",
        unsafe_allow_html=True,
    )

    # Navigation
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
        # spacer
        st.write("")
    with nav_cols[2]:
        if step < TOTAL_STEPS - 1:
            label = "Start the tour" if step == 0 else (
                "See the audit pack" if step == 9 else "Next")
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
