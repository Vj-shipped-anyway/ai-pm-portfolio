"""Step 3 - Deficiencies exposed: each check alone, a loose threshold, and the limit that stays.

Four checks run on a question and its draft: scope, source, ambiguity and grounding. Each is scored alone on
the same 30 questions, so you can see which wrong drafts it misses. Then the grounding threshold is relaxed
from every claim to half of them. KNOWN LIMIT, left in on purpose: a draft that quotes a number from the
right passage but gives it a different meaning (the wrong tier, month for year, a rate for a different
borrower) is supported by every check, and step 4 does not catch it either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from __future__ import annotations

from common import by_class, load_cases, load_kb_default, run_cases, tally


def show(name: str, cases: list, kb: list, **options) -> list:
    results = run_cases(cases, kb, **options)
    t = tally(cases, results)
    wrong = sum(1 for c in cases if not c["draft_ok"])
    good = sum(1 for c in cases if c["should_serve"])
    print(f"  {name:<50} wrong served {t['served_wrong']:>2} of {wrong}   correct served {t['served_ok']:>2} of {good}")
    return results


def main() -> None:
    cases, kb = load_cases(), load_kb_default()
    print("STEP 3 - each check alone")
    only_source = show("source check only", cases, kb, gates=frozenset({"source"}))
    show("scope, source and ambiguity (the question only)", cases, kb, gates=frozenset({"scope", "source", "ambiguity"}))
    only_grounding = show("grounding only (the draft only)", cases, kb, gates=frozenset({"grounding"}))
    print("  slips past the source check: " + by_class(cases, only_source, "served_wrong"))
    print("  slips past the grounding check: " + by_class(cases, only_grounding, "served_wrong"))
    print("  grounding threshold, all four checks on")
    strict = show("every claim must be supported (1.0)", cases, kb, min_grounded=1.0)
    loose = show("half of the claims must be supported (0.5)", cases, kb, min_grounded=0.5)
    extra = [c for c, s, r in zip(cases, strict, loose) if s["decision"] == "ABSTAIN" and r["decision"] == "SERVE"]
    print("  wrong drafts a loose threshold lets through: " + ", ".join(f"{c['qid']} ({c['mode']})" for c in extra))
    full = run_cases(cases, kb)
    print("  KNOWN LIMIT: wrong drafts that pass all four checks at 1.0")
    for c, r in zip(cases, full):
        if r["decision"] == "SERVE" and not c["should_serve"]:
            print(f"    {c['qid']} {c['mode']}: {c['draft']} (supported by {r['fact_id']}; the right answer is: {c['correct']})")
    print("  Each check misses something the others catch. The remaining misses are numbers that are in the passage and mean something else.")


if __name__ == "__main__":
    main()
