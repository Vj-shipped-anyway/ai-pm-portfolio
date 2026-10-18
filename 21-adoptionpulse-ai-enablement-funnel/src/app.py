"""AdoptionPulse - real AI usage by team and stage, not license counts and logins.

Streamlit walkthrough. Pick one org unit, then step through the story:
  Step 1  Pick an org unit
  Step 2  Without AdoptionPulse - the license-and-login view (red) next to the funnel truth
          the generator decided for that unit (blue)
  Step 3  With AdoptionPulse - stage counts, the leak between stages and the recommended action
  Step 4  Proof at scale - the same measures over all 20 units, with what it still gets wrong

All data is synthetic (data/_generate.py, seeded). The stage rules are plain thresholds; there
is no model anywhere in this app.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from step_01_license_counts_status_quo import STAGES, WEEKS, load_all  # noqa: E402
from step_02_login_adoption_baseline import ADOPTION_OK_PCT, summarize as summarize_step2  # noqa: E402
from step_03_deficiencies_exposed import summarize as summarize_step3, unit_deficiencies  # noqa: E402
from step_04_with_adoptionpulse import TYPE_LABEL, TYPE_ORDER, analyze  # noqa: E402

st.set_page_config(
    page_title="AdoptionPulse - Real AI usage by team and stage",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/21-adoptionpulse-ai-enablement-funnel/README.md"
NIST_URL = "https://www.nist.gov/itl/ai-risk-management-framework"

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.ap-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.ap-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.ap-hero h1 {color: #ffffff !important; font-size: 46px; line-height: 1.12; margin: 0 0 14px 0; font-weight: 700;}
.ap-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.ap-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.ap-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.ap-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.ap-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.ap-card h3 {margin-top: 0; color: #0f172a;}
.ap-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
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
.bot-bad ul, .bot-truth ul {margin: 8px 0 0 18px; padding: 0;}
.bot-bad li, .bot-truth li {line-height: 1.5; margin-bottom: 8px;}
.bot-bad .small, .bot-truth .small {font-size: 13px; opacity: 0.85; margin-top: 8px;}

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


@st.cache_resource
def load_analysis() -> dict:
    a = analyze(load_all(DATA_DIR))
    a["step2"] = summarize_step2(a["data"])
    a["step3"] = summarize_step3(a["data"])
    return a


A = load_analysis()
DATA = A["data"]
S = A["summary"]
S2 = A["step2"]
S3 = A["step3"]
ROW = {r["unit"]: r for r in A["rows"]}

# Option labels are plain strings; a dict maps label -> unit name.
LABEL_TO_UNIT = {f"{r['unit']}  -  {r['licensed']} users  -  {r['habitual_pct']}% habitual": r["unit"]
                 for r in A["ranked"]}
LABELS = list(LABEL_TO_UNIT)

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
<div class='ap-hero'>
  <div class='brand'>📈 AdoptionPulse</div>
  <h1>Real AI usage by team and stage: {S['habitual_pct']}% habitual, not the {S['reported_pct']}% a login count reports.</h1>
  <div class='sub'>A login count says who opened the tool once. AdoptionPulse stages every licensed user and shows which team loses people, and where.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>No model: plain rules</span>
    <span class='pill'>{S['licensed']} users · {S['units']} units · {WEEKS} weeks</span>
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
# STEP 1 - pick an org unit
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='ap-card'><span class='ap-step-label'>Step 1</span>"
    "<h3>Pick an org unit</h3>"
    f"<p class='muted'>{S['units']} units, {S['licensed']} licensed staff. The first one is the unit where "
    "AdoptionPulse finds the most habitual users to gain.</p></div>",
    unsafe_allow_html=True,
)
if "unit_choice" not in st.session_state:
    st.session_state.unit_choice = LABELS[0]
st.session_state.unit_choice = st.selectbox(
    "Org unit:",
    LABELS,
    index=LABELS.index(st.session_state.unit_choice),
    label_visibility="collapsed",
)
unit = LABEL_TO_UNIT[st.session_state.unit_choice]
r = ROW[unit]
n = r["licensed"]

st.markdown(
    f"<div class='ap-card'><b>Unit:</b> <code>{esc(unit)}</code><br>"
    f"<span class='muted'>{n} licensed users, "
    f"{'a champion assigned' if r['champion'] else 'no champion'}, "
    f"{r['trained_pct']}% completed training.</span></div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p class='muted'>Synthetic data, no model. The units, people and numbers are made up: nothing here is a "
    "real bank or employee. The generator decided what each person does, so the truth is known. "
    "Habitual means an AI session in at least 4 of the last 6 weeks. The stage rules are plain thresholds "
    "(assumptions of a modeled bank). The champion and training effects are planted by construction.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# STEP 2 - Without AdoptionPulse: the license and login view
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='ap-card'><span class='ap-step-label'>Step 2</span>"
        "<h3>Without AdoptionPulse - the login view says all is well</h3>"
        "<p class='muted'>The program reports licenses issued and people who logged in. Here is that view for "
        "this unit, next to what the generator decided these people do.</p></div>",
        unsafe_allow_html=True,
    )
    reads = ("It reads as healthy" if r["login_pct"] >= ADOPTION_OK_PCT
             else "It reads as below the healthy cut") + f" (cut: {ADOPTION_OK_PCT:.0f}%)."
    red = (
        "<div class='bot-bad'><b>What the license and login view reports (MISSED):</b>"
        "<ul>"
        f"<li><b>{n}</b> licenses issued; <b>{r['logged_in']}</b> people logged in at least once.</li>"
        f"<li>Reported adoption: <b>{r['login_pct']}%</b>. {esc(reads)}</li>"
        "<li>A person who logged in once stays counted, so the number does not fall when usage does. It does "
        "not say who uses the tool, how often or how well.</li>"
        "</ul>"
        "<div class='small'>Modeled: adoption is the cumulative logged-in share; the healthy cut is an "
        "assumption.</div></div>"
    )
    tt, ts = r["truth_types"], r["truth_stages"]
    truth_hab = ts["habitual"] + ts["proficient"]
    types_txt = ", ".join(f"{esc(TYPE_LABEL[t])} {tt[t]}" for t in TYPE_ORDER)
    blue = (
        "<div class='bot-truth'><b>Source of truth - what the generator decided about these "
        f"{n} people (synthetic):</b>"
        "<ul>"
        f"<li>Behavior types: {types_txt}.</li>"
        f"<li>Habitual or better: <b>{truth_hab}</b> of {n} ({round(100 * truth_hab / n, 1)}%). "
        f"Started but not habitual: <b>{ts['activated']}</b>. Never started: <b>{ts['licensed']}</b>.</li>"
        f"<li>Champion in the unit: {'yes' if r['champion'] else 'no'}. Training completed: {r['trained_pct']}%.</li>"
        "</ul></div>"
    )
    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    d = unit_deficiencies(DATA, A["stage"], unit)
    est = S3
    rows3 = [
        ("1", "Logins that never became an AI session", d["logged_no_ai"] > 0,
         f"{d['logged_no_ai']} of {d['logged']} users who logged in never had an AI session"),
        ("2", "One-time activation counted as adoption", d["act_not_hab"] > 0,
         f"{d['act_not_hab']} of {d['activated']} activated users never became habitual"),
        ("3", "The average hides the spread between units", True,
         f"this unit is {r['habitual_pct']}% habitual; the estate is {S['habitual_pct']}%; "
         f"the best and worst units are {est['d3']['best']['habitual_pct']}% and {est['d3']['worst']['habitual_pct']}%"),
        ("4", "Training completion is not usage", d["trained_idle"] > 0,
         f"{d['trained_idle']} of {d['trained']} trained users never had an AI session"),
        ("5", "Champion coverage", True,
         f"champion in the unit: {'yes' if d['champion'] else 'no'}; the planted effect is "
         f"+{S['champion']['planted_gap_points']} points on the chance of becoming habitual"),
        ("6", "Weekly decay", d["active_wk4"] > d["active_wk12"],
         f"{d['active_wk4']} of {d['activated']} activated users active in week {d['compare_week']}, "
         f"{d['active_wk12']} in week {WEEKS}"),
    ]
    with st.expander("See the data"):
        st.markdown("**The six named deficiencies of the login view, on this unit**")
        st.caption("Step 3 of the README walkthrough (step_03_deficiencies_exposed.py) runs the same measures "
                   "over the whole estate.")
        df3 = pd.DataFrame(
            [{"#": x[0], "Deficiency": x[1], "Hits this unit": "yes" if x[2] else "no", "Evidence": x[3]}
             for x in rows3]
        )
        st.dataframe(df3, use_container_width=True, hide_index=True)
        st.markdown("**People in this unit: weekly AI sessions and the stage AdoptionPulse gave them**")
        recs = []
        for u in DATA["by_unit"][unit]:
            uid = u["user_id"]
            rec = {"user": uid, "role": u["role"], "licensed week": u["licensed_week"],
                   "trained week": str(u["trained_week"]) if u["trained_week"] is not None else "-"}
            for w in range(WEEKS):
                rec[f"w{w + 1}"] = DATA["use"][uid]["sessions"][w]
            rec["stage"] = A["stage"][uid]
            recs.append(rec)
        st.dataframe(pd.DataFrame(recs), use_container_width=True, hide_index=True)

    if st.session_state.step < 3:
        if st.button("See the fix ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With AdoptionPulse: stage, leak, action
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='ap-card'><span class='ap-step-label'>Step 3</span>"
        f"<h3>With AdoptionPulse - {esc(unit)} by stage</h3>"
        "<p class='muted'>AdoptionPulse stages each person from weekly AI usage, finds where the unit loses "
        "people, and attaches a rule-based action.</p></div>",
        unsafe_allow_html=True,
    )
    flagged = r["gain"] > 0 or bool(r["leak"])
    leak_html = ""
    if r["leak"]:
        leak_html = (f"<div class='vfind'><span class='vchip'>Biggest leak</span>{esc(r['leak'])}: "
                     f"{r['leak_users']} users, {abs(r['leak_gap_points'])} points below the estate rate.</div>")
    else:
        leak_html = "<div class='vfind'><span class='vchip'>Leak</span>None: at or above the estate rate at every stage.</div>"
    rank_txt = (f"Rank {r['rank']} of {S['units']} units with users to gain: {r['gain']} more habitual users if the "
                "unit matched the estate rate." if r["rank"]
                else "At or above the estate habitual rate, so it has no habitual users to gain and is not ranked.")
    st.markdown(
        "<div class='verdict-card verdict-pass'>"
        f"<div class='vlabel'>With AdoptionPulse - stage counts - {esc(unit)}</div>"
        f"<div class='vbig'>{'FLAGGED' if flagged else 'ON TRACK'}</div>"
        f"<div class='vmetric'>{r['habitual']} of {n} licensed users are habitual ({r['habitual_pct']}%)</div>"
        "<div class='vrow'>"
        f"<span class='vchip'>Licensed {n}</span>"
        f"<span class='vchip'>Activated {r['activated']}</span>"
        f"<span class='vchip'>Habitual {r['habitual']}</span>"
        f"<span class='vchip'>Proficient {r['proficient']}</span></div>"
        + leak_html +
        f"<div class='vfind'><span class='vchip'>Action</span>{esc(r['action'])}</div>"
        f"<div class='vtldr'>{esc(rank_txt)} AdoptionPulse staged {r['correct']} of {n} people the same way the "
        "generator decided. The action is a rule, not a tested intervention.</div></div>",
        unsafe_allow_html=True,
    )

    fn = S["funnel"]
    est_conv = S["est_conv"]
    unit_conv = [r["activated_pct"], r["conv_habitual_pct"], r["conv_proficient_pct"]]
    fig = go.Figure()
    labels = ["licensed to activated", "activated to habitual", "habitual to proficient"]
    fig.add_bar(x=labels, y=unit_conv, name=unit, marker_color="#1f5fb0")
    fig.add_bar(x=labels, y=[est_conv["activated"], est_conv["habitual"], est_conv["proficient"]],
                name="estate", marker_color="#94a3b8")
    fig.update_layout(barmode="group", height=320, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.12), yaxis_title="share that moves on (%)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Conversion from each stage to the next, this unit against the estate "
               f"({fn['licensed']} licensed, {fn['activated']} activated, {fn['habitual']} habitual, "
               f"{fn['proficient']} proficient).")

    with st.expander("See the data"):
        st.markdown("**Funnel by org unit, ranked by habitual users to gain**")
        udf = pd.DataFrame([{"rank": x["rank"], "unit": x["unit"], "licensed": x["licensed"],
                             "activated": x["activated"], "habitual": x["habitual"],
                             "proficient": x["proficient"], "habitual %": x["habitual_pct"],
                             "login view %": x["login_pct"], "champion": "yes" if x["champion"] else "no",
                             "trained %": x["trained_pct"], "gain": x["gain"], "leak": x["leak"] or "-"}
                            for x in A["ranked"]])
        st.dataframe(udf, use_container_width=True, hide_index=True)
        st.markdown("**Stage rules (assumptions of a modeled bank, from funnel_policy.csv)**")
        pol = pd.DataFrame([{"parameter": k, "value": v} for k, v in DATA["policy"].items()])
        st.dataframe(pol, use_container_width=True, hide_index=True)

    if st.session_state.step < 4:
        if st.button("See the proof at scale ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    d2, d3 = S3["d2"], S3["d3"]
    lim, ut, ch, tr = S["limit"], S["utility"], S["champion"], S["training"]
    st.markdown(
        "<div class='ap-card'><span class='ap-step-label'>Step 4</span>"
        "<h3>Proof at scale</h3>"
        f"<p class='muted'>The same stages over the whole synthetic estate: {S['units']} units, "
        f"{S['licensed']} licensed staff, {WEEKS} weeks.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Without AdoptionPulse: login view</div>"
        f"<div class='vbig'>{S['reported_pct']}%</div>"
        "<div class='vmetric'>reported as adopted</div>"
        f"<div class='vtldr'>Only {S['habitual_pct']}% of licensed users are habitual and "
        f"{S['proficient_pct']}% proficient.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>Without AdoptionPulse: one-time use</div>"
        f"<div class='vbig'>{d2['act_not_hab']} of {d2['activated']}</div>"
        "<div class='vmetric'>activated users never became habitual</div>"
        "<div class='vtldr'>The login view counts every one of them as adopted.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With AdoptionPulse: staging</div>"
        f"<div class='vbig'>{S['ap_correct']} of {S['licensed']}</div>"
        "<div class='vmetric'>users staged as the generator decided</div>"
        f"<div class='vtldr'>The best case for the login flag, mapped to stages with hindsight, is "
        f"{S['base_best']} of {S['licensed']}.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With AdoptionPulse: units</div>"
        f"<div class='vbig'>{d3['worst']['habitual_pct']}% to {d3['best']['habitual_pct']}%</div>"
        "<div class='vmetric'>habitual rate across units</div>"
        f"<div class='vtldr'>The login view showed {d3['login_worst_pct']}% to {d3['login_best_pct']}%. "
        f"{S['units_to_act']} units have habitual users to gain.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>"
        f"<li>Telemetry counts use, not value. {lim['rule_proficient_poor']} of {lim['rule_proficient']} users the "
        "rules call proficient produce poor work in the generator, and the weekly counts cannot show it.</li>"
        f"<li>Proficient is a proxy. Of {lim['true_proficient']} proficient-type users, "
        f"{lim['true_proficient_staged_proficient']} are staged proficient; "
        f"{lim['true_habitual_staged_activated']} of {lim['true_habitual']} habitual-type users are staged only "
        "activated.</li>"
        f"<li>The champion effect is true here by construction. Planted: +{ch['planted_gap_points']} points. "
        f"Measured: {ch['measured_gap_points']} points. Training: planted +{tr['planted_gap_points']}, measured "
        f"{tr['measured_gap_points']}. Real data would be confounded.</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Who is still using it, week by week**")
    st.caption("Share of activated users with an AI session in the week, against the login view's cumulative share.")
    ret = A["retention"]
    fig = go.Figure()
    fig.add_scatter(x=[x["week"] for x in ret], y=[x["login_view_pct"] for x in ret], mode="lines+markers",
                    name="login view (cumulative)", line=dict(color="#dc2626"))
    fig.add_scatter(x=[x["week"] for x in ret], y=[x["activated_pct"] for x in ret], mode="lines+markers",
                    name="activated users active", line=dict(color="#059669"))
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.12),
                      xaxis_title="week", yaxis_title="%")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Habitual rate by unit**")
    srt = sorted(A["rows"], key=lambda x: x["habitual_pct"])
    fig = go.Figure()
    fig.add_bar(x=[x["unit"] for x in srt], y=[x["login_pct"] for x in srt], name="login view",
                marker_color="#fca5a5")
    fig.add_bar(x=[x["unit"] for x in srt], y=[x["habitual_pct"] for x in srt], name="habitual",
                marker_color="#1f5fb0")
    fig.update_layout(barmode="group", height=380, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.12), xaxis_tickangle=-35, yaxis_title="%")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("Licensed", "Has a license."),
            ("Activated", "At least 1 AI session in the first 14 days after licensing."),
            ("Habitual", "AI sessions in at least 4 of the last 6 weeks."),
            ("Proficient", "Habitual, plus advanced-feature use and a high accepted-output rate. A proxy for skill."),
            ("Leak", "The stage conversion where a unit sits furthest below the estate rate."),
            ("Gain", "Habitual users a unit would add if it matched the estate habitual rate."),
            ("Champion", "A named person in the unit who helps colleagues use the tool."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is a usage feed from the AI assistant's "
            "gateway log, a join to the staff directory, the training record and the champion roster, a weekly "
            "stage job, and a unit-level report with a minimum group size so no individual is singled out. It is a "
            "design, not deployed; see `ARCHITECTURE.md`. Related projects: ValueLedger (12) ties benefit to habit, "
            "TierGate (11) decides which use cases to enable, PortfolioBoard (24) treats enablement as a program, "
            "InferenceLens (07) gives cost per active user. All designed, none built."
        )
    st.markdown(
        "<div class='ap-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>. Framework reference: "
        f"<a href='{NIST_URL}' target='_blank'>NIST AI RMF</a>.</div>",
        unsafe_allow_html=True,
    )
