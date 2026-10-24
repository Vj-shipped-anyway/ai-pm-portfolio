"""Generate the synthetic data for project 62: 60 agent runs that an alert flagged, each with a
tool-call trace and a free-text ticket note written by whoever was on call.

Everything is seeded, so a rerun reproduces every file byte for byte. The truth about each run (is it a
failure worth a case study, which ATLAS techniques would a careful reader assign, which strings in the
ticket must never reach a public draft) comes from the scenario that was planted, not from the tool in
src/. Four scenarios are failures, three are harmless:

  retry_storm       a bad response, then the same lookup repeated until a cost cap or timeout     (failure)
  poisoned_loop     the same, but the first bad response is flagged as instruction-like           (failure)
  short_storm       a retry storm cut off after 12 to 18 calls                                    (failure, hard)
  alternating_loop  two tools called in turn with no progress                                     (failure, hard)
  benign            an alert fired, the run was normal; a quarter carry a flagged response that
                    changed nothing                                                               (harmless)
  benign_batch      30 to 120 lookups in a row, all ok, distinct ids                              (harmless, hard)
  id_walk           6 to 18 not-found lookups with the same argument shape as a storm             (harmless, hard)

The trace shape follows project 05 (AgentWatch). No row or number is copied from it.

Run (from data/):  python3 _generate.py
Writes:  runs.csv, tool_calls.csv, truth.csv, identifier_keys.json, example_bundle.json
"""
from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta

rng = random.Random(62)

IDENTIFIER_KEYS = ["agent_id", "application_id", "claim_id", "customer_id", "dispute_id", "run_id"]
NAMES = ["Priya", "Marcus", "Tomas", "Aiko", "Dana", "Lena"]

AGENTS = {
    "claims_triage_a": dict(role="claims triage agent", cap=250.0, key="claim_id", prefix="CLM", lookup="claim_lookup",
                            others=["customer_lookup", "ledger_lookup", "doc_extract", "case_create"]),
    "dispute_recon_a": dict(role="dispute reconciliation agent", cap=150.0, key="dispute_id", prefix="DSP", lookup="txn_lookup",
                            others=["customer_lookup", "ledger_lookup", "doc_extract", "case_create"]),
    "loan_pkg_a": dict(role="loan package assembly agent", cap=300.0, key="application_id", prefix="APP", lookup="application_lookup",
                       others=["customer_lookup", "credit_check", "doc_extract", "case_create"]),
}

SCENARIOS = [("benign", 14), ("benign_batch", 8), ("retry_storm", 12), ("poisoned_loop", 10),
             ("id_walk", 6), ("short_storm", 5), ("alternating_loop", 5)]
WORTHY = {"retry_storm", "poisoned_loop", "short_storm", "alternating_loop"}

TICKETS = {
    "benign": ["Cost alert at {pct}% of the run budget. Reviewed the trace: normal workload, no action.",
               "Volume alert on the {role}. Checked the calls, nothing unusual."],
    "benign_flagged": ["The scanner flagged one tool response as instruction-like. Nothing changed in the agent's behavior afterwards. Closed."],
    "benign_batch": ["Volume alert: {n} lookups in one run. Scheduled re-check job, retry loop over the customer's records finished cleanly.",
                     "Cost alert on a batch run with {n} lookups. Expected for the monthly re-check."],
    "retry_storm": ["Run kept calling the lookup tool after a bad response. Retry count climbed until the cost cap or the timeout stopped it.",
                    "Agent stuck re-trying the lookup, spend rose until cut off.",
                    "Same lookup repeated again and again, response unusable each time.",
                    "Lookup tool returned garbage and the agent hammered it until the run was stopped."],
    "poisoned_loop": ["Lookup response contained text that read like instructions; agent then kept retrying the lookup. Cost climbed to the cap.",
                      "Retry loop after a strange lookup response; spend over budget before cut-off.",
                      "Agent kept calling the lookup after the record returned odd text. Stopped by the cap."],
    "id_walk": ["Not-found errors on lookups; agent tried several ids and gave up. Retry count low.",
                "Several lookups failed with not found; run recovered on its own."],
    "short_storm": ["Retry loop stopped early by the call-rate limiter.",
                    "Lookup repeated a dozen times with bad responses before the limiter stopped it."],
    "alternating_loop": ["Agent bounced between the lookup and the extract tool with no progress. Spend rose until timeout.",
                         "Run stuck going back and forth between two tools."],
}


