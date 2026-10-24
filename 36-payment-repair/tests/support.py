"""Small fixtures shared by the tests: one complete message and the four reference tables around it."""
import copy

import _bootstrap  # noqa: F401
import payment_repair as pr

DEBTOR_IBAN = "DE00900000011234567890"
CREDITOR_IBAN = "FR00900000020987654321"
UETR_OK = "11111111-2222-4333-8444-555555555555"

GOOD = {
    pr.MSG_ID: "M-1", pr.NB: "1", pr.E2E: "E2E-1", pr.UETR: UETR_OK, pr.AMT: "100.50", pr.CCY: "EUR", pr.CHRG: "SHAR",
    pr.DBTR_NM: "Debtor Co GmbH", pr.DBTR_IBAN: DEBTOR_IBAN, pr.DBTR_BIC: "AAAADEFFXXX",
    pr.CDTR_NM: "Creditor Co SARL", pr.CDTR_CTRY: "FR", pr.CDTR_IBAN: CREDITOR_IBAN, pr.CDTR_BIC: "BBBBFR22XXX",
    pr.PURP: "SUPP", pr.RMT: "Invoice 1",
}


def msg(**changes):
    """A complete message with the given paths replaced; a value of None deletes the path."""
    m = copy.deepcopy(GOOD)
    for k, v in changes.items():
        path = getattr(pr, k)
        if v is None:
            m.pop(path, None)
        else:
            m[path] = v
    return m


def refs(directory=None, master=None, orders=None, approvers=None):
    d = [{"country": "DE", "bank_code": "90000001", "bic": "AAAADEFFXXX", "status": "active"},
         {"country": "FR", "bank_code": "90000002", "bic": "BBBBFR22XXX", "status": "active"}] if directory is None else directory
    m = [{"iban": DEBTOR_IBAN, "customer_id": "CU-1", "name": "Debtor Co GmbH", "account_ccy": "EUR", "status": "open"}] \
        if master is None else master
    o = [{"end_to_end_id": "E2E-1", "uetr": UETR_OK, "charge_bearer": "SHAR", "initiator_id": "U-2001"}] if orders is None else orders
    a = [{"approver_id": "U-1041", "kind": "person", "role": "payments_reviewer", "active": "yes"},
         {"approver_id": "U-1042", "kind": "person", "role": "payments_reviewer", "active": "yes"},
         {"approver_id": "U-1044", "kind": "person", "role": "payments_reviewer", "active": "no"},
         {"approver_id": "U-2001", "kind": "person", "role": "payments_initiator", "active": "yes"},
         {"approver_id": "A-7001", "kind": "agent", "role": "repair_agent", "active": "yes"}] if approvers is None else approvers
    return pr.build_refs(d, m, o, a)


def approval(result, approver="U-1041", decision="approve", digest=None, msg_id=None):
    return {"msg_id": msg_id or result["msg_id"], "plan_digest": digest or result["digest"], "approver_id": approver,
            "decision": decision}
