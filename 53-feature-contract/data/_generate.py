"""Generate the synthetic data for project 53: 90 deliveries ("batches") of model-input data, three
feeds, 100 rows each. Some deliveries carry a planted change to one field; some carry a harmless
change that a strict check could mistake for a problem.

Two parts are kept apart on purpose:
  PROCESS    how the values are drawn, and what each planted change does to them. This is the
             generative side. It never reads the contracts.
  CONTRACTS  the rules the tool checks, written as a data owner would write them: round numbers,
             wider than the values the process draws.
The truth label of each batch comes from the change that was planted, not from the tool.

Everything is seeded, so the files are byte-for-byte reproducible. Values are stored as the text a
CSV export would hold: an empty string is a null.

Run (from data/):  python3 _generate.py
Writes:  contract_credit_triage.json, contract_card_fraud.json, contract_aml_alerts.json,
         batches.jsonl, batch_truth.csv, example_batch.csv
"""
from __future__ import annotations

import csv
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 53
ROWS = 100
MAX_BAD_RATE = 0.02
NULL_ALLOWANCE = 0.05


def clip(v, lo, hi):
    return max(lo, min(hi, v))


# ---------------------------------------------------------------- PROCESS: how values are drawn
def fld(name, role, draw, fmt, nullable=False, bounds=(None, None)):
    return {"name": name, "role": role, "draw": draw, "fmt": fmt, "nullable": nullable, "bounds": bounds}


def ident(name, prefix):
    return fld(name, "id", lambda rng: rng.randint(100000, 999999), lambda v: "%s-%d" % (prefix, v))


def ratio(name, draw, nullable=False, bounds=(0, None)):
    return fld(name, "ratio", draw, lambda v: "%.4f" % v, nullable, bounds)


def usd(name, draw, nullable=False, bounds=(0, None)):
    return fld(name, "usd", draw, lambda v: "%.2f" % v, nullable, bounds)


def whole(name, role, draw, bounds=(0, None)):
    return fld(name, role, lambda rng: int(draw(rng)), str, False, bounds)


def enum(name, values, weights):
    return fld(name, "enum", lambda rng: rng.choices(values, weights)[0], str)


FEEDS = {
    "credit_triage_features": [
        ident("application_id", "APP"),
        ratio("dti_ratio", lambda rng: clip(rng.gauss(0.34, 0.10), 0.03, 1.2)),
        whole("fico_score", "score", lambda rng: clip(round(rng.gauss(700, 60)), 480, 840), (300, 850)),
        ratio("ltv_ratio", lambda rng: clip(rng.gauss(0.62, 0.15), 0.05, 1.1), nullable=True),
        usd("annual_income_usd", lambda rng: clip(rng.lognormvariate(11.0, 0.5), 12000, 2000000), nullable=True),
        enum("employment_status", ["employed", "self_employed", "retired", "student", "unemployed"], [60, 15, 15, 6, 4]),
        whole("months_on_book", "months", lambda rng: clip(rng.expovariate(1 / 70), 0, 590)),
    ],
    "card_fraud_features": [
        ident("txn_id", "TXN"),
        usd("txn_amount_usd", lambda rng: clip(rng.lognormvariate(3.8, 1.1), 0.5, 24000), bounds=(0.01, None)),
        enum("merchant_category", ["grocery", "fuel", "restaurants", "travel", "online_retail", "utilities", "health", "entertainment"],
             [25, 12, 18, 6, 20, 8, 6, 5]),
        whole("txn_count_24h", "count", lambda rng: clip(rng.expovariate(1 / 3), 0, 80)),
        whole("account_age_days", "days", lambda rng: rng.randint(30, 7000)),
        fld("is_international", "bool", lambda rng: rng.random() < 0.08, lambda v: "true" if v else "false"),
        ratio("device_risk_score", lambda rng: rng.betavariate(2, 6), nullable=True, bounds=(0, 1)),
    ],
    "aml_alert_features": [
        ident("alert_id", "ALT"),
        usd("txn_total_30d_usd", lambda rng: clip(rng.lognormvariate(8.7, 1.0), 50, 5000000)),
        ratio("cash_ratio", lambda rng: rng.betavariate(1.2, 4), bounds=(0, 1)),
        whole("counterparty_count_30d", "count", lambda rng: clip(rng.expovariate(1 / 12) + 1, 1, 900)),
        enum("customer_segment", ["retail", "small_business", "private"], [70, 25, 5]),
        whole("days_since_kyc_review", "days", lambda rng: rng.randint(0, 1095)),
        ratio("high_risk_geo_share", lambda rng: rng.betavariate(1, 12), nullable=True, bounds=(0, 1)),
    ],
}

NEW_VALUES = ["gig_worker", "crypto_merchant", "other_segment"]
INT_ROLES = ("score", "count", "days", "months")
NUM_ROLES = ("ratio", "usd") + INT_ROLES

