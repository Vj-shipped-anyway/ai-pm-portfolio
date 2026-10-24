"""Step 3 - Where each rule helps, costs, or leaves a gap.

Five versions of the check, scored on the same 308 figures:
  a  value anywhere in the spread        step 2
  b  tied line and period, spread lines  the mark names a line and a period; only a mark on a spread line is
                                         compared; a mark on a formula such as debt_ebitda_x is not recomputed
  c  b plus formulas, 1% tolerance       formulas recomputed; a figure passes when within 1% of the spread value
  d  b plus formulas, shown precision    formulas recomputed; the spread value rounded to the decimals shown must
                                         equal the figure (the rule in step 4)
  e  d plus unmarked figures flagged     a figure with no mark is reported as untied (the settings of step 4)

KNOWN LIMIT, left in on purpose: when the sentence names one line and the mark and number are for another
(prose_tag_mismatch), every version that compares the number with its mark passes it, and a figure written
in words or with a USD prefix (unparsed_form) is never read. Step 4 does not fix either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from decimal import Decimal

from common import alarms, anywhere_flags, load_memos, load_truth, names_a_formula, score, tally, tool_flags

memos, truth = load_memos(), load_truth()
versions = [
    ("a  value anywhere in the spread", anywhere_flags),
    ("b  tied line and period, spread lines", lambda m: tool_flags(m, None, lambda r, mm: r["status"] == "unresolved" or (r["status"] == "mismatch" and not names_a_formula(r, mm)))),
    ("c  formulas too, 1% tolerance", lambda m: tool_flags(m, Decimal("0.01"), lambda r, mm: r["status"] != "untied")),
    ("d  formulas too, shown precision", lambda m: tool_flags(m, None, lambda r, mm: r["status"] != "untied")),
    ("e  d plus unmarked figures flagged", tool_flags),
]
print("step_03_deficiencies_exposed.py - five versions of the check")
tallies = [tally(truth, score(memos, truth, flagger)) for _, flagger in versions]
for (name, _), t in zip(versions, tallies):
    print(f"  {name:<40} caught {t['caught']:>3} of {t['wrong']}   false alarms {t['false_alarms']:>3} of {t['fine']}")

a, b, c, d, e = tallies


def got(t, kind):
    return t["by_kind"][kind]["flagged"]


def total(kind):
    return a["by_kind"][kind]["total"]


print("  flagged / figures, by planted kind (a, b, c, d, e):")
for kind in sorted(a["by_kind"]):
    row = "  ".join(f"{got(t, kind):>2}" for t in tallies)
    print(f"    {kind:<19} {row}   / {total(kind):<3} {'should be flagged' if a['by_kind'][kind]['expected'] == 'flag' else 'should pass'}")
print(f"  tying each figure to its mark (a to b): false alarms {a['false_alarms']} -> {b['false_alarms']} of {a['fine']}; caught {a['caught']} -> {b['caught']} of {a['wrong']}, "
      f"because a flagged every percent and multiple whether it was right or wrong and b does not recompute them")
print(f"  recomputing formulas: stale_denominator {got(b, 'stale_denominator')} -> {got(d, 'stale_denominator')} of {total('stale_denominator')}, "
      f"growth_wrong {got(b, 'growth_wrong')} -> {got(d, 'growth_wrong')} of {total('growth_wrong')}, wrong_period {got(b, 'wrong_period')} -> {got(d, 'wrong_period')} of {total('wrong_period')}")
print(f"  a 1% tolerance against the shown precision: typo flagged {got(c, 'typo')} against {got(d, 'typo')} of {total('typo')}, "
      f"covenant_round {got(c, 'covenant_round')} against {got(d, 'covenant_round')} of {total('covenant_round')}; false alarms {c['false_alarms']} against {d['false_alarms']} ({alarms(c)})")
print(f"  flagging unmarked figures: untied {got(d, 'untied')} -> {got(e, 'untied')} of {total('untied')}; the price is term_untagged, "
      f"proposed terms with no term mark, flagged {got(e, 'term_untagged')} of {total('term_untagged')}")
print(f"  KNOWN LIMIT: prose_tag_mismatch passes d and e: {total('prose_tag_mismatch') - got(e, 'prose_tag_mismatch')} of {total('prose_tag_mismatch')}; "
      f"unparsed_form is never read: {total('unparsed_form') - got(e, 'unparsed_form')} of {total('unparsed_form')} pass")
print("  A number can agree with its mark and still sit under the wrong words; a figure in words is invisible to a pattern.")
