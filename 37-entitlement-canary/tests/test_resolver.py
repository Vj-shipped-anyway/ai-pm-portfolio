import csv
import json
import os
import unittest

import _bootstrap  # noqa: F401
import entitlement_canary as ec

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def tiny(groups, users, docs):
    return {"groups": [{"parent": p, "child": c} for p, c in groups],
            "users": [{"user_id": u, "direct_groups": g} for u, g in users],
            "documents": [{"doc_id": d, "title": d, "source": "s", "acl": acl} for d, acl in docs]}


class ResolverTests(unittest.TestCase):
    def test_agrees_with_the_generator_on_every_pair(self):
        # the generator walks the tree downward, the resolver walks upward: same rule, two implementations
        access = load("access_base.json")
        ix = ec.index_access(access)
        checked = 0
        with open(os.path.join(DATA, "entitlement_truth.csv"), newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                entitled = set(row["entitled_doc_ids"].split(";")) if row["entitled_doc_ids"] else set()
                for d in access["documents"]:
                    self.assertEqual(ec.can_open(ix, row["user_id"], d["acl"]), d["doc_id"] in entitled, (row["user_id"], d["doc_id"]))
                    checked += 1
        self.assertEqual(checked, 20 * 120)

    def test_deny_wins_over_allow_and_nesting_is_followed(self):
        ix = ec.index_access(tiny([("all", "eng"), ("ext", "ext-eng")], [("a", ["eng"]), ("b", ["eng", "ext-eng"])],
                                  [("d", ["all", "-ext"])]))
        self.assertTrue(ec.can_open(ix, "a", ["all", "-ext"]))
        self.assertFalse(ec.can_open(ix, "b", ["all", "-ext"]))
        self.assertEqual(ec.stratum_of(ix, "b", {"acl": ["all", "-ext"]}), "nested_deny")

    def test_group_cycle_terminates(self):
        ix = ec.index_access(tiny([("a", "b"), ("b", "a")], [("u", ["a"])], [("d", ["b"])]))
        self.assertTrue(ec.can_open(ix, "u", ["b"]))

    def test_no_allow_entry_means_nobody(self):
        ix = ec.index_access(tiny([], [("u", ["g"])], [("d", ["-x"])]))
        self.assertFalse(ec.can_open(ix, "u", []))
        self.assertFalse(ec.can_open(ix, "u", ["-x"]))

    def test_stale_acl_stratum_needs_the_index_copy(self):
        ix = ec.index_access(tiny([], [("u", ["g"])], [("d", ["h"])]))
        doc = {"acl": ["h"], "acl_at_index": ["g", "h"]}
        self.assertEqual(ec.stratum_of(ix, "u", doc), "stale_acl")
        self.assertEqual(ec.stratum_of(ix, "u", {"acl": ["h"]}), "ordinary")

    def test_example_pack_strata_match_the_resolver(self):
        access = load("example_access.json")
        ix = ec.index_access(access)
        with open(os.path.join(DATA, "example_pack.csv"), newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self.assertEqual(ec.stratum_of(ix, row["user_id"], ix["docs"][row["doc_id"]]), row["stratum"], row["canary_id"])


if __name__ == "__main__":
    unittest.main()
