import unittest

import _bootstrap  # noqa: F401
import support
from agentkit.brief import acceptance_tests, derive_config, evaluate_acceptance
from agentkit.handoff import build_runbook, exit_status, monitoring_signals, split_id

IDS = [g["id"] for g in support.golden()]


class TestHandoff(unittest.TestCase):
    def setUp(self):
        self.cfg = derive_config(support.brief())

    def test_split_id(self):
        self.assertEqual(split_id("RB-01: Engage and release the kill switch"), ("RB-01", "Engage and release the kill switch"))
        self.assertEqual(split_id("no id here"), ("no id here", ""))

    def test_runbook_has_one_section_per_item_and_says_it_is_a_skeleton(self):
        text = build_runbook(self.cfg)
        for item in self.cfg.runbook_items:
            sid, _ = split_id(item)
            self.assertIn(f"## {sid} ", text)
        self.assertIn("SKELETON", text)
        self.assertIn("has not been run by anyone", text)
        self.assertIn("TO WRITE", text)
        self.assertIn(self.cfg.kill_switch, text)

    def test_runbook_names_the_monitoring_signals(self):
        text = build_runbook(self.cfg)
        for item in self.cfg.monitoring:
            self.assertIn(f"`{split_id(item)[0]}`", text)

    def test_monitoring_signals_are_computed_from_the_trace(self):
        k, _ = support.kit()
        res = k.orchestrator.run_all(IDS)
        sig = monitoring_signals(self.cfg, k.audit.events(), res, k.killswitch, agreement=0.97)
        self.assertEqual(set(sig), {split_id(m)[0] for m in self.cfg.monitoring})
        self.assertTrue(all(s["computable"] for s in sig.values()))
        self.assertEqual(sig["gate_queue_depth"]["value"], 6)
        self.assertEqual(sig["queue_return_rate"]["value"], round(4 / 14, 4))
        self.assertEqual(sig["kill_switch_state"]["value"], "released")
        self.assertEqual(sig["agreement_rate"]["value"], 0.97)

    def test_an_agreement_rate_that_was_not_supplied_is_not_computable(self):
        k, _ = support.kit()
        sig = monitoring_signals(self.cfg, k.audit.events(), k.orchestrator.run_all(IDS), k.killswitch)
        self.assertFalse(sig["agreement_rate"]["computable"])

    def test_exit_status_marks_live_criteria_as_not_evaluable_here(self):
        res = evaluate_acceptance(acceptance_tests(support.brief()), {"audit_completeness": 1.0,
                                                                      "silent_failures": 0})
        st = exit_status(self.cfg, res)
        self.assertEqual(len(st), len(self.cfg.exit_criteria))
        live = [s for s in st if s["criterion"].startswith(("limited rollout", "full rollout"))]
        self.assertEqual(len(live), 2)
        self.assertTrue(all(s["status"] == "not_evaluable_here" for s in live))
        sh = [s for s in st if s["criterion"].startswith("shadow: AC-03 and AC-04")][0]
        self.assertEqual(sh["status"], "pass")

    def test_a_failing_acceptance_test_fails_its_exit_criterion(self):
        res = evaluate_acceptance(acceptance_tests(support.brief()), {"audit_completeness": 0.9,
                                                                      "silent_failures": 0})
        sh = [s for s in exit_status(self.cfg, res) if s["criterion"].startswith("shadow: AC-03 and AC-04")][0]
        self.assertEqual((sh["status"], sh["failing"]), ("fail", ["AC-03"]))


if __name__ == "__main__":
    unittest.main()
