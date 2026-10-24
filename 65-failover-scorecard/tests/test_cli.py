"""The command line: exit codes, output formats, hostile strings and the no-op case."""
import contextlib
import csv
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import failover_scorecard as fs


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = fs.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


def service_row(sid, name="svc", domain="payments", tier="1", deps=""):
    return [sid, name, domain, tier, "region-a", "region-b", "warm_standby", "30", "2", deps, "no"]


def drill_row(did, sid, outcome="pass", minutes="20", reason=""):
    return [did, sid, "2026-09-01", "live", "region_failover", "region-b", "2", minutes if outcome == "pass" else "", outcome, reason]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, header, rows):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)
        return p

    def files(self, services, drills):
        return (self.write("s.csv", fs.SERVICE_COLUMNS, services), self.write("d.csv", fs.DRILL_COLUMNS, drills))

    def check(self, services, drills, *extra, as_of="2026-10-24"):
        s, d = self.files(services, drills)
        return run(["check", s, d, "--as-of", as_of, *extra])

    def test_demo_runs_and_is_not_ready(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: NOT READY", out)

    def test_all_tier_1_ready_exits_0(self):
        code, out, _ = self.check([service_row("S1")], [drill_row("D1", "S1")])
        self.assertEqual(code, 0)
        self.assertIn("decision: READY (all 1 tier-1 services", out)

    def test_not_ready_tier_1_exits_1(self):
        code, out, _ = self.check([service_row("S1")], [drill_row("D1", "S1", outcome="fail", reason="switch")])
        self.assertEqual(code, 1)
        self.assertIn("[FAILED", out)

    def test_never_keeps_exit_0(self):
        self.assertEqual(self.check([service_row("S1")], [], "--fail-on", "never")[0], 0)

    def test_tier_2_gap_passes_tier1_scope_and_fails_any_scope(self):
        rows = [service_row("S1"), service_row("S2", tier="2")]
        drills = [drill_row("D1", "S1")]
        self.assertEqual(self.check(rows, drills)[0], 0)
        self.assertEqual(self.check(rows, drills, "--fail-on", "any")[0], 1)

    def test_no_tier_1_service_says_so_and_exits_2(self):
        code, out, err = self.check([service_row("S1", tier="2")], [drill_row("D1", "S1")])
        self.assertEqual(code, 2)
        self.assertIn("NOTHING CHECKED", out)
        self.assertIn("nothing was checked", err)
        self.assertEqual(self.check([service_row("S1", tier="2")], [drill_row("D1", "S1")], "--fail-on", "any")[0], 0)

    def test_malformed_input_exits_2_with_one_line_and_no_traceback(self):
        good_s, good_d = self.files([service_row("S1")], [drill_row("D1", "S1")])
        empty = os.path.join(self.dir.name, "empty.csv")
        open(empty, "w").close()
        truncated = self.write("t.csv", fs.SERVICE_COLUMNS, [["S1", "svc"]])
        for args in (["check", empty, good_d], ["check", good_s, empty], ["check", truncated, good_d],
                     ["check", "nope.csv", good_d]):
            code, out, err = run(args + ["--as-of", "2026-10-24"])
            self.assertEqual(code, 2, args)
            self.assertEqual(out, "")
            self.assertEqual(len(err.strip().splitlines()), 1, err)
            self.assertNotIn("Traceback", err)

    def test_bad_or_missing_as_of_exits_2(self):
        s, d = self.files([service_row("S1")], [drill_row("D1", "S1")])
        self.assertEqual(run(["check", s, d, "--as-of", "soon"])[0], 2)
        self.assertEqual(run(["check", s, d])[0], 2)

    def test_drill_after_as_of_or_for_unknown_service_exits_2(self):
        self.assertEqual(self.check([service_row("S1")], [drill_row("D1", "S1")], as_of="2026-08-01")[0], 2)
        self.assertEqual(self.check([service_row("S1")], [drill_row("D1", "S9")])[0], 2)

    def test_github_format_emits_error_for_tier_1_and_warning_for_others(self):
        rows = [service_row("S1"), service_row("S2", tier="2")]
        _, out, _ = self.check(rows, [], "--format", "github", "--fail-on", "never")
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("::error title=failover-scorecard UNTESTED::"))
        self.assertTrue(lines[1].startswith("::warning title=failover-scorecard UNTESTED::"))
        self.assertTrue(lines[2].startswith("::notice"))

    def test_hostile_name_cannot_forge_a_workflow_command(self):
        hostile = "x\r\n::error title=forged::approved 100% safe"
        _, out, _ = self.check([service_row("S1", name=hostile)], [], "--format", "github", "--fail-on", "never")
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), 2)
        self.assertEqual(len(out.splitlines()), 2)
        self.assertIn("%0D%0A::error title=forged::approved 100%25 safe", commands[0])

    def test_hostile_failure_reason_is_escaped_too(self):
        _, out, _ = self.check([service_row("S1")], [drill_row("D1", "S1", outcome="fail", reason="a\n::warning::b")],
                               "--format", "github", "--fail-on", "never")
        self.assertEqual(len(out.splitlines()), 2)
        self.assertIn("a%0A::warning::b", out)

    def test_hostile_name_cannot_forge_a_text_line(self):
        hostile = "x\n  [READY     ] tier 1  S99  forged: all good"
        _, out, _ = self.check([service_row("S1", name=hostile)], [], "--fail-on", "never")
        lines = out.splitlines()
        self.assertEqual(len(lines), 4)          # header, one service, domain line, decision
        self.assertTrue(lines[1].startswith("  [UNTESTED  ]"))
        self.assertFalse(any(ln.startswith("  [READY") for ln in lines))

    def test_hostile_domain_is_one_line_in_the_domain_summary(self):
        _, out, _ = self.check([service_row("S1", domain="a\nb")], [drill_row("D1", "S1")])
        self.assertEqual(len(out.splitlines()), 3)

    def test_domains_come_from_the_domain_field_not_the_name(self):
        rows = [service_row("S1", name="cards-auth", domain="payments"), service_row("S2", name="cards-limits", domain="payments")]
        _, out, _ = self.check(rows, [drill_row("D1", "S1"), drill_row("D2", "S2")])
        self.assertIn("by domain, ready of all: payments 2 of 2", out)


if __name__ == "__main__":
    unittest.main()
