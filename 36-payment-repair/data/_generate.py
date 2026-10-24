"""Generate the synthetic data for project 36: 500 pacs.008-style payment messages, each built
complete and then damaged by a named recipe, plus the reference tables the repair tool reads.

Everything is seeded, so a rerun reproduces every file byte for byte. The true value of every
damaged field is the value the generator removed or overwrote, so the answer key comes from the
generative process and not from the repair rules. The intended route per recipe (PASS, REPAIRED,
HOLD or RETURN) is my policy written down once more; the rules in src/payment_repair.py are a
second statement of it, written by the same person.

Three kinds of hard case are planted on purpose:
  hard negatives   look like damage and are not (missing optional fields, names that contain the
                   word "unknown", 8-character BICs)
  traps            a table gives an answer that looks usable and is not (two active BICs for one
                   bank code, a retired BIC, a joint account, a stale beneficiary book)
  known misses     the tool cannot see them (a well-formed BIC that belongs to a different bank,
                   a directory that still lists a bank's old BIC, a creditor who lives abroad)

Run (from data/):  python3 _generate.py
Writes: messages.json, message_truth.csv, defects_truth.csv, bic_directory.csv, customer_master.csv,
        payment_orders.csv, beneficiary_book.csv, approvers.csv, example_messages.json
"""
from __future__ import annotations

import csv
import io
import json
import os
import random

SEED = 36
HERE = os.path.dirname(os.path.abspath(__file__))

MSG_ID = "GrpHdr.MsgId"
NB = "GrpHdr.NbOfTxs"
E2E = "CdtTrfTxInf.PmtId.EndToEndId"
UETR = "CdtTrfTxInf.PmtId.UETR"
AMT = "CdtTrfTxInf.IntrBkSttlmAmt"
CCY = "CdtTrfTxInf.IntrBkSttlmAmt@Ccy"
CHRG = "CdtTrfTxInf.ChrgBr"
DBTR_NM = "CdtTrfTxInf.Dbtr.Nm"
DBTR_IBAN = "CdtTrfTxInf.DbtrAcct.Id.IBAN"
DBTR_BIC = "CdtTrfTxInf.DbtrAgt.FinInstnId.BICFI"
CDTR_NM = "CdtTrfTxInf.Cdtr.Nm"
CDTR_CTRY = "CdtTrfTxInf.Cdtr.PstlAdr.Ctry"
CDTR_IBAN = "CdtTrfTxInf.CdtrAcct.Id.IBAN"
CDTR_BIC = "CdtTrfTxInf.CdtrAgt.FinInstnId.BICFI"
PURP = "CdtTrfTxInf.Purp.Cd"
RMT = "CdtTrfTxInf.RmtInf.Ustrd"

# name, count, intended route, hardness
RECIPES = [
    ("clean", 100, "PASS", "plain"),
    ("optional_absent", 30, "PASS", "hard_negative"),
    ("lookalike_name", 8, "PASS", "hard_negative"),
    ("bic8_valid", 6, "PASS", "hard_negative"),
    ("nbtxs_missing", 24, "REPAIRED", "plain"),
    ("dbtr_bic_missing", 36, "REPAIRED", "plain"),
    ("dbtr_name_missing", 30, "REPAIRED", "plain"),
    ("dbtr_name_joint", 8, "RETURN", "trap"),
    ("cdtr_bic_missing", 40, "HOLD", "plain"),
    ("cdtr_bic_malformed", 8, "HOLD", "plain"),
    ("cdtr_bic_ambiguous", 10, "RETURN", "trap"),
    ("cdtr_bic_retired", 6, "RETURN", "trap"),
    ("cdtr_bic_no_row", 6, "RETURN", "trap"),
    ("cdtr_bic_stale", 5, "HOLD", "known_miss"),
    ("cdtr_ctry_missing", 24, "HOLD", "plain"),
    ("cdtr_ctry_foreign", 4, "HOLD", "known_miss"),
    ("uetr_missing_order", 20, "HOLD", "plain"),
    ("uetr_missing_no_order", 6, "RETURN", "trap"),
    ("chrgbr_missing_order", 14, "HOLD", "plain"),
    ("chrgbr_missing_no_order", 5, "RETURN", "trap"),
    ("ccy_missing", 24, "RETURN", "trap"),
    ("amount_missing", 10, "RETURN", "plain"),
    ("cdtr_name_missing_book", 13, "RETURN", "trap"),
    ("cdtr_name_missing_stale_book", 5, "RETURN", "trap"),
    ("cdtr_name_missing_no_book", 6, "RETURN", "plain"),
    ("cdtr_name_placeholder", 14, "RETURN", "trap"),
    ("cdtr_iban_missing", 8, "RETURN", "plain"),
    ("two_holds", 10, "HOLD", "plain"),
    ("auto_and_return", 8, "RETURN", "trap"),
    ("bic_present_wrong", 12, "HOLD", "known_miss"),
]

