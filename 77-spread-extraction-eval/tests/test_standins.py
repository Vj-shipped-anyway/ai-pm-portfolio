import unittest

import _bootstrap  # noqa: F401
from _standins import alias_aware, fixed_label

PLAIN = """Acme Test Co
INCOME STATEMENT
                                  2025          2024
Revenue                      1,000,000       900,000
Cost of sales                  600,000       500,000
Net income                      -5,000        12,000
"""


class FixedLabelTests(unittest.TestCase):
    def test_reads_the_layout_it_was_written_for(self):
        self.assertEqual(fixed_label(PLAIN), {("revenue", "current"): 1000000, ("revenue", "prior"): 900000,
                                              ("cost_of_sales", "current"): 600000, ("cost_of_sales", "prior"): 500000,
                                              ("net_income", "current"): -5000, ("net_income", "prior"): 12000})

    def test_ignores_scale_header_and_loses_parentheses(self):
        out = fixed_label("(in thousands of dollars)\nNet income      (1,234)      2,000\n")
        self.assertEqual(out[("net_income", "current")], 1234)

    def test_unknown_label_and_one_number_are_skipped(self):
        self.assertEqual(fixed_label("Net sales    1,000    900\nRevenue    1,000\n"), {})


class AliasAwareTests(unittest.TestCase):
    def test_same_result_as_fixed_label_on_the_plain_layout(self):
        self.assertEqual(alias_aware(PLAIN), fixed_label(PLAIN))

    def test_scale_header_parentheses_dash_and_dollar_sign(self):
        text = ("(in thousands of dollars)\n                       2024          2025\n"
                "Revenue            $ 4,000       $ 4,500\nIncome tax              -         (12)\n"
                "Net income          (1,234)         900\n")
        out = alias_aware(text)
        self.assertEqual(out[("revenue", "current")], 4500000)
        self.assertEqual(out[("revenue", "prior")], 4000000)
        self.assertEqual(out[("income_tax", "prior")], 0)
        self.assertEqual(out[("income_tax", "current")], -12000)
        self.assertEqual(out[("net_income", "prior")], -1234000)

    def test_millions_header(self):
        self.assertEqual(alias_aware("in millions\nRevenue   2   3\n")[("revenue", "current")], 2000000)

    def test_aliases_footnote_marker_and_leaders(self):
        out = alias_aware("Net sales (1) ........   500   400\nProfit for the year ...   50   40\n")
        self.assertEqual((out[("revenue", "current")], out[("net_income", "prior")]), (500, 40))

    def test_wrapped_label(self):
        out = alias_aware("Total liabilities and\nequity ........   700   600\n")
        self.assertEqual(out[("total_liabilities_and_equity", "current")], 700)

    def test_two_digit_negative_is_not_a_footnote_marker(self):
        out = alias_aware("Income tax          (12)        (15)\n")
        self.assertEqual((out[("income_tax", "current")], out[("income_tax", "prior")]), (-12, -15))

    def test_side_by_side_halves(self):
        out = alias_aware("Cash          100    90   Accounts payable        50    40\n")
        self.assertEqual((out[("cash", "current")], out[("accounts_payable", "prior")]), (100, 40))

    def test_header_years_set_the_column_order(self):
        out = alias_aware("                 2023   2024\nRevenue     10     20\n")
        self.assertEqual((out[("revenue", "current")], out[("revenue", "prior")]), (20, 10))

    def test_known_limit_a_note_column_is_read_as_the_current_value(self):
        out = alias_aware("Revenue          3     4,210,500     3,987,120\n")
        self.assertEqual(out[("revenue", "current")], 3)
        self.assertEqual(out[("revenue", "prior")], 4210500)

    def test_first_occurrence_wins(self):
        out = alias_aware("Revenue   10   9\nRevenue   99   98\n")
        self.assertEqual(out[("revenue", "current")], 10)


class HostileInputTests(unittest.TestCase):
    def test_empty_and_textless_input(self):
        for f in (fixed_label, alias_aware):
            self.assertEqual(f(""), {})
            self.assertEqual(f("no numbers here\n\n"), {})

    def test_very_long_digit_runs_do_not_raise(self):
        text = "Revenue   " + "9" * 6000 + "   " + "8" * 6000 + "\n"
        for f in (fixed_label, alias_aware):
            f(text)
        self.assertEqual(alias_aware(text), {})

    def test_control_characters_and_markup_in_text(self):
        text = "Revenue\x00\x1b[31m   1   2\n<script>alert(1)</script>   3   4\r\n::error::x\n"
        for f in (fixed_label, alias_aware):
            self.assertIsInstance(f(text), dict)


if __name__ == "__main__":
    unittest.main()
