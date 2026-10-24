"""Small builders shared by the tests."""


def doc(doc_id, dtype, when="2026-01-10", ref="O-1", pages=1, **kw):
    d = {"doc_id": doc_id, "doc_type": dtype, "ref_id": ref, "doc_date": when, "pages": pages}
    d.update(kw)
    return d


def base():
    """RC-02, window 30 days from 2026-02-02, so due 2026-03-04."""
    return {"case_id": "T-1", "reason_code": "RC-02", "order_id": "O-1", "txn_date": "2026-01-10", "received_date": "2026-02-02",
            "amount_cents": 12900, "submitted_date": "",
            "docs": [doc("a", "order_record", amount_cents=12900), doc("b", "delivery_tracking", "2026-01-14")]}
