"""Pin the numbers the README prints, so a change to a rule, a parameter or the data that moves them fails here first."""
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(ROOT, "data")


def run_script(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_script("step_01_two_ledgers_unmatched.py")
        for line in ("bank lines: 383   book lines: 438   lines to read side by side: 821",
                     "answer key: 337 true matches (16 of them one bank line against several book lines), 46 bank-only lines, 65 book-only lines",
                     "USD totals differ by 139980.34",
                     "= 139980.34"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = run_script("step_02_amount_and_date_lookup.py")
        for line in ("matches posted: 316 of 383 bank lines", "correct against the answer key: 291; wrong: 25", "true matches found: 291 of 337",
                     "0 of 316", "35 (16 wrong, 19 right", "posted across two currencies: 5", "bank lines left unmatched: 67; book lines left unmatched: 122"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = run_script("step_03_deficiencies_exposed.py")
        for line in ("wrong matches posted: 25 (currency_clash 5, lookalike_conflict 10, near_ref_distinct 6, twin_payments 4)",
                     "true matches it cannot make, by planted kind: batch 12, fee_netted 20, out_of_window 6, split_no_batch 4, twin_payments 4",
                     "matches posted: 319; wrong: 6 (near_ref_distinct 6)",
                     "must see: 101, posted with nobody looking; 6 of them wrong",
                     "bank lines parked because two book lines fit equally well: 6",
                     "true matches found: 313 of 337",
                     "KNOWN LIMIT: 18 true matches have no proposal and are not parked (no_ref_abbrev 4, out_of_window 6, ref_garbled 4, split_no_batch 4)",
                     "BK-000029 = GL-000007 + GL-000008 + GL-000009"):
            self.assertIn(line, out)

    def test_step_04(self):
        out = run_script("step_04_with_gate.py")
        for line in ("proposals: 319; allowed to post on their own: 218; need a person: 101",
                     "posted on their own: 218; wrong: 0",
                     "posted on approval: 93 (the scripted approver approved 93 and rejected 8); wrong: 6 (near_ref_distinct 6)",
                     "of the 8 rejections by the scripted approver, right matches: 8",
                     "posted where the policy needs an approval and none is on record: 0",
                     "true matches posted: 305 of 337",
                     "open lines: 169 (ambiguous_candidates 18, currency_differs 10, no_counterpart 89, possible_duplicate 8, reference_conflict 28, rejected_by_reviewer 16)",
                     "lines a person has to look at: 385 of 821 (step 1: 821)",
                     "self-approval by the agent (three spellings): 101 of 101 refused, 0 posted",
                     "approval for a proposal that no longer exists (key altered): 101 of 101 refused, 0 posted",
                     "one approve and one reject for the same proposal: 10 of 10 left pending, 0 posted",
                     "posted matches that re-check against the ledgers: 311 of 311 (0 problems)",
                     "one book line swapped for another: 299 of 299 caught",
                     "an approved match relabelled as posted on its own: 93 of 93 caught",
                     "a posted match copied under a second id: 311 of 311 caught",
                     "sent to a person as undecidable: 6 bank lines (twin_payments)",
                     "the scripted approver approved all 21 ref_near proposals, and 6 of them are distinct invoices"):
            self.assertIn(line, out)
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["posted_auto"], s["posted_approved"], s["rejected"], s["wrong_auto"], s["wrong_approved"]), (218, 93, 8, 0, 6))
        self.assertEqual((s["to_read"], s["lines"], s["unseen"], s["check_problems"]), (385, 821, 0, 0))

    def test_demo_example_output(self):
        r = subprocess.run([sys.executable, "recon_agent.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("recon-agent: 11 bank lines, 15 book lines", r.stdout)
        self.assertIn("posted 5 (3 on their own, 2 on approval); waiting 2; rejected 1; blocked by the check 0; approvals refused 2", r.stdout)

    def test_the_generator_reproduces_every_data_file_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(DATA, "_generate.py"), tmp)
            r = subprocess.run([sys.executable, "_generate.py"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            names = sorted(f for f in os.listdir(DATA) if f.endswith(".csv"))
            self.assertEqual(len(names), 6)
            for name in names:
                self.assertTrue(filecmp.cmp(os.path.join(DATA, name), os.path.join(tmp, name), shallow=False), name)

    def test_the_answer_key_covers_every_line_exactly_once(self):
        import common
        a_rows, b_rows = common.load_data()
        truth = common.load_truth()
        self.assertEqual({k[1] for k in truth["kind_of"] if k[0] == "A"}, {r["id"] for r in a_rows})
        self.assertEqual({k[1] for k in truth["kind_of"] if k[0] == "B"}, {r["id"] for r in b_rows})
        self.assertEqual(sum(len(k["a"]) for k in truth["links"]), len(a_rows))
        self.assertEqual(sum(len(k["b"]) for k in truth["links"]), len(b_rows))


if __name__ == "__main__":
    unittest.main()
