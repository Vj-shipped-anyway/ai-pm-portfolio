"""Step 3 - Deficiencies exposed: what the average, the price per token and the median cannot see.

Six checks on the committed set and on the 80 simulated migrations:
  1. list price per token against cost per correct answer
  2. median latency against p95
  3. a slice that falls inside a rising average
  4. how far a single sample moves the p95 number
  5. which kind of problem the basic rule lets through
  6. the rollback triggers it leaves unwritten

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
import json
import os

from common import DATA, committed, scenario, load_truth, point_metrics, basic_rule, rate, gen, build_pairs, BASE, CAND, GO

pairs, prices = committed()
m = point_metrics(pairs, prices)
spec = gen.committed_spec()
with open(os.path.join(DATA, "committed_world.json"), encoding="utf-8") as fh:
    world = json.load(fh)

print("STEP 3 - what the basic approach cannot see (committed set)")
print("  1. list price per output token %.2fx, cost per correct answer %.2fx (answers are longer, so the cheaper token buys a dearer answer)" % (
    prices["cand"][1] / prices["base"][1], m["cost_ratio"]))
print("  2. median latency %.2fx, p95 latency %.2fx (true p95 ratio %.2fx)" % (m["p50_ratio"], m["p95_ratio"], world["true_p95_ratio"]))

observed = {}
for name, a, b in zip(pairs["slice"], pairs["base"]["ok"], pairs["cand"]["ok"]):
    cnt = observed.setdefault(name, [0, 0, 0])
    cnt[0] += 1
    cnt[1] += a
    cnt[2] += b
worst = min(spec["slices"], key=lambda s: gen.clip(s["p_base"] + s["d"]) - gen.clip(s["p_base"]))
n, a, b = observed[worst["name"]]
true_pp = (gen.clip(worst["p_base"] + worst["d"]) - gen.clip(worst["p_base"])) * 100
print("  3. the average moves %+.1f pp; slice %s (%d items) has a planted change of %+.1f pp and shows %+.1f pp in this sample" % (
    (m["acc_b"] - m["acc_a"]) * 100, worst["name"], n, true_pp, (b - a) / n * 100))

p95s, costs = [], []
for k in range(1, 21):
    p = build_pairs(gen.simulate(spec, gen.SEED + k), BASE, CAND)
    mm = point_metrics(p, prices)
    p95s.append(mm["p95_ratio"])
    costs.append(mm["cost_ratio"])
print("  4. 20 fresh samples of the same world: p95 ratio from %.2fx to %.2fx, cost per correct answer from %.2fx to %.2fx (one number, no interval)" % (
    min(p95s), max(p95s), min(costs), max(costs)))

truth = load_truth()
passed = []
for t in truth:
    if not t["bad"]:
        continue
    p, pr, _ = scenario(t["scenario"])
    if basic_rule(point_metrics(p, pr), pr) == GO:
        passed.append(t)
causes = {"cost only": 0, "p95 only": 0, "slice only": 0, "two or more": 0}
for t in passed:
    kinds = [k for k in ("bad_cost", "bad_p95", "bad_slice") if t[k]]
    if len(kinds) > 1:
        causes["two or more"] += 1
    else:
        causes[{"bad_cost": "cost only", "bad_p95": "p95 only", "bad_slice": "slice only"}[kinds[0]]] += 1
print("  5. over 80 simulated migrations the basic rule says GO to %s that carry a real problem:" % rate(len(passed), sum(t["bad"] for t in truth)))
for k in ("cost only", "p95 only", "slice only", "two or more"):
    print("       %-12s %d" % (k, causes[k]))
print("  6. rollback triggers written down by the basic approach: 0")
