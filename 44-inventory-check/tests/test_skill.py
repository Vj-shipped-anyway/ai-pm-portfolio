import os
import re
import unittest

import _bootstrap  # noqa: F401

SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skill", "inventory-check")


class SkillTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8") as fh:
            self.text = fh.read()
        m = re.match(r"---\nname: (.+)\ndescription: (.+)\n---\n", self.text)
        self.assertIsNotNone(m, "frontmatter must hold exactly name and description")
        self.name, self.description = m.group(1), m.group(2)

    def test_name_is_valid_and_equals_the_directory(self):
        self.assertRegex(self.name, r"^[a-z0-9-]+$")
        self.assertLessEqual(len(self.name), 64)
        self.assertEqual(self.name, os.path.basename(SKILL_DIR))

    def test_description_fits(self):
        self.assertLessEqual(len(self.description), 1024)
        self.assertGreater(len(self.description), 100)

    def test_body_is_short(self):
        self.assertLess(len(self.text.splitlines()), 500)

    def test_skill_never_tells_the_reader_to_build_a_shell_string_from_inventory_text(self):
        self.assertIn("Never build a shell string", self.text)


if __name__ == "__main__":
    unittest.main()
