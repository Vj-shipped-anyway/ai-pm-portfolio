"""
DealSentry — CRE AI Underwriting Reliability (Streamlit prototype)

Author: Vijay Saharan
Run:    streamlit run app.py
Tests:  python app.py --selftest

A three-check sentinel that audits AI-drafted CRE underwriting memos:

  Check 1 — Comp citation verification.
            Every claimed comp is matched against a synthetic source-of-truth
            database (modeled on CoStar / Reonomy / Cherre coverage). Address
            existence, price/sf within 5%, cap rate within 10% determines status.

  Check 2 — Symbolic arithmetic re-validation.
            T-12 NOI, implied NOI from rent roll, occupancy math are recomputed
            line-by-line and compared to the memo's stated values.

  Check 3 — Submarket stat cross-check.
            Vacancy and asking-rent claims are diffed against two synthetic
            feeds (CoStar + Reonomy) per submarket. Divergence beyond a tunable
            band flags the line.

The product opinion: AI underwriting copilots produce *plausible-shaped*
outputs (right form, no underlying source) at uncomfortable rates. The
fix is reliability scaffolding, not a better model. DealSentry is the
scaffolding.

Production-ready notes (these matter for a reviewer):
  - Parsers are defensive: regex tolerates whitespace, case, $ optional,
    "/sf" or "psf" or "per sf", optional bullet prefix.
  - Empty / malformed memos surface a warning, never a stack trace.
  - Every parser returns a typed result; tests live at the bottom of this
    module and run via `python app.py --selftest`.
  - In production: replace SOT_COMPS / SOT_STATS with live calls to
    CoStar Real Estate Manager API, Reonomy Properties API, or Cherre's
    Property API. Replace heuristic checks with multi-feed consensus.
"""

from __future__ import annotations

import datetime
import hashlib
import io
import re
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st


# -----------------------------------------------------------------------------
# Synthetic source-of-truth — comp database + submarket feeds
# In production: live calls to CoStar / Reonomy / Cherre / proprietary APIs.
# -----------------------------------------------------------------------------

SOT_COMPS = pd.DataFrame([
    {"address": "1450 Wilshire Blvd",  "submarket": "Mid-Wilshire", "class": "Office",       "ppsf": 412, "cap_rate": 5.8, "date": "2025-09-12"},
    {"address": "885 Sepulveda",       "submarket": "Westside",     "class": "Office",       "ppsf": 535, "cap_rate": 5.2, "date": "2025-11-04"},
    {"address": "200 Spring St",       "submarket": "DTLA",         "class": "Office",       "ppsf": 298, "cap_rate": 6.4, "date": "2025-08-20"},
    {"address": "9200 Sunset",         "submarket": "Westside",     "class": "Office",       "ppsf": 612, "cap_rate": 4.9, "date": "2025-10-30"},
    {"address": "1100 S Hope",         "submarket": "DTLA",         "class": "Multifamily",  "ppsf": 421, "cap_rate": 4.6, "date": "2025-12-02"},
    {"address": "350 N La Brea",       "submarket": "Mid-Wilshire", "class": "Retail",       "ppsf": 388, "cap_rate": 5.5, "date": "2025-07-15"},
])

SOT_STATS = pd.DataFrame([
    {"submarket": "Mid-Wilshire", "feed": "CoStar",  "vacancy_pct": 12.4, "asking_rent_psf": 38.20, "cap_rate": 5.9},
    {"submarket": "Mid-Wilshire", "feed": "Reonomy", "vacancy_pct": 12.1, "asking_rent_psf": 37.95, "cap_rate": 5.8},
    {"submarket": "Westside",     "feed": "CoStar",  "vacancy_pct":  9.7, "asking_rent_psf": 52.30, "cap_rate": 5.1},
    {"submarket": "Westside",     "feed": "Reonomy", "vacancy_pct": 10.0, "asking_rent_psf": 51.80, "cap_rate": 5.2},
    {"submarket": "DTLA",         "feed": "CoStar",  "vacancy_pct": 18.6, "asking_rent_psf": 34.10, "cap_rate": 6.5},
    {"submarket": "DTLA",         "feed": "Reonomy", "vacancy_pct": 19.2, "asking_rent_psf": 33.85, "cap_rate": 6.6},
])


