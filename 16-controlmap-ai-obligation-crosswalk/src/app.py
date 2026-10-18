"""ControlMap - AI obligation to control crosswalk.

Streamlit walkthrough. Pick one obligation, then step through the story:
  Step 1  Pick an obligation
  Step 2  Without ControlMap - what the keyword spreadsheet says (red) and what is true (blue)
  Step 3  With ControlMap - the status, with the matched control, its scope and its evidence age
  Step 4  Proof at scale - the same measures over all 48 obligations, with the known limit

All data is synthetic (data/_generate.py, seeded). The dictionary, the scope check and the freshness
check are plain rules; there is no model anywhere in this app.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from step_01_status_quo import AS_OF, STALE_FACTOR, load_all, scope_label  # noqa: E402
from step_04_with_controlmap import analyze, explain, picker_order  # noqa: E402

st.set_page_config(
    page_title="ControlMap - Every AI obligation mapped to a control and fresh evidence",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/16-controlmap-ai-obligation-crosswalk/README.md"
NIST_URL = "https://www.nist.gov/itl/ai-risk-management-framework"

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.cm-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.cm-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.cm-hero h1 {color: #ffffff !important; font-size: 44px; line-height: 1.12; margin: 0 0 14px 0; font-weight: 700;}
.cm-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.cm-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.cm-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.cm-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.cm-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.cm-card h3 {margin-top: 0; color: #0f172a;}
.cm-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
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

/* Sheet vs truth panel */
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


@st.cache_resource
def load_analysis() -> dict:
    return analyze(load_all(DATA_DIR))


A = load_analysis()
DATA = A["data"]
S = A["summary"]
ROWS = {r["obligation_id"]: r for r in A["rows"]}


_wrong = {}
for _r in A["rows"]:
    if not _r["ok"]:
        _wrong[(_r["truth_status"], _r["status"])] = _wrong.get((_r["truth_status"], _r["status"]), 0) + 1
WRONG_TEXT = "; ".join(f"{n} truth {a} read as {b}" for (a, b), n in sorted(_wrong.items())) or "none"

ORDER = picker_order(A["rows"])
# Option labels are plain strings; a dict maps label -> obligation id.
LABEL_TO_OB = {f"{r['obligation_id']}  -  {r['short']}  -  {r['theme']}  -  {r['status']}": r["obligation_id"] for r in ORDER}
LABELS = list(LABEL_TO_OB)

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
<div class='cm-hero'>
  <div class='brand'>🗺️ ControlMap</div>
  <h1>Every AI obligation mapped to a control and fresh evidence: {S['cm_ok']} of {S['obligations']} right, not {S['sheet_ok']} from a keyword spreadsheet.</h1>
  <div class='sub'>A keyword spreadsheet marks an obligation covered when two words match. ControlMap checks the control's wording, scope and evidence date, then says covered, partial, stale or uncovered.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>No model: plain rules</span>
    <span class='pill'>{S['obligations']} obligations · {S['controls']} controls · 4 frameworks</span>
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
# STEP 1 - pick an obligation
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='cm-card'><span class='cm-step-label'>Step 1</span>"
    "<h3>Pick an obligation</h3>"
    f"<p class='muted'>{S['obligations']} AI-related obligations from four frameworks. "
    "The first ones are where the spreadsheet is most wrong.</p></div>",
    unsafe_allow_html=True,
)
if "ob_choice" not in st.session_state:
    st.session_state.ob_choice = LABELS[0]
st.session_state.ob_choice = st.selectbox(
    "Obligation:",
    LABELS,
    index=LABELS.index(st.session_state.ob_choice),
    label_visibility="collapsed",
)
oid = LABEL_TO_OB[st.session_state.ob_choice]
R = ROWS[oid]
E = explain(A, oid)

st.markdown(
    f"<div class='cm-card'><b>{esc(E['short'])}</b> · theme <b>{esc(E['theme'])}</b> · applies to {esc(E['applies_to'])}<br>"
    f"“{esc(E['statement'])}”<br>"
    "<span class='muted'>Paraphrase written for this exercise, not the text of the rule.</span></div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p class='muted'>Synthetic data, no model. The frameworks are real names; the obligation wording, the bank, its controls "
    "and its evidence are made up, and the generator decided which control meets which obligation, so the truth is known. "
    f"Evidence is fresh when the latest item is no older than {STALE_FACTOR:g} times the control's test cycle, counted at {esc(AS_OF.isoformat())}. "
    "Statuses: COVERED (a full-scope control with fresh evidence), STALE (a full-scope control, old evidence), PARTIAL (only "
    "controls that miss part of the scope), UNCOVERED (no control).</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# STEP 2 - Without ControlMap: what the spreadsheet says
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='cm-card'><span class='cm-step-label'>Step 2</span>"
        "<h3>Without ControlMap - the failure</h3>"
        "<p class='muted'>The sheet marks an obligation covered when two words overlap with a control. "
        "Red: what the spreadsheet says. Blue: what is true.</p></div>",
        unsafe_allow_html=True,
    )
    sh = E["sheet"]
    items = []
    for it in sh["items"]:
        words = ", ".join(f"“{esc(w)}”" for w in it["shared"])
        mark = "Meets it." if it["is_true"] else "Does not meet it."
        items.append(f"<li><code>{esc(it['id'])}</code> {esc(it['name'])}: shares {words}. <b>{esc(mark)}</b></li>")
    if sh["n_more"]:
        items.append(f"<li>and {sh['n_more']} more control{'s' if sh['n_more'] != 1 else ''} linked the same way.</li>")
    if not sh["items"]:
        items.append("<li>No control shares two words with this obligation.</li>")
    red = (
        f"<div class='bot-bad'><b>What the keyword spreadsheet says ({esc(sh['tag'])}):</b>"
        f"<ul><li>Status: <b>{esc(sh['status'])}</b>. {esc(sh['tag'])}: {esc(sh['why'])}.</li>" + "".join(items) + "</ul>"
        "<div class='small'>The sheet has one status, no scope, no evidence date and no list of controls that serve nothing.</div></div>"
    )
    tr = E["truth"]
    t_items = []
    for it in tr["items"]:
        t_items.append(
            f"<li><code>{esc(it['id'])}</code> {esc(it['name'])}: <b>{esc(it['coverage'])}</b> coverage; scope {esc(it['scope'])}; "
            f"{esc(it['evidence'])}.</li>")
    blue = (
        f"<div class='bot-truth'><b>Source of truth - the generator's answer: {esc(tr['status'])}</b>"
        f"<ul><li>{esc(tr['why'][0].upper() + tr['why'][1:])}.</li>" + "".join(t_items) + "</ul></div>"
    )
    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**Controls linked by the sheet, by the truth and by ControlMap for this obligation**")
        sheet_ids = {i for i in R["sheet_controls"]}
        cm_ids = {l["control_id"] for l in R["links"]}
        true_ids = set(DATA["truth_by_ob"].get(oid, {}))
        rows_d = []
        for cid in sorted(sheet_ids | cm_ids | true_ids):
            c = DATA["ct_by_id"][cid]
            fr = DATA["fresh"][cid]
            rows_d.append({
                "control": cid, "name": c["name"], "scope": scope_label(c["scope"]), "test cycle (days)": c["freq"],
                "in sheet": "yes" if cid in sheet_ids else "", "in truth": DATA["truth_by_ob"].get(oid, {}).get(cid, ""),
                "in ControlMap": "yes" if cid in cm_ids else "", "latest evidence": fr["latest"] or "none",
                "age (days)": str(fr["age"]) if fr["age"] is not None else "", "evidence": fr["state"],
            })
        if rows_d:
            st.dataframe(pd.DataFrame(rows_d), use_container_width=True, hide_index=True)
        else:
            st.markdown("No control is linked by the sheet, the truth or ControlMap.")
        same = [o for o in DATA["obligations"] if o["theme"] == R["theme"] and o["obligation_id"] != oid]
        if same:
            st.markdown("**Other obligations with the same theme (asked as separate evidence requests today)**")
            st.dataframe(pd.DataFrame([{"obligation": o["obligation_id"], "framework": o["framework"], "statement": o["statement"]}
                                       for o in same]), use_container_width=True, hide_index=True)

    if st.session_state.step < 3:
        if st.button("See the fix  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With ControlMap
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='cm-card'><span class='cm-step-label'>Step 3</span>"
        f"<h3>With ControlMap - {esc(oid)} gets a status with reasons</h3>"
        "<p class='muted'>ControlMap reads the wording through a theme dictionary, checks whether the control's scope covers "
        "every class the obligation applies to, and checks how old the latest evidence is.</p></div>",
        unsafe_allow_html=True,
    )
    cm = E["cm"]
    finds = "".join(
        f"<div class='vfind'><span class='vchip'>{esc(it['coverage'])}</span>{esc(it['text'])}</div>" for it in cm["items"])
    if not cm["items"]:
        finds = "<div class='vfind'>No active control's name or description contains a phrase from this theme's dictionary group.</div>"
    st.markdown(
        "<div class='verdict-card verdict-pass'>"
        f"<div class='vlabel'>With ControlMap - {esc(oid)} - {esc(cm['tag'])}</div>"
        f"<div class='vbig'>{esc(cm['status'])}</div>"
        f"<div class='vmetric'>Spreadsheet said {esc(E['sheet']['status'])}; the truth is {esc(E['truth']['status'])}</div>"
        "<div class='vrow'>"
        f"<span class='vchip'>Right status: {'yes' if cm['ok'] else 'no'}</span>"
        f"<span class='vchip'>Spreadsheet right: {'yes' if cm['sheet_ok'] else 'no'}</span></div>"
        + finds +
        "<div class='vtldr'>Fresh evidence shows something was collected recently. It does not show the control works.</div></div>",
        unsafe_allow_html=True,
    )
    if cm["note"]:
        st.markdown(f"<div class='limit-note'><b>Known limit.</b> {esc(cm['note'])}</div>", unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**Evidence items for the controls ControlMap linked**")
        ev_rows = []
        for l in R["links"]:
            for e in DATA["ev_by_ct"].get(l["control_id"], []):
                ev_rows.append({"evidence": e["evidence_id"], "control": l["control_id"], "type": e["evidence_type"],
                                "collected on": e["collected_on"], "reviewer": e["reviewer"]})
        if ev_rows:
            st.dataframe(pd.DataFrame(ev_rows), use_container_width=True, hide_index=True)
        else:
            st.markdown("No evidence to show: ControlMap linked no control.")

    lines = [f"# ControlMap exam note: {oid}", "",
             "Synthetic data. Prototype output; not a real bank, control library or regulator file.", "",
             f"- Framework: {E['framework']}", f"- Theme: {E['theme']}", f"- Applies to: {E['applies_to']}",
             f"- Statement (paraphrase written for this exercise): {E['statement']}",
             f"- ControlMap status: **{cm['status']}** (the generator's answer: {E['truth']['status']})", ""]
    lines += [f"- {it['text']}" for it in cm["items"]] or ["- No control linked."]
    st.download_button("Download exam note (Markdown)", "\n".join(lines),
                       file_name=f"controlmap_{oid}.md", mime="text/markdown")

    if st.session_state.step < 4:
        if st.button("See the proof at scale  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='cm-card'><span class='cm-step-label'>Step 4</span>"
        "<h3>Proof at scale</h3>"
        f"<p class='muted'>The same checks over all {S['obligations']} obligations and {S['controls']} controls.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Without ControlMap: keyword spreadsheet</div>"
        f"<div class='vbig'>{S['sheet_ok']} of {S['obligations']}</div>"
        "<div class='vmetric'>obligations given the right status</div>"
        f"<div class='vtldr'>It marks {A['sheet_covered']} covered; {S['truth_covered_any']} have a control that meets them.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With ControlMap</div>"
        f"<div class='vbig'>{S['cm_ok']} of {S['obligations']}</div>"
        "<div class='vmetric'>obligations given the right status</div>"
        f"<div class='vtldr'>Pair precision {S['precision_pct']}%, recall {S['recall_pct']}% against the truth map.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>Orphan controls</div>"
        f"<div class='vbig'>{S['orphans_found']} of {S['true_orphans']}</div>"
        "<div class='vmetric'>controls that serve nothing, listed</div>"
        f"<div class='vtldr'>The sheet has no such view, and its word matching links {A['orphans_sheet_linked']} of them to an obligation.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>Evidence requests</div>"
        f"<div class='vbig'>{S['requests_theme']} not {S['requests_framework']}</div>"
        "<div class='vmetric'>one per theme instead of one per row</div>"
        f"<div class='vtldr'>{S['requests_gap']} of the {S['requests_theme']} are gaps with no control to ask.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>"
        f"<li>{S['missed_pairs']} true pairs from {S['missed_controls']} controls are missed because their wording is outside "
        f"the dictionary. That gives {S['wrong_status']} wrong statuses ({esc(WRONG_TEXT)}).</li>"
        f"<li>{S['false_links']} links are wrong, all from {S['false_controls']} control whose description names a dictionary phrase "
        "only to say it is not that thing. A phrase match cannot read the negation.</li>"
        "<li>Fresh evidence is not proof that a control works. Design and operating effectiveness are not tested.</li>"
        "<li>The dictionary was written by the author of the data, so these scores are an upper bound, not an estimate for a real "
        "control library.</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Statuses across all obligations**")
    st.caption("The sheet can only say covered or not covered, so it has no PARTIAL or STALE bars.")
    cats = ["COVERED", "STALE", "PARTIAL", "UNCOVERED"]
    truth_counts = [S["status_counts_truth"].get(c, 0) for c in cats]
    cm_counts = [S["status_counts_cm"].get(c, 0) for c in cats]
    sheet_counts = [A["sheet_covered"], 0, 0, S["obligations"] - A["sheet_covered"]]
    fig = go.Figure()
    fig.add_bar(x=cats, y=truth_counts, name="truth", marker_color="#1f5fb0")
    fig.add_bar(x=cats, y=sheet_counts, name="keyword sheet", marker_color="#b91c1c")
    fig.add_bar(x=cats, y=cm_counts, name="ControlMap", marker_color="#059669")
    fig.update_layout(barmode="group", height=340, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("See the data"):
        st.markdown("**All obligations: truth, keyword sheet, ControlMap**")
        st.dataframe(pd.DataFrame([{
            "obligation": r["obligation_id"], "framework": r["short"], "theme": r["theme"], "truth": r["truth_status"],
            "sheet": r["sheet_status"], "ControlMap": r["status"], "ControlMap right": "yes" if r["ok"] else "no",
        } for r in A["rows"]]), use_container_width=True, hide_index=True)
        st.markdown("**Orphan controls listed by ControlMap**")
        st.dataframe(pd.DataFrame([{
            "control": r["control_id"], "name": r["name"], "owner": r["owner"], "status": r["status"],
            "true orphan": "yes" if r["true_orphan"] else "no (missed by the dictionary)",
        } for r in A["orphan_rows"]]), use_container_width=True, hide_index=True)
        st.markdown("**Consolidated evidence requests, one per theme**")
        st.dataframe(pd.DataFrame([{
            "theme": r["theme"], "frameworks": ", ".join(r["frameworks"]), "obligations": ", ".join(r["obligations"]),
            "controls to ask": ", ".join(r["controls"]) or "gap: no control",
            "need new evidence": ", ".join(r["need_evidence"]),
        } for r in A["requests"]]), use_container_width=True, hide_index=True)

    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("Obligation", "One AI-related duty from a framework, in a paraphrase written for this exercise."),
            ("Theme", "The subject an obligation is about. The same theme can appear in several frameworks."),
            ("Control", "Something the bank does that is meant to meet an obligation."),
            ("Scope", "The use-case classes a control runs for: credit decision, customer chat, internal copilot, fraud scoring."),
            ("Full / partial", "Full: the control's scope includes every class the obligation applies to. Partial: it misses at least one."),
            ("Fresh / stale evidence", f"Fresh: the latest item is no older than {STALE_FACTOR:g} times the control's test cycle. Stale: older, or none."),
            ("Orphan control", "A control that meets no obligation."),
            ("Dictionary", "A hand-written table of phrases that say a control serves a theme."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is a crosswalk service that reads the obligation "
            "register and the control library, a dictionary a person maintains, and a nightly evidence-freshness job that reads "
            "evidence dates from the systems that hold them. It is a design, not deployed; see `ARCHITECTURE.md`. Related "
            "projects, all designed and none built: TierGate (11) sets which classes an obligation applies to, LineageLog (09) and "
            "EvalForge (04) are evidence sources, FairLens (17) supplies adverse-action evidence, IncidentLedger (19) links incidents "
            "to controls."
        )
    st.markdown(
        "<div class='cm-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>. Framework reference: "
        f"<a href='{NIST_URL}' target='_blank'>NIST AI RMF</a>.</div>",
        unsafe_allow_html=True,
    )
