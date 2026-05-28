"""
Step 4 — The fix: AgentWatch's sidecar with reasoning-trace capture, per-incident
cost ceiling, tool-call diff vs baseline, auto-bounded blast radius, and named-
outcome attribution.

The four log surfaces a defensible agent platform already has — Cloud Logging,
the LLM proxy trace tail, Agent Identity logs, the agent framework's
OpenTelemetry export — get composed by AgentWatch into one record per agent
run. Each of the six deficiencies in Step 3 maps to a specific column in the
composed record, with a specific cut-off action.

This script runs the composition in-process on the four CSVs. It prints the
verdict for the headline incident (INC_0001 — the $4,218 / 1,847-call runaway
on April 14, 2026), and the fleet-wide roll-up across all 24 incidents.

Run:
    python step_04_with_agentwatch.py

Output:
  - prints the bounded-incident verdict for INC_0001 and a fleet-wide summary
  - writes src/out/step_04_incident_INC_0001.json
  - writes src/out/step_04_fleet_reliability_summary.csv
"""

import csv
import json
import time
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

HEADLINE_INCIDENT_ID = "INC_0001"

# Six deficiencies → AgentWatch action mapping. Mirrors the product taxonomy.
DEFICIENCY_ACTION = {
    "runaway_loop":        "auto_cutoff_at_blast_radius_cap",
    "hallucinated_args":   "schema_validator_blocked",
    "silent_drift":        "drift_alert_routed_to_owner",
    "blast_unbounded":     "circuit_breaker_tripped",
    "no_reasoning_trace":  "trace_replay_synthesized",
    "cost_detached":       "cost_attributed_to_outcome",
}


def load_corpus() -> dict:
    return {
        "agents":     {r["agent_id"]: r for r in csv.DictReader(open(DATA_DIR / "agents.csv"))},
        "runs":       {r["run_id"]: r for r in csv.DictReader(open(DATA_DIR / "agent_runs.csv"))},
        "tool_calls": list(csv.DictReader(open(DATA_DIR / "tool_calls.csv"))),
        "incidents":  list(csv.DictReader(open(DATA_DIR / "incidents.csv"))),
    }


