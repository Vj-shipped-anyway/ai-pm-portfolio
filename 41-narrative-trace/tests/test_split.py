import time
import unittest

import _bootstrap  # noqa: F401
from narrative_trace import split_sentences


def texts(s):
    return [x["text"] for x in split_sentences(s)]


class SplitTests(unittest.TestCase):
    def test_two_sentences(self):
        self.assertEqual(texts("Paid $9,800.00 on March 3, 2026 [txn: T-1]. Next one [txn: T-2]."),
                         ["Paid $9,800.00 on March 3, 2026 [txn: T-1].", "Next one [txn: T-2]."])

    def test_period_after_company_suffix_does_not_split(self):
        self.assertEqual(len(texts("Sent a wire to Quillon Freight Inc. [txn: T-1]. Paid Tessel Trading Ltd. on time [txn: T-2].")), 2)

    def test_known_limit_a_sentence_that_ends_on_a_suffix_runs_into_the_next(self):
        self.assertEqual(len(texts("The wire went to Quillon Freight Inc. Then Tessel Trading Ltd. was paid.")), 1)

    def test_initial_and_abbreviations_do_not_split(self):
        self.assertEqual(len(texts("Payee J. Okafor was named. See e.g. the wire. Also No. 5 was paid.")), 3)

    def test_decimals_and_k_figures_do_not_split(self):
        self.assertEqual(len(texts("Paid $9.8k and 1.5 times that [txn: T-1].")), 1)

    def test_citation_after_the_period_stays_with_its_sentence(self):
        got = texts("Paid it on 2026-03-03. [txn: T-1] Then more [txn: T-2].")
        self.assertEqual(got, ["Paid it on 2026-03-03. [txn: T-1]", "Then more [txn: T-2]."])

    def test_blank_line_ends_a_sentence_without_a_period(self):
        self.assertEqual(texts("First part with no stop\n\nSecond part."), ["First part with no stop", "Second part."])

    def test_last_sentence_without_a_terminator_is_kept(self):
        self.assertEqual(texts("One. Two without a stop"), ["One.", "Two without a stop"])

    def test_question_and_exclamation_split(self):
        self.assertEqual(len(texts("Why was it sent? It was sent twice! Then it stopped.")), 3)

    def test_lowercase_after_a_period_does_not_split(self):
        self.assertEqual(len(texts("About approx. nine deposits were made.")), 1)

    def test_offsets_point_at_the_text(self):
        source = "  First [txn: T-1].\n\n  Second one. [txn: T-2]  Third."
        for s in split_sentences(source):
            self.assertEqual(source[s["start"]:s["end"]], s["text"])

    def test_empty_and_punctuation_only_give_nothing(self):
        self.assertEqual(split_sentences(""), [])
        self.assertEqual(split_sentences("  \n\n  "), [])
        self.assertEqual(split_sentences("... ?! ."), [])

    def test_many_abbreviations_in_a_row_stay_fast(self):
        start = time.time()
        split_sentences("A. " * 60000)
        self.assertLess(time.time() - start, 5)


if __name__ == "__main__":
    unittest.main()
