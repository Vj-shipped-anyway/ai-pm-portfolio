"""Generate the synthetic data for project 41: 40 cases, each with a ledger of transactions and a
narrative whose sentences cite those transactions as [txn: ID].

Everything is seeded, so the files are byte-for-byte reproducible. The truth label of each sentence
comes from the defect that was planted (or the harmless variation that was planted), not from the
rules in src/narrative_trace.py. Two kinds are hard on purpose, because the rules cannot see them:
a sentence that cites a real record but asserts something no field of the record can confirm
(laundered), and a sentence whose figures are each right but are bound to the wrong record (mixed_record).
Several fine kinds are hard negatives: formats, abbreviations, numbers that are not amounts, and a date that is
not the date of any transaction (ok_other_date), which the rules do flag.

Run (from data/):  python3 _generate.py
Writes:  transactions.csv, narratives.json, truth.csv, example_txns.csv, example_narrative.txt
"""
from __future__ import annotations

import csv
import datetime
import json
import random
from decimal import Decimal, ROUND_HALF_UP

rng = random.Random(41)
N_CASES = 40

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
COUNT_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]

# Invented counterparties. Any resemblance to a real business is coincidence.
PARTIES_ABBR = ["Quillon Freight Inc.", "Harbor Lane Supply Ltd.", "Tessel Trading Ltd.", "Brindle Foods Inc.",
                "Corvane Textiles Inc.", "Oakmere Tools Ltd."]
PARTIES_PLAIN = ["Marlow Freight", "Marlow Freight Holdings", "Pellam Imports LLC", "Ferrow Logistics",
                 "Dunmore Marine LLC", "Kestrel Row Foods", "Valdane Supply", "Ostrel Holdings",
                 "Wexcombe Trading", "Ildren Textiles LLC", "Sorrel Point Imports", "Nethrin Tools"]
PARTIES = PARTIES_ABBR + PARTIES_PLAIN

# One sentence per (direction, channel). Cash has no counterparty.
TEMPLATES = {
    ("in", "cash"): "The customer deposited {a} in cash on {d}",
    ("in", "wire"): "The account received a wire of {a} from {p} on {d}",
    ("in", "ach"): "The account received an ACH credit of {a} from {p} on {d}",
    ("in", "check"): "The customer deposited a check for {a} from {p} on {d}",
    ("out", "cash"): "The customer withdrew {a} in cash on {d}",
    ("out", "wire"): "The customer sent a wire of {a} to {p} on {d}",
    ("out", "ach"): "The customer paid {a} to {p} by ACH on {d}",
    ("out", "check"): "The customer wrote a check for {a} to {p} on {d}",
    ("out", "card"): "The customer paid {a} to {p} by card on {d}",
}
# The same facts with the counterparty last, so a name ending in "Inc." or "Ltd." sits at the end of the sentence.
PARTY_LAST = {"in": "On {d} the account received {a} by {c} from {p}", "out": "On {d} the customer sent {a} by {c} to {p}"}
CHANNEL_LABEL = {"wire": "wire", "ach": "ACH", "check": "check", "card": "card"}
NONCASH = {"in": ["wire", "ach", "check"], "out": ["wire", "ach", "check", "card"]}

AMOUNT_RANGE = {("in", "cash"): (2000, 9900), ("out", "cash"): (500, 4000), ("in", "wire"): (8000, 60000),
                ("out", "wire"): (5000, 48000), ("in", "ach"): (1200, 8000), ("out", "ach"): (300, 9000),
                ("in", "check"): (1500, 20000), ("out", "check"): (400, 12000), ("out", "card"): (50, 1500)}

# Sentences that cite a real record and say something no field of the record can confirm or deny.
LAUNDERED = ["The funds were moved onward within hours",
             "The customer gave no explanation for this activity when contacted",
             "The source of these funds was never documented",
             "This activity is inconsistent with the stated business of the customer",
             "The customer has a long record of similar activity",
             "A relative of the customer is the ultimate beneficiary",
             "The account holder asked staff not to record this entry",
             "The money came from an unrelated third party"]
