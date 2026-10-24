"""Step 4 - The fix: recompute with the catalog, the registry and the text rules.

This runs recompute() from tiergate.py, the same code the command line and the staged skill call, on
every form. The tool sees the visible form columns, the catalog's recorded class and the registry. The
hidden columns (true_*, reference_*, planted) are read afterwards, only to score the result.

Two groups of forms were planted on purpose. Hard cases: the form is wrong and the rules have nothing
to disagree with it. Hard negatives: the form is right and a rule could still raise the tier.

KNOWN LIMIT, left in on purpose: a form whose data class is understated while the catalog is stale or
silent, or whose vendor dependency is missing from the registry, keeps a tier below the reference. The
script prints each of those forms.

Run (from src/):  python3 step_04_with_tiergate.py
Output: a report, plus out/step_04_results.csv and out/step_04_summary.json
"""
from __future__ import annotations

import csv
import json
import os
from collections import Counter

from common import (HARD_CASES, HARD_NEGATIVES, OUT_DIR, ensure_out, form_as_written_tier, load_cases,
                    load_second_sources, metrics, pct)
from tiergate import recompute, status_of

cases = load_cases()
catalog, registry = load_second_sources()
results = {c["use_case_id"]: recompute(c, catalog, registry) for c in cases}
declared = {c["use_case_id"]: c["self_declared_tier"] for c in cases}
rescored = {c["use_case_id"]: form_as_written_tier(c) for c in cases}
tool = {i: r["tier"] for i, r in results.items()}
m_dec, m_form, m_tool = metrics(cases, declared), metrics(cases, rescored), metrics(cases, tool)

status = Counter(status_of(declared[i], tool[i]) for i in tool)
below = [c for c in cases if tool[c["use_case_id"]] < c["reference_tier"]]
above = [c for c in cases if tool[c["use_case_id"]] > c["reference_tier"]]
flagged = sum(1 for r in results.values() if any(f["code"] not in ("TIER_DECLARED_BELOW", "TIER_DECLARED_ABOVE") for f in r["flags"]))
codes_above = Counter(f["code"] for c in above for f in results[c["use_case_id"]]["flags"]
                      if f["code"] not in ("TIER_DECLARED_BELOW", "TIER_DECLARED_ABOVE"))
hard_neg_above = [c for c in above if any(t in HARD_NEGATIVES for t in c["planted"])]

print("STEP 4 - recompute with the catalog, the registry and the text rules")
print(f"  recomputed tier equals the reference: {m_tool['exact']} of {m_tool['n']} ({pct(m_tool['exact'], m_tool['n'])}); "
      f"declared was {m_dec['exact']}, form as written {m_form['exact']}")
print(f"  tier 3-4 forms recomputed at tier 3-4: {m_tool['full_caught']} of {m_tool['full']} "
      f"({pct(m_tool['full_caught'], m_tool['full'])}); declared was {m_dec['full_caught']}")
print(f"  below the reference: {m_tool['under']} (declared {m_dec['under']}); above: {m_tool['over']} (declared {m_dec['over']})")
print(f"  against the declared tier: {status['UNDER-DECLARED']} under-declared, {status['OVER-DECLARED']} over-declared, "
      f"{status['MATCH']} unchanged; {flagged} forms carry a cross-check flag")
print("  planted situations (planted; recomputed tier below the reference; above it):")
for group, tags in (("hard cases", HARD_CASES), ("hard negatives", HARD_NEGATIVES)):
    print(f"   {group}")
    for tag in tags:
        hit = [c for c in cases if tag in c["planted"]]
        lo = sum(1 for c in hit if tool[c["use_case_id"]] < c["reference_tier"])
        hi = sum(1 for c in hit if tool[c["use_case_id"]] > c["reference_tier"])
        print(f"    {tag:<42} planted {len(hit):>2}   below {lo:>2}   above {hi:>2}")
print(f"  forms recomputed above the reference: {len(above)}; with a planted hard negative: {len(hard_neg_above)}")
print("  flags on those: " + (", ".join(f"{k} {v}" for k, v in sorted(codes_above.items())) or "none"))
print(f"  KNOWN LIMIT: forms still below the reference after the recompute: {len(below)} of {len(cases)}")
for c in below:
    print(f"    {c['use_case_id']} declared {c['self_declared_tier']} recomputed {tool[c['use_case_id']]} "
          f"reference {c['reference_tier']}  planted: {', '.join(c['planted']) or 'none'}")

ensure_out()
fields = ["use_case_id", "title", "declared_tier", "form_tier", "recomputed_tier", "reference_tier", "status", "planted", "flags"]
with open(os.path.join(OUT_DIR, "step_04_results.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for c in cases:
        i = c["use_case_id"]
        w.writerow({"use_case_id": i, "title": c["title"], "declared_tier": declared[i], "form_tier": rescored[i],
                    "recomputed_tier": tool[i], "reference_tier": c["reference_tier"], "status": status_of(declared[i], tool[i]),
                    "planted": ";".join(c["planted"]) or "none",
                    "flags": " | ".join(f["code"] for f in results[i]["flags"]
                                        if f["code"] not in ("TIER_DECLARED_BELOW", "TIER_DECLARED_ABOVE")) or "none"})
summary = {"forms": m_tool["n"], "declared_exact": m_dec["exact"], "form_exact": m_form["exact"], "tool_exact": m_tool["exact"],
           "full": m_tool["full"], "declared_full_caught": m_dec["full_caught"], "form_full_caught": m_form["full_caught"],
           "tool_full_caught": m_tool["full_caught"], "declared_under": m_dec["under"], "tool_under": m_tool["under"],
           "declared_over": m_dec["over"], "tool_over": m_tool["over"], "under_declared": status["UNDER-DECLARED"],
           "over_declared": status["OVER-DECLARED"], "hard_negatives_above": len(hard_neg_above)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_results.csv and step_04_summary.json in src/out/")
