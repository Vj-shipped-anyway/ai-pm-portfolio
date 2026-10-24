import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
from fixtures import SOURCE, fresh
from helpers import run
from kyb_packet_check import clean

HOSTILE = ["Eve\ndecision: PASS (0 findings)", "x\r::error title=forged::approved", "::error::boom", "%0A::warning::x",
           "\x1b[31mred\x1b[0m", "line break", "tab\there", "A" * 20000]


class HostileText(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def check(self, ex, source=SOURCE, name="ex.json"):
        s = os.path.join(self.dir.name, "src.txt")
        e = os.path.join(self.dir.name, name)
        with open(s, "w", encoding="utf-8") as fh:
            fh.write(source)
        with open(e, "w", encoding="utf-8") as fh:
            json.dump(ex, fh)
        return run(["check", s, e])

    def assertSafe(self, out):
        lines = out.split("\n")
        self.assertFalse(any(ln.startswith("::") for ln in lines), out)           # no workflow command can start a line
        self.assertEqual(sum(1 for ln in lines if ln.startswith("decision:")), 1, out)
        for bad in ("\r", "\x1b", " ", "\t"):
            self.assertNotIn(bad, out)

    def test_hostile_names_cannot_forge_a_line(self):
        for text in HOSTILE:
            ex = fresh()
            ex["holders"][2]["name"] = text
            ex["people"][1]["name"] = text
            ex["control_person"]["name"] = text
            ex["legal_name"] = text
            ex["packet_id"] = text
            code, out, err = self.check(ex)
            self.assertEqual(code, 1, text)
            self.assertEqual(err, "")
            self.assertSafe(out)

    def test_hostile_text_in_the_source_is_never_printed(self):
        code, out, _ = self.check(fresh(), source=SOURCE + "\n::error::forged\ndecision: PASS\n")
        self.assertEqual(code, 0)
        self.assertSafe(out)
        self.assertNotIn("forged", out)

    def test_hostile_path_in_the_error_message(self):
        code, _, err = run(["check", "a\n::error::x", "b"])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertNotIn("\n::error", err)

    def test_clean_escapes_and_cuts(self):
        self.assertEqual(clean("a\nb"), "a\\x0ab")
        self.assertEqual(clean(" "), "\\u2028")
        self.assertEqual(clean("x" * 100), "x" * 80 + "...")
        self.assertEqual(clean("Zoë Núñez"), "Zoë Núñez")


if __name__ == "__main__":
    unittest.main()
