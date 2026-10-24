"""Shared loading for the four step scripts of project 58."""
from __future__ import annotations

import os

from _ledger_rules import flag_rows
from plant import Rand, apply_behavior, build, derive, load_spec, make_base, score, validate_spec

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")
SEEDS = (101, 102, 103, 104, 105)
LEVELS = ("naive", "tuned")


def demo_spec() -> dict:
    return load_spec(os.path.join(DATA, "demo_spec.json"))


def sprinkle(spec: dict, seed: int) -> dict:
    """The usual way to get bad data: build clean rows, then hit each row at random, once per failure.

    Every failure behavior in the spec is applied to each row with probability count / rows, independently,
    so one row can be hit twice. Look-alike behaviors are skipped, as they usually are. The only record kept
    in the file is an is_bad column. `hits` lists, per row, the failures the author applied to it. A file
    made this way does not carry that; step 3 uses it to show what the column hides.
    """
    s = validate_spec(dict(spec, seed=seed))
    failures = [b for b in s["behaviors"] if b["role"] == "positive"]
    rng = Rand(derive(seed, "sprinkle"))
    rngs = {b["id"]: Rand(derive(seed, "ops:" + b["id"])) for b in failures}
    rows, hits = [], []
    for row in make_base(s):
        cur, here, copies = row, [], []
        for b in failures:
            if rng.unit() >= b["count"] / s["rows"]:
                continue
            cur, copy, _, _ = apply_behavior(cur, b, rngs[b["id"]])
            if copy is None:
                here.append(b["id"])
            else:
                copies.append((b["id"], copy))
        rows.append(dict(cur, is_bad="1" if here else "0"))
        hits.append(here)
        for bid, copy in copies:
            rows.append(dict(copy, is_bad="1"))
            hits.append([bid])
    for n, r in enumerate(rows, 1):
        r["row_id"] = n
    return {"rows": rows, "hits": hits}


def boolean_key(made: dict) -> list:
    """The key the usual approach yields: every row with is_bad set, one behavior called is_bad."""
    return [{"row_id": r["row_id"], "behavior": "is_bad", "role": "positive"} for r in made["rows"] if r["is_bad"] == "1"]


__all__ = ["DATA", "OUT_DIR", "SEEDS", "LEVELS", "build", "boolean_key", "demo_spec", "flag_rows", "score", "sprinkle"]
