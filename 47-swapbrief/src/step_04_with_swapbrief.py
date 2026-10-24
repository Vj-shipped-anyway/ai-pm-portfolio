"""Step 4 - The fix: swapbrief, the brief on two files.

swapbrief (src/swapbrief.py) takes paired per-item results and a price table and prints:
  1. the headline accuracy change, with a paired bootstrap interval
  2. cost per correct answer, with an interval
  3. p50 and p95 latency, with an interval on p95
  4. a status per slice
  5. a decision: GO, GO WITH GUARDRAILS or NO-GO
  6. rollback triggers: metric, threshold, window

It is run on the committed set, then on the 80 simulated migrations of steps 1 to 3, and scored
against the planted truth next to the two earlier rules. The command line and this script run the
same code.

KNOWN LIMIT, left in on purpose: an interval on a slice of a few dozen items is wide. swapbrief
marks a slice INCONCLUSIVE when the interval is wide and reaches past the tolerance, but sampling
noise can still put the observed change near zero and a real regression passes. The script prints
how many pass, and each one with its planted change, its observed change and its interval.

Run (from src/):  python3 step_04_with_swapbrief.py        (about 15 seconds)
Output: a report, plus out/step_04_brief.json, out/step_04_scenarios.csv and out/step_04_summary.json
"""
import csv
import json
import os

from common import (committed, scenario, load_truth, point_metrics, basic_rule, headline_rule, analyze, render_text,
                    rate, ensure_out, OUT_DIR, gen, GO, GUARD, NOGO)

SIM_SEED = 47200000
RESAMPLES = 300
SMALL_SLICE = 50

pairs, prices = committed()
brief = analyze(pairs, prices, [s["name"] for s in gen.SLICES if s["critical"]], baseline="incumbent", candidate="successor")
print("STEP 4 - swapbrief")
print(render_text(brief))
print()

truth = load_truth()
rows, slice_rows = [], []
for t in truth:
    i = t["scenario"]
    p, pr, spec = scenario(i)
    crit = [s["name"] for s in spec["slices"] if s["critical"]]
    r = analyze(p, pr, crit, resamples=RESAMPLES, seed=SIM_SEED + i)
    m = point_metrics(p, pr)
    rows.append({"scenario": i, "kind": t["kind"], "bad": t["bad"], "bad_slice": t["bad_slice"], "bad_cost": t["bad_cost"], "bad_p95": t["bad_p95"],
                 "headline": headline_rule(m["acc_b"] - m["acc_a"]), "basic": basic_rule(m, pr), "swapbrief": r["decision"],
                 "cost_status": r["cost"]["status"], "p95_status": r["latency"]["status"],
                 "slice_inconclusive_critical": int(any(s["status"] == "INCONCLUSIVE" and s["critical"] for s in r["slices"])),
                 "slice_watch": int(any(s["status"] in ("WATCH", "REGRESSED") for s in r["slices"])),
                 "true_cost_ratio": t["true_cost_ratio"], "true_p95_ratio": t["true_p95_ratio"]})
    seen = {s["slice"]: s for s in r["slices"]}
    for s in spec["slices"]:
        planted = gen.clip(s["p_base"] + s["d"]) - gen.clip(s["p_base"])
        if planted <= -gen.BAD_SLICE_PP:
            o = seen[s["name"]]
            slice_rows.append({"scenario": i, "slice": s["name"], "n": s["n"], "status": o["status"], "planted": planted,
                               "delta": o["delta"], "lo": o["lo"], "hi": o["hi"]})

bad = [r for r in rows if r["bad"]]
good = [r for r in rows if not r["bad"]]
print("DECISION QUALITY on %d simulated migrations (%d carry a real problem, %d do not)" % (len(rows), len(bad), len(good)))
print("  %-24s %-18s %-20s %s" % ("rule", "false GO", "good stopped", "good given guardrails"))
for label, key in (("headline average", "headline"), ("average + vendor sheet", "basic"), ("swapbrief", "swapbrief")):
    guarded = sum(1 for r in good if r[key] == GUARD) if key == "swapbrief" else None
    print("  %-24s %-18s %-20s %s" % (label, rate(sum(1 for r in bad if r[key] == GO), len(bad)),
                                      rate(sum(1 for r in good if r[key] == NOGO), len(good)),
                                      rate(guarded, len(good)) if guarded is not None else "not applicable"))
