"""Shared loading and scoring for the four step scripts of project 73."""
import csv
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

import iso20022_map_check as tool  # noqa: E402

ROW_KINDS = ("dropped", "truncated", "altered")
CONVERTER = ("converter", "capacity")
# planted defect (the generator's word) -> the finding kind the checker is expected to raise
CHECKER_KIND = {"cut_early": "truncated", "drop_field": "dropped", "cond_drop": "dropped", "amount_round": "altered",
                "date_swap": "altered", "strip_zeros": "altered", "lines_swapped": "altered", "capacity_cut": "truncated"}
# planted mapping footprint -> the finding kind that shows it in a pair
FOOTPRINT_KIND = {"unmapped_lost": "unmapped_lost", "generated_value": "untraced", "code_fallback": "code_unmapped"}


def bundle() -> dict:
    return tool.load_bundle(DATA)


def _json(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def _csv(name) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def all_pairs() -> list:
    """One pair per (build, legacy message): 10 builds x 20 typical messages and 3 boundary probes."""
    messages, outputs = _json("legacy_messages.json"), _json("iso_outputs.json")
    return [{"build": b, "msg": m, "probe": m.startswith("P"), "source": messages[m], "target": outputs[b][m]}
            for b in sorted(outputs) for m in sorted(outputs[b])]


def builds() -> list:
    return _csv("builds.csv")


def mapping_truth() -> list:
    return _csv("mapping_truth.csv")


def truth_events() -> dict:
    out = {}
    for r in _csv("truth_events.csv"):
        out.setdefault((r["build"], r["msg"]), []).append((r["subject"], r["kind"], r["category"]))
    return out


def findings_of(pairs, bun) -> dict:
    """{(build, msg): findings} from the full checker."""
    return {(p["build"], p["msg"]): tool.check_pair(p["source"], p["target"], bun) for p in pairs}


def row_flags(findings) -> set:
    return {(f["subject"], f["kind"]) for f in findings if f["kind"] in ROW_KINDS}


def score(pairs, truth, flags) -> Counter:
    """Compare what a method flagged with the planted converter and capacity events, by element.
    flags: {(build, msg): set of (element, kind)}. Benign variations are not defects."""
    r = Counter()
    for p in pairs:
        key = (p["build"], p["msg"])
        events = truth.get(key, [])
        planted = {s for s, _k, c in events if c in CONVERTER}
        benign = {s for s, _k, c in events if c == "benign"} - planted
        flagged = {s for s, _k in flags[key]}
        r["pairs"] += 1
        r["events"] += len(planted)
        r["found"] += len(planted & flagged)
        r["false_alarms"] += len(flagged - planted)
        r["false_alarm_pairs"] += 1 if flagged - planted else 0
        r["benign"] += len(benign)
        r["benign_flagged"] += len(benign & flagged)
        r["defective_pairs"] += 1 if planted else 0
        r["defective_caught"] += 1 if planted & flagged else 0
    return r


def detected_builds(blds, pairs, flags) -> set:
    """Builds whose planted defect shows up as the expected kind of finding at the planted element."""
    need = {b["build"]: (b["iso_path"], CHECKER_KIND[b["defect"]]) for b in blds if b["defect"] != "none"}
    return {p["build"] for p in pairs if p["build"] in need and need[p["build"]] in flags[(p["build"], p["msg"])]}


def static_score(static, truth_rows) -> tuple:
    """(planted found, planted, hard negatives flagged, hard negatives) for the mapping-only findings."""
    got = {(f["kind"], f["subject"]) for f in static if f["severity"] == "error"}
    planted = {(r["kind"], r["subject"]) for r in truth_rows if r["planted"] == "yes"}
    negatives = {(r["kind"], r["subject"]) for r in truth_rows if r["planted"] == "no"}
    return len(planted & got), len(planted), len(negatives & got), len(negatives)


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
