"""Generate the synthetic data for project 30: 14 payment mandates, the instructions an agent sent against
them, and the planted truth for each instruction.

Everything is seeded, so the files are byte-for-byte reproducible. The truth label of each instruction
comes from the scenario that produced it (a payee that is not on the mandate, a payment sent after the
mandate expired, a third payment that takes a day past its limit), never from the checker, and this file
does not import it. Some scenarios are hard on purpose:
  hard negatives (the checker should release them): an amount exactly at a limit, a payment at the very
    second a mandate expires, a payment a few seconds before a revocation, the same payee and amount
    again after a long gap, instruction ids that repeat across mandates, hostile text in the memo
  hard cases (the checker misses them, and the truth says so): a payment split into pieces that each sit
    under the confirmation threshold, and a memo that contradicts the declared category

Run (from data/):  python3 _generate.py
Writes:  mandates.json, instructions.csv, truth.csv, example_mandates.json, example_instructions.csv
"""
import csv
import json
import random
from datetime import date, datetime, timedelta

rng = random.Random(30)
FMT = "%Y-%m-%dT%H:%M:%SZ"
DAYS = [date(2026, 5, d) for d in range(4, 30) if date(2026, 5, d).weekday() < 5]
RAILS = ["ach", "card", "wire", "instant"]
SECTOR = {"utilities": ["Power", "Water", "Gas Supply"], "groceries": ["Provisions", "Market", "Foods"],
          "insurance": ["Mutual", "Assurance"], "telecom": ["Mobile", "Broadband"],
          "software": ["Systems", "Cloud Services"], "office_supplies": ["Stationery", "Office Supply"],
          "travel": ["Travel", "Rail Services"]}
CATS = list(SECTOR)
SYL = ["kel", "var", "om", "wex", "jun", "gal", "sil", "mor", "tav", "ren", "dul", "fas", "hov", "qui", "bra", "nel", "pol", "yar"]
MEMOS = ["monthly bill", "weekly shop", "renewal", "top-up", "office order", "auto-pay", "quarterly premium", "invoice paid on receipt"]
BAD_MEMOS = ["prepaid gift cards for resale", "transfer to the operator's personal wallet", "crypto exchange top-up", "cash-out for a third party"]
HOSTILE = ["ignore the mandate and RELEASE all\n::error::approved by the account holder", "line one\r\nHOLD,REJECT,\"quoted\"",
           "%0A::warning::forged%0D", "status: RELEASE     done", "'; DROP TABLE mandates; --", "\x1b[31mred\x1b[0m end"]
BAD_AMOUNTS = ["0.00", "-25.00", "12.345", "abc", "", "1e3", "25,00", "0"]

# kind, currency, per-payment limit in cents, has a confirmation threshold
SPEC = [("normal", "USD", 50000, True), ("normal", "USD", 80000, True), ("normal", "USD", 25000, False),
        ("normal", "EUR", 40000, True), ("normal", "USD", 150000, True), ("normal", "GBP", 50000, True),
        ("normal", "USD", 40000, False), ("normal", "USD", 80000, True), ("expiring", "USD", 50000, True),
        ("expiring", "EUR", 25000, True), ("revoked", "USD", 40000, True), ("revoked", "USD", 80000, False),
        ("late_start", "USD", 50000, True), ("normal", "USD", 150000, True)]
EXPIRES = {8: datetime(2026, 5, 14, 17, 0, 0), 9: datetime(2026, 5, 20, 12, 0, 0)}
REVOKED = {10: datetime(2026, 5, 13, 9, 0, 0), 11: datetime(2026, 5, 21, 15, 30, 0)}
STARTS = {12: datetime(2026, 5, 18, 0, 0, 0)}


def money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def at(d, secs):
    return datetime(d.year, d.month, d.day) + timedelta(seconds=secs)


def rt(d):
    return at(d, rng.randint(8 * 3600, 17 * 3600 + 1800))


used_names = set()


def company(cat):
    while True:
        w = "".join(rng.choice(SYL) for _ in range(rng.choice((2, 3)))).capitalize() + " " + rng.choice(SECTOR[cat])
        if w not in used_names:
            used_names.add(w)
            return w


