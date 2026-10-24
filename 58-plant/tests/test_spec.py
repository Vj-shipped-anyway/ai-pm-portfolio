import copy
import unittest

import _bootstrap  # noqa: F401
import common
import plant

WRONG = [None, True, False, -1, 0, 1.5, 2 ** 70, float("nan"), float("inf"), "x", "", [], {}, [1], {"a": 1}]


def paths(node, prefix=()):
    """Every key or index in a JSON value, as a path."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield prefix + (k,)
            yield from paths(v, prefix + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield prefix + (i,)
            yield from paths(v, prefix + (i,))


def with_value(spec, path, value):
    out = copy.deepcopy(spec)
    node = out
    for step in path[:-1]:
        node = node[step]
    node[path[-1]] = value
    return out


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.spec = common.demo_spec()

    def bad(self, spec):
        with self.assertRaises(plant.SpecError):
            plant.validate_spec(spec)

    def test_demo_spec_is_valid(self):
        s = plant.validate_spec(self.spec)
        self.assertEqual((s["rows"], len(s["columns"]), len(s["behaviors"])), (600, 7, 7))

    def test_wrong_type_anywhere_never_raises_anything_but_spec_error(self):
        checked = 0
        for path in paths(self.spec):
            for value in WRONG:
                mutated = with_value(self.spec, path, value)
                try:
                    plant.build(mutated)
                except plant.SpecError:
                    pass
                checked += 1
        self.assertGreater(checked, 1000)

    def test_not_an_object(self):
        for spec in (None, [], "spec", 5, [self.spec]):
            self.bad(spec)

    def test_missing_and_unknown_keys(self):
        for key in ("name", "seed", "rows", "columns", "behaviors"):
            spec = dict(self.spec)
            del spec[key]
            self.bad(spec)
        self.bad(dict(self.spec, extra=1))

    def test_numbers_must_be_whole_and_in_range(self):
        for key, value in (("rows", True), ("rows", 0), ("rows", 10 ** 9), ("seed", -1), ("seed", 1.5), ("seed", "58")):
            self.bad(dict(self.spec, **{key: value}))

    def test_behaviors_cannot_ask_for_more_rows_than_exist(self):
        spec = copy.deepcopy(self.spec)
        spec["rows"] = 100
        self.bad(spec)

    def test_ids_are_restricted_and_unique(self):
        for hostile in ("x\n::error::forged", "Upper", "9lives", "a" * 41, "", "has space"):
            spec = copy.deepcopy(self.spec)
            spec["behaviors"][0]["id"] = hostile
            self.bad(spec)
        spec = copy.deepcopy(self.spec)
        spec["behaviors"][1]["id"] = spec["behaviors"][0]["id"]
        self.bad(spec)

    def test_template_must_name_a_column(self):
        spec = copy.deepcopy(self.spec)
        spec["behaviors"][5]["ops"][0]["set"]["ref"] = "{nope}b"
        self.bad(spec)

    def test_template_does_not_reach_into_attributes(self):
        spec = copy.deepcopy(self.spec)
        spec["behaviors"][5]["ops"][0]["set"]["ref"] = "{ref.__class__}"
        built = plant.build(spec)
        data = built["data_bytes"].decode()
        self.assertIn("{ref.__class__}", data)          # left as plain text, not evaluated
        self.assertNotIn("<class", data)

    def test_duplicate_must_be_the_only_op(self):
        spec = copy.deepcopy(self.spec)
        spec["behaviors"][0]["ops"].append({"op": "shift", "column": "day", "delta": 1})
        self.bad(spec)

    def test_op_targets_are_checked_against_column_kind(self):
        spec = copy.deepcopy(self.spec)
        spec["behaviors"][1]["ops"][0]["column"] = "day"          # scale needs a by_column column
        self.bad(spec)
        spec = copy.deepcopy(self.spec)
        spec["behaviors"][2]["ops"][0]["column"] = "memo"         # shift needs an integer column
        self.bad(spec)
        spec = copy.deepcopy(self.spec)
        spec["behaviors"][1]["ops"][0]["factor"] = 1               # a factor of 1 plants nothing
        self.bad(spec)

    def test_column_rules(self):
        spec = copy.deepcopy(self.spec)
        spec["columns"][1]["name"] = "row_id"
        self.bad(spec)
        spec = copy.deepcopy(self.spec)
        del spec["columns"][5]["ranges"]["rent"]
        self.bad(spec)
        spec = copy.deepcopy(self.spec)
        spec["columns"][4]["of"] = "memo"
        self.bad(spec)
        spec = copy.deepcopy(self.spec)
        spec["columns"][2]["weights"] = [1, 2]
        self.bad(spec)

    def test_ops_that_change_nothing_are_an_error_not_a_silent_no_op(self):
        spec = {"name": "tiny", "seed": 1, "rows": 5, "columns": [{"name": "memo", "kind": "choice", "values": ["a"]}],
                "behaviors": [{"id": "same", "role": "positive", "count": 2, "ops": [{"op": "set", "column": "memo", "value": "a"}]}]}
        with self.assertRaises(plant.SpecError) as ctx:
            plant.build(spec)
        self.assertIn("changed nothing", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
