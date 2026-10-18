"""The four step scripts as a whole: the numbers the README, the app and the demo quote are pinned here.
If the data, the brief or the kit changes, these fail first, and the docs need the new numbers."""

import sys
import unittest

import _bootstrap  # noqa: F401
import support

sys.path.insert(0, str(support.ROOT / "src"))

import step_01_manual_handling as step1  # noqa: E402
import step_03_deficiencies_exposed as step3  # noqa: E402
import step_04_with_agentkit as step4  # noqa: E402
from agentkit.data_io import load_world  # noqa: E402


class TestStepNumbers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = load_world()
        cls.S = step4.compute(cls.world)

    def test_step1_baseline(self):
        r = step1.compute(self.world)
        self.assertEqual((r["cases"], r["hours_total"], r["minutes_mean"]), (600, 268.1, 26.8))
        self.assertEqual(r["outcome_mix"], {"DUPLICATE_CLOSED": 14, "ESCALATE_COMPLIANCE": 22, "RESUBMIT": 432,
                                            "RETURN_TO_ORIGINATOR": 132})

    def test_step3_deficiencies_are_measured(self):
        m = step3.measure(self.world)
        self.assertEqual((m["a"]["calls_outside"], m["a"]["write_calls_outside"]), (1040, 515))
        self.assertEqual((m["b"]["resubmissions"], m["b"]["with_approval"]), (515, 0))
        self.assertEqual(m["c"]["cases_failed_silently"], 52)
        self.assertEqual((m["d"]["decisions"], m["d"]["logged"]), (2753, 515))
        self.assertEqual((m["e"]["agree"], m["e"]["disagree"], m["e"]["no_outcome"]), (490, 101, 9))
        self.assertEqual(sum(v["covered"] for k, v in m["f"].items() if k != "artifacts"), 0)
        self.assertEqual(len(m["wrong_cases"]), 127)

    def test_step4_shadow_numbers(self):
        sc = self.S["shadow"]["score"]
        self.assertEqual((sc["agree"], sc["disagree"], sc["deferred"], sc["queued"]), (522, 26, 40, 12))
        self.assertEqual(sc["routes"], {"auto": 134, "to_person": 454, "human_queue": 12})
        self.assertEqual(sc["to_person_detail"], {"S07": 40, "S09": 388, "escalation": 26})
        self.assertEqual(sc["agreement_rate"], 0.9526)

    def test_step4_acceptance_results(self):
        res = {a["id"]: a["passed"] for a in self.S["acceptance"]}
        self.assertEqual(len(res), 9)
        self.assertEqual([k for k, v in res.items() if not v], ["AC-06"])

    def test_the_known_miss_is_present_and_counted(self):
        m = self.S["misses"]
        self.assertEqual(m["auto_handled_wrongly"]["n"], 15)
        self.assertEqual(m["auto_handled_wrongly"]["by_scenario"], {"fix_name_ambiguous": 9, "closed_successor": 6})
        self.assertEqual(m["drafted_agreed_with_rules_human_differed"]["n"], 6)
        self.assertEqual(m["watch_list_missed"]["n"], 1)

    def test_step4_enforcement_and_faults(self):
        p, f = self.S["probes"], self.S["fault"]["summary"]
        self.assertEqual((p["cases"], p["blocked_total"], p["executed_with_valid_approval"]), (388, 1164, 388))
        self.assertEqual(p["unapproved_in_ledger"], 0)
        self.assertEqual((f["rogue_attempted"], f["rogue_blocked"], f["executed_outside_scope"]), (4, 4, 0))
        self.assertEqual((f["transient_recovered_same_result"], f["transient_cases"]), (12, 12))
        self.assertEqual(f["persistent_to_human_queue"], f["persistent_cases"])

    def test_the_stepscout_snapshot_status(self):
        snap = {b["id"]: b for b in self.S["snapshot"]}
        self.assertEqual(sorted(snap), ["BB-001", "BB-002", "BB-003"])
        self.assertTrue(all(b["valid"] for b in snap.values()))
        self.assertEqual((snap["BB-001"]["config"], snap["BB-002"]["config"], snap["BB-003"]["config"]),
                         ("accepted", "refused", "accepted"))
        self.assertEqual(snap["BB-002"]["unsupported_steps"], ["S14"])

    def test_the_recorded_human_outcome_is_not_an_input_to_the_kit(self):
        import pathlib
        src = pathlib.Path(_bootstrap.SRC) / "agentkit"
        for name in ("orchestrator.py", "tools.py", "environment.py", "kit.py"):
            text = (src / name).read_text(encoding="utf-8")
            self.assertNotIn("human_outcome", text, name)
            self.assertNotIn("outcomes", text.replace("proposed_outcome", ""), name)
        for p in (src / "skills").glob("*.py"):
            self.assertNotIn("human_outcome", p.read_text(encoding="utf-8"), p.name)

    def test_the_utility_terms(self):
        u = self.S["utility"]
        self.assertEqual((u["script_wrong_cases"], u["kit_wrong_cases"]), (127, 15))
        self.assertEqual(round(u["avoided_per_quarter"]), 336)


if __name__ == "__main__":
    unittest.main()
