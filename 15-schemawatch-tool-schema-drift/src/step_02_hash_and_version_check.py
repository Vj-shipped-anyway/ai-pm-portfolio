"""Step 2 - The basic approach: compare version strings, or compare content hashes.

This is what a platform team does when it first notices that tool schemas drift:

  * Version check: alert when a tool's declared version string changes.
  * Content hash:  alert when the hash of the canonical schema text changes.

Both are cheap and both are reasonable. This script runs them over every schema release in
the synthetic data and scores them against the change ledger (the ground truth):

  * What each one catches, and what it flags that needs no action.
  * What a version check cannot see because the owner did not bump the version.

A release "needs action" when the ledger says it contains at least one breaking or
behavior-risk change. A release is "noise only" when it contains only non-breaking changes
(cosmetic rewording, an added optional field, a widened type, an added enum value).

Run (from src/):
    python3 step_02_hash_and_version_check.py

Output: a readable summary, plus out/step_02_release_flags.csv and out/step_02_summary.json.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json

from step_01_no_monitoring import OUT_DIR, load_all


# ---------------------------------------------------------------------------
# The two basic detectors
# ---------------------------------------------------------------------------
def canonical(schema: dict) -> str:
    return json.dumps(schema, sort_keys=True, separators=(",", ":"))


def content_hash(schema: dict) -> str:
    return hashlib.sha256(canonical(schema).encode()).hexdigest()[:12]


def _strip(node, drop):
    if isinstance(node, dict):
        return {k: _strip(v, drop) for k, v in node.items() if k not in drop}
    if isinstance(node, list):
        return [_strip(v, drop) for v in node]
    return node


def structure_hash(schema: dict) -> str:
    """Hash of the structure only: descriptions and the version string are ignored."""
    return hashlib.sha256(canonical(_strip(copy.deepcopy(schema), {"description", "version"})).encode()
                          ).hexdigest()[:12]


def release_class(rel: dict) -> str:
    classes = {c["true_class"] for c in rel["changes"]}
    if "breaking" in classes:
        return "breaking"
    if "behavior_risk" in classes:
        return "behavior_risk"
    return "noise_only"


def score_releases(data: dict) -> list:
    rows = []
    for rel in data["releases"]:
        old = data["schemas"][rel["tool"]][rel["from_rev"]]["schema"]
        new = data["schemas"][rel["tool"]][rel["to_rev"]]["schema"]
        broken_new = sum(1 for c in data["calls_by_tool"].get(rel["tool"], [])
                         if data["truth"][c["call_id"]]["first_break_rev"] == rel["to_rev"])
        cls = release_class(rel)
        rows.append({
            "release_id": rel["release_id"], "tool": rel["tool"], "to_rev": rel["to_rev"],
            "n_changes": len(rel["changes"]),
            "declared_before": rel["declared_before"], "declared_after": rel["declared_after"],
            "version_alert": rel["declared_before"] != rel["declared_after"],
            "hash_alert": content_hash(old) != content_hash(new),
            "structure_alert": structure_hash(old) != structure_hash(new),
            "release_class": cls, "needs_action": cls != "noise_only",
            "calls_broken_here": broken_new,
        })
    return rows


def confusion(rows: list, key: str) -> dict:
    tp = sum(1 for r in rows if r[key] and r["needs_action"])
    fp = sum(1 for r in rows if r[key] and not r["needs_action"])
    fn = sum(1 for r in rows if not r[key] and r["needs_action"])
    tn = sum(1 for r in rows if not r[key] and not r["needs_action"])
    return {"alerts": tp + fp, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "recall_pct": round(100 * tp / (tp + fn), 1) if tp + fn else 0.0,
            "precision_pct": round(100 * tp / (tp + fp), 1) if tp + fp else 0.0}


def summarize(data: dict) -> dict:
    rows = score_releases(data)
    n_broken = sum(r["calls_broken_here"] for r in rows)
    ver, hsh = confusion(rows, "version_alert"), confusion(rows, "hash_alert")
    ver["broken_calls_in_alerted"] = sum(r["calls_broken_here"] for r in rows if r["version_alert"])
    ver["broken_calls_missed"] = n_broken - ver["broken_calls_in_alerted"]
    hsh["broken_calls_in_alerted"] = sum(r["calls_broken_here"] for r in rows if r["hash_alert"])
    hsh["broken_calls_missed"] = n_broken - hsh["broken_calls_in_alerted"]
    changes = data["ledger"]
    return {
        "releases": len(rows),
        "needs_action_releases": sum(1 for r in rows if r["needs_action"]),
        "noise_only_releases": sum(1 for r in rows if not r["needs_action"]),
        "changes": len(changes),
        "non_breaking_changes": sum(1 for c in changes if c["true_class"] == "non_breaking"),
        "broken_calls": n_broken,
        "version": ver, "hash": hsh,
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    rows = score_releases(data)
    s = summarize(data)
    v, h = s["version"], s["hash"]

    print("\n" + "=" * 78)
    print("Step 2 - The basic approach: version strings and content hashes")
    print("=" * 78)
    print(f"\n{s['releases']} schema releases, {s['changes']} injected changes. "
          f"{s['needs_action_releases']} releases need action; {s['noise_only_releases']} are noise only.\n")
    print(f"{'release':<38} {'ver check':>9} {'hash':>5} {'ledger says':>14} {'calls broken':>12}")
    print(f"{'-' * 38} {'-' * 9} {'-' * 5} {'-' * 14} {'-' * 12}")
    for r in sorted(rows, key=lambda x: x["release_id"]):
        print(f"{r['release_id']:<38} {'ALERT' if r['version_alert'] else '-':>9} "
              f"{'ALERT' if r['hash_alert'] else '-':>5} {r['release_class']:>14} {r['calls_broken_here']:>12}")

    print("\nRESULT (release level)")
    print(f"  Version check: {v['alerts']} alerts. Catches {v['tp']} of {s['needs_action_releases']} releases that need "
          f"action ({v['recall_pct']}%), flags {v['fp']} noise-only releases.")
    print(f"                 Misses {v['fn']} releases that need action: the owner shipped them without a version bump.")
    print(f"                 Calls broken inside releases it never alerts on: {v['broken_calls_missed']} of {s['broken_calls']}.")
    print(f"  Content hash:  {h['alerts']} alerts. Catches {h['tp']} of {s['needs_action_releases']} ({h['recall_pct']}%), "
          f"flags {h['fp']} noise-only releases the same way it flags a breaking one.")
    print(f"                 Calls broken inside releases it never alerts on: {h['broken_calls_missed']} of {s['broken_calls']}.")
    print(f"  Neither tells you which change is breaking: {s['non_breaking_changes']} of {s['changes']} changes "
          f"behind these alerts are non-breaking.")
    print("  Neither can say how many calls break, or rank the alerts.")

    with open(OUT_DIR / "step_02_release_flags.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["release_id", "declared_before", "declared_after", "version_alert", "hash_alert",
                    "release_class", "calls_broken_here"])
        for r in rows:
            w.writerow([r["release_id"], r["declared_before"], r["declared_after"],
                        int(r["version_alert"]), int(r["hash_alert"]), r["release_class"],
                        r["calls_broken_here"]])
    with open(OUT_DIR / "step_02_summary.json", "w") as f:
        json.dump(s, f, indent=2)
    print(f"\nWrote src/out/step_02_release_flags.csv and step_02_summary.json")


if __name__ == "__main__":
    main()
