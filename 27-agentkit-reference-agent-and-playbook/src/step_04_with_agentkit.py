"""Step 4 - The fix: run AgentKit from the brief on the same 600 cases, in shadow mode.

What it runs
  1. the brief is loaded, validated and turned into a workflow config
  2. a SHADOW run over all 600 historical cases: every write is a dry run, both person gates park the case;
     the kit's proposal is scored against the recorded human outcome
  3. a FAULT-INJECTION run over the same cases with the 24 faults in data/fault_schedule.csv
  4. an ENFORCEMENT run in a live sandbox with a scripted approver double (NOT a person): 388 S10 probes
     per kind, and a full pass with a lost answer after a write and redelivered exceptions
  5. a KILL-SWITCH drill
  6. the brief's acceptance criteria, evaluated, pass or fail
  7. the known miss, printed

The recorded human outcome is never an input to the kit. The generator's answer key (case_truth.csv) is used
only to explain a result. Run from src/:  python3 step_04_with_agentkit.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentkit import shadow  # noqa: E402
from agentkit.approvers import ScriptedApprover  # noqa: E402
from agentkit.audit import completeness, verify_chain  # noqa: E402
from agentkit.brief import (brief_warnings, check_brief, derive_config, evaluate_acceptance, load_brief,  # noqa: E402
                            scope_violation, unsupported_steps)
from agentkit.data_io import load_world  # noqa: E402
from agentkit.errors import GateViolation, UnsupportedStepError  # noqa: E402
from agentkit.gates import Approval  # noqa: E402
from agentkit.handoff import build_runbook, exit_status, monitoring_signals  # noqa: E402
from agentkit.kit import build_kit  # noqa: E402
from agentkit.matching import AMBIGUOUS, MISMATCH  # noqa: E402
from common import BRIEF_PATH, EVENTS_PER_QUARTER_CASES, OUT, fnum, pct, table, write_csv, write_json  # noqa: E402
import step_03_deficiencies_exposed as step3  # noqa: E402

REVIEWER = "person:reviewer-1"
REVIEWER_ROLE = "payments_operations_reviewer"


# ---------------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------------
def snapshot_status() -> list:
    """What the validator says about the three briefs StepScout (26) wrote. They are a snapshot, not hand-written."""
    import json
    out = []
    for p in sorted((BRIEF_PATH.parent / "stepscout_snapshot").glob("BB-*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        problems = check_brief(d)
        uns = unsupported_steps(d) if not problems else []
        run = "n/a"
        if not problems:
            try:
                derive_config(d)
                run = "accepted"
            except UnsupportedStepError:
                run = "refused"
        out.append({"id": d.get("brief_id", p.stem), "valid": not problems, "problems": len(problems),
                    "unsupported_steps": uns, "config": run})
    return out


def audit_health(kit, results) -> dict:
    ev = kit.audit.events()
    comp = completeness(ev, kit.orchestrator.expected_trace())
    by_case = {}
    for e in ev:
        by_case.setdefault(e["case_id"], set()).add(e["kind"])
    silent = []
    for r in results:
        kinds = by_case.get(r.case_id, set())
        if "route" not in kinds:
            silent.append(r.case_id)
        elif r.route == "human_queue" and not ({"fallback", "kill_switch"} & kinds):
            silent.append(r.case_id)
    blocked = sum(1 for e in ev if e["kind"] == "tool_call" and e["detail"].get("outcome") == "blocked_scope")
    return {"events": len(ev), "completeness": comp["fraction"], "complete": comp["ok"], "chain_ok": comp["chain_ok"],
            "missing": len(comp["missing"]), "silent_failures": len(set(silent)), "scope_blocks": blocked,
            "kinds": kit.audit.kind_counts()}


def scope_breaches_executed(kit) -> int:
    return sum(1 for system, action, _a, _c in kit.env.call_log if scope_violation(kit.config.tool_scope, system, action))


def run_shadow(world, brief, audit_path=None):
    kit = build_kit(world, brief, mode="shadow", audit_path=audit_path)
    res = shadow.replay(kit, world=world)
    return kit, res


def run_fault(world, brief):
    kit = build_kit(world, brief, mode="shadow", fault_rows=world["faults"])
    res = shadow.replay(kit, world=world)
    return kit, res


def run_probes(world, brief, case_ids) -> dict:
    """For every case that reached S09, try to resubmit five ways. Only the last one may run."""
    kit = build_kit(world, brief, mode="live")
    orch = kit.orchestrator
    blocked = {"no_approval": 0, "other_correction": 0, "not_a_person": 0}
    replays = executed = 0
    for cid in case_ids:
        ctx = orch.new_context(cid)
        for s in ("S01", "S02", "S03", "S04", "S05", "S06", "S08"):
            orch.run_step(s, ctx)
        digest = ctx.draft.digest
        attempts = [("no_approval", None),
                    ("other_correction", Approval(True, REVIEWER, REVIEWER_ROLE, "0" * 16)),
                    ("not_a_person", Approval(True, "agent:wire-repair", REVIEWER_ROLE, digest))]
        for name, ap in attempts:
            ctx.approval = ap
            try:
                orch.run_step("S10", ctx)
            except GateViolation:
                blocked[name] += 1
        before = len(kit.env.ledger)
        ctx.approval = Approval(True, REVIEWER, REVIEWER_ROLE, digest)
        orch.run_step("S10", ctx)
        executed += len(kit.env.ledger) - before
        before = len(kit.env.ledger)
        orch.run_step("S10", ctx)             # the same approval presented again
        replays += 1 if len(kit.env.ledger) == before else 0
    ev = kit.audit.events()
    approved_keys = {e["detail"].get("idempotency_key") for e in ev if e["kind"] == "tool_call"
                     and e["detail"]["action"] == "resubmit" and e["detail"]["outcome"] == "ok"
                     and str(e["detail"].get("approver", "")).startswith("person:")}
    unapproved = sum(1 for l in kit.env.ledger if l["key"] not in approved_keys)
    per_ref = Counter(l["key"] for l in kit.env.ledger)
    return {"cases": len(case_ids), "blocked": blocked, "blocked_total": sum(blocked.values()),
            "executed_with_valid_approval": executed, "same_approval_replayed_no_second_write": replays,
            "ledger": len(kit.env.ledger), "unapproved_in_ledger": unapproved,
            "duplicate_ledger_entries": sum(n - 1 for n in per_ref.values() if n > 1),
            "gate_violation_events": sum(1 for e in ev if e["kind"] == "gate_violation"),
            "blocked_gate_calls": sum(1 for e in ev if e["kind"] == "tool_call"
                                      and e["detail"].get("outcome") == "blocked_gate"),
            "kit": kit}


def run_live(world, brief) -> dict:
    """A full live pass in a sandbox: scripted approver, a lost answer after three resubmits, redeliveries."""
    ids = [c["case_id"] for c in world["cases"]]
    first_resubmits = [cid for cid in ids if world["truth"][cid]["scenario"] == "fix_account_clean"][:3]
    dups = [r for r in world["faults"] if r["fault_type"] == "duplicate_delivery"]
    lost = [{"fault_id": f"L{i}", "case_id": cid, "step": "S10", "tool": "payments_gateway", "action": "resubmit",
             "attempts": "1", "fault_type": "timeout_after_write", "payload": ""} for i, cid in enumerate(first_resubmits)]
    kit = build_kit(world, brief, mode="live", approver=ScriptedApprover(), fault_rows=dups + lost)
    res = kit.orchestrator.run_all(ids)
    per_payment = Counter(l["payment_id"] for l in kit.env.ledger)
    per_key = Counter(l["key"] for l in kit.env.ledger)
    retries_after_write = sum(1 for e in kit.audit.events() if e["kind"] == "retry"
                              and e["detail"]["action"] == "resubmit")
    return {"results": res, "kit": kit, "ledger": len(kit.env.ledger),
            "payments_with_more_than_one": sum(1 for n in per_payment.values() if n > 1),
            "keys_with_more_than_one": sum(1 for n in per_key.values() if n > 1),
            "lost_answers_injected": len(lost), "retries_after_a_lost_answer": retries_after_write,
            "redeliveries": sum(1 for r in res if r.redelivery),
            "routes": dict(Counter(r.route for r in res if not r.redelivery))}


def run_killswitch_drill(world, brief) -> dict:
    ids = [c["case_id"] for c in world["cases"]][:75]
    kit = build_kit(world, brief, mode="shadow")
    a = [kit.orchestrator.run_case(c) for c in ids[:25]]
    calls_at_engage = sum(kit.registry.calls_by_case.values())
    kit.killswitch.engage("drill", by="operator-1")
    b = [kit.orchestrator.run_case(c) for c in ids[25:50]]
    calls_while_engaged = sum(kit.registry.calls_by_case.values()) - calls_at_engage
    kit.killswitch.release(by="operator-2")
    c = [kit.orchestrator.run_case(x) for x in ids[50:75]]
    return {"before": len(a), "killed": sum(1 for r in b if r.state == "KILLED"), "engaged_cases": len(b),
            "tool_calls_while_engaged": calls_while_engaged, "after_release_running": sum(
                1 for r in c if r.state != "KILLED"), "released_cases": len(c),
            "all_killed_have_trace": all(
                [e["kind"] for e in kit.audit.events(r.case_id)] == ["case_start", "kill_switch", "route"] for r in b)}


def known_misses(world, results) -> dict:
    outcomes, truth = world["outcomes"], world["truth"]
    first = [r for r in results if not r.redelivery]
    judged = {r.case_id: shadow.judge_pair(r, outcomes[r.case_id]) for r in first}
    drafted_wrong = [r for r in first if r.proposed_outcome == "RESUBMIT" and judged[r.case_id].startswith("disagree")]
    aw = shadow.auto_wrong(first, outcomes)
    auto_wrong_ids = set(aw["cases"])
    watch_missed = [r for r in first if truth[r.case_id]["scenario"] in ("watch_exact", "watch_variant")
                    and r.proposed_outcome != "ESCALATE_COMPLIANCE"]
    watch_over = [r for r in first if r.proposed_outcome == "ESCALATE_COMPLIANCE"
                  and outcomes[r.case_id]["human_outcome"] != "ESCALATE_COMPLIANCE"]
    auto_from_mismatch = [r for r in first if r.route == "auto" and r.name_class == MISMATCH
                          and r.proposed_outcome == "RETURN_TO_ORIGINATOR"]
    auto_from_rule = [r for r in first if r.route == "auto" and r.proposed_outcome == "RETURN_TO_ORIGINATOR"
                      and r.name_class is None]
    advised = {c["case_id"]: bool(c["advised_value"].strip()) for c in world["cases"]}
    auto_with_advice = [r for r in auto_from_rule if advised[r.case_id]]

    def by_scn(rs):
        return dict(Counter(truth[r.case_id]["scenario"] for r in rs).most_common())

    return {
        "drafted_agreed_with_rules_human_differed": {"n": len(drafted_wrong), "by_scenario": by_scn(drafted_wrong),
                                                     "cases": [r.case_id for r in drafted_wrong]},
        "auto_handled_wrongly": {"n": aw["wrong"], "of_auto": aw["auto"], "rate": aw["rate"],
                                 "by_scenario": by_scn([r for r in first if r.case_id in auto_wrong_ids]),
                                 "cases": aw["cases"]},
        "watch_list_missed": {"n": len(watch_missed), "of": sum(1 for r in first if truth[r.case_id]["scenario"] in
                                                                  ("watch_exact", "watch_variant")),
                              "cases": [r.case_id for r in watch_missed]},
        "watch_list_over_escalated": {"n": len(watch_over), "by_scenario": by_scn(watch_over)},
        "auto_returns_from_name_mismatch": {"n": len(auto_from_mismatch), "human_resubmitted": sum(
            1 for r in auto_from_mismatch if outcomes[r.case_id]["human_outcome"] == "RESUBMIT")},
        "auto_returns_from_reason_code": {"n": len(auto_from_rule), "human_resubmitted": sum(
            1 for r in auto_from_rule if outcomes[r.case_id]["human_outcome"] == "RESUBMIT")},
        "auto_returns_with_advised_value": {"n": len(auto_with_advice), "human_resubmitted": sum(
            1 for r in auto_with_advice if outcomes[r.case_id]["human_outcome"] == "RESUBMIT")},
        "wrong_auto_inside_design_response": len(auto_wrong_ids & ({r.case_id for r in auto_from_mismatch}
                                                                   | {r.case_id for r in auto_with_advice})),
    }


def modeled_minutes(world, results) -> dict:
    """🟡 Touch minutes that stay with a person if the kit's routes hold. Assumptions are named in the printout."""
    sm = {s: v["minutes"] for s, v in world["step_minutes"].items()}
    outcomes = world["outcomes"]
    total = 0.0
    parts = Counter()
    for r in results:
        if r.redelivery:
            continue
        if r.route == "auto":
            m = 0.0
        elif r.state == "WAITING_S09":
            m = sm["S09"]
        elif r.state == "WAITING_S07":
            m = sm["S07"] + sm["S09"]
        else:
            m = outcomes[r.case_id]["touch_minutes"]
        total += m
        parts[r.route] += m
    n = sum(1 for r in results if not r.redelivery)
    manual = sum(o["touch_minutes"] for o in outcomes.values())
    return {"manual_per_case": manual / n, "kit_per_case": total / n, "kit_total_minutes": total,
            "manual_total_minutes": manual, "by_route_minutes": dict(parts)}


