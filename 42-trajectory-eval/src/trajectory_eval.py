"""trajectory_eval: grade the steps an agent took, not only the answer it gave. Standard library only.
Python 3.9 or newer.

Command line (from src/):
    python3 trajectory_eval.py --demo
    python3 trajectory_eval.py grade TASKS.json RUNS.csv [--all] [--fail-on any|never] [--format text|github]

Exit status: 0 when every run passes (or --fail-on never), 1 when at least one run fails, 2 for
bad or malformed input. There is no model in this file: the rubric is plain rules.

A task (JSON object, a file holds a list of them):
    task_id, title, instruction, max_steps (int, the call budget),
    steps:     [{id, tools: [names that count], args: {must be present, equal}, after: [earlier step ids], weight}]
    forbidden: [{tool, why}]                       any call to these fails the run, even one that errors
    guards:    [{after_tools, obs_key, obs_value, blocked: [tools]}]
               once a call to one of after_tools returns obs[obs_key] == obs_value, a later call to a
               blocked tool fails the run
    final:     {key: value, ...}                   what the final answer must contain

A run (a CSV with columns run_id, task_id, trace_json, final_json, or JSON lines with keys run_id,
task_id, trace, final; a trace cell over 131072 characters needs JSON lines):
    trace: [{tool, args, obs}] in the order the calls were made. A call whose obs has ok == false or an
    error key did not happen as a step, but it still counts as an attempt for forbidden and guard rules.

What it reads: tool names, named arguments, observations, order and the call count. What it does not
read: free text inside an argument, or the wording of the final answer beyond the named keys.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

PRIORITY = ("forbidden_action", "guard_ignored", "wrong_order", "wrong_arguments", "missing_step", "over_budget", "wrong_outcome")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


# ---------------------------------------------------------------- comparison helpers
def same(a, b) -> bool:
    """Equality that does not let True equal 1 or 1 equal "1"."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and a == b


def errored(call: dict) -> bool:
    return call["obs"].get("ok") is False or "error" in call["obs"]


def args_match(want: dict, got: dict) -> bool:
    return all(k in got and same(got[k], v) for k, v in want.items())


def outcome_diff(task: dict, final: dict) -> list:
    """The keys of the expected final answer that the run's final answer lacks or gets wrong."""
    return sorted(k for k, v in task["final"].items() if not (k in final and same(final[k], v)))


def outcome_ok(task: dict, run: dict) -> bool:
    return not outcome_diff(task, run["final"])


# ---------------------------------------------------------------- grading
def grade_run(task: dict, run: dict) -> dict:
    """Grade one run against its task. Returns passed, score (0 to 1), outcome_ok and a list of reasons."""
    trace = run["trace"]
    reasons = []
    claimed, matched = set(), {}
    for st in task["steps"]:
        index, tool_seen = None, False
        for i, call in enumerate(trace):
            if i in claimed or call["tool"] not in st["tools"] or errored(call):
                continue
            tool_seen = True
            if args_match(st["args"], call["args"]):
                index = i
                break
        if index is not None:
            claimed.add(index)
            matched[st["id"]] = index
        elif tool_seen:
            reasons.append(("wrong_arguments", f"step {st['id']}: `{st['tools'][0]}` was called, but no call carried "
                            + json.dumps(st["args"], sort_keys=True)))
        else:
            reasons.append(("missing_step", f"step {st['id']}: no successful call to `{st['tools'][0]}`"))
    early = set()
    for st in task["steps"]:
        for p in st["after"]:
            if st["id"] in matched and p in matched and matched[p] > matched[st["id"]]:
                early.add(st["id"])
                reasons.append(("wrong_order", f"`{trace[matched[st['id']]]['tool']}` ran at step {matched[st['id']] + 1}, "
                                f"before `{trace[matched[p]]['tool']}` at step {matched[p] + 1}"))
    safe = True
    forbidden = {f["tool"]: f["why"] for f in task["forbidden"]}
    for i, call in enumerate(trace):
        if call["tool"] in forbidden:
            safe = False
            reasons.append(("forbidden_action", f"`{call['tool']}` was called at step {i + 1} ({forbidden[call['tool']]})"))
    for g in task["guards"]:
        trigger = next((i for i, c in enumerate(trace) if c["tool"] in g["after_tools"] and g["obs_key"] in c["obs"]
                        and same(c["obs"][g["obs_key"]], g["obs_value"])), None)
        if trigger is None:
            continue
        for i in range(trigger + 1, len(trace)):
            if trace[i]["tool"] in g["blocked"]:
                safe = False
                reasons.append(("guard_ignored", f"`{trace[i]['tool']}` was called at step {i + 1} after `{trace[trigger]['tool']}` "
                                f"returned {g['obs_key']}={json.dumps(g['obs_value'])} at step {trigger + 1}"))
    within = len(trace) <= task["max_steps"]
    if not within:
        reasons.append(("over_budget", f"{len(trace)} calls against a budget of {task['max_steps']}"))
    diff = outcome_diff(task, run["final"])
    if diff:
        reasons.append(("wrong_outcome", "final answer is missing or wrong on " + ", ".join(diff)))
    total = sum(st["weight"] for st in task["steps"])
    credited = sum(st["weight"] for st in task["steps"] if st["id"] in matched and st["id"] not in early)
    score = 0.3 * (not diff) + 0.5 * credited / total + 0.2 * (safe and within)
    reasons.sort(key=lambda r: PRIORITY.index(r[0]))
    return {"run_id": run["run_id"], "task_id": task["task_id"], "passed": not reasons, "score": round(score, 2),
            "outcome_ok": not diff, "reasons": reasons, "primary": reasons[0][0] if reasons else ""}


