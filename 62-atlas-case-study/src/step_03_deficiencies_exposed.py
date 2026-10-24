"""Step 3 - Where each approach fails, scored against the planted truth.

Two ways to a draft, each with one idea:
  ticket words    step 2: look for technique words in the on-call note
  trace shape     step 4's loop rule alone: phases of calls with the same tool and argument shape

Seven kinds of run were planted, so each approach is scored per kind. KNOWN LIMIT, left in on purpose: a
retry storm cut off after a dozen calls, and two tools called in turn with no progress, both fall outside
the loop rule, and step 4 does not catch them either. The 20-call threshold is an assumption; the table at
the end shows what moving it costs.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import load_runs, keyword_draft, build_study, phases

runs = load_runs()
words = {r["run_id"]: keyword_draft(r["ticket"])[0] for r in runs}
shape = {r["run_id"]: build_study(r["bundle"]) for r in runs}
KINDS = ["retry_storm", "poisoned_loop", "short_storm", "alternating_loop", "benign", "benign_batch", "id_walk"]

print("STEP 3 - each approach alone, by planted kind of run")
print(f"  {'kind':<18}{'failure':<9}{'runs':>5}{'ticket words':>14}{'trace shape':>13}")
for k in KINDS:
    rs = [r for r in runs if r["scenario"] == k]
    print(f"  {k:<18}{'yes' if rs[0]['worthy'] else 'no':<9}{len(rs):>5}{sum(1 for r in rs if words[r['run_id']]):>14}{sum(1 for r in rs if shape[r['run_id']]):>13}")

poisoned = [r for r in runs if r["scenario"] == "poisoned_loop"]
inj_words = sum(1 for r in poisoned if "AML.T0051.001" in words[r["run_id"]])
inj_shape = sum(1 for r in poisoned if shape[r["run_id"]] and any(e["technique"] == "AML.T0051.001" for e in shape[r["run_id"]][1]))
print(f"  poisoned runs where the injection step is found: ticket words {inj_words} of {len(poisoned)}, trace shape {inj_shape} of {len(poisoned)}")

worthy = [r for r in runs if r["worthy"]]
missed = [r for r in worthy if not shape[r["run_id"]]]
print(f"  failures the trace shape does not draft: {len(missed)} of {len(worthy)}; the ticket words reach {sum(1 for r in missed if words[r['run_id']])} of them")
print("KNOWN LIMIT (left in on purpose, step 4 does not fix it):")
for k in ("short_storm", "alternating_loop"):
    longest = sorted(max(p["n"] for p in phases(r["bundle"]["calls"])) for r in runs if r["scenario"] == k)
    print(f"  {k}: longest run of same-shape calls per run is {longest}; the loop rule needs 20")

print(f"  moving the threshold (failures drafted of {len(worthy)}, harmless runs drafted of {len(runs) - len(worthy)}):")
for lm in (10, 20, 30):
    got = [(r["worthy"], build_study(r["bundle"], loop_min=lm) is not None) for r in runs]
    print(f"    {lm:>2} calls: {sum(1 for w, d in got if w and d)} of {len(worthy)}, {sum(1 for w, d in got if not w and d)} of {len(runs) - len(worthy)}")
print("  A ticket cannot show what the agent did; a trace cannot show what the on-call engineer saw.")
