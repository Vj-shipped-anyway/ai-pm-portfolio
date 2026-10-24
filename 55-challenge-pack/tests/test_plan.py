"""The tier table, the date arithmetic and the reconciliation rules, one rule at a time."""
from __future__ import annotations

import csv
import datetime as dt
import os
import unittest

import _bootstrap  # noqa: F401
from challenge_pack import (ITEM_BY_ID, ITEMS, TIERS, add_months, assess, clean, csv_safe, effective_tier, gh_escape,
                            md_cell, plan_items)

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
D = dt.date
AS_OF = D(2026, 10, 1)


def form(**o):
    base = {"use_case_id": "T-1", "title": "Staff lookup", "model_type": "ml", "vendor_model": "none",
            "customer_facing": "no", "decision_autonomy": "advisory", "data_class": "internal",
            "regulatory_scope": "none", "financial_exposure_band": "lt_1m", "developer_unit": "Cards",
            "deployed_version": "1.0", "declared_tier": 1}
    base.update(o)
    return base


def row(item, date=D(2026, 9, 1), reaffirmed=None, unit="Model Risk Management", version="1.0"):
    return {"use_case_id": "T-1", "item_id": item, "ref": "DOC-1", "prepared_by_unit": unit, "covers_version": version,
            "evidence_date": date, "reaffirmed_date": reaffirmed}


def rows_for(f, **override):
    tier = effective_tier(f)[0]
    out = {it["id"]: row(it["id"], unit=f["developer_unit"] if not it["independent"] else "Model Risk Management")
           for it in plan_items(f["model_type"], f["vendor_model"], tier)}
    out.update(override)
    return out


class MonthTests(unittest.TestCase):
    def test_add_months(self):
        self.assertEqual(add_months(D(2024, 2, 29), -12), D(2023, 2, 28))
        self.assertEqual(add_months(D(2026, 10, 31), -1), D(2026, 9, 30))
        self.assertEqual(add_months(D(2026, 1, 31), 1), D(2026, 2, 28))
        self.assertEqual(add_months(D(2026, 10, 1), -12), D(2025, 10, 1))
        self.assertEqual(add_months(D(2026, 1, 15), -2), D(2025, 11, 15))
        self.assertEqual(add_months(D(2026, 10, 1), -36), D(2023, 10, 1))


class TableTests(unittest.TestCase):
    def test_core_items_by_tier(self):
        sizes = [len([i for i in ITEMS if i["overlay"] == "" and i["min_tier"] <= t]) for t in (1, 2, 3, 4)]
        self.assertEqual(sizes, [3, 6, 10, 13])

    def test_ids_are_unique_and_windows_fall_as_tier_rises(self):
        self.assertEqual(len(ITEM_BY_ID), len(ITEMS))
        w = [TIERS[t]["window_months"] for t in (1, 2, 3, 4)]
        self.assertEqual(w, sorted(w, reverse=True))

    def test_the_data_files_equal_the_table(self):
        with open(os.path.join(DATA, "plan_items.csv"), newline="", encoding="utf-8") as fh:
            got = [(r["item_id"], int(r["min_tier"]), r["independent"] == "1", r["overlay"]) for r in csv.DictReader(fh)]
        self.assertEqual(got, [(i["id"], i["min_tier"], i["independent"], i["overlay"]) for i in ITEMS])
        with open(os.path.join(DATA, "plan_tiers.csv"), newline="", encoding="utf-8") as fh:
            tiers = {int(r["tier"]): (r["depth"], int(r["window_months"])) for r in csv.DictReader(fh)}
        self.assertEqual(tiers, {t: (v["depth"], v["window_months"]) for t, v in TIERS.items()})

    def test_overlays(self):
        ids = lambda mt, v, t: [i["id"] for i in plan_items(mt, v, t)]  # noqa: E731
        self.assertNotIn("V01", ids("ml", "none", 4))
        self.assertIn("V01", ids("ml", "self_hosted", 1))
        self.assertNotIn("V02", ids("ml", "vendor_api", 1))
        self.assertIn("V02", ids("ml", "vendor_api", 2))
        for mt in ("rules", "generative", "agentic"):
            self.assertIn("G01", ids(mt, "none", 1))
        for mt in ("statistical", "ml"):
            self.assertNotIn("G01", ids(mt, "none", 4))

    def test_tier_is_the_higher_of_declared_and_recomputed(self):
        hot = form(decision_autonomy="automated", data_class="restricted", regulatory_scope="fair_lending", declared_tier=1)
        self.assertEqual(effective_tier(hot)[0], 3)
        self.assertEqual(effective_tier(form(declared_tier=3))[0], 3)


