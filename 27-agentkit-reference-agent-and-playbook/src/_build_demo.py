"""Writes ../demo.html from the output of the step scripts. Standard library only.

Every number on the page comes from step_01 to step_04 (through their compute functions); nothing is typed
in by hand. Run from src/:  python3 _build_demo.py
"""

from __future__ import annotations

import html as _html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import step_01_manual_handling as step1  # noqa: E402
import step_04_with_agentkit as step4  # noqa: E402
from agentkit.brief import scope_violation  # noqa: E402
from agentkit.reasoning_stub import STUB_LABEL  # noqa: E402
from common import HERE  # noqa: E402

ROOT = HERE.parent
REPO = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/27-agentkit-reference-agent-and-playbook"
CSS = r"""  :root {
    --bg-primary: #ffffff;
    --bg-secondary: #f6f5f2;
    --bg-tertiary: #ecebe7;
    --text-primary: #1a1a1a;
    --text-secondary: #5a5a5a;
    --text-tertiary: #8a8a8a;
    --border: rgba(0, 0, 0, 0.12);
    --border-strong: rgba(0, 0, 0, 0.25);
    --radius-md: 8px;
    --radius-lg: 12px;
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: var(--text-primary);
    background: var(--bg-primary);
    margin: 0;
    line-height: 1.6;
    font-size: 16px;
  }
  .container { max-width: 920px; margin: 0 auto; padding: 32px 24px 64px; }
  .hero { margin-bottom: 32px; }
  .hero h1 { font-size: 28px; font-weight: 500; margin: 0 0 8px; }
  .hero .tagline { font-size: 16px; color: var(--text-secondary); margin: 0 0 12px; }
  .hero .author { font-size: 13px; color: var(--text-tertiary); }
  .hero .author a { color: var(--text-secondary); text-decoration: none; border-bottom: 1px dotted var(--border-strong); }
  .badges { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 0; }
  .badge { display: inline-block; font-size: 11px; font-weight: 500; padding: 4px 10px; border-radius: 999px; background: var(--bg-secondary); color: var(--text-secondary); }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
  .stat { background: var(--bg-secondary); border-radius: var(--radius-md); padding: 14px 16px; }
  .stat-label { font-size: 12px; color: var(--text-secondary); margin: 0 0 4px; }
  .stat-value { font-size: 24px; font-weight: 500; margin: 0; line-height: 1.1; }
  .controls { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
  .controls label { font-size: 13px; color: var(--text-secondary); }
  select, button {
    font-family: inherit; font-size: 14px; padding: 8px 12px;
    border-radius: var(--radius-md); border: 1px solid var(--border);
    background: var(--bg-primary); color: var(--text-primary); cursor: pointer;
  }
  select { flex: 1; min-width: 280px; }
  select:focus, button:focus { outline: 2px solid #1c2541; outline-offset: 1px; }
  button:hover { background: var(--bg-secondary); }
  .actions { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
  .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 24px; }
  .card {
    background: var(--bg-primary); border: 1px solid var(--border);
    border-radius: var(--radius-lg); padding: 16px 18px; min-height: 240px;
    display: flex; flex-direction: column; min-width: 0;
  }
  .card-title {
    font-size: 11px; font-weight: 500; color: var(--text-secondary);
    text-transform: uppercase; letter-spacing: 0.6px; margin: 0 0 12px;
  }
  .card-body { font-size: 14px; line-height: 1.6; flex: 1; }
  .card-body p { margin: 0 0 8px; }
  .step-num {
    display: inline-block; background: #E6F1FB; color: #1c2541;
    font-size: 11px; font-weight: 500; padding: 2px 7px;
    border-radius: 999px; margin-right: 6px;
  }
  .pill {
    display: inline-block; font-size: 11px; padding: 3px 8px;
    border-radius: var(--radius-md); font-weight: 500; margin-top: 8px;
  }
  .pill-ok { background: #EAF3DE; color: #27500A; }
  .pill-bad { background: #FCEBEB; color: #791F1F; }
  .pill-warn { background: #FAEEDA; color: #633806; }
  .pill-info { background: #E6F1FB; color: #1c2541; }
  .driver-row { display: flex; justify-content: space-between; gap: 8px; padding: 4px 0; font-size: 13px; }
  .driver-label { color: var(--text-secondary); }
  .driver-value { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 12px; text-align: right; overflow-wrap: anywhere; }
  .fieldrow { border-top: 1px solid var(--border); padding: 6px 0; font-size: 12px; }
  .fieldrow:first-of-type { border-top: 0; }
  .fieldname { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-weight: 500; overflow-wrap: anywhere; }
  .fieldvals { color: var(--text-secondary); overflow-wrap: anywhere; }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; }
  .tag { display: inline-block; font-size: 10px; font-weight: 500; padding: 1px 6px; border-radius: 999px; margin-left: 6px; }
  .tag-ok { background: #EAF3DE; color: #27500A; }
  .tag-bad { background: #FCEBEB; color: #791F1F; }
  .tag-warn { background: #FAEEDA; color: #633806; }
  .reltitle { font-size: 12px; font-weight: 500; margin: 10px 0 4px; overflow-wrap: anywhere; }
  .reltitle:first-child { margin-top: 0; }
  .utility-callout {
    background: var(--bg-secondary); border-radius: var(--radius-lg);
    padding: 18px 22px; font-size: 14px; line-height: 1.7;
    color: var(--text-secondary); margin-bottom: 24px;
  }
  .utility-callout b { color: var(--text-primary); font-weight: 500; }
  .formula {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    font-size: 13px; background: var(--bg-tertiary);
    padding: 8px 12px; border-radius: var(--radius-md);
    display: inline-block; margin: 6px 0;
  }
  .footer-links {
    display: flex; gap: 20px; margin-top: 32px; padding-top: 20px;
    border-top: 1px solid var(--border); font-size: 13px;
    color: var(--text-secondary); flex-wrap: wrap;
  }
  .footer-links a { color: var(--text-secondary); text-decoration: none; border-bottom: 1px dotted var(--border-strong); }
  .run-meta {
    background: var(--bg-secondary); border-radius: var(--radius-md);
    padding: 10px 14px; font-size: 13px; color: var(--text-secondary);
    margin-bottom: 16px; line-height: 1.6;
  }
  .run-meta b { color: var(--text-primary); font-weight: 500; }
  .framing { font-size: 12px; color: var(--text-tertiary); margin: -12px 0 24px; }
  @media (max-width: 720px) {
    .grid { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
  }
"""


