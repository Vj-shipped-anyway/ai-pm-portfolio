"""Step 2 - The common basic approach: the average, the list price per token and the median latency.

This is what a vendor page and a quick benchmark give a team: average accuracy, price per token and
a typical response time. The rule: GO when accuracy is not lower, both token prices are not higher
and the median latency is not higher. It is applied to the committed set and to the same 80
simulated migrations as step 1.

Run (from src/):  python3 step_02_average_plus_vendor_sheet.py
"""
from common import committed, scenario, load_truth, point_metrics, basic_rule, rate, GO

pairs, prices = committed()
m = point_metrics(pairs, prices)
print("STEP 2 - average, list price per token, median latency")
print("  committed set: accuracy %+.1f pp, list price per token %.2fx, median latency %.2fx -> %s" % (
    (m["acc_b"] - m["acc_a"]) * 100, prices["cand"][1] / prices["base"][1], m["p50_ratio"], basic_rule(m, prices)))

truth = load_truth()
said = {}
for t in truth:
    p, pr, _ = scenario(t["scenario"])
    said[t["scenario"]] = basic_rule(point_metrics(p, pr), pr)
bad = [t for t in truth if t["bad"]]
good = [t for t in truth if not t["bad"]]
print("  false GO: %s" % rate(sum(1 for t in bad if said[t["scenario"]] == GO), len(bad)))
print("  good migrations stopped: %s" % rate(sum(1 for t in good if said[t["scenario"]] != GO), len(good)))
for label, key in (("cost per correct answer", "bad_cost"), ("p95 latency", "bad_p95"), ("a regressed slice", "bad_slice")):
    sub = [t for t in truth if t[key]]
    print("  migrations with a real problem in %s that get GO: %s" % (label, rate(sum(1 for t in sub if said[t["scenario"]] == GO), len(sub))))
print("  rollback triggers written down: 0")
