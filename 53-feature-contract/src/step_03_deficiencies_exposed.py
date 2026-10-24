"""Step 3 - Where each part fails when used alone.

The contract gate has two layers. The structure layer asks whether the columns are there and whether
each value parses as its declared type. The value layer asks whether nulls, ranges and allowed values
hold, with a tolerance for isolated bad rows. Each is scored alone on the same 90 batches, and the
value layer is also run with zero tolerance to show what the tolerance is for.

KNOWN LIMIT, left in on purpose: a change that leaves every value inside the declared type, range
and null rate passes both layers, and step 4 does not catch it either. This step prints which ones.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from collections import Counter

from common import load_batches, load_contracts, basic_check, check_batch, decision_from, VALUE_KINDS, STRUCTURE_KINDS

contracts, batches = load_contracts(), load_batches()
bad = [b for b in batches if b["truth"] == "bad"]
ok = [b for b in batches if b["truth"] == "ok"]


def layer(kinds, tolerance=None):
    """Decision per batch from findings of the given kinds only; tolerance replaces the contract's when given."""
    out = {}
    for b in batches:
        c = contracts[b["feed"]]
        if tolerance is not None:
            c = dict(c, max_bad_rate=tolerance)
        out[b["batch_id"]] = decision_from(check_batch(c, b["columns"], b["rows"]), kinds)
    return out


def score(name, got):
    stopped = sum(1 for b in bad if got[b["batch_id"]] == "FAIL")
    blocked = [b for b in ok if got[b["batch_id"]] == "FAIL"]
    print(f"  {name}")
    print(f"    bad batches stopped: {stopped} of {len(bad)}")
    print(f"    harmless batches blocked: {len(blocked)} of {len(ok)}" + (f" ({', '.join(f'{k} {v}' for k, v in sorted(Counter(b['kind'] for b in blocked).items()))})" if blocked else ""))


tolerance = ", ".join(f"{t:.1%}" for t in sorted({c["max_bad_rate"] for c in contracts.values()}))
print("STEP 3 - each part alone")
score("header and type check (step 2)", {b["batch_id"]: basic_check(contracts[b["feed"]], b["columns"], b["rows"]) for b in batches})
by_structure = layer(STRUCTURE_KINDS)
score("structure layer alone (columns present, values parse as the declared type)", by_structure)
by_values_strict = layer(VALUE_KINDS, 0.0)
score("value layer alone, zero tolerance (nulls, range, allowed values)", by_values_strict)
by_values = layer(VALUE_KINDS)
score(f"value layer alone, {tolerance} tolerance", by_values)
missed = [b for b in bad if by_structure[b["batch_id"]] != "FAIL" and by_values[b["batch_id"]] != "FAIL"]
print(f"  bad batches that pass both layers: {len(missed)} of {len(bad)}")
print("  by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(b['kind'] for b in missed).items())))
print("  The structure layer cannot see a value that parses; the value layer cannot see a column that is gone or text where a number should be.")
print("  KNOWN LIMIT: a change that stays inside the declared type, range and null rate passes both layers.")
