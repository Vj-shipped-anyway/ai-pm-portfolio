import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
from fixtures import SOURCE, fresh
from helpers import run
from kyb_packet_check import InputError, check_packet, parse_extraction


class BadShape(unittest.TestCase):
    def assertRejected(self, obj):
        with self.assertRaises(InputError):
            parse_extraction(obj)

    def test_not_an_object(self):
        for obj in (None, [], "text", 5, [fresh()]):
            self.assertRejected(obj)

    def test_holders_missing_or_wrong(self):
        ex = fresh()
        del ex["holders"]
        self.assertRejected(ex)
        for bad in (None, "x", {"a": 1}, [1, 2], [[]]):
            ex = fresh()
            ex["holders"] = bad
            self.assertRejected(ex)

    def test_percent_must_be_a_finite_number(self):
        for bad in ("60", None, True, [60], float("nan"), float("inf"), 10 ** 400):
            ex = fresh()
            ex["holders"][0]["pct"] = bad
            self.assertRejected(ex)

    def test_kind_and_text_fields(self):
        ex = fresh()
        ex["holders"][0]["kind"] = "trust"
        self.assertRejected(ex)
        ex = fresh()
        ex["holders"][0]["name"] = 7
        self.assertRejected(ex)
        ex = fresh()
        ex["people"][0]["id_last4"] = 4821          # a number would lose a leading zero
        self.assertRejected(ex)

    def test_records_must_be_objects_or_null(self):
        for key in ("control_person", "certification"):
            ex = fresh()
            ex[key] = "Dana"
            self.assertRejected(ex)
            ex[key] = None
            parse_extraction(ex)

    def test_a_percent_out_of_range_is_a_finding_not_an_error(self):
        ex = fresh()
        ex["holders"][0]["pct"] = 250
        self.assertIn("pct_out_of_range", [f["kind"] for f in check_packet(SOURCE, ex)])


class BadFiles(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, data):
        p = os.path.join(self.dir.name, name)
        with open(p, "wb") as fh:
            fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        return p

    def good(self):
        return self.write("src.txt", SOURCE), self.write("ex.json", json.dumps(fresh()))

    def assertExit2(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)

    def test_good_input_exits_0(self):
        s, e = self.good()
        self.assertEqual(run(["check", s, e])[0], 0)

    def test_empty_files(self):
        s, e = self.good()
        for empty in (b"", b"  \n"):
            self.assertExit2(["check", self.write("empty.txt", empty), e])
            self.assertExit2(["check", s, self.write("empty.json", empty)])

    def test_truncated_and_wrong_type_json(self):
        s, _ = self.good()
        text = json.dumps(fresh())
        for bad in (text[:40], "{", "[]", "null", "5", '"x"', "{}", '{"holders": "x"}', "not json"):
            self.assertExit2(["check", s, self.write("bad.json", bad)])

    def test_deeply_nested_json(self):
        s, _ = self.good()
        self.assertExit2(["check", s, self.write("deep.json", "[" * 200000)])

    def test_missing_file_and_directory(self):
        s, e = self.good()
        self.assertExit2(["check", os.path.join(self.dir.name, "nope.txt"), e])
        self.assertExit2(["check", s, self.dir.name])

    def test_source_that_is_not_text(self):
        _, e = self.good()
        self.assertExit2(["check", self.write("bin.txt", b"\xff\xfe\x00\x80 not utf-8 \xc3("), e])

    def test_bad_options(self):
        s, e = self.good()
        for opt in (["--tolerance", "-1"], ["--tolerance", "nan"], ["--tolerance", "abc"], ["--fail-on", "sometimes"], ["--nope"]):
            self.assertExit2(["check", s, e] + opt)
        self.assertExit2(["check", s])
        self.assertExit2(["frobnicate"])

    def test_no_arguments_prints_help_and_exits_2(self):
        code, out, _ = run([])
        self.assertEqual(code, 2)
        self.assertIn("usage", out)


if __name__ == "__main__":
    unittest.main()
