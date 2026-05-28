"""
Step 3 — Six deficiencies, each illustrated on real incidents from the data.

This script takes the 24 detected incidents and walks the six named deficiencies
one by one. For each, it shows the agent failure mode in plain English, the
real-feeling consequence, and what generic APM returned today.

The point: each deficiency is a specific, named class — not a vague "we need
better agent observability" wish. Step 4 closes all six with the AgentWatch
sidecar.

Run:
    python step_03_deficiencies_exposed.py

Output:
  - prints the six deficiency classes with example incidents from the data
  - writes src/out/step_03_deficiency_examples.csv
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

# Six deficiencies — the product's intellectual property. Do not change.
DEFICIENCIES = [
    {
        "n": 1,
        "key": "runaway_loop",
        "label": "Runaway tool loops",
        "description": (
            "Agent gets stuck calling the same tool with slight argument variations, "
            "with no terminating condition. The first malformed response is taken as "
            "'try again'; 1,800 retries later the line item lands on the FinOps bill."
        ),
        "apm_returns": (
            "Eventually fires on the latency p99 alert if the run lasts > 10 minutes. "
            "By then, $4,000 of inference has already burned. The on-call gets a generic "
            "'service slow' page with no agent context."
        ),
        "consequence": (
            "Per-incident cost $5-50k for runaway runs at Tier-1 BFSI scale. Customer-"
            "facing surfaces still get the bad response; the on-call has no replay UI to "
            "diagnose what the agent was trying to do. Detection rate without AgentWatch: "
            "~30% of runaways eventually surface."
        ),
        "agentwatch_action": "auto_cutoff_at_blast_radius_cap (configurable per-agent dollar cap)",
    },
    {
        "n": 2,
        "key": "hallucinated_args",
        "label": "Hallucinated tool arguments",
        "description": (
            "Agent invents a customer_id, account_number, or claim_id that doesn't exist "
            "in the system-of-truth. The tool returns a generic NOT_FOUND error. The agent "
            "interprets it as 'I should try a different ID' — and fabricates another one."
        ),
        "apm_returns": (
            "Sees the 404 / NOT_FOUND error count rising. Generic APM doesn't know to "
            "correlate the error pattern to the tool-call arg payload. The dashboard "
            "shows 'higher error rate, investigate' — and no one investigates."
        ),
        "consequence": (
            "PII leak risk if the fabricated ID happens to belong to another customer. "
            "Class-action exposure under GLBA. Modeled cost per leak: $25-100k in CFPB "
            "settlements + remediation, before any reputational damage."
        ),
        "agentwatch_action": "schema_validator_blocked (every tool-call arg validated against SOT before fire)",
    },
    {
        "n": 3,
        "key": "silent_drift",
        "label": "Silent agent drift",
        "description": (
            "Agent's tool-call mix shifts over weeks. A KYC agent that was 60% retrieval "
            "and 40% case-creation last quarter is now 90% retrieval and 10% case-creation. "
            "Nobody flagged the shift; it signals model regression on the planning step."
        ),
        "apm_returns": (
            "Sees nothing. Latency and error rate are within bounds. Token usage is up "
            "marginally — within noise. The agent appears 'healthy' under generic APM until "
            "the next model-risk attestation cycle, three months from now."
        ),
        "consequence": (
            "Quality-of-decision degrades silently. The bank's MRM cycle is annual; by the "
            "time the drift surfaces, the agent has scored ~50k customer interactions on a "
            "regressed planner. Reattestation is mandatory under SR 11-7."
        ),
        "agentwatch_action": "drift_alert_routed_to_owner (tool-call mix diff against baseline)",
    },
    {
        "n": 4,
        "key": "blast_unbounded",
        "label": "Blast-radius unbounded",
        "description": (
            "Agent has authority to call N tools — credit pull, asset verification, rate "
            "lock, comms draft. A malformed plan can compound across all of them. Without "
            "a per-incident cap, one bad reasoning step fans out to 11 tool calls, each "
            "with downstream side-effects."
        ),
        "apm_returns": (
            "Sees that the agent's run touched 11 tools. There is no policy that says "
            "this is bad. The downstream side-effects (e.g., a rate-lock with a wrong "
            "rate) materialize hours or days later."
        ),
        "consequence": (
            "Operational risk: incorrect rate-locks, mis-drafted comms, premature "
            "approval routing. Modeled exposure: a single blast-unbounded run can "
            "cost $5-30k in rework and customer remediation."
        ),
        "agentwatch_action": "circuit_breaker_tripped (per-incident tool-call cap enforced)",
    },
    {
        "n": 5,
        "key": "no_reasoning_trace",
        "label": "No reasoning trace capture",
        "description": (
            "When the agent fails, there is no record of WHY the agent chose THIS tool, "
            "THIS argument, THIS sequence. The on-call sees the side-effects, not the "
            "plan. The line-1 owner cannot reproduce the failure. The line-2 validator "
            "cannot certify the next model."
        ),
        "apm_returns": (
            "Has the HTTP-level service trace. The agent's chain-of-thought waterfall — "
            "the actual reasoning — lives in the LLM proxy's transient buffer and TTLs "
            "out after 7-15 days. For an incident reviewed at week 4, the trace is gone."
        ),
        "consequence": (
            "The single most underrated trail in regulated AI. Without it, the bank "
            "cannot do effective challenge (SR 11-7), cannot meet the EU AI Act Article 14 "
            "human-oversight requirement, and cannot defend a customer complaint. The "
            "agent gets pulled from production until the trace pipeline is rebuilt."
        ),
        "agentwatch_action": "trace_replay_synthesized (long-term trace store, queryable by run_id)",
    },
    {
        "n": 6,
        "key": "cost_detached",
        "label": "Cost telemetry detached from outcomes",
        "description": (
            "The bank knows total agent spend (the FinOps dashboard). It cannot attribute "
            "that spend to specific customer outcomes or business value. A $0.42 average "
            "agent run gets approved at FinOps review — but the bank has no idea whether "
            "the $0.42 produced a closed claim, a denied loan, or noise."
        ),
        "apm_returns": (
            "Aggregate dollars per service. Aggregate token count. No attribution to the "
            "downstream business outcome. The conversation at the planning meeting is "
            "'agent spend is up 30%' with no answer to 'is the spend producing value?'"
        ),
        "consequence": (
            "FinOps cannot prioritize cost optimization without outcome-attribution. "
            "Model owners cannot defend their agent's ROI. The CRO's portfolio review "
            "shows total dollars; no view of cost-per-resolved-customer-action."
        ),
        "agentwatch_action": "cost_attributed_to_outcome (per-run cost joined to downstream business event)",
    },
]


def main() -> None:
    incidents = list(csv.DictReader(open(DATA_DIR / "incidents.csv")))

    # Group incidents by deficiency
    by_def = defaultdict(list)
    for inc in incidents:
        by_def[inc["deficiency_class"]].append(inc)

    print("\n" + "=" * 80)
    print("Step 3 — Six named agent deficiencies, each grounded in real incidents")
    print("=" * 80)
    print()
    print(f"Total incidents in the synthetic 30-day window: {len(incidents)}")
    print(f"Distribution across the six classes:")
    for d in DEFICIENCIES:
        n = len(by_def.get(d["key"], []))
        print(f"  {d['n']}. {d['label']:<32} {n} incident(s)")
    print()

    for d in DEFICIENCIES:
        examples = by_def.get(d["key"], [])
        print("-" * 80)
        print(f"  Deficiency #{d['n']}: {d['label']}")
        print("-" * 80)
        print(f"  DESCRIPTION")
        print(f"    {d['description']}")
        print()
        print(f"  WHAT GENERIC APM RETURNS")
        print(f"    {d['apm_returns']}")
        print()
        print(f"  CONSEQUENCE")
        print(f"    {d['consequence']}")
        print()
        print(f"  AGENTWATCH ACTION (Step 4)")
        print(f"    {d['agentwatch_action']}")
        print()
        if examples:
            print(f"  EXAMPLE INCIDENTS FROM THE DATA ({len(examples)} total)")
            for ex in examples[:2]:
                print(f"    - {ex['incident_id']} on {ex['run_id']} "
                      f"({ex['agent_id']}, cost ${float(ex['cost_at_cutoff_usd']):,.2f}, "
                      f"{ex['tool_calls_at_cutoff']} tool calls)")
        print()

    # Write per-deficiency aggregate stats
    out_csv = OUT_DIR / "step_03_deficiency_examples.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n", "deficiency_class", "label", "incident_count",
                    "description", "apm_returns", "consequence", "agentwatch_action"])
        for d in DEFICIENCIES:
            n = len(by_def.get(d["key"], []))
            w.writerow([d["n"], d["key"], d["label"], n,
                        d["description"], d["apm_returns"], d["consequence"],
                        d["agentwatch_action"]])

    print("=" * 80)
    print("Summary — six classes, six exam questions APM cannot answer")
    print("=" * 80)
    print(f"  Total deficiencies named:       {len(DEFICIENCIES)}")
    print(f"  Caught by generic APM today:    ~30% of runaways only (Step 2)")
    print(f"  Closed in Step 4 (AgentWatch):  all 6 by sidecar composition")
    print()
    print(f"Wrote: {out_csv}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