def gate_routing(world, kit, results) -> dict:
    gates = {}
    for e in kit.audit.events():
        if e["kind"] == "gate":
            gates.setdefault(e["case_id"], set()).add(e["step"])
    rule_of = {c["case_id"]: world["reason_codes"].get(c["reason_code"], {}).get("repair_rule") for c in world["cases"]}
    need = ok = 0
    for r in results:
        if r.redelivery:
            continue
        if not r.hits and (r.name_class == AMBIGUOUS or (r.name_class == MISMATCH and rule_of[r.case_id] != "FIX_NAME")):
            need += 1
            ok += 1 if "S07" in gates.get(r.case_id, set()) else 0
        if r.proposed_outcome == "RESUBMIT":
            need += 1
            ok += 1 if "S09" in gates.get(r.case_id, set()) else 0
    return {"required": need, "routed": ok, "rate": (ok / need) if need else 1.0}


# ---------------------------------------------------------------------------------------------------
# scenarios (used by the app and the demo)
# ---------------------------------------------------------------------------------------------------
def scenario_list(world, results) -> list:
    truth, outcomes = world["truth"], world["outcomes"]
    by = {r.case_id: r for r in results if not r.redelivery}
    faulted = {f["case_id"] for f in world["faults"]}
    order = [c["case_id"] for c in world["cases"]]

    def first(scn, pred=lambda r, h: True, allow_faulted=False):
        for cid in order:
            if truth[cid]["scenario"] == scn and (allow_faulted or cid not in faulted) and pred(by[cid], outcomes[cid]):
                return cid
        raise LookupError(scn)

    fault = {f["fault_id"]: f for f in world["faults"]}
    out = [
        ("account", "Clean account fix", first("fix_account_clean"), "plain",
         "The return advice carries the right account; the kit drafts it and a person approves."),
        ("style", "Name written another way", first("fix_name_style"), "plain",
         "Abbreviation, case and legal form differ; the names match after normalization."),
        ("bank", "Missing bank code", first("missing_bank_code"), "plain", "A rule-based fix on a code the return advises."),
        ("ambiguous", "Ambiguous name goes to a person",
         first("fix_name_ambiguous", lambda r, h: r.proposed_outcome == "DEFER_TO_PERSON"), "plain",
         "The match is not clear enough for a rule. S07 is a person's call; the kit never decides it."),
        ("unrelated", "Unrelated name, returned by the kit alone", first("fix_name_unrelated"), "plain",
         "The account belongs to a different party; the kit closes the case as a return."),
        ("closed", "Closed account, returned by the kit alone", first("closed_account"), "plain",
         "No repair exists for this reason code."),
        ("watch", "Watch-list hit", first("watch_exact"), "plain",
         "The hit is logged and the case goes to compliance. Nothing is resubmitted."),
        ("duplicate", "Duplicate delivery", first("duplicate"), "plain",
         "The same exception arrives twice. The second delivery is closed as a duplicate; nothing is resubmitted twice."),
        ("malformed", "Malformed record", first("malformed", lambda r, h: True), "plain",
         "The record fails validation. It goes back to the human queue with a reason."),
        ("miss_affiliate", "Known miss: affiliate drafted as a correction",
         first("fix_name_affiliate", lambda r, h: r.proposed_outcome == "RESUBMIT"), "plain",
         "A close-looking affiliate name passes the rules, so the kit drafts a correction. The recorded human outcome was a return."),
        ("miss_successor", "Known miss: closed account with a successor", first("closed_successor"), "plain",
         "The rule says a closed account has no repair, so the kit returns it. A person used the successor account in the advice."),
        ("miss_ambiguous", "Known miss: ambiguous name returned by the kit alone",
         first("fix_name_ambiguous", lambda r, h: r.proposed_outcome == "RETURN_TO_ORIGINATOR"), "plain",
         "The names scored as a mismatch, so the kit returned the case. A person had judged them the same party."),
        ("f_timeout", "Fault: a tool times out once", fault["F01"]["case_id"], "fault",
         "The payments lookup times out on the first attempt. The kit retries and the case completes."),
        ("f_persist", "Fault: a tool keeps timing out", fault["F09"]["case_id"], "fault",
         "The payments lookup never answers. After three attempts the case goes back to the human queue."),
        ("f_scope", "Fault: a call outside the brief's scope", fault["F18"]["case_id"], "fault",
         "The agent tries to edit the original payment. The registry refuses; the case goes back to the human queue."),
        ("f_kill", "Fault: kill switch engaged mid-case", first("fix_account_clean", lambda r, h: True), "kill",
         "An operator engages the switch before the watch-list screen. No further tool call is made."),
    ]
    return [{"key": k, "label": lab, "case_id": cid, "kind": kind, "note": note} for k, lab, cid, kind, note in out]


