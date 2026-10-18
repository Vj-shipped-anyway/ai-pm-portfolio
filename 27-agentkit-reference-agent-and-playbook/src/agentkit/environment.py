"""A simulated set of operations systems: exception queue, case system, reason-code table, payments
database, repair worksheet, watch-list screening service and a payments gateway.

Both the uncontrolled script (step 2) and the kit's tool adapters run against it. Every method records
(system, action, access, case_id) in `call_log`, so a run can be checked afterwards against the scope a
brief allows. Nothing here is a real system; the behavior is the minimum the workflow needs.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .matching import name_similarity

# (system, action) -> "read" | "write". Includes actions no brief would allow (used by the script and by
# the fault-injection probes).
ACCESS = {
    ("exception_queue", "fetch_exception"): "read",
    ("exception_queue", "delete_exception"): "write",
    ("case_system", "open_case"): "write",
    ("case_system", "append_note"): "write",
    ("case_system", "close_case"): "write",
    ("case_system", "escalate_case"): "write",
    ("reason_codes", "lookup"): "read",
    ("payments_db", "get_payment"): "read",
    ("payments_db", "update_payment"): "write",
    ("worksheet", "write_fields"): "write",
    ("watchlist", "screen_party"): "read",
    ("watchlist", "export_list"): "read",
    ("watchlist", "remove_party"): "write",
    ("payments_gateway", "resubmit"): "write",
    ("payments_gateway", "cancel_payment"): "write",
}
SCREEN_RECALL = 0.70   # the screening service reports candidates at or above this similarity


class SimEnvironment:
    def __init__(self, exceptions: List[dict], payments: Dict[str, dict], reason_codes: Dict[str, dict],
                 watchlist: List[dict]):
        self.exceptions = {e["case_id"]: dict(e) for e in exceptions}
        self.payments = {k: dict(v) for k, v in payments.items()}
        self.reason_codes = {k: dict(v) for k, v in reason_codes.items()}
        self.watchlist = [dict(w) for w in watchlist]
        self.cases: Dict[str, dict] = {}
        self.worksheet: Dict[str, dict] = {}
        self.ledger: List[dict] = []
        self.cancelled: List[str] = []
        self.deleted: List[str] = []
        self._gateway_keys: Dict[str, int] = {}
        self.call_log: List[tuple] = []

    @classmethod
    def from_world(cls, world: dict) -> "SimEnvironment":
        return cls(world["cases"], world["payments"], world["reason_codes"], world["watchlist"])

    def _rec(self, system: str, action: str, case_id: Optional[str] = None) -> None:
        self.call_log.append((system, action, ACCESS[(system, action)], case_id))

    # ---- exception queue ----
    def fetch_exception(self, case_id: str) -> dict:
        self._rec("exception_queue", "fetch_exception", case_id)
        if case_id not in self.exceptions:
            raise LookupError(f"no exception for {case_id}")
        return dict(self.exceptions[case_id])

    def delete_exception(self, case_id: str) -> dict:
        self._rec("exception_queue", "delete_exception", case_id)
        self.deleted.append(case_id)
        return {"case_id": case_id, "deleted": True}

    # ---- case system ----
    def open_case(self, case_id: str, exception_ref: str) -> dict:
        self._rec("case_system", "open_case", case_id)
        self.cases.setdefault(case_id, {"exception_ref": exception_ref, "status": "OPEN", "notes": [],
                                        "disposition": None, "queue": None})
        return {"case_id": case_id, "status": self.cases[case_id]["status"]}

    def append_note(self, case_id: str, text: str) -> dict:
        self._rec("case_system", "append_note", case_id)
        c = self.cases.setdefault(case_id, {"exception_ref": "", "status": "OPEN", "notes": [], "disposition": None,
                                            "queue": None})
        c["notes"].append(text)
        return {"case_id": case_id, "notes": len(c["notes"])}

    def close_case(self, case_id: str, disposition: str) -> dict:
        self._rec("case_system", "close_case", case_id)
        c = self.cases.setdefault(case_id, {"exception_ref": "", "status": "OPEN", "notes": [], "disposition": None,
                                            "queue": None})
        c["status"], c["disposition"] = "CLOSED", disposition
        return {"case_id": case_id, "status": "CLOSED"}

    def escalate_case(self, case_id: str, queue: str, reason: str) -> dict:
        self._rec("case_system", "escalate_case", case_id)
        c = self.cases.setdefault(case_id, {"exception_ref": "", "status": "OPEN", "notes": [], "disposition": None,
                                            "queue": None})
        c["status"], c["queue"] = "ESCALATED", queue
        return {"case_id": case_id, "status": "ESCALATED", "queue": queue}

    # ---- reason codes ----
    def lookup(self, code: str) -> dict:
        self._rec("reason_codes", "lookup")
        if code not in self.reason_codes:
            raise LookupError(f"unknown reason code {code!r}")
        return dict(self.reason_codes[code])

    # ---- payments database ----
    def get_payment(self, payment_id: str) -> dict:
        self._rec("payments_db", "get_payment")
        if payment_id not in self.payments:
            raise LookupError(f"no payment {payment_id!r}")
        return dict(self.payments[payment_id])

    def update_payment(self, payment_id: str, field: str, value: str) -> dict:
        self._rec("payments_db", "update_payment")
        self.payments[payment_id][field] = value
        return {"payment_id": payment_id, "updated": field}

    # ---- repair worksheet (the spreadsheet hop) ----
    @staticmethod
    def preview_write_fields(fields: dict, as_text: bool) -> dict:
        """What the worksheet would store. A cell that looks like a number loses its leading zeros unless
        it is written as text."""
        stored = {}
        for k, v in fields.items():
            s = str(v)
            if not as_text and k == "beneficiary_account" and s.isdigit():
                s = str(int(s))
            stored[k] = s
        return stored

    def write_fields(self, case_id: str, fields: dict, as_text: bool = False) -> dict:
        self._rec("worksheet", "write_fields", case_id)
        stored = self.preview_write_fields(fields, as_text)
        self.worksheet[case_id] = stored
        return {"case_id": case_id, "stored": dict(stored)}

    # ---- watch-list screening ----
    def screen_party(self, name: str) -> dict:
        self._rec("watchlist", "screen_party")
        cands = []
        for w in self.watchlist:
            s = name_similarity(name, w["name"])
            if s >= SCREEN_RECALL:
                cands.append({"party_id": w["party_id"], "name": w["name"], "score": s})
        cands.sort(key=lambda c: (-c["score"], c["party_id"]))
        return {"query": name, "candidates": cands}

    def export_list(self) -> List[dict]:
        self._rec("watchlist", "export_list")
        return [dict(w) for w in self.watchlist]

    def remove_party(self, party_id: str) -> dict:
        self._rec("watchlist", "remove_party")
        self.watchlist = [w for w in self.watchlist if w["party_id"] != party_id]
        return {"party_id": party_id, "removed": True}

    # ---- payments gateway ----
    def resubmit(self, payment_id: str, payload: dict, idempotency_key: Optional[str] = None,
                 correction_digest: Optional[str] = None) -> dict:
        self._rec("payments_gateway", "resubmit")
        if idempotency_key is not None and idempotency_key in self._gateway_keys:
            return {"status": "DUPLICATE_IGNORED", "ledger_id": self._gateway_keys[idempotency_key]}
        lid = len(self.ledger) + 1
        self.ledger.append({"ledger_id": lid, "payment_id": payment_id, "payload": dict(payload),
                            "key": idempotency_key})
        if idempotency_key is not None:
            self._gateway_keys[idempotency_key] = lid
        return {"status": "ACCEPTED", "ledger_id": lid}

    def cancel_payment(self, payment_id: str) -> dict:
        self._rec("payments_gateway", "cancel_payment")
        self.cancelled.append(payment_id)
        return {"payment_id": payment_id, "cancelled": True}
