"""Step 3 - Where a canary gate fails when a part is missing.

Four variants, each scored on the same fifty pull requests. A, B and C check by document id: the
canary's target must not be in the returned list. D is the resolver check used in step 4.

  A  60 canaries drawn at random from every (user, document) pair the user cannot open
  B  a stratified pack (stale access list, nested deny, direct deny, ordinary, and at least three per source)
  C  the stratified pack, with a control query by an entitled user run first for every canary
  D  the same run as C, but every returned document is checked against the access export of the pull
     request's branch, not only the canary's target

KNOWN LIMIT, left in on purpose: delegation_inherit leaks one (user, document) pair per pull request.
A pack of about sixty canaries aims at one of those four pairs. Step 4 prints what still passes.

Run (from src/):  python3 step_03_deficiencies_exposed.py
Output: out/step_03_variants.csv
"""
import csv
import os
import random

from common import (load_world, load_prs, pr_system, patched_access, build_pack, closed_pairs, make_canaries, run_harness,
                    evaluate, exhaustive_leaks, ensure_out, OUT_DIR)

world, prs = load_world(), load_prs()
access = world["access"]
rng = random.Random(3)
random_pack = make_canaries(access, rng.sample(closed_pairs(access), 60))
strat_pack = build_pack(access)
VARIANTS = {"A": ("random pack, unprimed", random_pack, False), "B": ("stratified pack, unprimed", strat_pack, False),
            "C": ("stratified pack, primed", strat_pack, True), "D": ("C plus every returned document checked", strat_pack, True)}


def target_hit(pack, rows) -> bool:
    returned = {r["canary_id"]: r["returned_doc_ids"].split(";") for r in rows}
    return any(c["doc_id"] in returned[c["canary_id"]] for c in pack)


leaking = [p for p in prs if p["leaks"]]
clean = [p for p in prs if not p["leaks"]]
flags = {v: {} for v in VARIANTS}
for p in prs:
    for v, (_name, pack, primed) in VARIANTS.items():
        rows = run_harness(pr_system(world, p), pack, prime=primed)
        if v == "D":
            flags[v][p["pr_id"]] = evaluate(patched_access(world, p["patch"]), pack, rows)["decision"] == "BLOCK"
        else:
            flags[v][p["pr_id"]] = target_hit(pack, rows)

print("STEP 3 - what each part of the pack and the run buys")
print(f"  pull requests: {len(leaking)} leak, {len(clean)} do not; canaries: A {len(random_pack)}, B {len(strat_pack)}, C {len(strat_pack)}, D {len(strat_pack)}")
out = []
for v, (name, _pack, _primed) in VARIANTS.items():
    caught = sum(1 for p in leaking if flags[v][p["pr_id"]])
    alarms = sum(1 for p in clean if flags[v][p["pr_id"]])
    print(f"  {v} {name}: leaking caught {caught} of {len(leaking)}; clean flagged {alarms} of {len(clean)}")
    out.append({"variant": f"{v} {name}", "caught": caught, "leaking": len(leaking), "flagged": alarms, "clean": len(clean)})
kinds = sorted({p["kind"] for p in prs})
print("  leaking pull requests caught by kind (A, B, C, D):")
for k in kinds:
    members = [p for p in prs if p["kind"] == k]
    if members[0]["leaks"]:
        print(f"    {k:<19} " + "  ".join(f"{sum(1 for p in members if flags[v][p['pr_id']])} of {len(members)}" for v in VARIANTS))
print("  clean pull requests flagged by kind (C): " + ", ".join(
    f"{k} {sum(1 for p in clean if p['kind'] == k and flags['C'][p['pr_id']])}" for k in kinds if not [p for p in prs if p['kind'] == k][0]["leaks"]))
pairs = {p["pr_id"]: exhaustive_leaks(pr_system(world, p)) for p in prs if p["kind"] == "delegation_inherit"}
aimed = sum(1 for leaked in pairs.values() for c in strat_pack if (c["user_id"], c["doc_id"]) in leaked)
print("  KNOWN LIMIT: delegation_inherit leaks " + ", ".join(f"{pr_id} {len(v)} pair" for pr_id, v in sorted(pairs.items()))
      + f"; canaries in the stratified pack aimed at those pairs: {aimed}")

ensure_out()
with open(os.path.join(OUT_DIR, "step_03_variants.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(out)
print("Wrote step_03_variants.csv in src/out/")