# Connecting sentences that are fine and also state nothing a program can compare.
NO_FACTS = ["This entry follows the earlier activity on the account",
            "This is one of the entries reviewed for the case",
            "The entry sits inside the review period",
            "The same account is involved in the entries above",
            "The entry is listed again for completeness",
            "No further entries were reviewed after this one"]

QUOTA = [("ok_plain", 110), ("ok_format", 40), ("ok_abbrev", 24), ("ok_aggregate", 24), ("ok_nonclaim", 20),
         ("ok_cash_adjective", 8), ("ok_cite_after", 16), ("ok_no_facts", 16), ("ok_other_date", 10),
         ("uncited", 20), ("dangling", 14), ("other_case", 12), ("wrong_amount", 14), ("wrong_date", 12),
         ("wrong_party", 12), ("wrong_direction", 10), ("wrong_channel", 10), ("wrong_count", 8),
         ("wrong_total", 8), ("laundered", 12), ("mixed_record", 8)]


# ---------------------------------------------------------------- ledger
def make_case(case_id, next_id):
    n = rng.randint(10, 14)
    spec = [("in", "cash")] * 3 + [("out", "wire")] * 2 + [("in", "ach"), ("in", "check"), ("out", "ach"), ("out", "check")]
    extra = [("in", "cash"), ("in", "wire"), ("in", "ach"), ("out", "wire"), ("out", "card"), ("out", "ach"),
             ("out", "cash"), ("in", "check"), ("out", "check")]
    spec += [rng.choice(extra) for _ in range(n - len(spec))]
    rng.shuffle(spec)
    days = sorted(rng.sample(range(0, 172), n))
    abbr_needed = [("out", "wire"), ("in", "ach")]
    recs = []
    for key, day in zip(spec, days):
        direction, channel = key
        if channel == "cash":
            party = ""
        elif key in abbr_needed:
            abbr_needed.remove(key)
            party = rng.choice(PARTIES_ABBR)
        else:
            party = rng.choice(PARTIES)
        lo, hi = AMOUNT_RANGE[key]
        amount = Decimal(rng.randint(lo * 100, hi * 100)) / 100
        recs.append({"txn_id": "T-%04d" % next_id, "case_id": case_id,
                     "date": datetime.date(2026, 1, 5) + datetime.timedelta(days=day),
                     "amount": amount, "direction": direction, "channel": channel, "counterparty": party})
        next_id += 1
    return recs, next_id


# ---------------------------------------------------------------- sentences
def money(v, style):
    if style == "full":
        return "$%s" % format(v, ",.2f")
    if style == "whole":
        return "$%s" % format(v.quantize(Decimal(1), ROUND_HALF_UP), ",")
    if style == "usd":
        return "%s USD" % format(v, ",.2f")
    return "$%sk" % (v / 1000).quantize(Decimal("0.1"), ROUND_HALF_UP)


def when(d, style):
    if style == "iso":
        return d.isoformat()
    if style == "mdy":
        return "%s %d, %d" % (MONTHS[d.month - 1], d.day, d.year)
    return "%d %s %d" % (d.day, MONTHS[d.month - 1], d.year)


def cite(ids):
    return "[txn: %s]" % ", ".join(ids)


def body(direction, channel, a, d, p):
    return TEMPLATES[(direction, channel)].format(a=a, d=d, p=p)


def count_text(n):
    return COUNT_WORDS[n] if rng.random() < 0.5 else str(n)