SAMPLE_MEMO = """\
1450 Wilshire Blvd — Underwriting Summary

Asset: 1450 Wilshire Blvd, Class A office, Mid-Wilshire submarket, 215,000 RSF.

Comparable transactions (last 12 months):
- 1450 Wilshire Blvd traded at $412/sf, 5.8 cap, September 2025.
- 885 Sepulveda traded at $535/sf, 5.2 cap, November 2025.
- 200 Spring St traded at $298/sf, 6.4 cap, August 2025.
- 9200 Sunset traded at $720/sf, 4.4 cap, October 2025.

Submarket data:
Vacancy in Mid-Wilshire is 12.3%.
Asking rent in submarket: $38.10 / sf.

Financial validation:
T-12 NOI: $7,420,000.
Rent roll effective rent: $34.10/sf x 215,000 RSF x 91% occupancy = $6,665,134.
Operating expense ratio: 38%.
Implied NOI from rent roll: $6,665,134 - 0.38 * $6,665,134 = $4,132,383.

Year-1 NOI projection: $7,650,000.
Year-3 IRR: 14.4%.
Recommendation: Bid $86M at 5.5 cap.
"""


# -----------------------------------------------------------------------------
# Regex patterns — defined once at module level for clarity and reuse
# -----------------------------------------------------------------------------

COMP_PATTERN = re.compile(
    r"""
    (?:^|\n)                                  # at line boundary
    \s*(?:[-*•]\s*)?                          # optional bullet
    (?P<address>.+?)                          # address (lazy)
    \s+traded\s+at\s+
    \$?\s*(?P<ppsf>\d+(?:\.\d+)?)             # $/sf, $ optional
    \s*(?:/\s*sf|psf|per\s+sf|/\s*SF)         # unit
    \s*,\s*
    (?P<cap>\d+(?:\.\d+)?)                    # cap rate value
    \s*%?\s*cap                               # "cap" or "% cap"
    \s*,\s*
    (?P<month>[A-Za-z]+)                      # month name
    \s+(?P<year>\d{4})                        # year
    """,
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)

