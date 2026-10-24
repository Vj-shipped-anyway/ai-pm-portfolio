"""name_match_eval: score name matchers against a watchlist and sweep the alert threshold.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 name_match_eval.py --demo
    python3 name_match_eval.py score "Hasan Karimov" "Karimov, Hassan"
    python3 name_match_eval.py sweep WATCHLIST.csv CUSTOMERS.csv TRUTH.csv [--matcher exact|edit|tokens|tokens-flat]
                                     [--min-recall 0.85] [--max-false-alerts 0.10]

Exit status: 0 when the sweep ran and a threshold meets both targets, 1 when no threshold meets them,
2 for bad or malformed input.

Three matchers, each a plain function of two names, no model:
  exact   the normalised names are equal (score 0 or 1)
  edit    character edit similarity of the whole normalised name
  tokens  names split into words, each word folded to a spelling-insensitive key, words aligned in any
          order, initials credited, and each word weighted by how rare it is on the watchlist

Input files (CSV with a header row):
  watchlist  entity_id, listed_name          one row per listed name; several rows may share an entity
  customers  customer_id, name
  truth      customer_id, truth, entity_id   truth is match or clear; planted_as is optional

Names in non-Latin scripts are compared letter by letter as they are; nothing is transliterated.
"""
from __future__ import annotations

import argparse
import csv
import functools
import math
import os
import re
import sys
import unicodedata
from collections import Counter

MAX_NAME_CHARS = 200
MAX_PAIRS = 2_000_000
TOKEN_FLOOR = 0.6
INITIAL_CREDIT = 0.85
DEMO_THRESHOLD = 0.80
FINE = [round(i / 100, 2) for i in range(30, 101)]
GRID = [round(0.5 + 0.05 * i, 2) for i in range(11)]
MATCHERS = ("exact", "edit", "tokens", "tokens-flat")


class InputError(ValueError):
    """Bad or malformed input: the command line turns it into exit status 2."""


# ---------------------------------------------------------------- escaping for anything echoed
def escape_log(text, limit: int = 80) -> str:
    """Escape text from an input file or argument before it is printed, the way GitHub documents for
    workflow commands: % to %25, carriage return to %0D, newline to %0A, other control characters to %XX."""
    out = []
    for ch in str(text)[:limit]:
        o = ord(ch)
        if ch == "%":
            out.append("%25")
        elif ch == "\r":
            out.append("%0D")
        elif ch == "\n":
            out.append("%0A")
        elif unicodedata.category(ch) in ("Cc", "Zl", "Zp"):
            out.append("%%%02X" % o if o < 256 else "%%u%04X" % o)
        else:
            out.append(ch)
    return "".join(out) + ("..." if len(str(text)) > limit else "")


# ---------------------------------------------------------------- normalising and folding
_LETTERS = str.maketrans({"ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "ł": "l",
                          "đ": "d", "ð": "d", "þ": "th"})
_APOSTROPHES = {ord(c): None for c in "'’ʼ`´"}
_FOLD = [("ph", "f"), ("ck", "k"), ("kh", "h"), ("ou", "u"), ("oo", "u"), ("ee", "i"), ("ie", "i"),
         ("dj", "j"), ("q", "k"), ("w", "v"), ("y", "i")]


@functools.lru_cache(maxsize=None)
def normalize(name: str) -> str:
    """Lower case, accents and punctuation removed, apostrophes joined, hyphens and commas as spaces."""
    s = unicodedata.normalize("NFKD", name).casefold()
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.translate(_LETTERS).translate(_APOSTROPHES)
    s = "".join(c if c.isalnum() else " " for c in s)
    return " ".join(s.split())


@functools.lru_cache(maxsize=None)
def words(name: str) -> tuple:
    return tuple(normalize(name).split())


