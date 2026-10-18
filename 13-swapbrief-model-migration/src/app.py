"""SwapBrief - go or no-go brief for moving a production GenAI feature to a new model version.

Streamlit walkthrough. Every result is SIMULATED: data/_generate.py is a seeded
stub that stands in for real evaluation runs, and no model is called.

  Step 1   pick a migration scenario
  Stage 1  the headline decision (overall average) and the aggregate significance test
  Stage 2  the slice table with paired bootstrap intervals
  Stage 3  cost per correct answer and latency (p50 and p95)
  Stage 4  the SwapBrief decision and its rollback triggers
  Extra    decision quality over 200 simulated scenarios; production notes

Run from the repository root:  streamlit run 13-swapbrief-model-migration/src/app.py
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

SRC_DIR = Path(__file__).parent
DATA_DIR = SRC_DIR.parent / "data"
sys.path.insert(0, str(SRC_DIR))

import step_04_with_swapbrief as s4  # noqa: E402
from step_01_headline_average import load_dataset  # noqa: E402
from step_03_deficiencies_exposed import cost_per_correct, latency_stats  # noqa: E402

st.set_page_config(
    page_title="SwapBrief - go or no-go brief for a model migration",
    page_icon="🔀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
README_URL = GITHUB_URL + "/blob/main/13-swapbrief-model-migration/README.md"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"

SYSTEM_LABELS = {"A": "Model A", "B_old_prompt": "Model B, A's old prompt", "B_new_prompt": "Model B, retuned prompt"}

st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.sb-hero {
  background: linear-gradient(135deg,#0f172a 0%, #1e3a5f 55%, #2a9d8f 100%);
  border-radius: 18px; padding: 36px 40px; color:#fff; margin-bottom:22px;
}
.sb-hero .brand {font-size:26px; font-weight:600; opacity:0.95; margin-bottom:12px;}
.sb-hero h1 {color:#fff !important; font-size:38px; line-height:1.16; margin:0 0 14px 0; font-weight:700;}
.sb-hero .sub {font-size:17px; line-height:1.5; opacity:0.93; max-width:840px; margin-bottom:22px;}
.sb-hero .pills {display:flex; flex-wrap:wrap; gap:10px;}
.sb-hero .pill {background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
                color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.sb-hero .pill a {color:#fff; text-decoration:none;}

.sb-sim {background:#fff7ed; border:1px solid #fed7aa; border-radius:10px; padding:10px 16px;
         color:#7c2d12; font-size:14px; margin-bottom:18px;}
.sb-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:22px 26px;
          margin-bottom:18px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.sb-card h3 {margin-top:0; color:#0f172a;}
.sb-step {display:inline-block; background:#1e3a5f; color:#fff; padding:3px 10px;
          border-radius:6px; font-size:12px; font-weight:600; letter-spacing:0.04em;
          text-transform:uppercase; margin-bottom:10px;}
.sb-verdict {border-radius:16px; padding:24px 28px; margin-bottom:16px; color:#fff;}
.sb-go {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.sb-guard {background: linear-gradient(135deg,#b45309,#f59e0b);}
.sb-nogo {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.sb-hold {background: linear-gradient(135deg,#475569,#94a3b8);}
.sb-verdict .vlabel {font-size:13px; opacity:0.9; letter-spacing:0.08em; text-transform:uppercase;}
.sb-verdict .vbig {font-size:38px; font-weight:800; line-height:1.1; margin:4px 0 10px 0;}
.sb-verdict .vmetric {font-size:18px; font-weight:600;}
.sb-verdict .vtldr {margin-top:12px; font-size:15px; line-height:1.5; opacity:0.95;}
.sb-note {background:#f8fafc; border:1px solid #cbd5e1; border-left:5px solid #1e3a5f; border-radius:12px;
          padding:16px 22px; margin-bottom:18px; color:#334155; font-size:15px; line-height:1.55;}
div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#1e3a5f,#0f172a) !important; color:#fff !important;
  border:0 !important; padding:12px 26px !important; font-size:16px !important;
  font-weight:600 !important; border-radius:12px !important;
  box-shadow:0 4px 14px rgba(30,58,95,0.35) !important;
}
h1, h2, h3 {color:#0f172a;}
.muted {color:#64748b; font-size:14px;}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data (all cached; the dataset is the committed CSVs, the scenarios are re-drawn
# from the same seeded generator the 200-scenario test uses)
# ---------------------------------------------------------------------------
COMMITTED_LABEL = "Committed set: 720 items, the CSVs in data/"
SCENARIO_LABELS = [COMMITTED_LABEL] + ["S%03d: %s" % (i, text) for i, text in s4.CURATED]
SCENARIO_IDS = [0] + [i for i, _ in s4.CURATED]


@st.cache_data(show_spinner=False)
def load_base() -> dict:
    return load_dataset()


@st.cache_data(show_spinner="Analysing the scenario ...")
def get_scenario(scenario_id: int):
    base = load_base()
    if scenario_id == 0:
        return base, s4.committed_view(base)
    ds, truth = s4.scenario_dataset(scenario_id, base["policy"])
    return ds, s4.build_view(ds, s4.B_SIM, s4.SIM_BOOT_SEED + scenario_id, truth)


@st.cache_data(show_spinner="Running 200 simulated scenarios (about 20 seconds) ...")
def get_decision_quality() -> dict:
    base = load_base()
    records = s4.run_scenarios(policy=base["policy"])
    scores = s4.score_rules(records)
    return {"scores": scores, "utility": s4.utility(scores), "inconclusive": s4.inconclusive_counts(records),
            "curated_ok": s4.verify_curated(records)}


def esc(x) -> str:
    return html.escape(str(x))


def pp(x: float) -> str:
    return "%+.1f pp" % (x * 100)


def verdict_class(decision: str) -> str:
    return {"GO": "sb-go", "GO WITH GUARDRAILS": "sb-guard", "NO-GO": "sb-nogo", "HOLD": "sb-hold"}.get(decision, "sb-hold")


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "step" not in st.session_state:
    st.session_state.step = 1
if "scenario_label" not in st.session_state:
    st.session_state.scenario_label = COMMITTED_LABEL


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='sb-hero'>
  <div class='brand'>🔀 SwapBrief</div>
  <h1>A go or no-go brief for moving a production GenAI feature to a new model version.</h1>
  <div class='sub'>The vendor is retiring model A. The average score on model B went up. SwapBrief checks the slices,
  the cost per correct answer, the tail latency and the prompt, then writes the decision and the rollback triggers
  before anyone ships.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>720 simulated items · 8 slices · 3 conditions</span>
    <span class='pill'>Simulated data, no model called</span>
  </div>
</div>
<div class='sb-sim'><b>Simulated evaluation results.</b> The numbers on this page come from a seeded generator
(<code>data/_generate.py</code>, a stub that stands in for real evaluation runs). They are not measurements of any real
model, vendor or bank.</div>
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
# Step 1 - pick a scenario
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='sb-card'><span class='sb-step'>Step 1</span>"
    "<h3>Pick a migration scenario</h3>"
    "<p class='muted'>The committed set is the 720-item evaluation in <code>data/</code>. The other six are simulated "
    "scenarios drawn from the same generator as the 200-scenario test, chosen to show each kind of outcome: a block, "
    "a cost problem, a clean pass, the known limit, a miss, and a guardrail that was not needed.</p></div>",
    unsafe_allow_html=True,
)
chosen_label = st.selectbox(
    "Scenario:",
    SCENARIO_LABELS,
    index=SCENARIO_LABELS.index(st.session_state.scenario_label),
    label_visibility="collapsed",
)
st.session_state.scenario_label = chosen_label
scenario_id = SCENARIO_IDS[SCENARIO_LABELS.index(chosen_label)]
ds, view = get_scenario(scenario_id)
fair = view["fair"]
res = fair["retuned"]
res_old = fair["old"]
head = view["headline"]
basic = view["basic"]
truth = view["truth"]

if st.session_state.step < 2:
    if st.button("Show the headline decision  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# Stage 1 - headline decision and aggregate test
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='sb-card'><span class='sb-step'>Stage 1</span>"
        "<h3>The headline decision: did the average go up?</h3>"
        "<p class='muted'>What most teams do. Compare one number, model B with a prompt retuned for B against model A. "
        "Optionally ask whether the difference is bigger than noise.</p></div>",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"""
