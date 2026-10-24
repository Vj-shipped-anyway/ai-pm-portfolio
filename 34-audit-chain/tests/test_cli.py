import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401
import audit_chain as ac
from support import TempDir, chain, event, lines, run

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


class VerifyCommandTests(TempDir, unittest.TestCase):
    def test_an_intact_log_exits_0(self):
        code, out, err = run(["verify", self.write_log(chain(5))])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("5 events", out)
        self.assertIn("verdict: OK", out)

    def test_without_an_anchor_the_output_says_what_it_cannot_see(self):
        _, out, _ = run(["verify", self.write_log(chain(3))])
        self.assertIn("no anchor given", out)

    def test_an_altered_log_exits_1_and_names_the_line(self):
        evs = chain(5)
        evs[3]["detail"] = {"decided": "hold"}
        code, out, _ = run(["verify", self.write_log(evs)])
        self.assertEqual(code, 1)
        self.assertIn("line 4 (seq 4): hash does not match the event content", out)
        self.assertIn("verdict: ALTERED (1 problem)", out)

    def test_a_truncated_last_line_exits_1(self):
        text = "".join(x + "\n" for x in map(ac.dumps_event, chain(4)))
        code, out, _ = run(["verify", self.write("cut.jsonl", text[:-30])])
        self.assertEqual(code, 1)
        self.assertIn("line 4", out)

    def test_a_json_array_or_a_csv_is_a_finding_not_a_crash(self):
        for name, text in (("a.jsonl", "[1, 2, 3]\n"), ("b.jsonl", "id,name\n1,x\n"), ("c.jsonl", "5\n")):
            code, out, err = run(["verify", self.write(name, text)])
            self.assertEqual((code, err), (1, ""), name)
            self.assertIn("verdict: ALTERED", out)

    def test_a_missing_file_exits_2_with_one_line(self):
        code, out, err = run(["verify", os.path.join(self.dir, "nope.jsonl")])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err.count("\n"), 1)
        self.assertTrue(err.startswith("input error: cannot read"))

    def test_a_directory_exits_2(self):
        self.assertEqual(run(["verify", self.dir])[0], 2)

    def test_an_empty_log_exits_2_and_says_so(self):
        for name, content in (("empty.jsonl", ""), ("blank.jsonl", "\n\n  \n")):
            code, out, err = run(["verify", self.write(name, content)])
            self.assertEqual((code, out), (2, ""), name)
            self.assertIn("nothing to verify", err)

    def test_an_empty_log_with_an_anchor_is_a_finding(self):
        anchor = self.write_json("anchor.json", ac.make_anchor(chain(4)))
        code, out, _ = run(["verify", self.write("empty.jsonl", ""), "--anchor", anchor])
        self.assertEqual(code, 1)
        self.assertIn("anchor was taken at event 4", out)

    def test_the_anchor_catches_a_cut_and_a_rewrite(self):
        evs = chain(8)
        anchor = self.write_json("anchor.json", ac.make_anchor(evs, 6))
        code, out, _ = run(["verify", self.write_log(evs[:5]), "--anchor", anchor])
        self.assertEqual(code, 1)
        self.assertIn("events were removed", out)
        self.assertEqual(run(["verify", self.write_log(evs), "--anchor", anchor])[0], 0)

    def test_a_bad_anchor_exits_2(self):
        log = self.write_log(chain(3))
        good_hash = chain(3)[0]["hash"]
        bad = {
            "missing.json": None,
            "notjson.json": "{not json",
            "truncated.json": '{"version": 1, "seq": 2, "hash": "' + good_hash[:10],
            "array.json": "[1, 2]",
            "noseq.json": json.dumps({"version": 1, "hash": good_hash}),
            "strseq.json": json.dumps({"version": 1, "seq": "2", "hash": good_hash}),
            "boolseq.json": json.dumps({"version": 1, "seq": True, "hash": good_hash}),
            "zeroseq.json": json.dumps({"version": 1, "seq": 0, "hash": good_hash}),
            "shorthash.json": json.dumps({"version": 1, "seq": 2, "hash": "abc"}),
            "version.json": json.dumps({"version": 2, "seq": 2, "hash": good_hash}),
        }
        for name, text in bad.items():
            path = os.path.join(self.dir, name) if text is None else self.write(name, text)
            code, out, err = run(["verify", log, "--anchor", path])
            self.assertEqual((code, out), (2, ""), name)
            self.assertEqual(err.count("\n"), 1, name)
            self.assertTrue(err.startswith("input error:"), name)

    def test_no_arguments_and_an_unknown_command_exit_2(self):
        self.assertEqual(run([])[0], 2)
        self.assertEqual(run(["frobnicate"])[0], 2)
        self.assertEqual(run(["verify"])[0], 2)

    def test_more_than_ten_problems_are_summarised(self):
        evs = chain(30)
        for e in evs:
            e["detail"] = {"decided": "hold"}
        _, out, _ = run(["verify", self.write_log(evs)])
        self.assertIn("... and 20 more", out)
        self.assertIn("verdict: ALTERED (30 problems)", out)

    def test_the_demo_runs_and_shows_all_three_verdicts(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertEqual(out.count("verdict: OK"), 1)
        self.assertEqual(out.count("verdict: ALTERED"), 2)


class HostileTextTests(TempDir, unittest.TestCase):
    HOSTILE = "x\n::error::forged\r\x1b[2J%0A\ud800"

    def hostile_log(self):
        return self.write_log([event(1, ac.GENESIS, kind=self.HOSTILE)])

    def test_text_from_the_log_cannot_start_a_new_output_line(self):
        code, out, _ = run(["verify", self.hostile_log()])
        self.assertEqual(code, 1)
        for ln in out.splitlines():
            self.assertTrue(ln.startswith(("verify:", "  ", "verdict:")), repr(ln))
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\r", out)
        self.assertIn("%0A::error::forged%0D%1B[2J%250A%uD800", out)

    def test_a_lone_surrogate_does_not_break_real_output(self):
        r = subprocess.run([sys.executable, "audit_chain.py", "verify", self.hostile_log()], cwd=SRC, capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stderr), (1, ""))

    def test_a_hostile_key_in_a_duplicate_or_extra_field_is_escaped(self):
        ev = chain(1)[0]
        ev["a\n::error::x"] = 1
        _, out, _ = run(["verify", self.write_log([ev])])
        self.assertNotIn("\n::error", out)
        self.assertIn("a%0A::error::x", out)

    def test_a_hostile_path_is_escaped_in_every_message(self):
        hostile = os.path.join(self.dir, "a\n::error::b.jsonl")
        code, out, err = run(["verify", hostile])
        self.assertEqual(code, 2)
        self.assertEqual(err.count("\n"), 1)
        self.assertIn("%0A::error::b.jsonl", err)
        code, _, err = run(["verify", self.write_log(chain(2)), "--anchor", hostile])
        self.assertEqual((code, err.count("\n")), (2, 1))


