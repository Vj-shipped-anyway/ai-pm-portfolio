import contextlib
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401
import feature_contract as fc

SRC = _bootstrap.SRC
CONTRACT = {"contract": "t", "version": "1.0.0", "max_bad_rate": 0.02, "fields": [
    {"name": "id", "type": "string"},
    {"name": "ratio", "type": "number", "min": 0, "max": 1},
    {"name": "kind", "type": "string", "allowed": ["a", "b"]}]}


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = fc.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.contract = self.write_json("contract.json", CONTRACT)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def write_json(self, name, obj):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return self.path(name)

    def write_text(self, name, text, mode="w"):
        with open(self.path(name), mode, **({} if "b" in mode else {"encoding": "utf-8", "newline": ""})) as fh:
            fh.write(text)
        return self.path(name)

    def write_csv(self, name, header, rows):
        with open(self.path(name), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        return self.path(name)

    def rows(self, n=50, ratio="0.5", kind="a"):
        return [["X-%d" % i, ratio, kind] for i in range(n)]

    # ------------------------------------------------------------ decisions and exit codes
    def test_clean_batch_exits_0(self):
        b = self.write_csv("b.csv", ["id", "ratio", "kind"], self.rows())
        code, out, _ = run(["check", self.contract, b])
        self.assertEqual(code, 0)
        self.assertIn("no violations", out)
        self.assertIn("decision: PASS", out)

    def test_broken_field_exits_1(self):
        b = self.write_csv("b.csv", ["id", "ratio", "kind"], self.rows(ratio="50"))
        code, out, _ = run(["check", self.contract, b])
        self.assertEqual(code, 1)
        self.assertIn("above_max", out)
        self.assertIn("decision: FAIL", out)

    def test_warn_exits_0_unless_asked(self):
        b = self.write_csv("b.csv", ["id", "ratio", "kind", "extra"], [r + ["z"] for r in self.rows()])
        self.assertEqual(run(["check", self.contract, b])[0], 0)
        self.assertEqual(run(["check", self.contract, b, "--fail-on", "warn"])[0], 1)

    def test_never_keeps_exit_0(self):
        b = self.write_csv("b.csv", ["id", "ratio", "kind"], self.rows(ratio="50"))
        self.assertEqual(run(["check", self.contract, b, "--fail-on", "never"])[0], 0)

    def test_github_format_emits_error_annotation(self):
        b = self.write_csv("b.csv", ["id", "ratio", "kind"], self.rows(ratio="50"))
        _, out, _ = run(["check", self.contract, b, "--format", "github"])
        self.assertTrue(out.startswith("::error title=feature-contract above_max::"))
        self.assertIn("::notice", out)

    def test_jsonl_batch_is_typed(self):
        lines = "\n".join(json.dumps({"id": "X", "ratio": "0.5", "kind": "a"}) for _ in range(20))
        b = self.write_text("b.jsonl", lines + "\n")
        code, out, _ = run(["check", self.contract, b])
        self.assertEqual(code, 1)
        self.assertIn("type_mismatch", out)
        good = self.write_text("g.jsonl", "\n".join(json.dumps({"id": "X", "ratio": 0.5, "kind": "a"}) for _ in range(20)))
        self.assertEqual(run(["check", self.contract, good])[0], 0)

    def test_jsonl_missing_key_is_a_null(self):
        lines = "\n".join(json.dumps({"id": "X", "kind": "a"} if i else {"id": "X", "ratio": 0.5, "kind": "a"}) for i in range(10))
        b = self.write_text("b.jsonl", lines)
        _, out, _ = run(["check", self.contract, b, "--fail-on", "never"])
        self.assertIn("null_rate", out)

    def test_bom_and_blank_lines_are_tolerated(self):
        b = self.write_text("b.csv", "﻿id,ratio,kind\n" + "".join("X,0.5,a\n\n" for _ in range(5)))
        self.assertEqual(run(["check", self.contract, b])[0], 0)

    def test_demo_runs(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertEqual(len(out.strip().splitlines()), 3)
        self.assertIn("decision: FAIL", out)

    # ------------------------------------------------------------ malformed input exits 2, one line, no traceback
    def assert_input_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("input error: "), err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)

    def test_missing_files(self):
        self.assert_input_error(["check", "nope.json", "nope.csv"])
        b = self.write_csv("b.csv", ["id", "ratio", "kind"], self.rows())
        self.assert_input_error(["check", self.path("nope.json"), b])
        self.assert_input_error(["check", self.contract, self.path("nope.csv")])

    def test_directory_instead_of_file(self):
        self.assert_input_error(["check", self.dir.name, self.dir.name + ".csv"])

    def test_empty_batch_files(self):
        self.assert_input_error(["check", self.contract, self.write_text("e.csv", "")])
        self.assert_input_error(["check", self.contract, self.write_text("h.csv", "id,ratio,kind\n")])
        self.assert_input_error(["check", self.contract, self.write_text("e.jsonl", "")])
        self.assert_input_error(["check", self.contract, self.write_text("n.jsonl", "\n\n")])

    def test_truncated_batch_files(self):
        self.assert_input_error(["check", self.contract, self.write_text("t.csv", "id,ratio,kind\nX,0.5,a\nX,0.")])
        self.assert_input_error(["check", self.contract, self.write_text("t.jsonl", '{"id": "X", "ratio": 0.5}\n{"id": "X", "rat')])

    def test_wrong_type_batch_files(self):
        self.assert_input_error(["check", self.contract, self.write_text("w.jsonl", "[1, 2]\n")])
        self.assert_input_error(["check", self.contract, self.write_text("w2.jsonl", "5\n")])
        self.assert_input_error(["check", self.contract, self.write_text("w.txt", "id,ratio,kind\nX,0.5,a\n")])

    def test_repeated_column_name(self):
        self.assert_input_error(["check", self.contract, self.write_text("d.csv", "id,ratio,ratio\nX,0.5,0.6\n")])

    def test_bytes_that_are_not_text(self):
        self.assert_input_error(["check", self.contract, self.write_text("bin.csv", b"id,ratio\n\xff\xfe\x00\n", "wb")])
        self.assert_input_error(["check", self.contract, self.write_text("nul.csv", "id,ratio,kind\nX,0.5\x00,a\n")])

    def test_deeply_nested_json_is_input_error(self):
        deep = "[" * 100000 + "]" * 100000
        self.assert_input_error(["check", self.write_text("deep.json", deep), self.write_csv("b.csv", ["id"], [["x"]])])

    def test_malformed_contracts(self):
        b = self.write_csv("b.csv", ["id", "ratio", "kind"], self.rows())
        self.assert_input_error(["check", self.write_text("c1.json", ""), b])
        self.assert_input_error(["check", self.write_text("c2.json", '{"fields": [{"name": "a"'), b])
        self.assert_input_error(["check", self.write_json("c3.json", []), b])
        self.assert_input_error(["check", self.write_json("c4.json", {"fields": []}), b])
        self.assert_input_error(["check", self.write_json("c5.json", {"fields": [{"name": "a", "type": "number", "maximum": 5}]}), b])
        self.assert_input_error(["check", self.write_json("c6.json", {"fields": 5}), b])

    def test_bad_arguments_exit_2(self):
        self.assertEqual(run([])[0], 2)
        self.assertEqual(run(["check", "only-one"])[0], 2)
        self.assertEqual(run(["check", self.contract, "b.csv", "--fail-on", "sometimes"])[0], 2)

    # ------------------------------------------------------------ hostile strings
    def test_hostile_column_name_cannot_forge_an_annotation(self):
        hostile = "bad\n::error title=forged::approved\r%0A"
        b = self.write_csv("b.csv", ["id", "ratio", "kind", hostile], [r + ["z"] for r in self.rows()])
        _, out, _ = run(["check", self.contract, b, "--format", "github"])
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), len(out.splitlines()))
        self.assertEqual(len(commands), 2)          # the unexpected-column warning and the notice, nothing forged
        self.assertTrue(commands[0].startswith("::warning title=feature-contract unexpected_column::"))
        self.assertNotIn("\r", out)

    def test_hostile_value_cannot_forge_a_line_in_text_or_github_output(self):
        hostile = "zz\n::error title=forged::approved\r"
        b = self.write_csv("b.csv", ["id", "ratio", "kind"], self.rows(kind=hostile))
        for fmt in ("text", "github"):
            _, out, _ = run(["check", self.contract, b, "--format", fmt, "--fail-on", "never"])
            lines = out.splitlines()
            self.assertFalse([ln for ln in lines if ln.startswith("::error title=forged")], out)
            self.assertNotIn("\r", out)
            if fmt == "github":
                self.assertEqual(sum(1 for ln in lines if ln.startswith("::")), len(lines))
            else:
                self.assertTrue(all(ln.startswith(("contract:", "  [", "decision:")) for ln in lines), out)

    def test_hostile_contract_name_stays_on_its_line(self):
        c = dict(CONTRACT, contract="n\n::error::forged")
        b = self.write_csv("b.csv", ["id", "ratio", "kind"], self.rows())
        for fmt in ("text", "github"):
            _, out, _ = run(["check", self.write_json("h.json", c), b, "--format", fmt])
            self.assertFalse([ln for ln in out.splitlines() if ln.startswith("::error")], out)

    def test_percent_signs_are_escaped_in_annotations(self):
        b = self.write_csv("b.csv", ["id", "ratio", "kind"], self.rows(kind="100%"))
        _, out, _ = run(["check", self.contract, b, "--format", "github", "--fail-on", "never"])
        self.assertIn("100%25", out)

    def test_a_path_that_starts_with_a_dash_works_after_double_dash(self):
        self.write_csv("-b.csv", ["id", "ratio", "kind"], self.rows())
        self.write_json("-c.json", CONTRACT)
        r = subprocess.run([sys.executable, os.path.join(SRC, "feature_contract.py"), "check", "--", "-c.json", "-b.csv"],
                           cwd=self.dir.name, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("decision: PASS", r.stdout)


if __name__ == "__main__":
    unittest.main()
