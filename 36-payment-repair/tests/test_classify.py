import unittest

import _bootstrap  # noqa: F401
import payment_repair as pr
from support import msg


class ClassifyTests(unittest.TestCase):
    def test_complete_message_has_no_defect(self):
        self.assertEqual(pr.find_defects(msg()), {})

    def test_kinds(self):
        self.assertEqual(pr.classify(pr.CDTR_NM, None), "missing")
        self.assertEqual(pr.classify(pr.CDTR_NM, ""), "blank")
        self.assertEqual(pr.classify(pr.CDTR_NM, "   "), "blank")
        self.assertEqual(pr.classify(pr.CDTR_NM, "N/A"), "placeholder")
        self.assertEqual(pr.classify(pr.CDTR_NM, "NotProvided"), "placeholder")
        self.assertEqual(pr.classify(pr.CDTR_BIC, "BBBBFR"), "malformed")

    def test_zero_width_and_no_break_spaces_are_blank(self):
        self.assertEqual(pr.classify(pr.CDTR_NM, "​ "), "blank")
        self.assertEqual(pr.classify(pr.CDTR_NM, "⁠"), "blank")

    def test_names_that_contain_a_placeholder_word_are_usable(self):
        for name in ("Unknown Pleasures Trading Ltd", "N/A Logistics GmbH", "Null Point Freight SA", "Not Provided Catering SL"):
            self.assertIsNone(pr.classify(pr.CDTR_NM, name), name)

    def test_bic_eight_and_eleven_characters_are_both_usable(self):
        self.assertIsNone(pr.classify(pr.CDTR_BIC, "BBBBFR22"))
        self.assertIsNone(pr.classify(pr.CDTR_BIC, "BBBBFR22XXX"))

    def test_bic_with_trailing_newline_or_lowercase_is_malformed(self):
        self.assertEqual(pr.classify(pr.CDTR_BIC, "BBBBFR22\n"), "malformed")
        self.assertEqual(pr.classify(pr.CDTR_BIC, "bbbbfr22"), "malformed")
        self.assertEqual(pr.classify(pr.CDTR_BIC, "BBBBFR22XXX "), "malformed")

    def test_number_of_transactions(self):
        self.assertIsNone(pr.classify(pr.NB, "1"))
        self.assertIsNone(pr.classify(pr.NB, "01"))
        self.assertEqual(pr.classify(pr.NB, "2"), "malformed")
        self.assertEqual(pr.classify(pr.NB, "²"), "malformed")      # isdigit() is true for this; int() would raise

    def test_amount(self):
        self.assertIsNone(pr.classify(pr.AMT, "10"))
        self.assertIsNone(pr.classify(pr.AMT, "0.50"))
        for bad in ("0.00", "12,50", "-5.00", "1e3", "١٢٣"):
            self.assertEqual(pr.classify(pr.AMT, bad), "malformed", bad)

    def test_optional_fields_are_never_defects(self):
        m = msg(PURP=None, RMT=None)
        self.assertEqual(pr.find_defects(m), {})
        m2 = msg(PURP="", RMT="N/A")
        self.assertEqual(pr.find_defects(m2), {})

    def test_defects_follow_the_order_of_required(self):
        m = msg(CDTR_BIC=None, NB=None, CCY="")
        self.assertEqual(list(pr.find_defects(m)), [pr.NB, pr.CCY, pr.CDTR_BIC])


if __name__ == "__main__":
    unittest.main()
