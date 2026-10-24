"""Step 2 - The common basic approach: a blanket hold.

Hold every first payment to a new payee at or above $500 for the hold length. The rule looks only at
the payee and the amount, so it is easy to explain and easy to build. This step scores it: what it
stops, who it holds, and what the waiting costs.

Run (from src/):  python3 step_02_blanket_hold.py
"""
from __future__ import annotations

from common import BLANKET_MIN_AMOUNT, HARD_NEGATIVE, fmt_money, fmt_pct, load_all, metrics, policy_blanket, simulate

rows, A = load_all()
r = simulate(rows, policy_blanket(BLANKET_MIN_AMOUNT), A)
m = metrics(r)

print(f"STEP 2 - blanket hold: first payment to a new payee, {BLANKET_MIN_AMOUNT} or more")
print(f"  scam payments held: {r['scam_held_n']} of {r['scam_n']}; stopped: {r['scam_stopped_n']}")
print(f"  scam value stopped: {fmt_money(r['scam_stopped_value'])} of {fmt_money(r['scam_value'])} ({fmt_pct(m['stopped_pct'])})")
print(f"  legitimate payments held: {r['legit_held']} of {r['legit_n']} ({fmt_pct(m['legit_held_pct'])})")
print(f"  legitimate payments lost (customer gave up): {r['legit_lost']}")
print(f"  minutes legitimate customers waited: {r['legit_minutes']:g}; value delayed: {fmt_money(r['legit_value_delayed'])}")
print(f"  legitimate holds per scam payment stopped: {m['holds_per_stopped']:.1f}")
print("  by scenario (stopped of total scam payments):")
for name in sorted(r["scam_by_scenario"]):
    print(f"    {name:<15} {r['stopped_by_scenario'].get(name, 0):>3} of {r['scam_by_scenario'][name]}")
print(f"  hard negative, a large first payment that is legitimate ({HARD_NEGATIVE}): "
      f"{r['legit_held_by_scenario'].get(HARD_NEGATIVE, 0)} of {r['legit_by_scenario'][HARD_NEGATIVE]} held")
print("  The rule stops something and holds a lot of people who did nothing wrong. Step 3 shows where the number cannot be trusted.")
