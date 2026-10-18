"""Step 1 - Before ScopeKeeper: scopes are granted, and nobody compares them with the calls.

A modeled bank runs 15 AI agents. Each agent calls tools through scopes (read an account, write a
ledger entry, send an e-mail, initiate a payment). Scopes are granted at launch and added over
time. The control is an annual access recertification (step 2). This script describes the starting
point only: who holds what, how much of it is high-impact, how many wildcards there are, and how
many grants were added after launch. It also holds the shared loaders and helpers that the later
steps and the app import.

There is no modeled assumption in this step. Every number is a count over the shipped files.
Nothing here is a real bank, agent, platform or model; the files were written by data/_generate.py.

Run (from src/):
    python3 step_01_status_quo.py

Output: a readable summary, plus out/step_01_grants_per_agent.csv and out/step_01_summary.json.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

AS_OF = date(2026, 10, 17)                  # review date; last day of the window (same constant as the generator)
WINDOW_DAYS = 90
WINDOW_START = AS_OF - timedelta(days=WINDOW_DAYS - 1)       # day 1
IMPACT_ORDER = ["read", "write", "external_message", "money_movement"]


# ---------------------------------------------------------------------------
# Shared loaders and helpers (later steps and the app import these)
# ---------------------------------------------------------------------------
def namespace(scope: str) -> str:
    return scope.split(":")[0]


def is_wildcard(scope: str) -> bool:
    return scope.endswith(":*")


def _read(data_dir: Path, name: str) -> list:
    with open(data_dir / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_all(data_dir: Path = DATA_DIR) -> dict:
    """Load the six CSVs into plain dicts. No pandas needed."""
    agents = _read(data_dir, "agents.csv")
    by_id = {a["agent_id"]: a for a in agents}

    catalog = {}
    for r in _read(data_dir, "scope_catalog.csv"):
        catalog[r["scope"]] = {"scope": r["scope"], "kind": r["kind"], "impact": r["impact"],
                               "needs_approval": r["needs_human_approval"] == "yes"}
    members: dict = defaultdict(list)
    for s, c in catalog.items():
        if c["kind"] == "specific":
            members[namespace(s)].append(s)
    members = {k: sorted(v) for k, v in members.items()}

    grants = []
    for r in _read(data_dir, "grants.csv"):
        a = by_id[r["agent_id"]]
        c = catalog[r["scope"]]
        grants.append({
            "agent_id": r["agent_id"], "scope": r["scope"], "granted_on": r["granted_on"],
            "ticket_id": r["ticket_id"], "has_ticket": bool(r["ticket_id"]),
            "wildcard": is_wildcard(r["scope"]),
            "post_launch": r["granted_on"] > a["launched_on"],
            "impact": c["impact"], "needs_approval": c["needs_approval"],
        })
    calls = [{"call_id": r["call_id"], "agent_id": r["agent_id"], "day": int(r["day"]), "scope": r["scope_used"],
              "human_approved": r["human_approved"], "service_account": r["service_account"]}
             for r in _read(data_dir, "calls.csv")]
    rare = [{"agent_id": r["agent_id"], "scope": r["scope"], "last_use_date": r["last_use_date"],
             "cycle_days": int(r["cycle_days"]), "next_use_date": r["next_use_date"],
             "calls_next_quarter": int(r["calls_next_quarter"]), "why": r["why"]}
            for r in _read(data_dir, "rare_use_truth.csv")]
    needed = {(r["agent_id"], r["scope"]): {"needed": r["needed"] == "yes", "basis": r["basis"],
                                            "needed_scopes": [x for x in r["needed_scopes"].split(";") if x]}
              for r in _read(data_dir, "needed_truth.csv")}

    sa_agents: dict = defaultdict(list)
    for a in agents:
        sa_agents[a["service_account"]].append(a["agent_id"])
    sa_agents = dict(sa_agents)

    grants_by_agent: dict = defaultdict(list)
    for g in grants:
        grants_by_agent[g["agent_id"]].append(g)
    grants_by_agent = dict(grants_by_agent)

    data = {"agents": agents, "agent_by_id": by_id, "catalog": catalog, "members": members, "grants": grants,
            "grants_by_agent": grants_by_agent, "calls": calls, "rare": rare, "needed": needed,
            "sa_agents": sa_agents, "shared_accounts": sorted(k for k, v in sa_agents.items() if len(v) > 1)}
    data["effective"] = {a["agent_id"]: effective_scopes(data, a["agent_id"]) for a in agents}
    return data


def date_of_day(day: int) -> str:
    return (WINDOW_START + timedelta(days=day - 1)).isoformat()


def expand(data: dict, scope: str) -> list:
    """The specific scopes one grant reaches: itself, or every member of a wildcard's namespace."""
    return list(data["members"][namespace(scope)]) if is_wildcard(scope) else [scope]


