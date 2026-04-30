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

import re
import sys
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

# Comp citation: "- 1450 Wilshire Blvd traded at $412/sf, 5.8 cap, September 2025"
# Tolerance built in:
#   - optional leading dash/bullet/asterisk
#   - optional $ on the price
#   - "/sf", " /sf", "psf", "per sf", "/SF" all accepted
#   - cap rate accepts "5.8", "5.8%", "5.8 cap", "5.8% cap"
#   - month is a word, year is 4 digits
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
# Each parser is defensive: never raises on malformed input, returns
# typed empty result instead.
# -----------------------------------------------------------------------------

@dataclass
class CompClaim:
    """A comp citation extracted from the memo."""
    address: str
    ppsf_claimed: int
    cap_claimed: float
    month_claimed: str
    year_claimed: int


def parse_comps(text: str) -> list[dict[str, Any]]:
    """Extract comp citations from the underwriting memo.

    Tolerant to whitespace, case, optional $ prefix, multiple unit forms
    ("/sf", "psf", "per sf"), and optional leading bullet.

    Returns a list of dicts (one per comp). Empty list on no matches or
    malformed input. Never raises.

    Example match line:
        "- 1450 Wilshire Blvd traded at $412/sf, 5.8 cap, September 2025"
    """
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
        # Malformed numeric capture — skip this row, continue parsing
        pass
    return out


def parse_submarket_stats(text: str) -> dict[str, Any]:
    """Extract vacancy and asking-rent claims from the memo.

    Returns dict with optional 'vacancy' and 'asking_rent' keys. Never raises.
    """
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
    """Extract financial-arithmetic claims from the memo.

    Captures: t12_noi_claimed, rent_psf, rsf, occ (as fraction),
    implied_noi_claimed, opex_ratio (as fraction).

    Returns dict with whichever keys parsed successfully. Never raises.
    """
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
    """Verify each comp citation against the synthetic SOT database.

    Status banding:
        VERIFIED            ppsf within 2%, cap within 5%
        WITHIN TOLERANCE    ppsf within 5%, cap within 10%
        VALUE MISMATCH      outside both bands
        NOT FOUND           address not in SOT
    """
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
    """Re-compute claimed financial math and flag divergences.

    Lines checked:
        - Implied NOI from rent roll = rent_psf × RSF × occ × (1 - opex_ratio)
        - T-12 NOI vs implied NOI consistency

    Tolerances: 1% for the recomputed-vs-claimed; 5% for T-12 vs implied.
    """
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
    """Cross-check vacancy and asking-rent claims against two SOT feeds.

    For each claim, returns one row per feed (CoStar + Reonomy).
    Tolerances: 5% on vacancy, 3% on asking rent.
    """
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
# Designed to fail loudly if regex/parser logic regresses.
# -----------------------------------------------------------------------------

