"""EvalForge - Eval-First Console for Regulated AI.

Streamlit walkthrough:
  Hero        - what EvalForge is, with a single CTA
  Step 1      - pick an eval_run_id (default: ER012, the headline catch)
  Verdict     - CI gate PASS / FAIL / REVIEW card
  Trust       - rubric calibration + judge stability signals
  Findings    - per-rubric / per-slice breakdown + human overrides
  Source data - inline CSV viewers for the four sample-data files
  Glossary    - plain-English terms with hyperlinks to the canonical sources
  Production  - Streamlit-vs-production reassessment
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="EvalForge - Eval-First Console for Regulated AI",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
HAMEL_URL = "https://hamel.dev/blog/posts/evals/"
OWASP_URL = "https://owasp.org/www-project-top-10-for-large-language-model-applications/"
NIST_URL = "https://www.nist.gov/itl/ai-risk-management-framework"

PASS_RATE_THRESHOLD = 0.90
KAPPA_THRESHOLD = 0.75
PASS_RATE_REGRESSION_PP = 0.03
PASS_RATE_REGRESSION_FAIL_PP = 0.05

# ---------------------------------------------------------------------------
# Theme - matches LeaseGuard / DriftSentinel: dark gradient hero, white body.
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hide Streamlit chrome */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.ef-hero {
  background: linear-gradient(135deg,#0b132b 0%, #1c2541 50%, #5bc0be 100%);
  border-radius: 18px; padding: 36px 40px; color:#fff; margin-bottom:28px;
}
.ef-hero .brand {font-size:26px; font-weight:600; opacity:0.95; margin-bottom:12px;}
.ef-hero h1 {color:#fff !important; font-size:42px; line-height:1.14; margin:0 0 14px 0; font-weight:700;}
.ef-hero .sub {font-size:17px; line-height:1.5; opacity:0.93; max-width:820px; margin-bottom:22px;}
.ef-hero .pills {display:flex; flex-wrap:wrap; gap:10px;}
.ef-hero .pill {background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
                color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.ef-hero .pill a {color:#fff; text-decoration:none;}

.ef-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:22px 26px;
          margin-bottom:18px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.ef-card h3 {margin-top:0; color:#0f172a;}
.ef-step-label {display:inline-block; background:#1c2541; color:#fff; padding:3px 10px;
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

.trust-card {background:#f8fafc; border:1px solid #cbd5e1; border-left:5px solid #1c2541;
             border-radius:12px; padding:20px 24px; margin-bottom:18px;}
.trust-card h4 {margin:0 0 10px 0; color:#0f172a; font-size:16px; letter-spacing:0.04em;
                text-transform:uppercase;}
.trust-card .tlabel {font-weight:700; color:#1c2541; font-size:13px; letter-spacing:0.04em;
                     text-transform:uppercase; margin-top:12px; display:block;}
.trust-card ul {margin:6px 0 0 18px; padding:0;}
.trust-card li {color:#334155; line-height:1.55;}
.confidence-high {color:#047857; font-weight:700;}
.confidence-med  {color:#b45309; font-weight:700;}
.confidence-low  {color:#b91c1c; font-weight:700;}

div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#1c2541,#0b132b) !important; color:#fff !important;
  border:0 !important; padding:14px 28px !important; font-size:17px !important;
  font-weight:600 !important; border-radius:12px !important;
  box-shadow:0 4px 14px rgba(28,37,65,0.35) !important;
}
h1, h2, h3 {color:#0f172a;}
.muted {color:#64748b; font-size:14px;}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
@st.cache_data
def load_data() -> dict[str, pd.DataFrame]:
    return {
        "probes": pd.read_csv(DATA_DIR / "probes.csv"),
        "rubrics": pd.read_csv(DATA_DIR / "rubrics.csv"),
        "eval_runs": pd.read_csv(DATA_DIR / "eval_runs.csv"),
        "overrides": pd.read_csv(DATA_DIR / "judge_overrides.csv"),
    }


DATA = load_data()


def evaluate_ci_gate(run: pd.Series, baseline_pass_rate: float) -> dict:
    pass_rate = float(run["pass_rate"])
    kappa = float(run["inter_judge_kappa"])
    delta = pass_rate - baseline_pass_rate

    if pass_rate < PASS_RATE_THRESHOLD - 0.02:
        return {
            "verdict": "FAIL",
            "reason": f"Aggregate pass_rate {pass_rate:.3f} below floor {PASS_RATE_THRESHOLD-0.02:.3f}.",
            "action": "Block deploy. Re-run after prompt patch or vendor snapshot pin.",
        }
    if delta < -PASS_RATE_REGRESSION_FAIL_PP:
        return {
            "verdict": "FAIL",
            "reason": (
                f"Regression of {delta*100:+.1f}pp vs rolling baseline {baseline_pass_rate:.3f}."
                " Likely vendor snapshot drift or prompt regression."
            ),
            "action": "Block deploy. Pin to last green snapshot. Investigate root cause.",
        }
    if kappa < KAPPA_THRESHOLD - 0.05:
        return {
            "verdict": "FAIL",
            "reason": f"Inter-judge kappa {kappa:.2f} collapsed below safety floor {KAPPA_THRESHOLD-0.05:.2f}.",
            "action": "Block deploy. Re-anchor rubrics and re-validate judge agreement.",
        }
    if delta < -PASS_RATE_REGRESSION_PP:
        return {
            "verdict": "REVIEW",
            "reason": f"Regression of {delta*100:+.1f}pp vs baseline {baseline_pass_rate:.3f}.",
            "action": "Human sign-off required within 24h or deploy auto-blocks.",
        }
    if kappa < KAPPA_THRESHOLD:
        return {
            "verdict": "REVIEW",
            "reason": f"Inter-judge kappa {kappa:.2f} below target {KAPPA_THRESHOLD:.2f}. Rubric anchor drift suspected.",
            "action": "Recalibrate rubrics before next deploy. L2 trust-and-safety sign-off.",
        }
    return {
        "verdict": "PASS",
        "reason": f"pass_rate={pass_rate:.3f} kappa={kappa:.2f} delta={delta*100:+.1f}pp vs baseline.",
        "action": "Ship.",
    }


def compute_rolling_baseline(runs: pd.DataFrame, eval_run_id: str) -> float:
    idx = runs.index[runs["eval_run_id"] == eval_run_id]
    if len(idx) == 0:
        return float(runs["pass_rate"].iloc[0])
    pos = int(idx[0])
    baseline = float(runs["pass_rate"].iloc[0])
    for i in range(pos):
        if runs["ci_gate_verdict"].iloc[i] == "PASS":
            baseline = float(runs["pass_rate"].iloc[i])
    return baseline


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "step" not in st.session_state:
    st.session_state.step = 1
if "run_choice" not in st.session_state:
    st.session_state.run_choice = "ER012"  # default to the dramatic vendor-update catch


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='ef-hero'>
  <div class='brand'>🧪 EvalForge</div>
  <h1>Catches GenAI behavioral regressions before they ship - not 8 weeks later via the complaint backlog.</h1>
  <div class='sub'>An eval-first console for regulated AI. Versioned probe sets, calibrated rubrics, cross-vendor LLM-as-judge, and a CI gate that blocks the deploy on regression. Sits between your prompt-edit pull request and your production deploy. Turns "ship and pray" GenAI deployments into "evals are the bottleneck" engineering discipline.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>50 historical runs · 60 probes · 12 rubrics</span>
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
# STEP 1 - pick an eval run
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='ef-card'><span class='ef-step-label'>Step 1</span>"
    "<h3>Pick an eval run to inspect</h3>"
    "<p class='muted'>50 historical eval runs across 6 probe-set versions and 3 vendor model snapshots. "
    "The default (ER012) is the headline catch: Anthropic's 2026-02-14 silent snapshot update. "
    "Pass rate dropped 5pp, kappa collapsed, EvalForge's CI gate blocked the deploy.</p></div>",
    unsafe_allow_html=True,
)

run_options = DATA["eval_runs"]["eval_run_id"].tolist()
default_idx = run_options.index("ER012") if "ER012" in run_options else 0
st.session_state.run_choice = st.selectbox(
    "Eval run:",
    run_options,
    index=run_options.index(st.session_state.run_choice) if st.session_state.run_choice in run_options else default_idx,
    label_visibility="collapsed",
    format_func=lambda rid: (
        f"{rid}  -  {DATA['eval_runs'].loc[DATA['eval_runs']['eval_run_id']==rid, 'run_date'].values[0]}"
        f"  -  {DATA['eval_runs'].loc[DATA['eval_runs']['eval_run_id']==rid, 'model_version'].values[0]}"
    ),
)

selected = DATA["eval_runs"][DATA["eval_runs"]["eval_run_id"] == st.session_state.run_choice].iloc[0]
baseline = compute_rolling_baseline(DATA["eval_runs"], st.session_state.run_choice)
gate = evaluate_ci_gate(selected, baseline)
overrides_for_run = DATA["overrides"][DATA["overrides"]["eval_run_id"] == st.session_state.run_choice]

if st.session_state.step < 2:
    if st.button("Run the CI gate  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - verdict card
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    verdict = gate["verdict"]
    if verdict == "PASS":
        verdict_class = "verdict-pass"
        risk = "LOW"
        confidence = "HIGH (>95%)"
        confidence_class = "confidence-high"
        tldr = (
            f"Pass rate {selected['pass_rate']:.2f} above the rolling baseline "
            f"{baseline:.2f}; inter-judge kappa {selected['inter_judge_kappa']:.2f} "
            "above target. Safe to deploy."
        )
    elif verdict == "REVIEW":
        verdict_class = "verdict-review"
        risk = "MEDIUM"
        confidence = "MEDIUM (70-95%)"
        confidence_class = "confidence-med"
        tldr = (
            f"Regression vs baseline {baseline:.2f} or kappa drift detected. "
            "Human L2 trust-and-safety sign-off required within 24h or deploy auto-blocks."
        )
    else:
        verdict_class = "verdict-flag"
        risk = "HIGH"
        confidence = "LOW (<70%)"
        confidence_class = "confidence-low"
        tldr = (
            f"CI gate blocked deploy. Pass rate {selected['pass_rate']:.2f} regressed "
            f"{(selected['pass_rate']-baseline)*100:+.1f}pp vs baseline. Likely a vendor "
            "snapshot update or prompt regression. Pin to last green snapshot."
        )

    st.markdown(
        f"""
