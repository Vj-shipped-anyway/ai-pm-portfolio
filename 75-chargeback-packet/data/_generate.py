"""Generate the synthetic data for project 75: 100 merchant dispute cases, each with a packet of
evidence documents, plus the evidence list (rules.json) the checker reads.

Everything is seeded, so the files are byte-for-byte reproducible. The evidence list, the response
windows and the page limit are invented for this prototype (assumptions, not any card network's
rules). The truth label of each case comes from the fault that was planted into a good packet,
not from the checker. Three kinds of case are hard on purpose:
  hard negatives  packets that look short or late but are fine: the second option of an either-or
                  item, a partial dispute, a packet sent on the last day, a draft due today, an
                  extra document that is on no list
  hard misses     packets whose metadata is perfect and whose files are wrong: a document that
                  belongs to another case, an unreadable scan. The checker reads labels, dates,
                  references, amounts and page counts, so it cannot see these.
The same author wrote this recipe table and the checker's rules, so a result on this data is a
ceiling for the rules, not a rate on real disputes.

Run (from data/):  python3 _generate.py
Writes:  rules.json, cases.json, case_truth.csv, as_of.txt, example_case.json
"""
from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta

rng = random.Random(75)
AS_OF = date(2026, 3, 31)
MAX_PAGES = 12
POST_PURCHASE = ["delivery_signature", "delivery_tracking", "digital_access_log", "refund_record"]
AMOUNT_TYPES = ["billing_history", "order_record"]


def slot(sid, label, accept, required):
    return {"id": sid, "label": label, "accept": accept, "required": required}


RULES = {
    "version": "synthetic-1",
    "note": "Invented for this prototype. These are not any card network's reason codes, lists or deadlines.",
    "max_pages": MAX_PAGES,
    "after_purchase_types": POST_PURCHASE,
    "amount_types": AMOUNT_TYPES,
    "reason_codes": {
        "RC-01": {"name": "Unauthorized transaction", "window_days": 20, "slots": [
            slot("order", "order record", ["order_record"], True),
            slot("auth", "authorization log", ["payment_auth_log"], True),
            slot("link", "link to the cardholder", ["device_match", "prior_orders"], True),
            slot("comms", "customer messages", ["customer_comms"], False)]},
        "RC-02": {"name": "Goods or services not received", "window_days": 30, "slots": [
            slot("order", "order record", ["order_record"], True),
            slot("delivery", "delivery proof", ["delivery_tracking", "digital_access_log"], True),
            slot("signature", "signed receipt", ["delivery_signature"], False),
            slot("comms", "customer messages", ["customer_comms"], False)]},
        "RC-03": {"name": "Not as described", "window_days": 30, "slots": [
            slot("order", "order record", ["order_record"], True),
            slot("listing", "listing as shown at purchase", ["product_description"], True),
            slot("policy", "return policy", ["return_policy"], True),
            slot("comms", "customer messages", ["customer_comms"], False)]},
        "RC-04": {"name": "Duplicate charge", "window_days": 14, "slots": [
            slot("order", "order record", ["order_record"], True),
            slot("ledger", "ledger of distinct charges", ["duplicate_ledger"], True),
            slot("refund", "refund record", ["refund_record"], False)]},
        "RC-05": {"name": "Refund not processed", "window_days": 21, "slots": [
            slot("order", "order record", ["order_record"], True),
            slot("outcome", "refund record or return policy", ["refund_record", "return_policy"], True),
            slot("comms", "customer messages", ["customer_comms"], False)]},
        "RC-06": {"name": "Cancelled subscription", "window_days": 30, "slots": [
            slot("billing", "billing history", ["billing_history"], True),
            slot("terms", "cancellation terms", ["cancellation_terms"], True),
            slot("cancel_log", "cancellation request log", ["cancel_request_log"], True),
            slot("comms", "customer messages", ["customer_comms"], False)]},
    },
}

# What a good packet holds for each code: groups of either-or document types that must be there, and
# types that may be there. Written separately from the slots above so a mistake in one shows up as a
# false alarm on a good packet.
GOOD = {
    "RC-01": ([["order_record"], ["payment_auth_log"], ["device_match", "prior_orders"]], ["customer_comms"]),
    "RC-02": ([["order_record"], ["delivery_tracking", "digital_access_log"]], ["delivery_signature", "customer_comms"]),
    "RC-03": ([["order_record"], ["product_description"], ["return_policy"]], ["customer_comms"]),
    "RC-04": ([["order_record"], ["duplicate_ledger"]], ["refund_record"]),
    "RC-05": ([["order_record"], ["refund_record", "return_policy"]], ["customer_comms"]),
    "RC-06": ([["billing_history"], ["cancellation_terms"], ["cancel_request_log"]], ["customer_comms"]),
}
CODES = sorted(GOOD)

QUOTA = [("ready_plain", "ready", 17), ("ready_alt_branch", "ready", 8), ("ready_partial", "ready", 5),
         ("ready_on_deadline", "ready", 5), ("ready_draft", "ready", 5), ("ready_extra_doc", "ready", 3),
         ("missing_required", "defective", 10), ("wrong_ref", "defective", 6), ("amount_short", "defective", 5),
         ("dated_before_purchase", "defective", 5), ("dated_in_future", "defective", 3), ("too_many_pages", "defective", 5),
         ("content_mismatch", "defective", 6), ("unreadable_scan", "defective", 3),
         ("late_submitted", "late", 7), ("late_draft", "late", 4), ("late_and_incomplete", "late", 3)]
SUBMITTED = {"ready_plain", "ready_partial", "ready_on_deadline", "late_submitted", "late_and_incomplete"}
INVISIBLE = {"content_mismatch", "unreadable_scan"}


