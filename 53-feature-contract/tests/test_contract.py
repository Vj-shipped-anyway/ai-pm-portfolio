import copy
import unittest

import _bootstrap  # noqa: F401
from feature_contract import check_contract_shape

GOOD = {"contract": "t", "version": "1", "unexpected_columns": "warn", "max_bad_rate": 0.01, "fields": [
    {"name": "a", "type": "number", "min": 0, "max": 1, "max_null_rate": 0.1, "unit": "ratio", "description": "x"},
    {"name": "b", "type": "string", "allowed": ["p", "q"]}]}


def with_field(**changes):
    c = copy.deepcopy(GOOD)
    c["fields"][0].update(changes)
    return c


class ContractShapeTests(unittest.TestCase):
    def test_good_contract_is_accepted(self):
        check_contract_shape(GOOD, "t")

    def bad(self, c):
        with self.assertRaises(ValueError) as ctx:
            check_contract_shape(c, "t")
        self.assertNotIn("\n", str(ctx.exception))

    def test_wrong_top_level_types(self):
        for c in ([], "x", 5, None):
            self.bad(c)

    def test_fields_must_be_a_non_empty_list(self):
        self.bad({"fields": []})
        self.bad({"fields": {"a": 1}})
        self.bad({})

    def test_unknown_keys_are_rejected_so_a_typo_is_not_a_silent_no_op(self):
        self.bad(with_field(maximum=5))
        self.bad(dict(GOOD, max_bad=0.5))

    def test_field_problems(self):
        self.bad(with_field(type="float"))
        self.bad(with_field(name=""))
        self.bad(with_field(name=5))
        self.bad(with_field(min=2, max=1))
        self.bad(with_field(min="0"))
        self.bad(with_field(min=True))
        self.bad(with_field(max_null_rate=1.5))
        self.bad(with_field(allowed=["x"]))
        self.bad(with_field(type="string", min=0))
        c = copy.deepcopy(GOOD)
        c["fields"][1]["allowed"] = []
        self.bad(c)
        c["fields"][1]["allowed"] = [1, 2]
        self.bad(c)

    def test_duplicate_field_names(self):
        c = copy.deepcopy(GOOD)
        c["fields"][1]["name"] = "a"
        self.bad(c)

    def test_top_level_values(self):
        self.bad(dict(GOOD, unexpected_columns="ignore"))
        self.bad(dict(GOOD, max_bad_rate=2))
        self.bad(dict(GOOD, max_bad_rate="0.1"))

    def test_hostile_field_name_stays_on_one_line(self):
        c = copy.deepcopy(GOOD)
        c["fields"][0]["name"] = "a\n::error::forged"
        c["fields"][0]["type"] = "float"
        self.bad(c)


if __name__ == "__main__":
    unittest.main()
