"""AgentKit - a reference agent build and delivery playbook for a rule-based operations workflow.

Streamlit walkthrough. Pick one scenario case, then step through the story:
  Step 1  Pick a scenario case
  Step 2  Without controls - what the happy-path script does, and what actually happened
  Step 3  With AgentKit - the route, the STUB-drafted correction, the audit trace and the brief
  Step 4  Proof at scale - the 600 historical cases in shadow mode, the acceptance criteria, what it still gets wrong

All data is synthetic (data/_generate.py, seeded). The reasoning stub is a deterministic template, not a
language model: it is labelled STUB wherever it appears. There is no model in this app.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

import step_01_manual_handling as step1  # noqa: E402
import step_04_with_agentkit as step4  # noqa: E402
from agentkit.brief import scope_violation  # noqa: E402
from agentkit.reasoning_stub import STUB_LABEL  # noqa: E402

st.set_page_config(
    page_title="AgentKit - A reference agent with the controls built in",
    page_icon="🧰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/27-agentkit-reference-agent-and-playbook/README.md"
PLAYBOOK_URL = GITHUB_URL + "/blob/main/27-agentkit-reference-agent-and-playbook/playbook/DELIVERY_PLAYBOOK.md"

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.ak-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.ak-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.ak-hero h1 {color: #ffffff !important; font-size: 42px; line-height: 1.14; margin: 0 0 14px 0; font-weight: 700;}
.ak-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 840px; margin-bottom: 22px;}
.ak-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.ak-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.ak-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.ak-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.ak-card h3 {margin-top: 0; color: #0f172a;}
.ak-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
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
.verdict-card .vfind {margin-top: 12px; font-size: 15px; line-height: 1.5;}
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

/* Script vs truth panels */
.bot-bad {background: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #dc2626;
          border-radius: 10px; padding: 14px 18px; color: #7f1d1d;}
.bot-good {background: #ecfdf5; border: 1px solid #bbf7d0; border-left: 4px solid #059669;
           border-radius: 10px; padding: 14px 18px; color: #065f46;}
.bot-truth {background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb;
            border-radius: 10px; padding: 14px 18px; color: #1e3a8a;}
.bot-bad ul, .bot-truth ul, .bot-good ul {margin: 8px 0 0 18px; padding: 0;}
.bot-bad li, .bot-truth li, .bot-good li {line-height: 1.5; margin-bottom: 8px;}
.bot-bad .small {font-size: 13px; opacity: 0.85; margin-top: 8px;}

/* STUB-labelled draft */
.stub-box {background: #f1f5f9; border: 1px dashed #64748b; border-radius: 10px; padding: 12px 16px;
           color: #0f172a; font-size: 14px; margin-top: 10px;}
.stub-box .tag {display: inline-block; background: #475569; color: #fff; border-radius: 6px; padding: 1px 8px;
                font-size: 11px; font-weight: 700; letter-spacing: 0.06em; margin-right: 8px;}

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


def pct(x, nd: int = 1) -> str:
    return "n/a" if x is None else f"{100 * x:.{nd}f}%"


@st.cache_resource
def load_everything() -> dict:
    S = step4.compute()
    SC = step4.scenario_list(S["world"], S["shadow"]["results"])
    return {"S": S, "SC": SC, "M1": step1.compute(S["world"])}


@st.cache_resource
def scenario_run(key: str) -> dict:
    ALL = load_everything()
    sc = next(s for s in ALL["SC"] if s["key"] == key)
    return step4.run_scenario(ALL["S"]["world"], ALL["S"]["brief"], sc)


ALL = load_everything()
S, SCENARIOS, M1 = ALL["S"], ALL["SC"], ALL["M1"]
WORLD, CFG = S["world"], S["config"]
SCORE = S["shadow"]["score"]
M3 = S["m3"]
MEAS = S["measured"]
PASSED = sum(1 for a in S["acceptance"] if a["passed"])

LABEL_TO_INDEX = {f"{s['label']}  -  {s['case_id']}": i for i, s in enumerate(SCENARIOS)}
LABELS = list(LABEL_TO_INDEX)
DEFAULT_LABEL = LABELS[0]

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
<div class='ak-hero'>
  <div class='brand'>🧰 AgentKit</div>
  <h1>A reference agent with the controls built in, and the playbook an engineer follows to production.</h1>
  <div class='sub'>Replayed in shadow mode on {SCORE['cases']} historical cases, it proposed an outcome for {SCORE['scored']} and agreed with the
  recorded human outcome on {pct(SCORE['agreement_rate'], 1)} of them. {PASSED} of {len(S['acceptance'])} acceptance criteria from the brief pass;
  the one that fails is shown, not hidden.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>STUB reasoning, not a model</span>
    <span class='pill'>{SCORE['cases']} cases · 12 steps · 2 person gates</span>
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
# STEP 1 - pick a scenario
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='ak-card'><span class='ak-step-label'>Step 1</span>"
    "<h3>Pick a scenario case</h3>"
    f"<p class='muted'>{len(SCENARIOS)} cases picked from the {SCORE['cases']} synthetic ones: the clean paths, the person gates, the "
    "known misses and four fault injections. Each runs through the real kit and the real step 2 script, live in this app.</p></div>",
    unsafe_allow_html=True,
)
if "scenario_choice" not in st.session_state:
    st.session_state.scenario_choice = DEFAULT_LABEL
st.session_state.scenario_choice = st.selectbox(
    "Scenario:", LABELS, index=LABELS.index(st.session_state.scenario_choice), label_visibility="collapsed")
sc = SCENARIOS[LABEL_TO_INDEX[st.session_state.scenario_choice]]
run = scenario_run(sc["key"])
case, human, truth = run["case"], run["human"], run["truth"]
kr = run["kit_result"]
script = run["script"]

st.markdown(
    "<p class='muted'>How to read this: all data is synthetic and no model is used. The 'recorded human outcome' is what the "
    "generator says a careful worker did; it is the yardstick, not ground truth about any real operation. The reasoning step is a "
    f"STUB: {esc(STUB_LABEL)}.</p>",
    unsafe_allow_html=True,
)
st.markdown(f"<p><b>{esc(sc['label'])}.</b> {esc(sc['note'])}</p>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# STEP 2 - Without controls
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='ak-card'><span class='ak-step-label'>Step 2</span>"
        "<h3>Without controls - the happy-path script</h3>"
        "<p class='muted'>The script follows the steps in order. It has no scope check, no gate and no audit trail. "
        "Here is what it did on this case, and what actually happened.</p></div>",
        unsafe_allow_html=True,
    )
    items = []
    act = script["action"]
    pid = case["payment_id"]
    ledger = [l for l in run["ledger_script"] if l["payment_id"] == pid]
    if act == "RESUBMIT":
        items.append(f"<li><b>Resubmits with no approval.</b> {esc(script['field'])} -> {esc(script['value'])}; "
                     f"{len(ledger)} resubmission(s) of {esc(pid)} sent to the gateway, none approved by a second person.</li>")
        orig = run["payment"]
        if orig and script["field"] != "beneficiary_account" and script["payload"].get("beneficiary_account") != orig["beneficiary_account"]:
            items.append(f"<li><b>Altered account number.</b> The spreadsheet hop turned {esc(orig['beneficiary_account'])} into "
                         f"{esc(script['payload'].get('beneficiary_account'))}; that is what was resubmitted.</li>")
        items.append("<li><b>Acts outside any sensible scope.</b> It rewrote the original payment record to make the match pass "
                     "and read the whole watch list to compare names exactly.</li>")
    elif act == "RETURN_TO_ORIGINATOR":
        items.append("<li><b>Closes the case as a return.</b> No second look, no check that the advice carried a successor account.</li>")
    elif act == "ESCALATE_COMPLIANCE":
        items.append("<li><b>Escalates an exact watch-list name.</b> It only catches names that match exactly after upper-casing.</li>")
    else:
        items.append("<li><b>Swallows the error and moves on.</b> The case stays open in the queue. No log line, no alert; the job "
                     "still prints 'Done'.</li>")
    if case["delivery_no"] == 2:
        items.append(f"<li><b>Processes the redelivered exception again.</b> {len(run['ledger_script'])} resubmission(s) for the same exception.</li>")
    items.append(f"<li>Log lines written: <b>{len(run['script_log'])}</b>. It never records why it decided anything.</li>")
    agrees = (act == human["human_outcome"]) and (act != "RESUBMIT" or (script["field"] == human["corrected_field"] and script["value"] == human["corrected_value"]))
    red = ("<div class='bot-bad'><b>What the script does:</b><ul>" + "".join(items) + "</ul>"
           f"<div class='small'>Against the recorded human outcome the script {'agrees' if agrees else '<b>disagrees</b>'}.</div></div>")
    blue = ("<div class='bot-truth'><b>Source of truth - what actually happened (synthetic):</b><ul>"
            f"<li>The generator built this case as <b>{esc(truth['scenario'])}</b>{' (a planted edge case)' if truth['planted'] else ''}"
            f"{': ' + esc(truth['note']) if truth['note'] else ''}.</li>"
            f"<li>Return reason <b>{esc(case['reason_code'])}</b> on payment {esc(case['payment_id'] or '(blank)')}; "
            f"returned name '{esc(case['returned_name'])}'.</li>"
            f"<li>Recorded human outcome: <b>{esc(human['human_outcome'])}</b>"
            f"{' - ' + esc(human['corrected_field']) + ' -> ' + esc(human['corrected_value']) if human['corrected_field'] else ''}. "
            f"Touch time {human['touch_minutes']:.1f} min (modeled).</li></ul></div>")
    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**The exception as delivered**")
        st.dataframe(pd.DataFrame([{k: v for k, v in case.items()}]), use_container_width=True, hide_index=True)
        if run["payment"]:
            st.markdown("**The original payment**")
            st.dataframe(pd.DataFrame([run["payment"]]), use_container_width=True, hide_index=True)
        st.markdown("**System calls the script made for this case (outside the brief's scope are marked)**")
        st.dataframe(pd.DataFrame([{"system": c[0], "action": c[1], "access": c[2],
                                    "outside the brief": "yes" if scope_violation(CFG.tool_scope, c[0], c[1]) else "no"}
                                   for c in run["script_calls"]]), use_container_width=True, hide_index=True)

    if st.session_state.step < 3:
        if st.button("See the fix ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With AgentKit
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='ak-card'><span class='ak-step-label'>Step 3</span>"
        "<h3>With AgentKit - scoped tools, two person gates, one audit trail</h3>"
        "<p class='muted'>The kit reads the brief, runs the same case in shadow mode (every write a dry run) and decides one of "
        "three routes: finish it, send it to a person, or send it back to the human queue.</p></div>",
        unsafe_allow_html=True,
    )
    route_label = {"auto": "AUTO", "to_person": "TO A PERSON", "human_queue": "BACK TO THE HUMAN QUEUE"}[kr.route]
    style = "verdict-pass"      # every route is the control working; a hand-back to the human queue is a safe stop
    where = {"WAITING_S09": "waiting at S09, four-eyes approval", "WAITING_S07": "waiting at S07, a judgment on an ambiguous match",
             "ESCALATED": "escalated to compliance on a watch-list hit", "CLOSED": "closed by the agent",
             "CLOSED_DUPLICATE": "closed as a duplicate delivery", "QUEUED_HUMAN": f"reason: {kr.reason_kind}",
             "KILLED": "kill switch engaged"}.get(kr.state, kr.state)
    chips = [f"Proposal: {kr.proposed_outcome}", f"Steps run: {len(kr.steps_done)}", f"Tool calls: {kr.tool_calls}"]
    if kr.name_class:
        chips.append(f"Name match: {kr.name_class} {kr.name_score:.2f}")
    blocked = [e for e in run["events"] if e["kind"] == "tool_call" and e["detail"].get("outcome") == "blocked_scope"]
    if blocked:
        chips.append(f"Out-of-scope calls blocked: {len(blocked)}")
    verdict = (f"<div class='verdict-card {style}'><div class='vlabel'>With AgentKit - {esc(case['case_id'])}</div>"
               f"<div class='vbig'>{esc(route_label)}</div><div class='vmetric'>{esc(where)}</div>"
               "<div class='vrow'>" + "".join(f"<span class='vchip'>{esc(c)}</span>" for c in chips) + "</div>"
               + (f"<div class='vtldr'>{esc(kr.reason)}</div>" if kr.reason else "")
               + ("<div class='vtldr'>The kit stopped and handed the case back with its trace. That is the control working, "
                  "not a failure to hide.</div>" if kr.route == "human_queue" else "") + "</div>")
    st.markdown(verdict, unsafe_allow_html=True)

    if kr.correction:
        st.markdown(
            f"<div class='stub-box'><span class='tag'>STUB</span><b>Drafted correction:</b> {esc(kr.correction['field'])}: "
            f"{esc(kr.correction['old'] or '(blank)')} -> <b>{esc(kr.correction['new'])}</b>"
            f"<br><span class='muted'>{esc(kr.draft_message)}</span>"
            f"<br><span class='muted'>{esc(STUB_LABEL)}. A rule check passed it; a person approves it at S09. Digest {esc(kr.correction['digest'])}.</span></div>",
            unsafe_allow_html=True)
    if kr.hits:
        st.markdown("<div class='stub-box'><b>Watch-list hit logged:</b> " + ", ".join(
            f"{esc(h['party_id'])} at {h['score']:.2f}" for h in kr.hits) + "</div>", unsafe_allow_html=True)

    verdict_human = "agrees with" if kr.proposed_outcome == human["human_outcome"] and (
        kr.proposed_outcome != "RESUBMIT" or (kr.correction and kr.correction["field"] == human["corrected_field"]
                                              and kr.correction["new"] == human["corrected_value"])) else "differs from"
    if kr.proposed_outcome in ("DEFER_TO_PERSON", "HUMAN_QUEUE"):
        st.markdown(f"<p class='muted'>Not scored against the human outcome ({esc(human['human_outcome'])}): the kit sent this case to a person.</p>",
                    unsafe_allow_html=True)
    elif verdict_human == "agrees with":
        st.markdown(f"<p class='muted'>The proposal {verdict_human} the recorded human outcome ({esc(human['human_outcome'])}).</p>",
                    unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='limit-note'>Known miss. The proposal ({esc(kr.proposed_outcome)}) {verdict_human} the recorded human outcome "
                    f"({esc(human['human_outcome'])}). This is left in on purpose; it is counted in the acceptance table below.</div>",
                    unsafe_allow_html=True)

    with st.expander("Audit trace for this case"):
        rows = []
        for e in run["events"]:
            d = e["detail"]
            if e["kind"] == "tool_call":
                summ = f"{d['tool']}.{d['action']} -> {d['outcome']}" + (f" ({d['reason']})" if d.get("reason") else "")
            elif e["kind"] == "decision":
                summ = f"{d['decision']}: {d['rationale']}"
            elif e["kind"] == "gate":
                summ = f"parked for {d['approver_role']}"
            elif e["kind"] == "route":
                summ = f"{d['route']} / {d['state']} / proposal {d['proposed_outcome']}"
            else:
                summ = ", ".join(f"{k}={v}" for k, v in d.items())
            rows.append({"seq": e["seq"], "kind": e["kind"], "step": e["step"] or "", "what": summ})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(f"{len(rows)} events for this case. The whole log's hash chain is "
                   f"{'intact' if run['chain_ok'] else 'BROKEN'}. Time is a sequence number, never the clock.")
    with st.expander("The brief this agent was built from"):
        st.markdown(f"`{CFG.brief_id}`: {esc(CFG.name)}. Shape: build-brief/v1, the shape StepScout (26) emits. This one is a "
                    "hand-written sample, not StepScout output.")
        snap_parts = []
        for b_ in S["snapshot"]:
            if b_["unsupported_steps"]:
                snap_parts.append(f"{b_['id']} validates but its {', '.join(b_['unsupported_steps'])} step is unsupported and refused at run time")
            else:
                snap_parts.append(f"{b_['id']} validates")
        st.markdown("The three briefs StepScout wrote are kept as a snapshot in `briefs/stepscout_snapshot/` (not hand-written): "
                    + "; ".join(snap_parts) + ". Those ids are StepScout's, not this sample's.")
        st.markdown("**Derived from the brief**")
        st.dataframe(pd.DataFrame(
            [{"what": "person gates", "value": ", ".join(f"{g.step} -> {g.approver_role}" for g in CFG.gates.values())},
             {"what": "resubmit rule", "value": "S10 requires an approved S09 for the same correction digest"},
             {"what": "tools", "value": ", ".join(f"{n} ({t.access}: {', '.join(sorted(t.allowed_actions))})" for n, t in CFG.tool_scope.items())},
             {"what": "kill switch", "value": CFG.kill_switch},
             {"what": "acceptance criteria", "value": ", ".join(t.id for t in CFG.acceptance)}]),
            use_container_width=True, hide_index=True)
        st.json(S["brief"], expanded=False)

    if st.session_state.step < 4:
        if st.button("See the proof at scale ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    sc_ = SCORE
    r = sc_["routes"]
    e3, a3, b3, c3, d3 = M3["e"], M3["a"], M3["b"], M3["c"], M3["d"]
    st.markdown(
        "<div class='ak-card'><span class='ak-step-label'>Step 4</span>"
        f"<h3>Proof at scale - the {sc_['cases']} historical cases in shadow mode</h3>"
        "<p class='muted'>The kit proposed; nothing was written. Each proposal is compared with the recorded human outcome, "
        "which the kit never saw.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Manual handling (modeled minutes)</div>"
        f"<div class='vbig'>{M1['hours_total']} h</div>"
        f"<div class='vmetric'>{M1['minutes_mean']} min per case over {M1['cases']} cases</div>"
        "<div class='vtldr'>The size of the pool, from the generator's per-step minutes. Not a time study and not a saving.</div></div>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Script without controls</div>"
        f"<div class='vbig'>{pct(e3['agreement_rate_with_outcome'])}</div>"
        f"<div class='vmetric'>agreement where it produced an outcome</div>"
        f"<div class='vtldr'>{b3['without_approval']} resubmits with no approval, {c3['cases_failed_silently']} cases failed silently, "
        f"{pct(d3['share_without_trace'])} of decisions untraced.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With AgentKit (shadow)</div>"
        f"<div class='vbig'>{pct(sc_['agreement_rate'], 1)}</div>"
        f"<div class='vmetric'>agreement on {sc_['scored']} proposed outcomes</div>"
        f"<div class='vtldr'>{r['auto']} auto, {r['to_person']} to a person, {r['human_queue']} back to the human queue. "
        f"{MEAS['out_of_scope_calls_executed']} out-of-scope calls executed, {MEAS['resubmits_without_approval']} resubmits without approval, "
        f"audit completeness {MEAS['audit_completeness']:.2f}.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>Acceptance criteria from the brief</div>"
        f"<div class='vbig'>{PASSED} of {len(S['acceptance'])}</div>"
        "<div class='vmetric'>pass; AC-06 fails</div>"
        f"<div class='vtldr'>Auto-handled cases that differ from the recorded human outcome: {S['auto_wrong']['wrong']} of "
        f"{S['auto_wrong']['auto']} ({pct(S['auto_wrong']['rate'])}), against a limit of "
        f"{pct(CFG.acceptance[5].threshold, 0)}.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    mis = S["misses"]
    st.markdown(
        "<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>"
        f"<li>It finished {S['auto_wrong']['auto']} cases on its own and {mis['auto_handled_wrongly']['n']} differ from the recorded human "
        f"outcome: {mis['auto_returns_with_advised_value']['human_resubmitted']} closed accounts whose advice carried a successor account, and "
        f"{mis['auto_returns_from_name_mismatch']['human_resubmitted']} name mismatches a person had resubmitted. AC-06 fails; under the "
        "brief's own exit criteria the kit stays in shadow mode.</li>"
        f"<li>The stub drafted a correction that passed the rule check where the recorded outcome was different in "
        f"{mis['drafted_agreed_with_rules_human_differed']['n']} cases, mostly affiliate companies with close-looking names. They reach a "
        "person at S09; how many a real reviewer would catch is not measured.</li>"
        f"<li>Watch list: {mis['watch_list_missed']['of'] - mis['watch_list_missed']['n']} of {mis['watch_list_missed']['of']} planted hits "
        f"escalated; {mis['watch_list_over_escalated']['n']} look-alikes a person had cleared were escalated too.</li>"
        f"<li>The abbreviation table knows 5 of the 8 abbreviations the generator uses on purpose, and every threshold is a design value "
        "set before the run. A real name list would need its own calibration.</li>"
        f"<li>The approver in the enforcement run is a scripted test double. It tests the controls, not reviewer quality.</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Agreement with the recorded human outcome, by class: script against AgentKit**")
    classes = list(SCORE["by_human_class"])
    fig = go.Figure()
    fig.add_bar(x=classes, y=[100 * (M3["e"]["by_human_class"][c]["agree"] / M3["e"]["by_human_class"][c]["n"]) for c in classes],
                name="script without controls (share of all cases in the class)", marker_color="#b91c1c")
    fig.add_bar(x=classes, y=[100 * (SCORE["by_human_class"][c]["agreement_rate"] or 0) for c in classes],
                name="AgentKit (share of proposed outcomes that agree)", marker_color="#059669")
    fig.update_layout(barmode="group", height=340, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="percent",
                      legend=dict(orientation="h", y=1.15))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("The two bars do not share a denominator: the kit's excludes cases it sent to a person to judge or back to the queue.")

    with st.expander("See the data"):
        st.markdown("**Acceptance criteria (thresholds are the brief's)**")
        st.dataframe(pd.DataFrame([{"id": a["id"], "metric": a["metric"], "limit": f"{'>=' if a['direction'] == 'min' else '<='} {a['threshold']:g}",
                                    "measured": round(a["value"], 4) if isinstance(a["value"], float) else a["value"],
                                    "result": "PASS" if a["passed"] else "FAIL", "how measured": a["how_measured"]}
                                   for a in S["acceptance"]]), use_container_width=True, hide_index=True)
        st.markdown("**Routes in the shadow run**")
        st.dataframe(pd.DataFrame([{"route": k, "cases": v, "share": pct(v / sc_["cases"])} for k, v in r.items()]),
                     use_container_width=True, hide_index=True)
        st.markdown("**Agreement by recorded human outcome**")
        st.dataframe(pd.DataFrame([{"recorded outcome": k, **{kk: vv for kk, vv in v.items() if kk != "agreement_rate"},
                                    "agreement": pct(v["agreement_rate"])} for k, v in SCORE["by_human_class"].items()]),
                     use_container_width=True, hide_index=True)
        st.markdown("**Fault-injection run**")
        f = S["fault"]["summary"]
        st.dataframe(pd.DataFrame([
            {"measure": "transient faults recovered by retry", "value": f"{f['transient_recovered_same_result']} of {f['transient_cases']}"},
            {"measure": "persistent failures sent to the human queue", "value": f"{f['persistent_to_human_queue']} of {f['persistent_cases']}"},
            {"measure": "out-of-scope calls attempted / blocked / executed", "value": f"{f['rogue_attempted']} / {f['rogue_blocked']} / {f['executed_outside_scope']}"},
            {"measure": "redelivered cases ignored", "value": str(f["redeliveries_ignored"])}]), use_container_width=True, hide_index=True)
        st.markdown("**Enforcement run (scripted approver double)**")
        p = S["probes"]
        st.dataframe(pd.DataFrame([
            {"measure": "S10 attempts blocked (no approval / other fix / not a person)", "value": f"{p['blocked']['no_approval']} / {p['blocked']['other_correction']} / {p['blocked']['not_a_person']}"},
            {"measure": "S10 ran with a valid approval", "value": str(p["executed_with_valid_approval"])},
            {"measure": "resubmissions without a person's approval", "value": str(p["unapproved_in_ledger"])},
            {"measure": "payments resubmitted twice in the full live pass", "value": str(S["live"]["payments_with_more_than_one"])}]),
            use_container_width=True, hide_index=True)
        st.markdown("**Known miss, case by case**")
        rows = []
        for cid in mis["drafted_agreed_with_rules_human_differed"]["cases"] + mis["auto_handled_wrongly"]["cases"]:
            rr = next(x for x in S["shadow"]["results"] if x.case_id == cid)
            rows.append({"case": cid, "kit route": rr.route, "kit proposal": rr.proposed_outcome,
                         "human outcome": WORLD["outcomes"][cid]["human_outcome"], "scenario (answer key)": WORLD["truth"][cid]["scenario"]})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown("**Modeled minutes per case (🟡)**")
        st.caption("Assumptions: the generator's step minutes; a reviewer spends the S09 minutes and nothing more; every S07 is followed by an S09; "
                   "escalated and queued cases keep the full manual minutes. Not a saving claim.")
        st.dataframe(pd.DataFrame([{"manual, min per case": round(S["minutes"]["manual_per_case"], 1),
                                    "with the kit's routes, min per case": round(S["minutes"]["kit_per_case"], 1)}]),
                     use_container_width=True, hide_index=True)

    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("Shadow mode", "The kit runs on cases and proposes. Every write is a dry run; both person gates park the case."),
            ("S07 / S09", "S07 judges an ambiguous name match; S09 is the four-eyes approval. Both are always a person."),
            ("Scope", "The tools and actions the brief lists. A call outside them is refused and logged."),
            ("Idempotency key", "A label on a write so a retry or a redelivery cannot make it happen twice."),
            ("Audit trace", "An append-only, hash-chained log of every decision, tool call, gate and approval."),
            ("STUB", "A deterministic template that stands in for a language model. It is not a model."),
            ("Known miss", "A result the kit gets wrong that is left in and printed."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is a queue consumer, an orchestrator with a state store, a tool "
            "gateway that enforces scope, an approval service for S07 and S09, an append-only audit store, a kill-switch flag and a shadow "
            "scorecard job. It is a design, not deployed; see `ARCHITECTURE.md` and the delivery playbook. Intake and business case are "
            "11 TierGate and 12 ValueLedger, permissions 23 ScopeKeeper, agent observability 05 AgentWatch, fallback 25 KillSwitch, and the "
            "brief shape comes from 26 StepScout. All designed, none built here."
        )
    st.markdown(
        "<div class='ak-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>; the gate-by-gate path in the "
        f"<a href='{PLAYBOOK_URL}' target='_blank'><code>delivery playbook</code></a>.</div>",
        unsafe_allow_html=True,
    )