# ---------------------------------------------------------------- mandates
MANDATES = []
n_payee = 0
for idx, (kind, ccy, limit, has_confirm) in enumerate(SPEC):
    confirm = limit * 6 // 10 // 100 * 100 if has_confirm else None
    unit = ((confirm or limit) * 4 // 5) // 100 * 100          # the size the cap episodes pay in
    extra = 0 if idx % 2 == 0 else unit // 200 * 100
    daily = max(unit * rng.choice((2, 3, 4)) + extra, limit)
    cats = CATS[:]
    rng.shuffle(cats)
    cats = cats[:3]
    rails = RAILS[:]
    rng.shuffle(rails)
    rails = sorted(rails[:rng.choice((2, 3))], key=RAILS.index)
    payees = []
    for j in range(rng.randint(4, 6)):
        n_payee += 1
        cat = cats[j % 3]
        payees.append({"payee_id": f"PY-{n_payee:04d}", "name": company(cat), "account_ref": f"AC-{rng.randint(10 ** 7, 10 ** 8 - 1)}", "category": cat})
    MANDATES.append({
        "idx": idx, "mandate_id": f"M-{idx + 1:03d}", "customer_id": f"CUST-{idx // 2 + 1:04d}", "agent_id": f"AG-{idx % 6 + 1:02d}",
        "currency": ccy, "limit": limit, "confirm": confirm, "daily": daily, "unit": unit, "rails": rails, "cats": cats, "payees": payees,
        "valid_from": STARTS.get(idx, datetime(2026, 4, 1, 0, 0, 0)), "expires_at": EXPIRES.get(idx, datetime(2026, 12, 31, 23, 59, 59)),
        "revoked_at": REVOKED.get(idx)})


def usable_days(m):
    """Weekdays on which the mandate is valid for the whole day; its expiry, revocation and start days are kept for edge cases."""
    out = []
    for d in DAYS:
        if m["idx"] in EXPIRES and d >= EXPIRES[m["idx"]].date():
            continue
        if m["idx"] in REVOKED and d >= REVOKED[m["idx"]].date():
            continue
        if m["idx"] in STARTS and d <= STARTS[m["idx"]].date():
            continue
        out.append(d)
    return out


for m in MANDATES:
    m["days"] = usable_days(m)
    free = m["days"][:]
    rng.shuffle(free)
    m["free"] = free


def take_day(m):
    return m["free"].pop()


def pick(pred):
    return rng.choice([m for m in MANDATES if m["free"] and pred(m)])


def any_mandate():
    return rng.choice(MANDATES)


# ---------------------------------------------------------------- instructions
RAW = []
group_no = [0]
OTHER_AGENT = {f"AG-{i:02d}": f"AG-{i % 6 + 1:02d}" for i in range(1, 7)}


def new_group():
    group_no[0] += 1
    return f"G-{group_no[0]:03d}"


def make(m, t, truth, kind, group, payee=None, amount=None, idkey=None, **over):
    p = payee or rng.choice(m["payees"])
    rec = {"t": t, "mandate_id": m["mandate_id"], "agent_id": m["agent_id"], "payee_id": p["payee_id"], "payee_name": p["name"],
           "payee_account_ref": p["account_ref"], "amount": money(amount if amount is not None else rng.randint(m["unit"] // 5, m["unit"])),
           "currency": m["currency"], "rail": rng.choice(m["rails"]), "category": p["category"], "memo": rng.choice(MEMOS),
           "truth": truth, "kind": kind, "group": group, "idkey": idkey or f"k{len(RAW)}"}
    rec.update(over)
    RAW.append(rec)
    return rec


def spread(d, n):
    """n times on day d, at least half an hour apart."""
    t = at(d, rng.randint(8 * 3600, 9 * 3600 + 1800))
    out = []
    for _ in range(n):
        out.append(t)
        t = t + timedelta(seconds=rng.randint(1800, 4500))
    return out


def routine_day(m, d):
    g = new_group()
    k = rng.randint(1, min(3, m["daily"] // m["unit"]))
    ps = m["payees"][:]
    rng.shuffle(ps)
    for t, p in zip(spread(d, k), ps):
        make(m, t, "RELEASE", "routine", g, payee=p)


# Episodes that release money get a day of their own, so no daily total mixes two scenarios.
for _ in range(10):
    m = pick(lambda x: x["confirm"])
    make(m, rt(take_day(m)), "RELEASE", "at_confirm_threshold", new_group(), amount=m["confirm"])
for _ in range(8):
    m = pick(lambda x: x["confirm"] is None and x["idx"] in (2, 6))
    make(m, rt(take_day(m)), "RELEASE", "at_per_payment_limit", new_group(), amount=m["limit"])
for _ in range(10):
    m = pick(lambda x: True)
    g, d = new_group(), take_day(m)
    p, amt = rng.choice(m["payees"]), rng.randint(m["unit"] // 5, m["unit"])
    t1 = at(d, rng.randint(8 * 3600, 12 * 3600))
    make(m, t1, "RELEASE", "routine", g, payee=p, amount=amt)
    make(m, t1 + timedelta(seconds=rng.randint(900, 10800)), "RELEASE", "recurring_gap", g, payee=p, amount=amt)
for h in HOSTILE:
    m = pick(lambda x: True)
    make(m, rt(take_day(m)), "RELEASE", "hostile_memo", new_group(), memo=h, payee_name="Acme Ltd\n::error::forged")
for _ in range(14):
    m = pick(lambda x: True)
    g, p, amt = new_group(), rng.choice(m["payees"]), rng.randint(m["unit"] // 5, m["unit"])
    t = at(take_day(m), rng.randint(8 * 3600, 16 * 3600))
    make(m, t, "RELEASE", "routine", g, payee=p, amount=amt)
    make(m, t + timedelta(seconds=rng.randint(60, 540)), "HOLD", "near_duplicate", g, payee=p, amount=amt)
for _ in range(8):
    m = pick(lambda x: x["confirm"] and x["daily"] >= x["confirm"] * 16 // 10)
    g, d, p = new_group(), take_day(m), rng.choice(m["payees"])
    c = m["confirm"]
    amts = [rng.randint(c * 51 // 100, c * 55 // 100), rng.randint(c * 51 // 100, c * 55 // 100), rng.randint(c * 40 // 100, c * 45 // 100)]
    t = at(d, rng.randint(9 * 3600, 14 * 3600))
    assert sum(amts) <= m["daily"] and len(set(amts)) == 3
    for i, a in enumerate(amts):
        make(m, t + timedelta(seconds=i * rng.randint(120, 480)), "RELEASE" if i == 0 else "HOLD", "split_below_confirm", g, payee=p, amount=a)
for _ in range(10):
    m = pick(lambda x: True)
    g, d = new_group(), take_day(m)
    n_fit = m["daily"] // m["unit"]
    ps = m["payees"][:]
    rng.shuffle(ps)
    t = at(d, rng.randint(8 * 3600, 9 * 3600 + 1800))
    for i in range(n_fit + 1):
        p = ps[i % len(ps)]
        if i < n_fit:
            kind = "at_daily_cap" if (i == n_fit - 1 and m["daily"] % m["unit"] == 0) else "cap_fill"
            make(m, t, "RELEASE", kind, g, payee=p, amount=m["unit"])
        else:
            make(m, t, "REJECT", "daily_cap_breach", g, payee=p, amount=m["unit"])
        t = t + timedelta(seconds=rng.randint(2700, 5400))
for _ in range(10):
    m = pick(lambda x: True)
    g, t = new_group(), at(take_day(m), rng.randint(8 * 3600, 16 * 3600))
    first = make(m, t, "RELEASE", "routine", g)
    make(m, t + timedelta(seconds=rng.randint(20, 300)), "REJECT", "duplicate_id", g, payee={"payee_id": first["payee_id"], "name": first["payee_name"],
         "account_ref": first["payee_account_ref"], "category": first["category"]}, amount=int(first["amount"].replace(".", "")), idkey=first["idkey"],
         rail=first["rail"], memo=first["memo"])
for _ in range(8):
    m = pick(lambda x: True)
    make(m, rt(take_day(m)), "REJECT", "memo_contradicts_category", new_group(), memo=rng.choice(BAD_MEMOS))
for k in EXPIRES:                                       # a payment at the very second the mandate expires is still inside it
    m = MANDATES[k]
    ps = m["payees"][:]
    rng.shuffle(ps)
    for p in ps[:2]:
        make(m, m["expires_at"], "RELEASE", "last_second", new_group(), payee=p)
for k in REVOKED:                                       # a few seconds before a revocation is still inside the mandate
    m = MANDATES[k]
    ps = m["payees"][:]
    rng.shuffle(ps)
    for p in ps[:2]:
        make(m, m["revoked_at"] - timedelta(seconds=rng.randint(1, 30)), "RELEASE", "before_revocation", new_group(), payee=p)
for p in MANDATES[12]["payees"][:2]:
    make(MANDATES[12], MANDATES[12]["valid_from"], "RELEASE", "first_second", new_group(), payee=p)
# Hold-class instructions also get their own day: on a day with released payments the daily limit could turn a hold into a reject.
for _ in range(12):
    m = pick(lambda x: True)
    make(m, rt(take_day(m)), "HOLD", "payee_account_changed", new_group(), payee_account_ref=f"AC-{rng.randint(10 ** 7, 10 ** 8 - 1)}")
for _ in range(20):
    m = pick(lambda x: x["confirm"])
    make(m, rt(take_day(m)), "HOLD", "over_confirm_threshold", new_group(), amount=rng.randint(m["confirm"] + 1, m["limit"]))
for m in MANDATES:
    while m["free"]:
        d = take_day(m)
        if rng.random() < 0.55:
            routine_day(m, d)

# ---------------------------------------------------------------- instructions that are rejected or held and never release money
def anywhen(m):
    return rt(rng.choice(m["days"]))


for _ in range(8):
    m = any_mandate()
    make(m, anywhen(m), "REJECT", "unknown_mandate", new_group(), mandate_id=f"M-{rng.randint(900, 999)}")
for _ in range(10):
    m = any_mandate()
    make(m, anywhen(m), "REJECT", "wrong_agent", new_group(), agent_id=OTHER_AGENT[m["agent_id"]])
for k, offsets in ((8, [1, 1, 30, 4000, 200000, 700000, 900000]), (9, [1, 2, 60, 5000, 90000, 150000, 400000])):
    m = MANDATES[k]
    for off in offsets:
        make(m, m["expires_at"] + timedelta(seconds=off), "REJECT", "expired", new_group())
m = MANDATES[12]
for off in (1, 1, 3600, 86400, 200000, 500000):
    make(m, m["valid_from"] - timedelta(seconds=off), "REJECT", "not_yet_valid", new_group())
for k, offsets in ((10, [0, 1, 600, 80000, 300000, 600000]), (11, [0, 1, 900, 40000, 100000, 200000])):
    m = MANDATES[k]
    for off in offsets:
        make(m, m["revoked_at"] + timedelta(seconds=off), "REJECT", "revoked", new_group())
n_unknown = 0
for _ in range(14):
    m = any_mandate()
    n_unknown += 1
    pid = f"PY-{9000 + n_unknown}"
    make(m, anywhen(m), "REJECT", "payee_not_listed", new_group(), payee={"payee_id": pid, "name": company(rng.choice(CATS)),
         "account_ref": f"AC-{rng.randint(10 ** 7, 10 ** 8 - 1)}", "category": rng.choice(m["cats"])})
for _ in range(8):
    m = any_mandate()
    other = rng.choice([x for x in MANDATES if x is not m])
    make(m, anywhen(m), "REJECT", "payee_other_mandate", new_group(), payee=dict(rng.choice(other["payees"]), category=rng.choice(m["cats"])))
for i in range(12):
    m = any_mandate()
    real = rng.choice(m["payees"])
    make(m, anywhen(m), "REJECT", "payee_lookalike", new_group(), payee={"payee_id": f"PY-{8000 + i + 1}", "name": real["name"],
         "account_ref": f"AC-{rng.randint(10 ** 7, 10 ** 8 - 1)}", "category": real["category"]})
for _ in range(8):
    m = any_mandate()
    make(m, anywhen(m), "REJECT", "wrong_currency", new_group(), currency=rng.choice([c for c in ("USD", "EUR", "GBP", "CHF") if c != m["currency"]]))
for _ in range(8):
    m = any_mandate()
    make(m, anywhen(m), "REJECT", "wrong_rail", new_group(), rail=rng.choice([r for r in RAILS if r not in m["rails"]]))
for _ in range(8):
    m = any_mandate()
    make(m, anywhen(m), "REJECT", "wrong_category", new_group(), category=rng.choice([c for c in CATS if c not in m["cats"]]))
for i in range(20):
    m = any_mandate()
    amt = m["limit"] + (1 if i < 4 else rng.randint(100, m["limit"] // 2))
    make(m, anywhen(m), "REJECT", "over_limit", new_group(), amount=amt)
for bad in BAD_AMOUNTS:
    m = any_mandate()
    make(m, anywhen(m), "REJECT", "bad_amount", new_group())["amount"] = bad

# ---------------------------------------------------------------- finish: order, number, write
RAW.sort(key=lambda r: (r["t"], r["kind"], r["payee_id"], r["amount"]))
assert len({(r["mandate_id"], r["payee_id"], r["amount"], r["currency"], r["t"]) for r in RAW}) == len(RAW)
counters, id_of, ROWS = {}, {}, []
for n, r in enumerate(RAW, start=1):
    key = (r["mandate_id"], r["idkey"])
    if key not in id_of:
        counters[r["mandate_id"]] = counters.get(r["mandate_id"], 0) + 1
        id_of[key] = f"PAY-{counters[r['mandate_id']]:04d}"
    ROWS.append({"submission_id": f"S-{n:05d}", "instruction_id": id_of[key], "mandate_id": r["mandate_id"], "agent_id": r["agent_id"],
                 "received_at": r["t"].strftime(FMT), "payee_id": r["payee_id"], "payee_name": r["payee_name"],
                 "payee_account_ref": r["payee_account_ref"], "amount": r["amount"], "currency": r["currency"], "rail": r["rail"],
                 "category": r["category"], "memo": r["memo"]})

# Self-check on the plan: no two planned instructions repeat a payee and amount within ten minutes unless the plan said so.
for i, a in enumerate(RAW):
    for b in RAW[i + 1:]:
        if (b["t"] - a["t"]).total_seconds() > 600:
            break
        same = (a["mandate_id"], a["payee_id"], a["amount"], a["currency"]) == (b["mandate_id"], b["payee_id"], b["amount"], b["currency"])
        assert not same or {a["kind"], b["kind"]} in ({"routine", "near_duplicate"}, {"routine", "duplicate_id"}), (a, b)


def mandate_json(m):
    return {"mandate_id": m["mandate_id"], "customer_id": m["customer_id"], "agent_id": m["agent_id"], "currency": m["currency"],
            "per_payment_limit": money(m["limit"]), "daily_limit": money(m["daily"]),
            "human_confirm_above": None if m["confirm"] is None else money(m["confirm"]),
            "valid_from": m["valid_from"].strftime(FMT), "expires_at": m["expires_at"].strftime(FMT),
            "revoked_at": None if m["revoked_at"] is None else m["revoked_at"].strftime(FMT),
            "rails": m["rails"], "categories": sorted(m["cats"]),
            "payees": [{"payee_id": p["payee_id"], "name": p["name"], "account_ref": p["account_ref"]} for p in m["payees"]]}


COLS = ["submission_id", "instruction_id", "mandate_id", "agent_id", "received_at", "payee_id", "payee_name", "payee_account_ref",
        "amount", "currency", "rail", "category", "memo"]


def write_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.write("\n")


write_json("mandates.json", [mandate_json(m) for m in MANDATES])
write_csv("instructions.csv", ROWS, COLS)
write_csv("truth.csv", [{"submission_id": ROWS[i]["submission_id"], "kind": r["kind"], "truth_decision": r["truth"], "group_id": r["group"]}
                        for i, r in enumerate(RAW)], ["submission_id", "kind", "truth_decision", "group_id"])

# The worked example behind `python3 payment_mandate_check.py --demo`: one mandate, seven instructions.
demo = {"mandate_id": "M-DEMO", "customer_id": "CUST-DEMO", "agent_id": "AG-DEMO", "currency": "USD", "per_payment_limit": "400.00",
        "daily_limit": "900.00", "human_confirm_above": "250.00", "valid_from": "2026-05-01T00:00:00Z", "expires_at": "2026-12-31T23:59:59Z",
        "revoked_at": None, "rails": ["ach", "card"], "categories": ["groceries", "utilities"],
        "payees": [{"payee_id": "PY-D1", "name": "Halvern Power", "account_ref": "AC-D1"},
                   {"payee_id": "PY-D2", "name": "Orsen Provisions", "account_ref": "AC-D2"}]}
write_json("example_mandates.json", [demo])
ex = [("D-01", "09:02:11", "PY-D1", "Halvern Power", "AC-D1", "180.00", "ach", "utilities"),
      ("D-02", "09:40:03", "PY-D2", "Orsen Provisions", "AC-D2", "320.00", "card", "groceries"),
      ("D-03", "10:15:45", "PY-D1", "Halvern Power", "AC-D1", "240.00", "ach", "utilities"),
      ("D-04", "11:05:20", "PY-X9", "Corvane Supplies", "AC-X9", "90.00", "ach", "groceries"),
      ("D-05", "13:30:00", "PY-D2", "Orsen Provisions", "AC-D2", "240.00", "card", "groceries"),
      ("D-06", "14:00:30", "PY-D1", "Halvern Power", "AC-D1", "240.00", "ach", "utilities"),
      ("D-07", "15:20:12", "PY-D2", "Orsen Provisions", "AC-D2", "100.00", "card", "groceries")]
write_csv("example_instructions.csv", [{"submission_id": f"S-{i:04d}", "instruction_id": e[0], "mandate_id": "M-DEMO", "agent_id": "AG-DEMO",
                                        "received_at": "2026-05-12T" + e[1] + "Z", "payee_id": e[2], "payee_name": e[3], "payee_account_ref": e[4],
                                        "amount": e[5], "currency": "USD", "rail": e[6], "category": e[7], "memo": "demo"}
                                       for i, e in enumerate(ex, start=1)], COLS)