SECTORS = ["Paper", "Foods", "Ceramics", "Timber", "Logistics", "Textiles", "Marine", "Plastics", "Electrical",
           "Chemicals", "Freight", "Machining", "Packaging", "Optics"]
SUFFIX = {"DE": "GmbH", "FR": "SARL", "NL": "BV", "ES": "SL", "IT": "SpA", "BE": "NV"}
COUNTRIES = ["DE", "FR", "NL", "ES", "IT", "BE"]
OWN_COUNTRIES = ["DE", "FR", "NL", "ES"]
CCYS = ["EUR", "EUR", "EUR", "EUR", "EUR", "USD", "USD", "GBP", "GBP", "CHF"]
LOOKALIKES = ["Unknown Pleasures Trading Ltd", "N/A Logistics GmbH", "None Such Wines BV", "Null Point Freight SA",
              "TBD Holdings Ltd", "Not Provided Catering SL", "Na Zdrowie Imports SpA", "Test Kitchen Supplies NV"]
PLACEHOLDERS = ["N/A", "  ", "NOTPROVIDED", "UNKNOWN", "-", "TBD"]
INITIATORS = ["U-2001", "U-2002", "U-2003", "U-2004", "U-2005", "U-2006", "U-2007", "U-2008"]
REVIEWER_INITIATORS = ["U-1041", "U-1042"]
APPROVERS = [
    ("U-1041", "person", "payments_reviewer", "yes"), ("U-1042", "person", "payments_reviewer", "yes"),
    ("U-1043", "person", "payments_reviewer", "yes"), ("U-1044", "person", "payments_reviewer", "no"),
    ("U-2001", "person", "payments_initiator", "yes"), ("U-2002", "person", "payments_initiator", "yes"),
    ("U-2003", "person", "payments_initiator", "yes"), ("U-2004", "person", "payments_initiator", "yes"),
    ("U-2005", "person", "payments_initiator", "yes"), ("U-2006", "person", "payments_initiator", "yes"),
    ("U-2007", "person", "payments_initiator", "yes"), ("U-2008", "person", "payments_initiator", "yes"),
    ("A-7001", "agent", "repair_agent", "yes"), ("S-7100", "service", "batch_scheduler", "yes"),
]
VOW, CON = "aeiou", "bdfgklmnprstvz"


def company(rng, seen, country):
    while True:
        base = "".join(rng.choice(CON) + rng.choice(VOW) for _ in range(rng.choice([2, 3]))).capitalize()
        name = f"{base} {rng.choice(SECTORS)} {SUFFIX[country]}"
        if name not in seen:
            seen.append(name)
            return name


def bic_letters(rng, seen):
    while True:
        s = (rng.choice(CON) + rng.choice(VOW) + rng.choice(CON) + rng.choice(VOW)).upper()
        if s not in seen:
            seen.append(s)
            return s


def uuid_like(rng):
    h = "%032x" % rng.getrandbits(128)
    return f"{h[:8]}-{h[8:12]}-4{h[13:16]}-{'89ab'[int(h[16], 16) & 3]}{h[17:20]}-{h[20:32]}"


def cents_text(c):
    return f"{c // 100}.{c % 100:02d}"


