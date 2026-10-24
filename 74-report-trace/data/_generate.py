"""Generate the synthetic data for project 74: a loan position table at filing, the same table months later,
the report a reporting job filed from it, and the planted facts about what happened in between.

Everything is seeded and uses integer arithmetic only, so a rerun reproduces every file byte for byte.
The filed numbers and the truth labels come from this file's own aggregation (a bisect on bucket edges),
which is written separately from the cell rules in src/report_trace.py that the steps evaluate.

Run (from data/):  python3 _generate.py
Writes (prefix "" for the main set, "example_" for the small set behind `report_trace.py --demo`):
  loans_filed.csv, loans_now.csv, report_spec.json, report_filed.csv, adjustments.csv
  main set only: mapping_sheet.csv, truth_cells.csv, truth_rows.csv
"""
from __future__ import annotations

import bisect
import csv
import json
import random
from datetime import date, timedelta

NOTES = ["", "promise to pay", "hardship plan", "contact attempted", "payment arrangement", "dispute open", "skip trace"]
REASONS = ["top-side entry for a late recovery", "reclass approved by the controller", "correction after a reconciliation break",
           "accrual true-up"]

MAIN = dict(
    seed=74, prefix="", as_of="2026-06-30",
    products=[("auto", 520, 100, 30), ("card", 700, 150, 4), ("heloc", 260, 60, 60), ("mortgage", 480, 50, 600),
              ("overdraft", 330, 180, 1), ("personal", 440, 110, 20), ("small_business", 220, 130, 120), ("student", 250, 120, 25)],
    buckets=[("current", 0, 0), ("d01_29", 1, 29), ("d30_59", 30, 59), ("d60_89", 60, 89), ("d90_179", 90, 179), ("d180_plus", 180, None)],
    tail=[80, 50, 35, 25, 10], counts=None, closed=480, null_dpd=7, min_rows=4,
    plan=[("logged_adjustment", 4), ("silent_plug", 4), ("restated", 5), ("row_removed", 3), ("late_arrival", 3),
          ("offsetting", 3), ("source_error", 4), ("unreported_field", 4)],
    new_cells=12, footing=True, rate_from=2, truth=True)

EXAMPLE = dict(
    seed=7401, prefix="example_", as_of="2026-06-30",
    products=[("auto", 0, 100, 30), ("card", 0, 100, 4)],
    buckets=[("current", 0, 0), ("d01_59", 1, 59), ("d60_plus", 60, None)],
    tail=None, counts={"auto": [8, 5, 4], "card": [10, 6, 4]}, closed=3, null_dpd=1, min_rows=3,
    plan=[("logged_adjustment", 1), ("silent_plug", 1), ("restated", 1), ("unreported_field", 1)],
    new_cells=1, footing=False, rate_from=2, truth=False)


def shuffled(rng, seq):
    a = list(seq)
    for i in range(len(a) - 1, 0, -1):
        j = rng.randrange(i + 1)
        a[i], a[j] = a[j], a[i]
    return a


def pick(rng, weights):
    t = rng.randrange(sum(weights))
    for i, w in enumerate(weights):
        if t < w:
            return i
        t -= w
    raise AssertionError("unreachable")