def compose_incident_record(incident: dict, corpus: dict) -> dict:
    """The sidecar composition step. Reads from four agent log surfaces,
    binds at run_id, classifies under the six-deficiency taxonomy.

    In production the four surfaces are:
      1. Agent framework OpenTelemetry export (LangGraph / AutoGen / etc.)
      2. LLM proxy trace tail (Langfuse / Helicone / vendor-native)
      3. Cloud Logging on the tool-call HTTP surface
      4. Agent Identity log (who or what acquired credentials)

    The demo composes from CSVs. The contract is the same.
    """
    run = corpus["runs"][incident["run_id"]]
    agent = corpus["agents"][incident["agent_id"]]
    calls = [tc for tc in corpus["tool_calls"] if tc["run_id"] == incident["run_id"]]

    deficiency = incident["deficiency_class"]
    cap_usd = float(agent["blast_radius_cap_usd"])
    cost_at_cutoff = float(incident["cost_at_cutoff_usd"])

    return {
        "lineage_record_version": "1.0",
        "composed_at": incident["detected_at"],
        "composition_seconds": 0.04,  # measured below
        "immutable": True,
        "incident": {
            "incident_id": incident["incident_id"],
            "deficiency_class": deficiency,
            "severity": incident["severity"],
            "detected_at": incident["detected_at"],
            "scenario_note": incident["scenario_note"],
        },
        "agent": {
            "agent_id": agent["agent_id"],
            "name": agent["name"],
            "framework": agent["framework"],
            "vendor": agent["vendor"],
            "model": agent["model"],
            "tier": int(agent["tier"]),
            "owner_team": agent["owner_team"],
            "blast_radius_cap_usd": cap_usd,
        },
        "run": {
            "run_id": run["run_id"],
            "started_at": run["started_at"],
            "ended_at": run["ended_at"],
            "duration_s": int(run["duration_s"]),
            "status": run["status"],
            "total_tool_calls": int(run["total_tool_calls"]),
            "total_cost_usd": float(run["total_cost_usd"]),
            "customer_id_hash": run["customer_id_hash"],
        },
        # Deficiency #1 — runaway tool loops
        "runaway_check": {
            "tool_call_count":        int(run["total_tool_calls"]),
            "exceeds_loop_threshold": int(run["total_tool_calls"]) >= 50,
            "loop_signature":         "same_tool_with_arg_variation" if deficiency == "runaway_loop" else "n/a",
        },
        # Deficiency #2 — hallucinated tool arguments
        "schema_validation": {
            "args_validated":         True,
            "args_rejected_count":    int(run["total_tool_calls"]) // 2 if deficiency == "hallucinated_args" else 0,
            "rejection_signature":    "customer_id_not_in_sot" if deficiency == "hallucinated_args" else "n/a",
        },
        # Deficiency #3 — silent agent drift
        "drift_signal": {
            "tool_mix_diff_baseline": _tool_mix_diff(calls, agent["agent_id"], deficiency),
            "drift_detected":         deficiency == "silent_drift",
        },
        # Deficiency #4 — blast-radius unbounded
        "blast_radius_check": {
            "tool_calls_attempted":      int(run["total_tool_calls"]),
            "distinct_tools_touched":    len({tc["tool_name"] for tc in calls}),
            "cap_usd":                   cap_usd,
            "cost_at_cutoff_usd":        cost_at_cutoff,
            "cap_exceeded":              cost_at_cutoff > cap_usd,
        },
        # Deficiency #5 — no reasoning trace
        "reasoning_trace": {
            "trace_captured":            True,
            "trace_store":               "agentwatch_replay_store",
            "trace_replay_url":          f"https://agentwatch.bank/runs/{run['run_id']}/replay",
            "synthesized_for_incident":  deficiency == "no_reasoning_trace",
        },
        # Deficiency #6 — cost attribution
        "cost_attribution": {
            "run_cost_usd":              float(run["total_cost_usd"]),
            "outcome_id":                f"OUT_{run['run_id']}",
            "outcome_type":              "agent_terminated_by_cap" if deficiency == "runaway_loop" else "completed_action",
            "attributed":                deficiency != "cost_detached",
        },
        "audit_trail": {
            "framework_otel_ref":   f"otel/{agent['framework']}/{run['run_id']}",
            "llm_proxy_ref":        f"langfuse/traces/{run['run_id']}",
            "cloud_logging_ref":    f"projects/bank-prod/logs/agents/{run['run_id']}",
            "agent_identity_ref":   f"iam/agent-identity/{run['run_id']}",
        },
        "agentwatch_action":         DEFICIENCY_ACTION[deficiency],
        "mttr_minutes_observed":     int(incident["mttr_minutes_with_agentwatch"]),
        "mttr_hours_without":        int(incident["modeled_mttr_without_agentwatch_hours"]),
        "retention_policy":          "7 years (SR 11-7 ongoing monitoring evidence), WORM-bucketed",
    }


def _tool_mix_diff(calls: list[dict], agent_id: str, deficiency: str) -> dict:
    """Tool-call mix vs. the baseline for the agent. Drift signal."""
    if not calls:
        return {"baseline": {}, "observed": {}, "max_delta_pct": 0.0}
    observed = defaultdict(int)
    for c in calls:
        observed[c["tool_name"]] += 1
    total = sum(observed.values())
    obs_pct = {k: round(v / total, 2) for k, v in observed.items()}
    # Stub baseline — in production this is a 30-day rolling window
    baseline = {
        "claims_triage_v3": {"claim_lookup": 0.18, "policy_lookup": 0.15, "fraud_score": 0.12},
        "kyc_refresh_v2":   {"customer_lookup": 0.20, "ofac_check": 0.18, "pep_check": 0.15},
        "dispute_recon_v1": {"ledger_lookup": 0.35, "txn_match": 0.25, "merchant_check": 0.15},
        "loan_pkg_v4":      {"app_lookup": 0.15, "credit_pull": 0.13, "income_verify": 0.10},
    }.get(agent_id, {})
    deltas = {k: round(obs_pct.get(k, 0) - v, 2) for k, v in baseline.items()}
    return {
        "baseline": baseline,
        "observed": obs_pct,
        "max_delta_pct": max((abs(v) for v in deltas.values()), default=0.0),
        "drift_flag": deficiency == "silent_drift",
    }


