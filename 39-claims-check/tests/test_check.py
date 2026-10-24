import unittest

import _bootstrap  # noqa: F401
from claims_check import check_claims, extract_claims, index_evidence

G = "\U0001F7E2"


def verdict(readme, evidence, **kw):
    results = check_claims(extract_claims(readme), index_evidence([evidence]), **kw)
    return [(r["text"], r["status"]) for r in results]


class CheckTests(unittest.TestCase):
    def test_a_piece_of_a_longer_number_is_not_support(self):
        self.assertEqual(verdict(f"- {G} 12 cases", "cases: 112\n"), [("12", "unsupported")])
        self.assertEqual(verdict(f"- {G} 40 percent", "rate: 40.3%\n"), [("40", "unsupported")])
        self.assertEqual(verdict(f"- {G} 4.2 days", "days: 14.25\n"), [("4.2", "unsupported")])

    def test_unsupported_reason_names_the_longer_figure(self):
        r = check_claims(extract_claims(f"- {G} 58 cases"), index_evidence(["cases: 158\n"]))[0]
        self.assertIn("158", r["why"])

    def test_commas_and_trailing_zeros_do_not_matter(self):
        self.assertEqual(verdict(f"- {G} 1,240 rows", "rows: 1240\n"), [("1,240", "supported")])
        self.assertEqual(verdict(f"- {G} 1240 rows", "rows: 1,240\n"), [("1240", "supported")])
        self.assertEqual(verdict(f"- {G} 25 rows", "rows: 25.0\n"), [("25", "supported")])
        self.assertEqual(verdict(f"- {G} 40.3%", "rate: 40.30%\n"), [("40.3", "supported")])

    def test_pair_must_be_printed_together(self):
        evidence = "passed: 24 of 30\ntotal: 25 of 25\n"
        self.assertEqual(verdict(f"- {G} 24 of 30", evidence), [("24 of 30", "supported")])
        self.assertEqual(verdict(f"- {G} 24 of 25", evidence), [("24 of 25", "unsupported")])
        self.assertEqual(verdict(f"- {G} 24 of 25", "ok: 24/25\n"), [("24 of 25", "supported")])

    def test_pair_split_over_two_lines_is_flagged_and_says_why(self):
        r = check_claims(extract_claims(f"- {G} 24 of 25"), index_evidence(["passed: 24\ntotal: 25\n"]))[0]
        self.assertEqual(r["status"], "unsupported")
        self.assertIn("never as", r["why"])

    def test_pair_with_a_missing_number_names_that_number(self):
        r = check_claims(extract_claims(f"- {G} 24 of 99"), index_evidence(["passed: 24 of 30\n"]))[0]
        self.assertIn("99 is not printed", r["why"])

    def test_no_pairs_checks_both_numbers_separately(self):
        self.assertEqual(verdict(f"- {G} 24 of 25", "passed: 24\ntotal: 25\n", pairs=False), [("24 of 25", "supported")])
        self.assertEqual(verdict(f"- {G} 24 of 99", "passed: 24\n", pairs=False), [("24 of 99", "unsupported")])

    def test_one_digit_numbers_are_skipped_not_passed(self):
        self.assertEqual(verdict(f"- {G} 7 tools", "nothing here: 12\n"), [("7", "skipped")])
        self.assertEqual(verdict(f"- {G} 7 tools", "nothing here: 12\n", min_digits=1), [("7", "unsupported")])
        self.assertEqual(verdict(f"- {G} 3 of 5", "x: 12\n"), [("3 of 5", "skipped")])

    def test_evidence_that_prints_no_numbers_flags_every_claim(self):
        self.assertEqual(verdict(f"- {G} 12 cases", "no numbers at all\n"), [("12", "unsupported")])

    def test_pair_must_sit_on_one_line(self):
        self.assertEqual(verdict(f"- {G} 24 of 25", "24 of\n25\n"), [("24 of 25", "unsupported")])

    def test_dates_in_the_output_count_as_printed_numbers(self):
        # a limit worth knowing: the day in a printed date supports a claim of the same number
        self.assertEqual(verdict(f"- {G} 18 cases", "run on 2026-10-18\n"), [("18", "supported")])


if __name__ == "__main__":
    unittest.main()
