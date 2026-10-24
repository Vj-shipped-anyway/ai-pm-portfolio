import unittest
from dataclasses import replace

import _bootstrap  # noqa: F401
import shadow_score as ss


def P(cid, outcome="A", value="", conf=0.95, segment="s", day=0):
    return {"case_id": cid, "segment": segment, "day": day, "outcome": outcome, "value": value, "conf": conf if outcome else None}


def O(cid, outcome="A", value="", reviewer="r1"):
    return {"case_id": cid, "outcome": outcome, "value": value, "reviewer": reviewer}


def result(proposals, outcomes, rules=None):
    rules = rules or ss.Rules()
    s = ss.score(proposals, outcomes, rules)
    return s, ss.evaluate(s, rules)


def by_id(checks):
    return {c["id"]: c for c in checks}


class JudgeTests(unittest.TestCase):
    def test_four_kinds(self):
        self.assertEqual(ss.judge(P("1"), O("1")), "agree")
        self.assertEqual(ss.judge(P("1", "A"), O("1", "B")), "disagree_outcome")
        self.assertEqual(ss.judge(P("1", "A", "5.00"), O("1", "A", "6.00")), "disagree_value")
        self.assertEqual(ss.judge(P("1", ""), O("1")), "abstained")

    def test_values_compare_as_numbers_when_both_parse(self):
        self.assertTrue(ss.same_value("12.50", "12.5"))
        self.assertFalse(ss.same_value("12.5", "12.6"))
        self.assertFalse(ss.same_value("", "0"))
        self.assertFalse(ss.same_value("abc", "abd"))
        self.assertTrue(ss.same_value("", ""))

    def test_wilson_interval(self):
        lo, hi = ss.wilson(50, 100)
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)
        self.assertAlmostEqual(ss.wilson(0, 10)[0], 0.0, places=9)


class JoinTests(unittest.TestCase):
    def test_pending_and_orphans_are_counted_not_scored(self):
        s, _ = result([P("1"), P("2"), P("3")], [O("1"), O("9")])
        self.assertEqual((s["matched"], s["pending"], s["orphans"]), (1, 2, 1))

    def test_no_shared_case_id_is_an_error_not_a_zero(self):
        with self.assertRaises(ss.InputError) as cm:
            ss.score([P("1")], [O("2")], ss.Rules())
        self.assertIn("no case_id appears in both files", str(cm.exception))

    def test_abstentions_count_as_misses_in_the_all_cases_rate(self):
        s, _ = result([P("1"), P("2", ""), P("3"), P("4")], [O("1"), O("2"), O("3"), O("4")])
        self.assertEqual((s["agree"], s["proposed"], s["abstained"]), (3, 3, 1))
        self.assertEqual(s["headline"], 1.0)
        self.assertEqual(s["end_to_end"], 0.75)

    def test_majority_ties_break_alphabetically(self):
        s, _ = result([P("1", "B"), P("2", "A")], [O("1", "B"), O("2", "A")])
        self.assertEqual(s["majority_label"], "A")


class GroupTests(unittest.TestCase):
    def rows(self, n, agree, segment):
        props = [P(f"{segment}{i}", "A", segment=segment) for i in range(n)]
        outs = [O(f"{segment}{i}", "A" if i < agree else "B") for i in range(n)]
        return props, outs

    def test_small_group_under_the_floor_is_too_few_not_below(self):
        p, o = self.rows(5, 2, "tiny")
        s, checks = result(p, o)
        g = s["by_segment"][0]
        self.assertEqual(g["status"], "too_few")
        self.assertEqual(by_id(checks)["C07"]["result"], "SKIP")

    def test_large_group_under_the_floor_fails_the_check(self):
        p, o = self.rows(40, 30, "big")
        s, checks = result(p, o)
        self.assertEqual(s["by_segment"][0]["status"], "below")
        self.assertEqual(by_id(checks)["C07"]["result"], "FAIL")

    def test_large_group_over_the_floor_passes(self):
        p, o = self.rows(40, 38, "big")
        _, checks = result(p, o)
        self.assertEqual(by_id(checks)["C07"]["result"], "PASS")

    def test_week_comes_from_the_day_field(self):
        s, _ = result([P("1", day=6), P("2", day=7), P("3", day=14)], [O("1"), O("2"), O("3")])
        self.assertEqual([g["name"] for g in s["by_week"]], ["0", "1", "2"])

    def test_groups_come_from_the_segment_field_not_from_the_case_id(self):
        p = [P("AA-1", segment="x"), P("AA-2", segment="y")]
        s, _ = result(p, [O("AA-1"), O("AA-2")])
        self.assertEqual([g["name"] for g in s["by_segment"]], ["x", "y"])


class CheckTests(unittest.TestCase):
    def test_risky_check_is_skipped_and_says_why_without_pairs(self):
        _, checks = result([P("1", "A")], [O("1", "B")])
        c = by_id(checks)["C06"]
        self.assertEqual(c["result"], "SKIP")
        self.assertIn("no --risky pairs", c["detail"])

    def test_risky_pairs_are_counted_in_one_direction_only(self):
        rules = replace(ss.Rules(), risky=(("A", "B"),))
        s, _ = result([P("1", "A"), P("2", "B")], [O("1", "B"), O("2", "A")], rules)
        self.assertEqual(s["risky"], 1)

    def test_class_coverage_is_skipped_when_no_class_is_big_enough(self):
        _, checks = result([P("1")], [O("1")])
        self.assertEqual(by_id(checks)["C03"]["result"], "SKIP")

    def test_reviewer_gap_fails_when_one_reviewer_is_far_below_the_rest(self):
        props = [P(f"a{i}") for i in range(40)] + [P(f"b{i}") for i in range(40)]
        outs = [O(f"a{i}", "A", reviewer="r1") for i in range(40)]
        outs += [O(f"b{i}", "A" if i < 24 else "B", reviewer="r2") for i in range(40)]
        s, checks = result(props, outs)
        c = by_id(checks)["C10"]
        self.assertEqual(c["result"], "FAIL")
        self.assertIn("reviewer r2", c["detail"])
        self.assertEqual({g["name"]: g["status"] for g in s["by_reviewer"]}, {"r1": "ok", "r2": "below"})

    def test_reviewer_check_is_skipped_with_one_reviewer(self):
        _, checks = result([P(f"{i}") for i in range(40)], [O(f"{i}") for i in range(40)])
        self.assertEqual(by_id(checks)["C10"]["result"], "SKIP")

    def test_clear_when_every_check_passes(self):
        n = 400
        props = [P(f"c{i}", "A" if i % 2 else "B", segment="s%d" % (i % 2), day=i // 8) for i in range(n)]
        outs = [O(f"c{i}", "A" if i % 2 else "B", reviewer="r%d" % (i % 2)) for i in range(n)]
        s, checks = result(props, outs)
        self.assertEqual([c["id"] for c in checks if c["result"] == "FAIL"], [])
        self.assertEqual(ss.decide(checks), "CLEAR")

    def test_confidence_band_check_uses_the_stated_floor(self):
        props = [P(f"{i}", conf=0.95) for i in range(40)]
        outs = [O(f"{i}", "A" if i < 30 else "B") for i in range(40)]
        _, checks = result(props, outs)
        self.assertEqual(by_id(checks)["C09"]["result"], "FAIL")


if __name__ == "__main__":
    unittest.main()
