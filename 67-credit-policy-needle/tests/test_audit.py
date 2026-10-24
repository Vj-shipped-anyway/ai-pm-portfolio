import unittest

import _bootstrap  # noqa: F401
import credit_policy_needle as cpn

BASE = "1.1 The maximum loan term for Alder Personal Loan is 60 months."
FILLER = "1.2 The file reviewer checks the file for missing pages."


def audit(*clauses):
    return cpn.audit_text("\n\n".join(clauses))


def relations(res):
    return {f["id"]: f["relation"] for f in res["flagged"]}


class AuditTests(unittest.TestCase):
    def test_inline_exception_is_listed_inside_the_rule(self):
        res = audit("1.1 The maximum loan term for Alder Personal Loan is 60 months, except that it is 72 months for an "
                    "applicant with a customer relationship of at least 24 months.", FILLER)
        self.assertEqual(relations(res), {"1.1": "inside"})

    def test_adjacent_exception_names_its_rule(self):
        res = audit(BASE, "1.2 Exception to clause 1.1: the maximum loan term for Alder Personal Loan is 72 months for an "
                    "applicant with a customer relationship of at least 24 months.")
        self.assertEqual(relations(res), {"1.2": "named"})

    def test_far_exception_that_cites_only_the_number_is_not_named(self):
        res = audit(BASE, FILLER, "2.1 Notwithstanding clause 1.1, the limit stated there is 72 months for an applicant "
                    "with a customer relationship of at least 24 months.")
        self.assertEqual(relations(res), {"2.1": "unnamed"})
        self.assertGreater(res["flagged"][0]["distance"], 0)

    def test_register_entry_and_carve_out_are_listed(self):
        res = audit(BASE, "1.2 Exception to clause 1.1: the maximum loan term for Alder Personal Loan is 72 months for an "
                    "applicant with a customer relationship of at least 24 months.",
                    "1.3 Clause 1.2 does not apply to an applicant with a payment default recorded in the prior 12 months.",
                    "R-1 Register entry (effective 2026-01-05): clause 1.1 is 72 months for an applicant with a customer "
                    "relationship of at least 24 months.")
        self.assertEqual(relations(res), {"1.2": "named", "1.3": "unnamed", "R-1": "unnamed"})

    def test_citation_of_a_clause_that_does_not_exist_is_reported(self):
        res = audit(BASE, "1.2 Notwithstanding clause 9.9, the limit stated there is 72 months.")
        self.assertEqual(relations(res), {"1.2": "missing"})

    def test_prohibition_and_generic_except_are_left_alone(self):
        res = audit(BASE, "1.2 No exception to clause 1.1 is permitted without the written approval of the credit committee.",
                    "1.3 Except for the cover sheet, each sheet of the file shows the case number in the margin.")
        self.assertEqual(res["flagged"], [])

    def test_known_miss_restated_limit_has_no_cue_word(self):
        res = audit(BASE, "1.2 For an applicant with a customer relationship of at least 24 months, the limit in clause 1.1 is 72 months.")
        self.assertEqual(res["flagged"], [])

    def test_known_false_alarm_pointer_that_says_except(self):
        res = audit(BASE, "1.2 Reviewers cite clause 1.1 in the case log, except for files closed with no decision.")
        self.assertEqual(list(relations(res)), ["1.2"])

    def test_clause_numbers_are_matched_whole(self):
        res = audit("1.1 The maximum loan term for Alder Personal Loan is 60 months.",
                    "1.2 Notwithstanding clause 1.10, the limit stated there is 72 months.")
        self.assertEqual(relations(res), {"1.2": "missing"})

    def test_empty_manual_is_an_error(self):
        for text in ("", "   \n\n  "):
            with self.assertRaises(cpn.InputError):
                cpn.audit_text(text)

    def test_nothing_found_says_so(self):
        lines = cpn.render_audit("m.txt", audit(BASE, FILLER))
        self.assertIn("none found", "\n".join(lines))

    def test_hostile_text_cannot_forge_a_log_line(self):
        res = audit(BASE, "1.2 Notwithstanding clause 1.1, the limit is 5%.\r::error::forged\r%0A done")
        text_lines = cpn.render_audit("m.txt", res)
        self.assertFalse(any(ln.startswith("::") for ln in text_lines))
        self.assertFalse(any("\r" in ln or "\n" in ln for ln in text_lines))
        gh = cpn.render_audit("m.txt", res, "github")
        self.assertTrue(all(ln.startswith(("::warning ", "::notice ")) for ln in gh))
        self.assertTrue(any("%0D::error::forged%0D%250A" in ln for ln in gh))


if __name__ == "__main__":
    unittest.main()
