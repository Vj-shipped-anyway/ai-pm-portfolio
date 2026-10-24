import unittest

import _bootstrap  # noqa: F401
import common
from credit_policy_needle import normalize


class ReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probes = common.load_sweep()
        cls.manuals = common.load_manuals()
        cls.answers = {n: common.run_reader(n, cls.probes, cls.manuals) for n in common.READERS}

    def right(self, reader, p):
        return normalize(self.answers[reader][p["probe_id"]]) == normalize(p["expected_answer"])

    def test_the_sweep_has_the_shape_the_readme_states(self):
        self.assertEqual(len(self.probes), 210)
        self.assertEqual({p["form"] for p in self.probes},
                         {"plain", "inline", "adjacent", "crossref", "restated", "register", "nested"})
        self.assertEqual(sorted({p["length_pages"] for p in self.probes}), [50, 150, 300])
        self.assertEqual(sorted({p["depth_pct"] for p in self.probes}), [0, 25, 50, 75, 100])

    def test_control_answers_every_question(self):
        self.assertEqual(sum(self.right("control", p) for p in self.probes), 210)

    def test_each_fault_fails_exactly_where_it_was_written_to(self):
        for reader in common.READERS:
            wrong = {p["probe_id"] for p in self.probes if not self.right(reader, p)}
            predicted = {p["probe_id"] for p in self.probes if common.oracle_fails(reader, p)}
            self.assertEqual(wrong, predicted, reader)

    def test_base_only_gives_the_rule_value_where_an_exception_applies(self):
        p = next(p for p in self.probes if p["form"] == "inline" and p["variant"] == "applies")
        self.assertEqual(self.answers["base_only"][p["probe_id"]], p["trap_answer"])

    def test_retrieval_misses_a_far_exception_and_finds_a_near_one(self):
        far = next(p for p in self.probes if p["form"] == "crossref" and p["variant"] == "applies")
        near = next(p for p in self.probes if p["form"] == "adjacent" and p["variant"] == "applies")
        self.assertEqual(self.answers["retrieval"][far["probe_id"]], far["trap_answer"])
        self.assertTrue(self.right("retrieval", near))

    def test_the_far_clause_that_cancels_an_exception_changes_the_control_answer(self):
        carved = next(p for p in self.probes if p["variant"] == "carved_out")
        self.assertEqual(self.answers["control"][carved["probe_id"]], carved["expected_answer"])
        self.assertEqual(self.answers["retrieval"][carved["probe_id"]], carved["trap_answer"])

    def test_hostile_and_malformed_questions_get_an_empty_answer(self):
        doc = next(iter(self.manuals.values()))
        for q in ("", "What is the (((( for ???", "What is the x for y for an applicant with ?", "\n::error::" * 50,
                  "What is the " + "a" * 5000 + " for " + "b" * 5000 + "?"):
            for fn in common.READER_FUNCS.values():
                self.assertEqual(fn(doc, q), "")

    def test_a_product_that_is_not_in_the_manual_gets_an_empty_answer(self):
        doc = next(iter(self.manuals.values()))
        q = "What is the maximum loan term for Nonesuch Personal Loan?"
        self.assertEqual([fn(doc, q) for fn in common.READER_FUNCS.values()], [""] * 4)


if __name__ == "__main__":
    unittest.main()
