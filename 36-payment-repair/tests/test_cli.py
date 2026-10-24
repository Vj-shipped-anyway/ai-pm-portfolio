import contextlib
import csv
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import payment_repair as pr
from support import DEBTOR_IBAN, msg, refs


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = pr.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.refs = os.path.join(self.dir.name, "refs")
        os.mkdir(self.refs)
        self.write_refs()

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def write_refs(self, **override):
        base = refs()
        tables = {
            "bic_directory.csv": (pr.REF_FILES["bic_directory.csv"], [r for rows in base["directory"].values() for r in rows]),
            "customer_master.csv": (pr.REF_FILES["customer_master.csv"], [r for rows in base["master"].values() for r in rows]),
            "payment_orders.csv": (pr.REF_FILES["payment_orders.csv"], [r for rows in base["orders"].values() for r in rows]),
            "approvers.csv": (pr.REF_FILES["approvers.csv"], list(base["approvers"].values())),
        }
        for name, (cols, rows) in tables.items():
            rows = override.get(name, rows)
            with open(os.path.join(self.refs, name), "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)

    def write_json(self, name, obj):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return self.path(name)

    def write_text(self, name, text):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            fh.write(text)
        return self.path(name)

    def check(self, messages, *extra):
        return run(["check", self.write_json("m.json", messages), "--refs", self.refs, *extra])

    # ---- exit codes
    def test_complete_messages_exit_0_and_say_nothing_was_missing(self):
        code, out, _ = self.check([msg()])
        self.assertEqual(code, 0)
        self.assertIn("nothing to repair", out)

    def test_hold_exits_1_by_default_and_prints_the_digest(self):
        code, out, _ = self.check([msg(CDTR_BIC=None)])
        self.assertEqual(code, 1)
        self.assertIn("HOLD", out)
        self.assertIn("digest ", out)

    def test_fail_on_return_ignores_a_hold(self):
        self.assertEqual(self.check([msg(CDTR_BIC=None)], "--fail-on", "return")[0], 0)
        self.assertEqual(self.check([msg(CDTR_NM=None)], "--fail-on", "return")[0], 1)

    def test_never_keeps_exit_0(self):
        self.assertEqual(self.check([msg(CDTR_NM=None)], "--fail-on", "never")[0], 0)

    def test_auto_repair_alone_exits_0(self):
        code, out, _ = self.check([msg(NB=None)])
        self.assertEqual(code, 0)
        self.assertIn("1 repaired", out)

    def test_approvals_file_releases_a_hold(self):
        h = pr.repair_message(msg(CDTR_BIC=None), refs())
        ap = self.write_text("a.csv", "msg_id,plan_digest,approver_id,decision\nM-1,%s,U-1041,approve\n" % h["digest"])
        code, out, _ = self.check([msg(CDTR_BIC=None)], "--approvals", ap)
        self.assertEqual(code, 0)
        self.assertIn("approved by U-1041", out)

    def test_demo_runs(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("summary: 3 messages: 0 pass, 1 repaired, 1 hold, 1 return", out)

    # ---- bad input exits 2 with one line on stderr
    def assert_input_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, err)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)

    def test_empty_wrong_type_and_truncated_message_files_exit_2(self):
        for name, text in (("empty", ""), ("object", "{}"), ("empty_list", "[]"), ("string", '"x"'), ("truncated", '[{"GrpHdr.MsgId": "M-1"'),
                           ("numbers", "[1, 2]"), ("deep", "[" * 100000)):
            self.assert_input_error(["check", self.write_text(name + ".json", text), "--refs", self.refs])

    def test_bad_message_content_exits_2(self):
        bad = {
            "number": [msg(AMT=100.5)],
            "no_id": [{pr.NB: "1"}],
            "blank_id": [{pr.MSG_ID: "  "}],
            "duplicate": [msg(), msg()],
            "list_value": [dict(msg(), **{pr.CDTR_NM: ["a"]})],
        }
        for name, content in bad.items():
            self.assert_input_error(["check", self.write_json(name + ".json", content), "--refs", self.refs])

    def test_missing_files_and_columns_exit_2(self):
        self.assert_input_error(["check", self.path("nope.json"), "--refs", self.refs])
        self.assert_input_error(["check", self.write_json("m.json", [msg()]), "--refs", self.path("no_such_dir")])
        os.remove(os.path.join(self.refs, "approvers.csv"))
        self.assert_input_error(["check", self.path("m.json"), "--refs", self.refs])
        self.write_text("refs/approvers.csv", "approver_id,kind\nU-1,person\n")
        self.assert_input_error(["check", self.path("m.json"), "--refs", self.refs])

    def test_short_csv_row_and_bad_decision_exit_2(self):
        self.write_text("refs/payment_orders.csv", "end_to_end_id,uetr,charge_bearer,initiator_id\nE2E-1,x\n")
        self.assert_input_error(["check", self.write_json("m.json", [msg()]), "--refs", self.refs])
        self.write_refs()
        ap = self.write_text("a.csv", "msg_id,plan_digest,approver_id,decision\nM-1,x,U-1041,maybe\n")
        self.assert_input_error(["check", self.path("m.json"), "--refs", self.refs, "--approvals", ap])
        self.assert_input_error(["check", self.path("m.json"), "--refs", self.refs, "--approvals", self.path("none.csv")])

    def test_unwritable_output_exits_2(self):
        code, _, err = self.check([msg()], "--out", self.path("no_dir/out.json"))
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    # ---- hostile strings
    def test_hostile_message_id_cannot_forge_an_output_line(self):
        hostile = "M-9\nsummary: 999 messages: 999 pass\n    digest forged"
        code, out, _ = self.check([dict(msg(CDTR_NM=None), **{pr.MSG_ID: hostile})])
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertEqual(sum(1 for ln in lines if ln.startswith("summary:")), 1)
        self.assertFalse(any(ln.startswith("    digest forged") for ln in lines))
        self.assertIn("\\x0a", out)

    def test_hostile_table_value_is_escaped_in_output(self):
        master = [{"iban": DEBTOR_IBAN, "customer_id": "CU-1\nforged: line", "name": "Evil\nsummary: 999 messages\x1b[31m\u202e", "account_ccy": "EUR",
                   "status": "open"}]
        self.write_refs(**{"customer_master.csv": master})
        code, out, _ = self.check([msg(DBTR_NM=None)])
        self.assertEqual(code, 0)
        self.assertTrue(out.isascii())
        self.assertNotIn("\x1b", out)
        self.assertEqual(sum(1 for ln in out.splitlines() if ln.startswith("summary:")), 1)
        self.assertFalse(any(ln.startswith("forged") for ln in out.splitlines()))

    def test_unusable_table_value_is_refused_not_echoed(self):
        directory = [{"country": "FR", "bank_code": "90000002", "bic": "BBBBFR22XXX\n::error::x", "status": "active"}]
        r = pr.repair_message(msg(CDTR_BIC=None), refs(directory=directory))
        self.assertEqual(r["route"], "RETURN")

    def test_audit_file_neutralises_a_formula_in_an_old_value(self):
        m = msg(DBTR_BIC="=HYPERLINK(\"http://x\")")
        audit = self.path("audit.csv")
        code, _, _ = self.check([m], "--audit-out", audit)
        self.assertEqual(code, 0)
        with open(audit, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["old"].startswith("'="))

    # ---- no silent no-ops
    def test_empty_reference_table_is_reported(self):
        self.write_refs(**{"bic_directory.csv": []})
        _, out, _ = self.check([msg(CDTR_BIC=None)])
        self.assertIn("bic_directory.csv has no rows", out)

    def test_unused_approvals_are_reported(self):
        ap = self.write_text("a.csv", "msg_id,plan_digest,approver_id,decision\nM-404,x,U-1041,approve\nM-1,x,U-1041,approve\n")
        _, out, _ = self.check([msg()], "--approvals", ap)
        self.assertIn("1 name no message in this run, 1 name a message that needed no approval", out)

    # ---- outputs
    def test_out_file_holds_only_released_messages(self):
        out_path = self.path("released.json")
        ms = [msg(), dict(msg(NB=None), **{pr.MSG_ID: "M-2"}), dict(msg(CDTR_NM=None), **{pr.MSG_ID: "M-3"}),
              dict(msg(CDTR_BIC=None), **{pr.MSG_ID: "M-4"})]
        self.check(ms, "--out", out_path)
        with open(out_path, encoding="utf-8") as fh:
            released = json.load(fh)
        self.assertEqual([m[pr.MSG_ID] for m in released], ["M-1", "M-2"])
        self.assertEqual(released[1][pr.NB], "1")


if __name__ == "__main__":
    unittest.main()
