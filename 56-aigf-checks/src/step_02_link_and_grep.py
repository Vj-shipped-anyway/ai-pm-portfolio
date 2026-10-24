"""Step 2 - The common basic approach: resolve the ids and grep for the number.

The usual script over a crosswalk does two things. It checks that the risk id and the check id
exist, and it looks for the claimed value anywhere in the check's printed output. A row whose
check has no output file is skipped, as a grep loop over missing files does. The truth is known,
so this step counts what it catches and what it flags by mistake.

Run (from src/):  python3 step_02_link_and_grep.py
"""
from __future__ import annotations

from common import HARD_NEGATIVES, basic_flags, basic_status, load_all, score, status_counts, status_right


def main() -> None:
    d = load_all()
    flags = basic_flags(d)
    s = score(d, flags)
    status = basic_status(d, flags)
    print("STEP 2 - resolve the ids, grep for the number")
    print(f"  rows flagged: {s['flagged']} of {s['rows']}")
    print(f"  defective rows flagged: {s['found']} of {s['defective']}")
    print(f"  harmless rows flagged by mistake: {s['false_alarms']} of {s['clean']}")
    for kind in HARD_NEGATIVES:
        f, n = s["by_kind"][kind]
        print(f"    {kind}: {f} of {n}")
    print(f"  risks with the right status: {status_right(d, status)} of {len(d['risks'])}")
    print(f"  status it gives: {status_counts(status)}")
    print("  It cannot say PARTIAL for a check that covers one aspect of a risk, and it trusts the covers column.")


if __name__ == "__main__":
    main()
