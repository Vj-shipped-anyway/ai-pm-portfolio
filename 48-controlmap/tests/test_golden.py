"""Pin the numbers the README prints, so a change to a rule that moves them fails here first."""
import contextlib
import io
import os
import re
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401
import controlmap as cm

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
README = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "README.md")


def step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return [ln.strip() for ln in r.stdout.splitlines()]


class GoldenTests(unittest.TestCase):
    def assert_lines(self, lines, expected):
        for e in expected:
            self.assertIn(e, lines)

    def test_step_01(self):
        self.assert_lines(step("step_01_register_as_it_stands.py"), [
            "obligations: 56   controls: 55 (51 active, 4 retired)",
            "true status: COVERED 19, STALE 16, PARTIAL 13, UNCOVERED 8",
            "obligations with at least one id typed: 52 of 56",
            "retired: 7", "not in the library: 6",
            "obligations that show an id and have no id that serves them: 6 of 52",
            "right status when an id means covered and an empty cell means uncovered: 22 of 56 (39.3%)"])

    def test_step_02(self):
        self.assert_lines(step("step_02_keyword_sheet.py"), [
            "true pairs found: 63 of 175 (recall 36.0%)",
            "links that are not true pairs: 132 of 195 (precision 32.3%)",
            "right status: 19 of 56 (33.9%)"])

    def test_step_03(self):
        self.assert_lines(step("step_03_deficiencies_exposed.py"), [
            "PARTIAL obligations the sheet shows as covered: 12 of 13",
            "STALE obligations the sheet shows as covered: 16 of 16",
            "UNCOVERED obligations the sheet shows as covered: 7 of 8",
            "links to controls that only deny a phrase: 15 without the negation rule, 0 with it",
            "obligations whose theme has no dictionary row: 4; read as a gap they would be wrong for 4",
            "CT-12 Payment file checks is linked to 5 obligations: OB-004, OB-014, OB-034, OB-043, OB-055",
            "CT-33 Switch configuration watch is linked to 5 obligations: OB-013, OB-018, OB-028, OB-029, OB-033"])

    def test_step_04(self):
        lines = step("step_04_controlmap.py")
        self.assert_lines(lines, [
            "right status: 42 of 56 (75.0%); keyword sheet 19 of 56; typed register column 22 of 56",
            "by rule: dictionary alone 27, with negation 27, with scope 34, with freshness and UNMAPPED 42",
            "wrong status: 14 of 56; 4 are UNMAPPED, which the tool says out loud, so 10 are silent",
            "causes (an obligation can have more than one): false link wrong_sense 4, missed negated_true 1, missed off_dictionary 5, theme not in the dictionary 4",
            "pairs: precision 93.0% (132 of 142 links), recall 75.4% (132 of 175 true pairs)",
            "negation rule: drops 20 links, of which 5 are true pairs; right status 42 of 56 with it, 41 of 56 without",
            "off_dictionary: 6 controls, linked by ControlMap 0, true pairs missed 30",
            "negated_true: 1 controls, linked by ControlMap 0, true pairs missed 5",
            "negated_decoy: 3 controls, linked by the sheet 2, linked by ControlMap 0",
            "lookalike: 4 controls, linked by the sheet 3, linked by ControlMap 0",
            "orphan: 6 controls, linked by the sheet 1, linked by ControlMap 0",
            "retired: 4 controls, linked by the sheet 2, linked by ControlMap 0",
            "KNOWN LIMIT wrong_sense: 2 controls, linked by the sheet 2, linked by ControlMap 2 (false links the rules cannot see)",
            "orphan controls: 13 of 15 true orphans listed; 9 others listed wrongly (negated_true 1, off_dictionary 6, unlisted_theme 2)",
            "evidence requests: 9 controls to ask for 16 STALE obligations (one ask per control, not per obligation)",
            "statuses: COVERED 18, STALE 16, PARTIAL 10, UNCOVERED 8, UNMAPPED 4"])

    def test_readme_run_one_now_block_is_the_real_output(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cm.main(["--demo"]), 0)
        with open(README, encoding="utf-8") as fh:
            blocks = re.findall(r"It prints:\n\n```text\n(.*?)\n```", fh.read(), re.S)
        self.assertEqual(blocks, [out.getvalue().rstrip("\n")])


if __name__ == "__main__":
    unittest.main()