@functools.lru_cache(maxsize=None)
def fold(word: str) -> str:
    """A spelling-insensitive key for one normalised word: common transliteration pairs map to one form
    and doubled letters collapse. The table is short on purpose; it does not know every variant."""
    for src, dst in _FOLD:
        word = word.replace(src, dst)
    return re.sub(r"(.)\1+", r"\1", word)


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (insert, delete, substitute; a swap of two letters costs 2)."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def edit_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return 1.0 - edit_distance(a, b) / max(len(a), len(b))


@functools.lru_cache(maxsize=None)
def word_similarity(x: str, y: str) -> float:
    """Similarity of two normalised words: 1 when equal, a fixed credit for an initial against a word
    that starts with it, else folded edit similarity when it clears TOKEN_FLOOR, else 0."""
    if x == y:
        return 1.0
    short, long_ = (x, y) if len(x) <= len(y) else (y, x)
    if len(short) == 1:
        return INITIAL_CREDIT if long_[0] == short else 0.0
    fx, fy = fold(x), fold(y)
    if fx == fy:
        return 1.0
    sim = edit_similarity(fx, fy)
    return sim if sim >= TOKEN_FLOOR else 0.0


# ---------------------------------------------------------------- the three matchers
class ExactMatcher:
    name = "exact"

    def score(self, a: str, b: str) -> float:
        return 1.0 if normalize(a) == normalize(b) else 0.0


class EditMatcher:
    name = "edit"

    def score(self, a: str, b: str) -> float:
        return round(edit_similarity(normalize(a), normalize(b)), 6)


class TokenMatcher:
    """Weighted Dice over aligned words: sum of similarity x (weight_a + weight_b) for the matched pairs,
    divided by the total weight of both names. Weight is 1 + ln((N + 1) / (df + 1)) with df the number of
    listed names that contain the word (an initial counts the listed names with a word that starts with
    it). With rarity off every word weighs 1."""

    def __init__(self, listed_names, rarity: bool = True):
        self.name = "tokens" if rarity else "tokens-flat"
        self.rarity = rarity
        self.n = len(listed_names)
        self.df_word, self.df_initial = Counter(), Counter()
        for nm in listed_names:
            ws = words(nm)
            for w in {fold(w) for w in ws if len(w) > 1}:
                self.df_word[w] += 1
            for letter in {w[0] for w in ws}:
                self.df_initial[letter] += 1

    def weight(self, w: str) -> float:
        if not self.rarity:
            return 1.0
        df = self.df_initial[w] if len(w) == 1 else self.df_word[fold(w)]
        return 1.0 + math.log((self.n + 1) / (df + 1))

    def score(self, a: str, b: str) -> float:
        wa, wb = words(a), words(b)
        pairs = []
        for i, x in enumerate(wa):
            for j, y in enumerate(wb):
                s = word_similarity(x, y)
                if s > 0:
                    pairs.append((-s, i, j))
        pairs.sort()
        used_a, used_b, got = set(), set(), 0.0
        for neg, i, j in pairs:
            if i in used_a or j in used_b:
                continue
            used_a.add(i)
            used_b.add(j)
            got += -neg * (self.weight(wa[i]) + self.weight(wb[j]))
        total = sum(self.weight(w) for w in wa) + sum(self.weight(w) for w in wb)
        return round(got / total, 6)


def make_matcher(kind: str, listed_names):
    if kind == "exact":
        return ExactMatcher()
    if kind == "edit":
        return EditMatcher()
    if kind == "tokens":
        return TokenMatcher(listed_names)
    if kind == "tokens-flat":
        return TokenMatcher(listed_names, rarity=False)
    raise ValueError("unknown matcher: " + kind)


# ---------------------------------------------------------------- loading and checking input
def check_name(value, where: str) -> str:
    if not isinstance(value, str) or not normalize(value):
        raise InputError("%s: the name has no letters or digits" % where)
    if len(value) > MAX_NAME_CHARS:
        raise InputError("%s: the name is longer than %d characters" % (where, MAX_NAME_CHARS))
    return value


