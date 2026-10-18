"""Step 1 - Before SchemaWatch: nobody watches tool schemas.

An agent calls tools. Each tool is an API with a JSON schema owned by another team. The
owners change schemas (rename a parameter, tighten a type, add a required field, drop an
enum value, change a unit in a description) and the agent team is not told. Today the
breakage is found when calls fail.

This script plays the recorded week of agent traffic forward from each release and counts
what happens when there is no schema monitoring:

  * how many calls fail, and when
  * how long until a failure alert would reach a person
  * how many calls keep working but mean something different (these never fail, so nothing
    ever alerts)

The synthetic ground truth (data/call_truth.csv) says which calls break. Nothing here is a
real bank, tool, API or model; the calls were written by data/_generate.py.

ASSUMPTIONS (modeled, change them at the top of this file):
  A1. After a release, traffic to that tool repeats the recorded week: same calls, same
      timing offsets, with offset zero at the release time.
  A2. Nobody compares schemas, so the first signal is a failed call. A failed call is loud:
      the tool rejects it.
  A3. A person is alerted when the ALARM_FAILURES-th failed call to the same tool has been
      seen after a release (a generic error-count alarm). Delivery of the alert is instant,
      so every time below is a floor, not an estimate of a real response.
  A4. A call that passes validation but means something different never fails, so it never
      raises an alert.

Run (from src/):
    python3 step_01_no_monitoring.py

Output: a readable summary, plus out/step_01_events.csv and out/step_01_summary.json.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

ALARM_FAILURES = 5          # assumption A3
WINDOW_DAYS = 7             # the recorded week
REC_START = datetime(2026, 3, 2)


# ---------------------------------------------------------------------------
# Shared loaders (later steps and the app import these)
# ---------------------------------------------------------------------------
def load_all(data_dir: Path = DATA_DIR) -> dict:
    """Load the four CSVs into plain dicts. No pandas needed."""
    schemas: dict = defaultdict(dict)
    with open(data_dir / "tool_schemas.csv", newline="") as f:
        for r in csv.DictReader(f):
            schemas[r["tool"]][r["rev"]] = {
                "declared_version": r["declared_version"],
                "released_at": r["released_at"],
                "schema": json.loads(r["schema_json"]),
            }
    schemas = dict(schemas)
    revs = {t: sorted(v.keys()) for t, v in schemas.items()}

    with open(data_dir / "change_ledger.csv", newline="") as f:
        ledger = list(csv.DictReader(f))
    for r in ledger:
        r["bumped"] = r["version_bumped"] == "yes"

    calls = []
    with open(data_dir / "recorded_calls.csv", newline="") as f:
        for r in csv.DictReader(f):
            calls.append({"call_id": r["call_id"], "tool": r["tool"],
                          "called_at": datetime.strptime(r["called_at"], "%Y-%m-%dT%H:%M:%S"),
                          "args": json.loads(r["args_json"])})

    truth = {}
    with open(data_dir / "call_truth.csv", newline="") as f:
        for r in csv.DictReader(f):
            truth[r["call_id"]] = {
                "broken": int(r["true_broken"]), "first_break_rev": r["first_break_rev"],
                "misread_unit": int(r["true_misread_unit"]),
                "misread_meaning": int(r["true_misread_meaning"]),
                "shifted_default": int(r["true_shifted_default"]),
                "causes": [c for c in r["cause_change_ids"].split(";") if c],
            }

    # A release is one revision of one tool: all ledger rows with the same (tool, to_rev).
    by_release: dict = defaultdict(list)
    for r in ledger:
        by_release[(r["tool"], r["to_rev"])].append(r)
    releases = []
    for (tool, to_rev), rows in by_release.items():
        first = rows[0]
        releases.append({
            "release_id": f"{tool}@{to_rev}", "tool": tool, "from_rev": first["from_rev"],
            "to_rev": to_rev, "released_at": first["released_at"],
            "declared_before": first["declared_version_before"],
            "declared_after": first["declared_version_after"], "bumped": first["bumped"],
            "changes": rows,
        })
    releases.sort(key=lambda r: (r["released_at"], r["tool"]))

    calls_by_tool: dict = defaultdict(list)
    for c in calls:
        calls_by_tool[c["tool"]].append(c)

    return {"schemas": schemas, "revs": revs, "ledger": ledger, "calls": calls,
            "calls_by_tool": dict(calls_by_tool), "truth": truth, "releases": releases,
            "tools": sorted(schemas.keys())}


def offset_hours(call: dict) -> float:
    return (call["called_at"] - REC_START).total_seconds() / 3600.0


# ---------------------------------------------------------------------------
# The simulation
# ---------------------------------------------------------------------------
def simulate(data: dict, alarm_failures: int = ALARM_FAILURES) -> list:
    """One event per release that breaks at least one recorded call."""
    events = []
    for rel in data["releases"]:
        failing = [c for c in data["calls_by_tool"].get(rel["tool"], [])
                   if data["truth"][c["call_id"]]["first_break_rev"] == rel["to_rev"]]
        if not failing:
            continue
        hours = sorted(offset_hours(c) for c in failing)
        events.append({
            "release_id": rel["release_id"], "tool": rel["tool"], "released_at": rel["released_at"],
            "failed_calls": len(hours), "first_failure_h": round(hours[0], 1),
            "alert_h": round(hours[alarm_failures - 1], 1) if len(hours) >= alarm_failures else None,
            "hours": hours,
        })
    return events


def silent_counts(data: dict) -> dict:
    t = data["truth"].values()
    return {
        "unit": sum(x["misread_unit"] for x in t),
        "meaning": sum(x["misread_meaning"] for x in t),
        "default": sum(x["shifted_default"] for x in t),
        "any": sum(1 for x in t if x["misread_unit"] or x["misread_meaning"] or x["shifted_default"]),
    }


def summarize(data: dict) -> dict:
    events = simulate(data)
    alerted = [e for e in events if e["alert_h"] is not None]
    never = [e for e in events if e["alert_h"] is None]
    silent = silent_counts(data)
    all_hours = sorted(h for e in events for h in e["hours"])
    daily = []
    cum = 0
    for d in range(WINDOW_DAYS):
        n = sum(1 for h in all_hours if d * 24 <= h < (d + 1) * 24)
        cum += n
        daily.append({"day": d + 1, "failed": n, "cumulative": cum,
                      "events_alerted": sum(1 for e in alerted if e["alert_h"] < (d + 1) * 24)})
    sens = []
    for n in (1, 3, 5, 10):
        ev = simulate(data, n)
        al = [e["alert_h"] for e in ev if e["alert_h"] is not None]
        sens.append({"alarm_failures": n, "alerted": len(al), "never": len(ev) - len(al),
                     "median_alert_h": round(statistics.median(al), 1) if al else None})
    return {
        "events": len(events),
        "broken_calls": sum(e["failed_calls"] for e in events),
        "total_calls": len(data["calls"]),
        "pct_broken": round(100 * sum(e["failed_calls"] for e in events) / len(data["calls"]), 1),
        "alarm_failures": ALARM_FAILURES,
        "alerted_events": len(alerted),
        "never_alert_events": len(never),
        "never_alert_calls": sum(e["failed_calls"] for e in never),
        "median_first_failure_h": round(statistics.median(e["first_failure_h"] for e in events), 1),
        "median_alert_h": round(statistics.median(e["alert_h"] for e in alerted), 1),
        "max_alert_h": max(e["alert_h"] for e in alerted),
        "silent_unit": silent["unit"], "silent_meaning": silent["meaning"],
        "silent_default": silent["default"], "silent_calls": silent["any"],
        "daily": daily, "sensitivity": sens,
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    events = simulate(data)
    s = summarize(data)

    print("\n" + "=" * 78)
    print("Step 1 - Before SchemaWatch: nobody watches tool schemas")
    print("=" * 78)
    print(f"\n{len(data['tools'])} tools, {len(data['releases'])} schema releases, "
          f"{len(data['ledger'])} injected changes, {s['total_calls']:,} recorded calls.")
    print("Data is synthetic and seeded. The truth is known because the generator injected it.\n")
    print("ASSUMPTIONS (modeled):")
    print("  A1  after a release, traffic repeats the recorded week from the release time")
    print("  A2  with no schema monitoring the first signal is a failed call")
    print(f"  A3  a person is alerted on the {ALARM_FAILURES}th failed call to one tool; delivery is instant")
    print("  A4  calls that pass but mean something different never fail, so never alert\n")

    print(f"{'release':<40} {'failed':>6} {'1st fail':>9} {'alert at':>9}")
    print(f"{'-' * 40} {'-' * 6} {'-' * 9} {'-' * 9}")
    for e in sorted(events, key=lambda x: -x["failed_calls"]):
        alert = f"{e['alert_h']:.1f} h" if e["alert_h"] is not None else "never"
        print(f"{e['release_id']:<40} {e['failed_calls']:>6} {e['first_failure_h']:>7.1f} h {alert:>9}")

    print("\nCalls failing day by day after release (all events combined):")
    for d in s["daily"]:
        print(f"  day {d['day']}: {d['failed']:>4} failed, {d['cumulative']:>4} cumulative, "
              f"{d['events_alerted']:>2} of {s['events']} events have alerted a person")

    print("\nRESULT")
    print(f"  Calls that fail loudly in the week after release:   {s['broken_calls']} of {s['total_calls']:,} "
          f"({100 * s['broken_calls'] / s['total_calls']:.1f}%), across {s['events']} releases")
    print(f"  Median hours to the first failed call:              {s['median_first_failure_h']} h")
    print(f"  Median hours until a person is alerted (floor):     {s['median_alert_h']} h "
          f"(slowest {s['max_alert_h']} h)")
    print(f"  Releases that never reach {ALARM_FAILURES} failures in the week: {s['never_alert_events']} of {s['events']} "
          f"({s['never_alert_calls']} calls fail with nobody alerted)")
    print(f"  Calls that pass but mean something different:       {s['silent_calls']} "
          f"(unit {s['silent_unit']}, meaning {s['silent_meaning']}, default {s['silent_default']}; "
          f"overlaps counted once), alert never")
    print("\nSensitivity of the alert time to assumption A3 (failures needed before an alert):")
    for x in s["sensitivity"]:
        med = f"{x['median_alert_h']} h" if x["median_alert_h"] is not None else "n/a"
        print(f"  {x['alarm_failures']:>2} failures: {x['alerted']:>2} releases alert, "
              f"{x['never']:>2} never, median {med}")

    with open(OUT_DIR / "step_01_events.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["release_id", "tool", "released_at", "failed_calls", "first_failure_h", "alert_h"])
        for e in events:
            w.writerow([e["release_id"], e["tool"], e["released_at"], e["failed_calls"],
                        e["first_failure_h"], "" if e["alert_h"] is None else e["alert_h"]])
    with open(OUT_DIR / "step_01_summary.json", "w") as f:
        json.dump(s, f, indent=2)
    print(f"\nWrote src/out/step_01_events.csv and step_01_summary.json")


if __name__ == "__main__":
    main()
