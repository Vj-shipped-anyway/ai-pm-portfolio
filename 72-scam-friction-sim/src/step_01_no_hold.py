"""Step 1 - Status quo: no hold. Every payment goes out at once.

This is the baseline the other steps are scored against: how much scam value passes, which scenarios it
comes from, and the one thing doing nothing costs nobody, which is waiting time. It also prints the
assumptions every later number depends on. They are invented. Edit data/assumptions.json to change them.

Run (from src/):  python3 step_01_no_hold.py
"""
from __future__ import annotations

from common import fmt_money, fmt_pct, load_all, metrics, policy_none, simulate

rows, A = load_all()
r = simulate(rows, policy_none(), A)
m = metrics(r)
total_value = sum(p["amount"] for p in rows)

print("STEP 1 - no hold")
print("  assumptions (invented, not measured; data/assumptions.json):")
print(f"    hold length: {A['hold_minutes']:g} minutes; in-app warning: {A['warn_minutes']:g} minutes")
print(f"    a held legitimate payment is abandoned with probability {A['legit_abandon_on_hold']:g}; after a warning only, {A['legit_abandon_on_warn']:g}")
print(f"    a warning has {A['warn_factor']:g} of the effect of a hold on a scam payment")
print(f"    a scammer in touch with the victim coaches them through the hold in {A['coach_rate']:g} of cases")
for name in sorted(A["scam_scenarios"]):
    s = A["scam_scenarios"][name]
    print(f"    {name:<15} a held victim gives up with probability {s['p_abandon']:g}; scammer in touch: {'yes' if s['human_scammer'] else 'no'}")
print(f"  payments: {r['payments']} ({r['scam_n']} scam, {r['legit_n']} legitimate)")
print(f"  scam value passing: {fmt_money(r['scam_value'])} of {fmt_money(total_value)} moved ({fmt_pct(100.0 * r['scam_value'] / total_value)})")
by_value = {}
for p in rows:
    if p["is_scam"]:
        by_value[p["scenario"]] = by_value.get(p["scenario"], 0.0) + p["amount"]
for name in sorted(by_value):
    print(f"    {name:<15} {r['scam_by_scenario'][name]:>4} payments, {fmt_money(by_value[name])}")
print(f"  scam payments stopped: {r['scam_stopped_n']} of {r['scam_n']} ({fmt_pct(m['stopped_pct'])} of value)")
print(f"  legitimate payments held: {r['legit_held']}; minutes waited: {r['legit_minutes']:g}")
print("  Nothing is held, so nobody waits and nothing is stopped. Step 2 adds the rule most teams start with.")
