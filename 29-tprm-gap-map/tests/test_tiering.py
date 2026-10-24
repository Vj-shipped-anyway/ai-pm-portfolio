import unittest

import _bootstrap  # noqa: F401
import tprm_gap_map as t


def vendor(**kw):
    v = {"vendor_id": "V1", "service_type": "ai_enabled_service", "activity_share_pct": 10, "upstream_provider": "P2",
         "model_change_notice_days": 30, "trains_on_bank_data": "no", "bank_data_retained_days": 30,
         "soc_report": "yes", "insurance": "yes", "financial_ok": "yes", "key_personnel": "yes"}
    v.update(kw)
    return v


class TieringTests(unittest.TestCase):
    def test_questionnaire_needs_all_four_documents(self):
        self.assertTrue(t.passes_questionnaire(vendor()))
        self.assertFalse(t.passes_questionnaire(vendor(insurance="no")))

    def test_text_examples(self):
        self.assertEqual(t.tier_text(vendor(service_type="core_processing", activity_share_pct=5)), "HIGH")
        self.assertEqual(t.tier_text(vendor(activity_share_pct=30)), "HIGH")
        self.assertEqual(t.tier_text(vendor(activity_share_pct=29)), "LOWER")

    def test_ai_characteristics_raise_a_lower_vendor(self):
        shares = {("ai_enabled_service", "P2"): 0.1}
        self.assertEqual(t.tier_ai(vendor(), shares), "LOWER")
        for field, value in (("model_change_notice_days", 0), ("trains_on_bank_data", "yes"), ("bank_data_retained_days", 365)):
            self.assertEqual(t.tier_ai(vendor(**{field: value}), shares), "HIGH", field)
        self.assertEqual(t.tier_ai(vendor(), {("ai_enabled_service", "P2"): 0.45}), "HIGH")

    def test_non_ai_vendor_has_no_ai_characteristics(self):
        self.assertEqual(t.indicators(vendor(service_type="facilities"), {}), {})

    def test_upstream_shares_are_per_service_type(self):
        vs = [vendor(upstream_provider="P1", activity_share_pct=30), vendor(upstream_provider="P2", activity_share_pct=10),
              vendor(service_type="cloud_hosting", upstream_provider="C1", activity_share_pct=50)]
        sh = t.upstream_shares(vs)
        self.assertAlmostEqual(sh[("ai_enabled_service", "P1")], 0.75)
        self.assertAlmostEqual(sh[("cloud_hosting", "C1")], 1.0)

    def test_provider_names_do_not_have_to_start_with_p_or_c(self):
        # four AI-enabled vendors on four different providers: none is concentrated
        names = ["OpenAI", "Gemini", "Acme", "Zeta"]
        vs = [vendor(vendor_id=f"V{i}", upstream_provider=n, activity_share_pct=25) for i, n in enumerate(names)]
        sh = t.upstream_shares(vs)
        self.assertTrue(all(abs(s - 0.25) < 1e-9 for s in sh.values()))
        self.assertTrue(all(t.tier_ai(v, sh) == "LOWER" for v in vs))

    def test_concentration_threshold_is_an_argument(self):
        v = vendor(upstream_provider="P2")
        sh = {("ai_enabled_service", "P2"): 0.25}
        self.assertEqual(t.tier_ai(v, sh), "LOWER")
        self.assertEqual(t.tier_ai(v, sh, concentration_high=0.20), "HIGH")

    def test_score(self):
        s = t.score({"a", "b", "c"}, {"b", "c", "d"})
        self.assertEqual((s["caught"], s["missed"], s["false_alarms"]), (2, 1, 1))

    def test_ai_wording_counter(self):
        self.assertEqual(len(t.ai_term_hits("Machine learning and generative tools, plus an AI vendor.")), 3)
        self.assertEqual(t.ai_term_hits("said the maid aided the bank"), [])
        self.assertEqual(t.ai_term_hits("an ai in lowercase is not counted"), [])


if __name__ == "__main__":
    unittest.main()
