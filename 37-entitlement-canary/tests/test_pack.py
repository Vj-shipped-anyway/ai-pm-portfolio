import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import entitlement_canary as ec

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
with open(os.path.join(DATA, "access_base.json"), encoding="utf-8") as _fh:
    ACCESS = json.load(_fh)


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ec.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class PackTests(unittest.TestCase):
    def test_same_seed_same_pack_other_seed_other_pack(self):
        self.assertEqual(ec.build_pack(ACCESS), ec.build_pack(ACCESS))
        self.assertNotEqual(ec.build_pack(ACCESS), ec.build_pack(ACCESS, seed=5))

    def test_every_canary_is_a_pair_the_user_cannot_open(self):
        ix = ec.index_access(ACCESS)
        for c in ec.build_pack(ACCESS):
            self.assertFalse(ec.can_open(ix, c["user_id"], ix["docs"][c["doc_id"]]["acl"]), c["canary_id"])
            self.assertEqual(ec.stratum_of(ix, c["user_id"], ix["docs"][c["doc_id"]]), c["stratum"])
            self.assertNotEqual(c["prime_user"], c["user_id"])
            if c["prime_user"]:
                self.assertTrue(ec.can_open(ix, c["prime_user"], ix["docs"][c["doc_id"]]["acl"]), c["canary_id"])
            else:
                self.assertFalse(any(ec.can_open(ix, u, ix["docs"][c["doc_id"]]["acl"]) for u in ix["users"]), c["canary_id"])

    def test_stale_canaries_were_open_under_the_index_copy(self):
        ix = ec.index_access(ACCESS)
        stale = [c for c in ec.build_pack(ACCESS) if c["stratum"] == "stale_acl"]
        self.assertEqual(len(stale), 10)
        for c in stale:
            self.assertTrue(ec.can_open(ix, c["user_id"], ix["docs"][c["doc_id"]]["acl_at_index"]))

    def test_quotas_and_source_minimum(self):
        pack = ec.build_pack(ACCESS, {"stale_acl": 0, "nested_deny": 2, "direct_deny": 0, "ordinary": 0}, min_per_source=4)
        per_source = {}
        for c in pack:
            per_source[c["source"]] = per_source.get(c["source"], 0) + 1
        self.assertEqual(sorted(per_source), ["dms", "minutes", "policy", "tickets", "wiki"])
        self.assertTrue(all(n >= 4 for n in per_source.values()), per_source)
        self.assertGreaterEqual(sum(1 for c in pack if c["stratum"] == "nested_deny"), 2)

    def test_everyone_may_open_everything_gives_an_error_not_an_empty_pack(self):
        access = {"groups": [], "users": [{"user_id": "u", "direct_groups": ["g"]}],
                  "documents": [{"doc_id": "d", "title": "t", "source": "s", "acl": ["g"]}]}
        with self.assertRaises(ValueError):
            ec.build_pack(access)

    def test_cli_build_pack_writes_the_file_and_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "pack.csv")
            code, stdout, _ = run(["build-pack", os.path.join(DATA, "access_base.json"), "--out", out])
            self.assertEqual(code, 0)
            self.assertIn("wrote 62 canaries", stdout)
            self.assertEqual(len(ec.load_pack(out)), 62)

    def test_cli_rejects_a_bad_quota_and_a_bad_export(self):
        base = os.path.join(DATA, "access_base.json")
        code, _, err = run(["build-pack", base, "--quota", "nonsense=3"])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "a.json")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("[1, 2]")
            self.assertEqual(run(["build-pack", bad])[0], 2)


if __name__ == "__main__":
    unittest.main()
