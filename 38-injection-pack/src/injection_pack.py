"""injection_pack: replay a pack of injection test cases against a five-layer prompt gateway, and compare
two revisions of the gateway rules so a pull request that makes the gateway weaker can fail a check.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 injection_pack.py --demo
    python3 injection_pack.py run RULES.json --pack PACK.csv [--min-catch PCT] [--max-fp PCT] [--format text|github]
    python3 injection_pack.py compare OLD.json NEW.json --pack PACK.csv [--min-catch PCT] [--max-fp PCT]
                                                        [--fail-on regression|never] [--format text|github]

Exit status: 0 when the check passes, 1 when it finds a problem (a regression, or a floor that is not met),
2 for missing, malformed or truncated input. Nothing here calls a model: the gateway is a rule file.

Pack: a CSV with columns case_id, channel, expected (block or allow) and text; optional columns technique,
hard, session_id and memory_owner. A case is read by exactly one layer, chosen by its channel field:
    user_input     layer 1  patterns over what the user typed
    retrieved_doc  layer 2  patterns over a retrieved document (the indirect injection path)
    tool_call      layer 3  text is JSON {"tool": ..., "args": {...}}; destinations must be on the allow-list
    response       layer 4  patterns over the model's answer
    session        layer 5  a memory item may only be read by the session that owns it (memory_owner)

Rules: a JSON object with normalize (bool), l1_input, l2_retrieval and l4_egress (lists of {id, pattern}),
l3_tools {allowed_domains, destination_keys, denied_tools} and l5_session {enforce_owner}. Patterns are
Python regular expressions, matched case-insensitively. All five layers must be present, so a file that
forgot a layer is an error and not a gateway that quietly allows everything.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from urllib.parse import urlsplit

CHANNELS = ("user_input", "retrieved_doc", "tool_call", "response", "session")
LAYER_OF = {"user_input": "L1", "retrieved_doc": "L2", "tool_call": "L3", "response": "L4", "session": "L5"}
LAYER_KEY = {"user_input": "l1_input", "retrieved_doc": "l2_retrieval", "response": "l4_egress"}
PATTERN_LAYERS = ("l1_input", "l2_retrieval", "l4_egress")
REQUIRED_COLUMNS = ("case_id", "channel", "expected", "text")
OPTIONAL_COLUMNS = ("technique", "hard", "session_id", "memory_owner")
ZERO_WIDTH = dict.fromkeys(ord(c) for c in "​‌‍⁠﻿­")
MAX_LISTED = 5


# ---------------------------------------------------------------- rules
def check_rules(rules, label: str) -> None:
    """Raise ValueError when a rule file lacks a field the gateway reads, so bad input exits 2."""
    if not isinstance(rules, dict):
        raise ValueError(f"{label}: expected a JSON object, got {type(rules).__name__}")
    if not isinstance(rules.get("normalize", True), bool):
        raise ValueError(f"{label}: normalize must be true or false")
    seen = set()
    for key in PATTERN_LAYERS:
        layer = rules.get(key)
        if not isinstance(layer, list):
            raise ValueError(f"{label}: {key} must be a list")
        for i, r in enumerate(layer):
            if not isinstance(r, dict) or not isinstance(r.get("id"), str) or not isinstance(r.get("pattern"), str):
                raise ValueError(f"{label}: {key}[{i}] needs a string id and a string pattern")
            if r["id"] in seen:
                raise ValueError(f"{label}: duplicate rule id {r['id']!r}")
            seen.add(r["id"])
            try:
                re.compile(r["pattern"], re.IGNORECASE)
            except re.error as e:
                raise ValueError(f"{label}: {key}[{i}] pattern does not compile: {e}")
    l3 = rules.get("l3_tools")
    if not isinstance(l3, dict):
        raise ValueError(f"{label}: l3_tools must be an object")
    for key in ("allowed_domains", "destination_keys", "denied_tools"):
        v = l3.get(key)
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise ValueError(f"{label}: l3_tools.{key} must be a list of strings")
    l5 = rules.get("l5_session")
    if not isinstance(l5, dict) or not isinstance(l5.get("enforce_owner"), bool):
        raise ValueError(f"{label}: l5_session.enforce_owner must be true or false")


def load_rules(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        rules = json.load(fh)
    check_rules(rules, path)
    return rules


def build_gateway(rules: dict) -> dict:
    """Compile a checked rule file into the object that evaluates cases."""
    l3 = rules["l3_tools"]
    return {
        "name": str(rules.get("name", "")),
        "normalize": rules.get("normalize", True),
        "patterns": {key: [(r["id"], re.compile(r["pattern"], re.IGNORECASE)) for r in rules[key]] for key in PATTERN_LAYERS},
        "allowed": tuple(d.lower().strip(".") for d in l3["allowed_domains"]),
        "dest_keys": frozenset(l3["destination_keys"]),
        "denied": frozenset(l3["denied_tools"]),
        "enforce_owner": rules["l5_session"]["enforce_owner"],
        "raw": rules,
    }


def empty_layers(rules: dict) -> list:
    """Layers that hold no rule, so every case on that channel is allowed."""
    out = [LAYER_OF[c] + " " + LAYER_KEY[c] for c in LAYER_KEY if not rules[LAYER_KEY[c]]]
    if not rules["l3_tools"]["allowed_domains"]:
        out.append("L3 allowed_domains (every destination is blocked)")
    return out


# ---------------------------------------------------------------- the pack
def load_pack(path: str) -> list:
    cases, seen = [], set()
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, strict=True)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing column {', '.join(missing)}")
        for n, row in enumerate(reader, 2):
            if None in row or any(row[c] is None for c in REQUIRED_COLUMNS):
                raise ValueError(f"{path}: line {n} has the wrong number of fields")
            if row["channel"] not in CHANNELS:
                raise ValueError(f"{path}: line {n}: channel {row['channel']!r} is not one of {', '.join(CHANNELS)}")
            if row["expected"] not in ("block", "allow"):
                raise ValueError(f"{path}: line {n}: expected must be block or allow")
            if row["case_id"] in seen:
                raise ValueError(f"{path}: line {n}: duplicate case_id {row['case_id']!r}")
            seen.add(row["case_id"])
            case = {c: row[c] for c in REQUIRED_COLUMNS}
            case.update({c: row.get(c) or "" for c in OPTIONAL_COLUMNS})
            cases.append(case)
    if not cases:
        raise ValueError(f"{path}: the pack has no cases")
    return cases


# ---------------------------------------------------------------- evaluation
def normalize(text: str) -> str:
    """NFKC, zero-width characters removed, runs of spaces collapsed. Newlines stay."""
    return re.sub(r"[ \t]+", " ", unicodedata.normalize("NFKC", text.translate(ZERO_WIDTH)))


def _tokens(value) -> list:
    """The destination strings under one key. Anything that is not a string or a list of strings is unreadable."""
    items = value if isinstance(value, list) else [value]
    out = []
    for item in items:
        if not isinstance(item, str):
            return ["\x00"]
        out.extend(t for t in re.split(r"[,;\s]+", item) if t.strip("<>\"'(),;"))
    return out


def _host_of(token: str):
    tok = token.strip("<>\"'(),;")
    if "://" in tok:
        try:
            host = urlsplit(tok).hostname
        except ValueError:
            return None
    elif "@" in tok:
        host = tok.rsplit("@", 1)[1]
    else:
        host = tok
    host = (host or "").rstrip(".").lower()
    return host or None


def _allowed(gw: dict, host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in gw["allowed"])


def _tool_hits(gw: dict, text: str) -> list:
    try:
        call = json.loads(text)
    except ValueError:
        return ["L3-malformed"]
    if not isinstance(call, dict) or not isinstance(call.get("tool"), str) or not isinstance(call.get("args", {}), dict):
        return ["L3-malformed"]
    hits = []
    if call["tool"] in gw["denied"]:
        hits.append("L3-denied-tool")
    for key, value in call.get("args", {}).items():
        if key not in gw["dest_keys"]:
            continue
        for tok in _tokens(value):
            host = _host_of(tok)
            if host is None or not _allowed(gw, host):
                hits.append("L3-destination")
                break
    return sorted(set(hits))


def matches(gw: dict, case: dict) -> list:
    """Ids of every rule that fires on one case (the layer is chosen by the case's channel field)."""
    ch = case["channel"]
    if ch in LAYER_KEY:
        text = normalize(case["text"]) if gw["normalize"] else case["text"]
        return [rid for rid, rx in gw["patterns"][LAYER_KEY[ch]] if rx.search(text)]
    if ch == "tool_call":
        return _tool_hits(gw, case["text"])
    if gw["enforce_owner"] and case["memory_owner"] and case["memory_owner"] != case["session_id"]:
        return ["L5-owner"]
    return []


def run_pack(gw: dict, cases: list) -> list:
    out = []
    for c in cases:
        hits = matches(gw, c)
        out.append({"case_id": c["case_id"], "channel": c["channel"], "technique": c["technique"], "expected": c["expected"],
                    "hard": c["hard"], "blocked": bool(hits), "rule": hits[0] if hits else "",
                    "ok": bool(hits) == (c["expected"] == "block")})
    return out


def summarize(results: list) -> dict:
    s = {"attacks": 0, "caught": 0, "benign": 0, "false_blocks": 0, "hard_attacks": 0, "hard_caught": 0, "hard_benign": 0,
         "hard_false_blocks": 0, "by_channel": {ch: {"attacks": 0, "caught": 0, "benign": 0, "false_blocks": 0} for ch in CHANNELS}}
    for r in results:
        ch = s["by_channel"][r["channel"]]
        hard = r["hard"] == "yes"
        if r["expected"] == "block":
            for t in (s, ch):
                t["attacks"] += 1
                t["caught"] += r["blocked"]
            if hard:
                s["hard_attacks"] += 1
                s["hard_caught"] += r["blocked"]
        else:
            for t in (s, ch):
                t["benign"] += 1
                t["false_blocks"] += r["blocked"]
            if hard:
                s["hard_benign"] += 1
                s["hard_false_blocks"] += r["blocked"]
    return s


# ---------------------------------------------------------------- comparing two rule files
def rule_changes(old: dict, new: dict) -> list:
    """Rule ids that were removed, added or given a different pattern, and settings that moved."""
    changes = []
    old_rules = {r["id"]: r["pattern"] for k in PATTERN_LAYERS for r in old[k]}
    new_rules = {r["id"]: r["pattern"] for k in PATTERN_LAYERS for r in new[k]}
    for rid in sorted(set(old_rules) | set(new_rules)):
        if rid not in new_rules:
            changes.append({"id": rid, "what": "removed", "rule": True})
        elif rid not in old_rules:
            changes.append({"id": rid, "what": "added", "rule": True})
        elif old_rules[rid] != new_rules[rid]:
            changes.append({"id": rid, "what": "pattern changed", "rule": True})
    for label, a, b in (("normalize", old.get("normalize", True), new.get("normalize", True)),
                        ("l5_session.enforce_owner", old["l5_session"]["enforce_owner"], new["l5_session"]["enforce_owner"])):
        if a != b:
            changes.append({"id": label, "what": f"{a} -> {b}", "rule": False})
    for key in ("allowed_domains", "destination_keys", "denied_tools"):
        a, b = old["l3_tools"][key], new["l3_tools"][key]
        if sorted(a) != sorted(b):
            added, removed = sorted(set(b) - set(a)), sorted(set(a) - set(b))
            changes.append({"id": "l3_tools." + key, "what": "added [%s] removed [%s]" % (", ".join(added), ", ".join(removed)), "rule": False})
    return changes


def compare(old_rules: dict, new_rules: dict, cases: list) -> dict:
    """Replay the pack on both rule files. A regression is a case the old rules got right and the new rules get wrong."""
    old_gw, new_gw = build_gateway(old_rules), build_gateway(new_rules)
    before, after = run_pack(old_gw, cases), run_pack(new_gw, cases)
    regressions = [(b, a) for b, a in zip(before, after) if b["ok"] and not a["ok"]]
    improvements = [(b, a) for b, a in zip(before, after) if not b["ok"] and a["ok"]]
    changes = rule_changes(old_rules, new_rules)
    fired = [set(matches(old_gw, c)) | set(matches(new_gw, c)) for c in cases]
    blind = [ch["id"] for ch in changes if ch["rule"] and not any(ch["id"] in f for f in fired)]
    return {"before": summarize(before), "after": summarize(after), "regressions": regressions, "improvements": improvements,
            "changes": changes, "blind": blind, "empty": empty_layers(new_rules)}


def floor_problems(summary: dict, min_catch, max_fp) -> list:
    out = []
    if min_catch is not None and summary["attacks"] and summary["caught"] * 100 < min_catch * summary["attacks"]:
        out.append(f"catch rate {summary['caught']} of {summary['attacks']} is below the floor of {min_catch:g} percent")
    if max_fp is not None and summary["benign"] and summary["false_blocks"] * 100 > max_fp * summary["benign"]:
        out.append(f"false blocks {summary['false_blocks']} of {summary['benign']} are above the ceiling of {max_fp:g} percent")
    return out


# ---------------------------------------------------------------- output
def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so pack or rule text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def clean(text, limit: int = 240) -> str:
    """One printable line: control characters become \\uXXXX so a hostile string cannot forge a log line."""
    s = "".join(c if c.isprintable() else "\\u%04x" % ord(c) for c in str(text))
    return s if len(s) <= limit else s[:limit - 3] + "..."


def _regression_text(b: dict, a: dict) -> str:
    what = (f"attack was blocked by {b['rule']}, now allowed" if b["expected"] == "block"
            else f"benign case was allowed, now blocked by {a['rule']}")
    return f"{b['case_id']} {b['channel']}/{b['technique'] or '-'}: {what}"


def _pack_line(cases: list) -> str:
    n_att = sum(1 for c in cases if c["expected"] == "block")
    return f"{len(cases)} cases ({n_att} attack, {len(cases) - n_att} benign)"


def _rate(s: dict) -> str:
    return f"{s['caught']} of {s['attacks']} attacks blocked, {s['false_blocks']} of {s['benign']} benign cases blocked"


def render_compare(old: dict, new: dict, cases: list, res: dict, problems: list, decision: str, fmt: str) -> str:
    lines = []
    if fmt == "github":
        for b, a in res["regressions"]:
            lines.append("::error title=injection-pack regression::" + escape_annotation(_regression_text(b, a)))
        for p in problems:
            lines.append("::error title=injection-pack floor::" + escape_annotation(p))
        for rid in res["blind"]:
            lines.append("::warning title=injection-pack blind spot::" + escape_annotation(
                f"no pack case matches rule {rid}, so the pack cannot see this change"))
        for e in res["empty"]:
            lines.append("::warning title=injection-pack empty layer::" + escape_annotation(f"{e} has no rules"))
        lines.append("::notice title=injection-pack::" + escape_annotation(
            f"decision {decision}; {len(res['regressions'])} regressions on {len(cases)} cases"))
        return "\n".join(lines)
    lines.append(f"pack: {_pack_line(cases)}   rules: {clean(old.get('name', '?'), 60)} -> {clean(new.get('name', '?'), 60)}")
    for ch in res["changes"]:
        lines.append(f"  changed: {clean(ch['id'], 80)} {clean(ch['what'], 120)}")
    if not res["changes"]:
        lines.append("  the two rule files are identical in behavior-relevant fields")
    for b, a in res["regressions"][:MAX_LISTED]:
        lines.append("  regression  " + clean(_regression_text(b, a)))
    if len(res["regressions"]) > MAX_LISTED:
        lines.append(f"  ... and {len(res['regressions']) - MAX_LISTED} more regressions")
    lines.append(f"  cases that got better: {len(res['improvements'])}")
    for rid in res["blind"]:
        lines.append(f"  note: no pack case matches rule {clean(rid, 80)}, so the pack cannot see this change")
    for e in res["empty"]:
        lines.append(f"  note: {clean(e, 120)} has no rules")
    lines.append("before: " + _rate(res["before"]))
    lines.append("after:  " + _rate(res["after"]))
    for p in problems:
        lines.append("  floor: " + p)
    lines.append(f"decision: {decision}" + (f" ({len(res['regressions'])} regressions)" if res["regressions"] else ""))
    return "\n".join(lines)


def render_run(rules: dict, cases: list, results: list, summary: dict, problems: list, fmt: str) -> str:
    misses = [r for r in results if r["expected"] == "block" and not r["blocked"]]
    falses = [r for r in results if r["expected"] == "allow" and r["blocked"]]
    if fmt == "github":
        lines = ["::warning title=injection-pack miss::" + escape_annotation(f"{r['case_id']} {r['channel']}/{r['technique'] or '-'} attack was allowed")
                 for r in misses[:MAX_LISTED]]
        lines += ["::warning title=injection-pack false block::" + escape_annotation(f"{r['case_id']} {r['channel']}/{r['technique'] or '-'} benign case was blocked by {r['rule']}")
                  for r in falses[:MAX_LISTED]]
        lines += ["::error title=injection-pack floor::" + escape_annotation(p) for p in problems]
        lines.append("::notice title=injection-pack::" + escape_annotation(_rate(summary)))
        return "\n".join(lines)
    lines = [f"rules: {clean(rules.get('name', '?'), 60)}   pack: {_pack_line(cases)}",
             f"  {'channel':<14} {'attacks':>7} {'blocked':>8} {'benign':>7} {'false blocks':>13}"]
    for ch in CHANNELS:
        c = summary["by_channel"][ch]
        lines.append(f"  {ch:<14} {c['attacks']:>7} {c['caught']:>8} {c['benign']:>7} {c['false_blocks']:>13}")
        if not c["attacks"] and not c["benign"]:
            lines.append(f"  note: the pack has no case for channel {ch}, so layer {LAYER_OF[ch]} was not exercised")
    lines.append(_rate(summary))
    for r in misses[:MAX_LISTED]:
        lines.append(f"  missed   {clean(r['case_id'], 40)} {clean(r['channel'], 20)}/{clean(r['technique'] or '-', 40)}")
    if len(misses) > MAX_LISTED:
        lines.append(f"  ... and {len(misses) - MAX_LISTED} more missed attacks")
    for r in falses[:MAX_LISTED]:
        lines.append(f"  blocked  {clean(r['case_id'], 40)} {clean(r['channel'], 20)}/{clean(r['technique'] or '-', 40)} by {clean(r['rule'], 40)}")
    if len(falses) > MAX_LISTED:
        lines.append(f"  ... and {len(falses) - MAX_LISTED} more false blocks")
    for e in empty_layers(rules):
        lines.append(f"  note: {clean(e, 120)} has no rules")
    for p in problems:
        lines.append("  floor: " + p)
    lines.append("result: " + ("FAIL" if problems else "PASS"))
    return "\n".join(lines)


# ---------------------------------------------------------------- command line
def run_compare(old_path, new_path, pack_path, min_catch, max_fp, fail_on, fmt) -> int:
    try:
        old, new = load_rules(old_path), load_rules(new_path)
        cases = load_pack(pack_path)
        res = compare(old, new, cases)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, csv.Error, RecursionError) as e:
        print(f"input error: {clean(e)}", file=sys.stderr)
        return 2
    problems = floor_problems(res["after"], min_catch, max_fp)
    decision = "BLOCK" if res["regressions"] or problems else "ALLOW"
    print(render_compare(old, new, cases, res, problems, decision, fmt))
    return 1 if decision == "BLOCK" and fail_on != "never" else 0