class AnchorCommandTests(TempDir, unittest.TestCase):
    def test_prints_an_anchor_for_the_last_event(self):
        evs = chain(5)
        code, out, _ = run(["anchor", self.write_log(evs)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"version": 1, "seq": 5, "hash": evs[-1]["hash"]})

    def test_seq_and_out(self):
        evs = chain(5)
        target = os.path.join(self.dir, "anchor.json")
        code, out, _ = run(["anchor", self.write_log(evs), "--seq", "3", "--out", target])
        self.assertEqual(code, 0)
        self.assertIn("event 3", out)
        with open(target, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["hash"], evs[2]["hash"])

    def test_a_seq_outside_the_log_exits_2(self):
        for n in ("0", "6", "-1"):
            code, _, err = run(["anchor", self.write_log(chain(5)), "--seq", n])
            self.assertEqual(code, 2, n)
            self.assertEqual(err.count("\n"), 1)

    def test_refuses_to_anchor_a_log_that_does_not_verify(self):
        evs = chain(5)
        evs[1]["detail"] = {"decided": "hold"}
        code, out, err = run(["anchor", self.write_log(evs)])
        self.assertEqual(code, 1)
        self.assertIn("ALTERED", out)
        self.assertIn("refusing", err)

    def test_an_empty_log_exits_2_and_an_unwritable_target_exits_2(self):
        self.assertEqual(run(["anchor", self.write("e.jsonl", "")])[0], 2)
        self.assertEqual(run(["anchor", self.write_log(chain(2)), "--out", os.path.join(self.dir, "no", "such", "a.json")])[0], 2)


class AppendCommandTests(TempDir, unittest.TestCase):
    def append(self, path, **over):
        opts = {"case": "C1", "kind": "decision"}
        opts.update(over)
        args = ["append", path]
        for k, v in opts.items():
            args += ["--" + k, v]
        return run(args)

    def test_creates_the_log_and_extends_it(self):
        path = os.path.join(self.dir, "new.jsonl")
        for n in (1, 2, 3):
            code, out, _ = self.append(path, detail='{"k": "v"}')
            self.assertEqual(code, 0)
            self.assertIn("appended event %d" % n, out)
        code, out, _ = run(["verify", path])
        self.assertEqual(code, 0)
        self.assertIn("3 events", out)

    def test_a_log_ending_without_a_newline_is_not_glued_to_the_next_event(self):
        path = self.write("a.jsonl", "\n".join(lines(chain(2))))
        self.assertEqual(self.append(path)[0], 0)
        self.assertIn("3 events", run(["verify", path])[1])

    def test_refuses_to_extend_a_log_that_does_not_verify(self):
        evs = chain(4)
        evs[1]["detail"] = {"decided": "hold"}
        path = self.write_log(evs)
        before = self.read(path)
        code, _, err = self.append(path)
        self.assertEqual(code, 1)
        self.assertIn("refusing", err)
        self.assertEqual(self.read(path), before)

    def test_bad_arguments_exit_2_and_leave_the_file_alone(self):
        path = self.write_log(chain(2))
        before = self.read(path)
        cases = [dict(kind="note"), dict(detail="[1]"), dict(detail="{not json"), dict(detail='{"x": NaN}'),
                 dict(detail='{"x": 1e999}'), dict(detail="[" * 100000 + "]" * 100000), dict(case="")]
        for over in cases:
            code, _, err = self.append(path, **over)
            self.assertEqual(code, 2, list(over))
            self.assertEqual(err.count("\n"), 1, list(over))
        self.assertEqual(self.read(path), before)

    def test_an_unknown_kind_is_escaped_in_the_message(self):
        code, _, err = self.append(os.path.join(self.dir, "x.jsonl"), kind="a\n::error::b")
        self.assertEqual((code, err.count("\n")), (2, 1))
        self.assertIn("a%0A::error::b", err)


if __name__ == "__main__":
    unittest.main()
