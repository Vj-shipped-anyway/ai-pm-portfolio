import unittest

import _bootstrap  # noqa: F401
import scopekeeper as sk

GROUPS = {"acct:*": ["acct:close", "acct:read", "acct:hold"]}


def grant(agent, scope, ticket="T-1"):
    return {"agent_id": agent, "scope": scope, "ticket_id": ticket}


def call(agent, scope, sa="", n=1, day=1):
    return [{"call_id": f"c{i}", "agent_id": agent, "day": day, "scope": scope, "service_account": sa} for i in range(n)]


def rows_by_key(res):
    return {(r["agent_id"], r["scope"]): r for r in res["grants"]}


class DiffTests(unittest.TestCase):
    def test_unused_grant_is_removed_and_used_grant_kept(self):
        res = sk.analyze([grant("A", "x:read"), grant("A", "x:write")], call("A", "x:read", n=3), {})
        rows = rows_by_key(res)
        self.assertEqual(rows[("A", "x:read")]["action"], "keep")
        self.assertEqual(rows[("A", "x:write")]["action"], "remove")
        self.assertEqual((res["summary"]["keep"], res["summary"]["remove"]), (1, 1))

    def test_group_is_narrowed_to_the_members_called(self):
        res = sk.analyze([grant("A", "acct:*")], call("A", "acct:read", n=2) + call("A", "acct:hold"), GROUPS)
        r = rows_by_key(res)[("A", "acct:*")]
        self.assertEqual((r["action"], r["after"]), ("narrow", ["acct:hold", "acct:read"]))
        self.assertEqual((res["summary"]["reach_before"], res["summary"]["reach_after"]), (3, 2))

    def test_group_with_every_member_called_is_kept_whole(self):
        calls = call("A", "acct:read") + call("A", "acct:hold") + call("A", "acct:close")
        r = rows_by_key(sk.analyze([grant("A", "acct:*")], calls, GROUPS))[("A", "acct:*")]
        self.assertEqual(r["action"], "keep")

    def test_group_never_called_is_removed(self):
        res = sk.analyze([grant("A", "acct:*"), grant("A", "y:z")], call("A", "y:z"), GROUPS)
        r = rows_by_key(res)[("A", "acct:*")]
        self.assertEqual((r["action"], r["reason"]), ("remove", "group never called"))

    def test_group_comes_from_the_catalog_not_from_the_name(self):
        # a scope that merely shares a prefix with a group is a plain scope
        res = sk.analyze([grant("A", "acct:read"), grant("A", "acct:hold")], call("A", "acct:read"), GROUPS)
        rows = rows_by_key(res)
        self.assertEqual(rows[("A", "acct:read")]["action"], "keep")
        self.assertEqual(rows[("A", "acct:hold")]["action"], "remove")
        # a group need not look like a wildcard at all
        res = sk.analyze([grant("A", "bundle_1")], call("A", "p"), {"bundle_1": ["p", "q"]})
        self.assertEqual(rows_by_key(res)[("A", "bundle_1")]["action"], "narrow")

    def test_untagged_call_is_credited_to_every_holder_on_the_account(self):
        agents = {"A": "S1", "B": "S1", "C": "S2"}
        grants = [grant("A", "x:read"), grant("B", "x:read"), grant("C", "x:read"), grant("C", "x:other")]
        calls = call("A", "x:read", "S1") + call("", "x:read", "S1", n=2) + call("C", "x:other", "S2")
        res = sk.analyze(grants, calls, {}, agents)
        rows = rows_by_key(res)
        self.assertEqual(rows[("B", "x:read")]["action"], "keep")
        self.assertTrue(rows[("B", "x:read")]["on_credit_only"])
        self.assertEqual(rows[("B", "x:read")]["calls_credited"], 2)
        self.assertEqual(rows[("C", "x:read")]["action"], "remove")        # other account: not credited
        self.assertEqual(res["summary"]["on_credit_only"], 1)

    def test_min_calls_turns_a_stray_grant_into_a_removal(self):
        grants, calls = [grant("A", "x:read"), grant("A", "x:smoke")], call("A", "x:read", n=5) + call("A", "x:smoke", n=2)
        self.assertEqual(rows_by_key(sk.analyze(grants, calls, {}))[("A", "x:smoke")]["action"], "keep")
        res = sk.analyze(grants, calls, {}, min_calls=3)
        r = rows_by_key(res)[("A", "x:smoke")]
        self.assertEqual((r["action"], r["reason"]), ("remove", "fewer than 3 calls"))
        self.assertEqual(res["summary"]["newly_denied"], 2)                # the price of the threshold

    def test_replay_is_not_vacuous(self):
        res = sk.analyze([grant("A", "x:read")], call("A", "x:read", n=4), {})
        self.assertEqual(res["summary"]["newly_denied"], 0)
        self.assertEqual(len(sk.replay(call("A", "x:read", n=4), {"A": set()}, {})), 4)

    def test_replay_tests_an_untagged_call_against_the_union_of_the_account(self):
        agents = {"A": "S1", "B": "S1"}
        calls = call("", "x:read", "S1")
        self.assertEqual(sk.replay(calls, {"A": set(), "B": {"x:read"}}, agents), [])
        self.assertEqual(sk.replay(calls, {"A": set(), "B": set()}, agents), [0])

    def test_calls_outside_every_grant_are_counted_and_not_credited(self):
        res = sk.analyze([grant("A", "x:read")], call("A", "x:read") + call("A", "x:elsewhere", n=3), {})
        self.assertEqual(res["summary"]["uncovered_calls"], 3)
        self.assertEqual(res["summary"]["newly_denied"], 0)

    def test_agents_with_no_call_at_all_are_listed(self):
        res = sk.analyze([grant("A", "x:read"), grant("B", "x:read")], call("A", "x:read"), {})
        self.assertEqual(res["summary"]["agents_without_calls"], ["B"])

    def test_window_comes_from_the_log_or_the_flag(self):
        calls = call("A", "x:read", day=40)
        self.assertEqual(sk.analyze([grant("A", "x:read")], calls, {})["summary"]["window_days"], 40)
        self.assertEqual(sk.analyze([grant("A", "x:read")], calls, {}, window_days=90)["summary"]["window_days"], 90)

    def test_result_does_not_depend_on_input_order(self):
        grants = [grant("B", "x:b"), grant("A", "x:a"), grant("A", "x:c")]
        calls = call("A", "x:a") + call("B", "x:b")
        a = sk.analyze(grants, calls, {})
        b = sk.analyze(list(reversed(grants)), list(reversed(calls)), {})
        self.assertEqual(sk.render_text(a), sk.render_text(b))


if __name__ == "__main__":
    unittest.main()
