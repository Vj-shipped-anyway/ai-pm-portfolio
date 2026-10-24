import unittest

import _bootstrap  # noqa: F401
import spread_eval as se

TRUTH = {("D1", "revenue", "current"): 1000.0, ("D1", "revenue", "prior"): 900.0, ("D1", "cash", "current"): 50.0,
         ("D1", "cash", "prior"): 40.0, ("D2", "revenue", "current"): 2000.0, ("D2", "revenue", "prior"): 1800.0}
LAYOUT = {"D1": "alpha", "D2": "beta"}


def ev(preds, truth=TRUTH, layout=LAYOUT):
    return se.evaluate(layout, truth, preds)


def klass(key, pred, truth=TRUTH):
    period = {}
    for (d, f, p), v in truth.items():
        if (d, p) == (key[0], key[2]):
            period[f] = v
    return se.classify(key, pred, truth, period)


class ClassifyTests(unittest.TestCase):
    def test_each_class(self):
        k = ("D1", "revenue", "current")
        self.assertEqual(klass(k, None), "missing")
        self.assertEqual(klass(k, 1.0), "scale")
        self.assertEqual(klass(k, 1000000.0), "scale")
        self.assertEqual(klass(k, -1000.0), "sign")
        self.assertEqual(klass(k, 900.0), "wrong_period")
        self.assertEqual(klass(k, 50.0), "wrong_line")
        self.assertEqual(klass(k, 777.0), "other")

    def test_two_repairs_are_compound(self):
        self.assertEqual(klass(("D1", "revenue", "current"), 0.9), "compound")
        self.assertEqual(klass(("D1", "revenue", "current"), -900.0), "compound")

    def test_a_small_number_against_a_zero_truth_is_not_a_scale_error(self):
        truth = {("D1", "income_tax", "current"): 0.0, ("D1", "income_tax", "prior"): 5.0}
        self.assertEqual(klass(("D1", "income_tax", "current"), 12.0, truth), "other")


class EvaluateTests(unittest.TestCase):
    def test_perfect_predictions(self):
        r = ev(dict(TRUTH))
        self.assertEqual((r["correct"], r["values"], r["missing"], r["extra"]), (6, 6, 0, 0))
        self.assertEqual(r["layouts"]["alpha"]["docs_all_right"], 1)

    def test_wrong_missing_and_extra_are_counted(self):
        preds = dict(TRUTH)
        del preds[("D1", "cash", "prior")]
        preds[("D2", "revenue", "current")] = 2.0
        preds[("D9", "revenue", "current")] = 1.0
        r = ev(preds)
        self.assertEqual((r["correct"], r["missing"], r["extra"]), (4, 1, 1))
        self.assertEqual(r["errors"]["scale"], 1)
        self.assertEqual(r["layouts"]["beta"]["docs_all_right"], 0)

    def test_half_a_dollar_is_the_tolerance(self):
        self.assertEqual(ev({**TRUTH, ("D1", "cash", "current"): 50.4})["correct"], 6)
        self.assertEqual(ev({**TRUTH, ("D1", "cash", "current"): 50.6})["correct"], 5)

    def test_nothing_matches_is_an_error_not_a_zero(self):
        with self.assertRaises(se.InputError):
            ev({("X", "revenue", "current"): 1.0})
        with self.assertRaises(se.InputError):
            ev({})

    def test_truth_for_an_unknown_document_is_an_error(self):
        with self.assertRaises(se.InputError):
            ev(dict(TRUTH), layout={"D1": "alpha"})

    def test_documents_without_truth_are_reported(self):
        self.assertEqual(ev(dict(TRUTH), layout={**LAYOUT, "D3": "gamma"})["unscored_documents"], 1)

    def test_grouping_uses_the_layout_field_not_the_doc_id(self):
        r = ev(dict(TRUTH), layout={"D1": "same", "D2": "same"})
        self.assertEqual(list(r["layouts"]), ["same"])
        self.assertEqual(r["layouts"]["same"]["docs"], 2)


