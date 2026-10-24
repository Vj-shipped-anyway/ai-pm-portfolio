from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
import runbook_dryrun as rd

BASE = """runbook: rb
reads: [svc.error_pct, change.freeze]
params:
  target: api
steps:
  - id: s1
    effect: read
    risk: low
    run: "ctl status {{target}}"
    requires: ["svc.error_pct >= 5"]
  - id: s2
    effect: write
    risk: high
    run: "ctl restart {{target}}"
    requires: ["change.freeze == off"]
    sets: {svc.mode: restarted}
    approval:
      role: commander
      ttl_minutes: 30
    rollback: "ctl start {{target}}"
  - id: s3
    effect: read
    risk: low
    run: "ctl status {{target}}"
    requires: ["svc.mode == restarted"]
"""
WORLD = {"svc.error_pct": 9, "change.freeze": "off"}
D = rd.digest("rb", "s2", "ctl restart api")


def rec(**kw):
    base = {"step": "s2", "approver": "marta", "role": "commander", "digest": D, "age_minutes": 5}
    base.update(kw)
    return base


def go(text=BASE, world=WORLD, approvals=None, requester="dana", params=None, checks=("lint", "state", "gate")):
    return rd.dry_run(rd.load_runbook(text), world, params or {}, [rec()] if approvals is None else approvals, requester, checks)


def kinds(res):
    return sorted(f["kind"] for f in res["findings"])


class GateTests(unittest.TestCase):
    def test_valid_approval_is_ready(self):
        res = go()
        self.assertEqual((res["verdict"], kinds(res)), ("READY", []))

    def test_no_record_waits_and_the_walk_continues(self):
        res = go(approvals=[])
        self.assertEqual(res["verdict"], "WAITING")
        self.assertEqual([r["status"] for r in res["rows"]], ["ok", "WAITING", "ok"])

    def test_self_approval_ignores_case_and_spaces(self):
        res = go(approvals=[rec(approver="  Dana ")])
        self.assertEqual(kinds(res), ["approval_invalid"])
        self.assertIn("self_approval", res["findings"][0]["reason"])

    def test_wrong_role(self):
        self.assertIn("wrong_role", go(approvals=[rec(role="analyst")])["findings"][0]["reason"])

    def test_digest_binds_the_exact_command(self):
        res = go(params={"target": "other"})
        self.assertEqual(res["verdict"], "BLOCKED")
        self.assertIn("digest_mismatch", res["findings"][0]["reason"])

    def test_age_equal_to_the_limit_is_valid_and_one_over_is_not(self):
        self.assertEqual(go(approvals=[rec(age_minutes=30)])["verdict"], "READY")
        self.assertIn("stale_approval", go(approvals=[rec(age_minutes=31)])["findings"][0]["reason"])

    def test_one_valid_record_outweighs_an_invalid_one(self):
        self.assertEqual(go(approvals=[rec(approver="dana"), rec()])["verdict"], "READY")

    def test_every_invalid_record_is_reported(self):
        res = go(approvals=[rec(approver="dana"), rec(role="analyst")])
        self.assertEqual(kinds(res), ["approval_invalid", "approval_invalid"])

    def test_record_for_a_step_without_a_gate_is_a_warning(self):
        res = go(approvals=[rec(), rec(step="s1")])
        self.assertEqual((res["verdict"], kinds(res)), ("READY", ["approval_unmatched"]))

    def test_gate_row_carries_the_digest(self):
        self.assertEqual(go()["rows"][1]["gate"]["digest"], D)


class LintTests(unittest.TestCase):
    def test_undefined_param_in_run_and_rollback(self):
        res = go(BASE.replace("ctl start {{target}}", "ctl start {{zone}}").replace("ctl status {{target}}\"\n    requires: [\"svc.error", "ctl status {{host}}\"\n    requires: [\"svc.error"))
        self.assertEqual(kinds(res), ["undefined_param", "undefined_param"])

    def test_placeholder_in_a_note_is_not_a_defect(self):
        res = go(BASE.replace("    rollback:", "    note: \"ask {{vendor}} first\"\n    rollback:"))
        self.assertEqual(res["verdict"], "READY")

    def test_write_ungated(self):
        text = BASE.replace("    approval:\n      role: commander\n      ttl_minutes: 30\n", "")
        res = go(text, approvals=[])
        self.assertEqual((res["verdict"], kinds(res)), ("BLOCKED", ["write_ungated"]))

    def test_low_risk_write_needs_no_gate_and_no_rollback(self):
        text = BASE.replace("risk: high", "risk: low").replace("    approval:\n      role: commander\n      ttl_minutes: 30\n", "").replace("    rollback: \"ctl start {{target}}\"\n", "")
        self.assertEqual(go(text, approvals=[])["verdict"], "READY")

    def test_missing_rollback_warns_and_none_does_not(self):
        no_rb = BASE.replace("    rollback: \"ctl start {{target}}\"\n", "")
        res = go(no_rb)
        self.assertEqual((res["verdict"], kinds(res)), ("READY", ["no_rollback"]))
        self.assertEqual(kinds(go(BASE.replace("rollback: \"ctl start {{target}}\"", "rollback: none"))), [])

    def test_duplicate_id(self):
        self.assertIn("duplicate_id", kinds(go(BASE.replace("id: s3", "id: s2"))))

    def test_undeclared_key_but_a_key_set_by_an_earlier_step_is_fine(self):
        self.assertEqual(kinds(go(BASE.replace("svc.error_pct >= 5", "svc.err_pct >= 5"))), ["state_unknown", "undeclared_state_key"])
        self.assertEqual([f for f in lint_of(BASE) if f["kind"] == "undeclared_state_key"], [])