def effective_scopes(data: dict, agent_id: str, grants: list | None = None) -> list:
    """Effective entitlements of an agent: specific scopes it can reach, wildcards expanded."""
    out = set()
    for g in (grants if grants is not None else data["grants_by_agent"].get(agent_id, [])):
        out.update(expand(data, g["scope"]))
    return sorted(out)


def usage_index(data: dict) -> dict:
    """Which (agent, scope) pairs the 90 days of calls touched.

    A call with an agent tag credits that agent. A call with no tag (shared service account) is
    credited to every agent on that account who could have made it, so nothing in use is ever
    marked unused. The cost is that a sibling's use can make an unneeded grant look used.
    """
    tagged: Counter = Counter()
    shared: Counter = Counter()
    unattributed = 0
    for c in data["calls"]:
        if c["agent_id"]:
            tagged[(c["agent_id"], c["scope"])] += 1
        else:
            unattributed += 1
            for a in data["sa_agents"][c["service_account"]]:
                if c["scope"] in data["effective"][a]:
                    shared[(a, c["scope"])] += 1
    return {"tagged": tagged, "shared": shared, "unattributed": unattributed,
            "used_pairs": set(tagged) | set(shared)}


def grant_usage(data: dict, u: dict) -> list:
    """One row per grant: was it used, which specific scopes were touched, from which kind of call."""
    rows = []
    for g in data["grants"]:
        a, s = g["agent_id"], g["scope"]
        reach = expand(data, s)
        touched = [m for m in reach if (a, m) in u["used_pairs"]]
        touched_tagged = [m for m in reach if u["tagged"][(a, m)] > 0]
        rows.append({**g, "reach": len(reach), "touched": touched, "touched_tagged": touched_tagged,
                     "calls_tagged": sum(u["tagged"][(a, m)] for m in reach),
                     "calls_shared": sum(u["shared"][(a, m)] for m in reach),
                     "used": bool(touched), "only_shared": bool(touched) and not touched_tagged})
    return rows


def replay_calls(data: dict, allowed: dict) -> list:
    """Dry-run: which calls would be denied if each agent could reach only allowed[agent].

    A tagged call is tested against its agent. A call with no tag is tested against the union of
    the agents on its service account, because the account is all the platform could see.
    """
    denied = []
    for c in data["calls"]:
        if c["agent_id"]:
            ok = c["scope"] in allowed.get(c["agent_id"], ())
        else:
            ok = any(c["scope"] in allowed.get(a, ()) for a in data["sa_agents"][c["service_account"]])
        if not ok:
            denied.append(c)
    return denied