def aggregate(recs, mode="ok"):
    """A sentence over 2 to 4 records of one direction: a count, a total and the first and last dates.
    mode "count" misstates the count, mode "total" overstates the total."""
    direction = rng.choice([x for x in ("in", "out") if sum(1 for r in recs if r["direction"] == x) >= 3])
    picked = sorted(rng.sample([r for r in recs if r["direction"] == direction], rng.randint(2, 4)), key=lambda r: r["date"])
    n, total = len(picked), sum(r["amount"] for r in picked)
    if mode == "count":
        n = rng.choice([x for x in (n - 1, n + 1, n + 2) if x >= 2])
    elif mode == "total":
        total += rng.randint(5, 30) * 100
    ds = rng.choice(["iso", "mdy"])
    head = "The account received %s deposits" if direction == "in" else "The customer sent %s payments"
    text = "%s totalling %s between %s and %s" % (head % count_text(n), money(total, "full"),
                                                 when(picked[0]["date"], ds), when(picked[-1]["date"], ds))
    return text + " " + cite([r["txn_id"] for r in picked]) + ".", picked[0]["date"]


def pick(cands, state):
    """A record from cands, preferring one that no sentence has used yet."""
    used = state["used"]
    low = min(used.get(c["txn_id"], 0) for c in cands)
    chosen = rng.choice([c for c in cands if used.get(c["txn_id"], 0) == low])
    used[chosen["txn_id"]] = used.get(chosen["txn_id"], 0) + 1
    return chosen


