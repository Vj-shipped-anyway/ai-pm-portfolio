"""Step 3 - Where the ticket queue breaks: six named deficiencies, each with a count.

Step 2 showed that a queue sorted by reporter priority gets part of the order right. This
step asks what it cannot do, using the same synthetic incidents and the generator's truth
(data/truth.csv) and policy (data/policy.csv).

  (a) The reporter's priority differs from the rubric severity.
  (b) Free-text categories cannot be aggregated.
  (c) Notification clocks are missed, or never started.
  (d) The clock starts at detection or at determination, and the two give different breach counts.
  (e) Follow-up actions are overdue, or closed with no evidence.
  (f) Related incidents are not linked: the same root cause sits in several tickets.

Clock arithmetic here is written from the truth (true severity and the policy file), and
evaluated at AS_OF. Step 4 re-derives the same statuses from the incident fields alone and
checks they agree.

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: a readable summary, plus out/step_03_deadlines.csv and out/step_03_summary.json.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict

from step_01_ticket_queue_status_quo import AS_OF, CATEGORIES, OUT_DIR, fmt_hour, load_all, normalize_label
from step_01_ticket_queue_status_quo import summarize as summarize_step1

STATUSES = ["on_time", "late", "breached", "running", "not_started"]


def truth_applies(applies_to: str, sev: str, pii: int, reg: int) -> bool:
    """Which policy clocks apply, from the TRUE severity (the generator's decision)."""
    notification = sev == "S1" or (sev == "S2" and bool(pii or reg))
    serious = sev == "S1" and bool(pii or reg)
    return {"sev_s1": sev == "S1", "notification_incident": notification,
            "pii_exposed": bool(pii), "serious_incident": serious}[applies_to]


def deadline_rows(data: dict, anchor: str = "policy") -> list:
    """One row per (incident, clock) that applies. anchor: 'policy', 'determination' or 'detection'."""
    rows = []
    for inc in data["incidents"]:
        t = data["truth"][inc["incident_id"]]
        for p in data["policy"]:
            if not truth_applies(p["applies_to"], t["severity"], inc["pii_exposed"],
                                 inc["regulated_decision_involved"]):
                continue
            anchor_name = p["anchor"] if anchor == "policy" else anchor
            start = inc["determined_at"] if anchor_name == "determination" else inc["detected_at"]
            row = {"incident_id": inc["incident_id"], "clock_id": p["clock_id"], "anchor": anchor_name,
                   "hours": p["hours"], "start": start, "due": None, "sent_at": None}
            if start is None:
                row["status"] = "not_started"
            else:
                row["due"] = start + p["hours"]
                row["sent_at"] = data["sent"].get((inc["incident_id"], p["clock_id"]))
                if row["sent_at"] is not None:
                    row["status"] = "on_time" if row["sent_at"] <= row["due"] else "late"
                else:
                    row["status"] = "breached" if row["due"] < AS_OF else "running"
            rows.append(row)
    return rows


def count_status(rows: list) -> dict:
    c = Counter(r["status"] for r in rows)
    out = {s: c.get(s, 0) for s in STATUSES}
    out["applicable"] = len(rows)
    out["missed"] = out["late"] + out["breached"]
    return out


def summarize(data: dict) -> dict:
    inc, truth, acts = data["incidents"], data["truth"], data["actions"]
    n = len(inc)

    # (a) priority vs rubric
    exact = sum(1 for i in inc if i["reporter_priority"][1] == truth[i["incident_id"]]["severity"][1])
    severe_low = [i for i in inc if truth[i["incident_id"]]["severity"] in ("S1", "S2")
                  and i["reporter_priority"] in ("P3", "P4")]
    mild_high = [i for i in inc if truth[i["incident_id"]]["severity"] in ("S3", "S4")
                 and i["reporter_priority"] in ("P1", "P2")]
    severe = sum(1 for i in inc if truth[i["incident_id"]]["severity"] in ("S1", "S2"))
    a = {"exact": exact, "severe": severe, "severe_filed_low": len(severe_low), "mild_filed_high": len(mild_high),
         "s1_filed_low": sum(1 for i in severe_low if truth[i["incident_id"]]["severity"] == "S1")}

    # (b) free-text categories
    raw = Counter(i["reporter_category"] for i in inc)
    classes_by_label = defaultdict(set)
    tickets_by_label = Counter()
    for i in inc:
        lab = normalize_label(i["reporter_category"])
        classes_by_label[lab].add(truth[i["incident_id"]]["category"])
        tickets_by_label[lab] += 1
    shared = [lab for lab in sorted(classes_by_label) if len(classes_by_label[lab]) > 1]
    b = {"raw": len(raw), "normalized": len(classes_by_label), "classes": len(CATEGORIES),
         "shared_labels": len(shared), "shared_tickets": sum(tickets_by_label[l] for l in shared),
         "shared_examples": sorted(shared, key=lambda l: (-tickets_by_label[l], l))[:5]}

    # (c) clocks at the policy anchor
    pol = deadline_rows(data, "policy")
    c = count_status(pol)
    c["by_clock"] = {p["clock_id"]: count_status([r for r in pol if r["clock_id"] == p["clock_id"]])
                     for p in data["policy"]}
    c["not_started_incidents"] = len({r["incident_id"] for r in pol if r["status"] == "not_started"})
    c["tracked_by_queue"] = summarize_step1(data)["clocks_tracked"]

    # (d) anchor
    det = count_status(deadline_rows(data, "detection"))
    lags = [i["determined_at"] - i["detected_at"] for i in inc if i["determined_at"] is not None]
    d = {"at_determination": c["missed"], "not_started": c["not_started"], "at_detection": det["missed"],
         "on_time_at_detection": det["on_time"], "median_lag": statistics.median(lags), "max_lag": max(lags),
         "lag_over_24": sum(1 for x in lags if x > 24), "determined": len(lags)}

    # (e) follow-ups
    closed = [x for x in acts if x["status"] == "closed"]
    not_closed = [x for x in acts if x["status"] != "closed"]
    overdue = [x for x in not_closed if x["due_at"] < AS_OF]
    no_evidence = [x for x in closed if x["evidence_link"] == "no"]
    flagged_incidents = {x["incident_id"] for x in overdue + no_evidence}
    e = {"actions": len(acts), "closed": len(closed), "not_closed": len(not_closed), "overdue": len(overdue),
         "closed_no_evidence": len(no_evidence), "flagged": len(overdue) + len(no_evidence),
         "flagged_incidents": len(flagged_incidents),
         "flagged_severe_incidents": sum(1 for x in flagged_incidents
                                         if truth[x]["severity"] in ("S1", "S2"))}

    # (f) related incidents
    groups = defaultdict(list)
    for i in inc:
        groups[truth[i["incident_id"]]["root_cause"]].append(i["incident_id"])
    repeated = {k: v for k, v in groups.items() if len(v) > 1}
    f = {"root_causes": len(groups), "repeated_causes": len(repeated),
         "tickets_in_repeated": sum(len(v) for v in repeated.values()),
         "repeat_tickets": sum(len(v) - 1 for v in repeated.values()),
         "largest_group": max(len(v) for v in groups.values()),
         "queue_links": summarize_step1(data)["link_fields"]}
    return {"incidents": n, "a": a, "b": b, "c": c, "d": d, "e": e, "f": f}


def noun(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    s = summarize(data)
    n = s["incidents"]
    a, b, c, d, e, f = s["a"], s["b"], s["c"], s["d"], s["e"], s["f"]

    print("\n" + "=" * 78)
    print("Step 3 - Where the ticket queue breaks: six named deficiencies")
    print("=" * 78)

    print("\n(a) The reporter's priority differs from the rubric severity")
    print(f"    Priority matches the rubric severity on {a['exact']} of {n} tickets ({100 * a['exact'] / n:.1f}%).")
    print(f"    {a['severe_filed_low']} of {a['severe']} tickets that are truly S1 or S2 were filed P3 or P4 "
          f"({a['s1_filed_low']} of them S1).")
    print(f"    {noun(a['mild_filed_high'], 'ticket')} that {'is' if a['mild_filed_high'] == 1 else 'are'} truly S3 or S4 "
          f"{'was' if a['mild_filed_high'] == 1 else 'were'} filed P1 or P2.")

    print("\n(b) Free-text categories cannot be aggregated")
    print(f"    Reporters typed {b['raw']} distinct category strings for {b['classes']} real classes "
          f"({b['normalized']} after lowercasing and trimming).")
    print(f"    {b['shared_labels']} of those {b['normalized']} labels are used for more than one real class, "
          f"covering {b['shared_tickets']} tickets ({100 * b['shared_tickets'] / n:.1f}%).")
    print("    Most-shared labels: " + ", ".join(f"'{x}'" for x in b["shared_examples"]) + ".")

    print("\n(c) Notification clocks are missed, or never started")
    print(f"    {c['applicable']} notification deadlines apply under the modeled policy; the queue tracks {c['tracked_by_queue']}.")
    print(f"    At {fmt_hour(AS_OF)}: {c['on_time']} sent on time, {c['late']} sent late, {c['breached']} never sent and past due, "
          f"{c['running']} still running, {c['not_started']} not started.")
    print(f"    Missed (late or never sent): {c['missed']} of {c['applicable']} ({100 * c['missed'] / c['applicable']:.1f}%).")
    print(f"    {noun(c['not_started'], 'deadline')} on {noun(c['not_started_incidents'], 'incident')} never started: "
          f"nobody recorded a determination.")
    print("    clock  applies  on_time  late  breached  running  not_started")
    for ck, v in c["by_clock"].items():
        print(f"    {ck:<5}  {v['applicable']:>7}  {v['on_time']:>7}  {v['late']:>4}  {v['breached']:>8}  "
              f"{v['running']:>7}  {v['not_started']:>11}")

    print("\n(d) The clock starts at detection or at determination, and the two disagree")
    print(f"    Detection to determination took a median {d['median_lag']:g} h (longest {d['max_lag']} h); "
          f"{d['lag_over_24']} of {d['determined']} determined incidents took more than 24 h.")
    print(f"    Deadlines missed with the clock from determination: {d['at_determination']} "
          f"(plus {d['not_started']} not started).")
    print(f"    Deadlines missed with the clock from detection:     {d['at_detection']}.")
    print(f"    The anchor changes the count by {d['at_detection'] - d['at_determination']}; "
          f"the queue has no anchor, so each team picks its own.")

    print("\n(e) Follow-up actions are overdue, or closed with no evidence")
    print(f"    {e['overdue']} of {e['not_closed']} open actions are past their due date; the queue shows no flag.")
    print(f"    {e['closed_no_evidence']} of {e['closed']} closed actions have no evidence link "
          f"({100 * e['closed_no_evidence'] / e['closed']:.1f}%).")
    print(f"    {e['flagged']} of {e['actions']} actions ({100 * e['flagged'] / e['actions']:.1f}%) sit on "
          f"{e['flagged_incidents']} incidents, {e['flagged_severe_incidents']} of them S1 or S2.")

    print("\n(f) Related incidents are not linked")
    print(f"    {n} tickets come from {f['root_causes']} root causes; {f['repeated_causes']} root causes appear in "
          f"more than one ticket ({f['tickets_in_repeated']} tickets).")
    print(f"    {f['repeat_tickets']} tickets are repeats of an earlier one; the largest root cause has "
          f"{f['largest_group']} tickets. The queue links {f['queue_links']}.")

    rows = deadline_rows(data, "policy")
    with open(OUT_DIR / "step_03_deadlines.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["incident_id", "clock_id", "anchor", "start", "due", "sent_at", "status"])
        for r in rows:
            w.writerow([r["incident_id"], r["clock_id"], r["anchor"], "" if r["start"] is None else r["start"],
                        "" if r["due"] is None else r["due"], "" if r["sent_at"] is None else r["sent_at"], r["status"]])
    with open(OUT_DIR / "step_03_summary.json", "w") as fh:
        json.dump(s, fh, indent=2)
    print("\nWrote src/out/step_03_deadlines.csv and step_03_summary.json")


if __name__ == "__main__":
    main()
