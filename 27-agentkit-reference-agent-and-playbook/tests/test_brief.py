import copy
import json
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
import support
from agentkit.audit import AuditLog
from agentkit.brief import (acceptance_tests, brief_warnings, check_brief, derive_config, evaluate_acceptance,
                            load_brief, scope_violation, validate_brief)
from agentkit.errors import BriefError, UnsupportedStepError
from agentkit.kit import build_kit
from agentkit.orchestrator import Orchestrator
from agentkit.tools import ToolRegistry, build_tools


def problems_of(mutator):
    b = support.brief()
    mutator(b)
    return check_brief(b)


class TestBriefValidation(unittest.TestCase):
    def test_sample_brief_is_valid(self):
        self.assertEqual(check_brief(support.brief()), [])

    def test_sample_brief_has_no_warnings(self):
        self.assertEqual(brief_warnings(support.brief()), [])

    def test_missing_top_level_key(self):
        p = problems_of(lambda b: b.pop("estimate"))
        self.assertTrue(any("missing key 'estimate'" in x for x in p))

    def test_unexpected_key_is_rejected(self):
        p = problems_of(lambda b: b.update({"extra": 1}))
        self.assertTrue(any("unexpected key 'extra'" in x for x in p))

    def test_nested_unexpected_key_is_rejected(self):
        p = problems_of(lambda b: b["tools"][0].update({"owner": "x"}))
        self.assertTrue(any("tools[0]: unexpected key 'owner'" in x for x in p))

    def test_wrong_schema_string(self):
        p = problems_of(lambda b: b.update({"schema": "build-brief/v2"}))
        self.assertTrue(any("schema" in x for x in p))

    def test_bad_brief_id(self):
        p = problems_of(lambda b: b.update({"brief_id": "001"}))
        self.assertTrue(any("brief_id" in x for x in p))

    def test_bad_automation_class(self):
        p = problems_of(lambda b: b["candidate"].update({"automation_class": "HUMAN_JUDGMENT"}))
        self.assertTrue(any("automation_class" in x for x in p))

    def test_a_malformed_step_id_is_a_problem(self):
        for bad in ("X13", "S1", "13", "S100", ""):
            p = problems_of(lambda b: b["candidate"]["steps"].append(bad))
            self.assertTrue(any("is not a step id" in x for x in p), bad)

    def test_a_well_formed_step_id_outside_the_catalog_is_a_warning_not_a_problem(self):
        b = support.brief()
        b["candidate"]["steps"].append("S13")
        self.assertEqual(check_brief(b), [])
        self.assertTrue(any("unsupported step 'S13'" in w for w in brief_warnings(b)))

    def test_an_unsupported_step_validates_but_running_it_is_refused(self):
        b = support.brief()
        b["candidate"]["steps"].append("S13")
        validate_brief(b)                                   # passes
        with self.assertRaises(UnsupportedStepError) as cm:
            derive_config(b)                                # refused
        self.assertIn("S13", str(cm.exception))
        self.assertIn("running it is refused", str(cm.exception))
        cfg = derive_config(b, allow_unsupported=True)      # inspection only
        self.assertEqual(cfg.unsupported_steps, ("S13",))
        with self.assertRaises(UnsupportedStepError):
            build_kit(support.tiny_world(), b)
        env = build_kit(support.tiny_world(), support.brief()).env
        with self.assertRaises(UnsupportedStepError):       # and the orchestrator refuses a config that carries one
            Orchestrator(cfg, ToolRegistry(build_tools(env), cfg.tool_scope, AuditLog()), AuditLog())

    def test_a_supported_brief_has_no_unsupported_steps(self):
        self.assertEqual(derive_config(support.brief()).unsupported_steps, ())

    def test_steps_out_of_order(self):
        def m(b):
            s = b["candidate"]["steps"]
            s[0], s[1] = s[1], s[0]
        self.assertTrue(any("workflow order" in x for x in problems_of(m)))

    def test_person_held_step_needs_a_gate_s09(self):
        def m(b):
            b["controls"]["hitl_gates"] = [g for g in b["controls"]["hitl_gates"] if g["step"] != "S09"]
        self.assertTrue(any("S09" in x and "person-held" in x for x in problems_of(m)))

    def test_person_held_step_needs_a_gate_s07(self):
        def m(b):
            b["controls"]["hitl_gates"] = [g for g in b["controls"]["hitl_gates"] if g["step"] != "S07"]
        self.assertTrue(any("S07" in x and "person-held" in x for x in problems_of(m)))

    def test_agent_class_cannot_include_person_held_steps(self):
        p = problems_of(lambda b: b["candidate"].update({"automation_class": "AGENT"}))
        self.assertTrue(any("person-held step" in x for x in p))

    def test_s10_needs_a_four_eyes_entry_for_s09_or_an_s10_entry_that_names_it(self):
        def without_s09(b, keep_s09_entry, s10_rule=None):
            b["candidate"]["steps"].remove("S09")
            b["controls"]["hitl_gates"] = [g for g in b["controls"]["hitl_gates"] if g["step"] != "S09"]
            fe = b["controls"]["four_eyes"]
            if not keep_s09_entry:
                fe[:] = [f for f in fe if f["step"] != "S09"]
            if s10_rule is not None:
                for f in fe:
                    if f["step"] == "S10":
                        f["rule"] = s10_rule
        # S09 outside the pack, with its own four-eyes entry: valid
        self.assertEqual(problems_of(lambda b: without_s09(b, True)), [])
        # S09 outside the pack, no S09 entry, but the S10 entry names the S09 approval: valid
        self.assertEqual(problems_of(lambda b: without_s09(b, False)), [])
        # S09 outside the pack, no S09 entry, and the S10 entry does not name it: a problem
        p = problems_of(lambda b: without_s09(b, False, "A person approves."))
        self.assertTrue(any("S10 resubmit_payment needs a four-eyes entry for S09" in x for x in p))

    def test_s10_with_no_four_eyes_entries_at_all_is_a_problem(self):
        def m(b):
            b["controls"]["four_eyes"] = []
        self.assertTrue(any("needs a four-eyes entry for S09" in x for x in problems_of(m)))

    def test_s09_in_the_pack_must_still_carry_its_four_eyes_rule(self):
        def m(b):
            b["controls"]["four_eyes"] = [f for f in b["controls"]["four_eyes"] if f["step"] != "S09"]
            for f in b["controls"]["four_eyes"]:
                f["rule"] = "Runs only after a person approves."      # names no S09, and S09 is in the pack
        p = problems_of(m)
        self.assertTrue(any("S09 must carry a four-eyes rule" in x for x in p))

    def test_a_four_eyes_control_may_name_a_step_outside_the_pack(self):
        b = support.brief()
        b["candidate"]["steps"].remove("S09")
        b["controls"]["hitl_gates"] = [g for g in b["controls"]["hitl_gates"] if g["step"] != "S09"]
        self.assertEqual(check_brief(b), [])
        self.assertIn("S09", [f["step"] for f in b["controls"]["four_eyes"]])
        self.assertEqual(derive_config(b).approval_required, {"S10": "S09"})
        self.assertNotIn("S09", derive_config(b).gates)

    def test_a_four_eyes_entry_must_still_be_a_step_id(self):
        p = problems_of(lambda b: b["controls"]["four_eyes"].append({"step": "nine", "rule": "x"}))
        self.assertTrue(any("four_eyes" in x and "is not a step id" in x for x in p))

    def test_person_held_steps_in_the_pack_still_need_their_gates(self):
        def m(b):
            b["controls"]["hitl_gates"] = []
        p = problems_of(m)
        self.assertTrue(any("S07" in x and "person-held" in x for x in p))
        self.assertTrue(any("S09" in x and "person-held" in x for x in p))

    def test_gate_step_must_be_in_candidate_steps(self):
        def m(b):
            b["candidate"]["steps"].remove("S07")
        self.assertTrue(any("not in candidate.steps" in x for x in problems_of(m)))

    def test_read_tool_with_write_like_action(self):
        p = problems_of(lambda b: b["tools"][0]["allowed_actions"].append("delete_exception"))
        self.assertTrue(any("write-like action 'delete_exception'" in x for x in p))

    def test_bad_access_value(self):
        p = problems_of(lambda b: b["tools"][0].update({"access": "admin"}))
        self.assertTrue(any("access" in x for x in p))

    def test_duplicate_tool_name(self):
        p = problems_of(lambda b: b["tools"].append(copy.deepcopy(b["tools"][0])))
        self.assertTrue(any("duplicate tool name" in x for x in p))

    def test_duplicate_acceptance_id(self):
        p = problems_of(lambda b: b["acceptance"].append(copy.deepcopy(b["acceptance"][0])))
        self.assertTrue(any("acceptance" in x and "unique" in x for x in p))

    def test_boolean_threshold_is_not_a_number(self):
        p = problems_of(lambda b: b["acceptance"][0].update({"threshold": True}))
        self.assertTrue(any("threshold" in x for x in p))

    def test_negative_test_plan_count(self):
        p = problems_of(lambda b: b["test_plan"].update({"golden_cases": -1}))
        self.assertTrue(any("golden_cases" in x for x in p))

    def test_estimate_must_name_its_assumption(self):
        p = problems_of(lambda b: b["estimate"].update({"assumption": ""}))
        self.assertTrue(any("assumption" in x for x in p))

    def test_validate_brief_raises_with_all_problems(self):
        b = support.brief()
        b["brief_id"] = "x"
        b["schema"] = "x"
        with self.assertRaises(BriefError) as cm:
            validate_brief(b)
        self.assertGreaterEqual(len(cm.exception.problems), 2)

    def test_not_an_object(self):
        self.assertTrue(check_brief([1, 2]))

    def test_load_brief_rejects_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "b.json"
            p.write_text("{not json", encoding="utf-8")
            with self.assertRaises(BriefError):
                load_brief(p)

    def test_load_brief_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "b.json"
            p.write_text(json.dumps(support.brief()), encoding="utf-8")
            self.assertEqual(load_brief(p)["brief_id"], "BB-001")


