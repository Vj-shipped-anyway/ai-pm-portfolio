"""Step 4 - The fix: score each payment, hold only the top band, warn the next band.

The score is a handful of points from what a bank can see when the payment is made: a first payment to a
new payee, an amount far above the customer's usual, a phone call in progress, a device the bank has not
seen, the hour. The hold threshold comes from a stated friction budget, not from the stopped number: it is
the lowest score at which no more than 0.5% of legitimate payments wait (the budget is an assumption).
Payments one or two points under that threshold get an in-app warning and no wait.

KNOWN LIMIT, left in on purpose: a scam to a payee the customer has paid for weeks scores 3 at most, so
it is not held. The script prints those payments.

Run (from src/):  python3 step_04_scored_hold.py
Output: a report, plus out/step_04_grid.csv and out/step_04_summary.json
"""
from __future__ import annotations

import csv
import json
import os

from common import (BLANKET_MIN_AMOUNT, HARD_CASE, HARD_NEGATIVE, OUT_DIR, changed, ensure_out, fmt_money, fmt_pct, load_all,
                    metrics, policy_blanket, policy_none, policy_score, simulate, tier)

BUDGET_PCT = 0.5
WARN_BELOW_HOLD = 2
SCORE_RANGE = range(1, 14)

rows, A = load_all()
blanket = policy_blanket(BLANKET_MIN_AMOUNT)
rb = simulate(rows, blanket, A)
mb = metrics(rb)

hold_at = next(h for h in SCORE_RANGE if metrics(simulate(rows, policy_score(h), A))["legit_held_pct"] <= BUDGET_PCT)
chosen = policy_score(hold_at, hold_at - WARN_BELOW_HOLD)
rc = simulate(rows, chosen, A)
mc = metrics(rc)

same_friction_at = next(h for h in SCORE_RANGE if simulate(rows, policy_score(h), A)["legit_held"] <= rb["legit_held"])
rs = simulate(rows, policy_score(same_friction_at), A)

print("STEP 4 - score the payment, hold the top band, warn the next")
print(f"  friction budget (assumed): at most {BUDGET_PCT:g}% of legitimate payments held")
print(f"  chosen: hold at score {hold_at} or more, warn at {chosen['warn_score']} and {hold_at - 1}")
print(f"  scam value stopped: {fmt_money(rc['scam_stopped_value'])} of {fmt_money(rc['scam_value'])} ({fmt_pct(mc['stopped_pct'])}); blanket rule {fmt_pct(mb['stopped_pct'])}")
print(f"  legitimate payments held: {rc['legit_held']} of {rc['legit_n']} ({fmt_pct(mc['legit_held_pct'])}); blanket rule {rb['legit_held']} ({fmt_pct(mb['legit_held_pct'])})")
print(f"  legitimate payments warned: {rc['legit_warned']}; lost: {rc['legit_lost']} (blanket rule {rb['legit_lost']})")
print(f"  minutes legitimate customers waited: {rc['legit_minutes']:g} (blanket rule {rb['legit_minutes']:g})")
print(f"  legitimate holds per scam payment stopped: {mc['holds_per_stopped']:.1f} (blanket rule {mb['holds_per_stopped']:.1f})")
print(f"  at the blanket rule's friction (hold only, score {same_friction_at} or more): {rs['legit_held']} legitimate held, "
      f"{fmt_pct(metrics(rs)['stopped_pct'])} of scam value stopped")
print(f"  hard negative, a large first payment that is legitimate ({HARD_NEGATIVE}): "
      f"{rc['legit_held_by_scenario'].get(HARD_NEGATIVE, 0)} of {rc['legit_by_scenario'][HARD_NEGATIVE]} held (blanket rule {rb['legit_held_by_scenario'][HARD_NEGATIVE]})")
for c in (0.5, 0.8):
    a2 = changed(A, coach_rate=c)
    print(f"  with coaching at {c:g}: chosen policy stops {fmt_pct(metrics(simulate(rows, chosen, a2))['stopped_pct'])}, "
          f"blanket rule {fmt_pct(metrics(simulate(rows, blanket, a2))['stopped_pct'])}")
print(f"  with scams one-tenth as common: legitimate holds per scam payment stopped {metrics(rc, 10)['holds_per_stopped']:.1f} "
      f"(blanket rule {metrics(rb, 10)['holds_per_stopped']:.1f})")
print("  by scenario (stopped of total scam payments):")
for name in sorted(rc["scam_by_scenario"]):
    print(f"    {name:<15} {rc['stopped_by_scenario'].get(name, 0):>3} of {rc['scam_by_scenario'][name]}")
passed = [p for p in rows if p["is_scam"] and tier(p, chosen) == "PASS"]
passed_hard = [p for p in passed if p["scenario"] == HARD_CASE]
print(f"  scam payments that get neither a hold nor a warning: {len(passed)} of {rc['scam_n']}, {fmt_money(sum(p['amount'] for p in passed))}")
print(f"  KNOWN LIMIT: {HARD_CASE}, a payee the customer has paid for weeks: {len(passed_hard)} of "
      f"{rc['scam_by_scenario'][HARD_CASE]} pass untouched ({fmt_money(sum(p['amount'] for p in passed_hard))}); stopped: {rc['stopped_by_scenario'].get(HARD_CASE, 0)}")

grid = []
for coach in (0.0, 0.2, 0.5, 0.8):
    a2 = changed(A, coach_rate=coach)
    pols = [("no hold", policy_none()), (f"blanket: new payee, {BLANKET_MIN_AMOUNT} or more", blanket)]
    pols += [(f"score {h} or more", policy_score(h)) for h in range(2, 11)]
    pols.append((f"score {hold_at} or more, warn {chosen['warn_score']}", chosen))
    for label, pol in pols:
        r = simulate(rows, pol, a2)
        for w in (1, 10):
            m = metrics(r, w)
            grid.append({"policy": label, "coach_rate": coach, "legit_weight": w,
                         "stopped_pct": round(m["stopped_pct"], 1), "scam_stopped": r["scam_stopped_n"], "scam_total": r["scam_n"],
                         "legit_held": round(r["legit_held"] * w), "legit_held_pct": round(m["legit_held_pct"], 2),
                         "legit_lost": round(m["legit_lost"]),
                         "holds_per_stopped": "" if m["holds_per_stopped"] is None else round(m["holds_per_stopped"], 1)})

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_grid.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(grid[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(grid)
summary = {"hold_score": hold_at, "warn_score": chosen["warn_score"], "budget_pct": BUDGET_PCT,
           "stopped_pct": round(mc["stopped_pct"], 1), "blanket_stopped_pct": round(mb["stopped_pct"], 1),
           "legit_held": rc["legit_held"], "blanket_legit_held": rb["legit_held"], "legit_n": rc["legit_n"],
           "legit_lost": rc["legit_lost"], "blanket_legit_lost": rb["legit_lost"],
           "same_friction_stopped_pct": round(metrics(rs)["stopped_pct"], 1), "same_friction_score": same_friction_at,
           "scam_n": rc["scam_n"], "scam_passing_untouched": len(passed), "hard_case_passing": len(passed_hard)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_grid.csv and step_04_summary.json in src/out/")
