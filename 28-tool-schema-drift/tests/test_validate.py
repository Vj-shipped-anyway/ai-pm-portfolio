import unittest

import _bootstrap  # noqa: F401
from tool_schema_drift import strict_validate, replay

S = {"name": "t", "parameters": {"required": ["a"], "properties": {
    "a": {"type": "string", "description": "x"},
    "n": {"type": "integer", "description": "x", "minimum": 1, "maximum": 10},
    "f": {"type": "boolean", "description": "x"},
    "s": {"type": "string", "description": "x", "maxLength": 3, "enum": ["ab", "cd", "abcd"]}}}}


def first(errs):
    return errs[0].split(":")[0] if errs else None


class ValidateTests(unittest.TestCase):
    def test_valid_call(self):
        self.assertEqual(strict_validate(S, {"a": "x", "n": 3, "f": True, "s": "ab"}), [])

    def test_unknown_and_missing(self):
        self.assertEqual(first(strict_validate(S, {"a": "x", "zzz": 1})), "unknown_parameter")
        self.assertEqual(first(strict_validate(S, {})), "missing_required")

    def test_bounds_and_enum_and_length(self):
        self.assertEqual(first(strict_validate(S, {"a": "x", "n": 0})), "below_minimum")
        self.assertEqual(first(strict_validate(S, {"a": "x", "n": 11})), "above_maximum")
        self.assertEqual(first(strict_validate(S, {"a": "x", "s": "zz"})), "enum_violation")
        self.assertIn("too_long", [e.split(":")[0] for e in strict_validate(S, {"a": "x", "s": "abcd"})])

    def test_bool_is_not_an_integer(self):
        self.assertEqual(first(strict_validate(S, {"a": "x", "n": True})), "type_mismatch")

    def test_replay_lists_only_failing_calls(self):
        calls = [{"call_id": "1", "args": {"a": "x"}}, {"call_id": "2", "args": {}}]
        self.assertEqual(list(replay(S, calls)), ["2"])


if __name__ == "__main__":
    unittest.main()
