"""Step 1 - Status quo: nobody checks the packet before it goes out.

A dispute arrives, someone gathers what they can find into a packet, and it is sent. Nothing compares
the packet with the evidence list for that reason code, and nothing watches the clock. This step
takes the 100 synthetic cases as they stand and counts the packets that go out with a planted fault.
The data is synthetic (data/_generate.py), and the truth label of each case is the fault that was
planted into a good packet, not anything a checker said.

Run (from src/):  python3 step_01_no_check.py
"""
from collections import Counter

from common import load_cases, total_cents, dollars

items = load_cases()
truth = Counter(it["truth"] for it in items)
faulty = [it for it in items if it["truth"] != "ready"]
by_kind = Counter(it["kind"] for it in faulty)

print("STEP 1 - no packet check")
print(f"  dispute cases: {len(items)}   disputed value: ${dollars(total_cents(items))}")
print(f"  planted truth: {truth['ready']} ready, {truth['defective']} defective (clock still running), {truth['late']} late")
print(f"  packets that go out with a planted fault: {len(faulty)} of {len(items)}")
print(f"  disputed value inside those packets: ${dollars(total_cents(faulty))} of ${dollars(total_cents(items))}")
print(f"  late before anyone looked: {truth['late']} of {len(items)}; fixable if someone had looked in time: {truth['defective']} of {len(items)}")
print("  faulty packets by planted fault: " + ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items())))
print("  Nothing on this path tells anyone about a fault before the packet leaves.")
