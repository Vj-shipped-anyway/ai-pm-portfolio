"""scopekeeper: compare what each agent may do (its grants) with what it did (its calls).

    python3 scopekeeper.py diff grants.csv calls.csv [--catalog scopes.csv] [--agents agents.csv]
    python3 scopekeeper.py --demo

For every grant the tool asks whether a scope it reaches was called in the log. A grant with no
call is proposed for removal. A group grant (one that stands for several scopes, listed in the
catalog) is proposed for narrowing to the scopes that were called. The proposal is then replayed
against the same log to count the calls it would newly deny.

A call with no agent tag (a shared service account) is credited to every agent on that account who
holds the scope, so a grant in use is never proposed for removal. The price is that a sibling's
calls can keep an unneeded grant alive; the report lists those grants.

Input files (CSV with a header row; extra columns are ignored):
    grants.csv    agent_id, scope                      (granted_on and ticket_id optional)
    calls.csv     agent_id, scope_used                 (day, call_id and service_account optional;
                                                        agent_id may be blank on a shared account)
    --catalog     scope, reaches                       reaches is a semicolon list; blank for a plain scope
    --agents      agent_id, service_account            needed when any call has a blank agent_id

Exit status: 0 nothing to change (or --fail-on never), 1 the diff proposes changes, 2 the input
could not be read. Standard library only, Python 3.9 or newer.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


class InputError(ValueError):
    """Input the tool cannot use. The command line turns it into one line on stderr and exit status 2."""


# ---------------------------------------------------------------- text safety
_CONTROL = re.compile("[\x00-\x1f\x7f-\x9f  ]")


def clean(text) -> str:
    """Make a value from an input file safe to print on one line: control characters become escapes."""
    def esc(m):
        return {"\n": "\\n", "\r": "\\r", "\t": "\\t"}.get(m.group(0), "\\u%04x" % ord(m.group(0)))
    return _CONTROL.sub(esc, str(text))


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so input text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


# ---------------------------------------------------------------- reading
def read_rows(path: str, required: list, label: str) -> list:
    """Rows of a CSV as (line number, dict). Raises InputError on anything that is not a well-formed table."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if not header:
                raise InputError(f"{label}: the file is empty")
            header = [h.strip() for h in header]
            missing = [c for c in required if c not in header]
            if missing:
                raise InputError(f"{label}: missing column {', '.join(missing)}; the header reads {clean(','.join(header))[:80]}")
            rows = []
            for n, rec in enumerate(reader, start=2):
                if not rec:
                    continue
                if len(rec) != len(header):
                    raise InputError(f"{label} line {n}: expected {len(header)} fields, found {len(rec)}")
                rows.append((n, dict(zip(header, (x.strip() for x in rec)))))
            return rows
    except OSError as e:
        raise InputError(f"{label}: cannot read {clean(path)}: {e.strerror or e}")
    except UnicodeDecodeError:
        raise InputError(f"{label}: {clean(path)} is not UTF-8 text")
    except csv.Error as e:
        raise InputError(f"{label}: {clean(path)} is not a readable CSV file: {clean(e)}")


def load_grants(path: str) -> list:
    out, seen = [], set()
    for n, r in read_rows(path, ["agent_id", "scope"], "grants"):
        if not r["agent_id"] or not r["scope"]:
            raise InputError(f"grants line {n}: agent_id and scope must not be blank")
        key = (r["agent_id"], r["scope"])
        if key in seen:
            raise InputError(f"grants line {n}: duplicate grant {clean(r['agent_id'])} {clean(r['scope'])}")
        seen.add(key)
        out.append({"agent_id": r["agent_id"], "scope": r["scope"], "ticket_id": r.get("ticket_id", "")})
    if not out:
        raise InputError("grants: the file has a header and no rows")
    return out


def load_calls(path: str) -> list:
    out = []
    for n, r in read_rows(path, ["agent_id", "scope_used"], "calls"):
        if not r["scope_used"]:
            raise InputError(f"calls line {n}: scope_used must not be blank")
        day = None
        if r.get("day", ""):
            if not re.fullmatch("[0-9]+", r["day"]) or int(r["day"]) < 1:
                raise InputError(f"calls line {n}: day must be a whole number of 1 or more, found {clean(r['day'])}")
            day = int(r["day"])
        sa = r.get("service_account", "")
        if not r["agent_id"] and not sa:
            raise InputError(f"calls line {n}: no agent_id and no service_account, so the call cannot be credited to anyone")
        out.append({"call_id": r.get("call_id") or f"line {n}", "agent_id": r["agent_id"], "day": day,
                    "scope": r["scope_used"], "service_account": sa})
    if not out:
        raise InputError("calls: the file has a header and no rows; refusing to propose removing every grant")
    return out


