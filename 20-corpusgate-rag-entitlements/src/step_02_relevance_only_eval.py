"""Step 2 - The baseline: a relevance-only retrieval eval.

This is what most teams run before they ship a retrieval layer: score the top 5 results against
a set of relevant documents with precision@5 and recall@5. It is a reasonable eval. This script
runs it on the step 1 system and then asks what the eval is able to see.

What it measures: for each query, how many of the top 5 are in `relevant_doc_ids`, and how many
of the relevant documents appear in the top 5.

What it cannot see: who is asking. queries.csv has no column for a document that must NOT be
returned, so the eval cannot express an entitlement test case.

Run (from src/):
    python3 step_02_relevance_only_eval.py

Output: a readable summary, plus out/step_02_eval.csv.
"""

from __future__ import annotations

import csv
from statistics import mean

from step_01_no_access_control import K, OUT_DIR, load_all, pct, status_quo


def relevance_eval(data: dict, results: dict) -> dict:
    """Precision@K and recall@K against relevant_doc_ids. results: query_id -> doc_ids returned."""
    rows = []
    for q in data["queries"]:
        rel = set(q["relevant"])
        rs = results[q["query_id"]]
        hit = [d for d in rs if d in rel]
        rows.append({"query_id": q["query_id"], "user_id": q["user_id"], "returned": len(rs), "hits": len(hit),
                     "precision": len(hit) / len(rs) if rs else 0.0, "recall": len(hit) / len(rel) if rel else 0.0,
                     "n_relevant": len(rel)})
    return {"rows": rows, "precision": mean(r["precision"] for r in rows), "recall": mean(r["recall"] for r in rows),
            "with_hit": sum(1 for r in rows if r["hits"]), "n": len(rows),
            "mean_relevant": mean(r["n_relevant"] for r in rows)}


def entitlement_negative_cases(data: dict) -> int:
    """Queries that carry an expectation that some document must not be returned. The eval file
    has no such column, so this counts rows with a non-empty `must_not_return_doc_ids` field."""
    return sum(1 for q in data["queries"] if q.get("must_not_return_doc_ids"))


def leaked_hits(data: dict, results: dict) -> int:
    """Leaked results that the relevance eval counts as correct (they are in relevant_doc_ids)."""
    n = 0
    for q in data["queries"]:
        rel = set(q["relevant"])
        n += sum(1 for d in results[q["query_id"]] if d in rel and d not in data["truth"][q["user_id"]])
    return n


def summarize(data: dict = None, sq: dict = None) -> dict:
    data = data or load_all()
    sq = sq or status_quo(data)
    ev = relevance_eval(data, sq["results_by_query"])
    ev["entitlement_negative"] = entitlement_negative_cases(data)
    ev["leaked"] = sq["leaked"]
    ev["results"] = sq["results"]
    ev["leaked_scored_as_hits"] = leaked_hits(data, sq["results_by_query"])
    return ev


def main() -> None:
    data = load_all()
    sq = status_quo(data)
    ev = summarize(data, sq)

    print("STEP 2 - BASELINE: THE RELEVANCE-ONLY EVAL")
    print("Same stub retriever as step 1 (TF-IDF, not a model). The eval scores the top 5 against relevant_doc_ids.")
    print()
    print("RESULT")
    print(f"  Precision@{K}: {ev['precision']:.3f}")
    print(f"  Recall@{K}:    {ev['recall']:.3f}   (queries have {ev['mean_relevant']:.1f} relevant documents on average, so recall@{K} cannot reach 1.0)")
    print(f"  Queries with at least one relevant document in the top {K}: {ev['with_hit']} of {ev['n']} ({pct(ev['with_hit'], ev['n'])})")
    print()
    print("WHAT THE EVAL CAN SEE")
    w = 66
    print(f"  {'Relevance of the top ' + str(K) + ':':<{w}}yes")
    print(f"  {'Who is asking:':<{w}}no (queries.csv has a user, the score never uses it)")
    print(f"  {'Entitlement test cases in the eval set:':<{w}}{ev['entitlement_negative']} of {ev['n']} queries")
    print(f"  {'Results the same system returns to a user who may not read them:':<{w}}{ev['leaked']} of {ev['results']:,} ({pct(ev['leaked'], ev['results'])})")
    print(f"  {'Of those, scored by the eval as correct answers:':<{w}}{ev['leaked_scored_as_hits']} of {ev['leaked']} ({pct(ev['leaked_scored_as_hits'], ev['leaked'])})")

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_02_eval.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["query_id", "user_id", "returned", "hits", "n_relevant", "precision", "recall"])
        for r in ev["rows"]:
            w.writerow([r["query_id"], r["user_id"], r["returned"], r["hits"], r["n_relevant"],
                        f"{r['precision']:.3f}", f"{r['recall']:.3f}"])


if __name__ == "__main__":
    main()
