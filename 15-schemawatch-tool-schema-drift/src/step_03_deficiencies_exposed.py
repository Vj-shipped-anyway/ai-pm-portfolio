"""Step 3 - Where the basic approach breaks: six named deficiencies, each with a count.

Step 2 showed that a version check and a content hash catch part of the drift. This step
asks what they cannot do, using the same synthetic releases, the change ledger (ground truth)
and the per-call truth file written by data/_generate.py.

  (a) Breaking and non-breaking changes are not separated.
  (b) Versionless changes are missed.
  (c) Semantic changes, such as a unit swap, are invisible to a structural diff.
  (d) Enum removal and enum addition are treated alike.
  (e) A new required field breaks every existing call.
  (f) A changed default silently alters behavior.

Counts of broken and silently-wrong calls come from data/call_truth.csv. Step 4 re-derives
them with a validator and checks they agree.

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: a readable summary, plus out/step_03_deficiencies.csv and out/step_03_summary.json.
"""

from __future__ import annotations

import csv
import json

from step_01_no_monitoring import OUT_DIR, load_all
from step_02_hash_and_version_check import _strip, score_releases


def param_structure(schema: dict, param: str):
    """The structural spec of one parameter (type, enum, default, bounds), no description."""
    spec = schema["parameters"]["properties"].get(param)
    if spec is None:
        return None
    return {"spec": _strip(spec, {"description"}),
            "required": param in schema["parameters"]["required"]}


def structural_diff_sees(data: dict, change: dict) -> bool:
    """Would a diff of types, enums, defaults and required lists notice this change?"""
    old = data["schemas"][change["tool"]][change["from_rev"]]["schema"]
    new = data["schemas"][change["tool"]][change["to_rev"]]["schema"]
    if change["param"] == "":
        return False                      # tool-level description only
    return param_structure(old, change["param"]) != param_structure(new, change["param"])


def naive_additive_is_safe(change: dict) -> str:
    """A diff that treats every added field as additive: only removals, type changes and
    removed enum values are called breaking."""
    if change["change_type"] in ("param_renamed", "param_removed", "type_changed",
                                 "enum_value_removed"):
        return "breaking"
    return "non_breaking"