class TieOutTests(unittest.TestCase):
    FULL = {"revenue": 100, "cost_of_sales": 60, "gross_profit": 40, "operating_expenses": 10, "operating_income": 30,
            "interest_expense": 5, "pretax_income": 25, "income_tax": 5, "net_income": 20, "cash": 10,
            "accounts_receivable": 20, "inventory": 5, "total_current_assets": 35, "fixed_assets_net": 65, "total_assets": 100,
            "accounts_payable": 15, "short_term_debt": 5, "total_current_liabilities": 20, "long_term_debt": 30,
            "total_liabilities": 50, "total_equity": 50, "total_liabilities_and_equity": 100}

    def preds(self, **changes):
        return {("D", f, p): v for p in se.PERIODS for f, v in {**self.FULL, **changes}.items()}

    def test_consistent_document_passes(self):
        self.assertEqual(se.tie_out(self.preds(), ["D"])["D"], [])

    def test_broken_identity_is_flagged(self):
        self.assertIn("current:gross_profit:broken", se.tie_out(self.preds(gross_profit=41), ["D"])["D"])

    def test_missing_field_is_flagged_as_incomplete(self):
        p = self.preds()
        del p[("D", "cash", "prior")]
        self.assertIn("prior:current_assets:incomplete", se.tie_out(p, ["D"])["D"])

    def test_known_limit_a_uniform_scale_error_still_ties_out(self):
        self.assertEqual(se.tie_out({k: v * 1000 for k, v in self.preds().items()}, ["D"])["D"], [])

    def test_known_limit_swapped_periods_still_tie_out(self):
        p = self.preds()
        swapped = {(d, f, "prior" if q == "current" else "current"): v for (d, f, q), v in p.items()}
        self.assertEqual(se.tie_out(swapped, ["D"])["D"], [])


class GateTests(unittest.TestCase):
    def layouts(self, **acc):
        return {n: {"docs": 20, "values": 1000, "correct": int(a * 10)} for n, a in acc.items()}

    def test_pass_and_fail_on_the_floor(self):
        self.assertEqual(se.gate(self.layouts(a=99.0, b=97.0), 95.0, 3.0, 10)["verdict"], "PASS")
        g = se.gate(self.layouts(a=99.0, b=94.0), 95.0, 10.0, 10)
        self.assertEqual((g["verdict"], len(g["reasons"])), ("FAIL", 1))

    def test_fail_on_the_gap_alone(self):
        g = se.gate(self.layouts(a=100.0, b=96.0), 90.0, 3.0, 10)
        self.assertEqual(g["verdict"], "FAIL")
        self.assertIn("4.0 points below a", g["reasons"][0])

    def test_a_layout_with_too_few_documents_is_listed_not_gated(self):
        ls = self.layouts(a=99.0, b=10.0)
        ls["b"]["docs"] = 3
        g = se.gate(ls, 95.0, 3.0, 10)
        self.assertEqual((g["verdict"], g["not_gated"]), ("PASS", ["b"]))

    def test_nothing_to_gate_is_an_error(self):
        with self.assertRaises(se.InputError):
            se.gate(self.layouts(a=99.0), 95.0, 3.0, 50)

    def test_ties_for_best_resolve_by_name(self):
        self.assertEqual(se.gate(self.layouts(b=100.0, a=100.0), 95.0, 3.0, 10)["best"], "a")


class CleanTests(unittest.TestCase):
    def test_escapes_the_workflow_command_characters(self):
        self.assertEqual(se.clean("a%b\r\nc"), "a%25b%0D%0Ac")
        self.assertEqual(se.clean("x\x00y\x1b"), "x\\x00y\\x1b")

    def test_truncates(self):
        self.assertEqual(len(se.clean("z" * 500)), 60)


if __name__ == "__main__":
    unittest.main()
