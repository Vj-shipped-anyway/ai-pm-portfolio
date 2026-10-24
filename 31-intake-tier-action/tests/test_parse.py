import unittest

import _bootstrap  # noqa: F401
import intake_tier_action as it
from forms import body


class ParseTests(unittest.TestCase):
    def test_well_formed_body_reads_all_ten_fields(self):
        f = it.read_form(body())
        self.assertEqual(f["problems"], [])
        self.assertEqual(len(f["values"]), 10)
        self.assertEqual(f["values"]["data_class"], "internal")

    def test_windows_line_endings_and_case_and_padding_are_tolerated(self):
        text = body(data_class="  Confidential ", vendor="VENDOR_API").replace("\n", "\r\n")
        f = it.read_form(text)
        self.assertEqual(f["problems"], [])
        self.assertEqual((f["values"]["data_class"], f["values"]["vendor"]), ("confidential", "vendor_api"))

    def test_no_response_is_blank_and_blocks_a_required_field(self):
        f = it.read_form(body(vendor=""))
        self.assertEqual(f["problems"], ["'Vendor model' is blank"])

    def test_blank_optional_fields_do_not_block(self):
        f = it.read_form(body(dataset="", unit="", declared="", customer_facing=""))
        self.assertEqual(f["problems"], [])

    def test_missing_heading_blocks(self):
        text = body().replace("### Data class", "### Data classification")
        self.assertIn("heading 'Data class' is missing", it.read_form(text)["problems"])

    def test_repeated_heading_is_ambiguous_and_blocks(self):
        text = body(summary="Notes:\n\n### Data class\n\npublic")
        f = it.read_form(text)
        self.assertEqual(len(f["problems"]), 1)
        self.assertIn("appears more than once", f["problems"][0])
        self.assertNotIn("data_class", f["values"])

    def test_unknown_heading_ends_the_section_it_is_in(self):
        f = it.read_form(body(summary="Plan.\n\n### Notes\n\nStill drafting."))
        self.assertEqual(f["problems"], [])
        self.assertEqual(f["values"]["summary"], "Plan.")

    def test_unknown_heading_after_a_required_field_does_not_spoil_its_value(self):
        text = body().replace("### Regulatory scope", "### Extra\n\nnotes\n\n### Regulatory scope")
        self.assertEqual(it.read_form(text)["problems"], [])

    def test_four_hashes_is_not_a_heading(self):
        text = body(summary="Plan.\n\n#### Data class\n\npublic")
        self.assertEqual(it.read_form(text)["problems"], [])

    def test_invalid_value_is_reported_without_echoing_markup(self):
        f = it.read_form(body(data_class="secret <b>@everyone</b>\n::error::x"))
        self.assertEqual(len(f["problems"]), 1)
        self.assertNotIn("<", f["problems"][0])
        self.assertNotIn("@", f["problems"][0])
        self.assertNotIn("\n", f["problems"][0])

    def test_truncated_body_names_what_is_missing(self):
        text = body()
        probs = it.read_form(text[:text.index("lt_1m") + 2])["problems"]
        self.assertEqual(probs, ["'Financial exposure band' has the value 'lt'; allowed: lt_1m, 1m_10m, 10m_50m, gt_50m"])

    def test_empty_and_headingless_bodies_name_every_required_field(self):
        for text in ("", "Please assess this use case.\n", '{"a": 1}'):
            f = it.read_form(text)
            self.assertEqual(len(f["problems"]), 5, text)

    def test_unreadable_declared_tier_does_not_block(self):
        f = it.read_form(body(declared="TBD"))
        self.assertEqual(f["problems"], [])
        self.assertNotIn("declared", f["values"])


if __name__ == "__main__":
    unittest.main()
