"""Step 2 - With the basic approach: read the red-amber-green report as sent.

The basic approach is the one most program offices already run: take the owners' statuses as
reported, put every amber and red on an attention list, and spend the monthly review on those.
This script scores that list against what each program's status truly is.

The truth is known because the data is synthetic: data/_generate.py decided which programs have
unmet or stale gate evidence, which are slipped and which wait on a bad upstream program, and
wrote the answer to data/program_truth.csv. No decision in this repo reads that file; it is
used here and in step 04 only to score.

Run (from src/):
    python3 step_02_rag_attention_list.py

Output: a readable summary, plus out/step_02_attention_list.csv and out/step_02_summary.json.
"""

from __future__ import annotations

import csv
import json

from step_01_rag_status_report import OUT_DIR, RAGS, load_all, pct, usd_m

COLORS = ["GREEN", "AMBER", "RED"]


def score_attention_list(data: dict) -> dict:
    """Score 'amber or red as reported' against the true status of each program."""
    rows = []
    for p in data["programs"]:
        t = data["truth"][p["program_id"]]
        reported = p["self_reported_rag"].upper()
        true = t["true_status"]
        rows.append({"program_id": p["program_id"], "name": p["name"], "stage": p["stage"],
                     "owner": p["owner"], "reported": reported, "true": true,
                     "on_list": reported != "GREEN", "needs_attention": true != "GREEN",
                     "benefit": p["est_benefit_usd"]})
    matrix = {r: {c: 0 for c in COLORS} for r in COLORS}
    for r in rows:
        matrix[r["reported"]][r["true"]] += 1
    needs = [r for r in rows if r["needs_attention"]]
    listed = [r for r in rows if r["on_list"]]
    caught = [r for r in rows if r["on_list"] and r["needs_attention"]]
    missed = [r for r in rows if not r["on_list"] and r["needs_attention"]]
    false_alarms = [r for r in rows if r["on_list"] and not r["needs_attention"]]
    true_red = [r for r in rows if r["true"] == "RED"]
    true_red_reported_red = [r for r in true_red if r["reported"] == "RED"]
    matches = [r for r in rows if r["reported"] == r["true"]]
    return {"rows": rows, "matrix": matrix, "listed": listed, "needs": needs, "caught": caught,
            "missed": missed, "false_alarms": false_alarms, "true_red": true_red,
            "true_red_reported_red": true_red_reported_red, "matches": matches}


def summarize(data: dict) -> dict:
    s = score_attention_list(data)
    n = len(s["rows"])
    return {
        "programs": n, "listed": len(s["listed"]), "needs_attention": len(s["needs"]),
        "caught": len(s["caught"]), "missed": len(s["missed"]), "false_alarms": len(s["false_alarms"]),
        "true_red": len(s["true_red"]), "true_red_reported_red": len(s["true_red_reported_red"]),
        "true_red_reported_green": sum(1 for r in s["true_red"] if r["reported"] == "GREEN"),
        "matches": len(s["matches"]), "pct_matches": round(100.0 * len(s["matches"]) / n, 1),
        "pct_missed_of_needs": round(100.0 * len(s["missed"]) / len(s["needs"]), 1),
        "missed_benefit": sum(r["benefit"] for r in s["missed"]),
        "matrix": s["matrix"],
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    sc = score_attention_list(data)
    s = summarize(data)
    n = s["programs"]

    print("\n" + "=" * 78)
    print("STEP 02 - With the basic approach: read the red-amber-green report as sent")
    print("=" * 78)
    print("\nThe attention list is every program its owner reported amber or red.")
    print("It is scored against the true status the generator wrote (known because the data is synthetic).\n")

    print("REPORTED STATUS (rows) AGAINST TRUE STATUS (columns)")
    print(f"{'':<14}{'true GREEN':>11}{'true AMBER':>12}{'true RED':>10}")
    for rep in COLORS:
        m = sc["matrix"][rep]
        print(f"{'reported ' + rep:<14}{m['GREEN']:>11}{m['AMBER']:>12}{m['RED']:>10}")

    print("\nRESULT")
    print(f"  Attention list length:                      {s['listed']} of {n} programs")
    print(f"  Programs whose true status is not green:    {s['needs_attention']} of {n}")
    print(f"  Truly not green and on the list (caught):   {s['caught']} of {s['needs_attention']} "
          f"({pct(s['caught'], s['needs_attention'])})")
    print(f"  Truly not green but reported green (missed): {s['missed']} of {s['needs_attention']} "
          f"({pct(s['missed'], s['needs_attention'])})")
    print(f"  On the list but truly green (false alarm):  {s['false_alarms']} of {s['listed']}")
    print(f"  Programs truly red:                         {s['true_red']}; reported red on "
          f"{s['true_red_reported_red']}, reported green on {s['true_red_reported_green']}")
    print(f"  Reported color equals true status:          {s['matches']} of {n} ({pct(s['matches'], n)})")
    print(f"  Owner-estimated benefit in the missed programs: {usd_m(s['missed_benefit'])}")

    print("\nLARGEST MISSED PROGRAMS (reported green, true status not green)")
    print(f"{'program':<8}{'name':<34}{'stage':<11}{'true':<7}{'benefit':>9}")
    for r in sorted(sc["missed"], key=lambda x: -x["benefit"])[:8]:
        print(f"{r['program_id']:<8}{r['name']:<34}{r['stage']:<11}{r['true']:<7}{usd_m(r['benefit']):>9}")
    print("  ...")

    print("\nThe list is only as good as the owners' own judgment. It cannot tell a green with")
    print("clean evidence from a green with an unmet gate criterion, because the report carries no evidence.")

    with open(OUT_DIR / "step_02_attention_list.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["program_id", "name", "stage", "owner", "reported", "true_status", "on_list", "needs_attention"])
        for r in sc["rows"]:
            w.writerow([r["program_id"], r["name"], r["stage"], r["owner"], r["reported"], r["true"],
                        int(r["on_list"]), int(r["needs_attention"])])
    with open(OUT_DIR / "step_02_summary.json", "w") as f:
        json.dump(s, f, indent=2)
    print("\nWrote src/out/step_02_attention_list.csv and step_02_summary.json")


if __name__ == "__main__":
    main()
