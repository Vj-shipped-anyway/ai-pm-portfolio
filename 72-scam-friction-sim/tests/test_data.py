from __future__ import annotations

import contextlib
import csv
import importlib.util
import io
import os
import tempfile
import unittest
from collections import Counter

import _bootstrap  # noqa: F401
import scam_friction_sim as sim

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def load_generator():
    spec = importlib.util.spec_from_file_location("gen72", os.path.join(DATA, "_generate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class DataTests(unittest.TestCase):
    def test_rerun_is_byte_for_byte_identical(self):
        gen = load_generator()
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                gen.main(tmp)
            for name in ("payments.csv", "truth.csv", "assumptions.json"):
                with open(os.path.join(tmp, name), "rb") as a, open(os.path.join(DATA, name), "rb") as b:
                    self.assertEqual(a.read(), b.read(), name)

    def test_planted_counts(self):
        with open(os.path.join(DATA, "truth.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 12000)
        counts = Counter(r["scenario"] for r in rows)
        self.assertEqual(counts, Counter({"ordinary": 10820, "big_first_time": 330, "night_new_device": 170, "on_call": 350,
                                          "coached_live": 120, "romance_invest": 90, "takeover": 60, "known_payee": 60}))
        self.assertEqual(sum(1 for r in rows if r["is_scam"] == "1"), 330)

    def test_label_flag_agrees_with_the_scenario_table(self):
        gen = load_generator()
        table = {name: flag for name, flag, _ in gen.SCENARIOS}
        with open(os.path.join(DATA, "truth.csv"), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                self.assertEqual(int(r["is_scam"]), table[r["scenario"]])

    def test_hard_cases_exist_in_the_data(self):
        rows = sim.load_payments(os.path.join(DATA, "payments.csv"), os.path.join(DATA, "truth.csv"))
        scores = {}
        for p in rows:
            scores.setdefault(p["scenario"], []).append(sim.risk_score(p))
        self.assertLessEqual(max(scores["known_payee"]), 3)
        self.assertGreaterEqual(sum(1 for s in scores["big_first_time"] if s >= 6), 100)
        self.assertGreaterEqual(sum(1 for s in scores["on_call"] if s >= 5), 50)

    def test_every_file_loads_through_the_tool(self):
        rows = sim.load_payments(os.path.join(DATA, "payments.csv"), os.path.join(DATA, "truth.csv"))
        self.assertEqual(len(rows), 12000)


if __name__ == "__main__":
    unittest.main()
