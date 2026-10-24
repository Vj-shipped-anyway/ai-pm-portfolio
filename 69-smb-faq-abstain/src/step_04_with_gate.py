"""Step 4 - The fix: the abstention gate.

The handoff test and the four checks run in order (handoff, scope, source, ambiguity, grounding). A draft is served only when
every claim in it is supported by the best passage; anything else becomes a handoff to a banker. Writes
out/step_04_decisions.csv and out/step_04_summary.json for the demo page.

Run (from src/):  python3 step_04_with_gate.py
"""
from __future__ import annotations

import csv
import json
import os
from collections import Counter

from common import OUT_DIR, ensure_out, load_cases, load_kb_default, outcome, run_cases, tally


def main() -> None:
    cases, kb = load_cases(), load_kb_default()
    results = run_cases(cases, kb)
    draft_only = tally(cases, run_cases(cases, kb, gates=frozenset()))
    t = tally(cases, results)
    wrong = sum(1 for c in cases if not c["draft_ok"])
    good = sum(1 for c in cases if c["should_serve"])
    held = sum(1 for r in results if r["decision"] == "ABSTAIN")
    reasons = Counter(r["reason"] for r in results if r["decision"] == "ABSTAIN")
    hard_neg = [(c, r) for c, r in zip(cases, results) if c["hard_case"] == "hard_negative"]
    hard_miss = [(c, r) for c, r in zip(cases, results) if c["hard_case"] == "hard_miss"]
    print("STEP 4 - the abstention gate")
    print(f"  wrong answers served: {t['served_wrong']} of {len(cases)} (step 2 served {draft_only['served_wrong']})")
    print(f"  wrong drafts held back: {t['caught']} of {wrong}")
    print(f"  correct drafts served: {t['served_ok']} of {good}; held back by mistake: {t['false_abstain']}")
    print(f"  drafts that decline on their own: {t['declined']}")
    print(f"  handed to a banker in all: {held} of {len(cases)} ({100 * held / len(cases):.1f}%)")
    print("  held back by check: " + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())))
    print(f"  hard negatives (correct drafts a rule could flag): {len(hard_neg)}; served {sum(1 for _c, r in hard_neg if r['decision'] == 'SERVE')}, held back {sum(1 for _c, r in hard_neg if r['decision'] == 'ABSTAIN')}")
    for c, r in hard_neg:
        if r["decision"] == "ABSTAIN":
            print(f"    held back by mistake: {c['qid']} ({r['reason']}) {c['question']}")
    print(f"  hard misses planted (right number, different meaning): {len(hard_miss)}; served {sum(1 for _c, r in hard_miss if r['decision'] == 'SERVE')}")
    for c, r in hard_miss:
        print(f"    KNOWN LIMIT: {c['qid']} served, {r['detail']}")
    ensure_out()
    with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["query_id", "q_class", "question", "draft", "mode", "hard_case", "decision", "reason", "detail", "outcome"])
        for c, r in zip(cases, results):
            w.writerow([c["qid"], c["q_class"], c["question"], c["draft"], c["mode"], c["hard_case"], r["decision"], r["reason"], r["detail"], outcome(c, r)])
    summary = {"questions": len(cases), "draft_wrong": wrong, "draft_correct": good, "declined": t["declined"],
               "wrong_served_draft_only": draft_only["served_wrong"], "wrong_served": t["served_wrong"], "caught": t["caught"],
               "served_ok": t["served_ok"], "false_abstain": t["false_abstain"], "held": held}
    with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    main()
