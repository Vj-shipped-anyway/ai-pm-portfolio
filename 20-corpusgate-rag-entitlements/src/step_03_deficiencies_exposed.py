"""Step 3 - Six deficiencies the relevance-only eval and the cheap guards leave open.

After a leak is found, teams usually try three cheap guards: filter on the ACL copy stored in the
index, check the user's own group list, or filter on the sensitivity label. Each is run here in
isolation, on the same 200 queries, and scored against the ground truth (data/entitlement_truth.csv).
A fourth cheap check, a regex scan for personal data, is scored against the injected truth.

  (1) Entitlement leakage        top-5 results the asker may not read
  (2) Stale ACL in the index     an ACL copy taken at index time misses later changes
  (3) Personal data in text      injected values sit in documents open to all staff; a regex finds some
  (4) Flat group check           ignores nested groups: wrongly denied and wrongly allowed
  (5) Label-only filter          over-blocks entitled documents, under-blocks mislabeled ones
  (6) The eval has no entitlement cases   0 of 200 queries; the canary pack finds the leaks

The retriever is a stub (TF-IDF, not a model). Counts are on a synthetic test set built so that each
effect appears; they are not estimates of real-world frequency.

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: a readable summary, plus out/step_03_summary.json.
"""

from __future__ import annotations

import json
import re
from statistics import mean

from step_01_no_access_control import (
    K, OUT_DIR, acl_allows, effective_groups, leak_stats, load_all, pct, rank_query,
    status_quo, top_k, _is_revoke,
)
from step_02_relevance_only_eval import entitlement_negative_cases, leaked_hits, relevance_eval

