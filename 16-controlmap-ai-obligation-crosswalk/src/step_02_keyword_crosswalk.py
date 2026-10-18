"""Step 2 - The basic approach: a keyword crosswalk spreadsheet.

This is how the crosswalk is usually built by hand or with a lookup formula. An obligation is marked
"covered" when at least two words (stopwords removed) overlap between the obligation (its theme and
statement) and a control (its name and description). The sheet then lists the controls that matched.
It has one status, covered or not covered. It has no scope, no evidence date and no list of controls
that serve nothing.

This script runs that rule on the synthetic data and scores it against data/truth_map.csv, the ground
truth the generator wrote. No model is used anywhere in this repo.

RULE (as the spreadsheet would do it):
  K1. Words are lowercase letters and digits, 3 or more characters, minus a short stopword list. No
      stemming: "monitor" and "monitoring" are different words.
  K2. An obligation and a control match when they share MIN_OVERLAP or more distinct words.
  K3. An obligation is "covered" when it matches at least one control, whatever the control's status.

HOW IT IS SCORED
  * Pairs: each (obligation, control) match against the truth rows (full or partial).
  * Obligations: the sheet's status (covered, or not) against the true status. The sheet gets credit
    only if its label is right and, for "covered", at least one control it names truly drives that
    status. The truth statuses are COVERED, PARTIAL, STALE and UNCOVERED; a sheet that only says
    covered or not covered can reach at most the COVERED and UNCOVERED ones.

Run (from src/):
    python3 step_02_keyword_crosswalk.py

Output: a readable summary, plus out/step_02_sheet.csv and out/step_02_summary.json.
"""

from __future__ import annotations

import csv
import json
from collections import Counter

from step_01_status_quo import (FRAMEWORK_SHORT, OUT_DIR, load_all, status_ok, tokens, truth_statuses)

MIN_OVERLAP = 2     # rule K2


def keyword_matches(data: dict) -> dict:
    """obligation_id -> {control_id: sorted shared words} for every pair at or above MIN_OVERLAP."""
    ct_tok = {c["control_id"]: tokens(c["name"] + " " + c["description"]) for c in data["controls"]}
    out = {}
    for o in data["obligations"]:
        ob_tok = tokens(o["theme"] + " " + o["statement"])
        hits = {}
        for cid, ctk in ct_tok.items():
            shared = ob_tok & ctk
            if len(shared) >= MIN_OVERLAP:
                hits[cid] = sorted(shared)
        out[o["obligation_id"]] = hits
    return out


def sheet_status(matches: dict) -> dict:
    """obligation_id -> (status, controls named). The sheet only knows COVERED or UNCOVERED."""
    return {oid: (("COVERED", sorted(h)) if h else ("UNCOVERED", [])) for oid, h in matches.items()}


def score(data: dict, matches: dict) -> dict:
    truth_pairs = {(t["obligation_id"], t["control_id"]) for t in data["truth"]}
    sheet_pairs = {(oid, cid) for oid, h in matches.items() for cid in h}
    tp = len(sheet_pairs & truth_pairs)
    n_possible = len(data["obligations"]) * len(data["controls"])
    ts = truth_statuses(data)
    ss = sheet_status(matches)
    covered = sum(1 for s in ss.values() if s[0] == "COVERED")
    true_any = sum(1 for o in data["obligations"] if data["truth_by_ob"].get(o["obligation_id"]))
    true_full = sum(1 for v in ts.values() if v[0] in ("COVERED", "STALE"))
    ok = {oid: status_ok(ss[oid], ts[oid]) for oid in ss}
    ceiling = sum(1 for v in ts.values() if v[0] in ("COVERED", "UNCOVERED"))
    conf = Counter((ts[oid][0], ss[oid][0]) for oid in ss)
    return {
        "possible_pairs": n_possible, "sheet_pairs": len(sheet_pairs), "truth_pairs": len(truth_pairs), "tp": tp,
        "fp": len(sheet_pairs) - tp, "fn": len(truth_pairs) - tp,
        "precision_pct": round(tp / len(sheet_pairs) * 100, 1), "recall_pct": round(tp / len(truth_pairs) * 100, 1),
        "obligations": len(ss), "covered": covered, "true_any": true_any, "true_full": true_full,
        "covered_wrong": sum(1 for oid in ss if ss[oid][0] == "COVERED" and not ok[oid]),
        "status_ok": sum(ok.values()), "status_ok_pct": round(sum(ok.values()) / len(ss) * 100, 1),
        "ceiling": ceiling, "ok": ok, "conf": {f"{a}|{b}": n for (a, b), n in conf.items()},
        "min_overlap": MIN_OVERLAP,
    }


