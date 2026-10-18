"""PolicyNeedle - Long-Context Fidelity Probes (Streamlit prototype).

Everything here is synthetic. The four readers are STUBS, not models: small
functions written to have known faults. Nothing calls a model or the network.

A four-step walkthrough, one step at a time:
  Step 1  pick a reader and a document length
  Step 2  without PolicyNeedle: the short test passes
  Step 3  with PolicyNeedle: faults flagged, heat map, gate verdict
  Step 4  proof at scale: catch rates, and what it still gets wrong

Every number is computed from data/ by the same code the step scripts run.
Run from the repo root:
    streamlit run 14-policyneedle-long-context-fidelity/src/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import harness as h  # noqa: E402
import step_01_short_document_test as s1  # noqa: E402
import step_02_fixed_needle_test as s2  # noqa: E402
import step_04_with_policyneedle as s4  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
BASE_URL = GITHUB_URL + "/blob/main/14-policyneedle-long-context-fidelity/"

st.set_page_config(
    page_title="PolicyNeedle - Finds what policy assistants miss in long manuals, before launch",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS
# (card, verdict and bot-* classes are the HalluGuard set; the hero keeps this project's accent)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Hero block */
.pn-hero {background: linear-gradient(135deg,#0b132b 0%, #1c2541 50%, #5bc0be 100%);
  border-radius: 18px; padding: 36px 40px 32px 40px; color: #ffffff; margin-bottom: 28px;}
.pn-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.pn-hero h1 {color: #ffffff !important; font-size: 44px; line-height: 1.12; margin: 0 0 14px 0; font-weight: 700;}
.pn-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.pn-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.pn-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.pn-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.pn-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.pn-card h3 {margin-top: 0; color: #0f172a;}
.pn-step-label {display: inline-block; background: #1c2541; color: #fff; padding: 3px 10px;
                border-radius: 6px; font-size: 12px; font-weight: 600; letter-spacing: 0.04em;
                text-transform: uppercase; margin-bottom: 10px;}
.pn-chip {display: inline-block; background: #f1f5f9; border: 1px solid #cbd5e1; color: #1c2541;
          padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; margin: 2px 6px 0 0;}
.pn-note {color: #64748b; font-size: 14px; line-height: 1.55; margin: 2px 4px 18px 4px;}

/* Verdict card */
.verdict-card {border-radius: 16px; padding: 26px 30px; margin-bottom: 18px; color: #fff;}
.verdict-pass {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.verdict-flag {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.verdict-review {background: linear-gradient(135deg,#b45309,#f59e0b);}
.verdict-info {background: linear-gradient(135deg,#163a6c,#1f5fb0);}
.verdict-card .vlabel {font-size: 13px; opacity: 0.9; letter-spacing: 0.08em; text-transform: uppercase;}
.verdict-card .vbig {font-size: 44px; font-weight: 800; line-height: 1.1; margin: 4px 0 14px 0;}
.verdict-card .vmetric {font-size: 22px; font-weight: 600;}
.verdict-card .vrow {display: flex; flex-wrap: wrap; gap: 24px; margin-top: 12px;}
.verdict-card .vchip {background: rgba(255,255,255,0.18); padding: 6px 12px; border-radius: 999px;
                      font-size: 13px; font-weight: 600;}
.verdict-card .vtldr {margin-top: 16px; font-size: 15px; line-height: 1.5; opacity: 0.95;}

/* Large metric cards for the proof step */
.pn-metrics {display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px;
             margin-bottom: 18px;}
.pn-metrics .verdict-card {margin-bottom: 0; padding: 22px 24px;}
.pn-metrics .vbig {font-size: 38px; margin: 6px 0 8px 0;}
.pn-metrics .vsub {font-size: 14px; line-height: 1.4; opacity: 0.95;}

/* Trust panel */
.trust-card {background: #f8fafc; border: 1px solid #cbd5e1; border-left: 5px solid #1c2541;
             border-radius: 12px; padding: 20px 24px; margin-bottom: 18px;}
.trust-card h4 {margin: 0 0 10px 0; color: #0f172a; font-size: 16px; letter-spacing: 0.04em;
                text-transform: uppercase;}
.trust-card .tlabel {font-weight: 700; color: #1c2541; font-size: 13px; letter-spacing: 0.04em;
                     text-transform: uppercase; margin-top: 12px; display: block;}
.trust-card ul {margin: 6px 0 0 18px; padding: 0;}
.trust-card li {color: #334155; line-height: 1.55;}

/* Muted known-limit panel */
.pn-limit {background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;
           padding: 18px 24px; margin-bottom: 18px; color: #475569; font-size: 14px; line-height: 1.55;}
.pn-limit h4 {margin: 0 0 8px 0; color: #475569; font-size: 14px; letter-spacing: 0.04em; text-transform: uppercase;}
.pn-limit ul {margin: 6px 0 0 18px; padding: 0;}
.pn-limit li {margin-bottom: 6px;}

/* Bot vs truth panel */
.bot-bad {background: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #dc2626;
          border-radius: 10px; padding: 14px 18px; color: #7f1d1d; line-height: 1.6;}
.bot-good {background: #ecfdf5; border: 1px solid #bbf7d0; border-left: 4px solid #059669;
           border-radius: 10px; padding: 14px 18px; color: #065f46; margin-bottom: 18px; line-height: 1.6;}
.bot-truth {background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb;
            border-radius: 10px; padding: 14px 18px; color: #1e3a8a; line-height: 1.6;}
.bot-good ul {margin: 6px 0 6px 18px; padding: 0;}

/* Buttons - one big primary CTA */
div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#1c2541,#0b132b) !important;
  color: #fff !important; border: 0 !important; padding: 14px 28px !important;
  font-size: 17px !important; font-weight: 600 !important; border-radius: 12px !important;
  box-shadow: 0 4px 14px rgba(28,37,65,0.35) !important;
}

h1, h2, h3 {color: #0f172a;}
.muted {color: #64748b; font-size: 14px;}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Results: computed once from data/ by the same code the step scripts use
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_results() -> dict:
    r1 = s1.compute()
    r2 = s2.compute()
    r4 = s4.compute()
    probes = h.long_probes(h.load_probes())
    known = {rk: h.known_fault_cells(probes, rk) for rk in h.READER_KEYS}
    return {"s1": r1, "s2": r2, "s4": r4, "known": known, "probes": probes}


RES = load_results()
CELLS = RES["s4"]["cells"]
ROWS = RES["s4"]["rows"]

# Scenario options: plain strings, mapped to (reader key, length) with a dict.
SCENARIOS = []
SCENARIO_MAP = {}
for _r in h.READERS:
    for _length in h.LENGTHS:
        _label = "{} | {} pages".format(_r["label"], _length)
        SCENARIOS.append(_label)
        SCENARIO_MAP[_label] = (_r["key"], _length)

# Plain-English account of what each stub really gets wrong (written from the stub docstrings in harness.py)
WHAT_IT_GETS_WRONG = {
    "truncating": (
        "It never sees the end of a long manual. Everything past the first {:,} characters is invisible to it. "
        "An amendment at the back is never read, so the old version of a clause comes back as the answer."
    ).format(h.TRUNCATE_AT),
    "first_match": (
        "It stops at the first passage that matches. It quotes the original clause when an amendment replaces it, "
        "skips the footnote that carves out an exception, reads the first column of a tier table whatever tier was asked, "
        "uses one clause when the answer needs two, and answers for whichever sibling product comes first."
    ),
    "last_match": (
        "It trusts the last passage that matches. That happens to be right for an amendment and for a footnote exception "
        "that applies. It is wrong when the footnote does not cover the case, on a tier table (it reads the first column "
        "whatever tier was asked), when the answer needs two clauses, and for whichever sibling product comes last."
    ),
    "control": (
        "It is here to show that every probe can be answered from the text and that PolicyNeedle stays quiet when nothing is wrong."
    ),
}

# Session state: the default is the truncating reader at 120 pages.
if "step" not in st.session_state:
    st.session_state.step = 1
if "scenario_choice" not in st.session_state:
    st.session_state.scenario_choice = SCENARIOS[1]


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='pn-hero'>
  <div class='brand'>📚 PolicyNeedle</div>
  <h1>Finds the clause a policy-manual assistant misses deep in a long document - before launch, not after.</h1>
  <div class='sub'>A short test passes assistants that fail deep inside long policy manuals. PolicyNeedle plants facts at five depths in six forms and shows exactly where a reader breaks.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>{RES['s4']['n_probes']} probes · 4 stub readers, not models</span>
    <span class='pill'>Synthetic data</span>
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
# STEP 1 - pick a reader and a document length
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='pn-card'><span class='pn-step-label'>Step 1</span>"
    "<h3>Pick a reader and a document length</h3>"
    "<p class='muted'>A reader is the assistant being tested. Choose one, then the length of the policy manual it reads.</p>"
    "<span class='pn-chip'>Stub, not a model</span></div>",
    unsafe_allow_html=True,
)

st.session_state.scenario_choice = st.selectbox(
    "Scenario:",
    SCENARIOS,
    index=SCENARIOS.index(st.session_state.scenario_choice),
    label_visibility="collapsed",
)
RK, LENGTH = SCENARIO_MAP[st.session_state.scenario_choice]
READER = h.READER_BY_KEY[RK]
STUB = RK != "control"

st.markdown(
    f"<div class='pn-card'><b>Reader:</b> {READER['label']}<br>"
    f"<b>Manual:</b> {LENGTH} synthetic pages</div>",
    unsafe_allow_html=True,
)

st.markdown(
    "<p class='pn-note'>How to read the numbers: the four readers are small functions written to have known faults - "
    "a truncating reader, a keyword-window reader, a recency reader and a full-scan control. They are stubs, not models. "
    "Nothing here calls a model, and their answers are not observed behavior of any real model. "
    "The manuals are synthetic and run 40, 120 and 240 pages (1 page = 1,800 characters). "
    "Every number on this page is computed by the same code the step scripts run.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# STEP 2 - without PolicyNeedle: the short test passes
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    sp = RES["s1"]["per_reader"][RK]
    fx = RES["s2"]["table"][RK]
    fx_len = fx["per_length"][LENGTH]
    short_tag = "PASSED" if sp["passed"] == sp["n"] else "FLAGGED"
    failing_lengths = [L for L in h.LENGTHS if fx["per_length"][L]["passed"] < fx["per_length"][L]["n"]]

    st.markdown(
        "<div class='pn-card'><span class='pn-step-label'>Step 2</span>"
        "<h3>Without PolicyNeedle - the short test passes</h3>"
        "<p class='muted'>The usual checks are a 6-page excerpt with ten questions, then one planted fact "
        "(the needle) in the middle of each long manual. Here is what they say about this reader.</p></div>",
        unsafe_allow_html=True,
    )

    if failing_lengths:
        fixed_line = (
            "Fixed-needle test: <b>FLAGGED</b> - {p} of {n} right. It fails at {lens} pages, "
            "but it cannot say which depth or form is at fault."
        ).format(p=fx["passed"], n=fx["n"], lens=" and ".join(str(L) for L in failing_lengths))
    else:
        fixed_line = "Fixed-needle test: <b>PASSED</b> - {p} of {n} right.".format(p=fx["passed"], n=fx["n"])
    at_length_line = "At {L} pages you picked: {p} of {n} right.".format(L=LENGTH, p=fx_len["passed"], n=fx_len["n"])
    control_line = "" if STUB else "<br><i>This reader has no planted fault, so passing is the right result.</i>"

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            "<div class='bot-bad'><b>What the usual tests say:</b><br>"
            "Short-document test: <b>{st_tag}</b> - {sp_p} of {sp_n} right.<br>"
            "{fixed_line}<br>"
            "{at_length_line}{control_line}</div>".format(
                st_tag=short_tag, sp_p=sp["passed"], sp_n=sp["n"], fixed_line=fixed_line,
                at_length_line=at_length_line, control_line=control_line),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            "<div class='bot-truth'><b>The fault planted in this reader:</b><br>"
            "{fault}<br>{wrong}<br><i>A stub, not a model.</i></div>".format(
                fault=READER["fault"], wrong=WHAT_IT_GETS_WRONG[RK]),
            unsafe_allow_html=True,
        )

    st.markdown(
        "<p class='pn-note'>Why the short test cannot see the faults: the excerpt holds no amendment register ({amend}), "
        "no footnote exception ({notes}), no tier table ({tables}) and no cross-section clause ({disc}). "
        "The faults need those structures. The fixed-needle test flags {n} of 3 faulty stubs (the truncating stub, "
        "at 120 and 240 pages). It tests one depth and one form of fact out of six.</p>".format(
            amend=RES["s1"]["structures"]["amendment register"], notes=RES["s1"]["structures"]["footnote exceptions"],
            tables=RES["s1"]["structures"]["tier tables"], disc=RES["s1"]["structures"]["cross-section discount clauses"],
            n=len(RES["s2"]["flagged_stubs"])),
        unsafe_allow_html=True,
    )

    with st.expander("See the data"):
        st.markdown("**Short-document test** - {} questions on a {:,}-character excerpt".format(
            RES["s1"]["n_probes"], RES["s1"]["doc_chars"]))
        m1, m2, m3 = st.columns(3)
        m1.metric("Questions passed", "{} of {}".format(sp["passed"], sp["n"]))
        m2.metric("Excerpt length", "{:,} characters".format(RES["s1"]["doc_chars"]))
        m3.metric("Questions matching more than one block", RES["s1"]["questions_with_more_than_one_match"])
        st.markdown("**Fixed-needle test** - plain clauses planted at depth 50% in the three long manuals, 3 probes per length")
        t = RES["s2"]["table"]
        fixed_rows = []
        for r in h.READERS:
            pl = t[r["key"]]["per_length"]
            fixed_rows.append({
                "Reader": r["label"],
                "40 pages": "{}/{}".format(pl[40]["passed"], pl[40]["n"]),
                "120 pages": "{}/{}".format(pl[120]["passed"], pl[120]["n"]),
                "240 pages": "{}/{}".format(pl[240]["passed"], pl[240]["n"]),
                "Total": "{}/{}".format(t[r["key"]]["passed"], t[r["key"]]["n"]),
            })
        st.dataframe(pd.DataFrame(fixed_rows), use_container_width=True, hide_index=True)
        st.caption("The keyword-window and recency stubs pass 9 of 9 because their faults are not about position.")

    if st.session_state.step < 3:
        if st.button("See the fix  ->", key="cta_step2", type="primary"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - with PolicyNeedle: faults flagged, heat map, gate verdict
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    PR = RES["s4"]["per_reader"][RK]
    gate = PR["gate_by_length"][LENGTH]

    st.markdown(
        "<div class='pn-card'><span class='pn-step-label'>Step 3</span>"
        "<h3>With PolicyNeedle - the sweep shows where it breaks</h3>"
        "<p class='muted'>Six forms of fact at five depths in the manual. A cell is flagged when fewer than 90% "
        "of its 3 probes pass, so one miss flags it.</p></div>",
        unsafe_allow_html=True,
    )

    # --- faults flagged for this reader and length -------------------------------------
    flagged_rows = []
    for form in h.FORMS:
        failing = h.localize(CELLS, RK, form, LENGTH)
        if failing == "none":
            continue
        passed = sum(CELLS[(RK, form, LENGTH, d)][0] for d in h.DEPTHS)
        total = sum(CELLS[(RK, form, LENGTH, d)][1] for d in h.DEPTHS)
        kinds = {}
        for r in ROWS:
            if r["reader"] == RK and r["form"] == form and r["length"] == LENGTH and not r["passed"]:
                kinds[r["diagnosis"]] = kinds.get(r["diagnosis"], 0) + 1
        designed = any((form, LENGTH, d) in RES["known"][RK] for d in h.DEPTHS)
        flagged_rows.append({
            "Deficiency": "({}) {}".format(h.DEFICIENCY[form][0], h.DEFICIENCY[form][1]),
            "Fails at": failing,
            "Probes passed": "{}/{}".format(passed, total),
            "Kind of wrong answer": ", ".join("{} {}".format(k, v) for k, v in sorted(kinds.items())),
            "Stub built to fail it": "yes" if designed else "no",
        })

    # --- verdict card ---------------------------------------------------------------------
    is_pass = gate["verdict"] == "PASS"
    verdict_class = "verdict-pass" if is_pass else "verdict-flag"
    if is_pass:
        tldr = "Every threshold is met on this manual. The probes are answerable and nothing is flagged."
    else:
        tldr = "Blocked. " + " ".join(b + "." for b in gate["broken"])
    st.markdown(
        f"""