# change kind, truth class, how many batches
QUOTA = [
    ("dropped_column", "bad", 4), ("renamed_column", "bad", 4), ("type_text", "bad", 5), ("fractional_int", "bad", 3),
    ("null_surge", "bad", 5), ("scale_percent", "bad", 5), ("sentinel_values", "bad", 5), ("new_category", "bad", 4),
    ("unit_cents", "bad", 4), ("unit_in_range", "bad", 5), ("null_zero_fill", "bad", 3),
    ("unchanged", "ok", 15), ("column_reorder", "ok", 5), ("extra_column", "ok", 5), ("nulls_within_allowance", "ok", 5),
    ("boundary_values", "ok", 4), ("int_as_decimal", "ok", 4), ("isolated_bad_rows", "ok", 5),
]


def make_cols(spec, rng):
    cols = {}
    for f in spec:
        cols[f["name"]] = [f["fmt"](f["draw"](rng)) for _ in range(ROWS)]
        if f["nullable"]:
            for i in rng.sample(range(ROWS), rng.randint(0, 3)):
                cols[f["name"]][i] = ""
    return cols


def to_percent(cols, name):
    cols[name] = [("%.2f" % (float(s) * 100)) if s else s for s in cols[name]]


def put(cols, name, idx, value):
    for i in idx:
        cols[name][i] = value


