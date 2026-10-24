import contextlib
import copy
import csv
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import payment_mandate_check as pmc
from test_rules import MANDATE

COLS = list(pmc.INSTRUCTION_COLUMNS) + ["payee_name", "memo"]


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = pmc.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


def line(n, **kw):
    r = {"submission_id": f"S-{n}", "instruction_id": f"I-{n}", "mandate_id": "M1", "agent_id": "AG-1", "received_at": "2026-05-12T09:00:00Z",
         "payee_id": "P1", "payee_account_ref": "AC-1", "amount": "100.00", "currency": "USD", "rail": "ach", "category": "utilities",
         "payee_name": "Alpha Power", "memo": "bill"}
    r.update(kw)
    return r


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def mandates(self, obj=None, name="m.json"):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            json.dump([MANDATE] if obj is None else obj, fh)
        return self.path(name)

    def instructions(self, rows, name="i.csv"):
        with open(self.path(name), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        return self.path(name)

    def raw(self, text, name):
        with open(self.path(name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return self.path(name)

    def test_release_exits_0_and_reject_exits_1(self):
        m = self.mandates()
        code, out, _ = run(["check", m, self.instructions([line(1)])])
        self.assertEqual(code, 0)
        self.assertIn("1 instructions: 1 RELEASE, 0 HOLD, 0 REJECT", out)
        code, out, _ = run(["check", m, self.instructions([line(1, payee_id="P9")])])
        self.assertEqual(code, 1)
        self.assertIn("PAYEE_NOT_LISTED", out)

    def test_fail_on_levels(self):
        m = self.mandates()
        held = self.instructions([line(1, amount="400.00")])
        self.assertEqual(run(["check", m, held])[0], 0)
        self.assertEqual(run(["check", m, held, "--fail-on", "hold"])[0], 1)
        rejected = self.instructions([line(1, amount="900.00")])
        self.assertEqual(run(["check", m, rejected, "--fail-on", "never"])[0], 0)

    def test_show_all_lists_released_instructions(self):
        m, i = self.mandates(), self.instructions([line(1)])
        self.assertNotIn("inside the mandate", run(["check", m, i])[1])
        self.assertIn("inside the mandate", run(["check", m, i, "--show", "all"])[1])

    def test_demo(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("4 RELEASE, 1 HOLD, 2 REJECT", out)
        self.assertIn("audit: 7 records, chain ok", out)

    def test_no_arguments_prints_help_and_exits_2(self):
        self.assertEqual(run([])[0], 2)

    def test_missing_files_and_directories_exit_2(self):
        m, i = self.mandates(), self.instructions([line(1)])
        self.assertEqual(run(["check", "nope.json", i])[0], 2)
        self.assertEqual(run(["check", m, "nope.csv"])[0], 2)
        self.assertEqual(run(["check", self.dir.name, i])[0], 2)
        self.assertEqual(run(["check", m, self.dir.name])[0], 2)

    def test_malformed_mandate_files_exit_2_with_one_stderr_line(self):
        i = self.instructions([line(1)])
        cases = {"empty.json": "", "truncated.json": '[{"mandate_id": "M1", "currency": "US', "object.json": "{}", "list.json": "[]",
                 "number.json": "5", "nested.json": "[" * 100000, "nan.json": '[{"per_payment_limit": NaN}]'}
        for name, text in cases.items():
            code, out, err = run(["check", self.raw(text, name), i])
            self.assertEqual(code, 2, name)
            self.assertEqual(out, "", name)
            self.assertEqual(len(err.strip().splitlines()), 1, name)
            self.assertTrue(err.startswith("input error:"), name)
        binary = self.path("bin.json")
        with open(binary, "wb") as fh:
            fh.write(b"\xff\xfe\x00\x01")
        self.assertEqual(run(["check", binary, i])[0], 2)

    def test_malformed_instruction_files_exit_2_with_one_stderr_line(self):
        m = self.mandates()
        head = ",".join(COLS) + "\n"
        good = ",".join(["S-1", "I-1", "M1", "AG-1", "2026-05-12T09:00:00Z", "P1", "AC-1", "100.00", "USD", "ach", "utilities", "n", "m"])
        cases = {"empty.csv": "", "header_only.csv": head, "json.csv": '[{"a": 1}]', "truncated.csv": head + good[:30],
                 "short_row.csv": head + "S-1,I-1,M1\n", "long_row.csv": head + good + ",extra\n", "nul.csv": head + good.replace("m", "\x00") + "\n",
                 "no_columns.csv": "a,b\n1,2\n", "bad_time.csv": head + good.replace("2026-05-12T09:00:00Z", "yesterday") + "\n",
                 "bad_date.csv": head + good.replace("2026-05-12", "2026-02-30") + "\n", "dup_submission.csv": head + good + "\n" + good + "\n",
                 "blank_submission.csv": head + good.replace("S-1", "", 1) + "\n"}
        for name, text in cases.items():
            code, out, err = run(["check", m, self.raw(text, name)])
            self.assertEqual(code, 2, name)
            self.assertEqual(out, "", name)
            self.assertEqual(len(err.strip().splitlines()), 1, name)
        binary = self.path("bin.csv")
        with open(binary, "wb") as fh:
            fh.write(b"\xff\xfe\x00\x01")
        self.assertEqual(run(["check", m, binary])[0], 2)

    def test_unwritable_audit_path_exits_2(self):
        m, i = self.mandates(), self.instructions([line(1)])
        self.assertEqual(run(["check", m, i, "--audit", os.path.join(self.dir.name, "no", "such", "dir.jsonl")])[0], 2)

    def test_hostile_strings_cannot_forge_output_lines(self):
        hostile = "x\n::error::approved\r\nRELEASE   \x1b[31m"
        m = self.mandates()
        i = self.instructions([line(1, instruction_id=hostile, payee_id=hostile, mandate_id=hostile, agent_id=hostile, memo=hostile,
                                    payee_name=hostile, category=hostile)])
        code, out, err = run(["check", m, i, "--show", "all"])
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertEqual(len(lines), 4)          # the instruction, the count, the note about the mandate id, the audit line
        self.assertFalse(any(ln.startswith("::") for ln in lines))
        for bad in ("\x1b", " ", "\r"):
            self.assertNotIn(bad, out)
        self.assertIn("\\n::error::", lines[0])

    def test_hostile_text_in_an_error_message_stays_on_one_line(self):
        m = self.mandates()
        i = self.instructions([line(1, received_at="2026\n::error::forged")])
        code, out, err = run(["check", m, i])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertNotIn("\n::error::", err)

    def test_input_that_matches_no_mandate_says_so(self):
        m = self.mandates()
        i = self.instructions([line(1, mandate_id="X"), line(2, mandate_id="Y")])
        code, out, _ = run(["check", m, i])
        self.assertEqual(code, 1)
        self.assertIn("note: no instruction names a mandate in the mandate file", out)

    def test_bom_and_crlf_are_accepted(self):
        m = self.mandates()
        text = "﻿" + ",".join(COLS) + "\r\n" + ",".join(line(1)[c] for c in COLS) + "\r\n"
        self.assertEqual(run(["check", m, self.raw(text, "bom.csv")])[0], 0)

    def test_optional_columns_may_be_absent(self):
        m = self.mandates()
        text = ",".join(pmc.INSTRUCTION_COLUMNS) + "\n" + ",".join(line(1)[c] for c in pmc.INSTRUCTION_COLUMNS) + "\n"
        self.assertEqual(run(["check", m, self.raw(text, "lean.csv")])[0], 0)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        rows = [line(1), line(2, payee_id="P9"), line(3, amount="400.00"), line(4, received_at="2026-05-12T09:05:00Z")]
        self.results = pmc.check_batch(pmc.parse_mandates([MANDATE]), rows)
        self.records = pmc.audit_records(self.results)

    def write(self, records, name="a.jsonl"):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
        return p

    def test_a_fresh_chain_verifies(self):
        self.assertTrue(pmc.verify_audit(self.records)[0])
        self.assertEqual(len(self.records), 4)
        self.assertEqual(self.records[0]["prev"], pmc.GENESIS)

    def test_record_holds_decision_reasons_and_input_digest(self):
        r = self.records[1]
        self.assertEqual((r["decision"], r["reasons"], r["rule_set"]), ("REJECT", ["PAYEE_NOT_LISTED"], "pmc-1"))
        self.assertEqual(len(r["input_sha256"]), 64)

    def test_editing_a_decision_breaks_the_chain_at_that_record(self):
        bad = copy.deepcopy(self.records)
        bad[1]["decision"] = "RELEASE"
        ok, msg = pmc.verify_audit(bad)
        self.assertFalse(ok)
        self.assertIn("record 2", msg)

    def test_removing_or_reordering_records_is_found(self):
        self.assertFalse(pmc.verify_audit(self.records[:1] + self.records[2:])[0])
        self.assertFalse(pmc.verify_audit([self.records[1], self.records[0]] + self.records[2:])[0])
        self.assertFalse(pmc.verify_audit(self.records[:2] + [self.records[2], self.records[2]])[0])

    def test_recomputing_one_hash_still_breaks_the_next_link(self):
        bad = copy.deepcopy(self.records)
        bad[1]["decision"] = "RELEASE"
        core = {k: v for k, v in bad[1].items() if k != "hash"}
        bad[1]["hash"] = pmc._chain_hash(bad[1]["prev"], core)
        ok, msg = pmc.verify_audit(bad)
        self.assertFalse(ok)
        self.assertIn("record 3", msg)

    def test_cutting_the_tail_needs_the_recorded_head_to_be_found(self):
        self.assertTrue(pmc.verify_audit(self.records[:-1])[0])
        self.assertFalse(pmc.verify_audit(self.records[:-1], head=self.records[-1]["hash"])[0])
        self.assertTrue(pmc.verify_audit(self.records, head=self.records[-1]["hash"])[0])

    def test_check_writes_a_file_that_verify_accepts(self):
        m = os.path.join(self.dir.name, "m.json")
        with open(m, "w", encoding="utf-8") as fh:
            json.dump([MANDATE], fh)
        i = os.path.join(self.dir.name, "i.csv")
        with open(i, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS, lineterminator="\n")
            w.writeheader()
            w.writerows([line(1), line(2, memo="a\nb")])
        a = os.path.join(self.dir.name, "audit.jsonl")
        self.assertEqual(run(["check", m, i, "--audit", a])[0], 0)
        with open(a, encoding="utf-8") as fh:
            self.assertEqual(len(fh.read().splitlines()), 2)
        code, out, _ = run(["verify", a])
        self.assertEqual(code, 0)
        self.assertIn("2 records, chain ok", out)

    def test_verify_exit_codes(self):
        good = self.write(self.records)
        self.assertEqual(run(["verify", good])[0], 0)
        self.assertEqual(run(["verify", good, "--head", "0" * 64])[0], 1)
        edited = copy.deepcopy(self.records)
        edited[0]["amount"] = "1.00"
        self.assertEqual(run(["verify", self.write(edited, "e.jsonl")])[0], 1)

    def test_verify_malformed_files_exit_2(self):
        for name, text in (("empty.jsonl", ""), ("blank.jsonl", "\n\n"), ("text.jsonl", "not json\n"), ("list.jsonl", "[1, 2]\n"),
                           ("missing.jsonl", '{"seq": 1}\n'), ("truncated.jsonl", '{"seq": 1, "prev": "0", "ha')):
            p = os.path.join(self.dir.name, name)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
            code, out, err = run(["verify", p])
            self.assertEqual(code, 2, name)
            self.assertEqual(len(err.strip().splitlines()), 1, name)
        self.assertEqual(run(["verify", os.path.join(self.dir.name, "nope.jsonl")])[0], 2)

    def test_hostile_text_is_json_escaped_in_the_audit_file(self):
        rows = [line(1, instruction_id="a\n{\"seq\": 2} ")]
        recs = pmc.audit_records(pmc.check_batch(pmc.parse_mandates([MANDATE]), rows))
        text = json.dumps(recs[0], sort_keys=True, ensure_ascii=True)
        self.assertEqual(len(text.splitlines()), 1)
        self.assertTrue(pmc.verify_audit([json.loads(text)])[0])


if __name__ == "__main__":
    unittest.main()
