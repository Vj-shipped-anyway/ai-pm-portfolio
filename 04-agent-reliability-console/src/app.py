"""
Agent Reliability & Tool-Use Observability — Streamlit Prototype
Author: Vijay Saharan
Run: streamlit run app.py

Demonstrates the three-loop reliability surface (Observe -> Contain -> Replay)
across three deployed BFSI ops agents (reconciliation, dispute, KYC refresh).
Trajectory-level telemetry, classifiers (loop, misuse, runaway, schema drift),
blast-radius circuit breaker, and replay UI. Synthetic data only.
"""

import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# Synthetic agent trajectories
# -----------------------------------------------------------------------------

np.random.seed(11)

AGENTS = {
    "recon_agent_v4": {
        "label": "Reconciliation",
        "tools": ["fetch_ledger", "fetch_statement", "match_entries", "post_adjustment"],
        "read_tools": {"fetch_ledger", "fetch_statement", "match_entries"},
        "write_tools": {"post_adjustment"},
        "budget": {"tokens": 60000, "dollars": 1.20, "wall_seconds": 90, "tool_calls": 15},
    },
    "dispute_agent_v2": {
        "label": "Dispute resolution",
        "tools": ["fetch_dispute", "fetch_txn_history", "classify_dispute_type", "request_evidence", "decide_credit"],
        "read_tools": {"fetch_dispute", "fetch_txn_history", "classify_dispute_type"},
        "write_tools": {"request_evidence", "decide_credit"},
        "budget": {"tokens": 80000, "dollars": 1.60, "wall_seconds": 120, "tool_calls": 18},
    },
    "kyc_refresh_agent_v1": {
        "label": "KYC refresh",
        "tools": ["fetch_customer", "fetch_id_doc", "ofac_check", "update_kyc_status"],
        "read_tools": {"fetch_customer", "fetch_id_doc", "ofac_check"},
        "write_tools": {"update_kyc_status"},
        "budget": {"tokens": 50000, "dollars": 1.00, "wall_seconds": 75, "tool_calls": 12},
    },
}


def gen_trajectory(agent_key, inject=None):
    agent = AGENTS[agent_key]
    tools = agent["tools"]
    n_calls = int(np.random.randint(4, 11))
    calls = []
    tokens = 0
    seconds = 0.0
    schema_ok = True

    for i in range(n_calls):
        tool = np.random.choice(tools)
        dur = float(np.random.uniform(1.5, 6.0))
        tok = int(np.random.randint(2500, 7000))
        calls.append({"step": i + 1, "tool": tool, "duration_s": round(dur, 2), "tokens": tok, "schema_ok": True})
        tokens += tok
        seconds += dur

    # Inject failure modes
    if inject == "loop":
        loop_tool = tools[0]
        for j in range(20):
            calls.append({"step": len(calls) + 1, "tool": loop_tool, "duration_s": 2.4, "tokens": 4200, "schema_ok": True})
            tokens += 4200
            seconds += 2.4
    elif inject == "misuse":
        misused = list(agent["write_tools"])[0]
        # Intent was read-only but a write tool was invoked
        calls.append({"step": len(calls) + 1, "tool": misused, "duration_s": 3.1, "tokens": 5200, "schema_ok": True})
        tokens += 5200
        seconds += 3.1
    elif inject == "runaway":
        for j in range(8):
            calls.append({"step": len(calls) + 1, "tool": np.random.choice(tools), "duration_s": 9.5, "tokens": 12500, "schema_ok": True})
            tokens += 12500
            seconds += 9.5
    elif inject == "schema_drift":
        bad = calls[-1].copy()
        bad["schema_ok"] = False
        calls[-1] = bad
        schema_ok = False

    dollars = round(tokens / 1000 * 0.02, 4)

    return {
        "agent": agent_key,
        "trajectory_id": f"traj_{np.random.randint(1_000_000)}",
        "started_at": datetime.utcnow() - timedelta(seconds=seconds),
        "intent": np.random.choice(["read_intent", "write_intent"]),
        "calls": calls,
        "tokens": tokens,
        "dollars": dollars,
        "wall_seconds": round(seconds, 2),
        "tool_calls": len(calls),
        "schema_ok_overall": schema_ok,
    }


# -----------------------------------------------------------------------------
# Classifiers — Loop 1
# -----------------------------------------------------------------------------

def detect_loop(traj, window=6, threshold=4):
    counts = {}
    for c in traj["calls"][-(window * 3):]:
        counts[c["tool"]] = counts.get(c["tool"], 0) + 1
    worst = max(counts.values()) if counts else 0
    return worst >= threshold, worst


def detect_misuse(traj, agent_key):
    agent = AGENTS[agent_key]
    if traj["intent"] == "read_intent":
        for c in traj["calls"]:
            if c["tool"] in agent["write_tools"]:
                return True, c["tool"]
    return False, None


def detect_runaway(traj, agent_key):
    b = AGENTS[agent_key]["budget"]
    breaches = []
    if traj["tokens"] > b["tokens"]:
        breaches.append(("tokens", traj["tokens"], b["tokens"]))
    if traj["dollars"] > b["dollars"]:
        breaches.append(("dollars", traj["dollars"], b["dollars"]))
    if traj["wall_seconds"] > b["wall_seconds"]:
        breaches.append(("wall_seconds", traj["wall_seconds"], b["wall_seconds"]))
    if traj["tool_calls"] > b["tool_calls"]:
        breaches.append(("tool_calls", traj["tool_calls"], b["tool_calls"]))
    return (len(breaches) > 0, breaches)


def detect_schema_drift(traj):
    return (not traj["schema_ok_overall"]), [c for c in traj["calls"] if not c["schema_ok"]]


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

