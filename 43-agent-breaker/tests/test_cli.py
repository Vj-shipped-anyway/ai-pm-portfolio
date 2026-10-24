import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
from _util import EVENT_HEADER, run_cli, write_csv
import agent_breaker as ab

GOOD = [[i, "a", f"c{i}", "ok", ""] for i in range(6)]
TRIPPING = [[i, "a", f"c{i}", "fail", "tool_error"] for i in range(6)]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def events(self, rows, header=None, name="events.csv"):
        return write_csv(self.dir.name, name, header or EVENT_HEADER, rows)

    def raw(self, text, name="raw.csv", mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8", "newline": ""})) as fh:
            fh.write(text)
        return p

    def test_demo_runs_and_trips_once(self):
        code, out, _ = run_cli(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: TRIPPED 1 time", out)
        self.assertIn("chain intact, replay agrees", out)

    def test_a_trip_exits_1_and_fail_on_never_exits_0(self):
        p = self.events(TRIPPING)
        self.assertEqual(run_cli(["run", p])[0], 1)
        self.assertEqual(run_cli(["run", p, "--fail-on", "never"])[0], 0)

    def test_a_clean_stream_exits_0_and_says_so(self):
        code, out, _ = run_cli(["run", self.events(GOOD)])
        self.assertEqual(code, 0)
        self.assertIn("CLEAR, the breaker never tripped", out)

    def test_controls_are_applied_and_a_no_op_release_is_reported(self):
        c = write_csv(self.dir.name, "c.csv", list(ab.CONTROL_COLS), [[2, "a", "release", "oncall", "nothing to release"], [3, "a", "engage", "oncall", "maintenance"]])
        code, out, _ = run_cli(["run", self.events(GOOD), "--controls", c])
        self.assertEqual(code, 0)
        self.assertIn("had no effect", out)
        self.assertIn("-> FORCED_OPEN", out)
        self.assertIn("held for a person", out)

    def test_a_control_for_an_agent_with_no_events_is_still_shown(self):
        c = write_csv(self.dir.name, "c.csv", list(ab.CONTROL_COLS), [[1, "ghost", "engage", "oncall", "maintenance"]])
        code, out, _ = run_cli(["run", self.events(GOOD), "--controls", c])
        self.assertEqual(code, 0)
        self.assertIn("agent ghost   0 calls", out)
        self.assertIn("CLOSED      -> FORCED_OPEN", out)

    def test_log_is_written_and_verifies_and_head_catches_a_cut(self):
        log = os.path.join(self.dir.name, "log.jsonl")
        code, out, _ = run_cli(["run", self.events(TRIPPING), "--log", log])
        self.assertEqual(code, 1)
        head = out.strip().splitlines()[-1].rsplit(" ", 1)[1]
        self.assertEqual(run_cli(["verify", log])[0], 0)
        self.assertEqual(run_cli(["verify", log, "--head", head])[0], 0)
        with open(log, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        short = self.raw("\n".join(lines[:-1]) + "\n", "short.jsonl")
        self.assertEqual(run_cli(["verify", short])[0], 0)              # a cut between two complete events is consistent on its own
        self.assertEqual(run_cli(["verify", short, "--head", head])[0], 1)
        self.assertEqual(run_cli(["verify", log, "--head", "0" * 64])[0], 1)

    def test_verify_reports_an_edit_with_exit_1(self):
        log = os.path.join(self.dir.name, "log.jsonl")
        run_cli(["run", self.events(TRIPPING), "--log", log])
        with open(log, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        ev = json.loads(lines[3])
        ev["t"] += 5
        lines[3] = json.dumps(ev, sort_keys=True)
        code, out, _ = run_cli(["verify", self.raw("\n".join(lines) + "\n", "edited.jsonl")])
        self.assertEqual(code, 1)
        self.assertIn("log NOT verified", out)

    def test_missing_files_exit_2(self):
        self.assertEqual(run_cli(["run", "nope.csv"])[0], 2)
        self.assertEqual(run_cli(["verify", "nope.jsonl"])[0], 2)

    def test_empty_wrong_type_and_truncated_events_exit_2_with_one_line(self):
        cases = {
            "empty": self.raw(""),
            "header only": self.events([]),
            "wrong columns": self.events([[1, "a"]], ["t_min", "agent"]),
            "outcome not ok or fail": self.events([[1, "a", "c", "maybe", ""]]),
            "minutes not a number": self.events([["soon", "a", "c", "ok", ""]]),
            "negative minutes": self.events([[-1, "a", "c", "ok", ""]]),
            "fractional minutes": self.events([[1.5, "a", "c", "ok", ""]]),
            "blank agent": self.events([[1, "", "c", "ok", ""]]),
            "out of order": self.events([[5, "a", "c1", "ok", ""], [4, "a", "c2", "ok", ""]]),
            "truncated row": self.raw(",".join(EVENT_HEADER) + "\n1,a,c1,ok,\n2,a,c"),
            "too many fields": self.raw(",".join(EVENT_HEADER) + "\n1,a,c1,ok,,extra\n"),
            "json instead of csv": self.raw('{"t_min": 1}'),
            "not utf-8": self.raw(b"\xff\xfe\x00\x01", "bin.csv", mode="wb"),
        }
        for name, path in cases.items():
            code, out, err = run_cli(["run", path])
            self.assertEqual(code, 2, name)
            self.assertEqual(out, "", name)
            self.assertEqual(len(err.strip().splitlines()), 1, name)
            self.assertNotIn("Traceback", err, name)

    def test_bad_controls_and_policy_exit_2(self):
        p = self.events(GOOD)
        bad_ctl = write_csv(self.dir.name, "c.csv", list(ab.CONTROL_COLS), [[1, "a", "pause", "x", "y"]])
        self.assertEqual(run_cli(["run", p, "--controls", bad_ctl])[0], 2)
        unknown = write_csv(self.dir.name, "p1.csv", ["parameter", "value"], [["trip_rate", 0.4]])
        dup = write_csv(self.dir.name, "p2.csv", ["parameter", "value"], [["probe_calls", 2], ["probe_calls", 3]])
        notnum = write_csv(self.dir.name, "p3.csv", ["parameter", "value"], [["window_min", "soon"]])
        outside = write_csv(self.dir.name, "p4.csv", ["parameter", "value"], [["trip_failure_rate", 7]])
        for path in (unknown, dup, notnum, outside):
            code, _, err = run_cli(["run", p, "--policy", path])
            self.assertEqual(code, 2, path)
            self.assertEqual(len(err.strip().splitlines()), 1)

    def test_policy_file_changes_the_result(self):
        p = self.events([[i, "a", f"c{i}", "fail", "tool_error"] for i in range(3)])
        self.assertEqual(run_cli(["run", p])[0], 0)
        strict = write_csv(self.dir.name, "p.csv", ["parameter", "value"], [["consecutive_trip", 3]])
        self.assertEqual(run_cli(["run", p, "--policy", strict])[0], 1)

    def test_agent_filter_that_matches_nothing_says_so(self):
        code, _, err = run_cli(["run", self.events(GOOD), "--agent", "nobody"])
        self.assertEqual(code, 2)
        self.assertIn("nothing was run", err)

    def test_agent_filter_runs_one_agent(self):
        rows = TRIPPING + [[i, "b", f"d{i}", "ok", ""] for i in range(6)]
        code, out, _ = run_cli(["run", self.events(sorted(rows, key=lambda r: r[0])), "--agent", "b"])
        self.assertEqual(code, 0)
        self.assertNotIn("agent a ", out)

    def test_malformed_logs_exit_2(self):
        for text in ("", "not json\n", "[1, 2]\n", '{"seq": 1}\n', "\n"):
            code, _, err = run_cli(["verify", self.raw(text, "bad.jsonl")])
            self.assertEqual(code, 2, repr(text))
            self.assertEqual(len(err.strip().splitlines()), 1)

    def test_hostile_strings_cannot_forge_output_lines(self):
        hostile = "a\n::error::forged\n  t=1     CLOSED -> OPEN"
        rows = [[i, hostile, f"c{i}", "fail", "scope\nviolation"] for i in range(6)]
        c = write_csv(self.dir.name, "c.csv", list(ab.CONTROL_COLS), [[7, hostile, "engage", "who\n::warning::x", "r"], [8, hostile, "engage", "who\n::warning::x", "r"]])
        code, out, _ = run_cli(["run", self.events(rows), "--controls", c, "--fail-on", "never"])
        self.assertEqual(code, 0)
        for line in out.splitlines():
            self.assertFalse(line.startswith("::"), line)
        self.assertEqual(sum(1 for ln in out.splitlines() if ln.startswith("agent ")), 1)
        self.assertIn("a\\n::error::forged", out)
        code, _, err = run_cli(["run", self.events(rows, name="e2.csv"), "--agent", hostile + "x"])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_hostile_policy_name_is_escaped_in_the_error(self):
        bad = write_csv(self.dir.name, "p.csv", ["parameter", "value"], [["x\n::error::forged", 1]])
        code, _, err = run_cli(["run", self.events(GOOD), "--policy", bad])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_no_arguments_prints_help_and_exits_2(self):
        self.assertEqual(run_cli([])[0], 2)


if __name__ == "__main__":
    unittest.main()
