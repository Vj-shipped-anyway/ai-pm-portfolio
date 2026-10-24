import unittest

import _bootstrap  # noqa: F401
import mcp_scope_lint as ml

READ = {"readOnlyHint": True}
WRITE = {"readOnlyHint": False, "destructiveHint": False}
DESTROY = {"readOnlyHint": False, "destructiveHint": True}


def manifest(grants, tools, extra_scopes=()):
    catalog = []
    for res in ("a", "b"):
        catalog += [{"id": f"{res}:read", "resource": res, "access": "read"}, {"id": f"{res}:write", "resource": res, "access": "write"},
                    {"id": f"{res}:delete", "resource": res, "access": "delete"}, {"id": f"{res}:*", "resource": res, "access": "any"}]
    catalog += list(extra_scopes)
    return ml.parse_manifest({"server": {"name": "s"}, "scope_catalog": catalog, "granted_scopes": grants, "tools": tools})


def tool(name, requires, hints=None):
    t = {"name": name, "requires_scopes": requires}
    if hints is not None:
        t["annotations"] = hints
    return t


def kinds(rep):
    return sorted((f["kind"], f["tool"] or f["scope"]) for f in rep["findings"])


class RuleTests(unittest.TestCase):
    def test_unused_grant(self):
        rep = ml.lint(manifest(["a:read", "b:read"], [tool("t", ["a:read"], READ)]))
        self.assertEqual(kinds(rep), [("unused_grant", "b:read")])
        self.assertEqual((rep["reach"], rep["unneeded"], rep["breadth"]), (2, 1, 50.0))

    def test_wildcard_used_in_part_is_narrowable(self):
        rep = ml.lint(manifest(["a:*"], [tool("t", ["a:read"], READ)]))
        self.assertEqual(kinds(rep), [("wildcard_narrowable", "a:*")])
        self.assertEqual(rep["unneeded"], 2)

    def test_wildcard_with_every_member_used_is_left_alone(self):
        tools = [tool("r", ["a:read"], READ), tool("w", ["a:write"], WRITE), tool("d", ["a:delete"], DESTROY)]
        m = manifest(["a:*"], tools)
        self.assertEqual(ml.lint(m)["findings"], [])
        self.assertEqual(ml.propose(m)["grants"][0]["action"], "keep")

    def test_wildcard_required_by_a_tool_counts_as_all_used(self):
        rep = ml.lint(manifest(["a:*"], [tool("t", ["a:*"])]))
        self.assertEqual(kinds(rep), [("tool_requires_wildcard", "t")])

    def test_read_only_tool_may_not_ask_for_write(self):
        rep = ml.lint(manifest(["a:read", "a:write"], [tool("t", ["a:read", "a:write"], READ)]))
        self.assertEqual(kinds(rep), [("tool_scope_above_hint", "t")])

    def test_read_only_tool_asking_for_a_wildcard_is_above_hint_not_the_wildcard_rule(self):
        rep = ml.lint(manifest(["a:*"], [tool("t", ["a:*"], READ)]))
        self.assertEqual(kinds(rep), [("tool_scope_above_hint", "t")])

    def test_non_destructive_tool_may_not_ask_for_delete(self):
        rep = ml.lint(manifest(["a:write", "a:delete"], [tool("t", ["a:write", "a:delete"], WRITE)]))
        self.assertEqual(kinds(rep), [("tool_scope_above_hint", "t")])

    def test_destructive_tool_may_ask_for_delete(self):
        self.assertEqual(ml.lint(manifest(["a:delete"], [tool("t", ["a:delete"], DESTROY)]))["findings"], [])

    def test_tool_with_no_hint_is_listed_as_not_checked(self):
        rep = ml.lint(manifest(["a:read", "a:write"], [tool("quiet", ["a:read", "a:write"]), tool("loud", ["a:read"], READ)]))
        self.assertEqual(rep["unjudged"], ["quiet"])
        self.assertEqual(rep["findings"], [])
        self.assertIn("not checked: quiet", ml.render_text(rep, None))

    def test_scope_a_tool_needs_but_nobody_granted(self):
        rep = ml.lint(manifest(["a:read"], [tool("t", ["b:read"], READ)]))
        self.assertIn(("tool_scope_not_granted", "t"), kinds(rep))

    def test_empty_manifest_lints_to_nothing_and_says_so(self):
        rep = ml.lint(manifest([], []))
        self.assertEqual((rep["reach"], rep["breadth"], rep["findings"]), (0, 0.0, []))
        self.assertIn("nothing to lint", ml.render_text(rep, None))
        self.assertIn("nothing was linted", ml.render_github(rep))

    def test_wildcard_on_a_resource_with_no_specific_scope_reaches_nothing(self):
        m = manifest(["z:*"], [], extra_scopes=[{"id": "z:*", "resource": "z", "access": "any"}])
        self.assertEqual([f["kind"] for f in ml.lint(m)["findings"]], ["unused_grant"])


class ProposalTests(unittest.TestCase):
    def test_keep_narrow_remove_and_tool_change(self):
        m = manifest(["a:*", "b:read", "b:write"], [tool("t", ["a:read", "a:write"], READ), tool("u", ["b:read"], READ)])
        p = ml.propose(m)
        self.assertEqual([(r["scope"], r["action"], r["to"]) for r in p["grants"]],
                         [("a:*", "narrow", ["a:read"]), ("b:read", "keep", ["b:read"]), ("b:write", "remove", [])])
        self.assertEqual(p["tool_changes"], [{"tool": "t", "from": ["a:read", "a:write"], "to": ["a:read"]}])
        self.assertEqual((p["reach_before"], p["reach_after"]), (5, 2))

    def test_wildcard_swapped_for_the_read_scope_the_server_already_holds(self):
        p = ml.propose(manifest(["a:*"], [tool("t", ["a:*"], READ)]))
        self.assertEqual(p["tool_changes"], [{"tool": "t", "from": ["a:*"], "to": ["a:read"]}])
        self.assertEqual(p["proposed_grants"], ["a:read"])

    def test_never_adds_a_scope(self):
        # a:read is not granted, so a read-only tool that asked for a:write is left with nothing rather than given a new scope
        m = manifest(["a:write"], [tool("t", ["a:write"], READ)])
        p = ml.propose(m)
        self.assertEqual(p["tools_emptied"], ["t"])
        self.assertEqual(p["proposed_grants"], [])
        self.assertLessEqual(set(p["cut"]), ml.reach(m, m["granted"]))
        self.assertIn("a person decides", ml.render_text(ml.lint(m), p))

    def test_switches_turn_parts_off(self):
        m = manifest(["a:*"], [tool("t", ["a:read", "a:write"], READ)])
        self.assertEqual(ml.propose(m, narrow=False, hints=False)["grants"][0]["action"], "keep")
        self.assertEqual(ml.propose(m, narrow=True, hints=False)["grants"][0]["to"], ["a:read", "a:write"])
        self.assertEqual(ml.propose(m, narrow=True, hints=True)["grants"][0]["to"], ["a:read"])

    def test_proposal_is_stable(self):
        m = manifest(["a:*", "b:*"], [tool("t", ["a:read"], READ)])
        self.assertEqual(ml.propose(m), ml.propose(m))


if __name__ == "__main__":
    unittest.main()
