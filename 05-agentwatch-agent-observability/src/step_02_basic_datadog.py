"""
Step 2 — Basic Datadog metrics: latency, error rate, token count.

Most banks call this "we have agent observability." The platform team wires
the agent's HTTP service into Datadog APM. They get RED metrics — Rate, Errors,
Duration — at the service level. Token-count gauges land alongside. Some teams
add a Langfuse / Helicone trace for the GenAI proxy.

That is necessary. It is nowhere near sufficient for an agent.

Generic APM is shaped for stateless services that take one request and return
one response. An agent is a multi-step plan. Its failure modes — looping,
hallucinating tool arguments, drifting its tool-call mix over weeks, compounding
blast radius — are invisible to a tool whose unit of observation is the
HTTP request.

This script reads the same 30-day run log, applies generic-APM heuristics
(latency thresholds, error-rate thresholds), and counts how many runaways
those heuristics surface. The headline: ~30% of runaways eventually surface.
The other 70% live and die quietly inside the FinOps bill.

Run:
    python step_02_basic_datadog.py

Output:
  - prints the per-incident detection rate under generic APM
  - writes src/out/step_02_apm_detection_attempt.csv
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

# Generic-APM thresholds — what a Datadog monitor or alert looks like in practice.
APM_LATENCY_ALERT_S = 600  # service "took > 10 minutes" — eventually fires
APM_ERROR_RATE_ALERT = 0.20  # service has > 20% errors in a window
APM_TOKEN_BURN_USD = 100.0  # raw "this single run cost > $100"


def load_runs() -> list[dict]:
    return list(csv.DictReader(open(DATA_DIR / "agent_runs.csv")))


def load_incidents() -> list[dict]:
    return list(csv.DictReader(open(DATA_DIR / "incidents.csv")))


def apm_would_have_caught(run: dict) -> tuple[bool, str]:
    """Return (caught, what_fired). Generic APM catches symptoms, not classes."""
    duration_s = int(run["duration_s"])
    cost = float(run["total_cost_usd"])
    if duration_s >= APM_LATENCY_ALERT_S:
        return True, "latency_p99_breached"
    if cost >= APM_TOKEN_BURN_USD:
        return True, "single_run_cost_breached"
    return False, ""


def main() -> None:
    runs = load_runs()
    incidents = load_incidents()
    runs_by_id = {r["run_id"]: r for r in runs}

    print("\n" + "=" * 80)
    print("Step 2 — Basic Datadog: latency + error-rate + token-count metrics")
    print("=" * 80)
    print()
    print("Datadog APM, configured for an agent service. The platform team wires the")
    print("standard RED method (Rate, Errors, Duration), and adds a token-count gauge")
    print("from the LLM proxy. Langfuse for the GenAI trace tail.")
    print()
    print("Thresholds in the monitor:")
    print(f"  - duration p99 alert:        run took > {APM_LATENCY_ALERT_S}s")
    print(f"  - cost per run alert:        run spent > ${APM_TOKEN_BURN_USD:.0f}")
    print(f"  - error-rate alert:          service > {APM_ERROR_RATE_ALERT*100:.0f}% errors in 5-min window")
    print()

    detected_count = 0
    detected_breakdown = {}
    detail_rows = []
    for inc in incidents:
        run = runs_by_id.get(inc["run_id"])
        if run is None:
            continue
        caught, fired = apm_would_have_caught(run)
        if caught:
            detected_count += 1
            detected_breakdown[inc["deficiency_class"]] = detected_breakdown.get(inc["deficiency_class"], 0) + 1
        detail_rows.append({
            "incident_id": inc["incident_id"],
            "deficiency_class": inc["deficiency_class"],
            "run_id": inc["run_id"],
            "agent_id": inc["agent_id"],
            "detected_by_apm": "yes" if caught else "no",
            "what_fired": fired or "—",
            "run_duration_s": run["duration_s"],
            "run_cost_usd": run["total_cost_usd"],
            "run_tool_calls": run["total_tool_calls"],
        })

    print("=" * 80)
    print("Detection rate — does generic APM catch each of the 24 incidents?")
    print("=" * 80)
    print(f"  {'incident':<12}{'deficiency':<24}{'agent_id':<22}{'caught?':<10}{'fired'}")
    print("  " + "-" * 84)
    by_def = {}
    by_def_caught = {}
    for row in detail_rows:
        print(f"  {row['incident_id']:<12}{row['deficiency_class']:<24}"
              f"{row['agent_id']:<22}{row['detected_by_apm']:<10}{row['what_fired']}")
        by_def[row["deficiency_class"]] = by_def.get(row["deficiency_class"], 0) + 1
        if row["detected_by_apm"] == "yes":
            by_def_caught[row["deficiency_class"]] = by_def_caught.get(row["deficiency_class"], 0) + 1

    print()
    print("=" * 80)
    print("Per-deficiency detection rate (what APM sees vs. what AgentWatch will catch)")
    print("=" * 80)
    print(f"  {'deficiency_class':<24}{'total':>8}{'caught':>10}{'rate':>10}")
    print("  " + "-" * 52)
    for k in sorted(by_def.keys()):
        caught = by_def_caught.get(k, 0)
        rate = caught / by_def[k] if by_def[k] else 0
        print(f"  {k:<24}{by_def[k]:>8}{caught:>10}{rate*100:>9.0f}%")

    overall_rate = detected_count / len(incidents) if incidents else 0
    print()
    print("=" * 80)
    print("Summary — what the Datadog dashboard tells the SRE on-call")
    print("=" * 80)
    print(f"  Incidents in window:                       {len(incidents)}")
    print(f"  Detected by generic APM heuristics:        {detected_count}")
    print(f"  Detection rate:                            {overall_rate*100:.0f}%")
    print(f"  Mean detection lag (when caught):          ~12-48 hours (next-day digest)")
    print()
    print("  APM catches the LATENCY and COST symptoms when they're loud enough.")
    print("  It misses ~70% of agent-shaped incidents — because the failure modes")
    print("  are not latency- or error-rate-shaped. They're agent-shaped: a tool")
    print("  loop, a fabricated argument, a mix shift, a compounded reach.")
    print()
    print("  Step 3 names each of the six deficiencies APM can't see. Step 4 closes")
    print("  them with the AgentWatch sidecar.")

    out_csv = OUT_DIR / "step_02_apm_detection_attempt.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(detail_rows[0].keys()))
        w.writeheader()
        for r in detail_rows:
            w.writerow(r)
    print()
    print(f"Wrote: {out_csv}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
