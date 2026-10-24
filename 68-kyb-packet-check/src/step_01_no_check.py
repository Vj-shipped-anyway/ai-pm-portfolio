"""Step 1 - Status quo: whatever the model read goes straight into the case file.

Seventy-five synthetic business-onboarding packets. For each one a model has read the filing and
returned the owners, their percentages, the control person and the details. Nothing compares that
reading with the filing. The planted truth (data/_generate.py) says which readings are wrong, so
this step counts what reaches the file. The data is synthetic and the misreads are planted, so the
counts say how much a check has to find, not how often a real model misreads.

Run (from src/):  python3 step_01_no_check.py
"""
from __future__ import annotations

from collections import Counter

from common import load_packets, owners_in_file


def main() -> None:
    packets = load_packets()
    bad = [p for p in packets if p["defect"]]
    wrong = [p for p in packets if owners_in_file(p["raw"]) != p["true_owners"]]
    print("STEP 1 (step_01_no_check.py) - no check between the extraction and the case file")
    print(f"  packets: {len(packets)}   planted misreads: {len(bad)}   clean: {len(packets) - len(bad)}")
    print(f"  packets the current process stops: 0 of {len(packets)}")
    print(f"  packets whose file would list the wrong people: {len(wrong)} of {len(packets)}")
    print("    (people = individuals at 25 percent or more, plus the control person)")
    print("  wrong-people packets by planted misread: "
          + ", ".join(f"{k} {v}" for k, v in sorted(Counter(p["scenario"] for p in wrong).items())))
    print("  Every one of these reaches the file, and nothing in the file marks it as a misread.")


if __name__ == "__main__":
    main()