def summarize(data: dict) -> dict:
    ledger, truth, calls_by_tool = data["ledger"], data["truth"], data["calls_by_tool"]
    rows = score_releases(data)
    ids = {c["change_id"]: c for c in ledger}

    def calls_with_cause(types: set) -> list:
        return [cid for cid, t in truth.items()
                if t["broken"] and any(ids[c]["change_type"] in types for c in t["causes"])]

    # (a) breaking and non-breaking not separated
    by_class = {k: sum(1 for c in ledger if c["true_class"] == k)
                for k in ("breaking", "behavior_risk", "non_breaking")}
    a = {"hash_alerts": sum(1 for r in rows if r["hash_alert"]), "changes": len(ledger),
         **by_class, "noise_only_releases": sum(1 for r in rows if not r["needs_action"]),
         "non_breaking_pct": round(100 * by_class["non_breaking"] / len(ledger), 1)}

    # (b) versionless changes
    unb_ch = [c for c in ledger if not c["bumped"]]
    unb_rel = [r for r in rows if not r["version_alert"]]
    tool_versions: dict = {}
    for r in rows:
        tool_versions.setdefault(r["tool"], []).append(r["version_alert"])
    invisible_tools = sorted(t for t, v in tool_versions.items() if not any(v))
    needs_action_invisible = sorted({r["tool"] for r in unb_rel if r["needs_action"]
                                     and not any(tool_versions[r["tool"]])})
    b = {"unbumped_changes": len(unb_ch), "changes": len(ledger),
         "unbumped_pct": round(100 * len(unb_ch) / len(ledger), 1),
         "unbumped_actionable_changes": sum(1 for c in unb_ch if c["true_class"] != "non_breaking"),
         "unbumped_releases": len(unb_rel), "releases": len(rows),
         "unbumped_actionable_releases": sum(1 for r in unb_rel if r["needs_action"]),
         "calls_broken_in_unbumped": sum(r["calls_broken_here"] for r in unb_rel),
         "tools_never_bumped": len(invisible_tools),
         "tools_never_bumped_needing_action": len(needs_action_invisible)}

    # (c) semantic changes invisible to a structural diff
    sem = [c for c in ledger if c["semantic_kind"] != "none"]
    seen = [c for c in sem if structural_diff_sees(data, c)]
    c_ = {"semantic_changes": len(sem),
          "unit_signal": sum(1 for c in sem if c["semantic_kind"] == "unit_signal"),
          "no_signal": sum(1 for c in sem if c["semantic_kind"] == "no_signal"),
          "seen_by_structural_diff": len(seen),
          "calls_misread_unit": sum(t["misread_unit"] for t in truth.values()),
          "calls_misread_meaning": sum(t["misread_meaning"] for t in truth.values())}
    c_["calls_misread"] = c_["calls_misread_unit"] + c_["calls_misread_meaning"]

    # (d) enum removal vs addition
    enum_rm = [c for c in ledger if c["change_type"] == "enum_value_removed"]
    enum_add = [c for c in ledger if c["change_type"] == "enum_value_added"]
    d = {"enum_removed": len(enum_rm), "enum_added": len(enum_add),
         "alerts_raised_for_both": len({(c["tool"], c["to_rev"]) for c in enum_rm + enum_add}),
         "calls_broken_by_removals": len(calls_with_cause({"enum_value_removed"})),
         "calls_broken_by_additions": len(calls_with_cause({"enum_value_added"}))}

    # (e) a new required field breaks every call
    req = [c for c in ledger if c["change_type"] == "required_added"]
    req_tools = sorted({c["tool"] for c in req})
    req_calls = [c for t in req_tools for c in calls_by_tool.get(t, [])]
    req_ids = {c["change_id"] for c in req}
    broken_by_req = sum(1 for c in req_calls if req_ids & set(truth[c["call_id"]]["causes"])
                        and truth[c["call_id"]]["broken"])
    e = {"required_added": len(req), "tools": len(req_tools), "calls_to_these_tools": len(req_calls),
         "calls_broken": broken_by_req,
         "naive_calls_safe": sum(1 for c in req if naive_additive_is_safe(c) == "non_breaking")}

    # (f) changed default silently alters behavior
    dflt = [c for c in ledger if c["change_type"] == "default_changed"]
    dtools = sorted({c["tool"] for c in dflt})
    dcalls = [c for t in dtools for c in calls_by_tool.get(t, [])]
    shifted = sum(truth[c["call_id"]]["shifted_default"] for c in dcalls)
    f = {"default_changed": len(dflt), "tools": len(dtools), "calls_to_these_tools": len(dcalls),
         "calls_rely_on_default": shifted,
         "reliance_pct": round(100 * shifted / len(dcalls), 1),
         "calls_failing_validation": sum(1 for c in dcalls if truth[c["call_id"]]["shifted_default"]
                                         and truth[c["call_id"]]["broken"])}

    return {"a": a, "b": b, "c": c_, "d": d, "e": e, "f": f}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    s = summarize(data)
    a, b, c, d, e, f = (s[k] for k in "abcdef")

    print("\n" + "=" * 78)
    print("Step 3 - Six deficiencies of the basic approach, with counts")
    print("=" * 78)
    print("\n(a) Breaking and non-breaking changes are not separated")
    print(f"    A hash alerts on {a['hash_alerts']} releases covering {a['changes']} changes. "
          f"{a['breaking']} are breaking, {a['behavior_risk']} change behavior, "
          f"{a['non_breaking']} ({a['non_breaking_pct']}%) are non-breaking.")
    print(f"    {a['noise_only_releases']} releases contain only non-breaking changes, yet raise the same alert.")
    print("\n(b) Versionless changes are missed")
    print(f"    {b['unbumped_changes']} of {b['changes']} changes ({b['unbumped_pct']}%) shipped without a version bump, "
          f"in {b['unbumped_releases']} of {b['releases']} releases;")
    print(f"    {b['unbumped_actionable_releases']} of those releases need action and "
          f"{b['calls_broken_in_unbumped']} recorded calls break inside them.")
    print(f"    {b['tools_never_bumped']} tools never changed their version string; "
          f"{b['tools_never_bumped_needing_action']} of them changed in ways that need action.")
    print("\n(c) Semantic changes are invisible to a structural diff")
    print(f"    {c['semantic_changes']} semantic changes ({c['unit_signal']} carry a unit signal, "
          f"{c['no_signal']} carry none). A diff of types, enums, defaults and required lists sees "
          f"{c['seen_by_structural_diff']} of {c['semantic_changes']}.")
    print(f"    {c['calls_misread']} recorded calls still pass validation and now mean something different "
          f"({c['calls_misread_unit']} unit, {c['calls_misread_meaning']} meaning).")
    print("\n(d) Enum removal and enum addition are treated alike")
    print(f"    {d['enum_removed']} removals and {d['enum_added']} additions raise {d['alerts_raised_for_both']} identical 'changed' alerts.")
    print(f"    Removals break {d['calls_broken_by_removals']} recorded calls; additions break {d['calls_broken_by_additions']}.")
    print("\n(e) A new required field breaks every existing call")
    print(f"    {e['required_added']} required fields were added, on {e['tools']} tools. "
          f"{e['calls_broken']} of {e['calls_to_these_tools']} recorded calls to those tools break (100%).")
    print(f"    A diff that treats added fields as additive labels {e['naive_calls_safe']} of {e['required_added']} of them safe.")
    print("\n(f) A changed default silently alters behavior")
    print(f"    {f['default_changed']} defaults changed, on {f['tools']} tools. {f['calls_rely_on_default']} of "
          f"{f['calls_to_these_tools']} calls to those tools ({f['reliance_pct']}%) omit the parameter and now get a")
    print(f"    different value. Validation fails {f['calls_failing_validation']} of them: nothing alerts.")

    rows = [("a", "hash alerts covering non-breaking changes", f"{a['non_breaking']} of {a['changes']}"),
            ("a", "noise-only releases alerted", a["noise_only_releases"]),
            ("b", "changes shipped without a version bump", f"{b['unbumped_changes']} of {b['changes']}"),
            ("b", "calls broken in unbumped releases", b["calls_broken_in_unbumped"]),
            ("c", "semantic changes seen by structural diff", f"{c['seen_by_structural_diff']} of {c['semantic_changes']}"),
            ("c", "calls passing validation but misread", c["calls_misread"]),
            ("d", "calls broken by enum removals", d["calls_broken_by_removals"]),
            ("d", "calls broken by enum additions", d["calls_broken_by_additions"]),
            ("e", "calls broken by required-field additions", f"{e['calls_broken']} of {e['calls_to_these_tools']}"),
            ("f", "calls relying on a changed default", f"{f['calls_rely_on_default']} of {f['calls_to_these_tools']}")]
    with open(OUT_DIR / "step_03_deficiencies.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["deficiency", "measure", "value"])
        w.writerows(rows)
    with open(OUT_DIR / "step_03_summary.json", "w") as fh:
        json.dump(s, fh, indent=2)
    print(f"\nWrote src/out/step_03_deficiencies.csv and step_03_summary.json")


if __name__ == "__main__":
    main()
