"""Step 4 - The fix: parse the plan, apply ten rules to what it creates or updates, say what it cannot know.

  1. read `resource_changes` and keep creates and updates; skip deletes, no-ops and data sources
  2. pick rules by the exact `type` field, never by the shape of the address
  3. a rule that cannot see its value because Terraform fills it in at apply says "unverified" (REVIEW)
  4. BLOCK if a high-severity rule is broken, REVIEW for a medium rule or an unverified value, else ALLOW

The command line and the GitHub Action in action/ run exactly this code (plan_guard.py).

KNOWN LIMIT, left in on purpose: a split world CIDR, a policy condition that matches everything and a
queue policy on a type with no rule are allowed. The script prints those plans. A plain HTTP listener on
an internal load balancer is sent to review, because the rules never join two resources.

Run (from src/):  python3 step_04_with_guard.py
Output: a report, plus out/step_04_decisions.csv, out/step_04_summary.json and out/step_04_rules.json
"""
import csv
import json
import os
from collections import Counter

from common import load_plans, check_plan, decide, flagged_by_search, ensure_out, OUT_DIR, RULES, TRUTH_TO_DECISION

plans = load_plans()
rows = []
for p in plans:
    result = check_plan(p["plan"])
    fs = result["findings"]
    on_target = [f for f in fs if f["address"] == p["target"]]
    rows.append({"plan_id": p["plan_id"], "kind": p["kind"], "truth": p["truth"], "decision": decide(fs),
                 "expected_hit": bool(p["expected"]) and any(f["rule"] == p["expected"] for f in on_target),
                 "off_target": len(fs) - len(on_target), "checked": result["checked"],
                 "findings": "; ".join(f"{f['rule']}:{f['address']}" for f in fs) or "none"})

b = [r for r in rows if r["truth"] == "block"]
rv = [r for r in rows if r["truth"] == "review"]
nb = [r for r in rows if r["truth"] == "ok"]
blocked = [r for r in b if r["decision"] == "BLOCK"]
hit = sum(1 for r in blocked if r["expected_hit"])
flagged = sum(1 for r in rv if r["decision"] != "ALLOW")
false_block = sum(1 for r in nb if r["decision"] == "BLOCK")
false_review = [r for r in nb if r["decision"] == "REVIEW"]
exact = sum(1 for r in rows if r["decision"] == TRUTH_TO_DECISION[r["truth"]])
reads = sum(1 for r in rows if r["decision"] != "ALLOW")
missed = [r for r in b if r["decision"] == "ALLOW"]
off_target = sum(r["off_target"] for r in rows)
text_flags = sum(1 for p in plans if flagged_by_search(p["plan"]))

print("STEP 4 - parser, ten rules and unknown handling together")
print(f"  risky plans blocked: {len(blocked)} of {len(b)}")
print(f"  blocked plans where the finding sits on the planted resource with the expected rule: {hit} of {len(blocked)}")
print(f"  plans that need a look, flagged for review: {flagged} of {len(rv)}")
print(f"  harmless plans blocked: {false_block} of {len(nb)}; sent to review: {len(false_review)} of {len(nb)} "
      f"({', '.join(sorted({r['kind'] for r in false_review})) or 'none'})")
print(f"  findings on a resource other than the planted one: {off_target}")
print(f"  decision matches the planted truth: {exact} of {len(rows)}")
print(f"  plans a person has to read: {reads} of {len(rows)} (step 2 flagged {text_flags})")
print(f"  risky plans that still pass: {len(missed)} of {len(b)} ({', '.join(sorted({r['kind'] for r in missed})) or 'none'})")
for r in missed:
    print(f"    {r['plan_id']} {r['kind']}")
by_kind = Counter((r["kind"], r["decision"]) for r in rows)
print("  decisions by planted change:")
for kind in sorted({r["kind"] for r in rows}):
    print(f"    {kind:<22} " + ", ".join(f"{d} {by_kind[(kind, d)]}" for d in ("BLOCK", "REVIEW", "ALLOW") if by_kind[(kind, d)]))

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
summary = {"risky_blocked": len(blocked), "risky": len(b), "review_flagged": flagged, "review": len(rv),
           "harmless_blocked": false_block, "harmless_reviewed": len(false_review), "harmless": len(nb),
           "exact_match": exact, "plans": len(rows), "to_read": reads, "missed_risky": len(missed)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
with open(os.path.join(OUT_DIR, "step_04_rules.json"), "w", encoding="utf-8") as fh:
    json.dump([{"id": r.id, "name": r.name, "severity": r.severity, "types": list(r.types)} for r in RULES], fh, indent=1)
print("Wrote step_04_decisions.csv, step_04_summary.json and step_04_rules.json in src/out/")
