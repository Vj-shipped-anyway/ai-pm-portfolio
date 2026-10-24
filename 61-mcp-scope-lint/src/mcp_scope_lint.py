"""mcp_scope_lint: lint the scopes an MCP server's tool manifest asks for, and propose a smaller set.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 mcp_scope_lint.py --demo
    python3 mcp_scope_lint.py lint MANIFEST.json [--propose] [--fail-on error|warn|never] [--format text|github]

Exit status: 0 when no finding reaches --fail-on, 1 when one does, 2 for bad or malformed input.
There is no model in this file: the parser, the rules, the breadth score and the proposal are plain rules.

Manifest shape (my own, modelled on a tools/list answer plus the grant that sits behind it):
    {"server": {"name": ...},
     "scope_catalog": [{"id": ..., "resource": ..., "access": "read|write|delete|admin|any"}],
     "granted_scopes": [scope ids the server holds],
     "tools": [{"name": ..., "requires_scopes": [scope ids],
                "annotations": {"readOnlyHint": bool, "destructiveHint": bool},   (optional)
                "description": str, "inputSchema": object}]}                       (optional, validated, not read)
Structure comes from the explicit fields `resource` and `access`, never from the spelling of an id.
An `any` scope covers every other scope of the same resource. A hint is the tool author's claim;
the rules compare the claim with the scopes the tool asks for and do not prove what the tool does.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ACCESS_RANK = {"read": 0, "write": 1, "delete": 2, "admin": 3, "any": 4}
CEILING_NAME = {0: "read", 1: "write"}
SEVERITY_RANK = {"warn": 1, "error": 2}
HERE = os.path.dirname(os.path.abspath(__file__))


class ManifestError(ValueError):
    """The manifest is not usable input."""


def clean(value) -> str:
    """Untrusted text on one line: control characters become visible escapes, so a name cannot forge a log line."""
    return "".join(c if c.isprintable() else "\\x%02x" % ord(c) if ord(c) < 256 else "\\u%04x" % ord(c) for c in str(value))


def escape_annotation(text: str) -> str:
    """Escape a workflow-command message the way GitHub documents, so manifest text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


# ---------------------------------------------------------------- parser
def _text(v) -> bool:
    return isinstance(v, str) and v != ""


def _scope_list(v, where: str, by_id: dict) -> list:
    if not isinstance(v, list):
        raise ManifestError(f"{where} must be a list")
    seen = []
    for s in v:
        if not isinstance(s, str) or s not in by_id:
            raise ManifestError(f"{where} names a scope that is not in scope_catalog: {clean(s)!r}")
        if s in seen:
            raise ManifestError(f"{where} lists {clean(s)!r} twice")
        seen.append(s)
    return seen


def parse_manifest(obj) -> dict:
    """Validate a manifest and return the parts the rules read. Raises ManifestError on anything else."""
    if not isinstance(obj, dict):
        raise ManifestError(f"expected a JSON object, got {type(obj).__name__}")
    server = obj.get("server")
    if not isinstance(server, dict) or not _text(server.get("name")):
        raise ManifestError("server.name must be a non-empty string")
    raw_catalog = obj.get("scope_catalog")
    if not isinstance(raw_catalog, list):
        raise ManifestError("scope_catalog must be a list")
    catalog, by_id = [], {}
    for i, s in enumerate(raw_catalog):
        if not isinstance(s, dict) or not _text(s.get("id")) or not _text(s.get("resource")):
            raise ManifestError(f"scope_catalog[{i}] needs a string id and a string resource")
        if not isinstance(s.get("access"), str) or s["access"] not in ACCESS_RANK:
            raise ManifestError(f"scope_catalog[{i}].access must be one of read, write, delete, admin, any")
        if s["id"] in by_id:
            raise ManifestError(f"scope_catalog lists {clean(s['id'])!r} twice")
        by_id[s["id"]] = {"id": s["id"], "resource": s["resource"], "access": s["access"]}
        catalog.append(by_id[s["id"]])
    granted = _scope_list(obj.get("granted_scopes"), "granted_scopes", by_id)
    raw_tools = obj.get("tools")
    if not isinstance(raw_tools, list):
        raise ManifestError("tools must be a list")
    tools, names = [], set()
    for i, t in enumerate(raw_tools):
        if not isinstance(t, dict) or not _text(t.get("name")):
            raise ManifestError(f"tools[{i}] needs a string name")
        if t["name"] in names:
            raise ManifestError(f"tools lists {clean(t['name'])!r} twice")
        names.add(t["name"])
        if "description" in t and not isinstance(t["description"], str):
            raise ManifestError(f"tool {clean(t['name'])!r}: description must be a string")
        if "inputSchema" in t and not isinstance(t["inputSchema"], dict):
            raise ManifestError(f"tool {clean(t['name'])!r}: inputSchema must be an object")
        ann = t.get("annotations", {})
        if not isinstance(ann, dict):
            raise ManifestError(f"tool {clean(t['name'])!r}: annotations must be an object")
        for hint in ("readOnlyHint", "destructiveHint"):
            if hint in ann and not isinstance(ann[hint], bool):
                raise ManifestError(f"tool {clean(t['name'])!r}: {hint} must be true or false")
        requires = _scope_list(t.get("requires_scopes"), f"tool {clean(t['name'])!r} requires_scopes", by_id)
        tools.append({"name": t["name"], "requires": requires,
                      "read_only": ann.get("readOnlyHint"), "destructive": ann.get("destructiveHint")})
    return {"name": server["name"], "catalog": catalog, "by_id": by_id, "granted": granted, "tools": tools}


