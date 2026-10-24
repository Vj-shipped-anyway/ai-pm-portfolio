"""Step 3 - Where each idea fails when used alone.

Two gates, each with one idea, scored on the same 40 change requests:
  point estimate   fail when the measured cost per correct answer of any judged scope is over its
                   ceiling, with no interval
  whole run only   fail when the interval's lower end for the whole run is over the overall ceiling,
                   with no slice ceilings

Then one more question: what happens to the slice ceilings when the eval set is a quarter of the size.

KNOWN LIMIT, left in on purpose: a change that is over budget by a few percent sits inside the noise
of 236 items, and a regression inside a slice with fewer than min_items items is never judged alone.
Neither gate here fails them, and step 4 does not fail them either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from collections import Counter

from common import load_budget, load_runs, evaluate, scope_of

budget = load_budget()
baseline, crs = load_runs(budget)
reports = {c["cr_id"]: evaluate(c["items"], budget) for c in crs}
over = [c for c in crs if c["over"]]
within = [c for c in crs if not c["over"]]


def point_gate(c) -> bool:
    return any(s["status"] in ("FAIL", "WARN") for s in reports[c["cr_id"]]["scopes"])


def whole_run_gate(c) -> bool:
    return scope_of(reports[c["cr_id"]], "overall")["status"] == "FAIL"


def score(name, gate):
    caught = [c for c in over if gate(c)]
    print(f"  {name}")
    print(f"    over budget and failed: {len(caught)} of {len(over)}")
    print(f"    within budget and failed: {sum(1 for c in within if gate(c))} of {len(within)}")
    return {c["cr_id"] for c in caught}


print("STEP 3 - each idea alone")
by_point = score("point estimate, no interval", point_gate)
by_whole = score("interval, whole run only", whole_run_gate)
slice_hidden = [c for c in over if c["cr_id"] not in by_whole and "overall" not in c["true_scopes"]]
print(f"  over budget only inside a slice, so the whole-run gate passes it: {len(slice_hidden)} of {len(over)}")
print("  by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(c["kind"] for c in slice_hidden).items())))
noisy = [c for c in within if point_gate(c)]
print(f"  within budget but over on the point estimate: {len(noisy)} of {len(within)}; by planted change: "
      + (", ".join(f"{k} {v}" for k, v in sorted(Counter(c["kind"] for c in noisy).items())) or "none"))

# An eval set a quarter of the size: keep every fourth item (item_ids are Q001, Q002, ...)
quarter = []
for c in crs:
    items = [it for i, it in enumerate(c["items"]) if i % 4 == 0]
    quarter.append({"cr_id": c["cr_id"], "over": c["over"], "report": evaluate(items, budget)})
q_items = quarter[0]["report"]["items"]
q_fail = sum(1 for q in quarter if q["over"] and q["report"]["decision"] == "FAIL")
q_judged = max(sum(1 for s in q["report"]["scopes"][1:] if s["status"] != "THIN") for q in quarter)
full_fail = sum(1 for c in over if reports[c["cr_id"]]["decision"] == "FAIL")
print(f"  with every fourth item ({q_items} items) the interval gate fails {q_fail} of {len(over)} over-budget change requests, against {full_fail} on the full set")
print(f"  slices judged alone on the smaller set: {q_judged} of {len(budget['slices'])} (the rest fall under min_items {budget['min_items']})")

passed_both = [c for c in over if c["cr_id"] not in by_point]
print(f"  over budget and passed by both gates: {len(passed_both)} of {len(over)}")
for c in passed_both:
    print(f"    {c['cr_id']} {c['kind']} true cost per correct {c['true_worst']:.3f}x its ceiling, over in: {', '.join(c['true_scopes'])}")
print("  The point estimate fails builds on noise; the whole-run gate never sees a slice. Neither sees a small overshoot.")