def summarize(data: dict) -> dict:
    m = keyword_matches(data)
    s = score(data, m)
    s["matches"] = m
    s["sheet"] = sheet_status(m)
    return s


def main() -> None:
    data = load_all()
    s = summarize(data)
    truth = truth_statuses(data)
    print("STEP 2 - Basic approach: keyword crosswalk spreadsheet")
    print(f"  Rule: an obligation is 'covered' when {s['min_overlap']} or more words (stopwords removed) overlap with a control's")
    print("  name or description. One status: covered or not. No scope, no evidence date, no orphan view.")
    print()
    print("SHEET OUTPUT (first rows)")
    print(f"  {'obligation':<10} {'framework':<13} {'theme':<28} {'sheet says':<12} {'controls linked':>15}  truth")
    for o in data["obligations"][:12]:
        oid = o["obligation_id"]
        sh = s["sheet"][oid]
        print(f"  {oid:<10} {FRAMEWORK_SHORT[o['framework']]:<13} {o['theme']:<28} {sh[0].lower().replace('uncovered', 'not covered'):<12} "
              f"{len(sh[1]):>15}  {truth[oid][0]}")
    print("  ...")
    print()
    print("RESULT")
    w = 50

    def line(label: str, value: str) -> None:
        print(f"  {label:<{w}}{value}")

    line("Candidate pairs checked:", f"{s['possible_pairs']:,} ({s['obligations']} obligations x {len(data['controls'])} controls)")
    line("Pairs the sheet links:", f"{s['sheet_pairs']}")
    line("True pairs in truth_map.csv:", f"{s['truth_pairs']}")
    line("Pair precision:", f"{s['tp']} of {s['sheet_pairs']} ({s['precision_pct']}%)")
    line("Pair recall:", f"{s['tp']} of {s['truth_pairs']} ({s['recall_pct']}%)")
    line("Obligations the sheet marks covered:", f"{s['covered']} of {s['obligations']}")
    line("Obligations with at least one meeting control:", f"{s['true_any']} of {s['obligations']} (truth)")
    line("Obligations with a full-scope control:", f"{s['true_full']} of {s['obligations']} (truth)")
    line("Marked covered but given a wrong status:", f"{s['covered_wrong']} of {s['covered']}")
    line("Right status (label and a true control named):", f"{s['status_ok']} of {s['obligations']} ({s['status_ok_pct']}%)")
    line("Most a covered / not-covered sheet could score:", f"{s['ceiling']} of {s['obligations']} (it cannot say PARTIAL or STALE)")

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_02_sheet.csv", "w", newline="", encoding="utf-8") as f:
        w2 = csv.writer(f, lineterminator="\n")
        w2.writerow(["obligation_id", "sheet_status", "controls_linked", "truth_status", "right_status"])
        for o in data["obligations"]:
            oid = o["obligation_id"]
            w2.writerow([oid, s["sheet"][oid][0], ";".join(s["sheet"][oid][1]), truth[oid][0], int(s["ok"][oid])])
    keep = {k: v for k, v in s.items() if k not in ("matches", "sheet", "ok")}
    (OUT_DIR / "step_02_summary.json").write_text(json.dumps(keep, indent=2), encoding="utf-8")
    print("\nWrote step_02_sheet.csv and step_02_summary.json in src/out/")


if __name__ == "__main__":
    main()