# ---------------------------------------------------------------- scope arithmetic
def members(m: dict, scope_id: str) -> frozenset:
    """The specific scopes one scope reaches: itself, or every specific scope of its resource when access is `any`."""
    s = m["by_id"][scope_id]
    if s["access"] != "any":
        return frozenset([scope_id])
    return frozenset(c["id"] for c in m["catalog"] if c["resource"] == s["resource"] and c["access"] != "any")


def reach(m: dict, scope_ids) -> frozenset:
    out = frozenset()
    for sid in scope_ids:
        out |= members(m, sid)
    return out


def hint_ceiling(tool: dict):
    """The highest access rank the tool's own hints allow, or None when the hints say nothing usable."""
    if tool["read_only"] is True:
        return ACCESS_RANK["read"]
    if tool["destructive"] is False:
        return ACCESS_RANK["write"]
    return None


def _finding(severity, kind, tool, scope, message) -> dict:
    return {"severity": severity, "kind": kind, "tool": tool, "scope": scope, "message": message}


# ---------------------------------------------------------------- rules
def lint(m: dict) -> dict:
    """Findings, the breadth score, and the tools whose hints let no rule judge them."""
    by_id = m["by_id"]
    granted_reach = reach(m, m["granted"])
    needed = reach(m, [s for t in m["tools"] for s in t["requires"]])
    findings = []
    for g in m["granted"]:
        covered = members(m, g)
        used = covered & needed
        if not used:
            findings.append(_finding("error", "unused_grant", "", g, f"no tool requires any of the {len(covered)} scope(s) it reaches"))
        elif by_id[g]["access"] == "any" and used != covered:
            findings.append(_finding("warn", "wildcard_narrowable", "", g,
                                     f"reaches {len(covered)} scopes and tools require {len(used)}: {', '.join(sorted(used))}"))
    unjudged = []
    for t in m["tools"]:
        ceiling = hint_ceiling(t)
        if ceiling is None:
            unjudged.append(t["name"])
        for r in t["requires"]:
            access = by_id[r]["access"]
            gap = members(m, r) - granted_reach
            if gap:
                findings.append(_finding("error", "tool_scope_not_granted", t["name"], r,
                                         f"requires `{r}` but {len(gap)} scope(s) it reaches are not granted"))
            if ceiling is None:
                if access == "any":
                    findings.append(_finding("warn", "tool_requires_wildcard", t["name"], r,
                                             f"requires the wildcard `{r}` and carries no hint to narrow it by"))
            elif ACCESS_RANK[access] > ceiling:
                findings.append(_finding("error", "tool_scope_above_hint", t["name"], r,
                                         f"requires `{r}` (access {access}) but its hints limit it to {CEILING_NAME[ceiling]}"))
    findings.sort(key=lambda f: (-SEVERITY_RANK[f["severity"]], f["kind"], f["tool"], f["scope"]))
    unneeded = granted_reach - needed
    return {"server": m["name"], "tools": len(m["tools"]), "granted": len(m["granted"]), "reach": len(granted_reach),
            "unneeded": len(unneeded), "breadth": round(100.0 * len(unneeded) / len(granted_reach), 1) if granted_reach else 0.0,
            "findings": findings, "unjudged": sorted(unjudged)}


def _best_within(m: dict, resource: str, ceiling: int, reachable: frozenset):
    """The highest specific scope of the resource at or below the ceiling that the server already holds."""
    options = [c for c in m["catalog"] if c["resource"] == resource and c["access"] != "any"
               and ACCESS_RANK[c["access"]] <= ceiling and c["id"] in reachable]
    options.sort(key=lambda c: (-ACCESS_RANK[c["access"]], c["id"]))
    return options[0]["id"] if options else None


def propose(m: dict, narrow: bool = True, hints: bool = True) -> dict:
    """A smaller grant that never adds a scope: tools are cut back to their hints, then each grant keeps what a tool needs."""
    by_id = m["by_id"]
    before = reach(m, m["granted"])
    changes, new_requires, emptied = [], [], []
    for t in m["tools"]:
        ceiling = hint_ceiling(t) if hints else None
        new = []
        for r in t["requires"]:
            target = r if ceiling is None or ACCESS_RANK[by_id[r]["access"]] <= ceiling else _best_within(m, by_id[r]["resource"], ceiling, before)
            if target and target not in new:
                new.append(target)
        if new != t["requires"]:
            changes.append({"tool": t["name"], "from": list(t["requires"]), "to": new})
        if t["requires"] and not new:
            emptied.append(t["name"])
        new_requires.extend(new)
    needed = reach(m, new_requires)
    rows, kept = [], []
    for g in m["granted"]:
        covered = members(m, g)
        used = covered & needed
        if not used:
            rows.append({"scope": g, "action": "remove", "to": []})
        elif narrow and by_id[g]["access"] == "any" and used != covered:
            rows.append({"scope": g, "action": "narrow", "to": sorted(used)})
            kept.extend(sorted(used))
        else:
            rows.append({"scope": g, "action": "keep", "to": [g]})
            kept.append(g)
    after = reach(m, kept)
    return {"grants": rows, "tool_changes": changes, "proposed_grants": sorted(set(kept)),
            "reach_before": len(before), "reach_after": len(after), "cut": sorted(before - after), "tools_emptied": sorted(emptied)}


