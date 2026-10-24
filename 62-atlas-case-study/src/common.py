"""Shared loading for the four step scripts of project 62."""
from __future__ import annotations

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from atlas_case_study import build_study, find_loops, find_leaks, lint_study, phases, read_json, to_yaml  # noqa: E402,F401

# The common first attempt: read the on-call ticket and look for words. The table is mine.
KEYWORDS = [("AML.T0051.001", ("inject", "instruction", "prompt")),
            ("AML.T0034", ("cost", "spend", "budget", "bill")),
            ("AML.T0029", ("loop", "retry", "retries", "stuck", "flood"))]


def _read(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_runs() -> list:
    """The 60 flagged runs: ticket note, planted truth, and the bundle that the tool reads."""
    truth = {r["run_id"]: r for r in _read("truth.csv")}
    calls = {}
    for r in _read("tool_calls.csv"):
        calls.setdefault(r["run_id"], []).append({
            "step_index": int(r["step_index"]), "tool_name": r["tool_name"], "args": json.loads(r["args_json"]),
            "response_kind": r["response_kind"], "response_flag": r["response_flag"], "cost_usd": float(r["cost_usd"])})
    keys = read_json(os.path.join(DATA, "identifier_keys.json"))
    out = []
    for r in _read("runs.csv"):
        t = truth[r["run_id"]]
        run = {k: r[k] for k in ("run_id", "agent_id", "agent_role", "customer_id", "started_at")}
        run["cost_cap_usd"] = float(r["cost_cap_usd"])
        out.append({"run_id": r["run_id"], "scenario": t["scenario"], "worthy": t["worthy"] == "yes",
                    "truth": sorted(x for x in t["truth_techniques"].split(";") if x),
                    "planted": [x for x in t["planted_strings"].split(";") if x], "ticket": r["ticket_note"],
                    "n_calls": int(r["n_calls"]), "bundle": {"identifier_keys": keys, "synthetic": True, "run": run, "calls": calls[r["run_id"]]}})
    return out


def keyword_draft(ticket: str) -> tuple:
    """Techniques whose words appear in the ticket, and the first sentence that matched each."""
    sentences = [s.strip() + "." for s in ticket.split(".") if s.strip()]
    techs, steps = [], []
    for tech, words in KEYWORDS:
        hit = [s for s in sentences if any(w in s.lower() for w in words)]
        if hit:
            techs.append(tech)
            steps.append(hit[0])
    return sorted(techs), steps


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