# ---------------------------------------------------------------------------
# Personal-data patterns (the cheap check; step 4 uses the same patterns at ingestion)
# ---------------------------------------------------------------------------
PII_PATTERNS = [
    ("ssn_like", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("account_like", re.compile(r"\bACCT-\d{4}-\d{4}\b")),
    ("email_like", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]


def scan_text(text: str) -> list:
    """List of (kind, matched text) for every pattern hit."""
    return [(kind, m.group(0)) for kind, rx in PII_PATTERNS for m in rx.finditer(text)]


# ---------------------------------------------------------------------------
# Systems under test: who may see which document, according to each guard
# ---------------------------------------------------------------------------
def allowed_by_acl(data: dict, acl_of: dict, nested: bool = True) -> dict:
    """user_id -> set of doc_ids the ACL says the user may read. acl_of: doc_id -> ACL list.
    nested=False is the flat check: the user's direct groups, plus the all-staff group that every
    directory export carries (an assumption of this modeled check)."""
    out = {}
    for u in data["users"]:
        g = effective_groups(data, u, nested)
        if not nested:
            g = g | {"grp-all-staff"}
        out[u] = {d for d in data["doc_ids"] if acl_allows(g, acl_of[d])}
    return out


def allowed_by_label(data: dict, open_labels=("public", "internal")) -> dict:
    ok = {d for d, r in data["docs"].items() if r["sensitivity"] in open_labels}
    return {u: set(ok) for u in data["users"]}


def run_system(data: dict, rank: dict, allowed: dict = None, mode: str = "pre") -> dict:
    """query_id -> doc_ids returned. pre: filter the ranking, then take K. post: take K, then filter."""
    out = {}
    for q in data["queries"]:
        ok = None if allowed is None else allowed[q["user_id"]]
        if mode == "post" and ok is not None:
            out[q["query_id"]] = [d for d in top_k(rank[q["query_id"]], K) if d in ok]
        else:
            out[q["query_id"]] = top_k(rank[q["query_id"]], K, ok)
    return out


def readable_recall(data: dict, results: dict) -> tuple:
    """Mean recall@K counted only over relevant documents the asker may read. Returns (mean, queries counted)."""
    vals = []
    for q in data["queries"]:
        rr = set(q["relevant"]) & data["truth"][q["user_id"]]
        if rr:
            vals.append(len(set(results[q["query_id"]]) & rr) / len(rr))
    return mean(vals), len(vals)


def readable_relevant_withheld(data: dict, allowed: dict) -> tuple:
    """(query, document) pairs that are relevant and readable but removed by the guard, and the total."""
    lost = total = 0
    for q in data["queries"]:
        rr = set(q["relevant"]) & data["truth"][q["user_id"]]
        total += len(rr)
        lost += len(rr - allowed[q["user_id"]])
    return lost, total


def run_canaries(data: dict, index: dict, allowed: dict = None) -> list:
    """Each canary asks for exactly one document the user may not read. Leaked = it came back."""
    out = []
    for c in data["canaries"]:
        ok = None if allowed is None else allowed[c["user_id"]]
        got = top_k(rank_query(index, c["query_text"]), K, ok)
        out.append({"canary_id": c["canary_id"], "user_id": c["user_id"], "doc_id": c["doc_id"],
                    "stratum": c["stratum"], "leaked": c["doc_id"] in got})
    return out


def doc_kinds(row: dict) -> set:
    return {k for k, _ in scan_text(row["text"])}


def open_to_all_staff(row: dict) -> bool:
    return "grp-all-staff" in row["acl_now"]


# ---------------------------------------------------------------------------
# The six measurements
# ---------------------------------------------------------------------------
def deficiencies(data: dict = None, sq: dict = None) -> dict:
    data = data or load_all()
    sq = sq or status_quo(data)
    docs, truth, rank = data["docs"], data["truth"], sq["rank"]
    n_users, n_docs = len(data["users"]), len(docs)
    n_pairs = n_users * n_docs
    n_q = len(data["queries"])
    base_recall, n_rr = readable_recall(data, sq["results_by_query"])
    truth_filter_recall, _ = readable_recall(data, run_system(data, rank, truth))
    r = {"n_users": n_users, "n_docs": n_docs, "n_pairs": n_pairs, "n_queries": n_q,
         "base_readable_recall": base_recall, "recall_queries": n_rr, "truth_filter_recall": truth_filter_recall}

    # (1) leakage
    r["leak"] = {"results": sq["results"], "leaked": sq["leaked"], "queries": sq["queries_with_leak"],
                 "by_label": sq["by_label"]}

    # (2) stale ACL in the index
    idx_allowed = allowed_by_acl(data, {d: docs[d]["acl_index"] for d in docs}, nested=True)
    res2 = run_system(data, rank, idx_allowed)
    s2 = leak_stats(data, res2)
    lost2, tot2 = readable_relevant_withheld(data, idx_allowed)
    changed = [c for c in data["changes"]]
    n_rev = sum(1 for c in changed if _is_revoke(data, c))
    r["stale"] = {
        "docs_changed": len(changed), "revokes": n_rev, "grants": len(changed) - n_rev,
        "pairs_stale_allow": sum(len(idx_allowed[u] - truth[u]) for u in truth),
        "pairs_stale_deny": sum(len(truth[u] - idx_allowed[u]) for u in truth),
        "leaked": s2["leaked"], "results": s2["results"], "queries": s2["queries_with_leak"],
        "withheld": lost2, "readable_relevant": tot2,
    }

    # (3) personal data in ingested text
    pii = [d for d, row in docs.items() if row["pii_truth"] != "none"]
    kinds = {d: doc_kinds(docs[d]) for d in docs}
    found = [d for d in pii if docs[d]["pii_truth"] in kinds[d]]
    missed = [d for d in pii if d not in found]
    false_pos = [d for d in docs if docs[d]["pii_truth"] == "none" and kinds[d]]
    open_pii = [d for d in pii if open_to_all_staff(docs[d])]
    pii_res = sum(1 for q in data["queries"] for d in sq["results_by_query"][q["query_id"]] if docs[d]["pii_truth"] != "none")
    pii_res_open = sum(1 for q in data["queries"] for d in sq["results_by_query"][q["query_id"]]
                       if docs[d]["pii_truth"] != "none" and open_to_all_staff(docs[d]))
    r["pii"] = {"injected": len(pii), "open_to_all_staff": len(open_pii), "found": len(found), "missed": len(missed),
                "false_positives": len(false_pos), "results_with_pii": pii_res, "results_with_pii_open": pii_res_open,
                "results": sq["results"], "scan_docs": len(docs)}

    # (4) flat group check
    flat = allowed_by_acl(data, {d: docs[d]["acl_now"] for d in docs}, nested=False)
    res4 = run_system(data, rank, flat)
    s4 = leak_stats(data, res4)
    lost4, tot4 = readable_relevant_withheld(data, flat)
    rec4, _ = readable_recall(data, res4)
    r["flat"] = {
        "recall": rec4,
        "wrongly_denied": sum(len(truth[u] - flat[u]) for u in truth),
        "wrongly_allowed": sum(len(flat[u] - truth[u]) for u in truth),
        "users_denied": sum(1 for u in truth if truth[u] - flat[u]),
        "users_allowed": sum(1 for u in truth if flat[u] - truth[u]),
        "leaked": s4["leaked"], "results": s4["results"], "queries": s4["queries_with_leak"],
        "withheld": lost4, "readable_relevant": tot4,
    }

    # (5) label-only filter
    lab = allowed_by_label(data)
    res5 = run_system(data, rank, lab)
    s5 = leak_stats(data, res5)
    lost5, tot5 = readable_relevant_withheld(data, lab)
    rec5, _ = readable_recall(data, res5)
    mis_ids = {d for d, row in docs.items() if row["sensitivity"] != row["sensitivity_label_truth"]}
    leak_mis = sum(1 for q in data["queries"] for d in res5[q["query_id"]]
                   if d in mis_ids and d not in truth[q["user_id"]])
    r["label"] = {
        "pairs_overblocked": sum(len(truth[u] - lab[u]) for u in truth),
        "pairs_readable": sum(len(truth[u]) for u in truth),
        "pairs_underblocked": sum(len(lab[u] - truth[u]) for u in truth),
        "mislabeled_docs": len(mis_ids), "leaked": s5["leaked"], "results": s5["results"],
        "leaked_mislabeled": leak_mis, "queries": s5["queries_with_leak"],
        "withheld": lost5, "readable_relevant": tot5, "recall": rec5,
    }

    # (6) the eval has no entitlement cases
    ev = relevance_eval(data, sq["results_by_query"])
    canary_none = run_canaries(data, sq["index"])
    r["eval"] = {"negative_cases": entitlement_negative_cases(data), "queries": n_q,
                 "leaked": sq["leaked"], "leaked_scored_as_hits": leaked_hits(data, sq["results_by_query"]),
                 "precision": ev["precision"], "recall": ev["recall"],
                 "canaries": len(data["canaries"]),
                 "canary_pairs_not_entitled": sum(1 for c in data["canaries"] if c["doc_id"] not in truth[c["user_id"]]),
                 "canary_leaks": {"no_filter": sum(c["leaked"] for c in canary_none),
                                  "index_acl": sum(c["leaked"] for c in run_canaries(data, sq["index"], idx_allowed)),
                                  "flat_groups": sum(c["leaked"] for c in run_canaries(data, sq["index"], flat)),
                                  "label_only": sum(c["leaked"] for c in run_canaries(data, sq["index"], lab))}}
    return r


def main() -> None:
    data = load_all()
    sq = status_quo(data)
    r = deficiencies(data, sq)
    n_q, np_ = r["n_queries"], r["n_pairs"]

    print("STEP 3 - SIX DEFICIENCIES, EACH WITH A COUNT")
    print("Stub retriever (TF-IDF, not a model). Synthetic test set; counts are not real-world frequencies.")
    print(f"Each cheap guard is run alone on the same {n_q} queries and scored against the ground truth.")
    print()
    L = r["leak"]
    print("(1) Entitlement leakage: nothing checks who is asking")
    print(f"    {L['leaked']} of {L['results']:,} results ({pct(L['leaked'], L['results'])}) go to a user who may not read them, in {L['queries']} of {n_q} queries ({pct(L['queries'], n_q)}).")
    print("    Leaked by true label: " + ", ".join(f"{k} {L['by_label'].get(k, 0)}" for k in ("public", "internal", "confidential", "restricted")) + ".")
    print()
    S = r["stale"]
    print("(2) Stale ACL in the index: an ACL copy taken at index time misses later changes")
    print(f"    {S['docs_changed']} of {r['n_docs']} documents changed ACL after indexing ({pct(S['docs_changed'], r['n_docs'])}): {S['revokes']} revokes, {S['grants']} grants.")
    print(f"    A filter on the index copy (nested groups handled correctly) still allows {S['pairs_stale_allow']} user and document pairs the source now denies,")
    print(f"    and denies {S['pairs_stale_deny']} pairs the source now allows.")
    print(f"    On the queries it leaks {S['leaked']} of {S['results']:,} results in {S['queries']} queries, and hides {S['withheld']} of {S['readable_relevant']:,} readable relevant documents.")
    print()
    P = r["pii"]
    print("(3) Personal data in ingested text: nothing scans documents before they are indexed")
    print(f"    {P['injected']} of {P['scan_docs']} documents carry injected personal data; {P['open_to_all_staff']} of those are open to all staff.")
    print(f"    {P['results_with_pii']} of {P['results']:,} results contain it, {P['results_with_pii_open']} of them from documents open to all staff.")
    print(f"    A regex scan finds {P['found']} of {P['injected']} ({pct(P['found'], P['injected'])}), misses {P['missed']}, and flags {P['false_positives']} documents that carry none.")
    print()
    F = r["flat"]
    print("(4) Flat group check: ignores nested groups")
    print(f"    Checking only the user's direct groups (plus all-staff) gets {F['wrongly_denied']:,} of {np_:,} user and document pairs wrongly denied ({F['users_denied']} users)")
    print(f"    and {F['wrongly_allowed']} wrongly allowed ({F['users_allowed']} users: an explicit deny reached only through a parent group is missed).")
    print(f"    On the queries it leaks {F['leaked']} results in {F['queries']} queries and hides {F['withheld']} of {F['readable_relevant']:,} readable relevant documents.")
    print(f"    Readable recall@{K} is {F['recall']:.3f}, against {r['truth_filter_recall']:.3f} for a filter that uses the true entitlement.")
    print()
    B = r["label"]
    print("(5) Label-only filter: allow public and internal, withhold confidential and restricted")
    print(f"    Over-blocks: {B['pairs_overblocked']} of {B['pairs_readable']:,} readable user and document pairs ({pct(B['pairs_overblocked'], B['pairs_readable'])}) are withheld.")
    print(f"    Recall lost: {B['withheld']} of {B['readable_relevant']:,} readable relevant documents ({pct(B['withheld'], B['readable_relevant'])}) never reach the user.")
    print(f"    Readable recall@{K} is {B['recall']:.3f}, against {r['truth_filter_recall']:.3f} for a filter that uses the true entitlement.")
    print(f"    Under-blocks: {B['leaked']} results still leak in {B['queries']} queries, {B['leaked_mislabeled']} of them from the {B['mislabeled_docs']} mislabeled documents; the rest are documents whose ACL is narrower than their label.")
    print()
    E = r["eval"]
    print("(6) The eval has no entitlement test cases")
    print(f"    {E['negative_cases']} of {E['queries']} queries is an entitlement-negative. The eval scores {E['leaked_scored_as_hits']} of the {E['leaked']} leaked results as correct (precision@{K} {E['precision']:.3f}).")
    cl = E["canary_leaks"]
    print(f"    A canary pack asks for exactly one document each user may not read ({E['canary_pairs_not_entitled']} of {E['canaries']} pairs verified not entitled).")
    print(f"    Leaked canaries: no filter {cl['no_filter']} of {E['canaries']}; index-ACL filter {cl['index_acl']}; flat group check {cl['flat_groups']}; label-only filter {cl['label_only']}.")
    print("    The pack is stratified toward the cases above, so these counts describe this pack, not a rate.")

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "step_03_summary.json").write_text(json.dumps(r, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
