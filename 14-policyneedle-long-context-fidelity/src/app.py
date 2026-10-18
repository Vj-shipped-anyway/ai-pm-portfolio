"""PolicyNeedle - Long-Context Fidelity Probes (Streamlit prototype).

Everything here is synthetic. The four readers are STUBS, not models: small
functions written to have known faults. Nothing calls a model or the network.

Walkthrough, four stages, each behind its own button:
  Stage 1  Before        the short-document spot test
  Stage 2  Basic         a long-document test with one fixed needle position
  Stage 3  Deficiencies  six named deficiencies, depth by length
  Stage 4  PolicyNeedle  heat map, faults flagged, gate verdict, harness validity

Pick a reader and a document length in the scenario box. Run from the repo root:
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
    page_title="PolicyNeedle - Long-Context Fidelity Probes",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.pn-hero {background: linear-gradient(135deg,#0b132b 0%, #1c2541 50%, #5bc0be 100%);
  border-radius: 18px; padding: 36px 40px; color:#fff; margin-bottom:28px;}
.pn-hero .brand {font-size:26px; font-weight:600; opacity:0.95; margin-bottom:12px;}
.pn-hero h1 {color:#fff !important; font-size:40px; line-height:1.14; margin:0 0 14px 0; font-weight:700;}
.pn-hero .sub {font-size:17px; line-height:1.5; opacity:0.93; max-width:840px; margin-bottom:22px;}
.pn-hero .pills {display:flex; flex-wrap:wrap; gap:10px;}
.pn-hero .pill {background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
  color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.pn-hero .pill a {color:#fff; text-decoration:none;}

.pn-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:22px 26px;
  margin-bottom:18px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.pn-card h3 {margin-top:0; color:#0f172a;}
.pn-step-label {display:inline-block; background:#1c2541; color:#fff; padding:3px 10px;
  border-radius:6px; font-size:12px; font-weight:600; letter-spacing:0.04em;
  text-transform:uppercase; margin-bottom:10px;}

.pn-verdict {border-radius:16px; padding:26px 30px; margin-bottom:18px; color:#fff;}
.pn-pass {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.pn-fail {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.pn-verdict .vlabel {font-size:13px; opacity:0.9; letter-spacing:0.08em; text-transform:uppercase;}
.pn-verdict .vbig {font-size:44px; font-weight:800; line-height:1.1; margin:4px 0 14px 0;}
.pn-verdict .vmetric {font-size:20px; font-weight:600;}
.pn-verdict .vrow {display:flex; flex-wrap:wrap; gap:12px; margin-top:12px;}
.pn-verdict .vchip {background: rgba(255,255,255,0.18); padding:6px 12px; border-radius:999px;
  font-size:13px; font-weight:600;}
.pn-verdict .vtldr {margin-top:16px; font-size:15px; line-height:1.5; opacity:0.95;}

.pn-trust {background:#f8fafc; border:1px solid #cbd5e1; border-left:5px solid #1c2541;
  border-radius:12px; padding:20px 24px; margin-bottom:18px;}
.pn-trust h4 {margin:0 0 10px 0; color:#0f172a; font-size:16px; letter-spacing:0.04em; text-transform:uppercase;}
.pn-trust .tlabel {font-weight:700; color:#1c2541; font-size:13px; letter-spacing:0.04em;
  text-transform:uppercase; margin-top:12px; display:block;}
.pn-trust ul {margin:6px 0 0 18px; padding:0;}
.pn-trust li {color:#334155; line-height:1.55;}

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

STAGES = ["stage1", "stage2", "stage3", "stage4"]
for _k in STAGES:
    if _k not in st.session_state:
        st.session_state[_k] = False


def run_all() -> None:
    for k in STAGES:
        st.session_state[k] = True


def run_stage(key: str) -> None:
    st.session_state[key] = True


def reset() -> None:
    for k in STAGES:
        st.session_state[k] = False


# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='pn-hero'>
  <div class='brand'>📚 PolicyNeedle</div>
  <h1>Finds the clause a policy-manual assistant misses at page 150 - before launch, not after.</h1>
  <div class='sub'>Long-context fidelity probes. Synthetic manuals at three lengths, facts planted at five depths in six forms, exact expected answers, a scoring harness that takes any reader function, a per-slice pass matrix, fault localization and a CI-style gate. The four readers here are stubs with known faults, not models.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>{RES['s4']['n_probes']} long-sweep probes · 4 stub readers</span>
    <span class='pill'>Synthetic data</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.button("Run all four stages  ->", key="cta_all", type="primary", on_click=run_all)

# ---------------------------------------------------------------------------
# Scenario picker
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='pn-card'><span class='pn-step-label'>Scenario</span>"
    "<h3>Pick a reader and a document length</h3>"
    "<p class='muted'>Four stub readers, each labeled a stub, none a model: a truncating reader, a keyword-window "
    "reader, a recency reader and a full-scan control. Three manual lengths: 40, 120 and 240 synthetic pages "
    "(1 page = 1,800 characters). The default is the truncating reader at 120 pages.</p></div>",
    unsafe_allow_html=True,
)
choice = st.selectbox("Scenario:", SCENARIOS, index=1, label_visibility="collapsed", key="scenario")
RK, LENGTH = SCENARIO_MAP[choice]
READER = h.READER_BY_KEY[RK]
STUB = RK != "control"
st.caption("Known fault of this stub: {}".format(READER["fault"]))

# ---------------------------------------------------------------------------
# Stage 1 - before
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='pn-card'><span class='pn-step-label'>Stage 1 - Before</span>"
    "<h3>The short-document spot test</h3>"
    "<p class='muted'>A 6-page excerpt, ten plain-clause questions, normalized exact match. It is the test that "
    "ships when everything passes.</p></div>",
    unsafe_allow_html=True,
)
st.button("Run the short-document test  ->", key="cta_s1", on_click=run_stage, args=("stage1",))
if st.session_state["stage1"]:
    pr = RES["s1"]["per_reader"][RK]
    c1, c2, c3 = st.columns(3)
    c1.metric("Questions passed", "{} of {}".format(pr["passed"], pr["n"]))
    c2.metric("Excerpt length", "{:,} characters".format(RES["s1"]["doc_chars"]))
    c3.metric("Questions matching more than one block", RES["s1"]["questions_with_more_than_one_match"])
    st.markdown(
        "Everything passes, including the three stubs that were written to fail. The excerpt holds no amendment "
        "register ({amend}), no footnote exception ({notes}), no tier table ({tables}) and no cross-section clause "
        "({disc}). The faults need those structures; the test has none of them.".format(
            amend=RES["s1"]["structures"]["amendment register"], notes=RES["s1"]["structures"]["footnote exceptions"],
            tables=RES["s1"]["structures"]["tier tables"], disc=RES["s1"]["structures"]["cross-section discount clauses"]))

# ---------------------------------------------------------------------------
# Stage 2 - basic approach
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='pn-card'><span class='pn-step-label'>Stage 2 - Basic approach</span>"
    "<h3>A long-document test with one fixed needle position</h3>"
    "<p class='muted'>Plain clauses planted at depth 50% in the three long manuals. Three probes per length.</p></div>",
    unsafe_allow_html=True,
)
st.button("Run the fixed-needle test  ->", key="cta_s2", on_click=run_stage, args=("stage2",))
if st.session_state["stage2"]:
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
    st.markdown(
        "This test flags {n} of 3 faulty stubs (the truncating stub, at 120 and 240 pages). The keyword-window and "
        "recency stubs pass 9 of 9 because their faults are not about position. It cannot say which depth fails "
        "and it tests one form of fact out of six.".format(n=len(RES["s2"]["flagged_stubs"])))

# ---------------------------------------------------------------------------
# Stage 3 - six deficiencies
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='pn-card'><span class='pn-step-label'>Stage 3 - Where this still breaks</span>"
    "<h3>Six named deficiencies, depth by length</h3>"
    "<p class='muted'>Six forms of fact at five depths in each of the three manuals. Each cell is the number of "
    "probes passed out of 3.</p></div>",
    unsafe_allow_html=True,
)
st.button("Expose the six deficiencies  ->", key="cta_s3", on_click=run_stage, args=("stage3",))
if st.session_state["stage3"]:
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
    st.markdown(
        "A staircase (pass above a depth that moves with length) is a position fault. A flat row is a fault in how a "
        "form is read. The control passes every cell, so every probe is answerable from the text.")

# ---------------------------------------------------------------------------
# Stage 4 - PolicyNeedle
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='pn-card'><span class='pn-step-label'>Stage 4 - The fix</span>"
    "<h3>The PolicyNeedle sweep: heat map, faults flagged, gate verdict</h3>"
    "<p class='muted'>270 probes through four stub readers. A cell is flagged when fewer than 90% of its 3 probes "
    "pass, so one miss flags it. The gate is CI-style: overall at least 98%, every form-by-length slice at least "
    "90%, every depth band at least 90%.</p></div>",
    unsafe_allow_html=True,
)
st.button("Run the PolicyNeedle sweep  ->", key="cta_s4", on_click=run_stage, args=("stage4",))
if st.session_state["stage4"]:
    PR = RES["s4"]["per_reader"][RK]
    gate = PR["gate_by_length"][LENGTH]
    verdict_class = "pn-pass" if gate["verdict"] == "PASS" else "pn-fail"
    if gate["verdict"] == "PASS":
        tldr = "Every threshold is met on this manual. The probes are answerable and nothing is flagged."
    else:
        tldr = "Blocked. " + " ".join(b + "." for b in gate["broken"])
    st.markdown(
        f"""
