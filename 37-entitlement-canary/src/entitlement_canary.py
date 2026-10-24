"""entitlement_canary: leak tests for a retrieval system. A canary is a (user, document) pair where the
user may not open the document, plus a query built to retrieve it. The tool builds a pack of canaries
from an access export, then checks what the retrieval system returned for each one. Standard library
only. Python 3.9 or newer.

Command line (from src/):
    python3 entitlement_canary.py --demo
    python3 entitlement_canary.py build-pack ACCESS.json [--out PACK.csv] [--seed N] [--min-per-source N]
                                                         [--quota STRATUM=N ...]
    python3 entitlement_canary.py check ACCESS.json PACK.csv RESULTS.csv [--min-per-source N]
                                                         [--fail-on block|review|never] [--format text|github]

Access export (JSON): {"groups": [{"parent", "child"}], "users": [{"user_id", "direct_groups": []}],
  "documents": [{"doc_id", "title", "source", "acl": [], "acl_at_index": [] (optional)}]}.
  Members of a child group are members of its parent. An ACL entry that starts with "-" is a deny and
  wins over any allow. A document with no allow entry can be opened by nobody.
Results (CSV, written by your own test harness): canary_id, returned_doc_ids (";" separated),
  primed ("yes" when the harness ran the control query first), control_returned_doc_ids.

How a canary is run: when the pack names a prime_user, the harness asks that user's query first (the
control), then asks it as user_id (the probe) and records the probe's results in returned_doc_ids.

Exit status: 0 when the decision is below --fail-on, 1 when it is at or above it, 2 for bad or
malformed input. BLOCK means a user was returned a document they may not open. REVIEW means no leak
was seen but the pack could not test everything (see the NOTE lines). There is no model in this file.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys

STRATA = ("stale_acl", "nested_deny", "direct_deny", "ordinary")
DEFAULT_QUOTAS = {"stale_acl": 10, "nested_deny": 15, "direct_deny": 15, "ordinary": 20}
DECISION_RANK = {"ALLOW": 0, "REVIEW": 1, "BLOCK": 2}
PACK_COLUMNS = ["canary_id", "user_id", "doc_id", "query", "stratum", "source", "prime_user"]
RESULT_COLUMNS = ["canary_id", "returned_doc_ids", "primed", "control_returned_doc_ids"]
SHOWN = 5


# ---------------------------------------------------------------- the access export
def _strings(value) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def check_access(data) -> None:
    """Raise ValueError when the export lacks what the resolver reads, so bad input exits 2."""
    if not isinstance(data, dict):
        raise ValueError(f"access export: expected a JSON object, got {type(data).__name__}")
    for key in ("groups", "users", "documents"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"access export: `{key}` must be a list")
    for g in data["groups"]:
        if not (isinstance(g, dict) and isinstance(g.get("parent"), str) and isinstance(g.get("child"), str)):
            raise ValueError("access export: every group needs string `parent` and `child`")
    for u in data["users"]:
        if not (isinstance(u, dict) and isinstance(u.get("user_id"), str) and _strings(u.get("direct_groups"))):
            raise ValueError("access export: every user needs a string `user_id` and a list `direct_groups`")
    for d in data["documents"]:
        if not (isinstance(d, dict) and all(isinstance(d.get(k), str) for k in ("doc_id", "title", "source"))
                and _strings(d.get("acl")) and (d.get("acl_at_index") is None or _strings(d.get("acl_at_index")))):
            raise ValueError("access export: every document needs string `doc_id`, `title`, `source` and a list `acl`")
    for key, rows in (("user_id", data["users"]), ("doc_id", data["documents"])):
        ids = [r[key] for r in rows]
        if len(ids) != len(set(ids)):
            raise ValueError(f"access export: duplicate {key}")


def index_access(data: dict) -> dict:
    parents: dict = {}
    for g in data["groups"]:
        parents.setdefault(g["child"], []).append(g["parent"])
    direct = {u["user_id"]: u["direct_groups"] for u in data["users"]}
    names = {g["parent"] for g in data["groups"]} | {g["child"] for g in data["groups"]}
    for groups in direct.values():
        names.update(groups)
    return {"parents": parents, "direct": direct, "docs": {d["doc_id"]: d for d in data["documents"]},
            "users": sorted(direct), "group_names": names, "closure_cache": {}}


def closure(ix: dict, user: str) -> set:
    """Every group the user is in: the direct groups and all their ancestors. Walks up, and stops on a cycle."""
    cache = ix["closure_cache"]
    if user not in cache:
        seen, stack = set(), list(ix["direct"].get(user, []))
        while stack:
            g = stack.pop()
            if g not in seen:
                seen.add(g)
                stack.extend(ix["parents"].get(g, []))
        cache[user] = seen
    return cache[user]


def split_acl(acl: list) -> tuple:
    return [g for g in acl if not g.startswith("-")], [g[1:] for g in acl if g.startswith("-")]


def can_open(ix: dict, user: str, acl: list) -> bool:
    groups = closure(ix, user)
    allow, deny = split_acl(acl)
    return any(g in groups for g in allow) and not any(g in groups for g in deny)


def stratum_of(ix: dict, user: str, doc: dict):
    """Why the user cannot open the document, or None when they can."""
    if can_open(ix, user, doc["acl"]):
        return None
    index_copy = doc.get("acl_at_index")
    if index_copy is not None and can_open(ix, user, index_copy):
        return "stale_acl"
    groups = closure(ix, user)
    allow, deny = split_acl(doc["acl"])
    denied = [g for g in deny if g in groups]
    if denied and any(g in groups for g in allow):
        return "direct_deny" if any(g in ix["direct"][user] for g in denied) else "nested_deny"
    return "ordinary"


def reason_for(ix: dict, user: str, acl: list) -> str:
    denied = sorted(g for g in split_acl(acl)[1] if g in closure(ix, user))
    return f"an ACL entry denies {denied[0]}" if denied else "none of the user's groups is on the ACL"


# ---------------------------------------------------------------- building a pack
def closed_pairs(data: dict) -> list:
    """Every (user, doc_id, stratum) where the user cannot open the document, in sorted order."""
    ix = index_access(data)
    out = []
    for user in ix["users"]:
        for doc_id in sorted(ix["docs"]):
            s = stratum_of(ix, user, ix["docs"][doc_id])
            if s:
                out.append((user, doc_id, s))
    return out


def make_canaries(data: dict, chosen: list) -> list:
    """Turn chosen (user, doc_id, stratum) triples into pack rows. The query is the document title; the
    prime user is the user who may open the document and can open the most documents, so a change that
    narrows one group's access does not blind the control."""
    ix = index_access(data)
    reach = {u: sum(1 for d in ix["docs"].values() if can_open(ix, u, d["acl"])) for u in ix["users"]}
    rows = []
    for i, (user, doc_id, s) in enumerate(sorted(chosen, key=lambda p: (STRATA.index(p[2]) if p[2] in STRATA else len(STRATA), p[0], p[1]))):
        doc = ix["docs"][doc_id]
        openers = [u for u in ix["users"] if u != user and can_open(ix, u, doc["acl"])]
        prime = min(openers, key=lambda u: (-reach[u], u)) if openers else ""
        rows.append({"canary_id": "CAN-%03d" % (i + 1), "user_id": user, "doc_id": doc_id, "query": doc["title"],
                     "stratum": s, "source": doc["source"], "prime_user": prime})
    return rows


