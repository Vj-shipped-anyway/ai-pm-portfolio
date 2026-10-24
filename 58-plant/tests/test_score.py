import csv
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import plant


def truth_rows():
    return [{"row_id": 2, "behavior": "dup", "role": "positive"}, {"row_id": 4, "behavior": "dup", "role": "positive"},
            {"row_id": 6, "behavior": "cents", "role": "positive"}, {"row_id": 8, "behavior": "legit", "role": "negative"}]


class ScoreTests(unittest.TestCase):
    def test_perfect_flags(self):
        sc = plant.score(truth_rows(), 10, {2, 4, 6})
        self.assertEqual((sc["found"], sc["positives"], sc["recall"], sc["precision"]), (3, 3, 1.0, 1.0))
        self.assertEqual((sc["look_alikes_flagged"], sc["clean_flagged"], sc["clean"]), (0, 0, 6))

    def test_no_flags_says_so_and_scores_zero(self):
        sc = plant.score(truth_rows(), 10, set())
        self.assertEqual((sc["found"], sc["recall"], sc["precision"]), (0, 0.0, None))
        self.assertIn("no rows were flagged", "\n".join(plant.score_lines(sc)))

    def test_look_alike_and_clean_flags_are_counted_apart(self):
        sc = plant.score(truth_rows(), 10, {2, 8, 9, 10})
        self.assertEqual((sc["found"], sc["look_alikes_flagged"], sc["clean_flagged"]), (1, 1, 2))
        self.assertAlmostEqual(sc["precision"], 0.25)

    def test_per_behavior_rows_list_failures_first(self):
        sc = plant.score(truth_rows(), 10, {2, 4})
        self.assertEqual([(e["behavior"], e["planted"], e["flagged"]) for e in sc["behaviors"]], [("cents", 1, 0), ("dup", 2, 2), ("legit", 1, 0)])
        self.assertEqual(plant.weakest(sc)["behavior"], "cents")

    def test_no_planted_failures_gives_no_recall(self):
        sc = plant.score([{"row_id": 1, "behavior": "legit", "role": "negative"}], 5, {1})
        self.assertIsNone(sc["recall"])
        self.assertIsNone(plant.weakest(sc))
        self.assertEqual(plant.ratio(sc["recall"]), "n/a")


class FileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def write(self, name, text):
        with open(self.path(name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return self.path(name)

    def key(self, rows, truth_text, name="k"):
        self.write(name + "_truth.csv", truth_text)
        self.write(name + "_manifest.json", json.dumps({"name": "k", "rows": rows, "truth_sha256": plant._sha(truth_text.encode("utf-8"))}))
        return self.path(name)

    def test_flags_reader_rejects_bad_ids(self):
        for text in ("row_id\n0\n", "row_id\n11\n", "row_id\nabc\n", "row_id\n-3\n", "row_id\n1.5\n", "row_id\n٣\n", "other\n1\n", "", "row_id\n1,2,3\n"):
            with self.subTest(text=text):
                with self.assertRaises(plant.SpecError):
                    plant.read_flags(self.write("f.csv", text), 10)

    def test_flags_file_with_only_a_header_flags_nothing(self):
        self.assertEqual(plant.read_flags(self.write("f.csv", "row_id\n\n"), 10), (set(), 0))

    def test_flags_reader_counts_repeats_once(self):
        flagged, repeats = plant.read_flags(self.write("f.csv", "row_id,rule\n3,a\n3,b\n5,a\n"), 10)
        self.assertEqual((flagged, repeats), ({3, 5}, 1))

    def test_flags_reader_survives_null_bytes_and_bad_encoding(self):
        with open(self.path("n.csv"), "wb") as fh:
            fh.write(b"row_id\n1\x00\n")
        with self.assertRaises(csv.Error):
            plant.read_flags(self.path("n.csv"), 10)
        with open(self.path("e.csv"), "wb") as fh:
            fh.write(b"row_id\n\xff\xfe\n")
        with self.assertRaises(ValueError):
            plant.read_flags(self.path("e.csv"), 10)

    def test_key_reader_accepts_a_matching_pair(self):
        prefix = self.key(10, "row_id,behavior,role\n2,dup,positive\n8,legit,negative\n")
        truth, rows, manifest = plant.read_key(prefix)
        self.assertEqual((rows, [t["row_id"] for t in truth], manifest["name"]), (10, [2, 8], "k"))

    def test_key_reader_rejects_an_edited_truth_file(self):
        prefix = self.key(10, "row_id,behavior,role\n2,dup,positive\n")
        self.write("k_truth.csv", "row_id,behavior,role\n2,dup,positive\n3,dup,positive\n")
        with self.assertRaises(plant.SpecError) as ctx:
            plant.read_key(prefix)
        self.assertIn("does not match", str(ctx.exception))

    def test_key_reader_rejects_listed_twice_bad_role_and_out_of_range(self):
        for text in ("row_id,behavior,role\n2,dup,positive\n2,cents,positive\n", "row_id,behavior,role\n2,dup,maybe\n",
                     "row_id,behavior,role\n99,dup,positive\n", "row_id,behavior\n2,dup\n", "row_id,behavior,role\n2,,positive\n"):
            with self.subTest(text=text):
                with self.assertRaises(plant.SpecError):
                    plant.read_key(self.key(10, text))

    def test_key_reader_rejects_a_manifest_without_rows(self):
        blob = "row_id,behavior,role\n"
        self.write("m_truth.csv", blob)
        for manifest in ({"truth_sha256": plant._sha(blob.encode())}, [], {"rows": True, "truth_sha256": plant._sha(blob.encode())}):
            self.write("m_manifest.json", json.dumps(manifest))
            with self.assertRaises(plant.SpecError):
                plant.read_key(self.path("m"))

    def test_hostile_behavior_name_is_escaped_in_the_report(self):
        sc = plant.score([{"row_id": 1, "behavior": "x\n::error::forged", "role": "positive"}], 3, {1})
        lines = plant.score_lines(sc)
        for line in lines:
            self.assertFalse(line.startswith("::"))
        self.assertIn("x\\n::error::forged", "\n".join(lines))

    def test_clean_escapes_control_characters(self):
        self.assertEqual(plant.clean("a\r\nb\x1b[0m"), "a\\r\\nb\\x1b[0m")


if __name__ == "__main__":
    unittest.main()
