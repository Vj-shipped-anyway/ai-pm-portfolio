"""SwapBrief - go or no-go brief for moving a production GenAI feature to a new model version.

Streamlit walkthrough. Every result is SIMULATED: data/_generate.py is a seeded
stub (not a model) that stands in for real evaluation runs, and no model is called.

  Step 1  pick a migration scenario
  Step 2  Without SwapBrief: what the average says (red) and what it hid (blue)
  Step 3  With SwapBrief: the decision and its rollback triggers (green)
  Step 4  Proof at scale: 200 simulated scenarios, plus what it still gets wrong

Slice tables, charts and the raw comparison tables sit in "See the data" expanders.

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
    page_title="SwapBrief - Catches the bad model swap the average calls safe",
    page_icon="🔀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
README_URL = GITHUB_URL + "/blob/main/13-swapbrief-model-migration/README.md"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"

SYSTEM_LABELS = {"A": "Model A", "B_old_prompt": "Model B, A's old prompt", "B_new_prompt": "Model B, retuned prompt"}

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, same card classes as HalluGuard
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Hero block */
.sb-hero {
  background: linear-gradient(135deg,#0f172a 0%, #1e3a5f 55%, #2a9d8f 100%);
  border-radius: 18px; padding: 36px 40px 32px 40px; color:#fff; margin-bottom:28px;
}
.sb-hero .brand {font-size:26px; font-weight:600; opacity:0.92; margin-bottom:12px;}
.sb-hero h1 {color:#fff !important; font-size:46px; line-height:1.12; margin:0 0 14px 0; font-weight:700;}
.sb-hero .sub {font-size:17px; line-height:1.5; opacity:0.93; max-width:820px; margin-bottom:22px;}
.sb-hero .pills {display:flex; flex-wrap:wrap; gap:10px; margin-top:14px;}
.sb-hero .pill {background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
                color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.sb-hero .pill a {color:#fff; text-decoration:none;}

/* Body cards */
.sb-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:22px 26px;
          margin-bottom:18px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.sb-card h3 {margin-top:0; color:#0f172a;}
.sb-step {display:inline-block; background:#1e3a5f; color:#fff; padding:3px 10px;
          border-radius:6px; font-size:12px; font-weight:600; letter-spacing:0.04em;
          text-transform:uppercase; margin-bottom:10px;}

/* Verdict card */
.verdict-card {border-radius:16px; padding:26px 30px; margin-bottom:18px; color:#fff;}
.verdict-pass {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.verdict-flag {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.verdict-review {background: linear-gradient(135deg,#b45309,#f59e0b);}
.verdict-card .vlabel {font-size:13px; opacity:0.9; letter-spacing:0.08em; text-transform:uppercase;}
.verdict-card .vbig {font-size:44px; font-weight:800; line-height:1.1; margin:4px 0 14px 0;}
.verdict-card .vmetric {font-size:20px; font-weight:600;}
.verdict-card .vrow {display:flex; flex-wrap:wrap; gap:24px; margin-top:12px;}
.verdict-card .vchip {background:rgba(255,255,255,0.18); padding:6px 12px; border-radius:999px;
                      font-size:13px; font-weight:600;}
.verdict-card .vtldr {margin-top:16px; font-size:15px; line-height:1.5; opacity:0.95;}
.verdict-card.mcard .vbig {font-size:52px; margin:6px 0 8px 0;}
.verdict-card.mcard .vtldr {margin-top:6px; font-size:14px;}

/* Red, blue and green panels (HalluGuard: wrong answer, source of truth, the fix) */
.bot-bad {background:#fef2f2; border:1px solid #fecaca; border-left:4px solid #dc2626;
          border-radius:10px; padding:16px 20px; color:#7f1d1d;}
.bot-good {background:#ecfdf5; border:1px solid #bbf7d0; border-left:4px solid #059669;
           border-radius:10px; padding:16px 20px; color:#065f46; margin-bottom:18px;}
.bot-truth {background:#eff6ff; border:1px solid #bfdbfe; border-left:4px solid #2563eb;
            border-radius:10px; padding:16px 20px; color:#1e3a8a;}
.bot-bad .sb-tag, .bot-good .sb-tag, .bot-truth .sb-tag {display:inline-block; color:#fff; font-size:12px;
        font-weight:800; letter-spacing:0.08em; padding:3px 10px; border-radius:6px; margin-bottom:10px;}
.bot-bad .sb-tag {background:#dc2626;}
.bot-good .sb-tag {background:#059669;}
.bot-truth .sb-tag {background:#2563eb;}
.sb-pair {display:flex; flex-wrap:wrap; gap:28px; margin-top:6px;}
.sb-k {font-size:12px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; opacity:0.85;}
.sb-dec {font-size:30px; font-weight:800; line-height:1.15;}
.sb-line {font-size:15px; line-height:1.5; margin-top:2px;}
.sb-fine {font-size:13px; line-height:1.5; margin-top:12px; opacity:0.88;}
.bot-bad ul, .bot-good ul, .bot-truth ul {margin:6px 0 0 18px; padding:0;}
.bot-bad li, .bot-good li, .bot-truth li {line-height:1.55; margin-bottom:3px;}

/* Notes */
.trust-card {background:#f8fafc; border:1px solid #cbd5e1; border-left:5px solid #1e3a5f; border-radius:12px;
             padding:16px 22px; margin-bottom:18px; color:#334155; font-size:15px; line-height:1.55;}
.limit-card {background:#f8fafc; border:1px dashed #94a3b8; border-radius:12px; padding:18px 24px; margin-bottom:18px;
             color:#475569; font-size:15px; line-height:1.55;}
.limit-card h4 {margin:0 0 8px 0; color:#334155; font-size:15px; letter-spacing:0.04em; text-transform:uppercase;}
.limit-card ul {margin:6px 0 0 18px; padding:0;}
.limit-card li {margin-bottom:5px;}

/* Buttons - one big primary CTA */
div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#1e3a5f,#0f172a) !important; color:#fff !important;
  border:0 !important; padding:14px 28px !important; font-size:17px !important;
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


@st.cache_data(show_spinner="Running 200 simulated scenarios (about 20 seconds the first time) ...")
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


def step_card(label: str, title: str, purpose: str) -> None:
    st.markdown(
        "<div class='sb-card'><span class='sb-step'>%s</span><h3>%s</h3><p class='muted'>%s</p></div>" % (
            esc(label), esc(title), purpose),
        unsafe_allow_html=True,
    )


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
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='sb-hero'>
  <div class='brand'>🔀 SwapBrief</div>
  <h1>Catches the bad model swap the average calls safe.</h1>
  <div class='sub'>The new model scores higher on average, so the team ships it. SwapBrief checks the slices, the cost and the slow calls first, then writes the decision and the rollback triggers.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>Simulated results - generator is a stub, not a model</span>
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
# STEP 1 - pick a scenario
# ---------------------------------------------------------------------------
step_card("Step 1", "Pick a migration scenario",
          "Model A is being retired. Model B scored higher on average. Pick a case and see what happens next.")
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

st.markdown(
    "<p class='muted'><b>Simulated evaluation results.</b> Every number on this page comes from a seeded generator "
    "(<code>data/_generate.py</code>), a stub, not a model, that stands in for real evaluation runs. Nothing here "
    "measures any real model, vendor or bank. The committed set is the 720-item evaluation in <code>data/</code>: "
    "8 slices and 3 conditions (model A, model B with A's old prompt, model B with a retuned prompt). The other six "
    "are simulated scenarios drawn from the same generator as the 200-scenario test, chosen to show each kind of "
    "outcome: a block, a cost problem, a clean pass, the known limit, a miss, and a guardrail that was not needed.</p>",
    unsafe_allow_html=True,
)

if st.session_state.step < 2:
    if st.button("Show what the average says  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

STATUS_COLOR = {"REGRESSED": "#b91c1c", "WATCH": "#d97706", "INCONCLUSIVE": "#6b7280", "OK": "#334155", "IMPROVED": "#047857"}

# ---------------------------------------------------------------------------
# STEP 2 - Without SwapBrief: the average says GO (red) / what it hid (blue)
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    step_card("Step 2", "Without SwapBrief - the average says %s" % head["decision"],
              "Most teams compare one number: did the average go up? Some also test whether the gain is bigger than noise.")

    shipped_tag = {"GO": "SHIPPED", "NO-GO": "BLOCKED"}.get(head["decision"], "HELD")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            "<div class='bot-bad'><span class='sb-tag'>%s</span>"
            "<div><b>The average says:</b></div>"
            "<div class='sb-pair'>"
            "<div><div class='sb-k'>Headline average</div><div class='sb-dec'>%s</div>"
            "<div class='sb-line'>A %.1f%% to B %.1f%% (%s)</div></div>"
            "<div><div class='sb-k'>Aggregate test</div><div class='sb-dec'>%s</div>"
            "<div class='sb-line'>McNemar p = %.4f; interval %s to %s</div></div>"
            "</div>"
            "<div class='sb-fine'>Headline rule: GO if B's overall average is higher. Test rule: GO if B is higher and "
            "significant at %.2f; HOLD if within noise. Slices looked at: none. Rollback triggers: %d. "
            "p is the chance of a gain this big from noise alone.</div></div>" % (
                shipped_tag, esc(head["decision"]), head["acc_a"] * 100, head["acc_b"] * 100, pp(head["delta"]),
                esc(basic["decision"]), basic["mcnemar_p"], pp(basic["ci_lo"]), pp(basic["ci_hi"]),
                basic["alpha"], len(head["rollback_triggers"])),
            unsafe_allow_html=True,
        )
    with c2:
        regressed = [r for r in res["slices"] if r["status"] == "REGRESSED"]
        unsettled = [r for r in res["slices"] if r["status"] in ("WATCH", "INCONCLUSIVE")]
        cost, lat = res["cost"], res["latency"]
        hid = bool(regressed or unsettled or cost["status"] != "OK" or lat["status"] != "OK")
        lines = []
        if regressed:
            for r in regressed:
                lines.append(
                    "<li><b>Slice that regressed:</b> <code>%s</code> (%s), %.1f%% to %.1f%% (%s), interval %+.1f to %+.1f pp</li>" % (
                        esc(r["slice"]), esc(r["severity"]), r["acc_a"] * 100, r["acc_b"] * 100, pp(r["delta"]),
                        r["lo"] * 100, r["hi"] * 100))
        else:
            lines.append("<li><b>Slice that regressed:</b> none in this scenario</li>")
        if unsettled:
            lines.append("<li><b>Not settled:</b> %s</li>" % ", ".join(
                "<code>%s</code> (%s)" % (esc(r["slice"]), esc(r["status"])) for r in unsettled))
        lines.append("<li><b>Cost per correct answer:</b> $%.5f (%+.1f%% vs A), %s</li>" % (
            cost["cpc_b"], (cost["ratio"] - 1) * 100, "inside the watch level" if cost["status"] == "OK" else "flagged " + esc(cost["status"])))
        lines.append("<li><b>p95 latency:</b> %.0f ms (%+.1f%% vs A), %s</li>" % (
            lat["p95_b"], (lat["p95_ratio"] - 1) * 100, "inside the watch level" if lat["status"] == "OK" else "flagged " + esc(lat["status"])))
        st.markdown(
            "<div class='bot-truth'><span class='sb-tag'>%s</span>"
            "<div><b>What the average did not show:</b></div><ul>%s</ul>"
            "<div class='sb-fine'>From the slice intervals, the cost per correct answer and the tail latency "
            "(model B with the retuned prompt against model A).</div></div>" % (
                "HIDDEN" if hid else "NOTHING HIDDEN", "".join(lines)),
            unsafe_allow_html=True,
        )

    ho, bo = view["headline_old"], view["basic_old"]
    st.caption(
        "Same model B with A's old prompt: headline %s (%s), aggregate test %s (p = %.4f). "
        "The aggregate rules cannot tell you which prompt has to ship with the model." % (
            ho["decision"], pp(ho["delta"]), bo["decision"], bo["mcnemar_p"]))

    # --- the data behind step 2 ------------------------------------------------
    with st.expander("See the data - slice intervals"):
        st.markdown(
            "<p class='muted'>Each dot is model B minus model A on one slice, with a 95% paired bootstrap interval "
            "(item pairs resampled within the slice). Diamonds mark the slice's tolerance. A slice is REGRESSED when "
            "its interval sits below zero and the change is beyond the tolerance, WATCH when it is not settled, "
            "INCONCLUSIVE when it has too few items to rule a regression out.</p>",
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

    with st.expander("See the data - cost per correct answer and tail latency"):
        st.markdown(
            "<p class='muted'>Price per token fell, but the cost that matters is the cost of a correct answer. "
            "The median improved, but the p95 is what a customer waiting on a slow call feels.</p>",
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
            fig2.add_trace(go.Bar(name="p50", x=[s["system"] for s in stats], y=[s["p50"] for s in stats], marker_color="#1f5fb0"))
            fig2.add_trace(go.Bar(name="p95", x=[s["system"] for s in stats], y=[s["p95"] for s in stats], marker_color="#f59e0b"))
            fig2.update_layout(barmode="group", height=340, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="latency (ms)",
                               title="Latency by system", plot_bgcolor="#ffffff")
            st.plotly_chart(fig2, use_container_width=True)
        with right:
            fig3 = go.Figure()
            fig3.add_trace(go.Bar(x=[s["system"] for s in stats], y=[s["cpc"] for s in stats], marker_color="#1f5fb0"))
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
        fig4.add_trace(go.Bar(x=mids, y=hb, name="Model B, retuned prompt", marker_color="#1f5fb0", opacity=0.75))
        fig4.update_layout(barmode="overlay", height=300, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="latency (ms)",
                           yaxis_title="calls", title="Latency distribution, all calls",
                           plot_bgcolor="#ffffff")
        st.plotly_chart(fig4, use_container_width=True)

    if st.session_state.step < 3:
        if st.button("See the fix  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With SwapBrief: the decision and its rollback triggers (green)
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    step_card("Step 3", "With SwapBrief - the decision and its rollback triggers",
              "Same data. SwapBrief checks every slice, the cost per correct answer and the p95, then writes one decision and the lines that roll it back.")

    decision_tag = {"NO-GO": "BLOCKED", "GO WITH GUARDRAILS": "FLAGGED", "GO": "CLEARED"}.get(res["decision"], "HELD")
    st.markdown(
        f"""
