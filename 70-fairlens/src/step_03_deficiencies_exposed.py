"""Step 3 - Where each check fails when used alone.

Three checks, each with one idea, scored on the same 36 portfolios against the planted truth:
  point AIR       flag a portfolio when the lowest group's approval ratio is under 0.80 (point estimate)
  ablation alone  call it a proxy when removing the proxy points lifts the lowest AIR by 0.05 or more,
                  with no accuracy check and no interval
  reason review   step 2

KNOWN LIMIT, left in on purpose: the proxy ablation names one column. A second proxy that it is
not pointed at, and a proxy worth only a few points, get through step 4 as well. This step prints
them.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import load_cases, run_cases, mechanisms

LIFT = 0.05           # the same lift the pack uses for REVIEW
cases = load_cases()
packs = run_cases(cases)
t = {c["id"]: {x["id"]: x for x in packs[c["id"]]["tests"]} for c in cases}
planted = [c for c in cases if c["planted"]]
others = [c for c in cases if not c["planted"]]


def of(m):
    return [c for c in cases if c["mechanism"] == m]


print("STEP 3 - each check alone")
flag_air = [c for c in cases if packs[c["id"]]["gs"]["min_air"] < 0.80]
print("  A. point AIR under 0.80")
print(f"     flags {len(flag_air)} of {len(cases)} portfolios; planted proxies among them: {sum(1 for c in flag_air if c['planted'])}")
noise = of("small_group_noise")
print(f"     small_group_noise (groups drawn identically): flagged {sum(1 for c in noise if packs[c['id']]['gs']['min_air'] < 0.80)} of {len(noise)}; "
      f"with the 95% interval, T2 FAIL {sum(1 for c in noise if t[c['id']]['T2']['verdict'] == 'FAIL')} and REVIEW {sum(1 for c in noise if t[c['id']]['T2']['verdict'] == 'REVIEW')}")
legit = of("legit_gap")
print(f"     legit_gap (real risk differences, no proxy): flagged {sum(1 for c in legit if packs[c['id']]['gs']['min_air'] < 0.80)} of {len(legit)}; "
      "the ratio cannot say the cause is not a proxy")

print("  B. ablation alone (lift of 0.05 or more = proxy)")
naive = {c["id"]: t[c["id"]]["T4"]["lift"] >= LIFT for c in cases}
print(f"     planted proxies called: {sum(1 for c in planted if naive[c['id']])} of {len(planted)}")
for m in mechanisms(cases):
    ms = of(m)
    print(f"       {m:<20} called {sum(1 for c in ms if naive[c['id']])} of {len(ms)}")
pred = of("proxy_predictive")
lost = ", ".join("%.1f" % t[c["id"]]["T4"]["cost_pts"] for c in pred)
print(f"     proxy_predictive (the feature also predicts default): called {sum(1 for c in pred if naive[c['id']])} of {len(pred)}; "
      f"accuracy lost by removing it, in points: {lost}")
print(f"     false alarms on the {len(others)} portfolios with no planted proxy: {sum(1 for c in others if naive[c['id']])}")

print("  C. reason-code review alone (T5)")
print(f"     planted proxies passed: {sum(1 for c in planted if t[c['id']]['T5']['verdict'] == 'PASS')} of {len(planted)}")

print("KNOWN LIMIT (left in on purpose): what the pack's T4 does not mark FAIL")
for m in ("two_proxies", "quiet_proxy"):
    for c in of(m):
        x = t[c["id"]]["T4"]
        print(f"    {c['id']} {m:<12} lowest AIR {x['before']:.3f} -> {x['after']:.3f} (lift {x['lift']:+.3f}), T4 {x['verdict']}")
print("  Step 4 does not fix this. It names one column; a proxy it is not pointed at stays in the score.")