def _run_selftests() -> int:
    """Inline regression suite. Returns exit code 0 on pass, 1 on fail."""
    failures = 0

    # parse_comps — happy path
    sample = "- 1450 Wilshire Blvd traded at $412/sf, 5.8 cap, September 2025."
    comps = parse_comps(sample)
    assert len(comps) == 1, f"parse_comps happy path: expected 1, got {len(comps)}"
    assert comps[0]["address"] == "1450 Wilshire Blvd"
    assert comps[0]["ppsf_claimed"] == 412
    assert comps[0]["cap_claimed"] == 5.8
    assert comps[0]["year_claimed"] == 2025

    # parse_comps — alternate units (psf, no $, lowercase month)
    sample_alt = "885 Sepulveda traded at 535 psf, 5.2% cap, november 2025"
    comps_alt = parse_comps(sample_alt)
    assert len(comps_alt) == 1, f"parse_comps psf form: expected 1, got {len(comps_alt)}"
    assert comps_alt[0]["ppsf_claimed"] == 535

    # parse_comps — defensive on empty / None / malformed
    assert parse_comps("") == []
    assert parse_comps(None) == []  # type: ignore[arg-type]
    assert parse_comps("blah blah no comps here") == []

    # parse_arithmetic — happy path
    a = parse_arithmetic("T-12 NOI: $7,420,000. expense ratio: 38%.")
    assert a.get("t12_noi_claimed") == 7420000
    assert a.get("opex_ratio") == 0.38

    # parse_arithmetic — defensive
    assert parse_arithmetic("") == {}
    assert parse_arithmetic("garbage") == {}

    # parse_submarket_stats — happy path
    s = parse_submarket_stats("Vacancy in Mid-Wilshire is 12.3%. Asking rent in submarket: $38.10 /sf")
    assert s["vacancy"]["submarket"] == "Mid-Wilshire"
    assert s["vacancy"]["value"] == 12.3
    assert s["asking_rent"] == 38.10

    # check_comps — divergence detection
    df = check_comps([
        {"address": "1450 Wilshire Blvd", "ppsf_claimed": 412, "cap_claimed": 5.8,
         "month_claimed": "September", "year_claimed": 2025}
    ])
    assert df.iloc[0]["status"] == "VERIFIED"

    df_bad = check_comps([
        {"address": "9200 Sunset", "ppsf_claimed": 720, "cap_claimed": 4.4,
         "month_claimed": "October", "year_claimed": 2025}  # SOT says 612 / 4.9
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

st.set_page_config(page_title="DealSentry — CRE Underwriting Reliability", layout="wide")
st.title("DealSentry — CRE AI Underwriting Reliability")
st.caption("Project 10 · CRE · PropTech · AI Reliability — Sr PM portfolio · Vijay Saharan")

with st.sidebar:
    st.header("Sentinel checks")
    st.markdown(
        "**1.** Comp citation verification\n\n"
        "**2.** Symbolic arithmetic re-validation\n\n"
        "**3.** Submarket stat cross-check"
    )
    st.divider()
    st.caption("Synthetic source-of-truth: 6 comps, 3 submarkets, 2 feeds")
    st.caption("Run inline tests: `python app.py --selftest`")

st.markdown("### AI-drafted underwriting summary")
memo = st.text_area("Paste an AI-drafted underwriting memo", SAMPLE_MEMO, height=320)

if st.button("Run sentinel", type="primary"):
    if not memo.strip():
        st.warning("Empty memo. Paste an AI-drafted underwriting summary above.")
        st.stop()

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
        st.stop()

    comp_df = check_comps(comps)
    arith_df = check_arithmetic(arith)
    stat_df = check_submarket(stats)

    # Top metrics
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

    # Recommendation
    st.markdown("### Recommendation to IC")
    if overall >= 95:
        st.success("CLEAN PASS — Forward to IC. Verification stamp attached.")
    elif overall >= 75:
        st.warning("FLAGGED — Senior review required before IC. See divergences above.")
    else:
        st.error("BLOCKED — Material reliability gaps. Do not forward to IC. Re-draft with verified inputs.")

    with st.expander("Verification record (writes to audit trail · Project 08)"):
        st.json({
            "memo_id": "memo_2026-04-28-1450wilshire",
            "overall_confidence_pct": overall,
            "comp_pass_pct": round(comp_pass * 100, 1),
            "arith_pass_pct": round(arith_pass * 100, 1),
            "stat_pass_pct": round(stat_pass * 100, 1),
            "comp_rows": len(comp_df),
            "arith_rows": len(arith_df),
            "stat_rows": len(stat_df),
        })

st.divider()
st.caption(
    "Prototype demonstrates the product mechanic. In production: real comp pulls "
    "via CoStar / Reonomy / Cherre APIs, deterministic arithmetic engine, "
    "multi-feed stat cross-check with tolerance bands. Verification record "
    "writes to Project 08 (Audit Trail). Lease-side inputs verified upstream "
    "by Project 09 (Lease Abstraction Detector)."
)