<div class='pn-verdict {verdict_class}'>
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

    # --- heat map: depth by slice ------------------------------------------
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

    # --- faults flagged -------------------------------------------------------
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
    st.markdown("**Faults flagged** - {} pages".format(LENGTH))
    if flagged_rows:
        st.dataframe(pd.DataFrame(flagged_rows), use_container_width=True, hide_index=True)
    else:
        st.markdown("No cell is flagged. The harness stays quiet on the control.")

    # --- harness validity -----------------------------------------------------
    st.markdown("**Harness validity** - does the sweep flag every known fault cell and stay quiet on the control? "
                "(a cell is form x length x depth; 90 per reader)")
    val_rows = []
    for r in h.READERS:
        p = RES["s4"]["per_reader"][r["key"]]
        val_rows.append({"Reader": r["label"], "Known fault cells": p["known_cells"], "Flagged": p["flagged_cells"],
                         "True flags": p["true_flags"], "Misses": p["misses"], "False flags": p["false_flags"]})
    st.dataframe(pd.DataFrame(val_rows), use_container_width=True, hide_index=True)
    st.caption("This validates the scoring, slicing and flagging against stubs with known faults. It is not a recall "
               "estimate for faults nobody planted, and not a statement about any real model.")

    # --- utility --------------------------------------------------------------
    ut = RES["s4"]["utility"]
    st.markdown("**Utility** = (catch rate with PolicyNeedle - catch rate with short-document testing) x assistants launched per year")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🟢 PolicyNeedle catch", "{:.0f}% ({} of {})".format(100 * ut["catch_pn"], ut["pn_caught"], ut["failing_cells"]))
    m2.metric("🟢 Short-document catch", "{:.0f}% ({} of {})".format(100 * ut["catch_short"], ut["short_caught"], ut["failing_cells"]))
    m3.metric("🟡 Assistants launched per year", "{} (range {}-{})".format(ut["assistants_per_year"], *ut["assistants_range"]))
    m4.metric("🟡 Launches with faults caught", "{:.0f} per year".format(ut["utility"]))
    st.caption("The catch rates are measured on stubs with known faults, not on any real model. The assistants-per-year figure is "
               "a modeled assumption, and the product assumes each launch carries at least one such fault.")

    # --- known limit ------------------------------------------------------------
    lim = RES["s4"]["limit"]
    with st.expander("Known limit left in: exact-match scoring on synthetic wording"):
        st.markdown(
            "The harness scores {ns} probe types and cannot score {nu}: **{names}**.\n\n"
            "Demonstration: the control's correct answers wrapped in one sentence score {vp} of {vn} under exact match, "
            "{vf} of {vc} cells are flagged and the gate says {vg}. A correct but wordy reader would be flagged as "
            "broken. Paraphrase and verbosity are not covered; scoring a real assistant needs a tolerant scorer first."
            .format(ns=len(lim["scorable"]), nu=len(lim["unscorable"]), names=", ".join(lim["unscorable"]),
                    vp=lim["verbose_passed"], vn=lim["verbose_n"], vf=lim["verbose_flagged_cells"],
                    vc=lim["verbose_cells"], vg=lim["verbose_gate"]))

    with st.expander("Source data - the files behind every number"):
        st.caption("Files in data/. Regenerate with python3 data/_generate.py (seeded, standard library only).")
        st.dataframe(pd.read_csv(DATA_DIR / "manuals.csv"), use_container_width=True, hide_index=True)
        st.dataframe(pd.read_csv(DATA_DIR / "probes.csv").head(30), use_container_width=True, hide_index=True)
        st.dataframe(pd.read_csv(DATA_DIR / "probe_types.csv"), use_container_width=True, hide_index=True)

st.button("Reset", key="cta_reset", on_click=reset)

st.markdown(
    f"<div class='pn-card muted'>Portfolio prototype on synthetic data. Full PRD, architecture and step-script "
    f"walkthrough in the <a href='{BASE_URL}README.md' target='_blank'><code>README.md</code></a>. "
    f"Part of the <a href='https://vj-shipped-anyway.github.io/ai-pm-portfolio/' target='_blank'>AI PM portfolio</a>.</div>",
    unsafe_allow_html=True,
)