def build_world(rng):
    """Banks, the directory snapshot, creditors, debtors and the beneficiary book."""
    letters, codes, ibans, names = [], [], [], []

    def code():
        while True:
            c = "9" + "%07d" % rng.randrange(10 ** 7)
            if c not in codes:
                codes.append(c)
                return c

    def iban(country, bank_code):
        while True:
            s = f"{country}{rng.randrange(100):02d}{bank_code}{rng.randrange(10 ** 10):010d}"
            if s not in ibans:
                ibans.append(s)
                return s

    def bic(country, long_form):
        base = bic_letters(rng, letters) + country + rng.choice(["FF", "2X", "MM", "22", "LL", "PP"])
        return base + "XXX" if long_form else base

    directory = []
    own_banks = []
    for i, c in enumerate(OWN_COUNTRIES):
        b = {"code": code(), "country": c, "bic": bic(c, i % 2 == 0), "kind": "own"}
        own_banks.append(b)
        directory.append({"country": c, "bank_code": b["code"], "bic": b["bic"], "status": "active"})
        if i % 2 == 1:
            directory.append({"country": c, "bank_code": b["code"], "bic": bic(c, True), "status": "retired"})
    kinds = ["normal"] * 14 + ["ambiguous"] * 4 + ["retired_only"] * 2 + ["no_row"] * 2 + ["stale"] * 2
    banks = []
    n_normal = 0
    for i, kind in enumerate(kinds):
        c = COUNTRIES[i % len(COUNTRIES)]
        long_form = True
        if kind == "normal":
            long_form = n_normal % 3 != 0
        b = {"code": code(), "country": c, "bic": bic(c, long_form), "kind": kind}
        banks.append(b)
        if kind == "normal":
            directory.append({"country": c, "bank_code": b["code"], "bic": b["bic"], "status": "active"})
            if n_normal % 3 == 1:
                directory.append({"country": c, "bank_code": b["code"], "bic": bic(c, True), "status": "retired"})
            n_normal += 1
        elif kind == "ambiguous":
            directory.append({"country": c, "bank_code": b["code"], "bic": b["bic"], "status": "active"})
            directory.append({"country": c, "bank_code": b["code"], "bic": bic(c, True), "status": "active"})
        elif kind == "retired_only":
            directory.append({"country": c, "bank_code": b["code"], "bic": bic(c, True), "status": "retired"})
        elif kind == "stale":
            directory.append({"country": c, "bank_code": b["code"], "bic": bic(c, True), "status": "active"})

    pool_spec = [("normal", 100), ("ambiguous", 12), ("retired_only", 6), ("no_row", 6), ("stale", 6), ("foreign", 6)]
    pools = {name: [] for name, _ in pool_spec}
    book = []
    for name, size in pool_spec:
        host = [b for b in banks if b["kind"] == ("normal" if name == "foreign" else name)]
        for j in range(size):
            b = host[j % len(host)]
            cname = company(rng, names, b["country"])
            postal = b["country"]
            if name == "foreign":
                postal = rng.choice([c for c in COUNTRIES if c != b["country"]])
            pools[name].append({"name": cname, "iban": iban(b["country"], b["code"]), "bank": b, "ctry": postal,
                                "book": "none"})
    for j, cr in enumerate(pools["normal"]):
        if j < 30:
            cr["book"] = "fresh"
            book.append({"iban": cr["iban"], "name": cr["name"]})
        elif j < 40:
            cr["book"] = "stale"
            book.append({"iban": cr["iban"], "name": company(rng, names, cr["bank"]["country"])})

    master, single, joint = [], [], []
    for j in range(108):
        b = own_banks[j % len(own_banks)]
        acct = {"iban": iban(b["country"], b["code"]), "bank": b, "ccy": rng.choice(CCYS), "holders": []}
        n_holders = 2 if j >= 100 else 1
        for h in range(n_holders):
            cid = f"CU-{len(master) + 1:04d}"
            hname = company(rng, names, b["country"])
            acct["holders"].append(hname)
            master.append({"iban": acct["iban"], "customer_id": cid, "name": hname, "account_ccy": acct["ccy"],
                           "status": "open"})
        (joint if n_holders == 2 else single).append(acct)
    return {"directory": directory, "banks": banks, "own_banks": own_banks, "pools": pools, "book": book,
            "master": master, "single": single, "joint": joint}


def damage(msg, defects, path, mode, source, kind=None):
    """Remove or overwrite one field and record the true value."""
    true = msg[path]
    if mode == "delete":
        del msg[path]
        kind = kind or "missing"
    elif mode == "blank":
        msg[path] = ""
        kind = kind or "blank"
    else:
        msg[path] = mode
        kind = kind or "malformed"
    defects.append((path, kind, true, source))


