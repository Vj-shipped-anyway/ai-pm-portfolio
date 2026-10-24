import unittest

import _bootstrap  # noqa: F401
from feature_contract import parse_value, _exceeds


def ok(raw, typ, typed=False):
    return parse_value(raw, typ, typed)[0]


class TextParseTests(unittest.TestCase):
    def test_integer_accepts_plain_and_integral_decimals(self):
        for s in ("12", "-3", "0", "12.0", "12.00"):
            self.assertTrue(ok(s, "integer"), s)
        self.assertEqual(parse_value("12.0", "integer"), (True, 12))

    def test_integer_rejects_everything_else(self):
        for s in ("12.5", "1e3", " 12", "12 ", "+5", "1_0", "1,000", "twelve", "-", ".0", "٣", "9" * 31, "12" + chr(10)):
            self.assertFalse(ok(s, "integer"), repr(s))

    def test_number(self):
        for s in ("1.5", "-0.5", "0", "1e3", "1E-3", "12"):
            self.assertTrue(ok(s, "number"), s)
        for s in ("nan", "inf", "-inf", "1,234.50", "$5", "5%", ".5", "5.", " 5", "1e999", "1_0", "0x10", "٣"):
            self.assertFalse(ok(s, "number"), repr(s))

    def test_boolean(self):
        for s in ("true", "FALSE", "True"):
            self.assertTrue(ok(s, "boolean"), s)
        for s in ("1", "0", "yes", "t", "truee"):
            self.assertFalse(ok(s, "boolean"), s)

    def test_string_takes_anything(self):
        self.assertTrue(ok("anything at all", "string"))


class TypedParseTests(unittest.TestCase):
    def test_a_string_is_only_a_string(self):
        self.assertFalse(ok("12", "integer", True))
        self.assertFalse(ok("1.5", "number", True))
        self.assertFalse(ok("true", "boolean", True))
        self.assertTrue(ok("x", "string", True))
        self.assertFalse(ok(5, "string", True))

    def test_bool_is_not_a_number(self):
        self.assertFalse(ok(True, "integer", True))
        self.assertFalse(ok(True, "number", True))
        self.assertTrue(ok(True, "boolean", True))
        self.assertFalse(ok(1, "boolean", True))

    def test_integer_accepts_integral_floats_only(self):
        self.assertTrue(ok(12.0, "integer", True))
        self.assertFalse(ok(12.5, "integer", True))

    def test_non_finite_and_containers_are_rejected(self):
        for v in (float("nan"), float("inf"), [], {}):
            self.assertFalse(ok(v, "number", True), repr(v))

    def test_huge_integer_does_not_crash(self):
        self.assertTrue(ok(10 ** 400, "number", True))
        self.assertTrue(ok(10 ** 400, "integer", True))


class RateTests(unittest.TestCase):
    def test_equal_rate_is_not_above(self):
        self.assertFalse(_exceeds(29, 100, 0.29))
        self.assertFalse(_exceeds(7, 100, 0.07))
        self.assertFalse(_exceeds(2, 100, 0.02))
        self.assertTrue(_exceeds(3, 100, 0.02))
        self.assertTrue(_exceeds(1, 100, 0.0))


if __name__ == "__main__":
    unittest.main()
