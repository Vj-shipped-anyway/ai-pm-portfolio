"""Step 1 - Status quo: decide on the headline average.

The candidate model scores higher on the team's evaluation set, so the team moves. This step
applies that rule, GO when the candidate's average accuracy is not lower, to the committed set
and to 80 simulated migrations whose true problems are planted (data/_generate.py). Everything
is synthetic: no model was called.

Run (from src/):  python3 step_01_headline_average.py
"""
from common import committed, scenario, load_truth, point_metrics, headline_rule, rate, GO

pairs, prices = committed()
m = point_metrics(pairs, prices)
print("STEP 1 - the headline average")
print("  committed set: %d paired items, accuracy %.1f%% -> %.1f%% (%+.1f pp), rule says %s" % (
    len(pairs["item"]), m["acc_a"] * 100, m["acc_b"] * 100, (m["acc_b"] - m["acc_a"]) * 100, headline_rule(m["acc_b"] - m["acc_a"])))

truth = load_truth()
said = {}
for t in truth:
    p, pr, _ = scenario(t["scenario"])
    mm = point_metrics(p, pr)
    said[t["scenario"]] = headline_rule(mm["acc_b"] - mm["acc_a"])
bad = [t for t in truth if t["bad"]]
good = [t for t in truth if not t["bad"]]
print("  simulated migrations: %d, of which %d carry a real problem (a slice down 5 pp or more, cost per correct answer up 10%% or more, or p95 up 25%% or more)" % (len(truth), len(bad)))
print("  false GO (a migration with a real problem gets GO): %s" % rate(sum(1 for t in bad if said[t["scenario"]] == GO), len(bad)))
print("  good migrations stopped: %s" % rate(sum(1 for t in good if said[t["scenario"]] != GO), len(good)))
for label, key in (("cost per correct answer", "bad_cost"), ("p95 latency", "bad_p95"), ("a regressed slice", "bad_slice")):
    sub = [t for t in truth if t[key]]
    print("  migrations with a real problem in %s that get GO: %s" % (label, rate(sum(1 for t in sub if said[t["scenario"]] == GO), len(sub))))
print("  rollback triggers written down: 0")
