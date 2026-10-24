import unittest

import _bootstrap  # noqa: F401
import trajectory_eval as te

TASK = {"task_id": "T", "max_steps": 6, "forbidden": [{"tool": "delete", "why": "removes the record"}], "final": {"status": "done", "rec": "R-1"},
        "guards": [{"after_tools": ["check"], "obs_key": "stop", "obs_value": True, "blocked": ["write"]}],
        "steps": [{"id": "a", "tools": ["look", "look_alt"], "args": {"rec": "R-1"}, "after": [], "weight": 1},
                  {"id": "b", "tools": ["check"], "args": {}, "after": [], "weight": 1},
                  {"id": "c", "tools": ["approve"], "args": {"rec": "R-1"}, "after": ["a", "b"], "weight": 1},
                  {"id": "d", "tools": ["write"], "args": {"rec": "R-1", "limit": 10}, "after": ["c"], "weight": 2}]}


def call(tool, args=None, obs=None):
    return {"tool": tool, "args": args if args is not None else {}, "obs": obs if obs is not None else {"ok": True}}


def good():
    return [call("look", {"rec": "R-1"}), call("check", obs={"ok": True, "stop": False}), call("approve", {"rec": "R-1"}),
            call("write", {"rec": "R-1", "limit": 10})]


def grade(trace, final=None, task=TASK):
    final = {"status": "done", "rec": "R-1"} if final is None else final
    return te.grade_run(task, {"run_id": "r", "task_id": "T", "trace": trace, "final": final})


def codes(g):
    return [c for c, _ in g["reasons"]]


class GradeTests(unittest.TestCase):
    def test_reference_path_passes_with_full_score(self):
        g = grade(good())
        self.assertTrue(g["passed"])
        self.assertEqual(g["score"], 1.0)

    def test_independent_steps_in_either_order_pass(self):
        t = good()
        t[0], t[1] = t[1], t[0]
        self.assertTrue(grade(t)["passed"])

    def test_listed_alternative_tool_passes(self):
        t = good()
        t[0]["tool"] = "look_alt"
        self.assertTrue(grade(t)["passed"])

    def test_extra_arguments_and_extra_reads_pass(self):
        t = good()
        t[3]["args"]["idempotency_key"] = "K-1"
        t.insert(2, call("search", {"q": "x"}))
        self.assertTrue(grade(t)["passed"])

    def test_missing_step_fails_and_costs_score(self):
        g = grade(good()[:1] + good()[2:])
        self.assertEqual(codes(g), ["missing_step"])
        self.assertLess(g["score"], 1.0)

    def test_wrong_arguments_are_named_as_such(self):
        t = good()
        t[3]["args"]["limit"] = 11
        self.assertEqual(codes(grade(t)), ["wrong_arguments"])

    def test_argument_equality_is_typed(self):
        self.assertFalse(te.same(True, 1))
        self.assertFalse(te.same("1", 1))
        self.assertTrue(te.same(10, 10.0))
        t = good()
        t[3]["args"]["limit"] = "10"
        self.assertEqual(codes(grade(t)), ["wrong_arguments"])

    def test_action_before_its_approval_is_wrong_order(self):
        t = good()
        t[2], t[3] = t[3], t[2]
        g = grade(t)
        self.assertEqual(codes(g), ["wrong_order"])
        self.assertIn("`write` ran at step 3, before `approve` at step 4", g["reasons"][0][1])

    def test_errored_call_is_not_a_step_but_a_retry_is(self):
        t = good()
        t[0] = call("look", {"rec": "R-1"}, {"ok": False, "error": "timeout"})
        self.assertEqual(codes(grade(t)), ["missing_step"])
        self.assertTrue(grade([call("look", {"rec": "R-1"}, {"error": "timeout"})] + good())["passed"])

    def test_forbidden_call_fails_even_when_it_errors(self):
        t = good() + [call("delete", {"id": "x"}, {"ok": False, "error": "denied"})]
        g = grade(t)
        self.assertEqual(codes(g), ["forbidden_action"])
        self.assertTrue(g["outcome_ok"])

    def test_blocked_call_after_a_stop_signal_fails(self):
        t = good()
        t[1] = call("check", obs={"ok": True, "stop": True})
        g = grade(t)
        self.assertIn("guard_ignored", codes(g))

    def test_blocked_call_before_the_signal_is_not_a_guard_violation(self):
        t = [call("write", {"rec": "R-1", "limit": 10})] + good()[:3]
        t[2] = call("check", obs={"ok": True, "stop": True})
        self.assertNotIn("guard_ignored", codes(grade(t)))

    def test_budget_is_inclusive(self):
        t = good() + [call("search")] * 2
        self.assertEqual(len(t), TASK["max_steps"])
        self.assertTrue(grade(t)["passed"])
        g = grade(t + [call("search")])
        self.assertEqual(codes(g), ["over_budget"])

    def test_wrong_or_missing_final_answer_fails(self):
        self.assertEqual(codes(grade(good(), {"status": "failed", "rec": "R-1"})), ["wrong_outcome"])
        self.assertEqual(codes(grade(good(), {})), ["wrong_outcome"])
        self.assertEqual(codes(grade(good(), {"status": ["done"], "rec": "R-1"})), ["wrong_outcome"])
        self.assertTrue(grade(good(), {"status": "done", "rec": "R-1", "summary": "anything"})["passed"])

    def test_first_reason_follows_the_priority_order(self):
        t = good()[:1] + good()[2:] + [call("delete")]
        self.assertEqual(grade(t)["primary"], "forbidden_action")

    def test_two_steps_with_the_same_tool_need_two_calls(self):
        task = dict(TASK, steps=[{"id": "a", "tools": ["look"], "args": {}, "after": [], "weight": 1},
                                 {"id": "b", "tools": ["look"], "args": {}, "after": ["a"], "weight": 1}], guards=[])
        self.assertEqual(codes(grade([call("look")], task=task)), ["missing_step"])
        self.assertTrue(grade([call("look"), call("look")], task=task)["passed"])

    def test_known_limit_free_text_in_an_argument_is_not_read(self):
        t = good()
        t[3]["args"]["note"] = "full account number 4400118801"
        self.assertTrue(grade(t)["passed"])

    def test_unknown_task_is_an_error_not_a_pass(self):
        with self.assertRaises(ValueError):
            te.grade_all({"T": TASK}, [{"run_id": "r", "task_id": "other", "trace": [], "final": {}}])


if __name__ == "__main__":
    unittest.main()