def load_catalog(path: str) -> dict:
    """{group scope: sorted list of the specific scopes it reaches}. A row with an empty reaches is a plain scope."""
    groups = {}
    for n, r in read_rows(path, ["scope", "reaches"], "catalog"):
        if not r["scope"]:
            raise InputError(f"catalog line {n}: scope must not be blank")
        if r["scope"] in groups:
            raise InputError(f"catalog line {n}: {clean(r['scope'])} is listed twice")
        members = sorted({m.strip() for m in r["reaches"].split(";") if m.strip()})
        if members:
            groups[r["scope"]] = members
    for scope, members in groups.items():
        for m in members:
            if m in groups:
                raise InputError(f"catalog: {clean(scope)} reaches {clean(m)}, which is itself a group; nested groups are not supported")
    return groups


def load_agents(path: str) -> dict:
    """{agent_id: service_account}"""
    out = {}
    for n, r in read_rows(path, ["agent_id", "service_account"], "agents"):
        if not r["agent_id"] or not r["service_account"]:
            raise InputError(f"agents line {n}: agent_id and service_account must not be blank")
        if r["agent_id"] in out:
            raise InputError(f"agents line {n}: {clean(r['agent_id'])} is listed twice")
        out[r["agent_id"]] = r["service_account"]
    if not out:
        raise InputError("agents: the file has a header and no rows")
    return out


# ---------------------------------------------------------------- the diff
def reach_of(scope: str, groups: dict) -> list:
    """The specific scopes one grant reaches: itself, or the members the catalog lists for a group."""
    return sorted(groups.get(scope, [scope]))


def effective_by_agent(grants: list, groups: dict) -> dict:
    """{agent_id: set of specific scopes the agent can reach}"""
    eff: dict = {}
    for g in grants:
        eff.setdefault(g["agent_id"], set()).update(reach_of(g["scope"], groups))
    return eff


def service_groups(agents: dict) -> dict:
    """{service_account: [agent_id, ...]} in a fixed order."""
    out: dict = {}
    for a in sorted(agents):
        out.setdefault(agents[a], []).append(a)
    return out


def replay(calls: list, allowed: dict, agents: dict) -> list:
    """Indexes of the calls denied if each agent could reach only allowed[agent].

    A tagged call is tested against its agent. A call with no tag is tested against the union of the
    agents on its service account, because the account is all the platform could see.
    """
    by_sa = service_groups(agents)
    denied = []
    for i, c in enumerate(calls):
        if c["agent_id"]:
            ok = c["scope"] in allowed.get(c["agent_id"], ())
        else:
            ok = any(c["scope"] in allowed.get(a, ()) for a in by_sa.get(c["service_account"], ()))
        if not ok:
            denied.append(i)
    return denied


def validate(grants: list, calls: list, groups: dict, agents: dict | None) -> None:
    for g in grants:
        if "*" in g["scope"] and g["scope"] not in groups:
            raise InputError(f"grants: {clean(g['scope'])} has no entry in the catalog, so what it reaches is unknown; pass --catalog")
    for c in calls:
        if c["scope"] in groups:
            raise InputError(f"calls: {clean(c['call_id'])} names the group scope {clean(c['scope'])}; a call must name a specific scope")
    if agents is None:
        untagged = sum(1 for c in calls if not c["agent_id"])
        if untagged:
            raise InputError(f"calls: {untagged} calls carry no agent_id; pass --agents (agent_id, service_account) so they can be credited")
    else:
        missing = sorted({g["agent_id"] for g in grants} - set(agents))
        if missing:
            raise InputError(f"agents: {clean(missing[0])} holds grants but is not in the agents file ({len(missing)} such agents)")