def build_pack(data: dict, quotas=None, min_per_source: int = 3, seed: int = 37) -> list:
    """A stratified pack: a quota of canaries per stratum, then enough extra canaries that every source
    has at least min_per_source (when the source has that many closed pairs)."""
    check_access(data)
    quotas = DEFAULT_QUOTAS if quotas is None else quotas
    ix = index_access(data)
    pairs = closed_pairs(data)
    if not pairs:
        raise ValueError("no user is shut out of any document, so no canary can be built")
    rng = random.Random(seed)
    chosen, taken = [], set()
    for s in STRATA:
        pool = [p for p in pairs if p[2] == s]
        for p in rng.sample(pool, min(quotas.get(s, 0), len(pool))):
            chosen.append(p)
            taken.add((p[0], p[1]))
    for src in sorted({d["source"] for d in ix["docs"].values()}):
        have = sum(1 for p in chosen if ix["docs"][p[1]]["source"] == src)
        pool = [p for p in pairs if ix["docs"][p[1]]["source"] == src and (p[0], p[1]) not in taken]
        for p in rng.sample(pool, min(max(0, min_per_source - have), len(pool))):
            chosen.append(p)
            taken.add((p[0], p[1]))
    return make_canaries(data, chosen)


# ---------------------------------------------------------------- files
def read_rows(path: str, required: list) -> list:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: file is empty")
        missing = [c for c in required if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path}: missing column {', '.join(missing)}")
        return [{c: (row.get(c) or "").strip() for c in required} for row in reader]


