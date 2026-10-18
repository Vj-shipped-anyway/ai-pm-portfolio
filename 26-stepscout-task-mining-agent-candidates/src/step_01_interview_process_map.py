"""Step 1 - Before StepScout: the interview process map.

A modeled bank runs a payment-exception queue (wire repair). Operations leads who want to put an agent
on part of it start with an interview: ask a subject-matter expert how the work goes, write down the
steps and how long each takes. This script plays that interview back from data/sme_process_map.csv and
adds up what it says: one path, minutes per step, three systems.

It is also the home of the loaders every later step and the apps import (everything below the
"Loaders" line). Nothing in it reads the answer key.

Run (from src/):
    python3 step_01_interview_process_map.py

Output: a readable summary, plus out/step_01_process_map.csv and out/step_01_summary.json.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

DAY_S = 36000                # a working day, 08:00 to 18:00, in seconds
EPOCH = date(2026, 9, 1)
APPS = ["case_system", "payments_hub", "spreadsheet", "matching_tool", "screening_app", "email"]
APP_LABEL = {"case_system": "case system", "payments_hub": "payments hub", "spreadsheet": "spreadsheet",
             "matching_tool": "matching tool", "screening_app": "screening application", "email": "email"}
AGENT_READY = ("AGENT", "AGENT_HITL")     # the answer key's "an agent can take this over" classes


# ---------------------------------------------------------------------------
# Loaders (shared by steps 2 to 4 and the apps). Times become working seconds since 08:00 on the first
# working day, so a wait never contains a night or a weekend.
# ---------------------------------------------------------------------------
def _workdates(n: int) -> list:
    d, out = EPOCH, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


WORKDATES = _workdates(130)
_DAY_INDEX = {d.isoformat(): i for i, d in enumerate(WORKDATES)}


def to_work(ts: str) -> int:
    """'2026-09-01T08:14:05' -> working seconds since 08:00 on the first working day."""
    return (_DAY_INDEX[ts[:10]] * DAY_S + (int(ts[11:13]) - 8) * 3600 + int(ts[14:16]) * 60 + int(ts[17:19]))


def label_w(w: float) -> str:
    """Working seconds -> 'Sep 03 09:41'."""
    day, s = divmod(int(w), DAY_S)
    return (datetime.combine(WORKDATES[day], time(8, 0)) + timedelta(seconds=s)).strftime("%b %d %H:%M")


def day_w(w: float) -> int:
    """Calendar day of the month for working seconds."""
    return WORKDATES[int(w) // DAY_S].day


def read_csv(name: str, data_dir: Path = DATA_DIR) -> list:
    with open(data_dir / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rnd(x: float) -> int:
    """Round half up, so a printed number is the same in every language the demo is built in."""
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def pct(a: float, b: float, digits: int = 1) -> float:
    return round(100.0 * a / b, digits) if b else 0.0


def median_or_none(v: list):
    return statistics.median(v) if v else None


def fnum(x: float, digits: int = 1) -> str:
    return f"{x:,.{digits}f}"


def split_catalog(rows: list) -> tuple:
    """Split the step catalog into the register (inputs a team can supply), the answer key (truth_class only)
    and the parameters the generator planted. Nothing in the register comes from the key."""
    register, key, planted = {}, {}, {}
    for r in rows:
        register[r["step_id"]] = {"id": r["step_id"], "name": r["step_name"], "order": int(r["process_order"]),
                                  "status": r["status_event"], "restricted": int(r["restricted_data"]),
                                  "control": int(r["control_flag"]), "gated_by": r["gated_by"],
                                  "fields": r["data_fields"].split(";")}
        key[r["step_id"]] = r["truth_class"]
        planted[r["step_id"]] = {"median_touch_min": float(r["planted_median_touch_min"]),
                                 "sigma": float(r["planted_timing_sigma"]), "text": float(r["planted_text_chars"]),
                                 "override": float(r["planted_override_rate"]),
                                 "cross_app": float(r["planted_cross_app_copy"]),
                                 "repeats": float(r["planted_repeats_per_case"]),
                                 "offdesk_share": float(r["planted_offdesk_share"])}
    return register, key, planted


def load_all(data_dir: Path = DATA_DIR) -> dict:
    """Read every CSV. Returns plain lists and dicts.

    'register' holds what a team could supply without knowing the answer (step names, which status a
    step posts, the data-classification and control flags). 'key' holds the answer key and nothing
    else. A classifier is given the register and the events, never the key. Two fields on each case are
    the generator's own record, used only to measure and to score: true_path and offdesk_min.
    """
    cases = [{"case": r["case_id"], "created": to_work(r["created"]), "first_closed": to_work(r["first_closed"]),
              "final_closed": to_work(r["final_closed"]), "reason": r["reason_code"], "variant": r["variant_id"],
              "reopened": int(r["reopened"]), "primary": r["primary_worker"], "offdesk_min": float(r["offdesk_min_truth"]),
              "true_path": r["true_path"].split(">")}
             for r in read_csv("cases.csv", data_dir)]
    desk = [{"case": r["case_id"], "worker": r["worker_id"], "app": r["application"], "action": r["action"],
             "step": r["step_id"], "start": to_work(r["start"]), "end": to_work(r["end"]), "chars": int(r["typed_chars"])}
            for r in read_csv("desktop_events.csv", data_dir)]
    system = [{"case": r["case_id"], "status": r["status"], "ts": to_work(r["ts"]), "worker": r["worker_id"]}
              for r in read_csv("system_events.csv", data_dir)]
    desk_by_case, sys_by_case = defaultdict(list), defaultdict(list)
    for e in desk:
        desk_by_case[e["case"]].append(e)
    for e in system:
        sys_by_case[e["case"]].append(e)
    for v in desk_by_case.values():
        v.sort(key=lambda e: (e["start"], e["end"]))
    for v in sys_by_case.values():
        v.sort(key=lambda e: e["ts"])
    register, key, planted = split_catalog(read_csv("step_catalog.csv", data_dir))
    sme = [{"seq": int(r["seq"]), "step": r["step_id"], "what": r["step"], "systems": r["systems_named"],
            "owner": r["owner_role"], "minutes": int(r["minutes_per_step"])} for r in read_csv("sme_process_map.csv", data_dir)]
    workers = read_csv("workers.csv", data_dir)
    return {"cases": cases, "desk": desk, "system": system, "desk_by_case": desk_by_case, "sys_by_case": sys_by_case,
            "register": register, "key": key, "planted": planted, "sme": sme, "workers": workers,
            "order": sorted(register, key=lambda s: register[s]["order"])}


def minutes(e: dict) -> float:
    return (e["end"] - e["start"]) / 60.0


# ---------------------------------------------------------------------------
# Step 1
# ---------------------------------------------------------------------------
def summarize(data: dict) -> dict:
    sme, cases = data["sme"], data["cases"]
    total = sum(r["minutes"] for r in sme)
    systems = sorted({r["systems"] for r in sme})
    stated = sorted(sme, key=lambda r: -r["minutes"])
    n_cases = len(cases)
    return {"steps": len(sme), "total_minutes": total, "paths": 1, "loops": 0, "systems_named": len(systems),
            "systems": systems, "cases": n_cases, "stated_hours": round(n_cases * total / 60.0),
            "by_minutes": [{"step": r["step"], "what": r["what"], "minutes": r["minutes"],
                            "stated_hours": round(n_cases * r["minutes"] / 60.0)} for r in stated],
            "step_ids": [r["step"] for r in sme]}


def main() -> None:
    data = load_all()
    S = summarize(data)
    print("=" * 100)
    print("Step 1 - Before StepScout: the interview process map")
    print("=" * 100)
    print("\nSource: data/sme_process_map.csv - an interview with one subject-matter expert. Nothing measured.\n")
    print(f"{'seq':>3}  {'step':<5} {'what the expert says':<42} {'systems named':<24} {'owner':<10} {'minutes':>7}")
    print("-" * 100)
    for r in data["sme"]:
        print(f"{r['seq']:>3}  {r['step']:<5} {r['what']:<42} {r['systems']:<24} {r['owner']:<10} {r['minutes']:>7}")
    print("-" * 100)
    print(f"{'':>3}  {'':<5} {'Total, one case':<42} {'':<24} {'':<10} {S['total_minutes']:>7}")
    print(f"\nWhat the map says: {S['steps']} steps, {S['paths']} path, {S['loops']} loops, no waits, "
          f"{S['systems_named']} systems named ({', '.join(S['systems'])}).")
    print(f"If every one of the {S['cases']:,} cases took this path: {S['cases']:,} x {S['total_minutes']} min = "
          f"{S['stated_hours']:,} hours in the 30 days (modeled from the interview, not measured).")
    print("\nAn interview-driven pick takes the steps with the most stated minutes:")
    for r in S["by_minutes"][:5]:
        print(f"  {r['step']}  {r['what']:<42} {r['minutes']:>2} min  ->  {r['stated_hours']:>4,} stated hours")
    print("\nThe map describes one happy path. Steps 2 and 3 count how many real cases take it.")

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_01_process_map.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["seq", "step_id", "what", "systems_named", "owner_role", "minutes_per_step", "stated_hours_30d"])
        for r in data["sme"]:
            w.writerow([r["seq"], r["step"], r["what"], r["systems"], r["owner"], r["minutes"],
                        round(S["cases"] * r["minutes"] / 60.0)])
    (OUT_DIR / "step_01_summary.json").write_text(json.dumps(S, indent=2), encoding="utf-8")
    print("\nWrote src/out/step_01_process_map.csv and step_01_summary.json")


if __name__ == "__main__":
    main()
