"""Step 3 - Six named deficiencies, measured on the step 2 script.

  (a) it acts outside the scope a brief would allow
  (b) it resubmits without the four-eyes approval
  (c) it fails silently on malformed and duplicate records
  (d) it leaves no audit trail for a share of its decisions
  (e) no shadow-mode comparison exists, so its disagreement with humans is unknown until measured here
  (f) nothing hands off: no runbook items, monitoring or exit criteria

The brief (briefs/wire_repair_agent_brief.json) is the yardstick. These are counts for the one script in
step 2; another script would score differently. Run from src/:  python3 step_03_deficiencies_exposed.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentkit import shadow  # noqa: E402
from agentkit.brief import derive_config, load_brief, scope_violation  # noqa: E402
from agentkit.data_io import load_world  # noqa: E402
from agentkit.handoff import split_id  # noqa: E402
from agentkit.matching import account_format_ok, bank_code_ok, luhn_ok  # noqa: E402
from common import BRIEF_PATH, pct, table, write_csv, write_json  # noqa: E402
from step_02_script_without_controls import ARTIFACTS, run_script  # noqa: E402

# Which brief hand-off items the script's artifacts cover. None: it leaves a script and a count behind.
SCRIPT_COVERS: set = set()


def _valid_value(field: str, value: str) -> bool:
    if field == "beneficiary_account":
        return account_format_ok(value) and luhn_ok(value)
    if field == "beneficiary_bank_code":
        return bank_code_ok(value)
    return bool(str(value).strip())


def measure(world: dict, brief: dict = None) -> dict:
    brief = brief or load_brief(BRIEF_PATH)
    cfg = derive_config(brief)
    run = run_script(world)
    env, s = run["env"], run["script"]
    truth, outcomes = world["truth"], world["outcomes"]
    case_row = {c["case_id"]: c for c in world["cases"]}

    # (a) scope
    breaches = Counter()
    for system, action, access, _cid in env.call_log:
        if scope_violation(cfg.tool_scope, system, action):
            breaches[(system, action, access)] += 1
    changed = sum(1 for pid, p in env.payments.items() if p != world["payments"][pid])
    a = {"calls_total": len(env.call_log), "calls_outside": sum(breaches.values()),
         "write_calls_outside": sum(n for (_s, _a, acc), n in breaches.items() if acc == "write"),
         "by_action": {f"{sy}.{ac} ({acc})": n for (sy, ac, acc), n in sorted(breaches.items())},
         "payment_records_changed_at_source": changed}

    # (b) resubmits without approval
    resub = [(cid, x) for cid, x in sorted(s.actions.items()) if x["action"] == "RESUBMIT"]
    not_resub = Counter(outcomes[cid]["human_outcome"] for cid, _x in resub
                        if outcomes[cid]["human_outcome"] != "RESUBMIT")
    b = {"resubmissions": len(env.ledger), "with_approval": 0, "without_approval": len(env.ledger),
         "human_did_not_resubmit": sum(not_resub.values()), "by_human_outcome": dict(sorted(not_resub.items()))}

    # (c) silent failures
    skipped = sorted(cid for cid, x in s.actions.items() if x["action"] == "SKIPPED_SILENTLY")
    garbage, corrupted = [], []
    for cid, x in resub:
        if not _valid_value(x["field"], x["value"]):
            garbage.append(cid)
        orig = world["payments"].get(case_row[cid]["payment_id"])
        if orig and x["field"] != "beneficiary_account" and x["payload"].get("beneficiary_account") != \
                orig["beneficiary_account"]:
            corrupted.append(cid)
    per_payment = Counter(l["payment_id"] for l in env.ledger)
    double_paid = sorted(pid for pid, n in per_payment.items() if n > 1)
    extra_ledger = sum(n - 1 for n in per_payment.values() if n > 1)
    silent = set(skipped) | set(garbage) | set(corrupted)
    dup_cases = {cid for cid, t in truth.items() if t["scenario"] == "duplicate"}
    silent |= {cid for cid in dup_cases if s.actions[cid]["action"] == "RESUBMIT"}
    c = {"skipped_silently": len(skipped), "skipped_by_scenario": dict(Counter(truth[x]["scenario"] for x in skipped)),
         "garbage_resubmitted": len(garbage), "corrupted_by_spreadsheet": len(corrupted),
         "payments_resubmitted_twice": len(double_paid), "extra_ledger_entries": extra_ledger,
         "cases_failed_silently": len(silent), "job_said": run["banner"]}

    # (d) audit
    d = {"decisions": len(s.decisions), "logged": len(s.log), "without_trace": len(s.decisions) - len(s.log),
         "share_without_trace": (len(s.decisions) - len(s.log)) / len(s.decisions),
         "cases_with_no_record": len(run["ids"]) - len(s.log),
         "log_has_a_reason": False}

    # (e) shadow comparison for the script
    rows = []
    for cid in run["ids"]:
        x = s.actions[cid]
        if x["action"] == "RESUBMIT":
            r = SimpleNamespace(case_id=cid, proposed_outcome="RESUBMIT", correction={"field": x["field"], "new": x["value"]},
                                redelivery=False, route="auto", gate=None, state="", reason_kind="")
        elif x["action"] == "SKIPPED_SILENTLY":
            r = SimpleNamespace(case_id=cid, proposed_outcome="NO_OUTCOME", correction=None, redelivery=False,
                                route="auto", gate=None, state="", reason_kind="")
        else:
            r = SimpleNamespace(case_id=cid, proposed_outcome=x["action"], correction=None, redelivery=False,
                                route="auto", gate=None, state="", reason_kind="")
        rows.append(r)
    sc = shadow.score(rows, outcomes, truth)
    dis_by_scn = Counter(x["scenario"] for x in sc["disagreements"])
    no_outcome = [r.case_id for r in rows if r.proposed_outcome == "NO_OUTCOME"]
    e = {"cases": sc["cases"], "with_outcome": sc["cases"] - len(no_outcome), "agree": sc["agree"],
         "disagree": sc["disagree"] - len(no_outcome), "no_outcome": len(no_outcome),
         "agreement_rate_with_outcome": sc["agree"] / (sc["agree"] + sc["disagree"] - len(no_outcome)),
         "agreement_rate_all_cases": sc["agree"] / sc["cases"],
         "by_human_class": {k: {"n": v["n"], "agree": v["agree"], "disagree": v["disagree"]}
                            for k, v in sc["by_human_class"].items()},
         "disagree_by_scenario": dict(sorted(dis_by_scn.items(), key=lambda kv: -kv[1]))}

    # (f) hand-off
    required = {"runbook_items": [split_id(x)[0] for x in cfg.runbook_items],
                "monitoring": [split_id(x)[0] for x in cfg.monitoring],
                "exit_criteria": list(cfg.exit_criteria), "acceptance_tests": [t.id for t in cfg.acceptance]}
    f = {k: {"required": len(v), "covered": len([x for x in v if x in SCRIPT_COVERS])} for k, v in required.items()}
    f["artifacts"] = list(ARTIFACTS)

    # cases the script got wrong in some way (used for the utility term in step 4)
    wrong = set(no_outcome) | set(garbage) | set(corrupted) | {x["case_id"] for x in sc["disagreements"]}
    return {"a": a, "b": b, "c": c, "d": d, "e": e, "f": f, "wrong_cases": sorted(wrong),
            "wrong_rate": len(wrong) / sc["cases"], "run": run, "rows": rows, "score": sc}


def main() -> int:
    world = load_world()
    m = measure(world)
    a, b, c, d, e, f = m["a"], m["b"], m["c"], m["d"], m["e"], m["f"]
    print("=" * 100)
    print("Step 3 - Six deficiencies of the script, measured against the brief")
    print("=" * 100)

    print("\n(a) It acts outside the scope the brief allows")
    print(f"    {a['calls_outside']:,} of {a['calls_total']:,} calls were outside the brief's tool scope; "
          f"{a['write_calls_outside']:,} of them were writes.")
    for k, v in a["by_action"].items():
        print(f"      {k:46s} {v:5d}")
    print(f"    {a['payment_records_changed_at_source']:,} records in the original payments table were changed to make a "
          "match pass (fix at source).")

    print("\n(b) It resubmits without the four-eyes approval")
    print(f"    {b['resubmissions']:,} resubmissions sent; {b['with_approval']} carried an approval, "
          f"{b['without_approval']:,} did not (100%).")
    print(f"    In {b['human_did_not_resubmit']} of them the recorded human outcome was not a resubmit: "
          + ", ".join(f"{k} {v}" for k, v in b["by_human_outcome"].items()) + ".")

    print("\n(c) It fails silently on malformed and duplicate records")
    print(f"    The job said: \"{c['job_said']}\" The queue held 600.")
    print(f"    {c['skipped_silently']} cases were skipped with the error swallowed, left open, no log line "
          f"({', '.join(f'{k} {v}' for k, v in c['skipped_by_scenario'].items())}).")
    print(f"    {c['garbage_resubmitted']} resubmissions carried a value that fails the format rule (for example a "
          "non-numeric account).")
    print(f"    {c['corrupted_by_spreadsheet']} resubmissions carried an account number the spreadsheet hop had altered "
          "(leading zeros dropped).")
    print(f"    {c['payments_resubmitted_twice']} payments were resubmitted twice ({c['extra_ledger_entries']} extra "
          "ledger entries) because a redelivered exception was processed again.")
    print(f"    {c['cases_failed_silently']} cases in all failed without any signal.")

    print("\n(d) It leaves no audit trail for a share of its decisions")
    print(f"    {d['decisions']:,} decisions made; {d['logged']:,} have a log line. "
          f"{d['without_trace']:,} ({pct(d['share_without_trace'])}) leave no trace. "
          f"{d['cases_with_no_record']} cases have no record at all, and no log line says why anything was decided.")

    print("\n(e) No shadow-mode comparison exists; its disagreement with humans was unknown until this step")
    print(f"    Against the recorded human outcome: {e['agree']} agree, {e['disagree']} disagree, "
          f"{e['no_outcome']} produced no outcome (of {e['cases']}).")
    print(f"    Agreement where it produced an outcome: {pct(e['agreement_rate_with_outcome'])}; "
          f"over all cases: {pct(e['agreement_rate_all_cases'])}.")
    rows = [(k, v["n"], v["agree"], v["disagree"]) for k, v in e["by_human_class"].items()]
    print(table(rows, ["human outcome", "cases", "agree", "disagree"]))
    print("    Where it disagrees, by the generator's scenario (the answer key): "
          + ", ".join(f"{k} {v}" for k, v in e["disagree_by_scenario"].items()))

    print("\n(f) Nothing hands off")
    for k in ("runbook_items", "monitoring", "exit_criteria", "acceptance_tests"):
        print(f"    {k.replace('_', ' '):18s} the brief asks for {f[k]['required']}; the script's artifacts cover "
              f"{f[k]['covered']}")
    print(f"    It leaves behind: {', '.join(f['artifacts'])}.")

    print(f"\nCases the script got wrong in at least one way: {len(m['wrong_cases'])} of {e['cases']} "
          f"({pct(m['wrong_rate'])}). The product is the controls around the steps, not the steps.")
    write_csv("step_03_deficiencies.csv", ["deficiency", "measure", "value"], [
        ("a_scope", "calls outside the brief's scope", a["calls_outside"]),
        ("a_scope", "write calls outside the brief's scope", a["write_calls_outside"]),
        ("a_scope", "payment records changed at source", a["payment_records_changed_at_source"]),
        ("b_four_eyes", "resubmissions without approval", b["without_approval"]),
        ("b_four_eyes", "resubmissions where the human did not resubmit", b["human_did_not_resubmit"]),
        ("c_silent", "cases skipped silently", c["skipped_silently"]),
        ("c_silent", "garbage values resubmitted", c["garbage_resubmitted"]),
        ("c_silent", "spreadsheet-altered account numbers resubmitted", c["corrupted_by_spreadsheet"]),
        ("c_silent", "payments resubmitted twice", c["payments_resubmitted_twice"]),
        ("d_audit", "decisions with no trace", d["without_trace"]),
        ("e_shadow", "disagreements with the recorded human outcome", e["disagree"]),
        ("e_shadow", "cases with no outcome", e["no_outcome"]),
        ("f_handoff", "brief hand-off items covered", sum(f[k]["covered"] for k in
                                                          ("runbook_items", "monitoring", "exit_criteria")))])
    summary = {k: m[k] for k in ("a", "b", "c", "d", "e", "f", "wrong_rate")}
    summary["wrong_cases"] = len(m["wrong_cases"])
    write_json("step_03_summary.json", summary)
    print("\nWrote src/out/step_03_deficiencies.csv and step_03_summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