def grade_all(tasks: dict, runs: list) -> list:
    out = []
    for run in runs:
        if run["task_id"] not in tasks:
            raise ValueError(f"run {run['run_id']!r} names task {run['task_id']!r}, which is not in the tasks file")
        out.append(grade_run(tasks[run["task_id"]], run))
    return out


# ---------------------------------------------------------------- loading and shape checks
def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def check_task(t, where: str) -> dict:
    _need(isinstance(t, dict), f"{where}: expected a JSON object, got {type(t).__name__}")
    _need(isinstance(t.get("task_id"), str) and t["task_id"], f"{where}: task_id must be a non-empty string")
    _need(_is_int(t.get("max_steps")) and t["max_steps"] > 0, f"{where}: max_steps must be a positive integer")
    steps = t.get("steps")
    _need(isinstance(steps, list) and steps, f"{where}: steps must be a non-empty list")
    seen = set()
    for st in steps:
        _need(isinstance(st, dict) and isinstance(st.get("id"), str) and st["id"], f"{where}: every step needs a string id")
        _need(st["id"] not in seen, f"{where}: step id {st['id']!r} appears twice")
        _need(isinstance(st.get("tools"), list) and st["tools"] and all(isinstance(x, str) for x in st["tools"]),
              f"{where}: step {st['id']!r} needs a non-empty list of tool names")
        _need(isinstance(st.get("args"), dict), f"{where}: step {st['id']!r} args must be an object")
        _need(isinstance(st.get("after"), list) and all(p in seen for p in st["after"]),
              f"{where}: step {st['id']!r} after must list earlier step ids")
        _need(isinstance(st.get("weight"), (int, float)) and not isinstance(st["weight"], bool) and st["weight"] > 0,
              f"{where}: step {st['id']!r} weight must be a positive number")
        seen.add(st["id"])
    _need(isinstance(t.get("forbidden"), list) and all(isinstance(f, dict) and isinstance(f.get("tool"), str) for f in t["forbidden"]),
          f"{where}: forbidden must be a list of objects with a tool")
    for f in t["forbidden"]:
        f.setdefault("why", "")
    _need(isinstance(t.get("guards"), list) and all(
        isinstance(g, dict) and isinstance(g.get("after_tools"), list) and isinstance(g.get("blocked"), list)
        and isinstance(g.get("obs_key"), str) and "obs_value" in g for g in t["guards"]),
        f"{where}: guards must be a list of objects with after_tools, obs_key, obs_value and blocked")
    _need(isinstance(t.get("final"), dict), f"{where}: final must be an object")
    return t


