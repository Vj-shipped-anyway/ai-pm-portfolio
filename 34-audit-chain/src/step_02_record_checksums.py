"""Step 2 - The common basic approach: a checksum on each event, and a check that sequence numbers run 1, 2, 3.

Each event stores a hash of its own content. A reader recomputes it, and also checks that no sequence
number is missing or out of order. This is what a careful engineer adds first. It does not look at how
one event relates to its neighbours beyond the sequence number. The same 101 planted edits as step 1.

Run (from src/):  python3 step_02_record_checksums.py
"""
from common import evaluate, tally, ops_in

rows = evaluate()["rows"]
t_flag, t_all = tally(rows, "records", truth="tampered")
b_flag, b_all = tally(rows, "records", truth="benign")

print("STEP 2 (step_02_record_checksums.py) - per-event checksum and sequence check")
print(f"  tampered logs flagged: {t_flag} of {t_all}")
print(f"  benign changes flagged: {b_flag} of {b_all}")
print("  by planted edit:")
for op in ops_in(rows, "tampered"):
    f, n = tally(rows, "records", op=op)
    print(f"    {op:<14} flagged {f} of {n}")
print("  It catches an edit nobody covered up and a line deleted without renumbering. A person who recomputes")
print("  the checksum, or renumbers after a delete, produces a log that passes; step 3 counts them.")
