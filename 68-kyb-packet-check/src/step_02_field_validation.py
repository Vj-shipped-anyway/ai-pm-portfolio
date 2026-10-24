"""Step 2 - The common basic approach: validate the shape of the extraction.

The first thing a team adds after a model extraction is a schema check: every field the form needs
is present and has the right type, the control person is there, the certification is signed. This
step runs that check, with no look at the filing, and scores it against the planted truth.

Run (from src/):  python3 step_02_field_validation.py
"""
from __future__ import annotations

from collections import Counter

from common import load_packets, owners_in_file, print_tally, tally


def shape_problems(raw: dict) -> list:
    """What a schema validator can see: required fields present and non-empty. No arithmetic, no filing."""
    out = []
    if not str(raw.get("legal_name") or "").strip():
        out.append("legal_name")
    for h in raw["holders"]:
        if not (str(h.get("name") or "").strip() and h.get("kind") and isinstance(h.get("pct"), (int, float))):
            out.append("holder row")
    for p in raw.get("people") or []:
        out += [f"person.{f}" for f in ("name", "address", "dob", "id_last4") if not str(p.get(f) or "").strip()]
    if not (raw.get("control_person") or {}).get("name"):
        out.append("control_person")
    cert = raw.get("certification") or {}
    out += [f"certification.{f}" for f in ("signed_by", "date") if not str(cert.get(f) or "").strip()]
    return out


def main() -> None:
    packets = load_packets()
    flagged = {p["packet_id"] for p in packets if shape_problems(p["raw"])}
    t = tally(packets, flagged)
    passing = [p for p in packets if p["defect"] and p["packet_id"] not in flagged]
    wrong_pass = [p for p in passing if owners_in_file(p["raw"]) != p["true_owners"]]
    print("STEP 2 (step_02_field_validation.py) - validate the shape of the extraction")
    print(f"  packets flagged: {len(flagged)} of {len(packets)}")
    print_tally(t)
    print(f"  misreads that pass as well-formed: {len(passing)} of {t['misreads']}")
    print(f"  of those, packets that would list the wrong people: {len(wrong_pass)}")
    print("  passing misreads by planted kind: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(p["scenario"] for p in passing).items())))
    print("  A percent read as 2.5 instead of 25 is a well-formed number, so no field is empty and nothing is flagged.")


if __name__ == "__main__":
    main()
