"""Step 4 - The fix: one gate with four parts.

  1. a parser that reads the change record by explicit labels and evidence ids, and ignores comments
     and code fences
  2. the tier-to-evidence table, with the tier taken from the registry when the use case is listed
  3. a check that each reference names a file in the repository
  4. a freshness check against the as-of date
Decision per pull request: BLOCK if required evidence is missing, stale or unusable, REVIEW if a person
should look (tier label disagrees with the registry, tier unverified, external link), else ALLOW.
The command-line tool and the GitHub Action in action/ run exactly this code (evidence_gate.py).

KNOWN LIMIT, left in on purpose: a reference to a real file with the wrong content, and a registry
that holds a use case too low, pass. The script prints those pull requests.

Run (from src/):  python3 step_04_with_gate.py
Output: a report, plus out/step_04_decisions.json and out/step_04_summary.json
"""
import json
import os
from collections import Counter

from common import OUT_DIR, TRUTH_TO_DECISION, ensure_out, load_cases, load_world, run_gate

cases, world = load_cases(), load_world()
rows = []
for c in cases:
    res = run_gate(c, world)
    flagged = sorted({i for f in res["findings"] if f["class"] == "block" for i in f["items"]})
    rows.append({"pr_id": c["pr_id"], "use_case": c["use_case"], "kind": c["kind"], "truth": c["truth"],
                 "decision": res["decision"], "flagged_items": flagged, "bad_items": c["bad_items"],
                 "findings": [{"class": f["class"], "kind": f["kind"], "reason": f["reason"]} for f in res["findings"]],
                 "body": c["body"]})

bad = [r for r in rows if r["truth"] == "should_block"]
fine = [r for r in rows if r["truth"] == "fine"]
review = [r for r in rows if r["truth"] == "needs_review"]
blocked = [r for r in bad if r["decision"] == "BLOCK"]
exact = [r for r in blocked if r["flagged_items"] == r["bad_items"]]
no_items = [r for r in blocked if r["kind"] == "no_record"]
missed = [r for r in bad if r["decision"] == "ALLOW"]
partial = [r for r in bad if r["decision"] == "REVIEW"]
fine_review = [r for r in fine if r["decision"] == "REVIEW"]
fine_blocked = [r for r in fine if r["decision"] == "BLOCK"]
matches = sum(1 for r in rows if r["decision"] == TRUTH_TO_DECISION[r["truth"]])
to_review = sum(1 for r in rows if r["decision"] == "REVIEW")
hard = Counter(r["kind"] for r in fine if r["decision"] == "ALLOW" and r["kind"] in ("complete_formatted", "at_limit"))

print("STEP 4 - parser, tier table, file listing and dates together")
print(f"  should-block pull requests blocked: {len(blocked)} of {len(bad)}")
print(f"  blocked ones that name exactly the planted bad items: {len(exact)} of {len(blocked) - len(no_items)} (the {len(no_items)} with no record name none)")
print(f"  fine pull requests blocked: {len(fine_blocked)} of {len(fine)} ({', '.join(sorted({r['kind'] for r in fine_blocked})) or 'none'}); "
      f"sent to review: {len(fine_review)} of {len(fine)} ({', '.join(sorted({r['kind'] for r in fine_review})) or 'none'})")
print("  hard negatives allowed: " + ", ".join(f"{k} {hard[k]} of {sum(1 for r in fine if r['kind'] == k)}" for k in sorted(hard)))
print(f"  wrong-tier-label pull requests sent to review: {sum(1 for r in review if r['decision'] == 'REVIEW')} of {len(review)}")
print(f"  decision matches the planted truth: {matches} of {len(rows)}")
print(f"  pull requests a reviewer is asked to look at: {to_review} of {len(rows)} (the author fixes the {sum(1 for r in rows if r['decision'] == 'BLOCK')} blocked ones)")
print(f"  should-block that still pass: {len(missed)} of {len(bad)} ({', '.join(sorted({r['kind'] for r in missed})) or 'none'})")
for r in missed:
    print(f"    {r['pr_id']} {r['use_case']} {r['kind']}")
print(f"  should-block that reach review only: {len(partial)} of {len(bad)} ({', '.join(sorted({r['kind'] for r in partial})) or 'none'})")
by_kind = Counter((r["kind"], r["decision"]) for r in rows)
print("  decisions by planted defect:")
for kind in sorted({r["kind"] for r in rows}):
    print(f"    {kind:<25} " + ", ".join(f"{d} {by_kind[(kind, d)]}" for d in ("BLOCK", "REVIEW", "ALLOW") if by_kind[(kind, d)]))

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_decisions.json"), "w", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=1, sort_keys=True)
summary = {"blocked": len(blocked), "should_block": len(bad), "exact_items": len(exact), "blocked_with_items": len(blocked) - len(no_items),
           "fine_blocked": len(fine_blocked), "fine": len(fine), "fine_review": len(fine_review),
           "needs_review": len(review), "needs_review_sent": sum(1 for r in review if r["decision"] == "REVIEW"),
           "exact_match": matches, "pull_requests": len(rows), "to_review": to_review, "missed": len(missed), "review_only": len(partial)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_decisions.json and step_04_summary.json in src/out/")
