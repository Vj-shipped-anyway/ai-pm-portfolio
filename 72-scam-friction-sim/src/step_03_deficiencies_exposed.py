"""Step 3 - Where the blanket hold, and the way it is scored, fall short.

Six checks on the step 2 rule, each changing one thing:
  1. the ceiling: what a hold on every payment would stop
  2. the response assumptions, scaled down and up
  3. coaching: a scammer who has told the victim to wait out the hold
  4. how common scams are: the same rule at one-tenth and one-hundredth of the scam rate
  5. hold length: the model has no curve for it, which the script shows
  6. KNOWN LIMIT, left in on purpose: scams to a payee the customer has paid for weeks never reach a
     hold. Step 4 does not fix that either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from __future__ import annotations

from common import (BLANKET_MIN_AMOUNT, HARD_CASE, changed, fmt_pct, load_all, metrics, policy_blanket, policy_score,
                    risk_score, scaled_response, simulate, tier)

rows, A = load_all()
blanket = policy_blanket(BLANKET_MIN_AMOUNT)


def stopped(assumptions: dict, policy: dict) -> str:
    return fmt_pct(metrics(simulate(rows, policy, assumptions))["stopped_pct"])


print("STEP 3 - where the hold falls short")
hold_all = policy_score(0)
print("  1. The ceiling is set by the customers, not by the rule")
print(f"     hold every payment, no coaching: {stopped(changed(A, coach_rate=0.0), hold_all)} of scam value stopped")
print(f"     hold every payment, coaching at {A['coach_rate']:g}: {stopped(A, hold_all)}")
print("  2. The answer moves with the response assumptions (blanket rule, all give-up probabilities scaled)")
print("     " + ", ".join(f"x{f:g}: {stopped(scaled_response(A, f), blanket)}" for f in (0.5, 1.0, 1.5)))
print("  3. Coaching (blanket rule, share of victims with a scammer in touch who wait it out)")
print("     " + ", ".join(f"{c:g}: {stopped(changed(A, coach_rate=c), blanket)}" for c in (0.0, 0.2, 0.5, 0.8)))

r = simulate(rows, blanket, A)
print("  4. How common scams are (blanket rule; legitimate payments counted w times, so scams are 1/w as common)")
for w in (1, 10, 100):
    m = metrics(r, w)
    print(f"     w={w:<3} legitimate payments held per scam payment stopped: {m['holds_per_stopped']:.1f}")

print("  5. Hold length (blanket rule)")
for minutes in (5, 20, 60):
    rr = simulate(rows, blanket, changed(A, hold_minutes=minutes))
    print(f"     {minutes:>2} minutes: scam value stopped {fmt_pct(metrics(rr)['stopped_pct'])}; legitimate minutes waited {rr['legit_minutes']:g}")
print("     The stop rate does not move because the model gives the give-up probability no dependence on length. That is an assumption, not a finding.")

hard = [p for p in rows if p["scenario"] == HARD_CASE]
hard_value = sum(p["amount"] for p in hard)
held_hard = sum(1 for p in hard if tier(p, blanket) == "HOLD")
scores = sorted((risk_score(p) for p in hard), reverse=True)
half_score = scores[(len(scores) + 1) // 2 - 1]
r_half = simulate(rows, policy_score(half_score), A)
print(f"  6. KNOWN LIMIT: scams to a payee the customer has paid before ({HARD_CASE})")
print(f"     {len(hard)} payments, ${hard_value:,.0f}, held by the blanket rule: {held_hard}")
print(f"     highest risk score among them: {scores[0]}; to hold half of them the score threshold would drop to {half_score},")
print(f"     which holds {r_half['legit_held']} of {r_half['legit_n']} legitimate payments ({fmt_pct(metrics(r_half)['legit_held_pct'])})")