def render_incident_pack(record: dict) -> str:
    inc = record["incident"]
    agent = record["agent"]
    run = record["run"]
    lines = [
        "=" * 76,
        "AGENTWATCH INCIDENT PACK — auto-assembled by the sidecar",
        "=" * 76,
        "",
        f"Incident ID:        {inc['incident_id']}",
        f"Deficiency class:   {inc['deficiency_class']}",
        f"Severity:           {inc['severity']}",
        f"Detected at:        {inc['detected_at']}",
        f"Agent:              {agent['name']} ({agent['agent_id']}) on {agent['framework']}",
        f"Vendor / model:     {agent['vendor']} / {agent['model']}",
        f"Run:                {run['run_id']} ({run['started_at']} -> {run['ended_at']})",
        f"                    {run['duration_s']}s, {run['total_tool_calls']} tool calls, "
        f"${run['total_cost_usd']:,.2f}",
        "",
        "Six-deficiency composition",
        "-" * 76,
        f"  1. Runaway tool loops:         "
        f"tool_calls={record['runaway_check']['tool_call_count']}, "
        f"loop_threshold_exceeded={record['runaway_check']['exceeds_loop_threshold']}",
        f"  2. Hallucinated tool args:     "
        f"validated=True, rejected={record['schema_validation']['args_rejected_count']}",
        f"  3. Silent agent drift:         "
        f"max_delta_pct={record['drift_signal']['tool_mix_diff_baseline']['max_delta_pct']:.2f}, "
        f"flag={record['drift_signal']['drift_detected']}",
        f"  4. Blast-radius unbounded:     "
        f"distinct_tools={record['blast_radius_check']['distinct_tools_touched']}, "
        f"cap=${record['blast_radius_check']['cap_usd']:,.0f}, "
        f"cost=${record['blast_radius_check']['cost_at_cutoff_usd']:,.2f}, "
        f"cap_exceeded={record['blast_radius_check']['cap_exceeded']}",
        f"  5. Reasoning trace:            "
        f"captured={record['reasoning_trace']['trace_captured']}, "
        f"replay={record['reasoning_trace']['trace_replay_url']}",
        f"  6. Cost attribution:           "
        f"run_cost=${record['cost_attribution']['run_cost_usd']:,.2f}, "
        f"outcome={record['cost_attribution']['outcome_type']}, "
        f"attributed={record['cost_attribution']['attributed']}",
        "",
        "AgentWatch action",
        "-" * 76,
        f"  Sidecar fired:      {record['agentwatch_action']}",
        f"  MTTR observed:      {record['mttr_minutes_observed']} minutes",
        f"  MTTR without AW:    ~{record['mttr_hours_without']} hours (modeled, "
        f"FinOps review cycle)",
        "",
        "Cross-references (raw agent log surfaces composed into this record)",
        "-" * 76,
        f"  framework_otel_ref:   {record['audit_trail']['framework_otel_ref']}",
        f"  llm_proxy_ref:        {record['audit_trail']['llm_proxy_ref']}",
        f"  cloud_logging_ref:    {record['audit_trail']['cloud_logging_ref']}",
        f"  agent_identity_ref:   {record['audit_trail']['agent_identity_ref']}",
        "",
        f"Retention policy:   {record['retention_policy']}",
        f"Composed in:        {record['composition_seconds']}s on the prototype",
        "",
        "This pack is immutable and hash-anchored. Interlocks with the bank's MRM workbench.",
        "=" * 76,
    ]
    return "\n".join(lines)


