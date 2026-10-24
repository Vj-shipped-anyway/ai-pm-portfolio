"""Shared loading and scoring for the four step scripts of project 63."""
import csv
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from call_notes_actions import load_notes, load_candidates, check_all  # noqa: E402,F401


def read_csv(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_world() -> dict:
    """Notes, candidates, and the planted truth. The truth labels come from data/_generate.py, not from the checker."""
    truth = {r["cand_id"]: {"defect": r["defect"], "valid": r["valid"] == "1", "truth_id": r["truth_action_id"]}
             for r in read_csv("candidate_truth.csv")}
    return {"notes": load_notes(os.path.join(DATA, "notes.csv")),
            "cands": load_candidates(os.path.join(DATA, "candidates.csv")),
            "truth": truth,
            "actions": read_csv("truth_actions.csv"),
            "roles": Counter(r["role"] for r in read_csv("sentence_roles.csv"))}


def score(decisions: dict, world: dict) -> dict:
    """Count outcomes for {cand_id: ACCEPT|REVIEW|REJECT} against the planted truth."""
    s = Counter()
    written_ids = set()
    for c in world["cands"]:
        t, d = world["truth"][c["cand_id"]], decisions[c["cand_id"]]
        side = "valid" if t["valid"] else "unsafe"
        s[{"ACCEPT": f"{side}_written", "REVIEW": f"{side}_held", "REJECT": f"{side}_dropped"}[d]] += 1
        if t["valid"] and d == "ACCEPT":
            written_ids.add(t["truth_id"])
    s["candidates"] = len(world["cands"])
    s["valid"] = s["valid_written"] + s["valid_held"] + s["valid_dropped"]
    s["ungrounded"] = s["candidates"] - s["valid"]
    s["actions"] = len(world["actions"])
    s["actions_written"] = len(written_ids)
    s["actions_proposed"] = len({t["truth_id"] for t in world["truth"].values() if t["valid"]})
    return s


def by_cause(decisions: dict, world: dict, decision: str, valid: bool) -> Counter:
    """Planted cause -> count, for candidates with the given decision and the given validity."""
    return Counter(world["truth"][c["cand_id"]]["defect"] for c in world["cands"]
                   if decisions[c["cand_id"]] == decision and world["truth"][c["cand_id"]]["valid"] == valid)


def fmt(counter: Counter) -> str:
    return ", ".join(f"{k} {counter[k]}" for k in sorted(counter)) or "none"


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "n/a"


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
