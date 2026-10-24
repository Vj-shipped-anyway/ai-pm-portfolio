import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import credit_policy_needle as cpn


def probe(i, form="inline", length=50, depth=0, expected="48%"):
    return {"probe_id": "p%d" % i, "form": form, "length_pages": length, "depth_pct": depth, "expected_answer": expected}


class ScoreTests(unittest.TestCase):
    def test_normalize_ignores_case_dollar_comma_percent_word_and_final_stop(self):
        self.assertEqual(cpn.normalize(" $25,000. "), cpn.normalize("25000"))
        self.assertEqual(cpn.normalize("48 percent"), cpn.normalize("48%"))
        self.assertEqual(cpn.normalize("72 Months"), cpn.normalize("72 months"))

    def test_all_correct_passes(self):
        ps = [probe(i) for i in range(4)]
        res = cpn.score_probes(ps, {p["probe_id"]: "48%" for p in ps})
        self.assertEqual(cpn.gate(res), ("PASS", []))
        self.assertEqual(res["flagged"], [])

    def test_one_miss_in_a_two_question_cell_flags_the_cell(self):
        ps = [probe(1), probe(2)]
        res = cpn.score_probes(ps, {"p1": "48%", "p2": "43%"})
        self.assertEqual(res["flagged"], [("inline", 50, 0)])
        decision, reasons = cpn.gate(res)
        self.assertEqual(decision, "FAIL")
        self.assertTrue(any("overall pass 50.0%" in r for r in reasons))

    def test_gate_threshold_is_inclusive(self):
        ps = [probe(i) for i in range(50)]
        answers = {p["probe_id"]: "48%" for p in ps}
        answers["p0"] = "wrong"
        res = cpn.score_probes(ps, answers)       # 49 of 50 is exactly 98.0%
        self.assertEqual(cpn.gate(res)[0], "PASS")

    def test_missing_answer_counts_as_a_miss_and_is_reported(self):
        ps = [probe(1), probe(2)]
        res = cpn.score_probes(ps, {"p1": "48%"})
        self.assertEqual((res["passed"], res["answered"], res["total"]), (1, 1, 2))
        self.assertIn("not answered: 1", cpn.render_score(res, *cpn.gate(res))[0])

    def test_answers_for_unknown_probes_are_counted_not_fatal(self):
        res = cpn.score_probes([probe(1)], {"p1": "48%", "zzz": "1"})
        self.assertEqual(res["unknown_answers"], 1)

    def test_answers_that_match_no_probe_is_an_error_not_a_pass(self):
        with self.assertRaises(cpn.InputError) as cm:
            cpn.score_probes([probe(1)], {"other": "48%"})
        self.assertIn("none of the 1 probe ids", str(cm.exception))

    def test_a_weak_depth_band_fails_the_gate_even_when_overall_is_high(self):
        ps = [probe(i, depth=0) for i in range(60)] + [probe(100 + i, depth=100) for i in range(10)]
        answers = {p["probe_id"]: "48%" for p in ps}
        for i in range(100, 105):
            answers["p%d" % i] = "no"
        res = cpn.score_probes(ps, answers)
        decision, reasons = cpn.gate(res)
        self.assertEqual(decision, "FAIL")
        self.assertTrue(any(r.startswith("depth 100%") for r in reasons))


class LoadTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return p

    def test_missing_column(self):
        with self.assertRaises(cpn.InputError) as cm:
            cpn.load_probes(self.write("p.csv", "probe_id,form\na,inline\n"))
        self.assertIn("missing column", str(cm.exception))

    def test_header_only_and_empty_files(self):
        with self.assertRaises(cpn.InputError):
            cpn.load_probes(self.write("h.csv", "probe_id,form,length_pages,depth_pct,expected_answer\n"))
        with self.assertRaises(cpn.InputError):
            cpn.load_probes(self.write("e.csv", ""))

    def test_non_numeric_depth(self):
        text = "probe_id,form,length_pages,depth_pct,expected_answer\na,inline,50,deep,48%\n"
        with self.assertRaises(cpn.InputError) as cm:
            cpn.load_probes(self.write("p.csv", text))
        self.assertIn("depth_pct", str(cm.exception))

    def test_truncated_row(self):
        text = "probe_id,form,length_pages,depth_pct,expected_answer\na,inline,50\n"
        with self.assertRaises(cpn.InputError) as cm:
            cpn.load_probes(self.write("p.csv", text))
        self.assertIn("line 2", str(cm.exception))

    def test_repeated_ids(self):
        text = "probe_id,form,length_pages,depth_pct,expected_answer\na,inline,50,0,1\na,inline,50,0,2\n"
        with self.assertRaises(cpn.InputError):
            cpn.load_probes(self.write("p.csv", text))
        with self.assertRaises(cpn.InputError):
            cpn.load_answers(self.write("a.csv", "probe_id,answer\na,1\na,2\n"))

    def test_binary_file(self):
        p = os.path.join(self.dir.name, "b.csv")
        with open(p, "wb") as fh:
            fh.write(b"\xff\xfe\x00\x81\x82")
        with self.assertRaises(cpn.InputError) as cm:
            cpn.load_probes(p)
        self.assertIn("not UTF-8", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