print("  swapbrief on a migration with a real problem: GO %d, GO WITH GUARDRAILS %d, NO-GO %d" % tuple(
    sum(1 for r in bad if r["swapbrief"] == d) for d in (GO, GUARD, NOGO)))
guarded = [r for r in good if r["swapbrief"] == GUARD]
print("  good migrations given guardrails: %d; with an inconclusive critical slice %d, a watch or regressed slice %d, a cost flag %d, a p95 flag %d" % (
    len(guarded), sum(r["slice_inconclusive_critical"] for r in guarded), sum(r["slice_watch"] for r in guarded),
    sum(1 for r in guarded if r["cost_status"] != "OK"), sum(1 for r in guarded if r["p95_status"] != "OK")))
cost_bad = [r for r in rows if r["bad_cost"]]
p95_bad = [r for r in rows if r["bad_p95"]]
print("  cost problems with no cost flag: %s" % rate(sum(1 for r in cost_bad if r["cost_status"] == "OK"), len(cost_bad)))
print("  p95 problems with no p95 flag: %s" % rate(sum(1 for r in p95_bad if r["p95_status"] == "OK"), len(p95_bad)))

flagged = ("REGRESSED", "WATCH")
small = [r for r in slice_rows if r["n"] < SMALL_SLICE]
big = [r for r in slice_rows if r["n"] >= SMALL_SLICE]
print("  true slice regressions: %d" % len(slice_rows))
for label, grp in (("in slices of %d items or more" % SMALL_SLICE, big), ("in slices under %d items" % SMALL_SLICE, small)):
    print("    %-32s %d: %d flagged, %d inconclusive, %d missed" % (
        label, len(grp), sum(1 for r in grp if r["status"] in flagged),
        sum(1 for r in grp if r["status"] == "INCONCLUSIVE"), sum(1 for r in grp if r["status"] in ("OK", "IMPROVED"))))
missed = [r for r in slice_rows if r["status"] in ("OK", "IMPROVED")]
print("KNOWN LIMIT: %d of %d true slice regressions pass unflagged" % (len(missed), len(slice_rows)))
for r in missed:
    print("    scenario %d, %s (%d items): planted %+.1f pp, observed %+.1f pp, interval %+.1f to %+.1f pp, status %s" % (
        r["scenario"], r["slice"], r["n"], r["planted"] * 100, r["delta"] * 100, r["lo"] * 100, r["hi"] * 100, r["status"]))
silent = [r for r in bad if r["swapbrief"] == GO]
print("  migrations with a real problem that still get GO: %s" % (", ".join(str(r["scenario"]) for r in silent) or "none"))
print("PLANTED HARD CASES, swapbrief decision")
for kind, label in (("hard_miss", "a real 7 to 10 pp fall in the 30-item account_closure slice, everything else clean"),
                    ("hard_negative", "a good migration whose true cost per correct answer is 1.06x to 1.09x")):
    grp = [r for r in rows if r["kind"] == kind]
    print("  %-14s %d scenarios (%s): GO %d, GO WITH GUARDRAILS %d, NO-GO %d" % (
        kind, len(grp), label, *(sum(1 for r in grp if r["swapbrief"] == d) for d in (GO, GUARD, NOGO))))

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_brief.json"), "w", encoding="utf-8") as fh:
    json.dump(brief, fh, indent=1, sort_keys=True)
with open(os.path.join(OUT_DIR, "step_04_scenarios.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
summary = {"scenarios": len(rows), "bad": len(bad), "good": len(good),
           "false_go": {k: sum(1 for r in bad if r[k] == GO) for k in ("headline", "basic", "swapbrief")},
           "good_stopped": {k: sum(1 for r in good if r[k] == NOGO) for k in ("headline", "basic", "swapbrief")},
           "good_guarded": sum(1 for r in good if r["swapbrief"] == GUARD),
           "slice_regressions": len(slice_rows), "slice_regressions_missed": len(missed)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_brief.json, step_04_scenarios.csv and step_04_summary.json in src/out/")