def make_message(recipe, k, n, w, rng):
    """One message from one recipe. Returns (message, order or None, defects)."""
    pools = w["pools"]
    debtor = rng.choice(w["single"])
    creditor = rng.choice(pools["normal"])
    pool_for = {"cdtr_bic_ambiguous": "ambiguous", "cdtr_bic_retired": "retired_only", "cdtr_bic_no_row": "no_row",
                "cdtr_bic_stale": "stale", "cdtr_ctry_foreign": "foreign"}
    if recipe in pool_for:
        creditor = rng.choice(pools[pool_for[recipe]])
    if recipe == "bic8_valid":
        creditor = rng.choice([c for c in pools["normal"] if len(c["bank"]["bic"]) == 8])
    if recipe == "cdtr_name_missing_book":
        creditor = rng.choice([c for c in pools["normal"] if c["book"] == "fresh"])
    if recipe == "cdtr_name_missing_stale_book":
        creditor = rng.choice([c for c in pools["normal"] if c["book"] == "stale"])
    if recipe in ("cdtr_name_missing_no_book", "cdtr_name_placeholder"):
        creditor = rng.choice([c for c in pools["normal"] if c["book"] == "none"])
    if recipe == "dbtr_name_joint":
        debtor = rng.choice(w["joint"])
    ccy = rng.choice(CCYS)
    if recipe == "ccy_missing":
        others = [c for c in ("EUR", "USD", "GBP", "CHF") if c != debtor["ccy"]]
        ccy = rng.choice(others) if k % 12 < 5 else debtor["ccy"]
    elif rng.randrange(10) < 6:
        ccy = debtor["ccy"]
    cents = rng.choice([rng.randint(10000, 200000), rng.randint(200000, 2000000), rng.randint(2000000, 25000000)])
    msg = {
        MSG_ID: f"M-{n:04d}", NB: "1", E2E: f"E2E-{n:05d}", UETR: uuid_like(rng), AMT: cents_text(cents), CCY: ccy,
        CHRG: rng.choice(["SHAR", "SHAR", "DEBT", "CRED", "SLEV"]),
        DBTR_NM: debtor["holders"][0], DBTR_IBAN: debtor["iban"], DBTR_BIC: debtor["bank"]["bic"],
        CDTR_NM: creditor["name"], CDTR_CTRY: creditor["ctry"], CDTR_IBAN: creditor["iban"],
        CDTR_BIC: creditor["bank"]["bic"],
        PURP: rng.choice(["SUPP", "GDDS", "TRAD"]), RMT: f"Invoice {rng.randrange(10 ** 6):06d}",
    }
    initiator = rng.choice(REVIEWER_INITIATORS) if rng.randrange(100) < 15 else rng.choice(INITIATORS)
    order = {"end_to_end_id": msg[E2E], "uetr": msg[UETR], "charge_bearer": msg[CHRG], "initiator_id": initiator}
    d = []
    mode = "delete" if k % 2 == 0 else "blank"
    if recipe == "optional_absent":
        if k % 3 in (0, 1):
            del msg[PURP]
        if k % 3 in (0, 2):
            del msg[RMT]
    elif recipe == "lookalike_name":
        msg[CDTR_NM] = LOOKALIKES[k % len(LOOKALIKES)]
    elif recipe == "nbtxs_missing":
        damage(msg, d, NB, mode, "message")
    elif recipe == "dbtr_bic_missing":
        damage(msg, d, DBTR_BIC, mode, "directory")
    elif recipe == "dbtr_name_missing":
        damage(msg, d, DBTR_NM, mode, "master")
    elif recipe == "dbtr_name_joint":
        msg[DBTR_NM] = rng.choice(debtor["holders"])
        damage(msg, d, DBTR_NM, mode, "none")
    elif recipe == "cdtr_bic_missing":
        damage(msg, d, CDTR_BIC, mode, "directory")
    elif recipe == "cdtr_bic_malformed":
        bad = [msg[CDTR_BIC][:5], msg[CDTR_BIC].lower(), msg[CDTR_BIC] + " "][k % 3]
        damage(msg, d, CDTR_BIC, bad, "directory")
    elif recipe in ("cdtr_bic_ambiguous", "cdtr_bic_retired", "cdtr_bic_no_row", "cdtr_bic_stale"):
        damage(msg, d, CDTR_BIC, mode, "none")
    elif recipe == "cdtr_ctry_missing":
        damage(msg, d, CDTR_CTRY, mode, "iban_prefix")
    elif recipe == "cdtr_ctry_foreign":
        damage(msg, d, CDTR_CTRY, mode, "none")
    elif recipe == "uetr_missing_order":
        damage(msg, d, UETR, mode, "order")
    elif recipe == "uetr_missing_no_order":
        order = None
        damage(msg, d, UETR, mode, "none")
    elif recipe == "chrgbr_missing_order":
        damage(msg, d, CHRG, mode, "order")
    elif recipe == "chrgbr_missing_no_order":
        order = None
        damage(msg, d, CHRG, mode, "none")
    elif recipe == "ccy_missing":
        damage(msg, d, CCY, mode, "none")
    elif recipe == "amount_missing":
        damage(msg, d, AMT, ["delete", "blank", "0.00"][k % 3], "none")
    elif recipe == "cdtr_name_missing_book":
        damage(msg, d, CDTR_NM, mode, "book")
    elif recipe in ("cdtr_name_missing_stale_book", "cdtr_name_missing_no_book"):
        damage(msg, d, CDTR_NM, mode, "none")
    elif recipe == "cdtr_name_placeholder":
        value = PLACEHOLDERS[k % len(PLACEHOLDERS)]
        damage(msg, d, CDTR_NM, value, "none", "blank" if value.strip() == "" else "placeholder")
    elif recipe == "cdtr_iban_missing":
        damage(msg, d, CDTR_IBAN, mode, "none")
    elif recipe == "two_holds":
        damage(msg, d, CDTR_BIC, mode, "directory")
        damage(msg, d, CDTR_CTRY, mode, "iban_prefix")
    elif recipe == "auto_and_return":
        damage(msg, d, NB, mode, "message")
        damage(msg, d, CCY, mode, "none")
    elif recipe == "bic_present_wrong":
        other = rng.choice([b for b in w["banks"] if b["kind"] == "normal" and b["bic"] != creditor["bank"]["bic"]])
        damage(msg, d, CDTR_BIC, other["bic"], "directory", "wrong")
    return msg, order, d


