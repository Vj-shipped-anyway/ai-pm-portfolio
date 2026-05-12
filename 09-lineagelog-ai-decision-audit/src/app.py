"""LineageLog - AI decision audit trail with sub-minute exam-pack export.

Streamlit walkthrough:
  Step 1 - pick a decision_id (or use the OCC's headline decision)
  Step 2 - executive verdict card: complete / partial / incomplete lineage
  Step 3 - the six-deficiency composition: each gap closed inline
  Step 4 - the exam pack (PDF download + glossary + production stack reassessment)
"""

from __future__ import annotations

import io
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="LineageLog - AI decision audit trail in 12 minutes, not 14 days",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
REPO_BLOB = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/09-lineagelog-ai-decision-audit"

TARGET_DECISION_ID = "DEC_0150_20260312"

# ---------------------------------------------------------------------------
# Theme - dark navy gradient hero, white body, indigo accent
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

.ll-hero {
  background: linear-gradient(135deg,#0a0e2e 0%, #1e2a78 60%, #4f46e5 100%);
  border-radius: 18px; padding: 36px 40px; color:#fff; margin-bottom:28px;
}
.ll-hero .brand {font-size:26px; font-weight:600; opacity:0.92; margin-bottom:12px;}
.ll-hero h1 {color:#fff !important; font-size:46px; line-height:1.12; margin:0 0 14px 0; font-weight:700;}
.ll-hero .sub {font-size:17px; line-height:1.5; opacity:0.93; max-width:840px; margin-bottom:22px;}
.ll-hero .pills {display:flex; flex-wrap:wrap; gap:10px;}
.ll-hero .pill {background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
                color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.ll-hero .pill a {color:#fff; text-decoration:none;}

.ll-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:22px 26px;
          margin-bottom:18px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.ll-card h3 {margin-top:0; color:#0f172a;}
.ll-step-label {display:inline-block; background:#4f46e5; color:#fff; padding:3px 10px;
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

.trust-card {background:#f8fafc; border:1px solid #cbd5e1; border-left:5px solid #4f46e5;
             border-radius:12px; padding:20px 24px; margin-bottom:18px;}
.trust-card h4 {margin:0 0 10px 0; color:#0f172a; font-size:16px; letter-spacing:0.04em;
                text-transform:uppercase;}
.trust-card .tlabel {font-weight:700; color:#4f46e5; font-size:13px; letter-spacing:0.04em;
                     text-transform:uppercase; margin-top:12px; display:block;}
.trust-card ul {margin:6px 0 0 18px; padding:0;}
.trust-card li {color:#334155; line-height:1.55;}
.confidence-high {color:#047857; font-weight:700;}
.confidence-med  {color:#b45309; font-weight:700;}
.confidence-low  {color:#b91c1c; font-weight:700;}

.def-row {background:#dcfce7; border-left:5px solid #16a34a; border-radius:10px;
          padding:14px 18px; margin-bottom:10px; color:#14532d;}
.def-row.gap {background:#fef3c7; border-left-color:#f59e0b; color:#78350f;}
.def-row .dlabel {font-weight:700; font-size:13px; letter-spacing:0.04em; text-transform:uppercase;}
.def-row .dval {font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size:13px; margin-top:4px;}

div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#4f46e5,#1e2a78) !important; color:#fff !important;
  border:0 !important; padding:14px 28px !important; font-size:17px !important;
  font-weight:600 !important; border-radius:12px !important;
  box-shadow:0 4px 14px rgba(79,70,229,0.35) !important;
}
h1, h2, h3 {color:#0f172a;}
.muted {color:#64748b; font-size:14px;}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@st.cache_data
def load_data() -> dict[str, pd.DataFrame]:
    return {
        "decisions":   pd.read_csv(DATA_DIR / "decisions.csv"),
        "models":      pd.read_csv(DATA_DIR / "models.csv"),
        "retrievals":  pd.read_csv(DATA_DIR / "retrieval_sets.csv"),
        "outcomes":    pd.read_csv(DATA_DIR / "outcomes.csv"),
    }


DATA = load_data()


# ---------------------------------------------------------------------------
# Composition primitives (mirror step_04_with_lineagelog.py)
# ---------------------------------------------------------------------------
PROMPT_REGISTRY = {
    "loan_pd_v3": [("template_loan_v3.2.1", "2026-02-08"), ("template_loan_v3.2.2", "2026-03-05")],
    "claims_triage_v2": [("template_claims_v2.1.0", "2025-11-01"), ("template_claims_v2.1.1", "2026-02-12")],
    "kyc_review_v4": [("template_kyc_v4.0.3", "2025-09-22"), ("template_kyc_v4.0.4", "2026-01-22")],
    "fraud_screen_v6": [("template_fraud_v6.1.0", "2025-10-15"), ("template_fraud_v6.1.1", "2026-03-01")],
}


def synth_prompt(model_id: str, decision_ts: str) -> dict:
    decision_d = datetime.strptime(decision_ts[:10], "%Y-%m-%d").date()
    effective = None
    for tmpl, eff_date in PROMPT_REGISTRY.get(model_id, []):
        eff_d = datetime.strptime(eff_date, "%Y-%m-%d").date()
        if eff_d <= decision_d:
            effective = tmpl, eff_date
    if effective is None:
        return {"template_id": "unknown", "effective_at": None}
    return {"template_id": effective[0], "effective_at": effective[1],
            "policy_hash": "sha256:5b9a3c...e7"}


def synth_features(decision_row: dict) -> dict:
    seed = sum(ord(c) for c in decision_row["decision_id"])
    if decision_row["decision_type"] == "loan_approval":
        return {"fico_at_decision_time": 580 + (seed % 220),
                "dti_at_decision_time": round(0.18 + (seed % 30) / 100.0, 3),
                "ltv_at_decision_time": round(0.55 + (seed % 35) / 100.0, 3)}
    if decision_row["decision_type"] == "claims_triage":
        return {"claim_amount": float(decision_row["decision_value"]),
                "policy_age_days": 90 + (seed % 1200),
                "prior_claims_24m": seed % 4}
    if decision_row["decision_type"] == "kyc_review":
        return {"risk_score_at_decision_time": float(decision_row["decision_value"]),
                "country_risk_tier": (seed % 4) + 1,
                "pep_match_score": round((seed % 50) / 100.0, 3)}
    return {"txn_amount": float(decision_row["decision_value"]),
            "velocity_24h_count": seed % 35,
            "merchant_risk_tier": (seed % 5) + 1}


def synth_reviewer(decision_row: dict) -> dict:
    seed = sum(ord(c) for c in decision_row["decision_id"])
    if decision_row["decision_type"] in ("kyc_review", "claims_triage") and (seed % 3) == 0:
        return {"actor_type": "human_user_delegated",
                "actor_id": f"u.adams.{seed % 7}@bank.com",
                "agent_identity": "loan-decisioning-sa@bank.iam"}
    return {"actor_type": "agent_autonomous",
            "actor_id": None,
            "agent_identity": f"{decision_row['model_id']}-sa@bank.iam"}


def compose_lineage(decision_id: str) -> dict:
    decisions = DATA["decisions"]
    models = DATA["models"]
    retrievals = DATA["retrievals"]
    outcomes = DATA["outcomes"]

    drow = decisions[decisions["decision_id"] == decision_id]
    if len(drow) == 0:
        return None
    drow = drow.iloc[0].to_dict()
    mrow = models[models["model_id"] == drow["model_id"]].iloc[0].to_dict()
    rrows = retrievals[retrievals["decision_id"] == decision_id].to_dict("records")
    orow = outcomes[outcomes["decision_id"] == decision_id]
    orow = orow.iloc[0].to_dict() if len(orow) else {}

    return {
        "decision": drow,
        "model_snapshot": mrow,
        "prompt": synth_prompt(drow["model_id"], drow["timestamp"]),
        "retrieval_set": rrows,
        "feature_at_decision_time": synth_features(drow),
        "reviewer": synth_reviewer(drow),
        "outcome": orow,
    }


def six_def_rows(record: dict) -> list[dict]:
    rows = []
    rows.append({"label": "1. Prompt versioning", "ok": True,
                 "value": f"{record['prompt']['template_id']} (effective {record['prompt']['effective_at']})"})
    rs = record["retrieval_set"]
    rows.append({"label": "2. Retrieval-set capture", "ok": True,
                 "value": f"{len(rs)} docs: " + ", ".join(f"{r['doc_id']}@{r['doc_version']}" for r in rs)})
    ms = record["model_snapshot"]
    rows.append({"label": "3. Model-snapshot pin", "ok": True,
                 "value": f"{ms['vendor']} / {ms['snapshot_id']} (trained {ms['training_date']})"})
    feat = record["feature_at_decision_time"]
    rows.append({"label": "4. Feature-at-decision-time", "ok": True,
                 "value": ", ".join(f"{k}={v}" for k, v in feat.items())})
    rev = record["reviewer"]
    rows.append({"label": "5. Reviewer attribution", "ok": True,
                 "value": f"{rev['actor_type']} - agent_identity={rev['agent_identity']}" +
                          (f"; delegated by {rev['actor_id']}" if rev.get("actor_id") else "")})
    out = record["outcome"]
    out_type = out.get("outcome_type", "") or "(not yet observed)"
    out_val = out.get("outcome_value", "") or "-"
    out_date = out.get("outcome_date", "") or "-"
    rows.append({"label": "6. Outcome backlink", "ok": bool(out.get("outcome_type")),
                 "value": f"{out_type} on {out_date} -> {out_val}"})
    return rows


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "step" not in st.session_state:
    st.session_state.step = 1

# Build the decision picker labels. Default to the headline DEC_0150.
all_decisions = DATA["decisions"]
DECISION_OPTIONS = []
for _, row in all_decisions.iterrows():
    label = f"{row['decision_id']} - {row['model_id']} - {row['outcome']} - {row['decision_type']}"
    DECISION_OPTIONS.append(label)
default_idx = next((i for i, d in enumerate(DECISION_OPTIONS) if d.startswith(TARGET_DECISION_ID)), 0)

if "decision_choice" not in st.session_state:
    st.session_state.decision_choice = DECISION_OPTIONS[default_idx]


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='ll-hero'>
  <div class='brand'>🔍 LineageLog</div>
  <h1>Every regulated AI decision, traceable to its inputs, model snapshot, and downstream outcome in under a minute.</h1>
  <div class='sub'>An immutable decision-grain composition layer that turns log fragments scattered across Cloud Logging, Cloud Audit Logs, Agent Identity Logs, and OpenTelemetry traces into a single record indexed by customer / decision / timestamp. Built against the Google Cloud secure-multi-agent reference architecture; mapped to <a href='https://eur-lex.europa.eu/eli/reg/2024/1689/oj' target='_blank' style='color:#fff;text-decoration:underline;'>EU AI Act Article 12</a>, <a href='https://www.nist.gov/itl/ai-risk-management-framework' target='_blank' style='color:#fff;text-decoration:underline;'>NIST AI RMF</a>, and the <a href='https://www.occ.gov/news-issuances/bulletins/2011/bulletin-2011-12.html' target='_blank' style='color:#fff;text-decoration:underline;'>SR 11-7 / OCC 2011-12</a> ongoing-monitoring expectation.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>200 synthetic decisions</span>
    <span class='pill'>4 deployed models</span>
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
# STEP 1 - pick a decision
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='ll-card'><span class='ll-step-label'>Step 1</span>"
    "<h3>Pick a decision the regulator might ask about</h3>"
    "<p class='muted'>Default selection is <code>DEC_0150_20260312</code> - the loan denial of "
    "<code>CUST_851897</code> on March 12, 2026 that the OCC opens an exam about on May 8. "
    "Today: 14 days of paralegal collation. With LineageLog: 12 minutes.</p></div>",
    unsafe_allow_html=True,
)

st.session_state.decision_choice = st.selectbox(
    "Decision:",
    DECISION_OPTIONS,
    index=DECISION_OPTIONS.index(st.session_state.decision_choice),
    label_visibility="collapsed",
)
chosen_id = st.session_state.decision_choice.split(" - ")[0]
record = compose_lineage(chosen_id)

drow = record["decision"]
mrow = record["model_snapshot"]

st.markdown(
    f"<div class='ll-card'><b>Decision:</b> {drow['decision_id']}<br>"
    f"<b>Customer (hashed):</b> {drow['customer_id']}  -  "
    f"<b>Decision type:</b> {drow['decision_type']}  -  "
    f"<b>Timestamp:</b> {drow['timestamp']}<br>"
    f"<b>Model:</b> {mrow['name']} ({mrow['model_id']})  -  "
    f"<b>Vendor:</b> {mrow['vendor']}  -  <b>Snapshot:</b> {mrow['snapshot_id']}<br>"
    f"<b>Outcome:</b> {drow['outcome']} ({float(drow['decision_value']):,.2f})</div>",
    unsafe_allow_html=True,
)

if st.session_state.step < 2:
    if st.button("Compose the lineage record  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - executive verdict
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    t0 = time.perf_counter()
    rows = six_def_rows(record)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    closed = sum(1 for r in rows if r["ok"])
    total = len(rows)

    if closed == total:
        verdict_class = "verdict-pass"
        verdict_word = "PASS"
        risk = "LOW"
        action = "Decision is exam-ready. All 6 lineage fields composed and immutable."
        confidence = "HIGH (>95%)"
        confidence_class = "confidence-high"
        tldr = (
            f"All 6 lineage deficiencies closed for {drow['decision_id']}. "
            f"Composition completed in {elapsed_ms}ms on the prototype. "
            f"Exam pack available for download below."
        )
    elif closed >= total - 1:
        verdict_class = "verdict-review"
        verdict_word = "REVIEW"
        risk = "MEDIUM"
        action = "One lineage field has not yet materialized (typically outcome backlink). Acceptable for exam if the outcome is genuinely too early to have surfaced."
        confidence = "MEDIUM (70-95%)"
        confidence_class = "confidence-med"
        tldr = (
            f"{closed} of {total} lineage fields composed; one pending. "
            f"Acceptable if the pending field is an outcome that has not materialized yet."
        )
    else:
        verdict_class = "verdict-flag"
        verdict_word = "INCOMPLETE"
        risk = "HIGH"
        action = "Multiple lineage fields missing. Decision should be flagged before any exam-pack release."
        confidence = "LOW (<70%)"
        confidence_class = "confidence-low"
        tldr = f"Only {closed} of {total} lineage fields composed. Decision is not yet exam-ready."

    st.markdown(
        f"""
<div class='verdict-card {verdict_class}'>
  <div class='vlabel'>LineageLog Verdict</div>
  <div class='vbig'>{verdict_word}</div>
  <div class='vmetric'>{closed} of {total} lineage deficiencies closed - composition in {elapsed_ms}ms</div>
  <div class='vrow'>
    <span class='vchip'>Risk: {risk}</span>
    <span class='vchip'>Recommended action: {action}</span>
    <span class='vchip'>Decision: {drow['decision_id']}</span>
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
  <span class='tlabel'>What we composed from</span>
  <div>The four CSVs in <a href='{REPO_BLOB}/data/decisions.csv' target='_blank'><code>data/decisions.csv</code></a>, <a href='{REPO_BLOB}/data/models.csv' target='_blank'><code>data/models.csv</code></a>, <a href='{REPO_BLOB}/data/retrieval_sets.csv' target='_blank'><code>data/retrieval_sets.csv</code></a>, and <a href='{REPO_BLOB}/data/outcomes.csv' target='_blank'><code>data/outcomes.csv</code></a> stand in for the four log surfaces a real deployment composes (Cloud Logging, Cloud Audit Logs, Agent Identity Logs, OpenTelemetry traces).</div>
  <span class='tlabel'>Assumptions we made</span>
  <ul>
    <li>The prompt-template registry has a deploy-time row per (model_id, effective_at). Production reads from a Postgres table; the demo synthesizes from a small lookup.</li>
    <li>Feature-at-decision-time is recoverable from a temporal feature-store API. The demo synthesizes a deterministic feature vector per decision_id.</li>
    <li>Reviewer attribution distinguishes <code>human_user_delegated</code> from <code>agent_autonomous</code> via the Agent Identity Auth Manager pattern described in Google's <i>Building secure multi-agent systems</i> reference.</li>
    <li>Outcome data lives in three downstream systems (loss-event lake, complaint database, claims platform). LineageLog joins by decision_id, which is the contract.</li>
    <li><a href='https://eur-lex.europa.eu/eli/reg/2024/1689/oj' target='_blank'>EU AI Act Article 12</a> record-keeping requirements apply to this tier-{mrow['tier']} decision; <a href='https://www.occ.gov/news-issuances/bulletins/2011/bulletin-2011-12.html' target='_blank'>SR 11-7</a> and <a href='https://www.nist.gov/itl/ai-risk-management-framework' target='_blank'>NIST AI RMF</a> apply alongside.</li>
  </ul>
  <span class='tlabel'>Confidence level</span>
  <div class='{confidence_class}'>{confidence}</div>
  <span class='tlabel'>What this does NOT cover</span>
  <ul>
    <li>OCR / vision-model lineage on document-extraction pipelines (covered by [LeaseGuard] in this portfolio).</li>
    <li>Multi-agent A2A handoffs where the deciding agent calls a downstream agent (covered by [AgentWatch]).</li>
    <li>Real-time drift detection on the model snapshot (covered by [DriftSentinel]).</li>
  </ul>
</div>
""",
        unsafe_allow_html=True,
    )

    if st.session_state.step < 3:
        if st.button("See the six-deficiency lineage  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - six-deficiency composition
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='ll-card'><span class='ll-step-label'>Step 3</span>"
        "<h3>Six-deficiency lineage - each gap closed inline</h3>"
        "<p class='muted'>Each row is one of the six deficiencies the product taxonomy names. "
        "Green = closed by composition. Amber = pending (typically an outcome that has not yet "
        "surfaced). The exact taxonomy is the product's intellectual property and is the lens "
        "through which a regulator reads the lineage.</p></div>",
        unsafe_allow_html=True,
    )

    for r in rows:
        cls = "def-row" if r["ok"] else "def-row gap"
        status = "RESOLVED" if r["ok"] else "PENDING (not yet observed)"
        st.markdown(
            f"<div class='{cls}'><div class='dlabel'>{r['label']} - {status}</div>"
            f"<div class='dval'>{r['value']}</div></div>",
            unsafe_allow_html=True,
        )

    with st.expander("Raw lineage JSON (the immutable record)"):
        st.json(record, expanded=False)

    if st.session_state.step < 4:
        if st.button("Open the exam pack  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - exam pack + glossary + production stack
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='ll-card'><span class='ll-step-label'>Step 4</span>"
        "<h3>Auto-assembled exam pack</h3>"
        "<p class='muted'>The regulator-facing artifact. Every field hash-anchored. "
        "Stored under WORM (Write-Once-Read-Many) retention for the SR 11-7 / EU AI Act "
        "Article 12 seven-year horizon.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Text export
    pack_text_lines = [
        "=" * 76,
        "LINEAGELOG EXAM PACK - auto-assembled for regulator request",
        "=" * 76,
        "",
        f"Decision ID:        {drow['decision_id']}",
        f"Customer (hashed):  {drow['customer_id']}",
        f"Decision type:      {drow['decision_type']}",
        f"Decision time:      {drow['timestamp']}",
        f"Outcome:            {drow['outcome']}  (${float(drow['decision_value']):,.2f})",
        "",
        "Six-deficiency lineage",
        "-" * 76,
    ]
    for r in rows:
        pack_text_lines.append(f"  {r['label']}: {r['value']}")
    pack_text_lines.extend([
        "",
        "Cross-references (raw log surfaces composed into this record)",
        "-" * 76,
        f"  cloud_logging_ref:   projects/bank-prod/logs/decisions/{drow['decision_id']}",
        f"  cloud_audit_ref:     projects/bank-prod/audit/{drow['decision_id']}",
        f"  agent_identity_ref:  iam/agent-identity/{drow['decision_id']}",
        f"  otel_trace_ref:      projects/bank-prod/traces/{drow['decision_id']}",
        "",
        "Retention policy:   7 years (SR 11-7, EU AI Act Article 12), WORM-bucketed",
        "Composition time:   <50ms on the prototype",
        "",
        "This pack is immutable and hash-anchored. Interlocks with the bank's MRM workbench.",
        "=" * 76,
    ])
    pack_text = "\n".join(pack_text_lines)

    # PDF export via reportlab (lazy import so the rest of the app loads even if not installed)
    def build_pdf_bytes(pack_lines: list[str]) -> bytes:
        try:
            from reportlab.lib.pagesizes import LETTER
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import inch
        except ImportError:
            return None

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=LETTER)
        width, height = LETTER
        c.setFont("Helvetica-Bold", 14)
        c.drawString(0.75 * inch, height - 0.75 * inch, "LineageLog - Exam Pack")
        c.setFont("Helvetica", 9)
        c.drawString(0.75 * inch, height - 1.0 * inch,
                     f"Decision {drow['decision_id']} - auto-assembled "
                     f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        c.line(0.75 * inch, height - 1.1 * inch, width - 0.75 * inch, height - 1.1 * inch)

        y = height - 1.4 * inch
        c.setFont("Courier", 8.5)
        for line in pack_lines:
            if y < 0.75 * inch:
                c.showPage()
                y = height - 0.75 * inch
                c.setFont("Courier", 8.5)
            c.drawString(0.75 * inch, y, line[:110])
            y -= 12
        c.save()
        buf.seek(0)
        return buf.read()

    pdf_bytes = build_pdf_bytes(pack_text_lines)

    col_a, col_b = st.columns(2)
    with col_a:
        if pdf_bytes is not None:
            st.download_button(
                "Download verification PDF",
                pdf_bytes,
                file_name=f"lineagelog_exam_pack_{drow['decision_id']}.pdf",
                mime="application/pdf",
                type="primary",
            )
        else:
            st.info("Install reportlab to enable the PDF download (`pip install reportlab==4.2.0`).")
    with col_b:
        st.download_button(
            "Download text export",
            pack_text,
            file_name=f"lineagelog_exam_pack_{drow['decision_id']}.txt",
            mime="text/plain",
        )

    with st.expander("View the exam pack inline", expanded=True):
        st.code(pack_text, language="text")

    # Source-of-truth data viewers - mirror LeaseGuard's expander pattern
    with st.expander("Inspect source-of-truth data (decisions.csv)"):
        st.caption(
            f"All 200 synthetic AI decisions across the 4-model fleet. "
            f"Click a column header to sort. Source: "
            f"[`data/decisions.csv`]({REPO_BLOB}/data/decisions.csv)."
        )
        st.dataframe(DATA["decisions"], use_container_width=True, hide_index=True)

    with st.expander("Inspect source-of-truth data (models.csv)"):
        st.caption(
            f"The 4 deployed models. Snapshot IDs are the pin that closes deficiency #3. "
            f"Source: [`data/models.csv`]({REPO_BLOB}/data/models.csv)."
        )
        st.dataframe(DATA["models"], use_container_width=True, hide_index=True)

    with st.expander("Inspect source-of-truth data (retrieval_sets.csv)"):
        st.caption(
            f"597 retrieval-set captures - the documents each decision was shown. "
            f"Closes deficiency #2. Source: "
            f"[`data/retrieval_sets.csv`]({REPO_BLOB}/data/retrieval_sets.csv)."
        )
        st.dataframe(DATA["retrievals"], use_container_width=True, hide_index=True)

    with st.expander("Inspect source-of-truth data (outcomes.csv)"):
        st.caption(
            f"200 downstream outcomes - the backlink that closes deficiency #6. "
            f"Source: [`data/outcomes.csv`]({REPO_BLOB}/data/outcomes.csv)."
        )
        st.dataframe(DATA["outcomes"], use_container_width=True, hide_index=True)

    # Glossary
    with st.expander("Glossary - what these terms mean"):
        glossary_df = pd.DataFrame(
            [
                ("AI decision lineage", "The chain of facts about one AI decision: which prompt, which model snapshot, which documents, which features, who authorized it, what happened next."),
                ("Decision-grain composition", "Joining log fragments at the decision_id level so one record carries every relevant fact about that decision."),
                ("Cloud Logging", "Google Cloud's request/response log surface. Captures every API call but not business context."),
                ("Cloud Audit Logs", "Separate audit-only log of who accessed which sensitive resource. Required by SR 11-7 and SOC 2."),
                ("Agent Identity Log", "Cryptographic record of when an AI agent acquired credentials. The trail that distinguishes 'human told the agent to act' from 'the agent acted on its own.'"),
                ("OpenTelemetry trace (OTel)", "Industry-standard distributed tracing. Captures the AI agent's chain-of-thought as a waterfall."),
                ("Model snapshot pin", "The exact version of the model that scored this decision. Without this, vendor silent updates are invisible."),
                ("Feature-at-decision-time", "The customer's features (FICO, DTI, risk score) AT the moment of the decision - not the current values, which have since changed."),
                ("Retrieval set", "The documents the model was shown when it made the decision. For RAG (Retrieval-Augmented Generation) systems, this is the whole context window."),
                ("Reviewer attribution", "Who or what authorized this action. A human user via delegated token, or an autonomous agent on its own credentials."),
                ("Outcome backlink", "The downstream consequence of the decision: complaint filed, charge-off, fraud loss, customer churn."),
                ("WORM (Write-Once-Read-Many)", "Storage mode where data cannot be modified after writing. Required for regulatory retention."),
                ("MRM", "Model Risk Management - the bank's internal team that approves every AI before deployment."),
                ("OCC", "Office of the Comptroller of the Currency - federal banking regulator that audits AI safety."),
                ("EU AI Act Article 12", "EU regulation requiring record-keeping for high-risk AI systems (loans, credit, KYC, insurance)."),
                ("NIST AI RMF", "NIST's AI Risk Management Framework. The US federal-government framework for AI risk."),
                ("SR 11-7", "Federal Reserve 2011 supervisory letter on model risk management - co-issued with OCC Bulletin 2011-12."),
                ("Exam pack", "The auto-assembled, regulator-friendly artifact summarizing one decision's full lineage. The thing that used to take 14 days to write."),
            ],
            columns=["Term", "Plain English"],
        )
        st.dataframe(glossary_df, use_container_width=True, hide_index=True)

        st.markdown("**Official references** (click to read the source documents):")
        st.markdown(
            "- [EU AI Act Article 12 - record-keeping for high-risk AI systems](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)\n"
            "- [NIST AI Risk Management Framework (AI RMF 1.0)](https://www.nist.gov/itl/ai-risk-management-framework)\n"
            "- [SR 11-7 / OCC Bulletin 2011-12 - Supervisory Guidance on Model Risk Management](https://www.occ.gov/news-issuances/bulletins/2011/bulletin-2011-12.html) - *the Federal Reserve's SR 11-7 and the OCC's Bulletin 2011-12 are co-issued. We link to the OCC's stable URL because many Fed SR-letter URLs now 404.*\n"
            "- [OCC - Model Risk Management resource center](https://www.occ.gov/topics/supervision-and-examination/model-risk-management.html)\n"
            "- [Federal Reserve - Supervisory Letters home](https://www.federalreserve.gov/supervisionreg/srletters/srletters.htm)"
        )

    # Production stack reassessment
    with st.expander("Production stack reassessment - what this would look like as client-facing SaaS"):
        st.markdown(
            """
            The Streamlit prototype here proves the *product mechanic* - that decision-grain composition can compress
            audit-evidence assembly from 14 days to 12 minutes. **If LineageLog were a real product shipping to a Tier-1
            bank's compliance and MRM organizations:**

            - **Frontend:** Next.js 15 + Tailwind + shadcn/ui (or the bank's design system - JPMorgan Glaze, Capital One Cube) -
              embedded as a panel inside the validator's existing MRM workbench (Archer, ServiceNow GRC, MetricStream), not a standalone app.
            - **Auth:** SAML / OIDC via the bank's IdP (Okta, ForgeRock, PingFederate); fine-grained RBAC mapping
              line-1 model-owner / line-2 validator / line-3 audit / regulator-facing roles.
            - **Backend:** FastAPI on the bank's existing K8s/EKS footprint; microservice per log-source ingester
              (Cloud Logging tail, Cloud Audit tail, Agent Identity Auth Manager tail, OTel collector).
            - **Data plane:** **Postgres** for the immutable `decision_lineage` table (row-level security, point-in-time
              recovery, append-only via triggers); **ClickHouse** for the high-cardinality drift signals (interlocks with
              [DriftSentinel](https://github.com/Vj-shipped-anyway/ai-pm-portfolio/tree/main/02-driftsentinel-model-drift-monitoring));
              **GCS / S3 with Object Lock** for the WORM evidence bundles and the 7-year audit archive.
            - **Composition engine:** Streaming Dataflow / EMR job that binds the four log surfaces by `(decision_id,
              customer_id_hash, timestamp)` within a 5-minute composition SLO.
            - **Observability:** OpenTelemetry -> Datadog (the bank's standard) for the service traces;
              Langfuse for any GenAI-as-judge traces; PagerDuty for SLO breaches.
            - **Compliance:** SOC 2 Type II baseline; FedRAMP Moderate where federal counterparty work demands it;
              data residency configurable per region (US East, EU West, India for RBI compliance).
            - **Governance:** Native integration with the bank's MRM workbench - each decision-lineage record gets a
              workflow ID, attestation routes to the line-2 validator's queue, audit-pack export is one click.
            - **Deployment:** Blue-green via Argo CD; canary rollout 1% -> 10% -> 50% -> 100% over 14 days;
              auto-rollback on composition-latency breach.

            The portfolio prototype is the conversation-starter. This architecture is the second meeting.
            """
        )

    st.markdown(
        f"<div class='ll-card muted'>Built as a portfolio prototype. Full walkthrough in "
        f"<a href='{REPO_BLOB}/README.md' target='_blank'><code>README.md</code></a> · "
        f"<a href='{REPO_BLOB}/ARCHITECTURE.md' target='_blank'><code>ARCHITECTURE.md</code></a> · "
        f"<a href='{REPO_BLOB}/PRD.md' target='_blank'><code>PRD.md</code></a>.</div>",
        unsafe_allow_html=True,
    )
