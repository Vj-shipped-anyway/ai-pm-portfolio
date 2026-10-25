"""atlas_case_study: turn the trace of one agent run into a draft case study in the shape the MITRE ATLAS
contribution schema describes. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 atlas_case_study.py --demo
    python3 atlas_case_study.py build BUNDLE.json [--reporter TEXT] [--yaml FILE] [--json FILE]
    python3 atlas_case_study.py lint STUDY.json [--bundle BUNDLE.json] [--strict]

Exit status: 0 when the command did what it was asked, 1 when the tool found a problem (no loop in the trace, or
lint found a schema error or a leaked identifier; with --strict also an unfinished field), 2 for missing,
malformed or wrongly shaped input.

A bundle is JSON: {"identifier_keys": [...], "synthetic": true|false, "run": {run_id, agent_id, agent_role,
customer_id, started_at, cost_cap_usd}, "calls": [{tool_name, args, response_kind, response_flag, cost_usd}]}.
identifier_keys names the fields (in run and in every call's args) whose values must never reach a public draft;
values shorter than 4 characters are ignored.

What the tool does is plain rules, with no model in it:
  1. split the calls into phases: runs of consecutive calls with the same tool and the same argument shape
     (key names and value types);
  2. a phase of LOOP_MIN_CALLS or more calls where NON_OK_SHARE or more of the responses are not "ok" is a loop;
  3. each loop becomes a Denial of AI Service step; an instruction-like response (flagged upstream) on the call
     before the loop or the first call of it adds an Indirect prompt injection step; the call where cumulative
     cost reaches the run's cap adds a Cost Harvesting step;
  4. the ticket note is never copied; actor, reporter and references stay marked TODO for a person.
The two thresholds are assumptions of mine, not values from ATLAS. The tactic and technique ids below were read
in the ATLAS 2026.09 release (https://github.com/mitre-atlas/atlas-data, dist/v6/ATLAS-2026.09.yaml, read
2026-10-24). The schema rules in lint come from dist/schemas/atlas_contribution_schema.json, same date. Object
forms of tactic and technique are accepted without being checked.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import sys

LOOP_MIN_CALLS = 20
NON_OK_SHARE = 0.9
SCRUB_MIN_DIGITS = 5
MIN_ID_LEN = 4
DIGITS = r"\d{%d,}" % SCRUB_MIN_DIGITS
REDACTED = "[redacted]"

TACTICS = {"AML.TA0005": "Execution", "AML.TA0011": "Impact"}
TECHNIQUES = {
    "AML.T0029": ("Denial of AI Service", "AML.TA0011"),
    "AML.T0034": ("Cost Harvesting", "AML.TA0011"),
    "AML.T0051.001": ("LLM Prompt Injection: Indirect", "AML.TA0005"),
}

STUDY_KEYS = {"name", "summary", "incident-date", "incident-date-granularity", "procedure", "reporter", "target", "actor",
              "case-study-type", "references", "id", "object-type", "reported-by"}
STUDY_REQUIRED = ["name", "summary", "incident-date", "incident-date-granularity", "procedure"]
TACTIC_RE = re.compile(r"^(?:[A-Z]+\d*\.)+TA\d{4}$")
TECHNIQUE_RE = re.compile(r"^(?:[A-Z]+\d*\.)+T\d{4}(?:\.\d{3})?$")
CASE_ID_RE = re.compile(r"^(?:[A-Z]+\d*\.)+CS\d{4}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


# ---------------------------------------------------------------- safe output
def safe(text, limit: int = 80) -> str:
    """Make untrusted text safe to print on one line: control characters and non-ASCII become escapes."""
    s = str(text)
    out = "".join(c if c.isascii() and c.isprintable() else c.encode("unicode_escape").decode("ascii") for c in s)
    return out if len(out) <= limit else out[:limit - 3] + "..."


# ---------------------------------------------------------------- identifiers
def keys_by_value(bundle: dict) -> dict:
    """{identifier value: set of identifier keys it was stored under}, from the run and from every call's args."""
    keys = set(bundle["identifier_keys"])
    out = {}
    pairs = list(bundle["run"].items()) + [kv for c in bundle["calls"] for kv in c["args"].items()]
    for k, v in pairs:
        if k in keys and isinstance(v, (str, int)) and not isinstance(v, bool) and len(str(v)) >= MIN_ID_LEN:
            out.setdefault(str(v), set()).add(k)
    return out


