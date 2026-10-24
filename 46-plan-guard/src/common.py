"""Shared loading for the four step scripts of project 46."""
from __future__ import annotations

import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from plan_guard import check_plan, decide, RULES  # noqa: E402,F401

TRUTH_TO_DECISION = {"block": "BLOCK", "review": "REVIEW", "ok": "ALLOW"}
# The three kinds of risky plan the rules cannot see; data/_generate.py plants them on purpose.
HARD_MISS_KINDS = ("split_world_cidr", "policy_weak_condition", "queue_policy_world")


# The text search a team adds first (step 2); step 3 also reports what it flags.
PATTERNS = [r"0\.0\.0\.0/0", r"::/0", r'"(?:public-read|public-read-write|authenticated-read)"',
            r'(?:Principal|AWS)\\*"\s*:\s*\\*"\*', r'"(?:encrypted|storage_encrypted)":false',
            r'"publicly_accessible":true',
            r'"(?:block_public_acls|block_public_policy|ignore_public_acls|restrict_public_buckets)":false',
            r'"protocol":"HTTP"']
COMPILED = [re.compile(p) for p in PATTERNS]


def flagged_by_search(plan: dict) -> bool:
    text = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    return any(p.search(text) for p in COMPILED)


def load_plans() -> list:
    """The 86 plans with their planted truth."""
    truth = {}
    with open(os.path.join(DATA, "plan_truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            truth[r["plan_id"]] = r
    plans = []
    with open(os.path.join(DATA, "plans.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = truth[r["plan_id"]]
            plans.append({"plan_id": r["plan_id"], "text": r["plan_json"], "plan": json.loads(r["plan_json"]),
                          "kind": t["kind"], "truth": t["truth_class"], "target": t["target_address"],
                          "expected": t["expected_rule"]})
    return plans


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
