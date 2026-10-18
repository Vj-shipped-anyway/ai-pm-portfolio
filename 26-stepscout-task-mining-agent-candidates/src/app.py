"""StepScout - task mining to agent candidates.

Streamlit walkthrough. Pick one workflow step, then step through the story:
  Step 1  Pick a step
  Step 2  Without StepScout - what the interview map and the log-based list say (red) next to what is
          true about the step in the synthetic data (blue)
  Step 3  With StepScout - the call from observable features, the control screen, the hours at stake
  Step 4  Proof at scale - the top 10 compared, a generated build brief, and what it still gets wrong

All data is synthetic (data/_generate.py, seeded). The classifier is a set of plain rules over observable
features; no model is used anywhere in this app. Hours at stake are modeled with one named assumption.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from step_01_interview_process_map import load_all  # noqa: E402
from step_04_with_stepscout import (  # noqa: E402
    HITL_OVERRIDE, HITL_TEXT, JUDGE_CV, JUDGE_NEED, JUDGE_OVERRIDE, JUDGE_REPEAT, JUDGE_TEXT, REMOVAL_SHARE, TOP_N,
    analyze, step_payload, validate_brief,
)

st.set_page_config(
    page_title="StepScout - Aim the agent at the steps it can take over",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/26-stepscout-task-mining-agent-candidates/README.md"
NIST_URL = "https://www.nist.gov/itl/ai-risk-management-framework"

CLASS_LABEL = {"AGENT": "Agent", "AGENT_HITL": "Agent with a person (HITL)", "HUMAN_JUDGMENT": "Person: judgment",
               "HUMAN_CONTROL": "Person: four-eyes control"}

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.ss-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.ss-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.ss-hero h1 {color: #ffffff !important; font-size: 46px; line-height: 1.12; margin: 0 0 14px 0; font-weight: 700;}
.ss-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.ss-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.ss-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.ss-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.ss-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.ss-card h3 {margin-top: 0; color: #0f172a;}
.ss-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
                border-radius: 6px; font-size: 12px; font-weight: 600; letter-spacing: 0.04em;
                text-transform: uppercase; margin-bottom: 10px;}

/* Verdict card */
.verdict-card {border-radius: 16px; padding: 26px 30px; margin-bottom: 18px; color: #fff;}
.verdict-pass {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.verdict-flag {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.verdict-review {background: linear-gradient(135deg,#b45309,#f59e0b);}
.verdict-card .vlabel {font-size: 13px; opacity: 0.9; letter-spacing: 0.08em; text-transform: uppercase;}
.verdict-card .vbig {font-size: 44px; font-weight: 800; line-height: 1.1; margin: 4px 0 14px 0;}
.verdict-card .vmetric {font-size: 22px; font-weight: 600;}
.verdict-card .vrow {display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px;}
.verdict-card .vchip {background: rgba(255,255,255,0.18); padding: 6px 12px; border-radius: 999px;
                      font-size: 13px; font-weight: 600;}
.verdict-card .vfind {margin-top: 12px; font-size: 15px; line-height: 1.5;}
.verdict-card .vfind .vchip {margin-right: 6px;}
.verdict-card .vtldr {margin-top: 16px; font-size: 15px; line-height: 1.5; opacity: 0.95;}

/* Proof-at-scale metric grid (verdict cards, two across) */
.metric-grid {display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 18px;}
.metric-grid .verdict-card {margin-bottom: 0;}
@media (max-width: 760px) {.metric-grid {grid-template-columns: 1fr;}}

/* Trust panel */
.trust-card {background: #f8fafc; border: 1px solid #cbd5e1; border-left: 5px solid #1f5fb0;
             border-radius: 12px; padding: 20px 24px; margin-bottom: 18px;}
.trust-card h4 {margin: 0 0 10px 0; color: #0f172a; font-size: 16px; letter-spacing: 0.04em;
                text-transform: uppercase;}
.trust-card ul {margin: 6px 0 0 18px; padding: 0;}
.trust-card li {color: #334155; line-height: 1.55;}
.trust-card.quiet {border-left-color: #94a3b8;}
.trust-card.quiet h4 {color: #475569;}
.trust-card.quiet li {color: #64748b; font-size: 14px;}

/* Without / source-of-truth panels */
.bot-bad {background: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #dc2626;
          border-radius: 10px; padding: 14px 18px; color: #7f1d1d;}
.bot-good {background: #ecfdf5; border: 1px solid #bbf7d0; border-left: 4px solid #059669;
           border-radius: 10px; padding: 14px 18px; color: #065f46;}
.bot-truth {background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb;
            border-radius: 10px; padding: 14px 18px; color: #1e3a8a;}
.bot-bad ul, .bot-truth ul, .bot-good ul {margin: 8px 0 0 18px; padding: 0;}
.bot-bad li, .bot-truth li, .bot-good li {line-height: 1.5; margin-bottom: 8px;}
.bot-bad .small {font-size: 13px; opacity: 0.85; margin-top: 8px;}

/* Known-limit note (amber, same palette as the review card) */
.limit-note {background: #fef3c7; border: 1px solid #fde68a; border-left: 5px solid #f59e0b;
             border-radius: 10px; padding: 12px 16px; color: #78350f; font-size: 14px; margin-bottom: 14px;}

/* Buttons - one big primary CTA */
div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#1f5fb0,#163a6c) !important;
  color: #fff !important; border: 0 !important; padding: 14px 28px !important;
  font-size: 17px !important; font-weight: 600 !important; border-radius: 12px !important;
  box-shadow: 0 4px 14px rgba(31,95,176,0.35) !important;
}

h1, h2, h3 {color: #0f172a;}
.muted {color: #64748b; font-size: 14px;}
</style>
""",
    unsafe_allow_html=True,
)


