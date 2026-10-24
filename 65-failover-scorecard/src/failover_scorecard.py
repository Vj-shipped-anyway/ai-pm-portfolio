"""failover_scorecard: from a service map and a drill log, say which services have a tested way back
from the loss of their primary region. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 failover_scorecard.py --demo
    python3 failover_scorecard.py check SERVICES.csv DRILLS.csv --as-of YYYY-MM-DD
                                        [--fail-on tier1|any|never] [--format text|github]

Exit status: 0 when the scorecard passes the --fail-on scope, 1 when a service in that scope has no
tested way back, 2 for bad input or when the scope matched no service (nothing was checked).

The readiness rule is plain code, no model. A service is READY only when all of these hold:
  1. it has a secondary region and a failover mode (or its owner formally accepted having none, which
     the rule honours for the tiers in the policy and reports as NOT_REQUIRED);
  2. its latest LIVE drill of the scenario its mode needs (region_failover, or backup_restore for
     cold_restore) passed; tabletop drills and availability-zone drills do not count;
  3. that drill recovered within the service's own recovery-time target;
  4. that drill ran against the service's current secondary region and current config version;
  5. that drill is not older than the window for the tier;
  6. every service it declares in depends_on is itself READY.
Every number in the policy (windows, accepted tiers) is an assumption of this prototype, not a
value taken from a rule. The date comes from --as-of; no clock is read.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from datetime import date

BUNDLED_AS_OF = "2026-10-24"
STATUSES = ("READY", "NOT_REQUIRED", "NO_PATH", "UNTESTED", "FAILED", "SLOW", "CHANGED", "STALE", "DEPENDENCY")
OK_STATUSES = ("READY", "NOT_REQUIRED")
MODES = ("active_active", "warm_standby", "cold_restore", "none")
SCENARIO_FOR_MODE = {"active_active": "region_failover", "warm_standby": "region_failover", "cold_restore": "backup_restore"}
DRILL_TYPES = ("live", "tabletop")
SCENARIOS = ("region_failover", "az_failover", "backup_restore")
OUTCOMES = ("pass", "fail", "partial")
CHECKS = ("type_and_scenario", "rto", "version_and_region", "age", "dependencies")

SERVICE_COLUMNS = ("service_id", "name", "domain", "tier", "primary_region", "secondary_region", "failover_mode",
                   "rto_target_min", "config_version", "depends_on", "accepted_risk")
DRILL_COLUMNS = ("drill_id", "service_id", "drill_date", "drill_type", "scenario", "target_region",
                 "config_version", "minutes_to_recover", "outcome", "failure_reason")


class InputError(ValueError):
    """Bad or malformed input. The command line turns it into one line on stderr and exit status 2."""


def default_policy() -> dict:
    """The rule's assumptions. window_days is the longest age of a passing drill, by tier."""
    return {"window_days": {1: 180, 2: 365, 3: 540}, "accept_tiers": (3,), "skip": ()}


# ---------------------------------------------------------------- loading
def _rows(path: str, columns: tuple) -> list:
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise InputError(f"{path}: the file is empty")
            missing = [c for c in columns if c not in reader.fieldnames]
            if missing:
                raise InputError(f"{path}: missing column(s) {', '.join(missing)}")
            out = []
            for row in reader:
                if None in row:
                    raise InputError(f"{path} line {reader.line_num}: more values than the header has columns")
                if any(v is None for v in row.values()):
                    raise InputError(f"{path} line {reader.line_num}: the row is truncated")
                out.append((reader.line_num, {k: v.strip() for k, v in row.items()}))
    except OSError as e:
        raise InputError(f"cannot read {path}: {e.strerror or e}")
    except (UnicodeDecodeError, csv.Error) as e:
        raise InputError(f"{path}: not a readable CSV file ({str(e).splitlines()[0]})")
    return out


def _int(value: str, path: str, line: int, column: str, low: int, high: int | None = None) -> int:
    if not re.fullmatch(r"[0-9]{1,9}", value):
        raise InputError(f"{path} line {line}: {column} {value!r} is not a whole number")
    n = int(value)
    if n < low or (high is not None and n > high):
        span = f"{low} to {high}" if high is not None else f"{low} or more"
        raise InputError(f"{path} line {line}: {column} {n} must be {span}")
    return n


