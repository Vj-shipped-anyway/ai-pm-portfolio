import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import chargeback_packet as cp
from _fixtures import base


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cp.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, obj=None, text=None):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text if text is not None else json.dumps(obj))
        return p

    def assert_input_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertTrue(err.startswith("input error: "))
        self.assertNotIn("Traceback", err)

    def test_demo_prints_three_lines_and_exits_0(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 3)
        self.assertIn("decision: FIX (1 problem, 4 days left)", out)

    def test_ready_packet_exits_0(self):
        code, out, _ = run(["check", self.write("c.json", base()), "--as-of", "2026-02-28"])
        self.assertEqual(code, 0)
        self.assertIn("decision: READY (4 days left)", out)

    def test_fix_exits_1(self):
        c = base()
        c["docs"] = c["docs"][:1]
        code, out, _ = run(["check", self.write("c.json", c), "--as-of", "2026-02-28"])
        self.assertEqual(code, 1)
        self.assertIn("missing_evidence", out)

    def test_late_exits_1(self):
        code, out, _ = run(["check", self.write("c.json", base()), "--as-of", "2026-03-05"])
        self.assertEqual(code, 1)
        self.assertIn("decision: LATE (1 day past the deadline)", out)

    def test_list_of_cases_ends_with_a_summary(self):
        late = base()
        late["case_id"] = "T-2"
        late["submitted_date"] = "2026-03-10"
        code, out, _ = run(["check", self.write("c.json", [base(), late]), "--as-of", "2026-02-28"])
        self.assertEqual(code, 1)
        self.assertEqual(out.splitlines()[-1], "summary: 2 packets: 1 READY, 0 FIX, 1 LATE")

    def test_custom_rules_file(self):
        rules = cp.load_rules()
        rules["reason_codes"]["RC-02"]["window_days"] = 1
        code, out, _ = run(["check", self.write("c.json", base()), "--rules", self.write("r.json", rules), "--as-of", "2026-02-28"])
        self.assertEqual(code, 1)
        self.assertIn("LATE", out)

    def test_missing_file_exits_2(self):
        self.assert_input_error(["check", os.path.join(self.dir.name, "nope.json")])

    def test_empty_and_truncated_files_exit_2(self):
        self.assert_input_error(["check", self.write("empty.json", text="")])
        self.assert_input_error(["check", self.write("cut.json", text=json.dumps(base())[:60])])

    def test_wrong_type_files_exit_2(self):
        for i, text in enumerate(["5", '"x"', "null", "[1, 2]", "{}", '{"case_id": 5}']):
            self.assert_input_error(["check", self.write(f"t{i}.json", text=text)])

    def test_empty_list_says_nothing_was_checked(self):
        code, out, err = run(["check", self.write("c.json", [])])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("nothing was checked", err)

    def test_bad_rules_file_exits_2(self):
        c = self.write("c.json", base())
        self.assert_input_error(["check", c, "--rules", self.write("r.json", {})])
        self.assert_input_error(["check", c, "--rules", self.write("r2.json", text="[")])

    def test_bad_as_of_exits_2(self):
        c = self.write("c.json", base())
        self.assert_input_error(["check", c, "--as-of", "yesterday"])
        self.assert_input_error(["check", c, "--as-of", "2026-13-01"])

    def test_deeply_nested_json_exits_2(self):
        self.assert_input_error(["check", self.write("deep.json", text="[" * 200000)])

    def test_hostile_strings_cannot_forge_a_log_line(self):
        c = base()
        evil = "X\n::error title=forged::approved\r\x1b[31m%0A"
        c["case_id"] = "T-9" + evil
        c["docs"][0]["doc_id"] = "a" + evil
        c["docs"][1]["ref_id"] = evil
        c["docs"][1]["doc_type"] = "delivery_tracking"
        c["docs"].append({"doc_id": "z", "doc_type": evil, "ref_id": "O-1", "doc_date": "2026-01-14", "pages": 1})
        code, out, _ = run(["check", self.write("c.json", c), "--as-of", "2026-02-28"])
        self.assertEqual(code, 1)
        self.assertNotIn("\r", out)
        self.assertNotIn("\x1b", out)
        for line in out.splitlines():
            self.assertTrue(line.startswith(("case ", "  [", "decision: ")), repr(line))
        self.assertIn("\\n::error", out)

    def test_hostile_reason_code_in_the_error_is_one_line(self):
        c = base()
        c["reason_code"] = "RC-9\n::error::boom\r"
        self.assert_input_error(["check", self.write("c.json", c)])

    def test_no_arguments_prints_help_and_exits_2(self):
        code, out, _ = run([])
        self.assertEqual(code, 2)
        self.assertIn("usage", out)


if __name__ == "__main__":
    unittest.main()
