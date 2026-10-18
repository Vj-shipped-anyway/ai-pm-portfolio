"""SchemaWatch - tool-schema drift detection for tool-calling agents.

Streamlit walkthrough. Pick one tool, then step through the four stages:
  Stage 1  Before        - no monitoring: calls fail, or quietly mean something else
  Stage 2  Basic         - version-string check and content hash
  Stage 3  Deficiencies  - which of the six named deficiencies hit this tool, with counts
  Stage 4  SchemaWatch   - schema diff, classification with reason, replayed calls that
                           would break, and the release-gate decision

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
from step_02_hash_and_version_check import score_releases  # noqa: E402
from step_04_with_schemawatch import analyze, DECISION_RANK  # noqa: E402

st.set_page_config(
    page_title="SchemaWatch - tool-schema drift detection",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/15-schemawatch-tool-schema-drift/README.md"
NIST_URL = "https://www.nist.gov/itl/ai-risk-management-framework"

st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.sw-hero {
  background: linear-gradient(135deg,#0b1f3a 0%, #1d4e89 55%, #00a6a6 100%);
  border-radius: 18px; padding: 36px 40px; color:#fff; margin-bottom:28px;
}
.sw-hero .brand {font-size:26px; font-weight:600; opacity:0.95; margin-bottom:12px;}
.sw-hero h1 {color:#fff !important; font-size:40px; line-height:1.14; margin:0 0 14px 0; font-weight:700;}
.sw-hero .sub {font-size:17px; line-height:1.5; opacity:0.93; max-width:820px; margin-bottom:22px;}
.sw-hero .pills {display:flex; flex-wrap:wrap; gap:10px;}
.sw-hero .pill {background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
                color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.sw-hero .pill a {color:#fff; text-decoration:none;}

.sw-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:22px 26px;
          margin-bottom:18px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.sw-card h3 {margin-top:0; color:#0f172a;}
.sw-step-label {display:inline-block; background:#1d4e89; color:#fff; padding:3px 10px;
                border-radius:6px; font-size:12px; font-weight:600; letter-spacing:0.04em;
                text-transform:uppercase; margin-bottom:10px;}

.gate-card {border-radius:16px; padding:26px 30px; margin-bottom:18px; color:#fff;}
.gate-allow {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.gate-block {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.gate-review {background: linear-gradient(135deg,#b45309,#f59e0b);}
.gate-card .glabel {font-size:13px; opacity:0.9; letter-spacing:0.08em; text-transform:uppercase;}
.gate-card .gbig {font-size:44px; font-weight:800; line-height:1.1; margin:4px 0 10px 0;}
.gate-card .gmetric {font-size:20px; font-weight:600;}
.gate-card .grow {display:flex; flex-wrap:wrap; gap:12px; margin-top:12px;}
.gate-card .gchip {background: rgba(255,255,255,0.18); padding:6px 12px; border-radius:999px;
                   font-size:13px; font-weight:600;}
.gate-card .gtldr {margin-top:14px; font-size:15px; line-height:1.5; opacity:0.96;}

.stage-card {background:#f8fafc; border:1px solid #cbd5e1; border-left:5px solid #1d4e89;
             border-radius:12px; padding:18px 22px; margin-bottom:16px;}
.stage-card h4 {margin:0 0 8px 0; color:#0f172a; font-size:15px; letter-spacing:0.04em;
                text-transform:uppercase;}
.stage-card li {color:#334155; line-height:1.55;}
.tag {display:inline-block; font-size:12px; font-weight:600; padding:2px 8px; border-radius:999px;}
.tag-breaking {background:#fee2e2; color:#991b1b;}
.tag-behavior_risk {background:#fef3c7; color:#92400e;}
.tag-non_breaking {background:#dcfce7; color:#166534;}
.limit-note {background:#fff7ed; border:1px solid #fdba74; border-radius:10px; padding:12px 16px;
             color:#7c2d12; font-size:14px; margin-bottom:14px;}

div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#1d4e89,#0b1f3a) !important; color:#fff !important;
  border:0 !important; padding:14px 28px !important; font-size:17px !important;
  font-weight:600 !important; border-radius:12px !important;
  box-shadow:0 4px 14px rgba(29,78,137,0.35) !important;
}
h1, h2, h3 {color:#0f172a;}
.muted {color:#64748b; font-size:14px;}
</style>
""",
    unsafe_allow_html=True,
)


def esc(v) -> str:
    return html.escape(str(v), quote=True)


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
    return a


