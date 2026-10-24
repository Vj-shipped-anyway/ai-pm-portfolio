"""Step 4 - The fix: the usage-versus-grant diff in scopekeeper.py.

For every grant: was a scope it reaches called in the log? No call -> propose removal. A group grant
called on some members only -> propose narrowing to those members. A call with no agent tag is
credited to every agent on its service account that holds the scope, so a grant in use is never
proposed for removal. The proposal is then replayed against the same log.

The command-line tool (`scopekeeper diff grants.csv calls.csv`) runs exactly this code.

KNOWN LIMITS, left in on purpose and printed below:
  - a scope used once a quarter shows no call in a 90-day log, so it is proposed for removal
  - an unneeded grant stays when a sibling on the same service account calls the scope untagged
  - an unneeded grant stays when something called it once or twice (a smoke test)

Run (from src/):  python3 step_04_with_diff.py
Output: a report, plus out/step_04_grants.csv, out/step_04_agents.csv and out/step_04_summary.json
"""
import csv
import json
import os

from common import load_world, analyze, annual_review, replay, ensure_out, OUT_DIR

w = load_world()
grants, calls, groups, agents, needed = w["grants"], w["calls"], w["groups"], w["agents"], w["needed"]
res = analyze(grants, calls, groups, agents)
s, rows = res["summary"], res["grants"]
rev = annual_review(w)

unneeded = {k for k, v in needed.items() if not v["needed"]}
periodic = {k for k, v in needed.items() if v["basis"] == "quarterly_cycle"}


def key(r):
    return r["agent_id"], r["scope"]


removed = {key(r) for r in rows if r["action"] == "remove"}
kept_rows = [r for r in rows if r["action"] != "remove"]
narrowed = [r for r in rows if r["action"] == "narrow"]

# entitlements: what each agent can reach, against what the truth says it needs
elig = {(a, sc) for a, scopes in res["effective"].items() for sc in scopes}
after = {(a, sc) for a, scopes in res["proposed"].items() for sc in scopes}
need = {(a, sc) for (a, _), v in needed.items() if v["needed"] for sc in v["needed_scopes"]}
assert need <= elig and after <= elig
ent_unneeded = elig - need

# the replay is not vacuous: take the busiest tagged scope away from one agent and calls are denied
busy = max(sorted({(c["agent_id"], c["scope"]) for c in calls if c["agent_id"]}),
           key=lambda k: sum(1 for c in calls if (c["agent_id"], c["scope"]) == k))
cut = {a: set(v) for a, v in res["proposed"].items()}
cut[busy[0]].discard(busy[1])
vacuous_check = len(replay(calls, cut, agents))

# hard negatives: grants a stricter rule would have flagged wrongly
needed_rows = [r for r in kept_rows if needed[key(r)]["needed"] and key(r) not in periodic]
rare_kept = [r for r in needed_rows if r["calls_tagged"] + r["calls_credited"] <= 2]
credit_kept = [r for r in needed_rows if r["on_credit_only"]]
no_ticket_kept = [r for r in kept_rows if needed[key(r)]["needed"] and not r["ticket_id"]]
whole_kept = [r for r in rows if r["group"] and r["action"] == "keep"]

# known limits
periodic_rows = [r for r in rows if key(r) in periodic]
periodic_removed = [r for r in periodic_rows if r["action"] == "remove"]
next_q = {(p["agent_id"], p["scope"]): p for p in w["periodic"]}
next_q_denied = sum(next_q[key(r)]["calls_next_quarter"] for r in periodic_removed)
stray_kept = [r for r in kept_rows if key(r) in unneeded and needed[key(r)]["basis"] == "stray_use"]
sibling_kept = [r for r in kept_rows if key(r) in unneeded and r["on_credit_only"]]
other_kept = [r for r in kept_rows if key(r) in unneeded and r not in stray_kept and r not in sibling_kept]

print("STEP 4 - the usage-versus-grant diff")
print(f"  input: {s['grants']} grants, {s['reach_before']} entitlements, {s['calls']} calls over {s['window_days']} days, "
      f"{s['untagged_calls']} with no agent tag")
print(f"  grants: keep {s['keep']}, remove {s['remove']}, narrow {s['narrow']}")
print(f"  unneeded grants removed: {len(removed & unneeded)} of {len(unneeded)} ({len(removed & unneeded) / len(unneeded):.1%}); "
      f"the annual review removed {len(rev['removed'] & unneeded)} of {len(unneeded)} ({len(rev['removed'] & unneeded) / len(unneeded):.1%})")
