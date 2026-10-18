"""Step 1 - Before CorpusGate: retrieval with no access control.

A modeled bank's internal assistant answers questions from a document corpus. This script plays
the status quo: for every query it returns the top 5 documents by relevance and ignores who is
asking. It then counts, against the ground truth, how many of those results the asker may not
read.

The retriever is a plain TF-IDF scorer written with the standard library. It is a stub, not a
vector model, and no model is used anywhere in this repo. Everything is synthetic: the generator
(data/_generate.py) decided every ACL, so the truth is known.

Shared building blocks that later steps and the app import:
  load_all, tokenize, build_index, rank_query, rank_all     data loading and the stub retriever
  effective_groups, acl_allows                              group-tree and ACL rules
  status_quo                                                the numbers printed below

Run (from src/):
    python3 step_01_no_access_control.py

Output: a readable summary, plus out/step_01_results.csv.
"""

from __future__ import annotations

import csv
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

K = 5                                   # results returned per query
# Must match data/_generate.py. Dates are constants, not the clock.
INDEXED_AT = "2026-06-01T02:00"         # the index copy of every ACL was taken here
SYNC_AT = "2026-09-30T00:00"            # the last time source ACLs were pulled
LABELS = ["public", "internal", "confidential", "restricted"]
STOPWORDS = {"the", "a", "an", "and", "for", "of", "to", "is", "on", "in", "when", "how", "do", "we", "what",
             "it", "this", "with", "by", "before", "after", "are", "was", "be", "at", "or", "each", "also", "see"}


def pct(a: float, b: float) -> str:
    return f"{100.0 * a / b:.1f}%" if b else "n/a"


def split_list(s: str) -> list:
    return [x for x in s.split(";") if x]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _read(path: Path) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_all(data_dir: Path = DATA_DIR) -> dict:
    """Load every CSV into plain dicts. No pandas needed."""
    docs = {}
    for r in _read(data_dir / "documents.csv"):
        r["acl_now"] = split_list(r["acl_groups"])
        r["acl_index"] = split_list(r["acl_groups_at_index"])
        r["index_text"] = r["title"] + " " + r["text"]
        docs[r["doc_id"]] = r
    users = {}
    for r in _read(data_dir / "users.csv"):
        r["direct"] = split_list(r["direct_groups"])
        users[r["user_id"]] = r
    edges = [(r["parent"], r["child"]) for r in _read(data_dir / "groups.csv")]
    parents = defaultdict(set)
    for p, c in edges:
        parents[c].add(p)
    queries = _read(data_dir / "queries.csv")
    for q in queries:
        q["relevant"] = split_list(q["relevant_doc_ids"])
    canaries = _read(data_dir / "canary_queries.csv")
    changes = _read(data_dir / "acl_changes.csv")
    truth = {r["user_id"]: set(split_list(r["entitled_doc_ids"])) for r in _read(data_dir / "entitlement_truth.csv")}
    return {"docs": docs, "doc_ids": sorted(docs), "users": users, "edges": edges, "parents": dict(parents),
            "queries": queries, "canaries": canaries, "changes": changes, "truth": truth}


# ---------------------------------------------------------------------------
# The stub retriever: TF-IDF cosine, standard library only
# ---------------------------------------------------------------------------
def tokenize(text: str) -> list:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


def build_index(texts: dict) -> dict:
    """texts: doc_id -> text. Returns an inverted index with smoothed IDF."""
    n = len(texts)
    tfs, df = {}, Counter()
    for d in sorted(texts):
        c = Counter(tokenize(texts[d]))
        tfs[d] = c
        for w in c:
            df[w] += 1
    idf = {w: math.log((n + 1) / (df[w] + 1)) + 1.0 for w in df}
    postings, norm = defaultdict(list), {}
    for d in sorted(tfs):
        wts = {w: (1.0 + math.log(c)) * idf[w] for w, c in tfs[d].items()}
        norm[d] = math.sqrt(sum(v * v for v in wts.values()))
        for w in sorted(wts):
            postings[w].append((d, wts[w]))
    return {"idf": idf, "postings": postings, "norm": norm}


