"""Step 4 - The fix: read the form by its own headings, recompute, cross-check, reconcile the labels.

For every issue the tool (intake_tier_action.py, the same code the GitHub Action in action/ runs):
  1. reads the body by exact form headings, and sends a body it cannot read to needs-info
  2. recomputes the tier from the rubric, using the higher of the form and the data catalog for the data
     class, the higher of the form and the registry for the vendor model, and counting a blank or unsure
     customer-facing answer as customer-facing until the sponsor confirms (a summary that mentions a
     customer while the form says no raises a flag but does not change the tier)
  3. adds exactly one tier label (plus tier-mismatch when the declared tier differs) and removes its own
     stale labels on every edit, leaving other labels alone
  4. writes one comment that carries a marker, and echoes only text it has made safe

KNOWN LIMIT, left in on purpose: when the form and the catalog both understate a data class, the result
agrees with the wrong answer. The script prints those issues.

Run (from src/):  python3 step_04_with_action.py
Output: a report, plus out/step_04_results.json
"""
import json
import os
from collections import Counter

from common import (CHOICES, DATA, OUT_DIR, assess, ensure_out, events, load_catalog, load_issues, load_registry,
                    naive_assess, plan_labels, render_comment, render_github, wanted_labels)

issues = load_issues()
catalog = load_catalog(os.path.join(DATA, "catalog.csv"))
registry = load_registry(os.path.join(DATA, "registry.csv"))
order = CHOICES["data_class"].index
n = len(issues)
res = {i["issue"]: assess(i["body_v1"], catalog, registry, i["issue"]) for i in issues}
tiered = [i for i in issues if res[i["issue"]]["decision"] == "TIERED"]
needs = [i for i in issues if res[i["issue"]]["decision"] == "NEEDS_INFO"]
right = [i for i in tiered if res[i["issue"]]["tier"] == i["ref"]]
hi = [i for i in issues if i["ref"] >= 3]
under = [i for i in tiered if res[i["issue"]]["tier"] < i["ref"]]
over = [i for i in tiered if res[i["issue"]]["tier"] > i["ref"]]
naive_right = sum(1 for i in issues if naive_assess(i["body_v1"])["tier"] == i["ref"])

print("STEP 4 - form headings, recompute, cross-check, reconcile")
print(f"  tiered: {len(tiered)} of {n}; sent to needs-info: {len(needs)} of {n}")
print(f"  tier equals the reference tier: {len(right)} of {n} (step 2: {naive_right} of {n}); among tiered issues: {len(right)} of {len(tiered)}")
print(f"  tier 3-4 issues: tiered 3-4 on {sum(1 for i in hi if i in tiered and res[i['issue']]['tier'] >= 3)} of {len(hi)}, "
      f"tiered 1-2 on {sum(1 for i in hi if i in tiered and res[i['issue']]['tier'] < 3)}, sent to needs-info on {sum(1 for i in hi if i in needs)}")
print(f"  tier below the reference: {len(under)}; above: {len(over)}")
by_kind = Counter(i["kind"] for i in needs)
print("  needs-info by kind of body: " + ", ".join(f"{k} {by_kind[k]} of {sum(1 for i in issues if i['kind'] == k)}"
                                                   for k in ("no_form", "renamed_heading", "truncated", "pasted_heading", "ok")))
print(f"  hard negative: {by_kind['pasted_heading']} complete forms went to needs-info only because a pasted block repeats a heading")
loose = [i for i in issues if i["loose"] and i["kind"] == "ok"]
crlf = [i for i in issues if i["crlf"] and i["kind"] == "ok"]
print(f"  hard negative: needs-info on {sum(1 for i in loose if i in needs)} of {len(loose)} intact bodies with odd case or padding, "
      f"and on {sum(1 for i in crlf if i in needs)} of {len(crlf)} intact bodies with Windows line endings")

mismatch = [i for i in tiered if "tier-mismatch" in wanted_labels(res[i["issue"]])]
real = [i for i in mismatch if res[i["issue"]]["declared"] != i["ref"]]
print(f"  tier-mismatch raised on {len(mismatch)} issues; on {len(real)} of them the declared tier differs from the reference tier")

def raised(code):
    return [i for i in tiered if any(f["code"] == code for f in res[i["issue"]]["flags"])]

cat = raised("DATA_CLASS_BELOW_CATALOG")
cue = raised("CUSTOMER_FACING_CUE")
amb = raised("CUSTOMER_FACING_AMBIGUOUS")
print(f"  DATA_CLASS_BELOW_CATALOG raised {len(cat)}, form below the true class on {sum(1 for i in cat if order(i['form_data_class']) < order(i['true']['data_class']))}")
print(f"  CUSTOMER_FACING_CUE raised {len(cue)}, truly customer-facing on {sum(1 for i in cue if i['true']['customer_facing'] == 'yes')} (a flag only; the tier is unchanged)")
print(f"  CUSTOMER_FACING_AMBIGUOUS raised {len(amb)}, truly customer-facing on {sum(1 for i in amb if i['true']['customer_facing'] == 'yes')}")
print(f"  VENDOR_NOT_DECLARED raised {len(raised('VENDOR_NOT_DECLARED'))}; DATA_CLASS_ABOVE_CATALOG raised {len(raised('DATA_CLASS_ABOVE_CATALOG'))} (tier kept at the form's class)")


