"""The three briefs project 26 StepScout writes in its step 4, kept as a snapshot in briefs/stepscout_snapshot/.
They are not hand-written. The validator must accept the shape StepScout emits."""

import json
import unittest

import _bootstrap  # noqa: F401
import support
from agentkit.brief import brief_warnings, check_brief, derive_config, load_brief
from agentkit.errors import UnsupportedStepError
from agentkit.kit import build_kit

SNAP = support.ROOT / "briefs" / "stepscout_snapshot"


def brief(n):
    return json.loads((SNAP / f"BB-00{n}.json").read_text(encoding="utf-8"))


class TestStepScoutSnapshot(unittest.TestCase):
    def test_the_snapshot_is_there_and_says_it_is_not_hand_written(self):
        self.assertEqual(sorted(p.name for p in SNAP.glob("BB-*.json")), ["BB-001.json", "BB-002.json", "BB-003.json"])
        text = (SNAP / "README.md").read_text(encoding="utf-8")
        self.assertIn("snapshot", text)
        self.assertIn("not hand-written", text)

    def test_all_three_validate(self):
        for n in (1, 2, 3):
            self.assertEqual(check_brief(brief(n)), [], f"BB-00{n}")
            self.assertEqual(load_brief(SNAP / f"BB-00{n}.json")["brief_id"], f"BB-00{n}")

    def test_bb001_validates_and_its_shape_is_accepted(self):
        cfg = derive_config(brief(1))
        self.assertEqual(cfg.steps, ("S03", "S04", "S05"))
        self.assertEqual(cfg.unsupported_steps, ())
        kit = build_kit(support.tiny_world(), brief(1))
        self.assertEqual(kit.config.brief_id, "BB-001")

    def test_bb001_has_no_s01_so_a_case_goes_back_to_the_human_queue_with_a_clear_reason(self):
        kit = build_kit(support.tiny_world(), brief(1))
        res = kit.orchestrator.run_case("G01")
        self.assertEqual((res.route, res.reason_kind), ("human_queue", "prerequisite_missing"))
        self.assertIn("earlier step", res.reason)
        self.assertEqual(kit.env.call_log, [])          # nothing reached a system

    def test_bb002_validates_with_an_unsupported_step_warning_and_is_refused_at_run_time(self):
        b = brief(2)
        self.assertEqual(check_brief(b), [])
        self.assertTrue(any("unsupported step 'S14'" in w for w in brief_warnings(b)))
        with self.assertRaises(UnsupportedStepError) as cm:
            derive_config(b)
        self.assertIn("S14", str(cm.exception))
        with self.assertRaises(UnsupportedStepError):
            build_kit(support.tiny_world(), b)
        self.assertEqual(derive_config(b, allow_unsupported=True).unsupported_steps, ("S14",))

    def test_bb002_four_eyes_control_names_s09_outside_the_pack(self):
        cfg = derive_config(brief(2), allow_unsupported=True)
        self.assertIn("S09", cfg.four_eyes)
        self.assertNotIn("S09", cfg.steps)

    def test_bb003_validates_and_keeps_the_resubmit_behind_an_s09_approval(self):
        b = brief(3)
        self.assertEqual(check_brief(b), [])
        cfg = derive_config(b)
        self.assertEqual(cfg.approval_required, {"S10": "S09"})
        self.assertNotIn("S09", cfg.steps)
        self.assertIn("S10", cfg.four_eyes)

    def test_removing_the_s10_approval_rule_from_bb003_makes_it_invalid(self):
        b = brief(3)
        b["controls"]["four_eyes"] = []
        self.assertTrue(any("needs a four-eyes entry for S09" in x for x in check_brief(b)))

    def test_a_shape_problem_in_a_stepscout_brief_is_still_a_problem(self):
        b = brief(1)
        b["tools"][0]["access"] = "admin"
        del b["estimate"]
        self.assertTrue(check_brief(b))


if __name__ == "__main__":
    unittest.main()
