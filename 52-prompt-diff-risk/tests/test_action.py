import os
import re
import unittest

import _bootstrap  # noqa: F401

ACTION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "action", "action.yml")


class ActionTests(unittest.TestCase):
    def setUp(self):
        with open(ACTION, encoding="utf-8") as fh:
            self.text = fh.read()

    def test_inputs_reach_the_shell_only_through_env(self):
        script = self.text.split("run: |", 1)[1]
        self.assertNotIn("${{", script)
        env_block = self.text.split("env:", 1)[1].split("run: |", 1)[0]
        for name in ("OLD", "NEW", "TOOLS", "PROBES", "FAIL_ON", "SCRIPT"):
            self.assertRegex(env_block, r"\n\s+%s: \$\{\{ " % name)

    def test_every_variable_is_quoted_in_the_command(self):
        script = self.text.split("run: |", 1)[1]
        for name in ("OLD", "NEW", "TOOLS", "PROBES", "FAIL_ON", "SCRIPT"):
            for m in re.finditer(r"\$%s\b" % name, script):
                self.assertEqual(script[m.start() - 1], '"', name)

    def test_declared_inputs_match_the_cli_flags(self):
        for name in ("old", "new", "tools", "probes", "fail-on"):
            self.assertIn("\n  %s:\n" % name, self.text)
        for flag in ("--tools", "--probes", "--fail-on", "--format github"):
            self.assertIn(flag, self.text)


if __name__ == "__main__":
    unittest.main()
