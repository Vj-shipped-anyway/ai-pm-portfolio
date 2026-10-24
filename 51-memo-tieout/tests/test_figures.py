import unittest
from decimal import Decimal

import _bootstrap  # noqa: F401
from memo_tieout import parse_figures, ties


def one(text):
    figs = parse_figures(text)
    assert len(figs) == 1, figs
    return figs[0]


class ParseTests(unittest.TestCase):
    def test_dollar_forms_and_scales(self):
        for text, value, decimals, scale in [("$47.3 million", "47.3", 1, 10 ** 6), ("$6,450 thousand", "6450", 0, 10 ** 3),
                                             ("$4.1m", "4.1", 1, 10 ** 6), ("$5K", "5", 0, 10 ** 3), ("$2 bn", "2", 0, 10 ** 9),
                                             ("$47,320,000", "47320000", 0, 1), ("$1.25MM", "1.25", 2, 10 ** 6)]:
            f = one(f"Revenue was {text}.")
            self.assertEqual((f["kind"], f["value"], f["decimals"], f["scale"]), ("money", Decimal(value), decimals, Decimal(scale)), text)
            self.assertEqual(f["text"], text)

    def test_percent_and_multiple(self):
        self.assertEqual((one("up 7.9%")["kind"], one("up 7.9 %")["value"]), ("pct", Decimal("7.9")))
        f = one("coverage of 3.04x")
        self.assertEqual((f["kind"], f["decimals"]), ("x", 2))
        self.assertEqual(one("2.5X")["kind"], "x")

    def test_sign_is_read_only_when_it_is_a_sign(self):
        self.assertEqual(one("fell -4.2% in FY2023")["value"], Decimal("-4.2"))
        self.assertEqual(one("fell −4.2%")["value"], Decimal("-4.2"))
        self.assertEqual(one("a range of 5-10%")["value"], Decimal("10"))
        self.assertEqual(one("a loss of -$1.2 million")["value"], Decimal("-1.2"))

    def test_years_counts_sections_and_part_numbers_are_not_figures(self):
        text = "Founded in 2011, FY2024, 12 locations, Section 4.2, Q3, a 5-year tenor, form 10-K, part A1.5x, a 3x4 grid, 7 days"
        self.assertEqual(parse_figures(text), [])

    def test_a_word_after_the_amount_is_not_a_scale(self):
        f = one("It cost $5 more than planned.")
        self.assertEqual((f["text"], f["scale"]), ("$5", Decimal(1)))

    def test_words_and_usd_prefix_are_not_read(self):
        self.assertEqual(parse_figures("USD 3.2m, 3.2 million dollars, 31 percent, three times"), [])

    def test_oversized_figure_is_marked_bad_not_a_crash(self):
        self.assertIn("digits", one("$" + "9" * 20 + " million")["bad"])
        self.assertIn("decimals", one("1.1234567%")["bad"])
        self.assertEqual(one("$47.3 million")["bad"], "")

    def test_start_and_end_locate_the_figure(self):
        text = "Revenue was $47.3 million."
        f = one(text)
        self.assertEqual(text[f["start"]:f["end"]], "$47.3 million")


class TieTests(unittest.TestCase):
    def test_rounds_half_away_from_zero_at_the_decimals_shown(self):
        edge = Decimal(1250000)                      # 1.25 million exactly
        self.assertTrue(ties(one("$1.3 million"), edge))
        self.assertFalse(ties(one("$1.2 million"), edge))
        self.assertTrue(ties(one("1.25x"), Decimal("1.245")))
        self.assertTrue(ties(one("-1.3%"), Decimal("-1.25")))
        self.assertTrue(ties(one("$47.3 million"), Decimal(47320000)))
        self.assertFalse(ties(one("$47.4 million"), Decimal(47320000)))

    def test_trailing_zeros_do_not_matter(self):
        self.assertTrue(ties(one("$4.10 million"), Decimal(4100000)))
        self.assertTrue(ties(one("$4,100 thousand"), Decimal(4100000)))

    def test_tolerance_is_a_share_of_the_spread_value(self):
        fig = one("1.25x")
        self.assertFalse(ties(fig, Decimal("1.243")))
        self.assertTrue(ties(fig, Decimal("1.243"), Decimal("0.01")))
        self.assertFalse(ties(fig, Decimal("1.1"), Decimal("0.01")))


if __name__ == "__main__":
    unittest.main()
