"""Step 4 - The fix: all three families together.

  completeness  details present for each 25 percent owner and the control person; certification signed
  arithmetic    percentages add up (tolerance 0.1 point); an entity at 25 percent or more shows its owners
  grounding     each name, percentage and detail appears on a filing line that names the same person

Decision per packet: PASS, or REVIEW with the findings. The command-line tool in kyb_packet_check.py
runs exactly this code.

KNOWN LIMIT, left in on purpose: a note in the filing that changes who the owner is (a nominee
holding for someone not on the schedule) passes. The script prints those packets.

Run (from src/):  python3 step_04_with_check.py
Output: a report, plus out/step_04_decisions.csv and out/step_04_summary.json
"""
from __future__ import annotations

import csv
import json
import os
from collections import Counter

from common import OUT_DIR, by_scenario, ensure_out, load_packets, owners_in_file, print_tally, run_checks, tally
from kyb_packet_check import decide
from step_02_field_validation import shape_problems


def main() -> None:
    packets = load_packets()
    found = run_checks(packets)
    flagged = {k for k, v in found.items() if v}
    t = tally(packets, flagged)
    missed = [p for p in packets if p["defect"] and p["packet_id"] not in flagged]
    print("STEP 4 (step_04_with_check.py) - completeness, arithmetic and grounding together")
    print_tally(t)
    by_shape = sum(1 for p in packets if shape_problems(p["raw"]))
    print(f"  packets sent to a person: {len(flagged)} of {len(packets)} (the step 2 shape check flagged {by_shape})")
    print(f"  findings per flagged packet: {min(len(found[k]) for k in flagged)} to {max(len(found[k]) for k in flagged)}")
    print(f"  misreads that still pass: {len(missed)} of {t['misreads']}")
    for p in missed:
        print(f"    {p['packet_id']} {p['scenario']}: {p['detail']}")
    fam = Counter()
    for k in sorted(flagged):
        fam["+".join(sorted({f["family"] for f in found[k]}))] += 1
    print("  flagged packets by the families that fired: " + ", ".join(f"{k} {v}" for k, v in sorted(fam.items())))
    print("  decisions by planted scenario:")
    flags = by_scenario(packets, flagged)
    for k, (n, total) in flags.items():
        print(f"    {k:<24}REVIEW {n}, PASS {total - n}")

    rows = [{"packet_id": p["packet_id"], "entity": p["entity"], "scenario": p["scenario"],
             "planted": "misread" if p["defect"] else "clean", "decision": decide(found[p["packet_id"]]),
             "findings": len(found[p["packet_id"]]),
             "finding_kinds": "; ".join(sorted({f["kind"] for f in found[p["packet_id"]]})) or "none",
             "wrong_people": "yes" if owners_in_file(p["raw"]) != p["true_owners"] else "no"} for p in packets]
    ensure_out()
    with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    summary = dict(t, packets=len(packets), sent_to_person=len(flagged), missed=len(missed))
    with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    print("Wrote step_04_decisions.csv and step_04_summary.json in src/out/")


if __name__ == "__main__":
    main()
