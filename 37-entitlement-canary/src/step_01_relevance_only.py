"""Step 1 - Status quo: the only retrieval gate in CI is a relevance eval.

Fifty pull requests each change the retrieval system. The gate runs 96 eval queries and fails a pull
request when the share of relevant results drops. It never asks who may read what. To see what that
misses, each pull request is also probed exhaustively: every document title asked as every user,
and every returned document checked against the access lists. The data is synthetic
(data/_generate.py) and the truth label of each pull request is the kind of change that was planted.

The 0.02 tolerance is an assumption, not taken from any standard.

Run (from src/):  python3 step_01_relevance_only.py
"""
from collections import Counter

from common import load_world, load_prs, pr_system, System, relevance_eval, exhaustive_leaks

TOLERANCE = 0.02

world, prs = load_world(), load_prs()
base = relevance_eval(System(world, {}), world["queries"])
rows = []
for pr in prs:
    system = pr_system(world, pr)
    ev = relevance_eval(system, world["queries"])
    rows.append({"pr": pr, "eval": ev, "stopped": ev["precision"] < base["precision"] - TOLERANCE,
                 "pairs": len(exhaustive_leaks(pr_system(world, pr)))})

leaking = [r for r in rows if r["pr"]["leaks"]]
clean = [r for r in rows if not r["pr"]["leaks"]]
seen = [r for r in leaking if r["eval"]["leaked"] > 0]
print("STEP 1 - a relevance-only eval is the gate")
print(f"  estate: {len(world['access']['documents'])} documents, {len(world['access']['users'])} users, {len(world['queries'])} eval queries, {len(prs)} pull requests")
print(f"  unchanged main: {base['results']} results, {base['precision'] * 100:.1f}% relevant, {base['leaked']} returned to a user who may not open them")
print(f"  rule: a pull request fails when the relevant share falls more than {TOLERANCE} below main")
print(f"  exhaustive probe: {len(leaking)} of {len(prs)} pull requests return a document to someone who may not open it")
print(f"  leaked (user, document) pairs across them: {sum(r['pairs'] for r in leaking)}")
print(f"  leaking pull requests the eval stops: {sum(1 for r in leaking if r['stopped'])} of {len(leaking)}")
print(f"  clean pull requests the eval stops: {sum(1 for r in clean if r['stopped'])} of {len(clean)}")
print(f"  leaking pull requests where the eval queries return at least one leaked document: {len(seen)} of {len(leaking)}")
lk, lc = sum(r["eval"]["leaked"] for r in leaking), sum(r["eval"]["leaked_correct"] for r in leaking)
print(f"  leaked results in those eval runs: {lk}; scored as correct answers: {lc}")
by_kind = Counter((r["pr"]["kind"], r["stopped"]) for r in leaking)
print("  leaking kinds the eval stops: " + ", ".join(f"{k} {by_kind[(k, True)]} of {by_kind[(k, True)] + by_kind[(k, False)]}"
                                                   for k in sorted({r["pr"]["kind"] for r in leaking})))
print("  A leaked document that matches the query is a relevant result, so the eval scores it as a hit.")
