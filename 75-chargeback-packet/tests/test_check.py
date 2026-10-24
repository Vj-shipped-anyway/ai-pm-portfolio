import copy
import unittest
from datetime import date

import _bootstrap  # noqa: F401
import chargeback_packet as cp
from _fixtures import base, doc

RULES = cp.load_rules()
AS_OF = date(2026, 2, 28)


def run(case, as_of=AS_OF, checks=cp.CHECKS):
    return cp.check_case(case, RULES, as_of, checks)


def kinds(r):
    return [p["kind"] for p in r["problems"]]


class CompletenessTests(unittest.TestCase):
    def test_complete_packet_is_ready_with_days_left(self):
        r = run(base())
        self.assertEqual((r["state"], r["due"], r["days_left"]), ("READY", "2026-03-04", 4))

    def test_missing_required_item_names_the_alternatives(self):
        c = base()
        c["docs"] = c["docs"][:1]
        r = run(c)
        self.assertEqual((r["state"], kinds(r)), ("FIX", ["missing_evidence"]))
        self.assertIn("one of delivery_tracking, digital_access_log", r["problems"][0]["detail"])

    def test_either_or_item_accepts_the_second_option(self):
        c = base()
        c["docs"][1] = doc("b", "digital_access_log", "2026-01-12")
        self.assertEqual(run(c)["state"], "READY")

    def test_optional_item_may_be_absent(self):
        self.assertNotIn("missing_evidence", kinds(run(base())))

    def test_empty_packet_lists_every_required_item(self):
        c = base()
        c["docs"] = []
        self.assertEqual(kinds(run(c)), ["missing_evidence", "missing_evidence"])

    def test_unlisted_type_is_a_note_not_a_problem(self):
        c = base()
        c["docs"].append(doc("c", "delivry_tracking", "2026-01-14"))
        r = run(c)
        self.assertEqual((r["state"], r["problems"]), ("READY", []))
        self.assertIn("delivry_tracking", r["notes"][0])


class ClockTests(unittest.TestCase):
    def test_last_day_still_counts(self):
        r = run(base(), date(2026, 3, 4))
        self.assertEqual((r["state"], r["days_left"]), ("READY", 0))

    def test_day_after_the_window_is_late(self):
        r = run(base(), date(2026, 3, 5))
        self.assertEqual((r["state"], r["days_left"]), ("LATE", -1))

    def test_submitted_on_the_due_day_is_on_time_and_a_day_later_is_late(self):
        c = base()
        c["submitted_date"] = "2026-03-04"
        self.assertEqual(run(c, date(2026, 6, 1))["state"], "READY")
        c["submitted_date"] = "2026-03-05"
        self.assertEqual(run(c, date(2026, 1, 1))["state"], "LATE")

    def test_late_wins_over_fix_and_keeps_the_problems(self):
        c = base()
        c["docs"] = c["docs"][:1]
        r = run(c, date(2026, 3, 9))
        self.assertEqual((r["state"], kinds(r)), ("LATE", ["missing_evidence"]))

    def test_window_crosses_a_leap_day(self):
        c = base()
        c.update(txn_date="2028-02-01", received_date="2028-02-25")
        c["docs"] = [doc("a", "order_record", "2028-02-01", amount_cents=12900), doc("b", "delivery_tracking", "2028-02-05")]
        self.assertEqual(run(c, date(2028, 3, 1))["due"], "2028-03-26")

    def test_without_the_clock_check_nothing_is_late(self):
        self.assertEqual(run(base(), date(2027, 1, 1), ("completeness",))["state"], "READY")


class ConsistencyTests(unittest.TestCase):
    def test_document_for_another_order(self):
        c = base()
        c["docs"][1]["ref_id"] = "O-2"
        self.assertEqual(kinds(run(c)), ["wrong_reference"])

    def test_order_record_below_the_disputed_amount(self):
        c = base()
        c["docs"][0]["amount_cents"] = 12899
        self.assertEqual(kinds(run(c)), ["amount_short"])

    def test_partial_dispute_is_fine(self):
        c = base()
        c["docs"][0]["amount_cents"] = 30000
        self.assertEqual(run(c)["state"], "READY")

    def test_delivery_dated_before_the_purchase(self):
        c = base()
        c["docs"][1]["doc_date"] = "2026-01-09"
        self.assertEqual(kinds(run(c)), ["dated_before_purchase"])

    def test_order_record_dated_before_the_purchase_is_not_flagged(self):
        c = base()
        c["docs"][0]["doc_date"] = "2026-01-09"
        self.assertEqual(run(c)["state"], "READY")

    def test_draft_document_dated_after_the_check_date(self):
        c = base()
        c["docs"][1]["doc_date"] = "2026-03-01"
        self.assertEqual(kinds(run(c)), ["dated_in_future"])

    def test_sent_packet_is_judged_on_its_own_submitted_date(self):
        c = base()
        c["submitted_date"] = "2026-02-20"
        c["docs"][1]["doc_date"] = "2026-02-21"
        self.assertEqual(kinds(run(c, date(2026, 3, 1))), ["dated_in_future"])

    def test_page_limit_boundary(self):
        c = base()
        c["docs"][0]["pages"] = 12 - c["docs"][1]["pages"]
        self.assertEqual(run(c)["state"], "READY")
        c["docs"][0]["pages"] += 1
        r = run(c)
        self.assertEqual((r["state"], kinds(r)), ("FIX", ["over_page_limit"]))

    def test_consistency_off_ignores_those_faults(self):
        c = base()
        c["docs"][1]["ref_id"] = "O-2"
        self.assertEqual(run(c, checks=("completeness", "clock"))["state"], "READY")

    def test_input_case_is_not_modified(self):
        c = base()
        before = copy.deepcopy(c)
        run(c)
        self.assertEqual(c, before)


class TextTests(unittest.TestCase):
    def test_render_of_a_draft_with_one_problem(self):
        c = base()
        c["docs"] = c["docs"][:1]
        lines = cp.render(run(c))
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("case T-1  RC-02 Goods or services not received  amount 129.00  due 2026-03-04, 4 days left as of 2026-02-28"))
        self.assertEqual(lines[2], "decision: FIX (1 problem, 4 days left)")

    def test_singular_and_plural(self):
        self.assertEqual((cp.plural(1, "day"), cp.plural(0, "day"), cp.plural(2, "day")), ("1 day", "0 days", "2 days"))

    def test_money_has_no_float_error(self):
        self.assertEqual((cp.money(5), cp.money(12900), cp.money(100001)), ("0.05", "129.00", "1000.01"))


if __name__ == "__main__":
    unittest.main()
