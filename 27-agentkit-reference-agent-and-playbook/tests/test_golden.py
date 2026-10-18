import unittest

import _bootstrap  # noqa: F401
import support


class TestGoldenCases(unittest.TestCase):
    def test_each_golden_case_ends_where_the_fixture_says(self):
        k, _ = support.kit()
        for g in support.golden():
            with self.subTest(g["id"], desc=g["desc"]):
                r = k.orchestrator.run_case(g["id"])
                self.assertEqual((r.route, r.proposed_outcome, r.state), (g["route"], g["outcome"], g["state"]))

    def test_there_are_fourteen_and_they_cover_every_route(self):
        gs = support.golden()
        self.assertEqual(len(gs), 14)
        self.assertEqual({g["route"] for g in gs}, {"auto", "to_person", "human_queue"})

    def test_a_golden_correction_is_the_advised_value(self):
        k, _ = support.kit()
        r = k.orchestrator.run_case("G01")
        self.assertEqual(r.correction["new"], support.RIGHT)
        self.assertEqual(r.correction["field"], "beneficiary_account")
        self.assertTrue(r.correction["stub"])

    def test_the_same_cases_in_a_different_order_end_in_the_same_place(self):
        k1, _ = support.kit()
        k2, _ = support.kit()
        ids = [g["id"] for g in support.golden() if g["id"] != "G13"]
        a = {r.case_id: (r.route, r.state) for r in k1.orchestrator.run_all(ids)}
        b = {r.case_id: (r.route, r.state) for r in k2.orchestrator.run_all(list(reversed(ids)))}
        self.assertEqual(a, b)

    def test_every_golden_case_leaves_a_decision_for_each_step_it_ran_or_skipped(self):
        k, _ = support.kit()
        for g in support.golden():
            k.orchestrator.run_case(g["id"])
            steps = [e["step"] for e in k.audit.events(g["id"]) if e["kind"] == "decision"]
            self.assertEqual(len(steps), k.orchestrator.expected_trace()[g["id"]]["steps"], g["id"])


if __name__ == "__main__":
    unittest.main()
