"""Step 3 - What the single number hides, measured against the generator's truth.

Each block takes one thing a steering group would assume and measures it. The truth file and the
list of planted problems are the generator's; the scorecard in step 4 never reads them.

KNOWN LIMIT, left in on purpose: when the agent and the person agree and are both wrong, the two
files look like a success. This step counts those cases from the truth file. Step 4 cannot see them.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from collections import Counter
from dataclasses import replace

from common import load, joined, planted, score, RULES

proposals, outcomes = load()
rows = joined()
s = score(proposals, outcomes, RULES)
print("STEP 3 - what one number hides")

# 1. the denominator
print("  1. Abstentions are dropped from the denominator")
ab = Counter(r["human"] for r in rows if not r["proposed"])
n_by = Counter(r["human"] for r in rows)
print(f"     {s['abstained']} abstentions; first-report rate {s['headline']:.1%}; counting them as misses {s['end_to_end']:.1%}")
print("     abstained by recorded outcome: " + ", ".join(f"{k} {ab[k]} of {n_by[k]}" for k in sorted(n_by)))

# 2. the sample
lo, hi = s["interval"]
print("  2. The rate is an estimate")
print(f"     {s['agree']} of {s['proposed']} gives a 95% interval of {lo:.1%} to {hi:.1%}; the bar of 90% sits inside it" if lo < 0.90 <= hi
      else f"     {s['agree']} of {s['proposed']} gives a 95% interval of {lo:.1%} to {hi:.1%}")

# 3. the baseline
print("  3. What a rule with no model scores")
print(f"     always proposing {s['majority_label']} agrees on {s['majority_share']:.1%} of matched cases; "
      f"the agent agrees on {s['end_to_end']:.1%} (lift {100 * s['lift']:.1f} points)")

# 4. costs differ
print("  4. Disagreements cost different amounts")
print(f"     {s['risky']} of {s['proposed']} proposals ({s['risky_rate']:.1%}) are in a direction I marked risky "
      "(money out where the person refused or escalated, or a fraud case denied)")

# 5. groups: no minimum size against a minimum of 30 proposals
roles = {(p["group_type"], p["group"]): ("real" if p["real"] == "1" else "look-alike") for p in planted()}


def flagged(result):
    out = []
    for gtype, key in (("segment", "by_segment"), ("week", "by_week"), ("reviewer", "by_reviewer")):
        out += [(gtype, g["name"]) for g in result[key] if g["status"] == "below"]
    return out


print("  5. Small groups raise alarms")
naive = flagged(score(proposals, outcomes, replace(RULES, min_group=1)))
kept = flagged(s)
for label, found in (("any size", naive), ("at least 30 proposals", kept)):
    tags = Counter(roles.get(f, "other") for f in found)
    print(f"     groups flagged ({label}): {len(found)}   planted problems {tags['real']}, planted look-alikes {tags['look-alike']},"
          f" unplanted {tags['other']}")

# 6. drift
drift = sorted(int(p["group"]) for p in planted() if p["kind"] == "drift")
inside = [r for r in rows if r["week"] in drift and r["proposed"]]
outside = [r for r in rows if r["week"] not in drift and r["proposed"]]
rate = lambda rs: sum(1 for r in rs if r["kind"] == "agree") / len(rs)  # noqa: E731
print("  6. A change in two weeks barely moves the all-weeks rate")
print(f"     weeks {drift[0]} and {drift[-1]}: {rate(inside):.1%} on {len(inside)} proposals; the other weeks: {rate(outside):.1%};"
      f" all weeks: {s['headline']:.1%}")

# 7. the yardstick
dis = [r for r in rows if r["kind"] == "disagree_outcome"]
agent_right = sum(1 for r in dis if r["proposed"] == r["true"])
human_right = sum(1 for r in dis if r["human"] == r["true"])
neither = len(dis) - agent_right - human_right
print("  7. A disagreement is not always the agent's mistake")
print(f"     of {len(dis)} outcome disagreements, the truth sides with the agent in {agent_right}, with the person in {human_right}, "
      f"with neither in {neither}")

# known limit
both_wrong = [r for r in rows if r["kind"] == "agree" and r["proposed"] != r["true"]]
print("  KNOWN LIMIT: agreement is not correctness")
print(f"     {len(both_wrong)} of the {s['agree']} agreements are cases where the agent and the person are both wrong against the truth"
      f" ({sum(1 for r in both_wrong if r['planted'] == 'shared_wrong')} planted, the rest where two separate errors landed on the same wrong outcome);"
      " no check on two files can see them")
