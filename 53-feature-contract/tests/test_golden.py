"""Pin the numbers the README prints, so a change to the checker or the data that moves them fails here first."""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401
import feature_contract as fc

SRC = _bootstrap.SRC
DATA = os.path.join(SRC, "..", "data")


def step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout.splitlines()


class GoldenTests(unittest.TestCase):
    def assertLines(self, lines, expected):
        for e in expected:
            self.assertIn(e, lines)

    def test_step_01(self):
        self.assertLines(step("step_01_no_check.py"), [
            "  deliveries: 90 batches of 100 rows from 3 feeds",
            "  planted truth: 47 with a changed field the model should not see, 43 harmless (15 unchanged)",
            "  batches the pipeline stops: 0 of 90",
            "  rows with a changed value in those batches: 3323 of 4700"])

    def test_step_02(self):
        self.assertLines(step("step_02_header_and_type.py"), [
            "  bad batches stopped: 16 of 47",
            "  harmless batches blocked: 14 of 43",
            "  share of blocks that are harmless: 46.7%",
            "  harmless blocked by planted change: column_reorder 5, extra_column 5, int_as_decimal 4",
            "  bad batches that pass: 31 of 47"])

    def test_step_03(self):
        lines = step("step_03_deficiencies_exposed.py")
        self.assertLines(lines, [
            "    bad batches stopped: 22 of 47",
            "    harmless batches blocked: 5 of 43 (isolated_bad_rows 5)",
            "    bad batches stopped: 21 of 47",
            "  bad batches that pass both layers: 10 of 47",
            "  by planted change: null_zero_fill 3, unit_cents 2, unit_in_range 5"])
        self.assertEqual(sum(1 for ln in lines if ln == "    bad batches stopped: 16 of 47"), 2)

    def test_step_04_summary(self):
        lines = step("step_04_with_contract.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["bad_stopped"], s["bad"]), (37, 47))
        self.assertEqual((s["harmless_blocked"], s["harmless_warned"], s["harmless"]), (0, 5, 43))
        self.assertEqual((s["correct"], s["batches"]), (80, 90))
        self.assertEqual((s["to_read"], s["step2_blocked"]), (42, 30))
        self.assertEqual(s["missed"], 10)
        self.assertIn("  bad batches that still pass: 10 of 47 (null_zero_fill, unit_cents, unit_in_range)", lines)
        self.assertIn("    unit_cents             FAIL 2, PASS 2", lines)
        self.assertEqual(sum(1 for ln in lines if ln.startswith("    BATCH-")), 10)

    def test_the_unchanged_batches_never_raise_an_alarm(self):
        step("step_04_with_contract.py")
        with open(os.path.join(SRC, "out", "step_04_decisions.csv"), newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if r["change_kind"] == "unchanged"]
        self.assertEqual(len(rows), 15)
        self.assertEqual({r["decision"] for r in rows}, {"PASS"})


class DataTests(unittest.TestCase):
    def test_generator_reproduces_every_file_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(DATA, "_generate.py"), tmp)
            r = subprocess.run([sys.executable, "_generate.py"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            for name in sorted(os.listdir(tmp)):
                if name == "_generate.py":
                    continue
                with open(os.path.join(tmp, name), "rb") as a, open(os.path.join(DATA, name), "rb") as b:
                    self.assertEqual(a.read(), b.read(), name)

    def test_a_csv_round_trip_gives_the_same_findings_as_the_in_memory_batch(self):
        with open(os.path.join(DATA, "batches.jsonl"), encoding="utf-8") as fh:
            batches = [json.loads(ln) for ln in fh][::9]
        with tempfile.TemporaryDirectory() as tmp:
            for b in batches:
                path = os.path.join(tmp, b["batch_id"] + ".csv")
                with open(path, "w", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    w.writerow(b["columns"])
                    w.writerows(b["rows"])
                columns, rows, typed = fc.read_batch(path)
                self.assertFalse(typed)
                self.assertEqual((columns, rows), (b["columns"], b["rows"]))
        self.assertEqual(len(batches), 10)

    def test_every_contract_in_data_is_valid(self):
        names = [n for n in sorted(os.listdir(DATA)) if n.startswith("contract_")]
        self.assertEqual(len(names), 3)
        for n in names:
            fc.load_contract(os.path.join(DATA, n))

    def test_truth_labels_cover_every_batch_once(self):
        with open(os.path.join(DATA, "batch_truth.csv"), newline="", encoding="utf-8") as fh:
            truth = list(csv.DictReader(fh))
        with open(os.path.join(DATA, "batches.jsonl"), encoding="utf-8") as fh:
            ids = [json.loads(ln)["batch_id"] for ln in fh]
        self.assertEqual([t["batch_id"] for t in truth], ids)
        self.assertEqual(sum(1 for t in truth if t["truth_class"] == "bad"), 47)


if __name__ == "__main__":
    unittest.main()
