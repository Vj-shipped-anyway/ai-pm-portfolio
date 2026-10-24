import unittest

import _bootstrap  # noqa: F401
import eval_gate as eg

PIN = "vendor-a-20260101"


def probes(n_high=4, n_low=6):
    out = [{"probe_id": "H%d" % i, "severity": "high", "baseline_rate": 1.0} for i in range(n_high)]
    out += [{"probe_id": "L%d" % i, "severity": "low", "baseline_rate": 1.0} for i in range(n_low)]
    return out


def rows(ps, passes=None, served=None):
    passes, served = passes or {}, served or {}
    return [{"probe_id": p["probe_id"], "passes": passes.get(p["probe_id"], 10), "trials": 10,
             "served_model": served.get(p["probe_id"], PIN)} for p in ps]


def kinds(result):
    return [f["kind"] for f in result["findings"]]


class GateTests(unittest.TestCase):
    def test_clean_run_is_allowed(self):
        ps = probes()
        r = eg.evaluate(ps, rows(ps), PIN)
        self.assertEqual((r["decision"], r["findings"], r["drop"]), ("ALLOW", [], 0.0))

    def test_one_probe_on_another_snapshot_blocks(self):
        ps = probes()
        r = eg.evaluate(ps, rows(ps, served={"L3": "vendor-a-20260102"}), PIN)
        self.assertEqual((r["decision"], kinds(r), r["off_pin"]), ("BLOCK", ["snapshot_changed"], 1))
        self.assertIn("1 of 10 probes", r["findings"][0]["message"])

    def test_snapshot_ids_are_compared_as_exact_strings(self):
        ps = probes()
        for other in ("Vendor-A-20260101", "vendor-a-20260101-b", "vendor-a-2026010"):
            r = eg.evaluate(ps, rows(ps, served={"H0": other}), PIN)
            self.assertEqual(r["decision"], "BLOCK", other)

    def test_two_foreign_ids_give_two_findings_in_sorted_order(self):
        ps = probes()
        r = eg.evaluate(ps, rows(ps, served={"L0": "zzz", "L1": "aaa"}), PIN)
        self.assertEqual(kinds(r), ["snapshot_changed", "snapshot_changed"])
        self.assertIn("aaa", r["findings"][0]["message"])

    def test_the_pin_is_what_the_caller_says(self):
        ps = probes()
        r = eg.evaluate(ps, rows(ps, served={p["probe_id"]: "vendor-a-20260520" for p in ps}), "vendor-a-20260520")
        self.assertEqual(r["decision"], "ALLOW")

    def test_unscored_high_probe_blocks_and_unscored_low_probe_reviews(self):
        ps = probes()
        r = eg.evaluate(ps, [x for x in rows(ps) if x["probe_id"] != "H0"], PIN)
        self.assertEqual((r["decision"], kinds(r)), ("BLOCK", ["unscored_probes"]))
        r = eg.evaluate(ps, [x for x in rows(ps) if x["probe_id"] != "L0"], PIN)
        self.assertEqual((r["decision"], kinds(r)), ("REVIEW", ["unscored_probes"]))
        self.assertIn("1 of 10 probes have no result (L0); 0 of them high severity", r["findings"][0]["message"])

    def test_overall_drop_thresholds(self):
        ps = probes(n_high=0, n_low=10)
        for n_lower, expect in ((2, "ALLOW"), (3, "ALLOW"), (4, "REVIEW"), (5, "REVIEW"), (6, "BLOCK")):
            lowered = {"L%d" % i: 9 for i in range(n_lower)}
            self.assertEqual(eg.evaluate(ps, rows(ps, lowered), PIN)["decision"], expect, n_lower)

    def test_drop_thresholds_can_be_moved(self):
        ps = probes(n_high=0, n_low=10)
        lowered = {"L%d" % i: 9 for i in range(4)}
        self.assertEqual(eg.evaluate(ps, rows(ps, lowered), PIN, review_drop=0.05, block_drop=0.08)["decision"], "ALLOW")

    def test_collapse_of_a_high_probe_blocks_even_when_the_mean_barely_moves(self):
        ps = probes(n_high=4, n_low=26)
        r = eg.evaluate(ps, rows(ps, {"H1": 4}), PIN)
        self.assertLess(r["drop"], 0.03)
        self.assertEqual((r["decision"], kinds(r)), ("BLOCK", ["probe_collapse"]))
        self.assertEqual(r["findings"][0]["probe"], "H1")

    def test_a_fall_just_short_of_the_collapse_line_does_not_collapse(self):
        ps = probes(n_high=4, n_low=26)
        self.assertNotIn("probe_collapse", kinds(eg.evaluate(ps, rows(ps, {"H1": 6}), PIN)))

    def test_collapse_applies_to_high_severity_only(self):
        ps = probes(n_high=4, n_low=26)
        r = eg.evaluate(ps, rows(ps, {"L1": 0}), PIN)
        self.assertNotIn("probe_collapse", kinds(r))

    def test_rows_for_unknown_probes_are_ignored_and_reported(self):
        ps = probes()
        extra = rows(ps) + [{"probe_id": "Z1", "passes": 0, "trials": 10, "served_model": "other"}]
        r = eg.evaluate(ps, extra, PIN)
        self.assertEqual((r["decision"], r["scored"]), ("ALLOW", 10))
        self.assertIn("1 result rows", r["notes"][0])

    def test_a_better_run_than_baseline_is_allowed(self):
        ps = [{"probe_id": "L0", "severity": "low", "baseline_rate": 0.5}]
        r = eg.evaluate(ps, rows(ps), PIN)
        self.assertEqual(r["decision"], "ALLOW")
        self.assertLess(r["drop"], 0)

    def test_a_four_point_drop_on_an_unchanged_id_is_review_not_block(self):
        ps = probes(n_high=0, n_low=10)
        r = eg.evaluate(ps, rows(ps, {"L%d" % i: 9 for i in range(4)}), PIN)
        self.assertEqual((r["decision"], r["off_pin"]), ("REVIEW", 0))


if __name__ == "__main__":
    unittest.main()
