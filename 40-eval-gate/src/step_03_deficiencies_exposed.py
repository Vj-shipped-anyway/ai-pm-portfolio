"""Step 3 - Where each half fails when used alone.

Three gates, each with one idea:
  id alarm        block when any probe was served by an id other than the last one the team knew; there is
                  no pin to move, so a change the team announced is blocked too
  pin only        block when any probe was served by an id other than the pin the caller passes in
  probe rules     the drop, collapse and coverage rules, with no look at the snapshot id

The truth is known, so each gate is scored on the same 64 runs. KNOWN LIMIT, left in on purpose: a vendor
that changes behavior by two points behind an unchanged id is below the noise of ten trials per probe;
neither half sees it, and step 4 does not either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from collections import Counter

from common import load_runs, gate

LAST_KNOWN = "vendor-balanced-4-20260214"
PROBE_RULES = {"overall_drop", "probe_collapse", "unscored_probes"}

probes, runs = load_runs()
must = [r for r in runs if r["truth"] == "BLOCK"]
rev = [r for r in runs if r["truth"] == "REVIEW"]
fine = [r for r in runs if r["truth"] == "ALLOW"]


def id_alarm(run):
    return "BLOCK" if any(x["served_model"] != LAST_KNOWN for x in run["rows"]) else "ALLOW"


def pin_only(run):
    return gate(probes, run, kinds={"snapshot_changed"})["decision"]


def probe_rules(run):
    return gate(probes, run, kinds=PROBE_RULES)["decision"]


def score(name, decide):
    got = {r["run_id"]: decide(r) for r in runs}
    print(f"  {name}")
    print(f"    should-block runs stopped: {sum(1 for r in must if got[r['run_id']] == 'BLOCK')} of {len(must)}")
    print(f"    should-review runs flagged (REVIEW or BLOCK): {sum(1 for r in rev if got[r['run_id']] != 'ALLOW')} of {len(rev)}")
    print(f"    fine runs stopped: {sum(1 for r in fine if got[r['run_id']] == 'BLOCK')} of {len(fine)}")
    slipped = Counter(r["kind"] for r in must if got[r["run_id"]] == "ALLOW")
    print("    should-block runs that pass, by planted event: " + (", ".join(f"{k} {v}" for k, v in sorted(slipped.items())) or "none"))
    return got


print("STEP 3 - each gate alone (step_03_deficiencies_exposed.py)")
score("id alarm, no pin to move", id_alarm)
by_pin = score("pin only", pin_only)
by_probes = score("probe rules only", probe_rules)
both_miss = [r for r in runs if r["truth"] != "ALLOW" and by_pin[r["run_id"]] == "ALLOW" and by_probes[r["run_id"]] == "ALLOW"]
print(f"  should-block or should-review runs that pass both halves: {len(both_miss)} of {len(must) + len(rev)}")
print("  by planted event: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(r["kind"] for r in both_miss).items())))
clean = [gate(probes, r)["drop"] for r in runs if r["kind"] == "clean"]
over = sum(1 for d in clean if d > 0.03)
print(f"  sampling noise on {len(clean)} clean runs: mean drop {sum(clean) / len(clean) * 100:.1f} points, "
      f"worst {max(clean) * 100:.1f} points, {over} over the 3-point review line")
print("  A pass rate cannot see a swap that scores the same; an id check cannot see a change behind the same id.")
