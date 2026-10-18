"""ScopeKeeper - agent permission review.

Streamlit walkthrough. Pick one agent, then step through the story:
  Step 1  Pick an agent
  Step 2  Without ScopeKeeper - the annual recertification approves the list, while the call log
          shows what the agent really used (red card: the review; blue card: the call log)
  Step 3  With ScopeKeeper - the proposed scope set, what is removed or narrowed, the dry-run
          replay of the 90 days, and the known limit
  Step 4  Proof at scale - the same measures over all 15 agents, with what it still gets wrong

All data is synthetic (data/_generate.py, seeded). The diff, the proposal, the replay and the risk
ranking are plain rules; there is no model anywhere in this app.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from step_01_status_quo import load_all  # noqa: E402
from step_04_with_scopekeeper import APPROVAL_POINTS, SHARED_POINTS, analyze  # noqa: E402

st.set_page_config(
    page_title="ScopeKeeper - Cuts AI agent permissions to what they use",
    page_icon="🔑",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/23-scopekeeper-agent-permission-review/README.md"
NIST_URL = "https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final"

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.sk-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.sk-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.sk-hero h1 {color: #ffffff !important; font-size: 46px; line-height: 1.12; margin: 0 0 14px 0; font-weight: 700;}
.sk-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.sk-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.sk-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.sk-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.sk-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.sk-card h3 {margin-top: 0; color: #0f172a;}
.sk-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
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

/* Review vs truth panels */
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


PLAIN_IMPACT = {"read": "reads data", "write": "changes data", "external_message": "sends a message",
                "money_movement": "moves money"}


def impact_word(scope: str) -> str:
    return PLAIN_IMPACT[CAT[scope]["impact"]]


@st.cache_resource
def load_analysis() -> dict:
    return analyze(load_all(DATA_DIR))


A = load_analysis()
DATA = A["data"]
S = A["summary"]
AG = {r["agent_id"]: r for r in A["agents"]}
CAT = DATA["catalog"]
S3 = A["deficiencies"]
RECERT = A["recert"]

# Option labels are plain strings; a dict maps label -> agent id.
LABEL_TO_AGENT = {
    f"{r['agent_id']}  {r['purpose']}  -  {r['tier']} tier  -  {r['cut']} of {r['reach']} scopes unused": r["agent_id"]
    for r in sorted(A["agents"], key=lambda x: x["rank"])
}
LABELS = list(LABEL_TO_AGENT)

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
<div class='sk-hero'>
  <div class='brand'>🔑 ScopeKeeper</div>
  <h1>Agent permissions cut by {S['reach_cut_pct']}% to what they actually use, not recertified once a year.</h1>
  <div class='sub'>An AI agent is granted scopes at launch and gains more over time, and nobody compares them with the calls it makes. ScopeKeeper reads 90 days of calls and proposes the smallest scope set that still covers every one.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>No model: plain rules</span>
    <span class='pill'>{S['agents']} agents · {S['grants']} grants · {S['calls']:,} calls</span>
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
# STEP 1 - pick an agent
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='sk-card'><span class='sk-step-label'>Step 1</span>"
    "<h3>Pick an agent</h3>"
    f"<p class='muted'>{S['agents']} AI agents of a modeled bank, each with grants and 90 days of calls. "
    "The first one carries the most risk by the ranking in step 4.</p></div>",
    unsafe_allow_html=True,
)
if "agent_choice" not in st.session_state:
    st.session_state.agent_choice = LABELS[0]
st.session_state.agent_choice = st.selectbox(
    "Agent:",
    LABELS,
    index=LABELS.index(st.session_state.agent_choice),
    label_visibility="collapsed",
)
aid = LABEL_TO_AGENT[st.session_state.agent_choice]
ag = AG[aid]
prop = [r for r in A["proposal"] if r["agent_id"] == aid]
rec_verdict = {r["scope"]: r["verdict"] for r in RECERT["rows"] if r["agent_id"] == aid}
sib = ", ".join(ag["siblings"])
acct = (f"{esc(ag['service_account'])} (shared with {esc(sib)})" if ag["shared"]
        else f"{esc(ag['service_account'])} (its own)")

st.markdown(
    f"<div class='sk-card'><b>{esc(aid)}</b> - {esc(ag['purpose'])}<br>"
    f"<span class='muted'>Owner {esc(ag['owner'])} · {esc(ag['tier'])} tier · launched {esc(ag['launched_on'])} · "
    f"service account {acct} · {ag['grants']} grants reaching {ag['reach']} scopes.</span></div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p class='muted'>Synthetic data, no model. The agents, scopes and calls are made up: nothing here is a real "
    "bank, platform or incident. The generator decided which grants each agent needs, so the truth is known. "
    "The diff, the proposal, the replay and the ranking are plain rules, not a model. Every number on this page "
    "is printed by a script in <code>src/</code>.</p>",
    unsafe_allow_html=True,
)

if st.session_state.step < 2:
    if st.button("Show what the annual review says  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - Without ScopeKeeper: the review approves the list
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='sk-card'><span class='sk-step-label'>Step 2</span>"
        "<h3>Without ScopeKeeper - the annual review approves the list</h3>"
        "<p class='muted'>The manager sees grant names, dates and ticket numbers. The call log is a "
        "different system, and nobody opens it.</p></div>",
        unsafe_allow_html=True,
    )
    approved = sum(1 for r in prop if rec_verdict[r["scope"]] == "approved")
    removed = [r for r in prop if rec_verdict[r["scope"]] == "removed"]
    hi = [r for r in prop if r["needs_approval"] and rec_verdict[r["scope"]] == "approved"]
    items = [f"<li><b>Approved {approved} of {len(prop)} grants ({100 * approved / len(prop):.1f}%).</b> "
             f"Removed {len(removed)}.</li>"]
    if hi:
        shown = ", ".join(f"<code>{esc(r['scope'])}</code>" for r in hi[:4])
        more = f" and {len(hi) - 4} more" if len(hi) > 4 else ""
        items.append(f"<li>{len(hi)} approved grants are high-impact (a human must approve each call): {shown}{more}.</li>")
    for r in removed:
        used_note = (f"The agent used it in the window; removing it would deny calls."
                     if r["used"] else "It was not used, so this removal happens to be right.")
        items.append(f"<li>Removed <code>{esc(r['scope'])}</code> because the ticket reference is missing. {esc(used_note)}</li>")
    items.append("<li>It saw ticket numbers and grant dates. It did not see a single call.</li>")
    red = ("<div class='bot-bad'><b>What the annual recertification says (MISSED: it checks tickets, not use):</b>"
           "<ul>" + "".join(items) + "</ul>"
           "<div class='small'>Modeled rule: approve a grant with a ticket reference, revoke one without; the "
           "reviewer does not open the call log.</div></div>")

    unused = ag["unused_scopes"]
    shown_unused = "".join(f"<li><code>{esc(s)}</code> ({esc(impact_word(s))})</li>" for s in unused[:8])
    if len(unused) > 8:
        shown_unused += f"<li>and {len(unused) - 8} more</li>"
    items = [f"<li><b>{ag['proposed']} of {ag['reach']}</b> reachable scopes were called in 90 days; "
             f"<b>{ag['cut']}</b> were not.</li>"]
    if unused:
        items.append(f"<li>Never called:<ul>{shown_unused}</ul></li>")
    for r in prop:
        if r["wildcard"]:
            called = 0 if r["action"] == "remove" else len(r["after"])
            items.append(f"<li>Wildcard <code>{esc(r['scope'])}</code> reaches {r['reach']} scopes; "
                         f"{called} were called.</li>")
    if ag["shared"]:
        items.append(f"<li>Shares a service account with {esc(sib)}, so some calls carry no agent tag and are "
                     "credited to every agent that could have made them.</li>")
    if ag["unapproved_tagged"]:
        n_bad = ag["unapproved_tagged"]
        items.append(f"<li><b>{n_bad}</b> {'call' if n_bad == 1 else 'calls'} to approval-required scopes "
                     f"carried no human approval.</li>")
    blue = ("<div class='bot-truth'><b>What the agent actually called (source of truth: the 90-day call log):</b>"
            "<ul>" + "".join(items) + "</ul></div>")

    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**Grants for this agent: what the review saw, and what the log shows**")
        df2 = pd.DataFrame([{
            "Scope": r["scope"], "Impact": r["impact"].replace("_", " "), "Granted on": r["granted_on"],
            "Ticket": r["ticket_id"] or "(none)", "After launch": "yes" if r["post_launch"] else "no",
            "Review verdict": rec_verdict[r["scope"]], "Calls with this agent's tag": r["calls_tagged"],
            "Untagged calls credited": r["calls_shared"],
        } for r in prop])
        st.dataframe(df2, use_container_width=True, hide_index=True)
        st.markdown("**The six named deficiencies of the annual review, over all agents**")
        d = S3
        st.dataframe(pd.DataFrame([
            ("1", "Grants never used in 90 days", f"{d['d1']['unused']} of {d['grants']}"),
            ("2", "Over-broad wildcard grants (1 or 2 scopes touched)", f"{d['d2']['over_broad']} of {d['d2']['wildcards']}"),
            ("3", "Unused grants added after launch", f"{d['d3']['post_launch_unused']} of {d['d3']['post_launch']}"),
            ("4", "Calls with no agent tag on a shared account", f"{d['d4']['unattributed']:,} of {d['d4']['calls']:,}"),
            ("5", "Approval-required calls with no approval", f"{d['d5']['unapproved']} of {d['d5']['approval_required_calls']:,}"),
            ("6", "Unused grants the review removed", f"{d['d6']['recert_removed_unused']} of {d['d6']['usage_unused']}"),
        ], columns=["#", "Deficiency", "Count in this dataset"]), use_container_width=True, hide_index=True)

    if st.session_state.step < 3:
        if st.button("See the fix  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With ScopeKeeper: the proposal and the replay
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='sk-card'><span class='sk-step-label'>Step 3</span>"
        f"<h3>With ScopeKeeper - {esc(aid)} gets the smallest set that covers its calls</h3>"
        "<p class='muted'>ScopeKeeper keeps what was called, removes what was not, and replaces a wildcard by the "
        "scopes actually used. Then it replays the 90 days of calls under the proposal.</p></div>",
        unsafe_allow_html=True,
    )
    agent_calls = [c for c in DATA["calls"] if c["agent_id"] == aid]
    finds = ""
    for r in prop:
        if r["action"] == "keep":
            continue
        if r["action"] == "narrow":
            detail = f"replace by {', '.join(esc(x) for x in r['after'])} ({esc(r['reason'])})"
        else:
            detail = esc(r["reason"])
        finds += (f"<div class='vfind'><span class='vchip'>{esc(r['action'].upper())}</span>"
                  f"<b>{esc(r['scope'])}</b> ({esc(PLAIN_IMPACT[r['impact']])}): {detail}.</div>")
    if not finds:
        finds = "<div class='vfind'>Every grant was used. Nothing to remove.</div>"
    big = f"{ag['cut']} of {ag['reach']} unused" if ag["cut"] else "Nothing to cut"
    st.markdown(
        "<div class='verdict-card verdict-pass'>"
        f"<div class='vlabel'>CAUGHT - ScopeKeeper - proposed scope set for {esc(aid)}</div>"
        f"<div class='vbig'>{esc(big)}</div>"
        f"<div class='vmetric'>Breadth score {ag['breadth_pct']}%: the share of reachable scopes never called</div>"
        "<div class='vrow'>"
        f"<span class='vchip'>Keep {ag['keep']} · remove {ag['remove']} · narrow {ag['narrow']}</span>"
        f"<span class='vchip'>Replay: {S['replay_denied']} of {S['replay_calls']:,} calls denied (by construction)</span>"
        f"<span class='vchip'>Risk rank {ag['rank']} of {S['agents']} · {ag['risk_points']} points</span></div>"
        + finds +
        f"<div class='vtldr'><b>Proposed set ({ag['proposed']} scopes):</b> {esc(', '.join(ag['proposed_scopes']))}</div></div>",
        unsafe_allow_html=True,
    )

    notes = []
    for r in A["rare"]:
        if r["agent_id"] == aid and r["removed"]:
            notes.append(f"Known limit. {r['scope']} is a quarterly scope ({r['why']}), last used {r['last_use_date']}. "
                         f"The log shows no use in 90 days, so the proposal removes it. Its next use is "
                         f"{r['next_use_date']} ({r['calls_next_quarter']} calls), which would be denied unless the owner "
                         "marks the scope as periodic. The logs cannot show that; the owner can.")
        elif r["agent_id"] == aid:
            notes.append(f"Known limit, hidden. {r['scope']} is a quarterly scope and looks used only because another "
                         "agent on the shared account called it. It stays by luck, not by design.")
    kept = [r for r in A["kept_unneeded"] if r["agent_id"] == aid]
    if kept:
        notes.append("Also kept. " + ", ".join(r["scope"] for r in kept) + " stay in the proposal because untagged "
                     "calls on the shared account are credited to every agent that could have made them. By the "
                     "generator's truth this agent does not need them. One service account per agent would fix it.")
    if ag["unapproved_tagged"]:
        n_bad = ag["unapproved_tagged"]
        notes.append(f"{n_bad} {'call' if n_bad == 1 else 'calls'} to approval-required scopes carried no human "
                     "approval. The proposal keeps those scopes and flags the calls for the approval check.")
    for n_ in notes:
        st.markdown(f"<div class='limit-note'>{esc(n_)}</div>", unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**Proposal for this agent, one row per grant**")
        df3 = pd.DataFrame([{
            "Scope": r["scope"], "Action": r["action"],
            "Replace with": ", ".join(r["after"]) if r["action"] == "narrow" else "",
            "Why": r["reason"], "Tagged calls": r["calls_tagged"], "Untagged credited": r["calls_shared"],
        } for r in prop])
        st.dataframe(df3, use_container_width=True, hide_index=True)
        st.markdown("**Dry-run replay**")
        st.markdown(f"The {S['replay_calls']:,} calls of the 90 days were replayed under every agent's proposed set: "
                    f"{S['replay_denied']} denied. This is in-sample and holds by construction, because the proposal "
                    "is built from the same calls. The informative number is the next-quarter count in step 4.")
        st.markdown(f"This agent made {len(agent_calls)} tagged calls.")

    csv_lines = ["agent_id,scope,action,replace_with"]
    csv_lines += [f"{r['agent_id']},{r['scope']},{r['action']},{';'.join(r['after']) if r['action'] == 'narrow' else ''}"
                  for r in prop]
    st.download_button("Download this proposal (CSV)", "\n".join(csv_lines) + "\n",
                       file_name=f"scopekeeper_{aid}.csv", mime="text/csv")

    if st.session_state.step < 4:
        if st.button("See the proof at scale  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='sk-card'><span class='sk-step-label'>Step 4</span>"
        "<h3>Proof at scale</h3>"
        f"<p class='muted'>The same checks over all {S['agents']} agents: {S['grants']} grants, "
        f"{S['calls']:,} calls, and the generator's truth about which grants are needed.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Without ScopeKeeper: annual recertification</div>"
        f"<div class='vbig'>{S['rec_removed']} of {S['grants']}</div>"
        "<div class='vmetric'>grants removed</div>"
        f"<div class='vtldr'>{S['rec_removed_unneeded']} of the {S['unneeded_grants']} grants no agent needs. "
        "It checks that a ticket exists, not that the access is used.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>The call log, read once</div>"
        f"<div class='vbig'>{S['unused_grants_log']} of {S['grants']}</div>"
        "<div class='vmetric'>grants had no call in 90 days</div>"
        "<div class='vtldr'>Found by comparing the grant list with the call log, nothing else.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With ScopeKeeper: unneeded grants removed</div>"
        f"<div class='vbig'>{S['sk_removed_unneeded']} of {S['unneeded_grants']}</div>"
        "<div class='vmetric'>grants no agent needs</div>"
        f"<div class='vtldr'>Effective entitlements go from {S['reach_before']} to {S['reach_after']} "
        f"(cut {S['reach_cut_pct']}%).</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With ScopeKeeper: dry-run replay</div>"
        f"<div class='vbig'>{S['replay_denied']} of {S['replay_calls']:,}</div>"
        "<div class='vmetric'>calls denied under the proposal</div>"
        "<div class='vtldr'>By construction: the proposal is built from these same calls.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>"
        f"<li>{S['rare_grants']} grants are legitimate but used once a quarter. A 90-day window cannot see them. "
        f"The proposal removes {S['rare_removed']} of them, and the next quarter would deny {S['next_q_denied']} "
        "legitimate calls until owners mark those scopes as periodic. The logs cannot show it; an owner attestation "
        "flag is the fix, and it is designed, not built.</li>"
        f"<li>On shared service accounts, {S['sk_kept_unneeded']} unneeded grants stay because untagged calls are "
        "credited to every agent that could have made them. One service account per agent is the fix.</li>"
        f"<li>The replay's {S['replay_denied']} denied calls is in-sample and holds by construction. It says nothing "
        "about calls that will happen after the review.</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Which agents hold the most access they never use**")
    st.caption("Effective entitlements per agent: the part the proposal keeps, and the part it cuts. Highest risk first.")
    order = sorted(A["agents"], key=lambda r: r["rank"])
    fig = go.Figure()
    fig.add_bar(x=[r["agent_id"] for r in order], y=[r["proposed"] for r in order], name="kept (called in 90 days)",
                marker_color="#0a7c3f")
    fig.add_bar(x=[r["agent_id"] for r in order], y=[r["cut"] for r in order], name="cut (never called)",
                marker_color="#f59e0b")
    fig.update_layout(barmode="stack", height=360, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("See the data"):
        st.dataframe(pd.DataFrame([{
            "Risk rank": r["rank"], "Agent": r["agent_id"], "Tier": r["tier"], "Reach": r["reach"],
            "Proposed": r["proposed"], "Cut": r["cut"], "Breadth %": r["breadth_pct"],
            "Unapproved calls": r["unapproved_tagged"], "Shared account": "yes" if r["shared"] else "no",
            "Risk points": r["risk_points"],
        } for r in order]), use_container_width=True, hide_index=True)
        st.caption(f"Risk points = tier multiplier x impact-weighted unused entitlements + {APPROVAL_POINTS} per "
                   f"unapproved call + {SHARED_POINTS} for a shared account. The weights are assumptions of a modeled bank.")

    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("Scope", "A permission to call one kind of tool action, such as payments:initiate_wire."),
            ("Wildcard", "A scope such as accounts:* that reaches every specific scope in its namespace."),
            ("Grant", "One row saying an agent holds a scope, with the date and the ticket that asked for it."),
            ("Effective entitlement", "One agent and one specific scope it can reach, wildcards expanded."),
            ("Breadth score", "The share of an agent's effective entitlements it never called in 90 days."),
            ("Dry-run replay", "Replaying the logged calls under the proposed scope set to count what would be denied."),
            ("Periodic scope", "A legitimate scope used less often than every 90 days, such as a quarter-end job."),
            ("Shared service account", "One credential used by several agents, so the log may not say which agent called."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is a nightly job that reads the agent "
            "platform's grant store and tool-call log, a diff and proposal service, a dry-run replay worker, and a "
            "review queue where the owner and the access-governance reviewer approve or reject each change. It is a "
            "design, not deployed; see `ARCHITECTURE.md`. Related projects: AgentWatch (05) supplies call logs, "
            "PromptShield (06) is the tool-call gate, and OversightOps (08) holds the human approvals."
        )
    st.markdown(
        "<div class='sk-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>. Control reference: "
        f"<a href='{NIST_URL}' target='_blank'>NIST SP 800-53 Rev 5</a> (AC-6, least privilege).</div>",
        unsafe_allow_html=True,
    )
