"""Step 3 - Where the interview map and the log-based list break: six named deficiencies, each with numbers.

Step 1 showed what an interview gives you. Step 2 showed what the case-system log gives you. This step
asks six things neither can do, on the same synthetic 30 days.

  (1) The interview map covers one path: what share of real cases and variants does it describe?
  (2) Work outside the case system is invisible to the log: what share of touch time is it?
  (3) Elapsed time is mostly wait: what share of it is touch time, and the log counts both as work.
  (4) Rework loops (reopened cases) sit outside the headline cycle time: how many hours do they add?
  (5) The volume-first top 10 contains judgment-heavy steps: how many of the ten can an agent take over?
  (6) The volume-first list has no control screen: how many of the ten touch restricted data or a
      four-eyes control?

Where this step uses the answer key (5) or the generator's record of the true path (1), it says so. The
desktop events are used here only for application and time, never for the step label: the miner infers
the label in step 4.

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: a readable summary, plus out/step_03_deficiencies.csv and out/step_03_summary.json.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter

from step_01_interview_process_map import (
    AGENT_READY, APP_LABEL, APPS, OUT_DIR, fnum, load_all, minutes, pct, rnd,
)
from step_02_system_log_mining import TOP_N, analyze as analyze_log

SYSTEM_TO_APP = {"case system": "case_system", "payments hub": "payments_hub", "screening application": "screening_app"}


def summarize(data: dict, log: dict | None = None) -> dict:
    log = log or analyze_log(data)
    reg, key, cases = data["register"], data["key"], data["cases"]
    n_cases = len(cases)
    sme_steps = [r["step"] for r in data["sme"]]

    # (1) the interview map against the generator's record of the true path ---------------------------
    paths = Counter(">".join(c["true_path"]) for c in cases)
    happy = ">".join(sme_steps)
    happy_cases = paths.get(happy, 0)
    cum, to80 = 0, 0
    for _, n in paths.most_common():
        cum += n
        to80 += 1
        if cum >= 0.8 * n_cases:
            break
    occ = Counter(s for c in cases for s in c["true_path"])
    off_map = [s for s in data["order"] if s not in sme_steps]
    named_apps = {SYSTEM_TO_APP[r["systems"]] for r in data["sme"]}
    d1 = {"happy_cases": happy_cases, "happy_pct": pct(happy_cases, n_cases), "variants": len(paths), "variants_to_80": to80,
          "off_map_steps": off_map, "off_map_occ_pct": pct(sum(occ[s] for s in off_map), sum(occ.values())),
          "apps_named": len(named_apps), "apps_seen": len({e["app"] for e in data["desk"]}),
          "log_variants": log["n_variants"], "log_top_variant_pct": pct(log["top_variant_cases"], n_cases)}

    # (2) touch time outside the case system -------------------------------------------------------------
    by_app = Counter()
    for e in data["desk"]:
        by_app[e["app"]] += minutes(e)
    total_touch = sum(by_app.values())
    no_status = [s for s in data["order"] if not reg[s]["status"]]
    d2 = {"touch_hours": total_touch / 60.0, "off_system_pct": pct(total_touch - by_app["case_system"], total_touch),
          "by_app_pct": {a: pct(by_app[a], total_touch) for a in APPS},
          "unnamed_pct": pct(sum(v for a, v in by_app.items() if a not in named_apps), total_touch),
          "no_status_steps": no_status}

    # (3) elapsed against touch --------------------------------------------------------------------------
    elapsed_bh, touch_min = [], []
    for c in cases:
        elapsed_bh.append((c["first_closed"] - c["created"]) / 3600.0)
        touch_min.append(sum(minutes(e) for e in data["desk_by_case"][c["case"]] if e["start"] <= c["first_closed"]))
    tot_el, tot_to = sum(elapsed_bh), sum(touch_min) / 60.0
    d3 = {"elapsed_hours": tot_el, "touch_hours": tot_to, "touch_share_pct": pct(tot_to, tot_el),
          "median_elapsed_h": statistics.median(elapsed_bh), "median_touch_min": statistics.median(touch_min),
          "log_credited_hours": log["elapsed_hours_total"], "all_touch_hours": total_touch / 60.0,
          "log_vs_touch": log["elapsed_hours_total"] / (total_touch / 60.0)}

    # (4) rework -----------------------------------------------------------------------------------------
    reopened = [c for c in cases if c["reopened"]]
    extra_touch = sum(minutes(e) for c in reopened for e in data["desk_by_case"][c["case"]] if e["start"] > c["first_closed"])
    extra_el = sum((c["final_closed"] - c["first_closed"]) / 3600.0 for c in reopened)
    first_bh = statistics.mean((c["first_closed"] - c["created"]) / 3600.0 for c in reopened)
    final_bh = statistics.mean((c["final_closed"] - c["created"]) / 3600.0 for c in reopened)
    d4 = {"reopened": len(reopened), "reopened_pct": pct(len(reopened), n_cases), "log_reopen_events": log["reopen_events"],
          "extra_touch_hours": extra_touch / 60.0, "extra_touch_pct": pct(extra_touch, total_touch),
          "extra_elapsed_hours": extra_el, "first_close_mean_h": first_bh, "final_close_mean_h": final_bh}

    # (5) the volume-first top 10 against the answer key ----------------------------------------------------
    top = log["top10"]
    ready = [s for s in top if key[s] in AGENT_READY]
    not_ready = [s for s in top if key[s] not in AGENT_READY]
    absent = [s for s in data["order"] if s not in {r["step"] for r in log["candidates"]}]
    d5 = {"top10": top, "ready": ready, "not_ready": not_ready, "not_ready_class": {s: key[s] for s in not_ready},
          "ready_count": len(ready), "absent_steps": absent, "absent_ready": [s for s in absent if key[s] in AGENT_READY]}

    # (6) the same ten against the control register -----------------------------------------------------------
    flagged = []
    for s in top:
        r = reg[s]
        why = []
        if r["restricted"]:
            why.append("restricted data")
        if r["control"]:
            why.append("four-eyes control")
        if r["gated_by"]:
            why.append(f"may run only after {r['gated_by']} approves")
        if why:
            flagged.append({"step": s, "why": why})
    d6 = {"flagged": flagged, "count": len(flagged)}
    return {"n_cases": n_cases, "d1": d1, "d2": d2, "d3": d3, "d4": d4, "d5": d5, "d6": d6}


def main() -> None:
    data = load_all()
    log = analyze_log(data)
    S = summarize(data, log)
    d1, d2, d3, d4, d5, d6 = (S[k] for k in ("d1", "d2", "d3", "d4", "d5", "d6"))
    reg = data["register"]
    print("=" * 100)
    print("Step 3 - Six deficiencies of the interview map and the log-based list, with numbers")
    print("=" * 100)

    print("\n(1) The interview map covers one path")
    print(f"    {d1['happy_cases']:,} of {S['n_cases']:,} cases ({d1['happy_pct']}%) took exactly the documented path, with no reopen "
          "(the generator's record of the true path).")
    print(f"    The cases took {d1['variants']} distinct paths; the map is 1 of them. It takes {d1['variants_to_80']} paths to cover 80% of cases.")
    print(f"    {len(d1['off_map_steps'])} of {len(data['order'])} steps are not on the map ({', '.join(d1['off_map_steps'])}); "
          f"they are {d1['off_map_occ_pct']}% of all step occurrences.")
    print(f"    The log is no better: it shows {d1['log_variants']} variants (three steps post no status, so true paths that differ only "
          f"there look the same). Its most common one covers {d1['log_top_variant_pct']}% of cases.")

    print("\n(2) Work outside the case system is invisible to the log")
    print(f"    {d2['off_system_pct']}% of desktop touch time is spent outside the case system "
          f"({fnum(d2['touch_hours'], 0)} touch hours in all).")
    print("    Share of touch time by application: " + ", ".join(f"{APP_LABEL[a]} {d2['by_app_pct'][a]}%" for a in APPS))
    print(f"    The interview names {d1['apps_named']} systems; the desktop shows {d1['apps_seen']} applications. "
          f"The {d1['apps_seen'] - d1['apps_named']} never named hold {d2['unnamed_pct']}% of touch time.")
    print(f"    {len(d2['no_status_steps'])} of {len(data['order'])} steps post no status at all ({', '.join(d2['no_status_steps'])}): "
          "the log never records that they happened.")

    print("\n(3) Elapsed time is mostly wait, and the log counts both as work")
    print(f"    Per case, receipt to first close: median {fnum(d3['median_elapsed_h'])} working hours; touch time in that span: "
          f"median {fnum(d3['median_touch_min'], 0)} minutes.")
    print(f"    Over all cases: {fnum(d3['elapsed_hours'], 0)} elapsed hours, {fnum(d3['touch_hours'], 0)} touch hours -> touch is "
          f"{d3['touch_share_pct']}% of elapsed time.")
    print(f"    The volume-first list credits {fnum(d3['log_credited_hours'], 0)} hours to the workflow's steps; the desktop shows "
          f"{fnum(d3['all_touch_hours'], 0)} hours of touch. It credits {d3['log_vs_touch']:.1f} times the hours of work.")

    print("\n(4) Rework loops are outside the headline cycle time")
    print(f"    {d4['reopened']} cases ({d4['reopened_pct']}%) were reopened; the log records {d4['log_reopen_events']} REOPENED statuses, "
          "but cycle time stops at the first close.")
    print(f"    For those cases the mean is {fnum(d4['first_close_mean_h'])} h to the first close and {fnum(d4['final_close_mean_h'])} h to the last.")
    print(f"    The rework adds {fnum(d4['extra_touch_hours'], 0)} touch hours ({d4['extra_touch_pct']}% of all touch time) and "
          f"{fnum(d4['extra_elapsed_hours'], 0)} elapsed hours. The interview map has no loop for it.")

    print("\n(5) The volume-first top 10 contains steps an agent cannot take over")
    print(f"    By the answer key, {d5['ready_count']} of the top {TOP_N} are agent-ready (AGENT or AGENT_HITL).")
    for s in d5["not_ready"]:
        print(f"      not ready: {s} {reg[s]['name']} ({d5['not_ready_class'][s]})")
    print(f"    The steps the log never records ({', '.join(d5['absent_steps'])}) are all agent-ready: "
          f"{len(d5['absent_ready'])} of {len(d5['absent_steps'])}. The list cannot propose them.")

    print("\n(6) The volume-first list has no control screen")
    print(f"    {d6['count']} of the top {TOP_N} touch restricted data or a four-eyes control:")
    for f in d6["flagged"]:
        print(f"      {f['step']} {reg[f['step']]['name']}: {', '.join(f['why'])}")
    print("\nThe interview map and the log find some steps and mishandle the rest. The product is the touch time,")
    print("the readiness call and the control screen per step, not another ranking.")

    rows = [
        (1, "Interview map covers one path", f"{d1['happy_pct']}% of cases", f"{d1['happy_cases']} of {S['n_cases']} cases; {d1['variants']} real paths"),
        (2, "Off-system work is invisible", f"{d2['off_system_pct']}% of touch time", f"{d1['apps_seen']} applications; {d1['apps_named']} named"),
        (3, "Elapsed time is mostly wait", f"{d3['touch_share_pct']}% touch", f"{fnum(d3['touch_hours'], 0)} touch of {fnum(d3['elapsed_hours'], 0)} elapsed hours"),
        (4, "Rework loops are hidden", f"{d4['reopened']} cases", f"{fnum(d4['extra_touch_hours'], 0)} touch hours after the first close"),
        (5, "Volume-first picks judgment-heavy steps", f"{d5['ready_count']} of {TOP_N} agent-ready", "not ready: " + ", ".join(d5["not_ready"])),
        (6, "No control screen", f"{d6['count']} of {TOP_N} flagged", ", ".join(f["step"] for f in d6["flagged"])),
    ]
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_03_deficiencies.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["n", "deficiency", "headline", "detail"])
        w.writerows(rows)
    (OUT_DIR / "step_03_summary.json").write_text(json.dumps(S, indent=2, default=str), encoding="utf-8")
    print("\nWrote src/out/step_03_deficiencies.csv and step_03_summary.json")


if __name__ == "__main__":
    main()
