"""Pin the numbers the README prints, so a change to the tool or the data that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401
import common
import dispute_clock as dc

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def run_step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout.splitlines()


class GoldenTests(unittest.TestCase):
    def assertLines(self, lines, expected):
        for want in expected:
            self.assertIn(want, lines)

    def test_step_01(self):
        self.assertLines(run_step("step_01_flat_target.py"), [
            "  disputes: 150   clocks that apply: 524   read as of 2026-09-30",
            "  planted truth: missed 151 (late 93, breached 58); running 33; not started 43; on time 297",
            "  disputes the queue flags past target: 40 of 150",
            "  missed clocks the queue shows: 32 of 151",
            "    DC1: 0 of 50 shown", "    DC2: 0 of 34 shown", "    DC3: 26 of 31 shown",
            "    DC4: 6 of 6 shown", "    DC5: 0 of 30 shown",
            "  disputes flagged although none of their clocks was missed: 3"])

    def test_step_02(self):
        self.assertLines(run_step("step_02_calendar_countdown.py"), [
            "  statuses that match the planted truth: 454 of 524 (86.6%)",
            "  missed clocks found: 126 of 151",
            "  called missed, truth says not: 45",
            "  called fine or not due, truth says missed: 25",
            "  wrong statuses by clock: DC1 29, DC2 12, DC3 8, DC4 1, DC5 20"])

    def test_step_03(self):
        self.assertLines(run_step("step_03_deficiencies_exposed.py"), [
            "  step 2 method: 70 wrong of 524", "  business days only: 37 wrong of 524",
            "  first-contact start only: 76 wrong of 524", "  both fixes: 5 wrong of 524",
            "    boundary     32 / 109", "    holiday      16 / 57", "    logged_late  33 / 241",
            "    pause        3 / 22", "    misrecorded  1 / 6",
            "  KNOWN LIMIT: with both fixes, 5 statuses still differ from the planted truth",
            "    called missed, plan says not: 4 (4 on paused investigations)",
            "    missed clocks called fine: 1 (1 on a wrongly recorded window class)",
            "    DSP-0036 DC3, DSP-0051 DC3, DSP-0079 DC3, DSP-0092 DC4, DSP-0103 DC3"])

    def test_step_04(self):
        lines = run_step("step_04_business_day_clocks.py")
        self.assertLines(lines, [
            "  statuses that match the planted truth: 519 of 524 (99.0%)",
            "  missed clocks found: 150 of 151; missed clocks the tool calls fine: 1",
            "  called missed, truth says not: 4",
            "    event on the due day                     108 / 109",
            "    business-day window across a holiday     57 / 57",
            "    logged after first contact               238 / 241",
            "    paused investigation                     18 / 22",
            "    extended class recorded, never applied   5 / 6",
            "  KNOWN LIMIT: 4 false alarms (4 on paused investigations): "
            "DSP-0036 DC3, DSP-0051 DC3, DSP-0079 DC3, DSP-0103 DC3",
            "  ALSO, the tool trusts the recorded window class: missed clocks it calls fine: DSP-0092 DC4",
            "  disputes with at least one missed clock: 107 of 150",
            "  running clocks due within 5 days of the as-of date: 14 on 14 disputes"])
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["right"], s["clocks"], s["missed_found"], s["missed_truth"], s["false_alarms"]),
                         (519, 524, 150, 151, 4))

    def test_the_stand_in_with_both_fixes_is_the_tool(self):
        world = common.load_world()
        self.assertEqual(common.stand_in_statuses(world, True, "first_contact_on"), common.tool_statuses(world))

    def test_the_tool_and_the_plan_agree_on_the_planted_hard_negatives(self):
        world = common.load_world()
        got = common.tool_statuses(world)
        wrong = set(common.disagreements(got, world))
        for key, t in world["truth"].items():
            if "pause" not in t["tags"] and "misrecorded" not in t["tags"]:
                self.assertNotIn(key, wrong, key)

    def test_truth_covers_exactly_the_clocks_that_apply(self):
        world = common.load_world()
        self.assertEqual(sorted((d["dispute_id"], c["clock_id"]) for d, c in common.applicable(world)),
                         sorted(world["truth"]))

    def test_demo_output_is_pinned(self):
        r = subprocess.run([sys.executable, "dispute_clock.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.splitlines(), [
            "as of 2026-09-30: 1 dispute, 4 clocks apply (5 clocks in policy, 11 holidays loaded)",
            "missed 1 (late 1, breached 0); running 1, of which 1 due within 5 days; not started 1; on time 1",
            "DSP-EX1  unauthorized_card",
            "  DC1 Acknowledge to customer                due 2026-09-09  sent 2026-09-09  on time",
            "  DC2 Provisional credit decision            due 2026-09-16  sent 2026-09-18  late by 2 business days",
            "  DC3 Investigation concluded (standard)     due 2026-10-04  sent not done    running, 4 days left",
            "  DC5 Final notice to customer               not started (waits for concluded_on)"])

    def test_bundled_policy_and_holidays_load(self):
        self.assertEqual([c["clock_id"] for c in dc.load_policy(os.path.join(common.DATA, "policy.csv"))],
                         ["DC1", "DC2", "DC3", "DC4", "DC5"])


if __name__ == "__main__":
    unittest.main()