def make_sentence(kind, recs, others, state):
    """One sentence of the given planted kind for this case. Returns (text, date used to order it)."""
    noncash = [r for r in recs if r["channel"] != "cash"]
    r = pick(recs, state)
    if kind == "ok_plain":
        text = body(r["direction"], r["channel"], money(r["amount"], "full"), when(r["date"], rng.choice(["iso", "mdy"])), r["counterparty"])
        return "%s %s." % (text, cite([r["txn_id"]])), r["date"]
    if kind == "ok_format":
        text = body(r["direction"], r["channel"], money(r["amount"], rng.choice(["whole", "usd", "k"])),
                    when(r["date"], rng.choice(["iso", "mdy", "dmy"])), r["counterparty"])
        return "%s %s." % (text, cite([r["txn_id"]])), r["date"]
    if kind == "ok_abbrev":
        r = pick([x for x in recs if x["counterparty"] in PARTIES_ABBR], state)
        text = PARTY_LAST[r["direction"]].format(a=money(r["amount"], "full"), d=when(r["date"], "mdy"),
                                                 c=CHANNEL_LABEL[r["channel"]], p=r["counterparty"])
        return "%s %s." % (text, cite([r["txn_id"]])), r["date"]
    if kind == "ok_aggregate":
        return aggregate(recs)
    if kind == "ok_nonclaim":
        text = body(r["direction"], r["channel"], money(r["amount"], "full"), when(r["date"], "iso"), r["counterparty"])
        text += ", within the %d-day review window on account ending %04d" % (rng.choice([14, 30, 45, 60, 90]), rng.randint(1000, 9999))
        return "%s %s." % (text, cite([r["txn_id"]])), r["date"]
    if kind == "ok_cash_adjective":
        r = pick([x for x in recs if (x["direction"], x["channel"]) == ("out", "wire")], state)
        text = "The customer, a cash-intensive business, sent a wire of %s to %s on %s" % (
            money(r["amount"], "full"), r["counterparty"], when(r["date"], "mdy"))
        return "%s %s." % (text, cite([r["txn_id"]])), r["date"]
    if kind == "ok_cite_after":
        text = body(r["direction"], r["channel"], money(r["amount"], "full"), when(r["date"], "mdy"), r["counterparty"])
        return "%s. %s" % (text, cite([r["txn_id"]])), r["date"]
    if kind == "ok_no_facts":
        return "%s %s." % (rng.choice(NO_FACTS), cite([r["txn_id"]])), r["date"]
    if kind == "ok_other_date":
        earlier = r["date"] - datetime.timedelta(days=rng.randint(60, 400))
        text = "The customer opened the account on %s, well before the activity cited here" % when(earlier, rng.choice(["iso", "mdy"]))
        return "%s %s." % (text, cite([r["txn_id"]])), r["date"]
    if kind == "uncited":
        text = body(r["direction"], r["channel"], money(r["amount"], "full"), when(r["date"], "mdy"), r["counterparty"])
        return text + ".", r["date"]
    if kind == "dangling":
        state["dangling"] += 1
        text = body(r["direction"], r["channel"], money(r["amount"], "full"), when(r["date"], "mdy"), r["counterparty"])
        return "%s %s." % (text, cite(["T-%04d" % (9000 + state["dangling"])])), r["date"]
    if kind == "other_case":
        s = rng.choice(others)
        text = body(r["direction"], r["channel"], money(r["amount"], "full"), when(r["date"], "mdy"), r["counterparty"])
        return "%s %s." % (text, cite([s["txn_id"]])), r["date"]
    if kind == "wrong_amount":
        wrong = r["amount"] * Decimal(rng.choice(["0.5", "0.8", "1.2", "1.5", "2"]))
        wrong = max(wrong.quantize(Decimal("0.01")), Decimal("1.00"))
        if abs(wrong - r["amount"]) < 100:
            wrong = r["amount"] + 400
        text = body(r["direction"], r["channel"], money(wrong, "full"), when(r["date"], "mdy"), r["counterparty"])
        return "%s %s." % (text, cite([r["txn_id"]])), r["date"]
    if kind == "wrong_date":
        shifted = r["date"] + datetime.timedelta(days=rng.choice([-1, 1]) * rng.randint(3, 40))
        text = body(r["direction"], r["channel"], money(r["amount"], "full"), when(shifted, "mdy"), r["counterparty"])
        return "%s %s." % (text, cite([r["txn_id"]])), r["date"]
    if kind == "wrong_party":
        r = pick(noncash, state)
        other = rng.choice([p for p in PARTIES if r["counterparty"].lower() not in p.lower() and p.lower() not in r["counterparty"].lower()])
        text = body(r["direction"], r["channel"], money(r["amount"], "full"), when(r["date"], "mdy"), other)
        return "%s %s." % (text, cite([r["txn_id"]])), r["date"]
    if kind == "wrong_direction":
        r = pick([x for x in recs if x["channel"] != "card"], state)
        flipped = "out" if r["direction"] == "in" else "in"
        text = body(flipped, r["channel"], money(r["amount"], "full"), when(r["date"], "mdy"), r["counterparty"])
        return "%s %s." % (text, cite([r["txn_id"]])), r["date"]
    if kind == "wrong_channel":
        r = pick(noncash, state)
        new = rng.choice([c for c in NONCASH[r["direction"]] if c != r["channel"]])
        text = body(r["direction"], new, money(r["amount"], "full"), when(r["date"], "mdy"), r["counterparty"])
        return "%s %s." % (text, cite([r["txn_id"]])), r["date"]
    if kind == "wrong_count":
        return aggregate(recs, "count")
    if kind == "wrong_total":
        return aggregate(recs, "total")
    if kind == "laundered":
        return "%s %s." % (rng.choice(LAUNDERED), cite([r["txn_id"]])), r["date"]
    if kind == "mixed_record":
        a, b = sorted(rng.sample([x for x in recs if (x["direction"], x["channel"]) == ("in", "cash")], 2), key=lambda x: x["date"])
        text = "The customer deposited %s in cash on %s, and %s in cash on %s" % (
            money(b["amount"], "full"), when(a["date"], "mdy"), money(a["amount"], "full"), when(b["date"], "mdy"))
        return "%s %s." % (text, cite([a["txn_id"], b["txn_id"]])), a["date"]
    raise ValueError(kind)


