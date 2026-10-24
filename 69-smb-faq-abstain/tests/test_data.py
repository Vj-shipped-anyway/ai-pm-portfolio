import csv
import filecmp
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

import _bootstrap  # noqa: F401

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
FILES = ("kb.csv", "queries.csv", "drafts.csv", "truth.csv")


def rows(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def nums(text):
    # a separate, simpler reading of numbers than the one in the tool
    out = set()
    for m in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text):
        m = m.replace(",", "")
        out.add(m.rstrip("0").rstrip(".") if "." in m else m)
    return out


class DataTests(unittest.TestCase):
    def test_rerun_reproduces_every_file_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(DATA, "_generate.py"), tmp)
            subprocess.run([sys.executable, "_generate.py"], cwd=tmp, check=True)
            for name in FILES:
                self.assertTrue(filecmp.cmp(os.path.join(DATA, name), os.path.join(tmp, name), shallow=False), name)

    def test_thirty_questions_in_five_classes(self):
        q = rows("queries.csv")
        self.assertEqual(len(q), 30)
        self.assertEqual(len({r["query_id"] for r in q}), 30)
        self.assertEqual(Counter(r["q_class"] for r in q),
                         {"answerable": 14, "not_in_kb": 6, "out_of_scope": 4, "state_specific": 3, "ambiguous": 3})

    def test_every_question_has_a_draft_and_a_truth_row(self):
        ids = [r["query_id"] for r in rows("queries.csv")]
        self.assertEqual(ids, [r["query_id"] for r in rows("drafts.csv")])
        self.assertEqual(ids, [r["query_id"] for r in rows("truth.csv")])

    def test_truth_labels_follow_the_mode(self):
        t = rows("truth.csv")
        self.assertEqual(sum(1 for r in t if r["should_serve"] == "yes"), 10)
        self.assertEqual(sum(1 for r in t if r["draft_ok"] == "no"), 18)
        self.assertEqual(sum(1 for r in t if r["draft_mode"] == "decline"), 2)
        self.assertEqual(Counter(r["hard_case"] for r in t), {"": 21, "hard_negative": 6, "hard_miss": 3})

    def test_faithful_drafts_only_use_numbers_from_their_passage(self):
        kb = {r["fact_id"]: r["text"] for r in rows("kb.csv")}
        q = {r["query_id"]: r["question"] for r in rows("queries.csv")}
        d = {r["query_id"]: r["draft"] for r in rows("drafts.csv")}
        checked = 0
        for r in rows("truth.csv"):
            if r["draft_mode"] == "faithful":
                checked += 1
                self.assertLessEqual(nums(d[r["query_id"]]), nums(kb[r["fact_id"]]) | nums(q[r["query_id"]]), r["query_id"])
        self.assertEqual(checked, 9)

    def test_wrong_number_drafts_really_contain_a_number_the_passage_lacks(self):
        kb = {r["fact_id"]: r["text"] for r in rows("kb.csv")}
        d = {r["query_id"]: r["draft"] for r in rows("drafts.csv")}
        for r in rows("truth.csv"):
            if r["draft_mode"] == "wrong_number":
                self.assertFalse(nums(d[r["query_id"]]) <= nums(kb[r["fact_id"]]), r["query_id"])

    def test_wrong_slot_drafts_use_only_numbers_that_are_in_the_passage(self):
        # these are the planted misses: the number is real and answers a different question
        kb = {r["fact_id"]: r["text"] for r in rows("kb.csv")}
        d = {r["query_id"]: r["draft"] for r in rows("drafts.csv")}
        q = {r["query_id"]: r["question"] for r in rows("queries.csv")}
        for qid in ("Q05", "Q10"):
            fact = [r["fact_id"] for r in rows("truth.csv") if r["query_id"] == qid][0]
            self.assertLessEqual(nums(d[qid]), nums(kb[fact]) | nums(q[qid]))

    def test_truth_fact_ids_exist_in_the_knowledge_base(self):
        ids = {r["fact_id"] for r in rows("kb.csv")}
        for r in rows("truth.csv"):
            self.assertTrue(r["fact_id"] == "" or r["fact_id"] in ids)


if __name__ == "__main__":
    unittest.main()
