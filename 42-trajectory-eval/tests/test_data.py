import csv
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

import _bootstrap  # noqa: F401
import trajectory_eval as te

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
PROFILES = {"faithful": 80, "reorder_independent": 18, "alt_tool": 14, "harmless_reads": 14, "retry_after_error": 12, "unlisted_alias": 6,
            "skipped_check": 16, "wrong_order": 14, "forbidden_action": 14, "ignored_guard": 12, "loop": 10, "wrong_entity": 12,
            "wrong_outcome": 12, "note_leak": 6}


def rows(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class DataTests(unittest.TestCase):
    def test_twenty_valid_tasks_and_240_runs(self):
        tasks = te.load_tasks(os.path.join(DATA, "tasks.json"))
        runs = te.load_runs(os.path.join(DATA, "runs.csv"))
        self.assertEqual((len(tasks), len(runs)), (20, 240))
        self.assertTrue(all(r["task_id"] in tasks for r in runs))
        self.assertEqual(set(tasks), {r["task_id"] for r in runs})

    def test_planted_mix_is_the_documented_one(self):
        truth = rows("runs_truth.csv")
        self.assertEqual(dict(Counter(r["profile"] for r in truth)), PROFILES)
        self.assertEqual(Counter(r["truth_class"] for r in truth), {"pass": 144, "fail": 96})

    def test_example_files_load(self):
        self.assertEqual(len(te.load_tasks(os.path.join(DATA, "example_task.json"))), 1)
        self.assertEqual(len(te.load_runs(os.path.join(DATA, "example_runs.csv"))), 3)

    def test_generator_reproduces_every_file_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "data")
            shutil.copytree(DATA, work)
            subprocess.run([sys.executable, "_generate.py"], cwd=work, check=True, capture_output=True)
            for name in ("tasks.json", "runs.csv", "runs_truth.csv", "example_task.json", "example_runs.csv"):
                self.assertTrue(filecmp.cmp(os.path.join(DATA, name), os.path.join(work, name), shallow=False), name)


if __name__ == "__main__":
    unittest.main()
