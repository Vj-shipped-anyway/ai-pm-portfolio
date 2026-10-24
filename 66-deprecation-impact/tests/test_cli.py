import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import _world as w


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = self.tmp.name

    def argv(self, usages, **kw):
        return w.build(self.d, usages, **kw)

    def assert_input_error(self, argv):
        code, out, err = w.run(argv)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertTrue(err.startswith("input error: "), err)
        return err

    # exit codes
    def test_late_exits_1_and_never_exits_0(self):
        a = self.argv(w.usage_line(1, "F1", "fallback", "dead@1"))
        self.assertEqual(w.run(a)[0], 1)
        self.assertEqual(w.run(a + ["--fail-on", "never"])[0], 0)

    def test_tight_threshold(self):
        room = self.argv(w.usage_line(1, "F1", "primary", "m-old@1"))   # 91 days left, 60 needed: 31 to spare
        self.assertEqual((w.run(room)[0], w.run(room + ["--fail-on", "tight"])[0]), (0, 0))
        tight = self.argv(w.usage_line(1, "F1", "judge", "m-old@1"))    # a judge needs 74 days: 17 to spare
        self.assertEqual((w.run(tight)[0], w.run(tight + ["--fail-on", "tight"])[0]), (0, 1))
        policy = w.write(self.d, "p.json", json.dumps({"tight_margin_days": 10}))
        self.assertEqual(w.run(tight + ["--fail-on", "tight", "--policy", policy])[0], 0)

    def test_json_output_parses(self):
        code, out, _ = w.run(self.argv(w.usage_line(1, "F1", "primary", "m-old@1")) + ["--format", "json"])
        res = json.loads(out)
        self.assertEqual((code, res["as_of"], res["hits"]), (0, w.AS_OF, 1))

    def test_demo_runs_and_names_the_decision(self):
        code, out, _ = w.run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: LATE", out)

    # silent no-op
    def test_nothing_retiring_says_so(self):
        code, out, _ = w.run(self.argv(w.usage_line(1, "F1", "primary", "m-new@2") + w.usage_line(2, "F2", "primary", "m-new@2")
                                       + w.usage_line(3, "F3", "primary", "m-new@2")))
        self.assertEqual(code, 0)
        self.assertIn("no usage resolves to a model with a retirement notice", out)
        self.assertIn("decision: CLEAR", out)

    def test_model_filter_with_no_notice_exits_2(self):
        err = self.assert_input_error(self.argv("") + ["--model", "m-new@2"])
        self.assertIn("no retirement notice", err)

    # malformed input exits 2 with one line and no traceback
    def test_missing_files_exit_2(self):
        a = self.argv("")
        a[a.index("--models") + 1] = os.path.join(self.d, "nope.csv")
        self.assert_input_error(a)

    def test_empty_files_exit_2(self):
        for name, key in (("features", "--features"), ("usages", "--usages"), ("models", "--models"), ("aliases", "--aliases")):
            a = self.argv("")
            w.write(self.d, f"{name}.csv", "")
            self.assertIn("empty", self.assert_input_error(a), name)

    def test_wrong_type_of_file_exits_2(self):
        a = self.argv("")
        w.write(self.d, "models.csv", json.dumps({"models": []}))
        self.assertIn("missing column", self.assert_input_error(a))
        w.write(self.d, "models.csv", "\x00\x01 not a csv\n")
        self.assert_input_error(a)

    def test_binary_file_exits_2(self):
        a = self.argv("")
        with open(os.path.join(self.d, "models.csv"), "wb") as fh:
            fh.write(b"\xff\xfe\x00\x80")
        self.assert_input_error(a)

    def test_truncated_file_exits_2(self):
        full = w.USAGE_HEAD + w.usage_line(1, "F1", "primary", "m-old@1")
        a = self.argv(w.usage_line(1, "F1", "primary", "m-old@1"))
        w.write(self.d, "usages.csv", full[:-12])
        self.assertIn("columns", self.assert_input_error(a))

    def test_bad_values_exit_2(self):
        bad_usages = {
            "date": (None, w.MODELS.replace("2026-12-01", "01/12/2026")),
            "number": (w.usage_line(1, "F1", "primary", "m-old@1", calls="many"), None),
            "negative": (w.usage_line(1, "F1", "primary", "m-old@1", calls=-5), None),
            "role": (w.usage_line(1, "F1", "backup", "m-old@1"), None),
            "orphan": (w.usage_line(1, "F9", "primary", "m-old@1"), None),
            "duplicate": (w.usage_line(1, "F1", "primary", "m-old@1") + w.usage_line(1, "F2", "primary", "m-old@1"), None),
        }
        for label, (usages, models) in bad_usages.items():
            a = self.argv(usages or "", **({"models": models} if models else {}))
            with self.subTest(label):
                self.assert_input_error(a)

    def test_bad_feature_fields_exit_2(self):
        for bad in (w.FEATURES.replace("critical", "urgent"), w.FEATURES.replace(",yes,", ",maybe,", 1), w.FEATURES + "F1,dup,t,x,low,yes,\n"):
            self.assert_input_error(self.argv("", features=bad))

    def test_bad_as_of_and_bad_policy_exit_2(self):
        a = self.argv("")
        a[-1] = "tomorrow"
        self.assertIn("--as-of", self.assert_input_error(a))
        a = self.argv("")
        for text in ("[1, 2]", "{not json", json.dumps({"lead_days": {"urgent": 5}}), json.dumps({"surprise": 1}),
                     json.dumps({"lead_days": {"critical": "soon"}}), json.dumps({"tight_margin_days": -1})):
            with self.subTest(text):
                self.assert_input_error(a + ["--policy", w.write(self.d, "p.json", text)])

    # hostile strings
    def test_hostile_text_cannot_forge_a_line_or_move_the_cursor(self):
        evil = "x\n::error title=forged::approved\x1b[2J"
        feats = w.FEATURES.replace("alpha", "alpha" + evil.replace("\n", " ")).replace("beta", "beta forged")
        a = self.argv(w.usage_line(1, "F1", "primary", "m-old@1") + w.usage_line(2, "F2", "primary", '"' + evil + '"')
                      + w.usage_line(3, "F3", "primary", "m-old@1"), features=feats)
        code, out, _ = w.run(a)
        self.assertEqual(code, 0)
        self.assertNotIn("\x1b", out)
        self.assertNotIn(" ", out)
        self.assertFalse([ln for ln in out.splitlines() if ln.startswith("::")])
        self.assertIn("\\x1b", out)
        self.assertIn("\\x0a", out)

    def test_hostile_text_in_an_error_message_stays_on_one_line(self):
        err = self.assert_input_error(self.argv("", models=w.MODELS + "x1,x,v,2026\n::error::forged\x1b[0m,,,1,1,1,\n"))
        self.assertNotIn("\x1b", err)

    def test_the_hostile_name_does_not_change_the_json_structure(self):
        a = self.argv(w.usage_line(1, "F1", "primary", '"quote\n}, {"hits": 99'))
        code, out, _ = w.run(a + ["--format", "json"])
        self.assertEqual(json.loads(out)["hits"], 0)


if __name__ == "__main__":
    unittest.main()
