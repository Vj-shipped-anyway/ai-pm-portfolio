"""Step 2 - The basic approach: work the ticket queue by reporter priority, oldest first.

This is what a team does with a ticket system: sort by the priority the reporter picked
(P1 first), oldest ticket first inside a priority (FIFO), and work down the list. There are
no clocks and no rubric. The queue marks a ticket P1 or P2 when the reporter said so.

This script builds that queue and scores it against the generator's truth (data/truth.csv):
how many tickets it marks urgent, how many of those are really severe, and where the
severe ones sit in the list. Scoring uses truth.csv; the queue itself does not.

Run (from src/):
    python3 step_02_priority_fifo_baseline.py

Output: a readable summary, plus out/step_02_queue.csv and out/step_02_summary.json.
"""

from __future__ import annotations

import csv
import json
import statistics

from step_01_ticket_queue_status_quo import OUT_DIR, load_all
from step_01_ticket_queue_status_quo import summarize as summarize_step1


def queue_order(incidents: list) -> list:
    """Priority first (P1 to P4), then oldest report first, then id."""
    return sorted(incidents, key=lambda i: (int(i["reporter_priority"][1]), i["reported_at"], i["incident_id"]))


def summarize(data: dict) -> dict:
    inc, truth = data["incidents"], data["truth"]
    order = queue_order(inc)
    pos = {i["incident_id"]: k + 1 for k, i in enumerate(order)}
    marked = [i for i in inc if i["reporter_priority"] in ("P1", "P2")]
    severe_ids = {i["incident_id"] for i in inc if truth[i["incident_id"]]["severity"] in ("S1", "S2")}
    s1 = [i for i in inc if truth[i["incident_id"]]["severity"] == "S1"]
    marked_severe = [i for i in marked if i["incident_id"] in severe_ids]
    top20 = order[:20]
    s1_pos = sorted(pos[i["incident_id"]] for i in s1)
    s1_low = [i for i in s1 if i["reporter_priority"] in ("P3", "P4")]
    return {
        "incidents": len(inc),
        "marked_urgent": len(marked),
        "marked_urgent_severe": len(marked_severe),
        "severe": len(severe_ids),
        "top20_severe": sum(1 for i in top20 if i["incident_id"] in severe_ids),
        "s1": len(s1),
        "s1_marked_urgent": sum(1 for i in s1 if i["reporter_priority"] in ("P1", "P2")),
        "s1_filed_low": len(s1_low),
        "s1_median_position": statistics.median(s1_pos),
        "s1_worst_position": s1_pos[-1],
        "clocks_shown": summarize_step1(data)["clocks_tracked"],
        "position": pos,
        "order": [i["incident_id"] for i in order],
    }


def short(text: str, width: int) -> str:
    return text if len(text) <= width else text[:width - 3] + "..."


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    s = summarize(data)
    truth = data["truth"]
    n = s["incidents"]
    order = [data["by_id"][x] for x in s["order"]]

    print("\n" + "=" * 78)
    print("Step 2 - With the basic approach: a ticket queue, priority then oldest first")
    print("=" * 78)
    print("\nThe queue sorts by the priority the reporter picked, oldest first within a priority.")
    print("There is no rubric and no clock. The 'truth' column is the generator's severity (scoring only).\n")
    print(f"{'pos':>3}  {'incident':<9} {'queue':<5} {'truth':<5} {'title'}")
    print(f"{'-' * 3}  {'-' * 9} {'-' * 5} {'-' * 5} {'-' * 50}")
    for k, i in enumerate(order[:12], 1):
        print(f"{k:>3}  {i['incident_id']:<9} {i['reporter_priority']:<5} "
              f"{truth[i['incident_id']]['severity']:<5} {short(i['title'], 50)}")
    print("  ...")

    def row(label, value):
        print(f"  {label:<52}{value}")

    print("\nRESULT")
    row("Tickets the queue marks P1 or P2:",
        f"{s['marked_urgent']} of {n} ({100 * s['marked_urgent'] / n:.1f}%)")
    row("Of those, truly S1 or S2 under the rubric:",
        f"{s['marked_urgent_severe']} of {s['marked_urgent']} ({100 * s['marked_urgent_severe'] / s['marked_urgent']:.1f}%)")
    row("Truly S1 or S2 tickets the queue marks P1 or P2:",
        f"{s['marked_urgent_severe']} of {s['severe']} ({100 * s['marked_urgent_severe'] / s['severe']:.1f}%)")
    row("Truly S1 or S2 among the first 20 tickets worked:", f"{s['top20_severe']} of 20")
    row("Truly S1 tickets filed P3 or P4:", f"{s['s1_filed_low']} of {s['s1']}")
    row(f"Queue position of the {s['s1']} S1 tickets:",
        f"median {s['s1_median_position']:g}, worst {s['s1_worst_position']} of {n}")
    row("Notification deadlines shown by the queue:", f"{s['clocks_shown']}")

    with open(OUT_DIR / "step_02_queue.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["position", "incident_id", "reporter_priority", "true_severity", "reported_at"])
        for k, i in enumerate(order, 1):
            w.writerow([k, i["incident_id"], i["reporter_priority"], truth[i["incident_id"]]["severity"], i["reported_at"]])
    slim = {k: v for k, v in s.items() if k not in ("position", "order")}
    with open(OUT_DIR / "step_02_summary.json", "w") as f:
        json.dump(slim, f, indent=2)
    print("\nWrote src/out/step_02_queue.csv and step_02_summary.json")


if __name__ == "__main__":
    main()
