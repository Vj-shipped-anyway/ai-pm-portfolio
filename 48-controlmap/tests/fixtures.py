"""Small CSV fixtures shared by the tests."""
import csv
import datetime
import os

AS_OF = datetime.date(2026, 6, 30)
OB_HEADER = ["obligation_id", "theme", "statement", "applies_to"]
CT_HEADER = ["control_id", "name", "description", "owner", "scope", "test_cycle_days", "last_evidence_on", "status"]
TERMS_HEADER = ["theme", "phrase"]


def write(folder, name, header, rows):
    path = os.path.join(folder, name)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


def days_ago(n):
    return (AS_OF - datetime.timedelta(days=n)).isoformat()


def control(cid="CT-1", name="Override log", desc="Every override is recorded.", scope="credit_decision", cycle=100, age=10, status="active", owner="Owner A"):
    return [cid, name, desc, owner, scope, cycle, "" if age is None else days_ago(age), status]
