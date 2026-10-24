import unittest

import _bootstrap  # noqa: F401
from _ledgers import Workspace, a_line, b_line
import recon_agent as ra


class Base(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.addCleanup(self.ws.close)

    def run_rows(self, a, b, approvals=(), params=ra.DEFAULT_PARAMS):
        ar, br = self.ws.rows(a, b)
        return ra.reconcile(ar, br, list(approvals), params)

    def reasons(self, res):
        return {o["id"]: o["reason"] for o in res["open"]}


class HelperTests(unittest.TestCase):
    def test_reference_formats_normalise_to_one_key(self):
        keys = {ra.norm_ref(x) for x in ("INV-10453", "inv 10453", "INV10453", "INV-010453")}
        self.assertEqual(keys, {"INV10453"})
        self.assertEqual(ra.norm_ref("PMT-004517"), ra.norm_ref("PMT-4517"))

    def test_a_reference_without_a_digit_is_not_evidence(self):
        self.assertEqual(ra.norm_ref("PAYMENT"), "")
        self.assertEqual(ra.norm_ref(""), "")

    def test_names_ignore_case_legal_form_and_known_abbreviations(self):
        self.assertEqual(ra.norm_name("BRINDLE FOODS LTD"), ra.norm_name("Brindle Foods Limited"))
        self.assertEqual(ra.norm_name("Sunmere Intl Inc"), ra.norm_name("Sunmere International Co"))

    def test_an_abbreviation_not_in_the_table_stays_different(self):
        self.assertNotEqual(ra.norm_name("Torlin MFG LLC"), ra.norm_name("Torlin Manufacturing LLC"))

    def test_one_edit_apart(self):
        self.assertTrue(ra.one_edit_apart("INV10453", "INV10463"))     # substitution
        self.assertTrue(ra.one_edit_apart("INV10481", "INV10418"))     # neighbouring swap
        self.assertTrue(ra.one_edit_apart("INV1045", "INV10453"))      # deletion
        self.assertFalse(ra.one_edit_apart("INV10453", "INV10453"))
        self.assertFalse(ra.one_edit_apart("INV10453", "INV10973"))    # two substitutions

    def test_money_and_clean(self):
        self.assertEqual(ra.money(-78000), "-780.00")
        self.assertEqual(ra.money(5), "0.05")
        self.assertEqual(ra.clean("a\nb\r\x00"), "a\\nb\\r\\x00")
        self.assertTrue(ra.clean("x" * 100).endswith("..."))
        self.assertEqual(ra.csv_safe("=1+1"), "'=1+1")
        self.assertEqual(ra.csv_safe("plain"), "plain")


class RuleTests(Base):
    def test_exact_reference_amount_and_window_posts_on_its_own(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", ref="inv-1001")], [b_line("B1", "2026-03-05", "100.00", ref="INV-1001")])
        q = res["proposals"][0]
        self.assertEqual((q["rule"], q["status"], q["gap"]), ("ref_exact", "posted_auto", 3))

    def test_a_gap_beyond_the_window_does_not_match(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", ref="INV-1001")], [b_line("B1", "2026-03-06", "100.00", ref="INV-1001")])
        self.assertEqual(res["proposals"], [])
        self.assertEqual(self.reasons(res), {"A1": "no_counterpart", "B1": "no_counterpart"})

    def test_window_is_a_parameter(self):
        a, b = [a_line("A1", "2026-03-02", "100.00", ref="INV-1001")], [b_line("B1", "2026-03-06", "100.00", ref="INV-1001")]
        res = self.run_rows(a, b, params=ra.Params(window=4))
        self.assertEqual(len(res["proposals"]), 1)

    def test_opposite_sign_does_not_match(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", ref="INV-1001")], [b_line("B1", "2026-03-02", "-100.00", ref="INV-1001")])
        self.assertEqual(res["proposals"], [])

    def test_different_currency_does_not_match_and_says_so(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", ref="INV-1001")], [b_line("B1", "2026-03-02", "100.00", ref="INV-1001", ccy="EUR")])
        self.assertEqual(res["proposals"], [])
        self.assertEqual(self.reasons(res), {"A1": "currency_differs", "B1": "currency_differs"})

    def test_scheduled_fee_matches_and_waits_for_a_person(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "4998.50", ref="INV-1001")], [b_line("B1", "2026-03-02", "5000.00", ref="INV-1001")])
        q = res["proposals"][0]
        self.assertEqual((q["rule"], q["status"]), ("ref_fee", "pending"))

    def test_a_fee_not_on_the_schedule_is_not_matched(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "4998.25", ref="INV-1001")], [b_line("B1", "2026-03-02", "5000.00", ref="INV-1001")])
        self.assertEqual(res["proposals"], [])

    def test_a_fee_is_only_netted_from_credits(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "-4998.50", ref="INV-1001")], [b_line("B1", "2026-03-02", "-5000.00", ref="INV-1001")])
        self.assertEqual(res["proposals"], [])

    def test_batch_sum_needs_the_explicit_batch_id_and_an_exact_sum(self):
        a = [a_line("A1", "2026-03-04", "3000.00", ref="BT-0304")]
        b = [b_line("B1", "2026-03-04", "1000.00", ref="INV-1", batch="BT-0304"), b_line("B2", "2026-03-04", "1200.00", ref="INV-2", batch="BT-0304"),
             b_line("B3", "2026-03-04", "800.00", ref="INV-3", batch="BT-0304")]
        res = self.run_rows(a, b)
        q = res["proposals"][0]
        self.assertEqual((q["rule"], q["b_ids"], q["status"]), ("batch_sum", ["B1", "B2", "B3"], "pending"))

    def test_a_batch_that_is_one_cent_short_is_not_matched_and_says_why(self):
        a = [a_line("A1", "2026-03-04", "3000.01", ref="BT-0304")]
        b = [b_line("B1", "2026-03-04", "1500.00", ref="INV-1", batch="BT-0304"), b_line("B2", "2026-03-04", "1500.00", ref="INV-2", batch="BT-0304")]
        res = self.run_rows(a, b)
        self.assertEqual(res["proposals"], [])
        self.assertEqual(self.reasons(res)["A1"], "batch_sum_differs")

    def test_lines_that_add_up_without_a_batch_id_are_not_grouped(self):
        a = [a_line("A1", "2026-03-04", "3000.00")]
        b = [b_line("B1", "2026-03-04", "1800.00", ref="INV-1"), b_line("B2", "2026-03-04", "1200.00", ref="INV-2")]
        self.assertEqual(self.run_rows(a, b)["proposals"], [])

    def test_a_batch_larger_than_the_cap_is_not_matched(self):
        b = [b_line(f"B{i}", "2026-03-04", "100.00", ref=f"INV-{i}", batch="BT-0304") for i in range(1, 8)]
        a = [a_line("A1", "2026-03-04", "700.00", ref="BT-0304")]
        self.assertEqual(self.run_rows(a, b)["proposals"], [])

    def test_references_one_edit_apart_go_to_a_person(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", ref="INV-10481")], [b_line("B1", "2026-03-02", "100.00", ref="INV-10418")])
        self.assertEqual((res["proposals"][0]["rule"], res["proposals"][0]["status"]), ("ref_near", "pending"))

    def test_references_two_edits_apart_are_a_conflict_not_a_match(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", ref="INV-10481")], [b_line("B1", "2026-03-02", "100.00", ref="INV-10999")])
        self.assertEqual(res["proposals"], [])
        self.assertEqual(self.reasons(res), {"A1": "reference_conflict", "B1": "reference_conflict"})

    def test_no_reference_on_one_side_matches_on_name_and_amount_for_a_person(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00")], [b_line("B1", "2026-03-03", "100.00", ref="INV-1001")])
        self.assertEqual((res["proposals"][0]["rule"], res["proposals"][0]["status"]), ("name_amount", "pending"))

    def test_a_name_match_is_not_used_when_both_sides_carry_different_references(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", ref="INV-1001")], [b_line("B1", "2026-03-02", "100.00", ref="INV-7777")])
        self.assertEqual(res["proposals"], [])

    def test_a_different_counterparty_with_no_reference_is_not_matched(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", name="Corvan Textiles Inc")], [b_line("B1", "2026-03-02", "100.00")])
        self.assertEqual(res["proposals"], [])

    def test_a_generic_word_is_not_a_reference(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", ref="PAYMENT")], [b_line("B1", "2026-03-02", "100.00", ref="PAYMENT")])
        self.assertEqual(res["proposals"][0]["rule"], "name_amount")

    def test_nearest_date_wins_when_two_book_lines_fit(self):
        res = self.run_rows([a_line("A1", "2026-03-04", "100.00", ref="INV-1001")],
                            [b_line("B1", "2026-03-02", "100.00", ref="INV-1001"), b_line("B2", "2026-03-04", "100.00", ref="INV-1001")])
        self.assertEqual(res["proposals"][0]["b_ids"], ["B2"])

    def test_two_equally_near_different_book_lines_are_parked_not_guessed(self):
        res = self.run_rows([a_line("A1", "2026-03-04", "100.00")],
                            [b_line("B1", "2026-03-03", "100.00"), b_line("B2", "2026-03-05", "100.00")])
        self.assertEqual(res["proposals"], [])
        self.assertEqual(self.reasons(res), {"A1": "ambiguous_candidates", "B1": "ambiguous_candidates", "B2": "ambiguous_candidates"})
        self.assertEqual(res["open"][0]["detail"], "cannot be told apart from: B1, B2")

    def test_parked_lines_are_not_picked_up_by_a_weaker_rule(self):
        res = self.run_rows([a_line("A1", "2026-03-04", "100.00", ref="INV-1001")],
                            [b_line("B1", "2026-03-03", "100.00", ref="INV-1001", memo="one"), b_line("B2", "2026-03-05", "100.00", ref="INV-1001", memo="two")])
        self.assertEqual(res["proposals"], [])
        self.assertEqual(len(res["parked"]), 3)

    def test_identical_book_lines_are_interchangeable_and_the_spare_is_flagged(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", ref="INV-1001")],
                            [b_line("B1", "2026-03-02", "100.00", ref="INV-1001"), b_line("B2", "2026-03-02", "100.00", ref="INV-1001")])
        self.assertEqual(res["proposals"][0]["b_ids"], ["B1"])
        self.assertEqual(self.reasons(res), {"B2": "possible_duplicate"})

    def test_a_line_is_never_used_twice(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", ref="INV-1001"), a_line("A2", "2026-03-02", "100.00", ref="INV-1001")],
                            [b_line("B1", "2026-03-02", "100.00", ref="INV-1001")])
        self.assertEqual(len(res["proposals"]), 1)
        self.assertEqual(self.reasons(res), {"A2": "possible_duplicate"})

    def test_nothing_matches_says_so(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", ref="INV-1001")], [b_line("B1", "2026-04-02", "555.00", ref="INV-9")])
        self.assertIn("no matches found", ra.render(res))
        self.assertEqual(len(res["open"]), 2)

    def test_every_proposal_cites_its_lines_and_passes_its_own_check(self):
        res = self.run_rows([a_line("A1", "2026-03-02", "100.00", ref="INV-1001")], [b_line("B1", "2026-03-02", "100.00", ref="INV-1001")])
        q = res["proposals"][0]
        self.assertEqual(q["problems"], [])
        self.assertEqual(len(q["evidence"]), 4)
        self.assertTrue(q["key"].startswith("ref_exact:A1:B1:"))


if __name__ == "__main__":
    unittest.main()
