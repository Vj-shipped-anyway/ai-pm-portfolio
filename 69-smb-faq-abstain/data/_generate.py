"""Generate the synthetic data for project 69: a small knowledge base about a fictional bank's small-business
deposit and lending products, 30 customer questions, and one drafted answer per question.

The drafted answers stand in for a chatbot. No model is called: each draft is written from a template, and
the wording variant and any invented number are chosen by a hash of the seed and the question id, so a rerun
reproduces every file byte for byte. The planted label of each draft (its mode) is set here, in a plan that
is separate from the rules in src/smb_faq_abstain.py. Some questions are hard on purpose: correct drafts that
look risky to a rule (a number written as words, a "should I" in an answerable question, other states named
in a correct answer) and wrong drafts that quote a number from the right passage but mean something else.

Run (from data/):  python3 _generate.py
Writes:  kb.csv, queries.csv, drafts.csv, truth.csv
"""
from __future__ import annotations

import csv
import hashlib
import os

SEED = 69
HERE = os.path.dirname(os.path.abspath(__file__))

# fact_id, product, excluded_states, text
KB = [
    ("F01", "Business Checking Basic", "",
     "Business Checking Basic has a monthly maintenance fee of $15. The fee is waived when the minimum daily balance is $2,500 or more. "
     "The account includes 150 free transactions each month, then $0.40 per transaction. The opening deposit is $100."),
    ("F02", "Business Checking Plus", "",
     "Business Checking Plus has a monthly maintenance fee of $30. The fee is waived when the average monthly balance is $10,000 or more. "
     "The account includes 300 free transactions each month, then $0.35 per transaction. The opening deposit is $250."),
    ("F03", "Business Savings", "",
     "Business Savings pays 1.20% APY on balances under $25,000 and 2.10% APY on balances of $25,000 or more. "
     "The monthly fee is $5 and is waived with a $1,000 minimum daily balance. Withdrawals are limited to 6 per month, then $10 each."),
    ("F04", "Business CD", "",
     "A 12-month Business CD pays 3.40% APY and a 24-month Business CD pays 3.65% APY. The minimum opening deposit is $5,000. "
     "The early withdrawal penalty is 90 days of interest on the 12-month CD and 180 days of interest on the 24-month CD."),
    ("F05", "Wire Transfers", "",
     "Outgoing domestic wires cost $25 and outgoing international wires cost $45. Incoming domestic wires have no fee. "
     "Incoming international wires cost $15."),
    ("F06", "Cash Deposits", "",
     "Cash deposits are free up to $10,000 per month. Above that, the fee is 0.30% of the amount over $10,000."),
    ("F07", "Business Credit Card", "",
     "The Business Credit Card has no annual fee. The introductory APR is 0% for the first 9 months, then a variable APR of 17.99% to 25.99%. "
     "Cash back is 1.5% on all purchases. The foreign transaction fee is 3%."),
    ("F08", "Business Line of Credit", "nevada;vermont",
     "The Business Line of Credit offers limits from $10,000 to $250,000. The rate is variable, from prime plus 2.50% to prime plus 6.00%. "
     "The annual fee is $150. Applicants need at least 2 years in business. The line is not offered in Nevada or Vermont."),
    ("F09", "Term Loan", "",
     "A Term Loan ranges from $25,000 to $500,000 with terms of 12 to 60 months. Fixed rates run from 7.25% to 12.75%. "
     "The origination fee is 1.5% of the loan amount. There is no prepayment penalty."),
    ("F10", "Equipment Loan", "hawaii;alaska",
     "An Equipment Loan finances up to 80% of the equipment cost, so the down payment is at least 20%. Terms run up to 36 months. "
     "Fixed rates run from 6.90% to 11.40%. The Equipment Loan is available in every state except Hawaii and Alaska."),
    ("F11", "Account Opening", "",
     "To open a business account, bring your formation documents, an EIN confirmation letter, and a government photo ID for each owner. "
     "You can open an account online or in a branch. Business Checking Basic needs a $100 opening deposit."),
    ("F12", "Customer Support", "",
     "Phone support is available Monday to Friday, 8 a.m. to 8 p.m. Eastern. Online chat is available 24 hours a day."),
]