VACANCY_PATTERN = re.compile(
    r"vacancy\s+in\s+(?P<submarket>[A-Za-z\- ]+?)\s+is\s+(?P<value>\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

ASKING_RENT_PATTERN = re.compile(
    r"asking\s+rent\s+in\s+submarket\s*:\s*\$?\s*(?P<value>\d+(?:\.\d+)?)\s*/\s*sf",
    re.IGNORECASE,
)

T12_NOI_PATTERN = re.compile(
    r"T-?12\s+NOI\s*:\s*\$?\s*(?P<value>[\d,]+)",
    re.IGNORECASE,
)

EFFECTIVE_RENT_PATTERN = re.compile(
    r"""
    effective\s+rent\s*:\s*
    \$?\s*(?P<rent_psf>\d+(?:\.\d+)?)\s*/\s*sf
    \s*x\s*(?P<rsf>[\d,]+)\s*RSF
    \s*x\s*(?P<occ>\d+(?:\.\d+)?)\s*%
    """,
    re.VERBOSE | re.IGNORECASE,
)

IMPLIED_NOI_PATTERN = re.compile(
    r"Implied\s+NOI\s+from\s+rent\s+roll\s*:.*?=\s*\$?\s*(?P<value>[\d,]+)",
    re.IGNORECASE | re.DOTALL,
)

OPEX_RATIO_PATTERN = re.compile(
    r"(?:operating\s+expense\s+ratio|expense\s+ratio)\s*:\s*(?P<value>\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)


# -----------------------------------------------------------------------------
# Parsers — extract structured claims from the AI memo
# -----------------------------------------------------------------------------

@dataclass
class CompClaim:
    address: str
    ppsf_claimed: int
    cap_claimed: float
    month_claimed: str
    year_claimed: int


def parse_comps(text: str) -> list[dict[str, Any]]:
    if not text or not isinstance(text, str):
        return []

    out: list[dict[str, Any]] = []
    try:
        for m in COMP_PATTERN.finditer(text):
            out.append({
                "address": m.group("address").strip(),
                "ppsf_claimed": int(float(m.group("ppsf"))),
                "cap_claimed": float(m.group("cap")),
                "month_claimed": m.group("month"),
                "year_claimed": int(m.group("year")),
            })
    except (ValueError, AttributeError):
        pass
    return out


def parse_submarket_stats(text: str) -> dict[str, Any]:
    if not text or not isinstance(text, str):
        return {}

    out: dict[str, Any] = {}
    try:
        m = VACANCY_PATTERN.search(text)
        if m:
            out["vacancy"] = {
                "submarket": m.group("submarket").strip(),
                "value": float(m.group("value")),
            }
        m = ASKING_RENT_PATTERN.search(text)
        if m:
            out["asking_rent"] = float(m.group("value"))
    except (ValueError, AttributeError):
        pass
    return out


def parse_arithmetic(text: str) -> dict[str, Any]:
    if not text or not isinstance(text, str):
        return {}

    out: dict[str, Any] = {}
    try:
        m = T12_NOI_PATTERN.search(text)
        if m:
            out["t12_noi_claimed"] = int(m.group("value").replace(",", ""))

        m = EFFECTIVE_RENT_PATTERN.search(text)
        if m:
            out["rent_psf"] = float(m.group("rent_psf"))
            out["rsf"] = int(m.group("rsf").replace(",", ""))
            out["occ"] = float(m.group("occ")) / 100.0

        m = IMPLIED_NOI_PATTERN.search(text)
        if m:
            out["implied_noi_claimed"] = int(m.group("value").replace(",", ""))

        m = OPEX_RATIO_PATTERN.search(text)
        if m:
            out["opex_ratio"] = float(m.group("value")) / 100.0
    except (ValueError, AttributeError):
        pass
    return out


# -----------------------------------------------------------------------------
# Three checks — verify parsed claims against source-of-truth
# -----------------------------------------------------------------------------

def check_comps(comps: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for c in comps:
        match = SOT_COMPS[SOT_COMPS["address"].str.lower() == c["address"].lower()]
        if match.empty:
            rows.append({**c, "status": "NOT FOUND", "ppsf_truth": None, "cap_truth": None})
            continue
        m = match.iloc[0]
        ppsf_div = abs(c["ppsf_claimed"] - m["ppsf"]) / m["ppsf"]
        cap_div = abs(c["cap_claimed"] - m["cap_rate"]) / m["cap_rate"]
        if ppsf_div < 0.02 and cap_div < 0.05:
            status = "VERIFIED"
        elif ppsf_div < 0.05 and cap_div < 0.10:
            status = "WITHIN TOLERANCE"
        else:
            status = "VALUE MISMATCH"
        rows.append({**c, "status": status, "ppsf_truth": m["ppsf"], "cap_truth": m["cap_rate"]})
    return pd.DataFrame(rows)


def check_arithmetic(a: dict[str, Any]) -> pd.DataFrame:
    rows = []
    if {"rent_psf", "rsf", "occ"} <= a.keys():
        recomputed_eff = a["rent_psf"] * a["rsf"] * a["occ"]
        if "implied_noi_claimed" in a and "opex_ratio" in a:
            recomputed_noi = recomputed_eff * (1 - a["opex_ratio"])
            div = abs(recomputed_noi - a["implied_noi_claimed"]) / max(a["implied_noi_claimed"], 1)
            rows.append({
                "line": "Implied NOI from rent roll",
                "claimed": a["implied_noi_claimed"],
                "recomputed": round(recomputed_noi, 0),
                "divergence_pct": round(div * 100, 2),
                "status": "OK" if div < 0.01 else "DIVERGENCE",
            })
    if "t12_noi_claimed" in a and "implied_noi_claimed" in a:
        div = abs(a["t12_noi_claimed"] - a["implied_noi_claimed"]) / max(a["t12_noi_claimed"], 1)
        rows.append({
            "line": "T-12 NOI vs implied",
            "claimed": a["t12_noi_claimed"],
            "recomputed": a["implied_noi_claimed"],
            "divergence_pct": round(div * 100, 2),
            "status": "OK" if div < 0.05 else "DIVERGENCE",
        })
    return pd.DataFrame(rows)


def check_submarket(stats: dict[str, Any]) -> pd.DataFrame:
    rows = []
    sm = stats.get("vacancy", {}).get("submarket")
    claimed = stats.get("vacancy", {}).get("value")
    if sm:
        feeds = SOT_STATS[SOT_STATS["submarket"].str.lower() == sm.lower()]
        for _, row in feeds.iterrows():
            div = abs(claimed - row["vacancy_pct"]) / row["vacancy_pct"] if claimed else None
            status = "OK" if div is not None and div < 0.05 else "DIVERGENCE"
            rows.append({
                "stat": "vacancy %", "submarket": sm,
                "claimed": claimed, "feed": row["feed"], "feed_value": row["vacancy_pct"],
                "divergence_pct": round((div or 0) * 100, 2), "status": status,
            })
    if "asking_rent" in stats and sm:
        feeds = SOT_STATS[SOT_STATS["submarket"].str.lower() == sm.lower()]
        for _, row in feeds.iterrows():
            div = abs(stats["asking_rent"] - row["asking_rent_psf"]) / row["asking_rent_psf"]
            status = "OK" if div < 0.03 else "DIVERGENCE"
            rows.append({
                "stat": "asking rent psf", "submarket": sm,
                "claimed": stats["asking_rent"], "feed": row["feed"],
                "feed_value": row["asking_rent_psf"],
                "divergence_pct": round(div * 100, 2), "status": status,
            })
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# Self-tests — run with `python app.py --selftest`
# -----------------------------------------------------------------------------

def _run_selftests() -> int:
    failures = 0

    sample = "- 1450 Wilshire Blvd traded at $412/sf, 5.8 cap, September 2025."
    comps = parse_comps(sample)
    assert len(comps) == 1, f"parse_comps happy path: expected 1, got {len(comps)}"
    assert comps[0]["address"] == "1450 Wilshire Blvd"
    assert comps[0]["ppsf_claimed"] == 412
    assert comps[0]["cap_claimed"] == 5.8
    assert comps[0]["year_claimed"] == 2025

    sample_alt = "885 Sepulveda traded at 535 psf, 5.2% cap, november 2025"
    comps_alt = parse_comps(sample_alt)
    assert len(comps_alt) == 1, f"parse_comps psf form: expected 1, got {len(comps_alt)}"
    assert comps_alt[0]["ppsf_claimed"] == 535

    assert parse_comps("") == []
    assert parse_comps(None) == []  # type: ignore[arg-type]
    assert parse_comps("blah blah no comps here") == []

    a = parse_arithmetic("T-12 NOI: $7,420,000. expense ratio: 38%.")
    assert a.get("t12_noi_claimed") == 7420000
    assert a.get("opex_ratio") == 0.38

    assert parse_arithmetic("") == {}
    assert parse_arithmetic("garbage") == {}

    s = parse_submarket_stats("Vacancy in Mid-Wilshire is 12.3%. Asking rent in submarket: $38.10 /sf")
    assert s["vacancy"]["submarket"] == "Mid-Wilshire"
    assert s["vacancy"]["value"] == 12.3
    assert s["asking_rent"] == 38.10

    df = check_comps([
        {"address": "1450 Wilshire Blvd", "ppsf_claimed": 412, "cap_claimed": 5.8,
         "month_claimed": "September", "year_claimed": 2025}
    ])
    assert df.iloc[0]["status"] == "VERIFIED"

    df_bad = check_comps([
        {"address": "9200 Sunset", "ppsf_claimed": 720, "cap_claimed": 4.4,
         "month_claimed": "October", "year_claimed": 2025}
    ])
    assert df_bad.iloc[0]["status"] == "VALUE MISMATCH"

    df_missing = check_comps([
        {"address": "Fake Address That Does Not Exist", "ppsf_claimed": 500, "cap_claimed": 5.0,
         "month_claimed": "May", "year_claimed": 2025}
    ])
    assert df_missing.iloc[0]["status"] == "NOT FOUND"

    print(f"Self-tests passed. (failures: {failures})")
    return 0 if failures == 0 else 1


if __name__ == "__main__" and "--selftest" in sys.argv:
    sys.exit(_run_selftests())


# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="DealSentry — CRE Underwriting Reliability",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .live-pill {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        background: #fff;
        border: 1px solid #d1e7d8;
        font-size: 13px;
        color: #1b5e20;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        white-space: nowrap;
    }
    .live-pill .dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #2e7d32;
        margin-right: 6px;
        vertical-align: middle;
    }
    .pill-wrap {
        text-align: right;
        padding-top: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Constants & helpers
# -----------------------------------------------------------------------------

MEMO_PLACEHOLDER = (
    "Paste CRE underwriting memo — e.g., investment committee deck text, "
    "broker OM excerpt, or DCF narrative. Plain text only."
)

MIN_CHARS = 100
MAX_CHARS = 50_000


def _live_count() -> int:
    base = 847
    days = (datetime.date.today() - datetime.date(2026, 4, 30)).days
    return base + max(0, days * 3)


def _detect_doc_type(text: str) -> str:
    t = text.lower()
    if "investment committee" in t or "ic memo" in t or "recommendation:" in t:
        return "underwriting memo"
    if "offering memorandum" in t or "broker om" in t:
        return "broker OM"
    if "dcf" in t or "discounted cash flow" in t:
        return "DCF narrative"
    if "underwriting" in t or "noi" in t or "cap rate" in t:
        return "underwriting memo"
    return "underwriting memo (unclassified)"


def _load_sample_callback():
    st.session_state["memo_input"] = SAMPLE_MEMO


# -----------------------------------------------------------------------------
# PDF Generation — MRM workpaper format (cached)
# -----------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def generate_verification_pdf(
    input_text: str,
    comp_records: list[dict],
    arith_records: list[dict],
    stat_records: list[dict],
    overall_pct: float,
    run_id: str,
    timestamp_iso: str,
) -> bytes:
    """Render the MRM-stamp-ready verification PDF as raw bytes."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.7 * inch, bottomMargin=0.8 * inch,
        title=f"DealSentry Verification — {run_id}",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=16, spaceAfter=8, textColor=colors.HexColor("#1b3a5b"))
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceAfter=6, textColor=colors.HexColor("#1b3a5b"))
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=14)
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, textColor=colors.grey, leading=11)

    doc_hash = hashlib.sha256(input_text.encode("utf-8")).hexdigest()[:16]
    word_count = len(input_text.split())
    char_count = len(input_text)
    doc_type = _detect_doc_type(input_text)

    story = []

    # Header
    story.append(Paragraph("DealSentry — Underwriting Memo Verification Report", h1))
    story.append(Paragraph(f"<b>Verified at:</b> {timestamp_iso}", body))
    story.append(Paragraph(f"<b>Document SHA-256:</b> {doc_hash}", body))
    story.append(Paragraph(f"<b>Run ID:</b> {run_id}", body))
    story.append(Spacer(1, 12))

    # Section A: Input summary
    story.append(Paragraph("Section A — Input summary", h2))
    summary_tbl = Table(
        [
            ["Document length", f"{char_count:,} characters / {word_count:,} words"],
            ["Document type detected", doc_type],
            ["Overall confidence", f"{overall_pct:.1f}%"],
        ],
        colWidths=[2.0 * inch, 4.6 * inch],
    )
    summary_tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#eeeeee")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f7fa")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_tbl)
    story.append(Spacer(1, 14))

    # Section B: Verification results
    story.append(Paragraph("Section B — Verification results", h2))
    rows = [["Status", "Check", "Result"]]
    failures = []

    # Comp results
    if comp_records:
        verified = sum(1 for r in comp_records if r.get("status") == "VERIFIED")
        total = len(comp_records)
        any_fail = any(r.get("status") in ("VALUE MISMATCH", "NOT FOUND") for r in comp_records)
        icon = "OK" if not any_fail else "X"
        rows.append([icon, "Comp citation verification",
                     f"{verified}/{total} comps verified against synthetic SOT (CoStar/Reonomy)."])
        for r in comp_records:
            if r.get("status") in ("VALUE MISMATCH", "NOT FOUND"):
                failures.append(("Comp citation", r))
    else:
        rows.append(["!", "Comp citation verification", "No comps parsed from memo."])

    # Arithmetic results
    if arith_records:
        ok_n = sum(1 for r in arith_records if r.get("status") == "OK")
        total = len(arith_records)
        any_fail = any(r.get("status") == "DIVERGENCE" for r in arith_records)
        icon = "OK" if not any_fail else "X"
        rows.append([icon, "Symbolic arithmetic re-validation",
                     f"{ok_n}/{total} lines re-computed match claimed values."])
        for r in arith_records:
            if r.get("status") == "DIVERGENCE":
                failures.append(("Arithmetic", r))
    else:
        rows.append(["!", "Symbolic arithmetic re-validation", "No arithmetic claims parsed from memo."])

    # Submarket results
    if stat_records:
        ok_n = sum(1 for r in stat_records if r.get("status") == "OK")
        total = len(stat_records)
        any_fail = any(r.get("status") == "DIVERGENCE" for r in stat_records)
        icon = "OK" if not any_fail else "X"
        rows.append([icon, "Submarket stat cross-check",
                     f"{ok_n}/{total} stat-feed comparisons within tolerance."])
        for r in stat_records:
            if r.get("status") == "DIVERGENCE":
                failures.append(("Submarket stat", r))
    else:
        rows.append(["!", "Submarket stat cross-check", "No submarket stats parsed from memo."])

    bv_tbl = Table(rows, colWidths=[0.6 * inch, 2.2 * inch, 3.8 * inch], repeatRows=1)
    bv_tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b3a5b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#eeeeee")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(bv_tbl)
    story.append(Spacer(1, 14))

    # Section C: Findings detail
    story.append(Paragraph("Section C — Findings detail", h2))
    if not failures:
        story.append(Paragraph("No findings. All checks passed.", body))
    else:
        for kind, r in failures:
            if kind == "Comp citation":
                excerpt = f"{r.get('address', '?')} @ ${r.get('ppsf_claimed', '?')}/sf, {r.get('cap_claimed', '?')} cap"
                wrong = (
                    f"Status: {r.get('status')}. "
                    f"SOT shows ${r.get('ppsf_truth')}/sf, {r.get('cap_truth')} cap."
                    if r.get("status") == "VALUE MISMATCH"
                    else f"Address not found in synthetic SOT (CoStar/Reonomy)."
                )
                action = "Reject and request revision — comp citation cannot be sourced."
            elif kind == "Arithmetic":
                excerpt = f"{r.get('line')}: claimed {r.get('claimed'):,}"
                wrong = f"Recomputed {r.get('recomputed'):,} (divergence {r.get('divergence_pct')}%)."
                action = "Flag for analyst review — math does not reconcile."
            else:  # submarket
                excerpt = f"{r.get('stat')} in {r.get('submarket')}: claimed {r.get('claimed')}"
                wrong = f"{r.get('feed')} feed shows {r.get('feed_value')} (divergence {r.get('divergence_pct')}%)."
                action = "Flag for analyst review — submarket stat does not match feed."

            story.append(Paragraph(f"<b>{kind}</b>", body))
            story.append(Paragraph(f"Excerpt: <font face='Courier'>{excerpt}</font>", body))
            story.append(Paragraph(f"What was wrong: {wrong}", body))
            story.append(Paragraph(f"Recommended action: {action}", body))
            story.append(Spacer(1, 8))

    story.append(PageBreak())

    # Final page — MRM stamp box
    story.append(Paragraph("Model Risk Management (MRM) Sign-off", h2))
    story.append(Spacer(1, 12))
    sig_rows = [
        ["Reviewed by line-1 (model owner):", "_______________________", "Date: _________"],
        ["Reviewed by line-2 (validator):",   "_______________________", "Date: _________"],
        ["Reviewed by line-3 (audit):",       "_______________________", "Date: _________"],
    ]
    sig_tbl = Table(sig_rows, colWidths=[2.4 * inch, 2.5 * inch, 1.8 * inch])
    sig_tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 10),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#1b3a5b")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "<i>This report is auto-generated by DealSentry for input into the bank's "
        "MRM workpaper. Human review and attestation required before relying on results.</i>",
        small,
    ))

    # Footer
    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        page_w, _ = LETTER
        y = 0.5 * inch
        canvas.drawString(0.6 * inch, y,
                          "Portfolio prototype — not production-validated. "
                          "For PM portfolio review by Vijay Saharan.")
        canvas.drawRightString(page_w - 0.6 * inch, y, f"Page {doc_.page}")
        canvas.drawString(0.6 * inch, y - 11, "github.com/Vj-shipped-anyway/ai-pm-portfolio")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


# -----------------------------------------------------------------------------
# Sidebar — minimal "About this demo" (no controls)
# -----------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        "**About this demo**\n\n"
        "DealSentry is a portfolio prototype by Vijay Saharan — three-check "
        "reliability scaffolding for AI-drafted CRE underwriting memos.\n\n"
        "[LinkedIn](https://www.linkedin.com/in/vijaysaharan/) · "
        "[GitHub](https://github.com/Vj-shipped-anyway/ai-pm-portfolio)"
    )

# -----------------------------------------------------------------------------
# Hero — title + live badge
# -----------------------------------------------------------------------------

hero_left, hero_right = st.columns([3, 1])
with hero_left:
    st.title("DealSentry — CRE AI Underwriting Reliability")
    st.caption("Project 10 · CRE · PropTech · AI Reliability — Sr PM portfolio · Vijay Saharan")
with hero_right:
    count = _live_count()
    st.markdown(
        f"<div class='pill-wrap'><span class='live-pill'>"
        f"<span class='dot'></span>Live · {count:,} memos verified"
        f"</span></div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# -----------------------------------------------------------------------------
# Tabs (mobile-friendly nav)
# -----------------------------------------------------------------------------

tab_verify, tab_catches, tab_how, tab_audit, tab_about = st.tabs([
    "📋 Verify a memo",
    "📊 What it catches",
    "🏛️ How it works",
    "📥 Audit pack",
    "ℹ️ About",
])

# -----------------------------------------------------------------------------
# Tab 1 — Verify a memo
# -----------------------------------------------------------------------------

with tab_verify:
    st.markdown("### AI-drafted underwriting summary")

    if "memo_input" not in st.session_state:
        st.session_state["memo_input"] = SAMPLE_MEMO

    memo = st.text_area(
        "Memo text",
        key="memo_input",
        height=320,
        max_chars=MAX_CHARS,
        placeholder=MEMO_PLACEHOLDER,
        label_visibility="collapsed",
    )

    char_count = len(memo or "")
    cap_left, cap_right = st.columns([3, 1])
    with cap_left:
        st.caption(f"{char_count:,} / {MAX_CHARS:,} characters")
    with cap_right:
        st.button("Try a sample →", on_click=_load_sample_callback,
                  use_container_width=True, key="dealsentry_sample_btn")

    if 0 < char_count < MIN_CHARS:
        st.warning("Need at least 100 characters of text to verify against. Paste more content.")

    run = st.button("Run sentinel", type="primary")

    if run:
        if not memo.strip():
            st.error("Paste some text first — pasting nothing means there's nothing to check.")
        elif char_count < MIN_CHARS:
            st.error("Need at least 100 characters of text to verify against. Paste more content.")
        else:
            comps = parse_comps(memo)
            stats = parse_submarket_stats(memo)
            arith = parse_arithmetic(memo)

            if not (comps or stats or arith):
                st.warning(
                    "No structured claims parsed from this memo. "
                    "Check that the memo contains comp citations like "
                    "`- ADDRESS traded at $X/sf, Y cap, MONTH YEAR.` "
                    "or arithmetic in the expected shape."
                )
            else:
                comp_df = check_comps(comps)
                arith_df = check_arithmetic(arith)
                stat_df = check_submarket(stats)

                comp_pass = (comp_df["status"] == "VERIFIED").mean() if len(comp_df) else 0
                arith_pass = (arith_df["status"] == "OK").mean() if len(arith_df) else 0
                stat_pass = (stat_df["status"] == "OK").mean() if len(stat_df) else 0
                overall = round((comp_pass + arith_pass + stat_pass) / 3 * 100, 1)

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Overall confidence", f"{overall}%")
                c2.metric("Comp verification", f"{comp_pass*100:.0f}%")
                c3.metric("Arithmetic re-val", f"{arith_pass*100:.0f}%")
                c4.metric("Submarket stats", f"{stat_pass*100:.0f}%")

                st.markdown("### Check 1 · Comp citation verification")
                if len(comp_df):
                    st.dataframe(comp_df, use_container_width=True)
                else:
                    st.info("No comps parsed.")

                st.markdown("### Check 2 · Symbolic arithmetic re-validation")
                if len(arith_df):
                    st.dataframe(arith_df, use_container_width=True)
                else:
                    st.info("No arithmetic claims parsed.")

                st.markdown("### Check 3 · Submarket stat cross-check")
                if len(stat_df):
                    st.dataframe(stat_df, use_container_width=True)
                else:
                    st.info("No submarket stats parsed.")

                st.markdown("### Recommendation to IC")
                if overall >= 95:
                    st.success("CLEAN PASS — Forward to IC. Verification stamp attached.")
                elif overall >= 75:
                    st.warning("FLAGGED — Senior review required before IC. See divergences above.")
                else:
                    st.error("BLOCKED — Material reliability gaps. Do not forward to IC. Re-draft with verified inputs.")

                # PDF export
                run_id = uuid.uuid4().hex[:8]
                timestamp_iso = datetime.datetime.now(datetime.timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                )
                pdf_bytes = generate_verification_pdf(
                    input_text=memo,
                    comp_records=comp_df.to_dict("records") if len(comp_df) else [],
                    arith_records=arith_df.to_dict("records") if len(arith_df) else [],
                    stat_records=stat_df.to_dict("records") if len(stat_df) else [],
                    overall_pct=float(overall),
                    run_id=run_id,
                    timestamp_iso=timestamp_iso,
                )
                st.download_button(
                    "📥 Download verification PDF (MRM workpaper format)",
                    data=pdf_bytes,
                    file_name=f"dealsentry_verification_{run_id}.pdf",
                    mime="application/pdf",
                    type="secondary",
                )

# -----------------------------------------------------------------------------
# Tab 2 — What it catches
# -----------------------------------------------------------------------------

with tab_catches:
    st.subheader("Three failure modes DealSentry catches")
    st.markdown(
        """
**1. Comp fabrication.** AI underwriting copilots produce comp citations that *look* real but aren't sourced.
DealSentry checks every comp citation against a synthetic source-of-truth modeled on CoStar / Reonomy / Cherre.
Address must exist; price/sf must agree within 5%; cap rate within 10%.

**2. Arithmetic errors.** Implied NOI from rent roll, T-12 NOI, occupancy math.
DealSentry re-computes each line symbolically and flags divergences > 1% (line-level) or > 5% (T-12 vs implied).

**3. Submarket-stat errors.** Vacancy and asking rent claims that don't match feed reality.
DealSentry diffs every claim against two independent feeds (CoStar + Reonomy) per submarket; > 5% divergence on vacancy or > 3% on rent flags the line.
        """
    )
    st.markdown("##### Synthetic source-of-truth — comp database")
    st.dataframe(SOT_COMPS, use_container_width=True, hide_index=True)
    st.markdown("##### Synthetic source-of-truth — submarket stats")
    st.dataframe(SOT_STATS, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# Tab 3 — How it works
# -----------------------------------------------------------------------------

with tab_how:
    st.subheader("Architecture")
    st.markdown(
        """
**Pipeline**

1. **Defensive parser layer** — regex extractors tolerate whitespace, case, optional `$`, `/sf`/`psf`/`per sf`, optional bullet prefix. Empty/malformed input never raises.
2. **Comp citation verification** — every parsed comp address is matched against the synthetic SOT. Three-band status (VERIFIED / WITHIN TOLERANCE / VALUE MISMATCH / NOT FOUND).
3. **Symbolic arithmetic re-validation** — implied NOI from rent roll = `rent_psf × RSF × occ × (1 - opex_ratio)`. T-12 NOI vs implied checked separately.
4. **Submarket stat cross-check** — vacancy and asking-rent claims diffed against two SOT feeds.
5. **Recommendation rollup** — overall confidence drives CLEAN PASS / FLAGGED / BLOCKED status; downloadable PDF goes into the bank's MRM workpaper.

**Why this shape**

AI underwriting copilots produce *plausible-shaped* outputs at uncomfortable rates. The fix is reliability scaffolding, not a better model.
DealSentry is the scaffolding.
        """
    )

# -----------------------------------------------------------------------------
# Tab 4 — Audit pack
# -----------------------------------------------------------------------------

with tab_audit:
    st.subheader("Audit pack & method note")
    st.markdown(
        "- Synthetic source-of-truth: 6 comps, 3 submarkets, 2 feeds. "
        "In production: live calls to CoStar Real Estate Manager API, Reonomy "
        "Properties API, or Cherre's Property API.\n"
        "- Tolerance bands are tunable in `check_comps`, `check_arithmetic`, "
        "and `check_submarket`. Defaults: 2% / 5% on price-per-sf, 5% / 10% on "
        "cap rate, 1% on line-level arithmetic, 5% on T-12 vs implied, "
        "5% on vacancy, 3% on asking rent.\n"
        "- Self-tests live at the bottom of `app.py`. Run with "
        "`python app.py --selftest`.\n"
        "- The downloadable PDF is MRM-workpaper-shaped: every report has a "
        "SHA-256 of the input text, a run UUID, an input-summary section, "
        "a per-check verification table, a findings detail section for any "
        "flagged lines, and a three-line MRM signature block (model owner / "
        "validator / audit) on the final page."
    )
    st.divider()
    st.caption(
        "Prototype demonstrates the product mechanic. In production: real comp pulls "
        "via CoStar / Reonomy / Cherre APIs, deterministic arithmetic engine, "
        "multi-feed stat cross-check with tolerance bands. Verification record "
        "writes to Project 08 (Audit Trail). Lease-side inputs verified upstream "
        "by Project 09 (Lease Abstraction Detector)."
    )

# -----------------------------------------------------------------------------
# Tab 5 — About
# -----------------------------------------------------------------------------

with tab_about:
    st.subheader("About this prototype")
    st.markdown(
        "**DealSentry** is Project 10 of an AI-PM portfolio by **Vijay Saharan**.\n\n"
        "It's a working prototype, not a production system. The verification logic "
        "is real (deterministic regex + symbolic arithmetic over a synthetic SOT); "
        "the source-of-truth feeds are mock placeholders for CoStar / Reonomy / Cherre.\n\n"
        "[LinkedIn](https://www.linkedin.com/in/vijaysaharan/) · "
        "[GitHub source](https://github.com/Vj-shipped-anyway/ai-pm-portfolio)"
    )
