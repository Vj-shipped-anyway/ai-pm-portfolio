"""Shared loading and the baseline reader for the four step scripts of project 31."""
from __future__ import annotations

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from intake_tier_action import (CHOICES, FIELDS, POINTS, REQUIRED, RUBRIC_KEYS, assess, load_catalog, load_registry,  # noqa: E402,F401
                                plan_labels, render_comment, render_github, tier_from_score, wanted_labels)


def read_csv(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_issues() -> list:
    """The 160 issues with the hidden truth next to them. The truth is read only to score a result."""
    truth = {r["issue_number"]: r for r in read_csv("issue_truth.csv")}
    out = []
    for r in read_csv("issues.csv"):
        t = truth[r["issue_number"]]
        out.append({"issue": int(r["issue_number"]), "title": r["title"], "body_v1": r["body_v1"], "body_v2": r["body_v2"],
                    "kind": t["body_kind"], "hostile": t["hostile"] == "1", "loose": t["loose_values"] == "1",
                    "crlf": t["crlf"] == "1", "edited": t["edited"] == "1", "dataset": t["dataset_name"],
                    "true": {"customer_facing": t["true_customer_facing"], "autonomy": t["true_decision_autonomy"],
                             "data_class": t["true_data_class"], "vendor": t["true_vendor_model"],
                             "regulatory": t["true_regulatory_scope"], "exposure": t["true_financial_exposure_band"]},
                    "form_data_class": t["form_data_class"], "pasted": t["pasted_data_class"],
                    "ref": int(t["reference_tier"])})
    return out


def events(issue: dict) -> list:
    """The bodies the Action sees for one issue, in order: opened, then edited when the sponsor edited it."""
    return [issue["body_v1"]] + ([issue["body_v2"]] if issue["body_v2"] else [])


def naive_field(body: str, label: str) -> str:
    """What a first-match regex reads under a heading. This is the common basic approach, not the tool's parser."""
    m = re.search(r"### " + re.escape(label) + r"[ \t]*\r?\n\s*([^\r\n]*)", body)
    return m.group(1).strip().lower() if m else ""


def naive_assess(body: str) -> dict:
    """Issue form plus a regex: add up the points on the values as written. A missing or unreadable value
    scores 0, and no check is made against a catalog or a registry."""
    vals = {k: naive_field(body, label) for k, label in FIELDS}
    score = sum(POINTS[k].get(vals[k], 0) for k in RUBRIC_KEYS)
    found = sum(1 for k in REQUIRED if vals[k] in CHOICES[k])
    return {"tier": tier_from_score(score), "score": score, "values": vals, "found": found}


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
