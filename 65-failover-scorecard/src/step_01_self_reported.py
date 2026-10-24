"""Step 1 - Status quo: each service owner says whether a failover plan exists.

The service map has a column, failover_plan, where the owner states yes or no. Nothing in the
pipeline checks it. This step counts the claims and sets them against the planted truth, which
the generator fixed from the story behind each service and not from any rule. The data is
synthetic (data/_generate.py).

Run (from src/):  python3 step_01_self_reported.py
"""
from __future__ import annotations

from collections import Counter

from common import load_all, truth_class


def main() -> None:
    data = load_all()
    ids = sorted(data["by_id"])
    truth = Counter(truth_class(data, i) for i in ids)
    claimed = [i for i in ids if data["claims"][i]]
    holds = [i for i in claimed if truth_class(data, i) == "ready"]
    drilled = {d["service_id"] for d in data["drills"]}
    live = {d["service_id"] for d in data["drills"] if d["type"] == "live"}
    print("STEP 1 - the owner says there is a plan")
    print(f"  services: {len(ids)}   drill log rows: {len(data['drills'])}")
    print(f"  planted truth: {truth['ready']} would recover, {truth['not_ready']} would not, {truth['accepted']} have no way back by an accepted decision")
    print(f"  services whose owner states a documented failover plan: {len(claimed)} of {len(ids)}")
    print(f"  of those, services that would recover: {len(holds)} of {len(claimed)}")
    print(f"  services with at least one drill on record: {len(drilled)} of {len(ids)}; with a live drill: {len(live)} of {len(ids)}")
    print("  The claim costs nothing to make and nothing checks it against the drill log.")


if __name__ == "__main__":
    main()
