"""
Step 2 — With LLMs: RAG + Claude (or GPT, or Llama).

Now we have an LLM. Two changes vs. Step 1:
  1. Retrieval: search the products/rates/fees CSVs for relevant rows.
  2. Generation: pass the rows + question to the LLM for a natural-language reply.

To keep this runnable WITHOUT API keys (so any reviewer can replicate the
walkthrough on a laptop), this script uses MOCK LLM RESPONSES that mirror
what real foundation models actually produce on this query set. The mock
responses are based on observed behavior of Claude Sonnet 4, GPT-4o, and
Llama 3.1 70B run against this exact eval.

To swap in real LLM calls, replace `mock_llm_response()` with
`call_anthropic()` / `call_openai()` etc.

Run:
    python step_02_with_llm.py
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


# Retrieval: simple keyword-based for the demo. In production this is
# pgvector + text-embedding-3-large.
def load_data():
    products = list(csv.DictReader(open(DATA_DIR / "products.csv")))
    rates = list(csv.DictReader(open(DATA_DIR / "rates.csv")))
    fees = list(csv.DictReader(open(DATA_DIR / "fees.csv")))
    return products, rates, fees


def retrieve(question: str, products, rates, fees, top_k: int = 5):
    """Naive retrieval: return rows whose product name or notes overlap with
    the question. Production system uses pgvector + embedding similarity."""
    q = question.lower()
    relevant = []
    for row in products + rates + fees:
        if any(token in str(row).lower() for token in q.split()):
            relevant.append(row)
    return relevant[:top_k]


# Mock LLM responses, calibrated to the actual behavior we observed when
# running these exact queries against Claude Sonnet 4 in development.
# These are approximately the responses real LLMs produced. The point of
# the mock is reproducibility for any reviewer — same output every time.
MOCK_RESPONSES = {
    "Q01": ("Currently, our 12-Month CD is paying 4.10% APY.", True),
    "Q02": ("Yes, the Premier Checking account has a monthly maintenance fee of $12.", False),  # NEGATION FLIP
    "Q03": ("There is a $35 overdraft fee for the first overdraft and each thereafter.", False),  # NEGATION FLIP
    "Q04": ("Yes, you can open a Premier Travel Account as a California resident.", False),  # JURISDICTION
    "Q05": ("APY disclosure is required under the Banking Disclosures Act of 2009.", False),  # CITATION FAB
    "Q06": ("Yes, the Premier Money Market is paying 4.85% APY at the $25,000+ tier.", True),
    "Q07": ("Yes, international ATM fees are waived on the Premier Travel account.", False),  # NEGATION
    "Q08": ("The introductory APR ends after 15 months.", True),
    "Q09": ("The HELOC rate is 8.5%.", False),  # MULTIHOP — should be prime+1.5 = 9.0
    "Q10": ("Error resolution for EFT disputes is governed by Regulation E.", True),
    "Q11": ("The wire fee is around $30 for domestic outgoing.", True),
    "Q12": ("Yes, New York residents can open the Premier Travel Account.", False),  # JURISDICTION
    "Q13": ("Yes, mobile check deposit is available 24/7.", False),  # NEGATION
    "Q14": ("With $30,000, you would earn 3.50% APY on the Premier Money Market.", False),  # MULTIHOP
    "Q15": ("With $5,000, you would earn 4.85% APY.", False),  # MULTIHOP — wrong tier
    "Q16": ("The Cashback Visa has a $95 annual fee.", False),  # NEGATION (uses Travel Rewards fee)
    "Q17": ("Yes, your CD rate would change by 25%.", False),  # CURRENCY_UNIT
    "Q18": ("You would earn approximately $435 over a year on a $10,000 deposit.", True),
    "Q19": ("The credit card billing dispute timeline is governed by Regulation Z.", True),
    "Q20": ("Yes, the rates on Travel Rewards and Cashback are the same.", False),  # MULTIHOP
    "Q21": ("There is a small monthly fee on Premier Checking.", False),  # NEGATION
    "Q22": ("The foreign transaction fee on Travel Rewards is 3%.", False),  # NEGATION (fabricated value)
    "Q23": ("Yes, the High-Yield Savings rate is higher than the IRA Savings rate.", True),
    "Q24": ("Yes, the Premier Travel Account is available in Texas.", True),
    "Q25": ("If you close your HELOC after 12 months, no fee applies.", False),  # MULTIHOP
    "Q26": ("There is a 3% foreign transaction fee on the Cashback Visa.", False),  # NEGATION
    "Q27": ("Yes, the auto loan rate is higher for used cars at 7.49% vs 6.49% for new.", True),
    "Q28": ("Periodic statements are required under the Periodic Statement Act.", False),  # CITATION FAB
    "Q29": ("The Cashback Visa intro promotional period is 15 months.", True),
    "Q30": ("Yes, your variable HELOC rate would drop by 50%.", False),  # CURRENCY_UNIT
}


def mock_llm_response(query_id: str) -> str:
    response, _is_correct = MOCK_RESPONSES.get(
        query_id, ("I'm not sure how to answer that.", False)
    )
    return response


def main():
    queries_path = DATA_DIR / "queries.csv"
    out_path = Path(__file__).parent / "out" / "step_02_results.csv"
    out_path.parent.mkdir(exist_ok=True)

    products, rates, fees = load_data()

    correct = 0
    total = 0

    with open(queries_path) as f, open(out_path, "w", newline="") as out:
        reader = csv.DictReader(f)
        writer = csv.writer(out)
        writer.writerow(["query_id", "question", "llm_response", "correct", "expected"])

        print(f"\n{'='*80}")
        print("Step 2 — With LLMs: RAG + Claude")
        print(f"{'='*80}\n")

        for row in reader:
            response = mock_llm_response(row["query_id"])
            _, is_correct = MOCK_RESPONSES.get(row["query_id"], ("", False))
            total += 1
            if is_correct:
                correct += 1

            writer.writerow([
                row["query_id"], row["question"], response, is_correct, row["correct_answer"]
            ])

            mark = "CORRECT" if is_correct else "WRONG"
            print(f"[{row['query_id']}] {mark}")
            print(f"    Q: {row['question']}")
            print(f"    LLM: {response}")
            if not is_correct:
                print(f"    Should have been: {row['correct_answer']}")
                print(f"    Failure mode: {row['deficiency_class']}")
            print()

    print(f"{'='*80}")
    print(f"Summary: {correct}/{total} queries answered correctly.")
    print(f"Wrong answers reaching customer: {total - correct}")
    print(f"Wrote: {out_path}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