def rank_query(index: dict, text: str) -> list:
    """Every document with a non-zero score, best first. Ties break on doc_id."""
    q = Counter(tokenize(text))
    qw = {w: (1.0 + math.log(c)) * index["idf"][w] for w, c in q.items() if w in index["idf"]}
    qn = math.sqrt(sum(v * v for v in qw.values()))
    if not qn:
        return []
    scores = defaultdict(float)
    for w in sorted(qw):
        for d, v in index["postings"][w]:
            scores[d] += qw[w] * v
    out = [(d, s / (qn * index["norm"][d])) for d, s in scores.items()]
    out.sort(key=lambda x: (-round(x[1], 12), x[0]))
    return out


def rank_all(data: dict, index: dict) -> dict:
    """query_id -> full ranking (list of (doc_id, score))."""
    return {q["query_id"]: rank_query(index, q["text"]) for q in data["queries"]}


# ---------------------------------------------------------------------------
# Group tree and ACL rules (shared building blocks)
# ---------------------------------------------------------------------------
def effective_groups(data: dict, user_id: str, nested: bool = True) -> set:
    """The user's direct groups plus, if nested, every ancestor group (members of a child group
    are members of its parent)."""
    seen = set(data["users"][user_id]["direct"])
    if not nested:
        return seen
    stack = list(seen)
    while stack:
        g = stack.pop()
        for p in sorted(data["parents"].get(g, ())):
            if p not in seen:
                seen.add(p)
                stack.append(p)
    return seen


def acl_allows(groups: set, acl: list) -> bool:
    """Allow if the user is in any allow group and in no deny group (deny entries start with '-')."""
    allow = {g for g in acl if not g.startswith("-")}
    deny = {g[1:] for g in acl if g.startswith("-")}
    return bool(groups & allow) and not (groups & deny)


# ---------------------------------------------------------------------------
# Scoring helpers shared by the steps
# ---------------------------------------------------------------------------
def top_k(ranking: list, k: int = K, allowed: set = None) -> list:
    """First k doc_ids of a ranking, optionally pre-filtered to an allowed set."""
    out = []
    for d, _ in ranking:
        if allowed is None or d in allowed:
            out.append(d)
            if len(out) == k:
                break
    return out


def leak_stats(data: dict, results: dict) -> dict:
    """results: query_id -> list of doc_ids returned. Leak = result the asker may not read."""
    truth = data["truth"]
    n_res = leaked = q_leak = 0
    by_label = Counter()
    for q in data["queries"]:
        rs = results[q["query_id"]]
        bad = [d for d in rs if d not in truth[q["user_id"]]]
        n_res += len(rs)
        leaked += len(bad)
        q_leak += 1 if bad else 0
        for d in bad:
            by_label[data["docs"][d]["sensitivity_label_truth"]] += 1
    return {"results": n_res, "leaked": leaked, "queries_with_leak": q_leak, "by_label": dict(by_label)}


def status_quo(data: dict = None) -> dict:
    data = data or load_all()
    index = build_index({d: r["index_text"] for d, r in data["docs"].items()})
    rank = rank_all(data, index)
    results = {qid: top_k(r) for qid, r in rank.items()}
    s = leak_stats(data, results)
    s["n_queries"] = len(data["queries"])
    s["rank"], s["results_by_query"], s["index"] = rank, results, index
    return s