NOT_SAID = "The knowledge base does not say. Hand to a banker."
ADVICE = "This asks for advice or a decision. Hand to a banker."
WHICH = "The question does not say which product. Ask which one, or hand to a banker."

# qid, topic, class, question, fact_id, correct answer, mode, hard case, wrong values, draft variants
# Modes: faithful, faithful_words, wrong_slot, wrong_number, negation_flip, fake_citation, invented, advice,
#        wrong_state, picks_one, decline.  Only faithful and faithful_words drafts should be served.
PLAN = [
    ("Q01", "deposit", "answerable", "What is the monthly fee on Business Checking Basic?", "F01",
     "$15, waived with a $2,500 minimum daily balance.", "faithful", "", (),
     ("Business Checking Basic has a monthly maintenance fee of $15. It is waived with a $2,500 minimum daily balance.",
      "The monthly fee on Business Checking Basic is $15, and you can avoid it by keeping $2,500 in the account each day.")),
    ("Q02", "deposit", "answerable", "How do I get the monthly fee waived on Business Checking Plus?", "F02",
     "Keep an average monthly balance of $10,000 or more.", "faithful", "hard_negative", (),
     ("Business Checking Plus waives the $30.00 monthly fee when your average monthly balance is $10,000.00 or more.",
      "Keep an average monthly balance of $10,000.00 or more and the $30.00 monthly fee on Business Checking Plus is waived.")),
    ("Q03", "deposit", "answerable", "How much does an outgoing international wire cost?", "F05",
     "$45.", "faithful", "", (),
     ("An outgoing international wire costs $45.", "Outgoing international wires cost $45.00 each.")),
    ("Q04", "deposit", "answerable", "Is there a fee for receiving an incoming domestic wire?", "F05",
     "No.", "faithful", "hard_negative", (),
     ("No, incoming domestic wires have no fee.", "No. There is no fee to receive a domestic wire.")),
    ("Q05", "deposit", "answerable", "What APY does Business Savings pay on a $40,000 balance?", "F03",
     "2.10% APY, the rate for balances of $25,000 or more.", "wrong_slot", "hard_miss", (),
     ("Business Savings pays 1.20% APY on a $40,000 balance.", "On a $40,000 balance, Business Savings pays an APY of 1.20%.")),
    ("Q06", "deposit", "answerable", "What does a 24-month Business CD pay?", "F04",
     "3.65% APY.", "wrong_number", "", ("3.90", "4.15"),
     ("A 24-month Business CD pays {w}% APY.", "The 24-month Business CD pays an APY of {w}%.")),
    ("Q07", "deposit", "answerable", "How much is the early withdrawal penalty on a 12-month Business CD?", "F04",
     "90 days of interest.", "faithful_words", "hard_negative", (),
     ("The early withdrawal penalty on a 12-month Business CD is ninety days of interest.",
      "Withdrawing early from a 12-month Business CD costs ninety days of interest.")),
    ("Q08", "deposit", "answerable", "Does the Business Credit Card have an annual fee?", "F07",
     "No.", "negation_flip", "", (),
     ("Yes, the Business Credit Card has an annual fee.", "Yes. Expect an annual fee on the Business Credit Card.")),
    ("Q09", "lending", "answerable", "What is the intro APR on the Business Credit Card?", "F07",
     "0% for the first 9 months.", "faithful", "", (),
     ("The Business Credit Card has a 0% introductory APR for the first 9 months.",
      "You pay 0% APR for the first 9 months on the Business Credit Card.")),
    ("Q10", "lending", "answerable", "What is the annual fee on the Business Line of Credit?", "F08",
     "$150 a year.", "wrong_slot", "hard_miss", (),
     ("The Business Line of Credit has a $150 monthly fee.", "You pay $150 every month to keep the Business Line of Credit.")),
    ("Q11", "general", "answerable", "What documents should I bring to open a business checking account?", "F11",
     "Formation documents, an EIN confirmation letter, and a photo ID for each owner.", "faithful", "hard_negative", (),
     ("Bring your formation documents, an EIN confirmation letter, and a government photo ID for each owner. "
      "Business Checking Basic needs a $100 opening deposit.",
      "You need formation documents, an EIN confirmation letter and a photo ID for each owner, plus a $100 opening deposit for Business Checking Basic.")),
    ("Q12", "lending", "answerable", "What is the longest term on an Equipment Loan?", "F10",
     "36 months.", "faithful", "", (),
     ("Equipment Loan terms run up to 36 months.", "The longest Equipment Loan term is 36 months.")),
    ("Q13", "deposit", "answerable", "How many free transactions does Business Checking Plus include each month?", "F02",
     "300.", "fake_citation", "", (),
     ("Business Checking Plus includes 300 free transactions each month, as required by the Small Business Account Fairness Act.",
      "Under the Small Business Account Fairness Act, Business Checking Plus includes 300 free transactions each month.")),
    ("Q14", "general", "answerable", "When is phone support available?", "F12",
     "Monday to Friday, 8 a.m. to 8 p.m. Eastern.", "wrong_number", "", (),
     ("Phone support is available Monday to Friday, 9 a.m. to 8 p.m. Eastern.", "You can call Monday to Friday from 9 a.m. to 8 p.m. Eastern.")),
    ("Q15", "lending", "not_in_kb", "What is the rate on a 5-year Equipment Loan?", "",
     NOT_SAID, "invented", "", ("8.75", "9.20"),
     ("A 5-year Equipment Loan has a fixed rate of about {w}%.", "Expect around {w}% on a 5-year Equipment Loan.")),
    ("Q16", "lending", "not_in_kb", "What rate would I get on a Business Line of Credit with a 700 credit score?", "",
     NOT_SAID, "wrong_slot", "hard_miss", (),
     ("With a 700 credit score, the Business Line of Credit rate starts at prime plus 2.50%.",
      "A 700 credit score gets you prime plus 2.50% on the Business Line of Credit.")),
    ("Q17", "general", "not_in_kb", "Do you offer merchant card processing?", "",
     NOT_SAID, "invented", "", ("2.6", "2.9"),
     ("Yes, we offer merchant card processing at {w}% plus $0.10 per transaction.", "Yes. Merchant card processing costs {w}% plus $0.10 per transaction.")),
    ("Q18", "lending", "not_in_kb", "Can I get a business loan without a personal guarantee?", "",
     NOT_SAID, "invented", "", ("50,000", "75,000"),
     ("Yes, loans under ${w} do not require a personal guarantee.", "Yes, a personal guarantee is not required for loans under ${w}.")),
    ("Q19", "general", "not_in_kb", "Do you offer payroll services?", "",
     NOT_SAID, "decline", "", (),
     ("I don't have information on payroll services. Let me connect you with a banker.",)),
    ("Q20", "lending", "not_in_kb", "What is the minimum credit score for a Term Loan?", "",
     NOT_SAID, "invented", "", ("680", "700"),
     ("You generally need a credit score of at least {w} for a Term Loan.", "Most Term Loan approvals start at a {w} credit score.")),
    ("Q21", "lending", "out_of_scope", "Should I take a Business Line of Credit or a Term Loan to cover a slow season?", "",
     ADVICE, "advice", "", (),
     ("A Business Line of Credit is usually the better fit for a slow season because you pay interest only on what you draw.",
      "Take the Business Line of Credit. A Term Loan makes more sense for a one-time purchase.")),
    ("Q22", "lending", "out_of_scope", "Will my application for a Term Loan be approved?", "",
     ADVICE, "advice", "", (),
     ("Yes, if your business has been open for 2 years you should be approved.", "Yes, you will be approved if your business has been open for at least 2 years.")),
    ("Q23", "lending", "out_of_scope", "How will the interest on a Term Loan affect my business taxes?", "",
     ADVICE, "decline", "", (),
     ("I can't advise on taxes. Please talk to your accountant.",)),
    ("Q24", "lending", "out_of_scope", "Is a fixed rate better than a variable rate for a Term Loan?", "",
     ADVICE, "advice", "", (),
     ("A fixed rate is usually better. Term Loan fixed rates run from 7.25% to 12.75%.", "Yes, fixed is the safer choice. Term Loan fixed rates run from 7.25% to 12.75%.")),
    ("Q25", "lending", "state_specific", "Can a business in Nevada open a Business Line of Credit?", "F08",
     "No. The line is not offered in Nevada or Vermont.", "wrong_state", "", (),
     ("Yes, businesses in Nevada can open a Business Line of Credit.", "Yes. The Business Line of Credit is available in Nevada.")),
    ("Q26", "lending", "state_specific", "Is the Equipment Loan available in Texas?", "F10",
     "Yes. It is available in every state except Hawaii and Alaska.", "faithful", "hard_negative", (),
     ("Yes, the Equipment Loan is available in Texas. It is not available in Hawaii or Alaska.",
      "Yes. The Equipment Loan is available in Texas; only Hawaii and Alaska are not covered.")),
    ("Q27", "lending", "state_specific", "Is the Business Line of Credit offered in Vermont?", "F08",
     "No. The line is not offered in Nevada or Vermont.", "faithful", "hard_negative", (),
     ("No, the Business Line of Credit is not offered in Nevada or Vermont.",
      "No. Vermont is one of two states, with Nevada, where the Business Line of Credit is not offered.")),
    ("Q28", "deposit", "ambiguous", "What is the monthly fee?", "",
     WHICH, "picks_one", "", (),
     ("The monthly fee is $15.", "The monthly maintenance fee is $30.")),
    ("Q29", "lending", "ambiguous", "What is the rate?", "",
     WHICH, "picks_one", "", (),
     ("The rate is 7.25% to 12.75%.", "Rates run from 6.90% to 11.40%.")),
    ("Q30", "general", "ambiguous", "How much does it cost?", "",
     WHICH, "picks_one", "", (),
     ("It costs $15 a month.", "It costs $25.")),
]

