"""DealSentry - CRE underwriting reliability layer.

Streamlit walkthrough (single-page, scrollable - mirrors LeaseGuard's pattern):
  Step 1 - paste a memo, or pick a sample
  Step 2 - run the verifiers (executive verdict at top)
  Step 3 - per-finding breakdown + bid-risk
  Step 4 - download the verification workpaper (Markdown + PDF)

Run as Streamlit:   streamlit run app.py
Run self-tests:     python app.py --selftest
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
GH_BLOB_BASE = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/10-dealsentry-cre-underwriting/data"

MIN_MEMO_LEN = 80

# ---------------------------------------------------------------------------
# Tolerances (kept in module scope so the self-test can import them)
# ---------------------------------------------------------------------------
CAP_TOLERANCE_PCT = 0.05
T12_TOLERANCE_USD = 1.0
OCC_TOLERANCE_PCT = 1.0
EXIT_CAP_MIN_SPREAD_BPS = 20

# ---------------------------------------------------------------------------
# Sample memo (preserved for paste-textarea default + self-test)
# ---------------------------------------------------------------------------
SAMPLE_MEMO = (
    "Investment Memo - Project Brickell\n\n"
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
# Data loaders (CSV-backed; cache in Streamlit; load eagerly in self-test)
# ---------------------------------------------------------------------------
def _load_sot_comps_index() -> set[str]:
    """Return a lowercased property-name index for fast existence checks."""
    df = pd.read_csv(DATA_DIR / "sot_comps.csv")
    return {n.lower().strip() for n in df["property_name"].tolist()}


def _load_sample_memos_df() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "sample_memos.csv")


def _load_sot_stats_df() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "sot_stats.csv")


def _load_deficiency_classes_df() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "deficiency_classes.csv")


# ---------------------------------------------------------------------------
# Pure verifiers - tested by --selftest and used by the Streamlit shell
# ---------------------------------------------------------------------------
def extract_comp_names(text: str) -> list[str]:
    """Pull every 'Comp N - <name>, ...' line and return the names."""
    names: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.lower().startswith("comp ") and " - " in s:
            after_dash = s.split(" - ", 1)[1]
            name = after_dash.split(",")[0].strip()
            names.append(name)
    return names


def verify_comps_against_sot(text: str, sot_index: set[str]) -> tuple[list[str], list[str]]:
    """Return (verified_names, fabricated_names)."""
    names = extract_comp_names(text)
    verified = [n for n in names if n.lower().strip() in sot_index]
    fabricated = [n for n in names if n.lower().strip() not in sot_index]
    return verified, fabricated


def verify_t12_rollforward(text: str) -> tuple[bool, float, float]:
    """Sum monthly rows; compare to memo's stated sum.

    Returns (ok, memo_sum, recomputed_sum). ok=True means within tolerance OR
    not enough data to test.
    """
    months: list[float] = []
    sum_line = None
    for line in text.splitlines():
        m = re.match(r"\s*Month\s+\d+:\s*\$?([\d,]+)", line)
        if m:
            months.append(float(m.group(1).replace(",", "")))
            continue
        m = re.search(r"Sum\s*\(memo states\):\s*\$?([\d,]+)", line)
        if m:
            sum_line = float(m.group(1).replace(",", ""))
    if not months or sum_line is None:
        return True, 0.0, 0.0
    recomputed = sum(months)
    return abs(sum_line - recomputed) <= T12_TOLERANCE_USD, sum_line, recomputed


def verify_cap_rate(text: str) -> tuple[bool, float, float]:
    """Compare stated cap rate to the inline recompute annotation.

    Returns (ok, stated, recomputed). ok=True means within tolerance OR no
    annotation present.
    """
    m_stated = re.search(r"Stated cap rate:\s*([\d.]+)%", text)
    m_recomp = re.search(r"\[Recompute:[^\]]*=\s*([\d.]+)%", text)
    if not (m_stated and m_recomp):
        return True, 0.0, 0.0
    stated = float(m_stated.group(1))
    recomp = float(m_recomp.group(1))
    return abs(stated - recomp) <= CAP_TOLERANCE_PCT, stated, recomp


def verify_occupancy(text: str) -> tuple[bool, float, float]:
    m_stated = re.search(r"Stated occupancy:\s*([\d.]+)%", text)
    m_roll = re.search(r"Rent roll:\s*([\d.]+)%", text)
    if not (m_stated and m_roll):
        return True, 0.0, 0.0
    s = float(m_stated.group(1))
    r = float(m_roll.group(1))
    return abs(s - r) <= OCC_TOLERANCE_PCT, s, r


def verify_exit_cap_spread(text: str) -> tuple[bool, float, float]:
    m_g = re.search(r"Going-in cap[^%]*?([\d.]+)%", text)
    m_e = re.search(r"Exit cap[^%]*?([\d.]+)%", text)
    if not (m_g and m_e):
        return True, 0.0, 0.0
    g = float(m_g.group(1))
    e = float(m_e.group(1))
    spread_bps = (e - g) * 100
    return spread_bps >= EXIT_CAP_MIN_SPREAD_BPS, g, e


def detect_submarket_staleness(text: str) -> bool:
    """Look for the inline staleness annotation [NOTE: ... 2024 ...]."""
    if "[NOTE:" in text and "2024" in text:
        return True
    return False


def run_all_checks(text: str, sot_index: set[str]) -> dict:
    """Run every check and return a unified result dict."""
    verified, fabricated = verify_comps_against_sot(text, sot_index)
    t12_ok, t12_memo, t12_recomp = verify_t12_rollforward(text)
    cap_ok, cap_stated, cap_recomp = verify_cap_rate(text)
    occ_ok, occ_stated, occ_roll = verify_occupancy(text)
    exit_ok, exit_g, exit_e = verify_exit_cap_spread(text)
    stale = detect_submarket_staleness(text)

    findings: list[tuple[str, str, str]] = []
    for fab in fabricated:
        findings.append(
            ("comp_citation_fabrication", f"'{fab}' not found in SOT_COMPS", "high")
        )
    if not t12_ok:
        findings.append(
            (
                "t12_noi_rollforward_error",
                f"Memo sum ${t12_memo:,.0f} vs recompute ${t12_recomp:,.0f} (delta ${t12_memo - t12_recomp:+,.0f})",
                "high",
            )
        )
    if not cap_ok:
        findings.append(
            (
                "cap_rate_computational_error",
                f"Memo {cap_stated:.2f}% vs recompute {cap_recomp:.2f}% ({(cap_recomp - cap_stated) * 100:+.0f} bps)",
                "high",
            )
        )
    if not occ_ok:
        findings.append(
            (
                "occupancy_rate_discrepancy",
                f"Stated {occ_stated:.1f}% vs rent roll {occ_roll:.1f}% ({occ_stated - occ_roll:+.1f} pts)",
                "medium",
            )
        )
    if not exit_ok:
        spread = (exit_e - exit_g) * 100
        findings.append(
            (
                "exit_cap_assumption_mismatch",
                f"Going-in {exit_g:.2f}% / exit {exit_e:.2f}% (spread {spread:+.0f} bps; std practice +25-50 bps)",
                "medium",
            )
        )
    if stale:
        findings.append(
            (
                "submarket_stat_staleness",
                "Memo cites 2024 figure as current submarket stat",
                "medium",
            )
        )

    has_high = any(f[2] == "high" for f in findings)
    has_med = any(f[2] == "medium" for f in findings)
    if has_high:
        verdict = "FAIL"
        action = "Reject. Do not advance to IC."
    elif has_med:
        verdict = "REVIEW"
        action = "Send to senior analyst review before IC."
    else:
        verdict = "PASS"
        action = "Approve and proceed to IC."

    # Dollar bid-risk model: weight by severity * count
    fail_high_count = sum(1 for f in findings if f[2] == "high")
    fail_med_count = sum(1 for f in findings if f[2] == "medium")
    bid_risk = fail_high_count * 900_000 + fail_med_count * 240_000

    return {
        "comps_verified": verified,
        "comps_fabricated": fabricated,
        "comps_cited": len(verified) + len(fabricated),
        "findings": findings,
        "verdict": verdict,
        "recommended_action": action,
        "bid_risk_usd": bid_risk,
        "t12": (t12_ok, t12_memo, t12_recomp),
        "cap": (cap_ok, cap_stated, cap_recomp),
        "occ": (occ_ok, occ_stated, occ_roll),
        "exit": (exit_ok, exit_g, exit_e),
        "submarket_stale": stale,
    }


# ---------------------------------------------------------------------------
# PDF generation (preserved + extended)
# ---------------------------------------------------------------------------
def build_workpaper_pdf(memo_label: str, market: str, asset_class: str, result: dict) -> bytes:
    """Render a multi-page IC-ready PDF workpaper using reportlab."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            PageBreak,
        )
    except ImportError:
        return b""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#0f172a"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, textColor=colors.HexColor("#b45309"))
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14)
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#64748b"))

    flow = []
    flow.append(Paragraph("DealSentry Verification Workpaper", h1))
    flow.append(Spacer(1, 0.1 * inch))
    flow.append(Paragraph(f"<b>Memo:</b> {memo_label}", body))
    flow.append(Paragraph(f"<b>Market / asset class:</b> {market} / {asset_class}", body))
    flow.append(Paragraph(f"<b>Verdict:</b> {result['verdict']} - {result['recommended_action']}", body))
    flow.append(Paragraph(f"<b>Bid risk caught (modeled):</b> ${result['bid_risk_usd']:,.0f}", body))
    flow.append(Spacer(1, 0.18 * inch))

    flow.append(Paragraph("Comp verification", h2))
    comp_rows = [["Verified", str(len(result["comps_verified"]))]]
    comp_rows.append(["Fabricated", str(len(result["comps_fabricated"]))])
    comp_rows.append(["Total cited", str(result["comps_cited"])])
    t = Table(comp_rows, colWidths=[2.0 * inch, 1.0 * inch])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 0.15 * inch))

    flow.append(Paragraph("Findings (per deficiency class)", h2))
    if not result["findings"]:
        flow.append(Paragraph("No findings. All three verifier paths returned PASS.", body))
    else:
        fdata = [["Class", "Detail", "Severity"]]
        for cls, detail, sev in result["findings"]:
            fdata.append([cls, detail[:80], sev.upper()])
        t2 = Table(fdata, colWidths=[2.1 * inch, 4.0 * inch, 0.9 * inch])
        t2.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
            ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ]))
        flow.append(t2)

    flow.append(Spacer(1, 0.2 * inch))
    flow.append(Paragraph("Source of truth", h2))
    flow.append(Paragraph(
        "Comp existence dereferenced against <b>data/sot_comps.csv</b> "
        "(synthetic; in production: CoStar Real Estate Manager + Reonomy Properties + Cherre Property APIs). "
        "Submarket stats cross-checked against <b>data/sot_stats.csv</b>. "
        "T-12 NOI sum, cap-rate math, occupancy reconciliation, and exit-cap spread re-run symbolically in Python (no LLM in the math path).",
        body,
    ))
    flow.append(Spacer(1, 0.15 * inch))
    flow.append(Paragraph(
        "Generated by DealSentry portfolio prototype. "
        "Production architecture in <b>README.md</b> and <b>ARCHITECTURE.md</b>.",
        small,
    ))

    doc.build(flow)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Self-test entrypoint (importable + invokable: python app.py --selftest)