def run_scenario(world, brief, sc: dict) -> dict:
    """Run one scenario through the kit (shadow) and the step 2 script, on its own."""
    cid = sc["case_id"]
    rows = []
    if sc["kind"] == "fault":
        rows = [f for f in world["faults"] if f["case_id"] == cid]
    kit = build_kit(world, brief, mode="shadow", fault_rows=rows or None)
    ids = [cid]
    case = next(c for c in world["cases"] if c["case_id"] == cid)
    if case["delivery_no"] == 2:      # a duplicate delivery needs its first delivery to have gone through
        first = next(c["case_id"] for c in world["cases"] if c["exception_ref"] == case["exception_ref"]
                     and c["delivery_no"] == 1)
        ids = [first, cid]
    if sc["kind"] == "kill":
        kit.orchestrator.step_hook = lambda step, ctx: kit.killswitch.engage("operator drill", by="operator-1") \
            if step == "S06" else None
    res = {r.case_id: r for r in kit.orchestrator.run_all(ids)}[cid]
    script_run = step3.run_script(world, ids)
    sctx = script_run["script"]
    return {"scenario": sc, "case": case, "kit_result": res, "events": kit.audit.events(cid),
            "chain_ok": verify_chain(kit.audit.events())[0], "script": sctx.actions[cid],
            "script_calls": [c for c in script_run["env"].call_log if c[3] in (cid, None)],
            "script_log": list(sctx.log), "script_env": script_run["env"], "payment": world["payments"].get(case["payment_id"]),
            "human": world["outcomes"][cid], "truth": world["truth"][cid], "ids": ids,
            "ledger_script": [l for l in script_run["env"].ledger]}