def _choice(value: str, path: str, line: int, column: str, allowed: tuple) -> str:
    if value not in allowed:
        raise InputError(f"{path} line {line}: {column} {value!r} is not one of {', '.join(allowed)}")
    return value


def parse_date(value: str) -> date | None:
    """A date written YYYY-MM-DD, or None when the text is not one."""
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _date(value: str, path: str, line: int, column: str) -> date:
    d = parse_date(value)
    if d is None:
        raise InputError(f"{path} line {line}: {column} {value!r} is not a real date written like 2026-10-24")
    return d


def load_services(path: str) -> list:
    """Services from a CSV with the columns in SERVICE_COLUMNS. Extra columns are ignored."""
    services, seen = [], set()
    for line, r in _rows(path, SERVICE_COLUMNS):
        for column in ("service_id", "name", "domain"):
            if not r[column]:
                raise InputError(f"{path} line {line}: {column} is empty")
        if r["service_id"] in seen:
            raise InputError(f"{path} line {line}: service_id {r['service_id']!r} appears twice")
        seen.add(r["service_id"])
        services.append({
            "service_id": r["service_id"], "name": r["name"], "domain": r["domain"],
            "tier": _int(r["tier"], path, line, "tier", 1, 3),
            "primary_region": r["primary_region"], "secondary_region": r["secondary_region"],
            "failover_mode": _choice(r["failover_mode"], path, line, "failover_mode", MODES),
            "rto_target_min": _int(r["rto_target_min"], path, line, "rto_target_min", 1),
            "config_version": _int(r["config_version"], path, line, "config_version", 0),
            "depends_on": [d.strip() for d in r["depends_on"].split(";") if d.strip()],
            "accepted_risk": _choice(r["accepted_risk"], path, line, "accepted_risk", ("yes", "no")) == "yes",
        })
    if not services:
        raise InputError(f"{path}: no services in the file")
    for s in services:
        for d in s["depends_on"]:
            if d not in seen:
                raise InputError(f"{path}: {s['service_id']} depends on {d!r}, which is not in the file")
            if d == s["service_id"]:
                raise InputError(f"{path}: {s['service_id']} depends on itself")
    return services


def load_drills(path: str) -> list:
    """Drills from a CSV with the columns in DRILL_COLUMNS. A header with no rows is a valid, empty log."""
    drills, seen = [], set()
    for line, r in _rows(path, DRILL_COLUMNS):
        if not r["drill_id"] or not r["service_id"]:
            raise InputError(f"{path} line {line}: drill_id and service_id must not be empty")
        if r["drill_id"] in seen:
            raise InputError(f"{path} line {line}: drill_id {r['drill_id']!r} appears twice")
        seen.add(r["drill_id"])
        d = {"drill_id": r["drill_id"], "service_id": r["service_id"],
             "date": _date(r["drill_date"], path, line, "drill_date"),
             "type": _choice(r["drill_type"], path, line, "drill_type", DRILL_TYPES),
             "scenario": _choice(r["scenario"], path, line, "scenario", SCENARIOS),
             "target_region": r["target_region"],
             "config_version": _int(r["config_version"], path, line, "config_version", 0),
             "minutes": _int(r["minutes_to_recover"], path, line, "minutes_to_recover", 0) if r["minutes_to_recover"] else None,
             "outcome": _choice(r["outcome"], path, line, "outcome", OUTCOMES), "reason": r["failure_reason"]}
        if d["type"] == "live" and d["outcome"] == "pass" and d["minutes"] is None:
            raise InputError(f"{path} line {line}: a passing live drill needs minutes_to_recover")
        drills.append(d)
    return drills


