"""Step 1 - Before IncidentLedger: AI incidents live in a ticket queue.

A modeled bank logs AI incidents (wrong outputs, data exposure, unfair outcomes, outages,
injection, regressions after a model change) as tickets. The reporter picks the priority,
types a free-text category, and the ticket sits in a queue. Nobody tracks notification
deadlines, and follow-up actions close without evidence.

This script describes the queue as it stands at AS_OF, and counts what the queue can and
cannot say. No model is used; the data is synthetic (data/_generate.py, seeded).

Shared loaders live here (later steps and the app import them):
  load_all()   reads the five CSVs into plain dicts, no pandas needed
  fmt_hour()   turns an hour number into a date string (hour 0 = EPOCH)

Run (from src/):
    python3 step_01_ticket_queue_status_quo.py

Output: a readable summary, plus out/step_01_summary.json.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

EPOCH = datetime(2026, 7, 1)     # hour 0; same constant as data/_generate.py
AS_OF = 2304                     # hour 2304 = 2026-10-05T00:00; same constant as data/_generate.py

CATEGORIES = ["wrong_output", "unfair_outcome", "data_exposure", "security_injection",
              "availability", "regression_after_change", "misuse"]
CATEGORY_NAMES = {
    "wrong_output": "wrong output", "unfair_outcome": "unfair outcome", "data_exposure": "data exposure",
    "security_injection": "security and injection", "availability": "availability",
    "regression_after_change": "regression after change", "misuse": "misuse",
    "needs_review": "needs a person",
}


def fmt_hour(h) -> str:
    """Hour number to a date string. Hour 0 is EPOCH."""
    return (EPOCH + timedelta(hours=int(h))).strftime("%Y-%m-%d %H:%M")


def normalize_label(label: str) -> str:
    """The most a script can do with a free-text category: lowercase, trim, drop a trailing ?."""
    return label.strip().lower().rstrip("?").strip()


def _opt_int(v):
    return int(v) if v != "" else None


def load_all(data_dir: Path = DATA_DIR) -> dict:
    """Load the five CSVs into plain dicts. Incidents keep file order (= time order)."""
    with open(data_dir / "incidents.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames)
        incidents = []
        for r in reader:
            incidents.append({
                "incident_id": r["incident_id"], "reported_at": int(r["reported_at"]),
                "reporter_priority": r["reporter_priority"], "reporter_category": r["reporter_category"],
                "title": r["title"], "description": r["description"], "system": r["system"],
                "change_id": r["change_id"], "customers_affected": int(r["customers_affected"]),
                "regulated_decision_involved": int(r["regulated_decision_involved"]),
                "pii_exposed": int(r["pii_exposed"]), "financial_impact_band": r["financial_impact_band"],
                "duration_hours": int(r["duration_hours"]), "detected_at": int(r["detected_at"]),
                "determined_at": _opt_int(r["determined_at"]),
            })
    with open(data_dir / "truth.csv", newline="", encoding="utf-8") as f:
        truth = {r["incident_id"]: {"category": r["true_category"], "severity": r["true_severity"],
                                    "root_cause": r["root_cause_key"], "hard_case": r["hard_case"]}
                 for r in csv.DictReader(f)}
    with open(data_dir / "policy.csv", newline="", encoding="utf-8") as f:
        policy = [{"clock_id": r["clock_id"], "name": r["clock_name"], "applies_to": r["applies_to"],
                   "hours": int(r["hours"]), "anchor": r["anchor"], "basis": r["basis"], "note": r["note"]}
                  for r in csv.DictReader(f)]
    with open(data_dir / "notifications.csv", newline="", encoding="utf-8") as f:
        notifications = [{"notification_id": r["notification_id"], "incident_id": r["incident_id"],
                          "clock_id": r["clock_id"], "sent_at": int(r["sent_at"])} for r in csv.DictReader(f)]
    with open(data_dir / "actions.csv", newline="", encoding="utf-8") as f:
        actions = [{"action_id": r["action_id"], "incident_id": r["incident_id"], "action": r["action"],
                    "owner": r["owner"], "due_at": int(r["due_at"]), "status": r["status"],
                    "closed_at": _opt_int(r["closed_at"]), "evidence_link": r["evidence_link"]}
                   for r in csv.DictReader(f)]
    return {
        "incident_columns": columns, "incidents": incidents, "by_id": {i["incident_id"]: i for i in incidents}, "truth": truth,
        "policy": policy, "notifications": notifications,
        "sent": {(n["incident_id"], n["clock_id"]): n["sent_at"] for n in notifications},
        "actions": actions,
    }


def summarize(data: dict) -> dict:
    inc, acts = data["incidents"], data["actions"]
    prio = Counter(i["reporter_priority"] for i in inc)
    raw = Counter(i["reporter_category"] for i in inc)
    norm = Counter(normalize_label(i["reporter_category"]) for i in inc)
    not_closed = [a for a in acts if a["status"] != "closed"]
    overdue = [a for a in not_closed if a["due_at"] < AS_OF]
    return {
        "incidents": len(inc),
        "first_report": min(i["reported_at"] for i in inc),
        "last_report": max(i["reported_at"] for i in inc),
        "priority": {p: prio[p] for p in ("P1", "P2", "P3", "P4")},
        "raw_labels": len(raw), "normalized_labels": len(norm),
        "top_labels": sorted(raw.items(), key=lambda kv: (-kv[1], kv[0]))[:6],
        "actions": len(acts), "actions_closed": len(acts) - len(not_closed),
        "actions_not_closed": len(not_closed), "actions_overdue_not_flagged": len(overdue),
        "no_determination": sum(1 for i in inc if i["determined_at"] is None),
        # a queue tracks a deadline only if the ticket has a field for one
        "clocks_tracked": sum(1 for c in data["incident_columns"]
                              if any(w in c for w in ("deadline", "due", "clock", "sla"))),
        # ... and links tickets only if it has a field that points from one ticket to another
        "link_fields": sum(1 for c in data["incident_columns"]
                           if any(w in c for w in ("related", "parent", "duplicate", "link"))),
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    s = summarize(data)
    n = s["incidents"]

    print("\n" + "=" * 78)
    print("Step 1 - Before IncidentLedger: AI incidents in a ticket queue")
    print("=" * 78)
    print(f"\n{n} incidents reported between {fmt_hour(s['first_report'])} and {fmt_hour(s['last_report'])}; "
          f"the queue is read as of {fmt_hour(AS_OF)}.")
    print("Data is synthetic and seeded. The truth is known because the generator decided it.\n")
    print("What a ticket holds:  the priority the reporter picked, a free-text category, a title,")
    print("                      a description, a linked change id when the reporter knew one.")
    print("What the queue lacks: a severity rubric, a category list, a notification clock,")
    print("                      a link between related tickets, evidence on follow-up actions.\n")

    print("Tickets by the priority the reporter picked:")
    for p, c in s["priority"].items():
        print(f"  {p}  {c:>3}  ({100 * c / n:4.1f}%)")

    print("\nFree-text categories typed by reporters, most used first:")
    for label, c in s["top_labels"]:
        print(f"  {c:>3}  '{label}'")

    print("\nRESULT")
    print(f"  Tickets filed:                                {n}")
    print(f"  Priorities chosen by the reporter:            P1 {s['priority']['P1']}, P2 {s['priority']['P2']}, "
          f"P3 {s['priority']['P3']}, P4 {s['priority']['P4']}")
    print(f"  Distinct free-text categories:                {s['raw_labels']} "
          f"({s['normalized_labels']} after lowercasing and trimming)")
    print(f"  Notification deadlines tracked by the queue:  {s['clocks_tracked']}")
    print(f"  Follow-up actions:                            {s['actions']} "
          f"({s['actions_closed']} closed, {s['actions_not_closed']} not closed)")
    print(f"  Not-closed actions already past their due date: {s['actions_overdue_not_flagged']} "
          f"(the queue shows no flag)")
    print(f"  Tickets with no determination time recorded:  {s['no_determination']}")

    with open(OUT_DIR / "step_01_summary.json", "w") as f:
        json.dump(s, f, indent=2)
    print("\nWrote src/out/step_01_summary.json")


if __name__ == "__main__":
    main()
