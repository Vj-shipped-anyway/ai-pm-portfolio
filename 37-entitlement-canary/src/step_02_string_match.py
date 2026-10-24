"""Step 2 - The common basic approach: a short hand-written canary list and a string match.

A team adds a few canaries: pairs where the user plainly may not open the document, asked once, with
a check that the document's title does not appear in the answer text. This step builds that list
from the ordinary pairs (no deny entries, no stale access list), removes the canaries that already
fire on the unchanged main (the first red build on main teaches a team to do that), keeps twelve,
and runs them against all fifty pull requests.

Run (from src/):  python3 step_02_string_match.py
"""
from collections import Counter

from common import load_world, load_prs, pr_system, System, build_pack

KEEP = 12

world, prs = load_world(), load_prs()
text = world["text"]
titles = {d["doc_id"]: d["title"] for d in world["access"]["documents"]}


def fires(system, canary) -> bool:
    returned = system.retrieve(canary["user_id"], canary["query"])
    answer = "\n".join(titles[d] + "\n" + text[d] for d in returned)
    return titles[canary["doc_id"]] in answer


ordinary = build_pack(world["access"], {"stale_acl": 0, "nested_deny": 0, "direct_deny": 0, "ordinary": 30}, min_per_source=0)
main = System(world, {})
noisy = [c for c in ordinary if fires(main, c)]
quiet = [c for c in ordinary if c not in noisy]
handpicked = quiet[:KEEP]

leaking = [p for p in prs if p["leaks"]]
clean = [p for p in prs if not p["leaks"]]
flag = {p["pr_id"]: any(fires(pr_system(world, p), c) for c in handpicked) for p in prs}
caught = Counter(p["kind"] for p in leaking if flag[p["pr_id"]])
total = Counter(p["kind"] for p in leaking)
alarms = Counter(p["kind"] for p in clean if flag[p["pr_id"]])

print("STEP 2 - twelve hand-picked canaries and a string match")
print(f"  ordinary canaries tried: {len(ordinary)}; already firing on the unchanged main: {len(noisy)}")
print("  why they fire on main: a document that quotes another document's title is returned to the asker, and the string is there")
print(f"  kept: {len(handpicked)} canaries, none primed")
print(f"  leaking pull requests caught: {sum(caught.values())} of {len(leaking)}")
print("  caught by kind: " + ", ".join(f"{k} {caught[k]} of {total[k]}" for k in sorted(total)))
print(f"  clean pull requests flagged: {sum(alarms.values())} of {len(clean)}")
print("  flagged by kind: " + (", ".join(f"{k} {alarms[k]}" for k in sorted(alarms)) or "none"))
print("  A pair that was off limits when the list was written can be granted later; the list does not know.")
