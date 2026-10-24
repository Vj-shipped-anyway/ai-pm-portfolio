import copy
import csv
import io
import json
import os
import unittest

import _bootstrap  # noqa: F401
import common
import plant

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def parse(blob):
    return list(csv.DictReader(io.StringIO(blob.decode("utf-8"))))


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = common.demo_spec()
        cls.res = plant.build(cls.spec)

    def test_same_seed_same_bytes_and_other_seed_other_bytes(self):
        again = plant.build(copy.deepcopy(self.spec))
        self.assertEqual(again["data_bytes"], self.res["data_bytes"])
        self.assertEqual(again["truth_bytes"], self.res["truth_bytes"])
        self.assertEqual(again["manifest_bytes"], self.res["manifest_bytes"])
        self.assertNotEqual(plant.build(dict(self.spec, seed=59))["data_bytes"], self.res["data_bytes"])

    def test_committed_files_are_what_the_generator_writes(self):
        for suffix, key in (("_data.csv", "data_bytes"), ("_truth.csv", "truth_bytes"), ("_manifest.json", "manifest_bytes")):
            with open(os.path.join(DATA, "demo" + suffix), "rb") as fh:
                self.assertEqual(fh.read(), self.res[key], suffix)

    def test_random_stream_is_pinned(self):
        # a change in the seed derivation or the generator would move every number in the README
        self.assertEqual(plant.derive(58, "base"), 4507964479714409689)
        self.assertEqual(plant.Rand(plant.derive(58, "base")).unit(), 0.28065505820277237)

    def test_data_file_carries_no_label(self):
        header = parse(self.res["data_bytes"])[0].keys()
        self.assertEqual(list(header), ["row_id"] + [c["name"] for c in self.spec["columns"]])

    def test_key_counts_match_the_spec_and_rows_are_disjoint(self):
        for b in self.spec["behaviors"]:
            self.assertEqual(sum(1 for t in self.res["truth"] if t["behavior"] == b["id"]), b["count"])
        ids = [t["row_id"] for t in self.res["truth"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, sorted(ids))

    def test_row_ids_are_contiguous(self):
        self.assertEqual([r["row_id"] for r in self.res["rows"]], list(range(1, len(self.res["rows"]) + 1)))
        self.assertEqual(self.res["manifest"]["rows"], 600 + 24 + 20)

    def test_duplicates_sit_right_after_their_source(self):
        rows = {r["row_id"]: r for r in self.res["rows"]}
        dups = [t for t in self.res["truth"] if t["behavior"] == "duplicate_posting"]
        self.assertEqual(len(dups), 24)
        for t in dups:
            self.assertEqual(t["source_row_id"], t["row_id"] - 1)
            a, b = dict(rows[t["row_id"]]), dict(rows[t["source_row_id"]])
            a.pop("row_id"), b.pop("row_id")
            self.assertEqual(a, b)

    def test_look_alike_copies_differ_only_in_the_reference(self):
        rows = {r["row_id"]: r for r in self.res["rows"]}
        for t in (t for t in self.res["truth"] if t["behavior"] == "repeat_purchase_new_ref"):
            a, b = rows[t["row_id"]], rows[t["source_row_id"]]
            self.assertEqual(a["ref"], b["ref"] + "b")
            self.assertEqual({k: v for k, v in a.items() if k not in ("row_id", "ref")}, {k: v for k, v in b.items() if k not in ("row_id", "ref")})

    def test_every_planted_failure_really_is_one(self):
        rows = {r["row_id"]: r for r in self.res["rows"]}
        for t in self.res["truth"]:
            r = rows[t["row_id"]]
            if t["behavior"] == "posted_before_purchase":
                self.assertLess(int(r["posted_day"]), int(r["day"]))
            if t["behavior"] == "amount_in_cents":
                self.assertGreaterEqual(float(r["amount"]), 200.0)
        clean_backdated = [r for r in self.res["rows"] if r["row_id"] not in {t["row_id"] for t in self.res["truth"]} and int(r["posted_day"]) < int(r["day"])]
        self.assertEqual(clean_backdated, [])

    def test_adding_a_behavior_at_the_end_moves_nothing_else(self):
        spec = copy.deepcopy(self.spec)
        spec["behaviors"].append({"id": "late_day", "role": "positive", "count": 9, "ops": [{"op": "shift", "column": "day", "delta": 30}]})
        more = plant.build(spec)
        old = [t for t in self.res["truth"]]
        kept = [t for t in more["truth"] if t["behavior"] != "late_day"]
        self.assertEqual(kept, old)
        changed = [a["row_id"] for a, b in zip(self.res["rows"], more["rows"]) if a != b]
        self.assertEqual(sorted(changed), sorted(t["row_id"] for t in more["truth"] if t["behavior"] == "late_day"))

    def test_manifest_matches_the_files_and_counts_distinct_effects(self):
        m = self.res["manifest"]
        self.assertEqual(m["data_sha256"], plant._sha(self.res["data_bytes"]))
        self.assertEqual(m["truth_sha256"], plant._sha(self.res["truth_bytes"]))
        by_id = {b["id"]: b for b in m["behaviors"]}
        self.assertEqual(by_id["memo_injection_paraphrase"]["distinct_effects"], 3)
        self.assertEqual(by_id["amount_in_cents"]["distinct_effects"], 1)
        self.assertEqual(json.loads(self.res["manifest_bytes"])["seed"], 58)

    def test_hostile_text_round_trips_through_csv_as_one_row_each(self):
        hostile = ['x\n::error title=forged::approved', 'a,"b",c', 'line1\r\nline2', '%0A::warning::y']
        spec = {"name": "host", "seed": 3, "rows": 40, "columns": [{"name": "memo", "kind": "choice", "values": hostile}],
                "behaviors": [{"id": "marker", "role": "positive", "count": 3, "ops": [{"op": "append", "column": "memo", "text": "\n::error::tail"}]}]}
        res = plant.build(spec)
        rows = parse(res["data_bytes"])
        self.assertEqual(len(rows), 40)
        self.assertTrue(all(r["memo"].split("\n::error::tail")[0] in hostile for r in rows))
        self.assertEqual(sum(r["memo"].endswith("\n::error::tail") for r in rows), 3)
        truth = parse(res["truth_bytes"])
        self.assertEqual(len(truth), 3)
        self.assertTrue(all("\n" not in t["effect"] and "\n" not in t["detail"] for t in truth))


if __name__ == "__main__":
    unittest.main()