def build(seed=SEED):
    """All files as {name: text}. Pure: the same seed gives the same text."""
    rng = random.Random(seed)
    w = build_world(rng)
    plan = []
    for name, count, route, hardness in RECIPES:
        for k in range(count):
            plan.append((name, k, route, hardness))
    rng.shuffle(plan)
    messages, truth, defects, orders = [], [], [], []
    for n, (recipe, k, route, hardness) in enumerate(plan, start=1):
        msg, order, d = make_message(recipe, k, n, w, rng)
        messages.append(msg)
        truth.append([msg[MSG_ID], recipe, route, hardness])
        for path, kind, true, source in d:
            defects.append([msg[MSG_ID], path, kind, true, source])
        if order:
            orders.append([order["end_to_end_id"], order["uetr"], order["charge_bearer"], order["initiator_id"]])
    out = {}

    def csv_text(header, rows):
        buf = io.StringIO()
        wr = csv.writer(buf, lineterminator="\n")
        wr.writerow(header)
        wr.writerows(rows)
        return buf.getvalue()

    def json_text(items):
        return "[\n" + ",\n".join(json.dumps(m, sort_keys=True) for m in items) + "\n]\n"

    out["messages.json"] = json_text(messages)
    out["message_truth.csv"] = csv_text(["msg_id", "recipe", "intended_route", "hardness"], truth)
    out["defects_truth.csv"] = csv_text(["msg_id", "path", "kind", "true_value", "source_available"], defects)
    drows = sorted(w["directory"], key=lambda r: (r["country"], r["bank_code"], r["bic"]))
    out["bic_directory.csv"] = csv_text(["country", "bank_code", "bic", "status"],
                                        [[r["country"], r["bank_code"], r["bic"], r["status"]] for r in drows])
    mrows = sorted(w["master"], key=lambda r: (r["iban"], r["customer_id"]))
    out["customer_master.csv"] = csv_text(["iban", "customer_id", "name", "account_ccy", "status"],
                                          [[r["iban"], r["customer_id"], r["name"], r["account_ccy"], r["status"]]
                                           for r in mrows])
    out["payment_orders.csv"] = csv_text(["end_to_end_id", "uetr", "charge_bearer", "initiator_id"],
                                         sorted(orders))
    out["beneficiary_book.csv"] = csv_text(["iban", "name"], sorted([r["iban"], r["name"]] for r in w["book"]))
    out["approvers.csv"] = csv_text(["approver_id", "kind", "role", "active"], [list(a) for a in APPROVERS])
    first = {}
    for m, t in zip(messages, truth):
        first.setdefault(t[1], m)
    out["example_messages.json"] = json_text([first["dbtr_bic_missing"], first["cdtr_bic_missing"],
                                              first["cdtr_name_missing_no_book"]])
    return out


def main():
    files = build()
    for name, text in files.items():
        with open(os.path.join(HERE, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    print("Wrote", len(files), "files")


if __name__ == "__main__":
    main()
