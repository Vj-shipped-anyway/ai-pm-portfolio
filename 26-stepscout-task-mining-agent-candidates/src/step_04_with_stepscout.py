"""Step 4 - The fix: StepScout. Merge desktop and system events, classify each step, screen it, rank it, brief it.

What it does, in order
  1. MERGE. Group the labeled desktop events into step occurrences per case (the miner's label is used
     here for the first time), attach the case-system status events, and rebuild touch time and wait
     time per step. The merge is checked: how many status events land on an occurrence of the right step.
  2. CLASSIFY. Each step becomes AGENT, AGENT_HITL, HUMAN_JUDGMENT or HUMAN_CONTROL from observable
     features only: how often workers override a proposed value, how much free text they type, how
     often the step repeats within a case, how much its timing varies, whether it writes to the payments
     hub or sends email, and the register's control flag. The answer key is never read inside the
     classifier; a check at the end shuffles the key and shows the classes do not move.
  3. SCREEN. The control screen takes four-eyes steps out of the candidate list and attaches conditions
     to steps that touch restricted data or may run only after an approval.
  4. RANK. Modeled hours at stake times readiness. Hours at stake is touch time in the 30 days times ONE
     named assumption: the share of a step's touch time an agent removes (REMOVAL_SHARE). It is modeled,
     never measured.
  5. BRIEF. Write build-brief/v1 files for the top candidates and validate them with a stdlib check.
  6. SCORE against the answer key, which is the generator's own: accuracy, precision and recall of
     agent-ready steps, the top 10 against the volume-first list, the share of handling time recovered,
     and the known miss.

Run (from src/):
    python3 step_04_with_stepscout.py

Output: a readable summary, plus out/step_04_steps.csv, out/step_04_candidates.csv, out/step_04_summary.json
and out/BB-001.json and so on (one build brief per top candidate).
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from bisect import bisect_left

from step_01_interview_process_map import (
    AGENT_READY, APP_LABEL, DATA_DIR, OUT_DIR, load_all, minutes, pct, read_csv, split_catalog,
)
from step_02_system_log_mining import TOP_N, analyze as analyze_log
from step_03_deficiencies_exposed import summarize as summarize_deficiencies

# ---- the one named assumption, and the constants that only order candidates --------------------------------
REMOVAL_SHARE = 0.70                 # ASSUMPTION (modeled): an agent removes 70% of a step's touch time. A stub for what a
                                     # real agent would remove; never measured
READINESS = {"AGENT": 1.0, "AGENT_HITL": 0.6}   # ranking weights, not measurements: a person still reviews HITL output
N_BRIEFS = 3

# ---- classifier thresholds (my choices; printed with the result) -----------------------------------------
OCC_GAP_S = 600                      # two events of one step more than 10 minutes apart are two occurrences
JUDGE_OVERRIDE, JUDGE_TEXT, JUDGE_REPEAT, JUDGE_CV, JUDGE_NEED = 0.20, 200.0, 1.30, 0.50, 2
HITL_OVERRIDE, HITL_TEXT, HITL_WRITE, HITL_OUTWARD = 0.05, 80.0, 0.50, 0.50
STATUS_TOLERANCE_S = (-5, 120)       # an occurrence ends from 5 seconds after to 120 seconds before its status event
READ_ACTIONS = ("read", "search", "open", "copy")
BRIEF_SCHEMA = "build-brief/v1"


# ---------------------------------------------------------------------------
# 1. Merge
# ---------------------------------------------------------------------------
def build_occurrences(data: dict) -> list:
    occs = []
    for cid, evs in data["desk_by_case"].items():
        cur = None
        for e in evs:
            if not e["step"]:
                continue
            if cur is None or e["step"] != cur["step"] or e["start"] - cur["end"] > OCC_GAP_S:
                cur = {"case": cid, "step": e["step"], "worker": e["worker"], "start": e["start"], "end": e["end"], "events": []}
                occs.append(cur)
            cur["events"].append(e)
            cur["end"] = max(cur["end"], e["end"])
    prev = None
    for o in occs:
        ev = o["events"]
        o["touch"] = sum(minutes(e) for e in ev)
        o["chars"] = sum(e["chars"] for e in ev)
        o["override"] = any(e["action"] == "override_value" for e in ev)
        copied, cross = set(), False
        for e in ev:
            if e["action"] == "copy":
                copied.add(e["app"])
            elif e["action"] == "paste" and (copied - {e["app"]}):
                cross = True
        o["cross_copy"] = cross
        o["writes"] = any(e["app"] == "payments_hub" and e["action"] == "submit" for e in ev)
        o["outward"] = any(e["app"] == "email" and e["action"] == "send" for e in ev)
        o["wait"] = (o["start"] - prev["end"]) / 60.0 if prev is not None and prev["case"] == o["case"] else None
        prev = o
    return occs


def match_status_events(data: dict, occs: list) -> dict:
    """How many status events land on a labeled occurrence of the step that posts them."""
    step_of = {r["status"]: sid for sid, r in data["register"].items() if r["status"]}
    step_of["REOPENED"] = "S01"             # a reopen is the operator opening the case again
    ends = defaultdict(list)
    for o in occs:
        ends[(o["case"], o["step"])].append(o["end"])
    total = matched = 0
    for e in data["system"]:
        if e["status"] not in step_of:
            continue                          # RECEIVED is written by the system, not by a person
        total += 1
        v = ends.get((e["case"], step_of[e["status"]]), [])
        k = bisect_left(v, e["ts"] - STATUS_TOLERANCE_S[1])
        if k < len(v) and v[k] <= e["ts"] - STATUS_TOLERANCE_S[0]:
            matched += 1
    return {"status_events": total, "matched": matched, "matched_pct": pct(matched, total)}


def step_stats(data: dict, occs: list) -> dict:
    by = defaultdict(list)
    for o in occs:
        by[o["step"]].append(o)
    out = {}
    for s in data["order"]:
        L = by.get(s, [])
        n = len(L)
        t = [o["touch"] for o in L]
        mean = statistics.mean(t) if t else 0.0
        app_min, app_actions, read_min = Counter(), defaultdict(Counter), Counter()
        for o in L:
            for e in o["events"]:
                app_min[e["app"]] += minutes(e)
                app_actions[e["app"]][e["action"]] += 1
                if e["action"] in READ_ACTIONS and e["app"] != "spreadsheet":
                    read_min[e["app"]] += minutes(e)
        waits = [o["wait"] for o in L if o["wait"] is not None]
        cases = len({o["case"] for o in L})
        out[s] = {
            "step": s, "occurrences": n, "cases": cases, "repeats": n / cases if cases else 0.0,
            "touch_hours": sum(t) / 60.0, "median_min": statistics.median(t) if t else 0.0, "mean_min": mean,
            "cv": statistics.pstdev(t) / mean if mean else 0.0,
            "text_mean": statistics.mean(o["chars"] for o in L) if L else 0.0,
            "override_rate": sum(o["override"] for o in L) / n if n else 0.0,
            "cross_copy_rate": sum(o["cross_copy"] for o in L) / n if n else 0.0,
            "write_rate": sum(o["writes"] for o in L) / n if n else 0.0,
            "outward_rate": sum(o["outward"] for o in L) / n if n else 0.0,
            "wait_median": statistics.median(waits) if waits else 0.0,
            "app_min": dict(app_min), "app_actions": {a: dict(c) for a, c in app_actions.items()},
            "main_app": app_min.most_common(1)[0][0] if app_min else "",
            "read_app": read_min.most_common(1)[0][0] if read_min else "",
        }
    return out


# ---------------------------------------------------------------------------
# 2. Classify (observable features and the register only; never the answer key)
# ---------------------------------------------------------------------------
def classify(stat: dict, reg: dict) -> tuple:
    if reg["control"]:
        return "HUMAN_CONTROL", ["the register marks it as a four-eyes control"]
    evidence = []
    if stat["override_rate"] >= JUDGE_OVERRIDE:
        evidence.append(f"workers override a proposed value in {pct(stat['override_rate'], 1, 0):.0f}% of runs")
    if stat["text_mean"] >= JUDGE_TEXT:
        evidence.append(f"{stat['text_mean']:.0f} characters of free text per run")
    if stat["repeats"] >= JUDGE_REPEAT:
        evidence.append(f"repeats {stat['repeats']:.1f} times per case")
    if stat["cv"] >= JUDGE_CV:
        evidence.append(f"touch time varies a lot (spread {stat['cv']:.2f} of the mean)")
    if len(evidence) >= JUDGE_NEED:
        return "HUMAN_JUDGMENT", evidence
    gates = []
    if stat["write_rate"] >= HITL_WRITE:
        gates.append("writes to the payments hub")
    if stat["outward_rate"] >= HITL_OUTWARD:
        gates.append("sends email outside the bank")
    if stat["override_rate"] >= HITL_OVERRIDE:
        gates.append(f"workers override it in {pct(stat['override_rate'], 1, 0):.0f}% of runs")
    if stat["text_mean"] >= HITL_TEXT:
        gates.append(f"{stat['text_mean']:.0f} characters of free text per run")
    if gates:
        return "AGENT_HITL", gates
    why = [f"fixed timing (spread {stat['cv']:.2f} of the mean)", "no overrides to speak of", "no free text to speak of"]
    if stat["cross_copy_rate"] >= 0.5:
        why.append(f"moves values between applications in {pct(stat['cross_copy_rate'], 1, 0):.0f}% of runs")
    return "AGENT", why


def classify_all(register: dict, stats: dict) -> dict:
    out = {}
    for s, st in stats.items():
        cls, why = classify(st, register[s])
        out[s] = {"class": cls, "reasons": why}
    return out


# ---------------------------------------------------------------------------
# 3. Control screen
# ---------------------------------------------------------------------------
def control_screen(classes: dict, register: dict) -> dict:
    out = {}
    for s, c in classes.items():
        r, notes = register[s], []
        if c["class"] == "HUMAN_CONTROL":
            status = "blocked: stays with a person (four-eyes)"
        elif c["class"] == "HUMAN_JUDGMENT":
            status = "left to a person: judgment"
        else:
            status = "clear"
            if r["restricted"]:
                notes.append("restricted data: scoped read access, every hit logged, no raw hits in agent output; scope review before build")
            if r["gated_by"]:
                notes.append(f"runs only after {r['gated_by']} is approved by a different person; the agent never approves its own work")
            if notes:
                status = "conditioned"
        out[s] = {"status": status, "notes": notes}
    return out


# ---------------------------------------------------------------------------
# 4. Rank
# ---------------------------------------------------------------------------
def rank_candidates(classes: dict, stats: dict, register: dict, screen: dict) -> list:
    rows = []
    for s, c in classes.items():
        if c["class"] not in AGENT_READY:
            continue
        hours = stats[s]["touch_hours"] * REMOVAL_SHARE
        rows.append({"step": s, "name": register[s]["name"], "class": c["class"], "readiness": READINESS[c["class"]],
                     "touch_hours": stats[s]["touch_hours"], "hours_at_stake": hours,
                     "score": hours * READINESS[c["class"]], "screen": screen[s]["status"], "notes": screen[s]["notes"]})
    rows.sort(key=lambda r: (-r["score"], r["step"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


# ---------------------------------------------------------------------------
# 5. Build briefs
# ---------------------------------------------------------------------------
BRIEF_KEYS = ["schema", "brief_id", "candidate", "scope", "inputs", "tools", "controls", "acceptance", "test_plan",
              "rollout", "handoff", "estimate"]


def build_packs(top: list, order: list, classes: dict) -> list:
    """Adjacent top-10 steps in workflow order form a pack of at most three; a person-only step ends a pack."""
    in_top = {r["step"]: r for r in top}
    packs, cur = [], []
    for s in order:
        if s in in_top and classes[s]["class"] in AGENT_READY and len(cur) < 3:
            cur.append(s)
        else:
            if cur:
                packs.append(cur)
            cur = [s] if (s in in_top and classes[s]["class"] in AGENT_READY) else []
    if cur:
        packs.append(cur)
    out = []
    for p in packs:
        out.append({"steps": p, "score": sum(in_top[s]["score"] for s in p), "hours": sum(in_top[s]["hours_at_stake"] for s in p)})
    out.sort(key=lambda x: (-x["score"], x["steps"]))
    return out


def tools_for(steps: list, stats: dict) -> list:
    """Tools and verbs for a pack. The spreadsheet hop disappears (the agent passes values directly), the clipboard
    becomes 'write_fields', and anything outward (send) or an override stays with a person."""
    tools = {}
    for s in steps:
        for app, actions in stats[s]["app_actions"].items():
            if app == "spreadsheet":
                continue
            verbs = tools.setdefault(app, set())
            for a in actions:
                if a in ("read", "open", "copy"):
                    verbs.add("read")
                elif a == "search":
                    verbs.add("search")
                elif a in ("paste", "type", "edit_cell"):
                    verbs.add("write_fields")
                elif a == "select":
                    verbs.add("select_option" if app == "case_system" else "read")
                elif a == "submit":
                    verbs.add({"payments_hub": "submit_after_approval", "screening_app": "log_hit"}.get(app, "submit"))
    rows = []
    for app, verbs in sorted(tools.items()):
        write = bool(verbs & {"write_fields", "select_option", "submit", "submit_after_approval", "log_hit"})
        rows.append({"name": app, "access": "write" if write else "read", "allowed_actions": sorted(verbs)})
    return rows


def make_brief(n: int, pack: dict, data: dict, stats: dict, classes: dict) -> dict:
    reg, steps = data["register"], pack["steps"]
    hitl = [s for s in steps if classes[s]["class"] == "AGENT_HITL"]
    names = [reg[s]["name"] for s in steps]
    tool_rows = tools_for(steps, stats)
    inputs = [{"name": reg[s]["name"], "source": APP_LABEL[stats[s]["read_app"] or stats[s]["main_app"]], "fields": reg[s]["fields"]} for s in steps]
    gates = []
    for s in hitl:
        gates.append({"step": s, "reason": "; ".join(classes[s]["reasons"]),
                      "approver_role": "approver" if reg[s]["gated_by"] else "operator"})
    four = []
    for s in steps:
        if reg[s]["gated_by"]:
            four.append({"step": s, "rule": f"Runs only after {reg[s]['gated_by']} is approved by a person other than the one who drafted; the agent never approves its own work."})
    order = data["order"]
    nxt = [order[order.index(s) + 1] for s in steps if order.index(s) + 1 < len(order)]
    for s in nxt:
        if reg[s]["control"] and not any(f["step"] == s for f in four):
            four.append({"step": s, "rule": "Stays with a person who did not draft the correction; the agent only prepares what the approver reads."})
    restricted = [s for s in steps if reg[s]["restricted"]]
    sel = [
        {"id": "A1", "metric": "field agreement with the worker's saved result, shadow mode", "threshold": 0.98,
         "how_measured": "Run beside workers on golden cases and compare field by field."},
        {"id": "A2", "metric": "escalations to a person per 100 cases", "threshold": 10,
         "how_measured": "Count runs the agent hands back, from the agent's own audit log."},
        {"id": "A3", "metric": "touch-time share removed on the pack's steps", "threshold": REMOVAL_SHARE,
         "how_measured": "Task-mining touch time on the same step labels, before and after rollout."},
    ]
    if restricted:
        sel.append({"id": "A4", "metric": "restricted fields found in agent output", "threshold": 0,
                    "how_measured": "Scan every agent output for the register's restricted fields."})
    faults = ["a transposed character in the beneficiary name", "a closed account returned by the lookup",
              "a timeout from the payments hub", "a missing field in the original payment"]
    if any(s in ("S10",) for s in steps):
        faults.append("a resubmit attempted without an approval on file")
    if "S06" in steps:
        faults.append("a screening result that is empty")
    hours = pack["hours"]
    return {
        "schema": BRIEF_SCHEMA, "brief_id": f"BB-{n:03d}",
        "candidate": {"name": " + ".join(names), "workflow": "wire repair (payment exception handling)", "steps": steps,
                      "automation_class": "AGENT_HITL" if hitl else "AGENT"},
        "scope": {"in_scope": [f"{s} {reg[s]['name']}" for s in steps],
                  "out_of_scope": ["S07 judge_ambiguous_match and S13 triage_beneficiary_bank_reply: a person decides",
                                   "S09 approve_four_eyes: stays with a person",
                                   "phone calls and any work off the desktop",
                                   "sending anything outside the bank"]
                  + (["the spreadsheet hop in S04: the agent passes values between systems directly"] if "S04" in steps else [])},
        "inputs": inputs, "tools": tool_rows,
        "controls": {"hitl_gates": gates, "four_eyes": four,
                     "kill_switch": "One flag per step in the pack, read before every action. When it is off the step returns to the manual queue. The trip and return rules are designed in 25 KillSwitch.",
                     "audit": "Every read and write is logged with case id, step id, run id and the pseudonymous id of the approving person. Free text from case records is not stored in the log."},
        "acceptance": sel,
        "test_plan": {"golden_cases": 200, "fault_injections": faults, "shadow_mode_cases": 500},
        "rollout": {"stages": ["shadow: agent runs, workers keep working", "assist: agent drafts, worker confirms", "supervised: agent acts on a sample, worker audits", "scoped autonomy: agent acts, worker audits exceptions"],
                    "exit_criteria": ["A1 met on the golden cases", "A1 met on the shadow-mode cases", "no A4 finding in two weeks", "kill switch drilled once"]},
        "handoff": {"owner_role": "payments operations product owner",
                    "runbook_items": ["switch the flag off", "read the audit log for a case", "restart a stuck run", "return the step to the manual queue"],
                    "monitoring": ["field agreement", "escalations per 100 cases", "touch minutes per case on the pack's steps", "flag state"]},
        "estimate": {"hours_at_stake_modeled": round(hours, 1),
                     "assumption": f"An agent removes {int(REMOVAL_SHARE * 100)}% of a step's touch time (modeled, not measured). Hours are touch hours in the 30 days of data."},
    }


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validate_brief(b: dict) -> list:
    """Stdlib check of the build-brief/v1 shape. Returns a list of problems; empty means valid."""
    errs = []

    def keys(obj, want, where):
        if not isinstance(obj, dict):
            errs.append(f"{where}: expected an object")
            return False
        if set(obj) != set(want):
            errs.append(f"{where}: keys {sorted(obj)} do not match {sorted(want)}")
            return False
        return True

    def strs(v, where):
        if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
            errs.append(f"{where}: expected a list of strings")

    if not keys(b, BRIEF_KEYS, "brief"):
        return errs
    if b["schema"] != BRIEF_SCHEMA:
        errs.append("schema must be build-brief/v1")
    if not (isinstance(b["brief_id"], str) and len(b["brief_id"]) == 6 and b["brief_id"].startswith("BB-") and b["brief_id"][3:].isdigit()):
        errs.append("brief_id must look like BB-001")
    c = b["candidate"]
    if keys(c, ["name", "workflow", "steps", "automation_class"], "candidate"):
        if not (isinstance(c["name"], str) and isinstance(c["workflow"], str)):
            errs.append("candidate name and workflow must be strings")
        if not (isinstance(c["steps"], list) and c["steps"] and all(isinstance(s, str) and len(s) == 3 and s[0] == "S" and s[1:].isdigit() for s in c["steps"])):
            errs.append("candidate.steps must be a list of step ids such as S03")
        if c["automation_class"] not in ("AGENT", "AGENT_HITL"):
            errs.append("candidate.automation_class must be AGENT or AGENT_HITL")
    if keys(b["scope"], ["in_scope", "out_of_scope"], "scope"):
        strs(b["scope"]["in_scope"], "scope.in_scope")
        strs(b["scope"]["out_of_scope"], "scope.out_of_scope")
    for i, x in enumerate(b["inputs"] if isinstance(b["inputs"], list) else []):
        if keys(x, ["name", "source", "fields"], f"inputs[{i}]"):
            strs(x["fields"], f"inputs[{i}].fields")
    if not isinstance(b["inputs"], list):
        errs.append("inputs must be a list")
    for i, x in enumerate(b["tools"] if isinstance(b["tools"], list) else []):
        if keys(x, ["name", "access", "allowed_actions"], f"tools[{i}]"):
            if x["access"] not in ("read", "write"):
                errs.append(f"tools[{i}].access must be read or write")
            strs(x["allowed_actions"], f"tools[{i}].allowed_actions")
    if not isinstance(b["tools"], list):
        errs.append("tools must be a list")
    ctl = b["controls"]
    if keys(ctl, ["hitl_gates", "four_eyes", "kill_switch", "audit"], "controls"):
        for i, g in enumerate(ctl["hitl_gates"]):
            if keys(g, ["step", "reason", "approver_role"], f"controls.hitl_gates[{i}]"):
                if not all(isinstance(g[k], str) for k in g):
                    errs.append(f"controls.hitl_gates[{i}]: values must be strings")
        for i, g in enumerate(ctl["four_eyes"]):
            if keys(g, ["step", "rule"], f"controls.four_eyes[{i}]"):
                if not all(isinstance(g[k], str) for k in g):
                    errs.append(f"controls.four_eyes[{i}]: values must be strings")
        if not (isinstance(ctl["kill_switch"], str) and isinstance(ctl["audit"], str)):
            errs.append("controls.kill_switch and controls.audit must be strings")
    for i, a in enumerate(b["acceptance"] if isinstance(b["acceptance"], list) else []):
        if keys(a, ["id", "metric", "threshold", "how_measured"], f"acceptance[{i}]"):
            if not _is_num(a["threshold"]):
                errs.append(f"acceptance[{i}].threshold must be a number")
            if not all(isinstance(a[k], str) for k in ("id", "metric", "how_measured")):
                errs.append(f"acceptance[{i}]: id, metric and how_measured must be strings")
    if not isinstance(b["acceptance"], list) or not b["acceptance"]:
        errs.append("acceptance must be a non-empty list")
    t = b["test_plan"]
    if keys(t, ["golden_cases", "fault_injections", "shadow_mode_cases"], "test_plan"):
        if not (isinstance(t["golden_cases"], int) and not isinstance(t["golden_cases"], bool)):
            errs.append("test_plan.golden_cases must be an integer")
        if not (isinstance(t["shadow_mode_cases"], int) and not isinstance(t["shadow_mode_cases"], bool)):
            errs.append("test_plan.shadow_mode_cases must be an integer")
        strs(t["fault_injections"], "test_plan.fault_injections")
    if keys(b["rollout"], ["stages", "exit_criteria"], "rollout"):
        strs(b["rollout"]["stages"], "rollout.stages")
        strs(b["rollout"]["exit_criteria"], "rollout.exit_criteria")
    if keys(b["handoff"], ["owner_role", "runbook_items", "monitoring"], "handoff"):
        if not isinstance(b["handoff"]["owner_role"], str):
            errs.append("handoff.owner_role must be a string")
        strs(b["handoff"]["runbook_items"], "handoff.runbook_items")
        strs(b["handoff"]["monitoring"], "handoff.monitoring")
    if keys(b["estimate"], ["hours_at_stake_modeled", "assumption"], "estimate"):
        if not _is_num(b["estimate"]["hours_at_stake_modeled"]):
            errs.append("estimate.hours_at_stake_modeled must be a number")
        if not (isinstance(b["estimate"]["assumption"], str) and b["estimate"]["assumption"]):
            errs.append("estimate.assumption must be a non-empty string")
    return errs


# ---------------------------------------------------------------------------
# 6. Score and assemble
# ---------------------------------------------------------------------------
def analyze(data: dict) -> dict:
    reg, key = data["register"], data["key"]
    occs = build_occurrences(data)
    merge = match_status_events(data, occs)
    n_ev = len(data["desk"])
    n_lab = sum(1 for e in data["desk"] if e["step"])
    merge.update({"desktop_events": n_ev, "labeled": n_lab, "unlabeled_pct": pct(n_ev - n_lab, n_ev), "system_events": len(data["system"]),
                  "occurrences": len(occs), "cases": len(data["cases"])})
    stats = step_stats(data, occs)
    classes = classify_all(reg, stats)
    screen = control_screen(classes, reg)
    ranked = rank_candidates(classes, stats, reg, screen)
    top = ranked[:TOP_N]

    # key independence: shuffle the answer key in the catalog and classify again
    rows = read_csv("step_catalog.csv", DATA_DIR)
    truths = [r["truth_class"] for r in rows]
    for r, t in zip(rows, truths[5:] + truths[:5]):
        r["truth_class"] = t
    reg2, key2, _ = split_catalog(rows)
    independent = classify_all(reg2, stats) == classes and key2 != key

    # score against the key
    steps = data["order"]
    hit = [s for s in steps if classes[s]["class"] == key[s]]
    miss = [s for s in steps if classes[s]["class"] != key[s]]
    pred_ready = {s for s in steps if classes[s]["class"] in AGENT_READY}
    true_ready = {s for s in steps if key[s] in AGENT_READY}
    tp, fp, fn = len(pred_ready & true_ready), sorted(pred_ready - true_ready), sorted(true_ready - pred_ready)
    scoring = {"accuracy": len(hit), "n_steps": len(steps), "accuracy_pct": pct(len(hit), len(steps)),
               "mismatches": [{"step": s, "predicted": classes[s]["class"], "truth": key[s]} for s in miss],
               "tp": tp, "fp": fp, "fn": fn, "precision_pct": pct(tp, tp + len(fp)), "recall_pct": pct(tp, tp + len(fn)),
               "true_ready": sorted(true_ready), "pred_ready": sorted(pred_ready)}

    # the volume-first list against the same stats
    log = analyze_log(data)
    vf = log["top10"]
    hours_at_stake = {s: stats[s]["touch_hours"] * REMOVAL_SHARE for s in steps}
    oracle = sorted(true_ready, key=lambda s: (-hours_at_stake[s] * READINESS[key[s]], s))[:TOP_N]
    ss_top = [r["step"] for r in top]
    ceiling = sum(hours_at_stake[s] for s in true_ready)

    def real_hours(lst):
        return sum(hours_at_stake[s] for s in lst if s in true_ready)

    n_workers = len(data["workers"])
    lift = real_hours(ss_top) - real_hours(vf)
    compare = {"vf_top10": vf, "ss_top10": ss_top, "oracle_top10": oracle,
               "vf_ready": sum(1 for s in vf if s in true_ready), "ss_ready": sum(1 for s in ss_top if s in true_ready),
               "vf_overlap_oracle": len(set(vf) & set(oracle)), "ss_overlap_oracle": len(set(ss_top) & set(oracle)),
               "vf_real_hours": real_hours(vf), "ss_real_hours": real_hours(ss_top), "ceiling_hours": ceiling,
               "vf_share_pct": pct(real_hours(vf), ceiling), "ss_share_pct": pct(real_hours(ss_top), ceiling),
               "vf_flagged": sum(1 for s in vf if reg[s]["restricted"] or reg[s]["control"] or reg[s]["gated_by"]),
               "ss_blocked": [s for s in ss_top if screen[s]["status"].startswith(("blocked", "left"))],
               "ss_conditioned": [s for s in ss_top if screen[s]["status"] == "conditioned"],
               "vf_in_ss_top": [s for s in vf if s in ss_top]}
    utility = {"n_workers": n_workers, "ss_hours": compare["ss_real_hours"], "vf_hours": compare["vf_real_hours"], "lift_hours": lift,
               "ss_per_worker": compare["ss_real_hours"] / n_workers, "vf_per_worker": compare["vf_real_hours"] / n_workers,
               "per_worker": lift / n_workers, "removal_share": REMOVAL_SHARE}

    # handling time
    touch_all = sum(minutes(e) for e in data["desk"])
    labeled = sum(minutes(e) for e in data["desk"] if e["step"])
    case_sys = sum(minutes(e) for e in data["desk"] if e["app"] == "case_system")
    offdesk = sum(c["offdesk_min"] for c in data["cases"])
    true_h = touch_all + offdesk
    handling = {"true_hours": true_h / 60.0, "touch_hours": touch_all / 60.0, "offdesk_hours": offdesk / 60.0,
                "log_alone_pct": pct(case_sys, true_h), "merged_pct": pct(labeled, true_h),
                "recovered_pts": round(pct(labeled, true_h) - pct(case_sys, true_h), 1),
                "offdesk_pct": pct(offdesk, true_h), "unlabeled_pct": pct(touch_all - labeled, true_h)}

    # the known miss
    miss_step = next((s for s in sorted(pred_ready - true_ready)), None)
    known = None
    if miss_step:
        st = stats[miss_step]
        known = {"step": miss_step, "name": reg[miss_step]["name"], "predicted": classes[miss_step]["class"], "truth": key[miss_step],
                 "cv": st["cv"], "cv_rank": 1 + sum(1 for s in steps if stats[s]["cv"] < st["cv"]), "text_mean": st["text_mean"],
                 "override_rate": st["override_rate"], "repeats": st["repeats"], "touch_hours": st["touch_hours"],
                 "hours_at_stake": hours_at_stake[miss_step],
                 "rank": next((r["rank"] for r in ranked if r["step"] == miss_step), None),
                 "in_top10": miss_step in ss_top}

    packs = build_packs(top, data["order"], classes)
    briefs = [make_brief(i + 1, p, data, stats, classes) for i, p in enumerate(packs[:N_BRIEFS])]
    problems = {b["brief_id"]: validate_brief(b) for b in briefs}
    bad = validate_brief({**briefs[0], "estimate": {"hours_at_stake_modeled": "many", "assumption": ""}})
    return {"merge": merge, "occs": occs, "stats": stats, "classes": classes, "screen": screen, "ranked": ranked, "top": top,
            "scoring": scoring, "compare": compare, "utility": utility, "handling": handling, "known": known, "packs": packs,
            "briefs": briefs, "brief_problems": problems, "negative_check": bad, "independent": independent,
            "log": log, "deficiencies": summarize_deficiencies(data, log), "hours_at_stake": hours_at_stake}


def summarize(data: dict) -> dict:
    return analyze(data)


def step_payload(data: dict, A: dict, sid: str) -> dict:
    """Everything the demo and the app show for one step."""
    reg, key, planted = data["register"], data["key"], data["planted"]
    sme = {r["step"]: r for r in data["sme"]}
    st, cl = A["stats"][sid], A["classes"][sid]
    log = {r["step"]: r for r in A["log"]["candidates"]}
    rank = {r["step"]: r["rank"] for r in A["ranked"]}
    p = planted[sid]
    cand = next((r for r in A["ranked"] if r["step"] == sid), None)
    return {
        "id": sid, "name": reg[sid]["name"], "key": key[sid], "predicted": cl["class"], "reasons": cl["reasons"],
        "correct": cl["class"] == key[sid], "agent_ready_key": key[sid] in AGENT_READY,
        "agent_ready_pred": cl["class"] in AGENT_READY,
        "on_map": sid in sme, "sme_minutes": sme[sid]["minutes"] if sid in sme else None,
        "status": reg[sid]["status"], "log_rank": log[sid]["rank"] if sid in log else None,
        "log_volume": log[sid]["volume"] if sid in log else None,
        "log_mean_min": round(log[sid]["mean_elapsed_min"], 1) if sid in log else None,
        "log_hours": round(log[sid]["elapsed_hours"]) if sid in log else None,
        "in_vf_top10": sid in A["log"]["top10"],
        "runs": st["occurrences"], "touch_hours": round(st["touch_hours"], 1), "median_min": round(st["median_min"], 1),
        "spread": round(st["cv"], 2), "repeats": round(st["repeats"], 2), "text": round(st["text_mean"]),
        "override_pct": round(100 * st["override_rate"]), "xcopy_pct": round(100 * st["cross_copy_rate"]),
        "wait_median": round(st["wait_median"]), "main_app": APP_LABEL[st["main_app"]],
        "apps": {APP_LABEL[a]: round(m / 60.0, 1) for a, m in sorted(st["app_min"].items(), key=lambda kv: -kv[1])},
        "restricted": reg[sid]["restricted"], "control": reg[sid]["control"], "gated_by": reg[sid]["gated_by"],
        "screen": A["screen"][sid]["status"], "screen_notes": A["screen"][sid]["notes"],
        "planted": {"override_pct": round(100 * p["override"]), "text": round(p["text"]), "offdesk_pct": round(100 * p["offdesk_share"]),
                    "xcopy_pct": round(100 * p["cross_app"]), "median_min": p["median_touch_min"],
                    "repeats": p["repeats"]},
        "hours_at_stake": round(A["hours_at_stake"][sid], 1) if cl["class"] in AGENT_READY else 0.0,
        "readiness": READINESS.get(cl["class"], 0.0), "ss_rank": rank.get(sid), "in_ss_top10": bool(cand and cand["rank"] <= TOP_N),
    }


# ---------------------------------------------------------------------------
def main() -> None:
    data = load_all()
    A = analyze(data)
    reg, key = data["register"], data["key"]
    M, st, cl, sc, cp, ut, hd = A["merge"], A["stats"], A["classes"], A["scoring"], A["compare"], A["utility"], A["handling"]
    print("=" * 112)
    print("Step 4 - StepScout: merge, classify, screen, rank, brief")
    print("=" * 112)
    print("\n1. MERGE desktop and system events")
    print(f"   {M['desktop_events']:,} desktop events ({M['unlabeled_pct']}% the miner could not label) and {M['system_events']:,} status events "
          f"on {M['cases']:,} cases -> {M['occurrences']:,} step occurrences.")
    print(f"   Status events (written by a person) that land on a labeled occurrence of the right step: {M['matched']:,} of {M['status_events']:,} ({M['matched_pct']}%).")

    print("\n2. CLASSIFY from observable features (the register supplies the control flags; the answer key is not read)")
    print(f"   Judgment if at least {JUDGE_NEED} of: overrides >= {int(JUDGE_OVERRIDE * 100)}%, free text >= {JUDGE_TEXT:.0f} characters, "
          f"repeats >= {JUDGE_REPEAT}, timing spread >= {JUDGE_CV}.")
    print(f"   Agent with a person (HITL) if: writes to the hub, sends email, overrides >= {int(HITL_OVERRIDE * 100)}%, or free text >= {HITL_TEXT:.0f} characters.")
    print(f"\n   {'step':<4} {'name':<30} {'runs':>5} {'touch h':>8} {'med min':>7} {'spread':>6} {'rpt':>4} {'text':>5} {'ovr%':>5} {'xcopy%':>6}  class")
    for s in data["order"]:
        x = st[s]
        print(f"   {s:<4} {reg[s]['name']:<30} {x['occurrences']:>5,} {x['touch_hours']:>8.1f} {x['median_min']:>7.1f} {x['cv']:>6.2f} "
              f"{x['repeats']:>4.2f} {x['text_mean']:>5.0f} {100 * x['override_rate']:>5.1f} {100 * x['cross_copy_rate']:>6.1f}  {cl[s]['class']}")

    print("\n3. CONTROL SCREEN")
    for s in data["order"]:
        if A["screen"][s]["status"] != "clear":
            print(f"   {s} {reg[s]['name']}: {A['screen'][s]['status']}")
            for n in A["screen"][s]["notes"]:
                print(f"       - {n}")

    print(f"\n4. RANKED CANDIDATES: modeled hours at stake x readiness (assumption: an agent removes {int(REMOVAL_SHARE * 100)}% of a step's touch time)")
    print(f"   {'rank':>4} {'step':<4} {'name':<30} {'class':<11} {'ready':>5} {'touch h':>8} {'hours at stake (modeled)':>25} {'score':>7}")
    for r in A["ranked"]:
        mark = "  <- top 10" if r["rank"] <= TOP_N else ""
        print(f"   {r['rank']:>4} {r['step']:<4} {r['name']:<30} {r['class']:<11} {r['readiness']:>5.1f} {r['touch_hours']:>8.1f} "
              f"{r['hours_at_stake']:>25.1f} {r['score']:>7.1f}{mark}")

    print("\n5. SCORED AGAINST THE ANSWER KEY (the generator's own key)")
    print(f"   Classification accuracy: {sc['accuracy']} of {sc['n_steps']} steps ({sc['accuracy_pct']}%).")
    for m in sc["mismatches"]:
        print(f"      {m['step']} {reg[m['step']]['name']}: predicted {m['predicted']}, key says {m['truth']}")
    print(f"   Agent-ready steps (AGENT or AGENT_HITL): precision {sc['precision_pct']}% ({sc['tp']} of {sc['tp'] + len(sc['fp'])} predicted), "
          f"recall {sc['recall_pct']}% ({sc['tp']} of {sc['tp'] + len(sc['fn'])} true).")
    print(f"   Key independence check: shuffling the answer key leaves every class unchanged: {'yes' if A['independent'] else 'NO'}.")
    print(f"\n   Top {TOP_N} compared:")
    print(f"      volume-first list : {cp['vf_ready']} of {TOP_N} agent-ready; {cp['vf_flagged']} touch restricted data or a four-eyes control; "
          f"overlap with the best possible ten {cp['vf_overlap_oracle']}")
    print(f"      StepScout         : {cp['ss_ready']} of {TOP_N} agent-ready; overlap with the best possible ten {cp['ss_overlap_oracle']}; "
          f"blocked or left to a person: {len(cp['ss_blocked'])}; conditioned: {', '.join(cp['ss_conditioned']) or 'none'}")
    print(f"      Real hours at stake in the list (agent-ready steps only): volume-first {cp['vf_real_hours']:.0f} h "
          f"({cp['vf_share_pct']}% of the {cp['ceiling_hours']:.0f} h ceiling), StepScout {cp['ss_real_hours']:.0f} h ({cp['ss_share_pct']}%)")
    print(f"\n   {'pos':>3}  {'volume-first top 10':<33} {'ready':<6} {'StepScout top 10':<33} {'ready':<6}")
    for i, (a, b) in enumerate(zip(cp["vf_top10"], cp["ss_top10"]), 1):
        fa = "yes" if key[a] in AGENT_READY else "NO"
        fb = "yes" if key[b] in AGENT_READY else "NO"
        print(f"   {i:>3}  {a + ' ' + reg[a]['name']:<33} {fa:<6} {b + ' ' + reg[b]['name']:<33} {fb:<6}")
    print(f"\n   Handling time (desktop touch plus off-desktop work, {hd['true_hours']:,.0f} h in all):")
    print(f"      the case-system log alone can attribute at most {hd['log_alone_pct']}% (time spent in the case system; it records timestamps, not durations)")
    print(f"      the merged view attributes {hd['merged_pct']}% to a named step: {hd['recovered_pts']} points recovered")
    print(f"      still unseen: {hd['offdesk_pct']}% off the desktop (phone calls), {hd['unlabeled_pct']}% on the desktop but not labeled")

    k = A["known"]
    print("\nWHAT IT STILL GETS WRONG (known miss, left in on purpose)")
    if k:
        print(f"   {k['step']} {k['name']}: classified {k['predicted']}, the key says {k['truth']}.")
        tight = "the tightest of the " + str(len(data["order"])) + " steps" if k["cv_rank"] == 1 else f"number {k['cv_rank']} of {len(data['order'])} from the tightest"
        print(f"   On the desktop it looks rule-based: timing spread {k['cv']:.2f} ({tight}), {k['text_mean']:.0f} characters of text, "
              f"overrides in {100 * k['override_rate']:.0f}% of runs, {k['repeats']:.1f} run per case.")
        print(f"   The judgment happens in a phone call before the pick, and no file records the call. Ranked #{k['rank']} with {k['hours_at_stake']:.1f} modeled hours at stake"
              f"{' (inside the top 10)' if k['in_top10'] else ' (outside the top 10)'}.")
    print(f"   Work off the desktop stays invisible: {hd['offdesk_hours']:.0f} hours of calls in the data ({hd['offdesk_pct']}% of handling time), plus {hd['unlabeled_pct']}% on the desktop that the miner could not label.")
    print("   Task mining of employee desktops is a privacy and works-council question this prototype only designs for (pseudonymous ids,")
    print("   no keystroke content, aggregate views): designed, not built.")
    print("   The classes are scored against a key whose signals I planted, so accuracy shows the method works on this data, not on a real queue.")

    print("\n6. BUILD BRIEFS (build-brief/v1, validated with a stdlib check)")
    OUT_DIR.mkdir(exist_ok=True)
    for b in A["briefs"]:
        errs = A["brief_problems"][b["brief_id"]]
        (OUT_DIR / f"{b['brief_id']}.json").write_text(json.dumps(b, indent=2), encoding="utf-8")
        print(f"   {b['brief_id']}  {', '.join(b['candidate']['steps']):<14} {b['candidate']['automation_class']:<10} "
              f"{b['estimate']['hours_at_stake_modeled']:>6} modeled hours  valid: {'yes' if not errs else 'NO ' + '; '.join(errs)}")
    print(f"   Negative check: a brief with a bad estimate is rejected with {len(A['negative_check'])} problems.")

    print("\nUTILITY (modeled)")
    print(f"   Agent-ready hours at stake in the list a team would build from: StepScout {ut['ss_hours']:.0f} h, volume-first {ut['vf_hours']:.0f} h "
          f"({ut['ss_per_worker']:.1f} and {ut['vf_per_worker']:.1f} per worker per 30 days, {ut['n_workers']} workers).")
    print(f"   ({ut['ss_per_worker']:.1f} - {ut['vf_per_worker']:.1f}) = {ut['per_worker']:.1f} hours per worker per 30 days; "
          f"x {ut['n_workers']} workers = {ut['lift_hours']:.0f} hours per 30 days. Assumption: both teams build their top {TOP_N} and an agent removes {int(REMOVAL_SHARE * 100)}% of touch time.")

    rows = [[r["rank"], r["step"], r["name"], r["class"], r["readiness"], round(r["touch_hours"], 1), round(r["hours_at_stake"], 1),
             round(r["score"], 1), r["screen"]] for r in A["ranked"]]
    with open(OUT_DIR / "step_04_candidates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rank", "step_id", "name", "class", "readiness", "touch_hours_30d", "hours_at_stake_modeled", "score", "control_screen"])
        w.writerows(rows)
    with open(OUT_DIR / "step_04_steps.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["step_id", "name", "runs", "touch_hours", "median_min", "timing_spread", "repeats", "text_chars", "override_pct",
                    "cross_app_copy_pct", "predicted_class", "reason"])
        for s in data["order"]:
            x = st[s]
            w.writerow([s, reg[s]["name"], x["occurrences"], round(x["touch_hours"], 1), round(x["median_min"], 2), round(x["cv"], 3),
                        round(x["repeats"], 2), round(x["text_mean"]), round(100 * x["override_rate"], 1),
                        round(100 * x["cross_copy_rate"], 1), cl[s]["class"], cl[s]["reasons"][0]])
    summ = {"merge": A["merge"], "scoring": sc, "compare": cp, "utility": ut, "handling": hd, "known": k,
            "independent": A["independent"], "top10": [r["step"] for r in A["top"]],
            "briefs": [{"id": b["brief_id"], "steps": b["candidate"]["steps"], "hours": b["estimate"]["hours_at_stake_modeled"]} for b in A["briefs"]]}
    (OUT_DIR / "step_04_summary.json").write_text(json.dumps(summ, indent=2, default=str), encoding="utf-8")
    print("\nWrote src/out/step_04_steps.csv, step_04_candidates.csv, step_04_summary.json and the build briefs")


if __name__ == "__main__":
    main()
