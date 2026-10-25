"""DriftSentinel - production model drift, diagnosed and routed.

Streamlit walkthrough:
  Step 1 - pick a model
  Step 2 - run the drift simulation (Day 60 / Day 90)
  Step 3 - see what each oversight layer caught (Door 1 / 2 / 3)
  Step 4 - the vendor-snapshot surprise
  Step 5 - the audit pack

Synthetic data. The per-model days-to-detect shown in Step 3 are modeled
illustrations; no script prints a time to detect.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="DriftSentinel - Designed to catch model drift 69 days earlier (modeled)",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

.ds-hero {
  background: linear-gradient(135deg,#0b1f3a 0%, #1d3a76 60%, #2563eb 100%);
  border-radius: 18px; padding: 36px 40px; color: #fff; margin-bottom: 28px;
}
.ds-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.ds-hero h1 {color: #fff !important; font-size: 46px; line-height: 1.12;
             margin: 0 0 14px 0; font-weight: 700;}
.ds-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.ds-hero .pills {display:flex; flex-wrap:wrap; gap:10px;}
.ds-hero .pill {background: rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
                color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.ds-hero .pill a {color:#fff; text-decoration:none;}

.ds-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:22px 26px;
          margin-bottom:18px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.ds-card h3 {margin-top:0; color:#0f172a;}
.ds-step-label {display:inline-block; background:#2563eb; color:#fff; padding:3px 10px;
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

.trust-card {background:#f8fafc; border:1px solid #cbd5e1; border-left:5px solid #2563eb;
             border-radius:12px; padding:20px 24px; margin-bottom:18px;}
.trust-card h4 {margin:0 0 10px 0; color:#0f172a; font-size:16px; letter-spacing:0.04em;
                text-transform:uppercase;}
.trust-card .tlabel {font-weight:700; color:#2563eb; font-size:13px; letter-spacing:0.04em;
                     text-transform:uppercase; margin-top:12px; display:block;}
.trust-card ul {margin:6px 0 0 18px; padding:0;}
.trust-card li {color:#334155; line-height:1.55;}
.confidence-high {color:#047857; font-weight:700;}
.confidence-med  {color:#b45309; font-weight:700;}
.confidence-low  {color:#b91c1c; font-weight:700;}

.door-card {border-radius:12px; padding:18px 22px; margin-bottom:12px;}
.door-evidently {background:#fef3c7; border-left:5px solid #f59e0b; color:#78350f;}
.door-validator  {background:#fef3c7; border-left:5px solid #f59e0b; color:#78350f;}
.door-sentinel   {background:#dcfce7; border-left:5px solid #16a34a; color:#14532d;}

div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#2563eb,#1d3a76) !important; color:#fff !important;
  border:0 !important; padding:14px 28px !important; font-size:17px !important;
  font-weight:600 !important; border-radius:12px !important;
  box-shadow:0 4px 14px rgba(37,99,235,0.35) !important;
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
    models = pd.read_csv(DATA_DIR / "models.csv")
    drift = pd.read_csv(DATA_DIR / "drift_events.csv")
    return {"models": models, "drift": drift}


DATA = load_data()

MODELS = {
    "Consumer Credit PD (credit_pd_v3)": {
        "model_id": "credit_pd_v3",
        "tier": 1,
        "owner": "line1.credit-risk",
        "narrative": "Subprime DTI distribution shifts at Day 60. Aggregate PSI only reads YELLOW (0.22); the subprime slice reads 2.37.",
        "sota_caught_day": 78,
        "sentinel_caught_day": 9,
        "decision": "SHADOW",
        "rec_text": "Shadow-deploy a v3.1 candidate while v3 keeps scoring; route subprime_650_680 to the candidate; ramp on validator sign-off.",
    },
    "Card-Present Fraud (fraud_card_v7)": {
        "model_id": "fraud_card_v7",
        "tier": 1,
        "owner": "line1.fraud-ops",
        "narrative": "Card-present velocity drifts after an adversary tactic shift (synthetic). The slice cut localizes it to card_present_pos.",
        "sota_caught_day": 64,
        "sentinel_caught_day": 11,
        "decision": "RETRAIN",
        "rec_text": "Retrain a candidate on recent velocity data; it must hold AUC within -0.5pp of the incumbent on backtest before promotion; gate on validator review.",
    },
    "AML SAR Triage (aml_sar_v2)": {
        "model_id": "aml_sar_v2",
        "tier": 1,
        "owner": "line1.financial-crimes",
        "narrative": "No drift is injected for this model. Step 2 raises one YELLOW alert on the prediction column (PSI 0.1156), which is noise.",
        "sota_caught_day": -1,
        "sentinel_caught_day": -1,
        "decision": "RETAIN",
        "rec_text": "No action - continue monitoring; re-evaluate at the next window.",
    },
    "Customer Support Q&A GenAI (support_qa_v2)": {
        "model_id": "support_qa_v2",
        "tier": 1,
        "owner": "line1.servicing",
        "narrative": "The hosted-model snapshot changed silently on Feb 14 (synthetic). Refusal rate moved from 4.5% to 11.17%. PSI/KS flags numeric columns RED but carries no label and no cause.",
        "sota_caught_day": 999,  # PSI/KS alerts exist but explain nothing; no time to detect is modeled
        "sentinel_caught_day": 1,
        "decision": "ROLLBACK",
        "rec_text": "Roll back to the prior pinned snapshot; freeze new snapshot promotions until probe regression passes.",
    },
    "HELOC Default PD (heloc_pd_v1)": {
        "model_id": "heloc_pd_v1",
        "tier": 2,
        "owner": "line1.credit-risk",
        "narrative": "No drift is injected. Step 2 raises two YELLOW alerts (noise); Step 4 retains.",
        "sota_caught_day": -1,
        "sentinel_caught_day": -1,
        "decision": "RETAIN",
        "rec_text": "No action - quarterly attestation passes; resume routine monitoring.",
    },
    "Auto Loan PD (auto_pd_v4)": {
        "model_id": "auto_pd_v4",
        "tier": 2,
        "owner": "line1.auto-lending",
        "narrative": "Stable - no drift is injected and every feature reads GREEN in Step 2. Model retains.",
        "sota_caught_day": -1,
        "sentinel_caught_day": -1,
        "decision": "RETAIN",
        "rec_text": "No action - continue monitoring; re-evaluate at the next window.",
    },
}

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "step" not in st.session_state:
    st.session_state.step = 1
if "model_choice" not in st.session_state:
    st.session_state.model_choice = list(MODELS.keys())[0]


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='ds-hero'>
  <div class='brand'>🛰️ DriftSentinel</div>
  <h1>Designed to catch production model drift 69 days before quarterly attestation does (modeled).</h1>
  <div class='sub'>Sits on top of your existing drift tooling (Evidently, Arize) and adds the diagnose-decide loop they leave to the validator (the independent reviewer who must approve a model before launch). Slice-aware, GenAI-aware, vendor-snapshot-aware - and outputs a bounded recommendation, not a chart.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'><a href='https://www.occ.gov/news-issuances/bulletins/2011/bulletin-2011-12.html' target='_blank'>SR 11-7 aligned</a></span>
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
# STEP 1 - pick a model
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='ds-card'><span class='ds-step-label'>Step 1</span>"
    "<h3>Pick a model from the synthetic 8-model fleet</h3>"
    "<p class='muted'>$50B-asset US retail bank shape: 8 synthetic production models across credit, fraud, AML, GenAI. "
    "Drift (model drift) is when an AI quietly stops working as well as it used to "
    "(because the world changed). Each one has a different drift story.</p></div>",
    unsafe_allow_html=True,
)

st.session_state.model_choice = st.selectbox(
    "Model:",
    list(MODELS.keys()),
    index=list(MODELS.keys()).index(st.session_state.model_choice),
    label_visibility="collapsed",
)
m = MODELS[st.session_state.model_choice]
mrow = DATA["models"][DATA["models"]["model_id"] == m["model_id"]].iloc[0]

st.markdown(
    f"<div class='ds-card'><b>Model:</b> {mrow['name']} ({mrow['model_id']})<br>"
    f"<b>Tier:</b> {mrow['tier']}  -  <b>Owner:</b> {mrow['owner']}  -  "
    f"<b>Vendor:</b> {mrow['vendor']}  -  <b>Snapshot:</b> {mrow['snapshot_id']}<br>"
    f"<span class='muted'>{m['narrative']}</span></div>",
    unsafe_allow_html=True,
)

if st.session_state.step < 2:
    if st.button("Run the simulation  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - day-90 setup
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='ds-card'><span class='ds-step-label'>Step 2</span>"
        "<h3>Day-90 simulation - what each layer of oversight saw</h3>"
        "<p class='muted'>Three doors map to the bank's three lines of defense "
        "(standard model-risk structure: 1=builders, 2=reviewers, 3=auditors): "
        "(1) Evidently/Arize aggregate drift, "
        "(2) quarterly validator attestation, "
        "(3) DriftSentinel slice + vendor + GenAI awareness.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.step < 3:
        if st.button("See what each oversight layer caught  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - the three doors + verdict card
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    sentinel_day = m["sentinel_caught_day"]
    sota_day = m["sota_caught_day"]
    decision = m["decision"]
    is_drift = sentinel_day > 0

    if not is_drift:
        verdict_class = "verdict-pass"
        verdict_word = "RETAIN"
        risk = "LOW"
        action = "No action required"
        key_metric = "No drift detected on Day 90"
        tldr = "Model is stable. Quarterly attestation passes. Resume routine monitoring."
    elif sota_day == 999:
        verdict_class = "verdict-flag"
        verdict_word = "ROLLBACK"
        risk = "HIGH"
        action = m["rec_text"]
        days_saved = 90
        key_metric = "Flagged by the vendor-snapshot diff and the refusal-rate proxy; PSI/KS alone gives unlabeled numeric alerts"
        tldr = (
            f"The hosted vendor model's snapshot (the exact pinned version of an outside AI) changed without notice. "
            f"PSI (Population Stability Index - detects when the AI is seeing different data than "
            f"it was trained on) and KS (Kolmogorov-Smirnov test - another data-shift detector) do flag "
            f"numeric columns here, but with no label, no cause and no action. The vendor-snapshot diff and the "
            f"refusal-rate, response-length and groundedness proxies tie the shift to the snapshot change, "
            f"and DriftSentinel recommends ROLLBACK."
        )
    else:
        days_saved = sota_day - sentinel_day
        verdict_class = "verdict-review" if decision == "SHADOW" else "verdict-flag"
        verdict_word = decision
        risk = "MEDIUM" if decision in ("SHADOW", "RETAIN") else "HIGH"
        action = m["rec_text"]
        key_metric = f"Modeled: caught on Day {sentinel_day} vs Day {sota_day} for SOTA tooling ({days_saved} days earlier)"
        shadow_note = (
            " (SHADOW = shadow mode: run the new model alongside the old one without affecting customers, "
            "to see how it behaves)"
            if decision == "SHADOW"
            else ""
        )
        tldr = (
            f"In the model, DriftSentinel flags a slice-confined drift on Day {sentinel_day}. "
            f"Aggregate-only tooling would not surface it until Day {sota_day}. "
            f"Bounded recommendation: {decision}.{shadow_note}"
        )

    st.markdown(
        f"""
