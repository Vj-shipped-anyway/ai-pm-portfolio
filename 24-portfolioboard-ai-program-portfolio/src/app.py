"""PortfolioBoard - an AI program portfolio run on gate evidence, capacity and dependencies.

Streamlit walkthrough. Pick one program, then step through the story:
  Step 1  Pick a program
  Step 2  Without PortfolioBoard - the status the owner picked (red card) beside the gate evidence
          and dependency truth (blue card)
  Step 3  With PortfolioBoard - evidence status, what blocks the program, the capacity shortfall
          and what to pause, fund or defer
  Step 4  Proof at scale - the same measures over all 30 programs, with the known limit

All data is synthetic (data/_generate.py, seeded). Status, capacity, dependency and pull rules are
plain rules; there is no model anywhere in this app.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from step_01_rag_status_report import (TEAM_LABEL, TEAMS, load_all, summarize as summarize_step1, usd_m)  # noqa: E402
from step_02_rag_attention_list import summarize as summarize_step2  # noqa: E402
from step_03_deficiencies_exposed import summarize as summarize_step3  # noqa: E402
from step_04_with_portfolioboard import analyze  # noqa: E402

st.set_page_config(
    page_title="PortfolioBoard - An AI portfolio run on evidence, not red-amber-green",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/24-portfolioboard-ai-program-portfolio/README.md"
NIST_URL = "https://www.nist.gov/itl/ai-risk-management-framework"

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.pb-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.pb-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.pb-hero h1 {color: #ffffff !important; font-size: 40px; line-height: 1.15; margin: 0 0 14px 0; font-weight: 700;}
.pb-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.pb-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.pb-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.pb-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.pb-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.pb-card h3 {margin-top: 0; color: #0f172a;}
.pb-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
                border-radius: 6px; font-size: 12px; font-weight: 600; letter-spacing: 0.04em;
                text-transform: uppercase; margin-bottom: 10px;}

/* Verdict card */
.verdict-card {border-radius: 16px; padding: 26px 30px; margin-bottom: 18px; color: #fff;}
.verdict-pass {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.verdict-flag {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.verdict-review {background: linear-gradient(135deg,#b45309,#f59e0b);}
.verdict-card .vlabel {font-size: 13px; opacity: 0.9; letter-spacing: 0.08em; text-transform: uppercase;}
.verdict-card .vbig {font-size: 40px; font-weight: 800; line-height: 1.1; margin: 4px 0 14px 0;}
.verdict-card .vmetric {font-size: 20px; font-weight: 600;}
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

/* Bot vs truth panel */
.bot-bad {background: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #dc2626;
          border-radius: 10px; padding: 14px 18px; color: #7f1d1d;}
.bot-good {background: #ecfdf5; border: 1px solid #bbf7d0; border-left: 4px solid #059669;
           border-radius: 10px; padding: 14px 18px; color: #065f46;}
.bot-truth {background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb;
            border-radius: 10px; padding: 14px 18px; color: #1e3a8a;}
.bot-bad ul, .bot-truth ul {margin: 8px 0 0 18px; padding: 0;}
.bot-bad li, .bot-truth li {line-height: 1.5; margin-bottom: 8px;}
.bot-truth li ul {margin-top: 4px;}
.bot-truth li li {margin-bottom: 2px;}
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


BAD = {"GREEN": 0, "AMBER": 1, "RED": 2}


@st.cache_resource
def load_analysis() -> dict:
    a = analyze(load_all(DATA_DIR))
    data = a["data"]
    a["s1"] = summarize_step1(data)
    a["s2"] = summarize_step2(data)
    a["s3"] = summarize_step3(data)
    return a


A = load_analysis()
DATA = A["data"]
S = A["summary"]
S1, S2, S3 = A["s1"], A["s2"], A["s3"]
ROWS = {r["program_id"]: r for r in A["rows"]}
TRUTH = DATA["truth"]
PROG = DATA["prog"]
CRIT = DATA["crit"]

# Option labels are plain strings; a dict maps label -> program id. Biggest contradictions first.
_ordered = sorted(A["rows"], key=lambda r: (-(BAD[r["board"]] - BAD[r["reported"]]), -r["est_benefit_usd"], r["program_id"]))
LABEL_TO_PID = {f"{r['program_id']}  {r['name']}  -  reported {r['reported'].lower()}  -  board {r['board']}": r["program_id"]
                for r in _ordered}
LABELS = list(LABEL_TO_PID)
WRONG_SHOWN = " or ".join(sorted({r["board"] for r in A["board_wrong"]}))

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
<div class='pb-hero'>
  <div class='brand'>🧭 PortfolioBoard</div>
  <h1>An AI portfolio run on gate evidence, capacity and dependencies, not red-amber-green: {S['changed']} of {S['programs']} statuses change.</h1>
  <div class='sub'>Owners pick their own status, so the report cannot show which green programs fail their gates, where reviewers run short or what waits on a slipped upstream program. PortfolioBoard reads the evidence instead.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>No model: plain rules</span>
    <span class='pill'>{S['programs']} programs · {S1['criteria']} gate criteria · {len(TEAMS)} teams · {len(DATA['quarters'])} quarters</span>
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
# STEP 1 - pick a program
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='pb-card'><span class='pb-step-label'>Step 1</span>"
    "<h3>Pick a program</h3>"
    f"<p class='muted'>{S['programs']} AI programs at a modeled bank. The first one is where the owner's "
    "status and the evidence disagree most.</p></div>",
    unsafe_allow_html=True,
)
if "prog_choice" not in st.session_state:
    st.session_state.prog_choice = LABELS[0]
st.session_state.prog_choice = st.selectbox(
    "Program:",
    LABELS,
    index=LABELS.index(st.session_state.prog_choice),
    label_visibility="collapsed",
)
pid = LABEL_TO_PID[st.session_state.prog_choice]
r = ROWS[pid]
p = PROG[pid]
t = TRUTH[pid]

st.markdown(
    f"<p class='muted'>How to read the numbers: synthetic data, no model. The programs, owners and teams are made up; "
    "nothing here is a real bank, program or incident. The generator decided which evidence is missing, stale or "
    "false, so the truth is known. Status, capacity, dependency and pause rules are plain rules. Benefit figures "
    "are owner estimates, never measured.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# STEP 2 - Without PortfolioBoard: the failure
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='pb-card'><span class='pb-step-label'>Step 2</span>"
        "<h3>Without PortfolioBoard - the owner picks the color</h3>"
        "<p class='muted'>This is what the program office receives each month, next to the gate evidence and "
        "dependencies that sit behind the same program.</p></div>",
        unsafe_allow_html=True,
    )

    true_status = t["true_status"]
    if r["reported"] == "GREEN" and true_status != "GREEN":
        stamp = "MISSED"
    elif r["reported"] != true_status:
        stamp = "WRONG"
    else:
        stamp = "MATCHES, WITH NOTHING BEHIND IT"
    on_list = r["reported"] != "GREEN"
    red_items = [
        f"<li>Owner <b>{esc(p['owner'])}</b> reports <b>{esc(r['reported'])}</b> for <b>{esc(p['name'])}</b> "
        f"(stage: {esc(p['stage'])}).</li>",
        f"<li>Estimated benefit {esc(usd_m(p['est_benefit_usd']))} at the owner's confidence of "
        f"{esc(p['benefit_confidence'])}; target quarter {esc(p['target_quarter'])}.</li>",
        "<li>The report carries no gate evidence, no capacity, no dependencies and no work in progress.</li>",
        f"<li>On the attention list (amber or red as reported): <b>{'yes' if on_list else 'no'}</b>.</li>",
    ]
    red = (
        f"<div class='bot-bad'><b>What the monthly report says ({esc(stamp)}):</b>"
        "<ul>" + "".join(red_items) + "</ul>"
        "<div class='small'>The report is the owner's judgment. Nothing in it can be checked.</div></div>"
    )

    ev_rows = DATA["ev_by_prog"][pid]
    unmet = [e for e in ev_rows if not e["met"]]
    stale = [e for e in ev_rows if e["met"] and e["age"] > CRIT[e["criterion_id"]]["max_age_days"]]
    blue_items = [
        f"<li>{len(ev_rows)} gate criteria are in force at stage {esc(p['stage'])}: {len(ev_rows) - len(unmet) - len(stale)} "
        f"met with fresh evidence, {len(stale)} met with stale evidence, {len(unmet)} not met.</li>"
    ]
    if unmet:
        blue_items.append("<li>Not met: " + "; ".join(
            f"{esc(CRIT[e['criterion_id']]['criterion'])} ({esc(CRIT[e['criterion_id']]['attested_by'])})" for e in unmet) + "</li>")
    if stale:
        blue_items.append("<li>Stale: " + "; ".join(
            f"{esc(CRIT[e['criterion_id']]['criterion'])}, {e['age']} days old against {CRIT[e['criterion_id']]['max_age_days']}"
            for e in stale) + "</li>")
    if r["slipped"]:
        blue_items.append(f"<li>Slipped: the target quarter {esc(p['target_quarter'])} has passed and the program is not at scale.</li>")
    ups = DATA["ups"].get(pid, [])
    if ups:
        inner = "".join(
            f"<li>{esc(u)} {esc(PROG[u]['name'])}: board {esc(ROWS[u]['board'])}"
            f"{', slipped' if ROWS[u]['slipped'] else ''}</li>" for u in ups)
        blue_items.append(f"<li>Depends on:<ul>{inner}</ul></li>")
    else:
        blue_items.append("<li>Depends on no other program.</li>")
    truth_line = f"The generator's true status for this program: <b>{esc(true_status)}</b>."
    if t["false_attestation"]:
        truth_line += (f" It planted one false attestation here: {esc(CRIT[t['false_attestation']]['criterion'])} "
                       "is marked met with fresh evidence and is not truly met.")
    blue_items.append(f"<li>{truth_line}</li>")
    blue = ("<div class='bot-truth'><b>Source of truth - gate evidence and dependencies:</b>"
            "<ul>" + "".join(blue_items) + "</ul></div>")

    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**Gate evidence for this program (attested by the owner and review teams)**")
        edf = pd.DataFrame([{
            "criterion": f"{e['criterion_id']} {CRIT[e['criterion_id']]['criterion']}",
            "gate": CRIT[e["criterion_id"]]["gate_name"], "attested by": CRIT[e["criterion_id"]]["attested_by"],
            "met": "yes" if e["met"] else "no", "evidence age (days)": str(e["age"]) if e["age"] is not None else "-",
            "max age (days)": CRIT[e["criterion_id"]]["max_age_days"],
            "stale": "yes" if (e["met"] and e["age"] > CRIT[e["criterion_id"]]["max_age_days"]) else "no"}
            for e in ev_rows])
        st.dataframe(edf, use_container_width=True, hide_index=True)
        st.markdown("**Dependencies**")
        ddf = pd.DataFrame([{"depends on": d["depends_on"], "name": PROG[d["depends_on"]]["name"], "type": d["dep_type"],
                             "board status": ROWS[d["depends_on"]]["board"]}
                            for d in DATA["deps"] if d["program_id"] == pid])
        if len(ddf):
            st.dataframe(ddf, use_container_width=True, hide_index=True)
        else:
            st.markdown("No dependencies.")
        st.markdown("**Planned demand (FTE) by team and quarter**")
        dem = pd.DataFrame([{"team": TEAM_LABEL[d["team"]], "quarter": d["quarter"], "need (FTE)": d["need_fte"]}
                            for d in DATA["demand"] if d["program_id"] == pid])
        if len(dem):
            st.dataframe(dem.pivot_table(index="team", columns="quarter", values="need (FTE)", aggfunc="sum")
                         .reset_index(), use_container_width=True, hide_index=True)

    if st.session_state.step < 3:
        if st.button("See the fix  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With PortfolioBoard: status, blockers, capacity, pause or fund
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='pb-card'><span class='pb-step-label'>Step 3</span>"
        f"<h3>With PortfolioBoard - {esc(p['name'])} is read from the evidence</h3>"
        "<p class='muted'>PortfolioBoard reads the gate evidence, follows the dependencies, checks the reviewer "
        "capacity and the stage's work in progress, then suggests what to do.</p></div>",
        unsafe_allow_html=True,
    )
    if r["board"] != r["reported"]:
        word = f"FLAGGED {r['board']}"
        line = f"The owner reported {r['reported']}. Gate evidence, schedule and dependencies say {r['board']}."
    else:
        word = f"CONFIRMED {r['board']}"
        line = f"The owner reported {r['reported']} and the evidence agrees."
    chips = [f"Action this quarter: {r['action']}"]
    if r["blocked_by"]:
        chips.append("Blocked by " + ", ".join(f"{i['program_id']} ({i['why']})" for i in r["blocked_by"]))
    if r["slipped"]:
        chips.append(f"Slipped: target {r['target_quarter']}")
    for st_ in r["short_teams"]:
        chips.append(f"{TEAM_LABEL[st_['team']]} {st_['ratio_pct']}% subscribed in {S['plan_quarter']} before any pause: "
                     f"needs {st_['need']:.2f} FTE, pro-rata share {st_['pro_rata']:.2f}")
    if r["evidence_status"] == "RED":
        chips.append(f"Benefit at risk (modeled): {usd_m(r['est_benefit_usd'])}")
    st.markdown(
        "<div class='verdict-card verdict-pass'>"
        f"<div class='vlabel'>With PortfolioBoard - {esc(pid)} {esc(p['name'])}</div>"
        f"<div class='vbig'>{esc(word)}</div>"
        f"<div class='vmetric'>{esc(line)}</div>"
        "<div class='vrow'>" + "".join(f"<span class='vchip'>{esc(c)}</span>" for c in chips) + "</div>"
        f"<div class='vfind'><b>Why:</b> {esc(r['reason'])}</div>"
        f"<div class='vtldr'><b>What to do:</b> {esc(r['action'])} - {esc(r['action_reason'])}.</div></div>",
        unsafe_allow_html=True,
    )
    if r["board"] != t["true_status"]:
        why_missed = ("one criterion here was attested met with fresh evidence while not truly met, and nothing in the "
                      "file reveals it" if t["false_attestation"] else "the evidence it reads is not the whole truth")
        st.markdown(
            f"<div class='limit-note'>Known limit. The board shows {esc(r['board'])}, but the generator's true status is "
            f"{esc(t['true_status'])}. The board reads attested evidence: {esc(why_missed)}.</div>",
            unsafe_allow_html=True,
        )
    elif r["stale"]:
        st.markdown(
            "<div class='limit-note'>Stale evidence is marked, not judged. The board cannot tell whether a criterion "
            "attested months ago still holds.</div>",
            unsafe_allow_html=True,
        )

    with st.expander("See the data"):
        st.markdown("**Capacity grid (demand / supply in FTE)**")
        grid = pd.DataFrame([{"team": TEAM_LABEL[c["team"]], "quarter": c["quarter"],
                              "demand / supply": f"{c['demand']:.1f} / {c['supply']:.1f}", "over": "yes" if c["over"] else "no"}
                             for c in A["board"]["grid"]])
        st.dataframe(grid.pivot_table(index="team", columns="quarter", values="demand / supply", aggfunc="first")
                     .reset_index(), use_container_width=True, hide_index=True)
        st.markdown("**This program's action by quarter (model risk review)**")
        st.dataframe(pd.DataFrame([{"quarter": q, "action": a_} for q, a_ in r["actions"].items()]),
                     use_container_width=True, hide_index=True)
        st.markdown("**Stage work in progress against its limit**")
        wdf = pd.DataFrame([{"stage": w["stage"], "work in progress": w["wip"], "limit": w["limit"],
                             "above limit": "yes" if w["over"] else "no",
                             "WIP / throughput (weeks)": f"{w['little_weeks']:.1f}" if w["little_weeks"] is not None else "-"}
                            for w in A["pull"]["wip"]])
        st.dataframe(wdf, use_container_width=True, hide_index=True)

    lines = [f"# PortfolioBoard program evidence: {pid} {p['name']}", "",
             "Synthetic data. Written by the PortfolioBoard prototype; not a real bank, program or incident.", "",
             f"- Stage: {p['stage']}; owner {p['owner']}; target quarter {p['target_quarter']}",
             f"- Owner's status: {r['reported']}; board status: {r['board']}",
             f"- Action this quarter: {r['action']} ({r['action_reason']})",
             f"- Why: {r['reason']}",
             f"- Owner-estimated benefit (not measured): {usd_m(p['est_benefit_usd'])}", ""]
    st.download_button("Download program evidence (Markdown)", "\n".join(lines),
                       file_name=f"portfolioboard_{pid}.md", mime="text/markdown")

    if st.session_state.step < 4:
        if st.button("See the proof at scale  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='pb-card'><span class='pb-step-label'>Step 4</span>"
        "<h3>Proof at scale</h3>"
        f"<p class='muted'>The same checks over all {S['programs']} programs, {S1['criteria']} gate criteria and "
        f"{len(TEAMS)} teams over {len(DATA['quarters'])} quarters.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Without PortfolioBoard: the report</div>"
        f"<div class='vbig'>{S3['a_green_fail']} of {S3['green_reported']}</div>"
        "<div class='vmetric'>programs reported green fail a gate criterion</div>"
        "<div class='vtldr'>The report carries no evidence, so nothing in it can show this.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>Without PortfolioBoard: capacity</div>"
        f"<div class='vbig'>{S['cells_over_before']} of {S['cells']}</div>"
        f"<div class='vmetric'>team-quarters where demand exceeds supply</div>"
        f"<div class='vtldr'>Model risk review is short in {S['mr_over_before']} of {S['mr_quarters']} quarters.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With PortfolioBoard: status</div>"
        f"<div class='vbig'>{S['changed']} of {S['programs']}</div>"
        "<div class='vmetric'>statuses change once evidence is applied</div>"
        f"<div class='vtldr'>True status shown for {S['board_correct']} of {S['programs']} programs, "
        f"against {S['rag_correct']} of {S['programs']} in the report.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With PortfolioBoard: benefit at risk (modeled)</div>"
        f"<div class='vbig'>{usd_m(S['benefit_red_by_evidence'])} of {usd_m(S['benefit_total'])}</div>"
        "<div class='vmetric'>owner-estimated benefit on red-by-evidence programs</div>"
        f"<div class='vtldr'>The report shows {usd_m(S3['e_benefit_reported_red'])} as red.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>"
        f"<li>Status is only as good as the self-attested evidence. {S['planted_false_attestations']} programs show "
        f"{esc(WRONG_SHOWN)} while their true status is RED: one criterion was attested met with fresh evidence and is not "
        "truly met. The board cannot see that.</li>"
        f"<li>{S['stale_programs']} of {S['programs']} programs have a criterion marked met with evidence older than its "
        "freshness rule. The board marks them; it cannot tell whether they still hold.</li>"
        f"<li>Agreement with the truth ({S['board_correct']} of {S['programs']}) is by construction: the board and the "
        f"generator apply the same stated rules, apart from the {S['planted_false_attestations']} planted false attestations. "
        "Benefit figures are owner estimates, never measured benefit.</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Where reviewers run short**")
    st.caption("Model risk review and security review: planned demand against supply, in FTE.")
    fig = go.Figure()
    for team, col in (("model_risk_review", "#b91c1c"), ("security_review", "#f59e0b")):
        cells = [c for c in A["board"]["grid"] if c["team"] == team]
        fig.add_bar(x=[c["quarter"] for c in cells], y=[c["demand"] for c in cells], name=f"{TEAM_LABEL[team]} demand",
                    marker_color=col)
        fig.add_scatter(x=[c["quarter"] for c in cells], y=[c["supply"] for c in cells], mode="lines+markers",
                        name=f"{TEAM_LABEL[team]} supply", line=dict(color=col, dash="dot"))
    fig.update_layout(barmode="group", height=340, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.15))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Work in progress against the limit**")
    st.caption("Programs in each stage today, and the stage's limit (a policy assumption of the modeled bank).")
    wip = A["pull"]["wip"]
    fig2 = go.Figure()
    fig2.add_bar(x=[w["stage"] for w in wip], y=[w["wip"] for w in wip], name="work in progress",
                 marker_color=["#b91c1c" if w["over"] else "#1f5fb0" for w in wip])
    fig2.add_scatter(x=[w["stage"] for w in wip], y=[w["limit"] for w in wip], mode="markers", name="limit",
                     marker=dict(symbol="line-ew", size=26, color="#0f172a", line=dict(width=3, color="#0f172a")))
    fig2.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.15))
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("Pause suggestions: " + "; ".join(f"{x['program_id']} {x['name']} ({x['stage']})" for x in S["pauses"])
               + ". Programs that other programs depend on are never suggested.")

    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("Gate", "A checkpoint a program passes to enter the next stage. Each gate has criteria."),
            ("Gate criterion", "One thing that must be true to pass a gate, for example 'Risk review complete'."),
            ("Evidence age", "Days since the evidence for a criterion was attested. Past its freshness rule it is stale."),
            ("Red by evidence", "At least one criterion in force at the program's stage is not met."),
            ("Slipped", "Not yet at scale, and the target quarter has passed."),
            ("Blocked", "Depends, directly or through a chain, on a program that is red by evidence or slipped."),
            ("Work in progress (WIP)", "Programs in a stage right now. Each stage has a limit."),
            ("Pull rule", "When a stage is above its limit, pause the lowest-priority program rather than add more."),
            ("Benefit at risk", "Owner-estimated benefit on programs that are red by evidence. Modeled, not measured."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is a gate-evidence feed from the systems that "
            "hold reviews and approvals, a nightly status job that applies the rules, and a board for the head of the AI "
            "program office with the capacity grid and the pause and defer list. It is a design, not deployed; see "
            "`ARCHITECTURE.md`. Related projects: TierGate (11) feeds intake, ValueLedger (12) replaces the benefit "
            "estimate with a measured one, ControlMap (16) holds gate evidence, AdoptionPulse (21) and IncidentLedger (19) "
            "feed adoption and incidents. All five links are designed, none built."
        )
    st.markdown(
        "<div class='pb-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>. Framework reference: "
        f"<a href='{NIST_URL}' target='_blank'>NIST AI RMF</a>.</div>",
        unsafe_allow_html=True,
    )
