import copy
import unittest
from datetime import date

import _bootstrap  # noqa: F401
import chargeback_packet as cp
from _fixtures import base

RULES = cp.load_rules()


def bad(mutate):
    """The one-line message validate_case raises for the base case after mutate(), or None when it accepts it."""
    c = base()
    mutate(c)
    try:
        cp.validate_case(c, RULES)
    except ValueError as e:
        return str(e)
    return None


class CaseValidationTests(unittest.TestCase):
    def assert_rejected(self, mutate):
        msg = bad(mutate)
        self.assertIsNotNone(msg)
        self.assertNotIn("\n", msg)

    def test_base_case_is_valid(self):
        cp.validate_case(base(), RULES)

    def test_wrong_top_level_types(self):
        for value in (None, 5, "x", [1], []):
            with self.assertRaises(ValueError):
                cp.validate_case(value, RULES)

    def test_missing_or_empty_ids(self):
        self.assert_rejected(lambda c: c.pop("case_id"))
        self.assert_rejected(lambda c: c.update(case_id=""))
        self.assert_rejected(lambda c: c.update(order_id=5))

    def test_unknown_reason_code(self):
        self.assert_rejected(lambda c: c.update(reason_code="RC-99"))

    def test_bad_dates(self):
        for value in ("2026/01/10", "2026-02-30", "26-01-10", "", None, 20260110, "２０２６-01-10"):
            self.assert_rejected(lambda c, v=value: c.update(txn_date=v))
            self.assert_rejected(lambda c, v=value: c["docs"][0].update(doc_date=v))

    def test_dates_out_of_order(self):
        self.assert_rejected(lambda c: c.update(received_date="2026-01-09"))
        self.assert_rejected(lambda c: c.update(submitted_date="2026-02-01"))

    def test_bad_amounts(self):
        for value in (0, -5, 12.5, True, "129", None):
            self.assert_rejected(lambda c, v=value: c.update(amount_cents=v))
        self.assert_rejected(lambda c: c["docs"][0].update(amount_cents=-1))
        self.assert_rejected(lambda c: c["docs"][0].update(amount_cents=1.5))

    def test_bad_docs(self):
        self.assert_rejected(lambda c: c.update(docs="none"))
        self.assert_rejected(lambda c: c.update(docs=[5]))
        self.assert_rejected(lambda c: c["docs"][0].update(pages=0))
        self.assert_rejected(lambda c: c["docs"][0].update(pages=True))
        self.assert_rejected(lambda c: c["docs"][0].pop("ref_id"))
        self.assert_rejected(lambda c: c["docs"][0].update(doc_type=""))

    def test_hostile_text_cannot_add_a_line_to_the_message(self):
        msg = bad(lambda c: c.update(reason_code="RC-1\n::error title=forged::x\r\x1b[31m"))
        self.assertNotIn("\n", msg)
        self.assertNotIn("\r", msg)
        self.assertNotIn("\x1b", msg)

    def test_check_case_validates_before_reading(self):
        c = base()
        c["docs"] = None
        with self.assertRaises(ValueError):
            cp.check_case(c, RULES, date(2026, 2, 28))


class RulesValidationTests(unittest.TestCase):
    def test_bundled_rules_are_valid(self):
        cp.validate_rules(RULES)

    def test_bad_shapes(self):
        def broken(mutate):
            r = copy.deepcopy(RULES)
            mutate(r)
            with self.assertRaises(ValueError):
                cp.validate_rules(r)
        broken(lambda r: r.pop("reason_codes"))
        broken(lambda r: r.update(reason_codes={}))
        broken(lambda r: r.update(max_pages=0))
        broken(lambda r: r.update(amount_types="order_record"))
        broken(lambda r: r["reason_codes"]["RC-01"].update(window_days=0))
        broken(lambda r: r["reason_codes"]["RC-01"].update(slots=[]))
        broken(lambda r: r["reason_codes"]["RC-01"]["slots"][0].update(accept=[]))
        broken(lambda r: r["reason_codes"]["RC-01"]["slots"][0].update(required="yes"))

    def test_non_object(self):
        for value in (None, [], "rules", 3):
            with self.assertRaises(ValueError):
                cp.validate_rules(value)


if __name__ == "__main__":
    unittest.main()
