"""Hand-off helpers: a runbook skeleton drafted from the brief, monitoring signals computed from the audit
trace, and the rollout exit criteria checked against the acceptance results.

The runbook this writes is a SKELETON. It carries what the brief already knows (the kill switch text, the
gates, the scope) and leaves the steps an operator will actually follow marked TO WRITE. Nobody has run it.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .brief import WorkflowConfig

_ID = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*:\s*(.+)$")
_AC = re.compile(r"AC-\d+")


def split_id(item: str):
    m = _ID.match(item)
    return (m.group(1), m.group(2).strip()) if m else (item.strip(), "")


def monitoring_signals(config: WorkflowConfig, events: List[dict], results: List, killswitch=None,
                       agreement: Optional[float] = None) -> Dict[str, dict]:
    """Compute each monitoring signal the brief names. A signal this module cannot compute is reported as not computable."""
    calls = [e for e in events if e["kind"] == "tool_call"]
    bad = [e for e in calls if e["detail"].get("outcome") in ("timeout", "malformed", "not_found", "error")]
    first = [r for r in results if not r.redelivery]
    parked = [r for r in first if r.state.startswith("WAITING_")]
    queued = [r for r in first if r.route == "human_queue"]
    computed = {
        "gate_queue_depth": len(parked),
        "tool_error_rate": round(len(bad) / len(calls), 4) if calls else 0.0,
        "queue_return_rate": round(len(queued) / len(first), 4) if first else 0.0,
        "scope_block_count": sum(1 for e in calls if e["detail"].get("outcome") == "blocked_scope"),
        "kill_switch_state": ("engaged" if killswitch is not None and killswitch.engaged else "released"),
        "agreement_rate": agreement,
    }
    out = {}
    for item in config.monitoring:
        sid, desc = split_id(item)
        out[sid] = {"description": desc, "value": computed.get(sid), "computable": sid in computed and
                    computed.get(sid) is not None}
    return out


def exit_status(config: WorkflowConfig, acceptance_results: List[dict]) -> List[dict]:
    """For each rollout exit criterion, the acceptance tests it names and whether they pass on the data in hand.

    A criterion that names tests measured only in shadow mode is evaluated; one that needs live data
    (a weekly sample, 30 days) is reported as not evaluable here.
    """
    by_id = {r["id"]: r for r in acceptance_results}
    out = []
    for crit in config.exit_criteria:
        refs = sorted(set(_AC.findall(crit)))
        if re.search(r"AC-\d+ to AC-\d+", crit):
            m = re.search(r"AC-(\d+) to AC-(\d+)", crit)
            refs = [f"AC-{i:02d}" for i in range(int(m.group(1)), int(m.group(2)) + 1)]
        live = crit.startswith(("limited rollout", "full rollout"))
        if live or not refs:
            out.append({"criterion": crit, "refs": refs, "status": "not_evaluable_here",
                        "failing": []})
            continue
        failing = [r for r in refs if r in by_id and not by_id[r]["passed"]]
        if re.search(r"AC-\d+ to AC-\d+", crit):
            status = "measured" if not failing else "measured_with_failures"
        else:
            status = "pass" if not failing else "fail"
        out.append({"criterion": crit, "refs": refs, "status": status, "failing": failing})
    return out


_RUNBOOK_BODY = {
    "RB-01": ("Trigger: an operator sees wrong or unexpected agent behavior, a scope block burst, or a downstream "
              "incident.", "Engage the switch; confirm no new tool calls in the audit trace; confirm open cases "
              "appear in the human queue.", "Release is a second recorded action by a different person than the one "
              "who engaged it (design; not enforced in the prototype)."),
    "RB-02": ("Trigger: a question about one case, a complaint, or a review.", "Filter the JSONL trace by case_id; "
              "read case_start, each decision, each tool_call, the gate and the route; verify the hash chain.",
              "TO WRITE: where the trace lives in production and who may read it."),
    "RB-03": ("Trigger: a case arrives in the human queue from the agent.", "Read the route event for the reason "
              "kind (record_invalid, tool_failure, scope_violation, gate_violation, kill_switch, declined).",
              "TO WRITE: the work instruction per reason kind."),
    "RB-04": ("Trigger: tool_error_rate rises or several cases return with tool_failure.", "Check which tool the "
              "retry events name; check the tool's own status page or owner.", "If the failing tool is the "
              "watch-list screen, do not bypass it: cases stay in the human queue until it recovers."),
    "RB-05": ("Trigger: a duplicate delivery is closed by the agent or a redelivery is ignored.", "Confirm the "
              "ledger holds one resubmission for the exception_ref.", "TO WRITE: who is told when the duplicate "
              "rate moves."),
    "RB-06": ("Trigger: a new tool or action is requested.", "Raise a change request; the brief's tools list is the "
              "scope; a code change alone does not widen it.", "TO WRITE: approver for a scope change (see the "
              "permissions review gate in the playbook)."),
    "RB-07": ("Trigger: exit criteria fail in production or the owner decides to stop.", "Engage the kill switch, "
              "drain the gate queues to people, switch the intake back to the human-only process.", "TO WRITE: the "
              "intake switch in the real queue system."),
}


def build_runbook(config: WorkflowConfig) -> str:
    """A skeleton runbook as markdown. One section per runbook item in the brief."""
    lines = [f"# Runbook skeleton: {config.name} ({config.brief_id})", "",
             "Status: SKELETON drafted from the build brief. It has not been run by anyone and is not an",
             "operating procedure. Lines marked TO WRITE are for the owning engineer.", "",
             f"Owner role: {config.owner_role}", "", f"Kill switch (from the brief): {config.kill_switch}", "",
             "Gates (from the brief): " + "; ".join(f"{g.step} -> {g.approver_role}" for g in config.gates.values()),
             ""]
    for item in config.runbook_items:
        sid, title = split_id(item)
        trig, check, act = _RUNBOOK_BODY.get(sid, ("TO WRITE", "TO WRITE", "TO WRITE"))
        lines += [f"## {sid} {title}", "", trig, "", f"Check: {check}", "", f"Action: {act}", ""]
    lines += ["## Monitoring named in the brief", ""]
    for item in config.monitoring:
        sid, desc = split_id(item)
        lines.append(f"- `{sid}`: {desc}")
    lines.append("")
    return "\n".join(lines)