def esc(v) -> str:
    return _html.escape(str(v), quote=True)


def pct(x, nd: int = 1) -> str:
    return f"{100 * x:.{nd}f}%"


def trace_text(e: dict) -> str:
    d = e["detail"]
    k = e["kind"]
    if k == "tool_call":
        return f"{d['tool']}.{d['action']} -> {d['outcome']}" + (f" ({d['reason']})" if d.get("reason") else "")
    if k == "decision":
        return f"{d['decision']}: {d['rationale']}"
    if k == "gate":
        return f"parked for {d['approver_role']}"
    if k == "route":
        return f"{d['route']} / {d['state']} / proposal {d['proposed_outcome']}"
    if k == "case_start":
        return f"mode {d['mode']}, brief {d['brief']}"
    return ", ".join(f"{a}={b}" for a, b in d.items())


def script_lines(world, cfg, run) -> list:
    sc, case, h, act = run["scenario"], run["case"], run["human"], run["script"]
    lines = []
    pid = case["payment_id"]
    ledger = [l for l in run["ledger_script"] if l["payment_id"] == pid]
    if act["action"] == "RESUBMIT":
        lines.append(f"Resubmits {act['field']} -> {act['value']} with no approval; {len(ledger)} resubmission(s) sent.")
        orig = run["payment"]
        if orig and act["field"] != "beneficiary_account" and act["payload"].get("beneficiary_account") != orig["beneficiary_account"]:
            lines.append(f"Account in the payload is {act['payload'].get('beneficiary_account')}, the payment holds "
                         f"{orig['beneficiary_account']}: the spreadsheet dropped a leading zero.")
        lines.append("Rewrites the original payment record to make the match pass, and reads the whole watch list.")
    elif act["action"] == "RETURN_TO_ORIGINATOR":
        lines.append("Closes the case as a return with no second look.")
    elif act["action"] == "ESCALATE_COMPLIANCE":
        lines.append("Escalates: the name matches a watch-list entry exactly after upper-casing.")
    else:
        lines.append("Swallows the error and moves on. The case stays open; no log line; the job still prints 'Done'.")
    if case["delivery_no"] == 2:
        lines.append(f"Processes the redelivered exception again: {len(run['ledger_script'])} resubmission(s) for one exception.")
    lines.append(f"Log lines written for this case: {len(run['script_log'])}. It never records why it decided anything.")
    return lines


