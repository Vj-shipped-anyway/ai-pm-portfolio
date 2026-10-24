"""One small packet used by the unit tests: text, and a correct extraction of it."""
import copy

SOURCE = """Test Harbor Supply LLC
Entity type: Limited liability company, formed in Ohio. Application dated 2026-03-02.

Ownership of the customer (membership interests):
Dana A. Whitfield (individual) holds 60% of the membership interests.
Tomas Reyes (individual) holds 25% of the membership interests.
Priya Nair (individual) holds 15% of the membership interests.

Individuals named in this packet:
Person: Dana A. Whitfield | DOB 1981-05-14 | 412 Oak Street, Fairview OH 43215 | ID ending 4821
Person: Tomas Reyes | DOB 1975-11-02 | 9 Elm Road, Lakeside TX 75001 | ID ending 0415

Control person: Dana A. Whitfield, Managing Member.
Certification: I certify that the information above is accurate. Signed by Dana A. Whitfield, Managing Member, on 2026-03-02.
"""

EXTRACTION = {
    "packet_id": "T-1", "legal_name": "Test Harbor Supply LLC",
    "holders": [{"name": "Dana A. Whitfield", "kind": "individual", "pct": 60},
                {"name": "Tomas Reyes", "kind": "individual", "pct": 25},
                {"name": "Priya Nair", "kind": "individual", "pct": 15}],
    "lookthrough": [],
    "people": [{"name": "Dana A. Whitfield", "address": "412 Oak Street, Fairview OH 43215", "dob": "1981-05-14", "id_last4": "4821"},
               {"name": "Tomas Reyes", "address": "9 Elm Road, Lakeside TX 75001", "dob": "1975-11-02", "id_last4": "0415"}],
    "control_person": {"name": "Dana A. Whitfield", "title": "Managing Member"},
    "certification": {"signed_by": "Dana A. Whitfield", "date": "2026-03-02"},
}

ENTITY_SOURCE = """Test Harbor Supply LLC
Entity type: Limited liability company, formed in Ohio. Application dated 2026-03-02.

Ownership of the customer (membership interests):
Dana A. Whitfield (individual) holds 15% of the membership interests.
Hollis Park Holdings Ltd (entity) holds 40% of the membership interests.
Tomas Reyes (individual) holds 45% of the membership interests.
Look-through: Dana A. Whitfield holds 50% of Hollis Park Holdings Ltd.
Look-through: Priya Nair holds 50% of Hollis Park Holdings Ltd.

Individuals named in this packet:
Person: Dana A. Whitfield | DOB 1981-05-14 | 412 Oak Street, Fairview OH 43215 | ID ending 4821
Person: Tomas Reyes | DOB 1975-11-02 | 9 Elm Road, Lakeside TX 75001 | ID ending 0415

Control person: Tomas Reyes, President.
Certification: I certify that the information above is accurate. Signed by Tomas Reyes, President, on 2026-03-02.
"""

ENTITY_EXTRACTION = {
    "packet_id": "T-2", "legal_name": "Test Harbor Supply LLC",
    "holders": [{"name": "Dana A. Whitfield", "kind": "individual", "pct": 15},
                {"name": "Hollis Park Holdings Ltd", "kind": "entity", "pct": 40},
                {"name": "Tomas Reyes", "kind": "individual", "pct": 45}],
    "lookthrough": [{"entity": "Hollis Park Holdings Ltd", "name": "Dana A. Whitfield", "pct": 50},
                    {"entity": "Hollis Park Holdings Ltd", "name": "Priya Nair", "pct": 50}],
    "people": EXTRACTION["people"],
    "control_person": {"name": "Tomas Reyes", "title": "President"},
    "certification": {"signed_by": "Tomas Reyes", "date": "2026-03-02"},
}


def fresh(obj=None):
    return copy.deepcopy(EXTRACTION if obj is None else obj)
