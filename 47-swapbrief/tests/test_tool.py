"""Unit tests for src/swapbrief.py: validation, statistics, the decision rule."""
import unittest

import _bootstrap  # noqa: F401
from _fixtures import make_rows
import swapbrief as sb

PRICES = {"base": (0.003, 0.015), "cand": (0.003, 0.015)}


def run(rows, critical=(), resamples=200, seed=7, prices=PRICES):
    return sb.analyze(sb.build_pairs(rows, "old", "new"), prices, critical, resamples=resamples, seed=seed,
                      baseline="old", candidate="new")


class CleanTests(unittest.TestCase):
    def test_percent_and_control_characters(self):
        self.assertEqual(sb.clean("a%b\r\nc\x1bd\x7f"), "a%25b%0D%0Ac%1Bd%7F")

    def test_plain_text_unchanged(self):
        self.assertEqual(sb.clean("card_disputes (x)"), "card_disputes (x)")


class StatisticsTests(unittest.TestCase):
    def test_percentile(self):
        v = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertEqual(sb.percentile(v, 0.5), 3.0)
        self.assertEqual(sb.percentile(v, 0.0), 1.0)
        self.assertEqual(sb.percentile(v, 1.0), 5.0)
        self.assertAlmostEqual(sb.percentile(v, 0.875), 4.5)

    def test_percentile_single_value(self):
        self.assertEqual(sb.percentile([9.0], 0.95), 9.0)

    def test_slice_status(self):
        f = sb.slice_status
        self.assertEqual(f(-0.08, -0.12, -0.03, 0.05, 0.10), "REGRESSED")
        self.assertEqual(f(-0.02, -0.04, -0.01, 0.05, 0.10), "WATCH")        # confirmed but small
        self.assertEqual(f(-0.07, -0.15, 0.01, 0.05, 0.10), "WATCH")         # large but unconfirmed
        self.assertEqual(f(0.04, 0.01, 0.07, 0.05, 0.10), "IMPROVED")
        self.assertEqual(f(0.00, -0.02, 0.02, 0.05, 0.10), "OK")
        self.assertEqual(f(0.03, -0.09, 0.15, 0.05, 0.10), "INCONCLUSIVE")   # wide and reaches past the tolerance
        self.assertEqual(f(0.03, -0.04, 0.10, 0.05, 0.10), "OK")             # narrow enough

    def test_ratio_status(self):
        f = sb.ratio_status
        self.assertEqual(f(1.40, 1.30, 1.05, 1.25), "BLOCK")
        self.assertEqual(f(1.40, 1.20, 1.05, 1.25), "WATCH")
        self.assertEqual(f(1.20, 0.95, 1.05, 1.25), "OK")                    # point is high, interval includes 1.0
        self.assertEqual(f(1.02, 1.01, 1.05, 1.25), "OK")

    def test_headline_rule(self):
        self.assertEqual(sb.headline_rule(0.0), sb.GO)
        self.assertEqual(sb.headline_rule(-0.001), sb.NOGO)


class PairTests(unittest.TestCase):
    def test_pairs_by_item_and_counts_other_systems(self):
        rows = make_rows(40) + [dict(make_rows(40)[0], system="third")]
        pairs = sb.build_pairs(rows, "old", "new")
        self.assertEqual(len(pairs["item"]), 40)
        self.assertEqual(pairs["ignored"], 1)

    def test_same_system_twice(self):
        with self.assertRaises(sb.InputError):
            sb.build_pairs(make_rows(40), "old", "old")

    def test_unknown_system(self):
        with self.assertRaisesRegex(sb.InputError, "no rows for system"):
            sb.build_pairs(make_rows(40), "old", "missing")

    def test_duplicate_row(self):
        rows = make_rows(40)
        rows.append(dict(rows[0]))
        with self.assertRaisesRegex(sb.InputError, "twice"):
            sb.build_pairs(rows, "old", "new")

    def test_unpaired_item(self):
        rows = make_rows(40)[:-1]
        with self.assertRaisesRegex(sb.InputError, "do not appear for both"):
            sb.build_pairs(rows, "old", "new")

    def test_slice_must_agree(self):
        rows = make_rows(40)
        rows[1]["slice"] = "zzz"
        with self.assertRaisesRegex(sb.InputError, "in slice"):
            sb.build_pairs(rows, "old", "new")

    def test_bad_cells(self):
        for column, value in (("correct", "yes"), ("correct", "2"), ("input_tokens", "-3"), ("output_tokens", "1.5"),
                              ("latency_ms", "nan"), ("latency_ms", "0"), ("latency_ms", "fast"), ("slice", " "), ("item_id", "")):
            rows = make_rows(40)
            rows[0][column] = value
            with self.assertRaises(sb.InputError, msg=(column, value)):
                sb.build_pairs(rows, "old", "new")


