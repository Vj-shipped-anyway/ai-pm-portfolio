import os
import unittest

import _bootstrap  # noqa: F401
import name_match_eval as nme

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


class NormalizeTests(unittest.TestCase):
    def test_case_accents_punctuation(self):
        self.assertEqual(nme.normalize("  Álvaro   O'Brien-Smith, "), "alvaro obrien smith")

    def test_special_letters(self):
        self.assertEqual(nme.normalize("Straße"), "strasse")
        self.assertEqual(nme.normalize("Bjørn"), "bjorn")

    def test_non_latin_kept_letter_by_letter(self):
        self.assertEqual(nme.normalize("Иван"), "иван")
        self.assertEqual(nme.ExactMatcher().score("Иван", "иван"), 1.0)

    def test_nothing_left(self):
        self.assertEqual(nme.normalize("--, .. !"), "")
        with self.assertRaises(nme.InputError):
            nme.check_name("--, ..", "x")

    def test_too_long_name_is_refused_not_scored(self):
        with self.assertRaises(nme.InputError):
            nme.check_name("a" * (nme.MAX_NAME_CHARS + 1), "x")


class FoldAndEditTests(unittest.TestCase):
    def test_fold_pairs(self):
        self.assertEqual(nme.fold("hassan"), nme.fold("hasan"))
        self.assertEqual(nme.fold("khalid"), nme.fold("halid"))
        self.assertEqual(nme.fold("philip"), nme.fold("filip"))
        self.assertNotEqual(nme.fold("sasha"), nme.fold("chacha"))

    def test_edit_distance(self):
        self.assertEqual(nme.edit_distance("kitten", "sitting"), 3)
        self.assertEqual(nme.edit_distance("abc", "abc"), 0)
        self.assertEqual(nme.edit_distance("", "abc"), 3)
        self.assertEqual(nme.edit_distance("flaw", "lawn"), nme.edit_distance("lawn", "flaw"))

    def test_word_similarity(self):
        self.assertEqual(nme.word_similarity("h", "hasan"), nme.INITIAL_CREDIT)
        self.assertEqual(nme.word_similarity("k", "hasan"), 0.0)
        self.assertEqual(nme.word_similarity("abcdef", "uvwxyz"), 0.0)
        self.assertEqual(nme.word_similarity("hasan", "hassan"), 1.0)


class MatcherTests(unittest.TestCase):
    def test_exact_is_order_sensitive(self):
        m = nme.ExactMatcher()
        self.assertEqual(m.score("Hasan  KARIMOV", "hasan karimov"), 1.0)
        self.assertEqual(m.score("Karimov, Hasan", "Hasan Karimov"), 0.0)

    def test_tokens_ignore_order_edit_does_not(self):
        t, e = nme.TokenMatcher([], rarity=False), nme.EditMatcher()
        self.assertEqual(t.score("Karimov, Hasan", "Hasan Karimov"), 1.0)
        self.assertLess(e.score("Karimov, Hasan", "Hasan Karimov"), 0.5)

    def test_initial_gets_partial_credit_only_for_its_own_letter(self):
        t = nme.TokenMatcher([], rarity=False)
        ok, wrong = t.score("H. Karimov", "Hasan Karimov"), t.score("K. Karimov", "Hasan Karimov")
        self.assertTrue(0.7 < ok < 1.0)
        self.assertLess(wrong, ok)

    def test_scores_are_symmetric_and_in_range(self):
        names = ["Hasan Ali Karimov", "Karimov, Hassan", "H. Karimov", "Nadia Hadani", "Al Tavari Omar", "x"]
        for kind in nme.MATCHERS:
            m = nme.make_matcher(kind, names)
            for a in names:
                for b in names:
                    s = m.score(a, b)
                    self.assertTrue(0.0 <= s <= 1.0, (kind, a, b, s))
                    self.assertEqual(s, m.score(b, a), (kind, a, b))

    def test_identical_names_score_one(self):
        for kind in nme.MATCHERS:
            self.assertEqual(nme.make_matcher(kind, ["Hasan Karimov"]).score("Hasan Karimov", "HASAN KARIMOV"), 1.0)

    def test_rarity_lowers_a_shared_common_word(self):
        listed = ["Hasan Marov", "Tomas Marov", "Nadia Marov", "Omar Marov", "Lena Marov", "Viktor Zandri"]
        flat, weighted = nme.TokenMatcher(listed, rarity=False), nme.TokenMatcher(listed)
        self.assertLess(weighted.score("Yusuf Marov", "Hasan Marov"), flat.score("Yusuf Marov", "Hasan Marov"))

    def test_unknown_matcher_name(self):
        with self.assertRaises(ValueError):
            nme.make_matcher("nope", [])

    def test_escape_log(self):
        s = nme.escape_log("a%b\r\nc\x00d")
        self.assertEqual(s, "a%25b%0D%0Ac%00d")
        self.assertTrue(nme.escape_log("x" * 500).endswith("..."))

    def test_known_matches_on_the_planted_set(self):
        entries, customers, truth = nme.load_all(*(os.path.join(DATA, f) for f in ("watchlist.csv", "customers.csv", "truth.csv")))
        names = [e["name"] for e in entries]
        rec = nme.evaluate(nme.make_matcher("tokens", names), entries, customers, truth)
        by = nme.by_kind_at(rec, 0.80)
        self.assertEqual(by["order_swap"], (24, 24))
        self.assertEqual(by["alias_unlisted"][0], 0)


if __name__ == "__main__":
    unittest.main()
