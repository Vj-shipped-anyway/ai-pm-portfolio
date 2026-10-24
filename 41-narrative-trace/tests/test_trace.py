import datetime
import unittest
from decimal import Decimal

import _bootstrap  # noqa: F401
import narrative_trace as nt


def rec(rid, case, day, amount, direction, channel, party):
    return {"id": rid, "case": case, "date": datetime.date.fromisoformat(day), "amount": Decimal(amount),
            "direction": direction, "channel": channel, "party": party}


LEDGER = nt.Ledger([rec("T-1", "C1", "2026-03-03", "9800.00", "in", "cash", ""),
                    rec("T-2", "C1", "2026-03-04", "4900.50", "in", "cash", ""),
                    rec("T-3", "C1", "2026-03-05", "12000.00", "out", "wire", "Tessel Trading Ltd."),
                    rec("T-4", "C1", "2026-03-06", "500.00", "out", "wire", "Tessel Trading"),
                    rec("T-5", "C2", "2026-03-07", "100.00", "in", "ach", "Brindle Foods Inc.")], True)


def one(text, case="C1", **options):
    results = nt.analyse(text, LEDGER, case, **options)
    assert len(results) == 1, results
    return results[0]


def kinds(r):
    return [k for k, _ in r["findings"]]


class StatusTests(unittest.TestCase):
    def test_a_correct_sentence_is_traced(self):
        r = one("The customer deposited $9,800.00 in cash on March 3, 2026 [txn: T-1].")
        self.assertEqual((r["status"], r["findings"]), ("traced", []))
        self.assertGreaterEqual(r["facts"], 4)

    def test_uncited(self):
        self.assertEqual(one("The customer deposited $9,800.00 in cash.")["status"], "uncited")

    def test_dangling_id_and_empty_citation(self):
        self.assertEqual(one("Something happened [txn: T-99].")["status"], "dangling")
        r = one("Something happened [txn: ].")
        self.assertEqual((r["status"], r["ids"]), ("dangling", []))

    def test_citation_of_another_case_needs_the_case(self):
        self.assertEqual(one("It came in [txn: T-5].")["status"], "other_case")
        self.assertEqual(one("The account received 100 USD by ACH from Brindle Foods Inc. [txn: T-5].", case=None)["status"], "traced")

    def test_sentence_citing_a_real_record_with_no_checkable_fact_is_unchecked(self):
        r = one("The funds were moved onward within hours [txn: T-1].")
        self.assertEqual((r["status"], r["facts"]), ("unchecked", 0))

    def test_fail_on_levels(self):
        unchecked = nt.analyse("The funds were moved onward [txn: T-1].", LEDGER, "C1")
        self.assertFalse(nt.is_failure(unchecked, "untraced"))
        self.assertTrue(nt.is_failure(unchecked, "unchecked"))
        self.assertFalse(nt.is_failure(nt.analyse("Nothing cited.", LEDGER, "C1"), "never"))

    def test_resolve_off_accepts_any_bracket(self):
        r = one("Something happened [txn: T-99].", resolve=False, facts=())
        self.assertEqual(r["status"], "unchecked")


class AmountTests(unittest.TestCase):
    def test_formats_that_mean_the_same_amount(self):
        for shown in ("$9,800.00", "$9,800", "9,800 USD", "$9.8k", "$9.8 thousand", "$9800"):
            with self.subTest(shown=shown):
                self.assertEqual(one("Deposited %s [txn: T-1]." % shown)["status"], "traced")

    def test_wrong_amounts(self):
        for shown in ("$9,801", "$9,800.01", "$98,000", "$9.9k"):
            with self.subTest(shown=shown):
                self.assertEqual(kinds(one("Deposited %s [txn: T-1]." % shown)), ["amount"])

    def test_rounds_to_the_precision_written(self):
        self.assertEqual(one("Deposited $4,901 [txn: T-2].")["status"], "traced")
        self.assertEqual(kinds(one("Deposited $4,901 [txn: T-2].", rounding=False)), ["amount"])

    def test_total_of_cited_records(self):
        text = "Deposited $14,700.50 in total [txn: T-1, T-2]."
        self.assertEqual(one(text)["status"], "traced")
        self.assertEqual(kinds(one(text, sums=False)), ["amount"])
        self.assertEqual(kinds(one("Deposited $14,700.00 in total [txn: T-1, T-2].")), ["amount"])

    def test_numbers_that_are_not_amounts_are_not_claims(self):
        r = one("In the 30-day window on account ending 4471 it was moved [txn: T-1].")
        self.assertEqual((r["status"], r["facts"]), ("unchecked", 0))


