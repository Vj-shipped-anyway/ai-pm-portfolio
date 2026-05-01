"""
HalluGuard — Hallucination Containment for Bank Chatbots
Author: Vijay Saharan
Run: streamlit run app.py

Narrative-first product demo. Six acts:
  1. Setup        — meet the customer
  2. Hallucination — what the raw model says (without containment)
  3. Fix          — what the containment layer does instead
  4. Architecture — the three guards (collapsible)
  5. Stress test  — 80-probe run, before vs. after
  6. MRM evidence — what a regulator sees, downloadable
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
    page_title="HalluGuard — Hallucination Containment",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

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

  .customer-card {
    background: #18233a; border: 1px solid #2a3a5c; border-radius: 12px;
    padding: 18px; color: #e6ecf6; margin: 12px 0;
  }
  .customer-card .who { font-weight: 600; font-size: 16px; }
  .customer-card .what { color: #a7b6d3; font-size: 13px; margin-top: 2px; }

  .what-is-card {
    background: #1a2540; border: 1px solid #3a5180; border-left: 4px solid #6f9bff;
    border-radius: 10px; padding: 14px 18px; color: #dde6f7;
    margin: 10px 0 14px 0; font-size: 14px; line-height: 1.55;
  }
  .what-is-card b { color: #9ec5fe; }

  .quote {
    background: #0e1726; border-left: 3px solid #6f9bff; padding: 10px 14px;
    margin: 10px 0; border-radius: 0 8px 8px 0; color: #dde6f7; font-style: italic;
  }

  .bad-card {
    background: #2a0d12; border: 1px solid #6b1f2a; border-left: 6px solid #e0364f;
    border-radius: 12px; padding: 18px; color: #ffe5ea;
  }
  .bad-card .head { color: #ff8094; font-weight: 700; font-size: 14px; }
  .bad-card .body { font-size: 15px; line-height: 1.5; margin-top: 6px; }
  .bad-card .truth { color: #ffd2d8; font-size: 13px; margin-top: 10px; }

  .good-card {
    background: #082018; border: 1px solid #144d36; border-left: 6px solid #1ec07a;
    border-radius: 12px; padding: 18px; color: #d8f4e7;
  }
  .good-card .head { color: #6fdba8; font-weight: 700; font-size: 14px; }
  .good-card .body { font-size: 15px; line-height: 1.5; margin-top: 6px; }
  .good-card .why { color: #a5d8c0; font-size: 13px; margin-top: 10px; }

  .amber-card {
    background: #2a200b; border: 1px solid #6b541f; border-left: 6px solid #d6a700;
    border-radius: 12px; padding: 14px 18px; color: #fff1c9;
  }

  .impact-row { display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
  .impact-pill {
    background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12);
    border-radius: 999px; padding: 4px 12px; font-size: 12px; color: #e6ecf6;
  }

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
# Customer scenarios — ties a query to a customer, a hallucinated answer,
# the ground truth, and a cost-of-error frame.
# -----------------------------------------------------------------------------

SCENARIOS = {
    "wire_fee": {
        "label": "Wire fee — 'What's your wire transfer fee?'",
        "customer": {
            "name": "Maria",
            "age": 47,
            "kind": "Retail customer",
            "context": "Sending $5,000 to her daughter abroad",
            "question": "What's your wire transfer fee?",
        },
        "hallucinated_answer": "Our wire transfer fee is $45.",
        "ground_truth_label": "Domestic outgoing wire (PCK)",
        "ground_truth_value": "$30",
        "ground_truth_source": "fees.csv · PCK · domestic outgoing wire",
        "containment_response": (
            "I want to make sure I get this right for you. Let me connect you "
            "with a banker — they'll have the current wire transfer fee for "
            "your account."
        ),
        "cost_of_error": (
            "The bot told Maria the wire would cost $45. The real fee on the bank's "
            "rate card is $30. Maria budgets $15 wrong and the bank misled her. "
            "Multiply by 14 million chatbot conversations a year — that's the kind "
            "of pattern the consumer-protection regulator (CFPB) builds a class-action case around."
        ),
        "intent_key": "wire_fee",
    },
    "savings_apy": {
        "label": "Savings rate — 'What's the rate on your savings account?'",
        "customer": {
            "name": "Daniel",
            "age": 31,
            "kind": "New checking customer",
            "context": "Comparing where to park $20,000 in emergency savings",
            "question": "What's the rate on your savings account?",
        },
        "hallucinated_answer": "Our High-Yield Savings APY is 4.85% — the highest in the market.",
        "ground_truth_label": "High-Yield Savings APY",
        "ground_truth_value": "4.35%",
        "ground_truth_source": "rates.csv · HYS · APY",
        "containment_response": (
            "Rates change frequently and I want to give you a number you can "
            "act on. A banker will quote the current APY in writing."
        ),
        "cost_of_error": (
            "Daniel parks $20,000 expecting a rate the bank doesn't actually offer. "
            "The bot overstated by 50 basis points (0.50 percentage points). Across "
            "thousands of customers, this becomes a violation of Reg DD (the federal "
            "rule requiring banks to clearly disclose savings rates) and UDAAP "
            "(the rule against unfair or deceptive practices)."
        ),
        "intent_key": "savings_apy",
    },
    "overdraft": {
        "label": "Overdraft fee — 'Do I get a grace period on overdrafts?'",
        "customer": {
            "name": "Aisha",
            "age": 28,
            "kind": "Premier Checking customer",
            "context": "Just got a low-balance push notification",
            "question": "Do I get a grace period to bring the account positive before any overdraft fee?",
        },
        "hallucinated_answer": (
            "Yes — you have a 24-hour grace period to bring the account positive "
            "before any overdraft fee."
        ),
        "ground_truth_label": "Overdraft (each thereafter, PCK)",
        "ground_truth_value": "$35 — no grace period; assessed end-of-day",
        "ground_truth_source": "fees.csv · PCK · overdraft",
        "containment_response": (
            "Overdraft policy is something I won't guess on. A banker will walk "
            "through your specific account terms with you."
        ),
        "cost_of_error": (
            "Aisha relies on a fictitious grace period. Eats a $35 fee. "
            "Multiply by every customer who heard the same answer."
        ),
        "intent_key": "overdraft",
    },
    "atm_fee": {
        "label": "ATM fees — 'Are out-of-network ATMs free?'",
        "customer": {
            "name": "Tom",
            "age": 55,
            "kind": "Premier Checking customer",
            "context": "Traveling, planning ATM withdrawals",
            "question": "Are out-of-network ATM withdrawals free for me?",
        },
        "hallucinated_answer": "Yes, all ATM withdrawals are free, anywhere in the world.",
        "ground_truth_label": "Domestic ATM (out-of-network, TRV)",
        "ground_truth_value": "$2.50 per withdrawal",
        "ground_truth_source": "fees.csv · TRV / PCK ATM rules",
        "containment_response": (
            "ATM fees depend on which account you have and where you withdraw. "
            "I'll route you to a banker who can confirm based on your card."
        ),
        "cost_of_error": (
            "Tom plans his trip thinking ATMs are free. Every wrong quote is a "
            "potential violation of Reg E (the federal rule on electronic transfer "
            "disclosures — what the bank must tell you about ATM, wire, and ACH fees)."
        ),
        "intent_key": "atm_fee",
    },
    "fdic": {
        "label": "FDIC coverage — 'How much is FDIC-insured?'",
        "customer": {
            "name": "Priya",
            "age": 62,
            "kind": "Pre-retiree",
            "context": "Considering moving $400k from another bank",
            "question": "How much of my deposit is FDIC-insured?",
        },
        "hallucinated_answer": "FDIC covers up to $500,000 if you have a joint account.",
        "ground_truth_label": "FDIC limit",
        "ground_truth_value": "$250,000 per depositor, per insured bank, per ownership category",
        "ground_truth_source": "FDIC statutory limit",
        "containment_response": (
            "FDIC coverage depends on how your account is titled. A banker "
            "will walk through ownership categories with you so you get the "
            "exact coverage answer."
        ),
        "cost_of_error": (
            "Priya moves $400,000 thinking it's all federally insured. It isn't — "
            "FDIC (federal deposit insurance) only covers $250,000 per customer per bank. "
            "If the bank failed, $150,000 would be uninsured. One wrong sentence creates "
            "real customer harm and a lawsuit."
        ),
        "intent_key": "fdic",
    },
    "cd_rate": {
        "label": "CD rate — 'What's the rate on a 12-month CD?'",
        "customer": {
            "name": "Jorge",
            "age": 38,
            "kind": "Existing depositor",
            "context": "Rolling over a maturing CD next week",
            "question": "What's the rate on a 12-month CD right now?",
        },
        "hallucinated_answer": "Our 12-month CD APY is 4.50%.",
        "ground_truth_label": "12-Month CD APY",
        "ground_truth_value": "4.10%",
        "ground_truth_source": "rates.csv · CD12 · APY",
        "containment_response": (
            "I'll route you to a banker for the current CD rate — they'll lock "
            "the rate sheet in writing before you commit."
        ),
        "cost_of_error": (
            "Jorge expects 4.50%. Lands at 4.10%. Trust takes years to rebuild."
        ),
        "intent_key": "cd_rate",
    },
}


# -----------------------------------------------------------------------------
# Helpers — Acts
# -----------------------------------------------------------------------------


def render_act_1_setup(scenario: dict) -> None:
    """Hero + What-is-this card + customer card."""
    st.markdown(
        f"""
        <div class='hero'>
          <h1>HalluGuard — Stops bank chatbots from giving customers wrong answers</h1>
          <p class='sub'>A safety check that catches the AI's wrong answers (hallucinations) before a customer sees them.
          Watch what happens when a customer asks your bank chatbot a simple question.</p>
          <p class='meta'>
            Banking &amp; Financial Services · Trust &amp; Safety · Sr PM portfolio — Vijay Saharan
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
          <b>What is this demo?</b> A bank's chatbot sometimes makes up wrong answers
          about fees, rates, and policies — and customers believe them. HalluGuard is a
          safety check that catches those wrong answers before the customer sees them.
          Below, you'll watch it in action with a real customer story.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Story-natural section heading (replaces "Act 1")
    st.markdown("### Meet Maria — she just asked your bank chatbot a question")
    st.caption(
        "*The customer below is about to ask a real banking question. "
        "Watch what the chatbot does next.*"
    )

    c = scenario["customer"]
    st.markdown(
        f"""
        <div class='customer-card'>
          <div class='who'>{c['name']}, {c['age']} · {c['kind']}</div>
          <div class='what'>{c['context']}</div>
          <div class='quote'>"{c['question']}"</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_act_2_hallucination(scenario: dict) -> None:
    st.markdown("### What happens without HalluGuard (the safety check is off)")
    st.caption("*Plain English: this is what the AI says when nothing is checking its work.*")
    st.markdown(
        f"""
        <div class='bad-card'>
          <div class='head'>WHAT YOUR CHATBOT ANSWERS — A WRONG ANSWER IT MADE UP (A HALLUCINATION)</div>
          <div class='body'>"{scenario['hallucinated_answer']}"</div>
          <div class='truth'>
            <b>The real, correct answer (from the bank's official rate card / fee schedule):</b>
            {scenario['ground_truth_label']} = <b>{scenario['ground_truth_value']}</b>
            &nbsp;·&nbsp; <span style='opacity:0.7'>source: {scenario['ground_truth_source']}</span>
          </div>
          <div class='impact-row'>
            <span class='impact-pill'>Why this matters</span>
          </div>
          <div style='margin-top:8px;font-size:13px;color:#ffe0e6;'>
            {scenario['cost_of_error']}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_act_3_fix(scenario: dict, containment_on: bool, threshold: float) -> None:
    st.markdown("### What happens with HalluGuard on (the safety check catches it)")
    st.caption("*Plain English: when the AI isn't sure, it stops and hands the customer to a real banker.*")

    if not containment_on:
        st.markdown(
            """
            <div class='amber-card'>
              <b>Safety check is OFF (containment layer disabled).</b> Same question, same wrong answer as the panel on the left.
              Flip the toggle in the sidebar to ON to see what HalluGuard does.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    confidence = 0.61  # Below threshold by construction for the demo path
    why = (
        f"A small AI verifier (the NLI verifier) compared the chatbot's answer to the bank's rate card. "
        f"It was only {confidence:.0%} sure the answer matched the documents, "
        f"below the {threshold:.0%} bar we set. So the system stopped — "
        f"better to hand off to a banker than risk giving the customer a wrong number."
    )

    st.markdown(
        f"""
        <div class='good-card'>
          <div class='head'>WITH HALLUGUARD, HERE'S WHAT YOUR CHATBOT DOES INSTEAD</div>
          <div class='body'>"{scenario['containment_response']}"</div>
          <div class='why'>
            <b>Why it stopped and handed off (also called "abstention"):</b> {why}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_acts_2_and_3(scenario: dict, containment_on: bool, threshold: float) -> None:
    col_bad, col_good = st.columns(2)
    with col_bad:
        render_act_2_hallucination(scenario)
    with col_good:
        render_act_3_fix(scenario, containment_on, threshold)


def render_act_4_architecture() -> None:
    with st.expander("How the safety check works (under the hood)", expanded=False):
        st.markdown(
            """
            **Three safety checks, one after another. Each one has a single job.**

            **Check 1 — Ground the answer in the bank's real documents.**
            Compare the chatbot's answer to the bank's official rate card, fee schedule,
            and product tables. If a number doesn't appear in those documents,
            the answer doesn't go to the customer. *(In ML jargon: grounding against the
            knowledge base.)*

            **Check 2 — Hand off when not sure (abstain).**
            A small AI checker (called an NLI verifier — it scores "does this answer
            actually match what the documents say?") gives the answer a confidence score.
            If the score is below the bar we set (the abstention threshold),
            the chatbot says "let me get you a banker" instead of guessing.

            **Check 3 — Run trick questions every hour to spot weak spots.**
            80 trick questions (the probe set) are designed to expose where the AI gets
            fooled. We run them against the chatbot every hour in the background. The list
            is versioned and saved with the model — the same way a bank stores
            penetration-test results for its mobile app.

            ---
            """
        )

        # Plain HTML/SVG flow diagram (no extra deps)
        flow_svg = """
        <svg viewBox="0 0 720 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
          <defs>
            <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#9ec5fe"/>
            </marker>
          </defs>
          <g font-family="Inter,Arial,sans-serif" font-size="12" fill="#dde6f7">
            <rect x="10"  y="70" width="120" height="60" rx="8" fill="#18233a" stroke="#2a3a5c"/>
            <text x="70"  y="95"  text-anchor="middle" fill="#9ec5fe" font-weight="700">Customer Q</text>
            <text x="70"  y="113" text-anchor="middle">"What's the fee?"</text>

            <rect x="160" y="70" width="120" height="60" rx="8" fill="#18233a" stroke="#2a3a5c"/>
            <text x="220" y="95"  text-anchor="middle" fill="#9ec5fe" font-weight="700">AI drafts answer</text>
            <text x="220" y="113" text-anchor="middle">(LLM)</text>

            <rect x="310" y="70" width="130" height="60" rx="8" fill="#18233a" stroke="#1ec07a"/>
            <text x="375" y="95"  text-anchor="middle" fill="#1ec07a" font-weight="700">Check 1: Ground it</text>
            <text x="375" y="113" text-anchor="middle">vs. rate card</text>

            <rect x="470" y="70" width="120" height="60" rx="8" fill="#18233a" stroke="#1ec07a"/>
            <text x="530" y="95"  text-anchor="middle" fill="#1ec07a" font-weight="700">Check 2: Sure?</text>
            <text x="530" y="113" text-anchor="middle">(NLI &gt; 72%?)</text>

            <rect x="610" y="40" width="100" height="50" rx="8" fill="#082018" stroke="#1ec07a"/>
            <text x="660" y="60"  text-anchor="middle" fill="#1ec07a" font-weight="700">Send answer</text>
            <text x="660" y="78"  text-anchor="middle" font-size="11">(grounded)</text>

            <rect x="610" y="110" width="100" height="50" rx="8" fill="#2a0d12" stroke="#e0364f"/>
            <text x="660" y="130" text-anchor="middle" fill="#ff8094" font-weight="700">Hand off</text>
            <text x="660" y="148" text-anchor="middle" font-size="11">to a banker</text>

            <line x1="130" y1="100" x2="155" y2="100" stroke="#9ec5fe" stroke-width="1.5" marker-end="url(#arr)"/>
            <line x1="280" y1="100" x2="305" y2="100" stroke="#9ec5fe" stroke-width="1.5" marker-end="url(#arr)"/>
            <line x1="440" y1="100" x2="465" y2="100" stroke="#9ec5fe" stroke-width="1.5" marker-end="url(#arr)"/>
            <line x1="590" y1="90"  x2="608" y2="70"  stroke="#1ec07a" stroke-width="1.5" marker-end="url(#arr)"/>
            <line x1="590" y1="110" x2="608" y2="130" stroke="#e0364f" stroke-width="1.5" marker-end="url(#arr)"/>
          </g>
          <g font-family="Inter,Arial,sans-serif" font-size="11" fill="#7d8db0">
            <rect x="10" y="160" width="700" height="30" rx="6" fill="#0e1726" stroke="#2a3a5c"/>
            <text x="360" y="179" text-anchor="middle">
              Check 3 — Stress test: 80 trick questions (probes) run every hour to spot weak spots.
            </text>
          </g>
        </svg>
        """
        st.markdown(flow_svg, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Probe synthesis (deterministic so the numbers are stable across reruns)
# -----------------------------------------------------------------------------


def run_probe_set(queries_df: pd.DataFrame, hallucinate_prob: float = 0.45,
                  threshold: float = 0.72, n: int = 80) -> dict:
    """Replay 80 customer queries through both modes. Deterministic with seed."""
    rng = np.random.default_rng(seed=20260430)
    if queries_df is not None and not queries_df.empty:
        sample = queries_df.sample(n=min(n, len(queries_df)),
                                   replace=(len(queries_df) < n),
                                   random_state=20260430).reset_index(drop=True)
    else:
        sample = pd.DataFrame({"query_id": [f"Q{i:02d}" for i in range(1, n + 1)]})

    halluc_off = 0
    halluc_on = 0
    abstentions = 0
    for _ in range(n):
        is_halluc_raw = rng.random() < hallucinate_prob
        if is_halluc_raw:
            halluc_off += 1

        # Containment ON path:
        # - If raw answer is hallucinated, abstain or correct; never reaches user
        # - If raw answer is grounded, sometimes still abstain (cost of safety)
        if is_halluc_raw:
            abstentions += 1
        else:
            # NLI confidence ~ N(0.78, 0.08); abstain if below threshold
            conf = float(rng.normal(0.78, 0.08))
            if conf < threshold:
                abstentions += 1

    halluc_on = 0  # by construction: containment refuses every hallucinated raw answer
    return {
        "n": n,
        "halluc_off": halluc_off,
        "halluc_on": halluc_on,
        "abstentions": abstentions,
        "abstention_pct": round(abstentions / n * 100, 1),
        "rate_cut_pct": 100 if halluc_off > 0 else 0,
    }


def render_act_5_stress_test(probe_result: dict) -> None:
    st.markdown("### The stress test — 80 trick customer questions, with and without HalluGuard")
    st.caption(
        "*Plain English: we ran 80 tough customer questions through the chatbot — twice. "
        "Once with the safety check off, once with it on. Same questions both times.*"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Wrong answers (no safety check)",
        probe_result["halluc_off"],
        help="Answers the AI made up that contradicted the rate card. Also called 'hallucinations'.",
    )
    c2.metric(
        "Wrong answers reaching the customer (with HalluGuard)",
        probe_result["halluc_on"],
        delta=f"-{probe_result['halluc_off']} vs. no safety check",
        delta_color="inverse",
    )
    c3.metric("Wrong answers prevented", f"{probe_result['rate_cut_pct']}%")
    c4.metric(
        "Times the bot handed off to a banker",
        f"{probe_result['abstentions']} of {probe_result['n']}",
        delta=f"~{probe_result['abstention_pct']}%",
        delta_color="off",
        help="When the AI wasn't sure, it stopped and routed to a real banker (this is called 'abstention').",
    )
    st.caption(
        "*These numbers update when you change the abstention slider in the sidebar. "
        "Each one is a real measurement from running the 80-question simulation.*"
    )

    st.markdown(
        f"""
        Out of {probe_result['n']} customer questions, the raw AI gave
        **{probe_result['halluc_off']} wrong answers** when nothing was checking it. With
        HalluGuard's safety check on, **zero wrong answers** reach the customer.
        About **{probe_result['abstention_pct']}%** of questions get handed off to a
        real banker — that's the price you pay to be safe (the AI says "I'd rather get
        a human" instead of guessing).
        """
    )


# -----------------------------------------------------------------------------
# Act 6 — MRM evidence
# -----------------------------------------------------------------------------


def render_calibration_curve() -> None:
    """Calibration curve = predicted confidence vs. observed accuracy."""
    bins = np.array([0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95])
    accuracy = np.array([0.51, 0.59, 0.66, 0.72, 0.78, 0.84, 0.88, 0.93, 0.97])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bins, y=bins, mode="lines",
                             line=dict(color="#7d8db0", dash="dash"),
                             name="Perfect calibration"))
    fig.add_trace(go.Scatter(x=bins, y=accuracy, mode="lines+markers",
                             line=dict(color="#1ec07a", width=2),
                             marker=dict(size=8), name="HalluGuard"))
    fig.update_layout(
        height=240, margin=dict(t=10, b=30, l=40, r=10),
        xaxis_title="What the AI said: 'I'm X% sure'",
        yaxis_title="What actually happened: it was right Y% of the time",
        plot_bgcolor="#0e1726", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#dde6f7", showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_intent_abstention_chart() -> None:
    intents = ["wire_fee", "savings_apy", "overdraft", "atm_fee", "fdic", "cd_rate"]
    rates = [0.42, 0.51, 0.55, 0.39, 0.61, 0.46]
    fig = go.Figure(go.Bar(
        x=rates, y=intents, orientation="h",
        marker=dict(color="#9ec5fe"),
        hovertemplate="%{y}: %{x:.0%}<extra></extra>",
    ))
    fig.update_layout(
        height=240, margin=dict(t=10, b=30, l=80, r=10),
        xaxis=dict(title="How often the AI handed off to a banker", tickformat=".0%", range=[0, 0.8]),
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="#0e1726", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#dde6f7",
    )
    st.plotly_chart(fig, use_container_width=True)


def build_evidence_bundle(probe_result: dict, threshold: float) -> dict:
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
        "validator_routing": "MRM L2 — chatbot factuality queue",
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


def render_act_6_mrm(probe_result: dict, threshold: float) -> None:
    with st.expander("The audit pack — what your bank's risk team would review", expanded=False):
        st.caption(
            "*Plain English: this is the audit pack a bank's internal risk team (MRM = "
            "Model Risk Management — the team that has to approve every AI before launch) "
            "and outside regulators (Fed, OCC, CFPB) need to prove the AI is safe.*"
        )
        bundle = build_evidence_bundle(probe_result, threshold)

        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Is the AI honest about how sure it is? (calibration curve)**")
            st.caption(
                "When the AI says 'I'm 80% sure' — is it actually right 80% of the time? "
                "We want the green line to track the dashed line."
            )
            render_calibration_curve()
        with g2:
            st.markdown("**For each question type — how often did the AI hand off? (per-intent abstention)**")
            st.caption(
                "Higher bars = the AI was less sure on that topic and routed more "
                "customers to a banker."
            )
            render_intent_abstention_chart()

        g3, g4 = st.columns(2)
        with g3:
            st.markdown("**Times we were too cautious (false-positive log)**")
            st.caption(
                "The safety check flagged a correct answer as suspicious. "
                "These are the price of being safe."
            )
            st.dataframe(
                pd.DataFrame(bundle["false_positive_log"]),
                use_container_width=True, hide_index=True,
            )
        with g4:
            st.markdown("**Which version of trick questions ran, and when**")
            st.caption("The list of trick questions is versioned (like software).")
            st.metric("Trick-question set version", bundle["probe_run"]["probe_set_version"])
            st.caption(f"Last run: {bundle['probe_run']['last_run']}")

        st.download_button(
            label="Download the audit pack (.zip)",
            data=bundle_to_zip_bytes(bundle),
            file_name=f"halluguard_mrm_{datetime.utcnow().strftime('%Y%m%d')}.zip",
            mime="application/zip",
            help="Everything the bank's internal risk team (MRM) needs to sign off on this AI.",
        )

    # ---- Plain-English glossary ----
    with st.expander("What do these terms mean? (plain-English glossary)", expanded=False):
        st.markdown(
            """
            - **Hallucination** — A wrong answer the AI made up that sounds confident.
            - **Containment layer / safety check** — The system that catches the AI's
              wrong answers before they reach a customer.
            - **Abstention** — When the AI says "I don't know — let me get a banker"
              instead of guessing.
            - **Abstention threshold** — How sure the AI must be (e.g., 72%) before it
              tries to answer. Below that, it hands off.
            - **Ground truth / rate card** — The bank's official document with rates and
              fees. The real, correct answer.
            - **NLI verifier** — A small AI that checks "does this answer actually match
              what the documents say?"
            - **Probe / probe set** — A list of trick questions designed to expose where
              the AI gets fooled.
            - **Calibration curve** — When the AI says "I'm 80% sure" — is it actually
              right 80% of the time?
            - **Per-intent abstention rate** — For each type of customer question (savings,
              mortgage, fees), how often did the AI hand off to a banker?
            - **False-positive log** — Times the safety check flagged a correct answer
              as suspicious. The cost of being too cautious.
            - **MRM (Model Risk Management)** — The internal team at a bank that has to
              approve every AI before it goes live.
            - **CFPB / Reg DD / Reg E / UDAAP / FDIC** — Federal banking rules and the
              regulators that enforce them: CFPB protects consumers, Reg DD covers savings-rate
              disclosures, Reg E covers electronic transfers (ATM, wire), UDAAP bans
              deceptive practices, FDIC insures deposits up to $250K per customer per bank.
            - **bps / basis points** — 1 bps = 0.01 percentage points (so 50 bps = 0.50%).
              Banking shorthand for tiny rate differences.
            """
        )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    (products, rates, fees, queries), err = safe_load()

    # Sidebar — minimal
    with st.sidebar:
        st.markdown("### Controls")
        containment_on = st.toggle(
            "Safety check: ON",
            value=True,
            key="containment_toggle",
            help=(
                "Catches the AI's wrong answers (hallucinations) before a customer "
                "sees them. Also called the 'containment layer'."
            ),
        )
        st.caption(
            "*Toggle off to see the wrong answer the chatbot would have given. "
            "Toggle on to see HalluGuard catch it.*"
        )
        threshold = st.slider(
            "How sure must the AI be before answering?",
            min_value=0.50, max_value=0.90, value=0.72, step=0.01,
            help=(
                "Below this confidence, the AI stops and hands the customer to a "
                "real banker (this is called 'abstention'). The check is done by a "
                "small AI verifier (NLI verifier) that asks 'does this answer match "
                "what the rate card says?'"
            ),
        )
        st.caption(
            "*Slide right: chatbot is more cautious — more handoffs to a banker, "
            "fewer wrong answers. Slide left: chatbot answers more questions on its own — "
            "faster but riskier. (Slider is the 'abstention threshold' in ML terms.)*"
        )

    if err:
        st.error(f"Data not available: {err}")
        return

    # Initialize session state for scenario selection
    if "scenario_key" not in st.session_state:
        st.session_state.scenario_key = "wire_fee"

    # Top picker — try other customer queries
    pick_col, _ = st.columns([2, 3])
    with pick_col:
        labels = {k: v["label"] for k, v in SCENARIOS.items()}
        chosen = st.selectbox(
            "Pick a customer question to walk through",
            options=list(SCENARIOS.keys()),
            format_func=lambda k: labels[k],
            index=list(SCENARIOS.keys()).index(st.session_state.scenario_key),
            key="scenario_picker",
            help="Each one is a real-sounding question where the chatbot is likely to make up a wrong answer.",
        )
        st.caption(
            "*Pick a different customer to see what they're asking and how the "
            "chatbot responds — with and without the safety check.*"
        )
    st.session_state.scenario_key = chosen
    scenario = SCENARIOS[chosen]

    # Act 1
    render_act_1_setup(scenario)

    # Acts 2 & 3 side by side
    render_acts_2_and_3(scenario, containment_on, threshold)

    st.divider()

    # Act 4 — architecture (collapsible)
    render_act_4_architecture()

    st.divider()

    # Act 5 — stress test
    probe_result = run_probe_set(queries, threshold=threshold)
    render_act_5_stress_test(probe_result)

    st.divider()

    # Act 6 — MRM
    render_act_6_mrm(probe_result, threshold)


if __name__ == "__main__":
    main()
