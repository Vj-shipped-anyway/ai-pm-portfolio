"""
Step 1 - Before SwapBrief: decide on the overall average.

A vendor has announced that model A, the model behind a bank's customer-service
GenAI feature, will be deprecated. The team runs its evaluation set on the
successor, model B, with a prompt it retuned for B. It compares one number: the
overall average score. Higher means GO.

All results here are SIMULATED. data/_generate.py is a seeded stub that stands
in for real evaluation runs. No model is called and nothing in this repo
measures any real model, vendor or bank.

Run (standard library only, Python 3.9):
    python step_01_headline_average.py

Output: prints the decision and writes src/out/step_01_results.json.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

SYSTEMS = ("A", "B_old_prompt", "B_new_prompt")
CANDIDATE = "B_new_prompt"   # model B with the prompt retuned for B


# ---------------------------------------------------------------------------
# Loading (shared by every later step)
# ---------------------------------------------------------------------------
def _num(text: str):
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    return text


def load_dataset(data_dir: Path = DATA_DIR) -> dict:
    """Read the committed CSVs into columnar lists (items keep their file order)."""
    with open(data_dir / "slices.csv", newline="") as f:
        slices = []
        for r in csv.DictReader(f):
            slices.append({"slice": r["slice"], "severity": r["severity"],
                           "tol": int(r["tolerance_pp"]) / 100.0, "n_items": int(r["n_items"]),
                           "description": r["description"]})
    s_index = {s["slice"]: i for i, s in enumerate(slices)}

    with open(data_dir / "eval_items.csv", newline="") as f:
        items = list(csv.DictReader(f))
    item_pos = {r["item_id"]: i for i, r in enumerate(items)}
    n = len(items)

    cols = {s: {"correct": [0] * n, "tin": [0] * n, "tout": [0] * n, "lat": [0] * n, "ref": [0] * n}
            for s in SYSTEMS}
    with open(data_dir / "eval_results.csv", newline="") as f:
        for r in csv.DictReader(f):
            i = item_pos[r["item_id"]]
            c = cols[r["system"]]
            c["correct"][i] = int(r["correct"])
            c["tin"][i] = int(r["input_tokens"])
            c["tout"][i] = int(r["output_tokens"])
            c["lat"][i] = int(r["latency_ms"])
            c["ref"][i] = int(r["refusal"])

    with open(data_dir / "prices.csv", newline="") as f:
        prices = {r["model_id"]: {"in": float(r["input_usd_per_1k_tokens"]),
                                  "out": float(r["output_usd_per_1k_tokens"])} for r in csv.DictReader(f)}
    with open(data_dir / "models.csv", newline="") as f:
        models = {r["system"]: r for r in csv.DictReader(f)}
    with open(data_dir / "policy.csv", newline="") as f:
        policy = {r["parameter"]: _num(r["value"]) for r in csv.DictReader(f)}

    return {
        "slices": slices,
        "slice_idx": [s_index[r["slice"]] for r in items],
        "should_refuse": [int(r["should_refuse"]) for r in items],
        "item_ids": [r["item_id"] for r in items],
        "cols": cols,
        "prices": prices,
        "model_of": {k: v["model_id"] for k, v in models.items()},
        "models": models,
        "policy": policy,
    }


# ---------------------------------------------------------------------------
# The headline rule
# ---------------------------------------------------------------------------
def overall_accuracy(ds: dict, system: str) -> float:
    c = ds["cols"][system]["correct"]
    return sum(c) / len(c)


def headline_rule(ds: dict, system: str = CANDIDATE) -> dict:
    """GO if B's overall average is higher than A's. Nothing else is looked at."""
    n = len(ds["slice_idx"])
    ok_a = sum(ds["cols"]["A"]["correct"])
    ok_b = sum(ds["cols"][system]["correct"])
    delta = (ok_b - ok_a) / n
    return {
        "system": system,
        "n_items": n,
        "n_slices": len(ds["slices"]),
        "correct_a": ok_a,
        "correct_b": ok_b,
        "acc_a": ok_a / n,
        "acc_b": ok_b / n,
        "delta": delta,
        "decision": "GO" if delta > 0 else "NO-GO",
        "rollback_triggers": [],
    }


def run() -> dict:
    ds = load_dataset()
    return headline_rule(ds)


def main() -> None:
    res = run()
    print("\n" + "=" * 80)
    print("Step 1 - Before SwapBrief: decide on the overall average")
    print("=" * 80)
    print("SIMULATED results from a seeded generator (data/_generate.py). No model was called.\n")
    print("Situation: the vendor will deprecate model A. Model B is the successor, run with a")
    print("prompt retuned for B. The team compares one number, the overall average.\n")
    print("Items scored:                %d across %d slices" % (res["n_items"], res["n_slices"]))
    print("Model A accuracy:            %5.1f%%  (%d / %d)" % (res["acc_a"] * 100, res["correct_a"], res["n_items"]))
    print("Model B accuracy:            %5.1f%%  (%d / %d)" % (res["acc_b"] * 100, res["correct_b"], res["n_items"]))
    print("Headline change:             %+.1f percentage points" % (res["delta"] * 100))
    print("Decision rule:               GO if B's overall average is higher than A's")
    print("\nDECISION: %s" % res["decision"])
    print("\nWhat this decision contains:")
    print("  per-slice results:         none")
    print("  cost per correct answer:   not looked at")
    print("  p50 / p95 latency:         not looked at")
    print("  rollback triggers:         %d defined (metric, threshold, window all absent)" % len(res["rollback_triggers"]))

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_01_results.json", "w") as f:
        json.dump(res, f, indent=2)
    print("\nwrote src/out/step_01_results.json")


if __name__ == "__main__":
    main()
