"""Step 3 - Where each half of the mandate check fails when used alone.

Two gates, each with one idea:
  per-instruction checks   mandate, agent, validity window, payee, currency, rail, category, limits
                           and the confirmation threshold, each looked at on its own
  ledger only              the daily total and the duplicate checks, which need memory of what was released

The truth is known, so each is scored on the same 475 instructions. KNOWN LIMIT, left in on purpose:
a payment split into pieces that each sit under the confirmation threshold, and a memo that
contradicts the declared category, pass the full check as well. Step 4 prints them again.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from collections import Counter

from common import load_case, check_batch, score, ALL_GROUPS, RELEASE, KNOWN_LIMIT

mandates, rows, truth = load_case()


def run(name, enabled):
    got = {r["submission_id"]: r["decision"] for r in check_batch(mandates, rows, enabled)}
    s = score(got, truth)
    print(f"  {name}")
    print(f"    forbidden instructions released: {s['bad_released']}; needed a person but released: {s['person_released']}; legitimate stopped: {s['legit_stopped']}")
    return got


print("STEP 3 - each half alone")
stateless = run("per-instruction checks only (no memory of earlier instructions)", ALL_GROUPS - {"ledger"})
run("ledger only (daily total and duplicates, nothing else)", frozenset({"ledger"}))
full = {r["submission_id"]: r["decision"] for r in check_batch(mandates, rows)}
only_ledger = Counter(truth[sid]["kind"] for sid, d in stateless.items() if d == RELEASE and full[sid] != RELEASE)
print("  released by the per-instruction checks and stopped only by the ledger: " + ", ".join(f"{k} {v}" for k, v in sorted(only_ledger.items())))
print("  KNOWN LIMIT: still released by the full check")
for kind in KNOWN_LIMIT:
    bad = [sid for sid, t in truth.items() if t["kind"] == kind and t["truth_decision"] != RELEASE]
    print(f"    {kind}: {sum(full[x] == RELEASE for x in bad)} of {len(bad)}")
groups = {t["group_id"] for t in truth.values() if t["kind"] == "split_below_confirm"}
print(f"    the split payments come from {len(groups)} groups of three: the first piece is fine, the second and third are what a person should see")
print("  The ledger cannot see a wrong payee; the per-instruction checks cannot see a third payment that breaks the day.")
