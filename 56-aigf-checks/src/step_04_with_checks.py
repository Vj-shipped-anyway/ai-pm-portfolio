"""Step 4 - The fix: bind each claim to a labelled line, read the aspects, read the note.

aigf_checks.py applies eight rules to every crosswalk row:
  1. the risk id and the check id resolve (unknown_risk, unknown_check)
  2. the same risk, check and claim label does not appear twice (duplicate_row)
  3. the check has captured output; a row without it is reported, not skipped (no_output)
  4. the claimed label is printed by the check (label_missing)
  5. the value on that line equals the claimed value after case, spacing and thousands separators
     are set aside, and a short number is not found inside a longer one (stale_value)
  6. a row marked full is backed by a check that exercises every aspect of the risk (aspect_gap)
  7. the note does not say compliant, certified or guarantee (overclaim_wording)
  8. each risk gets a status from the rows that pass: CHECKED, PARTIAL, UNVERIFIED or GAP

KNOWN LIMIT, left in on purpose: a note that overclaims in other words, and a registry entry that
declares an aspect the check does not exercise, both pass. The script prints those rows.

Run (from src/):  python3 step_04_with_checks.py
Output: a report, plus out/step_04_rows.csv, out/step_04_risks.csv and out/step_04_summary.json
"""
from __future__ import annotations

import csv
import json
import os

from common import HARD_NEGATIVES, KIND_ORDER, OUT_DIR, ensure_out, load_all, score, status_counts, status_right, tool_flags


def main() -> None:
    d = load_all()
    flags, result = tool_flags(d)
    s = score(d, flags)
    status = result["risk_status"]
    truth = d["row_truth"]
    print("STEP 4 - labelled claims, aspects and notes together")
    print(f"  defective rows found: {s['found']} of {s['defective']}")
    print(f"  found as the planted kind: {s['right_kind']} of {s['defective']}")
    print(f"  harmless rows flagged by mistake: {s['false_alarms']} of {s['clean']}")
    for kind in HARD_NEGATIVES:
        f, n = s["by_kind"][kind]
        print(f"    {kind}: {f} of {n}")
    print(f"  rows a person has to read: {s['flagged']} of {s['rows']}")
    print(f"  claims compared with a printed line: {result['compared']} of {s['rows']}")
    print(f"  risks with the right status: {status_right(d, status)} of {len(d['risks'])}")
    print(f"  status it gives: {status_counts(status)}")
    print(f"  planted truth:   {status_counts(d['risk_truth'])}")
    print("  found by planted kind:")
    for kind in KIND_ORDER:
        f, n = s["by_kind"][kind]
        print(f"    {kind:<19} {f} of {n}")
    missed = [r for r, t in truth.items() if t["defective"] == "yes" and not flags[r]]
    print(f"  defective rows that still pass: {len(missed)} of {s['defective']}")
    for r in missed:
        row = next(x for x in d["rows"] if x["row_id"] == r)
        print(f"    {r} {row['risk_id']} -> {row['check_id']} {truth[r]['kind']}")
    wrong = [f"{r} {status[r]}, truth {d['risk_truth'][r]}" for r in d["risks"] if status[r] != d["risk_truth"][r]]
    print(f"  risks with the wrong status: {len(wrong)} of {len(d['risks'])} ({'; '.join(wrong) or 'none'})")

    ensure_out()
    by_row = {}
    for f in result["findings"]:
        by_row.setdefault(f["row_id"], []).append(f)
    with open(os.path.join(OUT_DIR, "step_04_rows.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["row_id", "risk_id", "check_id", "covers", "claim", "planted_kind", "found", "detail"])
        for row in d["rows"]:
            fs = by_row.get(row["row_id"], [])
            w.writerow([row["row_id"], row["risk_id"], row["check_id"], row["covers"], f"{row['claim_label']}: {row['claim_value']}",
                        truth[row["row_id"]]["kind"], ";".join(f["kind"] for f in fs), " | ".join(f["detail"] for f in fs)])
    with open(os.path.join(OUT_DIR, "step_04_risks.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["risk_id", "title", "status", "planted_status"])
        for r, rec in d["risks"].items():
            w.writerow([r, rec["title"], status[r], d["risk_truth"][r]])
    summary = {"defective": s["defective"], "found": s["found"], "right_kind": s["right_kind"], "clean": s["clean"],
               "false_alarms": s["false_alarms"], "rows": s["rows"], "to_read": s["flagged"], "missed": len(missed),
               "risks": len(d["risks"]), "risks_right": status_right(d, status), "compared": result["compared"]}
    with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    print("Wrote step_04_rows.csv, step_04_risks.csv and step_04_summary.json in src/out/")


if __name__ == "__main__":
    main()
