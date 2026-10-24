from __future__ import annotations

import json
import os
import unittest

import _bootstrap  # noqa: F401
import scam_friction_sim as sim

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def pay(pid="P1", amount=50, usual=50, age=100, hour=12, call=0, device=0, is_scam=0, scenario="ordinary", ua=0.99, ue=0.99):
    return {"payment_id": pid, "amount": amount, "usual_amount": usual, "payee_age_days": age, "hour": hour,
            "call_active": call, "device_new": device, "is_scam": is_scam, "scenario": scenario, "u_abandon": ua, "u_evade": ue}


A = sim.check_assumptions({})


class ScoreTests(unittest.TestCase):
    def test_each_feature_adds_its_points(self):
        self.assertEqual(sim.risk_score(pay()), 0)
        self.assertEqual(sim.risk_score(pay(age=0)), 3)
        self.assertEqual(sim.risk_score(pay(age=5)), 1)
        self.assertEqual(sim.risk_score(pay(amount=100)), 1)
        self.assertEqual(sim.risk_score(pay(amount=150)), 2)
        self.assertEqual(sim.risk_score(pay(amount=1000, usual=1000)), 1)
        self.assertEqual(sim.risk_score(pay(call=1)), 2)
        self.assertEqual(sim.risk_score(pay(device=1)), 2)
        self.assertEqual(sim.risk_score(pay(hour=5)), 1)
        self.assertEqual(sim.risk_score(pay(hour=6)), 0)

    def test_tier_reads_features_only(self):
        features = {k: v for k, v in pay(age=0, amount=1000, usual=100, call=1).items()
                    if k in sim.PAYMENT_COLUMNS}
        self.assertEqual(sim.tier(features, sim.policy_score(8)), "HOLD")
        self.assertEqual(sim.tier(features, sim.policy_blanket(500)), "HOLD")
        self.assertEqual(sim.tier(features, sim.policy_none()), "PASS")

    def test_warn_band(self):
        pol = sim.policy_score(8, 6)
        self.assertEqual(sim.tier(pay(age=0, amount=150, call=1), pol), "WARN")
        self.assertEqual(sim.tier(pay(age=0, amount=150), pol), "PASS")

    def test_warn_must_sit_below_hold(self):
        with self.assertRaises(ValueError):
            sim.policy_score(5, 5)


class SimulateTests(unittest.TestCase):
    scam = dict(amount=1000, usual=100, age=0, call=1, is_scam=1, scenario="coached_live")

    def test_held_scam_is_stopped_when_the_draw_is_under_the_probability(self):
        r = sim.simulate([pay(ua=0.1, ue=0.9, **self.scam)], sim.policy_score(8), A)
        self.assertEqual((r["scam_stopped_n"], r["scam_stopped_value"]), (1, 1000))

    def test_draw_over_the_probability_lets_it_through(self):
        r = sim.simulate([pay(ua=0.5, ue=0.9, **self.scam)], sim.policy_score(8), A)
        self.assertEqual((r["scam_held_n"], r["scam_stopped_n"]), (1, 0))

    def test_coaching_cancels_the_stop(self):
        r = sim.simulate([pay(ua=0.1, ue=0.1, **self.scam)], sim.policy_score(8), A)
        self.assertEqual((r["scam_held_n"], r["scam_stopped_n"]), (1, 0))

    def test_no_coaching_when_no_scammer_is_in_touch(self):
        row = pay(ua=0.1, ue=0.0, amount=1000, usual=100, age=0, device=1, is_scam=1, scenario="takeover")
        r = sim.simulate([row], sim.policy_score(8), A)
        self.assertEqual(r["scam_stopped_n"], 1)

    def test_warning_has_a_fraction_of_the_effect(self):
        row = pay(ua=0.2, ue=0.9, **self.scam)
        self.assertEqual(sim.simulate([row], sim.policy_score(9, 8), A)["scam_stopped_n"], 0)
        row["u_abandon"] = 0.1
        self.assertEqual(sim.simulate([row], sim.policy_score(9, 8), A)["scam_stopped_n"], 1)

    def test_legit_hold_costs_minutes_value_and_maybe_the_payment(self):
        row = pay(amount=600, usual=100, age=0, ua=0.01)
        r = sim.simulate([row], sim.policy_score(5), A)
        self.assertEqual((r["legit_held"], r["legit_lost"], r["legit_minutes"], r["legit_value_delayed"]), (1, 1, 20, 600))

    def test_pass_costs_nothing(self):
        r = sim.simulate([pay()], sim.policy_score(5), A)
        self.assertEqual((r["legit_held"], r["legit_warned"], r["legit_minutes"]), (0, 0, 0))

    def test_unknown_scam_scenario_is_an_error(self):
        with self.assertRaises(ValueError):
            sim.simulate([pay(is_scam=1, scenario="mystery")], sim.policy_none(), A)

    def test_metrics_weight(self):
        r = sim.simulate([pay(amount=600, usual=100, age=0, ua=0.9), pay(pid="P2", ua=0.9),
                          pay(pid="P3", ua=0.1, ue=0.9, **self.scam)], sim.policy_score(5), A)
        m1, m10 = sim.metrics(r), sim.metrics(r, 10)
        self.assertEqual(m1["holds_per_stopped"], 1)
        self.assertEqual(m10["holds_per_stopped"], 10)
        self.assertAlmostEqual(m1["legit_held_pct"], m10["legit_held_pct"])

    def test_metrics_with_no_scam_has_no_stopped_rate(self):
        r = sim.simulate([pay()], sim.policy_none(), A)
        self.assertIsNone(sim.metrics(r)["stopped_pct"])
        self.assertIsNone(sim.metrics(r)["holds_per_stopped"])


class AssumptionTests(unittest.TestCase):
    def test_defaults_match_the_committed_file(self):
        with open(os.path.join(DATA, "assumptions.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), sim.DEFAULT_ASSUMPTIONS)

    def test_rejects_unknown_key_wrong_type_and_out_of_range(self):
        for bad in ({"coach_rte": 0.2}, {"coach_rate": "0.2"}, {"coach_rate": 1.5}, {"coach_rate": True}, {"hold_minutes": -1},
                    {"scam_scenarios": {}}, {"scam_scenarios": {"x": {"p_abandon": 0.1}}},
                    {"scam_scenarios": {"x": {"p_abandon": 0.1, "human_scammer": "yes"}}}, [], "text"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                sim.check_assumptions(bad)

    def test_clean_escapes_workflow_command_characters(self):
        s = sim.clean("a\r\nb%::error::x")
        self.assertEqual(s, "a%0D%0Ab%25::error::x")
        self.assertEqual(sim.clean("x" * 100), "x" * 60 + "...")
        self.assertNotIn("\x1b", sim.clean("a\x1b[31m"))


if __name__ == "__main__":
    unittest.main()
