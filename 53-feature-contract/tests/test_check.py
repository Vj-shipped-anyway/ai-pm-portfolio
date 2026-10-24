import unittest

import _bootstrap  # noqa: F401
from feature_contract import check_batch, decide

CONTRACT = {"contract": "t", "version": "1.0.0", "max_bad_rate": 0.02, "fields": [
    {"name": "id", "type": "string"},
    {"name": "ratio", "type": "number", "min": 0, "max": 1},
    {"name": "count", "type": "integer", "min": 0, "max": 500},
    {"name": "kind", "type": "string", "allowed": ["a", "b"]},
    {"name": "flag", "type": "boolean"},
    {"name": "opt", "type": "number", "min": 0, "max": 1, "max_null_rate": 0.05},
]}
COLUMNS = ["id", "ratio", "count", "kind", "flag", "opt"]


def batch(n=100, **override):
    """n clean rows; override maps a column name to a function of the row index."""
    rows = []
    for i in range(n):
        row = {"id": "X-%d" % i, "ratio": "0.5", "count": "3", "kind": "a", "flag": "true", "opt": "0.1"}
        for k, fn in override.items():
            row[k] = fn(i)
        rows.append([row[c] for c in COLUMNS])
    return rows


def kinds(findings):
    return sorted((f["kind"], f["field"]) for f in findings)