<div class='sb-verdict {verdict_class(head['decision'])}'>
  <div class='vlabel'>Before: the headline average</div>
  <div class='vbig'>{esc(head['decision'])}</div>
  <div class='vmetric'>A {head['acc_a']*100:.1f}% to B {head['acc_b']*100:.1f}% ({pp(head['delta'])})</div>
  <div class='vtldr'>Rule: GO if B's overall average is higher. Slices looked at: none. Rollback triggers: {len(head['rollback_triggers'])}.</div>
</div>""",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
<div class='sb-verdict {verdict_class(basic['decision'])}'>
  <div class='vlabel'>Basic approach: average plus a significance test</div>
  <div class='vbig'>{esc(basic['decision'])}</div>
  <div class='vmetric'>McNemar p = {basic['mcnemar_p']:.4f}; interval {pp(basic['ci_lo'])} to {pp(basic['ci_hi'])}</div>
  <div class='vtldr'>Rule: GO if B is higher and significant at {basic['alpha']:.2f}; HOLD if within noise. Slices looked at: none.</div>
</div>""",
            unsafe_allow_html=True,
        )
    ho, bo = view["headline_old"], view["basic_old"]
    st.caption(
        "Same model B with A's old prompt: headline %s (%s), aggregate test %s (p = %.4f). "
        "The aggregate rules cannot tell you which prompt has to ship with the model." % (
            ho["decision"], pp(ho["delta"]), bo["decision"], bo["mcnemar_p"]))

    if st.session_state.step < 3:
        if st.button("Show the slice intervals  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# Stage 2 - slice table with intervals
# ---------------------------------------------------------------------------
STATUS_COLOR = {"REGRESSED": "#b91c1c", "WATCH": "#d97706", "INCONCLUSIVE": "#6b7280", "OK": "#334155", "IMPROVED": "#047857"}

if st.session_state.step >= 3:
    st.markdown(
        "<div class='sb-card'><span class='sb-step'>Stage 2</span>"
        "<h3>The slice table: paired bootstrap intervals</h3>"
        "<p class='muted'>Each dot is model B minus model A on one slice, with a 95% paired bootstrap interval "
        "(item pairs resampled within the slice). Diamonds mark the slice's tolerance. A slice is REGRESSED when "
        "its interval sits below zero and the change is beyond the tolerance, WATCH when it is not settled, "
        "INCONCLUSIVE when it has too few items to rule a regression out.</p></div>",
        unsafe_allow_html=True,
    )
    prompt_choice = st.radio("Prompt used with model B:", ["Retuned prompt", "A's old prompt"], horizontal=True)
    current = res if prompt_choice == "Retuned prompt" else res_old
    rows = current["slices"]
    table = pd.DataFrame([{
        "slice": r["slice"], "severity": r["severity"], "items": r["n"],
        "A": "%.1f%%" % (r["acc_a"] * 100), "B": "%.1f%%" % (r["acc_b"] * 100),
        "change (pp)": "%+.1f" % (r["delta"] * 100),
        "95% interval (pp)": "%+.1f to %+.1f" % (r["lo"] * 100, r["hi"] * 100),
        "tolerance (pp)": "%.0f" % (r["tol"] * 100), "status": r["status"],
    } for r in rows])
    st.dataframe(table, use_container_width=True, hide_index=True)

    fig = go.Figure()
    names = [r["slice"] for r in rows]
    for r in rows:
        fig.add_trace(go.Scatter(
            x=[r["delta"] * 100], y=[r["slice"]], mode="markers", name=r["status"], showlegend=False,
            marker=dict(size=11, color=STATUS_COLOR[r["status"]]),
            error_x=dict(type="data", symmetric=False, array=[(r["hi"] - r["delta"]) * 100],
                         arrayminus=[(r["delta"] - r["lo"]) * 100], color=STATUS_COLOR[r["status"]], thickness=2),
            hovertemplate="%{y}<br>change %{x:+.1f} pp<extra>" + r["status"] + "</extra>",
        ))
    fig.add_trace(go.Scatter(
        x=[-r["tol"] * 100 for r in rows], y=names, mode="markers", showlegend=False,
        marker=dict(size=9, symbol="diamond-open", color="#0f172a"), hovertemplate="tolerance %{x:.0f} pp<extra></extra>"))
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="#94a3b8")
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="B minus A, percentage points",
                      yaxis=dict(autorange="reversed"), plot_bgcolor="#ffffff")
    st.plotly_chart(fig, use_container_width=True)

    slice_names = ["All slices"] + [r["slice"] for r in rows]
    slice_pick = st.selectbox("Look at one slice:", slice_names)
    if slice_pick != "All slices":
        r = [x for x in rows if x["slice"] == slice_pick][0]
        d1, d2, d3 = st.columns(3)
        d1.metric("Items in the slice", r["n"])
        d2.metric("Model A accuracy", "%.1f%%" % (r["acc_a"] * 100))
        d3.metric("Model B accuracy", "%.1f%%" % (r["acc_b"] * 100), pp(r["delta"]))
        e1, e2, e3 = st.columns(3)
        e1.metric("95% interval", "%+.1f to %+.1f pp" % (r["lo"] * 100, r["hi"] * 100))
        e2.metric("Refusal rate, A to B", "%.0f%% to %.0f%%" % (r["refusal_a"] * 100, r["refusal_b"] * 100))
        e3.metric("Status", r["status"])
        if r["status"] == "INCONCLUSIVE":
            st.info("Too few items to resolve this slice (%d). SwapBrief lists it and attaches a trigger; it cannot say "
                    "whether a regression is hiding here." % r["n"])
        if truth is not None:
            reg = truth.get("regressed_slices", [])
            old_only = truth.get("old_prompt_only", [])
            if slice_pick in reg:
                st.warning("The generator injected a real regression in this slice (the retuned prompt). "
                           "Truth is shown for teaching; the decision rule never sees it.")
            elif slice_pick in old_only:
                st.warning("The generator injected a regression in this slice only under A's old prompt.")
            else:
                st.caption("The generator injected no regression in this slice for the retuned prompt.")

    if truth is not None:
        reg = truth.get("regressed_slices", [])
        st.markdown(
            "<div class='sb-note'><b>Generator's truth for this scenario (never shown to the rules):</b> "
            "truly regressed slices: %s. True cost per correct answer vs A: %.2fx. True p95 latency vs A: %.2fx.</div>" % (
                esc(", ".join(reg) if reg else "none"), truth["cost_ratio"], truth["p95_ratio"]),
            unsafe_allow_html=True,
        )

    if st.session_state.step < 4:
        if st.button("Show cost and latency  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# Stage 3 - cost and latency
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='sb-card'><span class='sb-step'>Stage 3</span>"
        "<h3>Cost per correct answer and tail latency</h3>"
        "<p class='muted'>Price per token fell, but the cost that matters is the cost of a correct answer. "
        "The median improved, but the p95 is what a customer waiting on a slow call feels.</p></div>",
        unsafe_allow_html=True,
    )
    cost, lat = res["cost"], res["latency"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Cost per correct answer", "$%.5f" % cost["cpc_b"], "%+.1f%% vs A" % ((cost["ratio"] - 1) * 100), delta_color="inverse")
    m2.metric("p50 latency", "%.0f ms" % lat["p50_b"], "%+.1f%% vs A" % ((lat["p50_ratio"] - 1) * 100), delta_color="inverse")
    m3.metric("p95 latency", "%.0f ms" % lat["p95_b"], "%+.1f%% vs A" % ((lat["p95_ratio"] - 1) * 100), delta_color="inverse")
    st.caption(
        "95%% intervals (paired bootstrap, %d resamples): cost %+.1f%% to %+.1f%% (%s); p50 %+.1f%% to %+.1f%%; p95 %+.1f%% to %+.1f%% (%s)." % (
            res["bootstrap_resamples"], (cost["lo"] - 1) * 100, (cost["hi"] - 1) * 100, cost["status"],
            (lat["p50_lo"] - 1) * 100, (lat["p50_hi"] - 1) * 100,
            (lat["p95_lo"] - 1) * 100, (lat["p95_hi"] - 1) * 100, lat["status"]))

    stats = []
    for key, label in SYSTEM_LABELS.items():
        ls = latency_stats(ds, key)
        stats.append({"system": label, "p50": ls["p50"], "p95": ls["p95"], "cpc": cost_per_correct(ds, key)})
    left, right = st.columns(2)
    with left:
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(name="p50", x=[s["system"] for s in stats], y=[s["p50"] for s in stats], marker_color="#2a9d8f"))
        fig2.add_trace(go.Bar(name="p95", x=[s["system"] for s in stats], y=[s["p95"] for s in stats], marker_color="#1e3a5f"))
        fig2.update_layout(barmode="group", height=340, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="latency (ms)",
                           title="Latency by system", plot_bgcolor="#ffffff")
        st.plotly_chart(fig2, use_container_width=True)
    with right:
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=[s["system"] for s in stats], y=[s["cpc"] for s in stats], marker_color="#b45309"))
        fig3.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="USD per correct answer",
                           title="Cost per correct answer (synthetic prices)", plot_bgcolor="#ffffff")
        st.plotly_chart(fig3, use_container_width=True)

    lat_a = np.array(ds["cols"]["A"]["lat"], dtype=float)
    lat_b = np.array(ds["cols"]["B_new_prompt"]["lat"], dtype=float)
    top = float(max(lat_a.max(), lat_b.max()))
    edges = np.linspace(0, top, 41)
    ha, _ = np.histogram(lat_a, bins=edges)
    hb, _ = np.histogram(lat_b, bins=edges)
    mids = (edges[:-1] + edges[1:]) / 2.0
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(x=mids, y=ha, name="Model A", marker_color="#94a3b8", opacity=0.75))
    fig4.add_trace(go.Bar(x=mids, y=hb, name="Model B, retuned prompt", marker_color="#2a9d8f", opacity=0.75))
    fig4.update_layout(barmode="overlay", height=300, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="latency (ms)",
                       yaxis_title="calls", title="Latency distribution, all calls",
                       plot_bgcolor="#ffffff")
    st.plotly_chart(fig4, use_container_width=True)

    if st.session_state.step < 5:
        if st.button("Show the SwapBrief decision  ->", type="primary", key="cta_step4"):
            advance(5)
            st.rerun()