# ---------------------------------------------------------------- example for --demo
EXAMPLE_TXNS = [
    ("T-E001", "EX-1", "2026-02-02", "4900.00", "in", "cash", ""),
    ("T-E002", "EX-1", "2026-02-03", "4950.00", "in", "cash", ""),
    ("T-E003", "EX-1", "2026-02-05", "4875.00", "in", "cash", ""),
    ("T-E004", "EX-1", "2026-02-06", "14500.00", "out", "wire", "Tessel Trading Ltd."),
    ("T-E005", "EX-1", "2026-02-10", "2300.00", "in", "ach", "Brindle Foods Inc."),
    ("T-E006", "EX-1", "2026-02-12", "3100.00", "out", "wire", "Ostrel Marine LLC"),
    ("T-E101", "EX-2", "2026-03-01", "9000.00", "out", "wire", "Kestrel Row Imports"),
]
EXAMPLE_NARRATIVE = (
    "Between 2026-02-02 and 2026-02-05 the account received three deposits totalling $14,725.00 [txn: T-E001, T-E002, T-E003].\n"
    "On February 6, 2026 the customer sent a wire of $14,500.00 to Tessel Trading Ltd. [txn: T-E004]. "
    "The customer paid $14,500.00 to Tessel Trading Ltd. by ACH on 2026-02-06 [txn: T-E004].\n\n"
    "On 2026-02-10 the account received an ACH credit of $2,800.00 from Brindle Foods Inc. [txn: T-E005]. "
    "The customer moved the balance offshore the same week. "
    "On 2026-02-12 the customer sent a wire of $3,100.00 to Ostrel Marine LLC [txn: T-E101]. "
    "A further payment followed on 2026-02-20 [txn: T-E099]. "
    "The activity is inconsistent with the stated business of the customer [txn: T-E005].\n")


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    case_ids = ["C-%03d" % (i + 1) for i in range(N_CASES)]
    ledger, by_case, next_id = [], {}, 1
    for cid in case_ids:
        recs, next_id = make_case(cid, next_id)
        by_case[cid] = recs
        ledger.extend(recs)
    plans = [kind for kind, n in QUOTA for _ in range(n)]
    rng.shuffle(plans)
    per_case = {cid: [] for cid in case_ids}
    for i, kind in enumerate(plans):
        per_case[case_ids[i % N_CASES]].append(kind)
    state = {"dangling": 0, "used": {}}
    narratives, truth = [], []
    for cid in case_ids:
        others = [r for r in ledger if r["case_id"] != cid]
        items = []
        for order, kind in enumerate(per_case[cid]):
            text, anchor = make_sentence(kind, by_case[cid], others, state)
            items.append((anchor, order, kind, text))
        items.sort(key=lambda x: (x[0], x[1]))
        half = (len(items) + 1) // 2
        out = ""
        for k, (_, _, kind, text) in enumerate(items):
            if k:
                out += "\n\n" if k == half else " "
            truth.append((cid, k + 1, len(out), len(out) + len(text), kind, "ok" if kind.startswith("ok_") else "flag"))
            out += text
        narratives.append({"case_id": cid, "text": out + "\n"})
    write_csv("transactions.csv", ["txn_id", "case_id", "date", "amount", "direction", "channel", "counterparty"],
              [(r["txn_id"], r["case_id"], r["date"].isoformat(), "%.2f" % r["amount"], r["direction"], r["channel"], r["counterparty"])
               for r in ledger])
    with open("narratives.json", "w", encoding="utf-8") as fh:
        json.dump(narratives, fh, indent=1, sort_keys=True)
        fh.write("\n")
    write_csv("truth.csv", ["case_id", "sent_no", "start", "end", "kind", "expected"], truth)
    write_csv("example_txns.csv", ["txn_id", "case_id", "date", "amount", "direction", "channel", "counterparty"], EXAMPLE_TXNS)
    with open("example_narrative.txt", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(EXAMPLE_NARRATIVE)


if __name__ == "__main__":
    main()
