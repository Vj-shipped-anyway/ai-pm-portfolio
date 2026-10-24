import copy
import unittest

import _bootstrap  # noqa: F401
import inventory_check as ic
from _fixtures import AS_OF, DROP, agent, kinds, rec


def run(r):
    return ic.check_record(r, "AI-1", AS_OF)


class CompletenessTests(unittest.TestCase):
    def test_clean_record_has_no_findings(self):
        self.assertEqual(run(rec()), [])
        self.assertEqual(run(agent()), [])

    def test_every_required_field_is_tested_when_blank(self):
        for f in ic.REQUIRED:
            for blank in (DROP, None, "", "   "):
                with self.subTest(field=f, blank=blank):
                    got = run(rec(**{f: blank}))
                    self.assertIn(("missing_required", f), [(x["kind"], x["field"]) for x in got])

    def test_listed_placeholders_are_flagged_whole_value_only(self):
        for v in ("TBD", "n/a", "N/A.", "  unknown ", "None", "-"):
            with self.subTest(v=v):
                self.assertEqual(kinds(run(rec(business_owner=v))), ["placeholder_value"])

    def test_a_sentence_that_contains_a_placeholder_word_is_not_flagged(self):
        self.assertEqual(run(rec(purpose="Flags unknown merchant names on disputed card items.")), [])

    def test_known_miss_a_placeholder_the_list_does_not_hold_passes(self):
        for v in ("to be confirmed with the team", "see wiki", "OWN-TBD"):
            with self.subTest(v=v):
                self.assertEqual(run(rec(business_owner=v)), [])

    def test_wrong_type_is_a_finding_not_a_crash(self):
        for v in (5, ["a"], {"a": 1}, True, 2.5):
            with self.subTest(v=v):
                self.assertEqual(kinds(run(rec(name=v))), ["invalid_value"])
        self.assertEqual(kinds(run(rec(customer_facing=True))), ["invalid_value"])
        self.assertEqual(kinds(run(rec(status=["production"]))), ["invalid_value"])

    def test_risk_tier_accepts_one_to_four_only(self):
        for v in (1, 2, 3, 4, "3", " 4 "):
            with self.subTest(v=v):
                self.assertEqual(ic.parse_tier(v) is not None, True)
        for v in (0, 5, "high", True, 2.5, "3.0", "", [3]):
            with self.subTest(v=v):
                self.assertIsNone(ic.parse_tier(v))
        self.assertEqual(kinds(run(rec(risk_tier=5))), ["invalid_value"])
        self.assertEqual(kinds(run(rec(risk_tier="high"))), ["invalid_value"])

    def test_dates_are_strict(self):
        for v in ("31/03/2026", "2026-02-30", "2026-09-30\n", "2026-9-3", "٢٠٢٦-٠٩-٣٠", 20260930, "2026-13-02"):
            with self.subTest(v=v):
                self.assertEqual(kinds(run(rec(last_reviewed=v))), ["invalid_value"])
        self.assertEqual(run(rec(last_reviewed="2026-09-30")), [])

    def test_a_date_after_the_as_of_date_is_invalid(self):
        got = run(rec(last_reviewed="2026-10-01"))
        self.assertEqual(kinds(got), ["invalid_value"])
        self.assertIn("after the as-of date", got[0]["message"])

    def test_enum_values_are_case_sensitive(self):
        self.assertEqual(kinds(run(rec(data_class="Internal"))), ["invalid_value"])
        self.assertEqual(kinds(run(rec(status="live"))), ["invalid_value"])

    def test_agentic_record_needs_each_agent_field(self):
        for f in ("tools", "permission_scope", "human_approval"):
            for blank in (DROP, "", []):
                with self.subTest(field=f, blank=blank):
                    got = run(agent(**{f: blank}))
                    self.assertEqual([(x["kind"], x["field"]) for x in got], [("agent_field_missing", f)])

    def test_agent_fields_must_be_well_formed(self):
        self.assertEqual(kinds(run(agent(tools="get_x"))), ["invalid_value"])
        self.assertEqual(kinds(run(agent(tools=["get_x", 5]))), ["invalid_value"])
        self.assertEqual(kinds(run(agent(permission_scope="root"))), ["invalid_value"])
        self.assertEqual(kinds(run(agent(human_approval=3))), ["invalid_value"])

    def test_generative_record_needs_no_agent_fields(self):
        self.assertEqual(run(rec()), [])
        self.assertEqual(run(rec(tools=[])), [])

    def test_generative_record_that_lists_tools_is_a_review_finding(self):
        got = run(rec(tools=["send_email"]))
        self.assertEqual([(x["kind"], x["severity"]) for x in got], [("kind_mismatch", "review")])

    def test_tier_one_production_needs_no_evidence(self):
        self.assertEqual(run(rec(risk_tier=1, evaluation_ref=DROP, last_evaluated=DROP)), [])

    def test_evidence_follows_tier_for_production(self):
        signed = {"independent_review_date": "2026-05-01"}
        cases = [(2, {"evaluation_ref": DROP}, ["evidence_missing"]),
                 (2, {"last_evaluated": DROP}, ["evidence_missing"]),
                 (3, {"independent_review_date": DROP}, ["evidence_missing"]),
                 (4, dict(signed, fallback_plan=DROP), ["evidence_missing"]),
                 (4, dict(signed, fallback_plan="no"), ["evidence_missing"]),
                 (4, dict(signed, fallback_plan="yes"), [])]
        for tier, over, want in cases:
            with self.subTest(tier=tier, over=over):
                self.assertEqual(kinds(run(rec(risk_tier=tier, **over))), want)

    def test_tier_three_needs_independent_review_date_and_tier_two_does_not(self):
        self.assertEqual(kinds(run(rec(risk_tier=3))), ["evidence_missing"])
        self.assertEqual(run(rec(risk_tier=2)), [])

    def test_evidence_is_not_required_before_production(self):
        for status in ("development", "pilot", "retired"):
            with self.subTest(status=status):
                r = rec(risk_tier=4, status=status, evaluation_ref=DROP, last_evaluated=DROP)
                self.assertEqual(run(r), [])

    def test_optional_values_are_checked_when_present(self):
        pilot = dict(status="pilot", risk_tier=3)
        self.assertEqual(kinds(run(rec(last_evaluated="soon", **pilot))), ["invalid_value"])
        self.assertEqual(kinds(run(rec(evaluation_ref="TBD", **pilot))), ["placeholder_value"])
        self.assertEqual(kinds(run(rec(independent_review_date="2027-01-01", **pilot))), ["invalid_value"])
        self.assertEqual(kinds(run(rec(fallback_plan="maybe", **pilot))), ["invalid_value"])
        self.assertEqual(kinds(run(rec(evaluation_ref=7, **pilot))), ["invalid_value"])

    def test_check_does_not_change_its_input(self):
        r = agent(tools=["a"], risk_tier="3")
        before = copy.deepcopy(r)
        run(r)
        self.assertEqual(r, before)

    def test_duplicate_and_missing_ids_are_labelled(self):
        got = ic.check([rec(system_id="AI-1"), rec(system_id="AI-1"), rec(system_id=DROP), rec(system_id=7)], None, AS_OF, tests=("completeness",))
        self.assertEqual([(f["system_id"], f["kind"]) for f in got],
                         [("(record 3)", "missing_required"), ("(record 4)", "invalid_value"), ("AI-1", "duplicate_id")])


if __name__ == "__main__":
    unittest.main()
