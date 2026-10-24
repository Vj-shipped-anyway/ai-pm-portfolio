"""Step 3 - Where each part fails alone, and what a stricter sheet costs.

Four variants, each scored on the same planted truth:
  completeness tests alone        field checks, no dates and no usage file
  staleness and coverage alone    dates and the usage file, no field checks
  everything but the usage file   what an inventory owner can run without a gateway export
  every column on every row       the quick answer to step 2's blind spot for agents and evidence

KNOWN LIMITS, left in on purpose and printed at the end: a placeholder the word list does not hold, a review
date refreshed in bulk, a quarterly system that looks idle, and shadow traffic that carries a listed id or none.
Step 4 does not fix them.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from collections import Counter

from common import load_world, load_truth, load_shadows, split_truth, check, flagged_ids, is_blank, REQUIRED

ALL_COLUMNS = REQUIRED + ("tools", "permission_scope", "human_approval", "evaluation_ref", "last_evaluated",
                          "independent_review_date", "fallback_plan")

as_of, records, usage = load_world()
truth, shadows = load_truth(), load_shadows()
defective, clean = split_truth(truth)


def score(name, flagged):
    bad = [s for s in defective if s in flagged]
    ok = [s for s in clean if s in flagged]
    print(f"  {name}")
    print(f"    defective records flagged: {len(bad)} of {len(defective)}; clean records flagged: {len(ok)} of {len(clean)}")
    return set(bad)


print("STEP 3 - each part alone")
full = flagged_ids(check(records, usage, as_of))
score("completeness tests alone", flagged_ids(check(records, usage, as_of, tests=("completeness",))))
score("staleness and coverage tests alone", flagged_ids(check(records, usage, as_of, tests=("staleness", "coverage"))))
no_usage = score("all three tests, no usage file", flagged_ids(check(records, None, as_of)))
every = {r["system_id"] for r in records if any(is_blank(r.get(f)) for f in ALL_COLUMNS)}
score(f"every one of the {len(ALL_COLUMNS)} columns required on every row", every)
only_usage = [s for s in defective if s in full and s not in no_usage]
print(f"  defective records only the usage file can show: {len(only_usage)} of {len(defective)}")

missed = [s for s in defective if s not in full]
false_alarms = [s for s in clean if s in full]
print("  KNOWN LIMITS, left in on purpose:")
print(f"    defective records that pass every test: {len(missed)} of {len(defective)} "
      f"({', '.join(f'{k} {v}' for k, v in sorted(Counter(truth[s]['case_kind'] for s in missed).items()))})")
print(f"    clean records the tests flag: {len(false_alarms)} of {len(clean)} "
      f"({', '.join(f'{k} {v}' for k, v in sorted(Counter(truth[s]['case_kind'] for s in false_alarms).items())) or 'none'})")
kinds = Counter(s["shadow_kind"] for s in shadows)
print(f"    shadow systems the usage export cannot name: {kinds['untagged'] + kinds['hidden_behind_registered']} of {len(shadows)} "
      f"({kinds['untagged']} with no system id, {kinds['hidden_behind_registered']} under a listed system's id)")
print("  A stricter sheet fails the other way: it flags the generative systems that have no tools to list.")
