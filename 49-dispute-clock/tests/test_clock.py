import datetime as dt
import unittest

import _bootstrap  # noqa: F401
import dispute_clock as dc

D = dt.date
HOL = frozenset([D(2026, 7, 3), D(2026, 9, 7)])
CLOCK = {"clock_id": "C1", "name": "Ack", "applies_to": "all", "window": 2, "unit": "business",
         "anchor": "contact", "satisfied_by": ("ack", "closed")}


def dispute(**dates):
    base = {"contact": D(2026, 9, 4), "ack": None, "closed": None}
    base.update(dates)
    return {"dispute_id": "D1", "dispute_type": "t", "window_class": "standard", "credit_eligible": 1, "dates": base}


class DayArithmeticTests(unittest.TestCase):
    def test_business_days_skip_a_holiday_and_the_weekend(self):
        self.assertEqual(dc.add_days(D(2026, 7, 2), 2, "business", HOL), D(2026, 7, 7))
        self.assertEqual(dc.add_days(D(2026, 9, 4), 2, "business", HOL), D(2026, 9, 9))

    def test_start_on_a_day_off_counts_from_the_next_business_day(self):
        self.assertEqual(dc.add_days(D(2026, 9, 5), 1, "business", HOL), D(2026, 9, 8))

    def test_month_boundary_and_zero(self):
        self.assertEqual(dc.add_days(D(2026, 1, 30), 1, "business", frozenset()), D(2026, 2, 2))
        self.assertEqual(dc.add_days(D(2026, 1, 30), 0, "business", frozenset()), D(2026, 1, 30))

    def test_calendar_days_ignore_days_off(self):
        self.assertEqual(dc.add_days(D(2026, 9, 4), 30, "calendar", HOL), D(2026, 10, 4))

    def test_count_days_undoes_add_days(self):
        for k in range(40):
            start = D(2026, 6, 20) + dt.timedelta(days=k)
            for n in range(0, 16):
                due = dc.add_days(start, n, "business", HOL)
                self.assertEqual(dc.count_days(start, due, "business", HOL), n, (start, n))

    def test_count_days_is_negative_going_back(self):
        self.assertEqual(dc.count_days(D(2026, 9, 9), D(2026, 9, 4), "business", HOL), -2)


class StatusTests(unittest.TestCase):
    def test_the_due_day_itself_is_on_time_and_the_next_day_is_late(self):
        due = D(2026, 9, 9)
        self.assertEqual(dc.status_of(due, D(2026, 9, 9), D(2026, 9, 30)), "on_time")
        self.assertEqual(dc.status_of(due, D(2026, 9, 10), D(2026, 9, 30)), "late")

    def test_unsent_is_running_until_the_day_after_the_due_date(self):
        due = D(2026, 9, 30)
        self.assertEqual(dc.status_of(due, None, D(2026, 9, 30)), "running")
        self.assertEqual(dc.status_of(due, None, D(2026, 10, 1)), "breached")

    def test_clock_without_its_anchor_has_not_started(self):
        r = dc.evaluate_clock(dispute(contact=None), CLOCK, HOL, D(2026, 9, 30))
        self.assertEqual((r["status"], r["due"], r["days"]), ("not_started", None, None))

    def test_earliest_satisfying_event_counts(self):
        r = dc.evaluate_clock(dispute(ack=D(2026, 9, 14), closed=D(2026, 9, 8)), CLOCK, HOL, D(2026, 9, 30))
        self.assertEqual((r["status"], r["sent"]), ("on_time", D(2026, 9, 8)))

    def test_days_late_and_days_left_use_the_clock_unit(self):
        late = dc.evaluate_clock(dispute(ack=D(2026, 9, 11)), CLOCK, HOL, D(2026, 9, 30))
        self.assertEqual((late["status"], late["days"]), ("late", 2))
        left = dc.evaluate_clock(dispute(), CLOCK, HOL, D(2026, 9, 8))
        self.assertEqual((left["status"], left["days"]), ("running", 1))
        over = dc.evaluate_clock(dispute(), CLOCK, HOL, D(2026, 9, 14))
        self.assertEqual((over["status"], over["days"]), ("breached", 3))

    def test_an_event_after_the_as_of_date_is_an_input_error(self):
        with self.assertRaises(dc.InputError):
            dc.evaluate_clock(dispute(ack=D(2026, 10, 1)), CLOCK, HOL, D(2026, 9, 30))
        with self.assertRaises(dc.InputError):
            dc.evaluate_clock(dispute(contact=D(2026, 10, 1)), CLOCK, HOL, D(2026, 9, 30))

    def test_applies_reads_explicit_fields(self):
        d = dispute()
        d["window_class"] = "extended"
        self.assertFalse(dc.applies(d, "standard"))
        self.assertTrue(dc.applies(d, "extended"))
        self.assertTrue(dc.applies(d, "credit_eligible"))
        d["credit_eligible"] = 0
        self.assertFalse(dc.applies(d, "credit_eligible"))

    def test_holiday_coverage_counts_clocks_that_reach_an_uncovered_year(self):
        r = dc.evaluate_clock(dispute(contact=D(2026, 12, 30)), CLOCK, HOL, D(2027, 1, 5))
        self.assertEqual(dc.outside_holiday_years([r], HOL), 1)
        self.assertEqual(dc.outside_holiday_years([dc.evaluate_clock(dispute(), CLOCK, HOL, D(2026, 9, 30))], HOL), 0)


if __name__ == "__main__":
    unittest.main()