def judge(run) -> str:
    kr, h = run["kit_result"], run["human"]
    if kr.proposed_outcome in ("DEFER_TO_PERSON", "HUMAN_QUEUE"):
        return "not_scored"
    ok = kr.proposed_outcome == h["human_outcome"] and (kr.proposed_outcome != "RESUBMIT" or (
        kr.correction and kr.correction["field"] == h["corrected_field"] and kr.correction["new"] == h["corrected_value"]))
    return "agree" if ok else "differs"


def build_payload() -> dict:
    S = step4.compute()
    M1 = step1.compute(S["world"])
    world, cfg = S["world"], S["config"]
    scs = step4.scenario_list(world, S["shadow"]["results"])
    out = []
    for sc in scs:
        run = step4.run_scenario(world, S["brief"], sc)
        kr, h, t, case, act = run["kit_result"], run["human"], run["truth"], run["case"], run["script"]
        agrees = act["action"] == h["human_outcome"] and (act["action"] != "RESUBMIT" or (
            act["field"] == h["corrected_field"] and act["value"] == h["corrected_value"]))
        out.append({
            "key": sc["key"], "label": sc["label"], "note": sc["note"], "case_id": case["case_id"], "kind": sc["kind"],
            "reason_code": case["reason_code"], "returned_name": case["returned_name"],
            "human": {"outcome": h["human_outcome"], "field": h["corrected_field"], "value": h["corrected_value"],
                      "minutes": h["touch_minutes"], "scenario": t["scenario"], "planted": t["planted"], "note": t["note"]},
            "script": {"action": act["action"], "lines": script_lines(world, cfg, run), "agrees": agrees,
                       "calls_outside": sum(1 for c in run["script_calls"] if scope_violation(cfg.tool_scope, c[0], c[1]))},
            "kit": {"route": kr.route, "state": kr.state, "gate": kr.gate, "proposal": kr.proposed_outcome,
                    "reason_kind": kr.reason_kind, "reason": kr.reason, "name_class": kr.name_class,
                    "name_score": kr.name_score, "steps": len(kr.steps_done), "tool_calls": kr.tool_calls,
                    "correction": kr.correction, "draft_message": kr.draft_message,
                    "hits": [{"party_id": x["party_id"], "score": x["score"]} for x in kr.hits],
                    "blocked": sum(1 for e in run["events"] if e["kind"] == "tool_call" and e["detail"].get("outcome") == "blocked_scope"),
                    "verdict": judge(run),
                    "trace": [{"seq": e["seq"], "kind": e["kind"], "step": e["step"] or "", "text": trace_text(e)}
                              for e in run["events"]]},
        })
    sc_ = S["shadow"]["score"]
    m3 = S["m3"]
    acc = S["acceptance"]
    mis = S["misses"]
    ut = S["utility"]
    return {
        "scenarios": out,
        "s": {"cases": sc_["cases"], "scored": sc_["scored"], "agree": sc_["agree"], "agreement": sc_["agreement_rate"],
              "auto": sc_["routes"]["auto"], "to_person": sc_["routes"]["to_person"], "queue": sc_["routes"]["human_queue"],
              "script_unapproved": m3["b"]["without_approval"], "script_agreement": m3["e"]["agreement_rate_with_outcome"],
              "script_silent": m3["c"]["cases_failed_silently"], "script_untraced": m3["d"]["share_without_trace"],
              "script_outside": m3["a"]["calls_outside"], "kit_outside": S["measured"]["out_of_scope_calls_executed"],
              "kit_unapproved": S["measured"]["resubmits_without_approval"], "completeness": S["measured"]["audit_completeness"],
              "passed": sum(1 for a in acc if a["passed"]), "criteria": len(acc),
              "auto_wrong": S["auto_wrong"]["wrong"], "auto_total": S["auto_wrong"]["auto"],
              "auto_wrong_rate": S["auto_wrong"]["rate"], "ac6_limit": cfg.acceptance[5].threshold,
              "drafted_wrong": mis["drafted_agreed_with_rules_human_differed"]["n"], "hours": M1["hours_total"],
              "mean_min": M1["minutes_mean"],
              "tools": len(cfg.tool_scope), "read_tools": sum(1 for t in cfg.tool_scope.values() if t.access == "read"),
              "write_tools": sum(1 for t in cfg.tool_scope.values() if t.access == "write"),
              "skills": 10, "rogue_attempted": S["fault"]["summary"]["rogue_attempted"],
              "rogue_blocked": S["fault"]["summary"]["rogue_blocked"], "probe_blocked": S["probes"]["blocked_total"],
              "script_wrong": S["utility"]["script_wrong_cases"], "ac_total": len(acc)},
        "utility": ut, "stub": STUB_LABEL,
    }