def read_rows(path: str, required: list) -> list:
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise InputError("%s: the file is empty" % escape_log(path))
            missing = [c for c in required if c not in reader.fieldnames]
            if missing:
                raise InputError("%s: missing column(s) %s" % (escape_log(path), ", ".join(missing)))
            rows = []
            for n, row in enumerate(reader, start=2):
                if None in row or any(v is None for v in row.values()):
                    raise InputError("%s: row %d has the wrong number of fields (truncated or extra)" % (escape_log(path), n))
                rows.append((n, row))
    except OSError as e:
        raise InputError("cannot read %s: %s" % (escape_log(path), e.strerror or "unreadable"))
    except UnicodeDecodeError:
        raise InputError("%s: not valid UTF-8" % escape_log(path))
    except csv.Error as e:
        raise InputError("%s: %s" % (escape_log(path), e))
    if not rows:
        raise InputError("%s: no data rows" % escape_log(path))
    return rows


def load_watchlist(path: str) -> list:
    out = []
    for n, r in read_rows(path, ["entity_id", "listed_name"]):
        if not r["entity_id"].strip():
            raise InputError("%s: row %d has an empty entity_id" % (escape_log(path), n))
        out.append({"entity_id": r["entity_id"].strip(), "name": check_name(r["listed_name"], "%s row %d" % (escape_log(path), n))})
    return out


def load_customers(path: str) -> list:
    out, seen = [], set()
    for n, r in read_rows(path, ["customer_id", "name"]):
        cid = r["customer_id"].strip()
        if not cid or cid in seen:
            raise InputError("%s: row %d has an empty or repeated customer_id" % (escape_log(path), n))
        seen.add(cid)
        out.append({"customer_id": cid, "name": check_name(r["name"], "%s row %d" % (escape_log(path), n))})
    return out


def load_truth(path: str) -> dict:
    out = {}
    for n, r in read_rows(path, ["customer_id", "truth", "entity_id"]):
        cid, truth, ent = r["customer_id"].strip(), r["truth"].strip(), r["entity_id"].strip()
        if truth not in ("match", "clear"):
            raise InputError("%s: row %d: truth must be match or clear" % (escape_log(path), n))
        if truth == "match" and not ent:
            raise InputError("%s: row %d: a match needs an entity_id" % (escape_log(path), n))
        if cid in out:
            raise InputError("%s: row %d repeats customer_id" % (escape_log(path), n))
        out[cid] = {"truth": truth, "entity_id": ent, "kind": r.get("planted_as", "").strip() or truth}
    return out


def load_all(watch_path: str, cust_path: str, truth_path: str):
    entries, customers, truth = load_watchlist(watch_path), load_customers(cust_path), load_truth(truth_path)
    ids = {c["customer_id"] for c in customers}
    absent = sorted(ids - set(truth))
    if absent:
        raise InputError("%d customer(s) have no truth row, first %s" % (len(absent), escape_log(absent[0])))
    extra = sorted(set(truth) - ids)
    if extra:
        raise InputError("%d truth row(s) name no customer, first %s" % (len(extra), escape_log(extra[0])))
    listed = {e["entity_id"] for e in entries}
    for cid in sorted(truth):
        if truth[cid]["truth"] == "match" and truth[cid]["entity_id"] not in listed:
            raise InputError("customer %s is a match for an entity that is not on the watchlist" % escape_log(cid))
    if len(entries) * len(customers) > MAX_PAIRS:
        raise InputError("%d customers x %d listed names is more than %d pairs; this prototype stops there"
                         % (len(customers), len(entries), MAX_PAIRS))
    return entries, customers, truth


