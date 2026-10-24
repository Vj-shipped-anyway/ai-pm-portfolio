import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import common
import plant


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = plant.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spec = common.demo_spec()

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def write(self, name, text):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            fh.write(text)
        return self.path(name)

    def snapshot(self, folder):
        files = {}
        for name in os.listdir(folder):
            with open(os.path.join(folder, name), "rb") as fh:
                files[name] = fh.read()
        return files

    def assert_clean_exit_2(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)

    def test_demo_prints_three_lines_and_exits_0(self):
        code, out, err = run(["--demo"])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(len(out.strip().splitlines()), 3)
        self.assertIn("weakest behavior: memo_injection_paraphrase, found 0 of 12", out)

    def test_generate_writes_three_files_and_a_rerun_matches(self):
        spec = self.write("s.json", json.dumps(self.spec))
        out_dir = self.path("out")
        code, out, _ = run(["generate", spec, "--out", out_dir])
        self.assertEqual(code, 0)
        self.assertEqual(sorted(os.listdir(out_dir)), ["demo_data.csv", "demo_manifest.json", "demo_truth.csv"])
        first = self.snapshot(out_dir)
        run(["generate", spec, "--out", out_dir])
        self.assertEqual(first, self.snapshot(out_dir))

    def test_generate_then_score_round_trip(self):
        out_dir = self.path("out")
        run(["generate", self.write("s.json", json.dumps(self.spec)), "--out", out_dir])
        ids = [t["row_id"] for t in plant.build(self.spec)["truth"] if t["role"] == "positive"]
        flags = self.write("f.csv", "row_id\n" + "\n".join(str(i) for i in ids) + "\n")
        code, out, _ = run(["score", os.path.join(out_dir, "demo"), flags])
        self.assertEqual(code, 0)
        self.assertIn("found 84 of 84 planted failures (recall 1.00)", out)
        self.assertIn("flagged 0 of 30 planted look-alikes", out)

    def test_bad_specs_exit_2_with_one_line(self):
        cases = {"empty": "", "truncated": '{"name": "demo", "seed": 58, "rows": 6', "list": "[1, 2]", "number": "5", "null": "null",
                 "deep": "[" * 100000, "not json": "name: demo", "lone surrogate": json.dumps(dict(self.spec, columns=[
                     {"name": "memo", "kind": "choice", "values": ["\ud800"]}], behaviors=[{"id": "b", "role": "positive", "count": 1, "ops": [{"op": "set", "column": "memo", "value": "z"}]}]))}
        for label, text in cases.items():
            with self.subTest(label):
                self.assert_clean_exit_2(["generate", self.write("s.json", text), "--out", self.path("o")])

    def test_missing_spec_and_unwritable_output_exit_2(self):
        self.assert_clean_exit_2(["generate", self.path("nope.json"), "--out", self.path("o")])
        blocker = self.write("blocker", "x")
        self.assert_clean_exit_2(["generate", self.write("s.json", json.dumps(self.spec)), "--out", blocker])

    def test_hostile_behavior_id_never_reaches_output_as_a_new_line(self):
        spec = json.loads(json.dumps(self.spec))
        spec["behaviors"][0]["id"] = "x\n::error::forged"
        code, out, err = run(["generate", self.write("s.json", json.dumps(spec)), "--out", self.path("o")])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(len(err.splitlines()), 1)
        self.assertTrue(err.startswith("input error:"))

    def test_unknown_key_in_spec_is_escaped(self):
        spec = dict(self.spec)
        spec["bad\n::error::key"] = 1
        code, _, err = run(["generate", self.write("s.json", json.dumps(spec)), "--out", self.path("o")])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.splitlines()), 1)

    def test_score_bad_inputs_exit_2(self):
        out_dir = self.path("out")
        run(["generate", self.write("s.json", json.dumps(self.spec)), "--out", out_dir])
        key = os.path.join(out_dir, "demo")
        self.assert_clean_exit_2(["score", key, self.path("missing.csv")])
        self.assert_clean_exit_2(["score", key, self.write("f.csv", "row_id\n99999\n")])
        self.assert_clean_exit_2(["score", key, self.write("g.csv", "")])
        self.assert_clean_exit_2(["score", key, self.write("h.csv", "id\n1\n")])
        self.assert_clean_exit_2(["score", self.path("nokey"), self.write("i.csv", "row_id\n1\n")])

    def test_score_with_no_flags_says_so(self):
        out_dir = self.path("out")
        run(["generate", self.write("s.json", json.dumps(self.spec)), "--out", out_dir])
        code, out, _ = run(["score", os.path.join(out_dir, "demo"), self.write("f.csv", "row_id\n")])
        self.assertEqual(code, 0)
        self.assertIn("no rows were flagged", out)

    def test_min_recall_sets_exit_1(self):
        out_dir = self.path("out")
        run(["generate", self.write("s.json", json.dumps(self.spec)), "--out", out_dir])
        flags = self.write("f.csv", "row_id\n1\n")
        key = os.path.join(out_dir, "demo")
        self.assertEqual(run(["score", key, flags, "--min-recall", "0.5"])[0], 1)
        self.assertEqual(run(["score", key, flags, "--min-recall", "0"])[0], 0)
        self.assertEqual(run(["score", key, flags])[0], 0)
        for bad in ("2", "-1", "nan", "abc"):
            self.assertEqual(run(["score", key, flags, "--min-recall", bad])[0], 2)

    def test_no_arguments_prints_help_and_exits_2(self):
        code, out, _ = run([])
        self.assertEqual(code, 2)
        self.assertIn("usage", out)


if __name__ == "__main__":
    unittest.main()
