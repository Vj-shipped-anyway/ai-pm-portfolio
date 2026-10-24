"""Step 2 - The common basic check: is the figure somewhere in the spread?

A team's first script reads every figure with a $, % or x from the memo and looks for that value among the
values in the spread file, rounded to the precision the memo shows. It ignores any mark on the figure. It
is cheap and it finds a dollar figure that was never in the spread. A percent or a multiple is never a
value in the file, so every one of them is flagged, right or wrong. That makes this check look worse on
fine figures, and better on wrong ones, than it would on a spread export that carries its own ratios; the
data here does not.

Run (from src/):  python3 step_02_value_anywhere.py
"""
from common import alarms, anywhere_flags, key, load_memos, load_truth, parse_figures, passed, score, tally

memos, truth = load_memos(), load_truth()
result = score(memos, truth, anywhere_flags)
t = tally(truth, result)
k = t["by_kind"]
ratio_like = {key(r) for r in truth if parse_figures(r["text"]) and parse_figures(r["text"])[0]["kind"] != "money"}
wrong_ratio = [r for r in truth if r["expected"] == "flag" and key(r) in ratio_like]
fine_ratio = [r for r in truth if r["expected"] == "ok" and key(r) in ratio_like]
wrong_money = [r for r in truth if r["expected"] == "flag" and key(r) not in ratio_like]
fine_money = [r for r in truth if r["expected"] == "ok" and key(r) not in ratio_like]
hit = lambda rows: sum(1 for r in rows if result["flagged"][key(r)])  # noqa: E731

print("step_02_value_anywhere.py - the figure must be a value somewhere in the spread")
print(f"  wrong figures caught: {t['caught']} of {t['wrong']}")
print(f"  fine figures flagged by mistake: {t['false_alarms']} of {t['fine']}")
print(f"  wrong dollar figures caught: {hit(wrong_money)} of {len(wrong_money)}; fine dollar figures flagged: {hit(fine_money)} of {len(fine_money)}")
print(f"  percents and multiples flagged, right or wrong: wrong {hit(wrong_ratio)} of {len(wrong_ratio)}, fine {hit(fine_ratio)} of {len(fine_ratio)}")
print(f"  let through, by planted kind: {passed(t)}")
print(f"  false alarms, by planted kind: {alarms(t)}")
print(f"  a dollar figure from the wrong period or line is still in the spread: wrong_period passes {k['wrong_period']['total'] - k['wrong_period']['flagged']} of {k['wrong_period']['total']}, "
      f"wrong_line passes {k['wrong_line']['total'] - k['wrong_line']['flagged']} of {k['wrong_line']['total']}")
print("  It cannot tell which line and period a figure was meant for, and it cannot recompute a ratio.")
