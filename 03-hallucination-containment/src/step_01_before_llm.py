"""
Step 1 — Before LLMs: rule-based keyword matching chatbot.

This is what most banking chatbots looked like in 2018-2022 — a keyword router
on top of a small set of canned responses. It cannot answer the question
directly; it can only deflect to a page or a human.

Run:
    python step_01_before_llm.py

Output: a CSV of (query_id, question, response, did_it_answer) and a
summary of how many queries actually got a real answer.
"""

import csv
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

INTENT_KEYWORDS = {
    "rate":       ["rate", "apy", "interest", "earn", "earning", "yield"],
    "fee":        ["fee", "charge", "cost", "monthly maintenance"],
    "intro":      ["intro", "introductory", "promotional"],
    "regulation": ["regulation", "rule", "law", "compliance", "act"],
    "available":  ["available", "open", "eligible"],
    "deposit":    ["deposit", "balance", "minimum"],
}

CANNED_RESPONSES = {
    "rate":       "Please see our rate sheet at /rates",
    "fee":        "Please see our fee schedule at /fees",
    "intro":      "Promotional rates are listed on the product details page",
    "regulation": "Please contact compliance@bank.example",
    "available":  "Please see product availability at /products",
    "deposit":    "Please see deposit account details at /deposits",
}


def classify_intent(question: str) -> str:
    q = question.lower()
    for intent, kws in INTENT_KEYWORDS.items():
        if any(kw in q for kw in kws):
            return intent
    return "unknown"


def respond(question: str) -> str:
    intent = classify_intent(question)
    if intent == "unknown":
        return "I'm sorry, I didn't understand that. Let me get a banker for you."
    return CANNED_RESPONSES[intent]


def did_it_answer(response: str) -> bool:
    """A 'real' answer is one that has the actual numbers/facts the customer
    asked about. Pointing to a page is not answering. Hand-off is not answering."""
    deflection_phrases = [
        "see our",
        "please contact",
        "please see",
        "let me get",
        "didn't understand",
    ]
    return not any(phrase in response.lower() for phrase in deflection_phrases)


def main():
    queries_path = DATA_DIR / "queries.csv"
    out_path = Path(__file__).parent / "out" / "step_01_results.csv"
    out_path.parent.mkdir(exist_ok=True)

    answered = 0
    total = 0

    with open(queries_path) as f, open(out_path, "w", newline="") as out:
        reader = csv.DictReader(f)
        writer = csv.writer(out)
        writer.writerow(["query_id", "question", "response", "did_it_answer"])

        print(f"\n{'='*80}")
        print("Step 1 — Before LLMs: Rule-Based Keyword Matching")
        print(f"{'='*80}\n")

        for row in reader:
            response = respond(row["question"])
            answered_flag = did_it_answer(response)
            total += 1
            if answered_flag:
                answered += 1

            writer.writerow([row["query_id"], row["question"], response, answered_flag])

            mark = "ANSWERED" if answered_flag else "DEFLECTED"
            print(f"[{row['query_id']}] {mark}")
            print(f"    Q: {row['question']}")
            print(f"    A: {response}")
            print()

    print(f"{'='*80}")
    print(f"Summary: {answered}/{total} queries got a real answer.")
    print(f"Deflection rate: {(total - answered) / total * 100:.1f}%")
    print(f"Wrote: {out_path}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
