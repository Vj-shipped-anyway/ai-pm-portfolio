"""Step 1 - Status quo: a name is an alert only when it equals a listed name.

Case, accents and punctuation are ignored, nothing else. This is the first screen most teams have, and
it has no threshold: the score is 0 or 1. The data is synthetic (data/_generate.py); the truth of each
customer is the way it was planted, not what any matcher says.

Run (from src/):  python3 step_01_exact_match.py
"""
from common import load, records_for, metrics_at, kinds_of, pct


def main() -> None:
    data = load()
    entries, customers, _truth = data
    rec = records_for("exact", data)
    m = metrics_at(rec, 1.0)
    match_kinds, clear_kinds = kinds_of(rec)
    hits = {}
    for r in rec:
        hit = (r["best_true"] if r["truth"] == "match" else r["best"]) >= 1.0
        h, n = hits.get(r["kind"], (0, 0))
        hits[r["kind"]] = (h + hit, n + 1)
    print("STEP 1 - exact match on the normalised name")
    print("  watchlist: %d names; customers screened: %d (%d are the same party as a listed entity, %d are not)"
          % (len(entries), len(customers), m["matches"], m["clear"]))
    print("  caught: %d of %d (%s)" % (m["caught"], m["matches"], pct(m["caught"], m["matches"])))
    print("  missed: %d of %d" % (m["matches"] - m["caught"], m["matches"]))
    print("  false alerts: %d of %d (%s)" % (m["false_alerts"], m["clear"], pct(m["false_alerts"], m["clear"])))
    print("  caught by planted change: " + ", ".join("%s %d of %d" % (k, hits[k][0], hits[k][1]) for k in match_kinds))
    print("  false alerts by planted kind: " + ", ".join("%s %d of %d" % (k, hits[k][0], hits[k][1]) for k in clear_kinds if hits[k][0]))
    print("  There is no threshold to tune. Every spelling the list does not carry is a miss.")


if __name__ == "__main__":
    main()
