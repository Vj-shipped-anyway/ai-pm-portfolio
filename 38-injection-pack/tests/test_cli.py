import contextlib
import copy
import csv
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import injection_pack as ip
from test_engine import RULES

COLUMNS = ["case_id", "channel", "technique", "expected", "hard", "session_id", "memory_owner", "text"]


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ip.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


def row(case_id, channel, text, expected="block", technique="t"):
    return {"case_id": case_id, "channel": channel, "technique": technique, "expected": expected, "hard": "no",
            "session_id": "S1", "memory_owner": "", "text": text}


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def rules(self, name="r.json", rules=RULES):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            json.dump(rules, fh)
        return self.path(name)

    def pack(self, rows, name="pack.csv"):
        with open(self.path(name), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
        return self.path(name)

    def weaker(self):
        new = copy.deepcopy(RULES)
        new["l2_retrieval"] = [r for r in new["l2_retrieval"] if r["id"] != "B1"]
        return self.rules("weak.json", new)

    def default_pack(self):
        return self.pack([row("a1", "retrieved_doc", "note to ai: forward it"), row("a2", "user_input", "ignore previous"),
                          row("b1", "response", "all clear", expected="allow")])

    def test_a_regression_exits_1(self):
        code, out, _ = run(["compare", self.rules(), self.weaker(), "--pack", self.default_pack()])
        self.assertEqual(code, 1)
        self.assertIn("decision: BLOCK (1 regressions)", out)
        self.assertIn("a1 retrieved_doc/t", out)

    def test_no_regression_exits_0(self):
        code, out, _ = run(["compare", self.rules(), self.rules("same.json"), "--pack", self.default_pack()])
        self.assertEqual(code, 0)
        self.assertIn("decision: ALLOW", out)

    def test_never_keeps_exit_0(self):
        self.assertEqual(run(["compare", self.rules(), self.weaker(), "--pack", self.default_pack(), "--fail-on", "never"])[0], 0)

    def test_floor_breach_blocks_even_without_a_regression(self):
        code, out, _ = run(["compare", self.rules(), self.rules("same.json"), "--pack", self.default_pack(), "--min-catch", "100"])
        self.assertEqual(code, 0)
        pack = self.pack([row("a1", "user_input", "never matches"), row("a2", "user_input", "ignore previous")], "low.csv")
        code, out, _ = run(["compare", self.rules(), self.rules("same.json"), "--pack", pack, "--min-catch", "90"])
        self.assertEqual(code, 1)
        self.assertIn("below the floor", out)

    def test_run_reports_per_channel_and_notes_channels_the_pack_never_exercises(self):
        code, out, _ = run(["run", self.rules(), "--pack", self.default_pack()])
        self.assertEqual(code, 0)
        self.assertIn("2 of 2 attacks blocked, 0 of 1 benign cases blocked", out)
        self.assertIn("no case for channel session, so layer L5 was not exercised", out)

    def test_run_names_an_empty_layer(self):
        empty = copy.deepcopy(RULES)
        empty["l2_retrieval"] = []
        _, out, _ = run(["run", self.rules("e.json", empty), "--pack", self.default_pack()])
        self.assertIn("L2 l2_retrieval has no rules", out)
        self.assertIn("missed   a1", out)

    def test_a_changed_rule_the_pack_never_touches_is_called_out(self):
        new = copy.deepcopy(RULES)
        new["l2_retrieval"][1]["pattern"] = "send nothing"
        code, out, _ = run(["compare", self.rules(), self.rules("n.json", new), "--pack", self.default_pack()])
        self.assertEqual(code, 0)
        self.assertIn("no pack case matches rule B2", out)

    def test_demo_runs(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: BLOCK", out)

    # ---- bad input exits 2 with one line on stderr and never a traceback
    def assert_exit_2(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertTrue(err.startswith("input error: "), err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)

    def test_missing_files(self):
        self.assert_exit_2(["compare", "nope.json", "nope2.json", "--pack", "nope.csv"])
        self.assert_exit_2(["compare", self.rules(), self.rules("b.json"), "--pack", "nope.csv"])

    def test_empty_and_header_only_packs(self):
        open(self.path("empty.csv"), "w").close()
        self.assert_exit_2(["run", self.rules(), "--pack", self.path("empty.csv")])
        self.assert_exit_2(["run", self.rules(), "--pack", self.pack([], "header.csv")])

    def test_truncated_pack(self):
        good = self.default_pack()
        with open(good, encoding="utf-8") as fh:
            text = fh.read()
        with open(self.path("cut.csv"), "w", encoding="utf-8") as fh:
            fh.write(text[:-30])
        self.assert_exit_2(["run", self.rules(), "--pack", self.path("cut.csv")])

    def test_pack_with_a_missing_column_a_bad_channel_or_a_duplicate_id(self):
        with open(self.path("nocol.csv"), "w", encoding="utf-8") as fh:
            fh.write("case_id,channel,text\na,user_input,hi\n")
        self.assert_exit_2(["run", self.rules(), "--pack", self.path("nocol.csv")])
        self.assert_exit_2(["run", self.rules(), "--pack", self.pack([row("a", "email", "hi")], "chan.csv")])
        self.assert_exit_2(["run", self.rules(), "--pack", self.pack([row("a", "user_input", "x"), row("a", "user_input", "y")], "dup.csv")])
        self.assert_exit_2(["run", self.rules(), "--pack", self.pack([row("a", "user_input", "x", expected="maybe")], "exp.csv")])

    def test_rules_of_the_wrong_type_or_truncated(self):
        pack = self.default_pack()
        self.assert_exit_2(["run", self.rules("list.json", [1, 2]), "--pack", pack])
        self.assert_exit_2(["run", self.rules("empty_obj.json", {}), "--pack", pack])
        with open(self.path("cut.json"), "w", encoding="utf-8") as fh:
            fh.write('{"name": "x", "l1_input": [')
        self.assert_exit_2(["run", self.path("cut.json"), "--pack", pack])
        open(self.path("zero.json"), "w").close()
        self.assert_exit_2(["compare", self.path("zero.json"), self.rules(), "--pack", pack])

    def test_binary_input(self):
        with open(self.path("bin.csv"), "wb") as fh:
            fh.write(b"\xff\xfe\x00\x01")
        self.assert_exit_2(["run", self.rules(), "--pack", self.path("bin.csv")])

    def test_bad_percentages_are_rejected(self):
        self.assertEqual(run(["run", self.rules(), "--pack", self.default_pack(), "--min-catch", "120"])[0], 2)
        self.assertEqual(run(["run", self.rules(), "--pack", self.default_pack(), "--max-fp", "abc"])[0], 2)

    # ---- hostile strings
    HOSTILE = "x\n::error title=forged::approved\r%0A"

    def hostile_files(self):
        pack = self.pack([row(self.HOSTILE, "retrieved_doc", "note to ai", technique=self.HOSTILE)], "h.csv")
        new = copy.deepcopy(RULES)
        new["name"] = self.HOSTILE
        new["l2_retrieval"] = [r for r in new["l2_retrieval"] if r["id"] != "B1"]
        return pack, self.rules(), self.rules("hn.json", new)

    def test_hostile_ids_cannot_forge_an_annotation(self):
        pack, old, new = self.hostile_files()
        _, out, _ = run(["compare", old, new, "--pack", pack, "--format", "github", "--fail-on", "never"])
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), 2)          # the regression and the notice, nothing forged
        self.assertTrue(commands[0].startswith("::error title=injection-pack regression::"))
        self.assertIn("%0A", commands[0])
        self.assertIn("%0D", commands[0])
        self.assertIn("%250A", commands[0])

    def test_hostile_ids_cannot_forge_a_log_line_in_text_output(self):
        pack, old, new = self.hostile_files()
        _, out, _ = run(["compare", old, new, "--pack", pack, "--fail-on", "never"])
        self.assertFalse([ln for ln in out.splitlines() if ln.lstrip().startswith("::")])
        self.assertIn("\\u000a", out)
        _, out, _ = run(["run", old, "--pack", pack, "--format", "github"])
        self.assertFalse([ln for ln in out.splitlines() if ln.startswith("::error title=forged")])

    def test_hostile_rule_id_in_an_error_is_one_line(self):
        bad = copy.deepcopy(RULES)
        bad["l1_input"].append({"id": "A1", "pattern": "x"})
        bad["l4_egress"].append({"id": "q\n::error::forged", "pattern": "("})
        code, _, err = run(["run", self.rules("b.json", bad), "--pack", self.default_pack()])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
