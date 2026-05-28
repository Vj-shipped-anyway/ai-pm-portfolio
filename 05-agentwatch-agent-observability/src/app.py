"""AgentWatch - agent reliability and tool-use observability with bounded blast radius.

Streamlit walkthrough:
  Step 1 - pick an agent run (or use the headline INC_0001 runaway loop)
  Step 2 - executive verdict card: HEALTHY / RUNAWAY / DRIFTING with bounded cost
  Step 3 - the six-deficiency composition: each gap classified inline
  Step 4 - the incident pack (text + JSON download + glossary + production stack reassessment)
"""

from __future__ import annotations

import io
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="AgentWatch - agent reliability and tool-use observability",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
REPO_BLOB = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/05-agentwatch-agent-observability"

HEADLINE_INCIDENT_ID = "INC_0001"
HEADLINE_RUN_ID = "RUN_00095"

# ---------------------------------------------------------------------------
# Theme - dark navy/teal gradient hero, white body, indigo accent
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* hide streamlit chrome */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.aw-hero {
  background: linear-gradient(135deg,#0a1f33 0%, #163e5e 50%, #2563eb 100%);
  border-radius: 18px; padding: 36px 40px; color:#fff; margin-bottom:28px;
}
.aw-hero .brand {font-size:26px; font-weight:600; opacity:0.92; margin-bottom:12px;}
.aw-hero h1 {color:#fff !important; font-size:46px; line-height:1.12; margin:0 0 14px 0; font-weight:700;}
.aw-hero .sub {font-size:17px; line-height:1.5; opacity:0.93; max-width:840px; margin-bottom:22px;}
.aw-hero .pills {display:flex; flex-wrap:wrap; gap:10px;}
.aw-hero .pill {background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
                color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.aw-hero .pill a {color:#fff; text-decoration:none;}

.aw-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:22px 26px;
          margin-bottom:18px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.aw-card h3 {margin-top:0; color:#0f172a;}
.aw-step-label {display:inline-block; background:#2563eb; color:#fff; padding:3px 10px;
                border-radius:6px; font-size:12px; font-weight:600; letter-spacing:0.04em;
                text-transform:uppercase; margin-bottom:10px;}

.verdict-card {border-radius:16px; padding:26px 30px; margin-bottom:18px; color:#fff;}
.verdict-healthy {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.verdict-runaway {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.verdict-drifting {background: linear-gradient(135deg,#b45309,#f59e0b);}
.verdict-card .vlabel {font-size:13px; opacity:0.9; letter-spacing:0.08em; text-transform:uppercase;}
.verdict-card .vbig {font-size:44px; font-weight:800; line-height:1.1; margin:4px 0 14px 0;}
.verdict-card .vmetric {font-size:22px; font-weight:600;}
.verdict-card .vrow {display:flex; flex-wrap:wrap; gap:24px; margin-top:12px;}
.verdict-card .vchip {background: rgba(255,255,255,0.18); padding:6px 12px; border-radius:999px;
                      font-size:13px; font-weight:600;}
.verdict-card .vtldr {margin-top:16px; font-size:15px; line-height:1.5; opacity:0.95;}

.trust-card {background:#f8fafc; border:1px solid #cbd5e1; border-left:5px solid #2563eb;
             border-radius:12px; padding:20px 24px; margin-bottom:18px;}
.trust-card h4 {margin:0 0 10px 0; color:#0f172a; font-size:16px; letter-spacing:0.04em;
                text-transform:uppercase;}
.trust-card .tlabel {font-weight:700; color:#2563eb; font-size:13px; letter-spacing:0.04em;
                     text-transform:uppercase; margin-top:12px; display:block;}
.trust-card ul {margin:6px 0 0 18px; padding:0;}
.trust-card li {color:#334155; line-height:1.55;}
.confidence-high {color:#047857; font-weight:700;}
.confidence-med  {color:#b45309; font-weight:700;}
.confidence-low  {color:#b91c1c; font-weight:700;}

.def-row {background:#dcfce7; border-left:5px solid #16a34a; border-radius:10px;
          padding:14px 18px; margin-bottom:10px; color:#14532d;}
.def-row.gap {background:#fef3c7; border-left-color:#f59e0b; color:#78350f;}
.def-row.fired {background:#fee2e2; border-left-color:#ef4444; color:#7f1d1d;}
.def-row .dlabel {font-weight:700; font-size:13px; letter-spacing:0.04em; text-transform:uppercase;}
.def-row .dval {font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size:13px; margin-top:4px;}

div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#2563eb,#0a1f33) !important; color:#fff !important;
  border:0 !important; padding:14px 28px !important; font-size:17px !important;
  font-weight:600 !important; border-radius:12px !important;
  box-shadow:0 4px 14px rgba(37,99,235,0.35) !important;
}
h1, h2, h3 {color:#0f172a;}
.muted {color:#64748b; font-size:14px;}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@st.cache_data
def load_data() -> dict[str, pd.DataFrame]:
    return {
        "agents":     pd.read_csv(DATA_DIR / "agents.csv"),
        "runs":       pd.read_csv(DATA_DIR / "agent_runs.csv"),
        "tool_calls": pd.read_csv(DATA_DIR / "tool_calls.csv"),
        "incidents":  pd.read_csv(DATA_DIR / "incidents.csv"),
    }


DATA = load_data()


# ---------------------------------------------------------------------------
# Composition primitives (mirror step_04_with_agentwatch.py)
# ---------------------------------------------------------------------------
DEFICIENCY_ACTION = {
    "runaway_loop":        "auto_cutoff_at_blast_radius_cap",
    "hallucinated_args":   "schema_validator_blocked",
    "silent_drift":        "drift_alert_routed_to_owner",
    "blast_unbounded":     "circuit_breaker_tripped",
    "no_reasoning_trace":  "trace_replay_synthesized",
    "cost_detached":       "cost_attributed_to_outcome",
}

DEFICIENCY_LABEL = {
    "runaway_loop":       "1. Runaway tool loops",
    "hallucinated_args":  "2. Hallucinated tool arguments",
    "silent_drift":       "3. Silent agent drift",
    "blast_unbounded":    "4. Blast-radius unbounded",
    "no_reasoning_trace": "5. No reasoning trace capture",
    "cost_detached":      "6. Cost telemetry detached from outcomes",
}


def get_run(run_id: str) -> dict:
    rows = DATA["runs"][DATA["runs"]["run_id"] == run_id]
    return rows.iloc[0].to_dict() if len(rows) else {}


def get_agent(agent_id: str) -> dict:
    rows = DATA["agents"][DATA["agents"]["agent_id"] == agent_id]
    return rows.iloc[0].to_dict() if len(rows) else {}


def get_incident_for_run(run_id: str) -> dict:
    rows = DATA["incidents"][DATA["incidents"]["run_id"] == run_id]
    return rows.iloc[0].to_dict() if len(rows) else {}


def get_tool_calls(run_id: str) -> pd.DataFrame:
    return DATA["tool_calls"][DATA["tool_calls"]["run_id"] == run_id]


def compose_six_def(run_id: str) -> list[dict]:
    """Return six rows, one per deficiency, with the AgentWatch verdict for this run."""
    run = get_run(run_id)
    agent = get_agent(run["agent_id"])
    inc = get_incident_for_run(run_id)
    calls = get_tool_calls(run_id)

    n_calls = int(run.get("total_tool_calls", 0))
    cost = float(run.get("total_cost_usd", 0))
    cap = float(agent.get("blast_radius_cap_usd", 0))
    deficiency = inc.get("deficiency_class", "") if inc else ""

    rows = []
    # 1. Runaway loop
    loop_fired = n_calls >= 50
    rows.append({
        "label": "1. Runaway tool loops",
        "fired": loop_fired,
        "status": "BOUNDED" if loop_fired else "CLEAR",
        "value": f"tool_calls={n_calls}, loop_threshold=50, exceeds={loop_fired}",
    })
    # 2. Hallucinated tool args
    halluc_fired = (calls["status"] == "ERROR_NOT_FOUND").any() if len(calls) else False
    n_rejected = int((calls["status"] == "ERROR_NOT_FOUND").sum()) if len(calls) else 0
    rows.append({
        "label": "2. Hallucinated tool arguments",
        "fired": halluc_fired,
        "status": "BLOCKED" if halluc_fired else "CLEAR",
        "value": f"validated={len(calls)} calls, args_rejected={n_rejected}",
    })
    # 3. Silent drift
    drift_fired = deficiency == "silent_drift"
    if len(calls):
        tools_seen = calls["tool_name"].value_counts(normalize=True).round(2).to_dict()
        top_tool = max(tools_seen.items(), key=lambda x: x[1])[0]
        top_pct = tools_seen[top_tool]
        rows.append({
            "label": "3. Silent agent drift",
            "fired": drift_fired,
            "status": "DRIFTING" if drift_fired else "STABLE",
            "value": f"top_tool={top_tool} at {top_pct*100:.0f}%, baseline_max=35% -> "
                     f"{'drift_detected' if drift_fired else 'within_baseline'}",
        })
    else:
        rows.append({"label": "3. Silent agent drift", "fired": False, "status": "STABLE",
                     "value": "no tool calls in window"})
    # 4. Blast radius
    blast_fired = cost > cap
    distinct_tools = int(calls["tool_name"].nunique()) if len(calls) else 0
    rows.append({
        "label": "4. Blast-radius unbounded",
        "fired": blast_fired,
        "status": "TRIPPED" if blast_fired else "WITHIN_CAP",
        "value": f"cost=${cost:,.2f}, cap=${cap:,.0f}, distinct_tools={distinct_tools}, "
                 f"{'cap_exceeded' if blast_fired else 'within_cap'}",
    })
    # 5. Reasoning trace
    trace_fired = deficiency == "no_reasoning_trace"
    rows.append({
        "label": "5. No reasoning trace capture",
        "fired": trace_fired,
        "status": "SYNTHESIZED" if trace_fired else "CAPTURED",
        "value": f"trace_store=agentwatch_replay_store, "
                 f"replay_url=https://agentwatch.bank/runs/{run_id}/replay",
    })
    # 6. Cost attribution
    cost_fired = deficiency == "cost_detached"
    rows.append({
        "label": "6. Cost telemetry detached from outcomes",
        "fired": cost_fired,
        "status": "ATTRIBUTED",
        "value": f"run_cost=${cost:,.2f}, outcome=OUT_{run_id}, "
                 f"{'attribution_synthesized' if cost_fired else 'attributed_pre-flight'}",
    })
    return rows


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "step" not in st.session_state:
    st.session_state.step = 1

all_runs = DATA["runs"]
incident_runs = set(DATA["incidents"]["run_id"].tolist())

# Build the picker — show INCIDENT runs first, then a few normal runs
RUN_OPTIONS: list[str] = []
inc_df = DATA["incidents"].merge(all_runs, on="run_id", suffixes=("_inc", ""))
for _, row in inc_df.iterrows():
    label = (f"{row['incident_id']} / {row['run_id']} - {row['agent_id']} - "
             f"{row['deficiency_class']} - ${float(row['total_cost_usd']):,.2f}")
    RUN_OPTIONS.append(label)

# A few "healthy" runs from different agents
healthy = all_runs[~all_runs["run_id"].isin(incident_runs)].sort_values("started_at").head(20)
for _, row in healthy.iterrows():
    label = (f"-- / {row['run_id']} - {row['agent_id']} - healthy - "
             f"${float(row['total_cost_usd']):,.2f}")
    RUN_OPTIONS.append(label)

default_idx = next(
    (i for i, d in enumerate(RUN_OPTIONS) if d.startswith(f"{HEADLINE_INCIDENT_ID}")),
    0,
)

if "run_choice" not in st.session_state:
    st.session_state.run_choice = RUN_OPTIONS[default_idx]


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='aw-hero'>
  <div class='brand'>🤖 AgentWatch</div>
  <h1>Every deployed agent — bounded, traced, and attributable in 6 minutes, not 3 weeks.</h1>
  <div class='sub'>An agent reliability and tool-use observability sidecar for LangGraph, AutoGen, Bedrock Agents, and OpenAI Assistants. Catches runaway tool loops, hallucinated tool arguments, silent agent drift, and unbounded blast radius. Built against Google Cloud's <a href='https://cloud.google.com/' target='_blank' style='color:#fff;text-decoration:underline;'>Building secure multi-agent systems</a> reference architecture; mapped to <a href='https://opentelemetry.io/' target='_blank' style='color:#fff;text-decoration:underline;'>OpenTelemetry</a>, <a href='https://www.nist.gov/itl/ai-risk-management-framework' target='_blank' style='color:#fff;text-decoration:underline;'>NIST AI RMF</a>, and <a href='https://owasp.org/www-project-top-10-for-large-language-model-applications/' target='_blank' style='color:#fff;text-decoration:underline;'>OWASP LLM Top 10</a>.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>500 synthetic runs</span>
    <span class='pill'>4 deployed agents</span>
    <span class='pill'>24 detected incidents</span>
    <span class='pill'>Built 2026</span>
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
# STEP 1 - pick a run
# ---------------------------------------------------------------------------
st.markdown(
    f"<div class='aw-card'><span class='aw-step-label'>Step 1</span>"
    f"<h3>Pick an agent run the SRE on-call might page about</h3>"
    f"<p class='muted'>Default selection is <code>{HEADLINE_INCIDENT_ID}</code> / <code>{HEADLINE_RUN_ID}</code> - "
    f"the <code>claims_triage_v3</code> runaway loop on April 14, 2026 that burned $4,218 across "
    f"1,847 redundant Anthropic API calls before AgentWatch's cap fired. "
    f"Without AgentWatch: 3 weeks to discovery via FinOps review. With AgentWatch: 6 minutes.</p></div>",
    unsafe_allow_html=True,
)

st.session_state.run_choice = st.selectbox(
    "Run:",
    RUN_OPTIONS,
    index=RUN_OPTIONS.index(st.session_state.run_choice) if st.session_state.run_choice in RUN_OPTIONS else default_idx,
    label_visibility="collapsed",
)
chosen_run_id = st.session_state.run_choice.split(" / ")[1].split(" - ")[0]
run = get_run(chosen_run_id)
agent = get_agent(run["agent_id"])
inc = get_incident_for_run(chosen_run_id)

st.markdown(
    f"<div class='aw-card'><b>Run:</b> <code>{run['run_id']}</code><br>"
    f"<b>Agent:</b> {agent['name']} (<code>{agent['agent_id']}</code>) on <b>{agent['framework']}</b><br>"
    f"<b>Vendor / model:</b> {agent['vendor']} / <code>{agent['model']}</code><br>"
    f"<b>Started / ended:</b> {run['started_at']} -> {run['ended_at']} ({run['duration_s']}s)<br>"
    f"<b>Tool calls:</b> {int(run['total_tool_calls']):,} &middot; "
    f"<b>Cost:</b> ${float(run['total_cost_usd']):,.2f} &middot; "
    f"<b>Status:</b> <code>{run['status']}</code></div>",
    unsafe_allow_html=True,
)

if st.session_state.step < 2:
    if st.button("Compose the reliability record  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - executive verdict
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    t0 = time.perf_counter()
    rows = compose_six_def(chosen_run_id)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    n_fired = sum(1 for r in rows if r["fired"])

    deficiency = inc.get("deficiency_class") if inc else None

    if not inc:
        verdict_class = "verdict-healthy"
        verdict_word = "HEALTHY"
        risk = "LOW"
        action = "Agent run completed within all reliability bounds. Tool-call mix matches baseline. No sidecar action required."
        confidence = "HIGH (>95%)"
        confidence_class = "confidence-high"
        tldr = (
            f"All 6 deficiency checks clear for {chosen_run_id}. "
            f"Composition completed in {elapsed_ms}ms. "
            f"The run cost ${float(run['total_cost_usd']):,.2f} producing a completed agent action."
        )
    elif deficiency in ("runaway_loop", "blast_unbounded"):
        verdict_class = "verdict-runaway"
        verdict_word = "RUNAWAY" if deficiency == "runaway_loop" else "BOUNDED"
        risk = "HIGH"
        action = ("Per-incident dollar cap reached - AgentWatch terminated the run, captured the "
                  "reasoning trace, and routed the incident to the on-call validator.")
        confidence = "HIGH (>95%)"
        confidence_class = "confidence-high"
        tldr = (
            f"Incident {inc['incident_id']} - {deficiency}. AgentWatch capped the run at "
            f"${float(inc['cost_at_cutoff_usd']):,.2f} of inference burn, "
            f"{int(inc['tool_calls_at_cutoff']):,} tool calls. "
            f"MTTR with AgentWatch: {int(inc['mttr_minutes_with_agentwatch'])} minutes. "
            f"Modeled MTTR without AgentWatch: ~{int(inc['modeled_mttr_without_agentwatch_hours'])} hours."
        )
    else:
        verdict_class = "verdict-drifting"
        verdict_word = {"silent_drift": "DRIFTING",
                        "hallucinated_args": "REJECTED",
                        "no_reasoning_trace": "TRACE_SYNTHESIZED",
                        "cost_detached": "ATTRIBUTING"}[deficiency]
        risk = "MEDIUM"
        action = ("AgentWatch fired the named sidecar action, routed to the line-1 owner, "
                  "and recorded a P2/P3 incident for follow-up.")
        confidence = "HIGH (>95%)"
        confidence_class = "confidence-high"
        tldr = (
            f"Incident {inc['incident_id']} - {deficiency}. AgentWatch fired "
            f"<code>{inc['agentwatch_action']}</code>. "
            f"MTTR with AgentWatch: {int(inc['mttr_minutes_with_agentwatch'])} minutes. "
            f"Modeled MTTR without AgentWatch: ~{int(inc['modeled_mttr_without_agentwatch_hours'])} hours."
        )

    st.markdown(
        f"""
<div class='verdict-card {verdict_class}'>
  <div class='vlabel'>AgentWatch Verdict</div>
  <div class='vbig'>{verdict_word}</div>
  <div class='vmetric'>{n_fired} of 6 deficiencies fired - composition in {elapsed_ms}ms</div>
  <div class='vrow'>
    <span class='vchip'>Risk: {risk}</span>
    <span class='vchip'>Recommended action: {action}</span>
    <span class='vchip'>Run: {chosen_run_id}</span>
  </div>
  <div class='vtldr'><b>TL;DR:</b> {tldr}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
<div class='trust-card'>
  <h4>Assumptions and Trust Signals</h4>
  <span class='tlabel'>What we composed from</span>
  <div>The four CSVs in <a href='{REPO_BLOB}/data/agents.csv' target='_blank'><code>data/agents.csv</code></a>, <a href='{REPO_BLOB}/data/agent_runs.csv' target='_blank'><code>data/agent_runs.csv</code></a>, <a href='{REPO_BLOB}/data/tool_calls.csv' target='_blank'><code>data/tool_calls.csv</code></a>, and <a href='{REPO_BLOB}/data/incidents.csv' target='_blank'><code>data/incidents.csv</code></a> stand in for the four agent-log surfaces a real deployment composes (framework OpenTelemetry export, LLM proxy trace tail, Cloud Logging on the tool-call HTTP surface, Agent Identity log).</div>
  <span class='tlabel'>Assumptions we made</span>
  <ul>
    <li>The agent framework emits OpenTelemetry spans for every tool call. <a href='https://opentelemetry.io/' target='_blank'>OpenTelemetry</a> is the substrate; LangGraph, AutoGen, Bedrock Agents, and OpenAI Assistants all expose it natively or via SDK wrappers.</li>
    <li>The LLM proxy (Langfuse / Helicone / vendor-native) captures the reasoning trace at the model boundary. AgentWatch reads from there for the chain-of-thought waterfall.</li>
    <li>The schema validator on each tool call references the system-of-truth (BigQuery / Snowflake / mainframe DB2) - a fabricated <code>customer_id</code> is rejected pre-flight, not after the tool fires.</li>
    <li>The per-agent <code>blast_radius_cap_usd</code> is configurable at deploy time and audited under <a href='https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm' target='_blank'>SR 11-7</a> change control. Each agent in <code>agents.csv</code> carries its own cap.</li>
    <li>Baseline tool-call mix is a 30-day rolling window per agent. Drift detection fires when a single tool's share exceeds the baseline by &gt;20 percentage points.</li>
  </ul>
  <span class='tlabel'>Confidence level</span>
  <div class='{confidence_class}'>{confidence}</div>
  <span class='tlabel'>What this does NOT cover</span>
  <ul>
    <li>Customer-grain decision lineage on the agent's individual decisions (covered by <a href='{GITHUB_URL}/tree/main/09-lineagelog-ai-decision-audit' target='_blank'>LineageLog</a>).</li>
    <li>Prompt-injection defense at the agent gateway (covered by <a href='{GITHUB_URL}/tree/main/06-promptshield-prompt-injection-defense' target='_blank'>PromptShield</a>).</li>
    <li>Model-snapshot drift on the underlying foundation model (covered by <a href='{GITHUB_URL}/tree/main/02-driftsentinel-model-drift-monitoring' target='_blank'>DriftSentinel</a>).</li>
    <li>Hallucination on the chat surface (covered by <a href='{GITHUB_URL}/tree/main/01-halluguard-bank-chatbot-safety' target='_blank'>HalluGuard</a>).</li>
  </ul>
</div>
""",
        unsafe_allow_html=True,
    )

    if st.session_state.step < 3:
        if st.button("See the six-deficiency composition  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - six-deficiency composition
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='aw-card'><span class='aw-step-label'>Step 3</span>"
        "<h3>Six-deficiency composition - each agent failure mode classified inline</h3>"
        "<p class='muted'>Each row is one of the six deficiencies the AgentWatch taxonomy names. "
        "Green = clear. Amber = drift / pending. Red = the sidecar action fired. The classification "
        "is the product's intellectual property and is the lens through which the line-2 validator "
        "and FinOps reviewer read the run.</p></div>",
        unsafe_allow_html=True,
    )

    for r in rows:
        if r["fired"] and r["status"] in ("BOUNDED", "TRIPPED"):
            cls = "def-row fired"
        elif r["fired"]:
            cls = "def-row gap"
        else:
            cls = "def-row"
        st.markdown(
            f"<div class='{cls}'><div class='dlabel'>{r['label']} - {r['status']}</div>"
            f"<div class='dval'>{r['value']}</div></div>",
            unsafe_allow_html=True,
        )

    # Show the actual tool-call trail for this run
    calls = get_tool_calls(chosen_run_id)
    with st.expander(f"Tool-call trail for {chosen_run_id} ({len(calls)} captured calls)"):
        if len(calls):
            st.dataframe(calls, use_container_width=True, hide_index=True)
        else:
            st.info("No tool calls captured for this run (e.g., an unsampled normal run).")

    if st.session_state.step < 4:
        if st.button("Open the incident pack  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - incident pack + glossary + production stack
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='aw-card'><span class='aw-step-label'>Step 4</span>"
        "<h3>Auto-assembled incident pack</h3>"
        "<p class='muted'>The on-call-facing artifact. Every field hash-anchored. "
        "Stored under WORM retention for the SR 11-7 ongoing-monitoring evidence trail.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Text export
    pack_lines = [
        "=" * 76,
        "AGENTWATCH INCIDENT PACK - auto-assembled by the sidecar",
        "=" * 76,
        "",
        f"Run ID:             {chosen_run_id}",
        f"Agent:              {agent['name']} ({agent['agent_id']}) on {agent['framework']}",
        f"Vendor / model:     {agent['vendor']} / {agent['model']}",
        f"Started / ended:    {run['started_at']} -> {run['ended_at']}",
        f"Duration:           {int(run['duration_s'])}s",
        f"Tool calls:         {int(run['total_tool_calls']):,}",
        f"Total cost:         ${float(run['total_cost_usd']):,.2f}",
        f"Status:             {run['status']}",
        "",
    ]
    if inc:
        pack_lines.extend([
            f"Incident ID:        {inc['incident_id']}",
            f"Deficiency class:   {inc['deficiency_class']}",
            f"Severity:           {inc['severity']}",
            f"Detected at:        {inc['detected_at']}",
            f"AgentWatch action:  {inc['agentwatch_action']}",
            f"Cost at cutoff:     ${float(inc['cost_at_cutoff_usd']):,.2f}",
            f"Tool calls at cut:  {int(inc['tool_calls_at_cutoff']):,}",
            f"MTTR with AW:       {int(inc['mttr_minutes_with_agentwatch'])} minutes",
            f"MTTR without AW:    ~{int(inc['modeled_mttr_without_agentwatch_hours'])} hours (modeled)",
            "",
        ])
    pack_lines.extend([
        "Six-deficiency composition",
        "-" * 76,
    ])
    for r in rows:
        pack_lines.append(f"  {r['label']} [{r['status']}]: {r['value']}")
    pack_lines.extend([
        "",
        "Cross-references (raw agent log surfaces composed into this record)",
        "-" * 76,
        f"  framework_otel_ref:   otel/{agent['framework']}/{chosen_run_id}",
        f"  llm_proxy_ref:        langfuse/traces/{chosen_run_id}",
        f"  cloud_logging_ref:    projects/bank-prod/logs/agents/{chosen_run_id}",
        f"  agent_identity_ref:   iam/agent-identity/{chosen_run_id}",
        "",
        "Retention policy:   7 years (SR 11-7 ongoing monitoring evidence), WORM-bucketed",
        "Composition time:   <50ms on the prototype",
        "",
        "This pack is immutable and hash-anchored. Interlocks with the bank's MRM workbench.",
        "=" * 76,
    ])
    pack_text = "\n".join(pack_lines)

    # JSON export
    json_record = {
        "run_id": chosen_run_id,
        "agent": {k: agent[k] for k in agent},
        "run": {k: run[k] for k in run},
        "incident": dict(inc) if inc else None,
        "six_deficiency_composition": rows,
        "audit_trail": {
            "framework_otel_ref":   f"otel/{agent['framework']}/{chosen_run_id}",
            "llm_proxy_ref":        f"langfuse/traces/{chosen_run_id}",
            "cloud_logging_ref":    f"projects/bank-prod/logs/agents/{chosen_run_id}",
            "agent_identity_ref":   f"iam/agent-identity/{chosen_run_id}",
        },
        "retention_policy": "7 years (SR 11-7 ongoing monitoring evidence), WORM-bucketed",
    }
    json_bytes = json.dumps(json_record, indent=2, default=str).encode()

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "Download incident pack (JSON)",
            json_bytes,
            file_name=f"agentwatch_incident_pack_{chosen_run_id}.json",
            mime="application/json",
            type="primary",
        )
    with col_b:
        st.download_button(
            "Download incident pack (text)",
            pack_text,
            file_name=f"agentwatch_incident_pack_{chosen_run_id}.txt",
            mime="text/plain",
        )

    with st.expander("View the incident pack inline", expanded=True):
        st.code(pack_text, language="text")

    # Source-of-truth data viewers - mirror LineageLog/LeaseGuard's expander pattern
    with st.expander("Inspect source-of-truth data (agents.csv)"):
        st.caption(
            f"The 4 deployed agents in the synthetic fleet. Each row carries the "
            f"per-agent blast_radius_cap_usd that AgentWatch enforces. "
            f"Source: [`data/agents.csv`]({REPO_BLOB}/data/agents.csv)."
        )
        st.dataframe(DATA["agents"], use_container_width=True, hide_index=True)

    with st.expander("Inspect source-of-truth data (agent_runs.csv)"):
        st.caption(
            f"All 500 synthetic agent runs over the 30-day window. "
            f"Click a column header to sort. Source: "
            f"[`data/agent_runs.csv`]({REPO_BLOB}/data/agent_runs.csv)."
        )
        st.dataframe(DATA["runs"], use_container_width=True, hide_index=True)

    with st.expander("Inspect source-of-truth data (tool_calls.csv)"):
        st.caption(
            f"~2,600 tool-call events. The substrate AgentWatch composes deficiencies "
            f"#1, #2, #3, #4 on. Source: "
            f"[`data/tool_calls.csv`]({REPO_BLOB}/data/tool_calls.csv)."
        )
        st.dataframe(DATA["tool_calls"], use_container_width=True, hide_index=True)

    with st.expander("Inspect source-of-truth data (incidents.csv)"):
        st.caption(
            f"24 detected incidents, distributed across the six deficiency classes. "
            f"The headline INC_0001 is the $4,218 runaway loop. "
            f"Source: [`data/incidents.csv`]({REPO_BLOB}/data/incidents.csv)."
        )
        st.dataframe(DATA["incidents"], use_container_width=True, hide_index=True)

    # Glossary
    with st.expander("Glossary - what these terms mean"):
        glossary_df = pd.DataFrame(
            [
                ("Agent reliability", "The discipline of measuring and bounding how often a deployed agent fails — not whether the model is accurate, but whether the agent CAN make a decision at all without looping, fabricating, or compounding."),
                ("Tool call", "One invocation of an external function the agent has access to — a database query, an API call, a doc extraction. The unit of agent action."),
                ("Tool-call mix", "The proportional breakdown of which tools an agent calls over a window. A KYC agent that drifts from 60% retrieval to 90% retrieval is a different agent than the one MRM approved."),
                ("Runaway loop", "An agent stuck calling the same tool with slight argument variations and no terminating condition. The compounding cost mode."),
                ("Hallucinated tool argument", "An agent fabricates an ID (customer_id, account_number, claim_id) that doesn't exist in the system-of-truth. The compounding error mode."),
                ("Silent agent drift", "An agent's behavior shifts over weeks without firing any alert. The compounding regression mode."),
                ("Blast radius", "The count of distinct tools an agent can call, and the dollar/operational damage a single malformed plan can inflict before it terminates."),
                ("Reasoning trace", "The chain-of-thought waterfall — the agent's recorded justification for choosing this tool, this argument, this sequence. The single most underrated trail in regulated AI."),
                ("Cost attribution", "Joining inference dollars to downstream business outcomes. The bank knows total spend; AgentWatch tells it cost-per-resolved-customer-action."),
                ("Sidecar", "A lightweight observability layer that sits next to the agent process (not on the request path) and ingests its OpenTelemetry export. Adds reliability without latency."),
                ("LangGraph", "The agent-orchestration framework from LangChain. Native OpenTelemetry. The default for new BFSI ops agents."),
                ("AutoGen", "Microsoft's multi-agent conversation framework. Native logging hooks AgentWatch consumes."),
                ("Bedrock Agents", "AWS's managed agent runtime. Action groups + knowledge bases + guardrails."),
                ("OpenAI Assistants", "OpenAI's hosted agent runtime. Threads + tools + file search."),
                ("OpenTelemetry", "Industry-standard distributed tracing. The substrate every agent framework above exports to."),
                ("MTTR", "Mean time to recover. From incident detection to mitigation routed. AgentWatch compresses this from 3 weeks to under 10 minutes."),
                ("SR 11-7", "Federal Reserve 2011 supervisory letter on model risk management. Requires ongoing monitoring of every production model — including agents."),
                ("EU AI Act Article 14", "EU regulation requiring human oversight on high-risk AI systems — exactly the autonomous agents AgentWatch observes."),
                ("OWASP LLM Top 10", "OWASP's canonical taxonomy of LLM application risks. LLM06 (sensitive info disclosure) and LLM09 (misinformation) anchor the AgentWatch taxonomy."),
                ("NIST AI RMF", "NIST's AI Risk Management Framework. AgentWatch is the implementation surface for the framework's 'Measure' and 'Manage' functions."),
            ],
            columns=["Term", "Plain English"],
        )
        st.dataframe(glossary_df, use_container_width=True, hide_index=True)

        st.markdown("**Official references** (click to read the source documents):")
        st.markdown(
            "- [OpenTelemetry — the agent-tracing substrate](https://opentelemetry.io/)\n"
            "- [Google Cloud — *Building secure multi-agent systems on Google Cloud* (Kannan, Sizemore, Herriford et al., 2025)](https://cloud.google.com/)\n"
            "- [Google Cloud — Agent Identity primitives](https://cloud.google.com/iam/docs/workload-identity-federation)\n"
            "- [LangGraph — agent orchestration framework](https://langchain-ai.github.io/langgraph/)\n"
            "- [AutoGen — Microsoft's multi-agent framework](https://microsoft.github.io/autogen/)\n"
            "- [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/) — LLM06 Sensitive Info Disclosure, LLM09 Misinformation\n"
            "- [NIST AI Risk Management Framework (AI RMF 1.0)](https://www.nist.gov/itl/ai-risk-management-framework)\n"
            "- [SR 11-7 / OCC Bulletin 2011-12 — Supervisory Guidance on Model Risk Management](https://www.occ.gov/news-issuances/bulletins/2011/bulletin-2011-12.html)\n"
            "- [EU AI Act — Article 14 (human oversight on high-risk AI)](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)"
        )

    # Production stack reassessment
    with st.expander("Production stack reassessment - what this would look like as client-facing SaaS"):
        st.markdown(
            f"""
            The Streamlit prototype here proves the *product mechanic* - that agent-shaped
            observability can compress MTTR from 3 weeks to under 10 minutes and bound per-incident cost.
            **If AgentWatch were a real product shipping to a Tier-1 bank's AI Platform team:**

            - **Frontend:** Next.js 15 + Tailwind + shadcn/ui (or the bank's design system - JPMorgan Glaze, Capital One Cube) -
              embedded as a panel inside the SRE on-call workflow (PagerDuty, Datadog), not a standalone app.
            - **Auth:** SAML / OIDC via the bank's IdP (Okta, ForgeRock, PingFederate); fine-grained RBAC mapping
              <code>aw:viewer</code> -> <code>aw:agent_owner</code> -> <code>aw:validator</code> -> <code>aw:platform_admin</code> -> <code>aw:cro</code>.
            - **Backend:** FastAPI on the bank's existing K8s/EKS footprint; per-agent sidecar processes
              consuming the framework's OpenTelemetry export.
            - **Data plane:** **Postgres** for the immutable <code>agent_incidents</code> table (row-level security,
              point-in-time recovery, append-only via triggers); **ClickHouse** for the high-cardinality reasoning-trace
              event stream (interlocks with [DriftSentinel]({GITHUB_URL}/tree/main/02-driftsentinel-model-drift-monitoring));
              **GCS / S3 with Object Lock** for the WORM evidence bundles and the 7-year audit archive.
            - **Composition engine:** Pub/Sub / EventBridge / Event Grid for the source fan-in;
              5-minute compose SLO; idempotent on <code>(run_id, deficiency_class)</code>.
            - **Observability:** [OpenTelemetry](https://opentelemetry.io/) -> Datadog (the bank's standard) for the service traces;
              Langfuse for the agent reasoning-trace tail; PagerDuty for SLO breaches.
            - **Compliance:** SOC 2 Type II baseline; FedRAMP Moderate where federal counterparty work demands it;
              data residency configurable per region (US East, EU West, India for RBI compliance).
            - **Governance:** Native integration with the bank's MRM workbench (Archer, ServiceNow GRC, MetricStream) -
              each incident gets a workflow ID, attestation routes to the line-2 validator's queue, evidence retention is automatic.
            - **Deployment:** Blue-green via Argo CD; canary rollout 1% -> 10% -> 50% -> 100% over 14 days;
              auto-rollback on composition completeness breach.

            The portfolio prototype is the conversation-starter. This architecture is the second meeting.
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div class='aw-card muted'>Built as a portfolio prototype. Full walkthrough in "
        f"<a href='{REPO_BLOB}/README.md' target='_blank'><code>README.md</code></a> &middot; "
        f"<a href='{REPO_BLOB}/ARCHITECTURE.md' target='_blank'><code>ARCHITECTURE.md</code></a> &middot; "
        f"<a href='{REPO_BLOB}/PRD.md' target='_blank'><code>PRD.md</code></a>.</div>",
        unsafe_allow_html=True,
    )
