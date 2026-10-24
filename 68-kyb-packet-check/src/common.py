"""Shared loading for the four step scripts of project 68."""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from kyb_packet_check import DEFAULT_TOLERANCE, FAMILIES, beneficial_owners, check_parsed, name_key, parse_extraction  # noqa: E402


def _rows(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_packets() -> list:
    """The 75 packets: filing text, the model's extraction, and the planted truth."""
    source = {r["packet_id"]: r["source_text"] for r in _rows("packets.csv")}
    extraction = {r["packet_id"]: json.loads(r["extraction_json"]) for r in _rows("extractions.csv")}
    packets = []
    for t in _rows("truth.csv"):
        true_owners = {name_key(n) for n in t["true_beneficial_owners"].split("; ") if n} | {name_key(t["true_control_person"])}
        packets.append({"packet_id": t["packet_id"], "entity": t["entity"], "scenario": t["scenario"], "defect": int(t["defect"]),
                        "detail": t["planted_detail"], "source": source[t["packet_id"]], "raw": extraction[t["packet_id"]],
                        "true_owners": true_owners})
    return packets


def owners_in_file(raw: dict) -> set:
    """The people the file would list as beneficial owners if the extraction were accepted as read."""
    ex = parse_extraction(raw)
    keys = {name_key(n) for n, _ in beneficial_owners(ex)}
    if ex["control_person"] and ex["control_person"]["name"]:
        keys.add(name_key(ex["control_person"]["name"]))
    return keys


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def run_checks(packets: list, families: tuple = FAMILIES, tolerance: float = DEFAULT_TOLERANCE) -> dict:
    """{packet_id: findings} from the tool, with the chosen families and tolerance."""
    return {p["packet_id"]: check_parsed(p["source"], parse_extraction(p["raw"]), tolerance, families) for p in packets}


def tally(packets: list, flagged: set) -> dict:
    """Score a set of flagged packet ids against the planted truth."""
    bad = [p for p in packets if p["defect"]]
    good = [p for p in packets if not p["defect"]]
    wrong = [p for p in packets if owners_in_file(p["raw"]) != p["true_owners"]]
    return {"misreads": len(bad), "misreads_flagged": sum(1 for p in bad if p["packet_id"] in flagged),
            "clean": len(good), "clean_flagged": sum(1 for p in good if p["packet_id"] in flagged),
            "wrong_people": len(wrong), "wrong_people_flagged": sum(1 for p in wrong if p["packet_id"] in flagged)}


def print_tally(t: dict) -> None:
    print(f"    misreads flagged: {t['misreads_flagged']} of {t['misreads']}")
    print(f"    clean packets flagged: {t['clean_flagged']} of {t['clean']}")
    print(f"    packets that would list the wrong people, flagged: {t['wrong_people_flagged']} of {t['wrong_people']}")


def by_scenario(packets: list, flagged: set) -> dict:
    """{scenario: (flagged, total)} in name order."""
    out = {}
    for p in sorted(packets, key=lambda p: p["scenario"]):
        a, b = out.get(p["scenario"], (0, 0))
        out[p["scenario"]] = (a + (p["packet_id"] in flagged), b + 1)
    return out
