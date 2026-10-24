"""Step 3 - Where character edit similarity fails.

One threshold has to serve every spelling variant. This step prints, for three thresholds, how many
planted matches the edit matcher catches by kind of change and how many clear names it alerts on by
kind. Then it prints the KNOWN LIMIT, left in on purpose: a party known by a name that is not on the
list, and a different person with a listed party's exact name. Step 4 removes neither.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import load, records_for, by_kind_at, kinds_of

THRESHOLDS = (0.60, 0.75, 0.93)


def main() -> None:
    data = load()
    rec = records_for("edit", data)
    match_kinds, clear_kinds = kinds_of(rec)
    tables = {t: by_kind_at(rec, t) for t in THRESHOLDS}
    print("STEP 3 - the edit matcher, by planted kind, at three thresholds")
    print("  matches caught:" + "".join("%12.2f" % t for t in THRESHOLDS))
    for k in match_kinds:
        print("  %-16s" % k + "".join("%12s" % ("%d of %d" % tables[t][k]) for t in THRESHOLDS))
    print("  clear names that alert:" + "".join("%12.2f" % t for t in THRESHOLDS))
    for k in clear_kinds:
        print("  %-16s" % k + "".join("%12s" % ("%d of %d" % tables[t][k]) for t in THRESHOLDS))
    print("  Going from 0.60 to 0.93 removes the shared_given and shared_surname alerts and also drops translit, translit_heavy and typo hits.")
    best = {k: max(tables[t][k][0] for t in THRESHOLDS) for k in ("order_swap", "initial")}
    print("  At none of the three does it catch more than %d of %d order swaps or %d of %d initials."
          % (best["order_swap"], tables[THRESHOLDS[0]]["order_swap"][1], best["initial"], tables[THRESHOLDS[0]]["initial"][1]))
    print("KNOWN LIMIT, left in on purpose:")
    for kind in ("exact", "edit", "tokens"):
        r = records_for(kind, data)
        low, top = by_kind_at(r, 0.50), by_kind_at(r, 1.0)
        print("  %-6s alias_unlisted caught at 0.50: %d of %d; namesake alerts at 1.00: %d of %d"
              % (kind, low["alias_unlisted"][0], low["alias_unlisted"][1], top["namesake"][0], top["namesake"][1]))
    print("  The first needs the list to carry the alias. The second needs a second identifier, which is not modeled here.")


if __name__ == "__main__":
    main()
