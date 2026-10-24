import os
import unittest

import _bootstrap  # noqa: F401
import smb_faq_abstain as g

KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "kb.csv")
KB = g.load_kb(KB_PATH)


def run(question, draft, **kw):
    return g.evaluate(question, draft, KB, **kw)


class NumberTests(unittest.TestCase):
    def test_formatting_variants_match(self):
        self.assertEqual(g.numbers_in("$2,500.00 and 1.20% and 0.40"), frozenset({"2500", "1.2", "0.4"}))

    def test_money_with_cents_is_supported(self):
        r = run("How much does an outgoing international wire cost?", "Outgoing international wires cost $45.00 each.")
        self.assertEqual(r["decision"], "SERVE")

    def test_invented_number_is_held(self):
        r = run("What does a 24-month Business CD pay?", "A 24-month Business CD pays 3.90% APY.")
        self.assertEqual((r["decision"], r["reason"]), ("ABSTAIN", "ungrounded"))
        self.assertIn("number 3.9", r["detail"])

    def test_number_echoed_from_the_question_is_not_a_claim(self):
        r = run("What APY does Business Savings pay on a $40,000 balance?", "Business Savings pays 2.10% APY on a $40,000 balance.")
        self.assertEqual((r["decision"], r["supported"], r["total"]), ("SERVE", 1, 1))


class GateTests(unittest.TestCase):
    def test_citation_not_in_source_is_held(self):
        r = run("How many free transactions does Business Checking Plus include each month?",
                "Business Checking Plus includes 300 free transactions each month, as required by the Small Business Account Fairness Act.")
        self.assertEqual((r["decision"], r["supported"], r["total"]), ("ABSTAIN", 1, 2))

    def test_yes_when_the_source_says_no_is_held(self):
        r = run("Does the Business Credit Card have an annual fee?", "Yes, the Business Credit Card has an annual fee.")
        self.assertEqual(r["reason"], "ungrounded")
        self.assertIn("yes or no", r["detail"])

    def test_negation_in_a_correct_answer_passes(self):
        r = run("Is there a fee for receiving an incoming domestic wire?", "No, incoming domestic wires have no fee.")
        self.assertEqual(r["decision"], "SERVE")

    def test_excluded_state_needs_a_negative_answer(self):
        held = run("Can a business in Nevada open a Business Line of Credit?", "Yes, businesses in Nevada can open a Business Line of Credit.")
        ok = run("Is the Business Line of Credit offered in Vermont?", "No, the Business Line of Credit is not offered in Nevada or Vermont.")
        self.assertEqual(held["decision"], "ABSTAIN")
        self.assertEqual(ok["decision"], "SERVE")

    def test_state_names_in_the_draft_do_not_count_as_the_questions_state(self):
        # the question names Texas; Hawaii and Alaska appear only in the draft, so there is no state claim
        r = run("Is the Equipment Loan available in Texas?", "Yes, the Equipment Loan is available in Texas. It is available in every state except Hawaii and Alaska.")
        self.assertEqual((r["decision"], r["total"]), ("SERVE", 1))

    def test_ambiguous_question_is_held_even_with_a_grounded_draft(self):
        r = run("What is the monthly fee?", "The monthly fee is $15.")
        self.assertEqual(r["reason"], "ambiguous")

    def test_question_with_no_source_is_held(self):
        r = run("Do you offer payroll services?", "Yes, payroll services are included.")
        self.assertEqual(r["reason"], "no_source")

    def test_unrelated_words_only_is_held_not_crashed(self):
        r = run("zzz qqq", "Yes.")
        self.assertEqual(r["reason"], "no_source")

    def test_advice_question_is_out_of_scope(self):
        r = run("Will my application for a Term Loan be approved?", "Yes, you will be approved.")
        self.assertEqual(r["reason"], "out_of_scope")

    def test_answerable_question_with_a_scope_cue_is_held_by_mistake(self):
        # a hard negative the cue list cannot tell apart: documented as a false alarm
        r = run("What documents should I bring to open a business checking account?", "Bring formation documents and $100.")
        self.assertEqual(r["reason"], "out_of_scope")

    def test_draft_that_declines_is_a_handoff(self):
        r = run("What is the monthly fee on Business Checking Basic?", "I don't have that. Let me connect you with a banker.")
        self.assertEqual(r["reason"], "handoff")

    def test_draft_with_nothing_to_check_is_unverifiable(self):
        r = run("How much is the early withdrawal penalty on a 12-month Business CD?", "It costs ninety days of interest.")
        self.assertEqual(r["reason"], "unverifiable")

    def test_known_limit_number_in_the_right_passage_with_the_wrong_meaning_passes(self):
        r = run("What is the annual fee on the Business Line of Credit?", "The Business Line of Credit has a $150 monthly fee.")
        self.assertEqual(r["decision"], "SERVE")


class ThresholdAndGatesTests(unittest.TestCase):
    Q = "How many free transactions does Business Checking Plus include each month?"
    D = "Business Checking Plus includes 300 free transactions each month, as required by the Small Business Account Fairness Act."

    def test_half_supported_passes_a_loose_threshold_only(self):
        self.assertEqual(run(self.Q, self.D, min_grounded=1.0)["decision"], "ABSTAIN")
        self.assertEqual(run(self.Q, self.D, min_grounded=0.5)["decision"], "SERVE")

    def test_no_gates_serves_every_draft_that_does_not_decline(self):
        self.assertEqual(run(self.Q, self.D, gates=frozenset())["decision"], "SERVE")
        self.assertEqual(run(self.Q, "Let me connect you with a banker.", gates=frozenset())["decision"], "ABSTAIN")

    def test_gates_are_parameters_not_globals(self):
        before = g.ALL_GATES
        run(self.Q, self.D, gates=frozenset({"source"}))
        self.assertIs(g.ALL_GATES, before)
        self.assertEqual(g.ALL_GATES, frozenset({"scope", "source", "ambiguity", "grounding"}))

    def test_retrieval_is_deterministic_and_sorted(self):
        a = [(round(s, 6), f.fact_id) for s, f in g.retrieve("What is the rate?", KB)]
        b = [(round(s, 6), f.fact_id) for s, f in g.retrieve("What is the rate?", KB)]
        self.assertEqual(a, b)
        self.assertEqual(a, sorted(a, key=lambda x: (-x[0], x[1])))


class HelperTests(unittest.TestCase):
    def test_clean_escapes_line_breaks_and_controls(self):
        s = g.clean("a\n::error::forged\r\x1b[31m")
        self.assertNotIn("\n", s)
        self.assertNotIn("\r", s)
        self.assertNotIn("\x1b", s)
        self.assertTrue(s.startswith("a\\n::error::"))

    def test_clean_caps_length(self):
        self.assertEqual(len(g.clean("x" * 1000, 50)), 53)

    def test_states_are_read_as_whole_names(self):
        self.assertEqual(g.states_in("Is it offered in New York or Nevada, or in Indiana?"), frozenset({"new-york", "nevada", "indiana"}))
        self.assertEqual(g.states_in("Is it ok to ship?"), frozenset())


if __name__ == "__main__":
    unittest.main()
