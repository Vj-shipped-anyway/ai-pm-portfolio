import math
import unittest

import _bootstrap  # noqa: F401
import review_capacity as rc


def queue(**kw):
    q = {"queue_id": "q", "hours_open": 8.0, "arrivals_per_hour": 6.0, "opening_batch": 0.0, "handling_minutes": 20.0,
         "handling_cv": 1.0, "arrival_cv": 1.0, "target_wait_min": 30.0, "target_share": 0.9, "max_utilization": 0.85,
         "shrinkage": 0.25, "current_headcount": None}
    q.update(kw)
    return q


class ErlangTests(unittest.TestCase):
    def test_two_reviewers_one_erlang(self):
        self.assertAlmostEqual(rc.erlang_c(2, 1.0), 1.0 / 3.0, places=12)

    def test_one_reviewer_waits_with_probability_rho(self):
        self.assertAlmostEqual(rc.erlang_c(1, 0.6), 0.6, places=12)

    def test_saturated_queue_always_waits(self):
        self.assertEqual(rc.erlang_c(3, 3.0), 1.0)
        self.assertEqual(rc.erlang_c(3, 4.5), 1.0)

    def test_more_reviewers_wait_less(self):
        waits = [rc.erlang_c(c, 3.2) for c in range(4, 10)]
        self.assertEqual(waits, sorted(waits, reverse=True))

    def test_no_work_no_wait(self):
        self.assertEqual(rc.erlang_c(2, 0.0), 0.0)


class ModelTests(unittest.TestCase):
    def test_unit_spreads_reduce_to_erlang_c(self):
        q = queue()
        for seats in (4, 5, 6):
            self.assertAlmostEqual(rc.late_share(q, seats, True, True), rc.late_share(q, seats, False, False), places=12)

    def test_batch_drain_by_hand(self):
        # 10 cases at open, 10 minutes each, 2 reviewers, target 20: cases 7 to 10 start after 20 minutes. 4 of 10.
        q = queue(arrivals_per_hour=0.0, opening_batch=10.0, handling_minutes=10.0, target_wait_min=20.0)
        self.assertAlmostEqual(rc.late_share(q, 2), 0.4, places=12)
        self.assertEqual(rc.late_share(q, 3), 0.1)

    def test_batch_folded_into_the_mean_hides_the_drain(self):
        q = queue(arrivals_per_hour=2.0, opening_batch=30.0, handling_minutes=15.0, target_wait_min=45.0)
        self.assertGreater(rc.required_seats(q), rc.required_seats(q, use_variability=False, use_batch=False))

    def test_low_variance_needs_no_more_than_exponential(self):
        q = queue(handling_cv=0.2, arrival_cv=1.0, arrivals_per_hour=7.0, handling_minutes=30.0)
        self.assertLessEqual(rc.required_seats(q), rc.required_seats(q, use_variability=False))

    def test_utilization_cap_binds_on_a_light_queue(self):
        q = queue(arrivals_per_hour=6.0, handling_minutes=20.0, max_utilization=0.5, target_wait_min=600.0)
        self.assertEqual(rc.offered_load(q), 2.0)
        self.assertEqual(rc.required_seats(q), 4)

    def test_seats_do_not_fall_as_load_rises(self):
        seats = [rc.required_seats(queue(arrivals_per_hour=r)) for r in (2, 4, 6, 8, 12, 16)]
        self.assertEqual(seats, sorted(seats))

    def test_absurd_load_is_an_input_error(self):
        with self.assertRaises(rc.InputError):
            rc.required_seats(queue(arrivals_per_hour=100000.0))

    def test_roster_counts_shrinkage(self):
        self.assertEqual(rc.roster(6, 0.25), 8)
        self.assertEqual(rc.roster(6, 0.0), 6)
        self.assertEqual(rc.roster(3, 0.25), 4)


class ReplayTests(unittest.TestCase):
    CASES = [{"day": 1, "arrival_min": 0.0, "handle_min": 10.0}] * 3

    def test_one_reviewer_queues_three_cases(self):
        r = rc.replay(self.CASES, 1, 5.0, 1.0, 1)
        self.assertEqual((r["cases"], r["late"]), (3, 2))
        self.assertAlmostEqual(r["utilization"], 30.0 / 60.0)

    def test_two_reviewers_queue_one(self):
        r = rc.replay(self.CASES, 2, 5.0, 1.0, 1)
        self.assertEqual(r["late"], 1)
        self.assertAlmostEqual(r["utilization"], 30.0 / 120.0)

    def test_each_day_starts_empty(self):
        cases = self.CASES + [dict(c, day=2) for c in self.CASES]
        self.assertEqual(rc.replay(cases, 1, 5.0, 1.0, 2)["late"], 4)

    def test_empty_window_is_zero(self):
        self.assertEqual(rc.replay([], 2, 5.0, 8.0, 10)["late_share"], 0.0)

    def test_order_in_the_file_does_not_matter(self):
        a = [{"day": 1, "arrival_min": t, "handle_min": 10.0} for t in (0.0, 1.0, 2.0)]
        self.assertEqual(rc.replay(a, 1, 5.0, 1.0, 1), rc.replay(list(reversed(a)), 1, 5.0, 1.0, 1))


class FitTests(unittest.TestCase):
    def cases(self):
        return [{"day": 1, "arrival_min": 0.0, "handle_min": 10.0, "channel": "batch"},
                {"day": 1, "arrival_min": 10.0, "handle_min": 20.0, "channel": "live"},
                {"day": 1, "arrival_min": 40.0, "handle_min": 30.0, "channel": "live"},
                {"day": 1, "arrival_min": 50.0, "handle_min": 20.0, "channel": "live"}]

    def test_measured_by_hand(self):
        f, notes = rc.fit_queue(self.cases(), 1.0, 1)
        self.assertEqual(f["arrivals_per_hour"], 3.0)
        self.assertEqual(f["opening_batch"], 1.0)
        self.assertAlmostEqual(f["handling_minutes"], 20.0)
        self.assertAlmostEqual(f["handling_cv"], math.sqrt(50.0) / 20.0)
        self.assertAlmostEqual(f["arrival_cv"], 0.5)  # gaps 30 and 10: mean 20, standard deviation 10
        self.assertEqual(notes, [])

    def test_batch_is_the_channel_field_and_not_the_arrival_time(self):
        cases = self.cases()
        cases[1]["arrival_min"] = 0.0
        f, _ = rc.fit_queue(cases, 1.0, 1)
        self.assertEqual((f["opening_batch"], f["arrivals_per_hour"]), (1.0, 3.0))

    def test_late_arrivals_are_ignored_and_said_so(self):
        cases = self.cases() + [{"day": 1, "arrival_min": 90.0, "handle_min": 5.0, "channel": "live"}]
        f, notes = rc.fit_queue(cases, 1.0, 1)
        self.assertEqual(f["arrivals_per_hour"], 3.0)
        self.assertTrue(any("after the shift" in n for n in notes))

    def test_too_few_gaps_is_said(self):
        f, notes = rc.fit_queue(self.cases()[:3], 1.0, 1)
        self.assertEqual(f["arrival_cv"], 1.0)
        self.assertTrue(any("arrival_cv is set to 1" in n for n in notes))

    def test_one_case_cannot_be_fitted(self):
        with self.assertRaises(rc.InputError):
            rc.fit_queue(self.cases()[:1], 1.0, 1)


if __name__ == "__main__":
    unittest.main()