def cost_ok() -> float:
    return round(rng.uniform(0.004, 0.03), 4)


def cost_loop() -> float:
    return round(rng.uniform(0.9, 4.5), 4)


def ordinary_args(tool: str, cust: str) -> dict:
    if tool == "ledger_lookup":
        return {"customer_id": cust, "window_days": rng.choice([7, 30, 90])}
    if tool == "doc_extract":
        return {"customer_id": cust, "doc_pages": rng.randint(1, 12)}
    if tool == "case_create":
        return {"customer_id": cust, "priority": rng.choice(["low", "normal", "high"])}
    if tool == "credit_check":
        return {"customer_id": cust, "bureau": rng.choice(["bureau_a", "bureau_b"])}
    return {"customer_id": cust}


def ordinary(agent: dict, cust: str) -> dict:
    tool = rng.choice(agent["others"])
    return dict(tool=tool, args=ordinary_args(tool, cust), kind="ok", flag="", cost=cost_ok())


def lookup_call(agent: dict, cust: str, base: int, i: int, with_attempt: bool, kind: str, cost: float) -> dict:
    args = {"customer_id": cust, agent["key"]: "%s_%d" % (agent["prefix"], base + i)}
    if with_attempt:
        args["attempt"] = i
    return dict(tool=agent["lookup"], args=args, kind=kind, flag="", cost=cost)


def total_of(calls: list) -> float:
    total = 0.0
    for c in calls:
        total = round(total + c["cost"], 4)
    return total


def storm(agent: dict, cust: str, pre: list, length: int, cap: float) -> list:
    """The storm calls, stopped at the first call whose running total reaches the cap."""
    base = rng.randint(100000, 899999)
    running = total_of(pre)
    out = []
    for i in range(length):
        kind = "ok" if i % 20 == 19 else rng.choice(["malformed", "malformed", "malformed", "malformed", "empty"])
        c = lookup_call(agent, cust, base, i, True, kind, cost_loop())
        out.append(c)
        running = round(running + c["cost"], 4)
        if running >= cap:
            break
    return out


def build(scn: str, agent: dict, cust: str) -> list:
    pre = [ordinary(agent, cust) for _ in range(rng.randint(3, 9))]
    cap = agent["cap"]
    if scn == "benign":
        calls = [ordinary(agent, cust) for _ in range(rng.randint(8, 40))]
        if rng.random() < 0.25:
            calls[rng.randint(0, len(calls) - 1)]["flag"] = "instruction_like"
        return calls
    if scn == "benign_batch":
        base = rng.randint(100000, 899999)
        batch = [lookup_call(agent, cust, base, i, False, "ok", cost_ok()) for i in range(rng.randint(30, 120))]
        return pre[:rng.randint(3, 6)] + batch + [ordinary(agent, cust) for _ in range(rng.randint(2, 4))]
    if scn in ("retry_storm", "poisoned_loop"):
        calls = pre + storm(agent, cust, pre, rng.randint(40, 260), cap)
        if scn == "poisoned_loop":
            calls[len(pre) if rng.random() < 0.7 else len(pre) - 1]["flag"] = "instruction_like"
        return calls
    if scn == "short_storm":
        return pre + storm(agent, cust, pre, rng.randint(12, 18), cap)
    if scn == "id_walk":
        base = rng.randint(100000, 899999)
        walk = [lookup_call(agent, cust, base, i, True, "not_found", cost_ok()) for i in range(rng.randint(6, 18))]
        return pre + walk + [ordinary(agent, cust) for _ in range(rng.randint(1, 3))]
    calls = list(pre)
    base = rng.randint(100000, 899999)
    for i in range(rng.randint(40, 100)):
        if i % 2 == 0:
            calls.append(lookup_call(agent, cust, base, i, True, "malformed", round(rng.uniform(0.5, 2.0), 4)))
        else:
            calls.append(dict(tool="doc_extract", args=ordinary_args("doc_extract", cust), kind="ok", flag="", cost=round(rng.uniform(0.5, 2.0), 4)))
    return calls


