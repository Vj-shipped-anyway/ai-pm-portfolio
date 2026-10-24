import copy
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import report_trace as rt


def leaf(p, b):
    return {"id": f"{p}.{b}", "kind": "leaf", "label": f"{p} / {b}", "product": p, "bucket": b}


SPEC = {"as_of": "2026-06-30", "status": "open", "products": ["a", "b"],
        "buckets": [{"name": "current", "min": 0, "max": 0}, {"name": "late", "min": 1, "max": None}],
        "cells": [leaf("a", "current"), leaf("a", "late"), leaf("b", "current"), leaf("b", "late"),
                  {"id": "ROW.a", "kind": "derived", "op": "sum", "inputs": ["a.current", "a.late"]},
                  {"id": "RATE.a", "kind": "derived", "op": "ratio_bps", "numerator": ["a.late"], "denominator": ["ROW.a"]}]}


def loan(lid, product, dpd, balance, status="open", booked="2026-05-01"):
    return {"loan_id": lid, "product": product, "status": status, "booked": booked, "dpd": dpd, "balance": balance}


def loans():
    rows = [loan("L1", "a", 0, 100000), loan("L2", "a", 0, 50000), loan("L3", "a", 30, 20000),
            loan("L4", "b", 0, 70000), loan("L5", "b", 10, 10000)]
    return {r["loan_id"]: r for r in rows}


FILED = {"a.current": 150000, "a.late": 20000, "b.current": 70000, "b.late": 10000, "ROW.a": 170000, "RATE.a": 1176}


def build(source=None, filed=None, adjustments=None):
    return rt.build_lineage(SPEC, source or loans(), adjustments or [], dict(FILED, **(filed or {})))


def verdicts(ev):
    return {cid: r["verdict"] for cid, r in ev["cells"].items()}


