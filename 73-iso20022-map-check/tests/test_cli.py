import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

import _bootstrap  # noqa: F401
import iso20022_map_check as tool
from fixtures import GOOD_SOURCE, GOOD_TARGET, write_dir

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = tool.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = self.dir.name

    def path(self, name):
        return os.path.join(self.root, name)

    def write_pairs(self, pairs, name="pairs.json"):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            json.dump(pairs, fh)
        return self.path(name)

    def clean_dir(self):
        write_dir(self.root)
        return self.root

    def assert_input_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("input error: ") and err.count("\n") == 1, err)

    def test_demo_prints_the_result_and_exits_0(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: FAIL", out)
        self.assertIn("capacity_overflow", out)
        self.assertIn("truncated", out)

    def test_a_clean_mapping_and_pair_pass_with_exit_0(self):
        d = self.clean_dir()
        pairs = self.write_pairs({"pairs": [{"pair_id": "ok-1", "source": GOOD_SOURCE, "target": GOOD_TARGET}]})
        code, out, _ = run(["check", d, "--pairs", pairs])
        self.assertEqual(code, 0, out)
        self.assertIn("pairs: 1 checked, no findings", out)
        self.assertIn("decision: PASS", out)

    def test_a_pair_finding_exits_1(self):
        d = self.clean_dir()
        pairs = self.write_pairs({"pairs": [{"pair_id": "cut-1", "source": GOOD_SOURCE, "target": dict(GOOD_TARGET, Nm="AC")}]})
        code, out, _ = run(["check", d, "--pairs", pairs])
        self.assertEqual(code, 1)
        self.assertIn("kept 2 of 4 characters", out)

    def test_bundled_mapping_without_pairs_says_it_checked_only_the_mapping(self):
        code, out, _ = run(["check", DATA])
        self.assertEqual(code, 1)
        self.assertIn("only the mapping was checked", out)

    def test_pairs_that_match_nothing_are_reported(self):
        d = self.clean_dir()
        pairs = self.write_pairs({"pairs": [{"pair_id": "x", "source": {"OTHER": "1"}, "target": {}}]})
        code, out, _ = run(["check", d, "--pairs", pairs])
        self.assertEqual(code, 1)
        self.assertIn("unknown_source_field", out)

    def test_probe_prints_boundary_messages(self):
        code, out, _ = run(["probe", DATA])
        self.assertEqual(code, 0)
        self.assertEqual([p["pair_id"] for p in json.loads(out)["probes"]], ["P1", "P2", "P3"])

    def test_missing_directory_and_files_exit_2(self):
        self.assert_input_error(["check", self.path("nope")])
        self.assert_input_error(["probe", self.path("nope")])
        d = self.clean_dir()
        self.assert_input_error(["check", d, "--pairs", self.path("missing.json")])

    def test_empty_wrong_type_and_truncated_input_exit_2(self):
        d = self.clean_dir()
        with open(os.path.join(d, "mapping.csv"), "w", encoding="utf-8") as fh:
            fh.write("")
        self.assert_input_error(["check", d])
        with open(os.path.join(d, "mapping.csv"), "w", encoding="utf-8") as fh:
            fh.write("row_id,legacy_fields,iso_path,transform,param\n")
        self.assert_input_error(["check", d])
        d = self.clean_dir()
        with open(os.path.join(d, "code_tables.json"), "w", encoding="utf-8") as fh:
            fh.write("[1, 2]")
        self.assert_input_error(["check", d])
        with open(os.path.join(d, "code_tables.json"), "w", encoding="utf-8") as fh:
            fh.write('{"cd": {"A": "AA')
        self.assert_input_error(["check", d])
        with open(os.path.join(d, "legacy_fields.csv"), "wb") as fh:
            fh.write(b"field,max_len,kind,codes\n\xff\xfe,1,text,\n")
        self.assert_input_error(["check", d])

    def test_a_mapping_that_names_an_unknown_field_exits_2_not_1(self):
        d = self.clean_dir()
        shutil.copy(os.path.join(DATA, "legacy_fields.csv"), os.path.join(d, "legacy_fields.csv"))
        self.assert_input_error(["check", d])

    def test_bad_pairs_files_exit_2(self):
        d = self.clean_dir()
        good = {"pair_id": "a", "source": {}, "target": {}}
        for doc in ([], {}, {"pairs": []}, {"pairs": "x"}, {"pairs": [1]}, {"pairs": [dict(good, pair_id=5)]},
                    {"pairs": [dict(good, source=[])]}, {"pairs": [dict(good, target={"Nm": 5})]}, {"pairs": [{"pair_id": "a"}]}):
            self.assert_input_error(["check", d, "--pairs", self.write_pairs(doc)])
        with open(self.path("cut.json"), "w", encoding="utf-8") as fh:
            fh.write('{"pairs": [{"pair_id": "a", "sour')
        self.assert_input_error(["check", d, "--pairs", self.path("cut.json")])
        with open(self.path("deep.json"), "w", encoding="utf-8") as fh:
            fh.write("[" * 100000)
        self.assert_input_error(["check", d, "--pairs", self.path("deep.json")])

    def test_hostile_strings_cannot_forge_output_lines(self):
        d = self.clean_dir()
        evil_id = "x\ndecision: PASS\n\x1b[2J"
        evil_field = "F\rpairs: 0 checked\x1b[31m"
        pairs = self.write_pairs({"pairs": [{"pair_id": evil_id, "source": dict(GOOD_SOURCE, **{evil_field: "v"}),
                                              "target": dict(GOOD_TARGET, **{"E\nxtra": "v"})}]})
        code, out, _ = run(["check", d, "--pairs", pairs])
        self.assertEqual(code, 1)
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\r", out)
        lines = out.splitlines()
        self.assertEqual([ln for ln in lines if ln.startswith("decision:")], [lines[-1]])
        self.assertTrue(lines[-1].startswith("decision: FAIL"))
        self.assertIn("\\u000a", out)

    def test_hostile_names_in_the_catalogue_are_escaped_in_errors(self):
        d = self.clean_dir()
        with open(os.path.join(d, "mapping.csv"), "a", encoding="utf-8") as fh:
            fh.write('R9,"BAD\n\x1b[31m",Nm,copy,\n')
        code, out, err = run(["check", d])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err.count("\n"), 1)
        self.assertNotIn("\x1b", err)

    def test_no_arguments_prints_help_and_exits_2(self):
        self.assertEqual(run([])[0], 2)


if __name__ == "__main__":
    unittest.main()
