"""Pin the numbers the README prints, and check that the data files reproduce and agree with the module."""
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401
import common

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(ROOT, "data")


class GoldenTests(unittest.TestCase):
    def test_step_04_summary(self):
        r = subprocess.run([sys.executable, "step_04_chain_and_anchor.py"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["events"], s["anchor_seq"], s["planted"]), (280, 200, 101))
        self.assertEqual((s["tampered"], s["benign"]), (91, 10))
        self.assertEqual(s["flagged"], {"none": 0, "records": 18, "chain": 48, "anchored": 76})
        self.assertEqual(s["false_alarms"], {"none": 0, "records": 0, "chain": 0, "anchored": 0})
        self.assertEqual((s["anchored_region"], s["open_tail"]), ([64, 64], [12, 27]))

    def test_the_known_misses_are_printed(self):
        r = subprocess.run([sys.executable, "step_04_chain_and_anchor.py"], cwd=SRC, capture_output=True, text=True)
        self.assertIn("KNOWN LIMIT, passes the check: 15 of 91, all in the open tail", r.stdout)
        r = subprocess.run([sys.executable, "step_03_deficiencies_exposed.py"], cwd=SRC, capture_output=True, text=True)
        self.assertIn("KNOWN LIMIT: forged appends flagged 0 of 6; legitimate appends accepted 6 of 6", r.stdout)

    def test_the_generator_reproduces_every_data_file_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(DATA, "_generate.py"), tmp)
            r = subprocess.run([sys.executable, "_generate.py"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            for name in sorted(os.listdir(DATA)):
                if name.endswith((".csv", ".json", ".jsonl")):
                    self.assertTrue(filecmp.cmp(os.path.join(DATA, name), os.path.join(tmp, name), shallow=False), name)

    def test_the_audit_module_writes_the_same_bytes_as_the_generators_own_writer(self):
        events = common.build_log()
        with open(os.path.join(DATA, "example_log.jsonl"), encoding="utf-8") as fh:
            sample = fh.read().splitlines()
        self.assertEqual(sample, [common.dumps_event(e) for e in events[:len(sample)]])

    def test_the_sample_files_give_the_three_verdicts_the_readme_shows(self):
        r = subprocess.run([sys.executable, "audit_chain.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("line 8 (seq 8): hash does not match the event content", r.stdout)
        self.assertIn("only 20 readable events, but the anchor was taken at event 24", r.stdout)


if __name__ == "__main__":
    unittest.main()