def analyze(grants: list, calls: list, groups: dict, agents: dict | None = None, min_calls: int = 1,
            window_days: int | None = None) -> dict:
    """The usage-versus-grant diff, the proposal and the replay. Pure: nothing is read from disk or changed."""
    if min_calls < 1:
        raise InputError("--min-calls must be 1 or more")
    if window_days is not None and window_days < 1:
        raise InputError("--window-days must be 1 or more")
    validate(grants, calls, groups, agents)
    agents = agents or {}
    days = [c["day"] for c in calls if c["day"] is not None]
    if window_days is not None and days and window_days < max(days):
        raise InputError(f"--window-days {window_days} is shorter than the latest day in the log ({max(days)})")
    window = window_days or (max(days) if days else None)
    eff = effective_by_agent(grants, groups)
    by_sa = service_groups(agents)

    tagged: Counter = Counter()
    credited: Counter = Counter()
    untagged = 0
    for c in calls:
        if c["agent_id"]:
            if c["scope"] in eff.get(c["agent_id"], ()):
                tagged[(c["agent_id"], c["scope"])] += 1
        else:
            untagged += 1
            for a in by_sa.get(c["service_account"], ()):
                if c["scope"] in eff.get(a, ()):
                    credited[(a, c["scope"])] += 1

    rows = []
    for g in sorted(grants, key=lambda g: (g["agent_id"], g["scope"])):
        a, s = g["agent_id"], g["scope"]
        reach = reach_of(s, groups)
        touched = [m for m in reach if tagged[(a, m)] + credited[(a, m)] >= min_calls]
        n_tagged = sum(tagged[(a, m)] for m in reach)
        n_credited = sum(credited[(a, m)] for m in reach)
        is_group = s in groups
        if not touched:
            action, after = "remove", []
            if n_tagged + n_credited:
                reason = f"fewer than {min_calls} calls"
            else:
                reason = "group never called" if is_group else "no call in the log"
        elif is_group and len(touched) < len(reach):
            action, after = "narrow", touched
            reason = f"{len(touched)} of {len(reach)} scopes it reaches were called"
        else:
            action, after = "keep", reach
            reason = "every scope it reaches was called" if is_group else "called in the log"
        rows.append({"agent_id": a, "scope": s, "action": action, "after": after, "reason": reason,
                     "group": is_group, "reach": len(reach), "calls_tagged": n_tagged, "calls_credited": n_credited,
                     "on_credit_only": bool(touched) and sum(tagged[(a, m)] for m in touched) == 0,
                     "ticket_id": g["ticket_id"]})

    proposed: dict = {a: set() for a in eff}
    for r in rows:
        proposed[r["agent_id"]].update(r["after"])

    agent_rows = []
    for a in sorted(eff):
        mine = [r for r in rows if r["agent_id"] == a]
        cut = len(eff[a]) - len(proposed[a])
        agent_rows.append({
            "agent_id": a, "grants": len(mine), "reach": len(eff[a]), "proposed": len(proposed[a]), "cut": cut,
            "breadth_pct": round(100 * cut / len(eff[a]), 1),
            "keep": sum(1 for r in mine if r["action"] == "keep"),
            "remove": sum(1 for r in mine if r["action"] == "remove"),
            "narrow": sum(1 for r in mine if r["action"] == "narrow"),
            "calls": sum(r["calls_tagged"] + r["calls_credited"] for r in mine),
        })

    denied_now = set(replay(calls, eff, agents))
    if len(denied_now) == len(calls):
        raise InputError("calls: none of the calls is covered by a grant in the grants file; check that both files describe the same agents and scopes")
    denied_after = set(replay(calls, proposed, agents))
    reach_before = sum(len(v) for v in eff.values())
    reach_after = sum(len(v) for v in proposed.values())
    summary = {
        "agents": len(eff), "grants": len(rows), "calls": len(calls), "untagged_calls": untagged, "window_days": window,
        "keep": sum(1 for r in rows if r["action"] == "keep"),
        "remove": sum(1 for r in rows if r["action"] == "remove"),
        "narrow": sum(1 for r in rows if r["action"] == "narrow"),
        "reach_before": reach_before, "reach_after": reach_after, "reach_cut": reach_before - reach_after,
        "reach_cut_pct": round(100 * (reach_before - reach_after) / reach_before, 1),
        "uncovered_calls": len(denied_now), "newly_denied": len(denied_after - denied_now),
        "on_credit_only": sum(1 for r in rows if r["action"] != "remove" and r["on_credit_only"]),
        "agents_without_calls": [r["agent_id"] for r in agent_rows if r["calls"] == 0],
        "min_calls": min_calls,
    }
    return {"grants": rows, "agents": agent_rows, "effective": eff, "proposed": proposed, "summary": summary,
            "denied_after": sorted(denied_after - denied_now)}