class AnalyzeTests(unittest.TestCase):
    def test_identical_systems_get_go(self):
        r = run(make_rows())
        self.assertEqual(r["decision"], sb.GO)
        self.assertEqual(r["cost"]["ratio"], 1.0)
        self.assertEqual(r["latency"]["p95_ratio"], 1.0)
        self.assertEqual(len(r["triggers"]), 2)

    def test_longer_answers_block_on_cost(self):
        r = run(make_rows(out_mult=4.0))
        self.assertEqual(r["cost"]["status"], "BLOCK")
        self.assertEqual(r["decision"], sb.NOGO)

    def test_cheaper_tokens_can_still_cost_more(self):
        cheaper = {"base": (0.003, 0.015), "cand": (0.0024, 0.012)}
        r = run(make_rows(out_mult=4.0), prices=cheaper)
        self.assertGreater(r["cost"]["ratio"], 1.25)

    def test_slow_tail_blocks_on_p95(self):
        r = run(make_rows(lat_mult=2.0))
        self.assertAlmostEqual(r["latency"]["p95_ratio"], 2.0, places=1)
        self.assertEqual(r["latency"]["status"], "BLOCK")
        self.assertEqual(r["decision"], sb.NOGO)

    def test_critical_regression_blocks_and_standard_guards(self):
        rows = make_rows(drop_slice="a")
        crit = run(rows, critical=["a"])
        self.assertEqual(crit["decision"], sb.NOGO)
        self.assertTrue(any("critical" in x for x in crit["block_reasons"]))
        std = run(rows)
        self.assertEqual(std["decision"], sb.GUARD)
        self.assertTrue(any(t["metric"].startswith("accuracy in slice a") for t in std["triggers"]))

    def test_same_seed_same_brief_and_other_seed_same_point_estimates(self):
        rows = make_rows(out_mult=1.5, lat_mult=1.3)
        a, b, c = run(rows, seed=3), run(rows, seed=3), run(rows, seed=4)
        self.assertEqual(a, b)
        self.assertEqual(a["cost"]["ratio"], c["cost"]["ratio"])
        self.assertNotEqual(a["cost"]["lo"], c["cost"]["lo"])

    def test_unknown_critical_slice_is_an_error(self):
        with self.assertRaisesRegex(sb.InputError, "names no slice"):
            run(make_rows(), critical=["nope"])

    def test_too_few_pairs(self):
        with self.assertRaisesRegex(sb.InputError, "at least 30"):
            run(make_rows(20))

    def test_no_correct_answers(self):
        rows = make_rows(40)
        for r in rows:
            r["correct"] = "0"
        with self.assertRaisesRegex(sb.InputError, "fewer than"):
            run(rows)

    def test_hostile_slice_name_is_escaped_in_text(self):
        hostile = "x\n::error::pwned%"
        text = sb.render_text(run(make_rows(drop_slice=hostile, slice_a=hostile), critical=[hostile]))
        self.assertNotIn(hostile, text)
        self.assertFalse(any(line.startswith("::") for line in text.split("\n")))
        self.assertIn("x%0A::error::pwned%25", text)


class ExitCodeTests(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(sb.exit_code(sb.NOGO, "nogo"), 1)
        self.assertEqual(sb.exit_code(sb.GUARD, "nogo"), 0)
        self.assertEqual(sb.exit_code(sb.GUARD, "guardrails"), 1)
        self.assertEqual(sb.exit_code(sb.GO, "guardrails"), 0)
        self.assertEqual(sb.exit_code(sb.NOGO, "never"), 0)


if __name__ == "__main__":
    unittest.main()