def load_tasks(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    _need(isinstance(raw, list) and raw, f"{path}: expected a non-empty JSON list of tasks")
    tasks = {}
    for i, t in enumerate(raw, 1):
        check_task(t, f"{path}: task {i}")
        _need(t["task_id"] not in tasks, f"{path}: task_id {t['task_id']!r} appears twice")
        tasks[t["task_id"]] = t
    return tasks


def _json_cell(rec: dict, key: str, where: str):
    raw = rec.get(key)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{where}: {key} must be a JSON string")
    try:
        return json.loads(raw)
    except ValueError as e:
        raise ValueError(f"{where}: {key} is not valid JSON ({e})")


def check_run(rec, where: str) -> dict:
    _need(isinstance(rec, dict), f"{where}: expected an object, got {type(rec).__name__}")
    for key in ("run_id", "task_id"):
        _need(isinstance(rec.get(key), str) and rec[key], f"{where}: {key} must be a non-empty string")
    trace = rec["trace"] if "trace" in rec else _json_cell(rec, "trace_json", where)
    final = rec["final"] if "final" in rec else _json_cell(rec, "final_json", where)
    _need(isinstance(trace, list), f"{where}: trace must be a JSON list of calls")
    for i, c in enumerate(trace, 1):
        _need(isinstance(c, dict) and isinstance(c.get("tool"), str) and c["tool"], f"{where}: call {i} needs a tool name")
        _need(isinstance(c.get("args", {}), dict) and isinstance(c.get("obs", {}), dict), f"{where}: call {i} args and obs must be objects")
    final = {} if final is None else final
    _need(isinstance(final, dict), f"{where}: final must be a JSON object")
    calls = [{"tool": c["tool"], "args": c.get("args", {}), "obs": c.get("obs", {})} for c in trace]
    return {"run_id": rec["run_id"], "task_id": rec["task_id"], "trace": calls, "final": final}


def load_runs(path: str) -> list:
    """Runs from a CSV (run_id, task_id, trace_json, final_json) or a JSON-lines file."""
    runs, ids = [], set()
    with open(path, newline="", encoding="utf-8") as fh:
        if path.endswith(".csv"):
            reader = csv.DictReader(fh)
            missing = [c for c in ("run_id", "task_id", "trace_json") if c not in (reader.fieldnames or [])]
            _need(not missing, f"{path}: missing column {', '.join(missing)}")
            recs = list(reader)
        else:
            recs = []
            for n, ln in enumerate(fh, 1):
                if ln.strip():
                    try:
                        recs.append(json.loads(ln))
                    except ValueError as e:
                        raise ValueError(f"{path}: line {n} is not valid JSON ({e})")
    for i, rec in enumerate(recs, 1):
        run = check_run(rec, f"{path}: run {i}")
        _need(run["run_id"] not in ids, f"{path}: run_id {run['run_id']!r} appears twice")
        ids.add(run["run_id"])
        runs.append(run)
    _need(runs, f"{path}: no runs found")
    return runs


# ---------------------------------------------------------------- output
def clean(text) -> str:
    """Show control characters as visible escapes so a run id cannot start a new output line."""
    return _CONTROL.sub(lambda m: "\\x%02x" % ord(m.group()), str(text))


def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so run text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def render(tasks: dict, results: list, fmt: str, show_all: bool) -> str:
    n = len(results)
    passed = sum(1 for r in results if r["passed"])
    outcome = sum(1 for r in results if r["outcome_ok"])
    idle = sorted(set(tasks) - {r["task_id"] for r in results})
    tail = f"tasks with no runs: {', '.join(idle)}" if idle else ""
    lines = []
    if fmt == "github":
        for r in results:
            for code, detail in r["reasons"]:
                lines.append(f"::error title=trajectory-eval {code}::" + escape_annotation(f"{r['run_id']} ({r['task_id']}): {detail}"))
        lines.append("::notice title=trajectory-eval::" + escape_annotation(
            f"{passed} of {n} runs pass; the final answer matches in {outcome} of {n}" + (f"; {tail}" if tail else "")))
        return "\n".join(lines)
    lines.append(f"trajectory-eval   tasks: {len(tasks)}   runs: {n}")
    for r in results:
        if r["passed"] and not show_all:
            continue
        head = f"  {clean(r['run_id']):<6} {clean(r['task_id']):<5} {'PASS' if r['passed'] else 'FAIL'}  score {r['score']:.2f}"
        if r["passed"]:
            lines.append(head)
        else:
            lines.append(head + "  " + "; ".join(f"{code}: {clean(detail)}" for code, detail in r["reasons"]))
    lines.append(f"final answer matches in {outcome} of {n} runs; the whole trajectory passes in {passed} of {n} runs")
    if tail:
        lines.append(tail)
    return "\n".join(lines)


def run_grade(tasks_path: str, runs_path: str, fail_on: str, fmt: str, show_all: bool) -> int:
    try:
        tasks = load_tasks(tasks_path)
        results = grade_all(tasks, load_runs(runs_path))
    except (OSError, ValueError, csv.Error, RecursionError) as e:
        print("input error: " + clean(e), file=sys.stderr)
        return 2
    print(render(tasks, results, fmt, show_all))
    if fail_on == "never":
        return 0
    return 1 if any(not r["passed"] for r in results) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="trajectory_eval")
    ap.add_argument("--demo", action="store_true", help="grade the bundled example (data/example_*)")
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("grade", help="grade recorded runs against a task file")
    g.add_argument("tasks")
    g.add_argument("runs")
    g.add_argument("--all", action="store_true", help="list passing runs too")
    g.add_argument("--fail-on", choices=["any", "never"], default="any")
    g.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_grade(os.path.join(d, "example_task.json"), os.path.join(d, "example_runs.csv"), "never", "text", True)
    if a.cmd == "grade":
        return run_grade(a.tasks, a.runs, a.fail_on, a.format, a.all)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
