import unittest

import _bootstrap  # noqa: F401
import inventory_check as ic
from _fixtures import AS_OF, kinds, rec, use


def run(records, rows, tests=("coverage",)):
    return ic.check(records, rows, AS_OF, tests=tests)


class CoverageTests(unittest.TestCase):
    def test_usage_with_no_record_is_named_with_its_calls(self):
        got = run([rec()], [use(), use(system_id="scratch-bot", calls=412)])
        self.assertEqual([(f["system_id"], f["kind"], f["severity"]) for f in got], [("scratch-bot", "unregistered_system", "fail")])
        self.assertIn("412 calls", got[0]["message"])

    def test_ids_match_exactly_and_not_by_prefix_or_case(self):
        got = run([rec(system_id="AI-1")], [use(system_id="AI-1"), use(system_id="AI-1-test"), use(system_id="ai-1")])
        self.assertEqual(sorted(f["system_id"] for f in got), ["AI-1-test", "ai-1"])

    def test_rows_with_no_system_id_are_reported_not_dropped(self):
        got = run([rec()], [use(), use(system_id="", calls=500), use(system_id="", calls=700)])
        self.assertEqual([(f["kind"], f["severity"]) for f in got], [("untagged_traffic", "review")])
        self.assertIn("2 usage rows with 1200 calls", got[0]["message"])

    def test_retired_system_seen_within_the_window_is_flagged(self):
        r = rec(status="retired")
        self.assertEqual(kinds(run([r], [use(last=ic.RETIRED_QUIET_DAYS)])), ["retired_still_running"])
        self.assertEqual(run([r], [use(last=ic.RETIRED_QUIET_DAYS + 1)]), [])
        self.assertEqual(run([r], []), [])

    def test_production_idle_boundary(self):
        self.assertEqual(run([rec()], [use(last=ic.IDLE_DAYS)]), [])
        got = run([rec()], [use(last=ic.IDLE_DAYS + 1)])
        self.assertEqual([(f["kind"], f["severity"]) for f in got], [("no_traffic", "review")])

    def test_production_with_no_row_at_all_says_so(self):
        got = run([rec(), rec(system_id="AI-2")], [use(system_id="AI-2")])
        self.assertEqual([(f["system_id"], f["kind"]) for f in got], [("AI-1", "no_traffic")])
        self.assertIn("no usage rows", got[0]["message"])

    def test_systems_not_in_production_may_be_quiet(self):
        for status in ("development", "pilot"):
            with self.subTest(status=status):
                self.assertEqual(run([rec(status=status)], [use(last=200)]), [])
                self.assertEqual(run([rec(status=status)], []), [])

    def test_a_duplicate_record_is_not_checked_twice(self):
        got = run([rec(), rec()], [use(last=200)])
        self.assertEqual(kinds(got), ["no_traffic"])

    def test_no_usage_file_means_no_coverage_findings(self):
        self.assertEqual(run([rec(status="retired"), rec(system_id="AI-2")], None), [])

    def test_the_tests_argument_selects_what_runs(self):
        records = [rec(business_owner="TBD", last_reviewed="2020-01-01")]
        rows = [use(last=200), use(system_id="ghost")]
        self.assertEqual(sorted({f["test"] for f in run(records, rows, tests=ic.TESTS)}), ["completeness", "coverage", "staleness"])
        self.assertEqual({f["test"] for f in run(records, rows, tests=("staleness",))}, {"staleness"})
        self.assertEqual({f["test"] for f in run(records, rows, tests=("completeness",))}, {"completeness"})

    def test_findings_come_back_in_a_stable_order(self):
        records = [rec(system_id="AI-2", business_owner="TBD"), rec(system_id="AI-1", last_reviewed="2020-01-01")]
        rows = [use(system_id="AI-1"), use(system_id="AI-2"), use(system_id="zeta"), use(system_id="", model="m")]
        a = run(records, rows, tests=ic.TESTS)
        b = run(list(reversed(records)), list(reversed(rows)), tests=ic.TESTS)
        self.assertEqual(a, b)
        self.assertEqual(a[-1]["kind"], "untagged_traffic")

    def test_notes_say_what_did_not_run_or_match(self):
        self.assertIn("no usage file", ic.notes_for([rec()], None)[0])
        self.assertIn("no usage row matches", ic.notes_for([rec()], [use(system_id="other")])[0])
        self.assertEqual(ic.notes_for([rec()], [use()]), [])

    def test_decision_is_the_worst_severity(self):
        self.assertEqual(ic.decide([]), "PASS")
        self.assertEqual(ic.decide([{"severity": "review"}]), "REVIEW")
        self.assertEqual(ic.decide([{"severity": "review"}, {"severity": "fail"}]), "FAIL")


if __name__ == "__main__":
    unittest.main()
