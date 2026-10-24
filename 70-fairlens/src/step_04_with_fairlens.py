"""Step 4 - The fix: the six-test pack, run as the command-line tool runs it.

  T1 approval gap   T2 AIR with a bootstrap interval   T3 cutoff sweep
  T4 proxy ablation, with an accuracy check   T5 reason pairs   T6 reason naming

Scored on the same 36 portfolios against the planted truth. The tool is fairlens_pack.py; this
script calls the same functions the command line does.

KNOWN LIMIT, left in on purpose: some planted proxies still get through T4 (two_proxies, quiet_proxy
and one weak proxy_gap portfolio). The script prints each one.

Run (from src/):  python3 step_04_with_fairlens.py
Output: a report, plus out/step_04_cases.csv, out/step_04_summary.json and out/step_04_example.json
"""
import csv
import json
import os
from collections import Counter

from common import load_cases, run_cases, verdicts, mechanisms, ensure_out, OUT_DIR, TESTS

cases = load_cases()
packs = run_cases(cases)
v = {c["id"]: verdicts(packs[c["id"]]) for c in cases}
t4 = {c["id"]: packs[c["id"]]["tests"][3] for c in cases}
planted = [c for c in cases if c["planted"]]
others = [c for c in cases if not c["planted"]]


def of(m):
    return [c for c in cases if c["mechanism"] == m]


def count(cs, test, verdict):
    return sum(1 for c in cs if v[c["id"]][test] == verdict)


found = [c for c in planted if v[c["id"]]["T4"] == "FAIL"]
false_t4 = [c for c in others if v[c["id"]]["T4"] == "FAIL"]
t4_fail = [c for c in cases if v[c["id"]]["T4"] == "FAIL"]
t5_pass_t4_fail = [c for c in t4_fail if v[c["id"]]["T5"] == "PASS"]
pred = of("proxy_predictive")
noise = of("small_group_noise")
point_noise = sum(1 for c in noise if packs[c["id"]]["gs"]["min_air"] < 0.80)
overall_fail_others = [c for c in others if packs[c["id"]]["overall"] == "FAIL"]
overall_fail_planted = [c for c in planted if packs[c["id"]]["overall"] == "FAIL"]

print("STEP 4 - the six-test pack")
print(f"  planted proxies marked FAIL by the ablation (T4): {len(found)} of {len(planted)}")
print(f"  portfolios with no planted proxy marked FAIL by the ablation: {len(false_t4)} of {len(others)}"
      + (f" ({', '.join(c['id'] + ' ' + c['mechanism'] for c in false_t4)})" if false_t4 else ""))
print(f"  reason pairs (T5) passed on {len(t5_pass_t4_fail)} of the {len(t4_fail)} portfolios where the ablation failed")
print(f"  proxy_predictive (feature also predicts default): T4 FAIL {count(pred, 'T4', 'FAIL')}, REVIEW {count(pred, 'T4', 'REVIEW')}, PASS {count(pred, 'T4', 'PASS')} of {len(pred)}")
print(f"  small_group_noise: point AIR under 0.80 in {point_noise} of {len(noise)}; T2 FAIL {count(noise, 'T2', 'FAIL')}, REVIEW {count(noise, 'T2', 'REVIEW')}")
print(f"  overall verdict FAIL: planted proxies {len(overall_fail_planted)} of {len(planted)}, no planted proxy {len(overall_fail_others)} of {len(others)}")
overall_pass = sum(1 for c in cases if packs[c["id"]]["overall"] == "PASS")
print(f"  reason naming (T6): FAIL {count(cases, 'T6', 'FAIL')}, REVIEW {count(cases, 'T6', 'REVIEW')}, PASS {count(cases, 'T6', 'PASS')} of {len(cases)}; "
      f"overall PASS: {overall_pass} of {len(cases)}")
print("  overall verdict by mechanism (FAIL / REVIEW / PASS):")
for m in mechanisms(cases):
    ms = of(m)
    c = Counter(packs[x["id"]]["overall"] for x in ms)
    print(f"    {m:<20} {c['FAIL']} / {c['REVIEW']} / {c['PASS']}")
print("  T4 verdict by mechanism (FAIL / REVIEW / PASS):")
for m in mechanisms(cases):
    ms = of(m)
    print(f"    {m:<20} {count(ms, 'T4', 'FAIL')} / {count(ms, 'T4', 'REVIEW')} / {count(ms, 'T4', 'PASS')}")
missed = [c for c in planted if v[c["id"]]["T4"] != "FAIL"]
print(f"  planted proxies the ablation does not mark FAIL: {len(missed)} of {len(planted)}")
for c in missed:
    print(f"    {c['id']} {c['mechanism']:<12} lowest AIR {t4[c['id']]['before']:.3f} -> {t4[c['id']]['after']:.3f}, T4 {v[c['id']]['T4']}")
ex = next(c for c in cases if c["id"] == "C19")
print(f"  worked example, {ex['id']} ({ex['mechanism']}), the portfolio behind --demo:")
for x in packs[ex["id"]]["tests"]:
    print(f"    {x['id']} {x['verdict']:<7} {x['name']}")

ensure_out()
fields = ["case_id", "mechanism", "proxy_planted", "point_air"] + list(TESTS) + ["overall", "t4_lift", "t4_cost_pts"]
with open(os.path.join(OUT_DIR, "step_04_cases.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(fields)
    for c in cases:
        p = packs[c["id"]]
        w.writerow([c["id"], c["mechanism"], int(c["planted"]), f"{p['gs']['min_air']:.3f}"] + [v[c["id"]][k] for k in TESTS]
                   + [p["overall"], f"{t4[c['id']]['lift']:.3f}", f"{t4[c['id']]['cost_pts']:.1f}"])
summary = {"portfolios": len(cases), "planted": len(planted), "found_by_t4": len(found), "false_t4": len(false_t4), "others": len(others),
           "t5_pass_t4_fail": len(t5_pass_t4_fail), "t4_fail": len(t4_fail), "predictive": len(pred),
           "predictive_t4_fail": count(pred, "T4", "FAIL"), "predictive_t4_review": count(pred, "T4", "REVIEW"),
           "noise": len(noise), "noise_point_air_flagged": point_noise, "noise_t2_fail": count(noise, "T2", "FAIL"),
           "noise_t2_review": count(noise, "T2", "REVIEW"), "overall_fail_planted": len(overall_fail_planted),
           "overall_fail_others": len(overall_fail_others), "missed": len(missed), "overall_pass": overall_pass,
           "t6_review": count(cases, "T6", "REVIEW")}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
with open(os.path.join(OUT_DIR, "step_04_example.json"), "w", encoding="utf-8") as fh:
    json.dump({"case_id": ex["id"], "tests": [{k: x[k] for k in ("id", "name", "verdict", "numbers", "rule")} for x in packs[ex["id"]]["tests"]],
               "overall": packs[ex["id"]]["overall"]}, fh, indent=1)
print("Wrote step_04_cases.csv, step_04_summary.json and step_04_example.json in src/out/")