def run_run(rules_path, pack_path, min_catch, max_fp, fail_on, fmt) -> int:
    try:
        rules = load_rules(rules_path)
        cases = load_pack(pack_path)
        results = run_pack(build_gateway(rules), cases)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, csv.Error, RecursionError) as e:
        print(f"input error: {clean(e)}", file=sys.stderr)
        return 2
    summary = summarize(results)
    problems = floor_problems(summary, min_catch, max_fp)
    print(render_run(rules, cases, results, summary, problems, fmt))
    return 1 if problems and fail_on != "never" else 0


def _percent(text: str) -> float:
    try:
        v = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number")
    if not 0 <= v <= 100:
        raise argparse.ArgumentTypeError("a percentage must be between 0 and 100")
    return v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="injection_pack")
    ap.add_argument("--demo", action="store_true", help="compare data/gateway_rules.json with data/example_rules_new.json on data/pack.csv")
    sub = ap.add_subparsers(dest="cmd")
    for name in ("run", "compare"):
        p = sub.add_parser(name, help="run the pack on one rule file" if name == "run" else "compare two rule files on the pack")
        if name == "run":
            p.add_argument("rules")
        else:
            p.add_argument("old")
            p.add_argument("new")
        p.add_argument("--pack", required=True, help="the test pack (CSV)")
        p.add_argument("--min-catch", type=_percent, help="fail when fewer than this percent of attack cases are blocked")
        p.add_argument("--max-fp", type=_percent, help="fail when more than this percent of benign cases are blocked")
        p.add_argument("--fail-on", choices=["regression", "never"], default="regression")
        p.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_compare(os.path.join(d, "gateway_rules.json"), os.path.join(d, "example_rules_new.json"),
                           os.path.join(d, "pack.csv"), None, None, "never", "text")
    if a.cmd == "run":
        return run_run(a.rules, a.pack, a.min_catch, a.max_fp, a.fail_on, a.format)
    if a.cmd == "compare":
        return run_compare(a.old, a.new, a.pack, a.min_catch, a.max_fp, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