st.set_page_config(page_title="Agent Reliability & Tool-Use Observability", layout="wide")
st.title("Agent Reliability & Tool-Use Observability")
st.caption("Project 04 · BFSI · AI Platform · Sr PM portfolio — Vijay Saharan")

with st.sidebar:
    st.header("Loops")
    st.markdown("**Observe -> Contain -> Replay**")
    agent_choice = st.selectbox("Agent", list(AGENTS.keys()), format_func=lambda k: AGENTS[k]["label"])
    inject = st.selectbox("Inject failure mode", ["none", "loop", "misuse", "runaway", "schema_drift"])
    st.divider()
    st.caption("Synthetic trajectory stream. Four-dim budgets per agent.")

agent = AGENTS[agent_choice]

# Show budget
st.markdown(f"### Agent: {agent['label']}  ·  `{agent_choice}`")
st.dataframe(pd.DataFrame([agent["budget"]]).rename(index={0: "budget"}), use_container_width=True)

# Loop 1 — Observe
st.markdown("### Loop 1 - Observe (trajectory + classifiers)")

if st.button("Capture trajectory"):
    t = gen_trajectory(agent_choice, inject if inject != "none" else None)
    st.session_state["last_traj"] = t

if "last_traj" not in st.session_state:
    st.info("Click 'Capture trajectory' to generate a synthetic trajectory.")
else:
    t = st.session_state["last_traj"]
    summary = pd.DataFrame([{
        "trajectory_id": t["trajectory_id"],
        "intent": t["intent"],
        "tokens": t["tokens"],
        "dollars": t["dollars"],
        "wall_seconds": t["wall_seconds"],
        "tool_calls": t["tool_calls"],
    }])
    st.dataframe(summary, use_container_width=True)

    # Classifiers
    loop_hit, loop_worst = detect_loop(t)
    misuse_hit, misused = detect_misuse(t, agent_choice)
    runaway_hit, breaches = detect_runaway(t, agent_choice)
    schema_hit, bad_calls = detect_schema_drift(t)

    classifiers = pd.DataFrame([
        {"classifier": "Loop", "hit": loop_hit, "evidence": f"max-tool-repeat={loop_worst}"},
        {"classifier": "Misuse", "hit": misuse_hit, "evidence": f"misused_tool={misused}" if misused else "n/a"},
        {"classifier": "Runaway", "hit": runaway_hit, "evidence": str(breaches) if breaches else "n/a"},
        {"classifier": "Schema drift", "hit": schema_hit, "evidence": f"n_bad_calls={len(bad_calls)}"},
    ])
    st.dataframe(classifiers, use_container_width=True)

    # Loop 2 — Contain
    st.markdown("### Loop 2 - Contain (blast-radius circuit breaker)")
    fired = loop_hit or misuse_hit or runaway_hit or schema_hit
    if fired:
        which = [r for r in ["Loop", "Misuse", "Runaway", "Schema"] if {
            "Loop": loop_hit, "Misuse": misuse_hit, "Runaway": runaway_hit, "Schema": schema_hit
        }[r]]
        st.error(f"CIRCUIT BREAKER FIRED on classifier(s): {', '.join(which)}. Trajectory halted. Use case routed to human queue. Exec notification SLO 4h.")
    else:
        st.success("No classifier hit. Trajectory passed reliability gate.")

    # Loop 3 — Replay
    st.markdown("### Loop 3 - Replay")
    calls_df = pd.DataFrame(t["calls"])
    st.dataframe(calls_df, use_container_width=True)
    st.caption("Replay UI: step through tool calls, intent classifications, schema validations. Diff against canonical trajectory for the same intent.")

    with st.expander("Reliability evidence bundle (auto-assembled)"):
        st.json({
            "agent": agent_choice,
            "trajectory_id": t["trajectory_id"],
            "intent": t["intent"],
            "budget": agent["budget"],
            "classifiers": {
                "loop": loop_hit,
                "misuse": misuse_hit,
                "runaway": runaway_hit,
                "schema_drift": schema_hit,
            },
            "circuit_breaker_fired": fired,
            "audit_trail_event_id": f"evt_agent_{datetime.utcnow().strftime('%Y%m%d')}_0001",
            "evidence_assembled_in_seconds": 0.5,
        })

# Fleet roll-up
st.divider()
st.markdown("### Fleet rollup (synthetic 200-trajectory sample)")
if st.button("Sample fleet"):
    rows = []
    for ak in AGENTS:
        n_clean = 0
        n_loop = n_misuse = n_runaway = n_schema = 0
        for _ in range(200):
            inj = np.random.choice([None, None, None, None, "loop", "misuse", "runaway", "schema_drift"])
            tr = gen_trajectory(ak, inj)
            l, _ = detect_loop(tr)
            m, _ = detect_misuse(tr, ak)
            r, _ = detect_runaway(tr, ak)
            s, _ = detect_schema_drift(tr)
            if not (l or m or r or s):
                n_clean += 1
            n_loop += int(l)
            n_misuse += int(m)
            n_runaway += int(r)
            n_schema += int(s)
        rows.append({
            "agent": ak, "n": 200, "clean": n_clean,
            "loop": n_loop, "misuse": n_misuse, "runaway": n_runaway, "schema_drift": n_schema,
            "reliability_pct": round(n_clean / 200 * 100, 1),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

st.divider()
st.caption(
    "Prototype demonstrates the product mechanic. In production: trajectory capture "
    "via OpenTelemetry, intent classifier as a small SLM, schema sentinel against "
    "API gateway contracts. Interlocks with Project 06 (inference economics) and "
    "Project 08 (audit trail)."
)
