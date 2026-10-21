"""Real-data mode - the case-log half of StepScout, on a public loan-application event log.

The default walkthrough runs on synthetic data, where the generator knows the answer. This script asks
the same questions of a real log, so the effect can be seen once without a planted signal. The log is
the BPI Challenge 2012 event log of a loan-application process at a financial institution (van Dongen,
2012, DOI 10.4121/uuid:3926db30-f712-4394-aebc-75976070e91f; licence: 4TU General Terms of Use).

What it can answer from a case-system log alone:
  - how many real paths the cases take, and how much of the work the most common path covers
    (the interview-map question);
  - how much of the elapsed time is hands-on work (START to COMPLETE of a work item) and how much is
    waiting (SCHEDULE to START), which a volume-times-time list counts as work;
  - how often a case schedules the same work item again, and how often a task is resumed after a pause;
  - how a list ranked by waiting plus hands-on time differs from a list ranked by hands-on hours.

What it cannot answer, and prints as such: there is no desktop layer in this log, so off-system work is
not observable; there is no control register and no answer key, so no step is classified and no accuracy
is claimed.

Run (from src/), after fetching the file once:
    python3 ../data/real/fetch_bpi2012.py
    python3 real_bpi2012.py
    python3 real_bpi2012.py --selftest     # no download needed: a three-case log with hand-worked answers

Output: a readable summary, plus out/real_bpi2012_summary.json and out/real_bpi2012_activities.csv.
The printed text is also committed as ../data/real/bpi2012_output.txt so the README can cite it.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "data" / "real" / "raw" / "BPI_Challenge_2012.xes.gz"
OUT_DIR = HERE / "out"
EXPECTED_MD5 = "74c7ba9aba85bfcb181a22c9d565e5b5"
CITATION = ("van Dongen, Boudewijn (2012): BPI Challenge 2012. Version 1. 4TU.ResearchData. dataset. "
            "https://doi.org/10.4121/uuid:3926db30-f712-4394-aebc-75976070e91f")
TOP_N = 3
HOUR = 3600.0


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_ts(s: str) -> float:
    """Seconds since the epoch from an XES timestamp such as 2011-10-01T00:38:44.546+02:00."""
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:                       # fractional part that is not 3 or 6 digits
        head, _, rest = s.partition(".")
        frac = ""
        tz = ""
        for i, ch in enumerate(rest):
            if not ch.isdigit():
                frac, tz = rest[:i], rest[i:]
                break
        else:
            frac = rest
        return datetime.fromisoformat("%s.%s%s" % (head, (frac + "000000")[:6], tz)).timestamp()


def load_cases(source) -> list:
    """Stream an XES file or file object. Returns [(case_id, [(ts, activity, transition, resource), ...])]."""
    if hasattr(source, "read"):
        f, close = source, False
    else:
        path = Path(source)
        f, close = (gzip.open(path, "rb") if str(path).endswith(".gz") else open(path, "rb")), True
    cases, events, ev, trace_name = [], [], None, None
    try:
        for kind, elem in ET.iterparse(f, events=("start", "end")):
            tag = _local(elem.tag)
            if kind == "start":
                if tag == "trace":
                    events, trace_name = [], None
                elif tag == "event":
                    ev = {}
                continue
            if tag in ("string", "date", "int", "float", "boolean"):
                key, val = elem.get("key"), elem.get("value")
                if ev is not None:
                    ev[key] = val
                elif key == "concept:name" and trace_name is None:
                    trace_name = val
            elif tag == "event":
                if ev is not None and "time:timestamp" in ev and "concept:name" in ev:
                    events.append((parse_ts(ev["time:timestamp"]), ev["concept:name"],
                                   (ev.get("lifecycle:transition") or "COMPLETE").upper(),
                                   ev.get("org:resource") or ""))
                ev = None
                elem.clear()
            elif tag == "trace":
                events.sort(key=lambda e: e[0])          # stable: ties keep file order
                cases.append((trace_name or "case-%d" % len(cases), events))
                elem.clear()
    finally:
        if close:
            f.close()
    return cases


def work_items(cases: list) -> tuple:
    """Pair SCHEDULE, START and COMPLETE per case and activity. Returns (sessions, waits, unpaired).

    A session is (case_id, activity, handling_s, resource, resumed): START to COMPLETE. A START with no
    SCHEDULE waiting is a resumed session. A wait is (case_id, activity, wait_s): SCHEDULE to the first
    START of a task, credited at the START whether or not a COMPLETE follows.
    """
    sessions, waits, unpaired = [], [], 0
    for cid, evs in cases:
        sched, started = defaultdict(list), {}
        for ts, act, trans, res in evs:
            if trans == "SCHEDULE":
                sched[act].append(ts)
            elif trans == "START":
                resumed = not sched[act]
                if not resumed:
                    waits.append((cid, act, max(ts - sched[act].pop(0), 0.0)))
                started[act] = (ts, resumed)
            elif trans == "COMPLETE" and act in started:
                t0, resumed = started.pop(act)
                sessions.append((cid, act, max(ts - t0, 0.0), res, resumed))
            elif trans == "COMPLETE" and act.startswith("W_"):
                unpaired += 1
    return sessions, waits, unpaired


def _pct(a: float, b: float) -> float:
    return 100.0 * a / b if b else 0.0


def analyze(cases: list) -> dict:
    n_cases = len(cases)
    n_events = sum(len(e) for _, e in cases)
    acts = Counter(a for _, e in cases for _, a, _, _ in e)
    resources = {r for _, e in cases for _, _, _, r in e if r}

    # 1. variants: the sequence of completed activities per case
    variants = Counter()
    for _, evs in cases:
        variants[tuple(a for _, a, t, _ in evs if t == "COMPLETE")] += 1
    ranked = sorted(variants.values(), reverse=True)
    covered, need80 = 0, 0
    for c in ranked:
        covered += c
        need80 += 1
        if covered >= 0.8 * n_cases:
            break

    # 2. touch against elapsed
    elapsed_s = sum(e[-1][0] - e[0][0] for _, e in cases if e)
    sessions, waits, unpaired = work_items(cases)
    handling_s = sum(x[2] for x in sessions)
    wait_s = sum(x[2] for x in waits)

    # 3. rework: a task scheduled again for the same activity in a case; resumed sessions of one task
    scheduled = defaultdict(Counter)
    for cid, evs in cases:
        for _, act, trans, _ in evs:
            if trans == "SCHEDULE":
                scheduled[cid][act] += 1
    tasks = sum(sum(c.values()) for c in scheduled.values())
    resched_cases = sum(1 for c in scheduled.values() if any(v > 1 for v in c.values()))
    resched_tasks = sum(max(v - 1, 0) for c in scheduled.values() for v in c.values())
    resumed = [x for x in sessions if x[4]]
    resumed_handling_s = sum(x[2] for x in resumed)

    # 4. per-activity table (work sessions only)
    by_act = defaultdict(list)
    for _, act, h, r, _ in sessions:
        by_act[act].append((h, r))
    wait_by_act = Counter()
    for _, act, w in waits:
        wait_by_act[act] += w
    task_count = Counter()
    for c in scheduled.values():
        task_count.update(c)
    rows = []
    for act, v in by_act.items():
        hs = [x[0] for x in v]
        ws_total = wait_by_act[act]
        rows.append({
            "activity": act,
            "tasks": task_count[act],
            "sessions": len(v),
            "median_session_min": round(statistics.median(hs) / 60.0, 1),
            "distinct_resources": len({x[1] for x in v if x[1]}),
            "wait_hours": round(ws_total / HOUR, 1),
            "handling_hours": round(sum(hs) / HOUR, 1),
            "wait_plus_handling_hours": round((sum(hs) + ws_total) / HOUR, 1),
        })
    volume_first = sorted(rows, key=lambda r: (-r["wait_plus_handling_hours"], r["activity"]))
    touch_first = sorted(rows, key=lambda r: (-r["handling_hours"], r["activity"]))
    for rank, r in enumerate(volume_first, 1):
        r["rank_wait_plus_handling"] = rank
    for rank, r in enumerate(touch_first, 1):
        r["rank_handling"] = rank
    top_v, top_t = volume_first[:TOP_N], touch_first[:TOP_N]
    credited = sum(r["wait_plus_handling_hours"] for r in top_v)
    touched = sum(r["handling_hours"] for r in top_v)

    return {
        "cases": n_cases,
        "events": n_events,
        "activities": len(acts),
        "work_activities": len(rows),
        "resources": len(resources),
        "sessions": len(sessions),
        "unpaired_completes": unpaired,
        "variants": len(variants),
        "top_variant_cases": ranked[0] if ranked else 0,
        "top_variant_pct": round(_pct(ranked[0], n_cases), 1) if ranked else 0.0,
        "variants_for_80pct": need80,
        "singleton_variants": sum(1 for c in ranked if c == 1),
        "singleton_cases_pct": round(_pct(sum(1 for c in ranked if c == 1), n_cases), 1),
        "elapsed_hours": round(elapsed_s / HOUR),
        "handling_hours": round(handling_s / HOUR),
        "wait_hours": round(wait_s / HOUR),
        "handling_pct_of_elapsed": round(_pct(handling_s, elapsed_s), 2),
        "wait_pct_of_wait_plus_handling": round(_pct(wait_s, wait_s + handling_s), 1),
        "tasks": tasks,
        "resched_cases": resched_cases,
        "resched_cases_pct": round(_pct(resched_cases, n_cases), 1),
        "resched_tasks": resched_tasks,
        "resumed_sessions": len(resumed),
        "resumed_handling_hours": round(resumed_handling_s / HOUR),
        "top_n": TOP_N,
        "overlap": len({r["activity"] for r in top_v} & {r["activity"] for r in top_t}),
        "credit_ratio": round(credited / touched, 1) if touched else 0.0,
        "rows": touch_first,
    }


def render(res: dict, md5_ok) -> str:
    L = []
    w = L.append
    n = res["top_n"]
    w("=" * 80)
    w("Real-data mode - the case-log half of StepScout on the BPI Challenge 2012 loan-application log")
    w("=" * 80)
    w("Source: " + CITATION)
    w("Terms: 4TU General Terms of Use (August 2016): cite the dataset, no commercial use, log not redistributed here.")
    if md5_ok is not None:
        w("File check: MD5 %s" % ("matches the published value" if md5_ok else "DOES NOT match the published value"))
    w("")
    w("1. What the log holds")
    w("   %s cases, %s events, %d activities, %d resources" % (
        format(res["cases"], ","), format(res["events"], ","), res["activities"], res["resources"]))
    w("   %d of the activities are work items (W_), with %s START-to-COMPLETE sessions (%s completes without a START)" % (
        res["work_activities"], format(res["sessions"], ","), format(res["unpaired_completes"], ",")))
    w("")
    w("2. Paths: how many real variants, and how much the most common one covers")
    w("   a variant is the ordered list of COMPLETE events of a case (A_, O_ and W_ activities)")
    w("   %s distinct variants over %s cases" % (format(res["variants"], ","), format(res["cases"], ",")))
    w("   the most common variant covers %s cases (%.1f%%)" % (format(res["top_variant_cases"], ","), res["top_variant_pct"]))
    w("   %s variants are needed to cover 80%% of cases" % format(res["variants_for_80pct"], ","))
    w("   %s variants occur once (%.1f%% of cases)" % (format(res["singleton_variants"], ","), res["singleton_cases_pct"]))
    w("")
    w("3. Hands-on time against elapsed time")
    w("   elapsed, first to last event per case:        %s h" % format(res["elapsed_hours"], ","))
    w("   hands-on, START to COMPLETE of work sessions: %s h (%.2f%% of elapsed)" % (
        format(res["handling_hours"], ","), res["handling_pct_of_elapsed"]))
    w("   waiting, SCHEDULE to first START of a task:   %s h (%.1f%% of waiting plus hands-on)" % (
        format(res["wait_hours"], ","), res["wait_pct_of_wait_plus_handling"]))
    w("")
    w("4. Rework and resumption")
    w("   %s tasks were scheduled; %s cases (%.1f%%) schedule the same activity again (%s repeat tasks)" % (
        format(res["tasks"], ","), format(res["resched_cases"], ","), res["resched_cases_pct"],
        format(res["resched_tasks"], ",")))
    w("   %s sessions resume a task already started; they hold %s hands-on hours" % (
        format(res["resumed_sessions"], ","), format(res["resumed_handling_hours"], ",")))
    w("")
    w("5. Work-item activities ranked two ways")
    w("   by hands-on hours (touch-first) and by waiting plus hands-on hours (volume-first)")
    w("   %-32s %7s %8s %8s %5s %10s %10s %5s %5s" % (
        "activity", "tasks", "sessions", "med. min", "res.", "wait h", "hands-on h", "t-rk", "v-rk"))
    for r in res["rows"]:
        w("   %-32s %7s %8s %8s %5d %10s %10s %5d %5d" % (
            r["activity"], format(r["tasks"], ","), format(r["sessions"], ","), r["median_session_min"],
            r["distinct_resources"], format(r["wait_hours"], ","), format(r["handling_hours"], ","),
            r["rank_handling"], r["rank_wait_plus_handling"]))
    w("   top %d by hands-on hours:         %s" % (n, "; ".join(r["activity"] for r in res["rows"][:n])))
    w("   top %d by waiting plus hands-on:  %s" % (n, "; ".join(r["activity"] for r in sorted(res["rows"], key=lambda r: r["rank_wait_plus_handling"])[:n])))
    w("   the volume-first top %d is credited %.1f times the hands-on hours it holds" % (n, res["credit_ratio"]))
    w("")
    w("6. What this log cannot show")
    w("   - No desktop layer: work in a spreadsheet, an email or a second application is not observable, so")
    w("     the off-system share that StepScout measures on the synthetic data cannot be measured here.")
    w("   - No control register and no answer key: no step is classified and no accuracy is claimed.")
    w("   - START to COMPLETE is the time a work item was open, not proof of hands on the keyboard.")
    w("   - One institution, one process, 2011-2012. The numbers describe this log and are not a benchmark.")
    return "\n".join(L) + "\n"


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def selftest() -> int:
    """Run the parser and the analysis on a three-case log whose answers are worked out by hand."""
    def ev(name, trans, ts, res="112"):
        return ('<event><string key="org:resource" value="%s"/><string key="lifecycle:transition" value="%s"/>'
                '<string key="concept:name" value="%s"/><date key="time:timestamp" value="%s"/></event>'
                % (res, trans, name, ts))
    x = '<?xml version="1.0"?><log xmlns="http://www.xes-standard.org/"><string key="concept:name" value="t"/>'
    x += ('<trace><string key="concept:name" value="1"/>'
          + ev("A_SUBMITTED", "COMPLETE", "2011-10-01T09:00:00.000+02:00")
          + ev("W_Check", "SCHEDULE", "2011-10-01T09:05:00.000+02:00")
          + ev("W_Check", "START", "2011-10-01T10:05:00.000+02:00")
          + ev("W_Check", "COMPLETE", "2011-10-01T10:35:00.000+02:00")
          + ev("W_Check", "SCHEDULE", "2011-10-01T10:40:00.000+02:00")
          + ev("W_Check", "START", "2011-10-01T11:40:00.000+02:00")
          + ev("W_Check", "COMPLETE", "2011-10-01T12:10:00.000+02:00", "113") + "</trace>")
    x += ('<trace><string key="concept:name" value="2"/>'
          + ev("A_SUBMITTED", "COMPLETE", "2011-10-02T09:00:00+02:00")
          + ev("W_Call", "SCHEDULE", "2011-10-02T09:00:00.5+02:00")
          + ev("W_Call", "START", "2011-10-02T09:30:00+02:00")
          + ev("W_Call", "COMPLETE", "2011-10-02T09:45:00+02:00") + "</trace>")
    x += ('<trace><string key="concept:name" value="3"/>'
          + ev("W_Review", "SCHEDULE", "2011-10-03T09:00:00+02:00")
          + ev("W_Review", "START", "2011-10-03T09:10:00+02:00")
          + ev("W_Review", "COMPLETE", "2011-10-03T09:20:00+02:00")
          + ev("W_Review", "START", "2011-10-03T09:40:00+02:00")
          + ev("W_Review", "COMPLETE", "2011-10-03T10:00:00+02:00") + "</trace></log>")
    res = analyze(load_cases(io.BytesIO(x.encode("utf-8"))))
    expect = [
        ("cases", res["cases"], 3), ("events", res["events"], 16), ("variants", res["variants"], 3),
        ("sessions", res["sessions"], 5), ("tasks", res["tasks"], 4),
        ("cases that schedule an activity again", res["resched_cases"], 1),
        ("resumed sessions", res["resumed_sessions"], 1), ("unpaired completes", res["unpaired_completes"], 0),
    ]
    by = {r["activity"]: r for r in res["rows"]}
    expect += [("W_Check wait hours", by["W_Check"]["wait_hours"], 2.0),
               ("W_Check hands-on hours", by["W_Check"]["handling_hours"], 1.0),
               ("W_Check sessions", by["W_Check"]["sessions"], 2),
               ("W_Review wait hours", by["W_Review"]["wait_hours"], 0.2)]
    bad = [(n, got, want) for n, got, want in expect if got != want]
    for n, got, want in bad:
        print("selftest FAIL: %s is %r, expected %r" % (n, got, want))
    if not bad:
        print("selftest ok: %d hand-worked values match" % len(expect))
    return 1 if bad else 0


def main(argv: list) -> int:
    if "--selftest" in argv:
        return selftest()
    path = Path(argv[argv.index("--file") + 1]) if "--file" in argv else RAW
    if not path.exists():
        print("The log is not on disk: %s" % path)
        print("Fetch it once with:  python3 ../data/real/fetch_bpi2012.py")
        return 2
    md5_ok = (md5_of(path) == EXPECTED_MD5) if path == RAW else None
    if md5_ok is False:
        print("The file at %s does not match the published MD5 %s; not parsing it." % (path, EXPECTED_MD5))
        return 3
    res = analyze(load_cases(path))
    text = render(res, md5_ok)
    print(text, end="")
    OUT_DIR.mkdir(exist_ok=True)
    summary = {k: v for k, v in res.items() if k != "rows"}
    (OUT_DIR / "real_bpi2012_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with open(OUT_DIR / "real_bpi2012_activities.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(res["rows"][0].keys()))
        w.writeheader()
        w.writerows(res["rows"])
    if "--write-output" in argv:
        (HERE.parent / "data" / "real" / "bpi2012_output.txt").write_text(text, encoding="utf-8")
    print("Wrote out/real_bpi2012_summary.json and out/real_bpi2012_activities.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
