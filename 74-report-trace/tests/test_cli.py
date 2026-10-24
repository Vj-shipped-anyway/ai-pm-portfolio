import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import report_trace as rt
from test_trace import FILED, SPEC


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = rt.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


HEADER = "loan_id,product,status,booked_date,days_past_due,balance_cents,servicer_note\n"
LOANS = [("L1", "a", "open", "2026-05-01", "0", "100000", ""), ("L2", "a", "open", "2026-05-01", "0", "50000", ""),
         ("L3", "a", "open", "2026-05-01", "30", "20000", ""), ("L4", "b", "open", "2026-05-01", "0", "70000", ""),
         ("L5", "b", "open", "2026-05-01", "10", "10000", "")]


def loans_csv(rows):
    return HEADER + "".join(",".join(f'"{x}"' for x in r) + "\n" for r in rows)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def write(self, name, text):
        with open(self.path(name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return self.path(name)

    def world(self, now=None, adjustments="adj_id,cell_id,amount_cents,reason\n", filed=None):
        self.write("spec.json", json.dumps(SPEC))
        self.write("filed.csv", "cell_id,value\n" + "".join(f"{k},{v}\n" for k, v in (filed or FILED).items()))
        self.write("adj.csv", adjustments)
        self.write("then.csv", loans_csv(LOANS))
        self.write("now.csv", loans_csv(now or LOANS))
        return run(["build", "--source", self.path("then.csv"), "--spec", self.path("spec.json"), "--filed", self.path("filed.csv"),
                    "--adjustments", self.path("adj.csv"), "--out", self.path("lin.json")])

    def verify(self, *extra):
        return run(["verify", "--lineage", self.path("lin.json"), "--source", self.path("now.csv"), *extra])

    def test_clean_report_exits_0(self):
        self.assertEqual(self.world()[0], 0)
        code, out, _ = self.verify()
        self.assertEqual(code, 0)
        self.assertIn("nothing needs a person", out)

    def test_source_change_exits_1_and_names_the_row(self):
        changed = [r[:5] + ("21000",) + r[6:] if r[0] == "L3" else r for r in LOANS]
        self.world(now=changed)
        code, out, _ = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("L3 balance_cents 20000 -> 21000", out)

    def test_note_change_alone_is_quiet(self):
        noted = [r[:6] + ("called twice",) if r[0] == "L3" else r for r in LOANS]
        self.world(now=noted)
        self.assertEqual(self.verify()[0], 0)

    def test_github_format_emits_annotations(self):
        changed = [r[:5] + ("21000",) + r[6:] if r[0] == "L3" else r for r in LOANS]
        self.world(now=changed)
        _, out, _ = self.verify("--format", "github")
        self.assertTrue(out.startswith("::error::a.late"))
        self.assertTrue(out.splitlines()[-1].startswith("::notice::"))

    def test_trace_prints_the_path(self):
        self.world()
        code, out, _ = run(["trace", "--lineage", self.path("lin.json"), "--cell", "a.current", "--source", self.path("now.csv")])
        self.assertEqual(code, 0)
        self.assertIn("source rows at filing: 2, sum 1,500.00", out)
        self.assertIn("every row is unchanged", out)

    def test_trace_of_an_unknown_cell_exits_2(self):
        self.world()
        code, _, err = run(["trace", "--lineage", self.path("lin.json"), "--cell", "nope"])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_wrong_source_file_says_so(self):
        self.world()
        self.write("now.csv", loans_csv([("Z1", "a", "open", "2026-05-01", "0", "1", "")]))
        code, _, err = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("none of the lineage rows", err)

    def assert_exit_2(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)

    def build_args(self, source=None, spec=None, filed=None, adj=None):
        return ["build", "--source", source or self.path("then.csv"), "--spec", spec or self.path("spec.json"),
                "--filed", filed or self.path("filed.csv"), "--adjustments", adj or self.path("adj.csv"), "--out", self.path("o.json")]

    def test_bad_loan_files_exit_2(self):
        self.world()
        cases = {"empty": "", "header_only": HEADER, "missing_column": "loan_id,product\nL1,a\n",
                 "truncated_row": HEADER + "L1,a,open,2026-05-01,0\n", "decimal_balance": loans_csv([("L1", "a", "open", "2026-05-01", "0", "12.5", "")]),
                 "underscore_balance": loans_csv([("L1", "a", "open", "2026-05-01", "0", "1_0", "")]),
                 "bad_date": loans_csv([("L1", "a", "open", "20260501", "0", "5", "")]),
                 "negative_dpd": loans_csv([("L1", "a", "open", "2026-05-01", "-3", "5", "")]),
                 "duplicate_id": loans_csv([LOANS[0], LOANS[0]]), "blank_id": loans_csv([("", "a", "open", "2026-05-01", "0", "5", "")])}
        for name, text in cases.items():
            with self.subTest(name):
                self.assert_exit_2(self.build_args(source=self.write(name + ".csv", text)))

    def test_binary_and_missing_and_directory_inputs_exit_2(self):
        self.world()
        with open(self.path("bin.csv"), "wb") as fh:
            fh.write(b"\xff\xfe\x00\x01garbage\n")
        self.assert_exit_2(self.build_args(source=self.path("bin.csv")))
        self.assert_exit_2(self.build_args(source=self.path("missing.csv")))
        self.assert_exit_2(self.build_args(source=self.tmp.name))

    def test_bad_spec_files_exit_2(self):
        self.world()
        text = json.dumps(SPEC)
        for name, body in {"empty": "", "list": "[1, 2]", "truncated": text[:60], "string": '"x"', "null": "null"}.items():
            with self.subTest(name):
                self.assert_exit_2(self.build_args(spec=self.write(name + ".json", body)))

    def test_bad_filed_and_adjustment_files_exit_2(self):
        self.world()
        self.assert_exit_2(self.build_args(filed=self.write("f1.csv", "cell_id,value\na.current,1\n")))
        self.assert_exit_2(self.build_args(filed=self.write("f2.csv", "cell_id,value\nghost,1\n")))
        self.assert_exit_2(self.build_args(filed=self.write("f3.csv", "cell_id,value\na.current,abc\n")))
        self.assert_exit_2(self.build_args(adj=self.write("a1.csv", "adj_id,cell_id,amount_cents,reason\nA1,a.current,1.5,x\n")))
        self.assert_exit_2(self.build_args(adj=self.write("a2.csv", "adj_id,cell_id,amount_cents,reason\nA1,a.current,1,x\nA1,a.late,2,y\n")))

    def test_bad_lineage_files_exit_2(self):
        self.world()
        with open(self.path("lin.json"), encoding="utf-8") as fh:
            good = json.load(fh)
        broken = {"list": [], "no_cells": {k: v for k, v in good.items() if k != "cells"}, "empty": None}
        for key, mutate in {"filed_string": lambda g: g["cells"]["a.late"].update(filed="x"),
                            "rows_not_list": lambda g: g["cells"]["a.late"].update(rows=5),
                            "bad_row": lambda g: g["cells"]["a.late"]["rows"].append([1]),
                            "rule_without_max": lambda g: g["cells"]["a.late"]["rule"].pop("max"),
                            "cycle": lambda g: g["cells"]["ROW.a"].update(inputs=["RATE.a"]),
                            "orphans_missing": lambda g: g.pop("orphans")}.items():
            g = json.loads(json.dumps(good))
            mutate(g)
            broken[key] = g
        for name, body in broken.items():
            with self.subTest(name):
                p = self.write(name + ".json", "" if body is None else json.dumps(body))
                self.assert_exit_2(["verify", "--lineage", p, "--source", self.path("now.csv")])
        self.assert_exit_2(["verify", "--lineage", self.write("trunc.json", json.dumps(good)[:80]), "--source", self.path("now.csv")])

    def test_unwritable_output_exits_2(self):
        self.world()
        self.assert_exit_2(self.build_args()[:-1] + [os.path.join(self.tmp.name, "no", "such", "dir", "o.json")])

    def test_hostile_strings_cannot_forge_annotations(self):
        evil = "L9\n::error::forged approval"
        loans = LOANS + [(evil, "a", "open", "2026-05-01", "", "5", "")]
        self.write("spec.json", json.dumps(SPEC))
        self.write("filed.csv", "cell_id,value\n" + "".join(f"{k},{v}\n" for k, v in FILED.items()))
        self.write("adj.csv", 'adj_id,cell_id,amount_cents,reason\nA1,a.current,5,"x\r\n::error::forged%0A"\n')
        self.write("then.csv", loans_csv(loans))
        changed = [r[:5] + ("21000",) + r[6:] if r[0] == "L3" else r for r in loans]
        changed[-1] = (evil, "a", "open", "2026-05-01", "", "5", "")
        self.write("now.csv", loans_csv(changed))
        self.assertEqual(run(["build", "--source", self.path("then.csv"), "--spec", self.path("spec.json"), "--filed", self.path("filed.csv"),
                              "--adjustments", self.path("adj.csv"), "--out", self.path("lin.json")])[0], 0)
        _, out, _ = self.verify("--format", "github")
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), len(out.splitlines()))
        self.assertTrue(all(ln.split("::")[1] in ("error", "warning", "notice") for ln in commands))
        self.assertFalse(any(ln.startswith("::error::forged") for ln in out.splitlines()))
        self.assertIn("%0A", out)
        _, text, _ = self.verify()
        self.assertFalse(any(ln.startswith("::") for ln in text.splitlines()))
        _, trace, _ = run(["trace", "--lineage", self.path("lin.json"), "--cell", "a.current"])
        self.assertFalse(any(ln.startswith("::") for ln in trace.splitlines()))
        self.assertIn("\\u000a", trace)

    def test_demo_runs(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("SOURCE_CHANGED", out)

    def test_no_command_prints_help_and_exits_2(self):
        self.assertEqual(run([])[0], 2)


if __name__ == "__main__":
    unittest.main()
