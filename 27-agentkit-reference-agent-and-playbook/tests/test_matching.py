import unittest

import _bootstrap  # noqa: F401
import support
from agentkit.matching import (AMBIGUOUS, CLOSE, EXACT, MISMATCH, bank_code_ok, classify_name_match, luhn_ok,
                               name_similarity, normalize_name)


class TestMatching(unittest.TestCase):
    def test_normalize_drops_legal_form_punctuation_and_case(self):
        self.assertEqual(normalize_name("Zorvane Freight, Ltd."), normalize_name("ZORVANE FREIGHT LIMITED"))

    def test_known_abbreviations_expand(self):
        self.assertEqual(normalize_name("Zorvane Freight Svcs"), normalize_name("Zorvane Freight Services"))

    def test_unknown_abbreviation_does_not_expand(self):
        self.assertNotEqual(normalize_name("Zorvane Freight Sols"), normalize_name("Zorvane Freight Solutions"))

    def test_token_order_does_not_matter(self):
        self.assertEqual(normalize_name("Freight Zorvane Services"), normalize_name("Zorvane Freight Services"))

    def test_classes(self):
        b = support.BASE
        self.assertEqual(classify_name_match(b, "ZORVANE FREIGHT SVCS LTD.")[0], EXACT)
        self.assertEqual(classify_name_match(b, "Zorvane Freigth Services Ltd")[0], CLOSE)
        self.assertEqual(classify_name_match(b, "Zorvane Freight Group Ltd")[0], AMBIGUOUS)
        self.assertEqual(classify_name_match(b, "Quillax Marine Systems Inc")[0], MISMATCH)

    def test_similarity_is_symmetric_and_bounded(self):
        a, b = "Zorvane Freight Services", "Zorvane Freight Group"
        self.assertEqual(name_similarity(a, b), name_similarity(b, a))
        self.assertTrue(0.0 <= name_similarity(a, b) <= 1.0)

    def test_blank_names_do_not_match(self):
        self.assertEqual(name_similarity("", ""), 0.0)

    def test_luhn(self):
        self.assertTrue(luhn_ok(support.RIGHT))
        self.assertFalse(luhn_ok(support.WRONG))
        self.assertFalse(luhn_ok("12AB-??9"))
        self.assertFalse(luhn_ok(""))

    def test_bank_code_format(self):
        self.assertTrue(bank_code_ok("SYNB0042"))
        self.assertFalse(bank_code_ok("SYNB42"))
        self.assertFalse(bank_code_ok(""))


if __name__ == "__main__":
    unittest.main()
