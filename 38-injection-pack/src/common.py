"""Shared loading and scoring for the four step scripts of project 38."""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from injection_pack import build_gateway, compare, load_pack, load_rules, run_pack, summarize  # noqa: E402,F401

# A rule change counts as harmful when, on the held-out population, it lowers the share of attacks
# blocked by at least this many percentage points, or raises the share of benign cases blocked by at
# least this many. An assumption (yellow in the README), not a standard.
HARM_POINTS = 1


def load_world() -> dict:
    prs = []
    with open(os.path.join(DATA, "rule_prs.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            prs.append({"pr_id": r["pr_id"], "kind": r["kind"], "layer": r["layer"], "note": r["note"], "rules": json.loads(r["new_rules_json"])})
    return {"base": load_rules(os.path.join(DATA, "gateway_rules.json")),
            "pack": load_pack(os.path.join(DATA, "pack.csv")),
            "population": load_pack(os.path.join(DATA, "population.csv")),
            "prs": prs}


def population_effect(base_rules: dict, new_rules: dict, population: list) -> dict:
    """What a rule change does to the held-out population: net attacks lost, net benign cases newly blocked, per technique."""
    before = run_pack(build_gateway(base_rules), population)
    after = run_pack(build_gateway(new_rules), population)
    n_att = sum(1 for r in before if r["expected"] == "block")
    n_ben = len(before) - n_att
    delta = Counter()
    lost = gained = 0
    for b, a in zip(before, after):
        step = int(a["blocked"]) - int(b["blocked"])
        delta[b["technique"]] += step
        if b["expected"] == "block":
            lost -= step
        else:
            gained += step
    catch_harm = lost * 100 >= HARM_POINTS * n_att
    fp_harm = gained * 100 >= HARM_POINTS * n_ben
    return {"lost": lost, "gained": gained, "catch_harm": catch_harm, "fp_harm": fp_harm, "harmful": catch_harm or fp_harm,
            "delta": {k: v for k, v in sorted(delta.items()) if v}}


def score_prs(world: dict) -> list:
    """The held-out truth for every rule pull request."""
    rows = []
    for pr in world["prs"]:
        e = population_effect(world["base"], pr["rules"], world["population"])
        rows.append({"pr_id": pr["pr_id"], "kind": pr["kind"], "layer": pr["layer"], "note": pr["note"],
                     "lost": e["lost"], "gained": e["gained"], "harmful": e["harmful"],
                     "harm_type": "both" if e["catch_harm"] and e["fp_harm"] else "catch" if e["catch_harm"] else "false_blocks" if e["fp_harm"] else "none",
                     "delta": e["delta"]})
    return rows


def pack_decisions(world: dict, cases: list) -> dict:
    """{pr_id: (decision, number of regressions)} when the pack `cases` is replayed on the base rules and on each pull request."""
    out = {}
    for pr in world["prs"]:
        res = compare(world["base"], pr["rules"], cases)
        out[pr["pr_id"]] = ("BLOCK" if res["regressions"] else "ALLOW", len(res["regressions"]), bool(res["blind"]))
    return out


def tally(rows: list, decisions: dict) -> dict:
    """Score a set of decisions against the held-out truth."""
    harmful = [r for r in rows if r["harmful"]]
    harmless = [r for r in rows if not r["harmful"]]
    return {"harmful": len(harmful), "harmless": len(harmless),
            "harmful_blocked": sum(1 for r in harmful if decisions[r["pr_id"]] == "BLOCK"),
            "harmless_blocked": sum(1 for r in harmless if decisions[r["pr_id"]] == "BLOCK"),
            "exact": sum(1 for r in rows if (decisions[r["pr_id"]] == "BLOCK") == r["harmful"])}


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def write_json(name: str, obj: dict) -> None:
    ensure_out()
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.write("\n")
