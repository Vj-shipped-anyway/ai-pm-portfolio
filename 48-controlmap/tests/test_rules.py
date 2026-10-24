import tempfile
import unittest

import _bootstrap  # noqa: F401
import controlmap as cm
from fixtures import AS_OF, CT_HEADER, OB_HEADER, TERMS_HEADER, control, write


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def run_rules(self, obligations, controls, terms, **kw):
        o = cm.load_obligations(write(self.dir.name, "o.csv", OB_HEADER, obligations))
        c = cm.load_controls(write(self.dir.name, "c.csv", CT_HEADER, controls), AS_OF)
        t = cm.load_terms(write(self.dir.name, "t.csv", TERMS_HEADER, terms))
        return cm.analyze(o, c, t, **kw)

    def status(self, controls, applies="credit_decision", **kw):
        res = self.run_rules([["OB-1", "human oversight", "s", applies]], controls, [["human oversight", "override log"]], **kw)
        return res, res["rows"][0]


class MatchingTests(Case):
    def test_phrase_in_description_and_in_name(self):
        _, r = self.status([control(name="Reviewer rota", desc="Keep an override log for every case.")])
        self.assertEqual(r["status"], "COVERED")
        _, r = self.status([control(name="Override log", desc="Nothing else.")])
        self.assertEqual(r["status"], "COVERED")

    def test_theme_names_compare_after_case_and_spacing(self):
        res = self.run_rules([["OB-1", "Human  Oversight", "s", "credit_decision"]], [control()], [["human oversight", "override log"]])
        self.assertEqual(res["rows"][0]["status"], "COVERED")

    def test_retired_control_is_skipped_and_named(self):
        _, r = self.status([control(status="retired")])
        self.assertEqual(r["status"], "UNCOVERED")
        self.assertEqual(r["skipped"], [{"control_id": "CT-1", "why": "retired"}])
        self.assertIn("CT-1 retired", cm.reason(r))

    def test_no_match_says_so(self):
        _, r = self.status([control(name="Fire drill", desc="Twice a year.")])
        self.assertEqual(r["status"], "UNCOVERED")
        self.assertIn('no active control in scope matches the theme "human oversight"', cm.reason(r))

    def test_unmapped_theme_is_not_a_gap(self):
        res = self.run_rules([["OB-1", "model retirement", "s", "credit_decision"]], [control()], [["human oversight", "override log"]])
        self.assertEqual(res["rows"][0]["status"], "UNMAPPED")
        self.assertEqual(res["counts"]["UNCOVERED"], 0)


class NegationTests(unittest.TestCase):
    def test_negators_within_three_words_deny_the_phrase(self):
        for text in ("This is not model monitoring.", "Runs without human review.", "There is no exception to human review.",
                     "It doesn't include human review.", "Staff cannot skip human review."):
            phrase = "model monitoring" if "monitoring" in text else "human review"
            self.assertEqual(cm.find_phrase([phrase], text), ("", phrase), text)

    def test_negator_four_words_back_does_not_deny(self):
        self.assertEqual(cm.find_phrase(["human review"], "No one doubts that this team does human review daily.")[0], "human review")

    def test_a_clear_mention_wins_over_a_denied_one(self):
        text = "There is no human review of till counts. Managers do a human review of exceptions."
        self.assertEqual(cm.find_phrase(["human review"], text), ("human review", ""))

    def test_negation_can_be_switched_off(self):
        self.assertEqual(cm.find_phrase(["model monitoring"], "This is not model monitoring.", negation=False)[0], "model monitoring")

    def test_phrase_must_match_whole_words(self):
        self.assertEqual(cm.find_phrase(["override log"], "An overrideslog file.")[0], "")


class ScopeAndFreshnessTests(Case):
    def test_scope_full_partial_none(self):
        _, r = self.status([control(scope="credit_decision;fraud_scoring")], applies="credit_decision;fraud_scoring")
        self.assertEqual((r["status"], r["links"][0]["coverage"]), ("COVERED", "full"))
        _, r = self.status([control(scope="credit_decision")], applies="credit_decision;fraud_scoring")
        self.assertEqual((r["status"], r["links"][0]["missing"]), ("PARTIAL", ["fraud_scoring"]))
        _, r = self.status([control(scope="doc_summary")], applies="credit_decision")
        self.assertEqual(r["status"], "UNCOVERED")
        self.assertIn("runs outside the scope", cm.reason(r))

    def test_freshness_boundary_is_inclusive(self):
        self.assertEqual(self.status([control(cycle=100, age=150)])[1]["status"], "COVERED")
        self.assertEqual(self.status([control(cycle=100, age=151)])[1]["status"], "STALE")

    def test_grace_is_a_parameter(self):
        self.assertEqual(self.status([control(cycle=100, age=151)], grace=2.0)[1]["status"], "COVERED")
        self.assertEqual(self.status([control(cycle=100, age=60)], grace=0.5)[1]["status"], "STALE")

    def test_no_evidence_is_stale_and_said(self):
        _, r = self.status([control(age=None)])
        self.assertEqual(r["status"], "STALE")
        self.assertIn("no evidence on file", cm.reason(r))

    def test_one_fresh_full_control_is_enough(self):
        _, r = self.status([control("CT-1", age=900), control("CT-2", age=5)])
        self.assertEqual(r["status"], "COVERED")
        self.assertIn("CT-2", cm.reason(r))
        self.assertIn("1 more control(s) match", cm.reason(r))

    def test_partial_with_fresh_evidence_is_still_partial(self):
        _, r = self.status([control("CT-1", scope="credit_decision", age=5), control("CT-2", scope="credit_decision", age=900)],
                           applies="credit_decision;customer_chat")
        self.assertEqual(r["status"], "PARTIAL")


class ViewTests(Case):
    def test_orphans_exclude_retired_and_linked_controls(self):
        res = self.run_rules([["OB-1", "human oversight", "s", "credit_decision"]],
                             [control("CT-1"), control("CT-2", name="Fire drill", desc="x"), control("CT-3", status="retired")],
                             [["human oversight", "override log"]])
        self.assertEqual(res["orphans"], ["CT-2"])

    def test_phrases_that_match_no_active_control_are_listed(self):
        res = self.run_rules([["OB-1", "human oversight", "s", "credit_decision"]], [control()],
                             [["human oversight", "override log"], ["human oversight", "second look"]])
        self.assertEqual(res["unmatched_phrases"], ["human oversight: second look"])

    def test_one_request_per_stale_control_across_obligations(self):
        res = self.run_rules([["OB-1", "human oversight", "s", "credit_decision"], ["OB-2", "human oversight", "s", "credit_decision"]],
                             [control("CT-1", age=900)], [["human oversight", "override log"]])
        self.assertEqual(res["requests"], ["CT-1"])
        self.assertEqual(res["stale_obligations"], 2)


if __name__ == "__main__":
    unittest.main()
