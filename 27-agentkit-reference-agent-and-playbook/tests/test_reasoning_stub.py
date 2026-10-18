import unittest

import _bootstrap  # noqa: F401
import support
from agentkit.reasoning_stub import STUB_LABEL, StubReasoner, correction_digest


class TestStub(unittest.TestCase):
    def setUp(self):
        self.stub = StubReasoner()
        self.pay = support.payment("P-1", account=support.WRONG)
        self.rule = support.REASON_CODES["RX01"]

    def draft(self):
        return self.stub.draft_correction(case_id="C", reason_code="RX01", rule=self.rule, payment=self.pay,
                                          advised_value=support.RIGHT, name_class="EXACT", name_score=1.0)

    def test_it_says_what_it_is(self):
        self.assertFalse(StubReasoner.is_model)
        self.assertIn("not a language model", STUB_LABEL)
        self.assertIn("STUB", StubReasoner.label)

    def test_a_draft_is_marked_stub(self):
        d = self.draft()
        self.assertTrue(d.stub)
        self.assertEqual(d.label, STUB_LABEL)
        self.assertTrue(d.message.startswith("[STUB]"))

    def test_it_is_deterministic(self):
        self.assertEqual(self.draft(), self.draft())

    def test_the_digest_binds_payment_field_and_value(self):
        a = correction_digest("P-1", "beneficiary_account", "1")
        self.assertEqual(a, correction_digest("P-1", "beneficiary_account", "1"))
        self.assertNotEqual(a, correction_digest("P-1", "beneficiary_account", "2"))
        self.assertNotEqual(a, correction_digest("P-2", "beneficiary_account", "1"))

    def test_case_note_is_labelled_and_names_the_hits(self):
        note = self.stub.draft_case_note(case_id="C", kind="final", reason_code="RX01", disposition="ESCALATE_COMPLIANCE",
                                         name_class="EXACT", hits=[{"party_id": "W-001", "score": 0.97}], draft=None,
                                         gate=None)
        self.assertIn("[STUB]", note)
        self.assertIn("W-001", note)
        self.assertIn("no language model wrote this note", note)

    def test_the_package_imports_only_the_standard_library_and_itself(self):
        import ast
        import pathlib
        allowed = {"__future__", "csv", "json", "hashlib", "re", "statistics", "pathlib", "typing", "dataclasses",
                   "collections", "difflib"}
        root = pathlib.Path(_bootstrap.SRC) / "agentkit"
        seen = set()
        for p in root.rglob("*.py"):
            for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    seen |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    seen.add(node.module.split(".")[0])
        self.assertEqual(seen - allowed, set(), "the package must not import anything outside the standard library")
        self.assertNotIn("socket", seen)
        self.assertNotIn("urllib", seen)


if __name__ == "__main__":
    unittest.main()