def esc(v) -> str:
    return html.escape(str(v), quote=True)


def num(x, d: int = 0) -> str:
    return f"{x:,.{d}f}"


@st.cache_resource
def load_everything() -> dict:
    data = load_all(DATA_DIR)
    A = analyze(data)
    payloads = [step_payload(data, A, s) for s in data["order"]]
    return {"data": data, "A": A, "P": payloads}


ALL = load_everything()
DATA, A, PAYLOADS = ALL["data"], ALL["A"], ALL["P"]
SC, CP, UT, HD, KN = A["scoring"], A["compare"], A["utility"], A["handling"], A["known"]
DEF = A["deficiencies"]
N_STEPS = len(PAYLOADS)
CAUTIOUS = [m["step"] for m in SC["mismatches"] if m["predicted"] == "AGENT_HITL" and m["truth"] == "AGENT"]

LABEL_TO_INDEX = {f"{p['id']}  -  {p['name']}": i for i, p in enumerate(PAYLOADS)}
LABELS = list(LABEL_TO_INDEX)
# The step shown first: the top-ranked StepScout candidate that the case-system log never records.
_first = next(r["step"] for r in A["ranked"] if not DATA["register"][r["step"]]["status"])
DEFAULT_LABEL = next(lab for lab, i in LABEL_TO_INDEX.items() if PAYLOADS[i]["id"] == _first)

if "step" not in st.session_state:
    st.session_state.step = 1


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='ss-hero'>
  <div class='brand'>🔎 StepScout</div>
  <h1>Aim the agent at the steps it can take over, not the steps that wait the longest.</h1>
  <div class='sub'>In {num(len(DATA['cases']))} synthetic wire-repair cases, the volume-first top {TOP_N} holds {CP['vf_ready']} agent-ready steps and {CP['vf_flagged']} that touch restricted data or a four-eyes control. StepScout's holds {CP['ss_ready']}, with a control screen on every one.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>Rules only, no model</span>
    <span class='pill'>{len(DATA['cases']):,} cases · {N_STEPS} steps · 30 days</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

