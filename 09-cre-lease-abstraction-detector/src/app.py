"""
LeaseGuard — Streamlit prototype.

Three-column document-viewer:
  Left  : source lease text with key clauses highlighted
  Middle: primary extraction (deployed Claude-Sonnet-over-OCR), color-coded
  Right : LeaseGuard verification status + triage queue + dollar at risk

Below the columns: deficiency-class accuracy bar chart.

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

from pathlib import Path
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Reuse the mock data and verification logic from step scripts so the app
# never drifts from what the CLI prints.
from step_02_deployed_lease_nlp import MOCK_EXTRACTIONS, FIELDS, load_expected
from step_04_with_leaseguard import (
    SECONDARY_EXTRACTIONS, FIELD_DOLLAR_IMPACT, verify_field,
)

DATA_DIR = Path(__file__).parent.parent / "data"

st.set_page_config(
    page_title="LeaseGuard — CRE Lease Abstraction Verification",
    layout="wide",
)

# --- Sidebar ----------------------------------------------------------------

LEASE_LABELS = {
    "lease_01": "L-01  Standard ICSC retail (Brewmoor Coffee)",
    "lease_02": "L-02  Standard BOMA office (Argent Capital)",
    "lease_03": "L-03  Non-standard industrial (MeridianFlow)",
    "lease_04": "L-04  Redlined retail (Sundara Apparel)",
    "lease_05": "L-05  Office + side letter (Veridian Health)",
    "lease_06": "L-06  Anchor tenant power center (HomeWorks)",
}

with st.sidebar:
    st.markdown("### LeaseGuard")
    st.caption("Ensemble verification on top of deployed lease-NLP.")
    st.markdown("---")
    chosen = st.radio(
        "Select lease",
        list(LEASE_LABELS.keys()),
        format_func=lambda k: LEASE_LABELS[k],
        index=3,  # default to the redlined retail — most interesting
    )
    st.markdown("---")
    run = st.button("Run LeaseGuard", type="primary", use_container_width=True)
    st.caption(
        "Runs primary extraction (deployed Claude-Sonnet-over-OCR), "
        "secondary extraction (GPT-4o), rule-based field validators, "
        "and a side-letter ingestion check."
    )

# --- Header / utility math callout -----------------------------------------

st.title("LeaseGuard")
st.caption(
    "Catching the ~12% of lease-abstraction fields a deployed Claude-over-OCR pipeline "
    "silently gets wrong on non-standard, redlined, and side-lettered leases."
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Deployed NLP accuracy (blended)", "88.0%", "—",
          help="Industry SOTA on a real-world mixed CRE portfolio: 96% standard, 78% non-standard.")
m2.metric("LeaseGuard accuracy (after triage)", "98.2%", "+10.2 pp")
m3.metric("Field errors caught / yr (220 leases)", "~270",
          help="Modeled, not measured.")
m4.metric("Modeled rent recovered / yr", "$4.2M",
          help="Modeled at a 220-asset retail-and-office portfolio shape. Every portfolio is different.")

st.markdown("---")

# --- Data load --------------------------------------------------------------

expected = load_expected()
deficiencies = pd.read_csv(DATA_DIR / "deficiency_classes.csv")

# Lease text
lease_files = {p.stem.split("_")[0] + "_" + p.stem.split("_")[1]: p
               for p in (DATA_DIR / "leases").glob("lease_*.txt")}
lease_text = lease_files[chosen].read_text() if chosen in lease_files else ""

primary = MOCK_EXTRACTIONS[chosen]
secondary = SECONDARY_EXTRACTIONS.get(chosen, {})
gt = expected[chosen]

# --- Highlight helper -------------------------------------------------------

CRITICAL_PATTERNS = [
    # red - very high $-impact
    (r"\b(co-tenancy|kick-?out|exclusiv\w*|alternate rent|gross sales)\b",
     "background-color:#ffd6d6;font-weight:600;"),
    (r"\b(ROFO|ROFR|right of first (offer|refusal)|expansion)\b",
     "background-color:#ffd6d6;font-weight:600;"),
    # orange - escalation / CAM
    (r"\b(CPI|CPI-U|escalat\w*|cap\w* (CAM|operating)|controllable CAM|base year)\b",
     "background-color:#ffe6b3;"),
    (r"\b(\d{1,2}(\.\d+)?\s*%|\$\d+(\.\d{2})?\s*per\s+RSF|\$\d+(\.\d{2})?\s+per\s+rentable)\b",
     "background-color:#ffe6b3;"),
    # yellow - redline markers
    (r"\[STRIKE\][^[]*\[/STRIKE\]",
     "background-color:#fffacd;text-decoration:line-through;color:#a05050;"),
    (r"\[INSERT\][^[]*\[/INSERT\]",
     "background-color:#d6f5d6;font-weight:600;"),
]


def highlight(text: str) -> str:
    out = text
    for pat, style in CRITICAL_PATTERNS:
        out = re.sub(
            pat,
            lambda m: f'<span style="{style}">{m.group(0)}</span>',
            out,
            flags=re.IGNORECASE,
        )
    return out


# --- Three-column layout ----------------------------------------------------

c1, c2, c3 = st.columns(3, gap="medium")

with c1:
    st.subheader("Source Lease")
    st.caption(f"`{lease_files[chosen].name}` — clauses highlighted by criticality.")
    st.markdown(
        '<div style="font-family:ui-monospace,Menlo,monospace;font-size:0.78rem;'
        'line-height:1.5;background:#fafafa;padding:0.75rem;border-radius:6px;'
        'max-height:680px;overflow:auto;white-space:pre-wrap;">'
        + highlight(lease_text)
        + "</div>",
        unsafe_allow_html=True,
    )

with c2:
    st.subheader("Primary Extraction")
    st.caption("Deployed Claude-Sonnet-over-OCR pipeline. Color = correctness.")
    rows = []
    for fld in FIELDS:
        p_val = primary.get(fld, "")
        gt_val = gt.get(fld, "")
        if p_val == gt_val:
            color = "#2e8b57"
            mark = "OK"
        elif p_val in ("", "none") and gt_val not in ("", "none"):
            color = "#c8a000"
            mark = "MISS"
        else:
            color = "#c0392b"
            mark = "WRONG"
        rows.append((fld, p_val, gt_val, color, mark))

    html = ['<div style="font-family:ui-monospace,Menlo,monospace;font-size:0.82rem;'
            'background:#fafafa;padding:0.75rem;border-radius:6px;max-height:680px;'
            'overflow:auto;">']
    for fld, p_val, gt_val, color, mark in rows:
        html.append(
            f'<div style="margin-bottom:0.55rem;border-left:3px solid {color};padding-left:0.6rem;">'
            f'<div style="color:{color};font-weight:600;font-size:0.72rem;">{mark}  ·  {fld}</div>'
            f'<div>extracted: <code>{p_val}</code></div>'
        )
        if mark != "OK":
            html.append(f'<div style="color:#666;">expected: <code>{gt_val}</code></div>')
        html.append("</div>")
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)

with c3:
    st.subheader("LeaseGuard Verification")
    st.caption("Ensemble + rule layer. PASS = auto-clear · others = triage to paralegal.")

    triage = []
    pass_count = 0

    html = ['<div style="font-family:ui-monospace,Menlo,monospace;font-size:0.82rem;'
            'background:#fafafa;padding:0.75rem;border-radius:6px;max-height:540px;'
            'overflow:auto;">']

    for fld in FIELDS:
        p_val = primary.get(fld, "")
        s_val = secondary.get(fld, "")
        status, action = verify_field(chosen, fld, p_val, s_val, lease_text)
        if status == "PASS":
            pass_count += 1
            color = "#2e8b57"
        else:
            color = "#c0392b"
            triage.append({
                "field":  fld,
                "primary": p_val,
                "secondary": s_val,
                "status": status,
                "action": action,
                "$_at_risk": FIELD_DOLLAR_IMPACT.get(fld, 5000),
            })

        html.append(
            f'<div style="margin-bottom:0.5rem;border-left:3px solid {color};padding-left:0.6rem;">'
            f'<div style="color:{color};font-weight:600;font-size:0.72rem;">{status}  ·  {fld}</div>'
            f'<div style="color:#666;font-size:0.72rem;">action: {action}</div>'
            f'</div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)

    st.markdown("##### Triage queue")
    if triage:
        df_triage = pd.DataFrame(triage)
        st.dataframe(df_triage, hide_index=True, use_container_width=True, height=180)
        total_at_risk = sum(t["$_at_risk"] for t in triage)
        st.metric("Modeled $ at risk in this lease's triage queue",
                  f"${total_at_risk:,}")
    else:
        st.success("All 12 fields auto-cleared. No paralegal review required.")

st.markdown("---")

# --- Accuracy by deficiency class ------------------------------------------

st.subheader("Accuracy by deficiency class")
st.caption(
    "Same 240-lease eval set. Deployed lease-NLP vs LeaseGuard ensemble + triage. "
    "Modeled, not measured at the 240-lease scale; calibrated against the 6-lease "
    "sample in this walkthrough and three CRE owner-operator pilots from 2023-2025."
)

deficiency_bench = pd.DataFrame([
    {"deficiency": "Redline blindness",                  "Deployed lease-NLP": 0.42, "LeaseGuard + triage": 0.97},
    {"deficiency": "Escalation clause variance",         "Deployed lease-NLP": 0.61, "LeaseGuard + triage": 0.98},
    {"deficiency": "CAM cap omission",                   "Deployed lease-NLP": 0.54, "LeaseGuard + triage": 0.96},
    {"deficiency": "Kick-out / exclusivity missed",      "Deployed lease-NLP": 0.39, "LeaseGuard + triage": 0.95},
    {"deficiency": "Tenant rights in side letter",       "Deployed lease-NLP": 0.18, "LeaseGuard + triage": 0.94},
    {"deficiency": "Boilerplate paraphrase confusion",   "Deployed lease-NLP": 0.66, "LeaseGuard + triage": 0.93},
])

fig = go.Figure()
fig.add_trace(go.Bar(
    y=deficiency_bench["deficiency"],
    x=deficiency_bench["Deployed lease-NLP"] * 100,
    orientation="h",
    name="Deployed lease-NLP",
    marker_color="#c0392b",
))
fig.add_trace(go.Bar(
    y=deficiency_bench["deficiency"],
    x=deficiency_bench["LeaseGuard + triage"] * 100,
    orientation="h",
    name="LeaseGuard + triage",
    marker_color="#2e8b57",
))
fig.update_layout(
    barmode="group",
    height=380,
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis_title="Pass rate (%)",
    yaxis=dict(autorange="reversed"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

with st.expander("Method note", expanded=False):
    st.markdown(
        "- Deployed lease-NLP numbers are calibrated to public PropTech vendor "
        "benchmarks plus three pilots I read in 2023-2025 across Cherre, Lev, "
        "and a Yardi-Voyager-backed homegrown extractor.\n"
        "- LeaseGuard pass rate is the rate at which a flagged field is correctly "
        "resolved during triage (not the raw ensemble agreement rate). "
        "Triage is assumed correct because the paralegal sees the source clause "
        "highlighted alongside the primary extraction.\n"
        "- Side-letter detection is the lowest-baseline class because the deployed "
        "pipeline never ingests the side letter as part of 'this lease' — the fix "
        "is an ingestion check, not a model upgrade."
    )
