"""KillSwitch - fallback and degradation drills for an AI decision service.

Streamlit walkthrough. Pick one degradation event, then step through the story:
  Step 1  Pick an event
  Step 2  Without KillSwitch - the manual switch-off (what the plan does, and what actually happened)
  Step 3  With KillSwitch - warn, per-segment trip, the way back, bad decisions avoided
  Step 4  Proof at scale - the held-out days, the drill scorecard, and what it still gets wrong

All data is synthetic (data/_generate.py, seeded). The signals, tiers and state machine are plain
rules; the fallback "rules path" quality numbers are stubs set by the generator. There is no model
anywhere in this app.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from step_01_manual_switch_off import (  # noqa: E402
    CLUSTER_COMPLAINTS_3H, HOURS, MANUAL_DECISION_DELAY_H, SEGMENTS, TRAIN_END, fmt_h, hour_label, load_all, rnd, seg_long, type_label,
)
from step_04_with_killswitch import event_payload, natural_units, summarize  # noqa: E402

st.set_page_config(
    page_title="KillSwitch - A fallback that trips in hours and gets drilled",
    page_icon="🛑",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/25-killswitch-ai-fallback-drills/README.md"
SR_URL = "https://www.federalreserve.gov/supervisionreg/srletters/SR2024.htm"
NIST_URL = "https://www.nist.gov/itl/ai-risk-management-framework"

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.ks-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.ks-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.ks-hero h1 {color: #ffffff !important; font-size: 46px; line-height: 1.12; margin: 0 0 14px 0; font-weight: 700;}
.ks-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.ks-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.ks-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.ks-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.ks-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.ks-card h3 {margin-top: 0; color: #0f172a;}
.ks-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
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

/* Bot vs truth panel */
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


def num(x) -> str:
    return f"{rnd(x):,}"


def segs(names) -> str:
    return ", ".join(n.replace("_", " ") for n in names)


@st.cache_resource
def load_everything() -> dict:
    data = load_all(DATA_DIR)
    S = summarize(data)
    payloads = [event_payload(data, S["A"], S["man"], S["s2"]["tuned"], i) for i in range(len(data["events"]))]
    return {"data": data, "S": S, "P": payloads}


ALL = load_everything()
DATA, S, PAYLOADS = ALL["data"], ALL["S"], ALL["P"]
A = S["A"]
KS = A["summary"]
PP = A["P"]
CN, DL = CLUSTER_COMPLAINTS_3H, MANUAL_DECISION_DELAY_H
MAN = S["s1"]
THR = S["s2"]["tuned"]
HELD, FIT = "heldout", "train"

LABEL_TO_INDEX = {
    f"{p['event_id']}  -  day {p['start'] // 24 + 1}  -  {type_label(p['type'])}  -  {segs(p['segments'])}  -  "
    f"{'held out' if p['period'] == 'heldout' else 'fit period'}": i
    for i, p in enumerate(PAYLOADS)
}
LABELS = list(LABEL_TO_INDEX)
_fit_ids = [p["event_id"] for p in PAYLOADS if p["period"] == FIT]
_held_ids = [p["event_id"] for p in PAYLOADS if p["period"] == HELD]
FIT_RANGE = f"{_fit_ids[0]} to {_fit_ids[-1]}"
HELD_RANGE = f"{_held_ids[0]} to {_held_ids[-1]}"
HELD_DAYS = (HOURS - TRAIN_END) // 24
# The event shown first: among the held-out events, the one where KillSwitch serves the fewest bad
# decisions compared with the manual plan.
_gain = {i: p["manual"]["bad_total"] - p["killswitch"]["bad_total"] for i, p in enumerate(PAYLOADS) if p["period"] == HELD}
DEFAULT_LABEL = LABELS[max(_gain, key=_gain.get)]

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
<div class='ks-hero'>
  <div class='brand'>🛑 KillSwitch</div>
  <h1>A fallback that trips in {esc(fmt_h(KS[HELD]['median_delay_h']))} hours and gets drilled, not 'we will switch it off manually'.</h1>
  <div class='sub'>On the {(HOURS - TRAIN_END) // 24} held-out days it moved only the hurt segments to the rules path for {KS[HELD]['caught']} of {KS[HELD]['events']} events. The manual plan switched for {MAN[HELD]['caught']} of {MAN[HELD]['events']}.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>Stub rules path, not a model</span>
    <span class='pill'>{len(DATA['events'])} events · {len(SEGMENTS)} segments · {HOURS // 24} days</span>
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
# STEP 1 - pick an event
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='ks-card'><span class='ks-step-label'>Step 1</span>"
    "<h3>Pick a degradation event</h3>"
    f"<p class='muted'>{len(DATA['events'])} events across {len(SEGMENTS)} customer segments in {HOURS // 24} synthetic days. "
    f"{FIT_RANGE} fall in the fit period (days 1-{TRAIN_END // 24}, where thresholds are set); {HELD_RANGE} are held out (days {TRAIN_END // 24 + 1}-{HOURS // 24}, scored only). "
    "The one shown first is the held-out event where KillSwitch gains the most on the manual plan.</p></div>",
    unsafe_allow_html=True,
)
if "event_choice" not in st.session_state:
    st.session_state.event_choice = DEFAULT_LABEL
st.session_state.event_choice = st.selectbox(
    "Event:",
    LABELS,
    index=LABELS.index(st.session_state.event_choice),
    label_visibility="collapsed",
)
idx = LABEL_TO_INDEX[st.session_state.event_choice]
ev = PAYLOADS[idx]
raw = DATA["events"][idx]
man, thr, ks = ev["manual"], ev["threshold"], ev["killswitch"]
n_hours = ev["end"] - ev["start"]

st.markdown(
    "<p class='muted'>How to read the numbers: all data is synthetic and no model is used. A 'bad decision' is a decision "
    "worse than a healthy model would have made, counted as decisions times a rate the generator set. The weaker rules path "
    "has a quality gap per segment, a stub and not a measurement. The manual process is modeled: a person notices when "
    f"complaints reach {CN} in 3 hours, then needs {DL} hours to flip the switch, with perfect triage.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# STEP 2 - Without KillSwitch
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='ks-card'><span class='ks-step-label'>Step 2</span>"
        "<h3>Without KillSwitch - 'we will switch it off manually'</h3>"
        "<p class='muted'>The service degrades. Nobody has defined a trigger. Here is what the manual plan does, and what "
        "actually happened.</p></div>",
        unsafe_allow_html=True,
    )

    items = []
    if man["acted"]:
        items.append(
            f"<li><b>LATE.</b> Complaints reach {CN} in 3 hours at {esc(hour_label(man['cluster_hour']))}. After the {DL}-hour decision "
            f"delay the switch is flipped at {esc(hour_label(man['switch_hour']))}, {man['delay']} hours after the event began. "
            "Every segment moves to the rules path.</li>")
    elif man["cluster_hour"] is not None:
        items.append(
            f"<li><b>MISSED.</b> Complaints cluster at {esc(hour_label(man['cluster_hour']))}, but the {DL}-hour decision delay lands "
            "after the event has already ended. Nothing is switched.</li>")
    else:
        items.append(
            f"<li><b>MISSED.</b> Complaints never cluster: the busiest 3 hours reach {man['peak_complaints_3h']} against a notice "
            f"level of {CN}. Nobody switches.</li>")
    items.append(f"<li>Bad decisions served by the degraded model path: <b>{num(man['bad_served'])}</b>.</li>")
    if man["unneeded"]:
        items.append(f"<li>Decisions in healthy segments moved to the weaker rules path: <b>{num(man['unneeded'])}</b> "
                     "(the switch is all-or-nothing).</li>")
    if thr["caught"]:
        items.append(f"<li>A single threshold on the overall error rate trips at {esc(hour_label(thr['hour']))}, "
                     f"{thr['delay']} hours in, and moves all four segments.</li>")
    else:
        items.append("<li>A single threshold on the overall error rate never trips: the event moves the overall rate too little.</li>")
    red = ("<div class='bot-bad'><b>What the manual plan does:</b><ul>" + "".join(items) + "</ul>"
           f"<div class='small'>Total bad decisions, manual: {num(man['bad_total'])}. Modeled: the notice level, the {DL}-hour delay and "
           "perfect triage are assumptions, so this is a floor on the harm.</div></div>")

    peak = ev["killswitch"]["peak"]
    sig = (f"error rate {peak['error_rate']:.1f}, override rate {peak['override_rate']:.1f}, latency {peak['latency']:.1f}, "
           f"drift {peak['drift']:.1f}")
    if raw["type"] == "silent_error":
        moved = (f"No signal moved enough to see: the highest score was {ks['peak_score']:.1f} standard errors, against a "
                 f"warn level of {A['warn_z']:.2f}.")
    else:
        moved = f"Peak signal scores (standard errors above normal): {sig}."
    ramp = f" It ramps in over {ev['ramp']} hours." if ev["ramp"] else ""
    blue = ("<div class='bot-truth'><b>Source of truth - what actually happened (synthetic):</b><ul>"
            f"<li>{esc(type_label(ev['type']).capitalize())} in {esc(seg_long(ev['segments']))}, from {esc(hour_label(ev['start']))} "
            f"for {n_hours} hours.{esc(ramp)}</li>"
            f"<li>{100 * ev['bad_rate']:.0f}% of decisions in the affected segments were bad while it lasted: "
            f"{num(ev['decisions_in_event'])} decisions, <b>{num(ev['exposure'])}</b> bad decisions if nothing is done.</li>"
            f"<li>{esc(moved)}</li></ul></div>")
    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    with st.expander("See the data"):
        seg0 = ev["segments"][0]
        m = DATA["m"][seg0]
        a, b = max(0, ev["start"] - 3), min(HOURS, ev["start"] + 10)
        st.markdown(f"**Hourly signals for {seg0.replace('_', ' ')} around the start of the event (ground truth is in the title)**")
        st.dataframe(pd.DataFrame({
            "hour": [hour_label(h) for h in range(a, b)],
            "event active": ["yes" if ev["start"] <= h < ev["end"] else "no" for h in range(a, b)],
            "decisions": [m["dec"][h] for h in range(a, b)],
            "error rate": [m["err"][h] for h in range(a, b)],
            "latency p95 ms": [m["lat"][h] for h in range(a, b)],
            "drift score": [m["drift"][h] for h in range(a, b)],
            "override rate": [m["ovr"][h] for h in range(a, b)],
            "complaints (all segments)": [DATA["comp_all"][h] for h in range(a, b)],
        }), use_container_width=True, hide_index=True)
        st.markdown("**Manual process, all twelve events**")
        rows = []
        for p in PAYLOADS:
            mm = p["manual"]
            rows.append({"event": p["event_id"], "type": type_label(p["type"]), "segments": segs(p["segments"]),
                         "complaints notice": hour_label(mm["cluster_hour"]) if mm["cluster_hour"] is not None else "never",
                         "switch": hour_label(mm["switch_hour"]) if mm["acted"] else "no switch",
                         "bad decisions served": rnd(mm["bad_served"]), "bad total": rnd(mm["bad_total"])})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if st.session_state.step < 3:
        if st.button("See the fix ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With KillSwitch
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='ks-card'><span class='ks-step-label'>Step 3</span>"
        "<h3>With KillSwitch - warn, trip the hurt segment, come back safely</h3>"
        "<p class='muted'>Each segment is scored on its own signals every hour. A warn tells a person. A trip moves only that "
        f"segment to the rules path, holds it there for at least {PP['cool_off']} hours, and returns it once the signals stay clean.</p></div>",
        unsafe_allow_html=True,
    )
    per = ks["per_segment"]
    if ks["caught"]:
        rows = []
        for s_name in ks["segments_moved"]:
            d = per[s_name]
            ret = (f"returned {esc(hour_label(d['return']))}, {abs(d['after_end'])} hours "
                   f"{'after' if d['after_end'] >= 0 else 'before'} the event ended") if d["return"] is not None else "still on the rules path"
            warn = f"warn {esc(hour_label(d['warn']))}, " if d.get("warn") is not None else ""
            rows.append(f"<div class='vfind'><span class='vchip'>{esc(s_name.replace('_', ' '))}</span>{warn}"
                        f"<b>trip {esc(hour_label(d['first']))}</b> ({d['first'] - ev['start']} h in); {ret}.</div>")
        other = ks["other_segments_on_rules"]
        note = (f"<div class='vtldr'>{esc(segs(other))} also ran on the rules path: a false trip on noise, counted in the fit.</div>"
                if other else "<div class='vtldr'>No segment the event did not touch was moved.</div>")
        diff_t = thr["bad_total"] - ks["bad_total"]
        verdict = (
            "<div class='verdict-card verdict-pass'>"
            f"<div class='vlabel'>With KillSwitch - {esc(ev['event_id'])}</div>"
            f"<div class='vbig'>CAUGHT in {ks['delay']} h</div>"
            f"<div class='vmetric'>{esc(segs(ks['segments_moved']))} moved; {num(ks['protected'])} decisions protected</div>"
            "<div class='vrow'>"
            f"<span class='vchip'>Bad decisions, KillSwitch: {num(ks['bad_total'])}</span>"
            f"<span class='vchip'>Manual: {num(man['bad_total'])}</span>"
            f"<span class='vchip'>Single threshold: {num(thr['bad_total'])}</span></div>"
            + "".join(rows) + note + "</div>")
        st.markdown(verdict, unsafe_allow_html=True)
        if diff_t < 0:
            st.markdown(
                "<div class='limit-note'>Known cost. The single threshold served fewer bad decisions here "
                f"({num(thr['bad_total'])} against {num(ks['bad_total'])}) because it came back sooner. KillSwitch stays on the rules "
                "path until the signals are clean, which keeps it from flapping and costs decisions on loud, short events.</div>",
                unsafe_allow_html=True)
    else:
        st.markdown(
            "<div class='verdict-card verdict-review'>"
            f"<div class='vlabel'>With KillSwitch - {esc(ev['event_id'])}</div>"
            "<div class='vbig'>MISSED</div>"
            f"<div class='vmetric'>{num(ks['bad_served'])} bad decisions served</div>"
            f"<div class='vtldr'>A silent error moves no signal enough to see: the highest score was {ks['peak_score']:.1f} standard "
            f"errors against a warn level of {A['warn_z']:.2f}. KillSwitch cannot trip on what no metric shows. A golden-set canary "
            "or an outcome backtest would; both are designed and not built.</div></div>",
            unsafe_allow_html=True)
        st.markdown("<div class='limit-note'>This is the known limit left in on purpose.</div>", unsafe_allow_html=True)

    with st.expander("See the data"):
        if ks["caught"]:
            st.markdown("**Per segment: warn, trip and return**")
            st.dataframe(pd.DataFrame([{
                "segment": s_name, "warn": hour_label(per[s_name]["warn"]) if per[s_name].get("warn") is not None else "-",
                "trip": hour_label(per[s_name]["first"]),
                "returned": hour_label(per[s_name]["return"]) if per[s_name]["return"] is not None else "still on",
                "hours on rules path": (per[s_name]["return"] - per[s_name]["first"]) if per[s_name]["return"] is not None else None,
                "hours after event end": per[s_name]["after_end"],
                "lead signal": per[s_name].get("lead_signal")} for s_name in ks["segments_moved"]]),
                use_container_width=True, hide_index=True)
        a, b = max(0, ev["start"] - 12), min(HOURS, ev["end"] + 40)
        fig = go.Figure()
        palette = ["#1f5fb0", "#059669", "#f59e0b", "#7c3aed"]
        for k_i, s_name in enumerate(ev["segments"]):
            fig.add_scatter(x=list(range(a, b)), y=A["scores"][s_name]["score"][a:b], mode="lines", name=s_name.replace("_", " "),
                            line=dict(color=palette[k_i % 4], width=2))
        for name, level, color in (("trip", A["z_fit"], "#b91c1c"), ("warn", A["warn_z"], "#f59e0b"), ("clear", A["clear_z"], "#64748b")):
            fig.add_hline(y=level, line=dict(color=color, dash="dash", width=1), annotation_text=name, annotation_position="top left")
        fig.add_vrect(x0=ev["start"], x1=ev["end"], fillcolor="#fecaca", opacity=0.3, line_width=0)
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="hour (0 = day 1, 00:00)",
                          yaxis_title="worst signal, standard errors above normal", legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Shaded: the event. A segment trips when its line holds above the trip level for {PP['persist']} hours, and returns once it "
                   f"stays under the clear level for {PP['clear_hours']} hours (and at least {PP['cool_off']} hours after the trip).")

    if st.session_state.step < 4:
        if st.button("See the proof at scale ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    h_ks, h_m, h_t = KS[HELD], MAN[HELD], THR[HELD]
    util = S["util"]
    dr = S["drills"]
    st.markdown(
        "<div class='ks-card'><span class='ks-step-label'>Step 4</span>"
        f"<h3>Proof at scale - the {HELD_DAYS} held-out days</h3>"
        f"<p class='muted'>The trip level was fitted on days 1-{TRAIN_END // 24}. These numbers are days {TRAIN_END // 24 + 1}-{HOURS // 24}: {h_ks['events']} events no threshold "
        "was set on.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Manual switch-off (modeled)</div>"
        f"<div class='vbig'>{h_m['caught']} of {h_m['events']}</div>"
        "<div class='vmetric'>events switched before they ended</div>"
        f"<div class='vtldr'>{num(h_m['bad_per_event'])} bad decisions per event, healthy segments dragged along.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>One threshold on the overall error rate</div>"
        f"<div class='vbig'>{h_t['caught']} of {h_t['events']}</div>"
        "<div class='vmetric'>events tripped, tuned to the same false-trip budget</div>"
        f"<div class='vtldr'>{num(h_t['bad_per_event'])} bad decisions per event. It sees the loud events and misses the rest.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With KillSwitch</div>"
        f"<div class='vbig'>{h_ks['caught']} of {h_ks['events']}</div>"
        f"<div class='vmetric'>events tripped, median {esc(fmt_h(h_ks['median_delay_h']))} hours in</div>"
        f"<div class='vtldr'>{num(h_ks['bad_per_event'])} bad decisions per event, {h_ks['false_trips']} false trip, "
        f"{h_ks['retripped']} returns re-tripped.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>Drill scorecard</div>"
        f"<div class='vbig'>{dr['ready']} of {dr['required']}</div>"
        "<div class='vmetric'>scenarios ready</div>"
        f"<div class='vtldr'>{dr['stats']['failed']} of {dr['stats']['drills']} drills failed, "
        f"{dr['stats']['failed_stale']} of those on a stale rules version.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    silent_ids = [e["event_id"] for e in DATA["events"] if e["type"] == "silent_error"]
    silent_served = sum(PAYLOADS[i]["killswitch"]["bad_served"] for i, e in enumerate(DATA["events"]) if e["type"] == "silent_error")
    st.markdown(
        "<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>"
        f"<li>Silent errors: {len(silent_ids)} of {len(DATA['events'])} events ({', '.join(silent_ids)}) move no signal enough to see. "
        f"KillSwitch trips on none of them and {num(silent_served)} bad decisions are served.</li>"
        f"<li>The trip level, {A['z_fit']:.1f} standard errors, was fitted on {KS[FIT]['events']} synthetic events. It is a property of this "
        "data, not of any real service.</li>"
        "<li>The way back is careful: it keeps a segment on the rules path until the signals are clean, a median "
        f"{esc(fmt_h(KS['all']['median_recovery_after_end_h']))} hours after an event ends. On loud, short events the single threshold's "
        "instant return costs fewer bad decisions.</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Bad decisions per event, by approach**")
    st.caption("Expected bad decisions inside each event window, including the cost of the weaker rules path. Lower is better.")
    ids = [p["event_id"] for p in PAYLOADS]
    fig = go.Figure()
    fig.add_bar(x=ids, y=[p["manual"]["bad_total"] for p in PAYLOADS], name="manual (modeled)", marker_color="#b91c1c")
    fig.add_bar(x=ids, y=[p["threshold"]["bad_total"] for p in PAYLOADS], name="single threshold", marker_color="#f59e0b")
    fig.add_bar(x=ids, y=[p["killswitch"]["bad_total"] for p in PAYLOADS], name="KillSwitch", marker_color="#059669")
    fig.update_layout(barmode="group", height=340, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"{FIT_RANGE} are the fit period; {HELD_RANGE} are held out.")

    with st.expander("See the data"):
        st.markdown("**Results by period**")
        rows = []
        for label, summ in (("manual (modeled)", MAN), ("single threshold (tuned)", THR), ("KillSwitch", KS)):
            for p_key in (FIT, HELD):
                q = summ[p_key]
                rows.append({"approach": label, "period": q["label"], "events tripped": f"{q['caught']} of {q['events']}",
                             "median delay h": q["median_delay_h"], "false trips": q["false_trips"],
                             "switches per day": round(q["switches_per_day"], 2),
                             "bad decisions per event": rnd(q["bad_per_event"])})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown("**Fit: trip level against false trips (days 1-60) and what happens held out**")
        st.dataframe(pd.DataFrame([{
            "trip level": r["trip_z"], "false trips 1-60": r["train_false"],
            "caught 1-60": f"{r['train_caught']} of {r['train_events']}", "false trips 61-90": r["heldout_false"],
            "caught 61-90": f"{r['heldout_caught']} of {r['heldout_events']}",
            "bad per event 61-90": rnd(r["heldout_bad_per_event"])} for r in A["fit_table"]]),
            use_container_width=True, hide_index=True)
        st.markdown(f"**Fitted thresholds in units a person reads** (trip level {A['z_fit']:.1f}, warn {A['warn_z']:.2f}, "
                    f"clear {A['clear_z']:.2f} standard errors; typical daytime window)")
        st.dataframe(pd.DataFrame([{
            "segment": r["segment"], "decisions in window": r["n_typ"],
            "error rate normal": f"{100 * r['base_err']:.2f}%", "error rate trip": f"{100 * r['trip']['error_rate']:.2f}%",
            "latency normal ms": round(r["base_lat"]), "latency trip ms": round(r["trip"]["latency"]),
            "drift normal": round(r["base_drift"], 3), "drift trip": round(r["trip"]["drift"], 3)}
            for r in natural_units(DATA, A)]), use_container_width=True, hide_index=True)
        st.markdown("**Drill scorecard**")
        st.dataframe(pd.DataFrame([{"drill": r["drill_id"], "scenario": r["scenario"], "status": r["status"],
                                    "gaps": r["gaps"]} for r in dr["rows"]]), use_container_width=True, hide_index=True)
        st.dataframe(pd.DataFrame([{"scenario": r["scenario"], "state": r["state"], "why": r["why"]}
                                   for r in dr["scenarios"]]), use_container_width=True, hide_index=True)

    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("Fallback", "A simple rules engine that makes the decision when the model path is not trusted."),
            ("Trip", "Moving one segment to the rules path."),
            ("Warn", "A lower level that tells a person; it switches nothing."),
            ("Hysteresis", "A gap between the trip level and the clear level, so the switch does not flap."),
            ("Cool-off", f"The minimum time a segment stays on the rules path after a trip: {PP['cool_off']} hours."),
            ("Bad decision", "A decision worse than a healthy model would have made (expected count, synthetic)."),
            ("Held out", "Days 61-90: scored, never used to set a threshold."),
            ("Silent error", "Degradation that moves no signal enough to see."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is a signal collector, a scorer per segment, a "
            "controller that owns the per-segment switch state, a router that honors it, versioned rules with an owner, and a "
            "drill scheduler with a scorecard. It is a design, not deployed; see `ARCHITECTURE.md`. Related projects: DriftSentinel "
            "(02) and AgentWatch (05) supply signals, OversightOps (08) would own the human queue, IncidentLedger (19) would "
            "open an incident on a trip. All designed, none built."
        )
    st.markdown(
        "<div class='ks-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>. Reference: "
        f"<a href='{SR_URL}' target='_blank'>SR 20-24</a>, <a href='{NIST_URL}' target='_blank'>NIST AI RMF</a>.</div>",
        unsafe_allow_html=True,
    )