class CheckTests(unittest.TestCase):
    def test_clean_batch_passes(self):
        f = check_batch(CONTRACT, COLUMNS, batch())
        self.assertEqual(f, [])
        self.assertEqual(decide(f), "PASS")

    def test_missing_column_fails(self):
        cols = [c for c in COLUMNS if c != "ratio"]
        rows = [[v for c, v in zip(COLUMNS, r) if c != "ratio"] for r in batch()]
        self.assertEqual(kinds(check_batch(CONTRACT, cols, rows)), [("missing_field", "ratio")])

    def test_rename_is_a_missing_field_and_an_unexpected_column(self):
        cols = ["id", "ratio_v2", "count", "kind", "flag", "opt"]
        f = check_batch(CONTRACT, cols, batch())
        self.assertEqual(kinds(f), [("missing_field", "ratio"), ("unexpected_column", "ratio_v2")])
        self.assertEqual(decide(f), "FAIL")

    def test_reordered_columns_are_harmless(self):
        order = [5, 3, 1, 0, 4, 2]
        cols = [COLUMNS[i] for i in order]
        rows = [[r[i] for i in order] for r in batch()]
        self.assertEqual(check_batch(CONTRACT, cols, rows), [])

    def test_text_in_a_number_column(self):
        f = check_batch(CONTRACT, COLUMNS, batch(ratio=lambda i: "$0.50"))
        self.assertEqual(kinds(f), [("type_mismatch", "ratio")])

    def test_tolerance_boundary(self):
        two = check_batch(CONTRACT, COLUMNS, batch(ratio=lambda i: "9" if i < 2 else "0.5"))
        three = check_batch(CONTRACT, COLUMNS, batch(ratio=lambda i: "9" if i < 3 else "0.5"))
        self.assertEqual(two, [])
        self.assertEqual(kinds(three), [("above_max", "ratio")])

    def test_zero_default_tolerance(self):
        strict = {k: v for k, v in CONTRACT.items() if k != "max_bad_rate"}
        f = check_batch(strict, COLUMNS, batch(ratio=lambda i: "9" if i == 0 else "0.5"))
        self.assertEqual(kinds(f), [("above_max", "ratio")])

    def test_bounds_are_inclusive(self):
        f = check_batch(CONTRACT, COLUMNS, batch(ratio=lambda i: ["0", "1", "0.0", "1.0000"][i % 4]))
        self.assertEqual(f, [])

    def test_below_min_and_above_max_are_separate(self):
        f = check_batch(CONTRACT, COLUMNS, batch(count=lambda i: "-999" if i < 10 else "501" if i < 20 else "3"))
        self.assertEqual(kinds(f), [("above_max", "count"), ("below_min", "count")])

    def test_null_allowance(self):
        within = check_batch(CONTRACT, COLUMNS, batch(opt=lambda i: "" if i < 5 else "0.1"))
        over = check_batch(CONTRACT, COLUMNS, batch(opt=lambda i: "" if i < 6 else "0.1"))
        self.assertEqual(within, [])
        self.assertEqual(kinds(over), [("null_rate", "opt")])

    def test_a_field_with_no_allowance_fails_on_one_null(self):
        f = check_batch(CONTRACT, COLUMNS, batch(ratio=lambda i: "" if i == 0 else "0.5"))
        self.assertEqual(kinds(f), [("null_rate", "ratio")])

    def test_zero_fill_of_nulls_is_not_seen(self):
        # known limit: nulls replaced by 0 stay inside type, range and null rate
        self.assertEqual(check_batch(CONTRACT, COLUMNS, batch(opt=lambda i: "0" if i < 20 else "0.1")), [])

    def test_value_outside_allowed_list(self):
        f = check_batch(CONTRACT, COLUMNS, batch(kind=lambda i: "gig" if i < 10 else "b"))
        self.assertEqual(kinds(f), [("not_allowed", "kind")])

    def test_integer_column_with_decimal_text(self):
        self.assertEqual(check_batch(CONTRACT, COLUMNS, batch(count=lambda i: "12.0")), [])
        self.assertEqual(kinds(check_batch(CONTRACT, COLUMNS, batch(count=lambda i: "12.5"))), [("type_mismatch", "count")])

    def test_unexpected_column_policies(self):
        cols, rows = COLUMNS + ["extra"], [r + ["z"] for r in batch()]
        self.assertEqual(decide(check_batch(CONTRACT, cols, rows)), "WARN")
        self.assertEqual(decide(check_batch(dict(CONTRACT, unexpected_columns="allow"), cols, rows)), "PASS")
        self.assertEqual(decide(check_batch(dict(CONTRACT, unexpected_columns="fail"), cols, rows)), "FAIL")

    def test_a_batch_that_matches_no_field_says_so_for_each_field(self):
        f = check_batch(CONTRACT, ["other"], [["x"]] * 10)
        self.assertEqual([x["kind"] for x in f if x["kind"] == "missing_field"], ["missing_field"] * 6)
        self.assertEqual(decide(f), "FAIL")

    def test_no_rows_is_an_error_not_a_pass(self):
        with self.assertRaises(ValueError):
            check_batch(CONTRACT, COLUMNS, [])

    def test_typed_rows_keep_their_json_types(self):
        rows = [["X", "0.5", 3, "a", True, 0.1]] * 100
        f = check_batch(CONTRACT, COLUMNS, rows, typed=True)
        self.assertEqual(kinds(f), [("type_mismatch", "ratio")])
        rows = [["X", 0.5, 3, "a", True, None]] * 100
        self.assertEqual(kinds(check_batch(CONTRACT, COLUMNS, rows, typed=True)), [("null_rate", "opt")])

    def test_a_hostile_value_cannot_put_a_newline_in_a_reason(self):
        f = check_batch(CONTRACT, COLUMNS, batch(kind=lambda i: "x\n::error::forged\r%"))
        self.assertTrue(f)
        for item in f:
            self.assertNotIn("\n", item["reason"])
            self.assertNotIn("\r", item["reason"])

    def test_a_clean_single_row_passes_because_there_is_no_row_count_check(self):
        self.assertEqual(check_batch(CONTRACT, COLUMNS, batch(1)), [])

    def test_null_tokens_in_a_numeric_column_are_type_mismatches(self):
        for token in ("NA", "null", "N/A", "None"):
            f = check_batch(CONTRACT, COLUMNS, batch(ratio=lambda i, t=token: t))
            self.assertEqual(kinds(f), [("type_mismatch", "ratio")], token)

    def test_decide(self):
        self.assertEqual(decide([]), "PASS")
        self.assertEqual(decide([{"level": "warn"}]), "WARN")
        self.assertEqual(decide([{"level": "warn"}, {"level": "fail"}]), "FAIL")


if __name__ == "__main__":
    unittest.main()