if st.session_state.step == 1:
    cta_col, _ = st.columns([1, 2])
    with cta_col:
        if st.button("See it in action ->", key="cta_hero", type="primary", use_container_width=True):
            advance(2)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 1 - pick a step
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='ss-card'><span class='ss-step-label'>Step 1</span>"
    "<h3>Pick a workflow step</h3>"
    f"<p class='muted'>{N_STEPS} steps of a modeled bank's wire-repair queue, in workflow order. Twelve are the fixed workflow (S01 to S12); "
    "four were added: S13 is a high-volume judgment step that a volume-first ranking would pick, S14 looks rule-based but hides a judgment, and S15 and S16 are ordinary additions. "
    "The one shown first is the top StepScout candidate that the case-system log never records.</p></div>",
    unsafe_allow_html=True,
)
if "step_choice" not in st.session_state:
    st.session_state.step_choice = DEFAULT_LABEL
st.session_state.step_choice = st.selectbox(
    "Step:",
    LABELS,
    index=LABELS.index(st.session_state.step_choice),
    label_visibility="collapsed",
)
idx = LABEL_TO_INDEX[st.session_state.step_choice]
P = PAYLOADS[idx]
sid = P["id"]

st.markdown(
    "<p class='muted'>How to read the numbers: all data is synthetic and no model is used. Touch time is measured from desktop events. "
    "The answer key is the generator's own and the classifier never reads it. Hours at stake are modeled with one assumption: an agent "
    f"removes {int(REMOVAL_SHARE * 100)}% of a step's touch time.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# STEP 2 - Without StepScout
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='ss-card'><span class='ss-step-label'>Step 2</span>"
        "<h3>Without StepScout - the interview map and the log-based list</h3>"
        "<p class='muted'>Operations teams pick candidates from an interview and from the case system's event log. Here is what each says "
        "about this step, and what is true.</p></div>",
        unsafe_allow_html=True,
    )
    items = []
    if P["on_map"]:
        items.append(f"<li><b>The interview map has it.</b> The expert says {P['sme_minutes']} minutes. Measured: a median of {num(P['median_min'], 1)} minutes a run.</li>")
    else:
        items.append("<li><b>NOT ON THE MAP.</b> The interview describes one happy path, and this step is not on it. Nobody would nominate it from the interview.</li>")
    if P["status"]:
        top = ("It is in the top 10" + (", and by the key it is agent-ready." if P["agent_ready_key"] else ", and by the key it is not agent-ready."))\
            if P["in_vf_top10"] else "It is below the top 10."
        items.append(
            f"<li><b>The log sees it</b> as <code>{esc(P['status'])}</code> and ranks it #{P['log_rank']} by volume times time: {num(P['log_volume'])} events, "
            f"{num(P['log_mean_min'], 1)} minutes on average since the previous status, {num(P['log_hours'])} hours credited against {num(P['touch_hours'], 1)} touch hours. {esc(top)}</li>")
    else:
        items.append("<li><b>NEVER SEEN.</b> The step posts no status, so the log never records that it happened and a list built from it cannot propose it.</li>")
    if P["restricted"] or P["control"] or P["gated_by"]:
        flags = []
        if P["restricted"]:
            flags.append("restricted data")
        if P["control"]:
            flags.append("a four-eyes control")
        if P["gated_by"]:
            flags.append(f"an approval from {P['gated_by']}")
        items.append(f"<li><b>No control screen.</b> The step touches {esc(' and '.join(flags))}; a volume-first list does not say so.</li>")
    red = ("<div class='bot-bad'><b>What the interview map and the log-based list say:</b><ul>" + "".join(items) + "</ul>"
           "<div class='small'>Interview minutes are one expert's estimate. Log hours are time since the previous status, which includes waiting.</div></div>")

    truth = [f"<li>Answer key (the generator's own): <b>{esc(P['key'])}</b>.</li>",
             f"<li>Measured on the desktop: {num(P['runs'])} runs, <b>{num(P['touch_hours'], 1)} touch hours</b> in 30 days, median {num(P['median_min'], 1)} minutes, "
             f"in {esc(', '.join(f'{k} {v} h' for k, v in P['apps'].items()))}.</li>",
             f"<li>Planted behavior: workers override a proposed value in {P['planted']['override_pct']}% of runs, "
             + (f"type about {P['planted']['text']} characters, " if P["planted"]["text"] else "type no free text, ")
             + f"and copy across applications in {P['planted']['xcopy_pct']}% of runs.</li>"]
    if P["planted"]["offdesk_pct"]:
        truth.append(f"<li>A phone call comes before {P['planted']['offdesk_pct']}% of runs: work off the desktop that no file records.</li>")
    blue = "<div class='bot-truth'><b>Source of truth - what is true about this step (synthetic):</b><ul>" + "".join(truth) + "</ul></div>"
    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**This step, measured, next to what was planted**")
        st.dataframe(pd.DataFrame([
            {"measure": "runs in 30 days", "measured": str(P["runs"]), "planted": "-"},
            {"measure": "median minutes a run", "measured": str(P["median_min"]), "planted": str(P["planted"]["median_min"])},
            {"measure": "runs per case that has the step", "measured": str(P["repeats"]), "planted": str(P["planted"]["repeats"])},
            {"measure": "overrides, % of runs", "measured": str(P["override_pct"]), "planted": str(P["planted"]["override_pct"])},
            {"measure": "characters typed a run", "measured": str(P["text"]), "planted": str(P["planted"]["text"])},
            {"measure": "cross-application copy, % of runs", "measured": str(P["xcopy_pct"]), "planted": str(P["planted"]["xcopy_pct"])},
        ]), use_container_width=True, hide_index=True)
        st.markdown("**All steps: interview minutes, log rank and measured touch**")
        rows = []
        for p in PAYLOADS:
            rows.append({"step": p["id"], "name": p["name"], "interview minutes": str(p["sme_minutes"]) if p["on_map"] else "not on the map",
                         "status posted": p["status"] or "none", "log rank": str(p["log_rank"]) if p["log_rank"] else "-",
                         "hours the log credits": str(p["log_hours"]) if p["log_hours"] else "-", "touch hours": p["touch_hours"]})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if st.session_state.step < 3:
        if st.button("See the fix ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With StepScout
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='ss-card'><span class='ss-step-label'>Step 3</span>"
        "<h3>With StepScout - merge, classify, screen, rank</h3>"
        "<p class='muted'>Desktop events give each step its touch time and its observable features. System events anchor the steps in the case. "
        "The class comes from the features and the register, never from the answer key.</p></div>",
        unsafe_allow_html=True,
    )
    chips = [f"<span class='vchip'>Control screen: {esc(P['screen'])}</span>"]
    if P["agent_ready_pred"]:
        chips.append(f"<span class='vchip'>Readiness weight {P['readiness']:.1f}</span>")
    reasons = "".join(f"<div class='vfind'><span class='vchip'>{k + 1}</span>{esc(r)}.</div>" for k, r in enumerate(P["reasons"]))
    notes = "".join(f"<div class='vtldr'>{esc(n)}</div>" for n in P["screen_notes"])
    if P["agent_ready_pred"]:
        metric = f"{num(P['hours_at_stake'], 1)} modeled hours at stake · rank #{P['ss_rank']} of {len(A['ranked'])} candidates"
    else:
        metric = "Not a candidate: it stays with a person"
    if P["correct"]:
        tone, verdict = "verdict-pass", f"Matches the answer key ({esc(P['key'])})."
    elif P["agent_ready_pred"] and not P["agent_ready_key"]:
        tone = "verdict-review"
        verdict = (f"MISSED. The key says {esc(P['key'])}. On the desktop this step is a short pick with tight timing, no free text and no overrides, "
                   "so nothing observable separates it from a rule. The judgment happens in a phone call that no file records.")
    else:
        tone = "verdict-review"
        verdict = f"More cautious than the key ({esc(P['key'])}). The step stays agent-ready with a person reviewing it, which lowers its readiness weight in the ranking."
    st.markdown(
        f"<div class='verdict-card {tone}'>"
        f"<div class='vlabel'>With StepScout - {esc(sid)} {esc(P['name'])}</div>"
        f"<div class='vbig'>{esc(P['predicted'])}</div>"
        f"<div class='vmetric'>{esc(metric)}</div>"
        f"<div class='vrow'>{''.join(chips)}</div>{reasons}{notes}"
        f"<div class='vtldr'>{verdict}</div></div>",
        unsafe_allow_html=True,
    )
    if tone == "verdict-review" and not P["correct"] and P["agent_ready_pred"] and not P["agent_ready_key"]:
        st.markdown("<div class='limit-note'>This is the known miss left in on purpose.</div>", unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**Features the class came from, next to the thresholds**")
        st.dataframe(pd.DataFrame([
            {"feature": "overrides, % of runs", "this step": P["override_pct"], "judgment at": f"{int(JUDGE_OVERRIDE * 100)} or more", "person-in-loop at": f"{int(HITL_OVERRIDE * 100)} or more"},
            {"feature": "characters typed a run", "this step": P["text"], "judgment at": f"{JUDGE_TEXT:.0f} or more", "person-in-loop at": f"{HITL_TEXT:.0f} or more"},
            {"feature": "runs per case", "this step": P["repeats"], "judgment at": f"{JUDGE_REPEAT} or more", "person-in-loop at": "-"},
            {"feature": "timing spread", "this step": P["spread"], "judgment at": f"{JUDGE_CV} or more", "person-in-loop at": "-"},
        ]), use_container_width=True, hide_index=True)
        st.caption(f"Judgment needs at least {JUDGE_NEED} of the four. A step that writes to the payments hub, sends email or reaches a person-in-loop level stays agent-ready with a person approving.")
        fig = go.Figure()
        fig.add_bar(x=list(P["apps"].keys()), y=list(P["apps"].values()), marker_color="#1f5fb0")
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="touch hours in 30 days")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Touch hours by application: work outside the case system never reaches the log.")

    if st.session_state.step < 4:
        if st.button("See the proof at scale ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    d1, d2, d3, d4 = DEF["d1"], DEF["d2"], DEF["d3"], DEF["d4"]
    st.markdown(
        "<div class='ss-card'><span class='ss-step-label'>Step 4</span>"
        f"<h3>Proof at scale - all {N_STEPS} steps</h3>"
        f"<p class='muted'>Scored against the generator's answer key. The key is the generator's own and the signals in the events were planted, "
        "so these numbers show the method works on this data, not on a real queue.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Interview map</div>"
        f"<div class='vbig'>{d1['happy_pct']}%</div>"
        "<div class='vmetric'>of cases took the documented path</div>"
        f"<div class='vtldr'>{d1['variants']} real paths; {d2['off_system_pct']}% of touch time is outside the case system.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>Log-based list, volume first</div>"
        f"<div class='vbig'>{CP['vf_ready']} of {TOP_N}</div>"
        "<div class='vmetric'>agent-ready by the answer key</div>"
        f"<div class='vtldr'>{CP['vf_flagged']} touch restricted data or a four-eyes control, with no control screen. Touch is {d3['touch_share_pct']}% of the elapsed time it counts.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With StepScout</div>"
        f"<div class='vbig'>{CP['ss_ready']} of {TOP_N}</div>"
        "<div class='vmetric'>agent-ready by the answer key</div>"
        f"<div class='vtldr'>{SC['accuracy']} of {SC['n_steps']} steps classified correctly; precision {SC['precision_pct']}% and recall {SC['recall_pct']}% for agent-ready steps.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>Handling time attributed to a named step</div>"
        f"<div class='vbig'>{HD['merged_pct']}%</div>"
        f"<div class='vmetric'>against at most {HD['log_alone_pct']}% from the log alone</div>"
        f"<div class='vtldr'>{HD['recovered_pts']} points recovered. {HD['offdesk_pct']}% stays off the desktop.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    wrong = [
        f"{KN['step']} {KN['name']} is classified {KN['predicted']}; the key says {KN['truth']}. Its timing spread ({KN['cv']:.2f}) is the tightest of any step, it has no free text and almost no overrides, "
        f"but the judgment happens in a phone call no file records. It ranks #{KN['rank']} with {KN['hours_at_stake']:.1f} modeled hours at stake." if KN else "",
        f"Work off the desktop is invisible: {HD['offdesk_hours']:.0f} hours of calls in the data ({HD['offdesk_pct']}% of handling time), plus {HD['unlabeled_pct']}% on the desktop the miner could not label.",
        f"{len(CAUTIOUS)} steps are classified more cautiously than the key ({', '.join(CAUTIOUS)}): they stay agent-ready with a person reviewing.",
        "The thresholds are mine and the signals in the events were planted, so accuracy is a property of this data.",
        "Task mining captures employee desktop activity. That is a privacy and works-council question this prototype only designs for (pseudonymous ids, no keystroke content, aggregate views): designed, not built.",
    ]
    st.markdown("<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>" + "".join(f"<li>{esc(w)}</li>" for w in wrong if w) + "</ul></div>",
                unsafe_allow_html=True)

    st.markdown("**Touch hours by step, coloured by the class StepScout gave it**")
    st.caption("From desktop events. Blue steps are candidates; grey steps stay with a person.")
    colors = {"AGENT": "#059669", "AGENT_HITL": "#1f5fb0", "HUMAN_JUDGMENT": "#94a3b8", "HUMAN_CONTROL": "#64748b"}
    fig = go.Figure()
    for cls in ("AGENT", "AGENT_HITL", "HUMAN_JUDGMENT", "HUMAN_CONTROL"):
        sub = [p for p in PAYLOADS if p["predicted"] == cls]
        fig.add_bar(x=[p["id"] for p in sub], y=[p["touch_hours"] for p in sub], name=CLASS_LABEL[cls], marker_color=colors[cls])
    fig.update_layout(barmode="stack", height=320, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.15),
                      xaxis=dict(categoryorder="array", categoryarray=[p["id"] for p in PAYLOADS]))
    st.plotly_chart(fig, use_container_width=True)

    # ---- one generated build brief --------------------------------------------------------------------
    st.markdown("<div class='ss-card'><span class='ss-step-label'>Hand-off</span><h3>A generated build brief</h3>"
                "<p class='muted'>A build brief is the pack an engineer picks up. The structure is the build-brief/v1 shape; every control and threshold in it is a design "
                "(not tested), and the estimate is the only modeled number.</p></div>", unsafe_allow_html=True)
    BRIEFS = {b["brief_id"]: b for b in A["briefs"]}
    brief_id = st.selectbox("Build brief:", list(BRIEFS), index=0, label_visibility="collapsed")
    B = BRIEFS[brief_id]
    problems = validate_brief(B)
    cand = B["candidate"]
    st.markdown(
        "<div class='bot-good'>"
        f"<b>{esc(B['brief_id'])} · {esc(cand['name'])}</b> · steps {esc(', '.join(cand['steps']))} · class {esc(cand['automation_class'])} · "
        f"schema check: {'valid' if not problems else 'INVALID'}<ul>"
        f"<li><b>In scope:</b> {esc('; '.join(B['scope']['in_scope']))}.</li>"
        f"<li><b>Out of scope:</b> {esc('; '.join(B['scope']['out_of_scope']))}.</li>"
        f"<li><b>Tools:</b> {esc('; '.join(t['name'] + ' (' + t['access'] + '): ' + ', '.join(t['allowed_actions']) for t in B['tools']))}.</li>"
        f"<li><b>Person-in-loop gates:</b> {esc('; '.join(g['step'] + ' - ' + g['reason'] for g in B['controls']['hitl_gates']) or 'none')}.</li>"
        f"<li><b>Four-eyes:</b> {esc('; '.join(g['step'] + ' - ' + g['rule'] for g in B['controls']['four_eyes']) or 'none in this pack')}.</li>"
        f"<li><b>Acceptance (design targets):</b> {esc('; '.join(a['id'] + ' ' + a['metric'] + ' at ' + str(a['threshold']) for a in B['acceptance']))}.</li>"
        f"<li><b>Estimate (modeled):</b> {B['estimate']['hours_at_stake_modeled']} hours at stake. {esc(B['estimate']['assumption'])}</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )
    with st.expander("See the full brief as JSON"):
        st.code(json.dumps(B, indent=2), language="json")

    with st.expander("See the data"):
        st.markdown("**Ranked candidates (modeled hours at stake x readiness)**")
        st.dataframe(pd.DataFrame([{
            "rank": r["rank"], "step": r["step"], "name": r["name"], "class": r["class"], "readiness": r["readiness"],
            "touch hours": round(r["touch_hours"], 1), "hours at stake (modeled)": round(r["hours_at_stake"], 1),
            "control screen": r["screen"]} for r in A["ranked"]]), use_container_width=True, hide_index=True)
        st.markdown("**The two top-10 lists side by side**")
        vf = {r["step"]: r["rank"] for r in A["log"]["candidates"]}
        st.dataframe(pd.DataFrame([{
            "position": i + 1,
            "volume-first": f"{a} {DATA['register'][a]['name']}", "volume-first: agent-ready by key": "yes" if a in SC["true_ready"] else "no",
            "StepScout": f"{b} {DATA['register'][b]['name']}", "StepScout: agent-ready by key": "yes" if b in SC["true_ready"] else "no"}
            for i, (a, b) in enumerate(zip(CP["vf_top10"], CP["ss_top10"]))]), use_container_width=True, hide_index=True)
        st.markdown("**The six deficiencies**")
        st.dataframe(pd.DataFrame([
            {"#": 1, "deficiency": "The interview map covers one path", "number": f"{d1['happy_pct']}% of cases; {d1['variants']} real paths"},
            {"#": 2, "deficiency": "Off-system work is invisible to the log", "number": f"{d2['off_system_pct']}% of touch time outside the case system"},
            {"#": 3, "deficiency": "Elapsed time is mostly wait", "number": f"touch is {d3['touch_share_pct']}% of elapsed time"},
            {"#": 4, "deficiency": "Rework loops are hidden", "number": f"{d4['reopened']} reopened cases, {d4['extra_touch_hours']:.0f} touch hours after the first close"},
            {"#": 5, "deficiency": "Volume-first picks judgment-heavy steps", "number": f"{CP['vf_ready']} of {TOP_N} agent-ready"},
            {"#": 6, "deficiency": "No control screen", "number": f"{CP['vf_flagged']} of {TOP_N} touch restricted data or a four-eyes control"},
        ]), use_container_width=True, hide_index=True)
        st.markdown("**Classification against the answer key**")
        st.dataframe(pd.DataFrame([{
            "step": p["id"], "name": p["name"], "predicted": p["predicted"], "key": p["key"], "match": "yes" if p["correct"] else "no",
            "first reason": p["reasons"][0]} for p in PAYLOADS]), use_container_width=True, hide_index=True)

    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("Task mining", "Recording which application and action a worker uses, with times, to rebuild how work is done. No keystroke content here."),
            ("Touch time", "Minutes a worker is actively working on a step, from desktop events."),
            ("Elapsed time", "Time between two status changes, waiting included."),
            ("AGENT", "Rule-based and data-complete: an agent can do it end to end."),
            ("AGENT_HITL", "An agent drafts or acts and a person approves."),
            ("HUMAN_JUDGMENT", "Leave to a person."),
            ("HUMAN_CONTROL", "A control, such as four-eyes approval, that stays with a person."),
            ("Hours at stake", f"Touch hours in 30 days times {int(REMOVAL_SHARE * 100)}%, the share an agent is assumed to remove. Modeled."),
            ("Build brief", "The pack an engineer picks up: scope, tools, controls, tests and an estimate."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is a desktop-event collector with pseudonymous ids, a step labeler, a merge "
            "with the case-system log, a classifier, a control register, a ranking and a brief writer. It is a design, not deployed; see `ARCHITECTURE.md`. "
            "Hand-off to intake and the business case is by 11 TierGate and 12 ValueLedger, agent permissions by 23 ScopeKeeper, fallback by 25 KillSwitch and "
            "adoption by 21 AdoptionPulse. All designed, none built."
        )
    st.markdown(
        "<div class='ss-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>. Reference: "
        f"<a href='{NIST_URL}' target='_blank'>NIST AI RMF</a>.</div>",
        unsafe_allow_html=True,
    )