# ---------------------------------------------------------------------------
# Step 1 summary
# ---------------------------------------------------------------------------
def summarize(data: dict) -> dict:
    grants = data["grants"]
    per_agent = []
    for a in data["agents"]:
        aid = a["agent_id"]
        gs = data["grants_by_agent"][aid]
        per_agent.append({
            "agent_id": aid, "tier": a["risk_tier"], "service_account": a["service_account"],
            "shared": a["service_account"] in data["shared_accounts"],
            "grants": len(gs), "wildcards": sum(1 for g in gs if g["wildcard"]),
            "high_impact": sum(1 for g in gs if g["needs_approval"]),
            "post_launch": sum(1 for g in gs if g["post_launch"]),
            "reach": len(data["effective"][aid]),
        })
    hi = [g for g in grants if g["needs_approval"]]
    by_impact = Counter(g["impact"] for g in hi)
    wild = [g for g in grants if g["wildcard"]]
    return {
        "agents": len(data["agents"]), "service_accounts": len(data["sa_agents"]),
        "shared_accounts": len(data["shared_accounts"]),
        "agents_on_shared": sum(len(data["sa_agents"][s]) for s in data["shared_accounts"]),
        "scopes": len(data["catalog"]), "wildcard_scopes": sum(1 for c in data["catalog"].values() if c["kind"] == "wildcard"),
        "grants": len(grants), "calls": len(data["calls"]),
        "wildcard_grants": len(wild), "high_impact_grants": len(hi),
        "high_impact_by_impact": {k: by_impact.get(k, 0) for k in IMPACT_ORDER if by_impact.get(k, 0)},
        "post_launch_grants": sum(1 for g in grants if g["post_launch"]),
        "no_ticket_grants": sum(1 for g in grants if not g["has_ticket"]),
        "reach_total": sum(len(v) for v in data["effective"].values()),
        "wildcard_extra_reach": sum(len(expand(data, g["scope"])) - 1 for g in wild),
        "per_agent": per_agent,
        "window_start": WINDOW_START.isoformat(), "as_of": AS_OF.isoformat(),
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    s = summarize(data)

    print("\n" + "=" * 78)
    print("Step 1 - Before ScopeKeeper: scopes are granted, and nobody compares them with the calls")
    print("=" * 78)
    print(f"\n{s['agents']} agents on {s['service_accounts']} service accounts "
          f"({s['agents_on_shared']} agents share {s['shared_accounts']} of the accounts).")
    print(f"{s['scopes']} scopes in the catalog ({s['wildcard_scopes']} of them wildcards such as accounts:*).")
    print(f"{s['grants']} grants and {s['calls']:,} calls over {WINDOW_DAYS} days "
          f"(day 1 = {s['window_start']}, review date {s['as_of']}).")
    print("Data is synthetic and seeded. No modeled assumption in this step: every figure is a count.\n")

    print("GRANTS PER AGENT")
    print(f"{'agent':<6} {'tier':<7} {'account':<8} {'grants':>6} {'wild':>5} {'high-impact':>11} "
          f"{'after launch':>12} {'reach':>6}")
    print(f"{'-' * 6} {'-' * 7} {'-' * 8} {'-' * 6} {'-' * 5} {'-' * 11} {'-' * 12} {'-' * 6}")
    for r in s["per_agent"]:
        print(f"{r['agent_id']:<6} {r['tier']:<7} {r['service_account']:<8} {r['grants']:>6} {r['wildcards']:>5} "
              f"{r['high_impact']:>11} {r['post_launch']:>12} {r['reach']:>6}")

    print("\nWILDCARD GRANTS (a wildcard reaches every specific scope in its namespace)")
    for g in data["grants"]:
        if g["wildcard"]:
            print(f"  {g['agent_id']}  {g['scope']:<12} reaches {len(expand(data, g['scope']))} specific scopes, "
                  f"impact {g['impact']}")

    print("\nHIGH-IMPACT GRANTS (the catalog says a human must approve the call)")
    parts = ", ".join(f"{k} {v}" for k, v in s["high_impact_by_impact"].items())
    print(f"  {s['high_impact_grants']} of {s['grants']} grants ({parts})")

    print("\nRESULT")
    print(f"  Grants held:                                  {s['grants']} ({s['wildcard_grants']} wildcards)")
    print(f"  Effective entitlements (agent x specific scope, wildcards expanded): {s['reach_total']}")
    print(f"  Added after launch:                           {s['post_launch_grants']} of {s['grants']} "
          f"({100 * s['post_launch_grants'] / s['grants']:.1f}%)")
    print(f"  Grants with no ticket reference:              {s['no_ticket_grants']} of {s['grants']}")
    print(f"  Control in place:                             annual recertification (step 2)")
    print(f"  Script that compares grants with calls:       none")

    with open(OUT_DIR / "step_01_grants_per_agent.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["agent_id", "tier", "service_account", "grants", "wildcards", "high_impact", "post_launch", "reach"])
        for r in s["per_agent"]:
            w.writerow([r["agent_id"], r["tier"], r["service_account"], r["grants"], r["wildcards"],
                        r["high_impact"], r["post_launch"], r["reach"]])
    with open(OUT_DIR / "step_01_summary.json", "w") as f:
        json.dump({k: v for k, v in s.items() if k != "per_agent"}, f, indent=2)
    print("\nWrote src/out/step_01_grants_per_agent.csv and step_01_summary.json")


if __name__ == "__main__":
    main()