def make(cfg):
    rng = random.Random(cfg["seed"])
    as_of = cfg["as_of"]
    as_of_date = date.fromisoformat(as_of)
    buckets = cfg["buckets"]
    names = [b[0] for b in buckets]
    edges = [b[1] for b in buckets[1:]]
    products = [p[0] for p in cfg["products"]]
    scale = {p[0]: p[3] for p in cfg["products"]}

    def dpd_in(b):
        lo, hi = buckets[b][1], buckets[b][2]
        return rng.randint(lo, lo + 360 if hi is None else hi)

    def balance(product):
        k = rng.randint(1, 60)
        return ((k * k * scale[product]) // 10 + rng.randint(1500, 6000)) * 100 + rng.randint(0, 99)

    def weights(risk):
        tail = [t * risk // 100 for t in cfg["tail"]]
        return [1000 - sum(tail)] + tail

    def loan(product, b, status="open", booked=None):
        return {"product": product, "status": status, "dpd": dpd_in(b), "balance": balance(product),
                "booked": booked or (as_of_date - timedelta(days=rng.randint(15, 2600))).isoformat(),
                "note": NOTES[rng.randrange(len(NOTES))]}

    s0 = []
    for name, count, risk, _ in cfg["products"]:
        if cfg["counts"]:
            blist = [b for b, n in enumerate(cfg["counts"][name]) for _ in range(n)]
        else:
            w = weights(risk)
            blist = [pick(rng, w) for _ in range(count)]
        s0 += [loan(name, b) for b in blist]
    for i in range(cfg["null_dpd"]):
        l = loan(products[i % len(products)], 0)
        l["dpd"] = None
        s0.append(l)
    for _ in range(cfg["closed"]):
        p = cfg["products"][rng.randrange(len(products))]
        s0.append(loan(p[0], rng.randrange(len(buckets)) if cfg["counts"] else pick(rng, weights(p[2])), "closed"))
    s0 = shuffled(rng, s0)
    for i, l in enumerate(s0, 1):
        l["loan_id"] = "L%06d" % i
    s1 = {l["loan_id"]: dict(l) for l in s0}
    next_id = [len(s0) + 1]

    def add_later(product, b, booked):
        l = loan(product, b, "open", booked)
        l["loan_id"] = "L%06d" % next_id[0]
        next_id[0] += 1
        s1[l["loan_id"]] = l
        return l

    keys = [(p, n) for p in products for n in names]
    cell_rows = {k: [] for k in keys}
    for l in sorted(s0, key=lambda x: x["loan_id"]):
        if l["status"] == "open" and l["dpd"] is not None and l["booked"] <= as_of:
            cell_rows[(l["product"], names[bisect.bisect_right(edges, l["dpd"])])].append(l)

    cand = shuffled(rng, [k for k in keys if len(cell_rows[k]) >= cfg["min_rows"]])
    cls = {}
    for kind, n in cfg["plan"]:
        for _ in range(n):
            if not cand:
                raise SystemExit("not enough cells with %d or more rows for the plan" % cfg["min_rows"])
            cls[cand.pop()] = kind
    for k in shuffled(rng, [k for k in keys if k not in cls])[:cfg["new_cells"]]:
        cls[k] = "new_after_asof"

    extra, adjustments, truth_rows, late_n = {}, [], [], 0
    for k in keys:
        kind, cid, rows = cls.get(k, "clean"), "%s.%s" % k, cell_rows[k]
        b = names.index(k[1])
        if kind in ("logged_adjustment", "silent_plug"):
            extra[cid] = (1 if rng.randrange(2) else -1) * rng.randint(300, 9000) * 1000
            if kind == "logged_adjustment":
                adjustments.append(("ADJ-%03d" % (len(adjustments) + 1), cid, extra[cid], REASONS[rng.randrange(len(REASONS))]))
        elif kind == "restated":
            r = rows[rng.randrange(len(rows))]
            delta = r["balance"] * rng.randint(3, 15) // 100
            new = r["balance"] + delta if rng.randrange(2) else r["balance"] - delta
            s1[r["loan_id"]]["balance"] = new
            truth_rows.append((cid, r["loan_id"], "balance_restated", "balance_cents %d -> %d" % (r["balance"], new)))
        elif kind == "row_removed":
            r = rows[rng.randrange(len(rows))]
            del s1[r["loan_id"]]
            truth_rows.append((cid, r["loan_id"], "row_removed", "row deleted from the source"))
        elif kind == "late_arrival":
            for _ in range(1 + late_n % 2):
                l = add_later(k[0], b, (as_of_date - timedelta(days=rng.randint(1, 20))).isoformat())
                truth_rows.append((cid, l["loan_id"], "late_arrival", "booked %s, loaded after filing" % l["booked"]))
            late_n += 1
        elif kind == "offsetting":
            i = rng.randrange(len(rows))
            j = (i + 1 + rng.randrange(len(rows) - 1)) % len(rows)
            d = min(rows[i]["balance"], rows[j]["balance"]) // 4
            s1[rows[i]["loan_id"]]["balance"] += d
            s1[rows[j]["loan_id"]]["balance"] -= d
            truth_rows.append((cid, rows[i]["loan_id"], "offset_up", "balance_cents +%d" % d))
            truth_rows.append((cid, rows[j]["loan_id"], "offset_down", "balance_cents -%d" % d))
        elif kind == "source_error":
            r = rows[rng.randrange(len(rows))]
            tb = b + 1 if b + 1 < len(names) else b - 1
            truth_rows.append((cid, r["loan_id"], "source_error", "recorded days_past_due %d (%s), true value %d (%s)"
                               % (r["dpd"], k[1], dpd_in(tb), names[tb])))
        elif kind == "unreported_field":
            i = rng.randrange(len(rows))
            for r in (rows[i], rows[(i + 1) % len(rows)]):
                new = NOTES[(NOTES.index(r["note"]) + 1 + rng.randrange(len(NOTES) - 1)) % len(NOTES)]
                s1[r["loan_id"]]["note"] = new
                truth_rows.append((cid, r["loan_id"], "note_changed", "servicer_note changed; the cell rule does not read it"))
        elif kind == "new_after_asof":
            for _ in range(3):
                l = add_later(k[0], b, (as_of_date + timedelta(days=rng.randint(2, 45))).isoformat())
                truth_rows.append((cid, l["loan_id"], "new_after_asof", "booked %s, after the as-of date" % l["booked"]))
    for l in sorted(s0, key=lambda x: x["loan_id"]):
        if l["dpd"] is None:
            truth_rows.append(("", l["loan_id"], "null_dpd", "open, booked before the as-of date, days_past_due blank"))

    spec_cells = []
    for p, n in keys:
        spec_cells.append({"id": "%s.%s" % (p, n), "kind": "leaf", "label": "%s / %s" % (p, n), "product": p, "bucket": n})
    for p in products:
        spec_cells.append({"id": "ROW." + p, "kind": "derived", "label": p + " total", "op": "sum", "inputs": ["%s.%s" % (p, n) for n in names]})
    for n in names:
        spec_cells.append({"id": "COL." + n, "kind": "derived", "label": n + " total", "op": "sum", "inputs": ["%s.%s" % (p, n) for p in products]})
    spec_cells.append({"id": "ALL", "kind": "derived", "label": "all products total", "op": "sum", "inputs": ["COL." + n for n in names]})
    for p in products:
        spec_cells.append({"id": "RATE." + p, "kind": "derived", "label": "%s share at %s or later, bps of total" % (p, names[cfg["rate_from"]]),
                           "op": "ratio_bps", "numerator": ["%s.%s" % (p, n) for n in names[cfg["rate_from"]:]], "denominator": ["ROW." + p]})

    perturb = {}
    if cfg["footing"]:
        a = rng.randrange(len(products))
        perturb["ROW." + products[a]] = (1 if rng.randrange(2) else -1) * rng.randint(2, 9) * 1000000
        perturb["COL." + names[rng.randrange(len(names))]] = (1 if rng.randrange(2) else -1) * rng.randint(2, 9) * 1000000
        perturb["RATE." + products[(a + 1 + rng.randrange(len(products) - 1)) % len(products)]] = (1 if rng.randrange(2) else -1) * rng.randint(3, 40)

    filed = {}
    for c in spec_cells:
        if c["kind"] == "leaf":
            filed[c["id"]] = sum(l["balance"] for l in cell_rows[(c["product"], c["bucket"])]) + extra.get(c["id"], 0)
        elif c["op"] == "sum":
            filed[c["id"]] = sum(filed[i] for i in c["inputs"]) + perturb.get(c["id"], 0)
        else:
            num, den = sum(filed[i] for i in c["numerator"]), sum(filed[i] for i in c["denominator"])
            filed[c["id"]] = ((num * 10000 + den // 2) // den if den else 0) + perturb.get(c["id"], 0)

    spec = {"as_of": as_of, "status": "open", "products": products,
            "buckets": [{"name": n, "min": lo, "max": hi} for n, lo, hi in buckets], "cells": spec_cells}
    return dict(spec=spec, filed=filed, s0=s0, s1=s1, adjustments=adjustments, cls=cls, extra=extra, perturb=perturb,
                truth_rows=truth_rows, buckets=buckets, keys=keys)


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write(cfg, w):
    pre = cfg["prefix"]
    cols = ["loan_id", "product", "status", "booked_date", "days_past_due", "balance_cents", "servicer_note"]

    def loan_rows(loans):
        return [[l["loan_id"], l["product"], l["status"], l["booked"], "" if l["dpd"] is None else l["dpd"], l["balance"], l["note"]]
                for l in sorted(loans, key=lambda x: x["loan_id"])]
    write_csv(pre + "loans_filed.csv", cols, loan_rows(w["s0"]))
    write_csv(pre + "loans_now.csv", cols, loan_rows(w["s1"].values()))
    with open(pre + "report_spec.json", "w", encoding="utf-8") as fh:
        json.dump(w["spec"], fh, indent=1)
        fh.write("\n")
    write_csv(pre + "report_filed.csv", ["cell_id", "value"], [[c["id"], w["filed"][c["id"]]] for c in w["spec"]["cells"]])
    write_csv(pre + "adjustments.csv", ["adj_id", "cell_id", "amount_cents", "reason"], w["adjustments"])
    if not cfg["truth"]:
        return
    limits = {n: (lo, hi) for n, lo, hi in w["buckets"]}
    write_csv("mapping_sheet.csv", ["cell_id", "source_table", "product", "dpd_min", "dpd_max", "status"],
              [[c["id"], "loans", c["product"], limits[c["bucket"]][0], "" if limits[c["bucket"]][1] is None else limits[c["bucket"]][1], "open"]
               for c in w["spec"]["cells"] if c["kind"] == "leaf"])
    rows = []
    for c in w["spec"]["cells"]:
        if c["kind"] == "leaf":
            rows.append([c["id"], "leaf", w["cls"].get((c["product"], c["bucket"]), "clean"),
                         "amount_cents %d" % w["extra"][c["id"]] if c["id"] in w["extra"] else ""])
        else:
            rows.append([c["id"], "derived", "footing_error" if c["id"] in w["perturb"] else "foots",
                         "filed value shifted by %d" % w["perturb"][c["id"]] if c["id"] in w["perturb"] else ""])
    write_csv("truth_cells.csv", ["cell_id", "kind", "truth_class", "note"], rows)
    write_csv("truth_rows.csv", ["cell_id", "loan_id", "change_kind", "detail"], sorted(w["truth_rows"], key=lambda r: (r[0], r[1])))


def main():
    for cfg in (MAIN, EXAMPLE):
        w = make(cfg)
        write(cfg, w)
        print("%s: wrote %d loans at filing, %d now, %d cells" % (cfg["prefix"] or "main", len(w["s0"]), len(w["s1"]), len(w["spec"]["cells"])))


if __name__ == "__main__":
    main()
