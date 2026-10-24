"""Shared loading and scoring for the four step scripts of project 61."""
import csv
import json
import os
from collections import Counter

from mcp_scope_lint import parse_manifest, reach

RISKY_ACCESS = ("any", "delete", "admin")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")


def load_servers() -> list:
    """The 30 manifests, parsed. Each item is the parsed manifest from mcp_scope_lint.parse_manifest."""
    with open(os.path.join(DATA, "manifests.json"), encoding="utf-8") as fh:
        return [parse_manifest(obj) for obj in json.load(fh)]


def load_entitlement_truth() -> dict:
    """{server: {scope: (needed, planted)}} for every scope the grants reach. The label comes from the generator."""
    out = {}
    with open(os.path.join(DATA, "entitlement_truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(r["server"], {})[r["scope"]] = (r["needed"] == "yes", r["planted"])
    return out


def load_tool_scope_truth() -> dict:
    """{(server, tool, scope): (needed, planted)} for every scope a tool declares."""
    out = {}
    with open(os.path.join(DATA, "tool_scope_truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[(r["server"], r["tool"], r["scope"])] = (r["needed"] == "yes", r["planted"])
    return out


def score_cuts(cuts: dict, truth: dict) -> dict:
    """Score a set of cut scopes per server against the generator's truth.
    cuts is {server: iterable of scope ids}. Counts are over the scopes the grants reach."""
    reach_n = unneeded = cut_unneeded = needed_cut = 0
    kept_unneeded_by, needed_cut_by = Counter(), Counter()
    for server, rows in truth.items():
        cut = set(cuts.get(server, ()))
        for scope, (needed, planted) in rows.items():
            reach_n += 1
            if needed and scope in cut:
                needed_cut += 1
                needed_cut_by[planted] += 1
            if not needed:
                unneeded += 1
                if scope in cut:
                    cut_unneeded += 1
                else:
                    kept_unneeded_by[planted] += 1
    return {"reach": reach_n, "unneeded": unneeded, "cut_unneeded": cut_unneeded, "kept_unneeded": unneeded - cut_unneeded,
            "needed_cut": needed_cut, "kept_unneeded_by": kept_unneeded_by, "needed_cut_by": needed_cut_by}


def blocklist_cut(m: dict) -> frozenset:
    """Scopes lost when every wildcard, delete and admin grant is removed (the step 2 approach)."""
    keep = [g for g in m["granted"] if m["by_id"][g]["access"] not in RISKY_ACCESS]
    return reach(m, m["granted"]) - reach(m, keep)


def fmt_counter(c: Counter) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(c.items())) or "none"


def total_reach(servers: list) -> int:
    return sum(len(reach(m, m["granted"])) for m in servers)


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
