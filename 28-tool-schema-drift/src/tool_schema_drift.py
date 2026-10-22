"""tool_schema_drift: compare two revisions of an agent tool schema and decide whether the change
may merge. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 tool_schema_drift.py --demo
    python3 tool_schema_drift.py check OLD.json NEW.json [--calls CALLS.csv] [--fail-on block|review|never]
                                                         [--format text|github]

Exit status: 0 when the decision is below --fail-on, 1 when it is at or above it, 2 for bad input.
A decision is BLOCK (a breaking change), REVIEW (the structure still validates but the meaning may
have moved) or ALLOW. There is no model in this file: the diff, the unit check, the replay and the
gate are plain rules. The classifier is the one from project 15 (SchemaWatch) plus bound checks.

Schema shape: {"name", "version", "description", "parameters": {"properties": {...}, "required": [...]}}
Supported keywords: type, enum, required, minimum, maximum, maxLength, default, items.type, items.enum.
Not supported: pattern, format, oneOf, anyOf, nested objects.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter

RENAME_SIMILARITY = 0.5
DECISION_RANK = {"ALLOW": 0, "REVIEW": 1, "BLOCK": 2}


# ---------------------------------------------------------------- strict validator
def _is_int(v) -> bool:
    return (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v.is_integer())


def _type_ok(v, t: str) -> bool:
    if t == "string":
        return isinstance(v, str)
    if t == "integer":
        return _is_int(v)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "array":
        return isinstance(v, list)
    if t == "object":
        return isinstance(v, dict)
    return True


def _check_value(name: str, v, spec: dict) -> list:
    t = spec.get("type")
    if t and not _type_ok(v, t):
        return [f"type_mismatch:{name}:expected {t}, got {type(v).__name__}"]
    errs = []
    if "enum" in spec and v not in spec["enum"]:
        errs.append(f"enum_violation:{name}:{v!r} is not an allowed value")
    if t in ("integer", "number"):
        if "minimum" in spec and v < spec["minimum"]:
            errs.append(f"below_minimum:{name}:{v} < {spec['minimum']}")
        if "maximum" in spec and v > spec["maximum"]:
            errs.append(f"above_maximum:{name}:{v} > {spec['maximum']}")
    if t == "string" and "maxLength" in spec and len(v) > spec["maxLength"]:
        errs.append(f"too_long:{name}:{len(v)} > {spec['maxLength']}")
    if t == "array" and "items" in spec:
        for i, x in enumerate(v):
            errs.extend(_check_value(f"{name}[{i}]", x, spec["items"]))
    return errs


def strict_validate(schema: dict, args: dict) -> list:
    """Violations of one call against one schema; an empty list means the call is valid."""
    params = schema["parameters"]
    props = params["properties"]
    errs = [f"unknown_parameter:{k}:not in the schema" for k in args if k not in props]
    errs += [f"missing_required:{r}:required but absent" for r in params.get("required", []) if r not in args]
    for k, v in args.items():
        if k in props:
            errs.extend(_check_value(k, v, props[k]))
    return errs


def replay(new_schema: dict, calls: list) -> dict:
    """Run recorded calls (dicts with call_id and args) against the new schema. Returns {call_id: errors}."""
    out = {}
    for c in calls:
        errs = strict_validate(new_schema, c["args"])
        if errs:
            out[c["call_id"]] = errs
    return out


# ---------------------------------------------------------------- numbers and units in descriptions
_UNITS = {
    "USD": ["us dollars", "us dollar", "dollars", "dollar", "usd"], "EUR": ["euros", "euro", "eur"],
    "GBP": ["pounds sterling", "pounds", "gbp"], "cents": ["cents", "cent"],
    "ms": ["milliseconds", "millisecond", "msec", "ms"], "s": ["seconds", "second", "secs", "sec"],
    "min": ["minutes", "minute", "mins"], "h": ["hours", "hour", "hrs"], "d": ["days", "day"],
    "wk": ["weeks", "week"], "mo": ["months", "month"], "yr": ["years", "year"],
    "bps": ["basis points", "basis point", "bps"], "pct": ["percentage", "percent", "per cent"],
    "mi": ["miles", "mile"], "km": ["kilometers", "kilometres", "kilometer", "kilometre", "km"],
    "bytes": ["bytes"], "sheets": ["sheets", "sheet"],
}
_ALIAS = {alias: canon for canon, aliases in _UNITS.items() for alias in aliases}
_WORDS = sorted(_ALIAS, key=len, reverse=True)
_UNIT_RE = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(w) for w in _WORDS) + r")(?![a-z0-9])|%")
_NUM_RE = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?")


def _norm_number(s: str) -> str:
    s = s.replace(",", "")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def description_signature(text: str) -> frozenset:
    """The (number, unit) pairs a description states. Number words ('seven') are not parsed."""
    t = text.lower()
    units = [(m.start(), m.end(), "pct" if m.group() == "%" else _ALIAS[m.group()]) for m in _UNIT_RE.finditer(t)]
    used, sig = set(), set()
    for m in _NUM_RE.finditer(t):
        unit = None
        for i, (us, _ue, canon) in enumerate(units):
            if i not in used and us >= m.end() and t[m.end():us].strip() == "" and us - m.end() <= 2:
                unit = canon
                used.add(i)
                break
        sig.add((_norm_number(m.group()), unit))
    for i, (_us, _ue, canon) in enumerate(units):
        if i not in used:
            sig.add((None, canon))
    return frozenset(sig)


def fmt_signature(sig: frozenset) -> str:
    parts = sorted(f"{n} {u}".strip() if n else (u or "") for n, u in sig)
    return ", ".join(parts) if parts else "none"


# ---------------------------------------------------------------- structural diff
def _finding(kind, param, cls, reason, old="", new="") -> dict:
    return {"kind": kind, "param": param, "class": cls, "reason": reason, "old": str(old), "new": str(new)}


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def _detect_renames(old_props, new_props, removed, added):
    cands = []
    for r in removed:
        for a in added:
            if old_props[r].get("type") != new_props[a].get("type"):
                continue
            ta, tb = _tokens(old_props[r].get("description", "")), _tokens(new_props[a].get("description", ""))
            score = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
            cands.append((score, r, a))
    cands.sort(key=lambda x: (-x[0], x[1], x[2]))
    pairs, used_r, used_a = [], set(), set()
    for score, r, a in cands:
        if score >= RENAME_SIMILARITY and r not in used_r and a not in used_a:
            pairs.append((r, a))
            used_r.add(r)
            used_a.add(a)
    return pairs


def _enum_of(spec):
    return spec["enum"] if "enum" in spec else spec.get("items", {}).get("enum")


def _describe(param, old_text, new_text, use_heuristic=True):
    so, sn = description_signature(old_text), description_signature(new_text)
    if use_heuristic and so != sn:
        return _finding("unit_or_number_changed", param, "behavior_risk",
                        f"numbers or units in the description changed: [{fmt_signature(so)}] -> [{fmt_signature(sn)}]. "
                        f"The structure is identical, so validation still passes calls that now mean something different.",
                        old_text, new_text)
    return _finding("description_reworded", param, "non_breaking", "wording changed; no number or unit changed",
                    old_text, new_text)


def diff_schemas(old: dict, new: dict, use_heuristic: bool = True) -> list:
    """Compare two revisions of one tool and return classified findings."""
    out = []
    if old.get("description") != new.get("description"):
        out.append(_describe("", old.get("description", ""), new.get("description", ""), use_heuristic))
    op, np_ = old["parameters"]["properties"], new["parameters"]["properties"]
    oreq, nreq = set(old["parameters"].get("required", [])), set(new["parameters"].get("required", []))
    removed = [n for n in op if n not in np_]
    added = [n for n in np_ if n not in op]
    renames = _detect_renames(op, np_, removed, added)
    ren_old, ren_new = {o for o, _ in renames}, {n for _, n in renames}
    for o, n in renames:
        extra = f" `{n}` is also required, so calls without it fail." if n in nreq else ""
        out.append(_finding("param_renamed", o, "breaking",
                            f"`{o}` is gone and `{n}` appears with the same type and description. "
                            f"Any call that still sends `{o}` is rejected.{extra}", o, n))
    for o in removed:
        if o not in ren_old:
            out.append(_finding("param_removed", o, "breaking", f"`{o}` was removed. Calls that send it are rejected.", o, ""))
    for n in added:
        if n in ren_new:
            continue
        if n in nreq:
            out.append(_finding("required_added", n, "breaking",
                                f"new required field `{n}`. Every existing call lacks it, so every existing call fails.", "", n))
        else:
            out.append(_finding("optional_added", n, "non_breaking", f"new optional field `{n}`. Existing calls are unaffected.", "", n))
    for name, spec in np_.items():
        if name not in op:
            continue
        o = op[name]
        if name in nreq and name not in oreq:
            out.append(_finding("required_added", name, "breaking", f"`{name}` became required. Calls that omit it fail.", "optional", "required"))
        if name in oreq and name not in nreq:
            out.append(_finding("required_relaxed", name, "non_breaking", f"`{name}` is no longer required.", "required", "optional"))
        if o.get("type") != spec.get("type"):
            ot, nt = o.get("type"), spec.get("type")
            if (ot, nt) == ("integer", "number"):
                out.append(_finding("type_changed", name, "non_breaking", f"`{name}` widened integer -> number. Every value that was valid still is.", ot, nt))
            elif (ot, nt) == ("number", "integer"):
                out.append(_finding("type_changed", name, "breaking", f"`{name}` narrowed number -> integer. Fractional values are now rejected.", ot, nt))
            else:
                out.append(_finding("type_changed", name, "breaking", f"`{name}` changed {ot} -> {nt}. Values of the old type are rejected.", ot, nt))
        oe, ne = _enum_of(o), _enum_of(spec)
        if oe is not None and ne is not None:
            for v in oe:
                if v not in ne:
                    out.append(_finding("enum_value_removed", name, "breaking", f"`{v}` was removed from `{name}`. Calls that send it are rejected.", v, ""))
            for v in ne:
                if v not in oe:
                    out.append(_finding("enum_value_added", name, "non_breaking", f"`{v}` was added to `{name}`. Existing calls still validate.", "", v))
        for key, tighter in (("minimum", lambda a, b: b > a), ("maximum", lambda a, b: b < a), ("maxLength", lambda a, b: b < a)):
            if key in o and key in spec and o[key] != spec[key]:
                if tighter(o[key], spec[key]):
                    out.append(_finding("bound_tightened", name, "breaking",
                                        f"`{key}` of `{name}` moved {o[key]} -> {spec[key]}. Values inside the old bound and outside the new one are rejected.", o[key], spec[key]))
                else:
                    out.append(_finding("bound_loosened", name, "non_breaking", f"`{key}` of `{name}` moved {o[key]} -> {spec[key]}. Old values still validate.", o[key], spec[key]))
        if o.get("default") != spec.get("default"):
            out.append(_finding("default_changed", name, "behavior_risk",
                                f"default of `{name}` changed from {json.dumps(o.get('default'))} to {json.dumps(spec.get('default'))}. "
                                f"Calls that omit it get the new value and still pass validation.", json.dumps(o.get("default")), json.dumps(spec.get("default"))))
        if o.get("description") != spec.get("description"):
            out.append(_describe(name, o.get("description", ""), spec.get("description", ""), use_heuristic))
    return out


def decide(findings: list) -> str:
    classes = {f["class"] for f in findings}
    return "BLOCK" if "breaking" in classes else "REVIEW" if "behavior_risk" in classes else "ALLOW"


# ---------------------------------------------------------------- loading
def load_calls(path: str, tool: str | None = None) -> list:
    """Recorded calls from a CSV with columns call_id, tool, args_json (or a JSON-lines file with the same keys)."""
    calls = []
    with open(path, newline="", encoding="utf-8") as fh:
        if path.endswith(".csv"):
            rows = list(csv.DictReader(fh))
        else:
            rows = [json.loads(ln) for ln in fh if ln.strip()]
    for r in rows:
        if tool and r.get("tool") != tool:
            continue
        args = r["args_json"] if isinstance(r.get("args_json"), dict) else json.loads(r["args_json"])
        calls.append({"call_id": r["call_id"], "tool": r.get("tool", ""), "args": args})
    return calls


# ---------------------------------------------------------------- command line
def render(old, new, findings, decision, broken, total_calls, fmt) -> str:
    lines = []
    if fmt == "github":
        for f in findings:
            if f["class"] in ("breaking", "behavior_risk"):
                level = "error" if f["class"] == "breaking" else "warning"
                lines.append(f"::{level} title=tool-schema-drift {f['kind']}::{new.get('name', '')}.{f['param']}: {f['reason']}")
        lines.append(f"::notice title=tool-schema-drift::decision {decision}"
                     + (f"; {len(broken)} of {total_calls} recorded calls fail on the new schema" if total_calls else ""))
        return "\n".join(lines)
    lines.append(f"tool: {new.get('name', '?')}   version {old.get('version', '?')} -> {new.get('version', '?')}")
    for f in findings:
        lines.append(f"  [{f['class']:<13}] {f['kind']:<22} {f['param'] or '(tool)':<16} {f['reason']}")
    if not findings:
        lines.append("  no structural or description change")
    if total_calls:
        lines.append(f"replay: {len(broken)} of {total_calls} recorded calls fail on the new schema")
    lines.append(f"decision: {decision}")
    return "\n".join(lines)


def run_check(old_path, new_path, calls_path, fail_on, fmt) -> int:
    try:
        with open(old_path, encoding="utf-8") as fo, open(new_path, encoding="utf-8") as fn:
            old, new = json.load(fo), json.load(fn)
        calls = load_calls(calls_path, new.get("name")) if calls_path else []
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    findings = diff_schemas(old, new)
    broken = replay(new, calls) if calls else {}
    decision = decide(findings)
    if broken and decision != "BLOCK":
        decision = "BLOCK"
    print(render(old, new, findings, decision, broken, len(calls), fmt))
    if fail_on == "never":
        return 0
    return 1 if DECISION_RANK[decision] >= DECISION_RANK[{"block": "BLOCK", "review": "REVIEW"}[fail_on]] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tool_schema_drift")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_*.json)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="compare two schema files")
    c.add_argument("old")
    c.add_argument("new")
    c.add_argument("--calls", help="recorded calls (CSV or JSON lines) to replay against the new schema")
    c.add_argument("--fail-on", choices=["block", "review", "never"], default="block")
    c.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_old.json"), os.path.join(d, "example_new.json"),
                         os.path.join(d, "example_calls.csv"), "never", "text")
    if a.cmd == "check":
        return run_check(a.old, a.new, a.calls, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
