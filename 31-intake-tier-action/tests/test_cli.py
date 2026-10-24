import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import _bootstrap  # noqa: F401
import intake_tier_action as it
from forms import body


class FakeStdin:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


def run(args, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        with mock.patch.object(sys, "stdin", FakeStdin(stdin or b"")):
            try:
                code = it.main(args)
            except SystemExit as e:
                code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text, mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8", "newline": ""})) as fh:
            fh.write(text)
        return p

    @staticmethod
    def read_out(directory, name):
        with open(os.path.join(directory, name), encoding="utf-8") as fh:
            return fh.read()

    def one_line_error(self, args, stdin=None):
        code, out, err = run(args, stdin)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("input error: "))
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertNotIn("Traceback", err)

    def test_demo_runs_and_swaps_the_stale_label(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("recomputed tier 3 (9 points)", out)
        self.assertIn("labels: add ai-tier:3, tier-mismatch; remove ai-tier:2", out)

    def test_body_from_standard_input(self):
        code, out, _ = run(["check", "-"], stdin=body().encode("utf-8"))
        self.assertEqual(code, 0)
        self.assertIn("recomputed tier 1", out)

    def test_empty_body_is_needs_info_and_fail_on_decides_the_exit(self):
        code, out, _ = run(["check", "-"], stdin=b"")
        self.assertEqual(code, 0)
        self.assertIn("decision: NEEDS_INFO", out)
        self.assertIn("labels: add needs-info", out)
        self.assertEqual(run(["check", "-", "--fail-on", "needs-info"], stdin=b"")[0], 1)

    def test_wrong_type_body_is_needs_info_not_a_crash(self):
        code, out, _ = run(["check", "-"], stdin=json.dumps({"parameters": {}}).encode("utf-8"))
        self.assertEqual(code, 0)
        self.assertIn("decision: NEEDS_INFO", out)

    def test_fail_on_mismatch(self):
        p = self.write("b.md", body(autonomy="automated", data_class="restricted", declared="1"))
        self.assertEqual(run(["check", p, "--fail-on", "mismatch"])[0], 1)
        self.assertEqual(run(["check", p, "--fail-on", "needs-info"])[0], 0)
        ok = self.write("ok.md", body())
        self.assertEqual(run(["check", ok, "--fail-on", "mismatch"])[0], 0)

    def test_missing_file_directory_binary_and_nul_exit_2_with_one_line(self):
        self.one_line_error(["check", os.path.join(self.dir.name, "nope.md")])
        self.one_line_error(["check", self.dir.name])
        self.one_line_error(["check", self.write("bin.md", b"\xff\xfe\x00\x01", "wb")])
        self.one_line_error(["check", self.write("nul.md", b"### Data class\n\x00\n", "wb")])
        self.one_line_error(["check", "-"], stdin=b"\xff\xfe")

    def test_catalog_problems_exit_2(self):
        good = self.write("b.md", body())
        self.one_line_error(["check", good, "--catalog", self.write("c1.csv", "")])
        self.one_line_error(["check", good, "--catalog", self.write("c2.csv", "dataset_name,catalog_class\n")])
        self.one_line_error(["check", good, "--catalog", self.write("c3.csv", "name,class\na,public\n")])
        self.one_line_error(["check", good, "--catalog", self.write("c4.csv", "dataset_name,catalog_class\nd_a,secret\n")])
        self.one_line_error(["check", good, "--catalog", self.write("c5.csv", "dataset_name,catalog_class\nd_a\n")])
        self.one_line_error(["check", good, "--catalog", self.write("c6.csv", "dataset_name,catalog_class\nd_a,public\nD_A,internal\n")])

    def test_registry_problems_exit_2(self):
        good = self.write("b.md", body())
        reg = self.write("r.csv", "issue_number,vendor_model,source\n5,vendor_api,x\n")
        self.one_line_error(["check", good, "--registry", reg])
        self.one_line_error(["check", good, "--registry", reg, "--issue-number", "abc"])
        self.one_line_error(["check", good, "--registry", reg, "--issue-number", "0"])
        self.one_line_error(["check", good, "--registry", self.write("r2.csv", "issue_number,vendor_model\nx,none\n"), "--issue-number", "5"])
        self.one_line_error(["check", good, "--registry", self.write("r3.csv", "issue_number,vendor_model\n5,none\n5,vendor_api\n"), "--issue-number", "5"])

    def test_labels_file_problems_exit_2(self):
        good = self.write("b.md", body())
        self.one_line_error(["check", good, "--labels", self.write("l1.json", "{}")])
        self.one_line_error(["check", good, "--labels", self.write("l2.json", "[1, 2]")])
        self.one_line_error(["check", good, "--labels", self.write("l3.json", '["a", ')])
        self.one_line_error(["check", good, "--labels", self.write("l4.json", "")])

    def test_registry_vendor_check_through_the_command(self):
        good = self.write("b.md", body())
        reg = self.write("r.csv", "issue_number,vendor_model,source\n5,vendor_api,x\n")
        code, out, _ = run(["check", good, "--registry", reg, "--issue-number", "5"])
        self.assertIn("VENDOR_NOT_DECLARED", out)
        self.assertIn("(3 points)", out)

    def test_out_dir_gets_labels_and_comment(self):
        good = self.write("b.md", body(autonomy="automated", data_class="restricted", declared="1"))
        labels = self.write("l.json", '["ai-intake", "ai-tier:1"]')
        out_dir = os.path.join(self.dir.name, "o", "p")
        self.assertEqual(run(["check", good, "--labels", labels, "--out-dir", out_dir])[0], 0)
        self.assertEqual(self.read_out(out_dir, "labels_add.txt"), "ai-tier:2\ntier-mismatch\n")
        self.assertEqual(self.read_out(out_dir, "labels_remove.txt"), "ai-tier:1\n")
        self.assertTrue(self.read_out(out_dir, "comment.md").startswith(it.MARKER))

    def test_out_dir_that_cannot_be_written_exits_2(self):
        blocker = self.write("file.txt", "x")
        self.one_line_error(["check", self.write("b.md", body()), "--out-dir", os.path.join(blocker, "sub")])

    def test_json_format_is_valid_json(self):
        code, out, _ = run(["check", "-", "--format", "json"], stdin=body().encode("utf-8"))
        data = json.loads(out)
        self.assertEqual((data["decision"], data["tier"], data["labels_add"]), ("TIERED", 1, ["ai-tier:1"]))

    def test_hostile_text_cannot_forge_an_annotation_or_a_mention(self):
        hostile = "d_x\n::error title=forged::approved %0A @everyone"
        text = body(dataset=hostile, data_class="secret\n::error::boom", summary="Plan\n::error title=forged::ok\n@everyone")
        catalog = self.write("c.csv", "dataset_name,catalog_class\nd_a,public\n")
        for fmt in ("github", "text", "json"):
            _, out, _ = run(["check", "-", "--format", fmt, "--catalog", catalog], stdin=text.encode("utf-8"))
            if fmt == "github":
                for ln in out.splitlines():
                    self.assertTrue(ln.startswith(("::warning title=intake-tier-action", "::notice title=intake-tier-action")), ln)
            else:
                self.assertNotIn("@everyone", out)
        ok = body(dataset=hostile)
        _, out, _ = run(["check", "-", "--format", "github", "--catalog", catalog], stdin=ok.encode("utf-8"))
        self.assertTrue(all(ln.startswith("::") and "title=intake-tier-action" in ln for ln in out.splitlines()))
        out_dir = os.path.join(self.dir.name, "o")
        run(["check", "-", "--catalog", catalog, "--out-dir", out_dir], stdin=ok.encode("utf-8"))
        comment = self.read_out(out_dir, "comment.md")
        for bad in ("@everyone", "::error", "forged::"):
            self.assertNotIn(bad, comment)

    def test_escape_annotation(self):
        self.assertEqual(it.escape_annotation("a%b\r\nc"), "a%25b%0D%0Ac")


if __name__ == "__main__":
    unittest.main()
