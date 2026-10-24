import unittest

import _bootstrap  # noqa: F401
from cost_gate import cost_per_correct


def items(costs, correct):
    return [{"cost": c, "correct": y, "slice": "s"} for c, y in zip(costs, correct)]


class IntervalTests(unittest.TestCase):
    def test_worked_example(self):
        # four calls at 1.0 each, three right: R = 4/3, residuals -1/3 x3 and 1, sum of squares 4/3,
        # variance = (4/3) / (4 * 3) / 0.75^2 = 0.19753, standard error 0.44444
        point, low, high = cost_per_correct(items([1, 1, 1, 1], [1, 1, 1, 0]))
        self.assertAlmostEqual(point, 4 / 3, places=6)
        self.assertAlmostEqual(low, 4 / 3 - 1.96 * 0.444444, places=4)
        self.assertAlmostEqual(high, 4 / 3 + 1.96 * 0.444444, places=4)

    def test_nothing_correct_has_no_ratio(self):
        self.assertIsNone(cost_per_correct(items([1, 1, 1], [0, 0, 0])))

    def test_one_item_has_no_interval(self):
        self.assertIsNone(cost_per_correct(items([1], [1])))

    def test_no_spread_gives_a_point_interval(self):
        point, low, high = cost_per_correct(items([2, 2, 2, 2], [1, 1, 1, 1]))
        self.assertEqual((point, low, high), (2.0, 2.0, 2.0))

    def test_lower_end_never_goes_below_zero(self):
        point, low, high = cost_per_correct(items([0, 0, 0, 10], [1, 1, 1, 1]))
        self.assertEqual(point, 2.5)
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 5.0)

    def test_wrong_answers_still_cost_money(self):
        right_only = cost_per_correct(items([1, 1], [1, 1]))[0]
        with_wrong = cost_per_correct(items([1, 1, 1, 1], [1, 1, 0, 0]))[0]
        self.assertEqual(right_only, 1.0)
        self.assertEqual(with_wrong, 2.0)


if __name__ == "__main__":
    unittest.main()
