"""Step 1 - Status quo: the register carries a hand-typed column of control ids.

Each obligation row has a `claimed_controls` cell. Someone typed ids into it once. The cell has no scope,
no evidence date and no check that the id still exists, so a reader can only take it as covered (an id is
there) or uncovered (the cell is empty). This step reads that column against the planted truth. The data is
synthetic (data/_generate.py); the typed ids were produced by a process that drops true controls, keeps
retired ones, adds a wrong row and sometimes types an id that was renumbered away.

Run (from src/):  python3 step_01_register_as_it_stands.py
"""
from common import load_all, covered_or_not, count_by, pct

data = load_all()
obs, ctls = data["obligations"], data["controls"]
truth, claimed = data["truth_status"], data["claimed"]
active = sum(1 for c in ctls if c["active"])
mix = count_by(truth.values())

classes = {"serves the obligation": 0, "active but serves another theme or nothing": 0, "retired": 0, "not in the library": 0}
all_invalid = 0
for o in obs:
    oid = o["obligation_id"]
    kinds = []
    for cid in claimed[oid]:
        c = data["ctl_by_id"].get(cid)
        if c is None:
            kinds.append("not in the library")
        elif not c["active"]:
            kinds.append("retired")
        elif (oid, cid) in data["truth_pairs"]:
            kinds.append("serves the obligation")
        else:
            kinds.append("active but serves another theme or nothing")
    for k in kinds:
        classes[k] += 1
    if kinds and "serves the obligation" not in kinds:
        all_invalid += 1
typed = sum(len(v) for v in claimed.values())
with_ids = sum(1 for v in claimed.values() if v)
right = sum(1 for o in obs if covered_or_not(claimed[o["obligation_id"]]) == truth[o["obligation_id"]])
ceiling = mix.get("COVERED", 0) + mix.get("UNCOVERED", 0)

print("STEP 1 - the register as it stands (hand-typed control ids)")
print(f"  obligations: {len(obs)}   controls: {len(ctls)} ({active} active, {len(ctls) - active} retired)")
print("  true status: " + ", ".join(f"{s} {mix.get(s, 0)}" for s in ("COVERED", "STALE", "PARTIAL", "UNCOVERED")))
print(f"  obligations with at least one id typed: {with_ids} of {len(obs)}")
print(f"  ids typed: {typed}")
for k, n in classes.items():
    print(f"    {k}: {n}")
print(f"  obligations that show an id and have no id that serves them: {all_invalid} of {with_ids}")
print(f"  right status when an id means covered and an empty cell means uncovered: {right} of {len(obs)} ({pct(right, len(obs))})")
print(f"  most that reading can reach, since it cannot say STALE or PARTIAL: {ceiling} of {len(obs)}")
print("  The cell carries no scope and no date, and nothing checks the ids when a control is retired or renumbered.")