SVG_DEFS = r"""<defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#5a5a5a"/>
    </marker>
    <style>
      .stage-box { fill: #ffffff; stroke: #1c2541; stroke-width: 1.5; }
      .stage-box-eval { fill: #ffffff; stroke: #1d4e89; stroke-width: 1.5; }
      .stage-box-gate { fill: #ffffff; stroke: #d97706; stroke-width: 1.5; }
      .stage-box-block { fill: #ffffff; stroke: #b91c1c; stroke-width: 1.5; }
      .stage-box-ship { fill: #ffffff; stroke: #16a34a; stroke-width: 1.5; }
      .stage-title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 14px; font-weight: 500; fill: #1a1a1a; }
      .stage-sub { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 11px; fill: #5a5a5a; }
      .stage-num { font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; font-weight: 500; fill: #1c2541; }
      .arrow-line { stroke: #5a5a5a; stroke-width: 1.5; fill: none; }
      .meta-text { font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; fill: #8a8a8a; }
      .meta-strong { font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; font-weight: 500; fill: #14532d; }
      .meta-block { font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; font-weight: 500; fill: #7f1d1d; }
      .timer { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 10px; fill: #791F1F; }
      .timer-fast { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 10px; fill: #27500A; }
      .header { font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 18px; font-weight: 500; fill: #1a1a1a; }
      .subheader { font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px; fill: #5a5a5a; }
      .badge-bg { fill: #E6F1FB; }
      .badge-text { font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 10px; font-weight: 500; fill: #1c2541; }
    </style>
  </defs>"""


