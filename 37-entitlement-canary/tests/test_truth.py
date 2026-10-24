"""The planted label of each pull request is the kind of change that was planted. These tests check that
the label and an exhaustive probe of the toy system agree, so the numbers in the steps are scored
against something that is true of the system and not against the canary rules."""
import unittest

import _bootstrap  # noqa: F401
from common import load_world, load_prs, pr_system, System, exhaustive_leaks


class PlantedTruthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = load_world()
        cls.prs = load_prs()

    def test_unchanged_main_leaks_nothing(self):
        self.assertEqual(exhaustive_leaks(System(self.world, {})), set())

    def test_leaking_kinds_leak_and_the_rest_do_not(self):
        self.assertEqual(len(self.prs), 50)
        for pr in self.prs:
            leaked = exhaustive_leaks(pr_system(self.world, pr))
            self.assertEqual(bool(leaked), pr["leaks"], (pr["pr_id"], pr["kind"], len(leaked)))

    def test_delegation_leaks_exactly_one_pair(self):
        for pr in self.prs:
            if pr["kind"] == "delegation_inherit":
                self.assertEqual(len(exhaustive_leaks(pr_system(self.world, pr))), 1, pr["pr_id"])

    def test_shared_cache_leaks_only_when_a_user_asks_after_another(self):
        pr = next(p for p in self.prs if p["kind"] == "shared_cache")
        first = pr_system(self.world, pr)
        doc = next(d for d in self.world["access"]["documents"] if not first.entitled("U001", d["doc_id"]))
        self.assertNotIn(doc["doc_id"], first.retrieve("U001", doc["title"]))
        opener = next(u for u in sorted(first.direct) if first.entitled(u, doc["doc_id"]))
        second = pr_system(self.world, pr)
        second.retrieve(opener, doc["title"])
        self.assertIn(doc["doc_id"], second.retrieve("U001", doc["title"]))


if __name__ == "__main__":
    unittest.main()
