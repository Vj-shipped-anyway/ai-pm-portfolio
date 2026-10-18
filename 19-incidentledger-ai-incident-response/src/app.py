"""IncidentLedger - AI incident response with the notification clock running.

Streamlit walkthrough. Pick one incident, then step through the story:
  Step 1  Pick an incident
  Step 2  Without IncidentLedger - the ticket queue (what it shows, and what actually happened)
  Step 3  With IncidentLedger - category, rubric severity, the clocks with hours left or
          breached, follow-ups and linked tickets
  Step 4  Proof at scale - the same measures over all 120 incidents, with the known limit

All data is synthetic (data/_generate.py, seeded). The classifier, rubric, clock engine,
tracker and linker are plain rules; there is no model anywhere in this app.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from step_01_ticket_queue_status_quo import (AS_OF, CATEGORY_NAMES, fmt_hour,  # noqa: E402
                                             summarize as summarize_step1)
from step_04_with_incidentledger import analyze, interest_order, view  # noqa: E402

st.set_page_config(
    page_title="IncidentLedger - AI incident response with the clock running",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/19-incidentledger-ai-incident-response/README.md"
NIST_URL = "https://www.nist.gov/itl/ai-risk-management-framework"

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.il-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.il-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.il-hero h1 {color: #ffffff !important; font-size: 42px; line-height: 1.14; margin: 0 0 14px 0; font-weight: 700;}
.il-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.il-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.il-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.il-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.il-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.il-card h3 {margin-top: 0; color: #0f172a;}
.il-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
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
.verdict-card .vchip.bad {background: #fee2e2; color: #7f1d1d;}
.verdict-card .vchip.warn {background: #fef3c7; color: #78350f;}
.verdict-card .vchip.ok {background: #dcfce7; color: #14532d;}
.verdict-card .vchip.idle {background: #e2e8f0; color: #334155;}
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

/* Queue vs truth panels */
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


def cat_name(c: str) -> str:
    return CATEGORY_NAMES.get(c, c)


@st.cache_resource
def load_analysis() -> dict:
    a = analyze()
    a["order"] = interest_order(a)
    a["step1"] = summarize_step1(a["data"])
    return a


A = load_analysis()
DATA = A["data"]
S = A["summary"]
S1 = A["step1"]
S2 = A["step2"]
S3 = A["step3"]
C = S["clocks"]
N = S["incidents"]

# Option labels are plain strings; a dict maps label -> incident id.
LABEL_TO_ID = {}
for _x in A["order"]:
    _i = DATA["by_id"][_x]
    _v_missed = sum(1 for c in A["clocks"][_x] if c["status"] in ("late", "breached"))
    LABEL_TO_ID[f"{_x}  -  queue {_i['reporter_priority']}, rubric {A['sev'][_x][0]}  -  "
                f"{_v_missed} missed  -  {_i['title'][:46]}"] = _x
LABELS = list(LABEL_TO_ID)

if "step" not in st.session_state:
    st.session_state.step = 1


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


def clock_chip(cl: dict) -> tuple:
    """(css class, text) for one clock."""
    s = cl["status"]
    if s == "on_time":
        return "ok", f"ON TIME - sent {fmt_hour(cl['sent_at'])}"
    if s == "late":
        return "bad", f"LATE - sent {cl['hours_over']} h after the deadline"
    if s == "breached":
        return "bad", f"BREACHED - never sent, {cl['hours_over']} h past due"
    if s == "running":
        return "warn", f"RUNNING - {cl['hours_left']} h left"
    return "idle", f"NOT STARTED - {cl['hours_since_detection']} h since detection, no determination"


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='il-hero'>
  <div class='brand'>🚨 IncidentLedger</div>
  <h1>AI incidents triaged by rubric with the notification clock running, not a ticket queue that missed {C['missed']} of {C['applicable']} deadlines.</h1>
  <div class='sub'>Reporters pick the priority and nobody watches the deadlines. IncidentLedger rates each incident by rubric, starts its notification clocks and counts down the hours.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>No model: plain rules</span>
    <span class='pill'>{N} incidents · {C['applicable']} deadlines · {S['actions']['total']} follow-ups</span>
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
# STEP 1 - pick an incident
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='il-card'><span class='il-step-label'>Step 1</span>"
    "<h3>Pick an incident</h3>"
    f"<p class='muted'>{N} synthetic AI incidents from one quarter. The first is a severe one the queue "
    "under-rated and then missed deadlines on; the list runs from the most telling to the least.</p></div>",
    unsafe_allow_html=True,
)
if "incident_choice" not in st.session_state:
    st.session_state.incident_choice = LABELS[0]
st.session_state.incident_choice = st.selectbox(
    "Incident:",
    LABELS,
    index=LABELS.index(st.session_state.incident_choice),
    label_visibility="collapsed",
)
iid = LABEL_TO_ID[st.session_state.incident_choice]
V = view(A, iid)
inc, tr, pr = V["inc"], V["truth"], V["pred"]

st.markdown(
    f"<div class='il-card'><b>{esc(iid)}</b> - {esc(inc['title'])}<br>"
    f"<span class='muted'>{esc(inc['description'])}<br>System: <code>{esc(inc['system'])}</code>. "
    f"Reported {esc(fmt_hour(inc['reported_at']))}. Filed by the reporter as <b>{esc(inc['reporter_priority'])}</b>.</span></div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p class='muted'>How to read the numbers: the data is synthetic and no model is used. The generator decided "
    "each incident's true category, severity and root cause, and who sent which notice when, so the truth is known. "
    "Deadline lengths and rubric thresholds are assumptions of a modeled bank, not legal advice or a statement of any "
    "rule. Severity and clock results agree with the truth by construction; the category and link results are the "
    "ones that can be wrong.</p>",
    unsafe_allow_html=True,
)

if st.session_state.step < 2:
    if st.button("Show what the queue does  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - Without IncidentLedger: the ticket queue
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='il-card'><span class='il-step-label'>Step 2</span>"
        "<h3>Without IncidentLedger - the ticket queue</h3>"
        "<p class='muted'>The queue shows the priority the reporter picked and a free-text label. "
        "Here is what it shows for this incident, and what actually happened.</p></div>",
        unsafe_allow_html=True,
    )
    acts = V["actions"]
    n_over = sum(1 for a in acts if a["state"] == "overdue")
    n_noev = sum(1 for a in acts if a["state"] == "closed_no_evidence")
    gap = ""
    if int(inc["reporter_priority"][1]) > int(tr["severity"][1]):
        gap = f" The rubric says {esc(tr['severity'])}: the queue under-rated it (WRONG)."
    elif int(inc["reporter_priority"][1]) < int(tr["severity"][1]):
        gap = f" The rubric says {esc(tr['severity'])}: the queue over-rated it (WRONG)."
    items = [
        f"<li>Priority <b>{esc(inc['reporter_priority'])}</b>, picked by the reporter; position "
        f"<b>{V['queue_position']} of {N}</b> in the work order.{gap}</li>",
        f"<li>Category typed by the reporter: <b>'{esc(inc['reporter_category'].strip())}'</b>, one of "
        f"{S1['raw_labels']} different strings for {len(S['per_class'])} real classes.</li>",
        f"<li>Notification deadlines shown: <b>{S1['clocks_tracked']}</b> (MISSED). "
        f"{len(V['truth_deadlines'])} apply to this incident.</li>",
        f"<li>Linked tickets: <b>{S3['f']['queue_links']}</b>. "
        + (f"{len(V['same_root_cause'])} other ticket(s) have the same root cause." if V["same_root_cause"]
           else "No other ticket shares its root cause.") + "</li>",
        f"<li>Follow-ups: {len(acts)} action(s), {n_over} past due and {n_noev} closed with no evidence; "
        "the queue flags none of them.</li>",
    ]
    red = ("<div class='bot-bad'><b>What the ticket queue shows (MISSED):</b><ul>" + "".join(items) + "</ul>"
           "<div class='small'>The queue has no rubric, no category list, no clock and no link field.</div></div>")

    td = []
    for r in V["truth_deadlines"]:
        name = next(p["name"] for p in DATA["policy"] if p["clock_id"] == r["clock_id"])
        if r["status"] == "not_started":
            what = "no determination recorded, so the clock never started"
        elif r["status"] == "on_time":
            what = f"sent on time (due {fmt_hour(r['due'])})"
        elif r["status"] == "late":
            what = f"sent {r['sent_at'] - r['due']} h late (due {fmt_hour(r['due'])})"
        elif r["status"] == "breached":
            what = f"never sent; due {fmt_hour(r['due'])}, {AS_OF - r['due']} h ago"
        else:
            what = f"not sent yet; due {fmt_hour(r['due'])}, {r['due'] - AS_OF} h left"
        td.append(f"<li>{esc(name)}: {esc(what)}</li>")
    rc_txt = ""
    if V["same_root_cause"]:
        rc_txt = " Same root cause as " + ", ".join(esc(y) for y in V["same_root_cause"]) + "."
    blue_items = [
        f"<li>Category: <b>{esc(cat_name(tr['category']))}</b>. Severity: <b>{esc(tr['severity'])}</b>. "
        f"Root cause {esc(tr['root_cause'])}.{rc_txt}</li>",
        "<li>Deadlines that applied, and what happened:<ul>" + ("".join(td) if td else "<li>none apply</li>") + "</ul></li>",
    ]
    blue = "<div class='bot-truth'><b>Source of truth - what the generator decided:</b><ul>" + "".join(blue_items) + "</ul></div>"

    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**The ticket as filed**")
        fields = [("incident_id", iid), ("reported_at", fmt_hour(inc["reported_at"])),
                  ("detected_at", fmt_hour(inc["detected_at"])),
                  ("determined_at", fmt_hour(inc["determined_at"]) if inc["determined_at"] is not None else "(none)"),
                  ("reporter_priority", inc["reporter_priority"]), ("reporter_category", inc["reporter_category"].strip()),
                  ("system", inc["system"]), ("change_id", inc["change_id"] or "(none)"),
                  ("customers_affected", inc["customers_affected"]),
                  ("regulated_decision_involved", inc["regulated_decision_involved"]),
                  ("pii_exposed", inc["pii_exposed"]), ("financial_impact_band", inc["financial_impact_band"]),
                  ("duration_hours", inc["duration_hours"])]
        st.dataframe(pd.DataFrame([(k, str(v)) for k, v in fields], columns=["Field", "Value"]),
                     use_container_width=True, hide_index=True)
        st.markdown("**Follow-up actions**")
        if acts:
            st.dataframe(pd.DataFrame([{"action": a["action"], "owner": a["owner"], "due": fmt_hour(a["due_at"]),
                                        "status": a["status"], "evidence link": a["evidence_link"]} for a in acts]),
                         use_container_width=True, hide_index=True)
        else:
            st.markdown("No follow-up actions on this incident.")
        st.markdown("**The six named deficiencies of the queue, over all incidents**")
        a_, b_, c_, d_, e_, f_ = (S3[k] for k in "abcdef")
        st.dataframe(pd.DataFrame([
            ("1", "Priority differs from the rubric", f"{a_['severe_filed_low']} of {a_['severe']} S1 or S2 tickets filed P3 or P4"),
            ("2", "Free-text categories cannot be aggregated", f"{b_['raw']} strings for {b_['classes']} classes"),
            ("3", "Clocks missed or never started", f"{c_['missed']} missed, {c_['not_started']} never started, of {c_['applicable']}"),
            ("4", "Clock anchor changes the count", f"{d_['at_determination']} from determination, {d_['at_detection']} from detection"),
            ("5", "Follow-ups overdue or closed with no evidence", f"{e_['flagged']} of {e_['actions']} actions"),
            ("6", "Related incidents not linked", f"{f_['repeat_tickets']} repeat tickets across {f_['repeated_causes']} root causes"),
        ], columns=["#", "Deficiency", "Count over the whole set"]), use_container_width=True, hide_index=True)

    if st.session_state.step < 3:
        if st.button("See the fix  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With IncidentLedger
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='il-card'><span class='il-step-label'>Step 3</span>"
        f"<h3>With IncidentLedger - {esc(iid)} is rated and its clocks are running</h3>"
        "<p class='muted'>IncidentLedger classifies the incident, rates it against the rubric, starts every clock "
        "that applies and counts the hours.</p></div>",
        unsafe_allow_html=True,
    )
    missed = V["missed"]
    state = "CAUGHT" if missed else "RATED"
    reason_txt = "; ".join(V["reasons"])
    clock_html = ""
    for cl in V["clocks"]:
        cls, txt = clock_chip(cl)
        det = next((d for d in V["clocks_det"] if d["clock_id"] == cl["clock_id"]), None)
        alt = ""
        if det is not None and det["due"] is not None and cl["due"] is not None and det["due"] != cl["due"]:
            alt = f" (from detection it would be due {esc(fmt_hour(det['due']))}: {esc(det['status'].replace('_', ' '))})"
        due = f" Due {esc(fmt_hour(cl['due']))}." if cl["due"] is not None else ""
        clock_html += (f"<div class='vfind'><span class='vchip {cls}'>{esc(txt)}</span>"
                       f"<b>{esc(cl['name'])}</b> ({cl['hours']} h).{due}{alt}</div>")
    if not V["clocks"]:
        clock_html = "<div class='vfind'>No notification clock applies to this incident under the modeled policy.</div>"
    act_html = ""
    if V["actions"]:
        n_over = sum(1 for a in V["actions"] if a["state"] == "overdue")
        n_noev = sum(1 for a in V["actions"] if a["state"] == "closed_no_evidence")
        n_ok = sum(1 for a in V["actions"] if a["state"] == "closed_ok")
        n_track = sum(1 for a in V["actions"] if a["state"] == "open_on_track")
        worst = max((a["hours_over"] for a in V["actions"] if a["hours_over"]), default=None)
        act_html = (f"<div class='vfind'><span class='vchip {'bad' if n_over or n_noev else 'ok'}'>FOLLOW-UPS</span>"
                    f"{len(V['actions'])} action(s): {n_over} overdue"
                    + (f" (worst {worst} h)" if worst else "")
                    + f", {n_noev} closed with no evidence (reopen), {n_ok} closed with evidence, "
                      f"{n_track} open and on track.</div>")
    link_html = ""
    if V["links"]:
        parts = [f"{esc(y)} ({'same root cause' if V['links_ok'][y] else 'not the same root cause per the truth file'})"
                 for y in V["links"]]
        link_html = ("<div class='vfind'><span class='vchip ok'>LINKED</span>" + ", ".join(parts) + "</div>")
    else:
        link_html = "<div class='vfind'><span class='vchip idle'>LINKED</span>No related ticket found.</div>"
    st.markdown(
        "<div class='verdict-card verdict-pass'>"
        f"<div class='vlabel'>With IncidentLedger - {state} - {esc(iid)}</div>"
        f"<div class='vbig'>{esc(V['severity'])} - {esc(cat_name(pr['category']))}</div>"
        f"<div class='vmetric'>Rubric: {esc(reason_txt)}</div>"
        "<div class='vrow'>"
        f"<span class='vchip'>Queue said {esc(inc['reporter_priority'])}; rubric says {esc(V['severity'])}</span>"
        f"<span class='vchip'>Category rule: {esc(pr['rule'])}</span>"
        f"<span class='vchip'>{missed} missed deadline(s) flagged</span></div>"
        + clock_html + act_html + link_html +
        f"<div class='vtldr'>Clocks run from determination ({esc(fmt_hour(inc['determined_at'])) if inc['determined_at'] is not None else 'not recorded'}), "
        f"read at {esc(fmt_hour(AS_OF))}. Deadline lengths are assumptions of a modeled bank.</div></div>",
        unsafe_allow_html=True,
    )
    if not V["category_ok"]:
        if pr["confidence"] == "review":
            note = (f"Known limit. The classifier says 'needs a person' ({pr['rule']}); the truth is "
                    f"{cat_name(tr['category'])}. It flagged its own doubt, and a person has to decide.")
        else:
            note = (f"Known limit. The classifier says {cat_name(pr['category'])} ({pr['rule']}) with no flag; the truth is "
                    f"{cat_name(tr['category'])}. The clocks are unaffected because they run on rubric fields, not on category.")
        st.markdown(f"<div class='limit-note'>{esc(note)}</div>", unsafe_allow_html=True)
    unlinked = [y for y in V["same_root_cause"] if y not in V["links"]]
    if unlinked:
        st.markdown("<div class='limit-note'>Known limit. The truth file says this incident shares a root cause with "
                    + esc(", ".join(unlinked)) + "; the linker did not connect "
                    + ("it." if len(unlinked) == 1 else "them.") + "</div>", unsafe_allow_html=True)
    if inc["determined_at"] is None:
        st.markdown("<div class='limit-note'>Known limit. Nobody has recorded a determination for this incident, so "
                    "the clocks cannot start. IncidentLedger shows the hours since detection; a person has to make "
                    "the call.</div>", unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**Clocks (policy anchor: determination)**")
        if V["clocks"]:
            rows = []
            for cl in V["clocks"]:
                det = next(d for d in V["clocks_det"] if d["clock_id"] == cl["clock_id"])
                rows.append({"clock": cl["name"], "hours": cl["hours"], "status": cl["status"].replace("_", " "),
                             "due": fmt_hour(cl["due"]) if cl["due"] is not None else "-",
                             "sent": fmt_hour(cl["sent_at"]) if cl["sent_at"] is not None else "-",
                             "if started at detection": det["status"].replace("_", " ")})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.markdown("No clock applies.")
        st.markdown("**Follow-up tracker**")
        if V["actions"]:
            st.dataframe(pd.DataFrame([{"action": a["action"], "owner": a["owner"], "due": fmt_hour(a["due_at"]),
                                        "state": a["state"].replace("_", " "),
                                        "hours over": str(a["hours_over"]) if a["hours_over"] else "-"} for a in V["actions"]]),
                         use_container_width=True, hide_index=True)
        else:
            st.markdown("No follow-up actions.")
        st.markdown("**Classifier evidence**")
        st.markdown(f"Rule: {pr['rule']}. Confidence: {pr['confidence']}. "
                    f"Truth: {cat_name(tr['category'])}" + (" (a designed hard case)." if tr["hard_case"] else "."))

    lines = [f"# IncidentLedger record: {iid}", "",
             "Synthetic data. Produced by the IncidentLedger prototype; not a real bank, system or incident.", "",
             f"- Title: {inc['title']}", f"- System: {inc['system']}",
             f"- Queue priority: {inc['reporter_priority']}; rubric severity: {V['severity']}",
             f"- Category (rule): {cat_name(pr['category'])} ({pr['rule']})",
             f"- Rubric: {reason_txt}", "", "| Clock | Hours | Status | Due |", "| --- | --- | --- | --- |"]
    lines += [f"| {c['name']} | {c['hours']} | {c['status'].replace('_', ' ')} | "
              f"{fmt_hour(c['due']) if c['due'] is not None else '-'} |" for c in V["clocks"]]
    st.download_button("Download incident record (Markdown)", "\n".join(lines),
                       file_name=f"incidentledger_{iid}.md", mime="text/markdown")

    if st.session_state.step < 4:
        if st.button("See the proof at scale  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    a_ = S3["a"]
    st.markdown(
        "<div class='il-card'><span class='il-step-label'>Step 4</span>"
        "<h3>Proof at scale</h3>"
        f"<p class='muted'>The same checks over all {N} synthetic incidents and {C['applicable']} notification deadlines.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Ticket queue: deadlines</div>"
        f"<div class='vbig'>{C['missed']} of {C['applicable']}</div>"
        "<div class='vmetric'>notification deadlines missed, none shown by the queue</div>"
        f"<div class='vtldr'>{C['late']} sent late and {C['breached']} never sent. {C['not_started']} more never started.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>Ticket queue: priority</div>"
        f"<div class='vbig'>{a_['severe_filed_low']} of {a_['severe']}</div>"
        "<div class='vmetric'>truly S1 or S2 tickets were filed P3 or P4</div>"
        f"<div class='vtldr'>The reporter's priority matched the rubric on {a_['exact']} of {N} tickets.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With IncidentLedger: clocks</div>"
        f"<div class='vbig'>{S['missed_warned']} of {S['missed_total']}</div>"
        "<div class='vmetric'>missed deadlines flagged, with a countdown that fires first</div>"
        f"<div class='vtldr'>By construction: the clocks are arithmetic on the determination time and the policy. "
        f"{C['running']} clocks are running now, with hours left.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With IncidentLedger: category</div>"
        f"<div class='vbig'>{S['class_correct']} of {S['class_total']}</div>"
        "<div class='vmetric'>incidents put in the right class of seven</div>"
        f"<div class='vtldr'>All {S['class_misses']} misses are the {S['designed']} hard cases written into the data; "
        f"{S['class_flagged_miss']} of them were flagged for a person.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>"
        f"<li>{S['class_misses']} of {N} categories are wrong. {S['class_confident_miss']} of them carry no flag: an "
        "injection that exposes personal data is filed as data exposure because the field rule comes first.</li>"
        f"<li>Determination is a human call. {len([i for i in DATA['incidents'] if i['determined_at'] is None])} incidents have none, "
        f"so {C['not_started']} deadlines have not started. Starting every clock at detection instead would count "
        f"{S['clocks_at_detection']['missed']} missed deadlines, not {C['missed']}.</li>"
        f"<li>The linker found {S['link_tp']} of {S['link_true_pairs']} true pairs and {S['link_pred_pairs'] - S['link_tp']} of its "
        f"{S['link_pred_pairs']} links join different root causes.</li>"
        "<li>Severity and clock agreement hold by construction; they say the code does what the rules say, "
        "not that the rubric or the deadlines are right.</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Deadline outcomes by clock**")
    st.caption("Each notification deadline that applies, by what happened at the read date.")
    names = {p["clock_id"]: p["name"] for p in DATA["policy"]}
    fig = go.Figure()
    for key, label, color in (("on_time", "on time", "#059669"), ("late", "sent late", "#dc2626"),
                              ("breached", "never sent, past due", "#7f1d1d"), ("running", "running", "#f59e0b"),
                              ("not_started", "not started", "#94a3b8")):
        fig.add_bar(x=[names[k] for k in S["clocks_by_clock"]], y=[v[key] for v in S["clocks_by_clock"].values()],
                    name=label, marker_color=color)
    fig.update_layout(barmode="stack", height=340, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.14))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("Determination", "The moment the bank decides a report is a real incident. A person records it."),
            ("Detection", "The moment anyone first noticed the problem. It is never later than determination."),
            ("Severity S1 to S4", "A rating from five fields: customers affected, regulated decision, personal data, financial impact band and duration."),
            ("Notification clock", "A deadline counted from determination, set by the modeled policy."),
            ("Missed", "Sent after the deadline, or never sent and the deadline has passed."),
            ("Not started", "The clock applies but no determination is recorded, so it has no start."),
            ("Root cause", "What actually went wrong. Several tickets can share one."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is an intake service that classifies and "
            "rates each incident, a clock service that reads the policy and the determination time, a follow-up "
            "tracker that asks for evidence at closure, and a record written for the model-risk file. It is a design, "
            "not deployed; see `ARCHITECTURE.md`. Related projects: AgentWatch (05) detects, OversightOps (08) "
            "reviews, LineageLog (09) records the decisions, and SchemaWatch (15) and SwapBrief (13) supply the "
            "change ids. All interlocks are designed, none built."
        )
    st.markdown(
        "<div class='il-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>. Framework reference: "
        f"<a href='{NIST_URL}' target='_blank'>NIST AI RMF</a>.</div>",
        unsafe_allow_html=True,
    )
