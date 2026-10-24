"""Shared loading and scoring for the four step scripts of project 45."""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from concentration_register import (  # noqa: E402,F401
    fmt_pct, load_deps, load_services, lost_set, make_register, over_limit)

LIMIT_PCT = 30.0  # an assumption: no rule names a number, see the README


def _rows(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_register() -> tuple:
    """(services, edges, register) for the bundled 64-service register."""
    services = load_services(os.path.join(DATA, "services.csv"))
    edges = load_deps(os.path.join(DATA, "dependencies.csv"), services)
    return services, edges, make_register(services, edges)


def load_truth() -> dict:
    """What the generator decided: true placements, every edge, and the critical services lost per scenario."""
    scenarios = []
    for r in _rows("truth_scenarios.csv"):
        scenarios.append({"id": r["scenario_id"], "kind": r["kind"], "provider": r["provider"], "region": r["region"],
                          "lost": set(filter(None, r["critical_lost_ids"].split(";")))})
    return {"services": {r["service_id"]: r for r in _rows("truth_services.csv")},
            "edges": _rows("truth_edges.csv"), "scenarios": scenarios}


def with_truth(services: dict, edges: list, truth: dict, placements: bool = False, unlisted: bool = False,
               failovers: bool = False) -> dict:
    """A register that is given some of what the real register lacks. Used to say where a miss comes from."""
    svc = {sid: dict(s) for sid, s in services.items()}
    for sid, s in svc.items():
        t = truth["services"][sid]
        if placements and s["primary"] is None:
            s["primary"] = (t["true_provider"], t["true_region"])
            s["resilience"] = t["true_resilience"]
            s["second"] = (t["true_standby_provider"], t["true_standby_region"]) if t["true_standby_provider"] else None
        if failovers and t["failover_works"] == "no" and s["primary"] is not None:
            s["resilience"], s["second"] = "single", None
    extra = [(e["service_id"], e["depends_on"], "hard") for e in truth["edges"] if e["listed"] == "no"] if unlisted else []
    return make_register(svc, sorted(set(edges) | set(extra)))


def score(reg: dict, truth: dict, **flags) -> dict:
    """Compare the critical services the tool says are lost with the truth, scenario by scenario.
    flags go to lost_set (deps, failover, soft_as_hard)."""
    critical = {sid for sid, s in reg["services"].items() if s["criticality"] == "critical"}
    rows = []
    for sc in truth["scenarios"]:
        pred = lost_set(reg, sc, **flags) & critical
        rows.append({"scenario": sc["id"], "kind": sc["kind"], "provider": sc["provider"], "truth": len(sc["lost"]), "pred": len(pred),
                     "tp": len(pred & sc["lost"]), "fp": len(pred - sc["lost"]), "fn": len(sc["lost"] - pred),
                     "critical_total": len(critical)})
    return {"rows": rows, "truth": sum(r["truth"] for r in rows), "pred": sum(r["pred"] for r in rows),
            "tp": sum(r["tp"] for r in rows), "fp": sum(r["fp"] for r in rows), "fn": sum(r["fn"] for r in rows)}


def flag_counts(sc: dict, limit_pct: float) -> dict:
    """Over-limit scenarios in truth against over-limit scenarios flagged, from score(...)['rows']."""
    rows = sc["rows"]
    t = {r["scenario"] for r in rows if over_limit(r["truth"], r["critical_total"], limit_pct)}
    f = {r["scenario"] for r in rows if over_limit(r["pred"], r["critical_total"], limit_pct)}
    return {"truth": sorted(t), "flagged": sorted(f), "caught": sorted(t & f), "false": sorted(f - t), "missed": sorted(t - f)}


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
