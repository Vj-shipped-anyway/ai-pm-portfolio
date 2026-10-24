"""Pin the numbers the README prints, so a change to the rules or the data that moves them fails here first."""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401
from tiergate import rubric_score, tier_from_score

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
ROOT = os.path.join(SRC, "..")


def run_script(name: str) -> str:
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_1(self):
        out = run_script("step_01_declared_tier.py")
        self.assertIn("reference tiers 1/2/3/4: 23 / 84 / 73 / 20", out)
        self.assertIn("declared tier equals the reference: 137 of 200 (68.5%)", out)
        self.assertIn("declared below the reference: 57; above: 6", out)
        self.assertIn("declared at tier 3-4 and sent to full review: 63 of 93 (67.7%)", out)
        self.assertIn("tier 3-4 forms that get the light review: 30", out)

    def test_step_2(self):
        out = run_script("step_02_rescore_the_form.py")
        self.assertIn("declared tier differs from the points on the form: 26 of 200", out)
        self.assertIn("recomputed tier equals the reference: 157 of 200 (78.5%); declared was 137", out)
        self.assertIn("below the reference: 42; above: 1", out)
        self.assertIn("forms this fixes: 21; forms it makes wrong that the declared tier had right: 1", out)

    def test_step_3(self):
        out = run_script("step_03_deficiencies_exposed.py")
        self.assertIn("forms still at the wrong tier after step 2: 43 of 200", out)
        self.assertRegex(out, r"all three\s+equal 170\s+tier 3-4 caught 87 of 93\s+below 11\s+above 19")
        self.assertRegex(out, r"text rules only\s+equal 162\s+tier 3-4 caught 76 of 93\s+below 26\s+above 12")
        self.assertIn("together: 9 of 200 (4.5%)", out)

    def test_step_4(self):
        out = run_script("step_04_with_tiergate.py")
        self.assertIn("recomputed tier equals the reference: 170 of 200 (85.0%); declared was 137, form as written 157", out)
        self.assertIn("tier 3-4 forms recomputed at tier 3-4: 87 of 93 (93.5%); declared was 63", out)
        self.assertIn("below the reference: 11 (declared 57); above: 19 (declared 6)", out)
        self.assertIn("63 under-declared, 4 over-declared, 133 unchanged", out)
        self.assertIn("forms recomputed above the reference: 19; with a planted hard negative: 15", out)
        self.assertIn("KNOWN LIMIT: forms still below the reference after the recompute: 11 of 200", out)
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["declared_exact"], s["form_exact"], s["tool_exact"], s["forms"]), (137, 157, 170, 200))
        self.assertEqual((s["tool_under"], s["tool_over"]), (11, 19))

    def test_every_known_miss_is_a_planted_hard_case(self):
        out = run_script("step_04_with_tiergate.py")
        lines = [ln for ln in out.splitlines() if re.match(r"\s+IN-\d+ declared", ln)]
        self.assertEqual(len(lines), 11)
        for ln in lines:
            self.assertRegex(ln, r"planted: (class_understated|vendor_omitted|customer_facing_denied)")

    def test_demo_output_is_the_block_in_the_readme(self):
        out = subprocess.run([sys.executable, "tiergate.py", "--demo"], cwd=SRC, capture_output=True, text=True).stdout
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            self.assertIn(out, fh.read())

    def test_rubric_reproduces_the_reference_tier_on_the_true_inputs(self):
        with open(os.path.join(ROOT, "data", "intake_submissions.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 200)
        for r in rows:
            score = rubric_score(r["true_customer_facing"], r["decision_autonomy"], r["true_data_class"],
                                 r["true_vendor_model"], r["regulatory_scope"], r["financial_exposure_band"])
            self.assertEqual((score, tier_from_score(score)), (int(r["reference_score"]), int(r["reference_tier"])), r["use_case_id"])


class SkillFileTests(unittest.TestCase):
    def test_frontmatter_and_size(self):
        path = os.path.join(ROOT, "skill", "tiergate-intake-check", "SKILL.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        m = re.match(r"---\nname: (.+)\ndescription: (.+)\n---\n", text)
        self.assertIsNotNone(m)
        name, description = m.group(1), m.group(2)
        self.assertEqual(name, os.path.basename(os.path.dirname(path)))
        self.assertRegex(name, r"^[a-z0-9-]+$")
        self.assertLessEqual(len(name), 64)
        self.assertLessEqual(len(description), 1024)
        self.assertLess(len(text.splitlines()), 500)

    def test_the_command_in_the_skill_exists_with_the_flags_it_uses(self):
        with open(os.path.join(ROOT, "skill", "tiergate-intake-check", "SKILL.md"), encoding="utf-8") as fh:
            text = fh.read()
        r = subprocess.run([sys.executable, "tiergate.py", "check", "--help"], cwd=SRC, capture_output=True, text=True)
        for flag in re.findall(r"--(?:catalog|registry|out)", text):
            self.assertIn(flag, r.stdout)


if __name__ == "__main__":
    unittest.main()
