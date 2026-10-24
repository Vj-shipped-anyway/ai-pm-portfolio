import unittest

import _bootstrap  # noqa: F401
import atlas_case_study as t


def call(tool="lookup", kind="malformed", flag="", cost=0.01, **args):
    args.setdefault("customer_id", "CUST_123456")
    return {"tool_name": tool, "args": args, "response_kind": kind, "response_flag": flag, "cost_usd": cost}


def bundle(calls, cap=100.0, role="claims triage agent"):
    return {"identifier_keys": ["customer_id", "run_id"], "synthetic": True,
            "run": {"run_id": "RUN_0001", "agent_id": "agent_x", "agent_role": role, "customer_id": "CUST_123456",
                    "started_at": "2026-03-01T10:00:00Z", "cost_cap_usd": cap},
            "calls": calls}


def storm(n, **kw):
    return [call(attempt=i, **kw) for i in range(n)]


def techniques(b, **kw):
    built = t.build_study(b, **kw)
    return None if built is None else [e["technique"] for e in built[1]]


class PhaseTests(unittest.TestCase):
    def test_same_tool_same_shape_is_one_phase(self):
        ph = t.phases(storm(5))
        self.assertEqual([(p["start"], p["end"], p["n"]) for p in ph], [(0, 4, 5)])

    def test_shape_is_key_names_and_value_types(self):
        calls = [call(a=1), call(a=2), call(a="x"), call(b=1)]
        self.assertEqual([p["n"] for p in t.phases(calls)], [2, 1, 1])

    def test_different_tool_splits_a_phase(self):
        self.assertEqual([p["n"] for p in t.phases([call("a"), call("b"), call("a")])], [1, 1, 1])


class LoopTests(unittest.TestCase):
    def test_threshold_is_twenty_calls(self):
        self.assertIsNone(techniques(bundle(storm(19))))
        self.assertEqual(techniques(bundle(storm(20))), ["AML.T0029"])

    def test_threshold_is_a_parameter_and_nothing_global_moves(self):
        self.assertEqual(techniques(bundle(storm(12)), loop_min=10), ["AML.T0029"])
        self.assertEqual(t.LOOP_MIN_CALLS, 20)
        self.assertIsNone(techniques(bundle(storm(12))))

    def test_non_ok_share_boundary(self):
        def mixed(n_ok):
            return [call(attempt=i, kind="ok" if i < n_ok else "malformed") for i in range(20)]
        self.assertIsNotNone(techniques(bundle(mixed(2))))
        self.assertIsNone(techniques(bundle(mixed(3))))

    def test_long_batch_of_ok_calls_is_not_a_loop(self):
        self.assertIsNone(techniques(bundle([call(kind="ok", claim_id="C%d" % i) for i in range(80)])))

    def test_alternating_tools_are_missed(self):
        calls = [call("a" if i % 2 == 0 else "b") for i in range(80)]
        self.assertIsNone(techniques(bundle(calls)))

    def test_two_loops_give_two_denial_steps_in_order(self):
        calls = storm(20, tool="a") + [call("c", kind="ok")] + storm(25, tool="b")
        built = t.build_study(bundle(calls))
        self.assertEqual([e["first_call"] for e in built[1]], [1, 22])
        self.assertEqual([e["technique"] for e in built[1]], ["AML.T0029", "AML.T0029"])


class StepTests(unittest.TestCase):
    def test_flag_on_the_call_before_the_loop_adds_injection(self):
        calls = [call("other", kind="ok", flag="instruction_like")] + storm(20)
        self.assertEqual(techniques(bundle(calls)), ["AML.T0051.001", "AML.T0029"])

    def test_flag_on_the_first_loop_call_adds_injection_once(self):
        calls = storm(20)
        calls[0]["response_flag"] = "instruction_like"
        self.assertEqual(techniques(bundle(calls)), ["AML.T0051.001", "AML.T0029"])

    def test_flag_two_calls_before_the_loop_does_not(self):
        calls = [call("other", kind="ok", flag="instruction_like"), call("other2", kind="ok")] + storm(20)
        self.assertEqual(techniques(bundle(calls)), ["AML.T0029"])

    def test_flag_without_a_loop_gives_no_draft(self):
        calls = [call("other", kind="ok", flag="instruction_like")] + storm(5)
        self.assertIsNone(techniques(bundle(calls)))

    def test_cost_step_only_when_the_cap_is_reached(self):
        calls = storm(30, cost=1.0)
        self.assertEqual(techniques(bundle(calls, cap=25.0)), ["AML.T0029", "AML.T0034"])
        self.assertEqual(techniques(bundle(calls, cap=31.0)), ["AML.T0029"])
        built = t.build_study(bundle(calls, cap=25.0))
        self.assertEqual(built[1][-1]["first_call"], 25)

    def test_ticket_text_is_not_an_input(self):
        b = bundle(storm(20))
        b["ticket_note"] = "Customer CUST_999999 stuck. Paged Dana."
        doc = t.build_study(b)[0]
        self.assertNotIn("Dana", str(doc))
        self.assertNotIn("999999", str(doc))

    def test_reporter_flag_replaces_the_todo(self):
        doc = t.build_study(bundle(storm(20)), reporter="Team A")[0]
        self.assertEqual(doc["study"]["reporter"], "Team A")
        self.assertEqual(t.lint_study(doc)[1], ["actor", "references"])


class ScrubTests(unittest.TestCase):
    def test_identifier_in_the_role_is_redacted(self):
        doc = t.build_study(bundle(storm(20), role="agent for CUST_123456 and 123456"))[0]
        self.assertEqual(doc["study"]["target"], "agent for [redacted] and [redacted]")

    def test_digit_core_is_redacted_without_its_prefix(self):
        self.assertEqual(t.scrub("cust 123456.", ["CUST_123456"]), "cust [redacted].")

    def test_short_values_are_ignored(self):
        b = bundle(storm(20))
        b["identifier_keys"] = ["customer_id"]
        b["run"]["customer_id"] = "ab"
        for c in b["calls"]:
            c["args"]["customer_id"] = "ab"
        self.assertEqual(t.identifier_values(b), [])

    def test_find_leaks_names_keys_not_values(self):
        b = bundle(storm(20))
        self.assertEqual(t.find_leaks("see CUST_123456", b), ["customer_id"])
        self.assertEqual(t.find_leaks("nothing here", b), [])


if __name__ == "__main__":
    unittest.main()