def identifier_values(bundle: dict) -> list:
    """Every declared identifier value, longest first."""
    return sorted(keys_by_value(bundle), key=lambda v: (-len(v), v))


def scrub(text: str, values: list) -> str:
    """Replace each declared identifier value, and any long digit run taken from one, with [redacted]."""
    if values:
        text = re.sub("|".join(re.escape(v) for v in values), REDACTED, text)
    cores = {m for v in values for m in re.findall(DIGITS, v)}
    return re.sub(DIGITS, lambda m: REDACTED if m.group() in cores else m.group(), text)


def find_leaks(text: str, bundle: dict) -> list:
    """Names of the identifier keys whose value, or long digit core, appears in text. Never returns the values."""
    hit, runs = set(), set(re.findall(DIGITS, text))
    for v, keys in keys_by_value(bundle).items():
        if v in text or any(core in runs for core in re.findall(DIGITS, v)):
            hit.update(keys)
    return sorted(hit)


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


# ---------------------------------------------------------------- phases and loops
def shape(args: dict) -> tuple:
    return tuple(sorted((k, type(v).__name__) for k, v in args.items()))


def phases(calls: list) -> list:
    """Maximal runs of consecutive calls with the same tool and the same argument shape."""
    out = []
    for i, c in enumerate(calls):
        key = (c["tool_name"], shape(c["args"]))
        if out and out[-1]["key"] == key:
            out[-1]["end"] = i
        else:
            out.append({"key": key, "tool": c["tool_name"], "start": i, "end": i})
    for p in out:
        p["n"] = p["end"] - p["start"] + 1
        kinds = [calls[i]["response_kind"] for i in range(p["start"], p["end"] + 1)]
        p["not_ok"] = sum(1 for k in kinds if k != "ok")
        p["kinds"] = {k: kinds.count(k) for k in sorted(set(kinds))}
    return out


def find_loops(calls: list, loop_min: int = LOOP_MIN_CALLS, non_ok_share: float = NON_OK_SHARE) -> list:
    return [p for p in phases(calls) if p["n"] >= loop_min and p["not_ok"] / p["n"] >= non_ok_share]


# ---------------------------------------------------------------- building the draft
def cumulative_cost(calls: list) -> list:
    out, total = [], 0.0
    for c in calls:
        total = round(total + c["cost_usd"], 4)
        out.append(total)
    return out


