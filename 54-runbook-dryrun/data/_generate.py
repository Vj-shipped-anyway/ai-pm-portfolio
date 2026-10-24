"""Generate the synthetic data for project 54: 94 drill cases, each one incident runbook with a snapshot of
system state, a requester and the approval records on file, plus the truth about what a real run would do.

Everything is seeded, so a rerun reproduces every file byte for byte. The truth of each case is decided here,
by the defect planted into it, and never by running the tool. The runbooks are made-up AI-operations
runbooks for a modeled bank: the command names (routectl, modelctl and so on) belong to no real product.
Two kinds of case are hard on purpose: hard negatives that a rule could flag by mistake, and cases where the
runbook lies about itself, which a dry run cannot see.

Run (from data/):  python3 _generate.py
Writes:  cases.csv, truth.csv, example_runbook.yml, example_world.json, example_approvals.json
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re

rng = random.Random(54)
NAMES = ["dana", "marta", "ines", "omar", "priya", "tomas", "lena", "kofi"]
ROLE = "incident-commander"
TTL = 30

# slug, tool, state domain, metric, threshold, action, undo, mode before, mode after, targets, what the action does
SCENARIOS = [
    ("route-to-fallback", "routectl", "route", "error_rate_pct", 5, "set --target {{target}} --mode fallback",
     "set --target {{target}} --mode primary", "primary", "fallback", ["assistant-api", "faq-bot", "advisor-chat"], "Move traffic to the fallback model"),
    ("model-rollback", "modelctl", "model", "error_rate_pct", 4, "rollback --target {{target}} --to previous",
     "rollback --target {{target}} --to current", "current", "rolled_back", ["scorer-v7", "triage-v3", "summarizer-v2"], "Roll the model back to the previous version"),
    ("agent-tool-off", "agentctl", "agent", "blocked_calls_per_hour", 20, "disable-tool --agent {{target}} --tool payments.submit",
     "enable-tool --agent {{target}} --tool payments.submit", "enabled", "disabled", ["dispute-agent", "refund-agent", "kyc-agent"], "Switch off the agent's payment tool"),
    ("batch-pause", "schedctl", "job", "late_minutes", 30, "pause --job {{target}}",
     "resume --job {{target}}", "running", "paused", ["nightly-scoring", "embedding-refresh", "report-build"], "Pause the batch job"),
    ("index-quarantine", "ragctl", "index", "stale_docs_pct", 10, "quarantine --index {{target}}",
     "release --index {{target}}", "live", "quarantined", ["policy-index", "product-faq", "procedures-index"], "Quarantine the retrieval index"),
    ("credential-rotate", "secretctl", "secret", "failed_auth_per_min", 15, "rotate --name {{target}}",
     "restore --name {{target}}", "active", "rotated", ["tool-api-key", "vector-db-token", "gateway-signing-key"], "Rotate the credential"),
    ("pattern-block", "guardctl", "policy", "flagged_prompts_per_hour", 25, "add-pattern --policy {{target}}",
     "remove-pattern --policy {{target}}", "base", "patched", ["assistant-input", "advisor-input", "faq-input"], "Add the blocking pattern to the input policy"),
    ("traffic-shed", "gatewayctl", "gateway", "queue_depth", 500, "shed --route {{target}} --percent 50",
     "unshed --route {{target}}", "normal", "shedding", ["chat-route", "search-route", "batch-route"], "Shed half the load on the route"),
]

# kind, group, how many, truth verdict, what a real run does
KINDS = [
    ("clean_ready", "clean", 12, "READY", "completes"), ("hn_note_placeholder", "hard_negative", 4, "READY", "completes"),
    ("hn_low_risk_write", "hard_negative", 4, "READY", "completes"), ("hn_two_approvals_one_self", "hard_negative", 3, "READY", "completes"),
    ("hn_ttl_boundary", "hard_negative", 3, "READY", "completes"), ("hn_numeric_text", "hard_negative", 3, "READY", "completes"),
    ("no_rollback", "warning", 4, "READY", "completes"), ("waiting_no_approval", "waiting", 8, "WAITING", "parks"),
    ("undefined_param", "lint", 5, "BLOCKED", "garbled"), ("write_ungated", "lint", 5, "BLOCKED", "unsafe"),
    ("undeclared_state_key", "lint", 4, "BLOCKED", "stops"), ("duplicate_id", "lint", 3, "BLOCKED", "stops"),
    ("precondition_false", "state", 6, "BLOCKED", "stops"), ("self_blocking", "state", 4, "BLOCKED", "stops"),
    ("missing_state_key", "state", 3, "BLOCKED", "stops"), ("self_approval", "approval", 4, "BLOCKED", "unsafe"),
    ("wrong_role", "approval", 4, "BLOCKED", "unsafe"), ("digest_mismatch", "approval", 4, "BLOCKED", "unsafe"),
    ("stale_approval", "approval", 4, "BLOCKED", "unsafe"), ("mislabeled_effect", "hard_miss", 4, "BLOCKED", "unsafe"),
    ("world_drift", "hard_miss", 3, "BLOCKED", "stops"),
]


def digest(rb_id, step_id, rendered):
    return hashlib.sha256(("%s\n%s\n%s" % (rb_id, step_id, rendered)).encode("utf-8")).hexdigest()[:12]


def fill(text, params):
    for name, value in params.items():
        text = text.replace("{{%s}}" % name, value)
    return text


def approval(rb_id, run, params, who, age):
    return {"step": "s3", "approver": who, "role": ROLE, "digest": digest(rb_id, "s3", fill(run, params)), "age_minutes": age}


# ---------------------------------------------------------------- YAML text
def y_scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", v) and v not in ("true", "false"):
        return v
    return json.dumps(v)


def y_flow_map(d):
    return "{" + ", ".join("%s: %s" % (k, y_scalar(v)) for k, v in d.items()) + "}"


def emit(rb):
    out = ["runbook: " + y_scalar(rb["runbook"]), "title: " + y_scalar(rb["title"]),
           "reads: [" + ", ".join(y_scalar(k) for k in rb["reads"]) + "]", "params:"]
    out += ["  %s: %s" % (k, y_scalar(v)) for k, v in rb["params"].items()]
    out.append("steps:")
    for st in rb["steps"]:
        out.append("  - id: " + y_scalar(st["id"]))
        for key in ("title", "effect", "risk", "run"):
            out.append("    %s: %s" % (key, y_scalar(st[key])))
        if st.get("requires"):
            out.append("    requires: [" + ", ".join(y_scalar(c) for c in st["requires"]) + "]")
        if st.get("sets"):
            out.append("    sets: " + y_flow_map(st["sets"]))
        if st.get("approval"):
            out += ["    approval:", "      role: " + y_scalar(st["approval"]["role"]), "      ttl_minutes: %d" % st["approval"]["ttl_minutes"]]
        if st.get("rollback"):
            out.append("    rollback: " + y_scalar(st["rollback"]))
        if st.get("note"):
            out.append("    note: " + y_scalar(st["note"]))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- one case
def base(sc, rb_id, target):
    _, tool, dom, metric, thr, action, undo, before, after, _, act_title = sc
    return {"runbook": rb_id, "title": "%s (%s)" % (act_title, target),
            "reads": ["%s.%s" % (dom, metric), dom + ".fallback_health", "change.freeze"],
            "params": {"target": target, "channel": "ai-incident"},
            "steps": [
                {"id": "s1", "title": "Confirm the metric is over the line", "effect": "read", "risk": "low",
                 "run": tool + " status --target {{target}}", "requires": ["%s.%s >= %d" % (dom, metric, thr)]},
                {"id": "s2", "title": "Confirm the fallback is healthy", "effect": "read", "risk": "low",
                 "run": tool + " health --target {{target}} --fallback", "requires": [dom + ".fallback_health == healthy"]},
                {"id": "s3", "title": act_title, "effect": "write", "risk": "high", "run": tool + " " + action,
                 "requires": ["change.freeze == off"], "sets": {dom + ".mode": after},
                 "approval": {"role": ROLE, "ttl_minutes": TTL}, "rollback": tool + " " + undo},
                {"id": "s4", "title": "Tell the incident channel", "effect": "notify", "risk": "low",
                 "run": "chatctl post --channel {{channel}} --text 'mitigation applied to {{target}}'"},
                {"id": "s5", "title": "Verify the change", "effect": "read", "risk": "low",
                 "run": tool + " status --target {{target}}", "requires": ["%s.mode == %s" % (dom, after)]}]}


def build_case(kind, idx):
    sc = SCENARIOS[rng.randrange(len(SCENARIOS))]
    _, _, dom, metric, thr, _, _, before, _, targets, _ = sc
    target = rng.choice(targets)
    rb_id = "rb-%03d" % idx
    rb = base(sc, rb_id, target)
    steps = {s["id"]: s for s in rb["steps"]}
    run3 = steps["s3"]["run"]
    requester, approver = rng.sample(NAMES, 2)
    world = {"%s.%s" % (dom, metric): thr + rng.randint(1, 20), dom + ".fallback_health": "healthy",
             "change.freeze": "off", dom + ".mode": before}
    good = approval(rb_id, run3, rb["params"], approver, rng.randint(1, 25))
    approvals, params, warning, pi, detail = [good], {}, "no", 0, "nothing planted"
    if kind == "waiting_no_approval":
        approvals, pi, detail = [], 3, "no approval record on file for s3, so the run parks there"
    elif kind == "hn_note_placeholder":
        steps["s3"]["note"] = "Ask {{vendor}} to confirm before this step."
        detail = "a placeholder with no param sits in a note, which is never run"
    elif kind == "hn_low_risk_write":
        rb["steps"].insert(4, {"id": "s4a", "title": "Add a note to the ticket", "effect": "write", "risk": "low",
                               "run": "ticketctl comment --text 'mitigation applied to {{target}}'"})
        detail = "a low-risk write with no gate and no rollback is within the policy"
    elif kind == "hn_two_approvals_one_self":
        approvals = [dict(good, approver=requester), good]
        detail = "the requester also signed, which does not count, and a second person signed correctly"
    elif kind == "hn_ttl_boundary":
        good["age_minutes"] = TTL
        detail = "the approval is exactly as old as the limit, which is still valid"
    elif kind == "hn_numeric_text":
        world["%s.%s" % (dom, metric)] = str(world["%s.%s" % (dom, metric)])
        detail = "the snapshot holds the metric as text; a person reads it as the number it is"
    elif kind == "no_rollback":
        del steps["s3"]["rollback"]
        warning, detail = "yes", "the high-risk write names no rollback"
    elif kind == "undefined_param":
        steps["s4"]["run"] = steps["s4"]["run"].replace("{{channel}}", "{{chan}}")
        pi, detail = 4, "s4 uses {{chan}} but params defines channel"
    elif kind == "write_ungated":
        del steps["s3"]["approval"]
        approvals, pi, detail = [], 3, "the high-risk write has no approval gate"
    elif kind == "undeclared_state_key":
        steps["s2"]["requires"] = [dom + ".fallback_helth == healthy"]
        pi, detail = 2, "a typo in the key s2 reads"
    elif kind == "duplicate_id":
        steps["s4"]["id"] = "s3"
        pi, detail = 4, "the notify step reuses the id s3"
    elif kind == "precondition_false":
        if rng.randint(0, 1):
            world["change.freeze"], pi, detail = "on", 3, "a change freeze is on, so s3 cannot start"
        else:
            world["%s.%s" % (dom, metric)], pi, detail = thr - rng.randint(1, 3), 1, "the metric is under the line, so s1 stops the run"
    elif kind == "self_blocking":
        steps["s5"]["requires"] = ["%s.mode == %s" % (dom, before)]
        pi, detail = 5, "s5 checks for the state s3 just changed"
    elif kind == "missing_state_key":
        del world[dom + ".fallback_health"]
        pi, detail = 2, "the snapshot was exported without the key s2 reads"
    elif kind == "self_approval":
        good["approver"] = requester
        pi, detail = 3, "the only approval is from the requester"
    elif kind == "wrong_role":
        good["role"] = "duty-manager"
        pi, detail = 3, "the approver holds a role the gate does not accept"
    elif kind == "digest_mismatch":
        params = {"target": rng.choice([t for t in targets if t != target])}
        pi, detail = 3, "the approval was given for %s and the run is for %s" % (target, params["target"])
    elif kind == "stale_approval":
        good["age_minutes"] = TTL + rng.randint(1, 40)
        pi, detail = 3, "the approval is %d minutes old against a limit of %d" % (good["age_minutes"], TTL)
    elif kind == "mislabeled_effect":
        steps["s3"]["effect"], steps["s3"]["risk"] = "read", "low"
        del steps["s3"]["approval"]
        approvals, pi, detail = [], 3, "s3 changes production but is labeled a read, so nothing gates it"
    elif kind == "world_drift":
        pi, detail = 3, "change.freeze turned on 14 minutes after the snapshot was taken"
    before_steps = rb["steps"][:pi - 1] if pi else rb["steps"]
    writes = sum(1 for s in before_steps if s["effect"] == "write")
    if kind == "mislabeled_effect":
        writes = 0
    return rb, world, approvals, params, requester, pi, writes, warning, detail


def main():
    plan = [k for k in KINDS for _ in range(k[2])]
    plan.sort(key=lambda k: (rng.random(), k[0]))
    cases, truth = [], []
    for n, (kind, group, _, verdict, real) in enumerate(plan, 1):
        rb, world, approvals, params, requester, pi, writes, warning, detail = build_case(kind, n)
        cid = "C-%03d" % n
        cases.append([cid, requester, json.dumps(params, sort_keys=True), json.dumps(world, sort_keys=True),
                      json.dumps(approvals, sort_keys=True), emit(rb)])
        truth.append([cid, kind, group, verdict, real, pi, writes, warning, detail])
    with open("cases.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["case_id", "requester", "params_json", "world_json", "approvals_json", "runbook_yaml"])
        w.writerows(cases)
    with open("truth.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["case_id", "case_kind", "case_group", "truth_verdict", "real_run", "problem_index", "writes_before", "expect_warning", "detail"])
        w.writerows(truth)
    write_example()


def write_example():
    """The worked example behind `python3 runbook_dryrun.py --demo`: an approval given for scorer-v8 meets a run for scorer-v7."""
    rb = {"runbook": "scorer-rollback", "title": "Roll the scoring model back to the previous version",
          "reads": ["model.error_rate_pct", "model.previous_health", "change.freeze"],
          "params": {"target": "scorer-v7", "previous": "scorer-v6", "channel": "ai-incident"},
          "steps": [
              {"id": "s1", "title": "Confirm the error rate", "effect": "read", "risk": "low",
               "run": "modelctl status --target {{target}}", "requires": ["model.error_rate_pct >= 5"]},
              {"id": "s2", "title": "Confirm the previous version is healthy", "effect": "read", "risk": "low",
               "run": "modelctl health --target {{previous}}", "requires": ["model.previous_health == healthy"]},
              {"id": "s3", "title": "Roll back to the previous version", "effect": "write", "risk": "high",
               "run": "modelctl rollback --target {{target}} --to {{previous}}", "requires": ["change.freeze == off"],
               "sets": {"model.mode": "rolled_back"}, "approval": {"role": ROLE, "ttl_minutes": TTL},
               "rollback": "modelctl rollback --target {{previous}} --to {{target}}"},
              {"id": "s4", "title": "Tell the incident channel", "effect": "notify", "risk": "low",
               "run": "chatctl post --channel {{channel}} --text 'rolled back {{target}}'"},
              {"id": "s5", "title": "Verify the rollback", "effect": "read", "risk": "low",
               "run": "modelctl status --target {{previous}}", "requires": ["model.mode == rolled_back"]}]}
    with open("example_runbook.yml", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(emit(rb))
    with open("example_world.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"change.freeze": "off", "model.error_rate_pct": 12, "model.previous_health": "healthy"}, fh, indent=1, sort_keys=True)
        fh.write("\n")
    given_for = {"target": "scorer-v8", "previous": "scorer-v6"}
    with open("example_approvals.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump([approval("scorer-rollback", rb["steps"][2]["run"], given_for, "marta", 12)], fh, indent=1, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    main()
