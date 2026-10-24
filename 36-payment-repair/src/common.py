"""Shared loading for the four step scripts of project 36, the plain presence check that stands for the
status quo, and the script that stands for the common basic approach (steps 2 and 3)."""
from __future__ import annotations

import csv
import json
import os

from payment_repair import (CCY, CDTR_BIC, CDTR_CTRY, CDTR_IBAN, CDTR_NM, CHRG, DBTR_BIC, DBTR_IBAN, DBTR_NM, E2E, NB,
                            OPTIONAL, PURP, REQUIRED, RMT, UETR, classify, load_refs)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")


def read_rows(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_messages() -> list:
    with open(os.path.join(DATA, "messages.json"), encoding="utf-8") as fh:
        return json.load(fh)


def load_truth() -> tuple:
    """({msg_id: row of message_truth.csv}, {msg_id: [defect rows]}). The answer key; no tool reads it."""
    msgs = {r["msg_id"]: r for r in read_rows("message_truth.csv")}
    defects = {}
    for r in read_rows("defects_truth.csv"):
        defects.setdefault(r["msg_id"], []).append(r)
    return msgs, defects


def load_world() -> dict:
    """The reference tables as the repair tool reads them, plus the raw rows the basic script reads in file order."""
    refs = load_refs(DATA)
    return {"refs": refs, "directory_rows": read_rows("bic_directory.csv"), "book": {r["iban"]: r["name"] for r in read_rows("beneficiary_book.csv")}}


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------- the status quo
def presence_rejects(msg: dict) -> list:
    """What a downstream hop checks today: a required field is absent or an empty string."""
    return [p for p in REQUIRED if (msg.get(p) or "") == ""]


# ---------------------------------------------------------------- the common basic approach
def _uuid_like(rng) -> str:
    h = "%032x" % rng.getrandbits(128)
    return f"{h[:8]}-{h[8:12]}-4{h[13:16]}-8{h[17:20]}-{h[20:32]}"


def basic_fill(msg: dict, world: dict, rng) -> tuple:
    """One script that fills every empty field from the first table that has a value, and releases the message.

    It stands for the usual first version; what it gets wrong is a property of this script. It fills a field
    when the value is falsy, takes the first matching row without checking status or uniqueness, defaults
    where no table answers, and also completes the optional fields. Returns (new message, [paths it wrote]).
    """
    out, wrote = dict(msg), []
    refs = world["refs"]

    def first_bic(iban):
        code = (iban or "")[4:12]
        for r in world["directory_rows"]:
            if r["bank_code"] == code:
                return r["bic"]
        return None

    for p in REQUIRED + OPTIONAL:
        if out.get(p):
            continue
        order = refs["orders"].get(out.get(E2E) or "", [None])[0]
        master = refs["master"].get(out.get(DBTR_IBAN) or "", [None])[0]
        if p == NB:
            v = "1"
        elif p == UETR:
            v = order["uetr"] if order else _uuid_like(rng)
        elif p == CCY:
            v = master["account_ccy"] if master else "EUR"
        elif p == CHRG:
            v = order["charge_bearer"] if order else "SHAR"
        elif p == DBTR_NM:
            v = master["name"] if master else None
        elif p == DBTR_BIC:
            v = first_bic(out.get(DBTR_IBAN))
        elif p == CDTR_BIC:
            v = first_bic(out.get(CDTR_IBAN))
        elif p == CDTR_NM:
            v = world["book"].get(out.get(CDTR_IBAN) or "")
        elif p == CDTR_CTRY:
            v = (out.get(CDTR_IBAN) or "")[:2] or None
        elif p == PURP:
            v = "OTHR"
        elif p == RMT:
            v = "NOTPROVIDED"
        else:
            v = None            # amounts, account numbers and the end-to-end id have no table
        if v:
            out[p] = v
            wrote.append(p)
    return out, wrote


# ---------------------------------------------------------------- scoring against the answer key
def value_status(path: str, original, final, true: str) -> str:
    """For one planted defect: correct, filled_wrong (changed to a wrong value), left_unusable (still missing,
    blank, a placeholder or malformed) or wrong_untouched (present, well-formed and wrong)."""
    if final == true:
        return "correct"
    if final != original:
        return "filled_wrong"
    return "left_unusable" if classify(path, original) else "wrong_untouched"


def defect_status(by_id: dict, finals: dict, defects: dict) -> dict:
    """{(msg_id, path): status} for every planted defect, comparing the final message with the answer key."""
    out = {}
    for mid, ds in defects.items():
        for d in ds:
            out[(mid, d["path"])] = value_status(d["path"], by_id[mid].get(d["path"]), finals[mid].get(d["path"]), d["true_value"])
    return out