def build_study(bundle: dict, reporter: str | None = None, loop_min: int = LOOP_MIN_CALLS):
    """Return (document, evidence) for the bundle, or None when the trace holds no loop."""
    calls, run = bundle["calls"], bundle["run"]
    loops = find_loops(calls, loop_min)
    if not loops:
        return None
    ids = identifier_values(bundle)
    role = scrub(run["agent_role"], ids)
    main = max(loops, key=lambda p: (p["n"], -p["start"]))
    steps = []
    for lp in loops:
        tool = scrub(lp["tool"], ids)
        flagged = [i for i in (lp["start"] - 1, lp["start"]) if 0 <= i < len(calls) and calls[i]["response_flag"] == "instruction_like"]
        if flagged:
            p = flagged[0]
            steps.append((p, 0, "AML.T0051.001", "response flagged instruction-like", p + 1, p + 1,
                          "At call %d, the response from the %s tool was flagged as instruction-like by the upstream scanner. "
                          "A loop on the %s tool begins at call %d." % (p + 1, scrub(calls[p]["tool_name"], ids), tool, lp["start"] + 1)))
        kinds = ", ".join("%s %d" % (k, n) for k, n in lp["kinds"].items())
        steps.append((lp["start"], 1, "AML.T0029", "loop of %d calls" % lp["n"], lp["start"] + 1, lp["end"] + 1,
                      "From call %d to call %d, %d consecutive calls to the %s tool with the same argument shape; %d of them returned a "
                      "response that was not ok (%s)." % (lp["start"] + 1, lp["end"] + 1, lp["n"], tool, lp["not_ok"], kinds)))
    cum = cumulative_cost(calls)
    cap = float(run["cost_cap_usd"])
    over = [i for i, t in enumerate(cum) if t >= cap]
    if over:
        i = over[0]
        steps.append((i, 2, "AML.T0034", "cumulative cost over the cap", i + 1, i + 1,
                      "Cumulative cost reached %.2f USD at call %d, over the %.2f USD per-run cap." % (cum[i], i + 1, cap)))
    steps.sort(key=lambda s: (s[0], s[1]))
    injected = any(s[2] == "AML.T0051.001" for s in steps)
    date = run["started_at"][:10]
    cost_sentence = ("Run cost reached %.2f USD against a %.2f USD cap." % (cum[-1], cap) if over
                     else "Run cost was %.2f USD, under the %.2f USD cap." % (cum[-1], cap))
    cause = ("The upstream scanner flagged a response as instruction-like next to the loop; the trace does not show who wrote the record."
             if injected else "The trace does not show why the responses were bad.")
    summary = ("On %s, a %s made %d tool calls in one run. From call %d it called the %s tool %d times in a row with the same argument "
               "shape, and %d of those responses were not ok. %s %s"
               % (date, role, len(calls), main["start"] + 1, scrub(main["tool"], ids), main["n"], main["not_ok"], cost_sentence, cause))
    study = {
        "name": "Retry loop after an instruction-like tool response" if injected else "Retry loop after bad tool responses",
        "summary": summary,
        "incident-date": date,
        "incident-date-granularity": "DATE",
        "case-study-type": "exercise" if bundle.get("synthetic", False) else "incident",
        "reporter": reporter if reporter else "TODO(reporter): the person or team that submits this",
        "target": role,
        "actor": "TODO(actor): the trace does not show whether anyone caused the first bad response",
        "procedure": [{"tactic": TECHNIQUES[s[2]][1], "technique": s[2], "description": s[6]} for s in steps],
    }
    evidence = [{"step": n + 1, "technique": s[2], "label": s[3], "first_call": s[4], "last_call": s[5]} for n, s in enumerate(steps)]
    meta = {"draft": True, "synthetic": bool(bundle.get("synthetic", False)), "atlas_release_read": "2026.09",
            "mapping_basis": "effects seen in the trace; the trace does not show an adversary action", "evidence": evidence}
    return {"study": study, "meta": meta}, evidence


# ---------------------------------------------------------------- output formats
def _scalar(v) -> str:
    return "true" if v is True else "false" if v is False else json.dumps(v)


def to_yaml(obj, indent: int = 0) -> str:
    """Block-style YAML for dicts, lists and scalars. Every string is written as a double-quoted JSON string."""
    pad = " " * indent
    lines = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                lines.append("%s%s:" % (pad, k))
                lines.append(to_yaml(v, indent + 2))
            else:
                lines.append("%s%s: %s" % (pad, k, "{}" if v == {} else "[]" if v == [] else _scalar(v)))
    else:
        for item in obj:
            if isinstance(item, dict):
                inner = to_yaml(item, indent + 2).split("\n")
                lines.append("%s- %s" % (pad, inner[0].lstrip()))
                lines.extend(inner[1:])
            else:
                lines.append("%s- %s" % (pad, _scalar(item)))
    return "\n".join(lines)


# ---------------------------------------------------------------- lint
def _valid_date(s: str) -> bool:
    try:
        datetime.date.fromisoformat(s[:10])
    except ValueError:
        return False
    return bool(DATE_RE.match(s) or DATETIME_RE.match(s))


