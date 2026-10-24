"""Checks on the shipped data: shape, labels, and the blind spot the README admits to."""
import csv
import json
import os
import unittest
from collections import Counter

import _bootstrap  # noqa: F401
import injection_pack as ip

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = ip.load_pack(os.path.join(DATA, "pack.csv"))
        cls.pop = ip.load_pack(os.path.join(DATA, "population.csv"))

    def test_sizes(self):
        self.assertEqual(Counter(c["expected"] for c in self.pack), {"block": 100, "allow": 60})
        self.assertEqual(Counter(c["expected"] for c in self.pop), {"block": 1000, "allow": 500})

    def test_every_channel_is_exercised_by_the_pack(self):
        self.assertEqual(set(c["channel"] for c in self.pack), set(ip.CHANNELS))

    def test_retrieved_documents_are_the_largest_attack_group(self):
        counts = Counter(c["channel"] for c in self.pack if c["expected"] == "block")
        self.assertEqual(counts.most_common(1)[0][0], "retrieved_doc")

    def test_a_technique_has_one_label(self):
        for cases in (self.pack, self.pop):
            labels = {}
            for c in cases:
                labels.setdefault(c["technique"], set()).add(c["expected"])
            self.assertTrue(all(len(v) == 1 for v in labels.values()))

    def test_the_pack_does_not_contain_the_encoded_payload_technique_the_population_does(self):
        self.assertNotIn("doc_encoded_blob", {c["technique"] for c in self.pack})
        self.assertIn("doc_encoded_blob", {c["technique"] for c in self.pop})

    def test_ids_do_not_collide_between_pack_and_population(self):
        self.assertFalse({c["case_id"] for c in self.pack} & {c["case_id"] for c in self.pop})

    def test_tool_call_texts_are_json(self):
        for c in self.pack + self.pop:
            if c["channel"] == "tool_call":
                self.assertIsInstance(json.loads(c["text"]), dict)

    def test_session_cases_carry_explicit_owner_fields(self):
        for c in self.pack:
            if c["channel"] == "session":
                self.assertTrue(c["session_id"])
        owners = [c for c in self.pack if c["technique"] == "session_cross_read"]
        self.assertTrue(all(c["memory_owner"] and c["memory_owner"] != c["session_id"] for c in owners))

    def test_rule_prs_are_valid_rule_files(self):
        with open(os.path.join(DATA, "rule_prs.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 51)
        for r in rows:
            ip.check_rules(json.loads(r["new_rules_json"]), r["pr_id"])

    def test_the_base_rules_file_is_valid(self):
        ip.load_rules(os.path.join(DATA, "gateway_rules.json"))
        ip.load_rules(os.path.join(DATA, "example_rules_new.json"))


if __name__ == "__main__":
    unittest.main()