<div class='verdict-card verdict-pass'>
<div class='vlabel'>SwapBrief decision: model B with the retuned prompt</div>
<div class='vbig'>{esc(res['decision'])}</div>
<div class='vmetric'>With A's old prompt: {esc(res_old['decision'])}</div>
<div class='vrow'><span class='vchip'>{decision_tag}</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    why_html = "".join("<li>%s</li>" % esc(x) for x in res["reasons"])
    trig_html = ""
    for t in res["triggers"]:
        trig_html += "<li><code>%s</code> %s over %s%s: %s</li>" % (
            esc(t["metric"]), esc(t["threshold_text"]), esc(t["window"]),
            (", at least %d scored responses" % t["min_sample"]) if t["min_sample"] else "", esc(t["action"]))
    if res["inconclusive"]:
        limit_html = "".join(
            "<li><code>%s</code>: %d items, interval %+.1f to %+.1f pp. SwapBrief lists it and attaches a trigger; it cannot confirm or rule out a regression.</li>" % (
                esc(r["slice"]), r["n"], r["lo"] * 100, r["hi"] * 100) for r in res["inconclusive"])
    else:
        limit_html = "<li>No slice is inconclusive in this scenario.</li>"
    st.markdown(
        "<div class='bot-good'><span class='sb-tag'>%s</span>"
        "<div><b>Why:</b></div><ul>%s</ul>"
        "<div style='margin-top:12px'><b>Rollback triggers</b> (metric, threshold, window). The line that blocks at evaluation "
        "is the line that rolls back in production.</div><ul>%s</ul>"
        "<div class='sb-fine'><b>Known limit: slices with too few items stay inconclusive.</b></div><ul>%s</ul></div>" % (
            decision_tag, why_html, trig_html, limit_html),
        unsafe_allow_html=True,
    )

    if truth is not None:
        reg = truth.get("regressed_slices", [])
        st.markdown(
            "<div class='trust-card'><b>Generator's truth for this scenario (never shown to the rules):</b> "
            "truly regressed slices: %s. True cost per correct answer vs A: %.2fx. True p95 latency vs A: %.2fx.</div>" % (
                esc(", ".join(reg) if reg else "none"), truth["cost_ratio"], truth["p95_ratio"]),
            unsafe_allow_html=True,
        )

    st.download_button(
        "Download the decision brief (Markdown)",
        s4.brief_markdown(fair, "SwapBrief decision brief - %s" % chosen_label),
        file_name="swapbrief_brief_%s.md" % ("committed" if scenario_id == 0 else "S%03d" % scenario_id),
        mime="text/markdown",
    )

    with st.expander("See the data - the three rules side by side, and the trigger table"):
        cmp_rows = [
            {"rule": "Headline average (step 1)", "retuned prompt": head["decision"], "A's old prompt": view["headline_old"]["decision"]},
            {"rule": "Aggregate significance test (step 2)", "retuned prompt": basic["decision"], "A's old prompt": view["basic_old"]["decision"]},
            {"rule": "SwapBrief (step 4)", "retuned prompt": res["decision"], "A's old prompt": res_old["decision"]},
        ]
        st.dataframe(pd.DataFrame(cmp_rows), use_container_width=True, hide_index=True)
        st.markdown("**Rollback triggers** (metric, threshold, window).")
        trig = pd.DataFrame([{
            "metric": t["metric"], "threshold": t["threshold_text"], "window": t["window"],
            "min scored responses": str(t["min_sample"]) if t["min_sample"] else "n/a", "action": t["action"], "why": t["why"],
        } for t in res["triggers"]])
        st.dataframe(trig, use_container_width=True, hide_index=True)

    if st.session_state.step < 4:
        if st.button("See the proof at scale  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale: 200 simulated scenarios
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    step_card("Step 4", "Proof at scale - %d simulated migrations" % s4.gen.N_SCENARIOS,
              "Each scenario draws a new world with known true effects, runs the three rules and scores them against that truth. "
              "It takes about 20 seconds the first time.")

    dq = get_decision_quality()
    sc, ut = dq["scores"], dq["utility"]
    rules = sc["rules"]

    def metric_cards(title: str, note: str, key: str) -> None:
        st.markdown("**%s**  <span class='muted'>%s</span>" % (title, note), unsafe_allow_html=True)
        m_cols = st.columns(3)
        for col, (name, rule, css) in zip(m_cols, [("Headline average", "headline", "verdict-flag"),
                                                    ("Aggregate test", "basic", "verdict-review"),
                                                    ("SwapBrief", "swapbrief", "verdict-pass")]):
            with col:
                st.markdown(
                    "<div class='verdict-card mcard %s'><div class='vlabel'>%s</div><div class='vbig'>%.1f%%</div></div>" % (
                        css, name, rules[rule][key] * 100),
                    unsafe_allow_html=True,
                )

    metric_cards("False-GO rate", "A migration with a real problem got a plain GO. Lower is better.", "false_go_rate")
    metric_cards("Missed-regression rate", "A slice that truly regressed shipped while the rule called it fine. Lower is better.",
                 "missed_regression_rate")
    st.caption("%d scenarios: %d with a real problem, %d without; %d truly regressed slices." % (
        sc["n_scenarios"], sc["n_bad"], sc["n_good"], sc["total_true_regressed_slices"]))

    st.markdown(
        "<div class='trust-card'><b>Utility</b> = (headline bad-migration rate - SwapBrief bad-migration rate) x migrations per year "
        "= (%.1f%% - %.1f%%) x %d = <b>%.1f bad migrations avoided per year</b>. The two rates are 🟢 measured on these simulated "
        "scenarios (<code>step_04_with_swapbrief.py</code>). The %d migrations a year is a 🟡 modeled assumption: 9 production GenAI features, "
        "each forced onto a successor about every 18 months.</div>" % (
            ut["headline_rate"] * 100, ut["swapbrief_rate"] * 100, ut["migrations_per_year"], ut["avoided_per_year"],
            ut["migrations_per_year"]),
        unsafe_allow_html=True,
    )

    sw = rules["swapbrief"]
    st.markdown(
        "<div class='limit-card'><h4>What it still gets wrong</h4><ul>"
        "<li><b>Inconclusive slices.</b> SwapBrief left %d of %d true slice regressions unresolved (inconclusive). "
        "It lists the slice and attaches a trigger; it cannot say whether a regression is hiding there.</li>"
        "<li><b>Missed regressions.</b> It missed %d true slice regressions outright.</li>"
        "<li><b>Slow calls.</b> %d scenarios shipped with a real p95 problem it did not flag.</li>"
        "<li><b>One draw.</b> The committed 720-item set is one draw: seeds 1 to 300 were scanned and seed %d was committed "
        "because its draw shows the whole story (<code>data/README.md</code> lists the criteria). The 200-scenario test "
        "does not depend on that choice.</li>"
        "<li><b>All simulated.</b> The generator is a stub, not a model. Nothing here measures a real model, vendor or bank.</li>"
        "</ul></div>" % (sw["unresolved_regressions"], sc["total_true_regressed_slices"], sw["missed_regressions"],
                         sw["missed_p95_problems"], s4.gen.SEED),
        unsafe_allow_html=True,
    )

    with st.expander("See the data - all five measures"):
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
                                                      sw["unresolved_regressions"], sw["missed_regressions"]))

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
        st.rerun()

    st.markdown(
        "<div class='sb-card muted'>Built as a portfolio prototype on simulated data. Full walkthrough, PRD and architecture in the "
        f"<a href='{README_URL}' target='_blank'><code>README.md</code></a> of the 13-swapbrief-model-migration folder.</div>",
        unsafe_allow_html=True,
    )