A = load_analysis()
DATA = A["data"]
S = A["summary"]
S1 = A["step1"]
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
  <h1>Catches tool-schema drift before the agent's calls fail, or quietly mean something else.</h1>
  <div class='sub'>An agent calls tools. The tools are APIs with schemas owned by other teams. When an
  owner renames a parameter, tightens a type, adds a required field, drops an enum value or changes a
  unit in a description, nobody tells the agent team. SchemaWatch diffs each release, replays recorded
  calls against it, ranks the damage, and decides: block, review or allow.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>{S['tools']} tools · {S['releases']} releases · {S['changes']} changes · {S['calls']:,} calls</span>
    <span class='pill'>Synthetic, seeded data</span>
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
    "<p class='muted'>28 synthetic banking tools, ranked by blast radius. The default is the tool whose "
    "release breaks the most recorded calls. The truth is known because the generator injected every "
    "change: nothing here is a real bank, API or incident.</p></div>",
    unsafe_allow_html=True,
)
choice = st.selectbox("Tool:", LABELS, index=0, label_visibility="collapsed")
tool = LABEL_TO_TOOL[choice]
releases = [e for e in A["evaluated"] if e["tool"] == tool]
calls = DATA["calls_by_tool"].get(tool, [])
truth = DATA["truth"]
tool_changes = [c for c in DATA["ledger"] if c["tool"] == tool]