class TestDerivedConfig(unittest.TestCase):
    def setUp(self):
        self.cfg = derive_config(support.brief())

    def test_gates_are_s07_and_s09(self):
        self.assertEqual(sorted(self.cfg.gates), ["S07", "S09"])
        self.assertEqual(self.cfg.gates["S09"].approver_role, "payments_operations_reviewer")

    def test_resubmit_requires_s09(self):
        self.assertEqual(self.cfg.approval_required, {"S10": "S09"})

    def test_approval_requirement_follows_the_resubmit_step(self):
        b = support.brief()
        self.assertEqual(derive_config(b).approval_required, {"S10": "S09"})
        b["controls"]["four_eyes"] = [f for f in b["controls"]["four_eyes"] if f["step"] != "S10"]
        self.assertEqual(derive_config(b).approval_required, {"S10": "S09"})    # the S09 entry still covers it
        b["controls"]["four_eyes"] = []
        with self.assertRaises(BriefError):          # no entry at all: S10 may not be in the pack
            derive_config(b)

    def test_four_eyes_rules_are_carried(self):
        self.assertIn("S09", self.cfg.four_eyes)
        self.assertIn("S10", self.cfg.four_eyes)

    def test_tool_scope(self):
        self.assertEqual(self.cfg.tool_scope["payments_db"].access, "read")
        self.assertEqual(self.cfg.tool_scope["payments_db"].allowed_actions, frozenset({"get_payment"}))
        self.assertEqual(self.cfg.tool_scope["payments_gateway"].access, "write")

    def test_scope_violation_helper(self):
        self.assertIsNone(scope_violation(self.cfg.tool_scope, "payments_db", "get_payment"))
        self.assertIn("not allowed", scope_violation(self.cfg.tool_scope, "payments_db", "update_payment"))
        self.assertIn("not in the brief", scope_violation(self.cfg.tool_scope, "mailer", "send"))

    def test_golden_case_count_matches_fixtures(self):
        self.assertEqual(self.cfg.golden_cases, len(support.golden()))

    def test_derive_rejects_an_invalid_brief(self):
        b = support.brief()
        b.pop("tools")
        with self.assertRaises(BriefError):
            derive_config(b)


