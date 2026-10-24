"""concentration_register: which critical services sit on one cloud provider or in one region, once the
dependencies between services and the failover each service claims are followed. Standard library only.
Python 3.9 or newer.

Command line (from src/):
    python3 concentration_register.py --demo
    python3 concentration_register.py check SERVICES.csv [--deps DEPS.csv] [--limit-pct 30] [--format text|json]

Exit status: 0 when no outage scenario loses more than the limit of critical services, 1 when one does,
2 for bad or malformed input.

Input, one row per service (services.csv):
    service_id, name, owner_type (internal|saas), criticality (critical|important|standard),
    provider, region, resilience (single|warm_standby|active_active), standby_provider, standby_region
Provider and region are both blank when the owner does not disclose where the service runs.
Dependencies (deps.csv): service_id, depends_on, kind (hard|soft). A hard dependency takes the service
down when the target is down; a soft one does not.

An outage scenario is one provider going dark (P:CP-1) or one region of one provider (R:CP-1/R1). A service
is lost in a scenario when its placement is hit and no second placement survives, or when a hard
dependency is lost. There is no model in this file: the loss is plain set propagation. The figures
are a lower bound, because a service with no placement, a dependency nobody listed and a standby that
does not take over all look fine here.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

CRITICALITY = ("critical", "important", "standard")
OWNERS = ("internal", "saas")
RESILIENCE = ("single", "warm_standby", "active_active")
KINDS = ("hard", "soft")
SERVICE_COLUMNS = ("service_id", "name", "owner_type", "criticality", "provider", "region", "resilience",
                   "standby_provider", "standby_region")
DEP_COLUMNS = ("service_id", "depends_on", "kind")
DEFAULT_LIMIT_PCT = 30.0
ROWS_SHOWN = 6
IDS_SHOWN = 5


def clean(text, limit: int = 60) -> str:
    """Make untrusted text safe to print on one line: control and non-printable characters are escaped."""
    out = []
    for ch in str(text):
        o = ord(ch)
        out.append(ch if ch.isprintable() else (f"\\x{o:02x}" if o < 256 else f"\\u{o:04x}"))
    s = "".join(out)
    return s if len(s) <= limit else s[:limit - 3] + "..."


def fmt_pct(n: int, total: int) -> str:
    return f"{100.0 * n / total:.1f}%" if total else "0.0%"


def over_limit(n: int, total: int, limit_pct: float) -> bool:
    return n * 100 > limit_pct * total


# ---------------------------------------------------------------- reading
def _read_rows(path: str, columns, label: str) -> list:
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
    except csv.Error as e:
        raise ValueError(f"{label}: not readable as CSV ({clean(e)})")
    if not rows:
        raise ValueError(f"{label}: the file is empty")
    header = [h.strip() for h in rows[0]]
    missing = [c for c in columns if c not in header]
    if missing:
        raise ValueError(f"{label}: missing column(s) {', '.join(missing)}")
    out = []
    for n, row in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in row):
            continue
        if len(row) != len(header):
            raise ValueError(f"{label} line {n}: expected {len(header)} fields, found {len(row)}")
        out.append((n, {h: c.strip() for h, c in zip(header, row)}))
    return out


def _pair(a: str, b: str, what: str, label: str, n: int):
    if bool(a) != bool(b):
        raise ValueError(f"{label} line {n}: {what} provider and region must both be filled or both be blank")
    return (a, b) if a else None


def load_services(path: str) -> dict:
    label = "services"
    services = {}
    for n, r in _read_rows(path, SERVICE_COLUMNS, label):
        sid = r["service_id"]
        if not sid:
            raise ValueError(f"{label} line {n}: service_id is blank")
        if sid in services:
            raise ValueError(f"{label} line {n}: duplicate service_id {clean(sid)!r}")
        if not r["name"]:
            raise ValueError(f"{label} line {n}: name is blank")
        if r["owner_type"] not in OWNERS:
            raise ValueError(f"{label} line {n}: owner_type {clean(r['owner_type'])!r} is not one of {', '.join(OWNERS)}")
        if r["criticality"] not in CRITICALITY:
            raise ValueError(f"{label} line {n}: criticality {clean(r['criticality'])!r} is not one of {', '.join(CRITICALITY)}")
        primary = _pair(r["provider"], r["region"], "primary", label, n)
        second = _pair(r["standby_provider"], r["standby_region"], "standby", label, n)
        mode = r["resilience"]
        if primary is None:
            if mode or second:
                raise ValueError(f"{label} line {n}: resilience and standby need a primary provider and region")
        else:
            if mode not in RESILIENCE:
                raise ValueError(f"{label} line {n}: resilience {clean(mode)!r} is not one of {', '.join(RESILIENCE)}")
            if (mode == "single") == (second is not None):
                raise ValueError(f"{label} line {n}: a standby is required for {mode} and not allowed for single")
        services[sid] = {"id": sid, "name": r["name"], "owner": r["owner_type"], "criticality": r["criticality"],
                         "primary": primary, "resilience": mode, "second": second}
    if not services:
        raise ValueError(f"{label}: the file has a header and no services")
    return services


def load_deps(path: str, services: dict) -> list:
    label = "dependencies"
    edges = set()
    for n, r in _read_rows(path, DEP_COLUMNS, label):
        a, b, kind = r["service_id"], r["depends_on"], r["kind"]
        if kind not in KINDS:
            raise ValueError(f"{label} line {n}: kind {clean(kind)!r} is not one of {', '.join(KINDS)}")
        for sid in (a, b):
            if sid not in services:
                raise ValueError(f"{label} line {n}: {clean(sid)!r} is not a service_id in the services file")
        if a == b:
            raise ValueError(f"{label} line {n}: {clean(a)!r} depends on itself")
        edges.add((a, b, kind))
    return sorted(edges)


def make_register(services: dict, edges: list) -> dict:
    """Index the services and edges. Raises ValueError when the hard dependencies contain a cycle."""
    hard = {sid: [] for sid in services}
    soft = {sid: [] for sid in services}
    hard_rev = {sid: [] for sid in services}
    soft_rev = {sid: [] for sid in services}
    for a, b, kind in edges:
        (hard if kind == "hard" else soft)[a].append(b)
        (hard_rev if kind == "hard" else soft_rev)[b].append(a)
    waiting = {sid: len(deps) for sid, deps in hard.items()}
    ready = sorted(sid for sid, k in waiting.items() if k == 0)
    done = 0
    while ready:
        d = ready.pop()
        done += 1
        for s in hard_rev[d]:
            waiting[s] -= 1
            if waiting[s] == 0:
                ready.append(s)
    if done < len(services):
        stuck = sorted(sid for sid, k in waiting.items() if k > 0)
        raise ValueError("hard dependencies form a cycle involving " + ", ".join(clean(s) for s in stuck[:3]))
    return {"services": services, "edges": list(edges), "hard": hard, "soft": soft,
            "hard_rev": hard_rev, "soft_rev": soft_rev}


# ---------------------------------------------------------------- the model
def scenarios_for(services: dict) -> list:
    """One scenario per provider and one per (provider, region) that appears as a primary or a standby."""
    seen = set()
    for s in services.values():
        for placement in (s["primary"], s["second"]):
            if placement:
                seen.add(placement)
    out = [{"id": "P:" + p, "kind": "provider", "provider": p, "region": ""} for p in sorted({p for p, _ in seen})]
    out += [{"id": f"R:{p}/{r}", "kind": "region", "provider": p, "region": r} for p, r in sorted(seen)]
    return out


def hit(sc: dict, placement) -> bool:
    return placement is not None and placement[0] == sc["provider"] and (sc["kind"] == "provider" or placement[1] == sc["region"])


def lost_set(reg: dict, sc: dict, deps: bool = True, failover: bool = True, soft_as_hard: bool = False) -> set:
    """Services lost in one scenario. deps=False ignores dependencies, failover=False ignores the second
    placement, soft_as_hard=True treats a soft dependency as a hard one (the naive variant)."""
    down = set()
    for sid, s in reg["services"].items():
        if not hit(sc, s["primary"]):
            continue
        if failover and s["second"] is not None and not hit(sc, s["second"]):
            continue
        down.add(sid)
    if deps:
        maps = (reg["hard_rev"], reg["soft_rev"]) if soft_as_hard else (reg["hard_rev"],)
        queue = sorted(down)
        while queue:
            d = queue.pop()
            for m in maps:
                for s in m[d]:
                    if s not in down:
                        down.add(s)
                        queue.append(s)
    return down


def analyze(reg: dict, limit_pct: float = DEFAULT_LIMIT_PCT) -> dict:
    services = reg["services"]
    critical = sorted(sid for sid, s in services.items() if s["criticality"] == "critical")
    if not critical:
        raise ValueError("no service has criticality 'critical', so there is nothing to measure")
    total = len(critical)
    crit_set = set(critical)
    rows = []
    for sc in scenarios_for(services):
        direct = sorted(lost_set(reg, sc, deps=False, failover=False) & crit_set)
        eff = sorted(lost_set(reg, sc) & crit_set)
        rows.append({"scenario": sc["id"], "kind": sc["kind"], "provider": sc["provider"], "region": sc["region"],
                     "direct_critical": len(direct), "effective_critical": len(eff), "critical_total": total,
                     "over_limit": over_limit(len(eff), total, limit_pct), "effective_ids": eff})
    rows.sort(key=lambda r: (-r["effective_critical"], -r["direct_critical"], r["scenario"]))
    unplaced = [sid for sid in critical if services[sid]["primary"] is None]
    shared_fate = sorted(sid for sid, s in services.items() if s["primary"] is not None and s["second"] == s["primary"])
    return {"services": len(services), "critical": total,
            "providers": sorted({r["provider"] for r in rows}), "regions": sum(1 for r in rows if r["kind"] == "region"),
            "hard_edges": sum(len(v) for v in reg["hard"].values()), "soft_edges": sum(len(v) for v in reg["soft"].values()),
            "limit_pct": limit_pct, "scenarios": rows, "over": [r["scenario"] for r in rows if r["over_limit"]],
            "unplaced_critical": unplaced, "standby_same_placement": shared_fate}


# ---------------------------------------------------------------- output
def _ids(reg: dict, ids: list) -> str:
    shown = ", ".join(f"{clean(i)} {clean(reg['services'][i]['name'], 30)}" for i in ids[:IDS_SHOWN])
    return shown + (f" and {len(ids) - IDS_SHOWN} more" if len(ids) > IDS_SHOWN else "")


def render(reg: dict, res: dict, deps_given: bool) -> str:
    lim = f"{res['limit_pct']:g}%"
    lines = [f"register: {res['services']} services ({res['critical']} critical), {len(res['providers'])} providers, "
             f"{res['regions']} regions; {res['hard_edges']} hard and {res['soft_edges']} soft dependencies"]
    if not deps_given:
        lines.append("dependencies: no file given, so no dependency was followed")
    elif not res["hard_edges"] and not res["soft_edges"]:
        lines.append("dependencies: the file has no rows, so no dependency was followed")
    lines.append(f"critical services lost per outage scenario (limit {lim})")
    lines.append(f"  {'scenario':<12} {'direct view':<16} with dependencies and failover")
    for r in res["scenarios"][:ROWS_SHOWN]:
        d = f"{r['direct_critical']} of {r['critical_total']} ({fmt_pct(r['direct_critical'], r['critical_total'])})"
        e = f"{r['effective_critical']} of {r['critical_total']} ({fmt_pct(r['effective_critical'], r['critical_total'])})"
        lines.append(f"  {clean(r['scenario']):<12} {d:<16} {e}" + ("  OVER" if r["over_limit"] else ""))
    if len(res["scenarios"]) > ROWS_SHOWN:
        lines.append(f"  ({len(res['scenarios']) - ROWS_SHOWN} more scenarios; --format json lists all)")
    if res["unplaced_critical"]:
        n = len(res["unplaced_critical"])
        lines.append(f"unplaced: {n} critical service{'s' if n != 1 else ''} with no provider or region ("
                     f"{_ids(reg, res['unplaced_critical'])}); the figures above are a lower bound")
    if res["standby_same_placement"]:
        n = len(res["standby_same_placement"])
        lines.append(f"standby in the same provider and region as the primary: {n} service{'s' if n != 1 else ''} ("
                     f"{_ids(reg, res['standby_same_placement'])})")
    if res["over"]:
        lines.append(f"decision: OVER LIMIT ({len(res['over'])} of {len(res['scenarios'])} scenarios lose more than {lim} of critical services)")
    else:
        lines.append(f"decision: WITHIN LIMIT (no scenario loses more than {lim} of critical services)")
    return "\n".join(lines)


def run_check(services_path: str, deps_path, limit_pct: float, fmt: str, fail_on_over: bool = True) -> int:
    try:
        services = load_services(services_path)
        edges = load_deps(deps_path, services) if deps_path else []
        reg = make_register(services, edges)
        res = analyze(reg, limit_pct)
    except (OSError, ValueError) as e:
        print(f"input error: {clean(e, 300)}", file=sys.stderr)
        return 2
    if fmt == "json":
        print(json.dumps(res, indent=1, sort_keys=True))
    else:
        print(render(reg, res, bool(deps_path)))
    return 1 if (fail_on_over and res["over"]) else 0


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(f"input error: {clean(message, 300)}", file=sys.stderr)
        raise SystemExit(2)


def _limit(text: str) -> float:
    try:
        v = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"--limit-pct must be a number, got {clean(text)!r}")
    if not 0 <= v <= 100:
        raise argparse.ArgumentTypeError("--limit-pct must be between 0 and 100")
    return v


def main(argv=None) -> int:
    ap = _Parser(prog="concentration_register")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_*.csv)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="measure concentration in a services file")
    c.add_argument("services")
    c.add_argument("--deps", help="dependencies CSV: service_id, depends_on, kind")
    c.add_argument("--limit-pct", type=_limit, default=DEFAULT_LIMIT_PCT,
                   help="flag a scenario that loses more than this share of critical services (default 30, an assumption)")
    c.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_services.csv"), os.path.join(d, "example_deps.csv"),
                         DEFAULT_LIMIT_PCT, "text", fail_on_over=False)
    if a.cmd == "check":
        return run_check(a.services, a.deps, a.limit_pct, a.format)
    ap.error("give --demo or the check command")


if __name__ == "__main__":
    sys.exit(main())
