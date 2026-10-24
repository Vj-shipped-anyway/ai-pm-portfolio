import datetime
import tempfile
import unittest

import _bootstrap  # noqa: F401
import _world as w
import deprecation_impact as di

AS_OF = datetime.date(2026, 9, 1)


class RiskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def analyze(self, usages, features=w.FEATURES, policy=None, only=None):
        w.write(self.tmp.name, "u.csv", w.USAGE_HEAD + usages)
        models = di.load_models(w.write(self.tmp.name, "m.csv", w.MODELS))
        aliases = di.load_aliases(w.write(self.tmp.name, "a.csv", w.ALIASES), models)
        feats = di.load_features(w.write(self.tmp.name, "f.csv", features))
        return di.analyze(feats, di.load_usages(self.tmp.name + "/u.csv", feats), models, aliases, AS_OF, policy or di.load_policy(None), only)

    def test_tier_boundaries(self):
        p = di.DEFAULT_POLICY
        self.assertEqual(di.tier_of(-1, 10, p), "PAST")
        self.assertEqual(di.tier_of(9, 10, p), "LATE")
        self.assertEqual(di.tier_of(10, 10, p), "TIGHT")
        self.assertEqual(di.tier_of(39, 10, p), "TIGHT")
        self.assertEqual(di.tier_of(40, 10, p), "ROOM")

    def test_lead_time_adds_up(self):
        f = {"criticality": "critical", "has_eval_set": "no"}
        self.assertEqual(di.lead_days(f, "judge", True, di.DEFAULT_POLICY), 60 + 30 + 14 + 45)
        self.assertEqual(di.lead_days({"criticality": "low", "has_eval_set": "yes"}, "primary", False, di.DEFAULT_POLICY), 14)

    def test_monthly_cost_by_hand(self):
        # 1000 calls x (1000 input tokens x $3 + 100 output tokens x $15) per million = $4.50
        self.assertEqual(di.monthly_cost(1000, 1000, 100, 3.0, 15.0), 4.5)

    def test_cost_on_the_successor_uses_its_price_and_the_token_factor(self):
        d = self.analyze(w.usage_line(1, "F1", "primary", "m-old@1"))["dependencies"][0]
        self.assertEqual(d["cost_now"], 4.5)
        # 1000 x (1000 x 1.10 x $2 + 100 x $10) per million = $3.20
        self.assertEqual((d["successor"], d["cost_after"]), ("m-new@2", 3.2))

    def test_a_fine_tune_has_no_priced_successor_and_a_longer_lead(self):
        res = self.analyze(w.usage_line(1, "F1", "primary", "ft-a"))
        d = res["dependencies"][0]
        self.assertIsNone(d["cost_after"])
        self.assertEqual(d["lead_days"], 60 + 45)
        self.assertEqual(res["unpriced"], 1)

    def test_an_already_retired_model_is_past(self):
        res = self.analyze(w.usage_line(1, "F1", "fallback", "dead@1"))
        self.assertEqual((res["decision"], res["dependencies"][0]["days_left"]), ("PAST", -184))

    def test_feature_that_sunsets_first_needs_no_move(self):
        feats = w.FEATURES.replace("F1,alpha,t,retail,critical,yes,", "F1,alpha,t,retail,critical,yes,2026-11-30")
        res = self.analyze(w.usage_line(1, "F1", "primary", "m-old@1"), feats)
        self.assertEqual(res["dependencies"][0]["tier"], "SUNSETS")
        self.assertEqual((res["cost_now"], res["unpriced"]), (0, 0))

    def test_feature_that_sunsets_after_still_has_to_move(self):
        feats = w.FEATURES.replace("F1,alpha,t,retail,critical,yes,", "F1,alpha,t,retail,critical,yes,2026-12-02")
        self.assertEqual(self.analyze(w.usage_line(1, "F1", "primary", "m-old@1"), feats)["dependencies"][0]["tier"], "ROOM")

    def test_feature_with_no_usage_row_is_listed_for_a_person(self):
        res = self.analyze(w.usage_line(1, "F1", "primary", "m-new@2"))
        names = sorted(d["feature_name"] for d in res["dependencies"])
        self.assertEqual(names, ["beta", "gamma"])
        self.assertTrue(all(d["verdict"] == "check" and d["role"] == "unknown" for d in res["dependencies"]))

    def test_calendar_lists_a_notice_that_no_feature_uses(self):
        res = self.analyze(w.usage_line(1, "F1", "primary", "m-old@1"))
        dead = [c for c in res["calendar"] if c["model_id"] == "dead@1"][0]
        self.assertEqual((dead["features"], dead["tier"]), (0, "CLEAR"))
        self.assertIn("no registered feature resolves to it", di.render_text(res))

    def test_calendar_is_sorted_by_retirement_date(self):
        dates = [c["retire_date"] for c in self.analyze("")["calendar"]]
        self.assertEqual(dates, sorted(dates))

    def test_model_filter_keeps_only_that_notice(self):
        res = self.analyze(w.usage_line(1, "F1", "primary", "m-old@1") + w.usage_line(2, "F2", "primary", "dead@1"), only="dead@1")
        self.assertEqual([c["model_id"] for c in res["calendar"]], ["dead@1"])
        self.assertEqual([d["feature_name"] for d in res["dependencies"] if d["verdict"] == "hit"], ["beta"])

    def test_model_filter_without_a_notice_is_an_error_not_an_empty_report(self):
        with self.assertRaises(ValueError):
            self.analyze("", only="m-new@2")

    def test_a_policy_file_changes_the_tier(self):
        u = w.usage_line(1, "F1", "primary", "m-old@1")
        base = self.analyze(u)["decision"]
        policy = di.load_policy(None)
        policy["lead_days"]["critical"] = 200
        self.assertEqual((base, self.analyze(u, policy=policy)["decision"]), ("ROOM", "LATE"))


if __name__ == "__main__":
    unittest.main()