# ---------------------------------------------------------------- evaluation
def evaluate(matcher, entries: list, customers: list, truth: dict) -> list:
    """One record per customer: its best score against any listed name (best), the entity that gave it,
    and, for a match, its best score against the entity it really is (best_true)."""
    records = []
    for c in customers:
        t = truth[c["customer_id"]]
        best, best_entity = -1.0, ""
        best_true = -1.0 if t["truth"] == "match" else None
        for e in entries:
            s = matcher.score(c["name"], e["name"])
            if s > best:
                best, best_entity = s, e["entity_id"]
            if best_true is not None and e["entity_id"] == t["entity_id"] and s > best_true:
                best_true = s
        records.append({"customer_id": c["customer_id"], "truth": t["truth"], "kind": t["kind"],
                        "best": best, "best_entity": best_entity, "best_true": best_true})
    return records


def metrics_at(records: list, threshold: float) -> dict:
    thr = threshold - 1e-9
    m = [r for r in records if r["truth"] == "match"]
    c = [r for r in records if r["truth"] == "clear"]
    return {"threshold": threshold, "matches": len(m), "clear": len(c),
            "caught": sum(1 for r in m if r["best_true"] >= thr),
            "false_alerts": sum(1 for r in c if r["best"] >= thr),
            "alerts": sum(1 for r in records if r["best"] >= thr)}


def by_kind_at(records: list, threshold: float) -> dict:
    """{kind: (hits, total)}: matches counted when caught, clear names counted when they alert."""
    thr = threshold - 1e-9
    out = {}
    for r in records:
        hit = (r["best_true"] if r["truth"] == "match" else r["best"]) >= thr
        h, n = out.get(r["kind"], (0, 0))
        out[r["kind"]] = (h + hit, n + 1)
    return out


def lowest_threshold_with_false_rate_at_most(records: list, max_rate: float):
    """The lowest threshold in FINE whose false-alert rate is at most max_rate (so recall is highest), or None."""
    for t in FINE:
        m = metrics_at(records, t)
        if m["clear"] and m["false_alerts"] / m["clear"] <= max_rate + 1e-12:
            return m
    return None


def highest_threshold_with_recall_at_least(records: list, min_recall: float):
    """The highest threshold in FINE whose recall is at least min_recall (so false alerts are fewest), or None."""
    for t in reversed(FINE):
        m = metrics_at(records, t)
        if m["matches"] and m["caught"] / m["matches"] >= min_recall - 1e-12:
            return m
    return None


def pct(a: int, b: int) -> str:
    return "n/a" if b == 0 else "%.1f%%" % (100.0 * a / b)


def rate_text(x: float) -> str:
    return "%.1f%%" % (100.0 * x)


def false_alerts_per_true_hit(false_rate: float, recall: float, base_rate: float):
    """Modeled: false alerts per true hit when matches are base_rate of all customers. None when recall is 0."""
    if recall <= 0:
        return None
    return false_rate * (1 - base_rate) / (recall * base_rate)


# ---------------------------------------------------------------- command line
def format_sweep(kind: str, records: list, n_entries: int, min_recall: float, max_fa: float):
    """Returns (text, ok)."""
    n_match = sum(1 for r in records if r["truth"] == "match")
    n_clear = len(records) - n_match
    lines = ["matcher: %s   watchlist: %d names   customers: %d (%d match, %d clear)" % (kind, n_entries, len(records), n_match, n_clear)]
    if n_match == 0 or n_clear == 0:
        lines.append("truth has no %s rows, so %s is not defined; nothing to sweep" % (
            "match" if n_match == 0 else "clear", "recall" if n_match == 0 else "the false-alert rate"))
        return "\n".join(lines), False
    lines.append("threshold  caught  recall  false alerts  false rate  alerts")
    for t in GRID:
        m = metrics_at(records, t)
        lines.append("%9.2f  %6d  %6s  %12d  %10s  %6d" % (t, m["caught"], pct(m["caught"], n_match), m["false_alerts"],
                                                          pct(m["false_alerts"], n_clear), m["alerts"]))
    if metrics_at(records, 0.5)["alerts"] == 0:
        lines.append("no customer scored 0.50 or more against any listed name")
    a = lowest_threshold_with_false_rate_at_most(records, max_fa)
    b = highest_threshold_with_recall_at_least(records, min_recall)
    if a:
        lines.append("false alerts <= %s of clear names: lowest threshold %.2f, recall %s" % (rate_text(max_fa), a["threshold"], pct(a["caught"], n_match)))
    else:
        lines.append("false alerts <= %s of clear names: not reachable at any threshold from 0.30 to 1.00" % rate_text(max_fa))
    if b:
        lines.append("recall >= %s: highest threshold %.2f, false alerts %s of clear names" % (rate_text(min_recall), b["threshold"], pct(b["false_alerts"], n_clear)))
    else:
        lines.append("recall >= %s: not reachable at any threshold from 0.30 to 1.00" % rate_text(min_recall))
    ok = bool(b) and b["false_alerts"] / n_clear <= max_fa + 1e-12
    lines.append("both targets met at one threshold: %s" % ("yes" if ok else "no"))
    return "\n".join(lines), ok