# ---------------------------------------------------------------- report
def render_text(res: dict) -> str:
    s = res["summary"]
    span = f" over {s['window_days']} days" if s["window_days"] else ""
    out = [f"scopekeeper diff: {s['agents']} agents, {s['grants']} grants reaching {s['reach_before']} scopes, {s['calls']} calls{span}"]
    if s["min_calls"] > 1:
        out.append(f"  a grant counts as used from {s['min_calls']} calls")
    if s["untagged_calls"]:
        out.append(f"  {s['untagged_calls']} calls carry no agent tag; each is credited to every agent on its service account that holds the scope")
    out.append("")
    out.append(f"{'agent':<8}{'grants':>7}{'reach':>7}{'after':>7}{'cut':>5}{'breadth':>9}")
    for r in sorted(res["agents"], key=lambda r: (-r["breadth_pct"], r["agent_id"])):
        out.append(f"{clean(r['agent_id']):<8}{r['grants']:>7}{r['reach']:>7}{r['proposed']:>7}{r['cut']:>5}{r['breadth_pct']:>8.1f}%")
    changes = [r for r in res["grants"] if r["action"] != "keep"]
    out.append("")
    out.append(f"proposals ({len(changes)} of {s['grants']} grants):")
    if not changes:
        out.append("  none: every grant was called")
    for r in changes:
        detail = r["reason"] + ("; keep " + ", ".join(clean(m) for m in r["after"]) if r["action"] == "narrow" else "")
        out.append(f"  {r['action']:<8}{clean(r['agent_id']):<8}{clean(r['scope']):<34}{detail}")
    credit = [r for r in res["grants"] if r["action"] != "remove" and r["on_credit_only"]]
    if credit:
        out.append("")
        out.append(f"kept on untagged calls alone ({len(credit)}): a sibling on the same service account may be the only caller")
        for r in credit:
            out.append(f"  {clean(r['agent_id']):<8}{clean(r['scope']):<34}{plural(r['calls_credited'], 'untagged call')} credited")
    out.append("")
    out.append(f"grants: keep {s['keep']}, remove {s['remove']}, narrow {s['narrow']}")
    out.append(f"entitlements: {s['reach_before']} before, {s['reach_after']} after ({s['reach_cut']} cut, {s['reach_cut_pct']}%)")
    out.append(f"replay: {s['newly_denied']} of {s['calls']} calls newly denied (the proposal is built from these calls, so this is an in-sample check)")
    if s["uncovered_calls"]:
        out.append(f"  {s['uncovered_calls']} calls are not covered by any current grant; they are denied before and after")
    if s["agents_without_calls"]:
        out.append("agents with no call in the log: " + ", ".join(clean(a) for a in s["agents_without_calls"]) + " (check the log covers them)")
    out.append("caution: a scope used less often than the log is long looks unused. Ask each owner which removals are periodic before applying any.")
    out.append(f"decision: {s['remove'] + s['narrow']} grants to remove or narrow" if s["remove"] + s["narrow"] else "decision: no change proposed")
    return "\n".join(out)


def render_github(res: dict) -> str:
    s = res["summary"]
    out = []
    for r in res["grants"]:
        if r["action"] == "keep":
            continue
        msg = f"{r['agent_id']} {r['scope']}: {r['reason']}"
        if r["action"] == "narrow":
            msg += "; keep " + ", ".join(r["after"])
        out.append(f"::warning title=scopekeeper {r['action']}::" + escape_annotation(msg))
    out.append(f"::notice title=scopekeeper::keep {s['keep']}, remove {s['remove']}, narrow {s['narrow']}; "
               f"{s['newly_denied']} of {s['calls']} calls newly denied in replay")
    return "\n".join(out)


# ---------------------------------------------------------------- command line
def run_diff(grants_path, calls_path, catalog_path, agents_path, window_days, min_calls, fail_on, fmt) -> int:
    try:
        grants = load_grants(grants_path)
        calls = load_calls(calls_path)
        groups = load_catalog(catalog_path) if catalog_path else {}
        agents = load_agents(agents_path) if agents_path else None
        res = analyze(grants, calls, groups, agents, min_calls, window_days)
    except InputError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    print(render_github(res) if fmt == "github" else render_text(res))
    s = res["summary"]
    return 1 if fail_on == "findings" and s["remove"] + s["narrow"] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scopekeeper")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_*.csv)")
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("diff", help="compare grants with calls and propose a smaller set")
    d.add_argument("grants")
    d.add_argument("calls")
    d.add_argument("--catalog", help="scope,reaches CSV that says what each group scope stands for")
    d.add_argument("--agents", help="agent_id,service_account CSV; needed when calls carry no agent tag")
    d.add_argument("--window-days", type=int, help="length of the log in days (default: the latest day in the log)")
    d.add_argument("--min-calls", type=int, default=1, help="calls needed before a grant counts as used (default 1)")
    d.add_argument("--fail-on", choices=["findings", "never"], default="findings")
    d.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        files = [os.path.join(DATA_DIR, f"example_{name}.csv") for name in ("grants", "calls", "catalog", "agents")]
        return run_diff(*files, 90, 1, "never", "text")
    if a.cmd == "diff":
        return run_diff(a.grants, a.calls, a.catalog, a.agents, a.window_days, a.min_calls, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
