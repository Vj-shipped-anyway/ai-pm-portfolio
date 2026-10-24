from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
import runbook_dryrun as rd

MINIMAL = """runbook: r1
steps:
  - id: s1
    effect: read
    risk: low
    run: "echo hi"
"""


def bad(text):
    with_msg = None
    try:
        rd.parse_yaml(text)
    except rd.RunbookError as e:
        with_msg = str(e)
    return with_msg


class ParseTests(unittest.TestCase):
    def test_nested_mappings_and_lists(self):
        got = rd.parse_yaml("a: 1\nb:\n  - x: 1\n    y: [a, \"b, c\", 3]\n    z: {k: v}\n  - plain\nc:\n  d: e\n")
        self.assertEqual(got, {"a": 1, "b": [{"x": 1, "y": ["a", "b, c", 3], "z": {"k": "v"}}, "plain"], "c": {"d": "e"}})

    def test_list_at_the_same_indent_as_its_key(self):
        self.assertEqual(rd.parse_yaml("steps:\n- id: a\n  run: x\n- id: b\n  run: y\nafter: 1\n"),
                         {"steps": [{"id": "a", "run": "x"}, {"id": "b", "run": "y"}], "after": 1})

    def test_comments(self):
        got = rd.parse_yaml("# top\na: 1  # trailing\nb: \"x # kept\"\nc: a#b\nd: 'it''s'  # note\n")
        self.assertEqual(got, {"a": 1, "b": "x # kept", "c": "a#b", "d": "it's"})

    def test_scalar_types(self):
        got = rd.parse_yaml("a: true\nb: false\nc: -4\nd: 2.5\ne: yes\nf: null\ng: \"7\"\nh:\n")
        self.assertEqual(got, {"a": True, "b": False, "c": -4, "d": 2.5, "e": "yes", "f": "null", "g": "7", "h": None})

    def test_escapes_in_double_quotes(self):
        self.assertEqual(rd.parse_yaml('a: "x\\"y\\\\z\\tq"\n'), {"a": 'x"y\\z\tq'})

    def test_leading_document_marker_and_crlf(self):
        self.assertEqual(rd.parse_yaml("---\r\na: 1\r\nb: 2\r\n"), {"a": 1, "b": 2})

    def test_unsupported_syntax_is_refused_with_a_line_number(self):
        for text in ["a: &x 1\n", "a: *x\n", "a: !!str 1\n", "a: |\n  text\n", "a: >\n  text\n", "a: %x\n"]:
            self.assertIn("line 1", bad(text) or "", text)

    def test_structure_errors(self):
        self.assertIn("duplicate key", bad("a: 1\na: 2\n"))
        self.assertIn("several YAML documents", bad("a: 1\n---\nb: 2\n"))
        self.assertIn("tab", bad("a:\n\tb: 1\n"))
        self.assertIn("control character", bad("a: 1\x07\n"))
        self.assertIn("empty", bad("# nothing\n\n"))
        self.assertIn("indented", bad("  a: 1\n"))
        self.assertIn("multi-line", bad("a: 1\n  b: 2\n"))
        self.assertIn("unexpected indentation", bad("a:\n    b: 1\n  c: 2\n"))
        self.assertIn("expected 'key: value'", bad("just text\n"))

    def test_quoting_errors(self):
        self.assertIn("unterminated", bad('a: "oops\n'))
        self.assertIn("unterminated", bad("a: 'oops\n"))
        self.assertIn("quote a value", bad("a: b: c\n"))
        self.assertIn("after the closing quote", bad('a: "x" y\n'))
        self.assertIn("unsupported escape", bad('a: "\\q"\n'))
        self.assertIn("nested", bad("a: [[1]]\n"))
        self.assertIn("empty item", bad("a: [1,,2]\n"))
        self.assertIn("close on the same line", bad("a: [1, 2\n"))

    def test_nesting_depth_is_capped(self):
        text = "".join("  " * n + "k:\n" for n in range(12)) + "  " * 12 + "v: 1\n"
        self.assertIn("deeper than", bad(text))

    def test_size_is_capped(self):
        self.assertIn("larger than", bad("a: " + "x" * rd.MAX_BYTES + "\n"))

    def test_a_huge_integer_stays_text(self):
        self.assertEqual(rd.parse_yaml("a: " + "9" * 40 + "\n"), {"a": "9" * 40})


class SchemaTests(unittest.TestCase):
    def fails(self, text, fragment):
        with self.assertRaises(rd.RunbookError) as cm:
            rd.load_runbook(text)
        self.assertIn(fragment, str(cm.exception))

    def test_minimal_runbook_loads(self):
        rb = rd.load_runbook(MINIMAL)
        self.assertEqual(rb["steps"][0]["requires"], [])
        self.assertIsNone(rb["steps"][0]["approval"])

    def test_defaults(self):
        rb = rd.load_runbook(MINIMAL.replace("    run:", "    approval:\n      role: ic\n    run:"))
        self.assertEqual(rb["steps"][0]["approval"], {"role": "ic", "ttl_minutes": rd.DEFAULT_TTL_MINUTES})

    def test_unknown_fields_and_bad_values(self):
        self.fails(MINIMAL + "owner: x\n", "unknown field 'owner'")
        self.fails(MINIMAL.replace("effect: read", "effect: delete"), "effect must be one of")
        self.fails(MINIMAL.replace("risk: low", "risk: extreme"), "risk must be one of")
        self.fails(MINIMAL.replace("id: s1", "id: 's 1'"), "id must be")
        self.fails(MINIMAL.replace('    run: "echo hi"\n', ""), "run must be a non-empty string")
        self.fails(MINIMAL.replace("runbook: r1", "runbook: 12"), "the id must be")
        self.fails("runbook: r1\nsteps: []\n", "non-empty list")
        self.fails("- a\n- b\n", "mapping at the top level")

    def test_conditions(self):
        self.fails(MINIMAL + "    requires: [\"no operator here\"]\n", "must read 'key == value'")
        self.fails(MINIMAL + "    requires: not-a-list\n", "requires must be a list")
        rb = rd.load_runbook(MINIMAL + "    requires: [\"a.b >= 5\", \"c != off\"]\n")
        self.assertEqual(rb["steps"][0]["requires"], [("a.b", ">=", 5), ("c", "!=", "off")])

    def test_approval_and_rollback_shapes(self):
        self.fails(MINIMAL + "    approval:\n      role: ic\n      ttl_minutes: true\n", "ttl_minutes")
        self.fails(MINIMAL + "    approval:\n      role: ic\n      extra: 1\n", "unknown field 'extra'")
        self.fails(MINIMAL + "    approval: {}\n", "approval role")
        self.fails(MINIMAL + "    rollback:\n      run: x\n", "rollback")
        self.fails(MINIMAL + "    sets: [a]\n", "sets must be a mapping")

    def test_params_must_be_plain_values(self):
        self.fails("runbook: r1\nparams:\n  a: [1]\nsteps:\n  - id: s1\n    effect: read\n    risk: low\n    run: x\n", "params a")
