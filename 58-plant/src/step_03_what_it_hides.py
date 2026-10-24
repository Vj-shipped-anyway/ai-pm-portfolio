"""Step 3 - What the is_bad column hides.

Same five files as step 2, scored again with the facts the author had while corrupting them (`hits`
from common.sprinkle). The file itself does not hold these facts.

  1  the pooled recall hides which failures are found and which never are
  2  a row hit by two failures gets one flag, and one flag earns credit for both
  3  the column ships in the data, so a checker can read it
  4  the files hold no look-alike rows, so false alarms on them are not measured
  5  recall moves between files by more than the gap between the two rule sets

KNOWN LIMIT, left in on purpose: the tuned rules miss every paraphrased injection, in every file. A
better key makes the miss visible. It does not fix the rules, and step 4 does not either.

Run (from src/):  python3 step_03_what_it_hides.py
"""
from common import SEEDS, LEVELS, boolean_key, demo_spec, flag_rows, score, sprinkle

# which planted failures each rule can claim to have found
EXPLAINS = {"duplicate": {"duplicate_posting"}, "amount_high": {"amount_in_cents"},
            "backdated": {"posted_before_purchase"}, "injection": {"memo_injection_plain", "memo_injection_paraphrase"}}

spec = demo_spec()
files = [sprinkle(spec, seed) for seed in SEEDS]
planted, found = {}, {}
two_hits = two_flagged = two_half = 0
recall = {lvl: [] for lvl in LEVELS}
totals = {lvl: [0, 0] for lvl in LEVELS}      # found, marked rows, pooled over the five files
leak = [0, 0, 0]                              # found, marked, flagged by a checker that reads is_bad
for made in files:
    flags = {lvl: flag_rows(made["rows"], lvl) for lvl in LEVELS}
    for lvl in LEVELS:
        sc = score(boolean_key(made), len(made["rows"]), set(flags[lvl]))
        recall[lvl].append(sc["recall"])
        totals[lvl][0] += sc["found"]
        totals[lvl][1] += sc["positives"]
    read_column = {r["row_id"] for r in made["rows"] if r["is_bad"] == "1"}
    sc = score(boolean_key(made), len(made["rows"]), read_column)
    leak = [leak[0] + sc["found"], leak[1] + sc["positives"], leak[2] + sc["flagged"]]
    for i, hit in enumerate(made["hits"]):
        fired = flags["tuned"].get(i + 1, [])
        fits = {b: any(b in EXPLAINS[r] for r in fired) for b in hit}
        for b in hit:
            planted[b] = planted.get(b, 0) + 1
            found[b] = found.get(b, 0) + fits[b]
        if len(hit) >= 2:
            two_hits += 1
            if fired:
                two_flagged += 1
                two_half += not all(fits.values())
pooled = {lvl: totals[lvl][0] / totals[lvl][1] for lvl in LEVELS}

print("STEP 3 - what the is_bad column hides")
print(f"  1 tuned recall reads {pooled['tuned']:.2f}. By planted failure, counted only when a rule that fired fits it (the file does not say):")
for b in sorted(planted):
    print(f"      {b:<28} found {found[b]} of {planted[b]}")
print(f"  2 rows hit by two failures: {two_hits}. The tuned rules flag {two_flagged} of them; in {two_half} the rules that fired explain only one of the two,")
print("    and the row still counts as found")
print(f"  3 a checker that reads the is_bad column: recall {leak[0] / leak[1]:.2f}, precision {leak[0] / leak[2]:.2f}. The column is in the data file.")
looks = sum(1 for b in spec["behaviors"] if b["role"] == "negative")
print(f"  4 the spec describes {looks} look-alike behaviors; the corruption loop skips them, as such loops usually do. False alarms on look-alikes: not measured.")
spread = max(recall["tuned"]) - min(recall["tuned"])
print(f"  5 tuned recall by file: {min(recall['tuned']):.2f} to {max(recall['tuned']):.2f} (spread {spread:.2f}). Gap between tuned and naive recall: {pooled['tuned'] - pooled['naive']:.2f}.")
print(f"KNOWN LIMIT: the tuned rules find {found['memo_injection_paraphrase']} of {planted['memo_injection_paraphrase']} paraphrased injections. Nothing in this step changes that.")