def iso(d):
    return d.isoformat()


def order_id():
    return "O-%06d" % rng.randint(100000, 999999)


def doc_date(dtype, txn, received):
    if dtype in ("delivery_tracking", "delivery_signature", "digital_access_log"):
        return txn + timedelta(days=rng.randint(1, 9))
    if dtype == "refund_record":
        return txn + timedelta(days=rng.randint(2, 9))
    if dtype == "customer_comms":
        return txn + timedelta(days=rng.randint(1, 9))
    if dtype == "cancellation_terms":
        return txn - timedelta(days=rng.randint(30, 200))
    if dtype in ("duplicate_ledger", "cancel_request_log"):
        return received - timedelta(days=rng.randint(1, 3))
    return txn


def pick_code(kind):
    if kind == "ready_alt_branch":
        return rng.choice(["RC-01", "RC-02", "RC-05"])
    if kind == "dated_before_purchase":
        return rng.choice(["RC-02", "RC-05"])
    return rng.choice(CODES)


def timing(kind, n, window):
    """(received, submitted or None) for one case."""
    if kind in SUBMITTED:
        received = AS_OF - timedelta(days=window + 10 + rng.randint(0, 90))
        due = received + timedelta(days=window)
        if kind == "ready_on_deadline":
            return received, due
        if kind.startswith("late"):
            return received, due + timedelta(days=rng.randint(1, 10))
        return received, received + timedelta(days=rng.randint(1, window))
    if kind == "ready_draft":
        days_left = 0 if n < 2 else rng.randint(1, 12)
    elif kind == "late_draft":
        days_left = -rng.randint(1, 15)
    else:
        days_left = rng.randint(1, 14)
    return AS_OF - timedelta(days=window - days_left), None


def build(kind, n, case_id):
    code = pick_code(kind)
    window = RULES["reason_codes"][code]["window_days"]
    must, may = GOOD[code]
    second = kind == "ready_alt_branch"
    types = [opts[-1] if second else opts[0] for opts in must] + [t for t in may if rng.random() < 0.5]
    received, submitted = timing(kind, n, window)
    txn = received - timedelta(days=rng.randint(10, 60))
    amount = rng.randint(2500, 180000)
    stated = amount
    if kind == "ready_partial":
        stated = amount + rng.randint(1000, 20000)
    if kind == "amount_short":
        stated = amount - rng.randint(100, 2000)
    oid = order_id()
    docs = []
    for k, dtype in enumerate(types, 1):
        d = {"doc_id": "%s-D%d" % (case_id, k), "doc_type": dtype, "ref_id": oid,
             "doc_date": iso(doc_date(dtype, txn, received)), "pages": rng.randint(1, 2)}
        if dtype in AMOUNT_TYPES:
            d["amount_cents"] = stated
        docs.append(d)
    if kind == "ready_extra_doc":
        docs.append({"doc_id": "%s-D%d" % (case_id, len(docs) + 1), "doc_type": "shipping_label", "ref_id": oid,
                     "doc_date": iso(txn + timedelta(days=1)), "pages": 1})
    if kind in ("missing_required", "late_and_incomplete"):
        group = rng.choice(must)
        docs = [d for d in docs if d["doc_type"] not in group]
    if kind == "wrong_ref":
        rng.choice(docs)["ref_id"] = order_id()
    if kind == "dated_before_purchase":
        post = [d for d in docs if d["doc_type"] in POST_PURCHASE]
        post[0]["doc_date"] = iso(txn - timedelta(days=rng.randint(1, 20)))
    if kind == "dated_in_future":
        rng.choice(docs)["doc_date"] = iso(AS_OF + timedelta(days=rng.randint(1, 10)))
    if kind == "too_many_pages":
        k = rng.randrange(len(docs))
        others = sum(d["pages"] for i, d in enumerate(docs) if i != k)
        docs[k]["pages"] = MAX_PAGES - others + rng.randint(1, 6)
    return {"case_id": case_id, "reason_code": code, "order_id": oid, "txn_date": iso(txn), "received_date": iso(received),
            "amount_cents": amount, "submitted_date": iso(submitted) if submitted else "", "docs": docs}


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def dump(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.write("\n")


def main():
    plan = [(kind, cls, n) for kind, cls, count in QUOTA for n in range(count)]
    rng.shuffle(plan)
    cases, truth = [], []
    for i, (kind, cls, n) in enumerate(plan, 1):
        case_id = "CB-%04d" % i
        cases.append(build(kind, n, case_id))
        truth.append([case_id, kind, cls, "no" if kind in INVISIBLE else "yes"])
    dump("rules.json", RULES)
    dump("cases.json", cases)
    write_csv("case_truth.csv", ["case_id", "planted_kind", "truth_class", "visible_in_metadata"], truth)
    with open("as_of.txt", "w", encoding="utf-8") as fh:
        fh.write(iso(AS_OF) + "\n")
    # the worked example behind `python3 chargeback_packet.py --demo`: a not-received dispute with no delivery proof
    dump("example_case.json", {
        "case_id": "CB-DEMO", "reason_code": "RC-02", "order_id": "O-482910", "txn_date": "2026-01-10",
        "received_date": "2026-02-02", "amount_cents": 12900, "submitted_date": "",
        "docs": [
            {"doc_id": "CB-DEMO-D1", "doc_type": "order_record", "ref_id": "O-482910", "doc_date": "2026-01-10", "pages": 1, "amount_cents": 12900},
            {"doc_id": "CB-DEMO-D2", "doc_type": "customer_comms", "ref_id": "O-482910", "doc_date": "2026-01-15", "pages": 2}]})
    print("wrote %d cases" % len(cases))


if __name__ == "__main__":
    main()
