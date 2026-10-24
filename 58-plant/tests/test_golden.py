"""Pin the numbers the README prints, so a change to the tool, the rules or the spec fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
ROOT = os.path.join(SRC, "..")


def run_script(*args):
    r = subprocess.run([sys.executable] + list(args), cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_demo_output(self):
        self.assertEqual(run_script("plant.py", "--demo").splitlines(), [
            "spec demo seed 58: 644 rows, 7 behaviors, 114 rows in the answer key, data sha256 b2534df4",
            "naive checker flagged 126 rows: found 71 of 84 planted failures, flagged 29 of 30 planted look-alikes and 26 of 530 clean rows",
            "weakest behavior: memo_injection_paraphrase, found 0 of 12"])

    def test_step_01(self):
        out = run_script("step_01_no_key.py")
        self.assertIn("naive: 91 to 120 flags per file, 508 across the five files", out)
        self.assertIn("tuned: 69 to 89 flags per file, 389 across the five files", out)

    def test_step_02(self):
        out = run_script("step_02_is_bad_column.py")
        self.assertIn("naive, five files pooled: recall 0.88, precision 0.70 (355 of 405 marked rows found)", out)
        self.assertIn("tuned, five files pooled: recall 0.89, precision 0.92 (359 of 405 marked rows found)", out)

    def test_step_03(self):
        out = run_script("step_03_what_it_hides.py")
        for line in ("memo_injection_paraphrase    found 0 of 50",
                     "2 rows hit by two failures: 9. The tuned rules flag 9 of them; in 3 the rules that fired explain only one of the two,",
                     "3 a checker that reads the is_bad column: recall 1.00, precision 1.00.",
                     "5 tuned recall by file: 0.84 to 0.92 (spread 0.08). Gap between tuned and naive recall: 0.01.",
                     "KNOWN LIMIT: the tuned rules find 0 of 50 paraphrased injections."):
            self.assertIn(line, out)

    def test_step_04(self):
        out = run_script("step_04_with_a_key.py")
        for line in ("spec demo seed 58: 644 rows, 114 in the key (84 failures, 30 look-alikes), 530 clean by construction",
                     "rerun with the same seed gives identical bytes: yes; seed 59 gives different bytes: yes",
                     "columns in the data file: 8; label columns among them: 0",
                     "naive: found 71 of 84 failures (recall 0.85); look-alikes flagged 29 of 30; clean rows flagged 26 of 530; precision 0.56",
                     "tuned: found 72 of 84 failures (recall 0.86); look-alikes flagged 0 of 30; clean rows flagged 8 of 530; precision 0.90",
                     "naive precision with the look-alikes taken out of the file: 0.73 (with them: 0.56)",
                     "clean rows the tuned rules flag: 8, all in merchant utilities",
                     "failures the tuned rules miss: memo_injection_paraphrase 12",
                     "failures planted in each: 84; naive recall 0.83 to 0.87; tuned recall 0.86 to 0.86",
                     "KNOWN LIMIT: a checker that only memorizes the 3 planted paraphrase sentences finds 12 of 12."):
            self.assertIn(line, out)
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["rows"], s["key_rows"], s["failures"]), (644, 114, 84))
        self.assertEqual(s["checkers"]["naive"]["flagged"], 126)
        self.assertEqual(s["checkers"]["tuned"]["flagged"], 80)

    def test_demo_page_is_current_and_safe(self):
        run_script("step_04_with_a_key.py")
        with open(os.path.join(ROOT, "demo.html"), encoding="utf-8") as fh:
            page = fh.read()
        dec = json.JSONDecoder()
        start = page.index("var ROWS=") + len("var ROWS=")
        rows, end = dec.raw_decode(page, start)
        summary, _ = dec.raw_decode(page, end + len(", SUM="))
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            self.assertEqual(summary, json.load(fh))
        self.assertEqual(len(rows), 148)          # 114 planted rows, 26 clean rows the naive rules flag, 8 the tuned rules flag
        self.assertNotIn("innerHTML", page)
        for needle in ('name="viewport"', "prefers-color-scheme: dark"):
            self.assertIn(needle, page)


if __name__ == "__main__":
    unittest.main()
