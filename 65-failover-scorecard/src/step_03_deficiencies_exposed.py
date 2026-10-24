"""Step 3 - Where the evidence rule fails when a part is taken out, and the one thing it cannot see.

The full rule (failover_scorecard.py) has five parts: live drill of the right scenario, recovery
within the target, current region and config version, drill inside its window, and dependencies
that are themselves ready. This step takes one part out at a time and counts how many services
that would not recover then pass as READY. The planted truth is known, so the count is exact.

KNOWN LIMIT, left in on purpose: a service can have a clean drill and clean declared dependencies
and still need a service the map does not list. The rule only follows the edges it is given. Step 4
does not catch these either, and this step prints them.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from __future__ import annotations

from common import AS_OF, default_policy, load_all, score, truth_class


def passes(data: dict, skip: tuple) -> list:
    """Services that would not recover but score READY when the parts named in skip are removed."""
    policy = default_policy()
    policy["skip"] = skip
    results = score(data["services"], data["drills"], AS_OF, policy)
    return [r["service_id"] for r in results if r["status"] == "READY" and truth_class(data, r["service_id"]) == "not_ready"]


def main() -> None:
    data = load_all()
    not_ready = sum(1 for i in data["by_id"] if truth_class(data, i) == "not_ready")
    base = passes(data, ())
    print("STEP 3 - take one part of the rule out")
    print(f"  services that would not recover: {not_ready} of {len(data['by_id'])}")
    print(f"  full rule: {len(base)} of {not_ready} pass as READY")
    for part in ("type_and_scenario", "rto", "version_and_region", "age", "dependencies"):
        got = passes(data, (part,))
        stories = sorted({data["truth"][i]["story"] for i in got if i not in base})
        print(f"  without {part:<18} {len(got)} of {not_ready} pass, {len(got) - len(base)} more: {', '.join(stories) or 'none'}")
    print(f"  known limit: {len(base)} services pass every check and would not recover")
    for i in base:
        s, t = data["by_id"][i], data["truth"][i]
        hidden = data["by_id"][t["hidden_depends_on"]]
        drills = sum(1 for d in data["drills"] if d["service_id"] == hidden["service_id"])
        print(f"    {i} {s['name']}: the map lists {', '.join(s['depends_on']) or 'no dependencies'}; "
              f"the planted truth also needs {hidden['service_id']} {hidden['name']}, with {drills} drills on record")
    print("  The rule follows the edges it is given. A missing edge is invisible to it.")


if __name__ == "__main__":
    main()