def lint_study(doc, bundle: dict | None = None):
    """Return (problems, todos, leaks). problems are schema errors; todos are fields a person still owes."""
    problems, todos, leaks = [], [], []
    study = doc.get("study") if isinstance(doc, dict) else None
    if not isinstance(study, dict):
        return ["study: missing or not an object"], todos, leaks
    for k in sorted(study):
        if k not in STUDY_KEYS:
            problems.append("study: unknown key %s" % safe(k, 40))
    for k in STUDY_REQUIRED:
        if k not in study:
            problems.append("study: missing %s" % k)
    for k in ("name", "summary", "reporter", "target", "actor"):
        if k in study and not isinstance(study[k], str):
            problems.append("study.%s: expected a string" % k)
    if isinstance(study.get("incident-date"), str) and not _valid_date(study["incident-date"]):
        problems.append("study.incident-date: not a date or date-time")
    elif "incident-date" in study and not isinstance(study["incident-date"], str):
        problems.append("study.incident-date: expected a string")
    if study.get("incident-date-granularity") not in (None, "YEAR", "MONTH", "DATE"):
        problems.append("study.incident-date-granularity: not YEAR, MONTH or DATE")
    if study.get("case-study-type") not in (None, "incident", "exercise"):
        problems.append("study.case-study-type: not incident or exercise")
    if study.get("case-study-type") == "incident" and "reporter" not in study:
        problems.append("study.reporter: required for an incident")
    if "id" in study and not (isinstance(study["id"], str) and CASE_ID_RE.match(study["id"])):
        problems.append("study.id: does not match the case study id pattern")
    if "object-type" in study and study["object-type"] != "case-study":
        problems.append("study.object-type: must be case-study")
    proc = study.get("procedure")
    if "procedure" in study and not isinstance(proc, list):
        problems.append("study.procedure: expected a list")
    elif isinstance(proc, list):
        if not proc:
            problems.append("study.procedure: no steps")
        for n, step in enumerate(proc, start=1):
            if not isinstance(step, dict):
                problems.append("procedure step %d: expected an object" % n)
                continue
            for k in ("tactic", "technique", "description"):
                if k not in step:
                    problems.append("procedure step %d: missing %s" % (n, k))
            for k in sorted(set(step) - {"tactic", "technique", "description"}):
                problems.append("procedure step %d: unknown key %s" % (n, safe(k, 40)))
            if isinstance(step.get("tactic"), str) and not TACTIC_RE.match(step["tactic"]):
                problems.append("procedure step %d: tactic does not match the id pattern" % n)
            if isinstance(step.get("technique"), str) and not TECHNIQUE_RE.match(step["technique"]):
                problems.append("procedure step %d: technique does not match the id pattern" % n)
            for k in ("tactic", "technique"):
                if k in step and not isinstance(step[k], (str, dict)):
                    problems.append("procedure step %d: %s must be a string or an object" % (n, k))
            if "description" in step and not isinstance(step["description"], str):
                problems.append("procedure step %d: description must be a string" % n)
    refs = study.get("references")
    if "references" in study and not isinstance(refs, list):
        problems.append("study.references: expected a list")
    elif isinstance(refs, list):
        for n, r in enumerate(refs, start=1):
            if not (isinstance(r, dict) and set(r) == {"title", "url"} and all(v is None or isinstance(v, str) for v in r.values())):
                problems.append("reference %d: needs exactly title and url, each a string or null" % n)
    for k in ("reporter", "actor", "target"):
        if isinstance(study.get(k), str) and "TODO(" in study[k]:
            todos.append(k)
    if not refs:
        todos.append("references")
    if bundle is not None:
        leaks = find_leaks("\n".join(_strings(doc)), bundle)
    return problems, sorted(todos), leaks


# ---------------------------------------------------------------- loading
def check_bundle(b) -> None:
    """Raise ValueError (one line) when the bundle lacks what build reads, so bad input exits 2 instead of crashing."""
    if not isinstance(b, dict):
        raise ValueError("bundle: expected a JSON object, got %s" % type(b).__name__)
    keys = b.get("identifier_keys")
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise ValueError("bundle: identifier_keys must be a list of strings")
    run = b.get("run")
    if not isinstance(run, dict):
        raise ValueError("bundle: run must be an object")
    for k in ("run_id", "agent_id", "agent_role", "customer_id", "started_at"):
        if not isinstance(run.get(k), str):
            raise ValueError("bundle: run.%s must be a string" % k)
    if not _valid_date(run["started_at"][:10]):
        raise ValueError("bundle: run.started_at must start with a YYYY-MM-DD date")
    cap = run.get("cost_cap_usd")
    if isinstance(cap, bool) or not isinstance(cap, (int, float)) or not math.isfinite(cap) or cap <= 0:
        raise ValueError("bundle: run.cost_cap_usd must be a positive number")
    calls = b.get("calls")
    if not isinstance(calls, list) or not calls:
        raise ValueError("bundle: calls must be a non-empty list")
    for i, c in enumerate(calls, start=1):
        if not isinstance(c, dict):
            raise ValueError("bundle: call %d must be an object" % i)
        for k in ("tool_name", "response_kind"):
            if not isinstance(c.get(k), str):
                raise ValueError("bundle: call %d: %s must be a string" % (i, k))
        if not isinstance(c.get("args"), dict):
            raise ValueError("bundle: call %d: args must be an object" % i)
        if not isinstance(c.get("response_flag", ""), str):
            raise ValueError("bundle: call %d: response_flag must be a string" % i)
        c.setdefault("response_flag", "")
        cost = c.get("cost_usd")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
            raise ValueError("bundle: call %d: cost_usd must be a number of 0 or more" % i)


