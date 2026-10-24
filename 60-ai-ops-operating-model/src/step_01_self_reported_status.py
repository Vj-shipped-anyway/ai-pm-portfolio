"""Step 1 - Status quo: the owner says which stage the program has reached.

Sixty AI programs in bank operations each report a lifecycle stage, from 0 (nothing complete) to 8
(reviewed). The report goes into a status deck. Nobody opens an evidence register, so the deck shows
whatever the owner believes. The data is synthetic (data/_generate.py). The true stage of each program
comes from the evidence states the generator planted, not from any rule in this project.

Run (from src/):  python3 step_01_self_reported_status.py
"""
from common import load_all

d = load_all()
programs, truth = d["programs"], d["truth"]
n = len(programs)
same = sum(1 for p in programs if p["claimed_stage"] == truth[p["program_id"]]["true_stage"])
over = [p for p in programs if p["claimed_stage"] > truth[p["program_id"]]["true_stage"]]
under = [p for p in programs if p["claimed_stage"] < truth[p["program_id"]]["true_stage"]]
stages_over = sum(p["claimed_stage"] - truth[p["program_id"]]["true_stage"] for p in over)
late = [p for p in programs if p["claimed_stage"] >= 6]
late_over = [p for p in late if truth[p["program_id"]]["true_stage"] < 6]

print("STEP 1 - status as the owners report it")
print(f"  programs: {n}   checklist items: {len(d['checklist'])}   evidence rows on file: {len(d['register'])}")
print(f"  reported stage equals the true stage: {same} of {n}")
print(f"  reported stage above the true stage: {len(over)} of {n} ({stages_over} stages over in total)")
print(f"  reported stage below the true stage: {len(under)} of {n}")
print(f"  programs reporting stage 6 (hand-off) or later: {len(late)}; true stage below 6: {len(late_over)} of {len(late)}")
print("  Nobody reads the register, so the deck cannot tell an honest report from an optimistic one.")