print(f"  needed grants removed: {len(removed - unneeded)} (the quarterly ones, see the known limit); the annual review removed {len(rev['removed'] - unneeded)}")
print(f"  entitlements: {s['reach_before']} before, {s['reach_after']} after ({s['reach_cut']} cut, {s['reach_cut_pct']}%)")
print(f"    not needed: {len(ent_unneeded)}; cut {len(ent_unneeded - after)}, kept {len(ent_unneeded & after)}; needed entitlements cut: {len(need - after)}")
print(f"  group grants narrowed: {len(narrowed)}; scopes dropped from them: {sum(r['reach'] - len(r['after']) for r in narrowed)}")
print(f"  replay: {s['newly_denied']} of {s['calls']} calls newly denied; the annual review's removals deny {rev['denied']}")
print(f"    in-sample by construction: the proposal is built from these calls. Not vacuous: dropping {busy[1]} from {busy[0]} denies {vacuous_check} calls.")

print("HARD NEGATIVES (could raise a false alarm; the diff keeps them)")
print(f"  needed grants called once or twice in the whole log: {len(rare_kept)}")
print(f"  needed grants whose only calls carry no agent tag: {len(credit_kept)}")
print(f"  needed grants with no ticket reference (the annual review revokes them): {len(no_ticket_kept)}")
print(f"  group grants where every member was called, kept whole: {len(whole_kept)}")

print("KNOWN LIMITS (left in on purpose)")
print(f"  1. Quarterly use. {len(periodic_rows)} grants are legitimate and used once a quarter; the diff removes {len(periodic_removed)} of them.")
print(f"     The first quarter after the cut would deny {next_q_denied} legitimate calls (from data/periodic_truth.csv):")
for r in periodic_removed:
    p = next_q[key(r)]
    print(f"       {r['agent_id']} {r['scope']:<28} next use {p['next_use_date']}, {p['calls_next_quarter']} calls  ({p['why']})")
for r in periodic_rows:
    if r["action"] != "remove":
        print(f"       {r['agent_id']} {r['scope']:<28} kept only because a sibling on the service account called the scope")
print(f"     Owners see {s['remove']} removal proposals; {len(periodic_removed)} of them are periodic scopes the log cannot show.")
print(f"  2. Sibling credit. {len(sibling_kept)} unneeded grants stay because untagged calls are credited to every agent that holds the scope:")
for r in sibling_kept:
    print(f"       {r['agent_id']} {r['scope']:<28} {r['calls_credited']} untagged calls credited")
print(f"  3. Stray use. {len(stray_kept)} unneeded grants stay because a smoke test called them once or twice:")
for r in stray_kept:
    print(f"       {r['agent_id']} {r['scope']:<28} {r['calls_tagged']} tagged call{'s' if r['calls_tagged'] != 1 else ''}")
print(f"  unneeded grants kept for any other reason: {len(other_kept)}")

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_grants.csv"), "w", newline="", encoding="utf-8") as fh:
    wr = csv.writer(fh, lineterminator="\n")
    wr.writerow(["agent_id", "scope", "action", "review", "needed", "basis", "reason", "calls_tagged", "calls_credited", "after"])
    for r in rows:
        k = key(r)
        wr.writerow([r["agent_id"], r["scope"], r["action"], "removed" if k in rev["removed"] else "approved",
                     "yes" if needed[k]["needed"] else "no", needed[k]["basis"], r["reason"],
                     r["calls_tagged"], r["calls_credited"], ";".join(r["after"]) if r["action"] == "narrow" else ""])
with open(os.path.join(OUT_DIR, "step_04_agents.csv"), "w", newline="", encoding="utf-8") as fh:
    cols = ["agent_id", "grants", "reach", "proposed", "cut", "breadth_pct", "keep", "remove", "narrow", "calls"]
    wr = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
    wr.writeheader()
    wr.writerows(sorted(res["agents"], key=lambda r: (-r["breadth_pct"], r["agent_id"])))
summary = {"grants": s["grants"], "keep": s["keep"], "remove": s["remove"], "narrow": s["narrow"],
           "unneeded": len(unneeded), "unneeded_removed": len(removed & unneeded),
           "review_removed": len(rev["removed"]), "review_unneeded_removed": len(rev["removed"] & unneeded),
           "needed_removed": len(removed - unneeded), "reach_before": s["reach_before"], "reach_after": s["reach_after"],
           "reach_cut": s["reach_cut"], "reach_cut_pct": s["reach_cut_pct"], "calls": s["calls"],
           "newly_denied": s["newly_denied"], "review_denied": rev["denied"],
           "periodic": len(periodic_rows), "periodic_removed": len(periodic_removed), "next_quarter_denied": next_q_denied,
           "sibling_kept": len(sibling_kept), "stray_kept": len(stray_kept), "other_kept": len(other_kept),
           "hard_rare_kept": len(rare_kept), "hard_credit_kept": len(credit_kept)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_grants.csv, step_04_agents.csv and step_04_summary.json in src/out/")
