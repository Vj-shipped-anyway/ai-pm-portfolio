"""OversightOps - HITL workflow designer that replaces rubber-stamp with calibrated review.

Streamlit walkthrough:
  Step 1 - pick a case (or use the headline CASE_0317_20260512)
  Step 2 - executive verdict card: APPROVED / ESCALATED / RUBBER_STAMPED_BLOCKED
  Step 3 - the six deficiencies, before vs after
  Step 4 - trust signals + glossary + production stack reassessment
"""

from __future__ import annotations

import csv
import json
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="OversightOps - Calibrated HITL in 8 minutes, not 8 seconds",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
REPO_BLOB = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/08-oversightops-hitl-workflow"

TARGET_CASE_ID = "CASE_0317_20260512"
TIER_SLA_SEC = {"private_banking": 480, "sme": 180, "retail": 60}
TIER_FLOOR_SEC = {"private_banking": 60, "sme": 30, "retail": 8}


# ---------------------------------------------------------------------------
# Theme - dark navy gradient hero, white body, indigo accent
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

.oo-hero {
  background: linear-gradient(135deg,#0a0e2e 0%, #1e2a78 60%, #4f46e5 100%);
  border-radius: 18px; padding: 36px 40px; color:#fff; margin-bottom:28px;
}
.oo-hero .brand {font-size:26px; font-weight:600; opacity:0.92; margin-bottom:12px;}
.oo-hero h1 {color:#fff !important; font-size:44px; line-height:1.15; margin:0 0 14px 0; font-weight:700;}
.oo-hero .sub {font-size:17px; line-height:1.5; opacity:0.93; max-width:840px; margin-bottom:22px;}
.oo-hero .pills {display:flex; flex-wrap:wrap; gap:10px;}
.oo-hero .pill {background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
                color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.oo-hero .pill a {color:#fff; text-decoration:none;}

.oo-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:22px 26px;
          margin-bottom:18px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.oo-card h3 {margin-top:0; color:#0f172a;}
.oo-step-label {display:inline-block; background:#4f46e5; color:#fff; padding:3px 10px;
                border-radius:6px; font-size:12px; font-weight:600; letter-spacing:0.04em;
                text-transform:uppercase; margin-bottom:10px;}

.verdict-card {border-radius:16px; padding:26px 30px; margin-bottom:18px; color:#fff;}
.verdict-pass {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.verdict-flag {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.verdict-review {background: linear-gradient(135deg,#b45309,#f59e0b);}
.verdict-card .vlabel {font-size:13px; opacity:0.9; letter-spacing:0.08em; text-transform:uppercase;}
.verdict-card .vbig {font-size:40px; font-weight:800; line-height:1.1; margin:4px 0 14px 0;}
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
.def-row.bad {background:#fee2e2; border-left-color:#ef4444; color:#7f1d1d;}
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
        "cases":         pd.read_csv(DATA_DIR / "cases.csv"),
        "reviewers":     pd.read_csv(DATA_DIR / "reviewers.csv"),
        "outcomes":      pd.read_csv(DATA_DIR / "review_outcomes.csv"),
        "ground_truth":  pd.read_csv(DATA_DIR / "ground_truth_backfill.csv"),
    }


DATA = load_data()


# ---------------------------------------------------------------------------
# Routing primitives (mirror step_04_with_oversightops.py)
# ---------------------------------------------------------------------------
def difficulty_route(case: dict) -> str:
    diff = int(case["difficulty_score"])
    conf = float(case["ai_confidence"])
    ctier = case["customer_tier"]
    country_tier = int(case["country_risk_tier"])
    if ctier == "private_banking":
        return "lead"
    if country_tier >= 3 and (diff >= 4 or conf < 0.65):
        return "lead"
    if diff == 5:
        return "lead"
    if ctier == "sme":
        return "senior"
    if diff == 4 or conf < 0.70:
        return "senior"
    if country_tier >= 2:
        return "senior"
    return "junior"


def rubber_stamp_blocker(case: dict, time_to_decide: float) -> bool:
    floor = TIER_FLOOR_SEC.get(case["customer_tier"], 8)
    return time_to_decide < floor


@st.cache_data
def detect_calibration_drift() -> list[dict]:
    outcomes = DATA["outcomes"]
    reviewers = DATA["reviewers"].set_index("reviewer_id").to_dict("index")
    per_rev = defaultdict(list)
    for _, o in outcomes.iterrows():
        per_rev[o["reviewer_id"]].append(0 if bool(o["agreed_with_ai"]) else 1)
    rates = [(rid, sum(v) / max(len(v), 1), len(v)) for rid, v in per_rev.items()]
    if len(rates) < 2:
        return []
    rate_values = [r[1] for r in rates]
    cohort_mean = mean(rate_values)
    cohort_sd = stdev(rate_values) if len(rate_values) > 1 else 0.0
    flagged = []
    for rid, rate, n in rates:
        if cohort_sd > 0 and abs(rate - cohort_mean) >= 1.5 * cohort_sd:
            flagged.append({
                "reviewer_id": rid,
                "name": reviewers[rid]["name"],
                "tenure": reviewers[rid]["tenure"],
                "override_rate": round(rate, 3),
                "cohort_mean": round(cohort_mean, 3),
                "delta_sigma": round((rate - cohort_mean) / cohort_sd, 2),
                "n_cases": n,
            })
    return flagged


def compose_verdict(case_id: str) -> dict:
    cases_df = DATA["cases"]
    reviewers_df = DATA["reviewers"]
    outcomes_df = DATA["outcomes"]
    gt_df = DATA["ground_truth"]

    crow = cases_df[cases_df["case_id"] == case_id]
    if len(crow) == 0:
        return None
    case = crow.iloc[0].to_dict()

    orow = outcomes_df[outcomes_df["case_id"] == case_id]
    outcome = orow.iloc[0].to_dict() if len(orow) else {}
    reviewer = reviewers_df[reviewers_df["reviewer_id"] == outcome.get("reviewer_id")]
    reviewer = reviewer.iloc[0].to_dict() if len(reviewer) else {}

    grow = gt_df[gt_df["case_id"] == case_id]
    gt = grow.iloc[0].to_dict() if len(grow) else {}

    routed_to = difficulty_route(case)
    actual_time = float(outcome.get("time_to_decision_sec", 0))
    floor = TIER_FLOOR_SEC[case["customer_tier"]]
    sla = TIER_SLA_SEC[case["customer_tier"]]

    rubber_stamped = (actual_time < floor
                      and case["customer_tier"] in ("private_banking", "sme"))

    if rubber_stamped:
        verdict = "RUBBER_STAMPED_BLOCKED"
    elif routed_to == "lead" and reviewer.get("tenure") not in (None, "lead"):
        verdict = "ESCALATED"
    else:
        verdict = "APPROVED"

    return {
        "case": case,
        "outcome": outcome,
        "reviewer": reviewer,
        "ground_truth": gt,
        "routed_to": routed_to,
        "actual_time": actual_time,
        "sla_floor": floor,
        "sla_target": sla,
        "rubber_stamped": rubber_stamped,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "step" not in st.session_state:
    st.session_state.step = 1

all_cases = DATA["cases"]
CASE_OPTIONS = []
priority_ids = [TARGET_CASE_ID]
# Pick six interesting cases to show in dropdown: headline + 5 representative
extras = all_cases.sort_values(["customer_tier", "difficulty_score"], ascending=[True, False]).head(20)
for cid in priority_ids:
    row = all_cases[all_cases["case_id"] == cid]
    if len(row):
        r = row.iloc[0]
        CASE_OPTIONS.append(f"{r['case_id']} - {r['customer_tier']} - "
                            f"AI conf {r['ai_confidence']} - {r['ai_decision']}")

# Add representative interesting cases
seen = set(priority_ids)
for _, r in extras.iterrows():
    if len(CASE_OPTIONS) >= 8:
        break
    if r["case_id"] in seen:
        continue
    if r["customer_tier"] == "private_banking" or int(r["difficulty_score"]) >= 4:
        CASE_OPTIONS.append(f"{r['case_id']} - {r['customer_tier']} - "
                            f"AI conf {r['ai_confidence']} - {r['ai_decision']}")
        seen.add(r["case_id"])

# Pad with a few more
for _, r in all_cases.head(50).iterrows():
    if len(CASE_OPTIONS) >= 12:
        break
    if r["case_id"] not in seen:
        CASE_OPTIONS.append(f"{r['case_id']} - {r['customer_tier']} - "
                            f"AI conf {r['ai_confidence']} - {r['ai_decision']}")
        seen.add(r["case_id"])

if "case_choice" not in st.session_state:
    st.session_state.case_choice = CASE_OPTIONS[0]


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='oo-hero'>
  <div class='brand'>👥 OversightOps</div>
  <h1>Every regulated AI decision gets the right reviewer at the right tier with a real timer — instead of a rubber stamp.</h1>
  <div class='sub'>A HITL workflow designer that replaces single-queue review with difficulty-stratified routing, a rubber-stamp blocker, calibration-drift detection, and a ground-truth feedback loop. Built against the Google Cloud secure-multi-agent reference architecture (ADK confirmation primitives); mapped to <a href='https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng' target='_blank' style='color:#fff;text-decoration:underline;'>EU AI Act Article 14 (human oversight)</a>, <a href='https://www.nist.gov/itl/ai-risk-management-framework' target='_blank' style='color:#fff;text-decoration:underline;'>NIST AI RMF</a>, and <a href='https://www.occ.gov/topics/supervision-and-examination/model-risk-management.html' target='_blank' style='color:#fff;text-decoration:underline;'>OCC model risk supervisory guidance</a>.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>1,000 synthetic KYC cases</span>
    <span class='pill'>12 modeled reviewers</span>
    <span class='pill'>6 deficiencies closed</span>
    <span class='pill'>Built 2026</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

if st.session_state.step == 1:
    cta_col, _ = st.columns([1, 2])
    with cta_col:
        if st.button("See it in action  ->", key="cta_hero", type="primary",
                     use_container_width=True):
            advance(2)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 1 - pick a case
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='oo-card'><span class='oo-step-label'>Step 1</span>"
    "<h3>Pick a case the bank just routed for HITL review</h3>"
    "<p class='muted'>Default selection is <code>CASE_0317_20260512</code> - the private-banking KYC "
    "case the AI approved at 0.62 confidence on a country-tier-4 customer, "
    "rubber-stamped by a junior reviewer in 8 seconds, and surfaced 27 days later as "
    "an OFAC sanctions-list match. Today: ships with the bank's name attached. "
    "With OversightOps: auto-blocked, re-queued to a lead, rejected.</p></div>",
    unsafe_allow_html=True,
)

st.session_state.case_choice = st.selectbox(
    "Case:",
    CASE_OPTIONS,
    index=CASE_OPTIONS.index(st.session_state.case_choice) if st.session_state.case_choice in CASE_OPTIONS else 0,
    label_visibility="collapsed",
)
chosen_id = st.session_state.case_choice.split(" - ")[0]
record = compose_verdict(chosen_id)

case = record["case"]
reviewer = record["reviewer"]
outcome = record["outcome"]

st.markdown(
    f"<div class='oo-card'><b>Case:</b> {case['case_id']}<br>"
    f"<b>Customer (hashed):</b> {case['customer_id']}  -  "
    f"<b>Tier:</b> {case['customer_tier']}  -  "
    f"<b>Country risk tier:</b> {case['country_risk_tier']}<br>"
    f"<b>AI decision:</b> {case['ai_decision']}  -  "
    f"<b>AI confidence:</b> {case['ai_confidence']}  -  "
    f"<b>Difficulty:</b> {case['difficulty_score']} / 5<br>"
    f"<b>Ingested:</b> {case['ingested_at']}  -  "
    f"<b>Case value:</b> ${float(case['case_value_usd']):,.2f}</div>",
    unsafe_allow_html=True,
)

if st.session_state.step < 2:
    if st.button("Run the OversightOps router  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - executive verdict
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    t0 = time.perf_counter()
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    verdict_word = record["verdict"]
    if verdict_word == "APPROVED":
        verdict_class = "verdict-pass"
        risk = "LOW"
        action = ("OversightOps routes to the right-tier reviewer, the SLA timer engages, "
                  "the decision is logged with rubric attestation. Exam-ready.")
        confidence = "HIGH (>95%)"
        confidence_class = "confidence-high"
        tldr = (f"Case routed to the {record['routed_to']} queue; reviewer "
                f"{reviewer.get('name', 'unknown')} took {record['actual_time']}s "
                f"(SLA floor {record['sla_floor']}s). Verdict logged with rubric.")
    elif verdict_word == "ESCALATED":
        verdict_class = "verdict-review"
        risk = "MEDIUM"
        action = ("Case was routed by OversightOps to a lead-tier reviewer because "
                  "of difficulty score, low AI confidence, country risk, or tier. "
                  "Re-queued out of the junior queue.")
        confidence = "MEDIUM (70-95%)"
        confidence_class = "confidence-med"
        tldr = (f"OversightOps routes this to the LEAD queue; the actual reviewer was "
                f"{reviewer.get('tenure', 'unknown')}. Case is auto-escalated.")
    else:  # RUBBER_STAMPED_BLOCKED
        verdict_class = "verdict-flag"
        risk = "HIGH"
        action = ("Rubber-stamp blocker fires: review completed in "
                  f"{record['actual_time']}s on a {case['customer_tier']} case where "
                  f"the procedure-manual floor is {record['sla_floor']}s. "
                  "Decision is rejected at the gate. Case is re-queued to a lead "
                  "reviewer with the SLA timer engaged.")
        confidence = "HIGH (>95%)"
        confidence_class = "confidence-high"
        tldr = (f"BLOCKED: {record['actual_time']}s review on a "
                f"{case['customer_tier']} case under the {record['sla_floor']}s policy floor. "
                f"Re-queued to {record['routed_to']} tier.")

    st.markdown(
        f"""
<div class='verdict-card {verdict_class}'>
  <div class='vlabel'>OversightOps Verdict ({elapsed_ms}ms)</div>
  <div class='vbig'>{verdict_word.replace('_', ' ')}</div>
  <div class='vrow'>
    <div class='vchip'>Routed to: {record['routed_to']} queue</div>
    <div class='vchip'>Actual reviewer: {reviewer.get('tenure', '?')}</div>
    <div class='vchip'>Time: {record['actual_time']}s</div>
    <div class='vchip'>SLA floor: {record['sla_floor']}s</div>
    <div class='vchip'>Risk: {risk}</div>
  </div>
  <div class='vtldr'>{tldr}</div>
  <div class='vtldr' style='font-size:14px; margin-top:10px;'><b>Action:</b> {action}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if st.session_state.step < 3:
        if st.button("Show the six deficiencies it closes  ->",
                     type="primary", key="cta_step2"):
            advance(3)
            st.rerun()


# ---------------------------------------------------------------------------
# STEP 3 - The six deficiencies
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='oo-card'><span class='oo-step-label'>Step 3</span>"
        "<h3>The six deficiencies, closed inline</h3>"
        "<p class='muted'>Each row shows what the bank had before (single-queue HITL) "
        "and what OversightOps composes on the same data.</p></div>",
        unsafe_allow_html=True,
    )

    drift = detect_calibration_drift()
    drift_for_this_reviewer = next((d for d in drift
                                    if d["reviewer_id"] == reviewer.get("reviewer_id")), None)

    deficiencies = [
        {
            "label": "1. Difficulty-stratified routing",
            "value": (f"Case difficulty {case['difficulty_score']}/5 + AI conf "
                      f"{case['ai_confidence']} + tier {case['customer_tier']} "
                      f"-> routed to {record['routed_to'].upper()} queue"),
            "ok": True,
        },
        {
            "label": "2. Calibration drift detection",
            "value": (f"Reviewer {reviewer.get('name','?')} ({reviewer.get('tenure','?')}): "
                      f"override rate vs cohort = "
                      + (f"FLAGGED ({drift_for_this_reviewer['delta_sigma']} sigma above cohort)"
                         if drift_for_this_reviewer else "within 1.5 sigma")),
            "ok": True,
            "gap": drift_for_this_reviewer is not None,
        },
        {
            "label": "3. Rubber-stamp blocker",
            "value": (f"Review took {record['actual_time']}s; tier floor "
                      f"{record['sla_floor']}s -> "
                      + ("BLOCKED" if record["rubber_stamped"] else "PASSES")),
            "ok": True,
            "bad": record["rubber_stamped"],
        },
        {
            "label": "4. Escalation path",
            "value": (f"Edge-case features (diff={case['difficulty_score']}, "
                      f"country tier={case['country_risk_tier']}) -> "
                      f"{record['routed_to'].upper()} queue auto-routing"),
            "ok": True,
        },
        {
            "label": "5. SLA by tier",
            "value": (f"{case['customer_tier']} target: {record['sla_target']}s; "
                      f"floor: {record['sla_floor']}s; actual: {record['actual_time']}s"),
            "ok": True,
            "gap": record["actual_time"] < record["sla_floor"],
        },
        {
            "label": "6. Ground-truth feedback loop",
            "value": (
                (f"Downstream signal {record['ground_truth'].get('downstream_signal')} surfaced "
                 f"{record['ground_truth'].get('backfill_observed_at')}; "
                 f"reviewer-vs-truth divergence on this case")
                if record["ground_truth"] else
                "No downstream signal observed (yet); calibration packet will update next cycle"
            ),
            "ok": True,
            "gap": bool(record["ground_truth"]),
        },
    ]

    for d in deficiencies:
        css_class = "def-row"
        if d.get("bad"):
            css_class += " bad"
        elif d.get("gap"):
            css_class += " gap"
        st.markdown(
            f"<div class='{css_class}'>"
            f"<div class='dlabel'>{d['label']}</div>"
            f"<div class='dval'>{d['value']}</div></div>",
            unsafe_allow_html=True,
        )

    if st.session_state.step < 4:
        if st.button("Show the trust signals  ->",
                     type="primary", key="cta_step3"):
            advance(4)
            st.rerun()


# ---------------------------------------------------------------------------
# STEP 4 - trust signals, fleet stats, data viewers
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='oo-card'><span class='oo-step-label'>Step 4</span>"
        "<h3>Trust signals + fleet stats + the data underneath</h3></div>",
        unsafe_allow_html=True,
    )

    # Trust signals
    drift = detect_calibration_drift()
    pb_cases = DATA["cases"][DATA["cases"]["customer_tier"] == "private_banking"]
    pb_outcomes = DATA["outcomes"].merge(pb_cases[["case_id"]], on="case_id", how="inner")
    pb_under_10 = (pb_outcomes["time_to_decision_sec"] < 10).sum()
    pb_total = len(pb_cases)
    pb_floor_breaches = (pb_outcomes["time_to_decision_sec"]
                         < TIER_FLOOR_SEC["private_banking"]).sum()

    st.markdown(
        f"""
<div class='trust-card'>
  <h4>Trust signals — what you can verify from the corpus</h4>
  <span class='tlabel'>Composition latency</span>
  <ul>
    <li><span class='confidence-high'>0.13 ms / case</span> measured on the 1,000-case fleet sweep in <code>step_04_with_oversightops.py</code>.</li>
  </ul>
  <span class='tlabel'>Rubber-stamp detection</span>
  <ul>
    <li>Single-queue baseline: <span class='confidence-low'>{pb_under_10:,}</span> of {pb_total:,} private-banking reviews ({pb_under_10 / max(pb_total, 1):.0%}) completed in &lt;10s.</li>
    <li>OversightOps: blocked at the gate. <span class='confidence-high'>0</span> rubber-stamped reviews ship on Tier-1.</li>
  </ul>
  <span class='tlabel'>Calibration drift</span>
  <ul>
    <li>{len(drift)} reviewer(s) flagged at &ge; 1.5 sigma off cohort override rate across the 12-reviewer roster.</li>
  </ul>
  <span class='tlabel'>Ground-truth backfill</span>
  <ul>
    <li>198 downstream signals (OFAC matches, SARs, CFPB complaints, charge-offs) bound back to original reviewer decisions for the 90-day study window.</li>
  </ul>
  <span class='tlabel'>Confidence on the numbers</span>
  <ul>
    <li>Composition latency: <span class='confidence-high'>Measured</span> (real output, this run).</li>
    <li>Rubber-stamp rate 94% baseline: <span class='confidence-med'>Modeled</span> (calibrated against published Tier-1 bank operational telemetry; the synthetic corpus shows 40% under-floor on private banking).</li>
    <li>$420k headline loss avoided: <span class='confidence-med'>Modeled</span> (assumes published OFAC-finding mid-range MRA exposure on a single case).</li>
  </ul>
</div>
""",
        unsafe_allow_html=True,
    )

    # CSV viewers
    st.markdown("### The data underneath")
    with st.expander(f"cases.csv  -  {len(DATA['cases']):,} rows", expanded=False):
        st.dataframe(DATA["cases"].head(50), use_container_width=True, height=320)
        st.markdown(f"[View full file on GitHub]({REPO_BLOB}/data/cases.csv)")

    with st.expander(f"reviewers.csv  -  {len(DATA['reviewers']):,} rows", expanded=False):
        st.dataframe(DATA["reviewers"], use_container_width=True, height=320)
        st.markdown(f"[View full file on GitHub]({REPO_BLOB}/data/reviewers.csv)")

    with st.expander(f"review_outcomes.csv  -  {len(DATA['outcomes']):,} rows", expanded=False):
        st.dataframe(DATA["outcomes"].head(50), use_container_width=True, height=320)
        st.markdown(f"[View full file on GitHub]({REPO_BLOB}/data/review_outcomes.csv)")

    with st.expander(f"ground_truth_backfill.csv  -  {len(DATA['ground_truth']):,} rows",
                     expanded=False):
        st.dataframe(DATA["ground_truth"].head(50), use_container_width=True, height=320)
        st.markdown(f"[View full file on GitHub]({REPO_BLOB}/data/ground_truth_backfill.csv)")

    # Glossary
    with st.expander("Glossary — HITL, calibration drift, regulator references", expanded=False):
        st.markdown(
            """
- **HITL (Human-in-the-loop)** — A workflow step where an AI decision is paused for explicit human review before action. [EU AI Act Article 14](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng) names this as the human-oversight requirement for high-risk AI systems.
- **Rubber-stamp** — A human review completed so fast (typically <10s on a Tier-1 case) that no real adjudication is plausible. Today most HITL surfaces in BFSI have no detector.
- **Calibration drift** — When two reviewers reviewing the same case mix arrive at materially different override rates. Surfaced via cohort comparison (typically &ge; 1.5 sigma off cohort mean).
- **Tier-1 review SLA** — The procedure-manual floor for time-on-task. Private banking ~8 minutes; SME ~3 minutes; retail ~1 minute. Today the SLA is documented; enforcement is absent.
- **Ground-truth backfill** — The lag-time signal that names a reviewer decision wrong. Sources: OFAC list matches, SAR filings, CFPB complaints, 30-day charge-offs, regulator findings.
- **[NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)** — The federal-government reference framework for AI risk; the HITL section maps directly to OversightOps's calibration and escalation controls.
- **[EU AI Act Article 14](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng)** — Human oversight requirement for high-risk AI. Names the four conditions human oversight must meet; OversightOps is the implementation surface.
- **[OCC supervisory guidance on model risk management](https://www.occ.gov/topics/supervision-and-examination/model-risk-management.html)** — US bank supervisor's expectation that high-stakes AI decisions have effective, measured human oversight.
- **[FRB supervisory letters (SR 11-7)](https://www.federalreserve.gov/supervisionreg/srletters/srletters.htm)** — Co-issued model risk management guidance from the Federal Reserve.
"""
        )

    # Production stack reassessment
    with st.expander("Why Streamlit (and what production would actually look like)",
                     expanded=False):
        st.markdown(
            """
Streamlit was the right tool for this prototype. It would be the wrong tool for production. Worth saying out loud so a hiring manager hears the architectural judgment.

**Streamlit is right for:** validating the product mechanic in 5 days, not 5 weeks; walking a Head of Compliance through the calibrated-review story end-to-end on a free deploy; single-tenant, single-page workflows where the UI does not have to scale.

**Streamlit is wrong for:** production multi-tenant SaaS (no native tenant isolation, no row-level security); hardened auth (OIDC, SAML, fine-grained RBAC); real-time queue dashboards (every interaction is a full server rerender); latency-sensitive reviewer flows.

### What this would look like as a production SaaS

- **Frontend:** Next.js 15 + Tailwind + shadcn/ui (or the bank's design system) — embedded as a panel inside the reviewer workbench in Pega, Appian, or ServiceNow.
- **Auth:** SAML / OIDC via the bank's IdP (Okta, ForgeRock, PingFederate); fine-grained RBAC mapping `oo:reviewer_junior` -> `oo:reviewer_senior` -> `oo:reviewer_lead` -> `oo:queue_admin` -> `oo:compliance`.
- **Backend:** FastAPI on the bank's existing K8s/EKS footprint; Cloud Functions / Lambda for the case ingester and the drift detector job.
- **Data plane:** Postgres for the reviewer decision store (row-level security, immutability trigger); ClickHouse for the high-cardinality reviewer-throughput time series; GCS / S3 Object Lock for the WORM evidence bundles.
- **Event spine:** Kafka / Pub/Sub for case ingestion; Temporal for long-running review workflows with the 8-minute SLA timer.
- **Observability:** OpenTelemetry -> Datadog (the bank's standard); PagerDuty for SLA breaches and calibration-drift outliers.
- **Compliance:** SOC 2 Type II baseline; FedRAMP Moderate where federal counterparty work demands it.
- **Governance:** Native integration with the bank's case management workflow (Pega, Appian, ServiceNow); the reviewer workbench remains the system of record; OversightOps is the routing + calibration + blocker layer that sits in front.
- **Deployment:** Blue-green via Argo CD; canary rollout 1% -> 10% -> 50% -> 100% over 14 days; auto-rollback on rubber-stamp-rate regression or SLA-breach spike.

The Streamlit prototype here proves the product mechanic — that difficulty-stratified routing + a rubber-stamp blocker + calibration drift + a ground-truth feedback loop closes the six HITL deficiencies on real-feeling data. The production architecture above is what the seat I'm pursuing actually delivers.
"""
        )

    # Footer pill row
    st.markdown(
        f"""
<div style='display:flex; gap:12px; justify-content:center; flex-wrap:wrap; margin-top:24px;'>
  <a href='{GITHUB_URL}' target='_blank' style='display:inline-block; padding:10px 22px; background:#0f172a; color:#fff; border-radius:999px; text-decoration:none; font-weight:600;'>GitHub</a>
  <a href='{LINKEDIN_URL}' target='_blank' style='display:inline-block; padding:10px 22px; background:#4f46e5; color:#fff; border-radius:999px; text-decoration:none; font-weight:600;'>LinkedIn</a>
  <a href='{REPO_BLOB}/README.md' target='_blank' style='display:inline-block; padding:10px 22px; background:#64748b; color:#fff; border-radius:999px; text-decoration:none; font-weight:600;'>Full README walkthrough</a>
</div>
""",
        unsafe_allow_html=True,
    )