# ---------------------------------------------------------------- loading
def load_manifest(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return parse_manifest(json.load(fh))


# ---------------------------------------------------------------- output
def _count(findings, severity) -> int:
    return sum(1 for f in findings if f["severity"] == severity)


def render_text(rep: dict, prop) -> str:
    lines = [f"server: {clean(rep['server'])}   {rep['tools']} tools, {rep['granted']} scopes granted, {rep['reach']} scopes reachable"]
    if not rep["granted"]:
        lines.append("no scopes are granted, so there is nothing to lint on the grant side")
    else:
        lines.append(f"breadth: {rep['unneeded']} of {rep['reach']} reachable scopes are required by no tool ({rep['breadth']:.1f}%)")
    for f in rep["findings"]:
        subject = clean(f["tool"] or f["scope"])
        lines.append(f"  {'[' + f['severity'] + ']':<7} {f['kind']:<22} {subject:<22} {clean(f['message'])}")
    if not rep["findings"]:
        lines.append("  no findings")
    judged = rep["tools"] - len(rep["unjudged"])
    shown = ", ".join(clean(n) for n in rep["unjudged"][:6]) + (f" and {len(rep['unjudged']) - 6} more" if len(rep["unjudged"]) > 6 else "")
    lines.append(f"hints: {judged} of {rep['tools']} tools were checked against a hint" + (f"; not checked: {shown}" if rep["unjudged"] else ""))
    lines.append(f"result: {_count(rep['findings'], 'error')} errors, {_count(rep['findings'], 'warn')} warnings")
    if prop is not None:
        lines.append("proposal (least privilege; no scope is added):")
        for r in prop["grants"]:
            tail = f" -> {', '.join(clean(s) for s in r['to'])}" if r["action"] == "narrow" else ""
            lines.append(f"  {r['action']:<6} {clean(r['scope'])}{tail}")
        for c in prop["tool_changes"]:
            lines.append(f"  tool {clean(c['tool'])}: {', '.join(clean(s) for s in c['from'])} -> {', '.join(clean(s) for s in c['to']) or '(nothing)'}")
        lines.append(f"  reachable scopes: {prop['reach_before']} -> {prop['reach_after']}")
        if prop["tools_emptied"]:
            lines.append("  tools left with no scope, a person decides: " + ", ".join(clean(n) for n in prop["tools_emptied"]))
    return "\n".join(lines)


def render_github(rep: dict) -> str:
    lines = []
    for f in rep["findings"]:
        level = "error" if f["severity"] == "error" else "warning"
        lines.append(f"::{level} title=mcp-scope-lint {f['kind']}::" + escape_annotation(f"{rep['server']}: {f['tool'] or f['scope']}: {f['message']}"))
    note = f"{rep['server']}: {_count(rep['findings'], 'error')} errors, {_count(rep['findings'], 'warn')} warnings; breadth {rep['breadth']:.1f}%"
    if not rep["granted"]:
        note += "; no scopes are granted, so nothing was linted on the grant side"
    if rep["unjudged"]:
        note += f"; {len(rep['unjudged'])} of {rep['tools']} tools carry no usable hint and were not checked against one"
    lines.append("::notice title=mcp-scope-lint::" + escape_annotation(note))
    return "\n".join(lines)


def run_lint(path: str, want_proposal: bool, fail_on: str, fmt: str) -> int:
    try:
        m = load_manifest(path)
    except (OSError, ValueError, RecursionError) as e:
        print(f"input error: {clean(e)}", file=sys.stderr)
        return 2
    rep = lint(m)
    prop = propose(m) if want_proposal else None
    print(render_github(rep) if fmt == "github" else render_text(rep, prop))
    if fail_on == "never":
        return 0
    bar = SEVERITY_RANK["error" if fail_on == "error" else "warn"]
    return 1 if any(SEVERITY_RANK[f["severity"]] >= bar for f in rep["findings"]) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mcp_scope_lint")
    ap.add_argument("--demo", action="store_true", help="lint the bundled example (data/example_manifest.json)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("lint", help="lint one manifest file")
    c.add_argument("manifest")
    c.add_argument("--propose", action="store_true", help="also print the least-privilege proposal")
    c.add_argument("--fail-on", choices=["error", "warn", "never"], default="error")
    c.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        return run_lint(os.path.join(HERE, "..", "data", "example_manifest.json"), True, "never", "text")
    if a.cmd == "lint":
        return run_lint(a.manifest, a.propose, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