class AssessTests(unittest.TestCase):
    def kinds(self, f, rows):
        return {g["item"]["id"]: g["problems"] for g in assess(f, rows, AS_OF)["gaps"]}

    def test_complete_pack_has_no_gap(self):
        f = form()
        self.assertEqual(self.kinds(f, rows_for(f)), {})

    def test_missing(self):
        f = form()
        r = rows_for(f)
        del r["CH02"]
        self.assertEqual(self.kinds(f, r), {"CH02": ["missing"]})

    def test_window_edge_is_fine_and_one_day_older_is_stale(self):
        f = form()  # tier 1, window 36 months, cutoff 2023-10-01
        self.assertEqual(self.kinds(f, rows_for(f, CH01=row("CH01", D(2023, 10, 1), unit="Cards"))), {})
        self.assertEqual(self.kinds(f, rows_for(f, CH01=row("CH01", D(2023, 9, 30), unit="Cards"))), {"CH01": ["stale"]})

    def test_reaffirmation_inside_the_window_rescues_old_evidence(self):
        f = form()
        old = row("CH01", D(2020, 1, 1), reaffirmed=D(2026, 3, 1), unit="Cards")
        self.assertEqual(self.kinds(f, rows_for(f, CH01=old)), {})
        old_both = row("CH01", D(2020, 1, 1), reaffirmed=D(2023, 1, 1), unit="Cards")
        self.assertEqual(self.kinds(f, rows_for(f, CH01=old_both)), {"CH01": ["stale"]})

    def test_wrong_version_is_not_rescued_by_a_reaffirmation(self):
        f = form()
        bad = row("CH01", D(2020, 1, 1), reaffirmed=D(2026, 3, 1), unit="Cards", version="0.9")
        self.assertEqual(self.kinds(f, rows_for(f, CH01=bad)), {"CH01": ["wrong_version"]})

    def test_independence_only_where_the_item_requires_it(self):
        f = form(declared_tier=3)
        same = row("CH07", unit="  cards ")  # CH07 needs an outside preparer; case and spaces do not hide the unit
        self.assertEqual(self.kinds(f, rows_for(f, CH07=same)), {"CH07": ["not_independent"]})
        first_line = row("CH09", unit="Cards")  # CH09 is owned by the first line
        self.assertEqual(self.kinds(f, rows_for(f, CH09=first_line)), {})

    def test_several_problems_come_out_in_a_fixed_order(self):
        f = form(declared_tier=3)
        bad = row("CH08", D(2020, 1, 1), unit="Cards", version="0.9")
        self.assertEqual(self.kinds(f, rows_for(f, CH08=bad)), {"CH08": ["wrong_version", "not_independent", "stale"]})

    def test_evidence_for_items_not_in_the_plan_is_listed_not_flagged(self):
        f = form()
        r = rows_for(f, CH11=row("CH11", D(2000, 1, 1), version="0.1"))
        out = assess(f, r, AS_OF)
        self.assertEqual(out["gaps"], [])
        self.assertEqual(out["on_file_not_requested"], ["CH11"])

    def test_a_raised_tier_shortens_the_window(self):
        f = form(decision_autonomy="automated", data_class="restricted", regulatory_scope="fair_lending", declared_tier=1)
        out = assess(f, rows_for(f, CH01=row("CH01", D(2025, 6, 1), unit="Cards")), AS_OF)
        self.assertEqual((out["tier"], out["window"], out["raised"]), (3, 12, True))
        self.assertEqual([g["item"]["id"] for g in out["gaps"]], ["CH01"])


class TextSafetyTests(unittest.TestCase):
    def test_clean_removes_control_characters_and_cuts(self):
        self.assertEqual(clean("a\r\nb\x1b[31mc"), "a b [31mc")
        self.assertEqual(len(clean("x" * 500, 80)), 80)

    def test_gh_escape(self):
        self.assertEqual(gh_escape("50%\r\n::error::x"), "50%25%0D%0A::error::x")

    def test_csv_safe(self):
        self.assertEqual(csv_safe("=1+1"), "'=1+1")
        self.assertEqual(csv_safe("plain"), "plain")

    def test_md_cell(self):
        s = md_cell("a | b\n# c <script>[x](y)`z`")
        for ch in ("\n", "<", ">"):
            self.assertNotIn(ch, s)
        self.assertNotIn(" | ", s)
        self.assertIn("\\|", s)


if __name__ == "__main__":
    unittest.main()