def plant(kind, spec, cols, order, rng):
    """Apply one change to cols/order in place. Returns (field, rows_changed)."""
    def pick(*roles):
        return rng.choice([f for f in spec if f["role"] in roles])

    def rows(k):
        return rng.sample(range(ROWS), k)

    if kind == "unchanged":
        return "", 0
    if kind == "dropped_column":
        name = pick("ratio", "usd", "enum", "bool", *INT_ROLES)["name"]
        del cols[name]
        order.remove(name)
        return name, ROWS
    if kind == "renamed_column":
        name = pick("ratio", "usd", "enum", "bool", *INT_ROLES)["name"]
        cols[name + "_v2"] = cols.pop(name)
        order[order.index(name)] = name + "_v2"
        return name, ROWS
    if kind == "type_text":
        f = pick("ratio", "usd")
        n = f["name"]
        cols[n] = [(("$%s" % format(float(s), ",.2f")) if f["role"] == "usd" else "%.1f%%" % (float(s) * 100)) if s else s for s in cols[n]]
        return n, sum(1 for s in cols[n] if s)
    if kind == "fractional_int":
        n = pick(*INT_ROLES)["name"]
        cols[n] = ["%s.%d" % (s, rng.randint(1, 9)) if s else s for s in cols[n]]
        return n, ROWS
    if kind == "null_surge":
        n = pick("ratio", "usd", "enum", *INT_ROLES)["name"]
        idx = rows(rng.randint(25, 40))
        changed = sum(1 for i in idx if cols[n][i] != "")
        put(cols, n, idx, "")
        return n, changed
    if kind == "scale_percent":
        n = pick("ratio")["name"]
        to_percent(cols, n)
        return n, sum(1 for s in cols[n] if s)
    if kind == "sentinel_values":
        n = pick(*NUM_ROLES)["name"]
        idx = rows(rng.randint(5, 8))
        changed = sum(1 for i in idx if cols[n][i] != "-999")
        put(cols, n, idx, "-999")
        return n, changed
    if kind == "new_category":
        n = pick("enum")["name"]
        idx = rows(rng.randint(15, 30))
        put(cols, n, idx, rng.choice(NEW_VALUES))
        return n, len(idx)
    if kind == "unit_cents":
        n = pick("usd")["name"]
        cols[n] = ["%.2f" % (float(s) * 100) if s else s for s in cols[n]]
        return n, sum(1 for s in cols[n] if s)
    if kind == "unit_in_range":
        f = pick("days", "months")
        n, div = f["name"], (7 if f["role"] == "days" else 12)
        cols[n] = [str(int(s) // div) for s in cols[n]]
        return n, ROWS
    if kind == "null_zero_fill":
        f = rng.choice([f for f in spec if f["nullable"]])
        idx = rows(rng.randint(15, 20))
        put(cols, f["name"], idx, "0")
        return f["name"], len(idx)
    if kind == "column_reorder":
        rng.shuffle(order)
        return "", 0
    if kind == "extra_column":
        extra = rng.choice(["load_batch_tag", "source_system", "ingest_note"])
        cols[extra] = ["run-%d" % rng.randint(1, 9)] * ROWS
        order.insert(rng.randint(0, len(order)), extra)
        return extra, 0
    if kind == "nulls_within_allowance":
        f = rng.choice([f for f in spec if f["nullable"]])
        cols[f["name"]] = [s if s else f["fmt"](f["draw"](rng)) for s in cols[f["name"]]]
        idx = rows(4)
        put(cols, f["name"], idx, "")
        return f["name"], len(idx)
    if kind == "boundary_values":
        f = rng.choice([f for f in spec if f["role"] in NUM_ROLES and any(b is not None for b in f["bounds"])])
        bound = rng.choice([b for b in f["bounds"] if b is not None])
        idx = rows(rng.randint(3, 5))
        put(cols, f["name"], idx, f["fmt"](bound))
        return f["name"], len(idx)
    if kind == "int_as_decimal":
        n = pick(*INT_ROLES)["name"]
        cols[n] = [s + ".0" for s in cols[n]]
        return n, ROWS
    if kind == "isolated_bad_rows":
        n = pick(*NUM_ROLES)["name"]
        idx = rows(rng.randint(1, 2))
        put(cols, n, idx, "99999999")
        return n, len(idx)
    raise ValueError(kind)


# ---------------------------------------------------------------- CONTRACTS: the rules
def num(name, typ, lo, hi, unit, max_null=None):
    d = {"name": name, "type": typ, "min": lo, "max": hi, "unit": unit}
    if max_null is not None:
        d["max_null_rate"] = max_null
    return d


def text(name, allowed=None, unit=None):
    d = {"name": name, "type": "string"}
    if allowed:
        d["allowed"] = allowed
    if unit:
        d["unit"] = unit
    return d


def contract(name, fields):
    return {"contract": name, "version": "1.0.0", "unexpected_columns": "warn", "max_bad_rate": MAX_BAD_RATE, "fields": fields}


CONTRACTS = {
    "credit_triage_features": ("contract_credit_triage.json", contract("credit_triage_features", [
        text("application_id"),
        num("dti_ratio", "number", 0, 1.5, "ratio of monthly debt to monthly income"),
        num("fico_score", "integer", 300, 850, "score points"),
        num("ltv_ratio", "number", 0, 1.5, "ratio of loan to collateral value", NULL_ALLOWANCE),
        num("annual_income_usd", "number", 0, 5000000, "US dollars per year", NULL_ALLOWANCE),
        text("employment_status", ["employed", "self_employed", "retired", "student", "unemployed"]),
        num("months_on_book", "integer", 0, 600, "months"),
    ])),
    "card_fraud_features": ("contract_card_fraud.json", contract("card_fraud_features", [
        text("txn_id"),
        num("txn_amount_usd", "number", 0.01, 25000, "US dollars"),
        text("merchant_category", ["grocery", "fuel", "restaurants", "travel", "online_retail", "utilities", "health", "entertainment"]),
        num("txn_count_24h", "integer", 0, 500, "transactions"),
        num("account_age_days", "integer", 0, 20000, "days"),
        {"name": "is_international", "type": "boolean"},
        num("device_risk_score", "number", 0, 1, "score from 0 to 1", NULL_ALLOWANCE),
    ])),
    "aml_alert_features": ("contract_aml_alerts.json", contract("aml_alert_features", [
        text("alert_id"),
        num("txn_total_30d_usd", "number", 0, 10000000, "US dollars"),
        num("cash_ratio", "number", 0, 1, "share of volume that is cash"),
        num("counterparty_count_30d", "integer", 0, 2000, "counterparties"),
        text("customer_segment", ["retail", "small_business", "private"]),
        num("days_since_kyc_review", "integer", 0, 3650, "days"),
        num("high_risk_geo_share", "number", 0, 1, "share of volume", NULL_ALLOWANCE),
    ])),
}


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    rng = random.Random(SEED)
    feeds = sorted(FEEDS)
    made = []
    for kind, truth, count in QUOTA:
        for _ in range(count):
            feed = rng.choice(feeds)
            spec = FEEDS[feed]
            cols = make_cols(spec, rng)
            order = [f["name"] for f in spec]
            field, changed = plant(kind, spec, cols, order, rng)
            made.append({"feed": feed, "kind": kind, "truth": truth, "field": field, "changed": changed,
                         "columns": order, "rows": [[cols[c][i] for c in order] for i in range(ROWS)]})
    rng.shuffle(made)
    for _feed, (fname, c) in sorted(CONTRACTS.items()):
        with open(os.path.join(HERE, fname), "w", encoding="utf-8") as fh:
            json.dump(c, fh, indent=1)
            fh.write("\n")
    with open(os.path.join(HERE, "batches.jsonl"), "w", encoding="utf-8") as fh:
        for i, b in enumerate(made, 1):
            fh.write(json.dumps({"batch_id": "BATCH-%03d" % i, "feed": b["feed"], "columns": b["columns"], "rows": b["rows"]}, sort_keys=True) + "\n")
    write_csv(os.path.join(HERE, "batch_truth.csv"), ["batch_id", "feed", "change_kind", "truth_class", "changed_field", "rows_changed"],
              [["BATCH-%03d" % i, b["feed"], b["kind"], b["truth"], b["field"], b["changed"]] for i, b in enumerate(made, 1)])
    # a worked example for the command line: a ratio field that started arriving as a percent
    spec = FEEDS["credit_triage_features"]
    cols = make_cols(spec, rng)
    to_percent(cols, "dti_ratio")
    order = [f["name"] for f in spec]
    write_csv(os.path.join(HERE, "example_batch.csv"), order, [[cols[c][i] for c in order] for i in range(ROWS)])
    print("wrote %d batches of %d rows" % (len(made), ROWS))


if __name__ == "__main__":
    main()
