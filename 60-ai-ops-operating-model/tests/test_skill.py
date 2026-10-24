import csv
import os
import re
import unittest

import _bootstrap  # noqa: F401

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SKILL_DIR = os.path.join(ROOT, "skill", "ai-ops-review")


class SkillTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8") as fh:
            self.text = fh.read()

    def front(self):
        m = re.match(r"---\n(.*?)\n---\n", self.text, re.S)
        self.assertIsNotNone(m, "no frontmatter")
        return dict(line.split(": ", 1) for line in m.group(1).split("\n"))

    def test_frontmatter(self):
        fm = self.front()
        self.assertEqual(set(fm), {"name", "description"})
        self.assertEqual(fm["name"], os.path.basename(SKILL_DIR))
        self.assertRegex(fm["name"], r"^[a-z0-9-]{1,64}$")
        self.assertLessEqual(len(fm["description"]), 1024)

    def test_length(self):
        self.assertLess(len(self.text.splitlines()), 500)

    def test_every_checklist_item_is_in_the_table_with_its_numbers(self):
        with open(os.path.join(ROOT, "data", "checklist.csv"), newline="", encoding="utf-8") as fh:
            items = list(csv.DictReader(fh))
        self.assertEqual(len(items), 23)
        for it in items:
            cells = f"{it['item_id']} {it['item']} | {it['min_tier']} | {it['cycle_days']} | {it['independent']} | {it['day_window']} | {it['must_show']} |"
            self.assertIn(cells, self.text, it["item_id"])

    def test_commands_in_the_skill_exist(self):
        self.assertTrue(os.path.exists(os.path.join(ROOT, "src", "ops_model_review.py")))
        self.assertIn("python3 ops_model_review.py review", self.text)


if __name__ == "__main__":
    unittest.main()
