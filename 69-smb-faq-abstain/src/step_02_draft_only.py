"""Step 2 - The common basic approach: serve every drafted answer.

A model reads the question and the retrieved passage and drafts an answer; nothing checks it. In this
project the drafts are stored stand-ins written by data/_generate.py, not model output, so what this step
measures is what happens when the drafts are served as they come. A draft that declines on its own ("let me
connect you with a banker") is a handoff, not a served answer.

Run (from src/):  python3 step_02_draft_only.py
"""
from __future__ import annotations

from collections import Counter

from common import by_class, load_cases, load_kb_default, run_cases, tally


def main() -> None:
    cases, kb = load_cases(), load_kb_default()
    results = run_cases(cases, kb, gates=frozenset())
    t = tally(cases, results)
    served = t["served_ok"] + t["served_wrong"]
    print("STEP 2 - serve every drafted answer")
    print(f"  drafts served: {served} of {len(cases)}; {t['declined']} drafts decline on their own and become handoffs")
    print(f"  correct answers served: {t['served_ok']}")
    print(f"  wrong answers served: {t['served_wrong']} ({100 * t['served_wrong'] / len(cases):.1f}% of the {len(cases)} questions)")
    print(f"  wrong answers by question class: {by_class(cases, results, 'served_wrong')}")
    modes = Counter(c["mode"] for c, r in zip(cases, results) if r["decision"] == "SERVE" and not c["should_serve"])
    print("  wrong answers by planted mode: " + ", ".join(f"{k} {v}" for k, v in sorted(modes.items())))
    print("  The set is built from failure cases, so this is a stress-test rate, not a rate on live traffic.")


if __name__ == "__main__":
    main()
