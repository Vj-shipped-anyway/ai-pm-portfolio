"""Step 2 - The basic approach: annual access recertification.

Once a year the agent's manager gets the list of grants and approves what is on it. Nobody opens
the call log. This script plays that review at the review date on the shipped grants.

ASSUMPTIONS (modeled, change them at the top of this file):
  R1. The reviewer approves a grant that carries a ticket reference and revokes one that does not.
  R2. The reviewer does not look at the calls. The list has no usage column.
  R3. One pass a year; this run is the pass at the review date.

Because the data is synthetic, the script can also replay the 90 days of calls under what the
reviewer left in place, to see whether the revocations touched anything in use.

Run (from src/):
    python3 step_02_annual_recertification.py

Output: a readable summary, plus out/step_02_recertification.csv and out/step_02_summary.json.
"""

from __future__ import annotations

import csv
import json

from step_01_status_quo import (AS_OF, OUT_DIR, effective_scopes, grant_usage, load_all, replay_calls,
                                usage_index)

REVOKE_IF_NO_TICKET = True          # assumption R1


def recertify(data: dict) -> list:
    """One verdict per grant: approved or removed, by assumption R1."""
    rows = []
    for g in data["grants"]:
        removed = REVOKE_IF_NO_TICKET and not g["has_ticket"]
        rows.append({"agent_id": g["agent_id"], "scope": g["scope"], "ticket_id": g["ticket_id"],
                     "granted_on": g["granted_on"], "verdict": "removed" if removed else "approved"})
    return rows


def allowed_after(data: dict, rows: list) -> dict:
    removed = {(r["agent_id"], r["scope"]) for r in rows if r["verdict"] == "removed"}
    return {a["agent_id"]: set(effective_scopes(data, a["agent_id"], [
        g for g in data["grants_by_agent"][a["agent_id"]] if (g["agent_id"], g["scope"]) not in removed]))
        for a in data["agents"]}


def summarize(data: dict) -> dict:
    rows = recertify(data)
    n = len(rows)
    removed = [r for r in rows if r["verdict"] == "removed"]
    gu = {(g["agent_id"], g["scope"]): g for g in grant_usage(data, usage_index(data))}
    denied = replay_calls(data, allowed_after(data, rows))
    per_agent = []
    for a in data["agents"]:
        rs = [r for r in rows if r["agent_id"] == a["agent_id"]]
        ap = sum(1 for r in rs if r["verdict"] == "approved")
        per_agent.append({"agent_id": a["agent_id"], "grants": len(rs), "approved": ap, "removed": len(rs) - ap,
                          "approved_pct": round(100 * ap / len(rs), 1)})
    return {
        "grants": n, "approved": n - len(removed), "removed": len(removed),
        "approved_pct": round(100 * (n - len(removed)) / n, 1),
        "removed_pct": round(100 * len(removed) / n, 1),
        "removed_in_use": sum(1 for r in removed if gu[(r["agent_id"], r["scope"])]["used"]),
        "removed_unused": sum(1 for r in removed if not gu[(r["agent_id"], r["scope"])]["used"]),
        "replay_calls": len(data["calls"]), "replay_denied": len(denied),
        "agents_at_100": sum(1 for p in per_agent if p["removed"] == 0),
        "agents": len(per_agent),
        "removed_list": [{"agent_id": r["agent_id"], "scope": r["scope"],
                          "used": gu[(r["agent_id"], r["scope"])]["used"]} for r in removed],
        "per_agent": per_agent, "rows": rows,
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    s = summarize(data)

    print("\n" + "=" * 78)
    print("Step 2 - The basic approach: annual access recertification")
    print("=" * 78)
    print(f"\nReview date {AS_OF}. The manager sees {s['grants']} grants and no usage column.\n")
    print("ASSUMPTIONS (modeled):")
    print("  R1  a grant with a ticket reference is approved; a grant with none is revoked")
    print("  R2  the reviewer does not open the call log")
    print("  R3  one pass a year; this run is that pass\n")

    print(f"{'agent':<6} {'grants':>6} {'approved':>8} {'removed':>7} {'approved %':>10}")
    print(f"{'-' * 6} {'-' * 6} {'-' * 8} {'-' * 7} {'-' * 10}")
    for p in s["per_agent"]:
        print(f"{p['agent_id']:<6} {p['grants']:>6} {p['approved']:>8} {p['removed']:>7} {p['approved_pct']:>9.1f}%")

    print("\nRESULT")
    print(f"  Approved: {s['approved']} of {s['grants']} grants ({s['approved_pct']}%)")
    print(f"  Removed:  {s['removed']} of {s['grants']} grants ({s['removed_pct']}%), all for a missing ticket, none for lack of use")
    print(f"  Agents whose whole list was approved: {s['agents_at_100']} of {s['agents']}")
    for r in s["removed_list"]:
        print(f"    removed {r['agent_id']} {r['scope']}: {'the agent called it in the window' if r['used'] else 'no call in the window'}")
    print(f"  Dry-run of the 90 days of calls under what the review left in place: "
          f"{s['replay_denied']} of {s['replay_calls']:,} calls denied")

    with open(OUT_DIR / "step_02_recertification.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["agent_id", "scope", "granted_on", "ticket_id", "verdict"])
        for r in s["rows"]:
            w.writerow([r["agent_id"], r["scope"], r["granted_on"], r["ticket_id"], r["verdict"]])
    with open(OUT_DIR / "step_02_summary.json", "w") as f:
        json.dump({k: v for k, v in s.items() if k not in ("rows", "per_agent")}, f, indent=2)
    print("\nWrote src/out/step_02_recertification.csv and step_02_summary.json")


if __name__ == "__main__":
    main()
