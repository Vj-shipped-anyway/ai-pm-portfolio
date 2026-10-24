"""Step 3 - Where each half fails when used alone.

Two designs, each with one idea, scored on the same 75 packets:
  A  completeness and arithmetic      needs only the extraction: details present, percentages add up,
                                      an entity at 25 percent or more has its owners shown
  B  grounding                        needs the filing text: each name, percentage and detail must
                                      appear on a source line that names the same holder or person

KNOWN LIMIT, left in on purpose: a note in the filing that changes who the owner is (a nominee
holding for someone not on the schedule) is caught by neither design, and step 4 does not catch it
either. The script prints those packets.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from __future__ import annotations

from collections import Counter

from common import by_scenario, load_packets, print_tally, run_checks, tally


def main() -> None:
    packets = load_packets()
    a = run_checks(packets, ("completeness", "arithmetic"))
    b = run_checks(packets, ("grounding",))
    flag_a = {k for k, v in a.items() if v}
    flag_b = {k for k, v in b.items() if v}
    bad = [p for p in packets if p["defect"]]
    print("STEP 3 (step_03_deficiencies_exposed.py) - each half alone")
    print("  A. completeness and arithmetic, no filing text")
    print_tally(tally(packets, flag_a))
    print("  B. grounding against the filing text, no sums")
    print_tally(tally(packets, flag_b))
    only_a = [p for p in bad if p["packet_id"] in flag_a - flag_b]
    only_b = [p for p in bad if p["packet_id"] in flag_b - flag_a]
    both = [p for p in bad if p["packet_id"] in flag_a & flag_b]
    neither = [p for p in bad if p["packet_id"] not in flag_a | flag_b]
    print(f"  misreads caught only by A: {len(only_a)}, only by B: {len(only_b)}, by both: {len(both)}, by neither: {len(neither)}")
    fa, fb = by_scenario(packets, flag_a), by_scenario(packets, flag_b)
    print(f"  {'planted misread':<24}{'A':>9}{'B':>9}")
    for k in sorted({p["scenario"] for p in bad}):
        print(f"    {k:<22}{f'{fa[k][0]} of {fa[k][1]}':>9}{f'{fb[k][0]} of {fb[k][1]}':>9}")
    swaps = [p for p in packets if p["scenario"] == "pct_swapped"]
    kinds = Counter(f["kind"] for p in swaps for f in a[p["packet_id"]])
    print(f"  swapped percents still add up to 100, so the sum cannot see them; A flags {sum(1 for p in swaps if a[p['packet_id']])} of {len(swaps)}"
          " through a missing details record: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
    clean = sum(1 for p in packets if not p["defect"])
    for tol in (0.0, 0.1):
        z = run_checks(packets, ("arithmetic",), tolerance=tol)
        fz = Counter(p["scenario"] for p in packets if not p["defect"] and z[p["packet_id"]])
        print(f"  sum check at tolerance {tol}: clean packets flagged {sum(fz.values())} of {clean}"
              + (" (" + ", ".join(f"{k} {v}" for k, v in sorted(fz.items())) + ")" if fz else ""))
    print(f"  misreads that pass both A and B: {len(neither)} of {len(bad)}")
    for p in neither:
        print(f"    {p['packet_id']} {p['scenario']}: {p['detail']}")
    print("  Thirds written as 33.33 add up to 99.99, which is why the sum needs a tolerance. A note that moves the owner is not a number or a field.")


if __name__ == "__main__":
    main()
