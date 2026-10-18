import csv
import importlib.util
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import _bootstrap  # noqa: F401
import support
from agentkit.data_io import load_world
from agentkit.faults import FaultInjector

DATA = support.ROOT / "data"


def load_generator():
    spec = importlib.util.spec_from_file_location("agentkit_generate", DATA / "_generate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestGenerator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen = load_generator()
        cls.w = load_world()

    def test_running_it_twice_gives_identical_files(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.gen.generate(Path(a))
            self.gen.generate(Path(b))
            names = sorted(p.name for p in Path(a).glob("*.csv"))
            self.assertEqual(len(names), 8)
            for n in names:
                self.assertEqual((Path(a) / n).read_bytes(), (Path(b) / n).read_bytes(), n)

    def test_the_shipped_csvs_are_what_the_generator_writes(self):
        with tempfile.TemporaryDirectory() as a:
            self.gen.generate(Path(a))
            for p in Path(a).glob("*.csv"):
                self.assertEqual(p.read_bytes(), (DATA / p.name).read_bytes(), p.name)

    def test_counts(self):
        self.assertEqual(len(self.w["cases"]), 600)
        self.assertEqual(len(self.w["outcomes"]), 600)
        self.assertEqual(len(self.w["truth"]), 600)
        self.assertEqual(len(self.w["watchlist"]), 60)
        self.assertEqual(len({c["case_id"] for c in self.w["cases"]}), 600)

    def test_planted_edge_cases(self):
        c = Counter(t["scenario"] for t in self.w["truth"].values())
        self.assertEqual(c["malformed"], 12)
        self.assertEqual(c["duplicate"], 14)
        self.assertEqual(c["fix_name_ambiguous"], 36)
        self.assertEqual(c["watch_exact"] + c["watch_variant"], 22)
        self.assertEqual(c["closed_successor"], 6)

    def test_duplicates_repeat_an_exception_ref_and_arrive_later(self):
        by_ref = {}
        for c in self.w["cases"]:
            by_ref.setdefault(c["exception_ref"], []).append(c)
        twice = [v for v in by_ref.values() if len(v) == 2]
        self.assertEqual(len(twice), 14)
        for first, second in twice:
            self.assertEqual((first["delivery_no"], second["delivery_no"]), (1, 2))
            self.assertGreater(second["opened_hour"], first["opened_hour"])
            self.assertEqual(self.w["outcomes"][second["case_id"]]["human_outcome"], "DUPLICATE_CLOSED")

    def test_human_outcomes_use_known_labels(self):
        self.assertEqual({o["human_outcome"] for o in self.w["outcomes"].values()},
                         {"RESUBMIT", "RETURN_TO_ORIGINATOR", "ESCALATE_COMPLIANCE", "DUPLICATE_CLOSED"})

    def test_every_resubmit_outcome_names_a_field_and_a_value(self):
        for o in self.w["outcomes"].values():
            if o["human_outcome"] == "RESUBMIT":
                self.assertTrue(o["corrected_field"] and o["corrected_value"], o["case_id"])

    def test_cases_arrive_in_time_order(self):
        hours = [c["opened_hour"] for c in self.w["cases"]]
        self.assertEqual(hours, sorted(hours))
        self.assertTrue(0 <= hours[0] and hours[-1] < 720)

    def test_fault_schedule_points_at_real_cases_and_parses(self):
        ids = {c["case_id"] for c in self.w["cases"]}
        rows = self.w["faults"]
        self.assertEqual(len(rows), 24)
        self.assertTrue(all(r["case_id"] in ids for r in rows))
        self.assertEqual(FaultInjector(rows).counts(), {"timeout": 11, "malformed_output": 6, "rogue_call": 4,
                                                        "duplicate_delivery": 3})

    def test_some_accounts_start_with_zero(self):
        zero = [p for p in self.w["payments"].values() if p["beneficiary_account"].startswith("0")]
        self.assertGreater(len(zero), 20)

    def test_brief_estimate_equals_the_recorded_minutes(self):
        hours = round(sum(o["touch_minutes"] for o in self.w["outcomes"].values()) / 60, 1)
        self.assertEqual(support.brief()["estimate"]["hours_at_stake_modeled"], hours)

    def test_the_brief_shadow_count_matches_the_data(self):
        self.assertEqual(support.brief()["test_plan"]["shadow_mode_cases"], len(self.w["cases"]))

    def test_no_real_looking_identifiers(self):
        for p in list(self.w["payments"].values())[:50]:
            self.assertTrue(p["payment_id"].startswith("P-"))
            self.assertTrue(p["beneficiary_bank_code"] in ("",) or p["beneficiary_bank_code"].startswith("SYNB"))


if __name__ == "__main__":
    unittest.main()
