import unittest

import _bootstrap  # noqa: F401
import inventory_check as ic
from _fixtures import AS_OF, days_ago, kinds, rec, use


def run(r, rows=None):
    return ic.check([r], rows, AS_OF, tests=("staleness",))


class StalenessTests(unittest.TestCase):
    def test_review_exactly_on_cadence_passes_and_one_day_over_is_flagged(self):
        for tier, cadence in ic.CADENCE_DAYS.items():
            kw = dict(risk_tier=tier, evaluation_ref="EV-1", last_evaluated=days_ago(1).isoformat())
            with self.subTest(tier=tier):
                self.assertEqual(run(rec(last_reviewed=days_ago(cadence).isoformat(), **kw)), [])
                got = run(rec(last_reviewed=days_ago(cadence + 1).isoformat(), **kw))
                self.assertEqual(kinds(got), ["review_overdue"])
                self.assertEqual(got[0]["severity"], "review")

    def test_cadence_table_is_the_one_the_readme_names(self):
        self.assertEqual(ic.CADENCE_DAYS, {1: 365, 2: 270, 3: 180, 4: 90})

    def test_retired_systems_are_exempt(self):
        self.assertEqual(run(rec(status="retired", last_reviewed="2020-01-01")), [])

    def test_unknown_tier_or_date_is_left_to_the_completeness_tests(self):
        self.assertEqual(run(rec(risk_tier="high", last_reviewed="2020-01-01")), [])
        self.assertEqual(run(rec(last_reviewed="last spring")), [])

    def test_evaluation_cadence_applies_to_production_from_tier_two(self):
        old = days_ago(ic.CADENCE_DAYS[2] + 1).isoformat()
        self.assertEqual(kinds(run(rec(last_evaluated=old))), ["evaluation_overdue"])
        self.assertEqual(run(rec(last_evaluated=old, status="pilot")), [])
        self.assertEqual(run(rec(last_evaluated=days_ago(ic.CADENCE_DAYS[2]).isoformat())), [])
        self.assertEqual(run(rec(risk_tier=1, last_evaluated="2020-01-01")), [])

    def test_a_date_in_the_future_is_not_also_stale(self):
        self.assertEqual(run(rec(last_reviewed="2027-01-01")), [])

    def test_model_change_is_found_from_recent_traffic(self):
        got = run(rec(), [use(model="vendor-a-large-2026-08", first=20, last=2)])
        self.assertEqual(kinds(got), ["model_changed"])
        self.assertIn("vendor-a-large-2026-08", got[0]["message"])

    def test_model_ids_are_compared_without_case_or_extra_spaces(self):
        for recorded, seen in (("Vendor-A-Large-2026-03 ", "vendor-a-large-2026-03"), ("vendor-a-large-2026-03", "VENDOR-A-LARGE-2026-03")):
            with self.subTest(recorded=recorded):
                self.assertEqual(run(rec(model_id=recorded), [use(model=seen)]), [])

    def test_an_older_row_with_another_model_does_not_count(self):
        rows = [use(model="vendor-a-large-2026-01", first=300, last=100), use(model="vendor-a-large-2026-03", first=99, last=1)]
        self.assertEqual(run(rec(), rows), [])

    def test_the_latest_row_decides_even_when_listed_first(self):
        rows = [use(model="vendor-a-large-2026-08", first=20, last=1), use(model="vendor-a-large-2026-03", first=300, last=30)]
        self.assertEqual(kinds(run(rec(), rows)), ["model_changed"])

    def test_idle_traffic_is_left_to_the_coverage_test(self):
        self.assertEqual(run(rec(), [use(model="other-model", first=300, last=ic.IDLE_DAYS + 1)]), [])
        self.assertEqual(kinds(run(rec(), [use(model="other-model", first=300, last=ic.IDLE_DAYS)])), ["model_changed"])

    def test_blank_or_placeholder_model_ids_are_not_compared(self):
        for v in ("TBD", "", None, 5):
            with self.subTest(v=v):
                self.assertEqual(run(rec(model_id=v), [use(model="anything")]), [])

    def test_no_usage_file_means_no_model_test(self):
        self.assertEqual(run(rec()), [])

    def test_retired_system_is_not_compared_either(self):
        self.assertEqual(run(rec(status="retired"), [use(model="other-model", last=1)]), [])


if __name__ == "__main__":
    unittest.main()