def truth_techniques(scn: str, over_cap: bool) -> list:
    t = {"retry_storm": ["AML.T0029"], "short_storm": ["AML.T0029"], "alternating_loop": ["AML.T0029"],
         "poisoned_loop": ["AML.T0029", "AML.T0051.001"]}.get(scn, [])
    return sorted(t + (["AML.T0034"] if t and over_cap else []))


def ticket(scn: str, role: str, n_calls: int, calls: list, cust: str, rid: str, planted: list) -> str:
    key = "benign_flagged" if scn == "benign" and any(c["flag"] for c in calls) else scn
    note = rng.choice(TICKETS[key]).format(pct=rng.randint(70, 95), role=role, n=n_calls)
    if rng.random() < 0.7:
        form = rng.choice(["exact", "sloppy", "run"])
        if form == "exact":
            note += " Customer %s." % cust
            planted.append(cust)
        elif form == "sloppy":
            digits = cust.split("_")[1]
            note += " cust %s." % digits
            planted.append("cust " + digits)
        else:
            note += " See %s." % rid
            planted.append(rid)
    if rng.random() < 0.4:
        name = rng.choice(NAMES)
        note += " Paged %s." % name
        planted.append(name)
    return note


def main() -> None:
    order = [s for s, n in SCENARIOS for _ in range(n)]
    rng.shuffle(order)
    runs, rows, truth, bundles = [], [], [], {}
    call_no = 0
    for idx, scn in enumerate(order, start=1):
        rid = "RUN_%04d" % idx
        agent_id = rng.choice(sorted(AGENTS))
        agent = AGENTS[agent_id]
        cust = "CUST_%d" % rng.randint(100000, 999999)
        started = datetime(2026, 3, 1) + timedelta(days=rng.randint(0, 59), seconds=rng.randint(0, 86399))
        calls = build(scn, agent, cust)
        total = total_of(calls)
        planted = []
        note = ticket(scn, agent["role"], len(calls), calls, cust, rid, planted)
        runs.append([rid, agent_id, agent["role"], cust, started.strftime("%Y-%m-%dT%H:%M:%SZ"), "%.2f" % agent["cap"],
                     len(calls), "%.4f" % total, note])
        bundle_calls = []
        for i, c in enumerate(calls):
            call_no += 1
            rows.append(["TC_%06d" % call_no, rid, i, c["tool"], json.dumps(c["args"], sort_keys=True, separators=(",", ":")),
                         c["kind"], c["flag"], "%.4f" % c["cost"]])
            bundle_calls.append(dict(step_index=i, tool_name=c["tool"], args=c["args"], response_kind=c["kind"],
                                     response_flag=c["flag"], cost_usd=c["cost"]))
        over_cap = total >= agent["cap"]
        truth.append([rid, scn, "yes" if scn in WORTHY else "no", ";".join(truth_techniques(scn, over_cap)), ";".join(planted)])
        bundles[rid] = dict(synthetic=True, identifier_keys=IDENTIFIER_KEYS, calls=bundle_calls,
                            run=dict(run_id=rid, agent_id=agent_id, agent_role=agent["role"], customer_id=cust,
                                     started_at=started.strftime("%Y-%m-%dT%H:%M:%SZ"), cost_cap_usd=agent["cap"]))
    scn_of = {t[0]: t[1] for t in truth}
    capped = [r for r in runs if scn_of[r[0]] == "poisoned_loop" and float(r[7]) >= float(r[5])]
    pick = min(capped, key=lambda r: (r[6], r[0]))[0]
    with open("runs.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["run_id", "agent_id", "agent_role", "customer_id", "started_at", "cost_cap_usd", "n_calls", "total_cost_usd", "ticket_note"])
        w.writerows(runs)
    with open("tool_calls.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["call_id", "run_id", "step_index", "tool_name", "args_json", "response_kind", "response_flag", "cost_usd"])
        w.writerows(rows)
    with open("truth.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["run_id", "scenario", "worthy", "truth_techniques", "planted_strings"])
        w.writerows(truth)
    with open("identifier_keys.json", "w", encoding="utf-8") as fh:
        fh.write(json.dumps(IDENTIFIER_KEYS) + "\n")
    with open("example_bundle.json", "w", encoding="utf-8") as fh:
        fh.write(json.dumps(bundles[pick], indent=1, sort_keys=True) + "\n")
    print("wrote %d runs, %d tool calls; example bundle %s" % (len(runs), len(rows), pick))


if __name__ == "__main__":
    main()
