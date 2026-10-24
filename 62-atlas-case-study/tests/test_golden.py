"""Pin the numbers the README prints, so a change to the rules that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "src")


def run_step(name: str) -> str:
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_step("step_01_trace_as_report.py")
        self.assertIn("runs flagged by an alert: 60   tool-call rows: 3591", out)
        self.assertIn("failures among the flagged runs: 32 of 60", out)
        self.assertIn("median 59, longest 126", out)
        self.assertIn("tickets that carry an identifier or a person's name: 45 of 60", out)

    def test_step_02(self):
        out = run_step("step_02_ticket_keywords.py")
        self.assertIn("drafts written: 34 of 60 runs", out)
        self.assertIn("failures drafted: 15 of 32", out)
        self.assertIn("harmless runs drafted as case studies: 19 of 28", out)
        self.assertIn("drafts whose techniques equal the planted set: 6 of 34", out)
        self.assertIn("drafts that carry a planted identifier or name: 23 of 34", out)
        self.assertIn("procedure steps that point at a call in the trace: 0 of 43", out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        self.assertIn("ticket words 1 of 10, trace shape 10 of 10", out)
        self.assertIn("failures the trace shape does not draft: 10 of 32; the ticket words reach 7 of them", out)
        self.assertIn("short_storm: longest run of same-shape calls per run is [15, 15, 15, 15, 18]", out)
        self.assertIn("10 calls: 27 of 32, 5 of 28", out)
        self.assertIn("20 calls: 22 of 32, 0 of 28", out)

    def test_step_04(self):
        out = run_step("step_04_with_case_study_tool.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["failures_drafted"], s["failures"]), (22, 32))
        self.assertEqual((s["harmless_drafted"], s["harmless"]), (0, 28))
        self.assertEqual((s["techniques_exact"], s["drafted"]), (22, 22))
        self.assertEqual((s["schema_problems"], s["leaks_declared"], s["leaks_planted"]), (0, 0, 0))
        self.assertEqual((s["steps_median"], s["steps_max"], s["steps_total"], s["calls_in_drafted"]), (2, 3, 51, 2060))
        self.assertIn("RUN_0001 short_storm (20 calls)", out)
        self.assertIn("RUN_0002 alternating_loop (77 calls)", out)

    def test_demo_output_and_staged_draft(self):
        r = subprocess.run([sys.executable, "atlas_case_study.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), [
            'draft: "Retry loop after an instruction-like tool response" (2026-03-24), synthetic',
            "procedure: 3 steps: AML.T0051.001 at call 4, AML.T0029 over calls 4-61, AML.T0034 at call 61",
            "lint: schema ok; todo fields: actor, references, reporter; identifier leaks: 0"])
        staged = os.path.join(ROOT, "issue", "case_study_draft.yaml")
        out = os.path.join(SRC, "out", "staged_check.yaml")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        r = subprocess.run([sys.executable, "atlas_case_study.py", "build", "../data/example_bundle.json", "--yaml", out],
                           cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(staged, encoding="utf-8") as a, open(out, encoding="utf-8") as b:
            self.assertEqual(a.read(), b.read())
        os.remove(out)


if __name__ == "__main__":
    unittest.main()