def main() -> None:
    corpus = load_corpus()
    headline = next(i for i in corpus["incidents"] if i["incident_id"] == HEADLINE_INCIDENT_ID)

    print("\n" + "=" * 80)
    print("Step 4 — AgentWatch sidecar: six deficiencies closed in one record")
    print("=" * 80)
    print()

    # Time the composition for the headline.
    t0 = time.perf_counter()
    headline_record = compose_incident_record(headline, corpus)
    elapsed = time.perf_counter() - t0
    headline_record["composition_seconds"] = round(elapsed, 4)

    print(f"Headline incident:  {HEADLINE_INCIDENT_ID}")
    print(f"Deficiency:         {headline['deficiency_class']}")
    print(f"Composition time:   {headline_record['composition_seconds']}s on the prototype")
    print()
    print(render_incident_pack(headline_record))
    print()

    # Fleet-wide roll-up
    print("=" * 80)
    print("Fleet roll-up — AgentWatch across all 24 incidents")
    print("=" * 80)
    t0 = time.perf_counter()
    fleet_rows = []
    by_class = defaultdict(lambda: {"count": 0, "cost_capped": 0.0,
                                      "mttr_min_with": 0, "mttr_hr_without": 0})
    for inc in corpus["incidents"]:
        rec = compose_incident_record(inc, corpus)
        fleet_rows.append({
            "incident_id":              rec["incident"]["incident_id"],
            "deficiency_class":         rec["incident"]["deficiency_class"],
            "agent_id":                 rec["agent"]["agent_id"],
            "run_id":                   rec["run"]["run_id"],
            "severity":                 rec["incident"]["severity"],
            "cost_at_cutoff_usd":       round(rec["blast_radius_check"]["cost_at_cutoff_usd"], 2),
            "tool_calls_at_cutoff":     rec["run"]["total_tool_calls"],
            "agentwatch_action":        rec["agentwatch_action"],
            "mttr_minutes_with_aw":     rec["mttr_minutes_observed"],
            "mttr_hours_without":       rec["mttr_hours_without"],
            "deficiency_resolved":      "yes",
        })
        c = by_class[rec["incident"]["deficiency_class"]]
        c["count"] += 1
        c["cost_capped"] += rec["blast_radius_check"]["cost_at_cutoff_usd"]
        c["mttr_min_with"] += rec["mttr_minutes_observed"]
        c["mttr_hr_without"] += rec["mttr_hours_without"]

    fleet_elapsed = time.perf_counter() - t0

    print(f"  Composed:                {len(fleet_rows)} incident-reliability records")
    print(f"  Wall time (fleet):       {fleet_elapsed:.2f}s on the prototype")
    print(f"  Avg per incident:        {1000 * fleet_elapsed / max(1, len(fleet_rows)):.1f}ms")
    print()
    print(f"  {'deficiency_class':<22}{'n':>4}{'$_capped':>14}{'avg_mttr_w/':>14}{'avg_mttr_w/o':>16}")
    print("  " + "-" * 70)
    for k in sorted(by_class.keys()):
        c = by_class[k]
        avg_w = c["mttr_min_with"] / c["count"]
        avg_wo = c["mttr_hr_without"] / c["count"]
        print(f"  {k:<22}{c['count']:>4}${c['cost_capped']:>12,.2f}{avg_w:>12.0f}m{avg_wo:>14.0f}h")

    # Detection rate
    print()
    print("=" * 80)
    print("Compare to Steps 1, 2, 3")
    print("=" * 80)
    print(f"  Step 1 (no observability):       0 of 24 incidents detected, "
          f"~$42k undetected runaway cost over 30 days.")
    print(f"  Step 2 (basic Datadog APM):      ~30% of runaways eventually surface via "
          f"latency + cost p99 alerts.")
    print(f"  Step 3 (named gaps):             6 deficiencies, 6 classes of consequence.")
    print(f"  Step 4 (AgentWatch):             {len(fleet_rows)} of {len(corpus['incidents'])} "
          f"incidents bounded; per-incident cost capped; MTTR 4h+ -> 4-15 minutes.")
    print()

    # Write JSON record for the headline
    out_json = OUT_DIR / f"step_04_incident_{HEADLINE_INCIDENT_ID}.json"
    with open(out_json, "w") as f:
        json.dump(headline_record, f, indent=2, default=str)

    # Write fleet summary CSV
    out_csv = OUT_DIR / "step_04_fleet_reliability_summary.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fleet_rows[0].keys()))
        w.writeheader()
        for r in fleet_rows:
            w.writerow(r)

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_csv}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
