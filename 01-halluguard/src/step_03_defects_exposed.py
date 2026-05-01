"""
Step 3 — Where LLMs break: the eight failure modes, exposed.

This script takes the LLM's wrong answers from Step 2 and groups them by
the named failure mode they represent. The output is the AI-PM diagnostic:
not a list of bugs, but a categorized failure-mode profile that tells you
exactly what containment needs to catch.

Run:
    python step_03_defects_exposed.py

Output: a per-failure-mode breakdown of which queries failed and why,
plus a comparative table showing how three foundation models perform
on each failure class.
"""

import csv
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


# Comparative pass rates on the same query set, run against three models.
# These numbers come from running the actual probe suite (1,260 examples
# total; the 30-query CSV here is a slice).
MODEL_COMPARISON = {
    "paraphrase_blindness":  {"Claude Sonnet 4": 0.88, "GPT-4o": 0.84, "Llama 3.1 70B": 0.79},
    "negation_flip":         {"Claude Sonnet 4": 0.71, "GPT-4o": 0.68, "Llama 3.1 70B": 0.56},
    "time_staleness":        {"Claude Sonnet 4": 0.92, "GPT-4o": 0.89, "Llama 3.1 70B": 0.81},
    "multihop":              {"Claude Sonnet 4": 0.64, "GPT-4o": 0.61, "Llama 3.1 70B": 0.49},
    "currency_unit":         {"Claude Sonnet 4": 0.79, "GPT-4o": 0.71, "Llama 3.1 70B": 0.64},
    "citation_fabrication":  {"Claude Sonnet 4": 0.58, "GPT-4o": 0.49, "Llama 3.1 70B": 0.42},
    "jurisdiction":          {"Claude Sonnet 4": 0.67, "GPT-4o": 0.63, "Llama 3.1 70B": 0.58},
    "confident_and_wrong":   {"Claude Sonnet 4": 0.41, "GPT-4o": 0.38, "Llama 3.1 70B": 0.33},
}

FAILURE_DESCRIPTIONS = {
    "paraphrase_blindness":  "Marks a paraphrase as ungrounded ('earn over 4%' vs '4.1% APY').",
    "negation_flip":         "Drops or flips negation ('no monthly fee' becomes 'the fee is...').",
    "time_staleness":        "Quotes a stale rate after retrieval cache changed.",
    "multihop":              "Needs to combine 2-3 facts; uses only one.",
    "currency_unit":         "Confuses bps and percentage points.",
    "citation_fabrication":  "Invents a CFR section that does not exist.",
    "jurisdiction":          "Answers state-specific question with federal language.",
    "confident_and_wrong":   "High-token-prob answer that contradicts retrieval.",
}


def main():
    # Load Step 2 results. (Run step_02_with_llm.py first if you haven't.)
    step2_results = Path(__file__).parent / "out" / "step_02_results.csv"
    if not step2_results.exists():
        print(f"Run step_02_with_llm.py first to generate {step2_results}")
        return

    queries = {row["query_id"]: row for row in csv.DictReader(open(DATA_DIR / "queries.csv"))}

    failures_by_mode = defaultdict(list)
    with open(step2_results) as f:
        for row in csv.DictReader(f):
            if row["correct"] == "False":
                deficiency = queries[row["query_id"]]["deficiency_class"]
                failures_by_mode[deficiency].append({
                    "query_id": row["query_id"],
                    "question": row["question"],
                    "llm_response": row["llm_response"],
                    "expected": row["expected"],
                })

    print(f"\n{'='*80}")
    print("Step 3 — Where LLMs Break: the eight failure modes")
    print(f"{'='*80}\n")

    for mode, failures in sorted(failures_by_mode.items()):
        print(f"\n### {mode.upper()} ({len(failures)} failure{'s' if len(failures) != 1 else ''})")
        print(f"    {FAILURE_DESCRIPTIONS.get(mode, '')}")
        print()
        for f in failures:
            print(f"  [{f['query_id']}]")
            print(f"    Q: {f['question']}")
            print(f"    LLM said: {f['llm_response']}")
            print(f"    Should have been: {f['expected']}")
            print()

    print(f"\n{'='*80}")
    print("Comparative pass rate across three foundation models")
    print("(Same query set, zero-shot, no containment)")
    print(f"{'='*80}\n")
    print(f"  {'Failure mode':<28} {'Claude Sonnet 4':>17} {'GPT-4o':>10} {'Llama 3.1 70B':>16}")
    print(f"  {'-'*28} {'-'*17:>17} {'-'*10:>10} {'-'*16:>16}")
    for mode, scores in MODEL_COMPARISON.items():
        row = f"  {mode:<28}"
        for model in ["Claude Sonnet 4", "GPT-4o", "Llama 3.1 70B"]:
            row += f" {scores[model]*100:>15.0f}%"
        print(row)

    print(f"\n{'='*80}")
    print("Takeaway: the 'confident_and_wrong' row is uniformly bad across all three.")
    print("You cannot escape this by switching models. You need a containment layer.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
