"""Shared fixtures: a tiny in-memory world, the sample brief, and 14 golden cases."""

import copy
import json
from pathlib import Path

import _bootstrap  # noqa: F401
from agentkit.brief import derive_config, load_brief
from agentkit.kit import build_kit
from agentkit.matching import luhn_check_digit

ROOT = Path(__file__).resolve().parent.parent
BRIEF_PATH = ROOT / "briefs" / "wire_repair_agent_brief.json"


def acct(body9: str) -> str:
    return body9 + luhn_check_digit(body9)


def brief() -> dict:
    return copy.deepcopy(load_brief(BRIEF_PATH))


def config():
    return derive_config(brief())


REASON_CODES = {
    "RX01": {"code": "RX01", "description": "account number invalid", "repair_rule": "FIX_ACCOUNT",
             "field_to_correct": "beneficiary_account"},
    "RX02": {"code": "RX02", "description": "beneficiary name does not match the account", "repair_rule": "FIX_NAME",
             "field_to_correct": "beneficiary_name"},
    "RX03": {"code": "RX03", "description": "account closed", "repair_rule": "NOT_REPAIRABLE",
             "field_to_correct": ""},
    "RX04": {"code": "RX04", "description": "beneficiary bank code missing", "repair_rule": "FIX_BANK_CODE",
             "field_to_correct": "beneficiary_bank_code"},
}
BASE = "Zorvane Freight Services Ltd"
RIGHT = acct("123456789")
WRONG = RIGHT[:3] + RIGHT[4] + RIGHT[3] + RIGHT[5:]       # transposed digits: check digit fails
ZERO_ACCT = acct("012345678")


def payment(pid, name=BASE, account=None, bank="SYNB0001"):
    return {"payment_id": pid, "originator": "ORG-0001", "beneficiary_name": name,
            "beneficiary_account": account if account is not None else acct("555000111"),
            "beneficiary_bank_code": bank, "amount": "1000.00", "currency": "USD", "value_hour": -1}


def exc(case_id, ref, pid, code, returned_name=BASE, advised="", account="0000000000", hour=1, delivery=1):
    return {"case_id": case_id, "exception_ref": ref, "delivery_no": delivery, "opened_hour": hour,
            "payment_id": pid, "reason_code": code, "returned_name": returned_name, "returned_account": account,
            "advised_value": advised, "amount": "1000.00", "currency": "USD"}


# id -> (description, payment, exception, expected route, expected proposed outcome, expected state)
def golden():
    wl_name = "Kovel Trade Partners"
    g = []

    def add(gid, desc, pay, ex, route, outcome, state):
        g.append({"id": gid, "desc": desc, "payment": pay, "exception": ex, "route": route, "outcome": outcome,
                  "state": state})

    add("G01", "clean account fix", payment("P-1", account=WRONG),
        exc("G01", "EX-1", "P-1", "RX01", advised=RIGHT), "to_person", "RESUBMIT", "WAITING_S09")
    add("G02", "name style variant", payment("P-2"),
        exc("G02", "EX-2", "P-2", "RX02", returned_name="ZORVANE FREIGHT SVCS LTD.", advised="ZORVANE FREIGHT SVCS LTD."),
        "to_person", "RESUBMIT", "WAITING_S09")
    add("G03", "name typo", payment("P-3"),
        exc("G03", "EX-3", "P-3", "RX02", returned_name="Zorvane Freigth Services Ltd",
            advised="Zorvane Freigth Services Ltd"), "to_person", "RESUBMIT", "WAITING_S09")
    add("G04", "ambiguous name", payment("P-4"),
        exc("G04", "EX-4", "P-4", "RX02", returned_name="Zorvane Freight Group Ltd",
            advised="Zorvane Freight Group Ltd"), "to_person", "DEFER_TO_PERSON", "WAITING_S07")
    add("G05", "unrelated name", payment("P-5"),
        exc("G05", "EX-5", "P-5", "RX02", returned_name="Quillax Marine Systems Inc",
            advised="Quillax Marine Systems Inc"), "auto", "RETURN_TO_ORIGINATOR", "CLOSED")
    add("G06", "closed account", payment("P-6"), exc("G06", "EX-6", "P-6", "RX03"), "auto",
        "RETURN_TO_ORIGINATOR", "CLOSED")
    add("G07", "missing bank code", payment("P-7", bank=""),
        exc("G07", "EX-7", "P-7", "RX04", advised="SYNB4242"), "to_person", "RESUBMIT", "WAITING_S09")
    add("G08", "watch-list hit", payment("P-8", name=wl_name),
        exc("G08", "EX-8", "P-8", "RX01", returned_name=wl_name, advised=RIGHT), "to_person",
        "ESCALATE_COMPLIANCE", "ESCALATED")
    add("G09", "malformed: blank payment id", payment("P-9"), exc("G09", "EX-9", "", "RX01", advised=RIGHT),
        "human_queue", "HUMAN_QUEUE", "QUEUED_HUMAN")
    add("G10", "malformed: unknown reason code", payment("P-10"), exc("G10", "EX-10", "P-10", "RX99"),
        "human_queue", "HUMAN_QUEUE", "QUEUED_HUMAN")
    add("G11", "malformed: orphan payment id", payment("P-11"), exc("G11", "EX-11", "P-99999", "RX01", advised=RIGHT),
        "human_queue", "HUMAN_QUEUE", "QUEUED_HUMAN")
    add("G12", "malformed: advised account has letters", payment("P-12", account=WRONG),
        exc("G12", "EX-12", "P-12", "RX01", advised="12AB-??9"), "human_queue", "HUMAN_QUEUE", "QUEUED_HUMAN")
    add("G13", "duplicate delivery of G01", payment("P-1", account=WRONG),
        exc("G13", "EX-1", "P-1", "RX01", advised=RIGHT), "auto", "DUPLICATE_CLOSED", "CLOSED_DUPLICATE")
    add("G14", "leading-zero account on a name fix", payment("P-14", account=ZERO_ACCT),
        exc("G14", "EX-14", "P-14", "RX02", returned_name="ZORVANE FREIGHT SVCS LTD.",
            advised="ZORVANE FREIGHT SVCS LTD."), "to_person", "RESUBMIT", "WAITING_S09")
    return g


def tiny_world(cases=None):
    cases = cases or golden()
    payments = {}
    exceptions = []
    for c in cases:
        payments[c["payment"]["payment_id"]] = c["payment"]
        exceptions.append(c["exception"])
    watch = [{"party_id": "W-001", "name": "Kovel Trade Partners", "list_code": "SYN-A", "added_hour": -1},
             {"party_id": "W-002", "name": "Ompra Holding Group Ltd", "list_code": "SYN-B", "added_hour": -1}]
    return {"cases": exceptions, "payments": payments, "reason_codes": REASON_CODES, "watchlist": watch}


def kit(mode="shadow", cases=None, **kw):
    w = tiny_world(cases)
    return build_kit(w, brief(), mode=mode, **kw), w


def event_kinds(k, case_id):
    return [e["kind"] for e in k.audit.events(case_id)]
