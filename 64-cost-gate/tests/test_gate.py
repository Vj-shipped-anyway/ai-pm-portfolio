import unittest

import _bootstrap  # noqa: F401
from cost_gate import evaluate

BUDGET = {"prices": {}, "min_items": 30, "overall": 100.0, "slices": {}}


def block(name, n, right, cost=1.0):
    """n items in one slice, `right` of them correct, every call costing `cost`."""
    return [{"slice": name, "correct": 1 if i < right else 0, "cost": cost} for i in range(n)]


def status(report, scope):
    return next(s["status"] for s in report["scopes"] if s["scope"] == scope)


class GateTests(unittest.TestCase):
    def budget(self, overall=100.0, **slices):
        return dict(BUDGET, overall=overall, slices=dict(slices))

    def test_pass_warn_fail_on_one_slice(self):
        # 40 items, 20 right, each call 1.0: cost per correct 2.0, interval about 1.37 to 2.63
        run = block("a", 40, 20)
        self.assertEqual(status(evaluate(run, self.budget(a=2.5)), "a"), "PASS")
        self.assertEqual(status(evaluate(run, self.budget(a=1.8)), "a"), "WARN")
        self.assertEqual(status(evaluate(run, self.budget(a=1.0)), "a"), "FAIL")

    def test_decision_is_the_worst_scope(self):
        run = block("a", 40, 20) + block("b", 40, 40)
        rep = evaluate(run, self.budget(overall=100.0, a=1.0, b=100.0))
        self.assertEqual(status(rep, "overall"), "PASS")
        self.assertEqual(rep["decision"], "FAIL")

    def test_thin_slice_is_printed_not_judged_and_does_not_change_the_decision(self):
        run = block("a", 40, 40) + block("tiny", 10, 10, cost=50.0)
        rep = evaluate(run, self.budget(a=100.0, tiny=1.0))
        self.assertEqual(status(rep, "tiny"), "THIN")
        self.assertEqual(rep["decision"], "PASS")

    def test_thin_slice_still_counts_in_the_overall(self):
        run = block("a", 40, 40) + block("tiny", 10, 10, cost=50.0)
        rep = evaluate(run, self.budget(overall=5.0, a=100.0, tiny=1.0))
        self.assertEqual(status(rep, "overall"), "FAIL")

    def test_run_under_min_items_is_warn_not_pass(self):
        rep = evaluate(block("a", 10, 10), self.budget(a=100.0))
        self.assertEqual(status(rep, "overall"), "WARN")
        self.assertEqual(rep["decision"], "WARN")

    def test_no_correct_answers_fails(self):
        rep = evaluate(block("a", 40, 0), self.budget(a=100.0))
        self.assertEqual(status(rep, "a"), "FAIL")
        self.assertEqual(rep["decision"], "FAIL")

    def test_slice_without_a_ceiling_is_named_not_ignored(self):
        rep = evaluate(block("a", 40, 40) + block("new_slice", 40, 40), self.budget(a=100.0))
        self.assertEqual(status(rep, "new_slice"), "NO_BUDGET")
        self.assertEqual(rep["decision"], "WARN")

    def test_budgeted_slice_with_no_rows_is_named_not_ignored(self):
        rep = evaluate(block("a", 40, 40), self.budget(a=100.0, renamed=100.0))
        self.assertEqual(status(rep, "renamed"), "NO_ROWS")
        self.assertEqual(rep["decision"], "WARN")

    def test_slices_are_grouped_by_the_slice_field_not_by_name_prefix(self):
        run = block("card", 40, 40, cost=1.0) + block("card_wire", 40, 40, cost=9.0)
        rep = evaluate(run, self.budget(card=2.0, card_wire=20.0))
        by = {s["scope"]: s for s in rep["scopes"]}
        self.assertEqual(by["card"]["items"], 40)
        self.assertEqual(by["card_wire"]["items"], 40)
        self.assertEqual(by["card"]["status"], "PASS")

    def test_scopes_come_out_in_a_fixed_order(self):
        rep = evaluate(block("z", 40, 40) + block("b", 40, 40), self.budget(z=9.0, b=9.0))
        self.assertEqual([s["scope"] for s in rep["scopes"]], ["overall", "b", "z"])


if __name__ == "__main__":
    unittest.main()
