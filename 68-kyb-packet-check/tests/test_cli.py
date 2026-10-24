import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
from fixtures import SOURCE, fresh
from helpers import run


class Cli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def files(self, ex):
        s = os.path.join(self.dir.name, "src.txt")
        e = os.path.join(self.dir.name, "ex.json")
        with open(s, "w", encoding="utf-8") as fh:
            fh.write(SOURCE)
        with open(e, "w", encoding="utf-8") as fh:
            json.dump(ex, fh)
        return s, e

    def test_input_error_line_is_cleaned_even_when_the_message_was_not(self):
        from unittest import mock
        import kyb_packet_check as kpc
        s, e = self.files(fresh())
        with mock.patch.object(kpc, "read_text", side_effect=kpc.InputError("a\n::error::forged\r::notice::x")):
            code, out, err = run(["check", s, e])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("a\\x0a::error::forged", err)

    def test_demo_prints_the_two_swapped_percents_and_exits_0(self):
        code, out, err = run(["--demo"])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.count("pct_not_in_source"), 2)
        self.assertIn("decision: REVIEW (2 findings)", out)

    def test_clean_packet_exits_0(self):
        code, out, _ = run(["check"] + list(self.files(fresh())))
        self.assertEqual(code, 0)
        self.assertIn("decision: PASS (0 findings)", out)
        self.assertIn("owners at 25 percent or more as read: Dana A. Whitfield 60%, Tomas Reyes 25%", out)

    def test_a_finding_exits_1_and_never_keeps_exit_0(self):
        ex = fresh()
        ex["holders"][1]["pct"] = 2.5
        s, e = self.files(ex)
        code, out, _ = run(["check", s, e])
        self.assertEqual(code, 1)
        self.assertIn("pct_not_in_source", out)
        self.assertEqual(run(["check", s, e, "--fail-on", "never"])[0], 0)

    def test_tolerance_option(self):
        ex = fresh()
        ex["holders"][2]["pct"] = 14.95
        s, e = self.files(ex)
        self.assertEqual(run(["check", s, e])[0], 1)               # 14.95 is not on the source line
        ex["holders"][2]["pct"] = 15
        ex["holders"][0]["pct"] = 60.05
        s, e = self.files(ex)
        self.assertIn("direct_sum", run(["check", s, e, "--tolerance", "0.01"])[1])
        self.assertNotIn("direct_sum", run(["check", s, e])[1])

    def test_output_says_what_was_checked(self):
        _, out, _ = run(["check"] + list(self.files(fresh())))
        self.assertIn("checked: 3 holders, 0 look-through rows, 2 people against 11 source lines", out)


if __name__ == "__main__":
    unittest.main()
