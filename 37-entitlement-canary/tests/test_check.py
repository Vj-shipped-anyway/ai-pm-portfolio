import contextlib
import copy
import csv
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import entitlement_canary as ec

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
PACK_HEAD = ec.PACK_COLUMNS
RES_HEAD = ec.RESULT_COLUMNS


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ec.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


def read_csv(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        with open(os.path.join(DATA, "example_access.json"), encoding="utf-8") as fh:
            self.access = json.load(fh)
        self.pack = read_csv("example_pack.csv")
        self.results = read_csv("example_results.csv")

    def files(self, access=None, pack=None, results=None):
        paths = []
        for name, head, rows in (("pack.csv", PACK_HEAD, pack if pack is not None else self.pack),
                                 ("results.csv", RES_HEAD, results if results is not None else self.results)):
            p = os.path.join(self.dir.name, name)
            with open(p, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=head, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
            paths.append(p)
        a = os.path.join(self.dir.name, "access.json")
        with open(a, "w", encoding="utf-8") as fh:
            json.dump(access if access is not None else self.access, fh)
        return [a] + paths

    def clean_results(self):
        out = copy.deepcopy(self.results)
        out[0]["returned_doc_ids"] = "D3"
        return out

    def test_demo_prints_the_leak_and_exits_0(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("LEAK CAN-001 [nested_deny] U2 was returned D1", out)
        self.assertIn("decision: BLOCK", out)

    def test_leak_blocks_and_exits_1(self):
        code, out, _ = run(["check"] + self.files())
        self.assertEqual(code, 1)
        self.assertIn("leaks 1", out)

    def test_clean_run_allows_and_exits_0(self):
        code, out, _ = run(["check"] + self.files(results=self.clean_results()))
        self.assertEqual(code, 0)
        self.assertIn("decision: ALLOW", out)

    def test_fail_on_never_keeps_exit_0(self):
        self.assertEqual(run(["check"] + self.files() + ["--fail-on", "never"])[0], 0)

    def test_a_leak_of_a_document_that_is_not_the_target_is_caught(self):
        res = self.clean_results()
        res[2]["returned_doc_ids"] = "D3;D5"       # CAN-003 targets D2; D5 is closed to U1 as well
        code, out, _ = run(["check"] + self.files(results=res))
        self.assertEqual(code, 1)
        self.assertIn("CAN-003 [ordinary] U1 was returned D5", out)

    def test_retrieving_the_target_after_a_grant_is_not_a_leak(self):
        access = copy.deepcopy(self.access)
        access["documents"][0]["acl"] = ["grp-all-staff"]       # the pull request removes the deny on D1
        code, out, _ = run(["check"] + self.files(access=access))
        self.assertEqual(code, 0)
        self.assertIn("retired (the user may now open the target) 1", out)

    def test_inert_canary_is_a_review_not_a_pass(self):
        res = self.clean_results()
        res[2]["control_returned_doc_ids"] = "D3"
        code, out, _ = run(["check"] + self.files(results=res, access=None) + ["--fail-on", "review"])
        self.assertEqual(code, 1)
        self.assertIn("decision: REVIEW", out)
        self.assertIn("inert canaries (1)", out)

    def test_unprimed_run_is_a_review(self):
        res = self.clean_results()
        res[1]["primed"] = "no"
        _, out, _ = run(["check"] + self.files(results=res))
        self.assertIn("decision: REVIEW", out)
        self.assertIn("run without the control query (1)", out)

    def test_missing_result_row_and_unknown_user_are_reviews(self):
        _, out, _ = run(["check"] + self.files(results=self.clean_results()[:5]))
        self.assertIn("canaries with no result row (1): CAN-006", out)
        pack = copy.deepcopy(self.pack)
        pack[0]["user_id"] = "U99"
        res = self.clean_results()[1:]
        _, out, _ = run(["check"] + self.files(pack=pack, results=res))
        self.assertIn("missing from the access export (1): CAN-001", out)

    def test_source_with_too_few_canaries_is_a_review(self):
        _, out, _ = run(["check"] + self.files(results=self.clean_results()) + ["--min-per-source", "3"])
        self.assertIn("sources with too few canaries: minutes 2", out)
        self.assertIn("decision: REVIEW", out)

    def test_returned_document_unknown_to_the_export_is_a_review(self):
        res = self.clean_results()
        res[0]["returned_doc_ids"] = "D3;D404"
        _, out, _ = run(["check"] + self.files(results=res))
        self.assertIn("decision: REVIEW", out)
        self.assertIn("results naming a document missing from the access export (1 canaries)", out)

    def test_github_format_uses_error_and_warning_annotations(self):
        _, out, _ = run(["check"] + self.files() + ["--format", "github", "--fail-on", "never"])
        self.assertTrue(out.startswith("::error title=entitlement-canary leak::"))
        self.assertIn("::notice title=entitlement-canary::decision BLOCK", out)


class BadInputTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.access = os.path.join(DATA, "example_access.json")
        self.pack = os.path.join(DATA, "example_pack.csv")
        self.results = os.path.join(DATA, "example_results.csv")

    def write(self, name, text):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return p

    def exits_2_with_one_line(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, args)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)

    def test_empty_wrong_type_and_truncated_access_exports(self):
        for text in ("", "[1, 2]", '{"groups": [], "users": []}', '{"groups": [], "users": [], "documents": [{"doc_id": 5}]}',
                     '{"groups": [], "users": [], "docu', '{"groups": {}, "users": [], "documents": []}'):
            self.exits_2_with_one_line(["check", self.write("a.json", text), self.pack, self.results])

    def test_empty_missing_column_and_truncated_csv(self):
        for text in ("", "canary_id\n", "canary_id,user_id,doc_id,query,stratum,source,prime_user\n", "canary_id,user_id\nCAN-1,U1\n"):
            self.exits_2_with_one_line(["check", self.access, self.write("p.csv", text), self.results])
        for text in ("", "canary_id,returned_doc_ids,primed,control_returned_doc_ids\n", "canary_id,returned_doc_ids\nCAN-001,D1\n"):
            self.exits_2_with_one_line(["check", self.access, self.pack, self.write("r.csv", text)])

    def test_results_that_match_no_canary_say_so_instead_of_passing(self):
        text = "canary_id,returned_doc_ids,primed,control_returned_doc_ids\nCAN-900,D1,yes,D1\n"
        code, _, err = run(["check", self.access, self.pack, self.write("r.csv", text)])
        self.assertEqual(code, 2)
        self.assertIn("not in the pack", err)

    def test_bad_primed_value_duplicate_ids_and_missing_files(self):
        head = "canary_id,returned_doc_ids,primed,control_returned_doc_ids\n"
        self.exits_2_with_one_line(["check", self.access, self.pack, self.write("r.csv", head + "CAN-001,D3,maybe,D1\n")])
        self.exits_2_with_one_line(["check", self.access, self.pack, self.write("r.csv", head + "CAN-001,D3,yes,D1\nCAN-001,D3,yes,D1\n")])
        self.exits_2_with_one_line(["check", "nope.json", self.pack, self.results])
        self.exits_2_with_one_line(["check", self.access, self.pack, "nope.csv"])

    def test_nul_byte_and_binary_input(self):
        self.exits_2_with_one_line(["check", self.access, self.pack, self.write("r.csv", "canary_id,returned_doc_ids\x00\n")])
        with open(os.path.join(self.dir.name, "b.json"), "wb") as fh:
            fh.write(b"\xff\xfe\x00")
        self.exits_2_with_one_line(["check", os.path.join(self.dir.name, "b.json"), self.pack, self.results])


class HostileStringTests(unittest.TestCase):
    EVIL = "x\n::error title=forged::approved\r%0A"

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        with open(os.path.join(DATA, "example_access.json"), encoding="utf-8") as fh:
            access = json.load(fh)
        access["documents"][0]["title"] = self.EVIL
        access["users"][1]["user_id"] = "U2" + self.EVIL
        text = json.dumps(access)
        self.access = os.path.join(self.dir.name, "a.json")
        with open(self.access, "w", encoding="utf-8") as fh:
            fh.write(text)
        pack = [dict(r, user_id=("U2" + self.EVIL) if r["user_id"] == "U2" else r["user_id"]) for r in read_csv("example_pack.csv")]
        self.pack = os.path.join(self.dir.name, "p.csv")
        with open(self.pack, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=PACK_HEAD, lineterminator="\n")
            w.writeheader()
            w.writerows(pack)
        self.results = os.path.join(DATA, "example_results.csv")

    def test_github_output_cannot_forge_a_command(self):
        _, out, _ = run(["check", self.access, self.pack, self.results, "--format", "github", "--fail-on", "never"])
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), len(out.splitlines()))
        self.assertEqual(len(commands), 2)             # the one leak and the notice, nothing forged
        self.assertIn("%0A", commands[0])
        self.assertIn("%250A", commands[0])            # a literal %0A in the input is escaped too
        self.assertEqual(ec.escape_annotation("a\r\nb%"), "a%0D%0Ab%25")

    def test_text_output_keeps_each_value_on_one_line(self):
        _, out, _ = run(["check", self.access, self.pack, self.results, "--fail-on", "never"])
        lines = out.splitlines()
        self.assertFalse([ln for ln in lines if ln.startswith("::")])
        self.assertEqual(sum(1 for ln in lines if ln.startswith("LEAK")), 1)
        self.assertEqual(len(lines), 5)


if __name__ == "__main__":
    unittest.main()
