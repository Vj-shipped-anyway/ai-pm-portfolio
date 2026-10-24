"""Shared loading for the four step scripts of project 29."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from tprm_gap_map import (load_vendors, read_csv, upstream_shares, passes_questionnaire, tier_text, tier_ai,  # noqa: E402,F401
                          indicators, material_vendors, score)


def load_all():
    vendors = load_vendors(os.path.join(DATA, "vendors.csv"))
    incidents = read_csv(os.path.join(DATA, "incident_log.csv"))
    truth_rows = {r["vendor_id"]: r for r in read_csv(os.path.join(DATA, "vendor_truth.csv"))}
    truth = {vid for vid, r in truth_rows.items() if r["high_risk"] == "yes"}
    return vendors, incidents, truth_rows, truth


def ensure_out():
    os.makedirs(OUT_DIR, exist_ok=True)