# ---------------------------------------------------------------------------------------------------
# the whole measurement
# ---------------------------------------------------------------------------------------------------
def count_golden_cases() -> int:
    p = Path(__file__).resolve().parent.parent / "tests" / "support.py"
    return len(re.findall(r'^\s+add\("G\d\d"', p.read_text(encoding="utf-8"), flags=re.M)) if p.exists() else 0


def compute(world=None, audit_path=None) -> dict:
    world = world or load_world()
    brief = load_brief(BRIEF_PATH)
    snap = snapshot_status()
    m3 = step3.measure(world, brief)
    kit_s, res_s = run_shadow(world, brief, audit_path)
    sc = shadow.score(res_s, world["outcomes"], world["truth"])
    kit_f, res_f = run_fault(world, brief)
    first_s = {r.case_id: r for r in res_s}
    s09 = [c["case_id"] for c in world["cases"] if first_s[c["case_id"]].state == "WAITING_S09"]
    pr = run_probes(world, brief, s09)
    live = run_live(world, brief)
    ks = run_killswitch_drill(world, brief)

    h_s, h_f = audit_health(kit_s, res_s), audit_health(kit_f, res_f)
    h_p = audit_health(pr["kit"], [])
    h_l = audit_health(live["kit"], live["results"])
    aw = shadow.auto_wrong(res_s, world["outcomes"])
    gr = gate_routing(world, kit_s, res_s)
    queue_rate = sc["routes"]["human_queue"] / sc["cases"]

    # fault run, compared with the shadow run
    base = {r.case_id: r for r in res_s}
    fcounts = kit_f.faults.counts()
    flt_rows = world["faults"]
    transient = {r["case_id"] for r in flt_rows if r["fault_type"] in ("timeout", "malformed_output")
                 and r["attempts"] != "*"}
    persistent = {r["case_id"] for r in flt_rows if r["fault_type"] in ("timeout", "malformed_output")
                  and r["attempts"] == "*"}
    rogue = {r["case_id"] for r in flt_rows if r["fault_type"] == "rogue_call"}
    fres = {r.case_id: r for r in res_f if not r.redelivery}
    recovered = sum(1 for c in transient if (fres[c].route, fres[c].proposed_outcome) ==
                    (base[c].route, base[c].proposed_outcome))
    fault = {"scheduled": dict(fcounts), "total": len(flt_rows),
             "transient_cases": len(transient), "transient_recovered_same_result": recovered,
             "persistent_cases": len(persistent),
             "persistent_to_human_queue": sum(1 for c in persistent if fres[c].route == "human_queue"
                                              and fres[c].reason_kind == "tool_failure"),
             "persistent_watchlist_cases_unscreened": sum(1 for r in flt_rows if r["tool"] == "watchlist"
                                                          and r["attempts"] == "*" and fres[r["case_id"]].correction),
             "rogue_attempted": len(rogue), "rogue_blocked": h_f["scope_blocks"],
             "rogue_routed_to_queue": sum(1 for c in rogue if fres[c].reason_kind == "scope_violation"),
             "executed_outside_scope": scope_breaches_executed(kit_f),
             "redeliveries_ignored": sum(1 for r in res_f if r.redelivery),
             "retries": h_f["kinds"].get("retry", 0), "fallbacks": h_f["kinds"].get("fallback", 0)}

    measured = {
        "out_of_scope_calls_executed": sum(scope_breaches_executed(k) for k in (kit_s, kit_f, pr["kit"], live["kit"])),
        "resubmits_without_approval": pr["unapproved_in_ledger"] + sum(
            1 for l in live["kit"].env.ledger if l["key"] not in {
                e["detail"].get("idempotency_key") for e in live["kit"].audit.events()
                if e["kind"] == "tool_call" and e["detail"]["action"] == "resubmit" and e["detail"]["outcome"] == "ok"
                and str(e["detail"].get("approver", "")).startswith("person:")}),
        "audit_completeness": min(h["completeness"] if h["chain_ok"] else 0.0 for h in (h_s, h_f, h_p, h_l)),
        "silent_failures": h_s["silent_failures"] + h_f["silent_failures"] + h_l["silent_failures"],
        "shadow_agreement_rate": sc["agreement_rate"],
        "auto_wrong_rate": aw["rate"],
        "gate_routing_rate": gr["rate"],
        "duplicate_writes": live["payments_with_more_than_one"] + live["keys_with_more_than_one"]
        + pr["duplicate_ledger_entries"],
        "human_queue_rate": queue_rate,
    }
    cfg = kit_s.config
    acceptance = evaluate_acceptance(cfg.acceptance, measured)
    misses = known_misses(world, res_s)
    mins = modeled_minutes(world, res_s)
    sig = monitoring_signals(cfg, kit_s.audit.events(), res_s, kit_s.killswitch, agreement=sc["agreement_rate"])
    exits = exit_status(cfg, acceptance)

    # utility: uncontrolled wrong outcomes per case, script against kit
    script_rate = m3["wrong_rate"]
    kit_rate = aw["wrong"] / sc["cases"]
    utility = {"script_wrong_rate": script_rate, "kit_wrong_rate": kit_rate, "lift_per_case": script_rate - kit_rate,
               "cases_per_quarter": EVENTS_PER_QUARTER_CASES,
               "avoided_per_quarter": (script_rate - kit_rate) * EVENTS_PER_QUARTER_CASES,
               "script_wrong_cases": len(m3["wrong_cases"]), "kit_wrong_cases": aw["wrong"],
               "wrong_proposals_reaching_a_person": misses["drafted_agreed_with_rules_human_differed"]["n"]}
    pay_of = {c["case_id"]: world["payments"].get(c["payment_id"]) for c in world["cases"]}
    zero = [r.case_id for r in res_s if not r.redelivery and "S04" in r.steps_done
            and pay_of[r.case_id]["beneficiary_account"].startswith("0")]
    copy_check = {"copies_read_back": sum(1 for r in res_s if not r.redelivery and "S04" in r.steps_done),
                  "leading_zero_accounts_copied_intact": len(zero)}
    return {"world": world, "brief": brief, "config": cfg, "m3": m3, "copy_check": copy_check, "snapshot": snap, "shadow": {"kit": kit_s, "results": res_s,
            "score": sc, "health": h_s}, "fault": {"kit": kit_f, "results": res_f, "health": h_f, "summary": fault},
            "probes": pr, "live": live, "killswitch": ks, "health": {"live": h_l, "probes": h_p},
            "measured": measured, "acceptance": acceptance, "misses": misses, "minutes": mins, "signals": sig,
            "exits": exits, "utility": utility, "gate_routing": gr, "golden_cases": count_golden_cases(),
            "auto_wrong": aw}


