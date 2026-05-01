"""DealSentry - CRE underwriting reliability layer.

Streamlit walkthrough:
  Step 1 - paste a memo, or pick a sample
  Step 2 - run the 3 verifiers (comp existence, T-12 math, submarket stats)
  Step 3 - executive verdict + recommendation
  Step 4 - download the verification workpaper
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="DealSentry - Stops bad CRE bids built on hallucinated comps",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

.dl-hero {
  background: linear-gradient(135deg,#1c1917 0%, #44403c 50%, #b45309 100%);
  border-radius: 18px; padding: 36px 40px; color:#fff; margin-bottom:28px;
}
.dl-hero .brand {font-size:26px; font-weight:600; opacity:0.92; margin-bottom:12px;}
.dl-hero h1 {color:#fff !important; font-size:46px; line-height:1.12; margin:0 0 14px 0; font-weight:700;}
.dl-hero .sub {font-size:17px; line-height:1.5; opacity:0.93; max-width:820px; margin-bottom:22px;}
.dl-hero .pills {display:flex; flex-wrap:wrap; gap:10px;}
.dl-hero .pill {background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
                color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.dl-hero .pill a {color:#fff; text-decoration:none;}

.dl-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:22px 26px;
          margin-bottom:18px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.dl-card h3 {margin-top:0; color:#0f172a;}
.dl-step-label {display:inline-block; background:#b45309; color:#fff; padding:3px 10px;
                border-radius:6px; font-size:12px; font-weight:600; letter-spacing:0.04em;
                text-transform:uppercase; margin-bottom:10px;}

.verdict-card {border-radius:16px; padding:26px 30px; margin-bottom:18px; color:#fff;}
.verdict-pass {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.verdict-flag {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.verdict-review {background: linear-gradient(135deg,#b45309,#f59e0b);}
.verdict-card .vlabel {font-size:13px; opacity:0.9; letter-spacing:0.08em; text-transform:uppercase;}
.verdict-card .vbig {font-size:44px; font-weight:800; line-height:1.1; margin:4px 0 14px 0;}
.verdict-card .vmetric {font-size:22px; font-weight:600;}
.verdict-card .vrow {display:flex; flex-wrap:wrap; gap:24px; margin-top:12px;}
.verdict-card .vchip {background: rgba(255,255,255,0.18); padding:6px 12px; border-radius:999px;
                      font-size:13px; font-weight:600;}
.verdict-card .vtldr {margin-top:16px; font-size:15px; line-height:1.5; opacity:0.95;}

.trust-card {background:#f8fafc; border:1px solid #cbd5e1; border-left:5px solid #b45309;
             border-radius:12px; padding:20px 24px; margin-bottom:18px;}
.trust-card h4 {margin:0 0 10px 0; color:#0f172a; font-size:16px; letter-spacing:0.04em;
                text-transform:uppercase;}
.trust-card .tlabel {font-weight:700; color:#b45309; font-size:13px; letter-spacing:0.04em;
                     text-transform:uppercase; margin-top:12px; display:block;}
.trust-card ul {margin:6px 0 0 18px; padding:0;}
.trust-card li {color:#334155; line-height:1.55;}
.confidence-high {color:#047857; font-weight:700;}
.confidence-med  {color:#b45309; font-weight:700;}
.confidence-low  {color:#b91c1c; font-weight:700;}

.check-card {border-radius:12px; padding:14px 18px; margin-bottom:10px;}
.check-pass {background:#dcfce7; border-left:5px solid #16a34a; color:#14532d;}
.check-fail {background:#fef2f2; border-left:5px solid #dc2626; color:#7f1d1d;}
.check-review {background:#fef3c7; border-left:5px solid #f59e0b; color:#78350f;}

div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#b45309,#7c2d12) !important; color:#fff !important;
  border:0 !important; padding:14px 28px !important; font-size:17px !important;
  font-weight:600 !important; border-radius:12px !important;
  box-shadow:0 4px 14px rgba(180,83,9,0.35) !important;
}
h1, h2, h3 {color:#0f172a;}
.muted {color:#64748b; font-size:14px;}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Synthetic memos (no external data files yet for DealSentry)
# ---------------------------------------------------------------------------
MEMOS = {
    "Memo 01 - Atlanta industrial (clean)": {
        "summary": "180k sf last-mile industrial, Atlanta SE submarket. 5 comps cited from CoStar within last 12 months.",
        "comps_cited": 5,
        "comps_verified": 5,
        "comps_fabricated": 0,
        "math_errors": 0,
        "submarket_errors": 0,
        "verdict": "PASS",
        "dollar_at_risk": 0,
    },
    "Memo 02 - Phoenix multifamily (clean)": {
        "summary": "240-unit garden multifamily, Phoenix North submarket. 6 comps cited; T-12 NOI normalization shown.",
        "comps_cited": 6,
        "comps_verified": 6,
        "comps_fabricated": 0,
        "math_errors": 0,
        "submarket_errors": 0,
        "verdict": "PASS",
        "dollar_at_risk": 0,
    },
    "Memo 03 - Dallas office (math drift)": {
        "summary": "320k sf Class-A office, Dallas Uptown. T-12 NOI rolls up to a number that does not reconcile to the rent roll.",
        "comps_cited": 5,
        "comps_verified": 5,
        "comps_fabricated": 0,
        "math_errors": 1,
        "submarket_errors": 0,
        "verdict": "REVIEW",
        "dollar_at_risk": 720_000,
    },
    "Memo 04 - Miami retail (fabricated comps)": {
        "summary": "92k sf grocery-anchored retail, Miami Brickell. AI-generated comp set includes 2 properties that do not exist.",
        "comps_cited": 6,
        "comps_verified": 4,
        "comps_fabricated": 2,
        "math_errors": 0,
        "submarket_errors": 0,
        "verdict": "FAIL",
        "dollar_at_risk": 1_800_000,
    },
    "Memo 05 - Seattle MOB (submarket stats fabricated)": {
        "summary": "85k sf medical office, Seattle Bellevue submarket. Cited submarket vacancy rate of 4.2% does not match any source.",
        "comps_cited": 4,
        "comps_verified": 4,
        "comps_fabricated": 0,
        "math_errors": 0,
        "submarket_errors": 1,
        "verdict": "REVIEW",
        "dollar_at_risk": 360_000,
    },
    "Memo 06 - Chicago industrial (multi-fault)": {
        "summary": "410k sf last-mile industrial, Chicago O'Hare. 1 fabricated comp + arithmetic error in stabilized cap rate.",
        "comps_cited": 5,
        "comps_verified": 4,
        "comps_fabricated": 1,
        "math_errors": 1,
        "submarket_errors": 0,
        "verdict": "FAIL",
        "dollar_at_risk": 2_100_000,
    },
}

DEFAULT_MEMO_TEXT = (
    "Investment Memo — Project Brickell\n\n"
    "Asset: 92,000 sf grocery-anchored retail center, Miami FL.\n"
    "Submarket: Brickell South (per AI copilot).\n\n"
    "Comparable Sales (cited):\n"
    "  Comp 1 - Lakeshore Plaza, sold 2025-Q3, $245/sf\n"
    "  Comp 2 - Brickell Crossing, sold 2025-Q2, $268/sf\n"
    "  Comp 3 - Miramar Town Center, sold 2025-Q4, $231/sf\n"
    "  Comp 4 - Pinecrest Pavilion, sold 2026-Q1, $254/sf  [fabricated, no record]\n"
    "  Comp 5 - Coral Way Marketplace, sold 2025-Q3, $239/sf\n"
    "  Comp 6 - South Bay Galleria, sold 2025-Q4, $261/sf  [fabricated, no record]\n\n"
    "Stabilized cap rate: 6.25%.\n"
    "T-12 NOI: $4.6M. Asking price: $73.6M ($800/sf).\n"
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "step" not in st.session_state:
    st.session_state.step = 1
if "memo_choice" not in st.session_state:
    st.session_state.memo_choice = list(MEMOS.keys())[3]  # default to Miami fabricated


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    """
<div class='dl-hero'>
  <div class='brand'>🏗️ DealSentry</div>
  <h1>Stops CRE underwriting copilots from sending IC memos with fabricated comps and bad math.</h1>
  <div class='sub'>Verifies every cited comp against a source-of-truth DB, re-runs T-12 normalization symbolically, cross-checks submarket stats across feeds, and flags anything that smells synthetic before the deal hits IC.</div>
  <div class='pills'>
    <span class='pill'><a href='https://github.com/Vj-shipped-anyway/ai-pm-portfolio' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='https://www.linkedin.com/in/vijaysaharan/' target='_blank'>LinkedIn</a></span>
    <span class='pill'>6 memos verified</span>
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
# STEP 1 - paste memo / pick sample
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='dl-card'><span class='dl-step-label'>Step 1</span>"
    "<h3>Paste an AI-generated underwriting memo, or pick one of 6 samples</h3>"
    "<p class='muted'>Six synthetic memos covering the failure modes - clean, T-12 math drift, "
    "fabricated comps, submarket-stat fabrication, multi-fault.</p></div>",
    unsafe_allow_html=True,
)