def run_sweep(args) -> int:
    for label, v in (("--min-recall", args.min_recall), ("--max-false-alerts", args.max_false_alerts)):
        if not 0.0 <= v <= 1.0:
            raise InputError("%s must be between 0 and 1" % label)
    entries, customers, truth = load_all(args.watchlist, args.customers, args.truth)
    matcher = make_matcher(args.matcher, [e["name"] for e in entries])
    records = evaluate(matcher, entries, customers, truth)
    text, ok = format_sweep(args.matcher, records, len(entries), args.min_recall, args.max_false_alerts)
    print(text)
    return 0 if ok else 1


def run_score(args) -> int:
    for label, v in (("first name", args.a), ("second name", args.b)):
        check_name(v, label)
    print("a: %s -> %s" % (escape_log(args.a), normalize(args.a)))
    print("b: %s -> %s" % (escape_log(args.b), normalize(args.b)))
    print("exact %.2f   edit %.2f   tokens %.2f (equal word weights; no watchlist given)" % (
        ExactMatcher().score(args.a, args.b), EditMatcher().score(args.a, args.b),
        TokenMatcher([], rarity=False).score(args.a, args.b)))
    return 0


def run_demo() -> int:
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    entries, customers, truth = load_all(os.path.join(d, "example_watchlist.csv"), os.path.join(d, "example_customers.csv"),
                                         os.path.join(d, "example_truth.csv"))
    n_match = sum(1 for t in truth.values() if t["truth"] == "match")
    print("sample: %d names screened against %d listed names; %d are the same party as a listed entity, %d are not"
          % (len(customers), len(entries), n_match, len(customers) - n_match))
    for kind in ("edit", "tokens"):
        m = metrics_at(evaluate(make_matcher(kind, [e["name"] for e in entries]), entries, customers, truth), DEMO_THRESHOLD)
        print("%-6s at %.2f: caught %d of %d, false alerts %d of %d" % (kind, DEMO_THRESHOLD, m["caught"], m["matches"], m["false_alerts"], m["clear"]))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="name_match_eval")
    ap.add_argument("--demo", action="store_true", help="run the bundled sample (data/example_*.csv)")
    sub = ap.add_subparsers(dest="cmd")
    sc = sub.add_parser("score", help="score two names with the three matchers")
    sc.add_argument("a")
    sc.add_argument("b")
    sw = sub.add_parser("sweep", help="sweep the threshold over a watchlist, customers and truth")
    sw.add_argument("watchlist")
    sw.add_argument("customers")
    sw.add_argument("truth")
    sw.add_argument("--matcher", choices=MATCHERS, default="tokens")
    sw.add_argument("--min-recall", type=float, default=0.85)
    sw.add_argument("--max-false-alerts", type=float, default=0.10)
    a = ap.parse_args(argv)
    try:
        if a.demo:
            return run_demo()
        if a.cmd == "sweep":
            return run_sweep(a)
        if a.cmd == "score":
            return run_score(a)
    except InputError as e:
        print("input error: %s" % e, file=sys.stderr)
        return 2
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