# ---------------------------------------------------------------- the rule
def _own_status(svc: dict, mine: list, as_of: date, policy: dict) -> tuple:
    """Status and reason from the service's own record, before dependencies are looked at."""
    skip = policy["skip"]
    if svc["accepted_risk"] and svc["tier"] in policy["accept_tiers"]:
        return "NOT_REQUIRED", "owner accepted having no way back; the rule honours that for this tier"
    if not svc["secondary_region"] or svc["failover_mode"] == "none" or svc["secondary_region"] == svc["primary_region"]:
        note = f"risk acceptance is not honoured for tier {svc['tier']}" if svc["accepted_risk"] else "no accepted risk"
        return "NO_PATH", f"no secondary region distinct from the primary, or no failover mode; {note}"
    want = SCENARIO_FOR_MODE[svc["failover_mode"]]
    counted = mine if "type_and_scenario" in skip else [d for d in mine if d["type"] == "live" and d["scenario"] == want]
    if not counted:
        tabletop = sum(1 for d in mine if d["type"] == "tabletop")
        other = sum(1 for d in mine if d["type"] == "live")
        seen = [f"{n} {what}" for n, what in ((tabletop, "tabletop"), (other, "live of another scenario")) if n]
        return "UNTESTED", f"no live {want} drill" + (f" (on record, not counted: {', '.join(seen)})" if seen else "")
    last = max(counted, key=lambda d: (d["date"], d["drill_id"]))
    when = last["date"].isoformat()
    if last["outcome"] != "pass":
        return "FAILED", f"latest live {want} drill on {when} was {last['outcome']}" + (f": {last['reason']}" if last["reason"] else "")
    if "rto" not in skip and last["minutes"] is not None and last["minutes"] > svc["rto_target_min"]:
        return "SLOW", f"latest drill on {when} recovered in {last['minutes']} min against a target of {svc['rto_target_min']}"
    if "version_and_region" not in skip:
        if last["target_region"] != svc["secondary_region"]:
            return "CHANGED", f"latest drill on {when} failed over to {last['target_region']}, the secondary is now {svc['secondary_region']}"
        if last["config_version"] != svc["config_version"]:
            return "CHANGED", f"latest drill on {when} ran on config v{last['config_version']}, the service is now on v{svc['config_version']}"
    age, window = (as_of - last["date"]).days, policy["window_days"][svc["tier"]]
    if "age" not in skip and age > window:
        return "STALE", f"latest passing drill is {age} days old, the window for tier {svc['tier']} is {window}"
    return "READY", f"live {want} drill on {when} recovered in {last['minutes']} of {svc['rto_target_min']} min on config v{last['config_version']}"


def score(services: list, drills: list, as_of: date, policy: dict | None = None) -> list:
    """One result per service, sorted by service_id. Raises InputError for a drill that names no service or
    is dated after as_of."""
    policy = policy or default_policy()
    by_id = {s["service_id"]: s for s in services}
    mine = {sid: [] for sid in by_id}
    for d in drills:
        if d["service_id"] not in by_id:
            raise InputError(f"drill {d['drill_id']} names service {d['service_id']!r}, which is not in the service map")
        if d["date"] > as_of:
            raise InputError(f"drill {d['drill_id']} is dated {d['date'].isoformat()}, after --as-of {as_of.isoformat()}")
        mine[d["service_id"]].append(d)
    own = {sid: _own_status(by_id[sid], mine[sid], as_of, policy) for sid in sorted(by_id)}
    status = {sid: own[sid][0] for sid in own}
    if "dependencies" not in policy["skip"]:
        changed = True
        while changed:                  # a READY service drops when a dependency is not READY; it never comes back
            changed = False
            for sid in sorted(by_id):
                if status[sid] == "READY" and any(status[d] != "READY" for d in by_id[sid]["depends_on"]):
                    status[sid], changed = "DEPENDENCY", True
    results = []
    for sid in sorted(by_id):
        s, reason, blocker = by_id[sid], own[sid][1], ""
        if status[sid] == "DEPENDENCY":
            blocker, reason = _blocker(sid, by_id, status)
        results.append({"service_id": sid, "name": s["name"], "domain": s["domain"], "tier": s["tier"],
                        "status": status[sid], "reason": reason, "blocked_by": blocker,
                        "last_drill": max((d["date"].isoformat() for d in mine[sid]), default="")})
    return results


def _blocker(sid: str, by_id: dict, status: dict) -> tuple:
    """The dependency that holds a service back, and a sentence naming where the chain ends."""
    first = next(d for d in sorted(by_id[sid]["depends_on"]) if status[d] != "READY")
    seen, end = {sid, first}, first
    while status[end] == "DEPENDENCY":
        nxt = next(d for d in sorted(by_id[end]["depends_on"]) if status[d] != "READY")
        if nxt in seen:
            break
        seen.add(nxt)
        end = nxt

    def label(i: str) -> str:
        return f"{by_id[i]['name']} ({i})"

    if end == first:
        return first, f"depends on {label(first)}, which is {status[first]}"
    return first, f"depends on {label(first)}, whose chain ends at {label(end)}, which is {status[end]}"