if st.session_state.step < 2:
    if st.button("Show what happens today  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - stage 1 (before) and stage 2 (basic approach)
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        f"<div class='sw-card'><span class='sw-step-label'>Stage 1 and 2</span>"
        f"<h3>{esc(tool)}: what happens without SchemaWatch</h3>"
        f"<p class='muted'>{len(calls)} recorded calls to this tool, all valid under v1. "
        f"{len(releases)} schema release(s) since.</p></div>",
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    with left:
        items = []
        if not releases:
            items.append("<li>No schema change since v1. Nothing fails, nothing alerts.</li>")
        for e in releases:
            ev = A["events"].get(e["release_id"])
            if ev:
                alert = (f"the {S1['alarm_failures']}th failure arrives {ev['alert_h']} h after release"
                         if ev["alert_h"] is not None else
                         f"only {ev['failed_calls']} calls fail in the week, so the error alarm never fires")
                items.append(f"<li><b>{esc(e['to_rev'])}</b>: {ev['failed_calls']} calls fail, first after "
                             f"{ev['first_failure_h']} h; {esc(alert)}.</li>")
            else:
                items.append(f"<li><b>{esc(e['to_rev'])}</b>: no recorded call fails.</li>")
        sil = [cid for cid in (c["call_id"] for c in calls)
               if truth[cid]["misread_unit"] or truth[cid]["misread_meaning"] or truth[cid]["shifted_default"]]
        items.append(f"<li><b>{len(sil)}</b> calls keep working but mean something different. They never "
                     f"fail, so they never alert.</li>")
        st.markdown(
            "<div class='stage-card'><h4>Stage 1 - Before: no monitoring</h4>"
            "<ul>" + "".join(items) + "</ul>"
            "<div class='muted'>Modeled: traffic after a release repeats the recorded week; an alert "
            f"fires on the {S1['alarm_failures']}th failed call; delivery is instant (a floor).</div></div>",
            unsafe_allow_html=True,
        )
    with right:
        items = []
        if not releases:
            items.append("<li>Nothing changed, so neither check fires.</li>")
        for e in releases:
            f = A["flags"][e["release_id"]]
            verdict = {"breaking": "needs action (breaking)", "behavior_risk": "needs action (behavior risk)",
                       "noise_only": "noise only: no action needed"}[f["release_class"]]
            ver = (f"version {esc(f['declared_before'])} to {esc(f['declared_after'])}: ALERT"
                   if f["version_alert"] else f"version stays {esc(f['declared_after'])}: <b>no alert</b>")
            items.append(f"<li><b>{esc(e['to_rev'])}</b>: {ver}. Content hash: ALERT. "
                         f"Ledger says: {esc(verdict)}.</li>")
        st.markdown(
            "<div class='stage-card'><h4>Stage 2 - Basic: version string or hash</h4>"
            "<ul>" + "".join(items) + "</ul>"
            "<div class='muted'>Neither tells you which change is breaking, how many calls break, "
            "or which alert to read first.</div></div>",
            unsafe_allow_html=True,
        )
    if st.session_state.step < 3:
        if st.button("Show where the basic approach breaks  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - stage 3 (six deficiencies on this tool)
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
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
    st.markdown(
        "<div class='sw-card'><span class='sw-step-label'>Stage 3</span>"
        "<h3>The six deficiencies, on this tool</h3>"
        "<p class='muted'>Counts come from the per-call truth file the generator wrote. "
        "Step 3 of the walkthrough runs the same measures over the whole estate.</p></div>",
        unsafe_allow_html=True,
    )
    df3 = pd.DataFrame(
        [{"#": r[0], "Deficiency": r[1], "Hits this tool": "yes" if r[2] else "no", "Evidence": r[3] if r[2] else "-"}
         for r in rows3]
    )
    st.dataframe(df3, use_container_width=True, hide_index=True)
    if st.session_state.step < 4:
        if st.button("Run SchemaWatch  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - stage 4 (SchemaWatch)
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='sw-card'><span class='sw-step-label'>Stage 4</span>"
        f"<h3>SchemaWatch on {esc(tool)}</h3>"
        "<p class='muted'>Structural diff and description heuristic, then a replay of the recorded calls "
        "against each new revision with a strict validator, then the gate.</p></div>",
        unsafe_allow_html=True,
    )
    if not releases:
        st.markdown(
            "<div class='gate-card gate-allow'><div class='glabel'>SchemaWatch release gate</div>"
            "<div class='gbig'>ALLOW</div><div class='gtldr'>No release since v1. Nothing to diff or replay.</div></div>",
            unsafe_allow_html=True,
        )
    for e in releases:
        cls = {"BLOCK": "gate-block", "REVIEW": "gate-review", "ALLOW": "gate-allow"}[e["decision"]]
        st.markdown(f"#### {e['release_id']}  ({e['declared_before']} to {e['declared_after']}, "
                    f"{'version bumped' if e['bumped'] else 'no version bump'})")
        fdf = pd.DataFrame([{"Change": f["kind"].replace("_", " "), "Parameter": f["param"] or "(tool description)",
                             "Class": f["class"].replace("_", " "), "Why": f["reason"],
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

        st.markdown(
            f"<div class='gate-card {cls}'><div class='glabel'>SchemaWatch release gate</div>"
            f"<div class='gbig'>{esc(e['decision'])}</div>"
            f"<div class='gmetric'>{len(e['newly_broken'])} calls would break · {len(e['at_risk'])} at risk</div>"
            f"<div class='grow'><span class='gchip'>Release: {esc(e['release_id'])}</span>"
            f"<span class='gchip'>Ledger-derived answer: {esc(e['should'])}</span></div>"
            f"<div class='gtldr'><b>Reason:</b> {esc(e['reason'])}</div></div>",
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

    # Fleet view
    st.markdown(
        "<div class='sw-card'><span class='sw-step-label'>Fleet view</span>"
        "<h3>Blast radius across all 28 tools</h3>"
        "<p class='muted'>Recorded calls that would break (replay) or are flagged as changing meaning, per tool.</p></div>",
        unsafe_allow_html=True,
    )
    top = A["tool_rows"][:12]
    fig = go.Figure()
    fig.add_bar(x=[r["tool"] for r in top], y=[r["would_break"] for r in top], name="would break", marker_color="#b91c1c")
    fig.add_bar(x=[r["tool"] for r in top], y=[r["at_risk"] for r in top], name="at risk (valid, different meaning)",
                marker_color="#f59e0b")
    fig.update_layout(barmode="stack", height=360, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.12), xaxis_tickangle=-35)
    st.plotly_chart(fig, use_container_width=True)
    gc = S["gate_counts"]
    cum = np.cumsum([d["failed"] for d in S1["daily"]])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gate decisions", f"{gc.get('BLOCK', 0)} block / {gc.get('REVIEW', 0)} review / {gc.get('ALLOW', 0)} allow")
    m2.metric("Classification vs ledger", f"{S['class_correct']} of {S['class_total']}")
    m3.metric("Replay vs true broken calls", f"{S['replay_pred_broken']} of {S['replay_true_broken']}")
    m4.metric("Calls failing in week 1 (no gate)", f"{int(cum[-1])}")
    st.markdown(
        f"<div class='limit-note'>Known limit, left in on purpose: {S['limit_changes']} meaning changes with no number and no "
        f"unit are not detected. They leave {S['limit_calls']} recorded calls misread.</div>",
        unsafe_allow_html=True,
    )

    with st.expander("Schema revisions for this tool"):
        for rv in DATA["revs"][tool]:
            st.markdown(f"**{rv}**, declared version `{DATA['schemas'][tool][rv]['declared_version']}`, "
                        f"released {DATA['schemas'][tool][rv]['released_at']}")
            st.json(DATA["schemas"][tool][rv]["schema"], expanded=False)
    with st.expander("Ledger rows for this tool (ground truth)"):
        if tool_changes:
            st.dataframe(pd.DataFrame(tool_changes)[["change_id", "to_rev", "change_type", "param", "old_value",
                                                     "new_value", "version_bumped", "true_class", "semantic_kind"]],
                         use_container_width=True, hide_index=True)
        else:
            st.markdown("No ledger rows: this tool never changed.")
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