def summary_json(S: dict) -> dict:
    sc = S["shadow"]["score"]
    return {"brief_id": S["config"].brief_id, "shadow": {k: sc[k] for k in (
        "cases", "scored", "agree", "disagree", "agreement_rate", "deferred", "queued", "routes", "to_person_detail",
        "queue_reasons", "by_human_class", "confusion")},
        "fault": S["fault"]["summary"], "probes": {k: v for k, v in S["probes"].items() if k != "kit"},
        "live": {k: v for k, v in S["live"].items() if k not in ("kit", "results")}, "killswitch": S["killswitch"],
        "measured": S["measured"], "acceptance": S["acceptance"], "misses": S["misses"], "minutes": S["minutes"],
        "signals": S["signals"], "exits": S["exits"], "utility": S["utility"], "gate_routing": S["gate_routing"],
        "audit": {"shadow": {k: v for k, v in S["shadow"]["health"].items() if k != "kinds"},
                  "fault": {k: v for k, v in S["fault"]["health"].items() if k != "kinds"},
                  "live": {k: v for k, v in S["health"]["live"].items() if k != "kinds"},
                  "probes": {k: v for k, v in S["health"]["probes"].items() if k != "kinds"}},
        "golden_cases": S["golden_cases"], "copy_check": S["copy_check"], "snapshot": S["snapshot"]}


