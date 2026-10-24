"""Step 4 - The fix: the canary gate in entitlement_canary.py.

  1. a stratified pack built from the access export (stale access list, nested deny, direct deny,
     ordinary, and at least three canaries per source)
  2. each canary run with a control query by the user with the widest access first, then the probe
  3. every returned document checked against the resolver, not only the canary's target, using the
     access export from the pull request's branch, so a grant made in the same change is not a leak
  4. notes for a pack that cannot test: inert canaries, canaries run unprimed, sources with too few

Decision per pull request: BLOCK when a user was returned a document they may not open, REVIEW when
nothing leaked but the pack could not test everything, else ALLOW. The command line and the Action
in action/ run exactly this code (entitlement_canary.py).

KNOWN LIMIT, left in on purpose: a leak that touches one (user, document) pair can pass. The script
prints every leaking pull request that passes, and how many leaked pairs a canary was aimed at.

Run (from src/):  python3 step_04_with_canary.py
Output: a report, plus out/step_04_decisions.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import (load_world, load_prs, pr_system, patched_access, build_pack, evaluate, run_harness,
                    exhaustive_leaks, ensure_out, OUT_DIR)

world, prs = load_world(), load_prs()
pack = build_pack(world["access"])
rows = []
for p in prs:
    rep = evaluate(patched_access(world, p["patch"]), pack, run_harness(pr_system(world, p), pack), min_per_source=3)
    leaked = exhaustive_leaks(pr_system(world, p)) if p["leaks"] else set()
    rows.append({"pr_id": p["pr_id"], "change_kind": p["kind"], "truth": "leak" if p["leaks"] else "no leak",
                 "decision": rep["decision"], "leaking_canaries": len(rep["leaks"]), "retired": len(rep["retired"]),
                 "inert": len(rep["inert"]), "leaked_pairs": len(leaked),
                 "aimed": sum(1 for c in pack if (c["user_id"], c["doc_id"]) in leaked)})

leak = [r for r in rows if r["truth"] == "leak"]
clean = [r for r in rows if r["truth"] == "no leak"]
blocked = [r for r in leak if r["decision"] == "BLOCK"]
passed = [r for r in leak if r["decision"] != "BLOCK"]
incidental = [r for r in blocked if r["aimed"] == 0]
reviewed = [r for r in clean if r["decision"] == "REVIEW"]
grants = [r for r in rows if r["change_kind"] == "acl_grant"]
reads = sum(1 for r in rows if r["decision"] != "ALLOW")

print("STEP 4 - stratified pack, control queries, every returned document checked")
print(f"  pack: {len(pack)} canaries (" + ", ".join(f"{k} {v}" for k, v in sorted(Counter(c['stratum'] for c in pack).items())) + ")")
print(f"  canaries with no control query because nobody may open the target today: {sum(1 for c in pack if not c['prime_user'])} of {len(pack)}")
print(f"  leaking pull requests blocked: {len(blocked)} of {len(leak)}")
print(f"  blocked with no canary aimed at a leaked pair (another canary's results held a leaked document): {len(incidental)} of {len(blocked)}")
print(f"  clean pull requests blocked: {sum(1 for r in clean if r['decision'] == 'BLOCK')} of {len(clean)}; sent to review: {len(reviewed)} of {len(clean)}")
print(f"  access-grant pull requests allowed: {sum(1 for r in grants if r['decision'] == 'ALLOW')} of {len(grants)}; "
      f"canaries retired per pull request: {min(r['retired'] for r in grants)} to {max(r['retired'] for r in grants)}")
print(f"  pull requests sent to review because control queries came back empty: {sum(1 for r in clean if r['inert'] > 0)} of {len(clean)}")
print(f"  pull requests a person has to read: {reads} of {len(rows)}")
print(f"  leaking pull requests that pass: {len(passed)} of {len(leak)}")
for r in passed:
    print(f"    {r['pr_id']} {r['change_kind']}: {r['leaked_pairs']} leaked pair, canaries aimed at it {r['aimed']}")
by = Counter((r["change_kind"], r["decision"]) for r in rows)
print("  decisions by planted change:")
for kind in sorted({r["change_kind"] for r in rows}):
    print(f"    {kind:<19} " + ", ".join(f"{d} {by[(kind, d)]}" for d in ("BLOCK", "REVIEW", "ALLOW") if by[(kind, d)]))

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
summary = {"leaking_blocked": len(blocked), "leaking": len(leak), "clean_blocked": sum(1 for r in clean if r["decision"] == "BLOCK"),
           "clean": len(clean), "clean_reviewed": len(reviewed), "to_read": reads, "pull_requests": len(rows),
           "passed": len(passed), "incidental": len(incidental), "pack": len(pack)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_decisions.csv and step_04_summary.json in src/out/")