<div class='verdict-card {verdict_class}'>
  <div class='vlabel'>DriftSentinel Verdict</div>
  <div class='vbig'>{verdict_word}</div>
  <div class='vmetric'>{key_metric}</div>
  <div class='vrow'>
    <span class='vchip'>Risk: {risk}</span>
    <span class='vchip'>Recommended action: {action}</span>
  </div>
  <div class='vtldr'><b>TL;DR:</b> {tldr}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    confidence = "Not measured - seeded synthetic data, no confidence interval computed"
    st.markdown(
        f"""
<div class='trust-card'>
  <h4>Assumptions and Trust Signals</h4>
  <span class='tlabel'>What we compared against</span>
  <div>Compared the current window (days 60 to 90) with the reference window (days 0 to 30) of the synthetic <code>inference_logs.csv</code>; vendor snapshots tracked from <code>vendor_snapshots.csv</code>.</div>
  <span class='tlabel'>Assumptions we made</span>
  <ul>
    <li>The reference window (days 0 to 30 of the 90-day log) is representative of "stable" behavior.</li>
    <li>Slice cuts (subprime_650_680, card_present_pos, etc.) reflect the bank's actual operating segments.</li>
    <li>For GenAI proxy metrics (refusal-rate, response-length, groundedness), the synthetic columns stand in for real judge scores.</li>
    <li><a href='https://www.occ.gov/news-issuances/bulletins/2011/bulletin-2011-12.html' target='_blank'>SR 11-7</a> (2011 supervisory guidance on model risk management; see the README's regulatory note) is the design basis for this tier-{mrow['tier']} model's ongoing monitoring.</li>
  </ul>
  <span class='tlabel'>Confidence level</span>
  <div class='confidence-high'>{confidence}</div>
  <span class='tlabel'>What this does NOT cover</span>
  <ul>
    <li>Input data quality issues unrelated to drift (schema breaks, source-system outages).</li>
    <li>Concept drift that requires labeled outcomes (charge-off, dispute) longer than 90 days to materialize.</li>
    <li>Adversarial input attacks against the upstream model.</li>
  </ul>
</div>
""",
        unsafe_allow_html=True,
    )

    # The three doors
    st.markdown("<h3>What each oversight layer caught</h3>", unsafe_allow_html=True)
    if not is_drift:
        st.markdown(
            "<div class='door-card door-sentinel'><b>All three doors:</b> No drift. Model is stable.</div>",
            unsafe_allow_html=True,
        )
    else:
        d1_caught = "Caught only aggregate PSI, modeled at Day " + str(sota_day) if sota_day != 999 else "Raised unlabeled PSI/KS alerts only: no cause, no segment, no action"
        d2_caught = "Quarterly attestation passes - validator does not see the slice cut"
        d3_caught = (f"Slice-aware drift caught, modeled at Day {sentinel_day}; bounded recommendation: {decision}" if sota_day != 999 else f"Vendor-snapshot diff plus proxy metrics; bounded recommendation: {decision}")
        st.markdown(
            f"<div class='door-card door-evidently'><b>Door 1 - Evidently / Arize (SOTA aggregate):</b> {d1_caught}</div>"
            f"<div class='door-card door-validator'><b>Door 2 - Quarterly validator attestation:</b> {d2_caught}</div>"
            f"<div class='door-card door-sentinel'><b>Door 3 - DriftSentinel:</b> {d3_caught}</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Detailed findings - drift events"):
        events = DATA["drift"][DATA["drift"]["model_id"] == m["model_id"]]
        if len(events) == 0:
            st.markdown("_No drift events recorded for this model._")
        else:
            st.dataframe(events, use_container_width=True, hide_index=True)

    if st.session_state.step < 4:
        if st.button("See the vendor surprise  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - vendor snapshot
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='ds-card'><span class='ds-step-label'>Step 4</span>"
        "<h3>The vendor-snapshot surprise (synthetic, Feb 14, 2026)</h3>"
        "<p class='muted'>Hosted models can change snapshot without notice. PSI/KS flags numeric columns but cannot say why. "
        "In the synthetic data the refusal rate rose from 4.5% to 11.17%, responses got longer, and groundedness fell.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class='verdict-card verdict-flag'>
  <div class='vlabel'>Vendor Snapshot Diff</div>
  <div class='vbig'>ROLLBACK</div>
  <div class='vmetric'>The support_qa_v2 snapshot changed silently on Feb 14, 2026 (synthetic)</div>
  <div class='vrow'>
    <span class='vchip'>Risk: HIGH</span>
    <span class='vchip'>PSI/KS: RED on unlabeled numeric columns, no diagnosis</span>
    <span class='vchip'>Step 4: ROLLBACK from the snapshot diff plus proxies</span>
  </div>
  <div class='vtldr'><b>TL;DR:</b> A PSI dashboard shows unlabeled numeric alerts for this kind of drift. The snapshot diff and the proxy metrics (refusal-rate, response-length, groundedness) are what tie it to the vendor change.</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if st.session_state.step < 5:
        if st.button("See the audit pack  ->", type="primary", key="cta_step4"):
            advance(5)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 5 - audit pack
# ---------------------------------------------------------------------------
if st.session_state.step >= 5:
    st.markdown(
        "<div class='ds-card'><span class='ds-step-label'>Step 5</span>"
        "<h3>MRM-ready audit pack</h3>"
        "<p class='muted'>Step 4 writes a sample evidence bundle. The 5-minute read time for a validator is a design target, not measured.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("Audit pack - evidence bundle", expanded=True):
        st.markdown(
            f"- **Model:** {mrow['name']} ({mrow['model_id']})\n"
            f"- **Tier:** {mrow['tier']}, Owner: {mrow['owner']}\n"
            f"- **Decision:** {m['decision']}\n"
            f"- **Drift signal:** the sample bundle is `out/step_04_evidence_bundle_credit_pd_v3.json` (credit_pd_v3 only)\n"
            f"- **Reference window:** days 0 to 30 of the 90-day `inference_logs.csv`\n"
            f"- **Vendor snapshot pin:** {mrow['snapshot_id']}\n"
            f"- **Telemetry stack (design):** OpenTelemetry -> ClickHouse (drift events) + Datadog + Langfuse\n"
            f"- **[SR 11-7](https://www.occ.gov/news-issuances/bulletins/2011/bulletin-2011-12.html) design basis:** ongoing monitoring + change management + escalation routing. "
            f"[OCC](https://www.occ.gov/topics/supervision-and-examination/model-risk-management.html) (Office of the Comptroller of the Currency) and [FRB](https://www.occ.gov/news-issuances/bulletins/2011/bulletin-2011-12.html) (Federal Reserve Board) co-issued the guidance.\n"
            f"- **Validator workflow (design):** routes to the line-2 validator queue (the independent reviewer "
            f"who approves a model before launch) with the bounded recommendation pre-filled. The line-1 owner is {mrow['owner']}."
        )

    # ---------------------------------------------------------------------------
    # GLOSSARY - plain-English definitions for jargon a non-technical reader hits
    # ---------------------------------------------------------------------------
    with st.expander("Glossary - what these terms mean"):
        glossary_df = pd.DataFrame(
            [
                ("Drift / model drift", "When an AI quietly stops working as well as it used to (because the world changed)."),
                ("Silent decay", "Drift where nobody on the team has noticed yet."),
                ("PSI", "Population Stability Index - a way to detect when the AI is seeing different kinds of data than it was trained on."),
                ("KS", "Kolmogorov-Smirnov test - another way to detect data shift."),
                ("MTTD", "Mean Time To Detect - how long it took to notice the model went bad."),
                ("Vendor snapshot", "The exact version of an outside AI (e.g., Anthropic) you're using - pinned in writing."),
                ("MRM", "Model Risk Management - the bank's internal team that reviews and validates models."),
                ("Three lines of defense", "Bank's standard model-risk structure: 1=builders, 2=reviewers, 3=auditors."),
                ("SR 11-7", "Federal Reserve 2011 supervisory guidance on model risk management. This prototype uses its ongoing-monitoring expectations as a design basis (see the README's regulatory note on SR 26-2)."),
                ("OCC", "Office of the Comptroller of the Currency - federal regulator that supervises national banks, including their model risk management."),
                ("FRB", "Federal Reserve Board - central banking system; co-issued SR 11-7 with the OCC."),
                ("Validator / line-2 validator", "Independent reviewer who validates a model before launch and again when it changes."),
                ("Risk envelope", "Pre-agreed boundary for 'what we're allowed to do automatically' vs. 'what needs a human'."),
                ("Shadow mode", "Running a new model alongside the old one without affecting customers, to see how it behaves."),
                ("Inference", "The actual requests customers send to the AI in production."),
                ("Detect / Diagnose / Decide loop", "The three steps when something looks wrong: notice it, figure out why, decide what to do."),
            ],
            columns=["Term", "Plain English"],
        )
        st.dataframe(glossary_df, use_container_width=True, hide_index=True)

        st.markdown("**Official references** (click to read the source documents):")
        st.markdown(
            "- [SR 11-7 / OCC Bulletin 2011-12 — Supervisory Guidance on Model Risk Management](https://www.occ.gov/news-issuances/bulletins/2011/bulletin-2011-12.html) — *the Federal Reserve's SR 11-7 and the OCC's Bulletin 2011-12 are co-issued and contain the same model-risk-management guidance. We link to the OCC's stable URL because the Fed reorganized their site and many SR-letter URLs now 404.*\n"
            "- [OCC — Model Risk Management resource center](https://www.occ.gov/topics/supervision-and-examination/model-risk-management.html)\n"
            "- [NIST AI Risk Management Framework (AI RMF 1.0)](https://www.nist.gov/itl/ai-risk-management-framework)"
        )

    st.markdown(
        "<div class='ds-card muted'>Built as a portfolio prototype. Production architecture in <a href='https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/02-driftsentinel-model-drift-monitoring/README.md' target='_blank'><code>README.md</code></a>.</div>",
        unsafe_allow_html=True,
    )
