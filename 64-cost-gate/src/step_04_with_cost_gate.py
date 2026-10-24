"""Step 4 - The fix: cost per correct answer, an interval, a ceiling per slice.

For each change request the gate (cost_gate.py, the same code the command line and the GitHub Action
run) computes cost per correct answer for the whole run and for every slice, with a 95% interval:
  FAIL  the interval's lower end is over the ceiling, so the build stops
  WARN  the estimate is over the ceiling but the interval still reaches it, so a person decides
  PASS  otherwise
A slice with fewer than min_items items is not judged alone and is printed as THIN.

KNOWN LIMIT, left in on purpose: a small overshoot of the whole-run ceiling and a regression inside
a THIN slice can still pass. The script prints every over-budget change request that passes.

Run (from src/):  python3 step_04_with_cost_gate.py
Output: a report, plus out/step_04_decisions.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import load_budget, load_runs, evaluate, scope_of, ensure_out, OUT_DIR

budget = load_budget()
baseline, crs = load_runs(budget)
rows = []
for c in crs:
    rep = evaluate(c["items"], budget)
    overall = scope_of(rep, "overall")
    flagged = [f"{s['scope']}:{s['status']}" for s in rep["scopes"] if s["status"] not in ("PASS", "THIN")]
    rows.append({"cr_id": c["cr_id"], "change_kind": c["kind"], "truth": "over_budget" if c["over"] else "within_budget",
                 "true_worst_ratio": f"{c['true_worst']:.3f}", "decision": rep["decision"],
                 "overall_ratio": f"{overall['cpc'] / overall['ceiling']:.3f}", "flagged": "; ".join(flagged) or "none"})
    c["rep"], c["decision"] = rep, rep["decision"]

over = [c for c in crs if c["over"]]
within = [c for c in crs if not c["over"]]


def count(group, decision):
    return sum(1 for c in group if c["decision"] == decision)


slice_reg = [c for c in crs if c["kind"] == "slice_regression"]
slice_caught = [c for c in slice_reg if any(s["status"] == "FAIL" for s in c["rep"]["scopes"][1:])]
slice_only = [c for c in slice_caught if scope_of(c["rep"], "overall")["status"] == "PASS"]
reads = sum(1 for c in crs if c["decision"] != "PASS")
missed = [c for c in over if c["decision"] == "PASS"]

print("STEP 4 - interval per scope, a ceiling per slice, thin slices not judged alone")
print(f"  over budget: FAIL {count(over, 'FAIL')}, WARN {count(over, 'WARN')}, PASS {count(over, 'PASS')} (of {len(over)})")
print(f"  within budget: FAIL {count(within, 'FAIL')}, WARN {count(within, 'WARN')}, PASS {count(within, 'PASS')} (of {len(within)})")
print(f"  change requests that stop the build: {count(crs, 'FAIL')} of {len(crs)}; that a person reads (FAIL or WARN): {reads} of {len(crs)}")
print(f"  planted slice regressions failed on a slice ceiling: {len(slice_caught)} of {len(slice_reg)}; the whole-run status was PASS on {len(slice_only)} of them")
print(f"  with --fail-on warn the build would also stop on the WARN ones: {count(over, 'FAIL') + count(over, 'WARN')} of {len(over)} over budget, "
      f"{count(within, 'FAIL') + count(within, 'WARN')} of {len(within)} within budget")
print(f"  over budget and still PASS: {len(missed)} of {len(over)}")
for c in missed:
    print(f"    {c['cr_id']} {c['kind']} true cost per correct {c['true_worst']:.3f}x its ceiling, over in: {', '.join(c['true_scopes'])}")
by_kind = Counter((r["change_kind"], r["decision"]) for r in rows)
print("  decisions by planted change:")
for kind in sorted({r["change_kind"] for r in rows}):
    print(f"    {kind:<22} " + ", ".join(f"{d} {by_kind[(kind, d)]}" for d in ("FAIL", "WARN", "PASS") if by_kind[(kind, d)]))

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
summary = {"change_requests": len(crs), "over_budget": len(over), "within_budget": len(within),
           "over_fail": count(over, "FAIL"), "over_warn": count(over, "WARN"), "over_pass": count(over, "PASS"),
           "within_fail": count(within, "FAIL"), "within_warn": count(within, "WARN"), "within_pass": count(within, "PASS"),
           "to_read": reads, "stop_the_build": count(crs, "FAIL"), "items_per_run": len(baseline)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_decisions.csv and step_04_summary.json in src/out/")
