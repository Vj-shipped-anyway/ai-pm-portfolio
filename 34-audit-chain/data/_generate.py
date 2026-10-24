"""Generate the synthetic data for project 34: a stream of agent actions, a plan of planted edits to the
log those actions produce, and a small sample log for the --demo run.

Everything is seeded, so a rerun reproduces every file byte for byte. The truth label of each planted
edit comes from the edit that is planned (what is done to the file), not from any verifier. This file
has its own small hash writer on purpose: the verifier in src/ is tested against a log it did not write.

Hard cases are planted on purpose. Edits that a hash chain cannot see: the last event rewritten with its
own hash recomputed, the log cut back to a point after the last anchor, events appended by someone who
knows the algorithm, a rewrite of the open tail. Harmless changes that could raise a false alarm: keys
reordered, characters written raw instead of escaped, carriage returns, blank lines, and events appended
by the real writer after the anchor was taken.

Run (from data/):  python3 _generate.py
Writes:  actions.csv, tamper_plan.csv, params.json, example_log.jsonl, example_log_edited.jsonl,
         example_log_cut.jsonl, example_anchor.json
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 34
N_CASES = 36
ANCHOR_SEQ = 200          # assumption: one anchor per 200 events; no rule sets this number
EXAMPLE_EVENTS = 30
EXAMPLE_ANCHOR = 24
EXAMPLE_CUT = 20
GENESIS = "0" * 64

rng = random.Random(SEED)

SOURCES = ["queue_a", "queue_b", "queue_c"]
TOOLS = [("payments_db", "get_payment"), ("party_screen", "screen_party"), ("case_notes", "write_note")]
RATIONALES = ["amount within the agent limit", "beneficiary name matches the payment", "reason code maps to a known fix",
              "party screen returned no match", "details differ from the original message", "no prior correction on file"]
ROUTES = [("auto", "all checks passed"), ("to_person", "needs a reviewer"), ("human_queue", "tool failed twice")]
NOTES = ["checked against the original message", "revisé la referencia", "señal revisada por el equipo",
         "Zoë confirmed the reference", "ok"]
BENIGN_OPS = ("reformat_keys", "reformat_unicode", "reformat_crlf", "reformat_blank_lines", "append_legit")


# ---------------------------------------------------------------- the agent's actions
def make_actions() -> list:
    rows = []
    for i in range(1, N_CASES + 1):
        cid = "C%04d" % i
        rows.append((cid, "", "case_start", "agent", {"priority": rng.choice(["low", "normal", "high"]), "source": rng.choice(SOURCES)}))
        for s in range(1, rng.randint(2, 4) + 1):
            step = "S%02d" % s
            rows.append((cid, step, "decision", "agent", {"decided": rng.choice(["continue", "continue", "hold"]), "rationale": rng.choice(RATIONALES)}))
            if rng.random() < 0.6:
                tool, action = rng.choice(TOOLS)
                rows.append((cid, step, "tool_call", "agent", {"action": action, "outcome": rng.choice(["ok", "ok", "ok", "retried"]), "tool": tool}))
        if i % 3 == 1 or rng.random() < 0.15:
            rows.append((cid, "S07", "gate", "agent", {"reason": "amount above the agent limit"}))
            rows.append((cid, "S07", "approval", "reviewer.%d" % rng.randint(1, 5),
                         {"answer": rng.choice(["approved", "approved", "declined"]), "note": rng.choice(NOTES)}))
        if rng.random() < 0.08:
            rows.append((cid, "S05", "fallback", "agent", {"reason": "tool failed twice"}))
        route, reason = rng.choice(ROUTES)
        rows.append((cid, "", "route", "agent", {"reason": reason, "route": route}))
    return rows


# ---------------------------------------------------------------- an independent hash writer
def digest(prev: str, core: dict) -> str:
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256((prev + blob).encode("utf-8")).hexdigest()


def chain(rows: list) -> list:
    events, prev = [], GENESIS
    for n, (cid, step, kind, actor, detail) in enumerate(rows, start=1):
        core = {"seq": n, "case_id": cid, "step": step or None, "kind": kind, "actor": actor, "detail": detail}
        ev = dict(core)
        ev["prev"] = prev
        ev["hash"] = digest(prev, core)
        prev = ev["hash"]
        events.append(ev)
    return events


def line(ev: dict) -> str:
    return json.dumps(ev, sort_keys=True, ensure_ascii=True)


# ---------------------------------------------------------------- the plan of planted edits
def make_plan(total: int) -> list:
    """Rows of (op, seq, count, region, truth). seq is the first event the edit touches (0 when it touches the whole file)."""
    spec = []

    def add(op, n, lo, hi):
        for s in sorted(rng.sample(range(lo, hi + 1), n)):
            spec.append((op, s, 0))

    a = ANCHOR_SEQ
    for op, n in (("edit_value", 8), ("edit_rehash", 8), ("delete_event", 6), ("delete_fix", 6), ("swap_fix", 6),
                  ("insert_fix", 6), ("dup_key", 5), ("add_field", 5), ("rewrite_all", 8)):
        add(op, n, 3, a - 3)
    for k in sorted(rng.sample(range(total - a + 1, total - a + 41), 6)):
        spec.append(("truncate", total - k + 1, k))
    for op, n in (("edit_value", 4), ("edit_rehash", 4), ("rewrite_all", 4), ("dup_key", 2), ("add_field", 2)):
        add(op, n, a + 2, total - 2)
    spec.append(("edit_rehash", total, 0))
    for k in sorted(rng.sample(range(1, total - a + 1), 4)):
        spec.append(("truncate", total - k + 1, k))
    for _ in range(6):
        spec.append(("append_forged", total + 1, rng.randint(1, 3)))
    for op in BENIGN_OPS[:-1]:
        spec.append((op, 0, 0))
    for _ in range(6):
        spec.append(("append_legit", total + 1, rng.randint(1, 20)))
    rng.shuffle(spec)
    plan = []
    for op, seq, count in spec:
        benign = op in BENIGN_OPS
        region = "-" if benign else "anchored" if seq <= a else "open"
        plan.append((op, seq, count, region, "benign" if benign else "tampered"))
    return plan


def write(name: str, text: str) -> None:
    with open(os.path.join(HERE, name), "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def write_csv(name: str, header: list, rows: list) -> None:
    with open(os.path.join(HERE, name), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    rows = make_actions()
    events = chain(rows)
    total = len(events)
    assert total >= ANCHOR_SEQ + 50, "the open tail after the anchor is too short for the plan"
    write_csv("actions.csv", ["case_id", "step", "kind", "actor", "detail_json"],
              [(c, s, k, a, json.dumps(d, sort_keys=True, ensure_ascii=True)) for c, s, k, a, d in rows])
    plan = make_plan(total)
    write_csv("tamper_plan.csv", ["tamper_id", "op", "seq", "count", "region", "truth"],
              [("T%03d" % n, *p) for n, p in enumerate(plan, start=1)])
    write("params.json", json.dumps({"anchor_seq": ANCHOR_SEQ, "cases": N_CASES, "events": total, "seed": SEED,
                                     "tamper_rows": len(plan)}, indent=1, sort_keys=True) + "\n")

    sample = events[:EXAMPLE_EVENTS]
    write("example_log.jsonl", "".join(line(e) + "\n" for e in sample))
    edited = [dict(e) for e in sample]
    target = next(e for e in edited[:EXAMPLE_ANCHOR] if e["kind"] == "approval")
    target["detail"] = dict(target["detail"], answer="approved" if target["detail"]["answer"] == "declined" else "declined")
    write("example_log_edited.jsonl", "".join(line(e) + "\n" for e in edited))
    write("example_log_cut.jsonl", "".join(line(e) + "\n" for e in sample[:EXAMPLE_CUT]))
    write("example_anchor.json", json.dumps({"hash": sample[EXAMPLE_ANCHOR - 1]["hash"], "seq": EXAMPLE_ANCHOR, "version": 1},
                                            indent=1, sort_keys=True) + "\n")
    print("wrote %d actions, %d planted edits, 4 sample files" % (total, len(plan)))


if __name__ == "__main__":
    main()
