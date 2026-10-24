"""Step 2 - The common check: look for each number in the output.

For every digit string after a green circle on a line, search the scripts' printed output for the
same text and flag it when it is not there. This is the number check in tools/check_repo.py, run
here on the synthetic projects. It is cheap and it finds the typo.

Run (from src/):  python3 step_02_grep_for_the_number.py
"""
from common import false_alarms, grep_lines, load_projects, load_truth, misses, score, tally

projects, truth = load_projects(), load_truth()
t = tally(truth, score(projects, truth, grep_lines))

print("step_02_grep_for_the_number.py - every digit string must appear in the output")
print(f"  unsupported bullets caught: {t['caught']} of {t['unsupported']}")
print(f"  fine bullets flagged by mistake: {t['false_alarms']} of {t['supported']}")
print(f"  missed, by planted kind: {misses(t)}")
print(f"  false alarms, by planted kind: {false_alarms(t)}")
print("  It passes any number that is a piece of a longer one, and it reads one line at a time.")
