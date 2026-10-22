import copy
import unittest

import _bootstrap  # noqa: F401
from tool_schema_drift import diff_schemas, decide, description_signature


def base():
    return {"name": "t", "version": "1.0.0", "description": "A tool.", "parameters": {"required": ["a"], "properties": {
        "a": {"type": "string", "description": "Account identifier."},
        "n": {"type": "integer", "description": "Days back, 1 to 90 days.", "minimum": 1, "maximum": 90, "default": 30},
        "k": {"type": "string", "description": "Kind.", "enum": ["x", "y", "z"]}}}}


def kinds(old, new):
    return {(f["kind"], f["class"]) for f in diff_schemas(old, new)}


class DiffTests(unittest.TestCase):
    def test_no_change(self):
        self.assertEqual(diff_schemas(base(), base()), [])
        self.assertEqual(decide([]), "ALLOW")

    def test_rename_is_one_breaking_finding(self):
        new = copy.deepcopy(base())
        props = new["parameters"]["properties"]
        props["account_ref"] = props.pop("a")
        new["parameters"]["required"] = ["account_ref"]
        fs = diff_schemas(base(), new)
        self.assertEqual([f["kind"] for f in fs], ["param_renamed"])
        self.assertEqual(decide(fs), "BLOCK")

    def test_optional_added_is_allowed(self):
        new = copy.deepcopy(base())
        new["parameters"]["properties"]["trace"] = {"type": "string", "description": "Trace id."}
        self.assertEqual(decide(diff_schemas(base(), new)), "ALLOW")

    def test_required_added_blocks(self):
        new = copy.deepcopy(base())
        new["parameters"]["properties"]["ch"] = {"type": "string", "description": "Channel."}
        new["parameters"]["required"].append("ch")
        self.assertIn(("required_added", "breaking"), kinds(base(), new))

    def test_enum_value_removed_blocks_and_added_allows(self):
        new = copy.deepcopy(base())
        new["parameters"]["properties"]["k"]["enum"] = ["x", "y"]
        self.assertIn(("enum_value_removed", "breaking"), kinds(base(), new))
        new["parameters"]["properties"]["k"]["enum"] = ["x", "y", "z", "w"]
        self.assertEqual(decide(diff_schemas(base(), new)), "ALLOW")

    def test_bounds(self):
        tight, loose = copy.deepcopy(base()), copy.deepcopy(base())
        tight["parameters"]["properties"]["n"]["maximum"] = 30
        loose["parameters"]["properties"]["n"]["maximum"] = 365
        self.assertIn(("bound_tightened", "breaking"), kinds(base(), tight))
        self.assertIn(("bound_loosened", "non_breaking"), kinds(base(), loose))

    def test_type_narrow_and_widen(self):
        old = base()
        old["parameters"]["properties"]["n"]["type"] = "number"
        self.assertIn(("type_changed", "breaking"), kinds(old, base()))
        self.assertIn(("type_changed", "non_breaking"), kinds(base(), old))

    def test_unit_swap_needs_review_not_block(self):
        new = copy.deepcopy(base())
        new["parameters"]["properties"]["n"]["description"] = "Days back, 1 to 90 hours."
        fs = diff_schemas(base(), new)
        self.assertEqual(decide(fs), "REVIEW")
        self.assertEqual(fs[0]["kind"], "unit_or_number_changed")

    def test_reword_without_number_is_allowed(self):
        new = copy.deepcopy(base())
        new["parameters"]["properties"]["a"]["description"] = "Account identifier, as supplied by the caller."
        self.assertEqual(decide(diff_schemas(base(), new)), "ALLOW")

    def test_meaning_flip_without_number_is_the_known_miss(self):
        new = copy.deepcopy(base())
        new["parameters"]["properties"]["a"]["description"] = "Account identifier, exclusive of the end date."
        self.assertEqual(decide(diff_schemas(base(), new)), "ALLOW")

    def test_default_change_needs_review(self):
        new = copy.deepcopy(base())
        new["parameters"]["properties"]["n"]["default"] = 60
        self.assertEqual(decide(diff_schemas(base(), new)), "REVIEW")

    def test_signature_pairs_numbers_with_units(self):
        self.assertEqual(description_signature("1 to 90 days"), frozenset({("1", None), ("90", "d")}))
        self.assertNotEqual(description_signature("amount in dollars"), description_signature("amount in cents"))


if __name__ == "__main__":
    unittest.main()
