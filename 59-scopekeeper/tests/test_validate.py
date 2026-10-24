import csv
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import scopekeeper as sk


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def path(self, name, header=None, rows=(), raw=None):
        p = os.path.join(self.dir.name, name)
        if raw is not None:
            with open(p, "wb") as fh:
                fh.write(raw)
        else:
            with open(p, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh, lineterminator="\n")
                if header is not None:
                    w.writerow(header)
                w.writerows(rows)
        return p

    def bad(self, fn, p, fragment):
        with self.assertRaises(sk.InputError) as cm:
            fn(p)
        self.assertIn(fragment, str(cm.exception))
        self.assertNotIn("\n", str(cm.exception))

    def test_empty_file(self):
        self.bad(sk.load_grants, self.path("g.csv", raw=b""), "empty")

    def test_header_only(self):
        self.bad(sk.load_grants, self.path("g.csv", ["agent_id", "scope"]), "no rows")
        self.bad(sk.load_calls, self.path("c.csv", ["agent_id", "scope_used"]), "refusing to propose removing every grant")

    def test_wrong_type_of_file(self):
        self.bad(sk.load_grants, self.path("g.csv", raw=b'{"agent": "A", "scope": "x"}\n'), "missing column")
        self.bad(sk.load_calls, self.path("c.csv", raw=bytes(range(128, 256)) * 3), "not UTF-8")

    def test_a_directory_is_not_a_file(self):
        self.bad(sk.load_grants, self.dir.name, "cannot read")

    def test_missing_file(self):
        self.bad(sk.load_calls, os.path.join(self.dir.name, "nope.csv"), "cannot read")

    def test_truncated_row(self):
        p = self.path("g.csv", raw=b"agent_id,scope,ticket_id\nA,x:read,T-1\nA,x:wri")
        self.bad(sk.load_grants, p, "line 3: expected 3 fields, found 2")

    def test_blank_and_duplicate_grants(self):
        self.bad(sk.load_grants, self.path("g.csv", ["agent_id", "scope"], [["A", ""]]), "must not be blank")
        self.bad(sk.load_grants, self.path("g.csv", ["agent_id", "scope"], [["A", "x"], ["A", "x"]]), "duplicate grant")

    def test_call_day_must_be_a_whole_number(self):
        for day in ("abc", "0", "-3", "2.5"):
            p = self.path("c.csv", ["agent_id", "scope_used", "day"], [["A", "x", day]])
            self.bad(sk.load_calls, p, "day must be a whole number")

    def test_call_with_no_agent_and_no_account(self):
        self.bad(sk.load_calls, self.path("c.csv", ["agent_id", "scope_used"], [["", "x"]]), "cannot be credited")

    def test_nested_groups_and_duplicates_in_the_catalog(self):
        p = self.path("k.csv", ["scope", "reaches"], [["g1", "g2;a"], ["g2", "b;c"]])
        self.bad(sk.load_catalog, p, "nested groups")
        self.bad(sk.load_catalog, self.path("k.csv", ["scope", "reaches"], [["g1", "a"], ["g1", "b"]]), "listed twice")

    def test_agents_file(self):
        self.bad(sk.load_agents, self.path("a.csv", ["agent_id", "service_account"], [["A", ""]]), "must not be blank")
        self.bad(sk.load_agents, self.path("a.csv", ["agent_id", "service_account"], [["A", "S"], ["A", "T"]]), "listed twice")

    def test_a_bom_and_extra_columns_are_accepted(self):
        p = self.path("g.csv", raw=b"\xef\xbb\xbfagent_id,scope,note\nA,x:read,hello\n")
        self.assertEqual(sk.load_grants(p)[0]["scope"], "x:read")

    def test_untagged_calls_need_an_agents_file(self):
        grants = [{"agent_id": "A", "scope": "x", "ticket_id": ""}]
        calls = [{"call_id": "c1", "agent_id": "", "day": 1, "scope": "x", "service_account": "S"}]
        with self.assertRaises(sk.InputError) as cm:
            sk.analyze(grants, calls, {})
        self.assertIn("--agents", str(cm.exception))

    def test_every_grant_holder_must_be_in_the_agents_file(self):
        grants = [{"agent_id": "A", "scope": "x", "ticket_id": ""}, {"agent_id": "B", "scope": "x", "ticket_id": ""}]
        calls = [{"call_id": "c1", "agent_id": "A", "day": 1, "scope": "x", "service_account": "S"}]
        with self.assertRaises(sk.InputError) as cm:
            sk.analyze(grants, calls, {}, {"A": "S"})
        self.assertIn("B holds grants", str(cm.exception))

    def test_a_star_grant_without_a_catalog_entry_is_refused_not_guessed(self):
        grants = [{"agent_id": "A", "scope": "acct:*", "ticket_id": ""}]
        calls = [{"call_id": "c1", "agent_id": "A", "day": 1, "scope": "acct:read", "service_account": ""}]
        with self.assertRaises(sk.InputError) as cm:
            sk.analyze(grants, calls, {})
        self.assertIn("pass --catalog", str(cm.exception))

    def test_a_call_that_names_a_group_is_refused(self):
        grants = [{"agent_id": "A", "scope": "acct:read", "ticket_id": ""}]
        calls = [{"call_id": "c1", "agent_id": "A", "day": 1, "scope": "acct:*", "service_account": ""}]
        with self.assertRaises(sk.InputError):
            sk.analyze(grants, calls, {"acct:*": ["acct:read"]})

    def test_no_covered_call_is_an_error_not_a_silent_removal_of_everything(self):
        grants = [{"agent_id": "A", "scope": "x", "ticket_id": ""}]
        calls = [{"call_id": "c1", "agent_id": "Z", "day": 1, "scope": "y", "service_account": ""}]
        with self.assertRaises(sk.InputError) as cm:
            sk.analyze(grants, calls, {})
        self.assertIn("none of the calls is covered", str(cm.exception))

    def test_bad_flags(self):
        grants = [{"agent_id": "A", "scope": "x", "ticket_id": ""}]
        calls = [{"call_id": "c1", "agent_id": "A", "day": 30, "scope": "x", "service_account": ""}]
        for kwargs in ({"min_calls": 0}, {"window_days": 0}, {"window_days": 10}):
            with self.assertRaises(sk.InputError):
                sk.analyze(grants, calls, {}, **kwargs)

    def test_clean_escapes_control_characters(self):
        self.assertEqual(sk.clean("a\nb\rc\td\x1be"), "a\\nb\\rc\\td\\u001be")
        self.assertEqual(sk.escape_annotation("50%\r\nx"), "50%25%0D%0Ax")


if __name__ == "__main__":
    unittest.main()