<div class='verdict-card {verdict_class}'>
  <div class='vlabel'>PolicyNeedle gate verdict - {READER['label']} - {LENGTH} pages</div>
  <div class='vbig'>{gate['verdict']}</div>
  <div class='vmetric'>{100 * gate['overall']:.1f}% overall pass rate on {gate['n']} probes</div>
  <div class='vrow'>
    <span class='vchip'>Gate: overall >= 98%</span>
    <span class='vchip'>Every form-by-length slice >= 90%</span>
    <span class='vchip'>Every depth band >= 90%</span>
  </div>
  <div class='vtldr'><b>TL;DR:</b> {tldr}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # --- the green card: what PolicyNeedle caught ----------------------------------------
    if flagged_rows:
        items = "".join(
            "<li><b>{d}</b> - fails at {f}. {p} probes passed.</li>".format(
                d=r["Deficiency"], f=r["Fails at"], p=r["Probes passed"]) for r in flagged_rows)
        st.markdown(
            "<div class='bot-good'><b>PolicyNeedle (CAUGHT):</b> the gate says {v}. "
            "Where this reader breaks at {L} pages:<ul>{items}</ul>"
            "Across all three lengths it flagged {tf} of {kc} known fault cells, with {mi} missed and {ff} false flags. "
            "<i>A stub, not a model.</i></div>".format(
                v=gate["verdict"], L=LENGTH, items=items, tf=PR["true_flags"], kc=PR["known_cells"],
                mi=PR["misses"], ff=PR["false_flags"]),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='bot-good'><b>PolicyNeedle (CLEAR):</b> the gate says {v}. No cell is flagged. "
            "The harness stays quiet on the control, and the control passes every cell, "
            "so every probe is answerable from the text.</div>".format(v=gate["verdict"]),
            unsafe_allow_html=True,
        )

    # --- heat map: depth by form ---------------------------------------------------------
    z = np.array([[CELLS[(RK, f, LENGTH, d)][0] for f in h.FORMS] for d in h.DEPTHS], dtype=float) / 3.0
    text = [["{}/3".format(CELLS[(RK, f, LENGTH, d)][0]) for f in h.FORMS] for d in h.DEPTHS]
    fig = go.Figure(go.Heatmap(
        z=z, x=[h.FORM_LABEL[f] for f in h.FORMS], y=["{}%".format(d) for d in h.DEPTHS],
        text=text, texttemplate="%{text}", zmin=0.0, zmax=1.0, showscale=False,
        colorscale=[[0.0, "#b91c1c"], [0.3333, "#ea580c"], [0.6667, "#f59e0b"], [1.0, "#16a34a"]],
        hovertemplate="%{x}<br>depth %{y}<br>passed %{text}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed", title_text="depth in the manual body")
    fig.update_xaxes(side="top")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10),
                      title_text="Probes passed out of 3 - {} - {} pages".format(READER["label"], LENGTH))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Reading the map: a staircase (pass above a depth that moves with length) is a position fault. "
               "A flat row is a fault in how a form is read. The control passes every cell.")

    with st.expander("See the data"):
        st.markdown("**Faults flagged** - {} pages".format(LENGTH))
        if flagged_rows:
            st.dataframe(pd.DataFrame(flagged_rows), use_container_width=True, hide_index=True)
        else:
            st.markdown("No cell is flagged. The harness stays quiet on the control.")

        def_rows = []
        for form in h.FORMS:
            letter, name = h.DEFICIENCY[form]
            row = {"Deficiency": "({}) {}".format(letter, name)}
            for L in h.LENGTHS:
                p = sum(CELLS[(RK, form, L, d)][0] for d in h.DEPTHS)
                n = sum(CELLS[(RK, form, L, d)][1] for d in h.DEPTHS)
                row["{} pages".format(L)] = "{}/{}  ({:.0f}%)".format(p, n, 100.0 * p / n)
            def_rows.append(row)
        st.markdown("**{}** - pass rate by deficiency and length (15 probes each)".format(READER["label"]))
        st.dataframe(pd.DataFrame(def_rows), use_container_width=True, hide_index=True)

        grid_rows = []
        for d in h.DEPTHS:
            row = {"Depth": "{}%".format(d)}
            for L in h.LENGTHS:
                p = sum(CELLS[(RK, f, L, d)][0] for f in h.FORMS)
                n = sum(CELLS[(RK, f, L, d)][1] for f in h.FORMS)
                row["{} pages".format(L)] = "{}/{}".format(p, n)
            grid_rows.append(row)
        st.markdown("**{}** - depth by length, all six forms (18 probes per cell)".format(READER["label"]))
        st.dataframe(pd.DataFrame(grid_rows), use_container_width=True, hide_index=True)

    if st.session_state.step < 4:
        if st.button("See the proof at scale  ->", key="cta_step3", type="primary"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    ut = RES["s4"]["utility"]
    lim = RES["s4"]["limit"]
    pr_all = RES["s4"]["per_reader"]
    tot_miss = sum(pr_all[k]["misses"] for k in s4.STUBS)
    tot_false = sum(pr_all[k]["false_flags"] for k in h.READER_KEYS)

    st.markdown(
        "<div class='pn-card'><span class='pn-step-label'>Step 4</span>"
        "<h3>Proof at scale - {n} probes through four stub readers</h3>"
        "<p class='muted'>How many of the {k} known fault cells each test flags. These are the cells, out of "
        "270 stub cells, that a faulty stub was built to fail.</p></div>".format(
            n=RES["s4"]["n_probes"], k=ut["failing_cells"]),
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class='pn-metrics'>
  <div class='verdict-card verdict-flag'>
    <div class='vlabel'>Short-document test</div>
    <div class='vbig'>{sc} of {k}</div>
    <div class='vsub'>known fault cells flagged</div>
  </div>
  <div class='verdict-card verdict-review'>
    <div class='vlabel'>Fixed-needle test</div>
    <div class='vbig'>{nc} of {k}</div>
    <div class='vsub'>known fault cells flagged</div>
  </div>
  <div class='verdict-card verdict-pass'>
    <div class='vlabel'>PolicyNeedle sweep</div>
    <div class='vbig'>{pc} of {k}</div>
    <div class='vsub'>known fault cells flagged</div>
  </div>
  <div class='verdict-card verdict-info'>
    <div class='vlabel'>Full-scan control (stub)</div>
    <div class='vbig'>{co} of {cn}</div>
    <div class='vsub'>probes answered correctly, {ff} false flags</div>
  </div>
</div>
""".format(sc=ut["short_caught"], k=ut["failing_cells"], nc=ut["needle_caught"], pc=ut["pn_caught"],
           co=RES["s4"]["control_ok"], cn=RES["s4"]["n_probes"], ff=tot_false),
        unsafe_allow_html=True,
    )
    st.caption("The catch rates are measured on stubs with known faults, not on any real model.")

    st.markdown(
        """
<div class='pn-limit'>
  <h4>What it still gets wrong</h4>
  <ul>
    <li>Scoring is exact match on synthetic wording. The harness can score {ns} probe types and cannot score {nu}: {names}.</li>
    <li>A correct but wordy reader is flagged as broken. The control's correct answers wrapped in one sentence score {vp} of {vn}, {vf} of {vc} cells are flagged and the gate says {vg}. Scoring a real assistant needs a tolerant scorer first.</li>
    <li>The perfect validity above ({pc} of {k} known fault cells flagged, {mi} missed, {ff} false flags) follows from stubs built with known faults. It checks the scoring, slicing and flagging. It is not a recall estimate for faults nobody planted, and not a statement about any real model.</li>
  </ul>
</div>
""".format(ns=len(lim["scorable"]), nu=len(lim["unscorable"]),
           names=", ".join(t.replace("_", " ") for t in lim["unscorable"]),
           vp=lim["verbose_passed"], vn=lim["verbose_n"], vf=lim["verbose_flagged_cells"],
           vc=lim["verbose_cells"], vg=lim["verbose_gate"],
           pc=ut["pn_caught"], k=ut["failing_cells"], mi=tot_miss, ff=tot_false),
        unsafe_allow_html=True,
    )

    with st.expander("See the data - does the sweep flag every known fault?"):
        st.markdown("**Harness validity** - does the sweep flag every known fault cell and stay quiet on the control? "
                    "(a cell is form x length x depth; 90 per reader)")
        val_rows = []
        for r in h.READERS:
            p = pr_all[r["key"]]
            val_rows.append({"Reader": r["label"], "Known fault cells": p["known_cells"], "Flagged": p["flagged_cells"],
                             "True flags": p["true_flags"], "Misses": p["misses"], "False flags": p["false_flags"]})
        st.dataframe(pd.DataFrame(val_rows), use_container_width=True, hide_index=True)
        st.caption("This validates the scoring, slicing and flagging against stubs with known faults. It is not a recall "
                   "estimate for faults nobody planted, and not a statement about any real model.")

    with st.expander("See the data - how the utility number is built"):
        st.markdown("**Utility** = (catch rate with PolicyNeedle - catch rate with short-document testing) x assistants launched per year")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🟢 PolicyNeedle catch", "{:.0f}% ({} of {})".format(100 * ut["catch_pn"], ut["pn_caught"], ut["failing_cells"]))
        m2.metric("🟢 Short-document catch", "{:.0f}% ({} of {})".format(100 * ut["catch_short"], ut["short_caught"], ut["failing_cells"]))
        m3.metric("🟡 Assistants launched per year", "{} (range {}-{})".format(ut["assistants_per_year"], *ut["assistants_range"]))
        m4.metric("🟡 Launches with faults caught", "{:.0f} per year".format(ut["utility"]))
        st.caption("The catch rates are measured on stubs with known faults, not on any real model. The assistants-per-year figure is "
                   "a modeled assumption, and the product assumes each launch carries at least one such fault.")

    with st.expander("See the data - the files behind every number"):
        st.caption("Files in data/. Regenerate with python3 data/_generate.py (seeded, standard library only).")
        st.dataframe(pd.read_csv(DATA_DIR / "manuals.csv"), use_container_width=True, hide_index=True)
        st.dataframe(pd.read_csv(DATA_DIR / "probes.csv").head(30), use_container_width=True, hide_index=True)
        st.dataframe(pd.read_csv(DATA_DIR / "probe_types.csv"), use_container_width=True, hide_index=True)

    st.markdown(
        f"<div class='pn-card muted'>Portfolio prototype on synthetic data. The readers are stubs, not models. "
        f"Full PRD, architecture and step-script walkthrough in the "
        f"<a href='{BASE_URL}README.md' target='_blank'><code>README.md</code></a>. "
        f"Part of the <a href='https://vj-shipped-anyway.github.io/ai-pm-portfolio/' target='_blank'>AI PM portfolio</a>.</div>",
        unsafe_allow_html=True,
    )
