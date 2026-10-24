"""Pin the numbers the README prints, so a change to the splitter or the rules that moves them fails here first."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
DATA = os.path.join(HERE, "..", "data")


def run_step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout.splitlines()


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_step("step_01_no_trace.py")
        for line in ("  narratives: 40   sentences: 408   transaction records: 478",
                     "  citations a reviewer looks up by hand: 471",
                     "  sentences with a planted defect: 140 of 408",
                     "  narratives with at least one planted defect: 38 of 40",
                     "  planted defects stopped before a reviewer reads them: 0 of 140"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = run_step("step_02_bracket_check.py")
        self.assertIn("  pieces examined: 534 for 408 planted sentences", out)
        self.assertIn("  planted defects flagged: 44 of 140", out)
        self.assertIn("  of those flagged, uncited sentences: 19 of 20; the other 25 are defects that were cut in two by a period after Inc. or Ltd.", out)
        self.assertTrue(any(ln.startswith("  fine sentences flagged: 99 of 268 (") for ln in out), out)

    def test_step_03_ladder(self):
        run_step("step_03_deficiencies_exposed.py")
        with open(os.path.join(SRC, "out", "step_03_ladder.json"), encoding="utf-8") as fh:
            ladder = {r["version"]: (r["caught"], r["defects"], r["false_alarms"], r["fine"]) for r in json.load(fh)}
        self.assertEqual(ladder, {"A": (20, 140, 0, 268), "B": (46, 140, 0, 268), "C": (120, 140, 64, 268), "D": (120, 140, 10, 268)})

    def test_step_04(self):
        out = run_step("step_04_with_trace.py")
        for line in ("  planted defects flagged: 120 of 140",
                     "  fine sentences flagged: 10 of 268 (ok_other_date 10)",
                     "  sentences the splitter cut where the planted sentence ends: 408 of 408",
                     "  sentences a person has to read: 158 of 408 (step 1: 408)",
                     "  verdicts: 250 traced, 28 unchecked, 130 not traced",
                     "  KNOWN LIMIT: defects that pass by default: 20 of 140 (laundered 12, mixed_record 8)",
                     "  of the unchecked verdicts, 12 are planted defects and 16 are fine sentences the tool cannot tell apart",
                     "  with --fail-on unchecked: defects flagged 132 of 140, fine sentences flagged 26 of 268"):
            self.assertIn(line, out)
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["caught"], s["defects"], s["false_alarms"], s["fine"], s["to_read"]), (120, 140, 10, 268, 158))

    def test_every_planted_kind_is_in_the_truth_file(self):
        with open(os.path.join(DATA, "truth.csv"), encoding="utf-8") as fh:
            kinds = {line.split(",")[4] for line in fh.read().splitlines()[1:]}
        self.assertEqual(len(kinds), 21)

    def test_generator_reproduces_the_data_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, os.path.join(DATA, "_generate.py")], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            for name in sorted(os.listdir(tmp)):
                with open(os.path.join(tmp, name), "rb") as fresh, open(os.path.join(DATA, name), "rb") as kept:
                    self.assertEqual(fresh.read(), kept.read(), name)


if __name__ == "__main__":
    unittest.main()
