"""Pin the numbers the README prints, so a change to the checks that moves them fails here first."""
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

import _bootstrap  # noqa: F401
from common import load_packets, owners_in_file
from kyb_packet_check import check_packet

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(ROOT, "data")


def run_step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenSteps(unittest.TestCase):
    def assertLines(self, out, lines):
        have = [ln.strip() for ln in out.splitlines()]
        for ln in lines:
            self.assertIn(ln, have)

    def test_step_01(self):
        self.assertLines(run_step("step_01_no_check.py"), [
            "packets: 75   planted misreads: 43   clean: 32",
            "packets the current process stops: 0 of 75",
            "packets whose file would list the wrong people: 20 of 75"])

    def test_step_02(self):
        self.assertLines(run_step("step_02_field_validation.py"), [
            "packets flagged: 12 of 75", "misreads flagged: 12 of 43", "clean packets flagged: 0 of 32",
            "packets that would list the wrong people, flagged: 2 of 20", "misreads that pass as well-formed: 31 of 43"])

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        self.assertLines(out, [
            "misreads flagged: 30 of 43", "misreads flagged: 19 of 43",
            "packets that would list the wrong people, flagged: 14 of 20", "packets that would list the wrong people, flagged: 9 of 20",
            "misreads caught only by A: 21, only by B: 10, by both: 9, by neither: 3",
            "sum check at tolerance 0.0: clean packets flagged 4 of 32 (clean_rounding 4)",
            "sum check at tolerance 0.1: clean packets flagged 0 of 32",
            "misreads that pass both A and B: 3 of 43"])
        self.assertIn("swapped percents still add up to 100, so the sum cannot see them; A flags 4 of 6 through a missing details record: person_record_missing 4", out)

    def test_step_04(self):
        out = run_step("step_04_with_check.py")
        self.assertLines(out, ["misreads flagged: 40 of 43", "clean packets flagged: 0 of 32",
                               "packets that would list the wrong people, flagged: 17 of 20",
                               "packets sent to a person: 40 of 75 (the step 2 shape check flagged 12)",
                               "misreads that still pass: 3 of 43"])
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["misreads_flagged"], s["misreads"]), (40, 43))
        self.assertEqual((s["clean_flagged"], s["clean"]), (0, 32))
        self.assertEqual((s["wrong_people_flagged"], s["wrong_people"]), (17, 20))
        self.assertEqual((s["sent_to_person"], s["packets"], s["missed"]), (40, 75, 3))

    def test_the_known_miss_is_the_three_nominee_notes(self):
        packets = load_packets()
        passing = sorted(p["scenario"] for p in packets if p["defect"] and not check_packet(p["source"], p["raw"]))
        self.assertEqual(passing, ["nominee_note"] * 3)


class GeneratedData(unittest.TestCase):
    def test_scenario_counts(self):
        counts = Counter(p["scenario"] for p in load_packets())
        self.assertEqual(sum(counts.values()), 75)
        self.assertEqual(sum(v for k, v in counts.items() if k.startswith("clean_")), 32)
        self.assertEqual(counts["pct_swapped"], 6)
        self.assertEqual(counts["nominee_note"], 3)

    def test_clean_packets_list_the_true_people(self):
        # the generator and the checker compute the 25 percent rule separately; on clean packets they must agree
        for p in load_packets():
            if not p["defect"]:
                self.assertEqual(owners_in_file(p["raw"]), p["true_owners"], p["packet_id"])

    def test_every_clean_packet_passes_and_every_hard_negative_is_present(self):
        packets = load_packets()
        for p in packets:
            if not p["defect"]:
                self.assertEqual(check_packet(p["source"], p["raw"]), [], p["packet_id"])
        text = " ".join(p["source"] for p in packets if p["scenario"] == "clean_rounding")
        self.assertIn("33.33%", text)
        self.assertIn("16.67%", text)
        holders = [h["pct"] for p in packets if not p["defect"] for h in p["raw"]["holders"]]
        self.assertIn(25, holders)       # exactly on the threshold
        self.assertIn(24, holders)       # just under it

    def test_generator_reproduces_every_file_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "data")
            os.makedirs(work)
            shutil.copy(os.path.join(DATA, "_generate.py"), work)
            r = subprocess.run([sys.executable, "_generate.py"], cwd=work, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            for name in ("packets.csv", "extractions.csv", "truth.csv", "example_source.txt", "example_extracted.json"):
                self.assertTrue(filecmp.cmp(os.path.join(DATA, name), os.path.join(work, name), shallow=False), name)


if __name__ == "__main__":
    unittest.main()