<div class='verdict-card {verdict_class}'>
  <div class='vlabel'>EvalForge CI Gate Verdict</div>
  <div class='vbig'>{verdict}</div>
  <div class='vmetric'>{selected['pass_rate']*100:.1f}% pass rate · kappa {selected['inter_judge_kappa']:.2f} · baseline {baseline:.2f}</div>
  <div class='vrow'>
    <span class='vchip'>Risk: {risk}</span>
    <span class='vchip'>Action: {gate['action']}</span>
    <span class='vchip'>Model: {selected['model_version']}</span>
    <span class='vchip'>Probe set: {selected['probe_set_version']}</span>
  </div>
  <div class='vtldr'><b>TL;DR:</b> {tldr}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Trust signals card
    st.markdown(
        f"""
<div class='trust-card'>
  <h4>Trust signals - rubric calibration and judge stability</h4>
  <span class='tlabel'>What we compared against</span>
  <div>Compared this run against the rolling baseline ({baseline:.3f}) and the calibrated rubric set in <a href='https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/04-evalforge-llm-eval-platform/data/rubrics.csv' target='_blank'><code>data/rubrics.csv</code></a>. CI gate thresholds: pass-rate floor 0.88, regression-warn at -3pp, regression-block at -5pp, kappa target 0.75.</div>
  <span class='tlabel'>Inter-judge agreement (kappa)</span>
  <div>{selected['inter_judge_kappa']:.2f} for this run. Target: at or above 0.75. Anything below 0.70 trips a hard fail.</div>
  <span class='tlabel'>Judge configuration</span>
  <div>Judge ID: <code>{selected['judge_id']}</code>. Snapshot pin: <code>{selected['judge_snapshot']}</code>. Snapshot pin matters because a silently-updated judge produces silently-drifting scores.</div>
  <span class='tlabel'>Human overrides recorded this run</span>
  <div>{len(overrides_for_run)} override events. Clusters on specific rubrics or reviewers signal calibration drift.</div>
  <span class='tlabel'>Confidence level</span>
  <div class='{confidence_class}'>{confidence}</div>
  <span class='tlabel'>What this does NOT cover</span>
  <ul>
    <li>Live customer traffic - this is pre-deploy eval only; production observability covered by <a href='https://github.com/Vj-shipped-anyway/ai-pm-portfolio/tree/main/02-driftsentinel-model-drift-monitoring' target='_blank'>DriftSentinel</a>.</li>
    <li>Prompt-injection defense - covered by Project 06 (PromptShield), separately scoped.</li>
    <li>Agent reliability - covered by Project 05 (AgentWatch).</li>
  </ul>
</div>
""",
        unsafe_allow_html=True,
    )

    # Detailed findings
    with st.expander("Detailed findings - human overrides in this run", expanded=(verdict != "PASS")):
        if len(overrides_for_run) == 0:
            st.markdown("No human overrides recorded for this run. Clean judge-human agreement.")
        else:
            st.dataframe(
                overrides_for_run[
                    ["override_id", "probe_id", "rubric_id", "judge_score", "human_score",
                     "reviewer_id", "override_reason", "deficiency_class_addressed"]
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.markdown(
                f"_{len(overrides_for_run)} override(s) on this run. Clusters by rubric or reviewer "
                "indicate where calibration is drifting._"
            )

    if st.session_state.step < 3:
        if st.button("See the source data  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - inline source data viewers
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='ef-card'><span class='ef-step-label'>Step 3</span>"
        "<h3>Source of truth - inspect the four data tables</h3>"
        "<p class='muted'>Every number above is derived from these four CSVs. Expand any block "
        "to see the raw rows. Same files live in <a href='https://github.com/Vj-shipped-anyway/ai-pm-portfolio/tree/main/04-evalforge-llm-eval-platform/data' target='_blank'>the repo</a>.</p></div>",
        unsafe_allow_html=True,
    )

    with st.expander("probes.csv - the 60 versioned eval probes", expanded=False):
        st.caption(
            "Versioned probe set. Each probe is one question + expected behavior contract. "
            "Tagged by which of the six EvalForge deficiencies it surfaces, by behavioral slice, and by severity."
        )
        st.dataframe(DATA["probes"], use_container_width=True, hide_index=True)
        st.caption(f"{len(DATA['probes'])} rows. Source: data/probes.csv in the repo.")

    with st.expander("rubrics.csv - the 12 calibrated rubric criteria", expanded=False):
        st.caption(
            "The scoring rubric the LLM-as-judge applies. Each criterion has worked anchors at scores 1, 3, and 5 - "
            "the calibration that drives inter-rater agreement above 0.78 in the historical dataset."
        )
        st.dataframe(DATA["rubrics"], use_container_width=True, hide_index=True)
        st.caption(f"{len(DATA['rubrics'])} rows. Source: data/rubrics.csv in the repo.")

    with st.expander("eval_runs.csv - 50 historical eval runs across 6 model versions", expanded=False):
        st.caption(
            "The flight log. Each row is one nightly or pre-deploy eval run with model snapshot, probe-set version, "
            "judge config, inter-judge kappa, and CI gate verdict. ER012 (2026-02-17) and ER038 (2026-06-01) are the "
            "two silent-vendor-update catches."
        )
        st.dataframe(DATA["eval_runs"], use_container_width=True, hide_index=True)
        st.caption(f"{len(DATA['eval_runs'])} rows. Source: data/eval_runs.csv in the repo.")

    with st.expander("judge_overrides.csv - 30 human-overrode-the-judge events", expanded=False):
        st.caption(
            "Every time a human reviewer disagreed with the LLM-as-judge's score, the override is logged with the "
            "reason. Clusters reveal calibration drift - the data behind the human-override audit (deficiency #6)."
        )
        st.dataframe(DATA["overrides"], use_container_width=True, hide_index=True)
        st.caption(f"{len(DATA['overrides'])} rows. Source: data/judge_overrides.csv in the repo.")

    if st.session_state.step < 4:
        if st.button("Download the evidence bundle  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - workpaper download + glossary + production reassessment
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='ef-card'><span class='ef-step-label'>Step 4</span>"
        "<h3>CI gate evidence bundle</h3>"
        "<p class='muted'>An auto-assembled bundle for the AI platform engineering lead, L2 trust-and-safety, "
        "and the model validator. Routes into the bank's GRC tool (Archer / ServiceNow GRC) and the LineageLog "
        "audit trail (Project 09).</p></div>",
        unsafe_allow_html=True,
    )

    workpaper = (
        f"# EvalForge CI Gate Evidence Bundle\n\n"
        f"**Eval run:** {selected['eval_run_id']}\n\n"
        f"**Run date:** {selected['run_date']}\n\n"
        f"**Model version:** {selected['model_version']}\n\n"
        f"**Probe set version:** {selected['probe_set_version']}\n\n"
        f"**Judge ID + snapshot:** {selected['judge_id']} ({selected['judge_snapshot']})\n\n"
        f"**Pass rate:** {selected['pass_rate']:.3f}\n\n"
        f"**Rolling baseline:** {baseline:.3f}\n\n"
        f"**Inter-judge kappa:** {selected['inter_judge_kappa']:.2f}\n\n"
        f"**CI gate verdict:** {gate['verdict']}\n\n"
        f"**Reason:** {gate['reason']}\n\n"
        f"**Action:** {gate['action']}\n\n"
        f"**Human overrides recorded:** {len(overrides_for_run)}\n\n"
        f"**Source of truth:** [data/eval_runs.csv](https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/04-evalforge-llm-eval-platform/data/eval_runs.csv)\n"
    )
    st.download_button(
        "Download evidence bundle (Markdown)",
        workpaper,
        file_name=f"evalforge_bundle_{selected['eval_run_id']}.md",
        mime="text/markdown",
    )

    with st.expander("Audit pack - what is in the bundle"):
        st.markdown(
            "- **Source of truth:** [`data/eval_runs.csv`](https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/04-evalforge-llm-eval-platform/data/eval_runs.csv) (50 historical runs)\n"
            "- **Probe set:** [`data/probes.csv`](https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/04-evalforge-llm-eval-platform/data/probes.csv) (60 versioned probes)\n"
            "- **Rubric set:** [`data/rubrics.csv`](https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/04-evalforge-llm-eval-platform/data/rubrics.csv) (12 calibrated criteria)\n"
            "- **Override log:** [`data/judge_overrides.csv`](https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/04-evalforge-llm-eval-platform/data/judge_overrides.csv) (30 human-judge disagreements)\n"
            "- **Primary judge:** Anthropic Claude Sonnet (snapshot-pinned)\n"
            "- **Secondary judge:** Azure OpenAI GPT-4o (cross-vendor cross-check)\n"
            "- **CI gate:** GitHub Actions / Argo CD pre-deploy hook\n"
            "- **Audit trail handoff:** Project 09 LineageLog - decision lineage event emitted per run"
        )

    # ---------------------------------------------------------------------------
    # GLOSSARY - plain-English definitions
    # ---------------------------------------------------------------------------
    with st.expander("Glossary - what these terms mean"):
        glossary_df = pd.DataFrame(
            [
                ("Eval (evaluation)", "A test that asks a model a question and checks if the answer matches what we expected. The eval set is the regression suite."),
                ("Probe", "One question in the eval set, plus a documented expected behavior. Versioned and severity-tagged."),
                ("Probe set", "A Git-tagged collection of probes. The version pin matters: comparing ER001 to ER050 only makes sense if you know which probe set each used."),
                ("Rubric", "The scoring criteria a judge (human or LLM) applies. Anchored at 1, 3, and 5 with worked examples so different judges score consistently."),
                ("LLM-as-judge", "Using a second LLM (Claude, GPT-4o) to score the primary model's output against a rubric. Cheaper and faster than human review; needs calibration and snapshot pinning."),
                ("Inter-judge kappa", "Cohen's kappa - a statistical measure of agreement between two judges. Above 0.78 is solid; below 0.70 means the rubric is unstable."),
                ("CI gate", "Continuous-integration deployment gate. The eval result blocks or allows the production deploy. PASS / FAIL / REVIEW."),
                ("Behavioral regression", "Same question, plausible answer, but subtly worse than yesterday. The class of regression a basic eval set misses."),
                ("Vendor silent snapshot update", "When Anthropic, Azure OpenAI, or AWS Bedrock pushes a minor model update without changing the API contract. The reference incident here is Anthropic's 2026-02-14 update."),
                ("Calibration anchor", "A worked example for a specific rubric score. 'A score of 5 means refusal + correct routing; a score of 3 means refusal but no routing.' Closes the inter-rater gap."),
                ("Rolling baseline", "The pass rate of the last green eval run. The CI gate compares each new run against the rolling baseline, not a fixed threshold."),
                ("Probe slice", "A behavioral subset of probes - refusal_edge, fraud_workflow, pii_refusal. Slice-level pass rate catches what aggregate hides."),
                ("Human override audit", "The log of every time a reviewer overrode an LLM-as-judge score, with reason. The data behind catching calibration drift."),
                ("Eval-first thesis", "Hamel Husain's framing: build the eval set before the model, treat it as the moat, run it on every change. See the link in the trust card."),
            ],
            columns=["Term", "Plain English"],
        )
        st.dataframe(glossary_df, use_container_width=True, hide_index=True)

    with st.expander("References - canonical sources behind the deficiency taxonomy"):
        st.markdown(
            f"- **Hamel Husain on evals** - [hamel.dev/blog/posts/evals/]({HAMEL_URL}) - the eval-first thesis. The reason every probe and rubric in this repo is committed before any model code.\n"
            f"- **OWASP LLM Top 10** - [owasp.org/llm-top-10]({OWASP_URL}) - LLM09 (Misinformation), LLM06 (Sensitive Info Disclosure), LLM10 (Model Theft). The framing behind the high-severity slice weights.\n"
            f"- **NIST AI RMF** - [nist.gov/itl/ai-risk-management-framework]({NIST_URL}) - 'Measure' function maps cleanly to versioned probe sets + calibrated rubrics.\n"
            "- **Greg Kamradt - needle-in-haystack** - long-context evals; reason multi-hop is a separate slice in the EvalForge taxonomy.\n"
        )

    # ---------------------------------------------------------------------------
    # PRODUCTION STACK REASSESSMENT
    # ---------------------------------------------------------------------------
    with st.expander("What this would look like as a client-facing SaaS"):
        st.markdown(
            "**Production stack reassessment** - strengthening the Streamlit-vs-production framing with the SaaS shape a buyer would actually procure.\n\n"
            "If EvalForge were a real product shipping to a bank's AI platform org:\n\n"
            "- **Frontend:** Next.js 15 + Tailwind + shadcn/ui - embedded as a panel inside the bank's AI platform console (Vertex AI Studio, Azure AI Foundry, AWS SageMaker), not a standalone app.\n"
            "- **Auth:** SAML / OIDC with the bank's IdP (Okta, ForgeRock, PingFederate); RBAC mapping L1 product owner / L2 trust-and-safety / L3 compliance / L4 audit roles.\n"
            "- **Backend:** FastAPI on the bank's existing K8s footprint (EKS / GKE / AKS); microservice per check (probe runner, judge orchestrator, kappa calculator, CI gate evaluator, override audit).\n"
            "- **Probe registry:** Postgres with row-level versioning; probe set diffs surfaced as Git-style commits the L2 team reviews.\n"
            "- **Rubric calibration:** Snowflake for the historical scoring data; calibration anchor diffs surfaced as audit events.\n"
            "- **Judge models:** Anthropic Claude (primary) + Azure OpenAI GPT-4o (secondary) + a fine-tuned Llama 3.1 8B (tertiary, fully in-VPC). Cross-vendor kappa is the calibration signal.\n"
            "- **CI gate:** GitHub Actions / Argo CD pre-deploy hook; verdict posted as a PR check. FAIL blocks merge; REVIEW requires L2 approval within 24h.\n"
            "- **Observability:** OpenTelemetry traces; Langfuse for judge prompt traces; Datadog for SLO breaches.\n"
            "- **Compliance:** SOC 2 Type II baseline; SR 11-7 alignment for the regression-detection layer; NIST AI RMF 'Measure' function as the design target.\n"
            "- **Governance:** Native integration with the bank's GRC tool (Archer, ServiceNow GRC, MetricStream); each blocked deploy auto-files an evidence bundle and routes to the correct L2 queue.\n\n"
            "The Streamlit prototype here proves the *product mechanic* - that a versioned probe set + calibrated rubric + cross-vendor judge + CI gate catches silent vendor-snapshot regressions on first eval run. The production architecture above is what the seat I'm pursuing actually delivers."
        )

    st.markdown(
        "<div class='ef-card muted'>"
        "Built as a portfolio prototype. Full PRD, architecture, and step-script walkthrough in the <a href='https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/04-evalforge-llm-eval-platform/README.md' target='_blank'><code>README.md</code></a>."
        "</div>",
        unsafe_allow_html=True,
    )
