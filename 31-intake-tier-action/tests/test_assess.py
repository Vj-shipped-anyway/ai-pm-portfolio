import unittest

import _bootstrap  # noqa: F401
import intake_tier_action as it
from forms import body

CATALOG = {"d_policy_library": "internal", "d_loan_files": "confidential", "d_audit_findings": "restricted"}


def codes(r):
    return [f["code"] for f in r["flags"]]


class AssessTests(unittest.TestCase):
    def test_rubric_points_and_tier(self):
        # customer yes 2 + automated 3 + restricted 3 + vendor_api 2 + aml 2 + gt_50m 3 = 15 points
        r = it.assess(body(customer_facing="yes", autonomy="automated", data_class="restricted", vendor="vendor_api",
                           regulatory="aml", exposure="gt_50m", declared="4"))
        self.assertEqual((r["score"], r["tier"], r["decision"]), (15, 4, "TIERED"))
        self.assertEqual(it.assess(body())["tier"], 1)

    def test_tier_boundaries(self):
        for pts, tier in ((3, 1), (4, 2), (7, 2), (8, 3), (11, 3), (12, 4), (16, 4)):
            self.assertEqual(it.tier_from_score(pts), tier)

    def test_catalog_raises_a_understated_class(self):
        r = it.assess(body(dataset="d_loan_files", data_class="internal"), CATALOG)
        self.assertIn("DATA_CLASS_BELOW_CATALOG", codes(r))
        self.assertEqual(r["rows"][2][1], "confidential")

    def test_catalog_that_overstates_does_not_raise_the_tier(self):
        r = it.assess(body(dataset="d_policy_library", data_class="confidential"), CATALOG)
        self.assertIn("DATA_CLASS_ABOVE_CATALOG", codes(r))
        self.assertEqual(r["rows"][2][1], "confidential")

    def test_dataset_missing_or_unknown_is_said(self):
        self.assertIn("DATASET_NOT_GIVEN", codes(it.assess(body(dataset=""), CATALOG)))
        self.assertIn("DATASET_NOT_IN_CATALOG", codes(it.assess(body(dataset="d_unknown"), CATALOG)))
        self.assertEqual(codes(it.assess(body(dataset="D_Policy_Library "), CATALOG)), [])

    def test_no_catalog_means_no_catalog_flags(self):
        self.assertEqual(codes(it.assess(body(dataset=""))), [])

    def test_registry_raises_an_omitted_vendor(self):
        r = it.assess(body(vendor="none"), None, {12: "vendor_api"}, 12)
        self.assertIn("VENDOR_NOT_DECLARED", codes(r))
        self.assertEqual(r["rows"][3][1], "vendor_api")

    def test_registry_without_an_entry_says_so(self):
        r = it.assess(body(), None, {12: "vendor_api"}, 13)
        self.assertEqual(r["notes"][0], "the registry has no entry for issue 13")

    def test_blank_or_unsure_customer_facing_counts_as_yes_with_a_flag(self):
        for cf in ("", "unsure"):
            r = it.assess(body(customer_facing=cf))
            self.assertIn("CUSTOMER_FACING_AMBIGUOUS", codes(r))
            self.assertEqual(r["rows"][0][1:], ("yes", 2))

    def test_customer_cue_is_a_flag_and_leaves_the_tier_alone(self):
        r = it.assess(body(summary="Summarises customer complaint notes."))
        self.assertIn("CUSTOMER_FACING_CUE", codes(r))
        self.assertEqual(r["rows"][0][1:], ("no", 0))

    def test_declared_tier_below_and_above(self):
        low = it.assess(body(autonomy="automated", data_class="restricted", declared="1"))
        self.assertIn("TIER_DECLARED_BELOW", codes(low))
        high = it.assess(body(declared="4"))
        self.assertIn("TIER_DECLARED_ABOVE", codes(high))
        self.assertEqual(it.wanted_labels(high), ["ai-tier:1", "tier-mismatch"])

    def test_declared_tier_unreadable_is_noted(self):
        self.assertEqual(it.assess(body(declared="TBD"))["notes"], ["the declared tier is blank or unreadable"])
        self.assertEqual(it.assess(body().replace("### Declared tier", "### Tier"))["notes"], ["no declared tier on the form"])

    def test_hostile_dataset_name_is_made_safe_in_flags(self):
        r = it.assess(body(dataset="x`\n::error::forged @everyone <img src=x>"), CATALOG)
        text = " ".join(f["reason"] for f in r["flags"])
        for bad in ("\n", "::", "@", "<"):
            self.assertNotIn(bad, text)
        self.assertEqual(text.count("`"), 2)

    def test_needs_info_has_no_tier(self):
        r = it.assess("")
        self.assertEqual((r["decision"], r["tier"], it.wanted_labels(r)), ("NEEDS_INFO", None, ["needs-info"]))

    def test_comment_has_the_marker_and_the_evidence_count(self):
        c = it.render_comment(it.assess(body(autonomy="automated", data_class="restricted", vendor="vendor_api", declared="1")))
        self.assertTrue(c.startswith(it.MARKER))
        self.assertIn("(8 items)", c)
        self.assertTrue(it.render_comment(it.assess("")).startswith(it.MARKER))


class LabelTests(unittest.TestCase):
    def test_adds_one_tier_label_and_removes_a_stale_one(self):
        add, remove = it.plan_labels(["ai-tier:3", "tier-mismatch"], ["ai-intake", "ai-tier:2"])
        self.assertEqual((add, remove), (["ai-tier:3", "tier-mismatch"], ["ai-tier:2"]))

    def test_leaves_labels_it_does_not_own(self):
        self.assertEqual(it.plan_labels(["needs-info"], ["bug", "ai-intake", "priority:high"]), (["needs-info"], []))

    def test_a_second_run_changes_nothing(self):
        wanted = ["ai-tier:2"]
        self.assertEqual(it.plan_labels(wanted, ["ai-tier:2", "ai-intake"]), ([], []))

    def test_needs_info_clears_a_tier_label(self):
        self.assertEqual(it.plan_labels(["needs-info"], ["ai-tier:4", "tier-mismatch"]), (["needs-info"], ["ai-tier:4", "tier-mismatch"]))


if __name__ == "__main__":
    unittest.main()