def data_shape(data: dict) -> list:
    """Lines describing the shipped data (printed so the data README can cite them)."""
    docs, users = data["docs"], data["users"]
    labels = Counter(r["sensitivity_label_truth"] for r in docs.values())
    mis = sum(1 for r in docs.values() if r["sensitivity"] != r["sensitivity_label_truth"])
    pii = Counter(r["pii_truth"] for r in docs.values() if r["pii_truth"] != "none")
    groups = {g for e in data["edges"] for g in e}

    def depth(g):
        ps = data["parents"].get(g, ())
        return 1 + max((depth(p) for p in ps), default=0)

    cont = sum(1 for u in users.values() if u["role"] == "contractor")
    changed = data["changes"]
    rev = sum(1 for c in changed if _is_revoke(data, c))
    after = sum(1 for c in changed if c["changed_at"] > SYNC_AT)
    strata = Counter(c["stratum"] for c in data["canaries"])
    deny = sum(1 for r in docs.values() if any(g.startswith("-") for g in r["acl_now"]))
    return [
        f"  Documents: {len(docs)} (true label: " + ", ".join(f"{l} {labels[l]}" for l in LABELS) + f"); {mis} carry a wrong label",
        f"  Users: {len(users)} ({cont} contractors); groups: {len(groups)}, nested up to {max(depth(g) for g in groups)} levels deep; "
        f"documents with an explicit deny entry: {deny}",
        f"  Queries: {len(data['queries'])} asked by {len({q['user_id'] for q in data['queries']})} different users",
        f"  Personal data injected into {sum(pii.values())} documents (" + ", ".join(f"{k} {pii[k]}" for k in sorted(pii)) + ")",
        f"  ACL changes after indexing: {len(changed)} (revokes {rev}, grants {len(changed) - rev}); {after} of them after the last sync",
        f"  Canary pack: {len(data['canaries'])} user and document pairs (" + ", ".join(f"{k} {strata[k]}" for k in sorted(strata)) + ")",
    ]


def _is_revoke(data: dict, change: dict) -> bool:
    """A change is a revoke when some user lost access under it (checked with the group rules)."""
    old, new = split_list(change["from_acl"]), split_list(change["to_acl"])
    for u in data["users"]:
        g = effective_groups(data, u)
        if acl_allows(g, old) and not acl_allows(g, new):
            return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    data = load_all()
    s = status_quo(data)
    docs = data["docs"]

    print("STEP 1 - BEFORE CORPUSGATE: RETRIEVAL WITH NO ACCESS CONTROL")
    print("The retriever is a stub, not a model: plain TF-IDF in the standard library. No model is used anywhere in this repo.")
    print("All data is synthetic; the truth is known because the generator decided every ACL.")
    print()
    print("DATA SHAPE")
    for line in data_shape(data):
        print(line)
    print()
    print(f"Each of the {s['n_queries']} queries returns its top {K} documents by relevance. The asker is ignored.")
    print()
    print("RESULT")
    print(f"  Results returned:                       {s['results']:,}")
    print(f"  Results the asker may not read:         {s['leaked']} of {s['results']:,} ({pct(s['leaked'], s['results'])})")
    print(f"  Queries with at least one such result:  {s['queries_with_leak']} of {s['n_queries']} ({pct(s['queries_with_leak'], s['n_queries'])})")
    bl = s["by_label"]
    print("  By the label the document really has:  " + ", ".join(f"{l} {bl.get(l, 0)}" for l in LABELS))
    print("  No error is raised and nothing is logged: nothing in this setup notices.")
    print()
    shown = None
    for q in data["queries"]:
        for d in s["results_by_query"][q["query_id"]]:
            if d not in data["truth"][q["user_id"]] and docs[d]["sensitivity_label_truth"] == "restricted":
                shown = (q, d)
                break
        if shown:
            break
    if shown:
        q, d = shown
        u = data["users"][q["user_id"]]
        print("Example (first query by id that returned a restricted document the asker may not read):")
        print(f"  {q['query_id']} asked by {u['user_id']} ({u['dept']}, {u['role']}): \"{q['text']}\"")
        print(f"  returned {d} [{docs[d]['sensitivity_label_truth']}] {docs[d]['title']}")
        print(f"  the document's ACL is {docs[d]['acl_groups']}; the asker's direct groups are {';'.join(u['direct'])}")

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_01_results.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["query_id", "user_id", "rank", "doc_id", "score", "asker_may_read"])
        for q in data["queries"]:
            sc = dict(s["rank"][q["query_id"]])
            for i, d in enumerate(s["results_by_query"][q["query_id"]], 1):
                w.writerow([q["query_id"], q["user_id"], i, d, f"{sc[d]:.6f}", int(d in data["truth"][q["user_id"]])])


if __name__ == "__main__":
    main()
