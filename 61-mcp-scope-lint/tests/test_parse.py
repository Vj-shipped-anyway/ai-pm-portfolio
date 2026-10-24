import copy
import json
import os
import unittest

import _bootstrap  # noqa: F401
import mcp_scope_lint as lint_mod

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def good():
    return {"server": {"name": "s"},
            "scope_catalog": [{"id": "a:read", "resource": "a", "access": "read"}, {"id": "a:write", "resource": "a", "access": "write"},
                              {"id": "a:*", "resource": "a", "access": "any"}],
            "granted_scopes": ["a:read"],
            "tools": [{"name": "t", "requires_scopes": ["a:read"], "annotations": {"readOnlyHint": True},
                       "description": "d", "inputSchema": {"type": "object"}}]}


class ParseTests(unittest.TestCase):
    def bad(self, mutate, expect):
        obj = good()
        mutate(obj)
        with self.assertRaises(lint_mod.ManifestError) as cm:
            lint_mod.parse_manifest(obj)
        self.assertIn(expect, str(cm.exception))

    def test_good_manifest_parses(self):
        m = lint_mod.parse_manifest(good())
        self.assertEqual(m["name"], "s")
        self.assertEqual(m["tools"][0]["read_only"], True)
        self.assertIsNone(m["tools"][0]["destructive"])

    def test_bundled_examples_parse(self):
        for name in ("example_manifest.json", "example_clean.json"):
            with open(os.path.join(DATA, name), encoding="utf-8") as fh:
                lint_mod.parse_manifest(json.load(fh))

    def test_wrong_top_level_types(self):
        for value in ([], "text", 5, None):
            with self.assertRaises(lint_mod.ManifestError):
                lint_mod.parse_manifest(value)
        with self.assertRaises(lint_mod.ManifestError):
            lint_mod.parse_manifest({})

    def test_wrong_field_types(self):
        self.bad(lambda o: o.update(tools="not a list"), "tools must be a list")
        self.bad(lambda o: o.update(scope_catalog={}), "scope_catalog must be a list")
        self.bad(lambda o: o.update(granted_scopes="a:read"), "granted_scopes must be a list")
        self.bad(lambda o: o.update(server={"name": ""}), "server.name")
        self.bad(lambda o: o["scope_catalog"][0].update(access=["read"]), "access must be one of")
        self.bad(lambda o: o["scope_catalog"][0].update(access="owner"), "access must be one of")
        self.bad(lambda o: o["tools"][0].update(annotations=[]), "annotations must be an object")
        self.bad(lambda o: o["tools"][0]["annotations"].update(readOnlyHint="yes"), "readOnlyHint must be true or false")
        self.bad(lambda o: o["tools"][0].update(description=5), "description must be a string")
        self.bad(lambda o: o["tools"][0].update(inputSchema=[]), "inputSchema must be an object")

    def test_unknown_and_duplicate_names(self):
        self.bad(lambda o: o["granted_scopes"].append("zzz:read"), "not in scope_catalog")
        self.bad(lambda o: o["tools"][0].update(requires_scopes=["zzz:read"]), "not in scope_catalog")
        self.bad(lambda o: o["granted_scopes"].append("a:read"), "twice")
        self.bad(lambda o: o["tools"].append(copy.deepcopy(o["tools"][0])), "twice")
        self.bad(lambda o: o["scope_catalog"].append(dict(o["scope_catalog"][0])), "twice")

    def test_access_comes_from_the_field_not_the_spelling(self):
        # the id says read, the field says write: the rules must follow the field
        obj = good()
        obj["scope_catalog"][0]["access"] = "write"
        m = lint_mod.parse_manifest(obj)
        kinds = [f["kind"] for f in lint_mod.lint(m)["findings"]]
        self.assertIn("tool_scope_above_hint", kinds)


if __name__ == "__main__":
    unittest.main()