def read_json(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as e:
        raise ValueError("cannot read %s: %s" % (safe(path), safe(e.strerror or e, 60)))
    except (ValueError, RecursionError) as e:
        raise ValueError("%s is not valid JSON: %s" % (safe(path), safe(e, 60)))


# ---------------------------------------------------------------- command line
def summarize(doc: dict, evidence: list, problems: list, todos: list, leaks: list) -> str:
    study, meta = doc["study"], doc["meta"]
    where = ", ".join("%s at call %d" % (e["technique"], e["first_call"]) if e["first_call"] == e["last_call"]
                      else "%s over calls %d-%d" % (e["technique"], e["first_call"], e["last_call"]) for e in evidence)
    lines = ['draft: "%s" (%s)%s' % (study["name"], study["incident-date"], ", synthetic" if meta["synthetic"] else ""),
             "procedure: %d steps: %s" % (len(evidence), where),
             "lint: %s; todo fields: %s; identifier leaks: %d" % ("schema ok" if not problems else "%d schema problems" % len(problems),
                                                                  ", ".join(todos) if todos else "none", len(leaks))]
    return "\n".join(lines)


def run_build(path: str, reporter, yaml_path, json_path) -> int:
    try:
        bundle = read_json(path)
        check_bundle(bundle)
        built = build_study(bundle, reporter)
    except ValueError as e:
        print("input error: %s" % e, file=sys.stderr)
        return 2
    if built is None:
        print("no draft: no loop in %d calls (a loop is %d or more consecutive calls with the same tool and argument shape, "
              "%d%% or more of them not ok)" % (len(bundle["calls"]), LOOP_MIN_CALLS, round(NON_OK_SHARE * 100)))
        return 1
    doc, evidence = built
    problems, todos, leaks = lint_study(doc, bundle)
    try:
        if yaml_path:
            with open(yaml_path, "w", encoding="utf-8") as fh:
                fh.write(to_yaml(doc) + "\n")
        if json_path:
            with open(json_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(doc, indent=1) + "\n")
    except OSError as e:
        print("input error: cannot write output: %s" % safe(e.strerror or e, 60), file=sys.stderr)
        return 2
    print(summarize(doc, evidence, problems, todos, leaks))
    return 1 if problems or leaks else 0


def run_lint(path: str, bundle_path, strict: bool) -> int:
    try:
        doc = read_json(path)
        if not isinstance(doc, dict):
            raise ValueError("%s: expected a JSON object, got %s" % (safe(path), type(doc).__name__))
        bundle = None
        if bundle_path:
            bundle = read_json(bundle_path)
            check_bundle(bundle)
    except ValueError as e:
        print("input error: %s" % e, file=sys.stderr)
        return 2
    problems, todos, leaks = lint_study(doc, bundle)
    for p in problems:
        print("problem: %s" % p)
    if leaks:
        print("leak: declared identifier values appear in the study, under keys: %s" % ", ".join(safe(k, 40) for k in leaks))
    print("lint: %d problems; todo fields: %s; identifier leaks: %s" % (
        len(problems), ", ".join(todos) if todos else "none", len(leaks) if bundle is not None else "not checked (no --bundle)"))
    return 1 if problems or leaks or (strict and todos) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="atlas_case_study")
    ap.add_argument("--demo", action="store_true", help="draft a case study from the bundled example (data/example_bundle.json)")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build", help="draft a case study from a bundle")
    b.add_argument("bundle")
    b.add_argument("--reporter")
    b.add_argument("--yaml", help="write the draft as YAML")
    b.add_argument("--json", help="write the draft as JSON, which lint reads")
    li = sub.add_parser("lint", help="check a draft (JSON) against the contribution schema's rules")
    li.add_argument("study")
    li.add_argument("--bundle", help="the bundle the draft came from, to check for leaked identifiers")
    li.add_argument("--strict", action="store_true", help="exit 1 while any TODO field is left")
    a = ap.parse_args(argv)
    if a.demo:
        return run_build(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "example_bundle.json"), None, None, None)
    if a.cmd == "build":
        return run_build(a.bundle, a.reporter, a.yaml, a.json)
    if a.cmd == "lint":
        return run_lint(a.study, a.bundle, a.strict)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