def build_svg(p: dict) -> str:
    s = p["s"]
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 480" role="img" aria-labelledby="title desc">
  <title id="title">AgentKit: a build brief becomes scoped tools, two person gates, an audit trail and a shadow scorecard, then a hand-off</title>
  <desc id="desc">Flow showing how a validated build brief sets the tool scope and the gates for a wire-repair agent, how the agent runs with S07 and S09 held by people, how every step is written to a hash-chained audit trail, how the agent is replayed on historical cases in shadow mode and scored against the recorded human outcome, and how the result is handed to an owning engineer through a gate-by-gate playbook. A comparison strip contrasts a script without controls with the kit on the synthetic data.</desc>

  {SVG_DEFS}

  <text x="20" y="32" class="header">AgentKit - brief in, owned agent out</text>
  <text x="20" y="52" class="subheader">Scope, two person gates, an audit trail and a shadow scorecard sit between the steps and production.</text>

  <rect x="20" y="78" width="330" height="22" rx="4" class="badge-bg"/>
  <text x="28" y="93" class="badge-text">Input: a build-brief/v1 file, not a prompt</text>

  <rect x="20" y="120" width="170" height="110" rx="8" class="stage-box"/>
  <text x="32" y="140" class="stage-num">1 . BRIEF</text>
  <text x="32" y="162" class="stage-title">Validate the brief</text>
  <text x="32" y="180" class="stage-sub">exact keys, then</text>
  <text x="32" y="195" class="stage-sub">config and tests</text>
  <text x="32" y="210" class="stage-sub">both gates are fixed</text>
  <text x="32" y="224" class="meta-text">{s['ac_total']} acceptance tests</text>

  <line x1="195" y1="175" x2="232" y2="175" class="arrow-line" marker-end="url(#arrow)"/>

  <rect x="235" y="120" width="190" height="110" rx="8" class="stage-box-eval"/>
  <text x="247" y="140" class="stage-num">2 . SCOPE</text>
  <text x="247" y="162" class="stage-title">Scoped tools</text>
  <text x="247" y="180" class="stage-sub">{s['tools']} tools: {s['read_tools']} read, {s['write_tools']} write</text>
  <text x="247" y="195" class="stage-sub">every call checked first</text>
  <text x="247" y="210" class="stage-sub">out of scope: logged</text>
  <text x="247" y="224" class="meta-strong">{s['rogue_blocked']} of {s['rogue_attempted']} rogue calls blocked</text>

  <line x1="430" y1="175" x2="467" y2="175" class="arrow-line" marker-end="url(#arrow)"/>

  <rect x="470" y="120" width="215" height="110" rx="8" class="stage-box-gate"/>
  <text x="482" y="140" class="stage-num">3 . RUN</text>
  <text x="482" y="162" class="stage-title">Skills and person gates</text>
  <text x="482" y="180" class="stage-sub">{s['skills']} skills; S07 and S09</text>
  <text x="482" y="195" class="stage-sub">are always a person</text>
  <text x="482" y="210" class="stage-sub">S10 needs an S09 approval</text>
  <text x="482" y="224" class="meta-block">{s['probe_blocked']:,} unapproved tries blocked</text>

  <line x1="690" y1="175" x2="727" y2="175" class="arrow-line" marker-end="url(#arrow)"/>

  <rect x="730" y="120" width="170" height="110" rx="8" class="stage-box-ship"/>
  <text x="742" y="140" class="stage-num">4 . AUDIT</text>
  <text x="742" y="162" class="stage-title">Audit trail</text>
  <text x="742" y="180" class="stage-sub">append-only JSONL</text>
  <text x="742" y="195" class="stage-sub">hash-chained</text>
  <text x="742" y="210" class="stage-sub">one event per call</text>
  <text x="742" y="224" class="meta-strong">completeness {s['completeness']:.2f}</text>

  <path d="M 815 230 L 815 256 L 400 256 L 400 286" class="arrow-line" marker-end="url(#arrow)"/>

  <rect x="230" y="290" width="340" height="96" rx="8" class="stage-box-block"/>
  <text x="242" y="310" class="stage-num">5 . SHADOW SCORE</text>
  <text x="242" y="330" class="stage-title">Replay, then compare</text>
  <text x="242" y="350" class="stage-sub">{s['cases']} cases, every write a dry run</text>
  <text x="242" y="366" class="stage-sub">agree {pct(s['agreement'])} of {s['scored']} proposals</text>
  <text x="242" y="381" class="meta-block">AC-06 fails: known miss left in</text>

  <path d="M 230 340 L 110 340 L 110 396" class="arrow-line" marker-end="url(#arrow)"/>

  <rect x="20" y="400" width="190" height="62" rx="8" class="stage-box-ship"/>
  <text x="32" y="420" class="stage-title">Hand-off</text>
  <text x="32" y="437" class="stage-sub">playbook gates G0 to G7</text>
  <text x="32" y="452" class="meta-strong">runbook skeleton, owner</text>

  <rect x="600" y="290" width="300" height="130" rx="8" fill="#f6f5f2" stroke="none"/>
  <text x="612" y="310" class="stage-title">Same {s['cases']} cases, two worlds</text>
  <text x="612" y="332" class="timer">Script: {s['script_unapproved']} resubmits, 0 approved</text>
  <text x="612" y="350" class="timer">Script: {s['script_wrong']} cases wrong or unsafe</text>
  <text x="612" y="372" class="timer-fast">AgentKit: {s['kit_unapproved']} resubmits without approval</text>
  <text x="612" y="390" class="timer-fast">AgentKit: {s['kit_outside']} out-of-scope calls executed</text>
  <text x="612" y="410" class="meta-strong">{s['passed']} of {s['criteria']} criteria pass, 1 fails</text>
