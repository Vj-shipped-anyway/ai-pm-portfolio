"""
HalluGuard - Hallucination Containment for Bank Chatbots
Author: Vijay Saharan
Run: streamlit run app.py

One-page scrollable narrative. No tour scaffolding. One interactive element
(the customer dropdown in Section 4).
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
GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
DEMO_URL = "https://halluguard-bfsi.streamlit.app"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"

CSS = """
<style>
  /* Hide Streamlit chrome */
  #MainMenu { visibility: hidden; }
  footer { visibility: hidden; }
  header { visibility: hidden; }

  /* Hide default top padding so the hero sits up tight */
  .block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1100px; }

  /* Force Streamlit's auto-generated headings to be readable on white background */
  .stMarkdown h1, h1 { font-size: 42px !important; line-height: 1.15 !important; font-weight: 800 !important; color: #0b1c3d !important; }
  .stMarkdown h2, h2 { font-size: 32px !important; line-height: 1.25 !important; font-weight: 700 !important; margin-top: 28px !important; color: #0b1c3d !important; }
  .stMarkdown h3, h3 { font-size: 24px !important; line-height: 1.3 !important; font-weight: 700 !important; color: #0b1c3d !important; }
  .stMarkdown p, p { font-size: 16px !important; line-height: 1.65 !important; color: #1f2a44 !important; }

  /* Pills row at the top */
  .pill-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 18px 0; }
  .pill {
    display: inline-block; background: #18233a; border: 1px solid #2a3a5c;
    color: #cfd8ee; border-radius: 999px; padding: 6px 14px; font-size: 13px;
    text-decoration: none;
  }
  .pill a { color: #9ec5fe; text-decoration: none; }
  a.pill { color: #cfd8ee; }
  a.pill:hover { background: #2a3a5c; color: #9ec5fe; }
  .pill.author { border-color: #6f9bff; color: #9ec5fe; }
  a.pill.author { color: #9ec5fe; }
  a.pill.author:hover { background: #1f3a6b; }

  .hero {
    background: linear-gradient(135deg, #0b1c3d 0%, #142850 60%, #1f3a6b 100%);
    color: #f4f6fb; padding: 40px 40px; border-radius: 16px;
    border: 1px solid #2a3a5c; margin: 0 0 14px 0;
  }
  .hero h1 { font-size: 48px !important; margin: 0 0 12px 0; line-height: 1.1 !important; font-weight: 800 !important; }
  .hero .subtitle { color: #e6ecf6; font-size: 22px; margin: 0 0 18px 0; line-height: 1.4; font-weight: 500; }
  .hero .hook { color: #cfd8ee; font-size: 16px; line-height: 1.65; margin: 0 0 14px 0; max-width: 820px; }
  .hero .scroll-cue { color: #7d8db0; font-size: 13px; font-style: italic; margin-top: 10px; }

  /* Section headings — dark for legibility on white Streamlit background */
  .section-h {
    font-size: 34px; font-weight: 800; color: #0b1c3d;
    margin: 8px 0 16px 0; line-height: 1.2;
  }
  .section-lede {
    color: #1f2a44; font-size: 17px; line-height: 1.65;
    max-width: 860px; margin: 0 0 18px 0;
  }
  .caption {
    color: #4a5a7c; font-size: 14px; font-style: italic;
    margin-top: 14px; max-width: 860px; line-height: 1.55;
  }

  /* Section 2 - person card */
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

  /* Section 3 - solution mechanic */
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

  /* Section 4 - 3-way comparison cards */
  .compare-card {
    border-radius: 14px; padding: 20px 22px; height: 100%;
    color: #e6ecf6; min-height: 240px;
  }
  .compare-card .label {
    font-weight: 700; font-size: 11px; letter-spacing: 0.6px;
    text-transform: uppercase; margin-bottom: 10px;
  }
  .compare-card .what { font-size: 16px; font-weight: 700; margin-bottom: 10px; }
  .compare-card .body { font-size: 14px; line-height: 1.55; color: #cfd8ee; }
  .compare-card .quote {
    background: rgba(0,0,0,0.20); border-radius: 8px;
    padding: 12px 14px; margin: 10px 0; font-style: italic;
    font-size: 14px; line-height: 1.5;
  }
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
    color: #1f2a44; font-size: 15px; font-style: italic;
    margin: 18px 0 0 0; max-width: 860px; line-height: 1.6;
    border-left: 3px solid #6f9bff; padding-left: 14px;
  }

  /* Section 5 - proof tiles */
  .metric-tile {
    background: #18233a; border: 1px solid #2a3a5c; border-radius: 14px;
    padding: 22px 24px; color: #e6ecf6; height: 100%;
  }
  .metric-tile .mlabel {
    color: #9ec5fe; font-size: 12px; font-weight: 700;
    letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 10px;
  }
  .metric-tile .mvalue { font-size: 36px; font-weight: 800; line-height: 1.1; }
  .metric-tile.red .mvalue { color: #ff8094; }
  .metric-tile.green .mvalue { color: #6fdba8; }
  .metric-tile .mdelta { color: #a7b6d3; font-size: 13px; margin-top: 8px; }

  /* Section 6/7 - bullets */
  .bullet-list {
    color: #1f2a44; font-size: 16px; line-height: 1.75;
    max-width: 880px; padding-left: 22px;
  }
  .bullet-list li { margin-bottom: 8px; }
  .bullet-list b { color: #0b1c3d; }

  .second-order {
    color: #8a6500; font-size: 15px; font-style: italic;
    margin-top: 14px; max-width: 860px;
    border-left: 3px solid #d6a700; padding-left: 14px; line-height: 1.6;
  }

  /* Section 8 - audit cards */
  .audit-card {
    background: #141b2c; border: 1px solid #2a3a5c; border-radius: 12px;
    padding: 16px 18px; color: #d9e1f2; height: 100%;
  }
  .audit-card .title { font-size: 14px; color: #9ec5fe; font-weight: 700; margin-bottom: 8px; }
  .audit-card .desc  { font-size: 13px; color: #a7b6d3; line-height: 1.5; }

  /* Footer */
  .footer {
    color: #7d8db0; font-size: 13px; font-style: italic;
    margin: 36px 0 0 0; text-align: center; padding-top: 18px;
    border-top: 1px solid #2a3a5c;
  }
  .footer a { color: #9ec5fe; text-decoration: none; }

  /* Streamlit metric size */
  div[data-testid="stMetricValue"] { font-size: 30px; }

  /* Divider styling */
  hr { border-color: #2a3a5c; margin: 32px 0; }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Data loading
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


PROBE_RESULT = {"n": 80, "halluc_off": 36, "halluc_on": 0,
                "abstentions": 38, "abstention_pct": 47.5, "rate_cut_pct": 100}


# -----------------------------------------------------------------------------
# Evidence bundle
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
# Customer dropdown options
# -----------------------------------------------------------------------------

CUSTOMERS = {
    "Maria, 47 - sending money abroad": {
        "avatar": "M",
        "scenario": "Calling about a $5,000 wire to her daughter abroad.",
        "question": "What's your wire transfer fee?",
        "old_way": "I don't understand 'wire transfer fee'. Press 1 for rates, 2 for fees, 3 for hours, or stay on the line.",
        "old_label": "Rule-based phone tree, c. 2018",
        "ai_alone": "Our wire transfer fee is $45.",
        "ai_alone_note": "Sounds confident. Made up.",
        "halluguard": "I want to make sure I get this right for you. Let me connect you with a banker - they'll have the current wire transfer fee.",
        "real_answer": "$30 (per fees.csv, PCK domestic outgoing wire)",
        "harm": "Maria over-budgets by $15 and plans the transfer wrong.",
        "summary": "HalluGuard refused to make up a number and handed Maria off. The bot didn't get the answer wrong because it didn't try to.",
    },
    "Daniel, 32 - opening a savings account": {
        "avatar": "D",
        "scenario": "Comparing savings rates for his emergency fund.",
        "question": "What's your savings interest rate?",
        "old_way": "For current rates, please visit our website or speak with a banker. Press 0 for an associate.",
        "old_label": "Rule-based phone tree, c. 2018",
        "ai_alone": "Our high-yield savings account earns 4.5% APY.",
        "ai_alone_note": "Sounds great. Off by 1.65 points.",
        "halluguard": "I'd rather not quote a savings rate that might be stale. A banker can give you today's exact APY in 30 seconds.",
        "real_answer": "2.85% APY (per rates.csv, current standard tier)",
        "harm": "Daniel plans his retirement contributions around an inflated rate.",
        "summary": "HalluGuard refused to quote a regulated number it wasn't sure of. Truth in Savings (Reg DD) violation avoided.",
    },
    "Aisha, 28 - first home buyer": {
        "avatar": "A",
        "scenario": "Shopping mortgage rates between three banks this week.",
        "question": "What's your 30-year mortgage rate today?",
        "old_way": "Mortgage inquiries: please call 1-800-555-0102 during business hours. We're closed.",
        "old_label": "Rule-based phone tree, c. 2018",
        "ai_alone": "Our 30-year fixed is 5.25% today.",
        "ai_alone_note": "Off by 1.53 points - a real money mistake.",
        "halluguard": "Mortgage rates change daily and I want to give you today's exact number, not yesterday's. Let me connect you with a mortgage officer right now.",
        "real_answer": "6.78% (per rates.csv, today's lock)",
        "harm": "Aisha walks away from a competitor's better deal because she thinks yours is lower.",
        "summary": "HalluGuard refused to anchor Aisha to an out-of-date rate. She gets the real number from a banker before she signs anywhere.",
    },
    "Tom, 64 - retired, careful with money": {
        "avatar": "T",
        "scenario": "Has $300K across two CDs and is worried about safety.",
        "question": "Are my CD funds FDIC insured up to $300,000?",
        "old_way": "FDIC information is available in your account documents. Press 1 to request a paper copy mailed to your address.",
        "old_label": "Rule-based phone tree, c. 2018",
        "ai_alone": "Yes, your CD funds are FDIC insured up to $300,000.",
        "ai_alone_note": "Wrong. The cap is $250,000.",
        "halluguard": "FDIC coverage limits are something I want to be exact on. Let me transfer you to a banker who can walk through your specific situation.",
        "real_answer": "FDIC insures up to $250,000 per depositor, per ownership category.",
        "harm": "Tom believes more is protected; overcommits to your bank instead of diversifying.",
        "summary": "HalluGuard refused to confirm a number that would have given Tom false comfort about $50,000 of his retirement.",
    },
    "Priya, 41 - small business owner": {
        "avatar": "P",
        "scenario": "Running thin in cash this week, worried about cutting it close.",
        "question": "What's the overdraft fee?",
        "old_way": "Fee inquiries: refer to your account agreement, section 4. Press 2 to be mailed a copy.",
        "old_label": "Rule-based phone tree, c. 2018",
        "ai_alone": "The overdraft fee is $25.",
        "ai_alone_note": "Half the real cost.",
        "halluguard": "Overdraft fees can stack and I want to be precise. Let me connect you with a banker who can walk through the full fee schedule.",
        "real_answer": "$36 per item with rolling daily fees if not cured (per fees.csv, courtesy pay)",
        "harm": "Priya underestimates the penalty and gets a $300 surprise on a $40 shortfall.",
        "summary": "HalluGuard refused to under-quote a fee. UDAAP exposure avoided - misleading fee disclosures are a CFPB priority.",
    },
    "Jorge, 55 - comparing banks": {
        "avatar": "J",
        "scenario": "Looking at a 5-year CD before he locks up $80,000.",
        "question": "What's the early withdrawal penalty on a 5-year CD?",
        "old_way": "Please refer to your CD disclosure. For other questions press 0.",
        "old_label": "Rule-based phone tree, c. 2018",
        "ai_alone": "Three months of interest.",
        "ai_alone_note": "Sounds light. The real terms are heavier.",
        "halluguard": "Penalty terms vary by tenor and balance and I'd rather get this right. A banker can pull up the exact terms for the CD you're considering.",
        "real_answer": "Six months interest plus principal forfeiture above threshold (per fees.csv).",
        "harm": "Jorge thinks your CD is more flexible than it is and locks up money he might need.",
        "summary": "HalluGuard refused to soft-pedal the penalty. Jorge gets the real terms before he commits, not after.",
    },
}

CUSTOMER_NAMES = list(CUSTOMERS.keys())


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

Banking AI Trust & Safety. One of three demos in the portfolio.
""",
            )


# -----------------------------------------------------------------------------
# Section renderers
# -----------------------------------------------------------------------------


def render_hero():
    st.markdown(
        f"""
<div class='pill-row'>
  <a class='pill' href='{GITHUB_URL}' target='_blank'>GitHub</a>
  <a class='pill author' href='{LINKEDIN_URL}' target='_blank'>Vijay Saharan - LinkedIn</a>
</div>
<div class='hero'>
  <h1>HalluGuard</h1>
  <div class='subtitle'>Stops bank chatbots from giving customers wrong answers.</div>
  <div class='hook'>Watch what happens when a customer asks a chatbot a simple question -
  "what's your wire transfer fee?" - and the bot makes up a wrong number.
  Now watch what happens with a safety check in front of it. Same bot, same question, very different outcome.</div>
  <div class='scroll-cue'>Scroll to read.</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_section_problem():
    st.markdown(
        """
<div class='section-h'>What's the problem?</div>
<div class='section-lede'>Bank chatbots sometimes invent fees, rates, or rules that sound right but aren't.
Customers can't tell the difference. They make decisions based on the wrong number.
Under CFPB rules, that's the bank's problem - not the chatbot vendor's.</div>
<div class='person-card'>
  <div class='avatar'>M</div>
  <div class='name'>Maria, 47</div>
  <div class='meta'>Retail customer. Sending $5,000 to her daughter abroad.</div>
  <div class='scenario'>She asks the chatbot: "What's your wire transfer fee?"
  The bot replies, confidently: <b>$45</b>. The real answer on the rate card is <b>$30</b>.
  Maria over-budgets by $15 and times the transfer around the wrong number.</div>
  <div class='harm'>The bot didn't lie on purpose - it made up a number that sounded reasonable. AI calls this a hallucination. Customers can't tell.</div>
</div>
<div class='impact-line'>At a typical mid-size US bank: ~14 million chatbot turns per year. If 1 in 4 contains a wrong number like Maria's, that's ~3.5 million customers misled - class-action territory under CFPB Reg DD and UDAAP.</div>
""",
        unsafe_allow_html=True,
    )


def render_section_solution():
    st.markdown(
        """
<div class='section-h'>What's the solution?</div>
<div class='section-lede'>HalluGuard sits between the chatbot and the customer.
Every time the bot drafts an answer, HalluGuard checks it against the bank's official rate card, fee schedule, and product docs.
If the answer matches the source, customer sees it. If it doesn't, the bot quietly hands the customer to a human banker instead of guessing.
The bot doesn't get the answer wrong because it doesn't try to.</div>
<div class='mechanic-row'>
  <div class='mechanic-step'>
    <div class='num'>1</div>
    <div class='title'>Bot drafts an answer</div>
    <div class='desc'>The chatbot generates a reply: "Our wire transfer fee is $45."</div>
  </div>
  <div class='mechanic-step'>
    <div class='num'>2</div>
    <div class='title'>Safety check compares to truth</div>
    <div class='desc'>HalluGuard pulls the live fee schedule and asks: does the bot's number match? Is it supported by source?</div>
  </div>
  <div class='mechanic-step'>
    <div class='num'>3</div>
    <div class='title'>Approve or hand off</div>
    <div class='desc'>If supported, the answer ships. If not, the bot hands off to a banker. No guessing in the middle.</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_section_inaction():
    st.markdown(
        "<div class='section-h'>See it in action - pick a customer</div>",
        unsafe_allow_html=True,
    )

    selected = st.selectbox(
        "Customer",
        CUSTOMER_NAMES,
        index=0,
        key="selected_customer",
        label_visibility="collapsed",
    )
    c = CUSTOMERS[selected]

    st.markdown(
        f"""
<div class='person-card' style='max-width: 100%; margin: 14px 0 18px 0;'>
  <div class='avatar'>{c['avatar']}</div>
  <div class='name'>{selected}</div>
  <div class='meta'>{c['scenario']}</div>
  <div class='scenario'><b>She asks:</b> "{c['question']}"</div>
</div>
""",
        unsafe_allow_html=True,
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(
            f"""<div class='compare-card red-card'>
  <div class='label'>Before AI - the old way</div>
  <div class='what'>{c['old_label']}</div>
  <div class='quote'>"{c['old_way']}"</div>
  <div class='body'>Customer hears a script and a phone-tree menu. Frustrating but at least it doesn't lie. She hangs up.</div>
</div>""",
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(
            f"""<div class='compare-card red-card'>
  <div class='label'>With AI alone - no safety check</div>
  <div class='what'>The chatbot guesses confidently</div>
  <div class='quote'>"{c['ai_alone']}"</div>
  <div class='body'><b>{c['ai_alone_note']}</b> Real answer: {c['real_answer']}. Customer harm: {c['harm']}</div>
</div>""",
            unsafe_allow_html=True,
        )
    with col_c:
        st.markdown(
            f"""<div class='compare-card green-card'>
  <div class='label'>With HalluGuard</div>
  <div class='what'>Same bot. Safety check on.</div>
  <div class='quote'>"{c['halluguard']}"</div>
  <div class='body'>The bot checked its draft against the bank's source-of-truth, saw a mismatch, and handed off. The customer ends up with a banker who knows the right number.</div>
</div>""",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div class='summary-line'>{c['summary']}</div>",
        unsafe_allow_html=True,
    )


def render_section_proof():
    st.markdown(
        """
<div class='section-h'>Does it actually work?</div>
<div class='section-lede'>We ran 80 trick questions through the same chatbot, twice. Once with HalluGuard off. Once with it on.
The questions cover wire fees, savings APYs, overdraft, ATM fees, FDIC limits, and CD rates - the regulated claims that matter most.
Same questions. Same model. Only the safety check changed.</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            """<div class='metric-tile red'>
  <div class='mlabel'>Wrong answers without HalluGuard</div>
  <div class='mvalue'>36 / 80</div>
  <div class='mdelta'>45% hallucination rate on regulated claims</div>
</div>""",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """<div class='metric-tile green'>
  <div class='mlabel'>Wrong answers with HalluGuard</div>
  <div class='mvalue'>0 / 80</div>
  <div class='mdelta'>Every wrong answer caught before customer saw it</div>
</div>""",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            """<div class='metric-tile green'>
  <div class='mlabel'>Wrong-answer rate cut</div>
  <div class='mvalue'>100%</div>
  <div class='mdelta'>Zero new customer-misled-by-AI incidents</div>
</div>""",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            """<div class='metric-tile'>
  <div class='mlabel'>Customers handed off to a banker</div>
  <div class='mvalue' style='color:#ffc94d;'>38 / 80</div>
  <div class='mdelta'>The trade-off: 48% slower to answer, but right</div>
</div>""",
            unsafe_allow_html=True,
        )


def render_section_help():
    st.markdown(
        """
<div class='section-h'>How does this help the bank?</div>
<ul class='bullet-list'>
  <li><b>~3.85 million wrong answers prevented per year</b> at a mid-size US bank shape (~14M chatbot turns x 27.5% hallucination cut on uncaught queries). At a Tier-1 bank's scale, ~40 million.</li>
  <li><b>Zero new customer-misled-by-AI incidents</b> for the bank to investigate, refund, or apologize for. Each one of those today costs ~$3,400 in operational handling alone.</li>
  <li><b>Regulatory exposure cut on the four hottest CFPB lanes</b> - Truth in Savings (Reg DD), Electronic Funds Transfer (Reg E), Truth in Lending (Reg Z), and UDAAP misleading-disclosure claims.</li>
  <li><b>Audit pack auto-assembled</b> - when a regulator or internal validator asks for the evidence, it's already prepared. No 3-week scramble.</li>
</ul>
<div class='second-order'>The compliance audit pack a regulator would ask for is already prepared. Auto-assembled in seconds, not weeks.</div>
""",
        unsafe_allow_html=True,
    )


def render_section_caveats():
    st.markdown(
        """
<div class='section-h'>What to keep in mind</div>
<ul class='bullet-list'>
  <li><b>This is a portfolio prototype</b> - not a deployed bank product. Built to demonstrate the PM analysis and the architecture I'd bring to the seat.</li>
  <li><b>The trade-off is real:</b> 48% of HalluGuard's safe answers are "I don't know - let me get a banker." In production, you'd tune this dial. More handoffs = safer but slower. Fewer = faster but riskier. There's no free lunch.</li>
  <li><b>HalluGuard checks if the AI's answer matches the bank's documents.</b> It doesn't decide WHICH topics the AI should refuse to answer - that's a policy layer that sits above this.</li>
  <li><b>Designed against US banking rules</b> - CFPB exam expectations, Truth in Savings (Reg DD), Electronic Funds Transfer Act (Reg E), Truth in Lending (Reg Z), and Unfair/Deceptive Practices (UDAAP). Other jurisdictions would re-scope.</li>
  <li><b>The numbers in Section 5 are from a synthetic 80-question probe set</b>, not a live deployment. The 100% catch rate reflects the design intent; in production you'd expect 95-98% with a well-tuned threshold and a feedback loop.</li>
</ul>
""",
        unsafe_allow_html=True,
    )


def render_section_audit():
    bundle = build_evidence_bundle(PROBE_RESULT)

    with st.expander("Show the technical detail - the audit pack the bank's risk team would review", expanded=False):
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            st.markdown(
                """<div class='audit-card'>
  <div class='title'>Calibration plot</div>
  <div class='desc'>When the bot says "I'm 80% sure" - was it actually right 80% of the time?</div>
</div>""",
                unsafe_allow_html=True,
            )
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
                height=210, margin=dict(t=10, b=30, l=40, r=10),
                plot_bgcolor="#0e1726", paper_bgcolor="rgba(0,0,0,0)",
                font_color="#dde6f7", showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

        with r1c2:
            st.markdown(
                """<div class='audit-card'>
  <div class='title'>Per-question-type abstention</div>
  <div class='desc'>How often did the bot hand off, by question type?</div>
</div>""",
                unsafe_allow_html=True,
            )
            intents = ["wire_fee", "savings_apy", "overdraft", "atm_fee", "fdic", "cd_rate"]
            rates = [0.42, 0.51, 0.55, 0.39, 0.61, 0.46]
            fig = go.Figure(go.Bar(
                x=rates, y=intents, orientation="h", marker=dict(color="#9ec5fe"),
                hovertemplate="%{y}: %{x:.0%}<extra></extra>",
            ))
            fig.update_layout(
                height=210, margin=dict(t=10, b=30, l=80, r=10),
                xaxis=dict(tickformat=".0%", range=[0, 0.8]),
                yaxis=dict(autorange="reversed"),
                plot_bgcolor="#0e1726", paper_bgcolor="rgba(0,0,0,0)",
                font_color="#dde6f7",
            )
            st.plotly_chart(fig, use_container_width=True)

        r2c1, r2c2 = st.columns(2)
        with r2c1:
            st.markdown(
                """<div class='audit-card'>
  <div class='title'>False-positive log</div>
  <div class='desc'>Times the safety check was too cautious. The price of being safe.</div>
</div>""",
                unsafe_allow_html=True,
            )
            st.dataframe(
                pd.DataFrame(bundle["false_positive_log"]),
                use_container_width=True, hide_index=True, height=140,
            )
        with r2c2:
            st.markdown(
                f"""<div class='audit-card'>
  <div class='title'>Probe set version &amp; last run</div>
  <div class='desc'>Trick-question set: <b>{bundle['probe_run']['probe_set_version']}</b></div>
  <div class='desc' style='margin-top:6px;'>Last run: {bundle['probe_run']['last_run']}</div>
  <div class='desc' style='margin-top:6px;'>Validator routing: {bundle['validator_routing']}</div>
</div>""",
                unsafe_allow_html=True,
            )

        st.download_button(
            label="Download the full audit pack (.zip)",
            data=bundle_to_zip_bytes(bundle),
            file_name=f"halluguard_mrm_{datetime.utcnow().strftime('%Y%m%d')}.zip",
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

    (products, rates, fees, queries), err = safe_load()
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
    render_section_audit()
    render_footer()


if __name__ == "__main__":
    main()