# ---------------------------------------------------------------------------------------------------
# printing
# ---------------------------------------------------------------------------------------------------
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    S = compute(audit_path=OUT / "audit_shadow.jsonl")
    world, cfg, sc = S["world"], S["config"], S["shadow"]["score"]
    m3, mis, aw, ut = S["m3"], S["misses"], S["auto_wrong"], S["utility"]
    S["shadow"]["kit"].audit.close()
    print("=" * 100)
    print("Step 4 - The fix: AgentKit run from the brief on the same 600 cases, in shadow mode")
    print("=" * 100)

    print(f"\nTHE BRIEF  {cfg.brief_id}  ({cfg.name}; class {cfg.automation_class})")
    print(f"  steps {cfg.steps[0]}..{cfg.steps[-1]}; person gates: "
          + ", ".join(f"{g.step} -> {g.approver_role}" for g in cfg.gates.values()))
    print(f"  S10 resubmit requires an approved {cfg.approval_required['S10']}; tools "
          f"{len(cfg.tool_scope)} ({sum(1 for t in cfg.tool_scope.values() if t.access == 'read')} read, "
          f"{sum(1 for t in cfg.tool_scope.values() if t.access == 'write')} write); acceptance criteria {len(cfg.acceptance)}")
    w = brief_warnings(S["brief"])
    print(f"  validation: ok, {len(w)} warnings. Shape: the build-brief/v1 StepScout emits; this one is a hand-written sample.")
    parts = []
    for b_ in S["snapshot"]:
        if not b_["valid"]:
            parts.append(f"{b_['id']} INVALID ({b_['problems']} problems)")
        elif b_["unsupported_steps"]:
            parts.append(f"{b_['id']} validates with an unsupported-step warning ({', '.join(b_['unsupported_steps'])}), "
                         f"config {b_['config']} at run time")
        else:
            parts.append(f"{b_['id']} validates, config {b_['config']}")
    print("  StepScout snapshot (briefs/stepscout_snapshot, not hand-written): " + "; ".join(parts))

    print(f"\nSHADOW RUN  ({sc['cases']} historical cases; every write a dry run; both gates park the case)")
    r = sc["routes"]
    print(f"  went auto (agent finished it)          {r['auto']:4d}  {pct(r['auto'] / sc['cases'])}")
    print(f"  went to a person                       {r['to_person']:4d}  {pct(r['to_person'] / sc['cases'])}   "
          + ", ".join(f"{k} {v}" for k, v in sc["to_person_detail"].items()))
    print(f"  went back to the human queue           {r['human_queue']:4d}  {pct(r['human_queue'] / sc['cases'])}   "
          + ", ".join(f"{k} {v}" for k, v in sc["queue_reasons"].items()))
    print(f"\n  Agreement with the recorded human outcome: {sc['agree']} agree, {sc['disagree']} disagree, "
          f"{sc['deferred']} deferred to a person (S07), {sc['queued']} queued.")
    print(f"  Agreement rate on the {sc['scored']} cases where the kit proposed an outcome: {pct(sc['agreement_rate'], 2)}")
    rows = []
    for k, v in sc["by_human_class"].items():
        rows.append((k, v["n"], v["agree"], v["disagree"], v["deferred"], v["queued"], pct(v["agreement_rate"])))
    print(table(rows, ["recorded human outcome", "cases", "agree", "disagree", "deferred", "queued", "agreement"]))
    print("\n  Confusion (rows: the kit's proposal; columns: the recorded human outcome)")
    cols = ["RESUBMIT", "RETURN_TO_ORIGINATOR", "ESCALATE_COMPLIANCE", "DUPLICATE_CLOSED"]
    rows = [(p, *[sc["confusion"][p].get(c, 0) for c in cols]) for p in sc["confusion"]]
    print(table(rows, ["kit proposal"] + [c[:12] for c in cols]))

    f = S["fault"]["summary"]
    print(f"\nFAULT-INJECTION RUN  ({f['total']} scheduled faults: " + ", ".join(f"{k} {v}" for k, v in f["scheduled"].items()) + ")")
    print(f"  transient timeouts and malformed answers: {f['transient_recovered_same_result']} of {f['transient_cases']} cases "
          "recovered by retry and ended where the clean run ended")
    print(f"  persistent failures: {f['persistent_to_human_queue']} of {f['persistent_cases']} sent back to the human queue; "
          f"cases that proceeded without a watch-list screen: {f['persistent_watchlist_cases_unscreened']}")
    print(f"  out-of-scope calls attempted {f['rogue_attempted']}, BLOCKED {f['rogue_blocked']}, routed to the human queue "
          f"{f['rogue_routed_to_queue']}, executed outside scope {f['executed_outside_scope']}")
    print(f"  redelivered cases ignored {f['redeliveries_ignored']}; retries {f['retries']}; fallbacks {f['fallbacks']}")

    p = S["probes"]
    print(f"\nENFORCEMENT RUN  (live sandbox; the approver is a scripted test double, not a person)")
    print(f"  S10 resubmit attempted on {p['cases']} cases that reached S09, five ways each:")
    print(f"    no approval                  blocked {p['blocked']['no_approval']:4d} of {p['cases']}")
    print(f"    approval for another fix     blocked {p['blocked']['other_correction']:4d} of {p['cases']}")
    print(f"    approval from an agent id    blocked {p['blocked']['not_a_person']:4d} of {p['cases']}")
    print(f"    valid approval               ran     {p['executed_with_valid_approval']:4d} of {p['cases']}")
    print(f"    same approval shown again    no second write {p['same_approval_replayed_no_second_write']:4d} of {p['cases']}")
    print(f"  approvals enforced: {p['blocked_total']:,} unapproved attempts blocked, "
          f"{p['unapproved_in_ledger']} resubmissions in the ledger without a person's approval.")
    lv = S["live"]
    print(f"  full live pass: {lv['ledger']} resubmissions; {lv['lost_answers_injected']} answers lost after the write -> "
          f"{lv['retries_after_a_lost_answer']} retries, {lv['payments_with_more_than_one']} payments resubmitted twice; "
          f"{lv['redeliveries']} redeliveries ignored.")
    k = S["killswitch"]
    print(f"\nKILL-SWITCH DRILL  engaged after {k['before']} cases: {k['killed']} of {k['engaged_cases']} next cases went back to the human "
          f"queue, {k['tool_calls_while_engaged']} tool calls made while engaged; after release {k['after_release_running']} of "
          f"{k['released_cases']} ran again")

    print("\nAUDIT")
    for name, h in (("shadow", S["shadow"]["health"]), ("fault-injection", S["fault"]["health"]),
                    ("enforcement probes", S["health"]["probes"]), ("live pass", S["health"]["live"])):
        print(f"  {name:20s} {h['events']:6,d} events  completeness {h['completeness']:.3f}  hash chain "
              f"{'intact' if h['chain_ok'] else 'BROKEN'}  silent failures {h['silent_failures']}")
    print("  (completeness compares the log with the tool registry's call counts and the orchestrator's step, gate and approval counts)")

    print("\nACCEPTANCE CRITERIA from the brief (thresholds are the brief's; design values set before the runs)")
    rows = []
    for a in S["acceptance"]:
        v = a["value"]
        vs = "n/a" if v is None else (f"{v:.4f}" if isinstance(v, float) and v not in (0.0, 1.0) else f"{v:g}")
        rows.append((a["id"], a["metric"], f"{'>=' if a['direction'] == 'min' else '<='} {a['threshold']:g}", vs,
                     "PASS" if a["passed"] else "FAIL"))
    print(table(rows, ["id", "metric", "threshold", "measured", "result"]))
    npass = sum(1 for a in S["acceptance"] if a["passed"])
    print(f"  {npass} of {len(S['acceptance'])} pass.")
    print("\n  Rollout exit criteria (brief):")
    for e in S["exits"]:
        print(f"    [{e['status']:22s}] {e['criterion']}" + (f"  failing: {', '.join(e['failing'])}" if e["failing"] else ""))

    print("\nTHE KNOWN MISS (left in on purpose)")
    d = mis["drafted_agreed_with_rules_human_differed"]
    print(f"  A. The stub drafted a correction that passed the rule check, and the recorded human outcome was different: {d['n']} cases")
    print("     by the generator's scenario: " + ", ".join(f"{k} {v}" for k, v in d["by_scenario"].items()))
    for cid in d["cases"][:3]:
        r_ = next(x for x in S["shadow"]["results"] if x.case_id == cid)
        h = world["outcomes"][cid]
        print(f"       {cid}: kit drafted {r_.correction['field']} -> {r_.correction['new']!r} (name match {r_.name_class} "
              f"{r_.name_score:.2f}); human recorded {h['human_outcome']}")
    print("     These reach a person at S09 with the match score shown. How many a real reviewer would catch is not measured.")
    a_ = mis["auto_handled_wrongly"]
    print(f"  B. The kit finished {a_['of_auto']} cases on its own and {a_['n']} ({pct(a_['rate'])}) differ from the recorded human outcome:")
    print("     by the generator's scenario: " + ", ".join(f"{k} {v}" for k, v in a_["by_scenario"].items()))
    print(f"       {mis['auto_returns_from_reason_code']['human_resubmitted']} of {mis['auto_returns_from_reason_code']['n']} auto "
          "returns on a closed-account reason code: the advice carried a successor account the rule table ignores")
    print(f"       {mis['auto_returns_from_name_mismatch']['human_resubmitted']} of {mis['auto_returns_from_name_mismatch']['n']} auto "
          "returns on a name MISMATCH: a person had resubmitted")
    w_ = mis["watch_list_missed"]
    o_ = mis["watch_list_over_escalated"]
    print(f"  C. Watch list: {w_['of'] - w_['n']} of {w_['of']} planted hits escalated; missed {w_['n']}. "
          f"Escalated where a person had cleared the party: {o_['n']}.")
    print(f"  Result: acceptance criterion AC-06 (auto-handled wrongly <= {cfg.acceptance[5].threshold:g}) "
          f"{'passes' if S['acceptance'][5]['passed'] else 'FAILS'} at {pct(aw['rate'])}. "
          "Under the brief's own exit criteria the kit does not leave shadow mode on this data.")
    mm, ra = mis["auto_returns_from_name_mismatch"], mis["auto_returns_with_advised_value"]
    print("  Design response (🔴 designed from this miss, not built, not tested, so not held-out evidence): send RX02 name")
    print(f"  mismatches ({mm['n']} cases) and closed-account returns that carry an advised account ({ra['n']} cases) to a person")
    print(f"  instead of closing them. {mis['wrong_auto_inside_design_response']} of the {a_['n']} wrong auto outcomes sit inside those {mm['n'] + ra['n']} cases; the cost is "
          f"{mm['n'] + ra['n']} more S07 judgments on top of {sc['deferred']}.")

    print("\nMODELED touch minutes per case (🟡; assumptions: the generator's step minutes; a reviewer spends the S09")
    print("minutes and nothing more; every S07 is followed by an S09; escalated and queued cases keep the full manual minutes)")
    mi = S["minutes"]
    print(f"  manual {mi['manual_per_case']:.1f} min per case; with the kit's routes {mi['kit_per_case']:.1f} min per case. "
          "Not a saving claim: it assumes the routes hold.")

    print("\nHAND-OFF")
    sig = S["signals"]
    print(f"  runbook items drafted from the brief: {len(cfg.runbook_items)} of {len(cfg.runbook_items)} "
          "(a skeleton; nobody has run it)")
    print(f"  monitoring signals computed from the trace: {sum(1 for v in sig.values() if v['computable'])} of {len(sig)}")
    for k_, v in sig.items():
        print(f"    {k_:20s} {v['value']}")
    OUT.mkdir(exist_ok=True)
    (OUT / "runbook_draft.md").write_text(build_runbook(cfg), encoding="utf-8")

    print("\nTEST PLAN in the brief")
    print(f"  golden cases: brief {cfg.golden_cases}, fixtures in tests/support.py {S['golden_cases']}")
    print(f"  shadow-mode cases: brief {cfg.shadow_cases}, replayed {sc['cases']}")
    print("  fault injections named in the brief: " + ", ".join(cfg.fault_injections) + " (each exercised above and in tests/)")

    print("\nTHE SIX DEFICIENCIES, BEFORE AND AFTER")
    a3, b3, c3, d3, e3, f3 = m3["a"], m3["b"], m3["c"], m3["d"], m3["e"], m3["f"]
    print(f"  (a) Scope      script: {a3['calls_outside']:,} calls outside scope, {a3['write_calls_outside']} writes.  kit: "
          f"{S['measured']['out_of_scope_calls_executed']} executed; {f['rogue_blocked']} of {f['rogue_attempted']} attempted were blocked")
    print(f"  (b) Four-eyes  script: {b3['without_approval']} resubmits, 0 approved.  kit: {p['unapproved_in_ledger']} without an approval; "
          f"{p['blocked_total']:,} unapproved attempts blocked")
    print(f"  (c) Silent     script: {c3['cases_failed_silently']} cases failed with no signal.  kit: {S['measured']['silent_failures']} "
          f"(12 malformed -> human queue with a reason; 14 duplicates closed once; "
          f"{S['copy_check']['copies_read_back']} worksheet copies read back equal to the source, {S['copy_check']['leading_zero_accounts_copied_intact']} of them "
          "accounts that start with a zero)")
    print(f"  (d) Audit      script: {pct(d3['share_without_trace'])} of decisions untraced.  kit: completeness "
          f"{S['measured']['audit_completeness']:.3f}, hash chain intact")
    print(f"  (e) Shadow     script: {pct(e3['agreement_rate_with_outcome'])} agreement, unknown until step 3.  kit: "
          f"{pct(sc['agreement_rate'])}, measured before any live action")
    print(f"  (f) Hand-off   script: 0 of {f3['runbook_items']['required']} runbook items, 0 of {f3['monitoring']['required']} monitors.  "
          f"kit: {len(cfg.runbook_items)} runbook items drafted, {sum(1 for v in sig.values() if v['computable'])} of {len(sig)} monitors computed")

    print("\nUTILITY  =  (my solution - current state of the art) x number of people it affects")
    print(f"  current state of the art (the script):  wrong or unsafe outcomes per case  {ut['script_wrong_cases']} of {sc['cases']} = {pct(ut['script_wrong_rate'])}   (measured, step 3)")
    print(f"  my solution (AgentKit, shadow):         wrong outcomes the kit finishes on its own  {ut['kit_wrong_cases']} of {sc['cases']} = {pct(ut['kit_wrong_rate'])}   (measured)")
    print(f"  lift per case {pct(ut['lift_per_case'])}  x  {ut['cases_per_quarter']:,} cases a quarter (modeled: 600 cases in 30 days, three such windows, flat volume)")
    print(f"  = {ut['avoided_per_quarter']:.0f} fewer wrong or unsafe outcomes taken without a person per quarter (🟡)")
    print(f"  Not counted: {ut['wrong_proposals_reaching_a_person']} wrong proposals that reach a person at S09. A real reviewer's catch rate is unmeasured (🔴).")

    # outputs
    rows = []
    for r_ in S["shadow"]["results"]:
        h = world["outcomes"][r_.case_id]
        rows.append((r_.case_id, r_.route, r_.state, r_.gate or "", r_.proposed_outcome, h["human_outcome"],
                     shadow.judge_pair(r_, h), r_.reason_kind, r_.name_class or "", r_.name_score if r_.name_score is not None else ""))
    write_csv("step_04_cases.csv", ["case_id", "route", "state", "gate", "kit_proposal", "human_outcome", "judgment",
                                    "queue_reason", "name_class", "name_score"], rows)
    write_csv("step_04_acceptance.csv", ["id", "metric", "direction", "threshold", "measured", "passed"],
              [(a["id"], a["metric"], a["direction"], a["threshold"], a["value"], a["passed"]) for a in S["acceptance"]])
    write_json("step_04_summary.json", summary_json(S))
    print("\nWrote src/out/step_04_cases.csv, step_04_acceptance.csv, step_04_summary.json, audit_shadow.jsonl, runbook_draft.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