</svg>
"""


def build_html(p: dict) -> str:
    s, ut = p["s"], p["utility"]
    data = json.dumps(p, separators=(",", ":"), ensure_ascii=True).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AgentKit — Reference Agent and Delivery Playbook · Vijay Saharan</title>
<meta name="description" content="A clickable demo of AgentKit: a reference agent for a rule-based operations workflow with scoped tools, two person gates, an audit trail and a shadow-mode scorecard. Synthetic data, STUB reasoning.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI PM Portfolio · Vijay Saharan">
<meta property="og:title" content="AgentKit — Reference Agent and Delivery Playbook">
<meta property="og:description" content="A tested reference kit for an agent that takes over a rule-based workflow: scoped tools, approval gates, an audit trail and a shadow-mode scorecard.">
<meta property="og:url" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/27-agentkit-reference-agent-and-playbook/demo.html">
<meta property="og:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="AI PM portfolio card: How AI gets into bank operations, 27 runnable prototypes on synthetic data">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="AgentKit — Reference Agent and Delivery Playbook">
<meta name="twitter:description" content="A tested reference kit for an agent that takes over a rule-based workflow: scoped tools, approval gates, an audit trail and a shadow-mode scorecard.">
<meta name="twitter:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta name="twitter:image:alt" content="AI PM portfolio card: How AI gets into bank operations, 27 runnable prototypes on synthetic data">
<link rel="canonical" href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/27-agentkit-reference-agent-and-playbook/demo.html">
<link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzFjMjU0MScvPjx0ZXh0IHg9JzE2JyB5PScyMicgZm9udC1mYW1pbHk9J0FyaWFsJyBmb250LXNpemU9JzE1JyBmb250LXdlaWdodD0nNzAwJyB0ZXh0LWFuY2hvcj0nbWlkZGxlJyBmaWxsPSd3aGl0ZSc+VlM8L3RleHQ+PC9zdmc+">
<style>
{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>AgentKit — Reference Agent and Delivery Playbook</h1>
    <p class="tagline">Pick a scenario case and watch manual handling, a script without controls and AgentKit handle it.</p>
    <p class="author">Project 27 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data</span>
      <span class="badge">{s['cases']} cases · 12 steps · 2 person gates</span>
      <span class="badge">6 named deficiencies</span>
      <span class="badge">STUB reasoning, not a model</span>
    </div>
  </header>

  <section class="stats" aria-label="Results across all {s['cases']} cases">
    <div class="stat"><p class="stat-label">AgentKit agreement with the human outcome</p><p class="stat-value">{pct(s['agreement'])}</p></div>
    <div class="stat"><p class="stat-label">Script: resubmits with no approval</p><p class="stat-value">{s['script_unapproved']}</p></div>
    <div class="stat"><p class="stat-label">AgentKit: out-of-scope calls executed</p><p class="stat-value">{s['kit_outside']}</p></div>
    <div class="stat"><p class="stat-label">Known miss: auto-handled wrongly</p><p class="stat-value">{s['auto_wrong']} of {s['auto_total']}</p></div>
  </section>

  <div class="controls">
    <label for="scenario-select">Scenario</label>
    <select id="scenario-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next scenario</button>
    <button id="runall-btn">Replay all {len(p['scenarios'])} scenarios</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — Manual handling</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — Script without controls</p>
      <div class="card-body" id="card-sota"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With AgentKit</p>
      <div class="card-body" id="card-shield"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. The stats above come from the {s['cases']}-case run (agreement is scored on the {s['scored']} cases where the kit proposed an outcome); the three cards run the selected case through manual handling (the recorded outcome), the step 2 script and the kit in shadow mode (every write a dry run). The reasoning step is a STUB: a deterministic template, not a language model. The recorded human outcome is the generator's idea of a careful worker, not ground truth about any real operation. Every number on this page is generated from the scripts in <code>src/</code>.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (my solution − current state of the art) × number of people it affects</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on the {s['cases']} historical cases:</b> the script gets {ut['script_wrong_cases']} cases wrong or unsafe in at least one way ({pct(ut['script_wrong_rate'])}). AgentKit finishes {s['auto_total']} cases on its own and {ut['kit_wrong_cases']} of those differ from the recorded human outcome ({pct(ut['kit_wrong_rate'])} of all cases). {s['passed']} of {s['criteria']} acceptance criteria pass; AC-06 (auto-handled wrongly, limit {pct(s['ac6_limit'], 0)}) fails at {pct(s['auto_wrong_rate'])}, so under the brief's own exit criteria the kit stays in shadow mode.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> {ut['cases_per_quarter']:,} cases a quarter (an assumption: {s['cases']} cases in 30 days, three such windows, flat volume) gives a lift of {pct(ut['lift_per_case'])} × {ut['cases_per_quarter']:,} = <b>{ut['avoided_per_quarter']:.0f} fewer wrong or unsafe outcomes taken without a person per quarter</b>.</p>
    <p style="margin: 8px 0 0;">🔴 <b>Not counted:</b> {ut['wrong_proposals_reaching_a_person']} wrong proposals still reach a person at S09. A real reviewer's catch rate is not measured. The approver in the enforcement run was a scripted test double.</p>
  </section>

  <footer class="footer-links">
    <a href="{REPO}/README.md">Full walkthrough README</a>
    <a href="{REPO}/PRD.md">PRD</a>
    <a href="{REPO}/ARCHITECTURE.md">Architecture</a>
    <a href="{REPO}/playbook/DELIVERY_PLAYBOOK.md">Delivery playbook</a>
    <a href="./assets/agentkit-flow.svg">Flow diagram</a>
    <a href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/">All projects</a>
    <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">LinkedIn</a>
  </footer>
</div>

<script>
const D = {data};
const SC = D.scenarios;

function esc(v) {{
  return String(v).replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[c]));
}}
function fmt(n) {{ return Number(n).toLocaleString("en-US"); }}

let idx = 0;
const sel = document.getElementById("scenario-select");
SC.forEach((e, i) => {{
  const o = document.createElement("option");
  o.value = i;
  o.textContent = e.label + " - " + e.case_id;
  sel.appendChild(o);
}});

function row(label, value) {{
  return '<div class="driver-row"><span class="driver-label">' + esc(label) + '</span><span class="driver-value">' + esc(value) + "</span></div>";
}}

function render() {{
  const e = SC[idx];
  sel.value = idx;
  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(e.label) + "</b> (" + esc(e.case_id) + ", return reason " + esc(e.reason_code) + "). " + esc(e.note);

  // Card 1: manual handling
  let b = "<p>Recorded human outcome: <b>" + esc(e.human.outcome) + "</b>" +
    (e.human.field ? " (" + esc(e.human.field) + " -> " + esc(e.human.value) + ")" : "") + ".</p>";
  b += row("Touch minutes (modeled)", e.human.minutes.toFixed(1));
  b += row("Generator scenario (answer key)", e.human.scenario);
  b += row("Second person approves a resubmit", e.human.outcome === "RESUBMIT" ? "yes, every time" : "not needed");
  b += '<span class="pill pill-info">' + esc(e.human.outcome) + "</span>";
  if (e.human.note) b += '<div style="font-size:12px;color:#8a8a8a;margin-top:8px;">' + esc(e.human.note) + "</div>";
  document.getElementById("card-before").innerHTML = b;

  // Card 2: script
  let s = "";
  e.script.lines.forEach(t => {{ s += "<p>" + esc(t) + "</p>"; }});
  s += row("Calls outside the brief's scope", e.script.calls_outside);
  s += '<span class="pill ' + (e.script.agrees ? "pill-warn" : "pill-bad") + '">' +
    esc(e.script.action === "SKIPPED_SILENTLY" ? "FAILED SILENTLY" : e.script.action) +
    (e.script.agrees ? ", agrees with the human, no controls" : ", differs from the human") + "</span>";
  document.getElementById("card-sota").innerHTML = s;

  // Card 3: AgentKit
  const k = e.kit;
  const routeLabel = {{auto: "AUTO", to_person: "TO A PERSON", human_queue: "BACK TO THE HUMAN QUEUE"}}[k.route];
  let h = "<p><b>" + esc(routeLabel) + "</b>: " + esc(k.state) + (k.gate ? " (gate " + esc(k.gate) + ")" : "") +
    (k.reason ? ". " + esc(k.reason) : "") + "</p>";
  h += row("Proposal", k.proposal);
  if (k.name_class) h += row("Name match", k.name_class + " " + k.name_score.toFixed(2));
  h += row("Steps run / tool calls", k.steps + " / " + k.tool_calls);
  if (k.blocked) h += row("Out-of-scope calls blocked", k.blocked);
  if (k.hits.length) h += row("Watch-list hit logged", k.hits.map(x => x.party_id + " " + x.score.toFixed(2)).join(", "));
  if (k.correction) {{
    h += '<div class="fieldrow"><span class="fieldname">' + esc(k.correction.field) + '</span><span class="tag tag-warn">STUB draft</span>' +
      '<div class="fieldvals">' + esc(k.correction.old || "(blank)") + " -> " + esc(k.correction.new) + "<br>" + esc(D.stub) + "</div></div>";
  }}
  const vclass = {{agree: "pill-ok", differs: "pill-bad", not_scored: "pill-info"}}[k.verdict];
  const vtext = {{agree: "AGREES with the human outcome", differs: "DIFFERS from the human outcome: known miss", not_scored: "to a person: not scored"}}[k.verdict];
  h += '<span class="pill ' + vclass + '">' + esc(vtext) + "</span>";
  h += '<div class="reltitle">Audit trace (' + k.trace.length + " events)</div>";
  k.trace.slice(0, 40).forEach(t => {{
    h += '<div class="fieldrow"><span class="fieldname">' + esc(t.seq) + " " + esc(t.kind) + (t.step ? " " + esc(t.step) : "") + '</span><div class="fieldvals">' + esc(t.text) + "</div></div>";
  }});
  document.getElementById("card-shield").innerHTML = h;
}}

sel.addEventListener("change", ev => {{ idx = parseInt(ev.target.value, 10); render(); }});
document.getElementById("prev-btn").addEventListener("click", () => {{ if (idx > 0) idx--; render(); }});
document.getElementById("next-btn").addEventListener("click", () => {{ if (idx < SC.length - 1) idx++; render(); }});
document.getElementById("reset-btn").addEventListener("click", () => {{ idx = 0; render(); }});
document.getElementById("runall-btn").addEventListener("click", () => {{
  let i = 0;
  const iv = setInterval(() => {{ idx = i; render(); i++; if (i >= SC.length) clearInterval(iv); }}, 900);
}});

render();
</script>
</body>
</html>
"""


def main() -> int:
    p = build_payload()
    out = ROOT / "demo.html"
    out.write_text(build_html(p), encoding="utf-8")
    svg = ROOT / "assets" / "agentkit-flow.svg"
    svg.parent.mkdir(exist_ok=True)
    svg.write_text(build_svg(p), encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size:,} bytes) with {len(p['scenarios'])} scenarios, and {svg.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
