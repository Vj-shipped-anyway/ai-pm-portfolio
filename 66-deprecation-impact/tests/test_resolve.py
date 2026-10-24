import datetime
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import _world as w
import deprecation_impact as di

AS_OF = datetime.date(2026, 9, 1)


class ResolveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.models = di.load_models(w.write(cls.tmp.name, "m.csv", w.MODELS))
        cls.aliases = di.load_aliases(w.write(cls.tmp.name, "a.csv", w.ALIASES), cls.models)
        cls.idx = di._index(cls.models, cls.aliases)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def r(self, ref):
        return di.resolve(ref, self.idx, AS_OF, di.DEFAULT_POLICY)

    def test_exact_id_hits_a_retiring_model(self):
        v = self.r("m-old@1")
        self.assertEqual((v["verdict"], v["root"], v["retire"]), ("hit", "m-old@1", datetime.date(2026, 12, 1)))

    def test_exact_id_on_a_live_model_is_clear(self):
        self.assertEqual(self.r("m-new@2")["verdict"], "clear")

    def test_case_and_surrounding_spaces_do_not_hide_a_hit(self):
        self.assertEqual(self.r("  M-OLD@1 ")["verdict"], "hit")

    def test_fresh_alias_resolves_through_the_table(self):
        v = self.r("m-prod")
        self.assertEqual((v["verdict"], v["model_id"]), ("hit", "m-old@1"))
        self.assertIn("alias m-prod", v["note"])

    def test_stale_alias_in_a_family_with_a_retiring_snapshot_goes_to_check(self):
        v = self.r("m-stale")
        self.assertEqual(v["verdict"], "check")
        self.assertEqual(v["maybe"], ["m-old@1"])

    def test_stale_alias_in_a_family_with_nothing_retiring_stays_clear(self):
        self.assertEqual(self.r("lite-prod")["verdict"], "clear")

    def test_bare_family_with_a_retiring_snapshot_goes_to_check(self):
        v = self.r("m")
        self.assertEqual((v["verdict"], v["maybe"]), ("check", ["m-old@1"]))

    def test_bare_family_is_matched_by_the_family_field_not_by_prefix(self):
        # m-lite@1 starts with "m" and "m-", but its family is m-lite
        self.assertNotIn("m-lite@1", self.r("m")["maybe"])
        self.assertEqual(self.r("m-lite")["verdict"], "clear")

    def test_unknown_string_is_never_clear(self):
        v = self.r("no-such-model")
        self.assertEqual(v["verdict"], "check")
        self.assertIn("not in the models file", v["note"])

    def test_fine_tune_inherits_the_retirement_of_its_base(self):
        v = self.r("ft-a")
        self.assertEqual((v["verdict"], v["root"]), ("hit", "m-old@1"))
        self.assertIn("built on m-old@1", v["note"])

    def test_alias_may_not_shadow_a_family_name(self):
        bad = w.ALIASES + "m,m-new@2,2026-08-01\n"
        with self.assertRaises(ValueError):
            di.load_aliases(w.write(self.tmp.name, "bad.csv", bad), self.models)

    def test_alias_to_an_unknown_model_is_rejected(self):
        with self.assertRaises(ValueError):
            di.load_aliases(w.write(self.tmp.name, "bad.csv", w.ALIASES + "x,nope,2026-08-01\n"), self.models)

    def test_base_chain_that_loops_is_rejected(self):
        loop = w.MODELS + "x1,x,v,,,,1,1,1,x2\nx2,x,v,,,,1,1,1,x1\n"
        with self.assertRaises(ValueError):
            di.load_models(w.write(self.tmp.name, "loop.csv", loop))

    def test_base_model_that_is_not_in_the_file_is_rejected(self):
        with self.assertRaises(ValueError):
            di.load_models(w.write(self.tmp.name, "orphan.csv", w.MODELS + "x1,x,v,,,,1,1,1,ghost\n"))

    def test_retire_before_notice_is_rejected(self):
        with self.assertRaises(ValueError):
            di.load_models(w.write(self.tmp.name, "dates.csv", w.MODELS + "x1,x,v,2026-05-01,2026-04-01,,1,1,1,\n"))

    def test_the_tool_never_opens_the_truth_files(self):
        with open(os.path.join(os.path.dirname(di.__file__), "deprecation_impact.py"), encoding="utf-8") as fh:
            self.assertNotIn("truth", fh.read())


if __name__ == "__main__":
    unittest.main()
