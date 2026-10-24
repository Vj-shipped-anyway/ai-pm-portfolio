"""The rubric and recompute(): second sources, text rules, and what happens without them."""
from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from tiergate import recompute, rubric_score, status_of, tier_from_score


def form(**overrides) -> dict:
    base = {"use_case_id": "T-1", "title": "Staff lookup", "description": "Looks up a policy for staff.",
            "dataset_name": "ds", "customer_facing": "no", "decision_autonomy": "advisory", "data_class": "internal",
            "vendor_model": "none", "regulatory_scope": "none", "financial_exposure_band": "lt_1m",
            "self_declared_tier": 1}
    base.update(overrides)
    return base


def codes(result: dict) -> list:
    return [f["code"] for f in result["flags"]]


class RubricTests(unittest.TestCase):
    def test_tier_boundaries(self):
        got = {s: tier_from_score(s) for s in (0, 3, 4, 7, 8, 11, 12, 16)}
        self.assertEqual(got, {0: 1, 3: 1, 4: 2, 7: 2, 8: 3, 11: 3, 12: 4, 16: 4})

    def test_blank_and_unsure_score_zero(self):
        args = ("advisory", "internal", "none", "none", "lt_1m")
        self.assertEqual(rubric_score("", *args), rubric_score("no", *args))
        self.assertEqual(rubric_score("unsure", *args), rubric_score("no", *args))
        self.assertEqual(rubric_score("yes", *args), rubric_score("no", *args) + 2)

    def test_maximum_is_16(self):
        self.assertEqual(rubric_score("yes", "automated", "restricted", "vendor_api", "fair_lending", "gt_50m"), 16)


class SecondSourceTests(unittest.TestCase):
    def test_catalog_raises_class(self):
        r = recompute(form(), {"ds": "confidential"}, None)
        self.assertEqual(r["data_class"], "confidential")
        self.assertEqual(r["score"], recompute(form(), None, None)["score"] + 1)
        self.assertIn("DATA_CLASS_BELOW_CATALOG", codes(r))

    def test_catalog_below_form_keeps_form_class(self):
        r = recompute(form(data_class="restricted"), {"ds": "internal"}, None)
        self.assertEqual(r["data_class"], "restricted")
        self.assertIn("DATA_CLASS_ABOVE_CATALOG", codes(r))

    def test_dataset_missing_from_catalog_is_flagged(self):
        r = recompute(form(), {"other": "public"}, None)
        self.assertIn("DATASET_NOT_IN_CATALOG", codes(r))
        self.assertEqual(r["data_class"], "internal")

    def test_no_catalog_means_no_catalog_flags(self):
        self.assertEqual(codes(recompute(form(), None, None)), [])

    def test_registry_raises_vendor(self):
        r = recompute(form(), None, {"T-1": "vendor_api"})
        self.assertEqual(r["vendor_model"], "vendor_api")
        self.assertIn("VENDOR_NOT_DECLARED", codes(r))

    def test_registry_never_lowers_vendor(self):
        r = recompute(form(vendor_model="vendor_api"), None, {"T-1": "none"})
        self.assertEqual(r["vendor_model"], "vendor_api")
        self.assertNotIn("VENDOR_NOT_DECLARED", codes(r))


class TextRuleTests(unittest.TestCase):
    def test_no_with_a_customer_cue_becomes_yes(self):
        r = recompute(form(description="Answers customer questions."), None, None)
        self.assertEqual(r["customer_facing"], "yes")
        self.assertIn("CUSTOMER_FACING_CUE", codes(r))

    def test_cue_needs_a_whole_word(self):
        r = recompute(form(description="A customerless back office batch."), None, None)
        self.assertEqual(r["customer_facing"], "no")
        self.assertEqual(codes(r), [])

    def test_blank_and_unsure_resolve_to_yes(self):
        for answer in ("", "unsure"):
            r = recompute(form(customer_facing=answer), None, None)
            self.assertEqual(r["customer_facing"], "yes")
            self.assertIn("CUSTOMER_FACING_AMBIGUOUS", codes(r))

    def test_a_yes_stays_yes_without_a_flag(self):
        self.assertEqual(codes(recompute(form(customer_facing="yes"), None, None)), [])

    def test_switching_the_text_rules_off_keeps_the_answer_as_written(self):
        r = recompute(form(customer_facing="unsure", description="Helps customers."), None, None, check_text=False)
        self.assertEqual(r["customer_facing"], "unsure")
        self.assertEqual(codes(r), [])


class DeclaredTierTests(unittest.TestCase):
    def test_declared_below_and_above(self):
        low = recompute(form(decision_autonomy="automated", self_declared_tier=1), None, None)
        self.assertEqual((low["tier"], status_of(1, low["tier"])), (2, "UNDER-DECLARED"))
        self.assertIn("TIER_DECLARED_BELOW", codes(low))
        high = recompute(form(self_declared_tier=3), None, None)
        self.assertEqual(status_of(3, high["tier"]), "OVER-DECLARED")
        self.assertIn("TIER_DECLARED_ABOVE", codes(high))

    def test_match_has_no_tier_flag(self):
        r = recompute(form(), None, None)
        self.assertEqual((status_of(1, r["tier"]), codes(r)), ("MATCH", []))


if __name__ == "__main__":
    unittest.main()
