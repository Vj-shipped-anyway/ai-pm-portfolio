"""Step 3 - Where each simple approach fails.

Two lookups, each with one idea, scored on the same registry and the same planted truth:
  exact primary    the filter from step 2
  family search    search every model string, in every role, for the family name of each retiring
                   model (what a text search over a repository or a sheet does)

KNOWN LIMIT, left in on purpose: a dependency that no registry row records, and an alias whose
recorded target is wrong, are invisible to any lookup that reads the registry. Step 4 does not see
them either, and this step prints them.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import family_search, kinds, load_truth, noticed_models, read_csv, score, affected_keys

truth = load_truth()
retiring = {m["model_id"].casefold() for m in noticed_models()}
exact = {(u["feature_id"], u["role"]) for u in read_csv("usages.csv") if u["role"] == "primary" and u["model_ref"].casefold() in retiring}
family = family_search()
aff = affected_keys(truth)

print("STEP 3 - each lookup alone")
for name, flagged in (("exact primary", exact), ("family search", family)):
    s = score(flagged, truth)
    print(f"  {name}: found {s['found']} of {s['affected']} affected, flagged {s['flagged']}, not affected {s['false']}, "
          f"features to open {len({k[0] for k in flagged})}")
print(f"  affected dependencies exact primary does not find, by planted kind: {kinds(aff - exact, truth)}")
print(f"  rows family search flags that are not affected, by planted kind: {kinds(family - aff, truth)}")
print(f"  affected dependencies family search does not find, by planted kind: {kinds(aff - family, truth)}")
unrecorded = {(r["feature_id"], r["role"]) for r in truth if r["affected"] == "yes" and r["written_ref"] == ""}
stale = [a for a in read_csv("truth_aliases.csv") if a["recorded_target"] != a["true_target"]]
print(f"  KNOWN LIMIT: affected dependencies that no registry row records: {len(unrecorded)} ({kinds(unrecorded, truth)})")
print(f"  KNOWN LIMIT: aliases whose recorded target differs from the vendor's: {len(stale)} ({', '.join(sorted(a['alias'] for a in stale))})")
print("  Exact match is precise and blind to everything but the primary id. Family search sees more and floods the reader.")
