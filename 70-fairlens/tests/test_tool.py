"""Unit tests for the six tests, on small hand-built portfolios."""
import unittest

import _bootstrap  # noqa: F401
import fairlens_pack as fp


def make(rows, proxy=True, reasons=False):
    """rows: (group, score, bad, proxy_points, reasons tuple)"""
    return fp.Data(sorted({r[0] for r in rows}), [r[0] for r in rows], [float(r[1]) for r in rows], [r[2] for r in rows],
                   [float(r[3]) for r in rows] if proxy else [], "proxy" if proxy else "", [r[4] for r in rows] if reasons else [])


def proxy_portfolio(b_bad):
    """Group A: 10 approved at 110 with 20 proxy points. Group B: 4 approved at 105, 6 declined at 92, no proxy points.
    Removing the proxy (mean 10) moves the six declined B applicants from 92 to 102, above the cutoff of 100."""
    rows = [("A", 110, 0, 20, ())] * 10 + [("B", 105, 0, 0, ())] * 4 + [("B", 92, b_bad, 0, ())] * 6
    return make(rows)


class StatsTests(unittest.TestCase):
    def test_group_stats_hand_checked(self):
        d = proxy_portfolio(0)
        gs = fp.group_stats(d, d.scores, 100)
        self.assertEqual(gs["ref"], "A")
        self.assertAlmostEqual(gs["groups"]["B"]["rate"], 0.4)
        self.assertAlmostEqual(gs["min_air"], 0.4)
        self.assertAlmostEqual(gs["accuracy"], 14 / 20)

    def test_nobody_approved_is_none(self):
        d = proxy_portfolio(0)
        self.assertIsNone(fp.group_stats(d, d.scores, 1000))

    def test_reference_tie_breaks_alphabetically(self):
        d = make([("B", 10, 0, 0, ()), ("A", 10, 0, 0, ())])
        self.assertEqual(fp.group_stats(d, d.scores, 5)["ref"], "A")

    def test_interval_verdict(self):
        self.assertEqual(fp.interval_verdict(0.5, 0.79), "FAIL")
        self.assertEqual(fp.interval_verdict(0.7, 0.9), "REVIEW")
        self.assertEqual(fp.interval_verdict(0.8, 0.95), "PASS")

    def test_bootstrap_is_seeded(self):
        d = proxy_portfolio(0)
        a = fp.bootstrap(d, 100, "A", 200, 1)
        self.assertEqual(a, fp.bootstrap(d, 100, "A", 200, 1))
        lo, hi = a["intervals"]["B"]
        self.assertLessEqual(lo, hi)


class ProxyTests(unittest.TestCase):
    def test_proxy_with_no_value_in_outcomes_fails(self):
        d = proxy_portfolio(0)          # the six declined B applicants did not default
        t = fp.t4_proxy(d, fp.ablate(d, 100))
        self.assertEqual(t["verdict"], "FAIL")
        self.assertEqual((t["flip_in"], t["flip_out"]), (6, 0))
        self.assertAlmostEqual(t["after"], 1.0)

    def test_predictive_proxy_goes_to_review(self):
        d = proxy_portfolio(1)          # the six declined B applicants did default: the proxy was right about them
        t = fp.t4_proxy(d, fp.ablate(d, 100))
        self.assertEqual(t["verdict"], "REVIEW")
        self.assertGreater(t["cost_pts"], fp.ACCURACY_COST_MAX_PTS)

    def test_a_proxy_that_changes_nothing_passes(self):
        d = make([("A", 110, 0, 5, ())] * 10 + [("B", 110, 0, 5, ())] * 10)
        self.assertEqual(fp.t4_proxy(d, fp.ablate(d, 100))["verdict"], "PASS")

    def test_naming_counts_declines_that_turn_on_the_proxy(self):
        rows = [("A", 110, 0, 20, ("R1",))] * 10 + [("B", 105, 0, 0, ("R1",))] * 4
        rows += [("B", 95, 0, 0, ("R1", "R5"))] * 6 + [("B", 95, 0, 0, ("R1",))] * 6
        d = make(rows, reasons=True)
        ab = fp.ablate(d, 100)
        self.assertEqual(len(ab["flip_in"]), 12)
        t = fp.t6_naming(d, ab, "R5", True)
        self.assertEqual((t["count"], t["unnamed"]), (12, 6))
        self.assertEqual(t["verdict"], "FAIL")
        self.assertEqual(fp.t6_naming(d, ab, "R5", False)["verdict"], "REVIEW")      # capped when T4 passed

    def test_naming_with_few_declines_is_review_not_pass(self):
        rows = [("A", 110, 0, 20, ("R1",))] * 10 + [("B", 105, 0, 0, ("R1",))] * 4 + [("B", 92, 0, 0, ("R5",))] * 3
        d = make(rows, reasons=True)
        t = fp.t6_naming(d, fp.ablate(d, 100), "R5", True)
        self.assertEqual(t["verdict"], "REVIEW")
        self.assertIn("too few", t["numbers"])


class ReasonPairTests(unittest.TestCase):
    def pairs(self, other_reason):
        rows = [("A", 50 + i, 1, 0, ("R1",)) for i in range(20)] + [("B", 50 + i, 1, 0, (other_reason,)) for i in range(20)]
        rows += [("A", 200, 0, 0, ("R1",))] * 40
        return make(rows, proxy=False, reasons=True)

    def test_same_reasons_across_groups(self):
        d = self.pairs("R1")
        pr = fp.reason_pairs(d, 100, "A")
        self.assertEqual((pr["cross_pairs"], pr["cross_differ"], pr["control_differ"]), (20, 0, 0))
        self.assertEqual(fp.t5_pairs(pr, "A")["verdict"], "PASS")

    def test_different_top_reason_across_groups_fails(self):
        d = self.pairs("R2")
        pr = fp.reason_pairs(d, 100, "A")
        self.assertEqual((pr["cross_differ"], pr["control_differ"]), (20, 0))
        self.assertEqual(fp.t5_pairs(pr, "A")["verdict"], "FAIL")

    def test_too_few_pairs_is_review(self):
        d = make([("A", 50, 1, 0, ("R1",)), ("B", 50, 1, 0, ("R1",)), ("A", 200, 0, 0, ("R1",))], proxy=False, reasons=True)
        t = fp.t5_pairs(fp.reason_pairs(d, 100, "A"), "A")
        self.assertEqual(t["verdict"], "REVIEW")
        self.assertIn("not enough", t["numbers"])


class SweepTests(unittest.TestCase):
    def test_sweep_finds_the_cutoff_that_clears_the_screen(self):
        # Group B scores 20 points below Group A everywhere, so a higher cutoff does not help; a lower one does
        rows = [("A", 100 + i, 0, 0, ()) for i in range(50)] + [("B", 80 + i, 0, 0, ()) for i in range(50)]
        d = make(rows, proxy=False)
        sw = fp.sweep(d, 110, 30)
        t = fp.t3_sweep(sw, 30, "FAIL")
        self.assertEqual(t["verdict"], "FAIL")
        self.assertIn("lowest AIR", t["numbers"])

    def test_screen_that_holds_with_headroom_passes(self):
        rows = [("A", 100 + i, 0, 0, ()) for i in range(50)] + [("B", 100 + i, 0, 0, ()) for i in range(50)]
        d = make(rows, proxy=False)
        t = fp.t3_sweep(fp.sweep(d, 110, 30), 30, "PASS")
        self.assertEqual(t["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
