import unittest
from decimal import Decimal

import _bootstrap  # noqa: F401
from memo_tieout import build_spread, check_memo, find_ties, scan_memo, tally

# FY2022..FY2024 in thousands. FY2024: ebitda 7,120; debt/ebitda 2.1629; dscr 3.0427; current ratio 1.625; growth 7.913%.
LINES = {"revenue": [41200, 43850, 47320], "cogs": [27500, 29100, 31400], "opex": [7900, 8300, 8800],
         "interest_expense": [1320, 1250, 1140], "principal_payments": [1000, 1000, 1200], "total_debt": [17600, 16600, 15400],
         "current_assets": [12400, 13100, 14300], "current_liabilities": [8100, 8500, 8800], "total_equity": [14800, 17500, 20730],
         "net_income": [2100, 2700, 3230], "cash": [2900, 3300, 4100]}


def make(**overrides):
    lines = dict(LINES, **overrides)
    rows = [{"period": p, "period_end": e, "line": n, "value": str(v[i]), "unit": "usd_thousands"}
            for n, v in lines.items() for i, (p, e) in enumerate([("FY2022", "2022-12-31"), ("FY2023", "2023-12-31"), ("FY2024", "2024-12-31")])]
    return build_spread(rows)


SPREAD = make()


def one(text, spread=SPREAD, tolerance=None):
    results = check_memo(text, spread, tolerance)
    assert len(results) == 1, results
    return results[0]


class StatusTests(unittest.TestCase):
    def test_a_spread_line_ties_at_the_precision_shown(self):
        self.assertEqual(one("[$47.3 million](spread:revenue/FY2024)")["status"], "tied")
        self.assertEqual(one("[$47,320 thousand](spread:revenue/FY2024)")["status"], "tied")
        self.assertEqual(one("[$47,320,000](spread:revenue/FY2024)")["status"], "tied")
        r = one("[$47.4 million](spread:revenue/FY2024)")
        self.assertEqual(r["status"], "mismatch")
        self.assertIn("revenue/FY2024 is $47.32 million in the spread", r["why"])

    def test_a_figure_from_another_period_says_where_it_does_tie(self):
        r = one("[$6,450 thousand](spread:ebitda/FY2024)")
        self.assertEqual(r["status"], "mismatch")
        self.assertIn("recomputes to $7,120 thousand", r["why"])
        self.assertIn("does tie to ebitda/FY2023", r["why"])

    def test_formulas_are_recomputed(self):
        for text in ["[2.16x](spread:debt_ebitda_x/FY2024)", "[3.04x](spread:dscr_x/FY2024)", "[1.63x](spread:current_ratio_x/FY2024)",
                     "[7.9%](spread:revenue_growth_pct/FY2024)", "[15.0%](spread:ebitda_margin_pct/FY2024)",
                     "[6.8%](spread:net_margin_pct/FY2024)", "[0.74x](spread:debt_to_equity_x/FY2024)", "[$15,920 thousand](spread:gross_profit/FY2024)",
                     "[33.6%](spread:gross_margin_pct/FY2024)"]:
            self.assertEqual(one(text)["status"], "tied", text)

    def test_a_stale_denominator_does_not_tie(self):
        r = one("[2.39x](spread:debt_ebitda_x/FY2024)")
        self.assertEqual(r["status"], "mismatch")
        self.assertIn("total_debt / ebitda", r["why"])

    def test_rounding_up_by_one_hundredth_does_not_tie(self):
        self.assertEqual(one("[3.05x](spread:dscr_x/FY2024)")["status"], "mismatch")
        self.assertEqual(one("[3.05x](spread:dscr_x/FY2024)", tolerance=Decimal("0.01"))["status"], "tied")

    def test_negative_growth_ties_with_its_sign(self):
        s = make(revenue=[50000, 48000, 47000])
        self.assertEqual(one("[-2.1%](spread:revenue_growth_pct/FY2024)", s)["status"], "tied")
        self.assertEqual(one("[2.1%](spread:revenue_growth_pct/FY2024)", s)["status"], "mismatch")

    def test_a_line_in_the_spread_wins_over_a_formula_of_the_same_name(self):
        s = make(ebitda=[1, 2, 3])
        self.assertEqual(one("[$3 thousand](spread:ebitda/FY2024)", s)["status"], "tied")

    def test_unmarked_figures_are_untied(self):
        r = one("Cash was $4.1 million.")
        self.assertEqual((r["status"], r["tag"]), ("untied", ""))
        self.assertEqual(one("Pricing is base plus 2.75%.")["status"], "untied")
        self.assertEqual(one("Coverage covenant of 1.25x.")["status"], "untied")

    def test_terms_are_counted_and_not_checked(self):
        r = one("Requested [$5.0 million](term:facility_amount) senior loan.")
        self.assertEqual(r["status"], "term")
        self.assertEqual(one("[$5.0 million](term:Facility Amount)")["status"], "unresolved")

    def test_unresolved_reasons(self):
        cases = {
            "[$4.1 million](spread:cashh/FY2024)": "neither a line",
            "[$4.1 million](spread:cash/FY2025)": "not in the spread",
            "[$4.1 million](spread:cash/2024)": "not in the spread",
            "[$4.1 million](spread:cash)": "malformed tag",
            "[$4.1 million](spread:)": "malformed tag",
            "[$4.1 million](spread:cash/FY 2024)": "malformed tag",
            "[$4.1 million and $5 million](spread:cash/FY2024)": "2 figures",
            "[the cash balance](spread:cash/FY2024)": "0 figures",
            "[4.1x](spread:cash/FY2024)": "dollar figure and the memo writes a multiple",
            "[$4.1 million](spread:dscr_x/FY2024)": "multiple figure and the memo writes a dollar",
            "[0.0%](spread:revenue_growth_pct/FY2022)": "earliest period",
            "[$" + "9" * 20 + "](spread:cash/FY2024)": "more than 15 whole digits",
        }
        for text, reason in cases.items():
            r = one(text)
            self.assertEqual(r["status"], "unresolved", text)
            self.assertIn(reason, r["why"], text)

    def test_a_formula_with_a_missing_input_or_a_zero_divisor_is_unresolved(self):
        lean = build_spread([{"period": "FY2024", "period_end": "2024-12-31", "line": "revenue", "value": "5", "unit": "usd"}])
        self.assertIn("no total_debt value", one("[1.0x](spread:debt_ebitda_x/FY2024)", lean)["why"])
        zero = make(revenue=[1, 1, 1], cogs=[1, 1, 1], opex=[0, 0, 0])
        r = one("[1.0x](spread:debt_ebitda_x/FY2024)", zero)
        self.assertEqual(r["status"], "unresolved")
        self.assertIn("divisor is zero", r["why"])

    def test_find_ties_lists_at_most_three_sorted(self):
        fig = {"kind": "money", "value": Decimal(0), "decimals": 0, "scale": Decimal(1), "scale_word": ""}
        flat = make(**{k: [0, 0, 0] for k in LINES})
        found = find_ties(flat, fig, ("revenue", "FY2024"))
        self.assertEqual(len(found), 3)
        self.assertEqual(found, sorted(found))