class TestAcceptanceTests(unittest.TestCase):
    def test_directions_from_suffix(self):
        tests = {t.id: t for t in acceptance_tests(support.brief())}
        self.assertEqual(tests["AC-01"].direction, "max")
        self.assertEqual(tests["AC-05"].direction, "min")
        self.assertEqual(tests["AC-05"].name, "shadow_agreement_rate")

    def test_no_suffix_reads_as_minimum_and_warns(self):
        b = support.brief()
        b["acceptance"][0]["metric"] = "coverage"
        self.assertEqual(acceptance_tests(b)[0].direction, "min")
        self.assertTrue(brief_warnings(b))

    def test_evaluate_pass_and_fail(self):
        tests = acceptance_tests(support.brief())
        out = {r["id"]: r for r in evaluate_acceptance(tests, {"out_of_scope_calls_executed": 0,
                                                              "shadow_agreement_rate": 0.9})}
        self.assertTrue(out["AC-01"]["passed"])
        self.assertFalse(out["AC-05"]["passed"])

    def test_a_metric_that_was_not_measured_fails(self):
        out = evaluate_acceptance(acceptance_tests(support.brief()), {})
        self.assertTrue(all(not r["passed"] for r in out))

    def test_threshold_boundary_is_inclusive(self):
        tests = {t.id: t for t in acceptance_tests(support.brief())}
        self.assertTrue(tests["AC-05"].passes(0.95))
        self.assertTrue(tests["AC-01"].passes(0))
        self.assertFalse(tests["AC-01"].passes(1))


if __name__ == "__main__":
    unittest.main()
