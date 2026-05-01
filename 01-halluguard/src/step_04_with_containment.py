"""
Step 4 — The fix: a containment layer.

A second model — the grounding verifier — sits between the chatbot and
the customer. It scores whether the chatbot's response actually matches
the retrieved data. If the score is below a calibrated threshold, the
response is rewritten to an abstention message.

In production, the verifier is a LoRA fine-tune of Llama 3.1 8B trained
specifically on the eight failure modes. For the walkthrough, we mock
its behavior — flagging the same set of wrong answers that real verifier
runs catch in pilot.

Run:
    python step_04_with_containment.py
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


# Per-use-case threshold. Rates and regulatory questions are stricter.
THRESHOLDS = {
    "rates":      0.82,
    "regs":       0.82,
    "disputes":   0.82,
    "general":    0.65,
}


def threshold_for(question: str) -> float:
    q = question.lower()
    if any(w in q for w in ["rate", "apy", "interest", "earn", "yield", "apr"]):
        return THRESHOLDS["rates"]
    if any(w in q for w in ["regulation", "rule", "law", "act", "compliance"]):
        return THRESHOLDS["regs"]
    return THRESHOLDS["general"]


# Mock grounding verifier scores. In production, this is a LoRA-tuned
# Llama 3.1 8B. The mock numbers reflect what the actual verifier produces
# on this query set, calibrated by temperature scaling (T=1.34, ECE=0.07).
VERIFIER_SCORES = {
    "Q01": 0.94,   # correct, high confidence
    "Q02": 0.31,   # NEGATION FLIP detected
    "Q03": 0.28,   # NEGATION FLIP detected
    "Q04": 0.19,   # JURISDICTION caught (state exclusion missed)
    "Q05": 0.12,   # CITATION FAB caught
    "Q06": 0.91,   # correct
    "Q07": 0.24,   # NEGATION FLIP
    "Q08": 0.96,   # correct
    "Q09": 0.43,   # MULTIHOP failure flagged
    "Q10": 0.95,   # correct
    "Q11": 0.93,   # correct
    "Q12": 0.21,   # JURISDICTION
    "Q13": 0.26,   # NEGATION FLIP
    "Q14": 0.38,   # MULTIHOP — wrong tier
    "Q15": 0.34,   # MULTIHOP — wrong tier
    "Q16": 0.18,   # NEGATION (Travel Rewards fee swapped in)
    "Q17": 0.29,   # CURRENCY UNIT
    "Q18": 0.92,   # correct
    "Q19": 0.94,   # correct
    "Q20": 0.41,   # MULTIHOP
    "Q21": 0.32,   # NEGATION
    "Q22": 0.27,   # NEGATION (fabricated 3%)
    "Q23": 0.93,   # correct
    "Q24": 0.91,   # correct
    "Q25": 0.39,   # MULTIHOP
    "Q26": 0.25,   # NEGATION
    "Q27": 0.92,   # correct
    "Q28": 0.16,   # CITATION FAB
    "Q29": 0.95,   # correct
    "Q30": 0.31,   # CURRENCY UNIT
}


# Same mock LLM responses as Step 2.
from step_02_with_llm import MOCK_RESPONSES


def abstention_message(question: str) -> str:
    return "I'm not certain on this one. Let me get a banker for you who can confirm the details."


def respond_with_containment(query_id: str, question: str):
    llm_response, _ = MOCK_RESPONSES.get(query_id, ("(no response)", False))
    score = VERIFIER_SCORES.get(query_id, 0.5)
    threshold = threshold_for(question)
    if score < threshold:
        return abstention_message(question), score, threshold, "ABSTAIN"
    return llm_response, score, threshold, "SHIP"


def main():
    queries_path = DATA_DIR / "queries.csv"
    out_path = Path(__file__).parent / "out" / "step_04_results.csv"
    out_path.parent.mkdir(exist_ok=True)

    served_correct = 0
    served_wrong = 0
    abstained = 0
    total = 0

    print(f"\n{'='*80}")
    print("Step 4 — With Containment: LLM + Grounding Verifier + Abstention")
    print(f"{'='*80}\n")

    with open(queries_path) as f, open(out_path, "w", newline="") as out:
        reader = csv.DictReader(f)
        writer = csv.writer(out)
        writer.writerow([
            "query_id", "question", "raw_llm_response", "verifier_score",
            "threshold", "decision", "served_response", "outcome"
        ])

        for row in reader:
            qid = row["query_id"]
            served, score, threshold, decision = respond_with_containment(qid, row["question"])
            raw_response, was_correct = MOCK_RESPONSES.get(qid, ("", False))
            total += 1

            if decision == "ABSTAIN":
                abstained += 1
                outcome = "abstained_correctly" if not was_correct else "abstained_unnecessarily"
            else:
                if was_correct:
                    served_correct += 1
                    outcome = "served_correct"
                else:
                    served_wrong += 1
                    outcome = "served_wrong"

            writer.writerow([
                qid, row["question"], raw_response, score, threshold,
                decision, served, outcome
            ])

            print(f"[{qid}] verifier={score:.2f} threshold={threshold:.2f} -> {decision}")
            print(f"    Q:        {row['question']}")
            print(f"    LLM:      {raw_response}")
            if decision == "ABSTAIN":
                print(f"    SERVED:   {served}")
            print(f"    Outcome:  {outcome}")
            print()

    print(f"\n{'='*80}")
    print(f"Summary on {total} queries:")
    print(f"  Served correctly:        {served_correct}")
    print(f"  Wrong answers shipped:   {served_wrong}")
    print(f"  Abstained (handed off):  {abstained}")
    print()
    print(f"  Hallucination rate:      {served_wrong/total*100:.1f}%")
    print(f"  Deflection to human:     {abstained/total*100:.1f}%")
    print(f"{'='*80}")
    print(f"\nCompare to Step 2 (LLM only):")
    print(f"  Hallucination rate before containment: 8/30 = 26.7%")
    print(f"  Hallucination rate after containment:  {served_wrong}/{total} = {served_wrong/total*100:.1f}%")
    print(f"\nWrote: {out_path}\n")


if __name__ == "__main__":
    main()
