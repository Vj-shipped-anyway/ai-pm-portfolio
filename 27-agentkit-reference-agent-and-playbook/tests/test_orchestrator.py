import unittest

import _bootstrap  # noqa: F401
import support
from agentkit import skills as skills_pkg
from agentkit.skills import SKILLS, Skill
from agentkit.skills.base import SkillResult


class TestOrchestrator(unittest.TestCase):
    def test_a_bug_in_a_skill_ends_in_the_human_queue_with_a_trace(self):
        original = SKILLS["S03"]
        SKILLS["S03"] = Skill("S03", "lookup_original_payment", (), lambda ctx: 1 / 0)
        try:
            k, _ = support.kit()
            r = k.orchestrator.run_case("G01")
        finally:
            SKILLS["S03"] = original
        self.assertEqual((r.route, r.reason_kind), ("human_queue", "unexpected_error"))
        self.assertIn("ZeroDivisionError", r.reason)
        self.assertIn("fallback", [e["kind"] for e in k.audit.events("G01")])

    def test_results_come_back_in_arrival_order(self):
        k, _ = support.kit()
        res = k.orchestrator.run_all(["G02", "G01", "G03"])
        self.assertEqual([r.case_id for r in res], ["G02", "G01", "G03"])

    def test_steps_that_do_not_apply_are_skipped_with_a_reason(self):
        k, _ = support.kit()
        r = k.orchestrator.run_case("G06")         # closed account: no repair
        self.assertEqual(r.steps_skipped, ["S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10"])
        skipped = [e for e in k.audit.events("G06") if e["detail"].get("decision") == "skipped"]
        self.assertTrue(all("no repair" in e["detail"]["rationale"] for e in skipped))

    def test_a_clear_match_skips_s07(self):
        k, _ = support.kit()
        r = k.orchestrator.run_case("G01")
        self.assertIn("S07", r.steps_skipped)

    def test_mode_comes_from_the_registry(self):
        k, _ = support.kit(mode="live")
        self.assertEqual(k.orchestrator.mode, "live")

    def test_a_bad_mode_is_refused(self):
        with self.assertRaises(ValueError):
            support.kit(mode="turbo")

    def test_to_dict_has_the_fields_the_apps_read(self):
        k, _ = support.kit()
        d = k.orchestrator.run_case("G01").to_dict()
        for key in ("case_id", "route", "state", "proposed_outcome", "correction", "steps_done", "tool_calls"):
            self.assertIn(key, d)

    def test_the_resubmit_skill_is_the_only_one_that_can_move_money(self):
        gateway_users = [s.step for s in SKILLS.values() if "payments_gateway" in s.tools]
        self.assertEqual(gateway_users, ["S10"])

    def test_every_skill_names_its_tools_and_they_are_in_the_brief(self):
        cfg = support.config()
        for s in SKILLS.values():
            for t in s.tools:
                self.assertIn(t, cfg.tool_scope, f"{s.step} uses {t}")


if __name__ == "__main__":
    unittest.main()
