"""Small builders shared by the tests: a clean record, a usage row and a way to read findings."""
import datetime

AS_OF = datetime.date(2026, 9, 30)


def days_ago(n: int) -> datetime.date:
    return AS_OF - datetime.timedelta(days=n)


def rec(**over) -> dict:
    """A clean generative production record at tier 2. Pass a key with the value DROP to remove it."""
    r = {"system_id": "AI-1", "name": "Test assistant", "kind": "generative", "status": "production",
         "business_owner": "OWN-01", "technical_owner": "TECH-01", "risk_tier": 2, "purpose": "Answers test questions.",
         "provider_type": "vendor_api", "model_id": "vendor-a-large-2026-03", "data_class": "internal",
         "customer_facing": "no", "last_reviewed": days_ago(30).isoformat(),
         "evaluation_ref": "EV-1000", "last_evaluated": days_ago(40).isoformat()}
    r.update(over)
    return {k: v for k, v in r.items() if v is not DROP}


def agent(**over) -> dict:
    base = {"kind": "agentic", "tools": ["get_x", "put_y"], "permission_scope": "read_write", "human_approval": "on_exception"}
    base.update(over)
    return rec(**base)


class _Drop:
    def __repr__(self):
        return "DROP"


DROP = _Drop()


def use(system_id="AI-1", model="vendor-a-large-2026-03", first=100, last=1, calls=10) -> dict:
    """A usage row; first and last are days before the as-of date."""
    return {"system_id": system_id, "model_id": model, "first_seen": days_ago(first), "last_seen": days_ago(last), "calls": calls}


def kinds(findings) -> list:
    return sorted(f["kind"] for f in findings)
