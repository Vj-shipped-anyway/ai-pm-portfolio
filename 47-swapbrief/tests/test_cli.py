"""Command-line behavior: exit status, one-line errors on bad input, escaping of hostile strings."""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401
from _fixtures import COLUMNS, make_rows, write_prices, write_results

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
DATA = os.path.join(SRC, "..", "data")


def cli(*args):
    return subprocess.run([sys.executable, "swapbrief.py"] + list(args), cwd=SRC, capture_output=True, text=True)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.results = os.path.join(self.dir, "results.csv")
        self.prices = os.path.join(self.dir, "prices.csv")
        write_results(self.results, make_rows())
        write_prices(self.prices)

    def tearDown(self):
        self.tmp.cleanup()

    def brief(self, *extra, results=None, prices=None):
        return cli("brief", results or self.results, prices or self.prices, "--baseline", "old", "--candidate", "new",
                   "--resamples", "200", *extra)

    def assert_input_error(self, r):
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(r.stderr.count("\n"), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("input error: "), r.stderr)
        self.assertEqual(r.stdout, "")

    def test_demo(self):
        r = cli("--demo")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("decision: NO-GO", r.stdout)
        self.assertIn("rollback triggers", r.stdout)

    def test_no_arguments_is_a_usage_error(self):
        r = cli()
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_go_exit_zero(self):
        r = self.brief()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("decision: GO", r.stdout)

    def test_nogo_exit_one_and_never(self):
        write_results(self.results, make_rows(out_mult=4.0))
        self.assertEqual(self.brief().returncode, 1)
        self.assertEqual(self.brief("--fail-on", "never").returncode, 0)

    def test_guardrails_exit(self):
        write_results(self.results, make_rows(drop_slice="a"))
        self.assertEqual(self.brief().returncode, 0)
        self.assertEqual(self.brief("--fail-on", "guardrails").returncode, 1)

    def test_json_format(self):
        r = self.brief("--format", "json")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["decision"], "GO")
        self.assertEqual(out["pairs"], 120)

    def test_other_systems_are_counted_not_silent(self):
        rows = make_rows() + [dict(make_rows()[0], system="third")]
        write_results(self.results, rows)
        r = self.brief()
        self.assertIn("1 row(s) of other systems were ignored", r.stdout)

    def test_empty_file(self):
        open(self.results, "w").close()
        self.assert_input_error(self.brief())

    def test_header_only(self):
        write_results(self.results, [])
        self.assert_input_error(self.brief())

    def test_wrong_type_directory_json_and_binary(self):
        self.assert_input_error(self.brief(results=self.dir))
        with open(self.results, "w") as fh:
            json.dump({"results": [1, 2, 3]}, fh)
        self.assert_input_error(self.brief())
        with open(self.results, "wb") as fh:
            fh.write(b"\xff\xfe\x00\x81binary\x00")
        self.assert_input_error(self.brief())

    def test_missing_file(self):
        self.assert_input_error(self.brief(results=os.path.join(self.dir, "nope.csv")))

    def test_truncated_mid_row(self):
        with open(self.results, encoding="utf-8") as fh:
            text = fh.read()
        with open(self.results, "w", encoding="utf-8") as fh:
            fh.write(text[: text.rindex("\n", 0, len(text) - 5) + 12])
        self.assert_input_error(self.brief())

    def test_truncated_at_a_row_boundary(self):
        with open(self.results, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        with open(self.results, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines[:-1]) + "\n")
        self.assert_input_error(self.brief())

    def test_missing_column(self):
        with open(self.results, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow([c for c in COLUMNS if c != "latency_ms"])
            w.writerow(["I1", "a", "old", "1", "10", "10"])
        self.assert_input_error(self.brief())

    def test_wrong_type_cell(self):
        rows = make_rows()
        rows[3]["correct"] = "maybe"
        write_results(self.results, rows)
        self.assert_input_error(self.brief())

    def test_prices_problems(self):
        with open(self.prices, "w") as fh:
            fh.write("system,input_usd_per_1k,output_usd_per_1k\nold,0.003,0.015\n")
        self.assert_input_error(self.brief())
        with open(self.prices, "w") as fh:
            fh.write("system,input_usd_per_1k,output_usd_per_1k\nold,0.003,0.015\nnew,free,0.01\n")
        self.assert_input_error(self.brief())
        with open(self.prices, "w") as fh:
            fh.write("system,input_usd_per_1k,output_usd_per_1k\nold,0.003,0.015\nnew,0,0\n")
        self.assert_input_error(self.brief())

    def test_unknown_system_and_critical_slice(self):
        r = cli("brief", self.results, self.prices, "--baseline", "old", "--candidate", "ghost")
        self.assert_input_error(r)
        self.assert_input_error(self.brief("--critical", "nope"))

    def test_bad_options(self):
        self.assert_input_error(self.brief("--tolerance-pp", "nan"))
        r = cli("brief", self.results, self.prices, "--baseline", "old", "--candidate", "new", "--resamples", "5")
        self.assert_input_error(r)

    def test_hostile_system_name_in_an_error_stays_on_one_line(self):
        r = cli("brief", self.results, self.prices, "--baseline", "old", "--candidate", "x\n::error::boom%")
        self.assert_input_error(r)
        self.assertIn("x%0A::error::boom%25", r.stderr)

    def test_hostile_slice_name_in_the_brief(self):
        hostile = "s\r\n::warning::pwned"
        write_results(self.results, make_rows(drop_slice=hostile, slice_a=hostile))
        r = self.brief("--critical", hostile)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertFalse(any(line.startswith("::") for line in r.stdout.split("\n")))
        self.assertIn("s%0D%0A::warning::pwned", r.stdout)

    def test_demo_critical_slices_match_the_data(self):
        from swapbrief import DEMO
        with open(os.path.join(DATA, "slices.csv"), newline="", encoding="utf-8") as fh:
            critical = [r["slice"] for r in csv.DictReader(fh) if r["critical"] == "1"]
        self.assertEqual(sorted(critical), sorted(DEMO["critical"]))


if __name__ == "__main__":
    unittest.main()
