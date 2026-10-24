"""Step 3 - Where the record check fails, and where the hash chain on its own still fails.

Two checks on the same 101 planted edits:
  record check   step 2: a checksum per event and a gap-free sequence
  bare chain     the AgentKit audit module's verify_chain as it shipped: each event also carries the hash of
                 the one before it, and the whole chain is read with plain json.loads. No anchor.

KNOWN LIMIT, left in on purpose: events appended by someone who knows the algorithm are the same bytes as
events appended by the real writer, so no check on the file alone can tell them apart. Step 4 does not fix it.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import evaluate, tally, ops_in

result = evaluate()
rows, events = result["rows"], result["events"]
tampered = ops_in(rows, "tampered")

print("STEP 3 (step_03_deficiencies_exposed.py) - record check against the bare chain")
print(f"  {'planted edit':<14} {'planted':>7} {'record check':>13} {'bare chain':>11}")
for op in tampered:
    f1, n = tally(rows, "records", op=op)
    f2, _ = tally(rows, "chain", op=op)
    print(f"  {op:<14} {n:>7} {f1:>13} {f2:>11}")
r_flag, t_all = tally(rows, "records", truth="tampered")
c_flag, _ = tally(rows, "chain", truth="tampered")
r_false, b_all = tally(rows, "records", truth="benign")
c_false, _ = tally(rows, "chain", truth="benign")
print(f"  tampered logs flagged: record check {r_flag} of {t_all}, bare chain {c_flag} of {t_all}")
print(f"  benign changes flagged: record check {r_false} of {b_all}, bare chain {c_false} of {b_all}")

closed = [op for op in tampered if tally(rows, "records", op=op)[0] == 0 and tally(rows, "chain", op=op)[0] == tally(rows, "chain", op=op)[1]]
print(f"  the chain fully closes what the record check leaves open: {', '.join(closed)}")
print("  the bare chain still passes:")
for op in tampered:
    f, n = tally(rows, "chain", op=op)
    if f < n:
        print(f"    {op:<14} {n - f} of {n}")
last = [r["seq"] for r in rows if r["op"] == "edit_rehash" and not r["chain"]]
print(f"  edit_rehash passes only when nothing follows the edited event: it passed at event {', '.join(str(n) for n in last)} of {events}")
fa, fn = tally(rows, "chain", op="append_forged")
la, ln = tally(rows, "chain", op="append_legit")
print(f"  KNOWN LIMIT: forged appends flagged {fa} of {fn}; legitimate appends accepted {ln - la} of {ln}. Same bytes, same verdict.")
