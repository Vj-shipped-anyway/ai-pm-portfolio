"""Step 4 - The fix: the failover scorecard.

One readiness rule over the service map and the drill log (failover_scorecard.py, the same code the
command line runs). A service is READY only with a live drill of the right scenario that passed
inside its recovery target, ran against the current secondary region and config version, falls
inside the window for its tier, and sits on dependencies that are READY. An owner-accepted gap on a
low tier is reported as NOT_REQUIRED, and nothing else is.

KNOWN LIMIT, left in on purpose: a dependency the map does not list is invisible. The script
prints the services that pass because of it.

The windows (180, 365 and 540 days by tier) are my assumption. The last lines show how the
tier-1 count moves if the tier-1 window is changed.

Run (from src/):  python3 step_04_with_scorecard.py
Output: a report, plus out/step_04_scorecard.csv and out/step_04_summary.json
"""
from __future__ import annotations

import csv
import json
import os
from collections import Counter

from common import AS_OF, OUT_DIR, default_policy, ensure_out, load_all, predicted_class, score, truth_class


def main() -> None:
    data = load_all()
    results = score(data["services"], data["drills"], AS_OF)
    for r in results:
        r["story"] = data["truth"][r["service_id"]]["story"]
        r["truth"] = truth_class(data, r["service_id"])
    by_truth = {c: [r for r in results if r["truth"] == c] for c in ("ready", "not_ready", "accepted")}
    caught = [r for r in by_truth["not_ready"] if r["status"] not in ("READY", "NOT_REQUIRED")]
    false_alarm = [r for r in by_truth["ready"] if r["status"] != "READY"]
    kept = [r for r in by_truth["accepted"] if r["status"] == "NOT_REQUIRED"]
    missed = [r for r in by_truth["not_ready"] if r["status"] == "READY"]
    exact = [r for r in results if predicted_class(r["status"]) == r["truth"]]
    sent = [r for r in results if r["status"] not in ("READY", "NOT_REQUIRED")]
    tier1 = [r for r in results if r["tier"] == 1]
    tier1_ready = [r for r in tier1 if r["status"] == "READY"]
    counts = Counter(r["status"] for r in results)

    print("STEP 4 - the failover scorecard")
    print(f"  services not ready that the scorecard flags: {len(caught)} of {len(by_truth['not_ready'])}")
    print(f"  services ready in truth that it flags: {len(false_alarm)} of {len(by_truth['ready'])} (includes {sum(1 for r in by_truth['ready'] if r['story'] == 'failed_then_fixed')} fixed after a failed drill and {sum(1 for r in by_truth['ready'] if r['story'] == 'proven_old_unchanged')} with an old drill still inside its window)")
    print(f"  owner-accepted gaps reported as not required: {len(kept)} of {len(by_truth['accepted'])}")
    print(f"  status matches the planted truth: {len(exact)} of {len(results)}")
    print(f"  tier-1 services with a tested way back: {len(tier1_ready)} of {len(tier1)}")
    tier1_wrong = [r for r in tier1_ready if r["truth"] != "ready"]
    print(f"  of those tier-1 services, the number that would not recover: {len(tier1_wrong)} of {len(tier1_ready)}")
    print(f"  services sent to an owner: {len(sent)} of {len(results)}, all {sum(1 for r in sent if r['truth'] == 'not_ready')} not ready in truth")
    print("  by status: " + ", ".join(f"{s} {n}" for s, n in sorted(counts.items())))
    print(f"  known limit: {len(missed)} services score READY and would not recover (undeclared dependency)")
    for r in missed:
        print(f"    {r['service_id']} {r['name']} tier {r['tier']}")
    print("  tier-1 services READY if the tier-1 window were different (assumption, not a rule):")
    sensitivity = {}
    for days in (90, 180, 365):
        policy = default_policy()
        policy["window_days"][1] = days
        n = sum(1 for r in score(data["services"], data["drills"], AS_OF, policy) if r["tier"] == 1 and r["status"] == "READY")
        sensitivity[str(days)] = n
        print(f"    {days} days: {n} of {len(tier1)}")

    ensure_out()
    fields = ["service_id", "name", "domain", "tier", "status", "reason", "blocked_by", "last_drill", "story", "truth"]
    with open(os.path.join(OUT_DIR, "step_04_scorecard.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows([{k: r[k] for k in fields} for r in results])
    summary = {"services": len(results), "not_ready": len(by_truth["not_ready"]), "not_ready_flagged": len(caught),
               "ready": len(by_truth["ready"]), "ready_flagged": len(false_alarm),
               "accepted": len(by_truth["accepted"]), "accepted_kept": len(kept), "exact_match": len(exact),
               "tier1": len(tier1), "tier1_ready": len(tier1_ready), "tier1_ready_wrong": len(tier1_wrong), "sent_to_owner": len(sent),
               "missed": len(missed), "by_status": dict(sorted(counts.items())), "tier1_window_sensitivity": sensitivity}
    with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    print("Wrote step_04_scorecard.csv and step_04_summary.json in src/out/")


if __name__ == "__main__":
    main()
