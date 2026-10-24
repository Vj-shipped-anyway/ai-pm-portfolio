"""The staged files must agree with the tool: same headings, same options, no input pasted into a shell line."""
import json
import os
import re
import unittest

import _bootstrap  # noqa: F401
import intake_tier_action as it

ACTION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "action")


def read(name: str) -> str:
    with open(os.path.join(ACTION, name), encoding="utf-8") as fh:
        return fh.read()


class ActionFileTests(unittest.TestCase):
    def test_issue_form_labels_and_options_match_the_tool(self):
        text = read("ai-intake.yml")
        labels = re.findall(r"^      label: (.+)$", text, re.M)
        self.assertEqual(labels, [label for _, label in it.FIELDS])
        options = [json.loads(m) for m in re.findall(r"^      options: (\[.*\])$", text, re.M)]
        self.assertEqual(options, [it.CHOICES[k] for k in ("customer_facing", "autonomy", "data_class", "vendor", "regulatory", "exposure", "declared")])

    def test_no_expression_is_written_into_a_run_block(self):
        text = read("action.yml")
        blocks = re.findall(r"run: \|\n((?:        .*\n?)+)", text)
        self.assertEqual(len(blocks), 2)
        for b in blocks:
            self.assertNotIn("${{", b)

    def test_the_marker_in_the_action_is_the_marker_in_the_tool(self):
        self.assertIn(it.MARKER, read("action.yml"))

    def test_every_label_the_tool_owns_is_named_in_the_setup_notes(self):
        notes = read("README.md")
        for label in it.MANAGED + ["ai-intake"]:
            self.assertIn(label, notes)


if __name__ == "__main__":
    unittest.main()