class TraceTests(unittest.TestCase):
    def test_untouched_source_traces_everywhere(self):
        ev = rt.evaluate(build(), loans())
        self.assertEqual(ev["summary"]["needs_person"], 0)
        self.assertEqual(verdicts(ev)["a.current"], "TRACED")
        self.assertEqual(verdicts(ev)["ROW.a"], "FOOTS")

    def test_logged_adjustment_explains_the_gap(self):
        lin = build(filed={"a.current": 155000, "ROW.a": 175000, "RATE.a": 1143},
                    adjustments=[{"adj_id": "A1", "cell_id": "a.current", "amount_cents": 5000, "reason": "x"}])
        ev = rt.evaluate(lin, loans())
        self.assertEqual(ev["cells"]["a.current"]["verdict"], "ADJUSTED")
        self.assertEqual(ev["summary"]["needs_person"], 0)

    def test_unlogged_amount_is_unexplained(self):
        ev = rt.evaluate(build(filed={"a.current": 155000, "ROW.a": 175000, "RATE.a": 1143}), loans())
        self.assertEqual(ev["cells"]["a.current"]["verdict"], "UNEXPLAINED")
        self.assertEqual(ev["cells"]["a.current"]["residual"], 5000)

    def test_partly_logged_leaves_the_rest_unexplained(self):
        lin = build(filed={"a.current": 157000, "ROW.a": 177000, "RATE.a": 1130},
                    adjustments=[{"adj_id": "A1", "cell_id": "a.current", "amount_cents": 5000, "reason": "x"}])
        r = rt.evaluate(lin, loans())["cells"]["a.current"]
        self.assertEqual((r["verdict"], r["residual"]), ("UNEXPLAINED", 2000))

    def test_balance_change_names_the_row_and_field(self):
        now = loans()
        now["L3"]["balance"] = 25000
        r = rt.evaluate(build(), now)["cells"]["a.late"]
        self.assertEqual(r["verdict"], "SOURCE_CHANGED")
        self.assertEqual(r["changed"], [("L3", [("balance_cents", 20000, 25000)])])

    def test_offsetting_changes_are_caught_although_the_sum_holds(self):
        now = loans()
        now["L1"]["balance"] += 7000
        now["L2"]["balance"] -= 7000
        self.assertEqual(sum(l["balance"] for l in now.values() if l["product"] == "a" and l["dpd"] == 0), FILED["a.current"])
        r = rt.evaluate(build(), now)["cells"]["a.current"]
        self.assertEqual([x for x, _ in r["changed"]], ["L1", "L2"])

    def test_row_removed(self):
        now = loans()
        del now["L2"]
        r = rt.evaluate(build(), now)["cells"]["a.current"]
        self.assertEqual((r["verdict"], r["missing"]), ("SOURCE_CHANGED", ["L2"]))

    def test_late_row_that_fits_the_rule_is_flagged(self):
        now = loans()
        now["L9"] = loan("L9", "a", 0, 1000, booked="2026-06-15")
        r = rt.evaluate(build(), now)["cells"]["a.current"]
        self.assertEqual((r["verdict"], r["added"]), ("SOURCE_CHANGED", ["L9"]))

    def test_rows_after_the_as_of_date_and_closed_rows_are_ignored(self):
        now = loans()
        now["L9"] = loan("L9", "a", 0, 1000, booked="2026-07-02")
        now["L8"] = loan("L8", "a", 0, 1000, status="closed")
        self.assertEqual(rt.evaluate(build(), now)["summary"]["needs_person"], 0)

    def test_a_row_that_moved_bucket_flags_the_old_cell_only(self):
        now = loans()
        now["L1"]["dpd"] = 5
        ev = rt.evaluate(build(), now)
        self.assertEqual(ev["cells"]["a.current"]["verdict"], "SOURCE_CHANGED")
        self.assertEqual(ev["cells"]["a.late"]["verdict"], "TRACED")
        self.assertEqual(ev["cells"]["a.late"]["moved_in"], ["L1"])

    def test_orphans_are_open_rows_in_period_that_fit_no_cell(self):
        src = loans()
        src["L6"] = loan("L6", "a", None, 100)
        src["L7"] = loan("L7", "zzz", 0, 100)
        src["L8"] = loan("L8", "a", None, 100, status="closed")
        src["L9"] = loan("L9", "a", None, 100, booked="2026-07-02")
        lin = rt.build_lineage(SPEC, src, [], FILED)
        self.assertEqual([r[0] for r in lin["orphans"]], ["L6", "L7"])

    def test_total_that_does_not_foot(self):
        ev = rt.evaluate(build(filed={"ROW.a": 170001, "RATE.a": 1176}), loans())
        self.assertEqual(ev["cells"]["ROW.a"]["verdict"], "DOES_NOT_FOOT")
        self.assertEqual(ev["cells"]["ROW.a"]["expected"], 170000)
        self.assertEqual(ev["cells"]["RATE.a"]["verdict"], "FOOTS")   # judged against the filed inputs, not the true ones

    def test_derived_cell_counts_leaf_problems_beneath_it(self):
        now = loans()
        now["L3"]["balance"] = 1
        r = rt.evaluate(build(), now)["cells"]["ROW.a"]
        self.assertEqual((len(r["leaves"]), r["rows"], r["leaf_problems"]), (2, 3, 1))

    def test_ratio_rounds_half_away_from_zero(self):
        self.assertEqual(rt.ratio_bps(1, 32), 313)
        self.assertEqual(rt.ratio_bps(-1, 32), -313)
        self.assertEqual(rt.ratio_bps(1, 3), 3333)
        self.assertEqual(rt.ratio_bps(5, 0), 0)

    def test_unmatched_adjustments_are_kept_and_explained(self):
        adj = [{"adj_id": "A1", "cell_id": "nope", "amount_cents": 1, "reason": "r"},
               {"adj_id": "A2", "cell_id": "ROW.a", "amount_cents": 1, "reason": "r"}]
        lin = build(adjustments=adj)
        self.assertEqual([a["why"] for a in lin["unmatched_adjustments"]], ["targets no cell in the spec", "targets a derived cell"])
        self.assertEqual(rt.evaluate(lin, loans())["summary"]["unmatched_adjustments"], 2)

    def test_trace_of_an_empty_cell_says_so(self):
        src = {k: v for k, v in loans().items() if k != "L5"}
        lin = rt.build_lineage(SPEC, src, [], dict(FILED, **{"b.late": 0}))
        text = rt.render_trace(lin, rt.evaluate(lin, src), "b.late")
        self.assertIn("no loan matched this rule", text)

    def test_build_refuses_a_source_that_matches_nothing(self):
        with self.assertRaises(rt.InputError):
            rt.build_lineage(SPEC, {"L1": loan("L1", "q", 0, 1)}, [], FILED)

    def test_without_a_source_nothing_is_compared(self):
        ev = rt.evaluate(build())
        self.assertFalse(ev["summary"]["source_compared"])
        self.assertEqual(ev["summary"]["needs_person"], 0)

    def test_lineage_file_is_deterministic_and_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "a.json"), os.path.join(d, "b.json")
            rt.write_lineage(build(), a)
            rt.write_lineage(build(), b)
            with open(a, "rb") as fa, open(b, "rb") as fb:
                self.assertEqual(fa.read(), fb.read())
            with open(a, encoding="utf-8") as fh:
                self.assertEqual(rt.load_lineage(a), json.load(fh))


class SpecTests(unittest.TestCase):
    def load(self, mutate):
        spec = copy.deepcopy(SPEC)
        mutate(spec)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "spec.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(spec, fh)
            return rt.load_spec(p)

    def bad(self, mutate):
        with self.assertRaises(rt.InputError):
            self.load(mutate)

    def test_valid_spec_loads(self):
        self.assertEqual(len(self.load(lambda s: None)["cells"]), 6)

    def test_duplicate_cell_id(self):
        self.bad(lambda s: s["cells"].append(copy.deepcopy(s["cells"][0])))

    def test_unknown_input(self):
        self.bad(lambda s: s["cells"][4].update(inputs=["ghost"]))

    def test_cycle(self):
        self.bad(lambda s: s["cells"][4].update(inputs=["RATE.a"]))

    def test_overlapping_buckets(self):
        self.bad(lambda s: s["buckets"][0].update(max=3))

    def test_leaf_with_unknown_product(self):
        self.bad(lambda s: s["cells"][0].update(product="zzz"))

    def test_label_must_be_text(self):
        self.bad(lambda s: s["cells"][0].update(label=5))

    def test_bucket_without_a_max_key(self):
        self.bad(lambda s: s["buckets"][0].pop("max"))

    def test_leaf_with_an_unhashable_bucket(self):
        self.bad(lambda s: s["cells"][0].update(bucket={"x": 1}))

    def test_boolean_is_not_a_number(self):
        self.bad(lambda s: s["buckets"][0].update(min=True))

    def test_structure_comes_from_fields_not_names(self):
        spec = self.load(lambda s: s["cells"][5].update(id="x"))
        self.assertEqual(spec["cells"][5]["id"], "x")


if __name__ == "__main__":
    unittest.main()