def used(i):
    return dict(zip(["customer_facing", "autonomy", "data_class", "vendor", "regulatory", "exposure"], [r[1] for r in res[i["issue"]]["rows"]]))


causes = Counter()
for i in under + over:
    u, t = used(i), i["true"]
    if order(u["data_class"]) < order(t["data_class"]):
        causes["data class below the true class (catalog silent or also low)"] += 1
    if order(u["data_class"]) > order(t["data_class"]):
        causes["data class above the true class (catalog overstates)"] += 1
    if u["vendor"] != t["vendor"]:
        causes["vendor: form and registry both silent"] += 1
    if u["customer_facing"] == "no" and t["customer_facing"] == "yes":
        causes["customer-facing: form said no, truly customer-facing"] += 1
    if u["customer_facing"] == "yes" and t["customer_facing"] == "no":
        causes["customer-facing: resolved to yes, truly internal"] += 1
print("  why the tier differs from the reference (an issue can have more than one cause):")
for k, v in sorted(causes.items()):
    if v:
        print(f"    {k}: {v}")

# labels across edits: start with an unrelated label the tool must leave alone
final, kept, one_state = {}, 0, 0
for i in issues:
    labels = ["ai-intake"]
    for body in events(i):
        r = assess(body, catalog, registry, i["issue"])
        add, remove = plan_labels(wanted_labels(r), labels)
        labels = sorted((set(labels) - set(remove)) | set(add))
    final[i["issue"]] = labels
    kept += "ai-intake" in labels
    one_state += sum(1 for x in labels if x.startswith("ai-tier:") or x == "needs-info") == 1
edited = [i for i in issues if i["edited"]]
v2 = {i["issue"]: assess(i["body_v2"], catalog, registry, i["issue"]) for i in edited}
print(f"  after {len(edited)} edits: exactly one tier-or-needs-info label on {one_state} of {n} issues; the unrelated label kept on {kept} of {n}")
print(f"  edited issues with a tier equal to the reference: {sum(1 for i in edited if res[i['issue']]['tier'] == i['ref'])} of {len(edited)} before the edit, "
      f"{sum(1 for i in edited if v2[i['issue']]['tier'] == i['ref'])} of {len(edited)} after")

comments = {i["issue"]: render_comment(res[i["issue"]]) for i in issues}
hostile = [i for i in issues if i["hostile"]]
forged = 0
for i in issues:
    r = res[i["issue"]]
    forged += sum(1 for ln in render_github(r).splitlines()
                  if not ln.startswith(("::warning title=intake-tier-action", "::notice title=intake-tier-action")))
echoed = sum(1 for i in issues if any(m in ln for ln in comments[i["issue"]].splitlines()[1:] for m in ("@", "<", "::", "](")))
print(f"  hostile lines in {len(hostile)} bodies: workflow commands forged in the log: {forged}; comments that echo a mention, tag, link or command: {echoed} of {n}")
print(f"  comments that start with the marker the Action searches for: {sum(1 for c in comments.values() if c.startswith('<!-- intake-tier-action -->'))} of {n}")

low = [i for i in tiered if order(used(i)["data_class"]) < order(i["true"]["data_class"])]
wrong = [i for i in low if res[i["issue"]]["tier"] != i["ref"]]
print(f"  KNOWN LIMIT: {len(low)} issues are tiered with a data class below the true class (the form and the catalog both understate it, or the dataset was left blank); the tier is wrong on {len(wrong)} of them")
for i in wrong:
    print(f"    issue {i['issue']}: tier {res[i['issue']]['tier']}, reference {i['ref']}, dataset {i['dataset']}")

ensure_out()
rows = [{"issue": i["issue"], "title": i["title"], "kind": i["kind"], "declared": res[i["issue"]]["declared"], "reference": i["ref"],
         "step2_tier": naive_assess(i["body_v1"])["tier"], "tier": res[i["issue"]]["tier"], "decision": res[i["issue"]]["decision"],
         "labels": wanted_labels(res[i["issue"]]), "flags": [f["code"] for f in res[i["issue"]]["flags"]],
         "problems": res[i["issue"]]["problems"], "body": i["body_v1"], "comment": comments[i["issue"]]} for i in issues]
summary = {"issues": n, "tiered": len(tiered), "needs_info": len(needs), "correct": len(right), "step2_correct": naive_right,
           "high_tier": len(hi), "high_found": sum(1 for i in hi if i in tiered and res[i["issue"]]["tier"] >= 3),
           "mismatch": len(mismatch), "known_limit": len(low)}
with open(os.path.join(OUT_DIR, "step_04_results.json"), "w", encoding="utf-8") as fh:
    json.dump({"summary": summary, "rows": rows}, fh, indent=1, sort_keys=True)
print("Wrote step_04_results.json in src/out/")
