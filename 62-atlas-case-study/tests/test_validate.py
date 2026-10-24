import copy
import unittest

import _bootstrap  # noqa: F401
import atlas_case_study as t
from test_build import bundle, storm


def good():
    calls = storm(20, cost=6.0)
    calls[0]["response_flag"] = "instruction_like"
    return copy.deepcopy(t.build_study(bundle(calls), reporter="Team A")[0])


def problems(doc):
    return t.lint_study(doc)[0]


class LintTests(unittest.TestCase):
    def test_a_built_draft_is_clean(self):
        self.assertEqual(problems(good()), [])

    def test_missing_required_fields(self):
        for k in t.STUDY_REQUIRED:
            d = good()
            del d["study"][k]
            self.assertIn("study: missing %s" % k, problems(d))

    def test_no_study_object(self):
        self.assertEqual(problems({}), ["study: missing or not an object"])
        self.assertEqual(problems({"study": []}), ["study: missing or not an object"])

    def test_enums(self):
        d = good()
        d["study"]["incident-date-granularity"] = "DAY"
        d["study"]["case-study-type"] = "attack"
        self.assertEqual(len(problems(d)), 2)

    def test_incident_needs_a_reporter_but_an_exercise_does_not(self):
        d = good()
        del d["study"]["reporter"]
        self.assertIn("study.reporter: required for an incident", problems(d))
        d["study"]["case-study-type"] = "exercise"
        self.assertEqual(problems(d), [])

    def test_unknown_key_in_study_and_step(self):
        d = good()
        d["study"]["severity"] = "high"
        d["study"]["procedure"][0]["note"] = "x"
        self.assertEqual(len(problems(d)), 2)

    def test_id_patterns(self):
        d = good()
        d["study"]["procedure"][0]["technique"] = "T0029"
        d["study"]["procedure"][1]["tactic"] = "AML.TA11"
        d["study"]["id"] = "CS1"
        self.assertEqual(len(problems(d)), 3)
        d = good()
        d["study"]["procedure"][0]["technique"] = "AML.T0051.001"
        d["study"]["id"] = "AML.CS0042"
        self.assertEqual(problems(d), [])

    def test_dates(self):
        for bad in ("2026-02-30", "03/01/2026", "2026-03-01T10:00", 20260301):
            d = good()
            d["study"]["incident-date"] = bad
            self.assertTrue(problems(d), bad)
        d = good()
        d["study"]["incident-date"] = "2026-03-01T10:00:00Z"
        self.assertEqual(problems(d), [])

    def test_procedure_shape(self):
        for bad in ([], "steps", [1], [{"tactic": "AML.TA0011"}]):
            d = good()
            d["study"]["procedure"] = bad
            self.assertTrue(problems(d), repr(bad))

    def test_references(self):
        d = good()
        d["study"]["references"] = [{"title": "A", "url": None}]
        self.assertEqual(problems(d), [])
        self.assertNotIn("references", t.lint_study(d)[1])
        d["study"]["references"] = [{"title": "A"}]
        self.assertEqual(len(problems(d)), 1)
        d["study"]["references"] = "x"
        self.assertEqual(len(problems(d)), 1)

    def test_todos_are_reported_not_failed(self):
        d = good()
        d["study"]["actor"] = "TODO(actor): later"
        probs, todos, _ = t.lint_study(d)
        self.assertEqual((probs, todos), ([], ["actor", "references"]))

    def test_leak_check_names_the_key(self):
        b = bundle(storm(20))
        d = good()
        d["study"]["summary"] += " Customer CUST_123456."
        self.assertEqual(t.lint_study(d, b)[2], ["customer_id"])
        d["study"]["summary"] = "digits only 123456"
        self.assertEqual(t.lint_study(d, b)[2], ["customer_id"])


class BundleTests(unittest.TestCase):
    def test_good_bundle_passes(self):
        t.check_bundle(bundle(storm(3)))

    def test_bad_bundles_raise_value_error_with_one_line(self):
        bad = []
        for mutate in (lambda b: b.pop("run"), lambda b: b["run"].update(cost_cap_usd=0), lambda b: b["run"].update(cost_cap_usd=True),
                       lambda b: b["run"].update(started_at="March"), lambda b: b.update(calls=[]), lambda b: b.update(calls={}),
                       lambda b: b["calls"][0].update(args=[]), lambda b: b["calls"][0].update(cost_usd=-1),
                       lambda b: b["calls"][0].update(cost_usd=float("nan")), lambda b: b["calls"][0].update(response_kind=5),
                       lambda b: b.update(identifier_keys="customer_id"), lambda b: b["calls"].append("x")):
            b = bundle(storm(3))
            mutate(b)
            bad.append(b)
        bad += [[], "x", None, 3]
        for b in bad:
            with self.assertRaises(ValueError) as cm:
                t.check_bundle(b)
            self.assertNotIn("\n", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
