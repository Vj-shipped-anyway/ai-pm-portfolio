"""SchemaWatch - tool-schema drift detection for tool-calling agents.

Streamlit walkthrough. Pick one tool, then step through the story:
  Step 1  Pick a tool
  Step 2  Without SchemaWatch - the calls just start failing (what breaks, what a
          version check or hash says, and what actually changed per the ledger)
  Step 3  With SchemaWatch - classification with reason, replayed calls that would
          break, and the release-gate decision
  Step 4  Proof at scale - the same measures over all 28 tools, with the known limit

All data is synthetic (data/_generate.py, seeded). The diff, heuristic, validator and gate
are plain rules; there is no model anywhere in this app.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from step_01_no_monitoring import load_all, simulate, summarize as summarize_step1  # noqa: E402
from step_02_hash_and_version_check import score_releases, summarize as summarize_step2  # noqa: E402
from step_04_with_schemawatch import analyze, DECISION_RANK  # noqa: E402

st.set_page_config(
    page_title="SchemaWatch - Catches tool changes that break AI agents",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/15-schemawatch-tool-schema-drift/README.md"
NIST_URL = "https://www.nist.gov/itl/ai-risk-management-framework"

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.sw-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.sw-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.sw-hero h1 {color: #ffffff !important; font-size: 46px; line-height: 1.12; margin: 0 0 14px 0; font-weight: 700;}
.sw-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.sw-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.sw-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.sw-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.sw-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.sw-card h3 {margin-top: 0; color: #0f172a;}
.sw-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
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


def plain(v) -> str:
    """Escape for HTML and drop the backticks the step scripts use around names."""
    return esc(str(v).replace("`", ""))


def cls_label(c: str) -> str:
    return c.replace("non_breaking", "non-breaking").replace("_", " ")


def fmt_error(err: str) -> str:
    kind, param, msg = err.split(":", 2)
    return f"{kind.replace('_', ' ')} on {param}: {msg}"


@st.cache_resource
def load_analysis() -> dict:
    a = analyze(load_all(DATA_DIR))
    data = a["data"]
    a["flags"] = {r["release_id"]: r for r in score_releases(data)}
    a["events"] = {e["release_id"]: e for e in simulate(data)}
    a["step1"] = summarize_step1(data)
    a["step2"] = summarize_step2(data)
    return a


A = load_analysis()
DATA = A["data"]
S = A["summary"]
S1 = A["step1"]
S2 = A["step2"]
TOOLS = DATA["tools"]
TOOL_ROW = {r["tool"]: r for r in A["tool_rows"]}

# Option labels are plain strings; a dict maps label -> tool name.
LABEL_TO_TOOL = {
    f"{t}  -  {TOOL_ROW[t]['decision']}  -  {TOOL_ROW[t]['would_break']} calls would break": t
    for t in sorted(TOOLS, key=lambda x: TOOL_ROW[x]["rank"])
}
LABELS = list(LABEL_TO_TOOL)

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
<div class='sw-hero'>
  <div class='brand'>🔭 SchemaWatch</div>
  <h1>Catches tool changes that break an AI agent before release, not after its calls fail.</h1>
  <div class='sub'>Other teams change a tool's schema (its parameters and types) and nobody tells the agent team. SchemaWatch diffs each release, replays the agent's recorded calls against it, and says block, review or allow.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>No model: plain rules</span>
    <span class='pill'>{S['tools']} tools · {S['releases']} releases · {S['changes']} changes · {S['calls']:,} calls</span>
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
# STEP 1 - pick a tool
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='sw-card'><span class='sw-step-label'>Step 1</span>"
    "<h3>Pick a tool</h3>"
    f"<p class='muted'>{S['tools']} banking tools, each with recorded agent calls and a release history. "
    "The first one is the tool whose release breaks the most calls.</p></div>",
    unsafe_allow_html=True,
)
if "tool_choice" not in st.session_state:
    st.session_state.tool_choice = LABELS[0]
st.session_state.tool_choice = st.selectbox(
    "Tool:",
    LABELS,
    index=LABELS.index(st.session_state.tool_choice),
    label_visibility="collapsed",
)
tool = LABEL_TO_TOOL[st.session_state.tool_choice]
releases = [e for e in A["evaluated"] if e["tool"] == tool]
calls = DATA["calls_by_tool"].get(tool, [])
truth = DATA["truth"]
tool_changes = [c for c in DATA["ledger"] if c["tool"] == tool]

st.markdown(
    f"<div class='sw-card'><b>Tool:</b> <code>{esc(tool)}</code><br>"
    f"<span class='muted'>{len(calls)} recorded calls, all valid under v1. "
    f"{len(releases)} schema release(s) since.</span></div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p class='muted'>Synthetic data, no model. These banking tools are made up: nothing here is a real "
    "bank, API or incident. The generator injected every change, so the truth is known. The diff, the "
    "description heuristic, the validator and the gate are plain rules, not a model.</p>",
    unsafe_allow_html=True,
)

if st.session_state.step < 2:
    if st.button("Show what happens today  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - Without SchemaWatch: the calls just start failing
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='sw-card'><span class='sw-step-label'>Step 2</span>"
        "<h3>Without SchemaWatch - the calls just start failing</h3>"
        "<p class='muted'>The tool's owner shipped a new schema. Here is what happens to the agent's recorded "
        "calls, and what a version check or content hash tells you.</p></div>",
        unsafe_allow_html=True,
    )

    # RED: what the agent and the basic checks see
    items = []
    if not releases:
        items.append("<li>No schema change since v1. Nothing fails, nothing alerts.</li>")
    for e in releases:
        ev = A["events"].get(e["release_id"])
        f = A["flags"][e["release_id"]]
        if ev:
            alert = (f"the {S1['alarm_failures']}th failure arrives {ev['alert_h']} h after release"
                     if ev["alert_h"] is not None else
                     f"only {ev['failed_calls']} calls fail in the week, so the error alarm never fires")
            head = f"<b>{esc(e['to_rev'])}</b>: {ev['failed_calls']} calls fail, first after {ev['first_failure_h']} h; {esc(alert)}."
        else:
            head = f"<b>{esc(e['to_rev'])}</b>: no recorded call fails."
        ver = (f"version {esc(f['declared_before'])} to {esc(f['declared_after'])}: ALERT"
               if f["version_alert"] else f"version stays {esc(f['declared_after'])}: <b>no alert</b>")
        items.append(f"<li>{head}<br>Version check: {ver}. Content hash: ALERT.</li>")
    if releases:
        sil = [cid for cid in (c["call_id"] for c in calls)
               if truth[cid]["misread_unit"] or truth[cid]["misread_meaning"] or truth[cid]["shifted_default"]]
        items.append(f"<li><b>{len(sil)}</b> calls keep working but mean something different. They never "
                     f"fail, so they never alert.</li>")
    red = (
        "<div class='bot-bad'><b>What the agent and a version or hash check see (MISSED):</b>"
        "<ul>" + "".join(items) + "</ul>"
        "<div class='small'>Neither check says which change is breaking, how many calls break, or which "
        "alert to read first.</div>"
        "<div class='small'>Modeled: traffic after a release repeats the recorded week; an alert fires on "
        f"the {S1['alarm_failures']}th failed call; delivery is instant (a floor).</div></div>"
    )

    # BLUE: what actually changed, from the ledger
    verdicts = {"breaking": "needs action (breaking)", "behavior_risk": "needs action (behavior risk)",
                "noise_only": "noise only: no action needed"}
    items = []
    if not releases:
        items.append("<li>No ledger rows: this tool never changed.</li>")
    for e in releases:
        f = A["flags"][e["release_id"]]
        rows = [c for c in tool_changes if c["to_rev"] == e["to_rev"]]
        inner = "".join(
            f"<li>{esc(c['change_type'].replace('_', ' '))} on <code>{esc(c['param'] or '(tool description)')}</code>"
            f": {esc(cls_label(c['true_class']))}</li>" for c in rows)
        items.append(
            f"<li><b>{esc(e['to_rev'])}</b> (version {esc(e['declared_before'])} to {esc(e['declared_after'])}, "
            f"{'version bumped' if e['bumped'] else 'no version bump'}): ledger says "
            f"{esc(verdicts[f['release_class']])}.<ul>{inner}</ul></li>")
    blue = ("<div class='bot-truth'><b>Source of truth - what actually changed (ledger):</b>"
            "<ul>" + "".join(items) + "</ul></div>")

    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    # Data: ledger rows + the six named deficiencies on this tool
    ids = {c["change_id"]: c for c in tool_changes}
    cause_types = lambda cid: [ids[x]["change_type"] for x in truth[cid]["causes"] if x in ids]  # noqa: E731
    n_nb = sum(1 for c in tool_changes if c["true_class"] == "non_breaking")
    unb = [c for c in tool_changes if not c["bumped"]]
    sem = [c for c in tool_changes if c["semantic_kind"] != "none"]
    enum_rm = [c for c in tool_changes if c["change_type"] == "enum_value_removed"]
    enum_add = [c for c in tool_changes if c["change_type"] == "enum_value_added"]
    req = [c for c in tool_changes if c["change_type"] == "required_added"]
    dflt = [c for c in tool_changes if c["change_type"] == "default_changed"]
    call_ids = [c["call_id"] for c in calls]
    n_mis = sum(1 for cid in call_ids if truth[cid]["misread_unit"] or truth[cid]["misread_meaning"])
    n_enum = sum(1 for cid in call_ids if truth[cid]["broken"] and "enum_value_removed" in cause_types(cid))
    n_req = sum(1 for cid in call_ids if truth[cid]["broken"] and "required_added" in cause_types(cid))
    n_dflt = sum(truth[cid]["shifted_default"] for cid in call_ids)
    n_unb_broken = sum(1 for cid in call_ids if truth[cid]["broken"]
                       and any(not ids[x]["bumped"] for x in truth[cid]["causes"] if x in ids))
    rows3 = [
        ("a", "Breaking and non-breaking not separated",
         bool(tool_changes), f"{len(tool_changes)} changes behind the hash alert; {n_nb} are non-breaking"),
        ("b", "Versionless changes missed", bool(unb),
         f"{len(unb)} change(s) shipped without a version bump; {n_unb_broken} recorded calls break inside them"),
        ("c", "Semantic change invisible to a structural diff", bool(sem),
         f"{len(sem)} semantic change(s); {n_mis} calls pass validation and mean something different"),
        ("d", "Enum removal and addition treated alike", bool(enum_rm or enum_add),
         f"{len(enum_rm)} removal(s) break {n_enum} calls; {len(enum_add)} addition(s) break 0"),
        ("e", "New required field breaks every call", bool(req),
         f"{len(req)} required field(s) added; {n_req} of {len(calls)} calls break"),
        ("f", "Changed default silently alters behavior", bool(dflt),
         f"{len(dflt)} default(s) changed; {n_dflt} calls omit the parameter and get a different value"),
    ]
    with st.expander("See the data"):
        st.markdown("**Ledger rows for this tool (ground truth)**")
        if tool_changes:
            st.dataframe(pd.DataFrame(tool_changes)[["change_id", "to_rev", "change_type", "param", "old_value",
                                                     "new_value", "version_bumped", "true_class", "semantic_kind"]],
                         use_container_width=True, hide_index=True)
        else:
            st.markdown("No ledger rows: this tool never changed.")
        st.markdown("**The six named deficiencies of the basic checks, on this tool**")
        st.caption("Counts come from the per-call truth file the generator wrote. Step 3 of the README "
                   "walkthrough (step_03_deficiencies_exposed.py) runs the same measures over the whole estate.")
        df3 = pd.DataFrame(
            [{"#": r[0], "Deficiency": r[1], "Hits this tool": "yes" if r[2] else "no", "Evidence": r[3] if r[2] else "-"}
             for r in rows3]
        )
        st.dataframe(df3, use_container_width=True, hide_index=True)

    if st.session_state.step < 3:
        if st.button("See the fix  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With SchemaWatch: classify, replay, gate
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='sw-card'><span class='sw-step-label'>Step 3</span>"
        f"<h3>With SchemaWatch - {esc(tool)} is checked before it ships</h3>"
        "<p class='muted'>SchemaWatch compares the old and new schema, replays the recorded calls against the "
        "new one with a strict validator, then decides whether to hold the release.</p></div>",
        unsafe_allow_html=True,
    )
    if not releases:
        st.markdown(
            "<div class='verdict-card verdict-pass'><div class='vlabel'>With SchemaWatch - release gate</div>"
            "<div class='vbig'>ALLOW</div>"
            "<div class='vtldr'>No release since v1. Nothing to diff or replay.</div></div>",
            unsafe_allow_html=True,
        )
    for e in releases:
        n_broken, n_risk = len(e["newly_broken"]), len(e["at_risk"])
        finds = "".join(
            f"<div class='vfind'><span class='vchip'>{esc(cls_label(f['class']))}</span>"
            f"<b>{esc(f['kind'].replace('_', ' '))} {esc(f['param'] or '(tool description)')}</b>: {plain(f['reason'])}</div>"
            for f in e["findings"])
        st.markdown(
            "<div class='verdict-card verdict-pass'>"
            f"<div class='vlabel'>With SchemaWatch - release gate - {esc(e['release_id'])}</div>"
            f"<div class='vbig'>{esc(e['decision'])}</div>"
            f"<div class='vmetric'>Replay: {n_broken} of {e['n_calls']} recorded calls would fail strict validation</div>"
            "<div class='vrow'>"
            f"<span class='vchip'>{n_risk} more calls pass but are flagged as changing meaning</span>"
            f"<span class='vchip'>{'Version bumped' if e['bumped'] else 'No version bump'}: "
            f"{esc(e['declared_before'])} to {esc(e['declared_after'])}</span>"
            f"<span class='vchip'>Ledger-derived answer: {esc(e['should'])}</span></div>"
            + finds +
            f"<div class='vtldr'><b>Reason:</b> {plain(e['reason'])}</div></div>",
            unsafe_allow_html=True,
        )
        if e["decision"] != e["should"]:
            if e["decision"] == "ALLOW":
                note = ("Known limit. The ledger says this release changes meaning, but the change carries no "
                        "number and no unit, so the heuristic cannot see it. The gate says ALLOW and the "
                        "affected calls reach production.")
            else:
                note = ("False flag. The ledger says this release is cosmetic, but a number was rewritten as a "
                        "word, which the heuristic reads as a changed number. A person clears it in review.")
            st.markdown(f"<div class='limit-note'>{esc(note)}</div>", unsafe_allow_html=True)

    with st.expander("See the data"):
        for e in releases:
            st.markdown(f"#### {e['release_id']}  ({e['declared_before']} to {e['declared_after']}, "
                        f"{'version bumped' if e['bumped'] else 'no version bump'})")
            fdf = pd.DataFrame([{"Change": f["kind"].replace("_", " "), "Parameter": f["param"] or "(tool description)",
                                 "Class": cls_label(f["class"]), "Why": f["reason"],
                                 "Calls at risk": f["at_risk_calls"]} for f in e["findings"]])
            st.markdown("**Schema diff and classification**")
            st.dataframe(fdf, use_container_width=True, hide_index=True)

            st.markdown(f"**Replay: {len(e['newly_broken'])} of {e['n_calls']} recorded calls would fail strict validation**")
            if e["newly_broken"]:
                by_id = {c["call_id"]: c for c in calls}
                rdf = pd.DataFrame([{"call_id": cid, "arguments": json.dumps(by_id[cid]["args"]),
                                     "first violation": fmt_error(e["newly_broken_errors"][cid][0])}
                                    for cid in e["newly_broken"][:25]])
                st.dataframe(rdf, use_container_width=True, hide_index=True)
                if len(e["newly_broken"]) > 25:
                    st.caption(f"Showing 25 of {len(e['newly_broken'])} calls.")
            if e["at_risk"]:
                st.caption(f"{len(e['at_risk'])} further calls still validate but are flagged as changing meaning "
                           "(a unit or number moved in a description, or a default changed).")
        if not releases:
            st.markdown("No release since v1.")
        st.markdown("**Schema revisions for this tool**")
        for rv in DATA["revs"][tool]:
            st.markdown(f"**{rv}**, declared version `{DATA['schemas'][tool][rv]['declared_version']}`, "
                        f"released {DATA['schemas'][tool][rv]['released_at']}")
            st.json(DATA["schemas"][tool][rv]["schema"], expanded=False)

    # Evidence bundle
    lines = [f"# SchemaWatch release evidence: {tool}", "",
             "Synthetic data. Generated by the SchemaWatch prototype; not a real bank, tool or incident.", ""]
    for e in releases:
        lines += [f"## {e['release_id']}", f"- Declared version: {e['declared_before']} -> {e['declared_after']}",
                  f"- Gate: **{e['decision']}** (ledger-derived answer: {e['should']})",
                  f"- Recorded calls: {e['n_calls']}; would break: {len(e['newly_broken'])}; at risk: {len(e['at_risk'])}",
                  f"- Reason: {e['reason']}", "", "| Change | Parameter | Class | Why |", "| --- | --- | --- | --- |"]
        lines += [f"| {f['kind']} | {f['param'] or '(tool)'} | {f['class']} | {f['reason']} |" for f in e["findings"]]
        lines.append("")
    if not releases:
        lines.append("No release since v1.")
    st.download_button("Download release evidence (Markdown)", "\n".join(lines),
                       file_name=f"schemawatch_{tool}.md", mime="text/markdown")

    if st.session_state.step < 4:
        if st.button("See the proof at scale  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    gc = S["gate_counts"]
    cum = np.cumsum([d["failed"] for d in S1["daily"]])
    v = S2["version"]
    st.markdown(
        "<div class='sw-card'><span class='sw-step-label'>Step 4</span>"
        "<h3>Proof at scale</h3>"
        f"<p class='muted'>The same checks over the whole synthetic estate: {S['tools']} tools, "
        f"{S['changes']} changes, {S['calls']:,} recorded calls.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Without monitoring</div>"
        f"<div class='vbig'>{int(cum[-1])} of {S1['total_calls']:,}</div>"
        "<div class='vmetric'>recorded calls fail after the releases</div>"
        "<div class='vtldr'>Every one of these calls was valid under v1.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>Without SchemaWatch: version check</div>"
        f"<div class='vbig'>{v['tp']} of {S2['needs_action_releases']}</div>"
        "<div class='vmetric'>releases that needed action were caught</div>"
        "<div class='vtldr'>The rest shipped without a version bump, so the check stayed quiet.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With SchemaWatch: replay</div>"
        f"<div class='vbig'>{S['replay_pred_broken']} of {S['replay_true_broken']}</div>"
        f"<div class='vmetric'>failing calls predicted, {S['replay_fp']} false positives</div>"
        "<div class='vtldr'>Each recorded call is run against the new schema before the release ships.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With SchemaWatch: classification</div>"
        f"<div class='vbig'>{S['class_correct']} of {S['class_total']}</div>"
        "<div class='vmetric'>changes classified as in the ledger</div>"
        "<div class='vtldr'>Breaking, non-breaking or behavior risk, checked against the change ledger.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>"
        f"<li>{S['limit_changes']} meaning changes carry no number and no unit, so the heuristic cannot see "
        f"them. They leave {S['limit_calls']} recorded calls misread: they pass validation but mean "
        "something different.</li>"
        "<li>Replay equals the truth by construction. The generator and the validator both apply the declared "
        f"schema, so {S['replay_pred_broken']} of {S['replay_true_broken']} says nothing about servers that "
        "are stricter or looser than their published schema.</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Which tools take the most damage**")
    st.caption("Recorded calls that would break (replay) or are flagged as changing meaning, largest tools first.")
    top = A["tool_rows"][:12]
    fig = go.Figure()
    fig.add_bar(x=[r["tool"] for r in top], y=[r["would_break"] for r in top], name="would break", marker_color="#b91c1c")
    fig.add_bar(x=[r["tool"] for r in top], y=[r["at_risk"] for r in top], name="at risk (valid, different meaning)",
                marker_color="#f59e0b")
    fig.update_layout(barmode="stack", height=360, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.12), xaxis_tickangle=-35)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Release gate across the estate: {gc.get('BLOCK', 0)} BLOCK, {gc.get('REVIEW', 0)} REVIEW, "
               f"{gc.get('ALLOW', 0)} ALLOW.")

    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("Tool schema", "The JSON description of a tool's parameters: names, types, enums, required list, defaults, descriptions."),
            ("Release", "One new revision of one tool's schema. v1 is what the agent was built against."),
            ("Breaking", "A call that was valid before is rejected now."),
            ("Behavior risk", "The call still passes validation but means something different, or a default now differs."),
            ("Non-breaking", "Existing calls are unaffected."),
            ("Replay", "Validating the recorded calls against the new schema."),
            ("Blast radius", "How many recorded calls a release breaks or silently changes."),
            ("Gate", "BLOCK holds the release, REVIEW needs a person, ALLOW notifies only."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is a poller on the tool registry, a "
            "revision store keyed by content hash, a replay worker that reads recorded calls from the "
            "tool-call log, and a gate that posts a check on the owner's pipeline or holds a registry "
            "publish. It is a design, not deployed; see `ARCHITECTURE.md`. Related projects: AgentWatch (05) "
            "sees the runtime failure, PromptShield (06) is the tool-call gate, LineageLog (09) records which "
            "schema revision each call ran under."
        )
    st.markdown(
        "<div class='sw-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>. Framework reference: "
        f"<a href='{NIST_URL}' target='_blank'>NIST AI RMF</a>.</div>",
        unsafe_allow_html=True,
    )