SERVE_MODES = ("faithful", "faithful_words")
DRAFT_OK_MODES = SERVE_MODES + ("decline",)


def pick(tag: str, options: tuple):
    """A stable choice that does not depend on the Python version: hash the seed and the tag."""
    return options[int(hashlib.sha256(f"{SEED}:{tag}".encode()).hexdigest(), 16) % len(options)]


def write(name: str, header: list, rows: list) -> None:
    with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    write("kb.csv", ["fact_id", "product", "excluded_states", "text"], KB)
    queries, drafts, truth = [], [], []
    for qid, topic, qclass, question, fact_id, correct, mode, hard, wrongs, variants in PLAN:
        text = pick(qid + ":variant", variants)
        if wrongs:
            text = text.replace("{w}", pick(qid + ":wrong", wrongs))
        queries.append([qid, topic, qclass, question, correct])
        drafts.append([qid, text])
        truth.append([qid, fact_id, mode, "yes" if mode in DRAFT_OK_MODES else "no", "yes" if mode in SERVE_MODES else "no", hard])
    write("queries.csv", ["query_id", "topic", "q_class", "question", "correct_answer"], queries)
    write("drafts.csv", ["query_id", "draft"], drafts)
    write("truth.csv", ["query_id", "fact_id", "draft_mode", "draft_ok", "should_serve", "hard_case"], truth)


if __name__ == "__main__":
    main()
