"""The staged skill file: frontmatter and size."""
from __future__ import annotations

import os
import re
import unittest

import _bootstrap  # noqa: F401

SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skill", "challenge-pack")


class SkillTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8") as fh:
            self.text = fh.read()
        m = re.match(r"---\nname: (.+)\ndescription: (.+)\n---\n", self.text)
        self.assertIsNotNone(m, "frontmatter must hold exactly name and description")
        self.name, self.description = m.group(1), m.group(2)

    def test_name_matches_the_directory_and_the_rule(self):
        self.assertEqual(self.name, os.path.basename(SKILL_DIR))
        self.assertRegex(self.name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(self.name), 64)

    def test_description_fits(self):
        self.assertLessEqual(len(self.description), 1024)
        self.assertGreater(len(self.description), 100)

    def test_under_500_lines_and_names_the_command(self):
        self.assertLess(len(self.text.splitlines()), 500)
        self.assertIn("src/challenge_pack.py", self.text)
        self.assertIn("--as-of", self.text)


if __name__ == "__main__":
    unittest.main()