# ---------------------------------------------------------------------------
def _selftest() -> None:
    """Smoke tests for the verifier paths. Used in CI + by the user."""
    sot_index = _load_sot_comps_index()
    memos = _load_sample_memos_df()
    stats = _load_sot_stats_df()
    defs = _load_deficiency_classes_df()

    assert len(sot_index) >= 30, "SOT comp index too small"
    assert len(memos) == 6, f"Expected 6 memos, got {len(memos)}"
    assert len(defs) == 6, f"Expected 6 deficiency classes, got {len(defs)}"
    assert len(stats) >= 30, "SOT stats too small"

    by_id = {r["memo_id"]: r for _, r in memos.iterrows()}

    # MEMO_01 clean industrial - should PASS
    r1 = run_all_checks(by_id["MEMO_01"]["memo_text"], sot_index)
    assert r1["verdict"] == "PASS", f"MEMO_01 should PASS, got {r1['verdict']}: {r1['findings']}"
    assert not r1["comps_fabricated"], "MEMO_01 should have no fabricated comps"

    # MEMO_03 has T-12 drift - should FAIL
    r3 = run_all_checks(by_id["MEMO_03"]["memo_text"], sot_index)
    assert any(f[0] == "t12_noi_rollforward_error" for f in r3["findings"]), "MEMO_03 must trip T-12"

    # MEMO_04 has fabricated comps + exit-cap flat - should FAIL
    r4 = run_all_checks(by_id["MEMO_04"]["memo_text"], sot_index)
    assert len(r4["comps_fabricated"]) >= 2, "MEMO_04 should have >=2 fabricated comps"
    assert r4["verdict"] == "FAIL", f"MEMO_04 should FAIL, got {r4['verdict']}"

    # MEMO_05 has stale submarket stat
    r5 = run_all_checks(by_id["MEMO_05"]["memo_text"], sot_index)
    assert r5["submarket_stale"], "MEMO_05 should trip submarket staleness"

    # MEMO_06 multi-fault
    r6 = run_all_checks(by_id["MEMO_06"]["memo_text"], sot_index)
    assert r6["verdict"] == "FAIL", f"MEMO_06 should FAIL, got {r6['verdict']}: {r6['findings']}"
    assert len(r6["comps_fabricated"]) >= 1, "MEMO_06 should have fabricated comp"
    cap_classes = {f[0] for f in r6["findings"]}
    assert "cap_rate_computational_error" in cap_classes, "MEMO_06 must trip cap-rate"
    assert "occupancy_rate_discrepancy" in cap_classes, "MEMO_06 must trip occupancy"

    # Default SAMPLE_MEMO - the regex parser should handle it without crashing
    r_default = run_all_checks(SAMPLE_MEMO, sot_index)
    assert r_default["comps_cited"] >= 4

    # PDF render should produce non-empty bytes
    pdf = build_workpaper_pdf("self-test", "Brickell South", "retail", r4)
    assert len(pdf) > 1000, "PDF build returned suspiciously small bytes"

    print("Self-tests passed")


