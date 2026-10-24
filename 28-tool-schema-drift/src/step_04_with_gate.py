"""Step 4 - The fix: one gate with three parts.

  1. structural diff, each change classified breaking / behavior_risk / non_breaking
  2. a number-and-unit check on every description that changed
  3. replay of the recorded calls against the new schema

Decision per pull request: BLOCK if anything breaks, REVIEW if the meaning may have moved, else ALLOW.
The command-line tool and the GitHub Action in action/ run exactly this code (tool_schema_drift.py).

KNOWN LIMIT, left in on purpose: a change in meaning that carries no number and no unit
("exclusive of the end date") is allowed. The script prints those pull requests.

Run (from src/):  python3 step_04_with_gate.py
Output: a report, plus out/step_04_decisions.csv and out/step_04_summary.json
"""
import csv
import json
from collections import Counter

from common import load_cases, calls_by_tool, diff_schemas, decide, replay, ensure_out, OUT_DIR, TRUTH_TO_DECISION
import os

cases, calls = load_cases(), calls_by_tool()
rows = []
for c in cases:
    fs = diff_schemas(c["old"], c["new"])
    nbroken = len(replay(c["new"], calls.get(c["tool"], [])))
    d = decide(fs)
    if nbroken and d != "BLOCK":
        d = "BLOCK"
    rows.append({"pr_id": c["pr_id"], "tool": c["tool"], "change_kind": c["kind"], "truth": c["truth"],
                 "decision": d, "findings": "; ".join(f"{f['kind']}:{f['param']}" for f in fs) or "none", "broken_calls": nbroken})

b = [r for r in rows if r["truth"] == "breaking"]
rk = [r for r in rows if r["truth"] == "behavior_risk"]
nb = [r for r in rows if r["truth"] == "non_breaking"]
blocked_b = sum(1 for r in b if r["decision"] == "BLOCK")
flag_r = sum(1 for r in rk if r["decision"] != "ALLOW")
false_block = sum(1 for r in nb if r["decision"] == "BLOCK")
false_review = sum(1 for r in nb if r["decision"] == "REVIEW")
exact = sum(1 for r in rows if r["decision"] == TRUTH_TO_DECISION[r["truth"]])
reads = sum(1 for r in rows if r["decision"] != "ALLOW")
missed = [r for r in rk if r["decision"] == "ALLOW"]
confirmed = sum(1 for r in b if r["broken_calls"] > 0)

print("STEP 4 - structure, units and replay together")
print(f"  breaking blocked: {blocked_b} of {len(b)}")
print(f"  breaking confirmed by at least one failing recorded call: {confirmed} of {len(b)}")
print(f"  behavior-risk flagged for review: {flag_r} of {len(rk)}")
print(f"  harmless pull requests blocked: {false_block} of {len(nb)}; sent to review: {false_review} of {len(nb)}")
print(f"  decision matches the planted truth: {exact} of {len(rows)}")
print(f"  pull requests a person has to read: {reads} of {len(rows)} (step 2 flagged {len(rows)})")
print(f"  behavior-risk that still passes: {len(missed)} of {len(rk)} ({', '.join(sorted({r['change_kind'] for r in missed})) or 'none'})")
for r in missed:
    print(f"    {r['pr_id']} {r['tool']} {r['change_kind']}")
by_kind = Counter((r["change_kind"], r["decision"]) for r in rows)
print("  decisions by planted change:")
for kind in sorted({r["change_kind"] for r in rows}):
    print(f"    {kind:<15} " + ", ".join(f"{d} {by_kind[(kind, d)]}" for d in ("BLOCK", "REVIEW", "ALLOW") if by_kind[(kind, d)]))

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
summary = {"breaking_blocked": blocked_b, "breaking": len(b), "behavior_risk_flagged": flag_r, "behavior_risk": len(rk),
           "harmless_blocked": false_block, "harmless": len(nb), "exact_match": exact, "pull_requests": len(rows),
           "to_read": reads, "missed_behavior_risk": len(missed)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_decisions.csv and step_04_summary.json in src/out/")