# ---------------------------------------------------------------- rendering
def clean(text) -> str:
    """Printable text on one line, so a name in the input cannot start a new line of output."""
    return "".join(ch if ch.isprintable() else " " for ch in str(text))


def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so input text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def count_by_status(results: list) -> dict:
    return {st: sum(1 for r in results if r["status"] == st) for st in STATUSES}


def domain_line(results: list) -> str:
    """Ready services per domain, grouped by the domain field and nothing inferred from names."""
    domains = sorted({r["domain"] for r in results})
    return ", ".join(f"{clean(d)} {sum(1 for r in results if r['domain'] == d and r['status'] == 'READY')} of "
                     f"{sum(1 for r in results if r['domain'] == d)}" for d in domains)


def scope_of(results: list, fail_on: str) -> list:
    return [r for r in results if fail_on == "any" or r["tier"] == 1]


def decision(results: list, fail_on: str) -> tuple:
    """(code, text) where code is READY, NOT_READY or NOTHING_CHECKED."""
    scope = scope_of(results, fail_on)
    label = "services" if fail_on == "any" else "tier-1 services"
    if not scope:
        return "NOTHING_CHECKED", "decision: NOTHING CHECKED (no tier 1 services in the map; --fail-on any checks every service)"
    bad = [r for r in scope if r["status"] not in OK_STATUSES]
    if bad:
        return "NOT_READY", f"decision: NOT READY ({len(bad)} of {len(scope)} {label} have no tested way back)"
    return "READY", f"decision: READY (all {len(scope)} {label} have a tested way back)"


def render(results: list, as_of: date, fail_on: str, fmt: str) -> str:
    code, text = decision(results, fail_on)
    scope = scope_of(results, fail_on)
    lines = []
    if fmt == "github":
        for r in results:
            if r["status"] in OK_STATUSES:
                continue
            level = "error" if r["service_id"] in {s["service_id"] for s in scope} else "warning"
            lines.append(f"::{level} title=failover-scorecard {r['status']}::"
                         + escape_annotation(f"{r['name']} (tier {r['tier']}): {r['reason']}"))
        lines.append("::notice title=failover-scorecard::" + escape_annotation(text))
        return "\n".join(lines)
    counts = count_by_status(results)
    not_ready = sum(n for st, n in counts.items() if st not in OK_STATUSES)
    lines.append(f"as of {as_of.isoformat()}: {len(results)} services, {counts['READY']} ready, "
                 f"{counts['NOT_REQUIRED']} not required, {not_ready} not ready")
    for r in sorted((r for r in results if r["status"] not in OK_STATUSES), key=lambda r: (r["tier"], r["service_id"])):
        lines.append(f"  [{r['status']:<10}] tier {r['tier']}  {clean(r['service_id'])}  {clean(r['name'])}: {clean(r['reason'])}")
    lines.append("by domain, ready of all: " + domain_line(results))
    lines.append(text)
    return "\n".join(lines)


# ---------------------------------------------------------------- command line
def run_check(services_path: str, drills_path: str, as_of_text: str, fail_on: str, fmt: str) -> int:
    try:
        as_of = parse_date(as_of_text)
        if as_of is None:
            raise InputError(f"--as-of {as_of_text!r} is not a real date written like 2026-10-24")
        services, drills = load_services(services_path), load_drills(drills_path)
        results = score(services, drills, as_of)
    except InputError as e:
        print(f"input error: {clean(e)}", file=sys.stderr)
        return 2
    print(render(results, as_of, fail_on, fmt))
    code, _ = decision(results, fail_on)
    if code == "NOTHING_CHECKED" and fail_on != "never":
        print("input error: nothing was checked, the map has no tier 1 service", file=sys.stderr)
        return 2
    return 1 if code == "NOT_READY" and fail_on != "never" else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="failover_scorecard")
    ap.add_argument("--demo", action="store_true", help="score the bundled example (data/example_*.csv)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="score a service map and a drill log")
    c.add_argument("services")
    c.add_argument("drills")
    c.add_argument("--as-of", required=True, help="the date to judge drill age against, YYYY-MM-DD")
    c.add_argument("--fail-on", choices=["tier1", "any", "never"], default="tier1")
    c.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_services.csv"), os.path.join(d, "example_drills.csv"),
                         BUNDLED_AS_OF, "never", "text")
    if a.cmd == "check":
        return run_check(a.services, a.drills, a.as_of, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