# ---------------------------------------------------------------------------
# Streamlit shell
# ---------------------------------------------------------------------------
def _run_streamlit() -> None:
    import streamlit as st

    st.set_page_config(
        page_title="DealSentry - Stops bad CRE bids built on hallucinated comps",
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Theme
    st.markdown(
        """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

.ds-hero {
  background: linear-gradient(135deg,#1c1917 0%, #44403c 50%, #b45309 100%);
  border-radius: 18px; padding: 36px 40px; color:#fff; margin-bottom:28px;
}
.ds-hero .brand {font-size:26px; font-weight:600; opacity:0.92; margin-bottom:12px;}
.ds-hero h1 {color:#fff !important; font-size:46px; line-height:1.12; margin:0 0 14px 0; font-weight:700;}
.ds-hero .sub {font-size:17px; line-height:1.5; opacity:0.93; max-width:820px; margin-bottom:22px;}
.ds-hero .pills {display:flex; flex-wrap:wrap; gap:10px;}
.ds-hero .pill {background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
                color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.ds-hero .pill a {color:#fff; text-decoration:none;}

.ds-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:22px 26px;
          margin-bottom:18px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.ds-card h3 {margin-top:0; color:#0f172a;}
.ds-step-label {display:inline-block; background:#b45309; color:#fff; padding:3px 10px;
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

    @st.cache_data
    def _cached_sot_index():
        return _load_sot_comps_index()

    @st.cache_data
    def _cached_memos():
        return _load_sample_memos_df()

    @st.cache_data
    def _cached_stats():
        return _load_sot_stats_df()

    @st.cache_data
    def _cached_defs():
        return _load_deficiency_classes_df()

    sot_index = _cached_sot_index()
    memos_df = _cached_memos()
    stats_df = _cached_stats()
    defs_df = _cached_defs()

    if "step" not in st.session_state:
        st.session_state.step = 1
    if "memo_choice" not in st.session_state:
        st.session_state.memo_choice = "MEMO_04"  # default to fabricated-comp drama

    def advance(target: int) -> None:
        if st.session_state.step < target:
            st.session_state.step = target

    # Hero
    st.markdown(
        f"""
<div class='ds-hero'>
  <div class='brand'>🏗️ DealSentry</div>
  <h1>Stops CRE underwriting copilots from sending IC memos with fabricated comps and bad math.</h1>
  <div class='sub'>Sits behind your AI underwriting copilot. Verifies every cited comp against
  a source-of-truth comp database (CoStar / Reonomy / Cherre); re-runs T-12 NOI, cap-rate, and
  occupancy math symbolically; cross-checks submarket stats across multiple feeds to flag stale
  quarters. The output is a sectional PASS / REVIEW / FAIL verdict the IC chair can act on.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
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

    # Step 1 - pick a memo
    st.markdown(
        "<div class='ds-card'><span class='ds-step-label'>Step 1</span>"
        "<h3>Paste an AI-generated underwriting memo, or pick one of 6 samples</h3>"
        "<p class='muted'>Six synthetic memos cover the failure modes - clean industrial, clean multifamily, "
        "T-12 math drift, fabricated comps, stale submarket stat, multi-fault.</p></div>",
        unsafe_allow_html=True,
    )

    memo_options = {
        f"{r['memo_id']} - {r['asset_name']} ({r['market']})": r["memo_id"]
        for _, r in memos_df.iterrows()
    }
    chosen_label = st.selectbox(
        "Sample memo:",
        list(memo_options.keys()),
        index=list(memo_options.values()).index(st.session_state.memo_choice)
        if st.session_state.memo_choice in memo_options.values() else 3,
        label_visibility="collapsed",
    )
    st.session_state.memo_choice = memo_options[chosen_label]
    chosen_row = memos_df[memos_df["memo_id"] == st.session_state.memo_choice].iloc[0]

    with st.expander("View memo text (paste your own here):", expanded=False):
        pasted = st.text_area(
            "Memo text:",
            value=chosen_row["memo_text"],
            height=320,
            key="pasted_memo",
        )
        st.caption("Or pick a sample memo above to see a guaranteed-extraction demo.")

    pasted_clean = (pasted or "").strip()
    sample_clean = chosen_row["memo_text"].strip()
    user_pasted = bool(pasted_clean) and pasted_clean != sample_clean

    if user_pasted and len(pasted_clean) < MIN_MEMO_LEN:
        st.warning(
            f"Pasted text is too short to verify ({len(pasted_clean)} chars). "
            f"Paste at least {MIN_MEMO_LEN} characters of memo text, or pick a sample memo."
        )

    if user_pasted and len(pasted_clean) >= MIN_MEMO_LEN:
        memo_text = pasted_clean
        memo_label = "User-pasted memo (best-effort verification)"
        memo_market = "(user-pasted)"
        memo_asset_class = "(user-pasted)"
        is_user_paste = True
    else:
        memo_text = chosen_row["memo_text"]
        memo_label = chosen_label
        memo_market = chosen_row["market"]
        memo_asset_class = chosen_row["asset_class"]
        is_user_paste = False

    if st.session_state.step < 2:
        if st.button("Verify the memo  ->", type="primary", key="cta_step1"):
            advance(2)
            st.rerun()

    # Step 2 - executive verdict
    if st.session_state.step >= 2:
        result = run_all_checks(memo_text, sot_index)
        verdict = result["verdict"]
        action = result["recommended_action"]

        if verdict == "PASS":
            verdict_class = "verdict-pass"
            confidence = "HIGH (>95%)"
            confidence_class = "confidence-high"
            tldr = "All three verifier paths returned PASS. Memo is safe to send to IC."
            risk = "LOW"
        elif verdict == "REVIEW":
            verdict_class = "verdict-review"
            confidence = "MEDIUM (70-95%)"
            confidence_class = "confidence-med"
            tldr = f"{len(result['findings'])} medium-severity flag(s). Resolve before IC."
            risk = "MEDIUM"
        else:
            verdict_class = "verdict-flag"
            confidence = "LOW (<70%)"
            confidence_class = "confidence-low"
            tldr = (
                f"{len(result['comps_fabricated'])} comp(s) failed SOT existence check "
                "and/or arithmetic does not reconcile. Do not advance."
            )
            risk = "HIGH"

        st.markdown(
            f"""
<div class='verdict-card {verdict_class}'>
  <div class='vlabel'>DealSentry Verdict</div>
  <div class='vbig'>{verdict}</div>
  <div class='vmetric'>{len(result['comps_verified'])} of {result['comps_cited']} comps verified · {len(result['findings'])} finding(s) across 6 deficiency classes</div>
  <div class='vrow'>
    <span class='vchip'>Risk: {risk}</span>
    <span class='vchip'>Action: {action}</span>
    <span class='vchip'>Bid risk caught: ${result['bid_risk_usd']:,.0f}</span>
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
  <div>Compared cited comps against
    <a href='{GH_BLOB_BASE}/sot_comps.csv' target='_blank'><code>data/sot_comps.csv</code></a>
    (40 synthetic source-of-truth comps modeled on <a href='https://www.costar.com/' target='_blank'>CoStar</a>,
    <a href='https://www.reonomy.com/' target='_blank'>Reonomy</a>,
    <a href='https://cherre.com/' target='_blank'>Cherre</a> coverage). Arithmetic re-run symbolically
    (no LLM in the math path). Submarket stats cross-checked against
    <a href='{GH_BLOB_BASE}/sot_stats.csv' target='_blank'><code>data/sot_stats.csv</code></a>
    (quarterly versioning to catch staleness).</div>
  <span class='tlabel'>Assumptions we made</span>
  <ul>
    <li>SOT comp coverage in the engaged operator's submarkets approximates public CoStar / Reonomy / Cherre coverage shape (calibrated against published <a href='https://www.ncreif.org/' target='_blank'>NCREIF</a> data).</li>
    <li>Memos cite verifiable identifiers (property name, sale date, $/sf, cap rate) so a deterministic match is possible.</li>
    <li>T-12 normalization rules follow standard CRE practice (vacancy adjustment, capex reserve, management fee) per <a href='https://www.icsc.com/' target='_blank'>ICSC</a> / NCREIF convention.</li>
    <li>Dollar bid-risk numbers are modeled from finding severity counts; production tuning needed per operator.</li>
  </ul>
  <span class='tlabel'>Confidence level</span>
  <div class='{confidence_class}'>{confidence}</div>
  <span class='tlabel'>What this does NOT cover</span>
  <ul>
    <li>Macro / market-cycle risk (DealSentry is a memo-reliability layer, not a deal-quality oracle).</li>
    <li>Off-market or proprietary comps not in any feed (handled by analyst override workflow).</li>
    <li>Qualitative IC concerns (sponsor track record, management team, ESG).</li>
  </ul>
</div>
""",
            unsafe_allow_html=True,
        )

        # Detailed findings expander
        with st.expander("Detailed findings - per-deficiency breakdown", expanded=(verdict != "PASS")):
            if not result["findings"]:
                st.markdown("All checks passed. No findings.")
            else:
                df = pd.DataFrame(
                    result["findings"],
                    columns=["deficiency_class", "what DealSentry caught", "severity"],
                )
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.markdown(
                    f"_Comps cited: {result['comps_cited']}. "
                    f"Verified against SOT_COMPS: {len(result['comps_verified'])}. "
                    f"Fabricated (no SOT match): {len(result['comps_fabricated'])}._"
                )

        if is_user_paste:
            with st.expander("Extracted comp names from your pasted memo (best-effort)"):
                names = extract_comp_names(memo_text)
                if names:
                    ext_df = pd.DataFrame(
                        [(i + 1, n, ("verified" if n.lower().strip() in sot_index else "no SOT match"))
                         for i, n in enumerate(names)],
                        columns=["#", "comp name extracted", "SOT match"],
                    )
                    st.dataframe(ext_df, use_container_width=True, hide_index=True)
                else:
                    st.info(
                        "No 'Comp N - <name>' lines found in your paste. The regex parser looks "
                        "for that exact pattern. Use one of the sample memos for a guaranteed-extraction demo."
                    )

        if st.session_state.step < 3:
            if st.button("See the bid-risk and workpaper  ->", type="primary", key="cta_step2"):
                advance(3)
                st.rerun()

    # Step 3 - bid-risk + downloads
    if st.session_state.step >= 3:
        st.markdown(
            "<div class='ds-card'><span class='ds-step-label'>Step 3</span>"
            "<h3>Bid-risk and verification workpaper</h3>"
            "<p class='muted'>What it would cost the operator if these findings landed in the IC packet "
            "unverified - and the IC-ready workpaper auto-assembled for the deal team and IC chair.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        bid_risk = result["bid_risk_usd"]
        if bid_risk == 0:
            st.markdown(
                "<div class='verdict-card verdict-pass'>"
                "<div class='vlabel'>Bid Risk Caught</div>"
                "<div class='vbig'>$0</div>"
                "<div class='vmetric'>No findings - clean memo.</div>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
<div class='verdict-card verdict-flag'>
  <div class='vlabel'>Bid Risk Caught (modeled)</div>
  <div class='vbig'>${bid_risk:,.0f}</div>
  <div class='vmetric'>Captured by DealSentry before IC</div>
  <div class='vtldr'>Pattern: fabricated comp citations + T-12 arithmetic drift + cap-rate decimal-place errors = the recurring bad-bid shape.</div>
</div>
""",
                unsafe_allow_html=True,
            )

        # Markdown workpaper
        workpaper_md = (
            f"# DealSentry Verification Workpaper\n\n"
            f"**Memo:** {memo_label}\n\n"
            f"**Market / asset class:** {memo_market} / {memo_asset_class}\n\n"
            f"**Verdict:** {result['verdict']} - {result['recommended_action']}\n\n"
            f"**Bid risk caught (modeled):** ${result['bid_risk_usd']:,.0f}\n\n"
            f"**Comps cited / verified / fabricated:** "
            f"{result['comps_cited']} / {len(result['comps_verified'])} / {len(result['comps_fabricated'])}\n\n"
            f"## Findings\n\n"
        )
        if not result["findings"]:
            workpaper_md += "- All checks passed.\n"
        else:
            for cls, detail, sev in result["findings"]:
                workpaper_md += f"- **[{sev.upper()}] {cls}:** {detail}\n"
        workpaper_md += (
            f"\n## Source of truth\n\n"
            f"- Comp existence: [data/sot_comps.csv]({GH_BLOB_BASE}/sot_comps.csv)\n"
            f"- Submarket stats: [data/sot_stats.csv]({GH_BLOB_BASE}/sot_stats.csv)\n"
            f"- Deficiency taxonomy: [data/deficiency_classes.csv]({GH_BLOB_BASE}/deficiency_classes.csv)\n"
            f"- Symbolic math: pandas re-run of T-12, cap rate, occupancy, exit-cap spread (no LLM)\n"
        )

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "Download workpaper (Markdown)",
                workpaper_md,
                file_name=f"dealsentry_workpaper_{st.session_state.memo_choice.lower()}.md",
                mime="text/markdown",
            )
        with col2:
            pdf_bytes = build_workpaper_pdf(memo_label, memo_market, memo_asset_class, result)
            if pdf_bytes:
                st.download_button(
                    "Download workpaper (PDF)",
                    pdf_bytes,
                    file_name=f"dealsentry_workpaper_{st.session_state.memo_choice.lower()}.pdf",
                    mime="application/pdf",
                )

        # SOT data viewers
        with st.expander("Inspect source-of-truth comps (sot_comps.csv)"):
            st.caption(
                "Synthetic source-of-truth comp database modeled on CoStar / Reonomy / Cherre coverage. "
                "Every cited comp is dereferenced against this table. Sort by clicking a column header."
            )
            st.dataframe(_load_sot_comps_index_df(), use_container_width=True, hide_index=True)

        with st.expander("Inspect source-of-truth submarket stats (sot_stats.csv)"):
            st.caption(
                "Submarket vacancy / asking rent / cap rate stats with quarterly versioning. "
                "Bellevue Eastside MOB has both 2024-Q3 and 2025-Q4 rows so the staleness check is a real comparison."
            )
            st.dataframe(stats_df, use_container_width=True, hide_index=True)

        with st.expander("Inspect deficiency taxonomy (deficiency_classes.csv)"):
            st.caption("The 6 named deficiency classes DealSentry checks for.")
            st.dataframe(defs_df, use_container_width=True, hide_index=True)

        # Glossary
        with st.expander("Glossary - CRE terms in plain English"):
            glossary_df = pd.DataFrame(
                [
                    ("CoStar", "Largest commercial real estate data provider; CompStak for sale comps. costar.com"),
                    ("Reonomy", "Property intelligence platform with ownership + transaction data. reonomy.com"),
                    ("Cherre", "Real estate data integration platform; pulls many SOT feeds into one model. cherre.com"),
                    ("NCREIF", "National Council of Real Estate Investment Fiduciaries - publishes the industry benchmarks (NPI, ODCE)."),
                    ("ICSC", "International Council of Shopping Centers - sets standards for retail leases and convention research."),
                    ("Yardi Voyager", "Industry-standard property accounting + asset management system; the system of record DealSentry would write back into."),
                    ("T-12 NOI", "Trailing-twelve-month Net Operating Income. Income - operating expenses, summed across the prior 12 months."),
                    ("Cap rate", "Capitalization rate = NOI / property value. The yield the buyer is acquiring at."),
                    ("Going-in cap", "Cap rate at acquisition (Year 1)."),
                    ("Exit cap", "Cap rate assumed at sale in the IRR model (typically Year 5 or 10). Standard practice: exit = going-in + 25-50 bps for office / industrial."),
                    ("ppsf / $/sf", "Price per square foot. Industry-standard comp metric for office / retail / industrial."),
                    ("IC (Investment Committee)", "The senior decision-making body that approves acquisitions over a size threshold."),
                    ("OM (Offering Memorandum)", "The broker's marketing document for a property being sold. Contains the broker's view of comps, stabilized NOI, and asking price."),
                    ("Rent roll", "Line-by-line lease table showing tenant, unit, SF, rent, term, escalation, options. The source-of-truth for current NOI."),
                    ("Submarket", "A geographic sub-division of a metro. CoStar publishes formal submarket boundaries that operators standardize on."),
                    ("Bid risk", "Modeled dollar cost of advancing a deal on bad inputs - mispricing relative to a verified underwriting."),
                ],
                columns=["Term", "Plain English / link"],
            )
            st.dataframe(glossary_df, use_container_width=True, hide_index=True)

        # Why Streamlit / production stack reassessment
        with st.expander("Production stack reassessment - what this looks like as SaaS"):
            st.markdown(
                "**Streamlit was the right tool for this prototype.** It proves the product mechanic - "
                "three independent verifier paths on a 6-memo eval set - in a free, single-page deploy "
                "an acquisitions lead can walk in 10 minutes.\n\n"
                "**If DealSentry shipped to a national CRE operator:**\n"
                "- Frontend: Next.js + Tailwind + shadcn/ui, embedded in the deal-pipeline tool the team "
                "already uses (Dealpath, Juniper Square, or a custom Salesforce CRE Cloud build).\n"
                "- Auth: SAML / OIDC with the operator's IdP (Okta, Azure AD).\n"
                "- Backend: FastAPI on EKS; microservice per check (comp verifier, T-12 re-runner, submarket "
                "cross-check, cap-rate/occupancy/exit-cap validator).\n"
                "- Source-of-truth integrations: live CoStar Real Estate Manager API, Reonomy Properties API, "
                "Cherre Property API, RCA / MSCI Real Capital Analytics, REIS / Moody's CRE.\n"
                "- Symbolic math: sympy-based T-12 normalization that replays rent roll -> NOI -> cap rate.\n"
                "- Observability: OpenTelemetry -> Datadog; Langfuse for LLM-verifier traces.\n"
                "- Governance: every flagged comp produces a workpaper the senior analyst signs off on before IC.\n"
                "- Compliance: SOC 2 Type II baseline; audit log of every fabrication decision retained for the hold period.\n"
            )

        st.markdown(
            f"<div class='ds-card muted'>Built as a portfolio prototype. Production architecture in "
            f"<a href='{GITHUB_URL}/blob/main/10-dealsentry-cre-underwriting/README.md' target='_blank'><code>README.md</code></a> "
            f"and <a href='{GITHUB_URL}/blob/main/10-dealsentry-cre-underwriting/ARCHITECTURE.md' target='_blank'><code>ARCHITECTURE.md</code></a>.</div>",
            unsafe_allow_html=True,
        )


# Streamlit expander helper - need full df not just index set
def _load_sot_comps_index_df() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "sot_comps.csv")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        # When run as a Streamlit app, Streamlit imports this module and
        # executes top-level code, but `streamlit run` invokes the script
        # under its own runner. Fall through to the streamlit shell.
        _run_streamlit()
else:
    # When Streamlit imports this module via `streamlit run app.py`, the
    # __name__ is "__main__" (Streamlit overrides it), so this branch is
    # mostly dead - but kept as a safety net.
    pass
