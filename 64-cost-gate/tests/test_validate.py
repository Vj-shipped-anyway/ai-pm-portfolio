import json
import unittest

import _bootstrap  # noqa: F401
from cost_gate import parse_budget, parse_rows

PRICES = {"m": {"input": 0.003, "output": 0.015}}
GOOD = {"min_items": 30, "prices_usd_per_1k_tokens": {"m": {"input": 0.003, "output": 0.015}},
        "overall": {"max_cost_per_correct_usd": 0.01}, "slices": {"a": {"max_cost_per_correct_usd": 0.02}}}


def row(**kw):
    r = {"item_id": "Q1", "slice": "a", "model": "m", "correct": "1", "input_tokens": "1000", "output_tokens": "1000"}
    r.update(kw)
    return r


class BudgetTests(unittest.TestCase):
    def test_good_budget(self):
        b = parse_budget(GOOD)
        self.assertEqual((b["overall"], b["slices"], b["min_items"]), (0.01, {"a": 0.02}, 30))

    def bad(self, **change):
        obj = json.loads(json.dumps(GOOD))
        obj.update(change)
        with self.assertRaises(ValueError):
            parse_budget(obj)

    def test_wrong_types_raise_value_error(self):
        for obj in ([], "x", 5, None):
            with self.assertRaises(ValueError):
                parse_budget(obj)
        self.bad(prices_usd_per_1k_tokens={})
        self.bad(prices_usd_per_1k_tokens={"m": {"input": -1, "output": 1}})
        self.bad(prices_usd_per_1k_tokens={"m": {"input": True, "output": 1}})
        self.bad(prices_usd_per_1k_tokens={"m": {"input": 1}})
        self.bad(overall={"max_cost_per_correct_usd": 0})
        self.bad(overall={"max_cost_per_correct_usd": "0.01"})
        self.bad(overall=None)
        self.bad(min_items=2)
        self.bad(min_items=True)
        self.bad(min_items=30.5)
        self.bad(slices=[])
        self.bad(slices={"a": {"max_cost_per_correct_usd": -1}})

    def test_not_a_number_is_refused(self):
        obj = json.loads('{"prices_usd_per_1k_tokens": {"m": {"input": NaN, "output": 1}}, "overall": {"max_cost_per_correct_usd": 1}}')
        with self.assertRaises(ValueError):
            parse_budget(obj)


class RowTests(unittest.TestCase):
    def test_cost_is_tokens_times_price(self):
        out = parse_rows([row()], PRICES)
        self.assertAlmostEqual(out[0]["cost"], 0.018, places=9)
        self.assertEqual((out[0]["slice"], out[0]["correct"]), ("a", 1))

    def test_bad_rows_raise_value_error(self):
        cases = [[], [row(correct="2")], [row(correct="")], [row(input_tokens="-5")], [row(input_tokens="1.5")],
                 [row(output_tokens="abc")], [row(output_tokens="")], [row(input_tokens="9" * 40)],
                 [row(input_tokens="١٢")], [row(model="unknown")], [row(slice="  ")], [row(item_id="")],
                 [row(), row()], [row(correct=None)], [row(item_id="Q2", output_tokens=None)]]
        for rows in cases:
            with self.assertRaises(ValueError, msg=str(rows)):
                parse_rows(rows, PRICES)

    def test_error_names_the_line(self):
        with self.assertRaises(ValueError) as cm:
            parse_rows([row(), row(item_id="Q2", correct="9")], PRICES)
        self.assertIn("line 3", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
