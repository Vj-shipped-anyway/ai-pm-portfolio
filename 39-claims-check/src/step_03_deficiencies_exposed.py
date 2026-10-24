"""Step 3 - Where each change to the check helps, costs, or leaves a gap.

Five versions of the check, scored on the same 284 bullets:
  grep, one line at a time     step 2
  grep on extracted claims     wrapped bullets joined; code spans, links and fenced blocks skipped
  whole numbers, no pairs      a number counts only when printed as a whole number
  whole numbers and pairs      "a of b" must be printed as a pair (the settings of step 4)
  the same, single digits too  numbers of one digit are checked as well

KNOWN LIMIT, left in on purpose: a wrong number that equals another number the scripts print
(for example the row count) passes every version, and a wrong single-digit number passes unless
single digits are checked, which costs false alarms. Step 4 does not fix either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import grep_lines, grep_on_claims_lines, load_projects, load_truth, score, tally, tool_lines

projects, truth = load_projects(), load_truth()
versions = [
    ("grep, one line at a time", grep_lines),
    ("grep on extracted claims", grep_on_claims_lines),
    ("whole numbers, no pairs", lambda p: tool_lines(p, pairs=False)),
    ("whole numbers and pairs", tool_lines),
    ("the same, single digits too", lambda p: tool_lines(p, min_digits=1)),
]
print("step_03_deficiencies_exposed.py - five versions of the check")
tallies = {}
for name, flagger in versions:
    t = tallies[name] = tally(truth, score(projects, truth, flagger))
    print(f"  {name:<28} caught {t['caught']} of {t['unsupported']}   false alarms {t['false_alarms']} of {t['supported']}")

a, b, c, d, e = (tallies[n] for n, _ in versions)


def kind(t, k):
    """(flagged, total) for one planted kind."""
    return t["by_kind"][k]["flagged"], t["by_kind"][k]["total"]


print(f"  extracting claims first: wrapped_bad caught {kind(a, 'wrapped_bad')[0]} of {kind(a, 'wrapped_bad')[1]} before, "
      f"{kind(b, 'wrapped_bad')[0]} of {kind(b, 'wrapped_bad')[1]} after; inert_digits false alarms {kind(a, 'inert_digits')[0]} before, {kind(b, 'inert_digits')[0]} after")
print(f"  whole numbers catch what grep passes: substring_trap {kind(c, 'substring_trap')[0]} of {kind(c, 'substring_trap')[1]}, "
      f"rounded {kind(c, 'rounded')[0]} of {kind(c, 'rounded')[1]}")
print(f"  pairs catch what whole numbers pass: pair_broken {kind(c, 'pair_broken')[0]} of {kind(c, 'pair_broken')[1]} without, "
      f"{kind(d, 'pair_broken')[0]} of {kind(d, 'pair_broken')[1]} with")
print(f"  the pair rule costs: pair_split, two numbers printed on separate lines, flagged {kind(d, 'pair_split')[0]} of {kind(d, 'pair_split')[1]}, a false alarm each time")
print(f"  KNOWN LIMIT: a wrong number that equals another printed number passes every version: coincidence {kind(d, 'coincidence')[1] - kind(d, 'coincidence')[0]} of {kind(d, 'coincidence')[1]} pass")
print(f"  single digits checked: single_digit caught {kind(e, 'single_digit')[0]} of {kind(e, 'single_digit')[1]}, "
      f"small_numeral flagged {kind(e, 'small_numeral')[0]} of {kind(e, 'small_numeral')[1]} (a small numeral is not a claim)")
print("  Skipping single digits misses a wrong small count; checking them flags every stray small numeral.")
