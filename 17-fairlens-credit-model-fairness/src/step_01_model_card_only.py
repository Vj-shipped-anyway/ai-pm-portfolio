"""Step 1 - Before FairLens: the model card reports one number.

A modeled bank scores credit applicants with a points scorecard and approves everyone at or
above a fixed cutoff. The model card reports overall accuracy (and the overall approval
rate). That is all a reviewer is given.

THE MODEL IS A STUB, NOT A TRAINED MODEL. It is a hand-written points scorecard
(data/scorecard_points.csv). The points were set by hand and never fitted to this data. It
gives points for postcode_band, and that is the planted flaw. No machine-learning model is
used anywhere in this repo.

The outcome is known because the data is synthetic: data/_generate.py decided who defaulted
(from income, dti, history, utilization and delinquency only). Nothing here is a real bank,
applicant, postcode or model. The group labels are synthetic and encode no real protected
class.

ASSUMPTIONS (policy constants of a modeled bank, not legal advice; edit them below):
  P1  the cutoff is a fixed policy constant: approve when score >= POLICY_CUTOFF
  P2  a decision is "correct" when it agrees with the outcome: approve and no default, or
      decline and default. Accuracy is the share of correct decisions.

Run (from src/):
    python3 step_01_model_card_only.py

Output: a readable summary, plus out/step_01_model_card.json.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

POLICY_CUTOFF = 190        # P1: approve when the score is at or above this many points
GROUPS = ["Group A", "Group B", "Group C"]
BASELINE_TESTS_RUN = 0     # by definition: nothing on the model card is split by group


# ---------------------------------------------------------------------------
# Shared loaders and the stub scorecard (later steps and the app import these)
# ---------------------------------------------------------------------------
def load_scorecard(data_dir: Path = DATA_DIR) -> dict:
    """Return {'components': [names in file order], 'buckets': {component: [rows]}, 'max': {...}}."""
    buckets: dict = {}
    order = []
    with open(data_dir / "scorecard_points.csv", newline="") as f:
        for r in csv.DictReader(f):
            c = r["component"]
            if c not in buckets:
                buckets[c] = []
                order.append(c)
            buckets[c].append({
                "bucket": r["bucket"],
                "low": float(r["low"]) if r["low"] != "" else None,
                "high": float(r["high"]) if r["high"] != "" else None,
                "points": int(r["points"]),
            })
    reasons = {}
    with open(data_dir / "reason_codes.csv", newline="") as f:
        for r in csv.DictReader(f):
            reasons[r["component"]] = {"code": r["reason_code"], "text": r["plain_language"]}
    return {"components": order, "buckets": buckets,
            "max": {c: max(b["points"] for b in buckets[c]) for c in order},
            "reasons": reasons}


def load_applicants(data_dir: Path = DATA_DIR) -> list:
    rows = []
    with open(data_dir / "applicants.csv", newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "applicant_id": r["applicant_id"], "group": r["group"], "income": int(r["income"]),
                "dti": float(r["dti"]), "history_months": int(r["history_months"]),
                "utilization": float(r["utilization"]), "prior_delinq": int(r["prior_delinq"]),
                "postcode_band": r["postcode_band"], "defaulted": int(r["defaulted"]),
            })
    return rows


def component_points(applicant: dict, card: dict) -> dict:
    """Points earned on each scorecard component."""
    out = {}
    for comp in card["components"]:
        value = applicant[comp]
        for b in card["buckets"][comp]:
            if comp == "postcode_band":
                hit = b["bucket"] == value
            else:
                hit = value >= b["low"] and (b["high"] is None or value < b["high"])
            if hit:
                out[comp] = b["points"]
                break
    return out


def prepare(data_dir: Path = DATA_DIR) -> dict:
    """Load everything and score every applicant once. This is the object later steps share."""
    card = load_scorecard(data_dir)
    rows = load_applicants(data_dir)
    for a in rows:
        a["points"] = component_points(a, card)
        a["score"] = sum(a["points"].values())
    n_pb = sum(a["points"]["postcode_band"] for a in rows)
    return {"card": card, "rows": rows, "by_id": {a["applicant_id"]: a for a in rows},
            "mean_postcode_points": int(round(n_pb / len(rows)))}


def approved(score: int, cutoff: int = POLICY_CUTOFF) -> bool:
    return score >= cutoff


def correct(a: dict, is_approved: bool) -> bool:
    """P2: approve-and-repaid, or decline-and-defaulted."""
    return is_approved == (a["defaulted"] == 0)


def rate(num: int, den: int) -> float:
    return num / den if den else 0.0


def model_card(prep: dict, cutoff: int = POLICY_CUTOFF) -> dict:
    rows = prep["rows"]
    n = len(rows)
    n_app = sum(1 for a in rows if approved(a["score"], cutoff))
    n_ok = sum(1 for a in rows if correct(a, approved(a["score"], cutoff)))
    return {"applicants": n, "cutoff": cutoff, "approved": n_app, "correct": n_ok,
            "approval_rate": rate(n_app, n), "accuracy": rate(n_ok, n),
            "defaults": sum(a["defaulted"] for a in rows),
            "max_points": sum(prep["card"]["max"].values())}


def default_rates(prep: dict) -> dict:
    """The outcome the generator decided, by group (the truth the pack is scored against)."""
    out = {}
    for g in GROUPS:
        gr = [a for a in prep["rows"] if a["group"] == g]
        d = sum(a["defaulted"] for a in gr)
        out[g] = {"n": len(gr), "defaulted": d, "rate": rate(d, len(gr))}
    return out


def postcode_mix(prep: dict) -> dict:
    """Share of each group's applicants in each postcode band (the planted correlation)."""
    out = {}
    for g in GROUPS:
        gr = [a for a in prep["rows"] if a["group"] == g]
        out[g] = {b: rate(sum(1 for a in gr if a["postcode_band"] == b), len(gr))
                  for b in ("P1", "P2", "P3", "P4", "P5")}
    return out


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    prep = prepare()
    card = prep["card"]
    m = model_card(prep)

    print("\n" + "=" * 78)
    print("Step 1 - Before FairLens: the model card reports one number")
    print("=" * 78)
    print(f"\n{m['applicants']:,} synthetic applicants, scored by a hand-written points scorecard.")
    print("The scorecard is a stub, not a trained model. No model is used anywhere in this repo.")
    print("Data is synthetic and seeded. The generator decided who defaulted, so the outcome is known.\n")
    print("ASSUMPTIONS (policy constants of a modeled bank, not legal advice):")
    print(f"  P1  approve when score >= {POLICY_CUTOFF} points (maximum possible {m['max_points']})")
    print("  P2  a decision is correct when it agrees with the outcome; accuracy = share correct\n")

    print("THE SCORECARD (points available per component)")
    print(f"  {'component':<16} {'max points':>10}  reason code")
    for c in card["components"]:
        print(f"  {c:<16} {card['max'][c]:>10}  {card['reasons'][c]['code']} {card['reasons'][c]['text']}")

    print("\nFIRST THREE APPLICANTS (score = sum of component points)")
    for a in prep["rows"][:3]:
        parts = ", ".join(f"{c} {a['points'][c]}" for c in card["components"])
        verdict = "approve" if approved(a["score"]) else "decline"
        print(f"  {a['applicant_id']} score {a['score']:>3} -> {verdict:<7} defaulted {a['defaulted']}  ({parts})")

    print("\nTHE OUTCOME (known because the generator decided it; the model card does not show it by group)")
    for g, d in default_rates(prep).items():
        print(f"  {g}: {d['n']:,} applicants, {d['defaulted']:,} defaulted ({100 * d['rate']:.1f}%)")

    print("\nTHE PROXY (postcode band mix, share of each group's applicants; P1 is the best band)")
    for g, mix in postcode_mix(prep).items():
        print(f"  {g}: " + ", ".join(f"{b} {100 * v:.1f}%" for b, v in mix.items()))

    print("\nMODEL CARD (the only numbers a reviewer is given)")
    print(f"  Overall accuracy:      {m['correct']:,} of {m['applicants']:,} decisions correct ({100 * m['accuracy']:.1f}%)")
    print(f"  Overall approval rate: {m['approved']:,} of {m['applicants']:,} applicants approved ({100 * m['approval_rate']:.1f}%)")
    print("  By group:              nothing. No number on the card is split by group.")
    print(f"  Fairness tests run:    {BASELINE_TESTS_RUN}")

    with open(OUT_DIR / "step_01_model_card.json", "w") as f:
        json.dump(dict(m, default_rates=default_rates(prep)), f, indent=2)
    print("\nWrote src/out/step_01_model_card.json")


if __name__ == "__main__":
    main()
