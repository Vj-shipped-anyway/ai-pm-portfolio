import contextlib
import csv
import io
import os
import unittest

import _bootstrap  # noqa: F401
import tprm_gap_map as t

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def run(args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = t.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()


class CliAndMapTests(unittest.TestCase):
    def test_demo(self):
        code, out = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("text examples catch 17 of 24; with AI characteristics 22 of 24", out)

    def test_map_has_one_row_per_stage_and_valid_prompts(self):
        with open(os.path.join(DATA, "guidance_map.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 16)
        self.assertTrue({r["how_the_text_prompts_it"] for r in rows} <= {"named", "principle", "example", "not mentioned"})
        self.assertEqual([r["stage"] for r in rows if r["how_the_text_prompts_it"] == "not mentioned"],
                         ["High-risk characteristics: AI-specific", "Due diligence: AI evidence"])
        code, out = run(["map"])
        self.assertEqual(code, 0)
        self.assertIn("Subcontractors", out)

    def test_missing_file_exits_2(self):
        self.assertEqual(run(["tier", "nope.csv"])[0], 2)
        self.assertEqual(run(["terms", "nope.txt"])[0], 2)

    def test_terms_counts_a_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("a plain third-party text with no such wording")
        self.addCleanup(os.unlink, f.name)
        code, out = run(["terms", f.name])
        self.assertEqual(code, 0)
        self.assertIn("occurrences of AI wording: 0", out)


if __name__ == "__main__":
    unittest.main()