def load_pack(path: str) -> list:
    rows = read_rows(path, PACK_COLUMNS)
    if not rows:
        raise ValueError(f"{path}: the pack has no canaries")
    ids = [r["canary_id"] for r in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"{path}: canary_id must be present and unique")
    for r in rows:
        if not r["user_id"] or not r["doc_id"]:
            raise ValueError(f"{path}: canary {r['canary_id']!r} needs user_id and doc_id")
    return rows


def load_results(path: str) -> list:
    rows = read_rows(path, RESULT_COLUMNS)
    ids = [r["canary_id"] for r in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"{path}: canary_id must be present and unique")
    for r in rows:
        if r["primed"] not in ("yes", "no"):
            raise ValueError(f"{path}: `primed` must be yes or no, got {r['primed']!r} for {r['canary_id']!r}")
    return rows


def split_ids(text: str) -> list:
    return [x.strip() for x in text.split(";") if x.strip()]


def write_pack(rows: list, path) -> None:
    fh = open(path, "w", newline="", encoding="utf-8") if path else sys.stdout
    try:
        w = csv.DictWriter(fh, fieldnames=PACK_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    finally:
        if path:
            fh.close()


# ---------------------------------------------------------------- the check
def evaluate(data: dict, pack: list, results: list, min_per_source: int = 1) -> dict:
    """Score what the retrieval system returned. Every returned document is checked against the
    resolver, not only the canary's target, so a leak of a different document is caught too."""
    check_access(data)
    ix = index_access(data)
    by_id = {r["canary_id"]: r for r in results}
    stray = sorted(set(by_id) - {c["canary_id"] for c in pack})
    if stray:
        raise ValueError(f"results name canaries that are not in the pack: {', '.join(stray[:SHOWN])}")
    rep = {"leaks": [], "retired": [], "inert": [], "unprimed": [], "orphans": [], "not_run": [], "unverified": [],
           "ran": 0, "total": len(pack), "documents": len(ix["docs"]), "users": len(ix["users"]),
           "groups": len(ix["group_names"]), "strata": {}, "uncovered": {}}
    per_source: dict = {}
    for c in pack:
        cid, user, doc_id = c["canary_id"], c["user_id"], c["doc_id"]
        rep["strata"][c["stratum"]] = rep["strata"].get(c["stratum"], 0) + 1
        if user not in ix["direct"] or doc_id not in ix["docs"]:
            rep["orphans"].append(cid)
            continue
        doc = ix["docs"][doc_id]
        per_source[doc["source"]] = per_source.get(doc["source"], 0) + 1
        r = by_id.get(cid)
        if r is None:
            rep["not_run"].append(cid)
            continue
        rep["ran"] += 1
        bad, unknown = [], []
        for returned in split_ids(r["returned_doc_ids"]):
            if returned not in ix["docs"]:
                unknown.append(returned)
            elif not can_open(ix, user, ix["docs"][returned]["acl"]):
                bad.append(returned)
        if bad:
            rep["leaks"].append({"canary_id": cid, "user_id": user, "stratum": c["stratum"], "docs": bad,
                                 "title": ix["docs"][bad[0]]["title"], "reason": reason_for(ix, user, ix["docs"][bad[0]]["acl"])})
        if unknown:
            rep["unverified"].append(cid)
        if can_open(ix, user, doc["acl"]):
            rep["retired"].append(cid)
        if c["prime_user"]:
            if r["primed"] != "yes":
                rep["unprimed"].append(cid)
            elif doc_id not in split_ids(r["control_returned_doc_ids"]):
                rep["inert"].append(cid)
    if rep["ran"] == 0:
        raise ValueError("no canary in the pack has a result row, so nothing was tested")
    for src in sorted({d["source"] for d in ix["docs"].values()}):
        if per_source.get(src, 0) < min_per_source:
            rep["uncovered"][src] = per_source.get(src, 0)
    notes = ("inert", "unprimed", "orphans", "not_run", "unverified", "uncovered")
    rep["decision"] = "BLOCK" if rep["leaks"] else "REVIEW" if any(rep[k] for k in notes) else "ALLOW"
    return rep


# ---------------------------------------------------------------- output
def escape_annotation(text: str) -> str:
    """Escape a workflow-command message the way GitHub documents, so input text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def safe(text, limit: int = 80) -> str:
    """Make a value from the input fit on one log line."""
    s = "".join(ch if ch.isprintable() else "\\u%04x" % ord(ch) for ch in str(text))
    return s if len(s) <= limit else s[:limit - 3] + "..."


def _ids(ids: list, clean) -> str:
    shown = ", ".join(clean(i) for i in ids[:SHOWN])
    return shown + (f" and {len(ids) - SHOWN} more" if len(ids) > SHOWN else "")


def _leak_line(leak: dict, clean) -> str:
    title = f' "{clean(leak["title"])}"' if len(leak["docs"]) == 1 else ""
    return (f"{clean(leak['canary_id'])} [{clean(leak['stratum'])}] {clean(leak['user_id'])} was returned "
            f"{_ids(leak['docs'], clean)}{title}: {clean(leak['reason'])}")


def _notes(rep: dict, clean) -> list:
    out = []
    if rep["inert"]:
        out.append(f"inert canaries ({len(rep['inert'])}): the control query did not return the target, so a clean probe proves nothing: {_ids(rep['inert'], clean)}")
    if rep["unprimed"]:
        out.append(f"canaries run without the control query ({len(rep['unprimed'])}): a cache shared between users cannot show here: {_ids(rep['unprimed'], clean)}")
    if rep["orphans"]:
        out.append(f"canaries naming a user or document missing from the access export ({len(rep['orphans'])}): {_ids(rep['orphans'], clean)}")
    if rep["not_run"]:
        out.append(f"canaries with no result row ({len(rep['not_run'])}): {_ids(rep['not_run'], clean)}")
    if rep["unverified"]:
        out.append(f"results naming a document missing from the access export ({len(rep['unverified'])} canaries): {_ids(rep['unverified'], clean)}")
    if rep["uncovered"]:
        out.append("sources with too few canaries: " + ", ".join(f"{clean(s)} {n}" for s, n in sorted(rep["uncovered"].items())))
    return out


def render(rep: dict, fmt: str) -> str:
    lines = []
    if fmt == "github":
        for leak in rep["leaks"]:
            lines.append("::error title=entitlement-canary leak::" + escape_annotation(_leak_line(leak, str)))
        for note in _notes(rep, str):
            lines.append("::warning title=entitlement-canary::" + escape_annotation(note))
        lines.append(f"::notice title=entitlement-canary::decision {rep['decision']}; {len(rep['leaks'])} leaks in {rep['ran']} canaries run")
        return "\n".join(lines)
    strata = sorted(rep["strata"].items(), key=lambda kv: (STRATA.index(kv[0]) if kv[0] in STRATA else len(STRATA), kv[0]))
    lines.append(f"access: {rep['documents']} documents, {rep['users']} users, {rep['groups']} groups")
    lines.append(f"pack: {rep['total']} canaries (" + ", ".join(f"{safe(k)} {v}" for k, v in strata) + ")")
    for leak in rep["leaks"][:10]:
        lines.append("LEAK " + _leak_line(leak, safe))
    if len(rep["leaks"]) > 10:
        lines.append(f"... and {len(rep['leaks']) - 10} more canaries leaked")
    for note in _notes(rep, safe):
        lines.append("NOTE " + note)
    lines.append(f"canaries run {rep['ran']} of {rep['total']}; leaks {len(rep['leaks'])}; retired (the user may now open the target) {len(rep['retired'])}; "
                 f"inert {len(rep['inert'])}; unprimed {len(rep['unprimed'])}")
    lines.append(f"decision: {rep['decision']}")
    return "\n".join(lines)


# ---------------------------------------------------------------- command line
def _oneline(e: Exception) -> str:
    return (str(e).splitlines() or [type(e).__name__])[0]


def run_check(access_path, pack_path, results_path, fail_on, fmt, min_per_source) -> int:
    try:
        with open(access_path, encoding="utf-8") as fh:
            data = json.load(fh)
        rep = evaluate(data, load_pack(pack_path), load_results(results_path), min_per_source)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, csv.Error) as e:
        print(f"input error: {_oneline(e)}", file=sys.stderr)
        return 2
    print(render(rep, fmt))
    if fail_on == "never":
        return 0
    return 1 if DECISION_RANK[rep["decision"]] >= DECISION_RANK[{"block": "BLOCK", "review": "REVIEW"}[fail_on]] else 0


def run_build(access_path, out_path, seed, min_per_source, quota_args) -> int:
    try:
        quotas = dict(DEFAULT_QUOTAS)
        for item in quota_args or []:
            name, _, count = item.partition("=")
            if name not in STRATA or not count.isdigit():
                raise ValueError(f"--quota expects STRATUM=N with STRATUM one of {', '.join(STRATA)}, got {item!r}")
            quotas[name] = int(count)
        with open(access_path, encoding="utf-8") as fh:
            data = json.load(fh)
        pack = build_pack(data, quotas, min_per_source, seed)
        write_pack(pack, out_path)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        print(f"input error: {_oneline(e)}", file=sys.stderr)
        return 2
    if out_path:
        print(f"wrote {len(pack)} canaries to {out_path}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="entitlement_canary")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_*)")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build-pack", help="build a stratified canary pack from an access export")
    b.add_argument("access")
    b.add_argument("--out", help="write the pack here (default: standard output)")
    b.add_argument("--seed", type=int, default=37)
    b.add_argument("--min-per-source", type=int, default=3)
    b.add_argument("--quota", action="append", help="STRATUM=N, repeatable; defaults " + ", ".join(f"{k} {v}" for k, v in DEFAULT_QUOTAS.items()))
    c = sub.add_parser("check", help="check what the retrieval system returned for each canary")
    c.add_argument("access")
    c.add_argument("pack")
    c.add_argument("results")
    c.add_argument("--min-per-source", type=int, default=1)
    c.add_argument("--fail-on", choices=["block", "review", "never"], default="block")
    c.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_access.json"), os.path.join(d, "example_pack.csv"),
                         os.path.join(d, "example_results.csv"), "never", "text", 1)
    if a.cmd == "check":
        return run_check(a.access, a.pack, a.results, a.fail_on, a.format, a.min_per_source)
    if a.cmd == "build-pack":
        return run_build(a.access, a.out, a.seed, a.min_per_source, a.quota)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