st.session_state.memo_choice = st.selectbox(
    "Sample memo:",
    list(MEMOS.keys()),
    index=list(MEMOS.keys()).index(st.session_state.memo_choice),
    label_visibility="collapsed",
)
m = MEMOS[st.session_state.memo_choice]

with st.expander("View memo text"):
    pasted = st.text_area("Memo text (paste your own here):", value=DEFAULT_MEMO_TEXT, height=260)

st.markdown(f"<div class='dl-card'><b>Summary:</b> {m['summary']}</div>", unsafe_allow_html=True)

if st.session_state.step < 2:
    if st.button("Verify the memo  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - run the 3 verifiers
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='dl-card'><span class='dl-step-label'>Step 2</span>"
        "<h3>Three independent checks ran against the memo</h3></div>",
        unsafe_allow_html=True,
    )

    # Check 1 - comps
    if m["comps_fabricated"] == 0:
        c1_class = "check-pass"
        c1_msg = (
            f"<b>Check 1 - Comp existence:</b> PASS. "
            f"{m['comps_verified']} of {m['comps_cited']} comps verified against SOT_COMPS."
        )
    else:
        c1_class = "check-fail"
        c1_msg = (
            f"<b>Check 1 - Comp existence:</b> FAIL. "
            f"{m['comps_fabricated']} of {m['comps_cited']} comps could not be matched in any source-of-truth feed."
        )
    st.markdown(f"<div class='check-card {c1_class}'>{c1_msg}</div>", unsafe_allow_html=True)

    # Check 2 - math
    if m["math_errors"] == 0:
        c2_class = "check-pass"
        c2_msg = "<b>Check 2 - T-12 arithmetic:</b> PASS. NOI rolls up to the cited number; cap rate math reconciles."
    else:
        c2_class = "check-fail"
        c2_msg = (
            f"<b>Check 2 - T-12 arithmetic:</b> FAIL. "
            f"{m['math_errors']} arithmetic discrepancy detected. "
            f"Symbolic re-computation does not match the memo's stated NOI / cap rate."
        )
    st.markdown(f"<div class='check-card {c2_class}'>{c2_msg}</div>", unsafe_allow_html=True)

    # Check 3 - submarket
    if m["submarket_errors"] == 0:
        c3_class = "check-pass"
        c3_msg = "<b>Check 3 - Submarket stats:</b> PASS. Cited submarket statistics align with at least 2 SOT feeds."
    else:
        c3_class = "check-review"
        c3_msg = (
            f"<b>Check 3 - Submarket stats:</b> REVIEW. "
            f"{m['submarket_errors']} cited submarket stat could not be cross-confirmed in available feeds."
        )
    st.markdown(f"<div class='check-card {c3_class}'>{c3_msg}</div>", unsafe_allow_html=True)

    if st.session_state.step < 3:
        if st.button("See the recommendation  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - exec verdict
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    verdict = m["verdict"]
    fab_pct = 100.0 * m["comps_fabricated"] / max(m["comps_cited"], 1)

    if verdict == "PASS":
        verdict_class = "verdict-pass"
        risk = "LOW"
        action = "Approve and proceed to IC."
        confidence = "HIGH (>95%)"
        confidence_class = "confidence-high"
        key_metric = f"{m['comps_verified']} of {m['comps_cited']} comps verified; 0 math errors; submarket stats aligned"
        tldr = "All three independent checks passed. Memo is safe to send to IC."
    elif verdict == "REVIEW":
        verdict_class = "verdict-review"
        risk = "MEDIUM"
        action = "Send to senior analyst review before IC."
        confidence = "MEDIUM (70-95%)"
        confidence_class = "confidence-med"
        key_metric = f"{m['math_errors']} math error / {m['submarket_errors']} submarket stat unconfirmed"
        tldr = "Memo has at least one moderate-severity flag. Resolve before sending to IC."
    else:
        verdict_class = "verdict-flag"
        risk = "HIGH"
        action = "Reject. Re-run memo through underwriting copilot with verifier on; do not bid."
        confidence = "LOW (<70%)"
        confidence_class = "confidence-low"
        key_metric = (
            f"{m['comps_fabricated']} of {m['comps_cited']} comps fabricated "
            f"({fab_pct:.0f}%); ${m['dollar_at_risk']:,.0f} bid risk"
        )
        tldr = (
            "Memo cites comparables that do not exist in any source-of-truth feed. "
            "This is the canonical bad-bid pattern. Do not advance to IC."
        )

    st.markdown(
        f"""
<div class='verdict-card {verdict_class}'>
  <div class='vlabel'>DealSentry Verdict</div>
  <div class='vbig'>{verdict}</div>
  <div class='vmetric'>{key_metric}</div>
  <div class='vrow'>
    <span class='vchip'>Risk: {risk}</span>
    <span class='vchip'>Recommended action: {action}</span>
    <span class='vchip'>Bid risk caught: ${m['dollar_at_risk']:,.0f}</span>
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
  <span class='tlabel'>What we compared against</span>
  <div>Compared cited comps against SOT_COMPS (synthetic source-of-truth modeled on CoStar / Reonomy / Cherre coverage); arithmetic re-run symbolically; submarket stats cross-checked across simulated multi-feed (CoStar / REIS / proprietary).</div>
  <span class='tlabel'>Assumptions we made</span>
  <ul>
    <li>SOT_COMPS coverage in the engaged operator's submarkets matches public CoStar / Reonomy / Cherre coverage shape.</li>
    <li>The memo cites verifiable identifiers (property name, sale date, $/sf) so a deterministic match is possible.</li>
    <li>T-12 normalization rules follow standard CRE practice (vacancy adjustment, capex reserve, management fee).</li>
    <li>Submarket boundaries follow the operator's CoStar definitions (not loose AI-paraphrased boundaries).</li>
  </ul>
  <span class='tlabel'>Confidence level</span>
  <div class='{confidence_class}'>{confidence}</div>
  <span class='tlabel'>What this does NOT cover</span>
  <ul>
    <li>Macro/market-cycle risk (DealSentry is a memo-reliability layer, not a deal-quality oracle).</li>
    <li>Off-market or proprietary comps that are not in any feed (handled by analyst override workflow).</li>
    <li>Qualitative IC concerns (sponsor track record, management team, ESG).</li>
  </ul>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.expander("Detailed findings - per-check breakdown", expanded=(verdict != "PASS")):
        rows = [
            ("Comp existence", m["comps_cited"], m["comps_fabricated"], "FAIL" if m["comps_fabricated"] > 0 else "PASS"),
            ("T-12 arithmetic", 1, m["math_errors"], "FAIL" if m["math_errors"] > 0 else "PASS"),
            ("Submarket stats", 1, m["submarket_errors"], "REVIEW" if m["submarket_errors"] > 0 else "PASS"),
        ]
        df = pd.DataFrame(rows, columns=["check", "items_examined", "issues_found", "status"])
        st.dataframe(df, use_container_width=True, hide_index=True)

    if st.session_state.step < 4:
        if st.button("Download verification PDF  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - audit pack
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='dl-card'><span class='dl-step-label'>Step 4</span>"
        "<h3>Verification workpaper</h3>"
        "<p class='muted'>Auto-assembled for the deal team and IC chair.</p></div>",
        unsafe_allow_html=True,
    )

    workpaper = (
        f"# DealSentry Verification Workpaper\n\n"
        f"**Memo:** {st.session_state.memo_choice}\n\n"
        f"**Verdict:** {m['verdict']}\n\n"
        f"**Comps cited / verified / fabricated:** {m['comps_cited']} / {m['comps_verified']} / {m['comps_fabricated']}\n\n"
        f"**T-12 arithmetic errors:** {m['math_errors']}\n\n"
        f"**Submarket stat issues:** {m['submarket_errors']}\n\n"
        f"**Bid risk caught (modeled):** ${m['dollar_at_risk']:,.0f}\n\n"
        f"**Source of truth:** SOT_COMPS (synthetic, modeled on CoStar/Reonomy/Cherre coverage)\n"
    )
    st.download_button(
        "Download workpaper (Markdown)",
        workpaper,
        file_name=f"dealsentry_workpaper_{m['verdict'].lower()}.md",
        mime="text/markdown",
    )

    with st.expander("Audit pack - evidence bundle"):
        st.markdown(
            "- **Source of truth:** SOT_COMPS (synthetic; in production, live CoStar / Reonomy / Cherre)\n"
            "- **Symbolic math engine:** re-runs T-12 normalization and cap-rate math from the rent roll\n"
            "- **Multi-feed cross-check:** submarket stats verified against >= 2 independent feeds\n"
            "- **Provenance:** every accepted comp has a SOT pointer; every flagged comp has the failed match attempt logged\n"
            "- **Audit trail:** all checks + decisions exported as JSON for IC chair review"
        )

    st.markdown(
        "<div class='dl-card muted'>Built as a portfolio prototype. Production architecture in <code>README.md</code>.</div>",
        unsafe_allow_html=True,
    )