def lint_of(text):
    return rd.lint(rd.load_runbook(text))


class StateTests(unittest.TestCase):
    def test_precondition_false_names_the_value(self):
        res = go(world={"svc.error_pct": 2, "change.freeze": "off"})
        self.assertEqual(kinds(res), ["precondition_false"])
        self.assertIn("holds 2", res["findings"][0]["reason"])
        self.assertEqual([r["status"] for r in res["rows"]], ["STOPS", "not reached", "not reached"])

    def test_a_later_step_sees_what_an_earlier_step_set(self):
        res = go(BASE.replace("svc.mode == restarted", "svc.mode == started"))
        self.assertIn("(set by s2)", res["findings"][0]["reason"])

    def test_missing_key_is_an_error_not_a_pass(self):
        res = go(world={"change.freeze": "off"})
        self.assertEqual(kinds(res), ["state_unknown"])

    def test_text_is_not_compared_with_a_number(self):
        res = go(world={"svc.error_pct": "9", "change.freeze": "off"})
        self.assertEqual(kinds(res), ["state_type_mismatch"])
        self.assertIn("cannot compare text", res["findings"][0]["reason"])

    def test_bool_is_not_a_number_and_int_equals_float(self):
        self.assertEqual(kinds(go(world={"svc.error_pct": True, "change.freeze": "off"})), ["state_type_mismatch"])
        self.assertEqual(go(world={"svc.error_pct": 9.5, "change.freeze": "off"})["verdict"], "READY")

    def test_ordering_needs_numbers(self):
        res = go(BASE.replace("change.freeze == off", "change.freeze >= off"))
        self.assertEqual(kinds(res), ["state_type_mismatch"])

    def test_the_snapshot_passed_in_is_not_changed(self):
        world = dict(WORLD)
        go(world=world)
        self.assertEqual(world, WORLD)

    def test_a_runbook_with_no_conditions_says_the_snapshot_was_unused(self):
        text = "runbook: r\nsteps:\n  - id: s1\n    effect: read\n    risk: low\n    run: x\n"
        res = go(text, world={}, approvals=[])
        self.assertEqual(res["verdict"], "READY")
        self.assertIn("snapshot was not read", res["notes"][0])


class PartsTests(unittest.TestCase):
    def test_each_part_sees_only_its_own_defects(self):
        bad_gate = [rec(approver="dana")]
        self.assertEqual(go(approvals=bad_gate, checks=("lint",))["verdict"], "READY")
        self.assertEqual(go(approvals=bad_gate, checks=("state",))["verdict"], "READY")
        self.assertEqual(go(approvals=bad_gate, checks=("gate",))["verdict"], "BLOCKED")
        self.assertEqual(go(world={}, checks=("lint",))["verdict"], "READY")
        self.assertEqual(go(world={}, checks=("state",))["verdict"], "BLOCKED")


class RenderTests(unittest.TestCase):
    def test_unknown_placeholder_stays_visible(self):
        self.assertEqual(rd.render("a {{x}} {{ y }} {{z}}", {"x": 1, "y": True}), "a 1 true {{z}}")

    def test_digest_depends_on_runbook_step_and_command(self):
        a = rd.digest("r", "s1", "cmd")
        self.assertEqual(len(a), 12)
        self.assertNotEqual(a, rd.digest("r2", "s1", "cmd"))
        self.assertNotEqual(a, rd.digest("r", "s2", "cmd"))
        self.assertNotEqual(a, rd.digest("r", "s1", "cmd2"))

    def test_safe_replaces_control_characters(self):
        self.assertEqual(rd.safe("a\nb\r\x1b\u2028"), "a\\x0ab\\x0d\\x1b\\u2028")

    def test_escape_annotation(self):
        self.assertEqual(rd.escape_annotation("100%\r\n::error::x"), "100%25%0D%0A::error::x")


if __name__ == "__main__":
    unittest.main()
