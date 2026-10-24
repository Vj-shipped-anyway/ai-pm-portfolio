import csv
import importlib.util
import io
import json
import os
import unittest
from collections import Counter

import _bootstrap  # noqa: F401
import payment_repair as pr

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def load_generator():
    spec = importlib.util.spec_from_file_location("gen36", os.path.join(DATA, "_generate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen = load_generator()
        cls.built = cls.gen.build()

    def test_generator_is_deterministic(self):
        self.assertEqual(self.built, self.gen.build())

    def test_committed_files_equal_what_the_generator_writes(self):
        for name, text in self.built.items():
            with open(os.path.join(DATA, name), encoding="utf-8", newline="") as fh:
                self.assertEqual(fh.read(), text, name)

    def test_a_different_seed_gives_different_data(self):
        self.assertNotEqual(self.built["messages.json"], self.gen.build(seed=37)["messages.json"])

    def test_messages_are_flat_string_maps_with_unique_ids(self):
        msgs = json.loads(self.built["messages.json"])
        self.assertEqual(len(msgs), sum(r[1] for r in self.gen.RECIPES))
        self.assertEqual(len({m[pr.MSG_ID] for m in msgs}), len(msgs))
        pr.check_messages(msgs)

    def test_every_recipe_appears_with_its_planted_count(self):
        rows = [ln.split(",") for ln in self.built["message_truth.csv"].splitlines()[1:]]
        got = Counter(r[1] for r in rows)
        self.assertEqual(got, Counter({name: n for name, n, _, _ in self.gen.RECIPES}))

    def test_the_answer_key_matches_the_damage(self):
        msgs = {m[pr.MSG_ID]: m for m in json.loads(self.built["messages.json"])}
        for r in csv.DictReader(io.StringIO(self.built["defects_truth.csv"])):
            value = msgs[r["msg_id"]].get(r["path"])
            self.assertNotEqual(value, r["true_value"], r)       # the field really was damaged
            if r["kind"] == "missing":
                self.assertIsNone(value)
            if r["kind"] == "blank":
                self.assertEqual(value.strip(), "")

    def test_undamaged_messages_are_complete_under_the_tools_definition(self):
        # undamaged messages must be complete under the tool's own definition of complete
        damaged = {r["msg_id"] for r in csv.DictReader(io.StringIO(self.built["defects_truth.csv"]))}
        for m in json.loads(self.built["messages.json"]):
            if m[pr.MSG_ID] not in damaged:
                self.assertEqual(pr.find_defects(m), {}, m[pr.MSG_ID])

    def test_synthetic_ibans_are_not_valid_ibans(self):
        # the two check digits are arbitrary, so a generated number is almost never a valid IBAN
        def mod97(iban):
            digits = "".join(str(int(ch, 36)) for ch in iban[4:] + iban[:4])
            return int(digits) % 97
        msgs = json.loads(self.built["messages.json"])
        ibans = {m.get(p) for m in msgs for p in (pr.DBTR_IBAN, pr.CDTR_IBAN) if len(m.get(p) or "") > 4}
        valid = sum(1 for i in ibans if mod97(i) == 1)
        self.assertLess(valid, len(ibans) * 0.05)

    def test_example_messages_are_in_the_message_set(self):
        ids = {m[pr.MSG_ID] for m in json.loads(self.built["messages.json"])}
        ex = json.loads(self.built["example_messages.json"])
        self.assertEqual(len(ex), 3)
        self.assertTrue({m[pr.MSG_ID] for m in ex} <= ids)


if __name__ == "__main__":
    unittest.main()