# ---------------------------------------------------------------------------
# Stage 4 - the decision and the rollback triggers
# ---------------------------------------------------------------------------
if st.session_state.step >= 5:
    st.markdown(
        "<div class='sb-card'><span class='sb-step'>Stage 4</span>"
        "<h3>The SwapBrief decision and its rollback triggers</h3>"
        "<p class='muted'>One decision for the prompt that would ship with model B, one for the in-place swap, and the "
        "metric, threshold and window that would roll the migration back.</p></div>",
        unsafe_allow_html=True,
    )
    reasons_html = "".join("<li>%s</li>" % esc(x) for x in res["reasons"])
    st.markdown(
        f"""
<div class='sb-verdict {verdict_class(res['decision'])}'>
  <div class='vlabel'>SwapBrief decision: model B with the retuned prompt</div>
  <div class='vbig'>{esc(res['decision'])}</div>
  <div class='vmetric'>With A's old prompt: {esc(res_old['decision'])}</div>
  <div class='vtldr'><ul style='margin:6px 0 0 18px'>{reasons_html}</ul></div>
</div>""",
        unsafe_allow_html=True,
    )
    cmp_rows = [
        {"rule": "Headline average (step 1)", "retuned prompt": head["decision"], "A's old prompt": view["headline_old"]["decision"]},
        {"rule": "Aggregate significance test (step 2)", "retuned prompt": basic["decision"], "A's old prompt": view["basic_old"]["decision"]},
        {"rule": "SwapBrief (step 4)", "retuned prompt": res["decision"], "A's old prompt": res_old["decision"]},
    ]
    st.dataframe(pd.DataFrame(cmp_rows), use_container_width=True, hide_index=True)

    st.markdown("**Rollback triggers** (metric, threshold, window). The line that blocks at evaluation is the line that rolls back in production.")
    trig = pd.DataFrame([{
        "metric": t["metric"], "threshold": t["threshold_text"], "window": t["window"],
        "min scored responses": str(t["min_sample"]) if t["min_sample"] else "n/a", "action": t["action"], "why": t["why"],
    } for t in res["triggers"]])
    st.dataframe(trig, use_container_width=True, hide_index=True)

    st.markdown("**Known limit: slices with too few items stay inconclusive.**")
    if res["inconclusive"]:
        for r in res["inconclusive"]:
            st.markdown("- `%s`: %d items, interval %+.1f to %+.1f pp. SwapBrief lists it and attaches a trigger; it cannot confirm or rule out a regression." % (
                r["slice"], r["n"], r["lo"] * 100, r["hi"] * 100))
    else:
        st.markdown("- No slice is inconclusive in this scenario.")

    st.download_button(
        "Download the decision brief (Markdown)",
        s4.brief_markdown(fair, "SwapBrief decision brief - %s" % chosen_label),
        file_name="swapbrief_brief_%s.md" % ("committed" if scenario_id == 0 else "S%03d" % scenario_id),
        mime="text/markdown",
    )

    # --- decision quality over 200 simulated scenarios ---------------------
    st.markdown(
        "<div class='sb-card'><span class='sb-step'>Test</span>"
        "<h3>Decision quality: 200 simulated migrations scored against the generator's truth</h3>"
        "<p class='muted'>Each scenario draws a new world with known true effects, runs the three rules and scores them. "
        "It takes about 20 seconds the first time.</p></div>",
        unsafe_allow_html=True,
    )
    if "dq_ready" not in st.session_state:
        st.session_state.dq_ready = False
    if not st.session_state.dq_ready:
        if st.button("Run the 200-scenario test  ->", type="primary", key="cta_dq"):
            st.session_state.dq_ready = True
            st.rerun()
    if st.session_state.dq_ready:
        dq = get_decision_quality()
        sc, ut = dq["scores"], dq["utility"]
        rules = sc["rules"]
        table2 = pd.DataFrame([
            {"measure": "False-GO rate (bad migration got GO)", "headline average": "%.1f%%" % (rules["headline"]["false_go_rate"] * 100),
             "aggregate test": "%.1f%%" % (rules["basic"]["false_go_rate"] * 100), "SwapBrief": "%.1f%%" % (rules["swapbrief"]["false_go_rate"] * 100)},
            {"measure": "Missed-regression rate (slices)", "headline average": "%.1f%%" % (rules["headline"]["missed_regression_rate"] * 100),
             "aggregate test": "%.1f%%" % (rules["basic"]["missed_regression_rate"] * 100), "SwapBrief": "%.1f%%" % (rules["swapbrief"]["missed_regression_rate"] * 100)},
            {"measure": "Bad-migration rate (all scenarios)", "headline average": "%.1f%%" % (rules["headline"]["bad_migration_rate"] * 100),
             "aggregate test": "%.1f%%" % (rules["basic"]["bad_migration_rate"] * 100), "SwapBrief": "%.1f%%" % (rules["swapbrief"]["bad_migration_rate"] * 100)},
            {"measure": "Good migrations blocked or held", "headline average": "%.1f%%" % (rules["headline"]["good_blocked_rate"] * 100),
             "aggregate test": "%.1f%%" % (rules["basic"]["good_blocked_rate"] * 100), "SwapBrief": "%.1f%%" % (rules["swapbrief"]["good_blocked_rate"] * 100)},
            {"measure": "Good migrations given guardrails", "headline average": "%.1f%%" % (rules["headline"]["good_guarded_rate"] * 100),
             "aggregate test": "%.1f%%" % (rules["basic"]["good_guarded_rate"] * 100), "SwapBrief": "%.1f%%" % (rules["swapbrief"]["good_guarded_rate"] * 100)},
        ])
        st.dataframe(table2, use_container_width=True, hide_index=True)
        st.caption("%d scenarios: %d with a real problem, %d without; %d truly regressed slices. SwapBrief left %d of those regressions unresolved "
                   "(inconclusive) and missed %d." % (sc["n_scenarios"], sc["n_bad"], sc["n_good"], sc["total_true_regressed_slices"],
                                                      rules["swapbrief"]["unresolved_regressions"], rules["swapbrief"]["missed_regressions"]))
        st.markdown(
            "<div class='sb-note'><b>Utility</b> = (headline bad-migration rate - SwapBrief bad-migration rate) x migrations per year "
            "= (%.1f%% - %.1f%%) x %d = <b>%.1f bad migrations avoided per year</b>. The two rates are 🟢 measured on these simulated "
            "scenarios (<code>step_04_with_swapbrief.py</code>). The %d migrations a year is a 🟡 modeled assumption: 9 production GenAI features, "
            "each forced onto a successor about every 18 months.</div>" % (
                ut["headline_rate"] * 100, ut["swapbrief_rate"] * 100, ut["migrations_per_year"], ut["avoided_per_year"],
                ut["migrations_per_year"]),
            unsafe_allow_html=True,
        )

    with st.expander("What this prototype does not cover"):
        st.markdown(
            "- Real models, real prompts, real traffic. Every result is drawn by a seeded generator.\n"
            "- Judging answers. In production the `correct` column comes from the evaluation harness "
            "(project 04, EvalForge); here it is simulated.\n"
            "- Prices. They are synthetic parameters in `data/prices.csv`; project 07 (InferenceLens) holds the real per-feature price and cost view in the design.\n"
            "- Snapshot pins. Rolling back to model A needs the pinned snapshot that project 02 (DriftSentinel) tracks in the design.\n"
            "- Slices with too few items. They stay inconclusive; the table says which."
        )
    with st.expander("Why this is a Streamlit prototype, not a production app"):
        st.markdown(
            "Streamlit is the right tool for walking a platform lead or a model risk reviewer through the mechanic. "
            "A production brief would live inside the bank's model inventory and release workflow, with SSO, role-based approval "
            "of thresholds (proposer and approver are different people), an append-only audit log and a scheduler that evaluates "
            "triggers against live scoring. See `ARCHITECTURE.md` for the design; nothing in it is deployed."
        )

    if st.button("Start over", key="reset"):
        st.session_state.step = 1
        st.session_state.dq_ready = False
        st.rerun()

    st.markdown(
        "<div class='sb-card muted'>Built as a portfolio prototype on simulated data. Full walkthrough, PRD and architecture in the "
        f"<a href='{README_URL}' target='_blank'><code>README.md</code></a> of the 13-swapbrief-model-migration folder.</div>",
        unsafe_allow_html=True,
    )
