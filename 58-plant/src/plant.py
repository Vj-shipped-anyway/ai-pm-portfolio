"""plant - synthetic data with an answer key.

Two jobs, both on the standard library only:

  generate   read a spec (a seed, columns, planted behaviors), write the data, the answer key and a manifest
  score      compare the rows a checker flagged with the key, behavior by behavior

A behavior is a named failure (role "positive": the checker should flag it) or a named look-alike
(role "negative": the checker should leave it alone). Every planted row is listed in the key with its
behavior, role and the exact change made. Rows that are not in the key are clean by construction.
The key is a separate file; the data file carries no label column.

Run:  python3 plant.py --demo
      python3 plant.py generate SPEC.json --out DIR
      python3 plant.py score DIR/NAME FLAGS.csv [--min-recall 0.8]

Exit codes: 0 done, 1 a positive behavior fell under --min-recall, 2 the input could not be used.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import random
import re
import sys

NAME_RE = re.compile(r"[a-z][a-z0-9_]{0,39}")
TEMPLATE_RE = re.compile(r"\{([a-z][a-z0-9_]{0,39})\}")
MAX_ROWS = 100000
MAX_TEXT = 500
ROLES = ("positive", "negative")
TRUTH_FIELDS = ["row_id", "behavior", "role", "effect", "detail", "source_row_id"]
HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_SPEC = os.path.join(HERE, "..", "data", "demo_spec.json")


class SpecError(ValueError):
    """The spec, key or flags file cannot be used. The command line turns it into exit 2."""


def clean(value) -> str:
    """Escape control characters, so an untrusted string stays on one line in any log."""
    return str(value).encode("unicode_escape").decode("ascii")


# ---------------------------------------------------------------- validation
def _need(ok, msg: str) -> None:
    if not ok:
        raise SpecError(msg)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v) -> bool:
    if _is_int(v):
        return abs(v) <= 10 ** 9
    return isinstance(v, float) and math.isfinite(v) and abs(v) <= 1e9


def _int(v, label: str, lo: int, hi: int) -> int:
    _need(_is_int(v) and lo <= v <= hi, f"{label} must be an integer from {lo} to {hi}")
    return v


def _text(v, label: str) -> str:
    _need(isinstance(v, str) and len(v) <= MAX_TEXT, f"{label} must be text of at most {MAX_TEXT} characters")
    return v


def _name(v, label: str) -> str:
    _need(isinstance(v, str) and NAME_RE.fullmatch(v) is not None,
          f"{label} must be lowercase letters, digits and underscores, start with a letter, and be at most 40 characters")
    return v


def _list(v, label: str, lo: int, hi: int) -> list:
    _need(isinstance(v, list) and lo <= len(v) <= hi, f"{label} must be a list of {lo} to {hi} items")
    return v


def _keys(d: dict, required: tuple, optional: tuple, label: str) -> None:
    for k in required:
        _need(k in d, f"{label} is missing '{k}'")
    for k in d:
        _need(k in required or k in optional, f"{label} has an unknown key '{clean(k)[:40]}'")


def _template(v, label: str, names: set) -> str:
    _text(v, label)
    for m in TEMPLATE_RE.finditer(v):
        _need(m.group(1) in names, f"{label} refers to {{{m.group(1)}}}, which is not a column")
    return v


def _one_or_many(v, label: str, check) -> list:
    items = v if isinstance(v, list) else [v]
    _need(1 <= len(items) <= 20, f"{label} must be one value or a list of 1 to 20")
    return [check(x, label) for x in items]


def _column(c, label: str, seen: dict) -> dict:
    _need(isinstance(c, dict) and "name" in c and "kind" in c, f"{label} must be an object with 'name' and 'kind'")
    name = _name(c["name"], f"{label}.name")
    _need(name != "row_id" and name not in seen, f"{label}.name is repeated or reserved")
    kind = c["kind"]
    out = {"name": name, "kind": kind}
    if kind == "sequence":
        _keys(c, ("name", "kind"), ("prefix", "width"), label)
        out["prefix"] = _text(c.get("prefix", ""), f"{label}.prefix")
        _need(len(out["prefix"]) <= 10, f"{label}.prefix must be at most 10 characters")
        out["width"] = _int(c.get("width", 5), f"{label}.width", 1, 12)
    elif kind == "choice":
        _keys(c, ("name", "kind", "values"), ("weights",), label)
        out["values"] = [_text(v, f"{label}.values") for v in _list(c["values"], f"{label}.values", 1, 200)]
        w = c.get("weights")
        if w is not None:
            w = [_int(x, f"{label}.weights", 1, 1000) for x in _list(w, f"{label}.weights", len(out["values"]), len(out["values"]))]
        out["weights"] = w
    elif kind == "int_range":
        _keys(c, ("name", "kind", "min", "max"), (), label)
        out["min"] = _int(c["min"], f"{label}.min", -10 ** 9, 10 ** 9)
        out["max"] = _int(c["max"], f"{label}.max", -10 ** 9, 10 ** 9)
        _need(out["min"] <= out["max"], f"{label}.min must not exceed max")
    elif kind == "int_offset":
        _keys(c, ("name", "kind", "of", "choices"), (), label)
        _need(isinstance(c["of"], str) and seen.get(c["of"], {}).get("kind") in ("int_range", "int_offset"),
              f"{label}.of must name an earlier integer column")
        out["of"] = c["of"]
        out["choices"] = [_int(x, f"{label}.choices", -1000, 1000) for x in _list(c["choices"], f"{label}.choices", 1, 20)]
    elif kind == "by_column":
        _keys(c, ("name", "kind", "of", "ranges"), (), label)
        _need(isinstance(c["of"], str) and seen.get(c["of"], {}).get("kind") == "choice", f"{label}.of must name an earlier choice column")
        _need(isinstance(c["ranges"], dict) and set(c["ranges"]) == set(seen[c["of"]]["values"]),
              f"{label}.ranges needs exactly one [low, high] pair per value of '{c['of']}'")
        out["of"] = c["of"]
        out["ranges"] = {}
        for k, r in c["ranges"].items():
            r = _list(r, f"{label}.ranges", 2, 2)
            _need(_is_num(r[0]) and _is_num(r[1]) and 0 <= r[0] <= r[1], f"{label}.ranges pairs must be numbers with 0 <= low <= high")
            out["ranges"][k] = [r[0], r[1]]
    else:
        raise SpecError(f"{label}.kind must be one of sequence, choice, int_range, int_offset, by_column")
    return out


def _op(o, label: str, kinds: dict) -> dict:
    _need(isinstance(o, dict) and "op" in o, f"{label} must be an object with 'op'")
    op, names = o["op"], set(kinds)
    if op == "duplicate":
        _keys(o, ("op",), ("set",), label)
        s = o.get("set", {})
        _need(isinstance(s, dict) and len(s) <= 10 and all(k in kinds for k in s), f"{label}.set must map column names to text")
        return {"op": op, "set": {k: _template(t, f"{label}.set", names) for k, t in s.items()}}
    _need(op in ("scale", "shift", "set", "append"), f"{label}.op must be one of scale, shift, set, append, duplicate")
    _need(isinstance(o.get("column"), str) and o["column"] in kinds, f"{label}.column must name a column")
    col = o["column"]
    if op == "scale":
        _keys(o, ("op", "column", "factor"), (), label)
        _need(kinds[col] == "by_column", f"{label}.column must be a by_column column")
        _need(_is_num(o["factor"]) and o["factor"] not in (0, 1) and abs(o["factor"]) <= 10 ** 6, f"{label}.factor must be a number other than 0 and 1")
        return {"op": op, "column": col, "factor": o["factor"]}
    if op == "shift":
        _keys(o, ("op", "column", "delta"), (), label)
        _need(kinds[col] in ("int_range", "int_offset"), f"{label}.column must be an integer column")
        deltas = _one_or_many(o["delta"], f"{label}.delta", lambda x, lb: _int(x, lb, -10 ** 6, 10 ** 6))
        _need(all(d != 0 for d in deltas), f"{label}.delta must not contain 0")
        return {"op": op, "column": col, "delta": deltas}
    key = "value" if op == "set" else "text"
    _keys(o, ("op", "column", key), (), label)
    return {"op": op, "column": col, key: _one_or_many(o[key], f"{label}.{key}", lambda x, lb: _template(x, lb, names))}


def validate_spec(spec) -> dict:
    """Return a normalized copy of the spec, or raise SpecError with a one-line reason."""
    _need(isinstance(spec, dict), "the spec must be a JSON object")
    _keys(spec, ("name", "seed", "rows", "columns", "behaviors"), (), "spec")
    out = {"name": _name(spec["name"], "name"), "seed": _int(spec["seed"], "seed", 0, 2 ** 62),
           "rows": _int(spec["rows"], "rows", 1, MAX_ROWS), "columns": [], "behaviors": []}
    seen = {}
    for i, c in enumerate(_list(spec["columns"], "columns", 1, 40)):
        col = _column(c, f"columns[{i}]", seen)
        seen[col["name"]] = col
        out["columns"].append(col)
    kinds = {n: c["kind"] for n, c in seen.items()}
    ids = set()
    for i, b in enumerate(_list(spec["behaviors"], "behaviors", 1, 40)):
        label = f"behaviors[{i}]"
        _need(isinstance(b, dict), f"{label} must be an object")
        _keys(b, ("id", "role", "count", "ops"), (), label)
        bid = _name(b["id"], f"{label}.id")
        _need(bid not in ids, f"{label}.id is repeated")
        ids.add(bid)
        _need(b["role"] in ROLES, f"{label}.role must be positive or negative")
        ops = [_op(o, f"{label}.ops[{j}]", kinds) for j, o in enumerate(_list(b["ops"], f"{label}.ops", 1, 8))]
        _need(len(ops) == 1 or all(o["op"] != "duplicate" for o in ops), f"{label}: a duplicate op must be the only op")
        out["behaviors"].append({"id": bid, "role": b["role"], "count": _int(b["count"], f"{label}.count", 1, MAX_ROWS), "ops": ops})
    asked = sum(b["count"] for b in out["behaviors"])
    _need(asked <= out["rows"], f"the behaviors ask for {asked} rows but the spec has {out['rows']}")
    return out


# ---------------------------------------------------------------- generation
def derive(seed: int, label: str) -> int:
    """A separate seed per purpose, so adding a behavior does not move the draws of the others."""
    return int(hashlib.sha256(f"{seed}:{label}".encode("utf-8")).hexdigest()[:16], 16)


class Rand:
    """Every draw comes from random.random(), whose stream does not change between Python versions."""

    def __init__(self, seed: int):
        self._r = random.Random(seed)

    def unit(self) -> float:
        return self._r.random()

    def pick(self, items: list):
        return items[int(self.unit() * len(items))]

    def weighted(self, items: list, weights: list):
        x = self.unit() * sum(weights)
        for item, w in zip(items, weights):
            x -= w
            if x < 0:
                return item
        return items[-1]

    def shuffle(self, items: list) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = int(self.unit() * (i + 1))
            items[i], items[j] = items[j], items[i]


def make_base(spec: dict) -> list:
    """The clean rows, before any behavior is planted. Values are text, as they will be written."""
    rng = Rand(derive(spec["seed"], "base"))
    rows = []
    for i in range(spec["rows"]):
        row = {}
        for c in spec["columns"]:
            k = c["kind"]
            if k == "sequence":
                v = c["prefix"] + str(i + 1).zfill(c["width"])
            elif k == "choice":
                v = rng.weighted(c["values"], c["weights"]) if c["weights"] else rng.pick(c["values"])
            elif k == "int_range":
                v = str(c["min"] + int(rng.unit() * (c["max"] - c["min"] + 1)))
            elif k == "int_offset":
                v = str(int(row[c["of"]]) + rng.pick(c["choices"]))
            else:
                lo, hi = c["ranges"][row[c["of"]]]
                v = "%.2f" % (lo + (hi - lo) * rng.unit())
            row[c["name"]] = v
        rows.append(row)
    return rows


def _fill(text: str, row: dict) -> str:
    return TEMPLATE_RE.sub(lambda m: row[m.group(1)], text)


def apply_behavior(row: dict, beh: dict, rng: Rand):
    """Plant one behavior on a row. Returns (row, copy, effect, detail); copy is None unless the op is duplicate."""
    new, effects, details = dict(row), [], []
    for o in beh["ops"]:
        op = o["op"]
        if op == "duplicate":
            copy = dict(row)
            for col, tmpl in sorted(o["set"].items()):
                copy[col] = _fill(tmpl, row)
            sets = "".join(f" and set {col} to {json.dumps(t)}" for col, t in sorted(o["set"].items()))
            changed = "; ".join(f"{col}: {json.dumps(row[col])} -> {json.dumps(copy[col])}" for col in sorted(o["set"]))
            return new, copy, "duplicate" + sets, changed or "exact copy"
        col, before = o["column"], new[o["column"]]
        if op == "scale":
            new[col] = "%.2f" % round(float(before) * o["factor"], 2)
            effects.append(f"scale {col} by {json.dumps(o['factor'])}")
        elif op == "shift":
            delta = rng.pick(o["delta"])
            new[col] = str(int(before) + delta)
            effects.append(f"shift {col} by {delta}")
        else:
            chosen = rng.pick(o["value" if op == "set" else "text"])
            new[col] = _fill(chosen, new) if op == "set" else before + _fill(chosen, new)
            effects.append(f"{op} {col} {'to' if op == 'set' else 'with'} {json.dumps(chosen)}")
        details.append(f"{col}: {json.dumps(before)} -> {json.dumps(new[col])}")
    _need(new != row, f"behavior {beh['id']}: its ops changed nothing on a row; use values that differ from the base data")
    return new, None, "; ".join(effects), "; ".join(details)


def _csv_bytes(fields: list, records: list) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(fields)
    for r in records:
        w.writerow([r[f] for f in fields])
    return buf.getvalue().encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(spec_in) -> dict:
    """Plant the spec. Returns the validated spec, rows, key, manifest and the bytes of the three files."""
    spec = validate_spec(spec_in)
    base = make_base(spec)
    order = list(range(len(base)))
    Rand(derive(spec["seed"], "pick")).shuffle(order)
    plan, cursor = {}, 0
    for b in spec["behaviors"]:
        for i in order[cursor:cursor + b["count"]]:
            plan[i] = b
        cursor += b["count"]
    rngs = {b["id"]: Rand(derive(spec["seed"], "behavior:" + b["id"])) for b in spec["behaviors"]}
    rows, planted = [], []
    for i, row in enumerate(base):
        b = plan.get(i)
        if b is None:
            rows.append(row)
            continue
        new, copy, effect, detail = apply_behavior(row, b, rngs[b["id"]])
        rows.append(new)
        if copy is not None:
            rows.append(copy)
        planted.append((len(rows), b, effect, detail, copy is not None))
    for n, r in enumerate(rows, 1):
        r["row_id"] = n
    truth = [{"row_id": pos, "behavior": b["id"], "role": b["role"], "effect": effect, "detail": detail,
              "source_row_id": pos - 1 if dup else ""} for pos, b, effect, detail, dup in planted]
    data_bytes = _csv_bytes(["row_id"] + [c["name"] for c in spec["columns"]], rows)
    truth_bytes = _csv_bytes(TRUTH_FIELDS, truth)
    manifest = {"tool": "plant", "name": spec["name"], "seed": spec["seed"], "rows": len(rows), "base_rows": len(base),
                "planted_rows": len(truth), "spec_sha256": _sha(json.dumps(spec, sort_keys=True, separators=(",", ":")).encode("utf-8")),
                "data_sha256": _sha(data_bytes), "truth_sha256": _sha(truth_bytes),
                "behaviors": [{"id": b["id"], "role": b["role"], "count": b["count"],
                               "distinct_effects": len({t["effect"] for t in truth if t["behavior"] == b["id"]})} for b in spec["behaviors"]]}
    manifest_bytes = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode("utf-8")
    return {"spec": spec, "rows": rows, "truth": truth, "manifest": manifest,
            "data_bytes": data_bytes, "truth_bytes": truth_bytes, "manifest_bytes": manifest_bytes}


def write_outputs(result: dict, out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, result["spec"]["name"])
    paths = []
    for suffix, blob in (("_data.csv", result["data_bytes"]), ("_truth.csv", result["truth_bytes"]), ("_manifest.json", result["manifest_bytes"])):
        with open(stem + suffix, "wb") as fh:
            fh.write(blob)
        paths.append(stem + suffix)
    return paths


# ---------------------------------------------------------------- scoring
def _read_csv(blob: bytes, label: str, needed: tuple) -> list:
    text = blob.decode("utf-8")
    if "\x00" in text:
        raise csv.Error(f"{label}: contains a NUL byte")   # csv.reader refused NUL only before Python 3.11
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    for f in needed:
        _need(f in fields, f"{label} has no '{f}' column")
    rows = list(reader)
    _need(all(None not in r for r in rows), f"{label}: a row has more values than the header has columns")
    return rows


def _row_id(cell, label: str, n_rows: int) -> int:
    _need(isinstance(cell, str) and cell.strip().isdigit() and cell.strip().isascii(), f"{label}: row_id must be a whole number")
    value = int(cell.strip())
    _need(1 <= value <= n_rows, f"{label}: row_id {value} is outside 1 to {n_rows}")
    return value


def read_key(prefix: str):
    """Read PREFIX_truth.csv and PREFIX_manifest.json. Returns (truth, n_rows, manifest)."""
    with open(prefix + "_manifest.json", "rb") as fh:
        manifest = json.loads(fh.read().decode("utf-8"))
    with open(prefix + "_truth.csv", "rb") as fh:
        blob = fh.read()
    _need(isinstance(manifest, dict) and _is_int(manifest.get("rows")) and manifest["rows"] >= 1, "the manifest has no usable 'rows'")
    _need(manifest.get("truth_sha256") == _sha(blob), "the truth file does not match its manifest (truth_sha256)")
    truth, seen = [], set()
    for r in _read_csv(blob, "truth file", ("row_id", "behavior", "role")):
        rid = _row_id(r["row_id"], "truth file", manifest["rows"])
        _need(rid not in seen, f"truth file: row_id {rid} is listed twice")
        _need(r["role"] in ROLES and isinstance(r["behavior"], str) and r["behavior"] != "", "truth file: each row needs a behavior and a role of positive or negative")
        seen.add(rid)
        truth.append({"row_id": rid, "behavior": r["behavior"], "role": r["role"]})
    return truth, manifest["rows"], manifest


def read_flags(path: str, n_rows: int):
    """Read a flags CSV with a row_id column. Returns (set of flagged ids, number of repeated ids ignored)."""
    with open(path, "rb") as fh:
        rows = _read_csv(fh.read(), "flags file", ("row_id",))
    ids = [_row_id(r["row_id"], "flags file", n_rows) for r in rows]
    return set(ids), len(ids) - len(set(ids))


def score(truth: list, n_rows: int, flagged: set) -> dict:
    """Score flagged row ids against the key. truth items are {row_id, behavior, role}."""
    by_id = {t["row_id"] for t in truth}
    table = {}
    for t in truth:
        e = table.setdefault((t["behavior"], t["role"]), {"behavior": t["behavior"], "role": t["role"], "planted": 0, "flagged": 0})
        e["planted"] += 1
        e["flagged"] += t["row_id"] in flagged
    behaviors = sorted(table.values(), key=lambda e: (e["role"] != "positive", e["behavior"]))
    pos = [e for e in behaviors if e["role"] == "positive"]
    neg = [e for e in behaviors if e["role"] == "negative"]
    found, planted = sum(e["flagged"] for e in pos), sum(e["planted"] for e in pos)
    return {"behaviors": behaviors, "positives": planted, "found": found,
            "recall": found / planted if planted else None,
            "look_alikes": sum(e["planted"] for e in neg), "look_alikes_flagged": sum(e["flagged"] for e in neg),
            "clean": n_rows - len(by_id), "clean_flagged": len([i for i in flagged if i not in by_id]),
            "flagged": len(flagged), "precision": found / len(flagged) if flagged else None}


def ratio(x) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def weakest(sc: dict):
    """The positive behavior with the lowest recall (ties go to the name that sorts first), or None."""
    pos = [e for e in sc["behaviors"] if e["role"] == "positive"]
    return min(pos, key=lambda e: (e["flagged"] / e["planted"], e["behavior"])) if pos else None


def score_lines(sc: dict) -> list:
    lines = [f"  {'behavior':<30} {'role':<9} {'planted':>7} {'flagged':>7}"]
    for e in sc["behaviors"]:
        lines.append(f"  {clean(e['behavior']):<30} {e['role']:<9} {e['planted']:>7} {e['flagged']:>7}")
    lines.append(f"found {sc['found']} of {sc['positives']} planted failures (recall {ratio(sc['recall'])})")
    lines.append(f"flagged {sc['look_alikes_flagged']} of {sc['look_alikes']} planted look-alikes")
    lines.append(f"flagged {sc['clean_flagged']} of {sc['clean']} clean rows")
    lines.append(f"flagged {sc['flagged']} rows in all (precision {ratio(sc['precision'])})")
    if not sc["flagged"]:
        lines.append("no rows were flagged, so every planted failure is missed")
    return lines


# ---------------------------------------------------------------- command line
def load_spec(path: str):
    with open(path, "rb") as fh:
        blob = fh.read()
    try:
        return json.loads(blob.decode("utf-8"))
    except ValueError as e:
        raise SpecError(f"{clean(path)} is not valid JSON ({clean(e)})")


def cmd_generate(spec_path: str, out_dir: str) -> int:
    result = build(load_spec(spec_path))
    m = result["manifest"]
    paths = write_outputs(result, out_dir)
    print(f"spec {m['name']} seed {m['seed']}: {m['rows']} rows, {m['planted_rows']} in the answer key, data sha256 {m['data_sha256'][:8]}")
    for p in paths:
        print(f"wrote {clean(p)}")
    return 0


def cmd_score(prefix: str, flags_path: str, min_recall) -> int:
    truth, n_rows, manifest = read_key(prefix)
    flagged, repeats = read_flags(flags_path, n_rows)
    sc = score(truth, n_rows, flagged)
    print(f"key {clean(manifest.get('name', '?'))}: {n_rows} rows, {len(truth)} in the key")
    for line in score_lines(sc):
        print(line)
    if repeats:
        print(f"{repeats} repeated row_id values in the flags file were counted once")
    if min_recall is None:
        return 0
    low = [e for e in sc["behaviors"] if e["role"] == "positive" and e["flagged"] / e["planted"] < min_recall]
    for e in low:
        print(f"below --min-recall {min_recall}: {clean(e['behavior'])} found {e['flagged']} of {e['planted']}")
    return 1 if low else 0


def run_demo() -> int:
    from _ledger_rules import flag_rows
    result = build(load_spec(DEMO_SPEC))
    m = result["manifest"]
    sc = score(result["truth"], m["rows"], set(flag_rows(result["rows"], "naive")))
    print(f"spec {m['name']} seed {m['seed']}: {m['rows']} rows, {len(m['behaviors'])} behaviors, {m['planted_rows']} rows in the answer key, data sha256 {m['data_sha256'][:8]}")
    print(f"naive checker flagged {sc['flagged']} rows: found {sc['found']} of {sc['positives']} planted failures, "
          f"flagged {sc['look_alikes_flagged']} of {sc['look_alikes']} planted look-alikes and {sc['clean_flagged']} of {sc['clean']} clean rows")
    w = weakest(sc)
    print(f"weakest behavior: {w['behavior']}, found {w['flagged']} of {w['planted']}")
    return 0


def _fraction(text: str) -> float:
    try:
        x = float(text)
    except ValueError:
        x = float("nan")
    if not 0 <= x <= 1:
        raise argparse.ArgumentTypeError("must be a number from 0 to 1")
    return x


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="plant", description="Synthetic data with an answer key.")
    ap.add_argument("--demo", action="store_true", help="plant the bundled spec (data/demo_spec.json) and score the stand-in checker against it")
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("generate", help="write data, key and manifest for a spec")
    g.add_argument("spec")
    g.add_argument("--out", required=True, help="directory for NAME_data.csv, NAME_truth.csv and NAME_manifest.json")
    s = sub.add_parser("score", help="score a flags file against a key")
    s.add_argument("key", help="path prefix of the key, e.g. out/demo for out/demo_truth.csv and out/demo_manifest.json")
    s.add_argument("flags", help="CSV with a row_id column")
    s.add_argument("--min-recall", type=_fraction, default=None, help="exit 1 when a positive behavior is found less often than this")
    a = ap.parse_args(argv)
    try:
        if a.demo:
            return run_demo()
        if a.cmd == "generate":
            return cmd_generate(a.spec, a.out)
        if a.cmd == "score":
            return cmd_score(a.key, a.flags, a.min_recall)
    except (OSError, ValueError, csv.Error, RecursionError) as e:
        print(f"input error: {clean(e)}", file=sys.stderr)
        return 2
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
