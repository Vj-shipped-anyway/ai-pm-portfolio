"""Step 1 - Status quo: a pull request template, and nothing that reads it.

The repository has a template with an evidence section. Reviewers are asked to look at it. Nothing
fails when a line is missing, so every pull request here is merged. The data is synthetic
(data/_generate.py); the truth label of each pull request is the planted state of its evidence at the
use case's true tier, which is what a reviewer would find after opening every link.

Run (from src/):  python3 step_01_no_gate.py
"""
from collections import Counter

from common import load_cases, load_world
from evidence_gate import required_ids

cases, world = load_cases(), load_world()
truth = Counter(c["truth"] for c in cases)
owed = sum(len(required_ids(world["tiers"], c["true_tier"])) for c in cases)
bad = sum(len(c["bad_items"]) for c in cases)
kinds = Counter(c["kind"] for c in cases if c["truth"] == "should_block")

print("STEP 1 - a template, and no check")
print(f"  pull requests merged: {len(cases)}   use cases: {len({c['use_case'] for c in cases})}")
print(f"  truth: {truth['should_block']} lack evidence the true tier requires, {truth['needs_review']} carry the wrong tier label, {truth['fine']} are fine")
print(f"  pull requests the current process stops: 0 of {len(cases)}")
print(f"  evidence items owed across all pull requests: {owed}; missing, stale or unusable: {bad}")
print("  merged with a gap, by planted defect: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
print("  Whether the evidence exists is found by a reviewer who opens every link, or not found.")
