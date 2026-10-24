"""Shared loading for the four step scripts of project 35."""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from tiergate import read_catalog, read_intake, read_registry, rubric_score, tier_from_score  # noqa: E402

FULL_REVIEW_TIER = 3  # assumption: tier 3 and 4 get the full review
HARD_CASES = ("class_understated_in_form_and_catalog", "class_understated_dataset_not_listed",
              "vendor_omitted_and_not_in_registry", "customer_facing_denied_and_text_silent")
HARD_NEGATIVES = ("text_names_customers_but_internal", "catalog_overstates_class")


def load_cases() -> list:
    """The intake forms the tool sees, joined to the hidden truth by use_case_id."""
    path = os.path.join(DATA, "intake_submissions.csv")
    forms = read_intake(path)
    with open(path, newline="", encoding="utf-8") as fh:
        truth = {r["use_case_id"]: r for r in csv.DictReader(fh)}
    cases = []
    for form in forms:
        t = truth[form["use_case_id"]]
        case = dict(form)
        case.update({"true_customer_facing": t["true_customer_facing"], "true_data_class": t["true_data_class"],
                     "true_vendor_model": t["true_vendor_model"], "reference_score": int(t["reference_score"]),
                     "reference_tier": int(t["reference_tier"]),
                     "planted": [] if t["planted"] == "none" else t["planted"].split(";")})
        cases.append(case)
    return cases


def load_second_sources() -> tuple:
    return (read_catalog(os.path.join(DATA, "data_catalog.csv")),
            read_registry(os.path.join(DATA, "vendor_registry.csv")))


def form_as_written_tier(case: dict) -> int:
    """The basic approach: re-add the rubric points on the form exactly as the sponsor filled it in."""
    return tier_from_score(rubric_score(case["customer_facing"], case["decision_autonomy"], case["data_class"],
                                        case["vendor_model"], case["regulatory_scope"],
                                        case["financial_exposure_band"]))


def metrics(cases: list, tiers: dict) -> dict:
    """Score {use_case_id: tier} against the reference tier."""
    full = [c for c in cases if c["reference_tier"] >= FULL_REVIEW_TIER]
    return {"n": len(cases),
            "exact": sum(1 for c in cases if tiers[c["use_case_id"]] == c["reference_tier"]),
            "under": sum(1 for c in cases if tiers[c["use_case_id"]] < c["reference_tier"]),
            "over": sum(1 for c in cases if tiers[c["use_case_id"]] > c["reference_tier"]),
            "full": len(full),
            "full_caught": sum(1 for c in full if tiers[c["use_case_id"]] >= FULL_REVIEW_TIER)}


def pct(a: int, b: int) -> str:
    return "%.1f%%" % (100.0 * a / b) if b else "n/a"


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
