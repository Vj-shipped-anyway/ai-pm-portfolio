"""Step 4 - The fix: classify the change on four dimensions and run only the probe slices it puts at risk.

  1. split each prompt into statements and align the two revisions
  2. classify each changed statement as constraints, scope, tone, tools or other, with a risk class
  3. map the finding to probe slices (tool access, dimension, or topic words)
Decision per pull request: BLOCK if a rule was removed or weakened or a write tool was granted or lost its
guard, REVIEW if the behavior may have moved, else ALLOW. The command-line tool and the GitHub Action in
action/ run exactly this code (prompt_diff_risk.py).

KNOWN LIMIT, left in on purpose: a one-word swap in a long sentence that carries no rule word, tone word,
tool name or number is allowed, and a rule weakened by a short qualifier can pass. The script prints them.

Run (from src/):  python3 step_04_with_gate.py
Output: a report, plus out/step_04_decisions.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import load_cases, load_world, analyse_all, ensure_out, OUT_DIR, TRUTH_TO_DECISION

cases = load_cases()
catalogue, probes = load_world()
results = analyse_all(cases, catalogue, probes)
rows = []
for c in cases:
    r = results[c["pr_id"]]
    chosen = set(r["selection"]["probe_ids"])
    rows.append({"pr_id": c["pr_id"], "assistant": c["assistant"], "change_kind": c["kind"], "truth": c["truth"],
                 "decision": r["decision"], "findings": "; ".join(f"{f['kind']}" for f in r["findings"]) or "none",
                 "slices": "all" if r["selection"]["everything"] else "; ".join(r["selection"]["slices"]) or "none",
                 "probes_run": len(chosen), "failing": len(c["fails"]), "failing_in_run": sum(1 for p in c["fails"] if p in chosen)})

high = [r for r in rows if r["truth"] == "high"]
med = [r for r in rows if r["truth"] == "medium"]
low = [r for r in rows if r["truth"] == "low"]
risky = high + med
blocked_high = sum(1 for r in high if r["decision"] == "BLOCK")
flag_high = sum(1 for r in high if r["decision"] != "ALLOW")
flag_med = sum(1 for r in med if r["decision"] != "ALLOW")
false_block = [r for r in low if r["decision"] == "BLOCK"]
false_review = [r for r in low if r["decision"] == "REVIEW"]
exact = sum(1 for r in rows if r["decision"] == TRUTH_TO_DECISION[r["truth"]])
reads = sum(1 for r in rows if r["decision"] != "ALLOW")
caught = sum(1 for r in risky if r["failing_in_run"] > 0)
run = sum(r["probes_run"] for r in rows)
full = len(rows) * len(probes)
passed = [r for r in risky if r["decision"] == "ALLOW"]
under = [r for r in high if r["decision"] == "REVIEW"]

print("STEP 4 - four dimensions, one risk class, named probe slices")
print(f"  high-risk blocked: {blocked_high} of {len(high)}; flagged at all: {flag_high} of {len(high)}")
print(f"  medium-risk flagged for review or block: {flag_med} of {len(med)}")
print(f"  harmless pull requests blocked: {len(false_block)} of {len(low)}; sent to review: {len(false_review)} of {len(low)}")
print(f"  decision matches the planted truth: {exact} of {len(rows)}")
print(f"  pull requests a person has to read: {reads} of {len(rows)} (step 2 flagged {len(rows)})")
print(f"  pull requests with a planted failing probe that the selected slices contain: {caught} of {len(risky)}")
print(f"  probes run: {run} of {full} ({run / full:.1%} of what step 2 B runs)")
print(f"  risky pull requests that still pass: {len(passed)} of {len(risky)} ({', '.join(sorted({r['change_kind'] for r in passed})) or 'none'})")
for r in passed:
    print(f"    {r['pr_id']} {r['assistant']} {r['change_kind']}")
print(f"  high-risk pull requests flagged but not blocked: {len(under)} of {len(high)}")
for r in under:
    print(f"    {r['pr_id']} {r['assistant']} {r['change_kind']}")
names = ", ".join(r["pr_id"] + " " + r["change_kind"] for r in false_block) or "none"
print(f"  harmless pull requests blocked: {names}")
kinds = Counter(r["change_kind"] for r in false_review)
print("  harmless pull requests sent to review: " + (", ".join(f"{k} {v}" for k, v in sorted(kinds.items())) or "none"))
by_kind = Counter((r["change_kind"], r["decision"]) for r in rows)
print("  decisions by planted edit:")
for kind in sorted({r["change_kind"] for r in rows}):
    print(f"    {kind:<20} " + ", ".join(f"{d} {by_kind[(kind, d)]}" for d in ("BLOCK", "REVIEW", "ALLOW") if by_kind[(kind, d)]))

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
summary = {"high_blocked": blocked_high, "high": len(high), "high_flagged": flag_high, "medium_flagged": flag_med, "medium": len(med),
           "harmless_blocked": len(false_block), "harmless_review": len(false_review), "harmless": len(low),
           "exact_match": exact, "pull_requests": len(rows), "to_read": reads, "caught": caught, "risky": len(risky),
           "probes_run": run, "probes_full": full, "risky_passing": len(passed),
           "high_not_blocked": len(under)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_decisions.csv and step_04_summary.json in src/out/")