class ReadingTests(unittest.TestCase):
    def test_positions_point_at_the_figure(self):
        text = "# Memo\n\n- Revenue was [$47.3 million](spread:revenue/FY2024), and cash was $4.1 million.\n"
        rs = check_memo(text, SPREAD)
        line = text.split("\n")[2]
        self.assertEqual([(r["line"], r["col"], r["text"]) for r in rs],
                         [(3, line.index("$47.3") + 1, "$47.3 million"), (3, line.index("$4.1") + 1, "$4.1 million")])
        self.assertEqual((rs[0]["col"], rs[1]["col"]), (16, 68))

    def test_code_fences_code_spans_and_urls_are_skipped(self):
        text = "```\nrevenue was $47.3 million\n```\nSee `$5 million` and https://example.test/p?x=$5m or [docs](https://example.test/$9m).\n"
        self.assertEqual(check_memo(text, SPREAD), [])

    def test_an_unclosed_fence_is_an_error_not_a_silent_skip(self):
        with self.assertRaisesRegex(ValueError, "line 2 never closes"):
            scan_memo("Revenue $5 million\n```\n$6 million\n")

    def test_text_between_marks_is_still_read(self):
        rs = check_memo("[$47.3 million](spread:revenue/FY2024) then $5 million and 12 locations in 2011.", SPREAD)
        self.assertEqual([r["status"] for r in rs], ["tied", "untied"])

    def test_a_figure_with_no_dollar_sign_percent_or_x_is_not_read(self):
        self.assertEqual(check_memo("Revenue was USD 47.3m, or 47.3 million dollars; margin 15 percent; three times.", SPREAD), [])

    def test_table_rows_are_read(self):
        text = "| Line | Figure |\n|---|---|\n| Revenue | [$47.3 million](spread:revenue/FY2024) |\n"
        self.assertEqual([r["status"] for r in check_memo(text, SPREAD)], ["tied"])

    def test_crlf_and_bom_style_text(self):
        self.assertEqual([r["status"] for r in check_memo("a [$47.3 million](spread:revenue/FY2024)\r\nb $5 million\r\n", SPREAD)],
                         ["tied", "untied"])

    def test_a_truncated_mark_is_a_finding_not_a_crash(self):
        rs = check_memo("Revenue was [$47.3 million](spread:reven", SPREAD)
        self.assertEqual([r["status"] for r in rs], ["untied"])

    def test_hostile_link_text_is_cleaned_in_the_label(self):
        r = one("[::error title=x::boom \x1b %](spread:cash/FY2024)")
        self.assertEqual(r["status"], "unresolved")
        self.assertTrue(r["text"].startswith("::error title=x::boom"))
        self.assertNotIn("\x1b", r["text"])

    def test_tally_counts(self):
        rs = check_memo("[$47.3 million](spread:revenue/FY2024) [$1 million](spread:cashh/FY2024) $5 million [$5.0 million](term:facility)", SPREAD)
        t = tally(rs)
        self.assertEqual((t["read"], t["tied"], t["unresolved"], t["untied"], t["term"], t["flagged"], t["checked"]), (4, 1, 1, 1, 1, 2, 3))


if __name__ == "__main__":
    unittest.main()
