"""
Step 1 — Before observability: 30 days of agent runs with no telemetry.

This is what happens today at most BFSI shops deploying agents (LangGraph,
Bedrock Agents, OpenAI Assistants, AutoGen) into ops workflows. The platform
team ships the agent into production. It works. Then it stops working in a
mode no one has seen before: a runaway loop, a hallucinated tool argument,
a silent shift in the tool-call mix.

Nothing fires. There is no agent-shaped telemetry on top of the existing
service traces. The bank discovers the incident weeks later when the FinOps
review flags the line item, or when a customer complaint surfaces.

This script reads the 30-day synthetic run log and prints the bleed that
would have gone undetected. The headline: $42k of undetected runaway cost
over 30 days across the four-agent fleet.

Run:
    python step_01_no_observability.py

Output:
  - prints the per-agent run summary and the undetected runaway dollar cost
  - writes src/out/step_01_undetected_runaway_costs.csv
"""

import csv
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

# Threshold above which a run is "obviously a runaway" in retrospect.
# Without AgentWatch, this is only visible after the fact.
RUNAWAY_TOOL_CALL_THRESHOLD = 50
RUNAWAY_COST_THRESHOLD_USD = 50.0


def load_runs() -> list[dict]:
    return list(csv.DictReader(open(DATA_DIR / "agent_runs.csv")))


def load_agents() -> dict[str, dict]:
    return {row["agent_id"]: row for row in csv.DictReader(open(DATA_DIR / "agents.csv"))}


def main() -> None:
    runs = load_runs()
    agents = load_agents()

    print("\n" + "=" * 80)
    print("Step 1 — Before observability: 30 days of agent runs, zero telemetry")
    print("=" * 80)
    print()
    print(f"Scope: {len(runs)} agent runs across {len(agents)} deployed agents,")
    print(f"window 2026-04-01 -> 2026-04-30.")
    print()
    print("What the bank has today: latency + error-rate from generic APM. No agent-")
    print("shaped telemetry. No runaway detector. No tool-call diff. No cost ceiling.")
    print()

    # Per-agent rollups
    per_agent = defaultdict(lambda: {"runs": 0, "tool_calls": 0, "cost": 0.0, "runaway_runs": 0, "runaway_cost": 0.0})
    for r in runs:
        aid = r["agent_id"]
        per_agent[aid]["runs"] += 1
        per_agent[aid]["tool_calls"] += int(r["total_tool_calls"])
        per_agent[aid]["cost"] += float(r["total_cost_usd"])
        if (int(r["total_tool_calls"]) >= RUNAWAY_TOOL_CALL_THRESHOLD
                or float(r["total_cost_usd"]) >= RUNAWAY_COST_THRESHOLD_USD):
            per_agent[aid]["runaway_runs"] += 1
            per_agent[aid]["runaway_cost"] += float(r["total_cost_usd"])

    print("=" * 80)
    print("Per-agent rollup (what the FinOps spreadsheet shows at month-end)")
    print("=" * 80)
    print(f"  {'agent_id':<22}{'runs':>8}{'tool_calls':>14}{'total_cost':>14}{'runaways':>12}{'runaway_$':>14}")
    print("  " + "-" * 84)
    total_runaway = 0.0
    total_runaway_runs = 0
    for aid in sorted(per_agent.keys()):
        s = per_agent[aid]
        print(f"  {aid:<22}{s['runs']:>8}{s['tool_calls']:>14}"
              f"${s['cost']:>12,.2f}{s['runaway_runs']:>12}"
              f"${s['runaway_cost']:>12,.2f}")
        total_runaway += s["runaway_cost"]
        total_runaway_runs += s["runaway_runs"]

    print()
    print("=" * 80)
    print("Summary — what the bank does NOT see")
    print("=" * 80)
    print(f"  Total agent runs in window:         {len(runs)}")
    print(f"  Total inference + tool spend:       ${sum(float(r['total_cost_usd']) for r in runs):,.2f}")
    print(f"  Runs we'd retrospectively call      {total_runaway_runs}")
    print( "    runaways (>= 50 tool calls OR")
    print( "    >= $50 / run):")
    print(f"  Undetected runaway dollar bleed:    ${total_runaway:,.2f}")
    print()
    print("  Detection rate today:               0 of {} incidents detected".format(total_runaway_runs))
    print("  Mean-time-to-detect:                ~3 weeks (the FinOps review cycle)")
    print("  Mean-time-to-recover:                no MTTR — incidents are discovered post-mortem")
    print()
    print("  The bank is paying for the incidents AND paying again for the post-mortem.")
    print("  Step 2 adds basic Datadog metrics; Step 3 names the six deficiencies that")
    print("  Datadog still misses; Step 4 closes them with AgentWatch's sidecar.")
    print()

    # Write the undetected runaway report
    out_csv = OUT_DIR / "step_01_undetected_runaway_costs.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["agent_id", "runs", "tool_calls", "total_cost_usd",
                    "runaway_runs", "runaway_cost_usd"])
        for aid in sorted(per_agent.keys()):
            s = per_agent[aid]
            w.writerow([aid, s["runs"], s["tool_calls"], round(s["cost"], 2),
                        s["runaway_runs"], round(s["runaway_cost"], 2)])
    print(f"Wrote: {out_csv}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
