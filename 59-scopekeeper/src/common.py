"""Shared loading for the four step scripts of project 59."""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from scopekeeper import analyze, effective_by_agent, load_agents, load_calls, load_catalog, load_grants, reach_of, replay  # noqa: E402,F401


def _read(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_world() -> dict:
    """The generated grants, calls, catalog and agents, plus the two truth files the rules never see."""
    needed = {(r["agent_id"], r["scope"]): {"needed": r["needed"] == "yes", "basis": r["basis"],
                                            "needed_scopes": [x for x in r["needed_scopes"].split(";") if x]}
              for r in _read("needed_truth.csv")}
    periodic = [{"agent_id": r["agent_id"], "scope": r["scope"], "next_use_date": r["next_use_date"],
                 "calls_next_quarter": int(r["calls_next_quarter"]), "why": r["why"]} for r in _read("periodic_truth.csv")]
    return {"grants": load_grants(os.path.join(DATA, "grants.csv")), "calls": load_calls(os.path.join(DATA, "calls.csv")),
            "groups": load_catalog(os.path.join(DATA, "scope_catalog.csv")),
            "agents": load_agents(os.path.join(DATA, "agents.csv")), "needed": needed, "periodic": periodic}


def annual_review(world: dict, revoke_if_no_ticket: bool = True) -> dict:
    """The common basic approach: approve a grant that has a ticket reference, revoke one that has none.

    The reviewer does not open the call log. Because the data is synthetic, the script can replay the
    calls under what the review left in place.
    """
    removed = {(g["agent_id"], g["scope"]) for g in world["grants"] if revoke_if_no_ticket and not g["ticket_id"]}
    left = [g for g in world["grants"] if (g["agent_id"], g["scope"]) not in removed]
    allowed = effective_by_agent(left, world["groups"])
    return {"removed": removed, "denied": len(replay(world["calls"], allowed, world["agents"]))}


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