class DateTests(unittest.TestCase):
    def test_formats(self):
        for shown in ("2026-03-03", "March 3, 2026", "3 March 2026", "Mar 3 2026", "3rd March 2026"):
            with self.subTest(shown=shown):
                self.assertEqual(one("Moved on %s [txn: T-1]." % shown)["status"], "traced")

    def test_wrong_and_impossible_dates(self):
        self.assertEqual(kinds(one("Moved on 2026-03-04 [txn: T-1].")), ["date"])
        r = one("Moved on 2026-02-30 [txn: T-1].")
        self.assertEqual(kinds(r), ["date"])
        self.assertIn("not a day that exists", r["findings"][0][1])

    def test_known_false_alarm_a_date_that_is_not_a_transaction_date(self):
        self.assertEqual(kinds(one("The account was opened on 2025-01-01 [txn: T-1].")), ["date"])


class PartyDirectionChannelCountTests(unittest.TestCase):
    def test_longest_name_wins(self):
        self.assertEqual(one("Sent $500.00 to Tessel Trading [txn: T-4].")["status"], "traced")
        self.assertEqual(kinds(one("Sent $500.00 to Tessel Trading Ltd. [txn: T-4].")), ["party"])
        self.assertEqual(one("Sent $12,000.00 to tessel trading ltd. [txn: T-3].")["status"], "traced")

    def test_a_name_that_is_not_in_the_file_is_not_a_claim(self):
        self.assertEqual(one("Sent $500.00 to Unknown Partners [txn: T-4].")["status"], "traced")

    def test_direction(self):
        self.assertEqual(kinds(one("The customer sent $9,800.00 [txn: T-1].")), ["direction"])
        self.assertEqual(one("It was received and then sent on [txn: T-1, T-3].")["status"], "unchecked")

    def test_direction_word_list_is_short(self):
        self.assertIsNone(nt.direction_in("The customer wrote a check for $12,000.00"))

    def test_channel(self):
        self.assertEqual(kinds(one("The customer paid $12,000.00 by ACH [txn: T-3].")), ["channel"])
        self.assertEqual(one("The customer wired $12,000.00 [txn: T-3].")["status"], "traced")

    def test_cash_as_an_adjective_is_not_a_channel_claim(self):
        self.assertEqual(one("The cash-intensive customer sent $12,000.00 by wire [txn: T-3].")["status"], "traced")

    def test_count(self):
        self.assertEqual(one("The account received two deposits [txn: T-1, T-2].")["status"], "traced")
        self.assertEqual(kinds(one("The account received three deposits [txn: T-1, T-2].")), ["count"])
        self.assertEqual(kinds(one("The account received 2 cash deposits [txn: T-1].")), ["count"])
        self.assertEqual(one("It was repeated over 14 days [txn: T-1].")["status"], "unchecked")

    def test_known_miss_figures_right_but_bound_to_the_wrong_record(self):
        r = one("The customer deposited $4,900.50 on March 3, 2026 [txn: T-1, T-2].")
        self.assertEqual(r["status"], "traced")


class SummaryTests(unittest.TestCase):
    def test_counts(self):
        text = "Deposited $9,800.00 [txn: T-1]. Nothing cited. Moved on [txn: T-2]. Gone [txn: T-99]."
        self.assertEqual(nt.summarise(nt.analyse(text, LEDGER, "C1")),
                         {"sentences": 4, "traced": 1, "unchecked": 1, "untraced": 2})

    def test_notes_for_a_narrative_that_matches_nothing(self):
        none_cited = nt.analyse("One. Two.", LEDGER, "C1")
        self.assertIn("no sentence has a citation", nt.notes_for(none_cited, LEDGER)[0])
        wrong_file = nt.analyse("One [txn: X-1]. Two [txn: X-2].", LEDGER, "C1")
        self.assertIn("none of the 2 cited IDs", nt.notes_for(wrong_file, LEDGER)[0])


if __name__ == "__main__":
    unittest.main()
