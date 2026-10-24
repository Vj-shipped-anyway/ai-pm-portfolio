"""Step 2 - The common basic approach: compare the legacy value with the ISO value, field by field.

This is what a person does with a diff tool or a short script. For every mapping row that copies one
field to one element, take the legacy value (without its fixed-width padding) and compare it with the
ISO value as written, character for character. Rows that change the value on the way (amount, date,
code table, joined lines) cannot be compared this way and are skipped. The mapping itself is not
examined. Scored against the planted events on the same 230 pairs.

Run (from src/):  python3 step_02_exact_compare.py
"""
from common import all_pairs, truth_events, bundle, score, CONVERTER

pairs, truth, bun = all_pairs(), truth_events(), bundle()
copy_rows = [r for r in bun["rows"] if r["transform"] == "copy"]
copy_paths = {r["iso_path"] for r in copy_rows}


def exact_flags(p) -> set:
    return {(r["iso_path"], "mismatch") for r in copy_rows
            if p["source"].get(r["fields"][0], "").rstrip() and p["target"].get(r["iso_path"], "") != p["source"][r["fields"][0]].rstrip()}


flags = {(p["build"], p["msg"]): exact_flags(p) for p in pairs}
s = score(pairs, truth, flags)
blind = sum(1 for p in pairs for subj, _k, c in truth.get((p["build"], p["msg"]), []) if c in CONVERTER and subj not in copy_paths)
total = sum(1 for p in pairs for subj, _k, c in truth.get((p["build"], p["msg"]), []) if c in CONVERTER)

print("STEP 2 - exact comparison on one-to-one copy rows")
print(f"  rows compared: {len(copy_rows)} of {len(bun['rows'])} mapping rows (the rest change the value on the way)")
print(f"  pairs flagged: {sum(1 for f in flags.values() if f)} of {s['pairs']}")
print(f"  defective pairs caught: {s['defective_caught']} of {s['defective_pairs']}")
print(f"  pairs flagged with no planted defect: {s['false_alarm_pairs']} of {s['pairs']}")
print(f"  harmless variations flagged (padding, trailing zeros): {s['benign_flagged']} of {s['benign']}")
print(f"  planted defects on rows it cannot compare: {blind} of {total}")
print("  A padded name looks like a defect, and a rounded amount or a swapped date goes unseen.")
